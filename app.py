import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

FMP_API_KEY = os.getenv("FMP_API_KEY")
FMP_BASE_URL = "https://financialmodelingprep.com/stable"
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")
POLYGON_BASE_URL = "https://api.polygon.io/v2"

st.set_page_config(page_title="Stock Analysis Dashboard", layout="wide")

# API Functions
@st.cache_data(ttl=3600)
def get_stock_info(ticker, api_key):
    params = {"symbol": ticker, "apikey": api_key}
    response = requests.get(f"{FMP_BASE_URL}/profile", params=params)
    response.raise_for_status()
    return response.json()

@st.cache_data(ttl=3600)
def get_income_statement(ticker, api_key, period="annual", limit=5):
    params = {"period": period, "limit": limit, "apikey": api_key}
    response = requests.get(f"{FMP_BASE_URL}/income-statement?symbol={ticker}", params=params)
    response.raise_for_status()
    #print("INCOME statement", response.json())
    return response.json()

@st.cache_data(ttl=3600)
def get_balance_sheet(ticker, api_key, limit=5):
    params = {"limit": limit, "apikey": api_key}
    response = requests.get(f"{FMP_BASE_URL}/balance-sheet-statement?symbol={ticker}", params=params)
    response.raise_for_status()
    #print("BALANCE SHEET", response.json())
    return response.json()

@st.cache_data(ttl=3600)
def get_cash_flow(ticker, api_key, limit=5):
    params = {"limit": limit, "apikey": api_key}
    response = requests.get(f"{FMP_BASE_URL}/cash-flow-statement?symbol={ticker}", params=params)
    response.raise_for_status()
    #print("CASH FLOW", response.json())
    return response.json()

@st.cache_data(ttl=3600)
def get_quote(ticker, api_key):
    params = {"symbol": ticker, "apikey": api_key}
    response = requests.get(f"{FMP_BASE_URL}/quote", params=params)
    response.raise_for_status()
    print("QUOTE DATA", response.json())
    return response.json()

@st.cache_data(ttl=3600)
def get_historical_chart(ticker, api_key):
    # Calculate dates for 5 years ago
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - pd.DateOffset(years=5)).strftime('%Y-%m-%d')
    
    params = {
        "adjusted": "true",
        "sort": "asc",
        "limit": "50000",
        "apiKey": api_key
    }
    url = f"{POLYGON_BASE_URL}/aggs/ticker/{ticker}/range/1/day/{start_date}/{end_date}"
    response = requests.get(url, params=params)
    response.raise_for_status()
    print("POLYGON HISTORICAL DATA", response.json())
    return response.json()

def calculate_cagr(start_value, end_value, years):
    if start_value <= 0 or end_value <= 0 or years <= 0:
        return None
    return (((end_value / start_value) ** (1 / years)) - 1) * 100

def get_cagr_for_metric(df, metric_col, periods=[1, 2, 3, 5]):
    cagrs = {}
    for period in periods:
        if len(df) > period:
            start_val = df[metric_col].iloc[-1]
            end_val = df[metric_col].iloc[-(period+1)]
            cagr = calculate_cagr(end_val, start_val, period)
            if cagr is not None:
                cagrs[f"{period}Y"] = f"{cagr:.2f}%"
    return cagrs

# Streamlit App
st.title("📊 Stock Analysis Dashboard")

# Sidebar
with st.sidebar:
    st.header("Stock Selection")
    ticker = st.text_input("Enter Stock Ticker", value="AAPL").upper()
    
    if st.button("Analyze Stock", type="primary"):
        st.rerun()

