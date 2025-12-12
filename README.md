# 📈 Trading Strategy Backtester

A modern, web-based backtesting platform for trading strategies built with FastAPI and Backtesting.py.

## ✨ Features

- **Interactive Dashboard**: Beautiful, responsive web interface with real-time results
- **SMA Crossover Strategy**: Pre-configured Simple Moving Average crossover strategy
- **Visual Analytics**: Dynamic equity curve visualization using Chart.js
- **Performance Metrics**: Comprehensive statistics including Sharpe ratio, max drawdown, win rate
- **Data Validation**: Pydantic models for robust request/response handling
- **Fast & Modern**: Built with FastAPI for high performance

## 🏗️ Project Structure

```
├── data/
│   └── SPY.csv            # Historical market data
├── app/
│   ├── __init__.py
│   ├── main.py            # FastAPI application
│   ├── strategy.py        # Backtesting strategy logic
│   └── schemas.py         # Pydantic models
├── templates/
│   ├── base.html          # Base template with design system
│   └── dashboard.html     # Main dashboard interface
├── static/
│   └── js/
│       └── main.js        # Frontend logic and Chart.js integration
├── pyproject.toml         # UV package management
└── README.md
```

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- UV package manager

### Installation

1. **Install dependencies using UV**:
   ```bash
   uv pip install -e .
   ```

2. **Prepare data**:
   - Download historical data for SPY (or your preferred symbol)
   - Save as CSV with columns: Date (index), Open, High, Low, Close, Volume
   - Place in `data/SPY.csv`

3. **Run the application**:
   ```bash
   python -m app.main
   ```
   
   Or using uvicorn directly:
   ```bash
   uvicorn app.main:app --reload
   ```

4. **Open your browser**:
   Navigate to `http://localhost:8000`

## 📊 Usage

1. **Configure Parameters**:
   - Symbol: Stock ticker (default: SPY)
   - Date Range: Optional start/end dates
   - Initial Cash: Starting capital
   - Commission: Transaction costs (%)

2. **Run Backtest**:
   - Click "Run Backtest" button
   - View real-time results

3. **Analyze Results**:
   - Equity curve chart
   - Performance metrics
   - Trade statistics

## 🎯 Strategy Details

The default strategy is a **Simple Moving Average (SMA) Crossover**:
- **Buy Signal**: Fast SMA (10-period) crosses above Slow SMA (20-period)
- **Sell Signal**: Fast SMA crosses below Slow SMA
- Fully customizable parameters in `app/strategy.py`

## 🛠️ API Endpoints

- `GET /`: Main dashboard
- `POST /api/backtest`: Run backtest with parameters
- `GET /api/health`: Health check

## 📝 Data Format

CSV files should have the following structure:

```csv
Date,Open,High,Low,Close,Volume
2020-01-02,324.87,325.25,323.34,324.87,93121600
2020-01-03,323.54,325.15,323.40,324.34,87638400
...
```

## 🎨 Design Features

- **Dark Theme**: Modern, eye-friendly dark color scheme
- **Glassmorphism**: Frosted glass effects on cards
- **Gradient Accents**: Vibrant purple-blue gradients
- **Smooth Animations**: Micro-interactions for better UX
- **Responsive Layout**: Works on desktop and mobile

## 🔧 Customization

### Adding New Strategies

Edit `app/strategy.py` to create custom strategies:

```python
class MyStrategy(Strategy):
    def init(self):
        # Initialize indicators
        pass
    
    def next(self):
        # Trading logic
        pass
```

### Styling

Modify CSS variables in `templates/base.html`:

```css
:root {
    --accent-primary: #6366f1;
    --accent-secondary: #8b5cf6;
    /* ... */
}
```

## 📦 Dependencies

- **FastAPI**: Modern web framework
- **Backtesting.py**: Backtesting engine
- **Pandas**: Data manipulation
- **Pydantic**: Data validation
- **Chart.js**: Interactive charts
- **Uvicorn**: ASGI server

## 🤝 Contributing

Feel free to submit issues and enhancement requests!

## 📄 License

MIT License - feel free to use this project for learning and development.

## 🙏 Acknowledgments

- [Backtesting.py](https://kernc.github.io/backtesting.py/) for the excellent backtesting framework
- [FastAPI](https://fastapi.tiangolo.com/) for the amazing web framework
- [Chart.js](https://www.chartjs.org/) for beautiful charts
