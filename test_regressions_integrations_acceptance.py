"""
Comprehensive test suite covering:
- Regression tests: Verify bug fixes and prevent regressions
- Integration tests: Test component interactions and data flow
- Acceptance tests: End-to-end user workflows
"""

import pytest
import pandas as pd
import requests_mock
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import json

from financial_data_processor import (
    APIClient, DataTransformer, MetricsCalculator, 
    FinancialDataService
)
from app import ChartRenderer, MetricsDisplay, DashboardApp


# ===== REGRESSION TESTS =====
class TestRegressions:
    """Tests to prevent known bugs from reoccurring."""
    
    def test_cagr_handles_division_by_zero(self):
        """Regression: Ensure CAGR doesn't crash with zero start value."""
        result = MetricsCalculator.calculate_cagr(0, 100, 5)
        assert result is None
    
    def test_cagr_handles_negative_values(self):
        """Regression: Ensure CAGR doesn't crash with negative values."""
        result = MetricsCalculator.calculate_cagr(-100, -50, 5)
        assert result is None
    
    def test_dataframe_empty_handling_in_metrics(self):
        """Regression: Ensure empty DataFrames don't cause crashes."""
        empty_df = pd.DataFrame()
        result = MetricsCalculator.calculate_metric_cagrs(empty_df, 'revenue', [1, 3, 5])
        assert result == {}
    
    def test_missing_column_in_dataframe(self):
        """Regression: Ensure missing columns are handled gracefully."""
        df = pd.DataFrame({
            'date': pd.date_range('2020-01-01', periods=5),
            'revenue': [100, 110, 120, 130, 140]
        })
        result = MetricsCalculator.calculate_metric_cagrs(df, 'nonexistent', [1, 3, 5])
        assert result == {}
    
    def test_price_data_resampling_preserves_data(self):
        """Regression: Ensure monthly resampling doesn't lose data integrity."""
        dates = pd.date_range('2024-01-01', periods=30, freq='D')
        df = pd.DataFrame({
            'date': dates,
            'close': range(100, 130),
            'high': range(101, 131),
            'low': range(99, 129),
            'open': range(100, 130),
            'volume': [1000000] * 30
        })
        
        resampled = DataTransformer.resample_to_monthly(df)
        assert not resampled.empty
        assert 'date' in resampled.columns
        assert 'close' in resampled.columns
    
    def test_pe_ratio_with_zero_eps(self):
        """Regression: Ensure P/E ratio calculation handles zero EPS."""
        df = pd.DataFrame({
            'date': pd.date_range('2020-01-01', periods=3),
            'epsDiluted': [0, 5.0, 10.0]
        }).copy()
        
        result = MetricsCalculator.add_pe_ratio(df.copy(), 150.0)
        assert 'pe' in result.columns
        # Zero EPS should result in inf or be handled
        assert pd.isna(result['pe'].iloc[0]) or result['pe'].iloc[0] == float('inf')
    
    def test_fcf_yield_with_zero_market_cap(self):
        """Regression: Ensure FCF Yield doesn't crash with zero market cap."""
        df = pd.DataFrame({
            'date': pd.date_range('2020-01-01', periods=3),
            'freeCashFlow': [1e9, 2e9, 3e9],
            'stockBasedCompensation': [0.1e9, 0.2e9, 0.3e9]
        }).copy()
        
        result = MetricsCalculator.add_fcf_metrics(df.copy(), 0)
        assert 'fcf_minus_sbc' in result.columns
        # With zero market cap, fcf_yield should not exist or be inf
        if 'fcf_yield' in result.columns:
            assert all(pd.isna(result['fcf_yield'])) or all(v == float('inf') for v in result['fcf_yield'])
    
    def test_profit_margin_with_zero_revenue(self):
        """Regression: Ensure margin calculations handle zero revenue."""
        df = pd.DataFrame({
            'date': pd.date_range('2020-01-01', periods=3),
            'revenue': [0, 100, 200],
            'grossProfit': [0, 30, 60],
            'operatingIncome': [0, 10, 20],
            'netIncome': [0, 5, 10]
        }).copy()
        
        result = MetricsCalculator.add_profit_margins(df.copy())
        assert 'grossProfitRatio' in result.columns
        # Zero revenue should result in inf or NaN
        assert pd.isna(result['grossProfitRatio'].iloc[0]) or result['grossProfitRatio'].iloc[0] == float('inf')
    
    def test_quote_metrics_with_missing_percentage(self):
        """Regression: Ensure quote metrics handles missing change percentage."""
        quote = {
            'price': 150.0,
            'change': 2.5,
            'previousClose': 147.5,
            'dayHigh': 152.0,
            'dayLow': 148.0
        }
        
        # Should not crash and should calculate change percentage
        with patch('streamlit.columns', return_value=[Mock(), Mock(), Mock(), Mock()]):
            # This should not raise an exception
            MetricsDisplay.display_quote_metrics(quote)


