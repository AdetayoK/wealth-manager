# Fifteen-module implementation register

The repository contains an executable baseline for all fifteen modules. **A live interface is not a guarantee of institutional-grade model validation**. No result is represented as a verified real-time quote or a trained forecast. The maturity indicator `live` refers to a working computation on provided data, not automatically available market data.

| # | Capability | Functionality in this build | Honest maturity and next work |
|---|---|---|---|
| 1 | Global Portfolio Command Center | Ledger-backed NGN/USD worth, currency and asset exposures, valuations and data issues | Working baseline; needs full performance attribution |
| 2 | Wealth Trajectory Simulator | Inflation-aware goals, required monthly contribution, funding gap | Working deterministic baseline; multi-goal capital segregation missing |
| 3 | Hidden Risk & Exposure | Class/country/sector concentration, aligned historical variance/drawdown/VaR | Working when histories exist; FX-aware factor risk missing |
| 4 | Capital Allocation Optimizer | Candidate allocations, constraints, simulated goal likelihood and downside | Working assumption-driven simulator; calibrated correlations/costs missing |
| 5 | Cross-Market Equity Research | Instrument master, source-linked fundamentals, DCF, manual ETF constituent look-through | Working baseline; market-wide automatic filings and financial ratios pending |
| 6 | Quantitative Signals Lab | Sample-gated historical momentum and realized vol by recorded instrument | Working descriptive signals; no validated alpha or trading claims |
| 7 | Financial Event Intelligence | Structured source-identified market events connected to held exposure | Manual intake only; automatic event detection pending |
| 8 | Liquidity & Cash-Flow | Dated income/expense plans, cash trajectory, conservative outflow-first low, reserve | Working schedule simulator; obligations must be entered |
| 9 | Tax, Fees & Net-Return | Explicit tax basis and fee scenarios, stored per-class rules | Working calculator; current law is not embedded or certified |
| 10 | Probabilistic Forecasting | Seeded Monte Carlo percentiles, goal probability, real median | Working under assumptions; no calibrated empirical distribution |
| 11 | Decision Journal | Decision thesis, invalidation, benchmark and reviewed outcome; behavioural tags | Working journal; small sample may not support statistical inference |
| 12 | Rebalancing | Target drift and no-sell allocation of new capital | Working; transaction costs and practical order sizing missing |
| 13 | Financial Digital Twin | Combined one-step asset loss, emergency expense and income disruption | Working stress baseline; no correlated temporal simulation |
| 14 | AI Wealth Analyst | Deterministic evidence card, opt-in externally generated explanation via Responses API | Working local baseline; external provider requires explicit consent/credentials and generated prose is non-authoritative |
| 15 | Strategy Backtesting | Net-of-assumed-fees total return, holdout benchmark comparison, drawdown, chronological binary ML model evaluation | Working on supplied data; no full execution simulation or calibrated trading model |

## Optional machine learning and AI

A `/api/ml/evaluate` endpoint requires at least 100 dated feature/outcome rows, purges a user-declared future-label horizon from the development window, fits logistic regression on the earlier observations, and compares it with a fixed-probability baseline on a later holdout. Point-in-time feature timestamps, selection bias and trade feasibility remain user-supplied responsibilities.

The analyst remains fully local unless an operator configures a server-side API key and model, and explicitly consents for that one question. Only aggregate metrics, review triggers and the submitted question leave the application. No account credentials or raw trades are transmitted by the built-in adapter.

## Data sources in the initial release

**None are linked to external financial feeds.** Real holdings, prices, FX, fund constituent weights, cash flows and fundamentals require explicit manual entry or validated CSV import. Absence of data blocks or qualifies analysis.

## Production acceptance gates

1. Authoritative cash and holdings reconciliation against brokerage statements, including splits, rights issues, dividends and revised entries.
2. Provenanced historical market feed and end-of-day data license; price staleness SLAs by market and trading calendar.
3. Multi-currency cost lots, exact original transaction FX, cash FX attribution, total-return indices and TWR/XIRR.
4. Investment policy limits, liquidity settlement windows and jurisdiction-specific tax/estate risk reviewed by professionals.
5. Walk-forward/out-of-sample model verification with turnover, executable price assumptions and baseline benchmarks.
6. Independent review of financial assumptions and macro regimes; adversarial stress scenarios and model monitoring.
7. Auth hardening, data backup and restore, encryption-at-rest policy and cybersecurity review.
8. Financial recommendation safeguards and human authorization before any future transfer or order integration.

## Implementation notes

The repository is an independent fresh build. The API, models, analytics and frontend have no dependency on any other code repository.
