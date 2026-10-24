"""Deterministic investment analytics; independent of HTTP, database and AI.

Simulation and valuation outputs are CONDITIONAL on supplied assumptions.
Never treat a probability or fair value as a guaranteed investment outcome.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np


def _finite(*values):
    if not all(math.isfinite(float(x)) for x in values):
        raise ValueError("Inputs must be finite numbers")


def future_value(capital: float, monthly: float, annual_pct: float, years: float) -> float:
    _finite(capital, monthly, annual_pct, years)
    if capital < 0 or monthly < 0 or not 0 <= years <= 80 or annual_pct <= -100:
        raise ValueError("Invalid wealth simulation parameters")
    n = round(years * 12)
    r = (1 + annual_pct / 100) ** (1 / 12) - 1
    if abs(r) < 1e-12:
        return capital + monthly * n
    return capital * (1 + r) ** n + monthly * ((1 + r) ** n - 1) / r


def goal_projection(
    current: float, target_today: float, years: float,
    monthly: float, assumed_return_pct: float, inflation_pct: float,
) -> dict:
    _finite(current, target_today, years, monthly, assumed_return_pct, inflation_pct)
    if years <= 0 or target_today <= 0 or inflation_pct <= -100:
        raise ValueError("Goal date and amounts must be valid")
    target = target_today * (1 + inflation_pct / 100) ** years
    expected = future_value(current, monthly, assumed_return_pct, years)
    # Compute required contribution by linearity; no invented returns.
    starting_only = future_value(current, 0, assumed_return_pct, years)
    factor = future_value(0, 1, assumed_return_pct, years)
    required = max(0, (target - starting_only) / factor) if factor > 0 else None
    return {
        "target_future_ngn": round(target, 2), "expected_future_ngn": round(expected, 2),
        "shortfall_ngn": round(max(0, target - expected), 2),
        "required_monthly_ngn": round(required, 2) if required is not None else None,
        "monthly_contribution_ngn": monthly,
        "goal_funding_ratio": round(expected / target, 4),
        "assumption": {"annual_return_pct": assumed_return_pct, "inflation_pct": inflation_pct},
    }


def monte_carlo(
    initial: float, monthly: float, years: int,
    expected_return_pct: float, volatility_pct: float,
    goal_ngn: float, inflation_pct: float = 0,
    simulations: int = 3000, seed: int = 2046,
) -> dict:
    _finite(initial, monthly, years, expected_return_pct, volatility_pct, goal_ngn, inflation_pct)
    if not 1 <= years <= 60 or not 200 <= simulations <= 10000:
        raise ValueError("Years must be 1–60 and simulations 200–10000")
    if min(initial, monthly, goal_ngn) < 0 or volatility_pct < 0 or expected_return_pct <= -100 or inflation_pct <= -100:
        raise ValueError("Invalid capital or return assumptions")
    rng = np.random.default_rng(seed)
    wealth = np.full(simulations, initial, dtype=float)
    mu = (1 + expected_return_pct / 100) ** (1 / 12) - 1
    sig = volatility_pct / 100 / np.sqrt(12)
    for _ in range(years * 12):
        monthly_growth = np.maximum(-1.0, mu + sig * rng.standard_normal(simulations))
        wealth = wealth * (1 + monthly_growth) + monthly
    inflation_factor = (1 + inflation_pct / 100) ** years
    percentiles = np.percentile(wealth, [5, 10, 50, 90, 95])
    return {
        "goal_probability": round(float(np.mean(wealth >= goal_ngn)), 4),
        "percentiles_ngn": dict(zip(("p5", "p10", "p50", "p90", "p95"),
                                   [round(float(x), 2) for x in percentiles])),
        "median_real_today_ngn": round(float(percentiles[2] / inflation_factor), 2),
        "contributions_ngn": round(initial + monthly * 12 * years, 2),
        "probability_below_contributions": round(float(np.mean(wealth < initial + monthly * 12 * years)), 4),
        "simulations": simulations, "seed": seed,
        "limits": [
            "Expected return, volatility and inflation are supplied assumptions, not predictions.",
            "Independent, normally distributed monthly shocks miss fat tails and regime shifts.",
            "Taxes, fees, FX, portfolio rebalancing and correlation are excluded.",
        ],
    }


def stress_test(
    class_values: dict[str, float], shock_pct: dict[str, float],
    liabilities: float = 0, emergency_expense: float = 0,
    monthly_income_loss: float = 0, income_loss_months: int = 0,
) -> dict:
    if min(liabilities, emergency_expense, monthly_income_loss) < 0 or not 0 <= income_loss_months <= 60:
        raise ValueError("Costs cannot be negative, duration must be 0–60 months")
    if any(x < 0 for x in class_values.values()):
        raise ValueError("Asset class amounts must not be negative")
    if any(not -100 <= x <= 1000 for x in shock_pct.values()):
        raise ValueError("Shocks must be between -100% and 1000%")
    unknown = set(shock_pct) - set(class_values)
    if unknown:
        raise ValueError(f"Unknown asset classes: {', '.join(sorted(unknown))}")
    before = sum(class_values.values()) - liabilities
    after_classes = {k: round(value * (1 + shock_pct.get(k, 0) / 100), 2)
                     for k, value in class_values.items()}
    after = sum(after_classes.values()) - liabilities - emergency_expense - monthly_income_loss * income_loss_months
    return {
        "net_worth_before": round(before, 2), "net_worth_after": round(after, 2),
        "loss_ngn": round(before - after, 2),
        "change_pct": round((after / before - 1) * 100, 2) if before > 0 else None,
        "after_classes": after_classes,
        "disclosure": "One-step stress only. Assumptions are not probabilities. FX and market shocks must not be double-counted.",
    }


def opportunity_cost(
    amount: float, years: float, expected_return_pct: float,
    inflation_pct: float = 0, monthly_replacement: float = 0,
) -> dict:
    invested = future_value(amount, monthly_replacement, expected_return_pct, years)
    if inflation_pct <= -100:
        raise ValueError("Inflation must be above -100%")
    real = invested / (1 + inflation_pct / 100) ** years
    return {
        "spending_ngn": amount, "hypothetical_future_ngn": round(invested, 2),
        "hypothetical_today_naira": round(real, 2),
        "disclosure": "Opportunity cost is not a judgment about the value of spending. Taxes, fees and risk are excluded.",
    }


def dcf(
    base_fcf: float, growth_pct: float, discount_pct: float,
    terminal_growth_pct: float, forecast_years: int,
    net_debt: float = 0, shares: float = 1,
) -> dict:
    _finite(base_fcf, growth_pct, discount_pct, terminal_growth_pct, net_debt, shares)
    if not 1 <= forecast_years <= 20 or shares <= 0 or not -95 < growth_pct <= 100:
        raise ValueError("Invalid forecast length, growth or share count")
    if discount_pct <= terminal_growth_pct or discount_pct <= -100 or terminal_growth_pct <= -100:
        raise ValueError("Discount rate must exceed terminal growth")
    r, g, terminal_g = discount_pct / 100, growth_pct / 100, terminal_growth_pct / 100
    fcf = base_fcf
    pv = 0.0
    flows = []
    for year in range(1, forecast_years + 1):
        fcf *= 1 + g
        discounted = fcf / (1 + r) ** year
        pv += discounted
        flows.append({"year": year, "cash_flow": round(fcf, 2), "present_value": round(discounted, 2)})
    terminal_value = fcf * (1 + terminal_g) / (r - terminal_g)
    terminal_pv = terminal_value / (1 + r) ** forecast_years
    equity = pv + terminal_pv - net_debt
    return {
        "equity_value": round(equity, 2),
        "fair_value_per_share": round(equity / shares, 4),
        "terminal_value_share_pct": round(terminal_pv / (pv + terminal_pv) * 100, 2) if pv + terminal_pv else None,
        "forecast": flows, "assumptions": {
            "base_free_cash_flow": base_fcf, "growth_pct": growth_pct,
            "discount_pct": discount_pct, "terminal_growth_pct": terminal_growth_pct,
            "years": forecast_years, "net_debt": net_debt, "shares": shares,
        },
        "disclosure": "Illustrative DCF, not intrinsic-value truth. Terminal assumptions can dominate the result.",
    }


def momentum_signal(closes: list[float], lookback: int = 20) -> dict:
    if not 5 <= lookback <= 252:
        raise ValueError("Lookback must be 5 to 252 points")
    if len(closes) < lookback + 1:
        return {"available": False, "reason": f"Need at least {lookback + 1} closes"}
    px = np.asarray(closes[-(lookback + 1):], dtype=float)
    if np.any(~np.isfinite(px)) or np.any(px <= 0):
        return {"available": False, "reason": "Invalid or missing price"}
    returns = np.diff(px) / px[:-1]
    return {
        "available": True,
        "momentum_pct": round(float((px[-1] / px[0] - 1) * 100), 2),
        "annualized_vol_pct": round(float(np.std(returns, ddof=1) * np.sqrt(252) * 100), 2),
        "observations": lookback + 1,
        "disclosure": "Descriptive momentum. Not a validated trading recommendation.",
    }


def risk_from_aligned_returns(matrix: list[list[float]], weights: list[float]) -> dict:
    """Returns are fractions, columns aligned by date. Input is pre-filtered for stale prices."""
    a = np.asarray(matrix, dtype=float)
    w = np.asarray(weights, dtype=float)
    if a.ndim != 2 or a.shape[0] < 26 or a.shape[1] != len(w):
        raise ValueError("Need 26+ aligned historical observations for all selected assets")
    if not np.all(np.isfinite(a)) or np.any(a <= -1) or not np.all(np.isfinite(w)):
        raise ValueError("Invalid return data")
    if np.any(w < 0) or not np.isclose(np.sum(w), 1):
        raise ValueError("Weights must be nonnegative and sum to one")
    p = a @ w
    nav = np.cumprod(1 + p)
    max_drawdown = float(np.min(nav / np.maximum.accumulate(np.concatenate([[1], nav]))[1:] - 1))
    tail = np.percentile(p, 5)
    return {
        "observations": len(p),
        "historical_var95_pct_per_period": round(float(-tail * 100), 3),
        "historical_expected_shortfall95_pct_per_period": round(float(-np.mean(p[p <= tail]) * 100), 3),
        "max_drawdown_pct": round(max_drawdown * 100, 3),
        "volatility_pct_per_period": round(float(np.std(p, ddof=1) * 100), 3),
        "correlation": np.corrcoef(a, rowvar=False).tolist() if a.shape[1] > 1 else [[1.0]],
        "disclosure": "Only aligned historical returns of modelled assets. Historical risk is not a future loss bound.",
    }


def compare_allocations(
    candidates: dict[str, dict[str, float]], expected: dict[str, float],
    volatility: dict[str, float], initial: float, monthly: float,
    target: float, years: int, min_cash_pct: float = 0,
    simulations: int = 1500, seed: int = 42,
) -> dict:
    if not 1 <= len(candidates) <= 8 or target <= 0 or initial < 0 or monthly < 0:
        raise ValueError("Supply 1–8 allocations, a positive goal and nonnegative funding")
    if not 1 <= years <= 40 or not 200 <= simulations <= 5000:
        raise ValueError("Invalid horizon or number of simulated paths")
    classes = sorted(expected)
    if not classes or set(volatility) != set(classes):
        raise ValueError("Provide assumed returns and volatility for the same asset classes")
    if any(not -99 < expected[k] < 1000 or not 0 <= volatility[k] <= 200 for k in classes):
        raise ValueError("Invalid return / volatility assumptions")
    rng = np.random.default_rng(seed)
    normals = rng.standard_normal((simulations, years * 12, len(classes)))
    r = np.asarray([(1 + expected[k] / 100) ** (1 / 12) - 1 for k in classes])
    s = np.asarray([volatility[k] / 100 / math.sqrt(12) for k in classes])
    rows = []
    for name, mix in candidates.items():
        if set(mix) != set(classes) or any(x < 0 or x > 100 for x in mix.values()):
            raise ValueError("Allocation classes must exactly match assumptions; shares must be 0–100")
        if not math.isclose(sum(mix.values()), 100, abs_tol=0.001):
            raise ValueError(f"{name}: allocation must total 100%")
        if mix.get("CASH", 0) < min_cash_pct:
            raise ValueError(f"{name}: cash below required minimum")
        weights = np.array([mix[k] for k in classes]) / 100
        nav = np.full(simulations, initial, dtype=float)
        for month in range(years * 12):
            growth = np.maximum(0, 1 + r + normals[:, month, :] * s)
            nav = nav * (growth @ weights) + monthly
        rows.append({
            "name": name, "weights_pct": mix,
            "probability_goal": round(float(np.mean(nav >= target)), 4),
            "median_ngn": round(float(np.median(nav)), 2),
            "p10_ngn": round(float(np.percentile(nav, 10)), 2),
            "p90_ngn": round(float(np.percentile(nav, 90)), 2),
        })
    rows.sort(key=lambda a: (-a["probability_goal"], -a["p10_ngn"]))
    return {
        "ranked": rows, "assumptions": {"expected_return_pct": expected,
                                      "volatility_pct": volatility, "seed": seed, "paths": simulations},
        "disclosure": [
            "Only user-supplied return and volatility assumptions are used.",
            "Class shocks are independent normal draws; no estimated correlation or fat-tail model.",
            "Taxes, FX movements, transaction costs and liquidity constraints beyond min_cash_pct are omitted.",
        ],
    }


def rebalance(current: dict[str, float], target_pct: dict[str, float], contribution: float) -> dict:
    if contribution < 0 or not current or set(current) != set(target_pct):
        raise ValueError("Invalid contribution, holdings or target allocation")
    if any(x < 0 for x in current.values()) or any(not 0 <= x <= 100 for x in target_pct.values()):
        raise ValueError("Values and allocations must be nonnegative")
    if not math.isclose(sum(target_pct.values()), 100, abs_tol=.001):
        raise ValueError("Target must total 100%")
    total = sum(current.values()) + contribution
    short = {k: max(0, total * target_pct[k] / 100 - current[k]) for k in current}
    need = sum(short.values())
    if need >= contribution and need > 0:
        buys = {k: contribution * short[k] / need for k in current}
    else:
        spare = contribution - need
        buys = {k: short[k] + spare * target_pct[k] / 100 for k in current}
    after = {k: current[k] + buys[k] for k in current}
    return {
        "contribute_ngn": {k: round(v, 2) for k, v in buys.items()},
        "after_pct": {k: round(after[k] / total * 100, 2) if total else 0 for k in current},
        "drift_pct": {k: round(after[k] / total * 100 - target_pct[k], 2) if total else 0 for k in current},
        "disclosure": "Contribution-only, no selling, taxes or lot constraints. Asset-class targets are assumptions.",
    }


def net_sale_proceeds(value: float, cost_basis: float, tax_pct: float, fee_pct: float,
                      tax_basis: str = "GAIN") -> dict:
    _finite(value, cost_basis, tax_pct, fee_pct)
    if min(value, cost_basis, tax_pct, fee_pct) < 0 or max(tax_pct, fee_pct) > 100:
        raise ValueError("Negative values and percentage rates above 100% are unsupported")
    if tax_basis not in {"GAIN", "PROCEEDS"}:
        raise ValueError("Tax basis must be GAIN or PROCEEDS")
    fee = value * fee_pct / 100
    taxable = max(0, value - cost_basis - fee) if tax_basis == "GAIN" else value
    tax = taxable * tax_pct / 100
    return {
        "gross_proceeds": value, "estimated_tax": round(tax, 2),
        "estimated_fees": round(fee, 2), "net_proceeds": round(value - tax - fee, 2),
        "net_gain": round(value - tax - fee - cost_basis, 2),
        "disclosure": "Uses a manually supplied tax rule, not a determination of legal tax treatment.",
    }


def validate_backtest(strategy: list[float], benchmark: list[float], fee_pct: float = 0,
                      train_fraction: float = .7) -> dict:
    if len(strategy) != len(benchmark) or not 12 <= len(strategy) <= 5000:
        raise ValueError("Need 12–5000 chronologically aligned period returns")
    if not 0 <= fee_pct < 100 or not .5 <= train_fraction <= .9:
        raise ValueError("Invalid fee or development fraction")
    if any(not math.isfinite(v) or v < -100 for v in strategy + benchmark):
        raise ValueError("Period returns must be finite and not below -100%")
    n = max(1, min(len(strategy) - 1, int(len(strategy) * train_fraction)))
    def metrics(values):
        growth = np.cumprod(1 + np.asarray(values, dtype=float) / 100)
        tops = np.maximum.accumulate(np.concatenate([[1.0], growth]))[1:]
        return {
            "total_return_pct": round(float((growth[-1] - 1) * 100), 3),
            "max_drawdown_pct": round(float(np.min(growth / tops - 1) * 100), 3),
            "periods": len(values),
        }
    result = {}
    for title, a, b in (("development", strategy[:n], benchmark[:n]),
                        ("holdout", strategy[n:], benchmark[n:])):
        net_strategy = [x - fee_pct for x in a]
        result[title] = {
            "strategy": metrics(net_strategy), "benchmark": metrics(b),
            "average_excess_pct_per_period": round(float(np.mean(np.array(net_strategy) - np.array(b))), 4),
        }
    return {
        "segments": result, "fee_pct_per_period": fee_pct,
        "caveats": [
            "Chronological split is not proof against look-ahead or survivorship bias.",
            "Strategy design and parameter tuning must not use the holdout sample.",
            "User-provided period returns do not model trade execution, spreads or market impact.",
        ],
    }
