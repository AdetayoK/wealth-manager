"""Domain composition across the fifteen independent wealth capabilities."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timedelta
from decimal import Decimal
from calendar import monthrange

from sqlalchemy import select
from sqlalchemy.orm import Session

from .analytics import goal_projection, momentum_signal, risk_from_aligned_returns
from .finance import account_balance, balance_sheet, dec, fx_to_ngn, holdings, last_price, money
from .models import (
    Account, CashPlan, Decision, FundConstituent, Fundamental, FXRate, Goal, Instrument,
    MarketEvent, Price, TaxRule,
)

MODULES = [
    ("command", "Global Portfolio Command Center", "Portfolio", "live",
     "Unified holdings, liabilities, valuation freshness, geographic and FX exposure"),
    ("trajectory", "Wealth Trajectory Simulator", "Planning", "live",
     "Goal funding, inflation-aware projections and required contributions"),
    ("risk", "Hidden Risk & Exposure Engine", "Portfolio", "live",
     "Concentration and historical risk with explicit data coverage"),
    ("allocation", "Capital Allocation Optimizer", "Decision", "live",
     "Goal-sensitive comparison of user-defined multi-asset allocations"),
    ("research", "Cross-Market Equity Research", "Research", "live",
     "Standardized fundamentals, DCF calculations and fund look-through"),
    ("signals", "Quantitative Signals Lab", "Research", "live",
     "Momentum and realized volatility signals gated by available history"),
    ("events", "Financial Event Intelligence", "Research", "baseline",
     "Source-linked events and exposure impact; automated ingestion not enabled"),
    ("liquidity", "Liquidity and Cash-Flow Forecasting", "Planning", "live",
     "Cash runway, planned expenses and emergency reserves"),
    ("net-returns", "Tax, Fees and Net-Return Engine", "Decision", "live",
     "Net liquidation calculations with explicitly defined tax rules"),
    ("forecast", "Probabilistic Forecasting Engine", "Planning", "live",
     "Monte Carlo goal probability under transparent assumptions"),
    ("journal", "Investment Decision Journal", "Learning", "live",
     "Dated theses, invalidation conditions and process-vs-outcome reviews"),
    ("rebalance", "Rebalancing and Contribution Planner", "Decision", "live",
     "Target drift and no-sale contribution recommendations"),
    ("twin", "Personal Financial Digital Twin", "Planning", "baseline",
     "Joint one-step asset and household income shock simulations"),
    ("analyst", "AI Wealth Analyst", "Intelligence", "baseline",
     "Deterministic, evidence-linked briefings; optional external LLM adapter"),
    ("backtest", "Strategy Backtesting and Model Governance", "Learning", "live",
     "Holdout comparisons, fees, drawdowns and model validation limitations"),
]


def _add_months(d: date, months: int) -> date:
    m = d.month - 1 + months
    year, month = d.year + m // 12, m % 12 + 1
    return date(year, month, min(d.day, monthrange(year, month)[1]))


def cashflow(db: Session, horizon_months: int = 12, reserve_months: int = 6) -> dict:
    if not 1 <= horizon_months <= 60 or not 0 <= reserve_months <= 24:
        raise ValueError("Horizon must be 1–60 months and reserve 0–24 months")
    today = date.today()
    starting = Decimal("0")
    incomplete = []
    for a in db.scalars(select(Account)).all():
        rate, _ = fx_to_ngn(db, a.currency, today)
        if rate is None:
            incomplete.append(a.currency)
            continue
        starting += account_balance(db, a, today) * rate
    plans = db.scalars(select(CashPlan)).all()
    def monthly_expense():
        factor = {"MONTHLY": 1, "QUARTERLY": 1/3, "YEARLY": 1/12}
        return sum(float(p.amount_ngn) * factor.get(p.frequency, 0)
                   for p in plans if p.direction == "OUT")
    reserve = reserve_months * monthly_expense()
    balance = float(starting)
    worst = balance
    months = []
    for i in range(horizon_months):
        start, end = _add_months(today, i), _add_months(today, i + 1)
        events = []
        for p in plans:
            if p.end_date and p.end_date < start:
                continue
            if p.frequency == "ONCE":
                dates = [p.start_date]
            else:
                step = {"MONTHLY": 1, "QUARTERLY": 3, "YEARLY": 12}[p.frequency]
                dates = []
                n = 0
                while (when := _add_months(p.start_date, n * step)) <= end:
                    dates.append(when)
                    n += 1
                    if n > 1000:
                        break
            for d in dates:
                if start < d <= end and (not p.end_date or d <= p.end_date):
                    signed = float(p.amount_ngn) * (1 if p.direction == "IN" else -1)
                    events.append({"date": str(d), "name": p.name, "amount_ngn": signed})
        out = -sum(e["amount_ngn"] for e in events if e["amount_ngn"] < 0)
        inflow = sum(e["amount_ngn"] for e in events if e["amount_ngn"] > 0)
        worst = min(worst, balance - out)
        balance = balance + inflow - out
        worst = min(worst, balance)
        months.append({"month": str(end)[:7], "opening_ngn": round(balance - inflow + out, 2),
                       "closing_ngn": round(balance, 2), "events": events})
    return {
        "starting_cash_ngn": money(starting), "emergency_reserve_ngn": round(reserve, 2),
        "lowest_balance_ngn": round(worst, 2), "deployable_ngn": round(max(0, worst - reserve), 2),
        "months": months, "missing_fx_currencies": sorted(set(incomplete)),
        "notes": ["Only entered recurring schedules are forecast.",
                  "Future dividends, fund payouts and asset sale proceeds are intentionally excluded.",
                  "Cash cannot be assumed deployable if prices, obligations or FX are incomplete."],
    }


def goals_overview(db: Session) -> list[dict]:
    worth = balance_sheet(db)
    amount = max(0, worth["net_worth_ngn"])
    today = date.today()
    rows = []
    for g in db.scalars(select(Goal).order_by(Goal.due_date)).all():
        years = (g.due_date - today).days / 365.25
        if years <= 0:
            rows.append({"id": g.id, "name": g.name, "status": "DUE",
                         "target_today_ngn": float(g.target_today_ngn)})
            continue
        projection = goal_projection(
            amount, float(g.target_today_ngn), years, float(g.monthly_contribution_ngn),
            float(g.expected_return_pct), float(g.inflation_pct),
        )
        rows.append({
            "id": g.id, "name": g.name, "due_date": str(g.due_date),
            "years": round(years, 2), "priority": g.priority, **projection,
        })
    return rows


def risk_report(db: Session) -> dict:
    sheet = balance_sheet(db)
    total = sheet["assets_ngn"]
    by_class = sheet["allocation_ngn"]
    shares = {k: round(v / total * 100, 2) for k, v in by_class.items()} if total > 0 else {}
    concentration = sum((v / total) ** 2 for v in by_class.values()) if total > 0 else None
    h = holdings(db)["positions"]
    country: dict[str, float] = defaultdict(float)
    sector: dict[str, float] = defaultdict(float)
    for p in h:
        if p["value_ngn"] is not None:
            country[p["country"] or "UNKNOWN"] += p["value_ngn"]
            sector[p["sector"] or "UNCLASSIFIED"] += p["value_ngn"]

    # Align recorded closes on dates present for every held security; never
    # silently fill missing prices as unchanged. Local currency risk only.
    selected = [p for p in h if p["value_ngn"] and p["value_ngn"] > 0]
    ids = [p["instrument_id"] for p in selected]
    rows = db.scalars(select(Price).where(Price.instrument_id.in_(ids))
                      .order_by(Price.as_of)).all() if ids else []
    series: dict[int, dict[date, float]] = defaultdict(dict)
    for row in rows:
        series[row.instrument_id][row.as_of] = float(row.close)
    aligned = []
    hist = None
    if len(ids) > 0:
        shared = set(series[ids[0]])
        for iid in ids[1:]:
            shared &= set(series[iid])
        days = sorted(shared)
        if len(days) >= 27:
            matrix = []
            for day_before, day_after in zip(days[:-1], days[1:]):
                matrix.append([series[iid][day_after] / series[iid][day_before] - 1 for iid in ids])
            try:
                hist = risk_from_aligned_returns(
                    matrix, [p["value_ngn"] / sum(x["value_ngn"] for x in selected) for p in selected],
                )
            except ValueError:
                hist = None
    return {
        "allocation_pct": shares,
        "class_concentration_hhi": round(concentration, 4) if concentration is not None else None,
        "country_exposure_ngn": dict(country),
        "sector_exposure_ngn": dict(sector),
        "historical_model": hist,
        "modelled_positions": len(ids) if hist else 0,
        "excluded_positions": len(h) - (len(ids) if hist else 0),
        "issues": sheet["data_issues"],
        "notes": ["Class concentration uses all valued assets and does not reveal fund holdings until look-through data is entered.",
                  "Historical risk uses aligned recorded price closes in local currencies; NGN FX shocks and taxes are not in the covariance calculation.",
                  "Absent prices, thin trading, stale quotes and short data windows can severely understate risk."],
    }


def signals_report(db: Session, lookback: int = 20) -> dict:
    instruments = db.scalars(select(Instrument).order_by(Instrument.symbol)).all()
    out = []
    for ins in instruments:
        rows = db.scalars(select(Price).where(Price.instrument_id == ins.id)
                          .order_by(Price.as_of.desc()).limit(lookback + 1)).all()
        values = list(reversed([float(r.close) for r in rows]))
        out.append({"symbol": ins.symbol, "name": ins.name, "market": ins.exchange,
                    **momentum_signal(values, lookback)})
    return {"items": out, "disclosure": "Only observed closes; not model-validated buy/sell signals."}


def event_report(db: Session) -> dict:
    position_map = {p["instrument_id"]: p for p in holdings(db)["positions"]}
    out = []
    for e in db.scalars(select(MarketEvent).order_by(MarketEvent.occurred_on.desc()).limit(200)).all():
        p = position_map.get(e.instrument_id)
        ins = db.get(Instrument, e.instrument_id)
        out.append({
            "id": e.id, "date": str(e.occurred_on),
            "symbol": ins.symbol if ins else "UNKNOWN", "headline": e.headline,
            "type": e.event_type, "change": e.observed_change,
            "thesis_impact": e.thesis_impact, "source_url": e.source_url,
            "confidence": e.confidence,
            "held_value_ngn": p["value_ngn"] if p else None,
        })
    return {"events": out,
            "note": "Human-entered, source-linked events. Automatic detection, extraction and verification require a separate trusted ingestion integration."}


def journal_report(db: Session) -> dict:
    items = db.scalars(select(Decision).order_by(Decision.decided_on.desc())).all()
    reviewed = [d for d in items if d.reviewed_on is not None]
    mistakes = Counter(tag.strip() for d in reviewed
                       for tag in d.mistake_tags.split(",") if tag.strip())
    outcomes = {"good_process_good_outcome": 0, "good_process_bad_outcome": 0,
                "poor_process_good_outcome": 0, "poor_process_bad_outcome": 0}
    for d in reviewed:
        if d.process_rating not in {"GOOD", "POOR"} or d.actual_return_pct is None:
            continue
        baseline = d.benchmark_return_pct if d.benchmark_return_pct is not None else d.expected_return_pct
        good_outcome = d.actual_return_pct >= (baseline if baseline is not None else 0)
        outcomes[f"{d.process_rating.lower()}_process_{'good' if good_outcome else 'bad'}_outcome"] += 1
    return {
        "total": len(items), "reviewed": len(reviewed), "mistakes": dict(mistakes),
        "quadrants": outcomes, "patterns_reliable": sum(outcomes.values()) >= 10,
        "entries": [{"id": d.id, "date": str(d.decided_on), "action": d.action,
                     "thesis": d.thesis, "invalidation": d.invalidation,
                     "process_rating": d.process_rating,
                     "actual_return_pct": float(d.actual_return_pct) if d.actual_return_pct is not None else None}
                    for d in items[:40]],
        "note": "Process and outcome are separate. Small-sample patterns are descriptive, not proof of skill.",
    }


def fund_overlap(db: Session) -> dict:
    constituents = db.scalars(select(FundConstituent)).all()
    groups = defaultdict(list)
    all_inst = {r.id: r for r in db.scalars(select(Instrument)).all()}
    for c in constituents:
        groups[c.fund_id].append(c)
    # Weight snapshots per fund cannot be added across reporting dates.
    results = []
    for fid, all_rows in groups.items():
        latest = max(c.as_of for c in all_rows)
        rows = [c for c in all_rows if c.as_of == latest]
        total = sum(float(c.weight_pct) for c in rows)
        results.append({
            "fund": all_inst[fid].symbol if fid in all_inst else str(fid),
            "as_of": str(latest), "coverage_pct": round(total, 2),
            "constituents": [{
                "symbol": all_inst[c.constituent_id].symbol if c.constituent_id in all_inst else str(c.constituent_id),
                "weight_pct": float(c.weight_pct)}
                for c in rows
            ],
            "complete": abs(total - 100) <= 0.5,
        })
    return {"funds": results, "note": "Manual fund constituents; unreported or stale holdings are excluded from look-through concentration."}


def fundamentals_report(db: Session) -> list[dict]:
    entries = db.scalars(select(Fundamental).order_by(
        Fundamental.instrument_id, Fundamental.fiscal_year.desc())).all()
    instruments = {i.id: i for i in db.scalars(select(Instrument)).all()}
    result = []
    for f in entries:
        ins = instruments.get(f.instrument_id)
        result.append({
            "symbol": ins.symbol if ins else str(f.instrument_id),
            "year": f.fiscal_year, "currency": ins.currency if ins else None,
            "revenue": float(f.revenue) if f.revenue is not None else None,
            "net_income": float(f.net_income) if f.net_income is not None else None,
            "free_cash_flow": float(f.free_cash_flow) if f.free_cash_flow is not None else None,
            "net_debt": (float(f.total_debt or 0) - float(f.cash or 0)),
            "shares_outstanding": float(f.shares_outstanding) if f.shares_outstanding else None,
            "source_url": f.source_url,
        })
    return result


def tax_rules(db: Session) -> list[dict]:
    return [{"class": r.asset_class, "sale_tax_pct": float(r.sale_tax_pct),
             "sale_tax_basis": r.sale_tax_basis, "exit_fee_pct": float(r.exit_fee_pct),
             "effective_on": str(r.effective_on), "notes": r.notes}
            for r in db.scalars(select(TaxRule)).all()]


def quality_report(db: Session) -> dict:
    sheet = balance_sheet(db)
    issues = list(sheet["data_issues"])
    if not db.scalars(select(FXRate).limit(1)).first():
        issues.append({"type": "INFO", "name": "No FX rates recorded: NGN valuations only."})
    return {
        "issues": issues, "critical": sum(x["type"].startswith("MISSING") for x in issues),
        "warnings": sum(x["type"].startswith("STALE") for x in issues),
        "complete": sheet["complete"],
        "disclosure": "This validates recorded positions only, not unreported assets, corporate actions, stale fund constituents or missing cash transactions.",
    }


def wealth_health(db: Session) -> dict:
    sheet, cash = balance_sheet(db), cashflow(db)
    risk = risk_report(db)
    goals = goals_overview(db)
    has_assets = sheet["assets_ngn"] > 0
    has_reserve = cash["emergency_reserve_ngn"] > 0
    scores = {
        "liquidity": min(100, max(0, 100 * cash["starting_cash_ngn"] /
                              cash["emergency_reserve_ngn"]))
                     if has_reserve and not cash["missing_fx_currencies"] else None,
        "concentration": max(0, 100 * (1 - risk["class_concentration_hhi"]))
                         if risk["class_concentration_hhi"] is not None else None,
        "goal_readiness": min(100, sum(min(1, g.get("goal_funding_ratio", 0)) for g in goals) /
                              len(goals) * 100) if goals and all("goal_funding_ratio" in g for g in goals) else None,
        "data_quality": max(0, 100 - 30 * len([x for x in sheet["data_issues"] if x["type"].startswith("MISSING")])
                            - 5 * len([x for x in sheet["data_issues"] if x["type"].startswith("STALE")]))
                        if has_assets or sheet["data_issues"] else None,
    }
    weights = {"liquidity": .30, "concentration": .25, "goal_readiness": .35, "data_quality": .10}
    populated = {k: v for k, v in scores.items() if v is not None}
    # An overall score without assets or a planning goal would fabricate
    # personal financial confidence out of absent information.
    valid = has_assets and bool(goals) and sheet["complete"]
    overall = (sum(weights[k] * v for k, v in populated.items()) /
               sum(weights[k] for k in populated)) if populated and valid else None
    return {
        "score": round(overall, 1) if overall is not None else None,
        "dimensions": {k: round(v, 1) if v is not None else None for k, v in scores.items()},
        "unavailable": [k for k, v in scores.items() if v is None],
        "confidence": "insufficient" if not valid else ("partial" if len(populated) < 4 else "baseline"),
        "disclosure": "A transparent planning heuristic, not a validated financial or investment risk score. Missing assets, goal definitions or FX rates can suppress the total score.",
    }


def evidence_brief(db: Session) -> dict:
    sheet, cash, risk, quality = balance_sheet(db), cashflow(db), risk_report(db), quality_report(db)
    actions = []
    if quality["critical"] > 0:
        actions.append({"priority": "HIGH", "action": "Repair missing valuations",
                        "why": f'{quality["critical"]} missing-price or missing-FX issues affect reported net worth.'})
    if cash["lowest_balance_ngn"] < 0:
        actions.append({"priority": "HIGH", "action": "Address forecast cash shortfall",
                        "why": "Entered obligations could exceed forecast cash."})
    if risk["class_concentration_hhi"] is not None and risk["class_concentration_hhi"] > .5:
        actions.append({"priority": "MEDIUM", "action": "Review asset-class concentration",
                        "why": f'Concentration index {risk["class_concentration_hhi"]:.2f} exceeds review threshold 0.50.'})
    if not db.scalars(select(Goal).limit(1)).first():
        actions.append({"priority": "MEDIUM", "action": "Define financial goals",
                        "why": "There is no reliable objective for goal-based capital allocation."})
    return {
        "summary": {
            "net_worth_ngn": sheet["net_worth_ngn"],
            "deployable_ngn": cash["deployable_ngn"],
            "quality_critical": quality["critical"],
            "concentration_hhi": risk["class_concentration_hhi"],
        },
        "recommended_reviews": actions,
        "source_paths": ["/api/portfolio", "/api/liquidity", "/api/risk", "/api/quality"],
        "disclosure": "Rule-based evidence briefing. No generative AI assertion or autonomous action. Recommendations are reviews, not trade instructions.",
    }
