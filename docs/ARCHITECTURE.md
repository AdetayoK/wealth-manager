# Wealth Manager: system design

## Product

**Wealth Manager** is a single-owner, local-first wealth operating system focused on the quality of investment and financial planning decisions, not order execution.

Built completely from scratch: FastAPI/SQLAlchemy + SQLite + responsive HTML/CSS/vanilla JavaScript. Independent repository and implementation.

## Source-of-truth

- `accounts`: brokerage and cash accounts; each account is denominated in one currency.
- `instruments`: canonical securities (NGX equities, US equities, ETFs, funds, bonds, other securities), issuer metadata, ISO-like currency, exchange, domicile and optional ISIN.
- `cash_entries`: signed cash ledger. Transfers create one debit and one credit, linked by a transfer group.
- `trades`: position changes and **implicit account cash flows**: BUY = -(qty * unit price + fee), SELL = +(qty * unit price - fee).
- `prices`: price per instrument and date, with provenance and no future-dated quotes.
- `fx_rates`: dated explicit exchange rates, including direct and reciprocal NGN conversion.
- `balance_items`: nonmarket assets and liabilities, dated and denominated explicitly.
- `goals` and `cash_plans`: goal assumptions and forward cash obligations.
- `fundamentals`, `fund_constituents`, `market_events`: reproducible research inputs, with source attribution.
- `decisions`: investment theses, invalidation rules and post-decision reviews.
- `tax_rules`: explicit, user-verified tax/fee assumptions.

All persisted money uses SQLAlchemy Numeric/Decimal. JSON financial output is rounded to 2 decimals and converted to float at the API boundary; source amounts preserve precision.

### Valuation invariants

1. Every buy decreases the designated same-currency account balance; holdings are valued separately at their latest known dated quote. No double-counting capital invested.
2. Transfers create equal signed cash legs; total portfolio value is unchanged.
3. A sell cannot exceed quantity owned at the recorded date, including chronological checks for backdated inserts.
4. FX uses actual stored dated base/quote rates. Missing FX or missing security prices **exclude the affected asset from aggregated NGN values and flag a data issue**.
5. Source date and valuation issues are visible. A stale market price does not silently become a new quote.
6. Cash withdrawals must not overdraw the selected dated account. The initial version does not enforce full future-event cash balance replay for all backdated modifications.
7. Financial goals and expected returns are explicitly user-provided; the system does not infer future alpha from short historical samples.

## Request flow

`Browser UI → secured /api routes → domain services → pure analytics / SQLAlchemy → SQLite`.

`app/finance.py`: accounting and valuation. `app/analytics.py`: pure research and numerical methods. `app/intelligence.py`: data-backed orchestration across all 15 features. `app/api.py`: typed contracts and authorization. `app/main.py`: initialization, session middleware and static assets. No external market API keys are required for core functionality.

## Security baseline

- Single owner, PBKDF2-SHA256 hashed password, a signed HttpOnly session cookie with 8-hour maximum age, `SameSite=Lax`.
- Require `X-CSRF-Token` for state-changing authenticated requests.
- Explicit `WEALTH_SESSION_SECRET` and `WEALTH_PASSWORD_HASH` required; startup fails if absent.
- Secure-cookie flag configurable; **must be enabled behind HTTPS** for remote deployment.
- No public sign-up; no broker account linkage; no credential scraping.
- Security headers include a strict same-origin CSP, `nosniff`, frame denial, and restricted referrer policy.
- **This is not hardened for public hosting.** Before any remote deployment, implement TLS, encrypted backup, secrets management, account-level authorization, audit logging, rate-limited authentication, migration governance, a CSRF review, and penetration tests. SQLite on a personal device is appropriate only under suitable device-level security.
- CSV ingestion limits size, validates all rows before writes, and upserts by `(instrument, date)`.

## Analytics integrity and uncertainty

- Deterministic accounting and tax-rule computations are not delegated to a generative model.
- Monte Carlo uses explicitly supplied normal monthly return assumptions; independent-asset allocation simulations are simplified and should not be used as empirical risk forecasts.
- Historical portfolio risk is calculated only when at least 26 aligned recorded returns are available; this uses local-currency price returns, not fully hedged global returns.
- DCF exposes discount, growth, terminal and net-debt assumptions. Terminal value share is visible.
- Technical momentum is descriptive, **not** a validated buy/sell signal.
- Backtest accepts chronologically aligned supplied returns; it calculates an out-of-sample holdout but cannot detect data leakage upstream.
- AI Analyst v0 is **a deterministic evidence briefing** linked to authoritative computation endpoints. No LLM is called and no financial data is sent to a third party.

## Future target architecture

When accuracy and historical volume demand it: SQLite → PostgreSQL, Alembic schema migrations, append-only audited event ledger, encrypted object storage for filings, licensed vendor ingestion workers, factor/constituent graph, versioned point-in-time feature store, optimization service, strategy governance/evaluations, user-approved trade integration only with compliant providers.

A realistic external API plan includes: NGX-authorized market data, SEC Nigeria NAV disclosures, issuer annual/interim reports, US exchange-authorized data and corporate actions, reputable macro/FX/CPI data, and provider-backed FX transaction costs. Licenses and contracts must be verified before implementation.

## Local development

See `README.md` for clean setup, sample CSV and test commands. CI runs backend integration tests and JavaScript syntax validation.