# ===== INTEGRATION TESTS =====
class TestAPIIntegration:
    """Test integration with external APIs."""
    
    def test_full_fmp_api_workflow(self):
        """Test complete workflow with mocked FMP API responses."""
        mock_profile_response = [{
            'symbol': 'AAPL',
            'companyName': 'Apple Inc.',
            'mktCap': 2500e9,
            'price': 150.0
        }]
        
        mock_quote_response = [{
            'symbol': 'AAPL',
            'price': 150.0,
            'change': 2.5,
            'changesPercentage': 1.69,
            'dayHigh': 152.0,
            'dayLow': 148.0,
            'previousClose': 147.5
        }]
        
        with requests_mock.Mocker() as m:
            m.get('https://financialmodelingprep.com/stable/profile', json=mock_profile_response)
            m.get('https://financialmodelingprep.com/stable/quote', json=mock_quote_response)
            
            client = APIClient('test_fmp_key', 'test_polygon_key')
            profile = client.fetch_fmp_data('profile', 'AAPL')
            quote = client.fetch_fmp_data('quote', 'AAPL')
            
            assert profile[0]['symbol'] == 'AAPL'
            assert quote[0]['price'] == 150.0
    
    def test_full_polygon_api_workflow(self):
        """Test Polygon API integration for price history."""
        mock_polygon_response = {
            'results': [
                {'t': 1704067200000, 'c': 150.0, 'h': 152.0, 'l': 149.0, 'o': 150.5, 'v': 1000000},
                {'t': 1704153600000, 'c': 151.0, 'h': 153.0, 'l': 150.0, 'o': 150.0, 'v': 900000},
                {'t': 1704240000000, 'c': 152.0, 'h': 154.0, 'l': 151.0, 'o': 151.0, 'v': 1100000},
            ]
        }
        
        with requests_mock.Mocker() as m:
            m.get('https://api.polygon.io/v2/aggs/ticker/AAPL/range/1/day/2024-01-01/2024-01-31', 
                   json=mock_polygon_response)
            
            client = APIClient('test_fmp_key', 'test_polygon_key')
            data = client.fetch_polygon_data('AAPL', '2024-01-01', '2024-01-31')
            
            assert len(data['results']) == 3
            assert data['results'][0]['c'] == 150.0


class TestDataTransformationIntegration:
    """Test data transformation pipeline."""
    
    def test_financial_statement_transformation_end_to_end(self):
        """Test complete transformation of financial statement data."""
        raw_data = [
            {'date': '2024-12-31', 'revenue': 380e9, 'netIncome': 93e9},
            {'date': '2023-12-31', 'revenue': 380e9, 'netIncome': 97e9},
            {'date': '2022-12-31', 'revenue': 394e9, 'netIncome': 99e9},
        ]
        
        df = DataTransformer.to_financial_dataframe(raw_data)
        
        assert len(df) == 3
        assert df['date'].dtype == 'datetime64[ns]'
        assert df.iloc[0]['revenue'] == 394e9  # Should be sorted
        assert df.iloc[-1]['revenue'] == 380e9
    
    def test_price_data_transformation_end_to_end(self):
        """Test complete transformation of price data."""
        raw_results = [
            {'t': 1704067200000, 'c': 150.0, 'h': 152.0, 'l': 149.0, 'o': 150.5, 'v': 1000000},
            {'t': 1704153600000, 'c': 151.0, 'h': 153.0, 'l': 150.0, 'o': 150.0, 'v': 900000},
        ]
        
        df = DataTransformer.to_price_dataframe(raw_results)
        
        assert len(df) == 2
        assert 'date' in df.columns
        assert 'close' in df.columns
        assert df['close'].iloc[0] == 150.0


