import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import os
from dotenv import load_dotenv

# Assuming FinancialDataProcessor is in a separate file or included above
# from financial_data_processor import FinancialDataProcessor 

# --- CONFIGURATION AND SETUP ---
# Load environment variables
load_dotenv()
FMP_API_KEY = os.getenv("FMP_API_KEY")
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")

st.set_page_config(page_title="Stock Analysis Dashboard", layout="wide")
st.title("📊 Stock Analysis Dashboard")

# Initialize the data processor (Encapsulation of API access)
if FMP_API_KEY and POLYGON_API_KEY:
    processor = FinancialDataProcessor(FMP_API_KEY, POLYGON_API_KEY)
else:
    processor = None
    st.warning("Please set FMP_API_KEY and POLYGON_API_KEY in your .env file.")

# --- UI RENDERING FUNCTIONS (Single Responsibility) ---

def render_overview_metrics(info, quote_data):
    """Renders the company name and key financial metrics."""
    st.header(f"{info.get('companyName', info.get('symbol', 'N/A'))}")
    
    col1, col2, col3, col4 = st.columns(4)
    market_cap = info.get('mktCap', 0)
    price = info.get('price', 0)
    changes = quote_data[0].get('change', 0) if quote_data else 0
    
    with col1:
        st.metric("Ticker", info.get('symbol', 'N/A'))
    with col2:
        st.metric("Market Cap", f"${market_cap/1e9:.2f}B" if market_cap else "N/A")
    with col3:
        st.metric("Share Price", f"${price:.2f}" if price else "N/A")
    with col4:
        st.metric("Change", f"${changes:.2f}" if changes else "N/A", 
                  delta=f"{changes:.2f}" if changes else None)
    st.divider()

def render_price_chart(historical_data, quote_data):
    """Renders the 5-year stock price chart and daily metrics."""
    st.subheader("📈 Stock Price History (5 Years)")
    try:
        results = historical_data.get('results', [])
        if not results:
            st.info("Price history not available.")
            return

        # Data Preparation
        price_df = pd.DataFrame(results)
        price_df['date'] = pd.to_datetime(price_df['t'], unit='ms')
        price_df['close'] = price_df['c']
        monthly_df = price_df.set_index('date').resample('ME').last().reset_index()

        # Chart Logic
        fig_price = go.Figure()
        fig_price.add_trace(go.Scatter(x=monthly_df['date'], y=monthly_df['close'], 
                                       mode='lines', name='Close Price', line=dict(color='#1f77b4')))
        fig_price.update_layout(height=400, yaxis_title="Price ($)", showlegend=False)
        st.plotly_chart(fig_price, use_container_width=True)
        
        # Daily Metrics
        if quote_data and quote_data[0]:
            quote = quote_data[0]
            col1, col2, col3, col4 = st.columns(4)
            with col1: st.metric("Current Price", f"${quote.get('price', 0):.2f}")
            with col2: st.metric("Day Change %", f"{quote.get('changesPercentage', 0):.2f}%", 
                                 delta=f"{quote.get('change', 0):.2f}")
            with col3: st.metric("Day High", f"${quote.get('dayHigh', 0):.2f}")
            with col4: st.metric("Day Low", f"${quote.get('dayLow', 0):.2f}")
            
    except Exception as e:
        st.error(f"Error rendering price chart: {e}")

def render_metric_chart(df, metric_col, title, y_label, cagr_periods=None):
    """Generic function to render a bar chart and its corresponding CAGRs."""
    st.subheader(f"💰 {title}")
    
    if df.empty or metric_col not in df.columns or not df[metric_col].any():
        st.info(f"No {title} data available.")
        return

    # Chart
    fig = px.bar(df, x='date', y=metric_col, 
                 labels={metric_col: y_label, 'date': 'Year'})
    fig.update_layout(height=400, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)
    
    # CAGRs
    if cagr_periods and not df.empty:
        cagrs = processor.calculate_cagrs(df, metric_col, periods=cagr_periods)
        if cagrs:
            cols = st.columns(len(cagrs))
            for i, (period, value) in enumerate(cagrs.items()):
                cols[i].metric(f"{title} CAGR {period}", value)

