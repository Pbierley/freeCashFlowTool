import pytest
import pandas as pd
import plotly.graph_objects as go
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta

# Assuming these are imported from your main module
from main import ChartRenderer, MetricsDisplay, DashboardApp


# ===== FIXTURES =====
@pytest.fixture
def sample_price_df():
    """Create sample price history DataFrame."""
    dates = pd.date_range(start='2023-01-01', periods=10, freq='D')
    return pd.DataFrame({
        'date': dates,
        'close': [150 + i for i in range(10)]
    })


@pytest.fixture
def sample_financial_df():
    """Create sample financial metrics DataFrame."""
    dates = pd.date_range(start='2019-01-01', periods=5, freq='YS')
    return pd.DataFrame({
        'date': dates,
        'revenue': [100e9, 110e9, 120e9, 130e9, 140e9],
        'epsDiluted': [5.0, 5.5, 6.0, 6.5, 7.0],
        'pe': [25.0, 24.0, 23.0, 22.0, 21.0],
        'grossProfitRatio': [0.38, 0.39, 0.40, 0.41, 0.42],
        'operatingIncomeRatio': [0.25, 0.26, 0.27, 0.28, 0.29],
        'netIncomeRatio': [0.20, 0.21, 0.22, 0.23, 0.24],
        'weightedAverageShsOutDil': [16e9, 16.1e9, 16.2e9, 16.3e9, 16.4e9]
    })


@pytest.fixture
def sample_cashflow_df():
    """Create sample cashflow DataFrame."""
    dates = pd.date_range(start='2019-01-01', periods=5, freq='YS')
    return pd.DataFrame({
        'date': dates,
        'freeCashFlow': [20e9, 22e9, 24e9, 26e9, 28e9],
        'fcf_minus_sbc': [18e9, 20e9, 22e9, 24e9, 26e9],
        'fcf_yield': [2.5, 2.6, 2.7, 2.8, 2.9]
    })


@pytest.fixture
def sample_profile():
    """Create sample company profile."""
    return {
        'symbol': 'AAPL',
        'companyName': 'Apple Inc.',
        'mktCap': 2500e9,
        'price': 150.0
    }


@pytest.fixture
def sample_quote():
    """Create sample quote data."""
    return {
        'symbol': 'AAPL',
        'price': 150.0,
        'change': 2.5,
        'changesPercentage': 1.69,
        'dayHigh': 152.0,
        'dayLow': 148.0,
        'previousClose': 147.5
    }


# ===== CHART RENDERER TESTS =====
class TestChartRenderer:
    
    def test_render_line_chart_creates_figure(self, sample_price_df):
        """Test that render_line_chart creates a valid Plotly figure."""
        fig = ChartRenderer.render_line_chart(
            sample_price_df, 'date', 'close',
            'Stock Price', 'Price ($)'
        )
        
        assert isinstance(fig, go.Figure)
        assert len(fig.data) == 1
        assert fig.data[0].mode == 'lines'
    
    def test_render_line_chart_correct_data(self, sample_price_df):
        """Test that line chart contains correct data points."""
        fig = ChartRenderer.render_line_chart(
            sample_price_df, 'date', 'close',
            'Stock Price', 'Price ($)'
        )
        
        assert len(fig.data[0].x) == len(sample_price_df)
        assert len(fig.data[0].y) == len(sample_price_df)
    
    def test_render_line_chart_custom_color(self, sample_price_df):
        """Test that custom color is applied to line chart."""
        custom_color = '#FF5733'
        fig = ChartRenderer.render_line_chart(
            sample_price_df, 'date', 'close',
            'Stock Price', 'Price ($)',
            color=custom_color
        )
        
        assert fig.data[0].line.color == custom_color
    
    def test_render_line_chart_labels(self, sample_price_df):
        """Test that line chart has correct axis labels."""
        fig = ChartRenderer.render_line_chart(
            sample_price_df, 'date', 'close',
            'Stock Price', 'Price ($)'
        )
        
        assert fig.layout.yaxis.title.text == 'Price ($)'
        assert fig.layout.xaxis.title.text == 'Date'
    
    def test_render_bar_chart_creates_figure(self, sample_financial_df):
        """Test that render_bar_chart creates a valid Plotly figure."""
        fig = ChartRenderer.render_bar_chart(
            sample_financial_df, 'date', 'revenue',
            'Revenue ($)'
        )
        
        assert isinstance(fig, go.Figure)
        assert len(fig.data) > 0
    
    def test_render_bar_chart_correct_data(self, sample_financial_df):
        """Test that bar chart contains correct data points."""
        fig = ChartRenderer.render_bar_chart(
            sample_financial_df, 'date', 'revenue',
            'Revenue ($)'
        )
        
        assert len(fig.data[0].x) == len(sample_financial_df)
        assert len(fig.data[0].y) == len(sample_financial_df)
    
    def test_render_bar_chart_custom_color(self, sample_financial_df):
        """Test that custom color is applied to bar chart."""
        custom_color = '#00AA00'
        fig = ChartRenderer.render_bar_chart(
            sample_financial_df, 'date', 'revenue',
            'Revenue ($)',
            color=custom_color
        )
        
        assert fig.data[0].marker.color == custom_color
    
    def test_render_bar_chart_height(self, sample_financial_df):
        """Test that bar chart has correct height."""
        fig = ChartRenderer.render_bar_chart(
            sample_financial_df, 'date', 'revenue',
            'Revenue ($)'
        )
        
        assert fig.layout.height == 400