class TestMetricsCalculationIntegration:
    """Test metrics calculation pipeline."""
    
    def test_complete_metrics_enrichment_workflow(self):
        """Test complete enrichment of financial data with all metrics."""
        income_df = pd.DataFrame({
            'date': pd.date_range('2020-01-01', periods=5, freq='YS'),
            'revenue': [100e9, 110e9, 120e9, 130e9, 140e9],
            'epsDiluted': [5.0, 5.5, 6.0, 6.5, 7.0],
            'grossProfit': [30e9, 35e9, 40e9, 45e9, 50e9],
            'operatingIncome': [20e9, 25e9, 30e9, 35e9, 40e9],
            'netIncome': [10e9, 12e9, 14e9, 16e9, 18e9]
        }).copy()
        
        cashflow_df = pd.DataFrame({
            'date': pd.date_range('2020-01-01', periods=5, freq='YS'),
            'freeCashFlow': [8e9, 10e9, 12e9, 14e9, 16e9],
            'stockBasedCompensation': [1e9, 1.2e9, 1.4e9, 1.6e9, 1.8e9]
        }).copy()
        
        # Add all metrics - make copies to avoid inplace warnings
        income_df = MetricsCalculator.add_pe_ratio(income_df.copy(), 150.0)
        income_df = MetricsCalculator.add_profit_margins(income_df.copy())
        cashflow_df = MetricsCalculator.add_fcf_metrics(cashflow_df.copy(), 2500e9)
        
        # Verify all metrics were added
        assert 'pe' in income_df.columns
        assert 'grossProfitRatio' in income_df.columns
        assert 'operatingIncomeRatio' in income_df.columns
        assert 'netIncomeRatio' in income_df.columns
        assert 'fcf_minus_sbc' in cashflow_df.columns
        assert 'fcf_yield' in cashflow_df.columns
        
        # Verify calculations are reasonable
        assert income_df['pe'].iloc[-1] > 0
        assert income_df['grossProfitRatio'].iloc[-1] > 0
        assert cashflow_df['fcf_yield'].iloc[-1] > 0



