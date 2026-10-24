# Wealth Manager

**A private-first personal wealth intelligence operating system.**

A completely new Python/HTML/CSS/JavaScript application designed to help an individual understand assets and liabilities, model financial futures, evaluate NGX and global investments, measure risk, allocate capital and improve decisions through evidence and feedback.

The application includes **15 wealth intelligence modules**, a canonical financial database, an authentication layer, and a responsive financial workspace. This is a research/planning application, **not a brokerage or execution platform**. It does not automatically fetch live stock prices. It includes opt-in external LLM explanations and a time-split ML evaluation workflow, but does not bundle a trained investment prediction model. The maturity of each feature is documented explicitly in [Implementation Status](docs/IMPLEMENTATION_STATUS.md).

## Launch locally (Windows PowerShell)

You need Python 3.12+ and a modern browser.

```powershell
git clone https://github.com/AdetayoK/wealth-manager.git
cd wealth-manager
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
Copy-Item .env.example .env
cd backend
python -m app.security hash-password
```

Copy the resulting password hash, then edit the **repository root** `.env` file:

- `WEALTH_SESSION_SECRET`: at least 32 random characters, not a word or public sample.
- `WEALTH_PASSWORD_HASH`: your newly generated full `pbkdf2_sha256$...` string.
- `WEALTH_USER`: login name, default `owner`.
- `WEALTH_SECURE_COOKIE=false`: keep this only when using localhost HTTP. Set `true` under HTTPS for a remote deployment.

Generate a random secret with:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Then start the application from **inside** `backend`:

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000/login.html** and sign in with the username and original password. Your SQLite database is created at `data/wealth.db` in the repository root, which is gitignored.

### macOS/Linux

```bash
git clone https://github.com/AdetayoK/wealth-manager.git
cd wealth-manager
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
cp .env.example .env
cd backend
python -m app.security hash-password
# Edit ../.env with generated hash + secure random secret
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## First five minutes

1. Open **Data workspace** and create an NGN broker/cash account.
2. Record an account funding **DEPOSIT** in that account's own currency.
3. Register a security with its ticker, exchange and pricing currency. Use separate asset classes for `NGX_STOCK`, `US_STOCK`, `ETF`, `MUTUAL_FUND`, `BOND`.
4. Record a buy (cash is deducted automatically), then record a price with an accurate source and date.
5. If the security is denominated outside NGN, record a dated currency-to-NGN rate (for example USD→NGN) before expecting an NGN portfolio value.
6. Return to **Overview** to see holdings, allocation, liquidity warnings and data-quality alerts; then establish your first goal.

**Never record a stock buy as both a trade and a manual cash withdrawal.** A trade *already* affects its brokerage account's cash balance.

### Import historical prices

Select Data workspace → Price history CSV. Upload UTF-8 CSV with headers:

```csv
symbol,exchange,date,close,source
DEMO,XNSA,2026-01-02,100.5,broker-statement
DEMO,XNSA,2026-01-05,102.25,broker-statement
```

These are illustrative prices for a fictional ticker. Instruments must be registered first with exactly matching symbols and exchanges. No official historical prices are bundled. Uploaded rows are validated and upserted by instrument + date. Import is capped at 2 MB / 5000 rows.

## All fifteen modules

| # | Module | Initial functionality |
|---|---|---|
| 1 | Global Portfolio Command Center | Net worth, holdings, multicurrency assets/liabilities, data completeness |
| 2 | Wealth Trajectory Simulator | Retirement and goal funding under inflation/return assumptions |
| 3 | Hidden Risk & Exposure Engine | Concentration, country/sector exposure, sample-gated historical risk |
| 4 | Capital Allocation Optimizer | User-assumed candidate mixes, goal probabilities and downside percentiles |
| 5 | Cross-Market Equity Research | Fundamentals, discounted cash flow, ETF/fund constituent look-through |
| 6 | Quantitative Signals Lab | Sample-gated historical price momentum and volatility |
| 7 | Financial Event Intelligence | Source-linked manual events associated with portfolio positions |
| 8 | Liquidity and Cash-Flow Forecasting | Future cash movements, emergency reserves and deployable capital |
| 9 | Tax, Fees and Net-Return Engine | Explicit tax basis, fees and estimated net liquidation proceeds |
| 10 | Probabilistic Forecasting Engine | Seeded Monte Carlo simulations and goal-probability scenarios |
| 11 | Investment Decision Journal | Thesis, invalidation conditions, outcome review and mistake tracking |
| 12 | Portfolio Rebalancing | Contribution-only allocation and target drift |
| 13 | Personal Financial Digital Twin | One-step portfolio shock + lost income + emergency expense |
| 14 | AI Wealth Analyst | Local deterministic evidence briefing; optional, per-question-consented OpenAI response |
| 15 | Strategy Backtesting & Model Governance | Chronological holdout benchmark comparison, drawdowns and embargoed binary ML evaluation |

**Important:** A calculator working with user-entered assumptions is not evidence of future returns. The AI Analyst provides deterministic evidence summaries by default and can optionally call an externally configured LLM **only after explicit per-question consent**. A separate model evaluation endpoint trains a binary classifier on user-supplied, date-ordered data with a chronological gap and checks it against a no-skill baseline; it does not deploy a trading model. Neither capability places trades. Data integration, advanced scenario engines and validation are tracked separately in the design documents.

## Project structure

```text
backend/
  app/
    config.py        environment and authentication safety checks
    security.py      PBKDF2-SHA256 password creation / verification
    database.py      SQLAlchemy engine, sessions, SQLite PRAGMAs
    models.py        canonical financial records
    finance.py       ledger invariants, cost basis and multicurrency valuation
    analytics.py     pure numerical engines, no database
    intelligence.py  15-module domain orchestration
    api.py           typed authenticated REST interfaces
    main.py          FastAPI and secure session middleware
  tests/             calculations and authenticated integration tests
