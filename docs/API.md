# Core API map

All business endpoints require the signed owner session and state-changing requests require `X-CSRF-Token`. Login returns a CSRF token and sets a signed cookie. `/api/health` and `/api/auth/login` are public.

| Concern | Endpoints |
|---|---|
| Account and holdings | `GET/POST /api/accounts`, `GET/POST /api/instruments`, `GET /api/portfolio`, `GET /api/holdings` |
| Ledger | `POST /api/cash`, `POST /api/transfers`, `GET/POST /api/trades` |
| Prices and FX | `POST /api/prices`, `POST /api/fx`, `POST /api/import/prices` |
| Balance sheet | `POST /api/balance-items`, `GET /api/quality`, `GET /api/health-score` |
| Planning | `GET/POST /api/goals`, `POST /api/cash-plans`, `GET /api/liquidity` |
| Analytics | `GET /api/risk`, `POST /api/allocation/compare`, `POST /api/rebalance` |
| Research | `GET/POST /api/fundamentals`, `GET /api/lookthrough`, `POST /api/constituents`, `POST /api/research/dcf`, `GET /api/signals` |
| Events | `GET/POST /api/events` |
| Tax | `GET/POST /api/tax-rules`, `POST /api/net-return` |
| Simulation | `POST /api/forecast`, `POST /api/twin/stress`, `POST /api/opportunity` |
| Journal | `GET/POST /api/decisions`, `POST /api/decisions/{id}/review` |
| Decision & research | `GET /api/analyst/brief`, `POST /api/backtest` |
| Discovery | `GET /api/modules` |

`POST /api/import/prices`: multipart upload field `upload`, UTF-8 CSV with the headers `symbol,exchange,date,close,source`. The `source` field is optional. Maximum 2 MB, 5000 price rows. `symbol+exchange` must already exist, dates ISO-8601 and not in the future, closes positive. Every row is validated before any write.

Each output with modeled estimates states its assumptions, known gaps and applicable warnings. No endpoint will execute a broker trade automatically.
