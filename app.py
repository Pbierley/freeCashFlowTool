import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import os
from dotenv import load_dotenv
from financial_data_processor import APIClient, FinancialDataService, MetricsCalculator


# --- CONFIGURATION ---
load_dotenv()
st.set_page_config(page_title="Stock Analysis Dashboard", layout="wide")


class ChartRenderer:
    """Handles all chart rendering logic."""

    @staticmethod
    def render_line_chart(df: pd.DataFrame, x_col: str, y_col: str, 
                         title: str, y_label: str, color: str = '#1f77b4') -> go.Figure:
        """Create a line chart."""
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df[x_col], 
            y=df[y_col],
            mode='lines',
            name=y_label,
            line=dict(color=color, width=2),
            hovertemplate=f'<b>Date:</b> %{{x|%Y-%m-%d}}<br><b>{y_label}:</b> $%{{y:.2f}}<extra></extra>'
        ))
        fig.update_layout(
            height=400,
            xaxis_title="Date",
            yaxis_title=y_label,
            hovermode='x unified',
            showlegend=False
        )
        return fig

    @staticmethod
    def render_bar_chart(df: pd.DataFrame, x_col: str, y_col: str, 
                        y_label: str, color: str = None) -> go.Figure:
        """Create a bar chart."""
        fig = px.bar(
            df, 
            x=x_col, 
            y=y_col,
            labels={y_col: y_label, x_col: 'Year'}
        )
        if color:
            fig.update_traces(marker_color=color)
        fig.update_layout(height=400, showlegend=False)
        return fig


class MetricsDisplay:
    """Handles display of metrics and KPIs."""

    @staticmethod
    def display_overview(profile: dict, quote: dict):
        """Display company overview metrics."""
        st.header(f"{profile.get('companyName', profile.get('symbol', 'N/A'))}")
        
        col1, col2, col3, col4 = st.columns(4)
        
        market_cap = profile.get('mktCap') or profile.get('marketCap', 0)
        price = profile.get('price', 0)
        change = quote.get('change', 0)
        
        with col1:
            st.metric("Ticker", profile.get('symbol', 'N/A'))
        with col2:
            st.metric("Market Cap", f"${market_cap/1e9:.2f}B" if market_cap else "N/A")
        with col3:
            st.metric("Share Price", f"${price:.2f}" if price else "N/A")
        with col4:
            st.metric("Change", f"${change:.2f}" if change else "N/A", 
                     delta=f"{change:.2f}" if change else None)
        
        st.divider()

    @staticmethod
    def display_quote_metrics(quote: dict):
        """Display detailed quote metrics."""
        if not quote:
            return
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Current Price", f"${quote.get('price', 0):.2f}")
        with col2:
            st.metric("Day Change %", f"{quote.get('changesPercentage', 0):.2f}%", 
                     delta=f"{quote.get('change', 0):.2f}")
        with col3:
            st.metric("Day High", f"${quote.get('dayHigh', 0):.2f}")
        with col4:
            st.metric("Day Low", f"${quote.get('dayLow', 0):.2f}")

    @staticmethod
    def display_cagrs(df: pd.DataFrame, metric_col: str, label: str, periods: list = [1, 3, 5]):
        """Display CAGR metrics for a given column."""
        if df.empty or metric_col not in df.columns:
            return
        
        cagrs = MetricsCalculator.calculate_metric_cagrs(df, metric_col, periods)
        if cagrs:
            cols = st.columns(len(cagrs))
            for i, (period, value) in enumerate(cagrs.items()):
                cols[i].metric(f"{label} CAGR {period}", value)

    @staticmethod
    def display_fcf_yield_metrics(df: pd.DataFrame):
        """Display FCF Yield summary metrics."""
        if df.empty or 'fcf_yield' not in df.columns:
            return
        
        avg_yield = df['fcf_yield'].mean()
        latest_yield = df['fcf_yield'].iloc[-1]
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Average FCF Yield", f"{avg_yield:.2f}%")
        with col2:
            st.metric("Latest FCF Yield", f"{latest_yield:.2f}%")


