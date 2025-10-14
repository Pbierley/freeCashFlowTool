import unittest
import requests
import requests_mock
import os
from dotenv import load_dotenv
from unittest.mock import patch, MagicMock
from financial_data_processor import APIClient

# Instantiate the processor class once

load_dotenv()
FMP_API_KEY = os.getenv("FMP_API_KEY")
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")

processor = APIClient(FMP_API_KEY, POLYGON_API_KEY)

# Define mock data structures
MOCK_STOCK_INFO = [{"symbol": "TSLA", "price": 900.00, "mktCap": 900000000000}]
MOCK_INCOME_DATA = [{"date": "2024-12-31", "revenue": 1000000}]
MOCK_POLYGON_DATA = {"ticker": "TSLA", "status": "OK", "results": [{"t": 1609459200000, "c": 705.67}]}


class TestApiMocking(unittest.TestCase):

    # --- Mocking the generic _fetch_data method ---
    
    @patch('financial_data_processor.FinancialDataProcessor._fetch_data')
    def test_get_stock_info_success(self, mock_fetch):
        """Test successful stock info retrieval via mocked internal fetch."""
        mock_fetch.return_value = MOCK_STOCK_INFO
        
        result = processor.get_stock_info("TSLA")
        
        # Verify the mock fetch was called correctly
        mock_fetch.assert_called_once()
        self.assertEqual(result[0]['price'], 900.00)

    @patch('financial_data_processor.FinancialDataProcessor._fetch_data')
    def test_get_income_statement_params(self, mock_fetch):
        """Test that the income statement method passes correct parameters."""
        mock_fetch.return_value = MOCK_INCOME_DATA
        
        processor.get_income_statement("AAPL", period="quarter", limit=10)
        
        # Check that the internal fetch was called with the correct endpoint and parameters
        mock_fetch.assert_called_once_with(
            "income-statement", "AAPL", "FAKE_FMP_KEY",
            params={"period": "quarter", "limit": 10}
        )

    # --- Testing Error Handling (requires requests_mock for low-level mocking) ---
    
    def test_api_http_error_handling(self):
        """Test that the API functions correctly raise HTTPError."""
        
        # Use requests_mock to simulate a 404 response on the low-level API call
        with requests_mock.Mocker() as m:
            m.get(
                requests_mock.ANY,  # Mock any URL
                status_code=404
            )
            # Ensure the public facing method raises the expected exception
            with self.assertRaises(requests.HTTPError):
                processor.get_stock_info("BADTICKER")
                
    # --- Test Data Transformation (FCF Yield Calculation) ---
    def test_calculate_derived_metrics_fcf_yield(self):
        """Verifies derived metrics like FCF Yield are calculated correctly."""
        
        # Mock data for FCF and SBC (sorted by date)
        mock_cashflow_data = pd.DataFrame({
            'date': [datetime(2023, 12, 31), datetime(2024, 12, 31)],
            'freeCashFlow': [1000, 2000],
            'stockBasedCompensation': [100, 200],
        })
        
        data_dict = {'income_df': pd.DataFrame(), 'cashflow_df': mock_cashflow_data}
        market_cap = 100000 # $100k
        price = 100 # Placeholder
        
        result = processor.calculate_derived_metrics(data_dict, market_cap, price)
        df = result['cashflow_df']
        
        # 1. Verify FCF - SBC calculation
        # 1000 - 100 = 900
        # 2000 - 200 = 1800
        self.assertEqual(df.iloc[0]['fcf_minus_sbc'], 900)
        self.assertEqual(df.iloc[1]['fcf_minus_sbc'], 1800)

        # 2. Verify FCF Yield calculation
        # (900 / 100000) * 100 = 0.9%
        # (1800 / 100000) * 100 = 1.8%
        self.assertAlmostEqual(df.iloc[0]['fcf_yield'], 0.9, places=2)
        self.assertAlmostEqual(df.iloc[1]['fcf_yield'], 1.8, places=2)

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)