def render_fcf_yield(cashflow_df, market_cap):
    """Renders FCF Yield chart and metrics."""
    st.subheader("💰 Free Cash Flow Yield")
    
    if cashflow_df.empty or 'fcf_yield' not in cashflow_df.columns:
        st.info("FCF Yield calculation requires FCF, SBC, and Market Cap data.")
        return

    fig_fcf_yield = px.bar(
        cashflow_df, x='date', y='fcf_yield',
        labels={'fcf_yield': 'FCF Yield (%)', 'date': 'Year'},
        color_discrete_sequence=px.colors.qualitative.T10 # Change color for variety
    )
    fig_fcf_yield.update_layout(height=400, showlegend=False)
    st.plotly_chart(fig_fcf_yield, use_container_width=True)
    
    # Metrics
    if not cashflow_df.empty:
        avg_yield = cashflow_df['fcf_yield'].mean()
        latest_yield = cashflow_df['fcf_yield'].iloc[-1]
        col1, col2 = st.columns(2)
        with col1: st.metric("Average FCF Yield", f"{avg_yield:.2f}%")
        with col2: st.metric("Latest FCF Yield", f"{latest_yield:.2f}%")


# --- MAIN EXECUTION ---
with st.sidebar:
    st.header("Stock Selection")
    ticker = st.text_input("Enter Stock Ticker", value="AAPL").upper()
    if st.button("Analyze Stock", type="primary"):
        st.session_state['ticker'] = ticker
        st.rerun()

# Use session state to hold the ticker and prevent rerunning analysis if the page reloads
if 'ticker' not in st.session_state:
    st.session_state['ticker'] = ticker

if st.session_state['ticker'] and processor:
    try:
        with st.spinner(f"Fetching data for {st.session_state['ticker']}..."):
            # 1. Fetch Core Data
            stock_info = processor.get_stock_info(st.session_state['ticker'])
            quote_data = processor._fetch_data("quote", st.session_state['ticker'], FMP_API_KEY)
            historical_data = processor.get_historical_chart(st.session_state['ticker'])
            
            # 2. Get Market Cap and Price from info
            info = stock_info[0] if stock_info else {}
            market_cap = info.get('mktCap', 0) or info.get('marketCap', 0)
            price = info.get('price', 0)
            
            # 3. Process Financial Statements
            data_dict = processor.process_all_financial_data(st.session_state['ticker'])
            data_dict = processor.calculate_derived_metrics(data_dict, market_cap, price)
            
            income_df = data_dict['income_df']
            cashflow_df = data_dict['cashflow_df']

        # --- RENDERING ---
        if info:
            render_overview_metrics(info, quote_data)
            render_price_chart(historical_data, quote_data)

            # Revenue and EPS
            render_metric_chart(income_df, 'revenue', "Revenue", "Revenue ($)", cagr_periods=[1, 3, 5])
            render_metric_chart(income_df, 'epsDiluted', "Diluted EPS", "Diluted EPS ($)", cagr_periods=[1, 3, 5])
            
            # P/E Ratio
            render_metric_chart(income_df, 'pe', "P/E Ratio (Historical)", "P/E Ratio")
            
            # Shares Outstanding
            render_metric_chart(income_df, 'weightedAverageShsOutDil', "Shares Outstanding", "Shares Outstanding", cagr_periods=[1, 3, 5])

            # FCF with Toggle
            fcf_option = st.radio("FCF Metric:", ["Free Cash Flow", "FCF - SBC"], horizontal=True, key="fcf_radio")
            fcf_col = 'fcf_minus_sbc' if fcf_option == "FCF - SBC" else 'freeCashFlow'
            render_metric_chart(cashflow_df, fcf_col, fcf_option, f"{fcf_option} ($)", cagr_periods=[1, 3, 5])

            # FCF Yield
            render_fcf_yield(cashflow_df, market_cap)

            # Margins with Toggle
            margin_option = st.radio("Select Margin:", ["Gross Margin", "Operating Margin", "Net Margin"], horizontal=True, key="margin_radio")
            margin_map = {"Gross Margin": 'grossProfitRatio', "Operating Margin": 'operatingIncomeRatio', "Net Margin": 'netIncomeRatio'}
            render_metric_chart(income_df, margin_map[margin_option], margin_option, f"{margin_option} (%)")

        else:
            st.error("No data found for this ticker.")
            
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            st.error(f"Stock ticker not found: {st.session_state['ticker']}")
        else:
            st.error(f"Error fetching data: HTTP Status {e.response.status_code}")
    except Exception as e:
        st.error(f"An unexpected error occurred: {str(e)}")
else:
    st.info("👈 Enter a stock ticker in the sidebar to begin analysis.")