class DashboardApp:
    """Main application controller."""

    def __init__(self, fmp_key: str, polygon_key: str):
        self.api_client = APIClient(fmp_key, polygon_key)
        self.data_service = FinancialDataService(self.api_client)
        self.chart_renderer = ChartRenderer()
        self.metrics_display = MetricsDisplay()

    def render_sidebar(self) -> str:
        """Render sidebar and return selected ticker."""
        with st.sidebar:
            st.header("Stock Selection")
            ticker = st.text_input("Enter Stock Ticker", value="AAPL").upper()
            if st.button("Analyze Stock", type="primary"):
                st.session_state['ticker'] = ticker
                st.rerun()
        
        if 'ticker' not in st.session_state:
            st.session_state['ticker'] = ticker
        
        return st.session_state['ticker']

    def render_price_section(self, price_history: pd.DataFrame, quote: dict):
        """Render price chart and metrics."""
        st.subheader("📈 Stock Price History (5 Years)")
        
        if price_history.empty:
            st.info("Price history not available.")
            return
        
        fig = self.chart_renderer.render_line_chart(
            price_history, 'date', 'close', 
            'Stock Price', 'Price ($)'
        )
        st.plotly_chart(fig, use_container_width=True)
        
        self.metrics_display.display_quote_metrics(quote)

    def render_financial_metric(self, df: pd.DataFrame, metric_col: str, 
                                title: str, y_label: str, show_cagr: bool = True,
                                cagr_periods: list = [1, 3, 5]):
        """Render a financial metric chart with optional CAGR."""
        st.subheader(f"💰 {title}")
        
        if df.empty or metric_col not in df.columns:
            st.info(f"No {title} data available.")
            return
        
        fig = self.chart_renderer.render_bar_chart(df, 'date', metric_col, y_label)
        st.plotly_chart(fig, use_container_width=True)
        
        if show_cagr:
            self.metrics_display.display_cagrs(df, metric_col, title, cagr_periods)

    def render_fcf_section(self, cashflow_df: pd.DataFrame):
        """Render FCF section with toggle."""
        st.subheader("💵 Free Cash Flow")
        
        fcf_option = st.radio(
            "FCF Metric:", 
            ["Free Cash Flow", "FCF - SBC"], 
            horizontal=True, 
            key="fcf_radio"
        )
        
        fcf_col = 'fcf_minus_sbc' if fcf_option == "FCF - SBC" else 'freeCashFlow'
        
        if cashflow_df.empty or fcf_col not in cashflow_df.columns:
            st.info(f"No {fcf_option} data available.")
            return
        
        fig = self.chart_renderer.render_bar_chart(
            cashflow_df, 'date', fcf_col, f"{fcf_option} ($)"
        )
        st.plotly_chart(fig, use_container_width=True)
        
        self.metrics_display.display_cagrs(cashflow_df, fcf_col, fcf_option, [1, 3, 5])

    def render_fcf_yield_section(self, cashflow_df: pd.DataFrame):
        """Render FCF Yield chart and metrics."""
        st.subheader("💰 Free Cash Flow Yield")
        
        if cashflow_df.empty or 'fcf_yield' not in cashflow_df.columns:
            st.info("FCF Yield calculation requires FCF, SBC, and Market Cap data.")
            return
        
        fig = self.chart_renderer.render_bar_chart(
            cashflow_df, 'date', 'fcf_yield', 'FCF Yield (%)'
        )
        st.plotly_chart(fig, use_container_width=True)
        
        self.metrics_display.display_fcf_yield_metrics(cashflow_df)

    def render_margins_section(self, income_df: pd.DataFrame):
        """Render profit margins section with toggle."""
        st.subheader("📊 Profit Margins")
        
        margin_option = st.radio(
            "Select Margin:", 
            ["Gross Margin", "Operating Margin", "Net Margin"], 
            horizontal=True, 
            key="margin_radio"
        )
        
        margin_map = {
            "Gross Margin": 'grossProfitRatio',
            "Operating Margin": 'operatingIncomeRatio',
            "Net Margin": 'netIncomeRatio'
        }
        
        metric_col = margin_map[margin_option]
        
        if income_df.empty or metric_col not in income_df.columns:
            st.info(f"No {margin_option} data available.")
            return
        
        fig = self.chart_renderer.render_bar_chart(
            income_df, 'date', metric_col, f"{margin_option} (%)"
        )
        st.plotly_chart(fig, use_container_width=True)

    def run(self):
        """Main application entry point."""
        st.title("📊 Stock Analysis Dashboard")
        
        ticker = self.render_sidebar()
        
        if not ticker:
            st.info("👈 Enter a stock ticker in the sidebar to begin analysis.")
            return
        
        try:
            with st.spinner(f"Fetching data for {ticker}..."):
                data = self.data_service.get_all_financial_data(ticker)
            
            # Overview
            self.metrics_display.display_overview(data['profile'], data['quote'])
            
            # Price Chart
            self.render_price_section(data['price_history'], data['quote'])
            
            # Financial Metrics
            self.render_financial_metric(
                data['income_df'], 'revenue', 'Revenue', 'Revenue ($)'
            )
            
            self.render_financial_metric(
                data['income_df'], 'epsDiluted', 'Diluted EPS', 'Diluted EPS ($)'
            )
            
            self.render_financial_metric(
                data['income_df'], 'pe', 'P/E Ratio', 'P/E Ratio', show_cagr=False
            )
            
            self.render_financial_metric(
                data['income_df'], 'weightedAverageShsOutDil', 
                'Shares Outstanding', 'Shares Outstanding'
            )
            
            # Cash Flow
            self.render_fcf_section(data['cashflow_df'])
            self.render_fcf_yield_section(data['cashflow_df'])
            
            # Margins
            self.render_margins_section(data['income_df'])
            
        except Exception as e:
            st.error(f"Error: {str(e)}")


# --- APPLICATION ENTRY POINT ---
if __name__ == "__main__":
    FMP_API_KEY = os.getenv("FMP_API_KEY")
    POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")
    
    if not FMP_API_KEY or not POLYGON_API_KEY:
        st.warning("Please set FMP_API_KEY and POLYGON_API_KEY in your .env file.")
        st.stop()
    
    app = DashboardApp(FMP_API_KEY, POLYGON_API_KEY)
    app.run()