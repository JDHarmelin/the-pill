# 💊 THE PILL

**Shkreli Method Stock Analysis**

A local web application that runs rigorous fundamental analysis on any publicly traded company using the "Shkreli Method" - a ground-up financial modeling approach that prioritizes raw SEC data and cash flow over GAAP earnings.

![The Pill Screenshot](https://via.placeholder.com/800x400/000000/FFFFFF?text=THE+PILL)

---

## ✨ Features

- **Clean, Minimal UI** - Black screen with a simple search bar. Type any ticker.
- **Real SEC Data** - Pulls directly from SEC EDGAR for 10-K/10-Q filings
- **Live Stock Prices** - Real-time quotes via Yahoo Finance
- **AI-Powered Analysis** - Uses Claude to run the full 5-phase Shkreli Method
- **No BS** - Focus on cash flow truth, not GAAP earnings

## 📊 The Shkreli Method

The analysis follows 5 phases:

1. **The Six Important Things** - Stock price, shares outstanding, market cap, cash, debt, enterprise value
2. **Income Statement Analysis** - Longitudinal quarterly data, margins, operating income
3. **Cash Flow Truth** - Reconcile GAAP to actual cash flow (D&A, SBC, deferred taxes)
4. **Balance Sheet Liquidity** - Assets by liquidity, goodwill check, fundamental equation
5. **Qualitative Checks** - Organic vs inorganic growth, segment analysis, valuation

---

## 🚀 Quick Start

### Prerequisites

- Python 3.9 or higher
- An Anthropic API key ([get one here](https://console.anthropic.com/))

### Installation

1. **Clone or download this repository**

```bash
cd the-pill
```

2. **Create a virtual environment (recommended)**

```bash
python -m venv venv

# On macOS/Linux:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

3. **Install dependencies**

```bash
pip install -r requirements.txt
```

4. **Set up your API key**

```bash
# Copy the example env file
cp .env.example .env

# Edit .env and add your Anthropic API key
# ANTHROPIC_API_KEY=sk-ant-...
```

5. **Run the app**

```bash
python app.py
```

6. **Open your browser**

Navigate to: **http://localhost:5000**

---

## 🔧 Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `ANTHROPIC_API_KEY` | Your Anthropic API key | Yes |

### Changing the Port

By default, the app runs on port 5000. To change it:

```python
# In app.py, change the last line:
app.run(debug=True, port=8080)  # or any port you prefer
```

---

## 📁 Project Structure

```
the-pill/
├── app.py              # Main Flask application
├── requirements.txt    # Python dependencies
├── .env.example        # Environment template
├── .env               # Your API key (create this)
├── templates/
│   └── index.html     # Frontend UI
└── tools/
    ├── __init__.py
    ├── sec_fetcher.py # SEC EDGAR data fetching
    └── stock_data.py  # Yahoo Finance data fetching
```

---

## 🛠️ How It Works

1. **You enter a ticker** (e.g., "AAPL")
2. **The backend calls Claude** with the Shkreli Method system prompt
3. **Claude uses tools** to fetch:
   - Current stock quote (Yahoo Finance)
   - Company info
   - Financial statements (income, balance, cash flow)
   - SEC filing data (shares outstanding, etc.)
   - Key metrics and ratios
4. **Claude analyzes the data** following the 5-phase methodology
5. **Results are rendered** in clean Markdown format

---

## 🔍 Example Analysis

When you analyze a company like NVDA, you'll get:

- **Capital Structure**: Price, shares outstanding, market cap, EV
- **Income Statement**: Revenue trends, margins, operating income
- **Cash Flow Truth**: GAAP vs. proxy cash flow reconciliation
- **Balance Sheet**: Assets, liabilities, equity check
- **Verdict**: Is it investable? What are the red flags?

---

## ⚠️ Disclaimers

- **Not Financial Advice** - This is for educational purposes only
- **Data Sources** - Uses public data from Yahoo Finance and SEC EDGAR
- **API Costs** - Running analyses uses your Anthropic API credits
- **Rate Limits** - SEC EDGAR has rate limits; don't spam requests

---

## 🤝 Contributing

Feel free to submit issues and pull requests. Some ideas:

- Add more data sources (Bloomberg, FactSet integration)
- Export analysis to PDF
- Save/compare multiple analyses
- Add technical analysis charts
- Historical analysis comparisons

---

## 📄 License

MIT License - Use it however you want, just don't blame me if you lose money.

---

## 🙏 Credits

- Methodology inspired by Martin Shkreli's financial analysis approach
- Built with [Flask](https://flask.palletsprojects.com/), [Anthropic Claude](https://anthropic.com/), [yfinance](https://github.com/ranaroussi/yfinance)
- SEC data from [EDGAR](https://www.sec.gov/edgar)

---

**Made with 💊 for better investment decisions**
