---
marp: true
size: 4:3
paginate: true
---

# 📄 Stock Analysis Dashboard Documentation

This Streamlit application is a financial dashboard designed to provide a quick, visual analysis of a stock's historical performance, growth rates, and key profitability metrics by integrating data from the Financial Modeling Prep (FMP) and Polygon.io APIs.

---

### 1. Setup and Installation 🛠️
Prerequisites:

Python 3.8+

A valid Financial Modeling Prep (FMP) API Key.

A valid Polygon.io API Key.

---

### Installation Steps:

Install dependencies using the required packages:

Bash

pip install streamlit requests pandas plotly python-dotenv
Create a .env file in the project's root directory to securely store your API keys:

Ini, TOML

# .env
FMP_API_KEY="YOUR_FMP_API_KEY_HERE"
POLYGON_API_KEY="YOUR_POLYGON_API_KEY_HERE"
Run the application from your terminal:

Bash

streamlit run your_script_name.py

---

### 2. Application Structure 🏗️
The program is organized into logical sections to separate data fetching, business logic, and presentation:

Imports and Configuration: Imports libraries, loads environment variables, and sets the Streamlit page layout (st.set_page_config).

API Functions: Contains cached functions (decorated with @st.cache_data(ttl=3600)) for fetching financial and historical data.

Business Logic: Includes helper functions for financial calculations, primarily CAGR (Compound Annual Growth Rate).

Streamlit Sidebar: Handles user interaction (ticker input).

Main Dashboard Logic: Coordinates data retrieval, processing into pandas DataFrames, and rendering all metrics and charts using Plotly.


---

### 3. Core API Functions and Caching ⏱️
All data fetching functions are designed to use Streamlit's caching mechanism to improve performance and minimize redundant API calls. The data is refreshed hourly (ttl=3600).

Function Name	API / Service	Data Fetched	Purpose
get_stock_info	FMP (/profile)	Company name, Market Cap, current Price.	Core company metrics.
get_quote	FMP (/quote)	Latest trading metrics (Day High/Low, Day Change).	Current trading summary.
get_income_statement	FMP (/income-statement)	Annual Revenue, EPS, Gross Profit, etc.	Basis for growth and margin analysis.
get_cash_flow	FMP (/cash-flow-statement)	Free Cash Flow (FCF), Stock-Based Compensation (SBC).	FCF and FCF Yield calculations.
get_historical_chart	Polygon (/aggs/...)	5 years of daily historical price data.	Price history visualization.

---

### 4. Financial Calculations and Logic ⚙️
The dashboard includes custom financial metrics that go beyond raw API data:

Calculation	Formula/Metrics Used	Location
CAGR (Compound Annual Growth Rate)	(((End Value/Start Value) 
1/Years
 )−1)×100	Functions: calculate_cagr, get_cagr_for_metric.
P/E Ratio	Current Share Price / Annual Diluted EPS	Plotted historically.
FCF - SBC (Adjusted Free Cash Flow)	freeCashFlow - stockBasedCompensation	User-selectable toggle in the FCF chart.
FCF Yield	(FCF−SBC)/Current Market Cap×100	Calculated and plotted as a percentage.
Profit Margins	(Gross/Operating/Net Income) / Revenue	Calculated dynamically and visualized based on user selection.

---