if ticker and FMP_API_KEY and POLYGON_API_KEY:
    try:
        # Fetch data
        with st.spinner("Fetching stock data..."):
            stock_info = get_stock_info(ticker, FMP_API_KEY)
            quote_data = get_quote(ticker, FMP_API_KEY)
            historical_data = get_historical_chart(ticker, POLYGON_API_KEY)
            income_data = get_income_statement(ticker, FMP_API_KEY)
            balance_data = get_balance_sheet(ticker, FMP_API_KEY)
            cash_flow_data = get_cash_flow(ticker, FMP_API_KEY)
            
        if stock_info and len(stock_info) > 0:
            info = stock_info[0]
            
            # Company Overview Section
            st.header(f"{info.get('companyName', ticker)}")
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Ticker", info.get('symbol', 'N/A'))
            with col2:
                market_cap = info.get('mktCap') or info.get('marketCap') or info.get('market_cap', 0)
                st.metric("Market Cap", f"${market_cap/1e9:.2f}B" if market_cap else "N/A")
            with col3:
                price = info.get('price', 0)
                st.metric("Share Price", f"${price:.2f}" if price else "N/A")
            with col4:
                changes = info.get('changes') or info.get('change', 0)
                st.metric("Change", f"${changes:.2f}" if changes else "N/A", 
                         delta=f"{changes:.2f}" if changes else None)
            
            st.divider()
            
            # Prepare DataFrames
            if income_data:
                income_df = pd.DataFrame(income_data)
                income_df['date'] = pd.to_datetime(income_df['date'])
                income_df = income_df.sort_values('date')
            
            if balance_data:
                balance_df = pd.DataFrame(balance_data)
                balance_df['date'] = pd.to_datetime(balance_df['date'])
                balance_df = balance_df.sort_values('date')
            
            if cash_flow_data:
                cashflow_df = pd.DataFrame(cash_flow_data)
                cashflow_df['date'] = pd.to_datetime(cashflow_df['date'])
                cashflow_df = cashflow_df.sort_values('date')
            
            # Stock Price Chart
            st.subheader("📈 Stock Price History (5 Years)")
            try:
                if historical_data and 'results' in historical_data:
                    # Convert Polygon data to DataFrame
                    results = historical_data['results']
                    price_df = pd.DataFrame(results)
                    
                    # Polygon uses 't' for timestamp (in milliseconds), 'c' for close
                    price_df['date'] = pd.to_datetime(price_df['t'], unit='ms')
                    price_df['close'] = price_df['c']
                    price_df = price_df.sort_values('date')
                    
                    # Resample to monthly data (get last day of each month)
                    price_df = price_df.set_index('date')
                    monthly_df = price_df.resample('ME').last().reset_index()
                    
                    # Create line chart
                    fig_price = go.Figure()
                    fig_price.add_trace(go.Scatter(
                        x=monthly_df['date'], 
                        y=monthly_df['close'],
                        mode='lines',
                        name='Close Price',
                        line=dict(color='#1f77b4', width=2),
                        hovertemplate='<b>Date:</b> %{x|%Y-%m-%d}<br><b>Price:</b> $%{y:.2f}<extra></extra>'
                    ))
                    fig_price.update_layout(
                        height=400,
                        xaxis_title="Date",
                        yaxis_title="Price ($)",
                        hovermode='x unified',
                        showlegend=False
                    )
                    st.plotly_chart(fig_price, use_container_width=True)
                    
                    # Display current price metrics below chart
                    if quote_data and len(quote_data) > 0:
                        quote = quote_data[0]
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Current Price", f"${quote.get('price', 0):.2f}")
                        with col2:
                            day_change = quote.get('change', 0)
                            day_change_pct = quote.get('changesPercentage', 0)
                            st.metric("Day Change", f"${day_change:.2f}", 
                                    delta=f"{day_change_pct:.2f}%")
                        with col3:
                            st.metric("Day High", f"${quote.get('dayHigh', 0):.2f}")
                        with col4:
                            st.metric("Day Low", f"${quote.get('dayLow', 0):.2f}")
            except Exception as e:
                st.info(f"Price data not available: {str(e)}")
            
            # Revenue Chart
            st.subheader("💰 Revenue")
            if income_data and 'revenue' in income_df.columns:
                fig_rev = px.bar(
                    income_df, 
                    x='date', 
                    y='revenue',
                    labels={'revenue': 'Revenue ($)', 'date': 'Year'}
                )
                fig_rev.update_layout(height=400, showlegend=False)
                st.plotly_chart(fig_rev, use_container_width=True)
                
                cagr = get_cagr_for_metric(income_df, 'revenue')
                if cagr:
                    cols = st.columns(len(cagr))
                    for i, (period, value) in enumerate(cagr.items()):
                        cols[i].metric(f"Revenue CAGR {period}", value)
            
            # Diluted EPS Chart
            st.subheader("📊 Diluted EPS")
            if income_data and 'epsDiluted' in income_df.columns:
                fig_eps = px.bar(
                    income_df,
                    x='date',
                    y='epsDiluted',
                    labels={'epsDiluted': 'Diluted EPS ($)', 'date': 'Year'}
                )
                fig_eps.update_layout(height=400, showlegend=False)
                st.plotly_chart(fig_eps, use_container_width=True)
                
                cagr = get_cagr_for_metric(income_df, 'epsDiluted')
                if cagr:
                    cols = st.columns(len(cagr))
                    for i, (period, value) in enumerate(cagr.items()):
                        cols[i].metric(f"EPS CAGR {period}", value)
            
            # PE Ratio Chart
            st.subheader("📉 P/E Ratio")
            if income_data and 'revenue' in income_df.columns:
                # Calculate P/E ratio if not available
                if 'pe' not in income_df.columns and 'epsDiluted' in income_df.columns:
                    # Use current price divided by historical EPS
                    income_df['pe'] = price / income_df['epsDiluted']
                
                if 'pe' in income_df.columns:
                    fig_pe = go.Figure()
                    fig_pe.add_trace(go.Scatter(
                        x=income_df['date'],
                        y=income_df['pe'],
                        mode='lines+markers',
                        name='P/E Ratio',
                        line=dict(color='#ff7f0e', width=2)
                    ))
                    fig_pe.update_layout(
                        height=400,
                        xaxis_title="Year",
                        yaxis_title="P/E Ratio"
                    )
                    st.plotly_chart(fig_pe, use_container_width=True)
            
            # Shares Outstanding Chart
            st.subheader("📋 Shares Outstanding")
            if income_data and 'weightedAverageShsOutDil' in income_df.columns:
                fig_shares = go.Figure()
                fig_shares.add_trace(go.Scatter(
                    x=income_df['date'],
                    y=income_df['weightedAverageShsOutDil'],
                    mode='lines+markers',
                    name='Shares Outstanding',
                    fill='tozeroy',
                    line=dict(color='#2ca02c', width=2)
                ))
                fig_shares.update_layout(
                    height=400,
                    xaxis_title="Year",
                    yaxis_title="Shares Outstanding"
                )
                st.plotly_chart(fig_shares, use_container_width=True)
            
            # Free Cash Flow Chart with Toggle
            st.subheader("💵 Free Cash Flow")
            if cash_flow_data:
                fcf_option = st.radio(
                    "Select Metric:",
                    ["Free Cash Flow", "FCF - SBC"],
                    horizontal=True,
                    key="fcf_radio"
                )
                
                if 'freeCashFlow' in cashflow_df.columns:
                    if fcf_option == "Free Cash Flow":
                        metric_col = 'freeCashFlow'
                        metric_label = 'Free Cash Flow ($)'
                    else:
                        # Calculate FCF - SBC
                        if 'stockBasedCompensation' in cashflow_df.columns:
                            cashflow_df['fcf_minus_sbc'] = (
                                cashflow_df['freeCashFlow'] - 
                                cashflow_df['stockBasedCompensation']
                            )
                            metric_col = 'fcf_minus_sbc'
                            metric_label = 'FCF - SBC ($)'
                        else:
                            metric_col = 'freeCashFlow'
                            metric_label = 'Free Cash Flow ($)'
                    
                    fig_fcf = px.bar(
                        cashflow_df,
                        x='date',
                        y=metric_col,
                        labels={metric_col: metric_label, 'date': 'Year'}
                    )
                    fig_fcf.update_layout(height=400, showlegend=False)
                    st.plotly_chart(fig_fcf, use_container_width=True)
                    
                    cagr = get_cagr_for_metric(cashflow_df, metric_col)
                    if cagr:
                        cols = st.columns(len(cagr))
                        for i, (period, value) in enumerate(cagr.items()):
                            cols[i].metric(f"FCF CAGR {period}", value)
            
            # Free Cash Flow Yield Chart
            st.subheader("💰 Free Cash Flow Yield")
            if cash_flow_data:
                fcf_yield_df = cashflow_df.copy()
                
                if 'freeCashFlow' in fcf_yield_df.columns and 'stockBasedCompensation' in fcf_yield_df.columns:
                    # Calculate FCF - SBC
                    fcf_yield_df['fcf_minus_sbc'] = (
                        fcf_yield_df['freeCashFlow'] - 
                        fcf_yield_df['stockBasedCompensation']
                    )
                    
                    # Get current market cap - try different field names
                    current_market_cap = info.get('mktCap') or info.get('marketCap') or info.get('market_cap', 0)
                    
                    # Debug: print market cap value
                    # st.write(f"Debug - Market Cap: {current_market_cap}")
                    # st.write(f"Debug - Info keys: {list(info.keys())}")
                    
                    if current_market_cap > 0:
                        # Calculate FCF Yield as percentage: (FCF - SBC) / Market Cap * 100
                        fcf_yield_df['fcf_yield'] = (
                            fcf_yield_df['fcf_minus_sbc'] / current_market_cap
                        ) * 100
                        
                        fig_fcf_yield = px.bar(
                            fcf_yield_df,
                            x='date',
                            y='fcf_yield',
                            labels={'fcf_yield': 'FCF Yield (%)', 'date': 'Year'}
                        )
                        fig_fcf_yield.update_layout(height=400, showlegend=False)
                        st.plotly_chart(fig_fcf_yield, use_container_width=True)
                        
                        # Show average and latest yield
                        avg_yield = fcf_yield_df['fcf_yield'].mean()
                        latest_yield = fcf_yield_df['fcf_yield'].iloc[-1]
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Average FCF Yield", f"{avg_yield:.2f}%")
                        with col2:
                            st.metric("Latest FCF Yield", f"{latest_yield:.2f}%")
                    else:
                        st.info("Unable to calculate FCF Yield: market cap data not available")
                else:
                    st.info("Unable to calculate FCF Yield: required cash flow data not available")
            
            # Margins Chart with Toggle
            st.subheader("📊 Profit Margins")
            if income_data:
                margin_option = st.radio(
                    "Select Margin:",
                    ["Gross Margin", "Operating Margin", "Net Margin"],
                    horizontal=True
                )
                
                # Calculate margins if not present
                if 'grossProfitRatio' not in income_df.columns:
                    income_df['grossProfitRatio'] = (
                        income_df['grossProfit'] / income_df['revenue'] * 100
                    )
                if 'operatingIncomeRatio' not in income_df.columns:
                    income_df['operatingIncomeRatio'] = (
                        income_df['operatingIncome'] / income_df['revenue'] * 100
                    )
                if 'netIncomeRatio' not in income_df.columns:
                    income_df['netIncomeRatio'] = (
                        income_df['netIncome'] / income_df['revenue'] * 100
                    )
                
                margin_map = {
                    "Gross Margin": 'grossProfitRatio',
                    "Operating Margin": 'operatingIncomeRatio',
                    "Net Margin": 'netIncomeRatio'
                }
                
                metric_col = margin_map[margin_option]
                
                if metric_col in income_df.columns:
                    fig_margin = px.bar(
                        income_df,
                        x='date',
                        y=metric_col,
                        labels={metric_col: f'{margin_option} (%)', 'date': 'Year'}
                    )
                    fig_margin.update_layout(height=400, showlegend=False)
                    st.plotly_chart(fig_margin, use_container_width=True)
        else:
            st.error("No data found for this ticker")
            
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching data: {str(e)}")
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
else:
    st.warning("Please enter a stock ticker and ensure FMP_API_KEY and POLYGON_API_KEY are set in your .env file")
    st.info("👈 Enter a stock ticker in the sidebar to begin")