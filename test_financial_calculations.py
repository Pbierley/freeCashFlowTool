import unittest
import pandas as pd
from streamlit_app import calculate_cagr, get_cagr_for_metric # Replace 'your_script_name' with the actual file name

class TestFinancialCalculations(unittest.TestCase):

    # --- Test calculate_cagr function ---
    def test_cagr_positive_growth(self):
        # 100 -> 200 over 5 years
        start = 100
        end = 200
        years = 5
        # Expected CAGR: ((200/100)^(1/5) - 1) * 100 = 14.87%
        self.assertAlmostEqual(calculate_cagr(start, end, years), 14.869835, places=5)

    def test_cagr_negative_growth(self):
        # 200 -> 100 over 5 years
        start = 200
        end = 100
        years = 5
        # Expected CAGR: ((100/200)^(1/5) - 1) * 100 = -12.94%
        self.assertAlmostEqual(calculate_cagr(start, end, years), -12.942994, places=5)

    def test_cagr_no_growth(self):
        # 100 -> 100 over 1 year
        start = 100
        end = 100
        years = 1
        self.assertAlmostEqual(calculate_cagr(start, end, years), 0.0, places=5)

    def test_cagr_invalid_input(self):
        # Zero values
        self.assertIsNone(calculate_cagr(0, 100, 5))
        self.assertIsNone(calculate_cagr(100, 0, 5))
        # Zero years
        self.assertIsNone(calculate_cagr(100, 200, 0))
        # Negative values
        self.assertIsNone(calculate_cagr(100, -200, 5))

    # --- Test get_cagr_for_metric function ---
    def test_get_cagr_for_metric_success(self):
        # Data from Year 1 (oldest) to Year 5 (latest)
        data = {
            'date': ['2020-12-31', '2021-12-31', '2022-12-31', '2023-12-31', '2024-12-31'],
            'metric': [100, 110, 120, 130, 150]
        }
        df = pd.DataFrame(data).sort_values('date') # Must be sorted oldest to newest

        # 1Y CAGR: (150/130)^(1/1) - 1 = 15.38%
        # 2Y CAGR: (150/120)^(1/2) - 1 = 11.80%
        # 3Y CAGR: (150/110)^(1/3) - 1 = 11.87%
        # 5Y CAGR: (150/100)^(1/5) - 1 = 8.45%
        
        cagrs = get_cagr_for_metric(df, 'metric')
        
        self.assertIn("1Y", cagrs)
        self.assertIn("2Y", cagrs)
        self.assertIn("3Y", cagrs)
        self.assertIn("5Y", cagrs)
        
        self.assertAlmostEqual(float(cagrs["1Y"].strip('%')), 15.38, places=2)
        self.assertAlmostEqual(float(cagrs["2Y"].strip('%')), 11.80, places=2)
        self.assertAlmostEqual(float(cagrs["3Y"].strip('%')), 11.87, places=2)
        self.assertAlmostEqual(float(cagrs["5Y"].strip('%')), 8.45, places=2)

    def test_get_cagr_for_metric_insufficient_data(self):
        # Only 3 years of data available (cannot calculate 5Y CAGR)
        data = {
            'date': ['2022-12-31', '2023-12-31', '2024-12-31'],
            'metric': [100, 110, 120]
        }
        df = pd.DataFrame(data).sort_values('date')

        cagrs = get_cagr_for_metric(df, 'metric')
        
        self.assertIn("1Y", cagrs)
        self.assertIn("2Y", cagrs)
        self.assertNotIn("3Y", cagrs) # Needs 4 periods
        self.assertNotIn("5Y", cagrs)

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)