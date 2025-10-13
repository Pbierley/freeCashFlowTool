import pandas as pd
import requests
from datetime import datetime
from functools import lru_cache # Used for caching outside of Streamlit

class FinancialDataProcessor:
    """
    Manages all data fetching, cleaning, and calculation logic 
    for the stock analysis dashboard.
    """
    
    FMP_BASE_URL = "https://financialmodelingprep.com/stable"
    POLYGON_BASE_URL = "https://api.polygon.io/v2"

    def __init__(self, fmp_api_key, polygon_api_key):
        self._fmp_key = fmp_api_key
        self._polygon_key = polygon_api_key

    # --- API FETCHERS (Using lru_cache for pure function caching) ---

    @lru_cache(maxsize=32)
    def _fetch_data(self, endpoint, ticker, api_key, params=None):
        """Generic function for fetching data from FMP or Polygon."""
        url = f"{self.FMP_BASE_URL}/{endpoint}?symbol={ticker}" if 'polygon' not in endpoint else endpoint
        
        default_params = {"apikey": api_key}
        if params:
            default_params.update(params)
        
        response = requests.get(url, params=default_params)
        response.raise_for_status()
        return response.json()

    def get_stock_info(self, ticker):
        return self._fetch_data("profile", ticker, self._fmp_key)

    def get_income_statement(self, ticker, period="annual", limit=5):
        return self._fetch_data("income-statement", ticker, self._fmp_key, 
                                params={"period": period, "limit": limit})

    def get_cash_flow(self, ticker, limit=5):
        return self._fetch_data("cash-flow-statement", ticker, self._fmp_key, 
                                params={"limit": limit})

    def get_historical_chart(self, ticker):
        """Fetches 5 years of daily price data from Polygon."""
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - pd.DateOffset(years=5)).strftime('%Y-%m-%d')
        
        # Polygon API requires the URL format to be different
        url = f"{self.POLYGON_BASE_URL}/aggs/ticker/{ticker}/range/1/day/{start_date}/{end_date}"
        return self._fetch_data(url, ticker, self._polygon_key, 
                                params={"adjusted": "true", "sort": "asc"})

    # --- DATA PROCESSING & TRANSFORMATION ---

    def _prepare_financial_df(self, data):
        """Converts raw financial API data to a cleaned, sorted DataFrame."""
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data)
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date', ascending=True).reset_index(drop=True)
        return df

    def process_all_financial_data(self, ticker):
        """Fetches and processes all necessary financial statements."""
        raw_income = self.get_income_statement(ticker)
        raw_cash_flow = self.get_cash_flow(ticker)
        
        return {
            'income_df': self._prepare_financial_df(raw_income),
            'cashflow_df': self._prepare_financial_df(raw_cash_flow)
        }

    # --- FINANCIAL CALCULATIONS ---
    
    @staticmethod
    def calculate_cagr(start_value, end_value, years):
        """Calculates Compound Annual Growth Rate."""
        if start_value <= 0 or end_value <= 0 or years <= 0:
            return None
        return (((end_value / start_value) ** (1 / years)) - 1) * 100

    def calculate_cagrs(self, df, metric_col, periods=[1, 2, 3, 5]):
        """Calculates CAGR for a given metric column over multiple periods."""
        cagrs = {}
        for period in periods:
            # Need (period + 1) data points to calculate 'period' years of growth
            if len(df) > period:
                end_val = df[metric_col].iloc[-1]
                start_val = df[metric_col].iloc[-(period + 1)]
                cagr = self.calculate_cagr(start_val, end_val, period)
                if cagr is not None:
                    cagrs[f"{period}Y"] = f"{cagr:.2f}%"
        return cagrs

    def calculate_derived_metrics(self, data_dict, market_cap, price):
        """Calculates and adds P/E, Margins, and FCF-SBC to DataFrames."""
        income_df = data_dict['income_df']
        cashflow_df = data_dict['cashflow_df']
        
        # 1. P/E Ratio (Uses latest price and historical EPS)
        if 'epsDiluted' in income_df.columns and price > 0:
            income_df['pe'] = price / income_df['epsDiluted']
            income_df['pe'].replace([float('inf'), -float('inf')], float('nan'), inplace=True)
            
        # 2. Profit Margins
        if 'revenue' in income_df.columns and income_df['revenue'].any() > 0:
            for metric, col_name in [('grossProfit', 'grossProfitRatio'), 
                                     ('operatingIncome', 'operatingIncomeRatio'), 
                                     ('netIncome', 'netIncomeRatio')]:
                if metric in income_df.columns:
                    income_df[col_name] = income_df[metric] / income_df['revenue'] * 100
        
        # 3. FCF - SBC and FCF Yield
        if 'freeCashFlow' in cashflow_df.columns and 'stockBasedCompensation' in cashflow_df.columns:
            cashflow_df['fcf_minus_sbc'] = (
                cashflow_df['freeCashFlow'] - cashflow_df['stockBasedCompensation']
            )
            
            if market_cap > 0:
                cashflow_df['fcf_yield'] = (
                    cashflow_df['fcf_minus_sbc'] / market_cap
                ) * 100
        
        return {'income_df': income_df, 'cashflow_df': cashflow_df}