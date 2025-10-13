#!/usr/bin/env python3
"""
Streamlit Financial Data Visualizer
Interactive charts for FCF, EPS, and FCF Yield analysis
"""

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from datetime import datetime
import sys
import os

# Import the backend API (assuming it's in the same directory)
# You may need to adjust this import based on your file structure
try:
    from sec_edgar_api import get_financial_data
except ImportError:
    st.error("Could not import sec_edgar_api.py. Make sure it's in the same directory.")
    sys.exit(1)

# ----------------------------
# Page Configuration
# ----------------------------

st.set_page_config(
    page_title="Financial Data Analyzer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ----------------------------
# Helper Functions
# ----------------------------

def format_currency(value, decimals=0):
    """Format large numbers as readable currency."""
    if value is None:
        return "N/A"
    
    abs_value = abs(value)
    if abs_value >= 1e12:
        return f"${value/1e12:.{decimals}f}T"
    elif abs_value >= 1e9:
        return f"${value/1e9:.{decimals}f}B"
    elif abs_value >= 1e6:
        return f"${value/1e6:.{decimals}f}M"
    else:
        return f"${value:,.{decimals}f}"

def create_fcf_chart(data, subtract_sbc=False):
    """
    Create interactive FCF chart using stacked bars.
    The stack visualizes FCF + CapEx = CFO.
    """
    fcf_data = data.get("free_cash_flow_annual", [])
    sbc_data = data.get("stock_based_compensation_annual", [])
    
    if not fcf_data:
        return None
    
    # Create DataFrame
    df = pd.DataFrame(fcf_data)
    df = df.sort_values("year")
    
    # Add SBC data
    sbc_dict = {item["year"]: item["value"] for item in sbc_data}
    df["sbc"] = df["year"].map(sbc_dict).fillna(0)
    df["fcf_minus_sbc"] = df["value"] - df["sbc"]
    
    # Determine the FCF component to plot (base of the stack)
    if subtract_sbc:
        df["fcf_to_plot"] = df["fcf_minus_sbc"]
        fcf_label = "FCF (after SBC)"
    else:
        df["fcf_to_plot"] = df["value"]
        fcf_label = "FCF (before SBC)"
    
    # The CapEx component (stacked on top)
    # CFO = FCF + CapEx (where CapEx is a positive outflow amount)
    df["capex_to_plot"] = df["capex"]
    
    # Calculate the total height for reference (CFO)
    df["cfo_total"] = df["fcf_to_plot"] + df["capex_to_plot"]

    # Create figure
    fig = go.Figure()
    
    # 1. Add FCF bars (Bottom component)
    fig.add_trace(go.Bar(
        x=df["year"],
        y=df["fcf_to_plot"],
        name=fcf_label,
        marker_color="#1f77b4", # Blue
        hovertemplate="<b>Year %{x}</b><br>" +
                      "FCF: %{y:,.0f}<br>" +
                      "<extra></extra>"
    ))
    
    # 2. Add CapEx bars (Top component, stacked)
    fig.add_trace(go.Bar(
        x=df["year"],
        y=df["capex_to_plot"],
        name="Capital Expenditure",
        marker_color="#2ca02c", # Green color for the difference
        hovertemplate="<b>Year %{x}</b><br>" +
                      "CapEx: %{y:,.0f}<br>" +
                      "CFO (Total): %{customdata:,.0f}<br>" +
                      "<extra></extra>",
        customdata=df["cfo_total"]
    ))
    
    # Optional: Add SBC line (negative) if subtracting SBC
    if subtract_sbc:
        fig.add_trace(go.Scatter(
            x=df["year"],
            y=-df["sbc"],
            name="SBC (negative)",
            mode="lines+markers",
            line=dict(color="#ff7f0e", width=2, dash="dot"),
            marker=dict(size=8),
            hovertemplate="<b>Year %{x}</b><br>" +
                          "SBC: %{y:,.0f}<br>" +
                          "<extra></extra>"
        ))
    
    fig.update_layout(
        title="Cash Flow Composition: FCF + CapEx = CFO (Past 5 Years)",
        xaxis_title="Year",
        yaxis_title="Amount (USD)",
        barmode='stack', # Key setting for stacked bar chart
        hovermode="x unified",
        template="plotly_white",
        height=500,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    return fig

def create_eps_chart(data):
    """Create EPS chart showing quarterly data."""
    eps_data = data.get("eps_quarterly", [])
    
    if not eps_data:
        return None
    
    # Create DataFrame
    df = pd.DataFrame(eps_data)
    df = df.sort_values(["year", "quarter"])
    
    # Create quarter label
    df["quarter_label"] = df["year"].astype(str) + " " + df["quarter"]
    
    # Take last 20 quarters (5 years)
    df = df.tail(20)
    
    # Create figure
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=df["quarter_label"],
        y=df["value"],
        mode="lines+markers",
        name="EPS",
        line=dict(color="#1f77b4", width=2),
        marker=dict(size=8),
        fill="tozeroy",
        fillcolor="rgba(31, 119, 180, 0.1)",
        hovertemplate="<b>%{x}</b><br>" +
                      "EPS: $%{y:.2f}<br>" +
                      "<extra></extra>"
    ))
    
    fig.update_layout(
        title="Earnings Per Share - Quarterly (Past 5 Years)",
        xaxis_title="Quarter",
        yaxis_title="EPS (USD)",
        hovermode="x unified",
        template="plotly_white",
        height=400,
        xaxis=dict(tickangle=-45)
    )
    
    return fig