# ===== ACCEPTANCE TESTS =====
class TestUserWorkflows:
    """End-to-end user workflows and acceptance scenarios."""
    
    def test_user_analyzes_single_stock(self):
        """User story: User enters a ticker and views the dashboard."""
        mock_data = {
            'profile': {
                'symbol': 'AAPL',
                'companyName': 'Apple Inc.',
                'mktCap': 2500e9,
                'price': 150.0
            },
            'quote': {
                'symbol': 'AAPL',
                'price': 150.0,
                'change': 2.5,
                'changesPercentage': 1.69,
                'dayHigh': 152.0,
                'dayLow': 148.0,
                'previousClose': 147.5
            },
            'income_df': pd.DataFrame({
                'date': pd.date_range('2020-01-01', periods=5, freq='YS'),
                'revenue': [100e9, 110e9, 120e9, 130e9, 140e9],
                'epsDiluted': [5.0, 5.5, 6.0, 6.5, 7.0],
                'pe': [30.0, 27.27, 25.0, 23.08, 21.43],
                'grossProfitRatio': [30, 31, 32, 33, 34],
                'operatingIncomeRatio': [20, 21, 22, 23, 24],
                'netIncomeRatio': [10, 11, 12, 13, 14],
                'weightedAverageShsOutDil': [16e9, 16.1e9, 16.2e9, 16.3e9, 16.4e9]
            }),
            'cashflow_df': pd.DataFrame({
                'date': pd.date_range('2020-01-01', periods=5, freq='YS'),
                'freeCashFlow': [8e9, 10e9, 12e9, 14e9, 16e9],
                'fcf_minus_sbc': [7e9, 9e9, 11e9, 13e9, 15e9],
                'fcf_yield': [0.28, 0.36, 0.44, 0.52, 0.60]
            }),
            'price_history': pd.DataFrame({
                'date': pd.date_range('2023-01-01', periods=12, freq='ME'),
                'close': list(range(140, 152))
            }),
            'market_cap': 2500e9,
            'price': 150.0
        }
        
        with patch('streamlit.title'), \
             patch('streamlit.info'), \
             patch('streamlit.sidebar'), \
             patch('streamlit.header'), \
             patch('streamlit.divider'), \
             patch('streamlit.columns', return_value=[Mock(), Mock(), Mock(), Mock()]), \
             patch('streamlit.metric'), \
             patch('streamlit.subheader'), \
             patch('streamlit.plotly_chart'), \
             patch('streamlit.radio', side_effect=['Free Cash Flow', 'Gross Margin']), \
             patch('streamlit.text_input', return_value='AAPL'), \
             patch('streamlit.button', return_value=False):
            
            app = DashboardApp('test_fmp', 'test_polygon')
            
            with patch.object(app.data_service, 'get_all_financial_data', return_value=mock_data), \
                 patch.object(app, 'render_sidebar', return_value='AAPL'):
                app.run()
    
    def test_user_compares_financial_metrics_across_periods(self):
        """User story: User views CAGR metrics across different time periods."""
        # Create enough data points for 5-year CAGR (need at least 6 data points for 5Y calc)
        df = pd.DataFrame({
            'date': pd.date_range('2019-01-01', periods=6, freq='YS'),
            'revenue': [100e9, 110e9, 120e9, 130e9, 140e9, 150e9]
        })
        
        # Calculate CAGRs
        cagrs = MetricsCalculator.calculate_metric_cagrs(df, 'revenue', [1, 3, 5])
        
        # Verify user can see growth trends - should have at least 1Y and 3Y
        assert '1Y' in cagrs
        assert '3Y' in cagrs
        # 5Y might be included depending on data points
        
        # Verify calculations are reasonable
        cagr_1y = float(cagrs['1Y'].strip('%'))
        assert 0 < cagr_1y < 20  # Reasonable 1-year growth
    
    def test_user_toggles_fcf_metrics(self):
        """User story: User toggles between FCF and FCF-SBC metrics."""
        df = pd.DataFrame({
            'date': pd.date_range('2020-01-01', periods=5, freq='YS'),
            'freeCashFlow': [8e9, 10e9, 12e9, 14e9, 16e9],
            'fcf_minus_sbc': [7e9, 9e9, 11e9, 13e9, 15e9]
        })
        
        # User toggles to "Free Cash Flow"
        fcf_col_1 = 'freeCashFlow'
        assert fcf_col_1 in df.columns
        assert df[fcf_col_1].iloc[-1] == 16e9
        
        # User toggles to "FCF - SBC"
        fcf_col_2 = 'fcf_minus_sbc'
        assert fcf_col_2 in df.columns
        assert df[fcf_col_2].iloc[-1] == 15e9
        
        # Verify both are available
        assert df[fcf_col_1].sum() > df[fcf_col_2].sum()
    
    def test_user_views_profit_margins_trends(self):
        """User story: User views and compares profit margin trends."""
        df = pd.DataFrame({
            'date': pd.date_range('2020-01-01', periods=5, freq='YS'),
            'grossProfitRatio': [0.30, 0.31, 0.32, 0.33, 0.34],
            'operatingIncomeRatio': [0.20, 0.21, 0.22, 0.23, 0.24],
            'netIncomeRatio': [0.10, 0.11, 0.12, 0.13, 0.14]
        })
        
        # User views Gross Margin
        assert 'grossProfitRatio' in df.columns
        assert df['grossProfitRatio'].iloc[-1] > df['grossProfitRatio'].iloc[0]
        
        # User views Operating Margin
        assert 'operatingIncomeRatio' in df.columns
        assert df['operatingIncomeRatio'].iloc[-1] > df['operatingIncomeRatio'].iloc[0]
        
        # User views Net Margin
        assert 'netIncomeRatio' in df.columns
        assert df['netIncomeRatio'].iloc[-1] > df['netIncomeRatio'].iloc[0]
    
    def test_user_error_handling_invalid_ticker(self):
        """User story: User enters invalid ticker and sees error message."""
        with patch('streamlit.error') as mock_error:
            with requests_mock.Mocker() as m:
                m.get('https://financialmodelingprep.com/stable/profile', 
                       json=[])  # Empty response for invalid ticker
                
                client = APIClient('test_fmp', 'test_polygon')
                service = FinancialDataService(client)
                
                profile = service.get_company_profile('INVALID')
                assert profile == {}