frontend/
  index.html         authenticated wealth workspace
  login.html         single-owner login
  style.css          responsive visual design system
  app.js             safe rendering, navigation and API client
  modules.js         interfaces for the fifteen analytical modules
  data.js            ledger management and CSV ingestion
  login.js
docs/
  ARCHITECTURE.md
  IMPLEMENTATION_STATUS.md
  API.md
.github/workflows/ci.yml
```

## Test

```powershell
cd backend
python -m pytest -q
```

GitHub Actions runs pytest, Python bytecode compilation and `node --check` on the frontend JavaScript.

## Optional AI and ML

To enable external explanations, add a supported model ID to `WEALTH_LLM_MODEL` and a server-side `OPENAI_API_KEY` in your local `.env`. The AI workspace requires an explicit opt-in each time. It transmits only the question, aggregate financial metrics and review triggers, not raw brokerage transactions. Without credentials or consent, local deterministic briefings remain available. **Only use this if you accept that the disclosed aggregates will be processed externally.**

The Strategy Validation workspace also accepts a chronologically dated numeric feature matrix and binary future-outcome labels. The `/api/ml/evaluate` endpoint trains a standardized logistic regression on earlier rows, purges an embargo horizon, compares against a constant-probability baseline and reports Brier score, accuracy and ROC AUC on later rows. It requires at least 100 observations; users must verify labels and point-in-time feature availability before interpreting the results.

## Security and data limitations

- **Keep this repository private** before recording any personal financial data. Do not commit `.env`, account statements, API keys, real holdings or the SQLite DB.
- The default app binds localhost only. This is **not** a public internet production hardening plan.
- Do not expose the local development server publicly. Remote deployment requires HTTPS, secure cookies, backups, access controls, rate limiting, and a security audit.
- Only explicit documented financial records are valued. Missing prices and FX are flagged, not invented.
- Recorded date/currency/source are critical. Importing unadjusted split prices or survivorship-biased histories will corrupt backtests.
- The initial baseline models do not include calibrated macroeconomic regime changes, actual FX purchase-lot gains, real tax jurisdiction checks, or live execution/liquidity dynamics.

## Next steps

See [Architecture](docs/ARCHITECTURE.md), [Module Status](docs/IMPLEMENTATION_STATUS.md), and [API Contracts](docs/API.md). The priority after verifying this foundation is point-in-time data ingestion and financial statement reconciliation, followed by research-grade portfolio analytics, verified investment model pipelines and optional privacy-gated LLM research.
