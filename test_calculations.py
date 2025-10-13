import unittest
import pandas as pd
from datetime import datetime
# --- ADDED IMPORTS ---
import os 
from dotenv import load_dotenv
# ---------------------
# Import the class definition
from financial_data_processor import FinancialDataProcessor 

class TestPureCalculations(unittest.TestCase):
    
    def setUp(self):
        """
        Instantiates the FinancialDataProcessor class before each test method runs.
        This ensures the 'processor' instance is defined (fixing the NameError) 
        and ready for method-level tests.
        """
        # Define 'self.processor' inside setUp
        
        # This code now runs correctly because 'load_dotenv' and 'os' are imported.
        load_dotenv()
        FMP_API_KEY = os.getenv("FMP_API_KEY")
        POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")
        
        # We use fake keys here because these are PURE calculation tests 
        # that shouldn't actually hit the API. However, if they *do* run, 
        # using the real keys from the .env file is fine.
        # For true isolation, you'd use placeholder strings:
        # self.processor = FinancialDataProcessor("FAKE_FMP", "FAKE_POLY")
        self.processor = FinancialDataProcessor(FMP_API_KEY, POLYGON_API_KEY)

    # --- Test calculate_cagr (Static Method) ---
    
    def test_cagr_positive_growth(self):
        """Tests CAGR calculation for positive growth."""
        # Access the static method directly via the class name
        result = FinancialDataProcessor.calculate_cagr(100, 200, 5)
        self.assertAlmostEqual(result, 14.869835, places=5)

    def test_cagr_negative_growth(self):
        """Tests CAGR calculation for negative growth."""
        result = FinancialDataProcessor.calculate_cagr(200, 100, 5)
        self.assertAlmostEqual(result, -12.942994, places=5)

    def test_cagr_invalid_input(self):
        """Tests CAGR handling of zero or negative inputs."""
        self.assertIsNone(FinancialDataProcessor.calculate_cagr(0, 100, 5))
        self.assertIsNone(FinancialDataProcessor.calculate_cagr(100, 200, 0))
        self.assertIsNone(FinancialDataProcessor.calculate_cagr(100, -200, 5))

    # --- Test _prepare_financial_df (Helper Method) ---
    
    def test_prepare_financial_df_sorting_and_dates(self):
        """Verifies raw data is converted to a sorted DataFrame with datetime objects."""
        raw_data = [
            {'date': '2022-12-31', 'value': 100},
            {'date': '2024-12-31', 'value': 300},
            {'date': '2023-12-31', 'value': 200},
        ]
        # Use the instantiated processor
        df = self.processor._prepare_financial_df(raw_data)
        
        # Verify sorting (oldest first, newest last)
        self.assertEqual(df.iloc[0]['value'], 100)
        self.assertEqual(df.iloc[-1]['value'], 300)
        
        # Verify date type conversion
        self.assertTrue(pd.api.types.is_datetime64_any_dtype(df['date']))
        
    def test_prepare_financial_df_empty_data(self):
        """Verifies empty input returns an empty DataFrame."""
        df = self.processor._prepare_financial_df([])
        self.assertTrue(df.empty)

    # --- Test calculate_cagrs (Method) ---
    
    def test_calculate_cagrs_success(self):
        """Tests CAGR calculation over multiple periods for a valid DataFrame."""
        data = {
            'date': ['2020-12-31', '2021-12-31', '2022-12-31', '2023-12-31', '2024-12-31'],
            'metric': [100, 110, 120, 130, 150]
        }
        df = pd.DataFrame(data).sort_values('date') 

        cagrs = self.processor.calculate_cagrs(df, 'metric')
        
        self.assertIn("1Y", cagrs)
        self.assertIn("3Y", cagrs)
        self.assertAlmostEqual(float(cagrs["1Y"].strip('%')), 15.38, places=2)
        self.assertAlmostEqual(float(cagrs["3Y"].strip('%')), 11.87, places=2)

    def test_calculate_cagrs_insufficient_data(self):
        """Tests that CAGR returns are limited when insufficient data exists."""
        # Only 3 periods of data available (cannot calculate 3Y or 5Y CAGR)
        data = {
            'date': ['2022-12-31', '2023-12-31', '2024-12-31'],
            'metric': [100, 110, 120]
        }
        df = pd.DataFrame(data).sort_values('date')

        cagrs = self.processor.calculate_cagrs(df, 'metric', periods=[1, 2, 3, 5])
        
        self.assertIn("1Y", cagrs)
        self.assertIn("2Y", cagrs)
        self.assertNotIn("3Y", cagrs) 
        self.assertNotIn("5Y", cagrs)


if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)