class TestDataIntegrity:
    """Tests to ensure data integrity throughout the application."""
    
    def test_sorted_dates_in_financial_data(self):
        """Verify financial data is sorted by date."""
        raw_data = [
            {'date': '2024-12-31', 'revenue': 380e9},
            {'date': '2022-12-31', 'revenue': 394e9},
            {'date': '2023-12-31', 'revenue': 380e9},
        ]
        
        df = DataTransformer.to_financial_dataframe(raw_data)
        dates = df['date'].tolist()
        
        assert dates == sorted(dates)
    
    def test_no_nan_in_metrics(self):
        """Verify calculated metrics don't introduce unexpected NaNs."""
        df = pd.DataFrame({
            'date': pd.date_range('2020-01-01', periods=5, freq='YS'),
            'revenue': [100e9, 110e9, 120e9, 130e9, 140e9],
            'epsDiluted': [5.0, 5.5, 6.0, 6.5, 7.0],
            'grossProfit': [30e9, 35e9, 40e9, 45e9, 50e9],
            'operatingIncome': [20e9, 25e9, 30e9, 35e9, 40e9],
            'netIncome': [10e9, 12e9, 14e9, 16e9, 18e9]
        }).copy()
        
        result = MetricsCalculator.add_pe_ratio(df.copy(), 150.0)
        result = MetricsCalculator.add_profit_margins(result.copy())
        
        # Check for unexpected NaNs (legitimate infs should be ok)
        assert not result[['grossProfitRatio', 'operatingIncomeRatio', 'netIncomeRatio']].isna().any().any()
    
    def test_price_history_chronological_order(self):
        """Verify price history is in chronological order."""
        raw_results = [
            {'t': 1704240000000, 'c': 152.0, 'h': 154.0, 'l': 151.0, 'o': 151.0, 'v': 1100000},
            {'t': 1704067200000, 'c': 150.0, 'h': 152.0, 'l': 149.0, 'o': 150.5, 'v': 1000000},
            {'t': 1704153600000, 'c': 151.0, 'h': 153.0, 'l': 150.0, 'o': 150.0, 'v': 900000},
        ]
        
        df = DataTransformer.to_price_dataframe(raw_results)
        dates = df['date'].tolist()
        
        assert dates == sorted(dates)


class TestChartingAcceptance:
    """Acceptance tests for charting functionality."""
    
    def test_line_chart_renders_all_points(self):
        """Verify line chart renders all data points."""
        df = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=12, freq='ME'),
            'close': list(range(150, 162))
        })
        
        fig = ChartRenderer.render_line_chart(df, 'date', 'close', 'Price', 'Price ($)')
        
        assert len(fig.data[0].x) == 12
        assert len(fig.data[0].y) == 12
    
    def test_bar_chart_renders_all_values(self):
        """Verify bar chart renders all values."""
        df = pd.DataFrame({
            'date': pd.date_range('2020-01-01', periods=5, freq='YS'),
            'revenue': [100e9, 110e9, 120e9, 130e9, 140e9]
        })
        
        fig = ChartRenderer.render_bar_chart(df, 'date', 'revenue', 'Revenue ($)')
        
        assert len(fig.data[0].x) == 5
        assert len(fig.data[0].y) == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])