"""
Compatibility shim module for tests and entry-points that expect `main`.

This module re-exports classes from `app.py` and `financial_data_processor.py`
so tests that import from `main` continue to work without changing tests.
"""
from app import ChartRenderer, MetricsDisplay, DashboardApp  # noqa: F401
from financial_data_processor import APIClient, FinancialDataService, FinancialDataProcessor  # noqa: F401

__all__ = [
    "ChartRenderer",
    "MetricsDisplay",
    "DashboardApp",
    "APIClient",
    "FinancialDataService",
    "FinancialDataProcessor",
]
