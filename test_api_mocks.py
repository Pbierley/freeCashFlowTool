import unittest
import requests
import requests_mock
import pandas as pd
from unittest.mock import patch, MagicMock
from streamlit_app import ( # IMPORTANT: Replace 'your_script_name'
    get_stock_info, 
    get_income_statement, 
    get_historical_chart
) 

# Define mock data structures that resemble the actual API responses
MOCK_FMP_QUOTE_DATA = [{
    "symbol": "TSLA",
    "name": "Tesla Inc.",
    "price": 900.00,
    "mktCap": 900000000000,
    "changes": 10.50
}]

MOCK_POLYGON_HISTORICAL_DATA = {
    "ticker": "TSLA",
    "status": "OK",
    "resultsCount": 3,
    "results": [
        {"t": 1609459200000, "c": 705.67}, # Jan 1, 2021
        {"t": 1609545600000, "c": 725.32}, # Jan 2, 2021
        {"t": 1609632000000, "c": 710.00}, # Jan 3, 2021
    ]
}

MOCK_FMP_INCOME_DATA = [{
    "date": "2024-12-31",
    "revenue": 1000000,
    "epsDiluted": 5.00
}]

class TestApiMocking(unittest.TestCase):
    
    # Setup variables needed for tests
    def setUp(self):
        self.ticker = "TSLA"
        self.fmp_key = "FAKE_FMP_KEY"
        self.polygon_key = "FAKE_POLYGON_KEY"
    
    # Helper to clear Streamlit's cache after each test to ensure isolation
    def tearDown(self):
        get_stock_info.clear()
        get_income_statement.clear()
        get_historical_chart.clear()

    # --- Test FMP Stock Info (Success and Params) ---
    def test_get_stock_info_success(self):
        """Test successful FMP profile data retrieval."""
        with requests_mock.Mocker() as m:
            # Mock the exact URL with the expected parameters
            m.get(
                f"https://financialmodelingprep.com/stable/profile?symbol={self.ticker}&apikey={self.fmp_key}",
                json=MOCK_FMP_QUOTE_DATA, 
                status_code=200
            )
            
            result = get_stock_info(self.ticker, self.fmp_key)
            self.assertEqual(result[0]['symbol'], self.ticker)
            self.assertEqual(result[0]['price'], 900.00)

    def test_get_stock_info_http_error(self):
        """Test API function handling of non-200 HTTP status codes."""
        with requests_mock.Mocker() as m:
            m.get(
                f"https://financialmodelingprep.com/stable/profile?symbol={self.ticker}&apikey={self.fmp_key}",
                status_code=404
            )
            # The function should raise an exception due to requests.raise_for_status()
            with self.assertRaises(requests.HTTPError):
                get_stock_info(self.ticker, self.fmp_key)
                
    # --- Test FMP Income Statement (Caching) ---
    def test_get_income_statement_caching(self):
        """Test that the cache decorator prevents redundant API calls."""
        with requests_mock.Mocker() as m:
            # Mock the request and track how many times it's called
            mock_url = f"https://financialmodelingprep.com/stable/income-statement?symbol={self.ticker}"
            m.get(mock_url, json=MOCK_FMP_INCOME_DATA, status_code=200)

            # 1. First call (should hit the mock API)
            get_income_statement(self.ticker, self.fmp_key)
            
            # 2. Second call (should hit the cache, not the mock API again)
            get_income_statement(self.ticker, self.fmp_key)
            
            # Check that the mock endpoint was called only once
            history = m.request_history
            self.assertEqual(len(history), 1, "The API was called more than once, indicating caching failed.")

    # --- Test Polygon Historical Chart Data ---
    @patch('your_script_name.datetime') # Mock datetime to control start/end dates
    def test_get_historical_chart_success(self, mock_dt):
        """Test successful Polygon data retrieval and parameter formatting."""
        
        # Set a fixed 'now' for date calculation validation
        mock_dt.now.return_value = pd.Timestamp("2025-10-10")
        mock_dt.now.strftime.side_effect = lambda format: "2025-10-10"
        mock_dt.now.return_value.__sub__.return_value.strftime.side_effect = lambda format: "2020-10-10"

        with requests_mock.Mocker() as m:
            # Construct the expected URL with fixed dates
            expected_url = f"https://api.polygon.io/v2/aggs/ticker/{self.ticker}/range/1/day/2020-10-10/2025-10-10"
            m.get(expected_url, json=MOCK_POLYGON_HISTORICAL_DATA, status_code=200)
            
            result = get_historical_chart(self.ticker, self.polygon_key)
            self.assertEqual(result['ticker'], self.ticker)
            self.assertEqual(result['resultsCount'], 3)
            
            # Verify the API key was passed as a query parameter
            self.assertIn(f"apiKey={self.polygon_key}", m.request_history[0].url)


if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)