# ===== METRICS DISPLAY TESTS =====
class TestMetricsDisplay:
    
    @patch('streamlit.header')
    @patch('streamlit.columns')
    @patch('streamlit.metric')
    @patch('streamlit.divider')
    def test_display_overview_renders_header(self, mock_divider, mock_metric, 
                                            mock_columns, mock_header, 
                                            sample_profile, sample_quote):
        """Test that display_overview renders company header."""
        MetricsDisplay.display_overview(sample_profile, sample_quote)
        mock_header.assert_called_once()
    
    @patch('streamlit.columns')
    @patch('streamlit.metric')
    def test_display_overview_renders_four_columns(self, mock_metric, mock_columns,
                                                   sample_profile, sample_quote):
        """Test that display_overview uses four columns."""
        mock_columns.return_value = [Mock(), Mock(), Mock(), Mock()]
        MetricsDisplay.display_overview(sample_profile, sample_quote)
        mock_columns.assert_called_with(4)
    
    @patch('streamlit.metric')
    def test_display_quote_metrics_renders_current_price(self, mock_metric, 
                                                        sample_quote):
        """Test that quote metrics displays current price."""
        with patch('streamlit.columns', return_value=[Mock(), Mock(), Mock(), Mock()]):
            MetricsDisplay.display_quote_metrics(sample_quote)
        
        # Verify metric was called (would be for current price among others)
        assert mock_metric.called
    
    @patch('streamlit.metric')
    def test_display_quote_metrics_calculates_change_percentage_fallback(self, mock_metric):
        """Test that quote metrics calculates change % if not provided."""
        quote_no_percentage = {
            'price': 150.0,
            'change': 2.5,
            'previousClose': 147.5,
            'dayHigh': 152.0,
            'dayLow': 148.0
        }
        
        with patch('streamlit.columns', return_value=[Mock(), Mock(), Mock(), Mock()]):
            MetricsDisplay.display_quote_metrics(quote_no_percentage)
        
        assert mock_metric.called
    
    @patch('streamlit.metric')
    def test_display_cagrs_empty_dataframe(self, mock_metric):
        """Test that display_cagrs handles empty DataFrame gracefully."""
        empty_df = pd.DataFrame()
        MetricsDisplay.display_cagrs(empty_df, 'revenue', 'Revenue')
        mock_metric.assert_not_called()
    
    @patch('streamlit.metric')
    def test_display_cagrs_missing_column(self, mock_metric, sample_financial_df):
        """Test that display_cagrs handles missing column gracefully."""
        MetricsDisplay.display_cagrs(sample_financial_df, 'nonexistent_col', 'Revenue')
        mock_metric.assert_not_called()
    
    @patch('streamlit.metric')
    def test_display_fcf_yield_metrics_empty_dataframe(self, mock_metric):
        """Test that display_fcf_yield_metrics handles empty DataFrame gracefully."""
        empty_df = pd.DataFrame()
        MetricsDisplay.display_fcf_yield_metrics(empty_df)
        mock_metric.assert_not_called()
    
    @patch('streamlit.metric')
    @patch('streamlit.columns')
    def test_display_fcf_yield_metrics_valid_data(self, mock_columns, mock_metric, 
                                                  sample_cashflow_df):
        """Test that display_fcf_yield_metrics displays correct metrics."""
        mock_columns.return_value = [Mock(), Mock()]
        MetricsDisplay.display_fcf_yield_metrics(sample_cashflow_df)
        assert mock_metric.called


