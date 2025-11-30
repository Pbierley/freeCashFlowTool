import pandas as pd
import requests
from datetime import datetime
from typing import Dict, List, Optional


class APIClient:
    """Handles all external API requests."""
    
    FMP_BASE_URL = "https://financialmodelingprep.com/stable"
    POLYGON_BASE_URL = "https://api.polygon.io/v2"

    def __init__(self, fmp_api_key: str, polygon_api_key: str):
        self._fmp_key = fmp_api_key
        self._polygon_key = polygon_api_key

    def fetch_fmp_data(self, endpoint: str, ticker: str, params: Optional[Dict] = None) -> Dict:
        """Fetch data from Financial Modeling Prep API."""
        url = f"{self.FMP_BASE_URL}/{endpoint}"
        default_params = {"symbol": ticker, "apikey": self._fmp_key}
        if params:
            default_params.update(params)
        
        response = requests.get(url, params=default_params)
        response.raise_for_status()
        return response.json()

    def fetch_polygon_data(self, ticker: str, start_date: str, end_date: str) -> Dict:
        """Fetch historical price data from Polygon API."""
        url = f"{self.POLYGON_BASE_URL}/aggs/ticker/{ticker}/range/1/day/{start_date}/{end_date}"
        params = {
            "adjusted": "true",
            "sort": "asc",
            "limit": "50000",
            "apiKey": self._polygon_key
        }
        
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()


class DataTransformer:
    """Transforms raw API data into cleaned DataFrames."""

    @staticmethod
    def to_financial_dataframe(data: List[Dict]) -> pd.DataFrame:
        """Convert financial statement data to DataFrame with sorted dates."""
        if not data:
            return pd.DataFrame()
        
        df = pd.DataFrame(data)
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date', ascending=True).reset_index(drop=True)
        return df

    @staticmethod
    def to_price_dataframe(polygon_results: List[Dict]) -> pd.DataFrame:
        """Convert Polygon price data to DataFrame."""
        if not polygon_results:
            return pd.DataFrame()
        
        df = pd.DataFrame(polygon_results)
        df['date'] = pd.to_datetime(df['t'], unit='ms')
        df['close'] = df['c']
        df['high'] = df['h']
        df['low'] = df['l']
        df['open'] = df['o']
        df['volume'] = df['v']
        return df.sort_values('date')

    @staticmethod
    def resample_to_monthly(df: pd.DataFrame) -> pd.DataFrame:
        """Resample daily price data to monthly."""
        if df.empty or 'date' not in df.columns or 'close' not in df.columns:
            return pd.DataFrame()
        
        df_indexed = df.set_index('date')
        return df_indexed.resample('ME').last().reset_index()


class MetricsCalculator:
    """Calculates financial metrics and ratios."""

    @staticmethod
    def calculate_cagr(start_value: float, end_value: float, years: int) -> Optional[float]:
        """Calculate Compound Annual Growth Rate."""
        if start_value <= 0 or end_value <= 0 or years <= 0:
            return None
        return (((end_value / start_value) ** (1 / years)) - 1) * 100

    @classmethod
    def calculate_metric_cagrs(cls, df: pd.DataFrame, metric_col: str, 
                               periods: List[int] = [1, 2, 3, 5]) -> Dict[str, str]:
        """Calculate CAGR for multiple periods."""
        cagrs = {}
        for period in periods:
            if len(df) > period and metric_col in df.columns:
                end_val = df[metric_col].iloc[-1]
                start_val = df[metric_col].iloc[-(period + 1)]
                cagr = cls.calculate_cagr(start_val, end_val, period)
                if cagr is not None:
                    cagrs[f"{period}Y"] = f"{cagr:.2f}%"
        return cagrs

    @staticmethod
    def add_pe_ratio(income_df: pd.DataFrame, current_price: float) -> pd.DataFrame:
        """Add P/E ratio column to income statement."""
        if 'epsDiluted' in income_df.columns and current_price > 0:
            # FIXED: Use direct assignment instead of chained assignment
            income_df = income_df.copy()  # Ensure we have a copy
            income_df['pe'] = current_price / income_df['epsDiluted']
            # Replace inf values with NaN
            income_df['pe'] = income_df['pe'].replace([float('inf'), -float('inf')], float('nan'))
        return income_df

    @staticmethod
    def add_profit_margins(income_df: pd.DataFrame) -> pd.DataFrame:
        """Add profit margin columns to income statement."""
        if 'revenue' not in income_df.columns or income_df.empty:
            return income_df
        
        income_df = income_df.copy()  # Ensure we have a copy
        margin_metrics = [
            ('grossProfit', 'grossProfitRatio'),
            ('operatingIncome', 'operatingIncomeRatio'),
            ('netIncome', 'netIncomeRatio')
        ]
        
        for metric, ratio_col in margin_metrics:
            if metric in income_df.columns:
                income_df[ratio_col] = (income_df[metric] / income_df['revenue']) * 100
        
        return income_df

    @staticmethod
    def add_fcf_metrics(cashflow_df: pd.DataFrame, market_cap: float) -> pd.DataFrame:
        """Add FCF - SBC and FCF Yield columns."""
        if cashflow_df.empty:
            return cashflow_df
        
        cashflow_df = cashflow_df.copy()  # Ensure we have a copy
        
        # FCF - SBC
        if 'freeCashFlow' in cashflow_df.columns and 'stockBasedCompensation' in cashflow_df.columns:
            cashflow_df['fcf_minus_sbc'] = (
                cashflow_df['freeCashFlow'] - cashflow_df['stockBasedCompensation']
            )
            
            # FCF Yield
            if market_cap > 0:
                cashflow_df['fcf_yield'] = (
                    cashflow_df['fcf_minus_sbc'] / market_cap
                ) * 100
        
        return cashflow_df


