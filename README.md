# BUD - Budget Dashboard

A Streamlit-based financial tracking application that connects to YNAB (You Need A Budget) to provide spending insights, anomaly detection, and budget monitoring.

## Features

- **Dashboard**: Overview of spending, budget status, and recent transactions
- **Spending Analysis**: Deep dive into spending patterns by category, time period, and payee
- **Smart Alerts**:
  - Unusual spending detection using Modified Z-Score algorithm
  - Budget overspending alerts
  - Recurring transaction monitoring (amount changes, missing transactions)
- **Recurring Transactions**: View and track scheduled transactions

## Quick Start

### 1. Install dependencies

```bash
uv sync
```

### 2. Configure YNAB API Token

Create `.streamlit/secrets.toml`:

```toml
YNAB_ACCESS_TOKEN = "your-personal-access-token"
```

Get your token from: **YNAB Settings > Developer Settings > Personal Access Tokens**

### 3. Run the app

```bash
uv run streamlit run app.py
```

## Configuration

### Alert Thresholds

Add to `.streamlit/secrets.toml`:

```toml
[alert_thresholds]
unusual_spending_warning = 2.5    # Modified Z-Score threshold for warning
unusual_spending_critical = 3.5   # Modified Z-Score threshold for critical
budget_approaching = 0.90         # Budget percentage to trigger warning (90%)
recurring_days_warning = 3        # Days past due before warning
recurring_days_critical = 7       # Days past due before critical
```

## Data Privacy

- All data is cached locally in SQLite (`~/.bud/cache.db`)
- No data is sent to third parties
- API communication is directly with YNAB over HTTPS

## Rate Limits

YNAB API allows 200 requests per hour. BUD uses delta sync (`last_knowledge_of_server`) to minimize API calls.

## Project Structure

```
bud/
├── app.py                    # Main Streamlit application
├── pages/                    # Streamlit pages
│   ├── 1_Dashboard.py
│   ├── 2_Spending_Analysis.py
│   ├── 3_Alerts.py
│   ├── 4_Recurring.py
│   └── 5_Settings.py
├── src/
│   ├── api/                  # YNAB API client
│   ├── cache/                # SQLite database & sync
│   ├── alerts/               # Alert detection algorithms
│   └── utils/                # Utilities
└── .streamlit/               # Streamlit configuration
```

## License

MIT
