---
marp: true
size: 4:3
paginate: true
---


# 🚀 Quick Start Guide: Stock Analysis Dashboard
Welcome to Your Analysis Tool!
This dashboard provides a comprehensive view of a stock's performance, key financial metrics, and valuation ratios over the last 5 years.

It relies on external APIs (FMP and Polygon) for real-time and historical data.

---

## 1. Getting Started: Analyze a Ticker
To begin your analysis, visit the live site! - https://freecashflowtool-rmxuchyhfbk6wrx5vgingf.streamlit.app/

Steps:
Locate the Sidebar: Look for the Stock Selection header.

Enter Ticker: Input the stock symbol (e.g., AAPL, MSFT, GOOG) into the text box.

Run Analysis: Click the Analyze Stock button.

The dashboard will update in real-time with company profile, quote, and historical financial data.

---

## 2. Dashboard Overview (The Main View)
After entering a ticker, the main screen presents data in clear, sectioned views:

Overview & Quote
Company Name & Market Cap: High-level details.

Real-time Metrics: Current Price, Day Change, Day High/Low.

📈 Stock Price History
Displays monthly closing prices for the last 5 years using a line chart.

Financial Growth Metrics
Revenue, Diluted EPS, Shares Outstanding: Presented as bar charts showing annual trends.

CAGR (Compound Annual Growth Rate): Summary metrics are displayed beneath the charts for 1Y, 3Y, and 5Y periods.

---

## 3. Interactive Analysis Sections
These sections feature toggles for deeper analysis.

💵 Free Cash Flow (FCF)
Metric Toggle: Use the radio buttons to switch between:

Free Cash Flow (Standard)

FCF - SBC (Free Cash Flow minus Stock-Based Compensation)

💰 FCF Yield
Shows the ratio of FCF (minus SBC) to the company's Market Capitalization, indicating valuation attractiveness.

📊 Profit Margins
Select Margin: Use the radio buttons to view the trend for:

Gross Margin

Operating Margin

Net Margin

---

## Running locally 

### Running locally

1. Create and activate a virtual environment (recommended):

```bash
python3 -m venv my_project_env
source my_project_env/bin/activate
```

2. Install runtime and development dependencies:

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

3. Run the streamlit app locally:

```bash
streamlit run app.py
```

4. Run tests:

```bash
pytest -q
```

### Running using Docker (recommended for exact reproducibility)

1. Build the Docker image (first time):

```bash
docker build -t freecashflow-tool .
```

2. Run the test suite inside Docker:

```bash
docker run --rm -v "$(pwd):/app" freecashflow-tool
```

Or use docker-compose:

```bash
docker-compose up --build --abort-on-container-exit
```

This approach ensures a consistent environment across machines and avoids committing local virtualenvs or other hidden files.

Note: You'll need valid environment variables for the FMP and POLYGON API keys when running the app:
- FMP_API_KEY
- POLYGON_API_KEY

Add these to a `.env` file at the repo root or export them into your shell.

### Using a secure .env (do not commit)

We provide `.env.example` with placeholders for your convenience. DO NOT commit a `.env` containing secrets. Copy it and provide your own keys:

```bash
cp .env.example .env
# then fill in your keys
```

This repo ignores `.env` and locally created virtual environments so they are not shared with colleagues.