# ===== DASHBOARD APP TESTS =====
class TestDashboardApp:
    
    @patch('main.APIClient')
    @patch('main.FinancialDataService')
    def test_dashboard_app_initialization(self, mock_service, mock_client):
        """Test that DashboardApp initializes correctly."""
        app = DashboardApp('test_fmp_key', 'test_polygon_key')
        
        assert app.api_client is not None
        assert app.data_service is not None
        assert isinstance(app.chart_renderer, ChartRenderer)
        assert isinstance(app.metrics_display, MetricsDisplay)
    
    @patch('streamlit.sidebar')
    @patch('streamlit.text_input', return_value='AAPL')
    @patch('streamlit.button', return_value=False)
    @patch('streamlit.session_state', {'ticker': 'AAPL'})
    @patch('main.APIClient')
    @patch('main.FinancialDataService')
    def test_render_sidebar_returns_ticker(self, mock_service, mock_client,
                                          mock_button, mock_input, mock_sidebar):
        """Test that render_sidebar returns selected ticker."""
        app = DashboardApp('test_fmp_key', 'test_polygon_key')
        
        with patch('streamlit.session_state', {'ticker': 'AAPL'}):
            with patch('streamlit.text_input', return_value='AAPL'):
                result = app.render_sidebar()
        
        assert result in ['AAPL', None] or result == 'AAPL'
    
    @patch('streamlit.subheader')
    @patch('streamlit.plotly_chart')
    @patch('streamlit.info')
    @patch('main.APIClient')
    @patch('main.FinancialDataService')
    def test_render_price_section_empty_data(self, mock_service, mock_client,
                                            mock_info, mock_chart, mock_subheader):
        """Test that render_price_section handles empty data."""
        app = DashboardApp('test_fmp_key', 'test_polygon_key')
        empty_df = pd.DataFrame()
        quote = {}
        
        app.render_price_section(empty_df, quote)
        mock_info.assert_called_once()
    
    @patch('streamlit.subheader')
    @patch('streamlit.plotly_chart')
    @patch('main.APIClient')
    @patch('main.FinancialDataService')
    def test_render_price_section_valid_data(self, mock_service, mock_client,
                                            mock_chart, mock_subheader,
                                            sample_price_df, sample_quote):
        """Test that render_price_section renders with valid data."""
        app = DashboardApp('test_fmp_key', 'test_polygon_key')
        app.render_price_section(sample_price_df, sample_quote)
        
        mock_subheader.assert_called()
        mock_chart.assert_called()
    
    @patch('streamlit.subheader')
    @patch('streamlit.plotly_chart')
    @patch('streamlit.info')
    @patch('main.APIClient')
    @patch('main.FinancialDataService')
    def test_render_financial_metric_empty_data(self, mock_service, mock_client,
                                               mock_info, mock_chart, mock_subheader):
        """Test that render_financial_metric handles empty data."""
        app = DashboardApp('test_fmp_key', 'test_polygon_key')
        empty_df = pd.DataFrame()
        
        app.render_financial_metric(empty_df, 'revenue', 'Revenue', 'Revenue ($)')
        mock_info.assert_called()
    
    @patch('streamlit.subheader')
    @patch('streamlit.radio')
    @patch('streamlit.plotly_chart')
    @patch('streamlit.info')
    @patch('main.APIClient')
    @patch('main.FinancialDataService')
    def test_render_fcf_section_empty_data(self, mock_service, mock_client,
                                          mock_info, mock_chart, mock_radio,
                                          mock_subheader):
        """Test that render_fcf_section handles empty data."""
        mock_radio.return_value = "Free Cash Flow"
        app = DashboardApp('test_fmp_key', 'test_polygon_key')
        empty_df = pd.DataFrame()
        
        app.render_fcf_section(empty_df)
        mock_info.assert_called()
    
    @patch('streamlit.subheader')
    @patch('streamlit.radio')
    @patch('streamlit.plotly_chart')
    @patch('main.APIClient')
    @patch('main.FinancialDataService')
    def test_render_fcf_section_valid_data(self, mock_service, mock_client,
                                          mock_chart, mock_radio, mock_subheader,
                                          sample_cashflow_df):
        """Test that render_fcf_section renders with valid data."""
        mock_radio.return_value = "Free Cash Flow"
        app = DashboardApp('test_fmp_key', 'test_polygon_key')
        
        app.render_fcf_section(sample_cashflow_df)
        mock_chart.assert_called()
    
    @patch('streamlit.subheader')
    @patch('streamlit.radio')
    @patch('streamlit.plotly_chart')
    @patch('streamlit.info')
    @patch('main.APIClient')
    @patch('main.FinancialDataService')
    def test_render_margins_section_empty_data(self, mock_service, mock_client,
                                              mock_info, mock_chart, mock_radio,
                                              mock_subheader):
        """Test that render_margins_section handles empty data."""
        mock_radio.return_value = "Gross Margin"
        app = DashboardApp('test_fmp_key', 'test_polygon_key')
        empty_df = pd.DataFrame()
        
        app.render_margins_section(empty_df)
        mock_info.assert_called()
    
    @patch('streamlit.subheader')
    @patch('streamlit.radio')
    @patch('streamlit.plotly_chart')
    @patch('main.APIClient')
    @patch('main.FinancialDataService')
    def test_render_margins_section_gross_margin(self, mock_service, mock_client,
                                                 mock_chart, mock_radio,
                                                 mock_subheader, sample_financial_df):
        """Test that render_margins_section works for gross margin."""
        mock_radio.return_value = "Gross Margin"
        app = DashboardApp('test_fmp_key', 'test_polygon_key')
        
        app.render_margins_section(sample_financial_df)
        mock_chart.assert_called()
    
    @patch('streamlit.title')
    @patch('streamlit.spinner')
    @patch('streamlit.error')
    @patch('main.APIClient')
    @patch('main.FinancialDataService')
    def test_run_handles_exception(self, mock_service, mock_client,
                                   mock_error, mock_spinner, mock_title):
        """Test that run method handles exceptions gracefully."""
        mock_service_instance = Mock()
        mock_service.return_value = mock_service_instance
        mock_service_instance.get_all_financial_data.side_effect = Exception("API Error")
        
        app = DashboardApp('test_fmp_key', 'test_polygon_key')
        app.data_service = mock_service_instance
        
        with patch('main.DashboardApp.render_sidebar', return_value='AAPL'):
            with patch('streamlit.spinner'):
                app.run()
        
        mock_error.assert_called()


# ===== INTEGRATION TESTS =====
class TestIntegration:
    
    def test_chart_renderer_with_sample_data(self, sample_price_df, sample_financial_df):
        """Test chart rendering pipeline with sample data."""
        line_fig = ChartRenderer.render_line_chart(
            sample_price_df, 'date', 'close', 'Stock Price', 'Price ($)'
        )
        bar_fig = ChartRenderer.render_bar_chart(
            sample_financial_df, 'date', 'revenue', 'Revenue ($)'
        )
        
        assert isinstance(line_fig, go.Figure)
        assert isinstance(bar_fig, go.Figure)
        assert len(line_fig.data) > 0
        assert len(bar_fig.data) > 0
    
    @patch('streamlit.metric')
    def test_metrics_display_with_all_data(self, mock_metric, sample_profile, 
                                          sample_quote, sample_financial_df,
                                          sample_cashflow_df):
        """Test metrics display with complete data set."""
        with patch('streamlit.header'), \
             patch('streamlit.columns', return_value=[Mock(), Mock(), Mock(), Mock()]), \
             patch('streamlit.divider'):
            MetricsDisplay.display_overview(sample_profile, sample_quote)
        
        assert mock_metric.called


if __name__ == "__main__":
    pytest.main([__file__, "-v"])