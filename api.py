# import requests
# from typing import Dict, Any, List, Optional
# from datetime import datetime
# import json
# from dotenv import load_dotenv
# import os

# load_dotenv()

# FMP_API_KEY = os.getenv("FMP_API_KEY")
# FMP_BASE_URL = "https://financialmodelingprep.com/stable"

# def main():
#     ticker = getUserInput()
#     getStockByName(ticker, FMP_API_KEY)
#     getStockInfo(ticker, FMP_API_KEY)
#     getIncomeStatement(ticker, FMP_API_KEY, "annual", 5)
#     getBalanceSheet(ticker, FMP_API_KEY)
#     getCashFlow(ticker, FMP_API_KEY)


# def getUserInput():
#     ticker = input("Enter the stock ticker symbol (e.g., AAPL): ").upper()
#     return ticker

# def getStockByName(ticker, api_key):
#     params = {
#       "query": ticker,
#       "apikey": api_key
#     }
    
#     response = requests.get(f"{FMP_BASE_URL}/search-symbol", params=params)
#     response.raise_for_status()
#     data = response.json()
#     # pretty_json = json.dumps(data, indent=4)
#     # Now i need to search th json for the exact ticker match
#     for item in data:
#         if item['symbol'] == ticker:
#             print(f"Found exact match: {item}")
#     return item

# def getStockInfo(ticker, api_key):
#     params = {
#         "symbol": ticker,
#         "apikey": api_key
#     }
#     response = requests.get(f"{FMP_BASE_URL}/profile", params=params)
#     response.raise_for_status()
#     data = response.json()
#     pretty_json = json.dumps(data, indent=4)
#     print("Stock Info:")
#     print(pretty_json)
#     return data

# def getIncomeStatement(ticker, api_key, period, limit):
#     params = {
#         "period": period,
#         "limit": limit,
#         "apikey": api_key
#     }
#     response = requests.get(f"{FMP_BASE_URL}/income-statement?symbol=AAPL", params=params)
#     response.raise_for_status()
#     data = response.json()
#     pretty_json = json.dumps(data, indent=4)
#     print("Income Statement:")
#     print(pretty_json)
#     return data
# def getBalanceSheet(ticker, api_key):
#     params = {
#         "apikey": api_key
#     }
#     response = requests.get(f"{FMP_BASE_URL}/balance-sheet-statement?symbol={ticker}", params=params)
#     response.raise_for_status()
#     data = response.json()
#     pretty_json = json.dumps(data, indent=4)
#     print("Balance Sheet:")
#     print(pretty_json)
#     return data

# def getCashFlow(ticker, api_key):
#     params = {
#         "apikey": api_key
#     }
#     response = requests.get(f"{FMP_BASE_URL}/cash-flow-statement?symbol={ticker}", params=params)
#     response.raise_for_status()
#     data = response.json()
#     pretty_json = json.dumps(data, indent=4)
#     print("Cash Flow Statement:")
#     print(pretty_json)
#     return data


# if __name__ == "__main__":
#     main()