def create_fcf_yield_chart(data):
    """Create FCF Yield chart."""
    fcf_data = data.get("free_cash_flow_annual", [])
    sbc_data = data.get("stock_based_compensation_annual", [])
    market_cap_data = data.get("market_cap_annual", [])
    
    if not fcf_data or not market_cap_data:
        return None
    
    # Create DataFrame
    df = pd.DataFrame(fcf_data)
    df = df.sort_values("year")
    
    # Add SBC and Market Cap
    sbc_dict = {item["year"]: item["value"] for item in sbc_data}
    cap_dict = {item["year"]: item["value"] for item in market_cap_data}
    
    df["sbc"] = df["year"].map(sbc_dict).fillna(0)
    df["market_cap"] = df["year"].map(cap_dict)
    
    # Calculate FCF Yield
    df["fcf_after_sbc"] = df["value"] - df["sbc"]
    df["fcf_yield"] = (df["fcf_after_sbc"] / df["market_cap"]) * 100
    
    # Create figure with dual axis
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Add FCF Yield line
    fig.add_trace(
        go.Scatter(
            x=df["year"],
            y=df["fcf_yield"],
            name="FCF Yield (%)",
            mode="lines+markers",
            line=dict(color="#2ca02c", width=3),
            marker=dict(size=10),
            hovertemplate="<b>Year %{x}</b><br>" +
                          "FCF Yield: %{y:.2f}%<br>" +
                          "<extra></extra>"
        ),
        secondary_y=False
    )
    
    # Add Market Cap bars
    fig.add_trace(
        go.Bar(
            x=df["year"],
            y=df["market_cap"],
            name="Market Cap",
            marker_color="rgba(31, 119, 180, 0.3)",
            hovertemplate="<b>Year %{x}</b><br>" +
                          "Market Cap: %{y:,.0f}<br>" +
                          "<extra></extra>"
        ),
        secondary_y=True
    )
    
    # Update axes
    fig.update_xaxes(title_text="Year")
    fig.update_yaxes(title_text="FCF Yield (%)", secondary_y=False)
    fig.update_yaxes(title_text="Market Cap (USD)", secondary_y=True)
    
    fig.update_layout(
        title="Free Cash Flow Yield (Past 5 Years)<br><sub>(FCF - SBC) / Market Cap</sub>",
        hovermode="x unified",
        template="plotly_white",
        height=500,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    return fig

# ----------------------------
# Main App
# ----------------------------

def main():
    st.title("📊 Financial Data Analyzer")
    st.markdown("Analyze Free Cash Flow, EPS, and FCF Yield from SEC filings")
    
    # Sidebar
    with st.sidebar:
        st.header("Settings")
        
        ticker = st.text_input(
            "Stock Ticker",
            value="AAPL",
            help="Enter a valid stock ticker (e.g., AAPL, MSFT, GOOGL)"
        ).upper()
        
        subtract_sbc = st.checkbox(
            "Subtract Stock-Based Compensation",
            value=True,
            help="Show FCF after subtracting stock-based compensation"
        )
        
        fetch_button = st.button("Fetch Data", type="primary", use_container_width=True)
        
        st.markdown("---")
        st.markdown("### About")
        st.markdown("""
        This tool fetches financial data from SEC EDGAR filings and visualizes:
        - Free Cash Flow trends
        - Earnings Per Share
        - FCF Yield relative to market cap
        """)
    
    # Main content
    if fetch_button or "data" not in st.session_state:
        if fetch_button:
            with st.spinner(f"Fetching data for {ticker}..."):
                result = get_financial_data(ticker)
                
                if result["status"] == "success":
                    st.session_state.data = result["data"]
                    st.session_state.metadata = result["metadata"]
                    st.session_state.ticker = ticker
                    st.success(f"Data loaded for {ticker}")
                else:
                    st.error(f"Error: {result['error']['message']}")
                    return
    
    if "data" not in st.session_state:
        st.info("👈 Enter a ticker and click 'Fetch Data' to begin")
        return
    
    data = st.session_state.data
    metadata = st.session_state.metadata
    
    # Header with company info
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Company", data.get("stock_name", "N/A"))
    
    with col2:
        price = data.get("stock_price")
        st.metric("Stock Price", f"${price:.2f}" if price else "N/A")
    
    with col3:
        market_cap = data.get("market_cap")
        st.metric("Market Cap", format_currency(market_cap, 2) if market_cap else "N/A")
    
    with col4:
        shares = data.get("shares_outstanding")
        st.metric("Shares Out", format_currency(shares, 2) if shares else "N/A")
    
    st.markdown("---")
    
    # Free Cash Flow Chart
    st.subheader("Cash Flow Composition (FCF + CapEx = CFO)")
    fcf_chart = create_fcf_chart(data, subtract_sbc)
    if fcf_chart:
        st.plotly_chart(fcf_chart, use_container_width=True)
    else:
        st.warning("No FCF data available")
    
    # EPS Chart
    st.subheader("Earnings Per Share")
    eps_chart = create_eps_chart(data)
    if eps_chart:
        st.plotly_chart(eps_chart, use_container_width=True)
    else:
        st.warning("No EPS data available")
    
    # FCF Yield Chart
    st.subheader("Free Cash Flow Yield")
    
    # Check if we have market cap history
    if not data.get("market_cap_annual"):
        st.info("⚠️ Historical market cap data not available. FCF Yield chart requires market cap for each year.")
        st.markdown("""
        To calculate FCF Yield, we need:
        - **FCF - SBC** (Cash available after operations and stock compensation)
        - **Market Cap** for each historical year
        
        The current API only provides current market cap. Historical market cap would need to be added.
        """)
    else:
        fcf_yield_chart = create_fcf_yield_chart(data)
        if fcf_yield_chart:
            st.plotly_chart(fcf_yield_chart, use_container_width=True)
        else:
            st.warning("Unable to create FCF Yield chart")
    
    # Data source info
    with st.expander("📋 Data Source Information"):
        st.json(metadata)

if __name__ == "__main__":
    main()