class FinancialDataService:
    """Orchestrates data fetching, transformation, and enrichment."""

    def __init__(self, api_client: APIClient):
        self.api_client = api_client
        self.transformer = DataTransformer()
        self.calculator = MetricsCalculator()

    def get_company_profile(self, ticker: str) -> Dict:
        """Get company profile information."""
        data = self.api_client.fetch_fmp_data("profile", ticker)
        return data[0] if data else {}

    def get_quote(self, ticker: str) -> Dict:
        """Get current stock quote."""
        data = self.api_client.fetch_fmp_data("quote", ticker)
        return data[0] if data else {}

    def get_historical_prices(self, ticker: str, years: int = 5) -> pd.DataFrame:
        """Get historical price data and resample to monthly."""
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - pd.DateOffset(years=years)).strftime('%Y-%m-%d')
        
        polygon_data = self.api_client.fetch_polygon_data(ticker, start_date, end_date)
        results = polygon_data.get('results', [])
        
        daily_df = self.transformer.to_price_dataframe(results)
        return self.transformer.resample_to_monthly(daily_df)

    def get_income_statement(self, ticker: str, limit: int = 5) -> pd.DataFrame:
        """Get income statement data."""
        data = self.api_client.fetch_fmp_data(
            "income-statement", ticker, 
            params={"period": "annual", "limit": limit}
        )
        return self.transformer.to_financial_dataframe(data)

    def get_cashflow_statement(self, ticker: str, limit: int = 5) -> pd.DataFrame:
        """Get cash flow statement data."""
        data = self.api_client.fetch_fmp_data(
            "cash-flow-statement", ticker, 
            params={"limit": limit}
        )
        return self.transformer.to_financial_dataframe(data)

    def enrich_financial_data(self, income_df: pd.DataFrame, cashflow_df: pd.DataFrame,
                              market_cap: float, price: float) -> Dict[str, pd.DataFrame]:
        """Add calculated metrics to financial DataFrames."""
        income_df = self.calculator.add_pe_ratio(income_df, price)
        income_df = self.calculator.add_profit_margins(income_df)
        cashflow_df = self.calculator.add_fcf_metrics(cashflow_df, market_cap)
        
        return {
            'income_df': income_df,
            'cashflow_df': cashflow_df
        }

    def get_all_financial_data(self, ticker: str) -> Dict:
        """Fetch and process all financial data for a ticker."""
        # Get company info and current data
        profile = self.get_company_profile(ticker)
        quote = self.get_quote(ticker)
        
        # Extract market cap and price
        market_cap = profile.get('mktCap') or profile.get('marketCap', 0)
        price = profile.get('price', 0)
        
        # Get financial statements
        income_df = self.get_income_statement(ticker)
        cashflow_df = self.get_cashflow_statement(ticker)
        
        # Enrich with calculated metrics
        enriched = self.enrich_financial_data(income_df, cashflow_df, market_cap, price)
        
        # Get price history
        price_history = self.get_historical_prices(ticker)
        
        return {
            'profile': profile,
            'quote': quote,
            'income_df': enriched['income_df'],
            'cashflow_df': enriched['cashflow_df'],
            'price_history': price_history,
            'market_cap': market_cap,
            'price': price
        }


class FinancialDataProcessor:
    """Compatibility wrapper/alias class so older code/tests that expect
    FinancialDataProcessor can still use this module.
    """

    def __init__(self, fmp_key: str, polygon_key: str):
        self.api_client = APIClient(fmp_key, polygon_key)
        self.transformer = DataTransformer()
        self.calculator = MetricsCalculator()

    @staticmethod
    def calculate_cagr(start_value: float, end_value: float, years: int):
        return MetricsCalculator.calculate_cagr(start_value, end_value, years)

    def _prepare_financial_df(self, data: List[Dict]):
        return self.transformer.to_financial_dataframe(data)

    def calculate_cagrs(self, df: pd.DataFrame, metric_col: str, periods: List[int] = [1, 3, 5]):
        return self.calculator.calculate_metric_cagrs(df, metric_col, periods)
