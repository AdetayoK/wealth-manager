"""Foreign investment return attribution in local (NGN) purchasing currency.

Use currency amounts per share and NGN-per-unit FX. This is explicitly a
two-point attribution and excludes interim capital flows / tax rules.
Decimal math avoids floating point drift and residual arithmetic.
"""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

Q = Decimal("0.01")


def _decimal(value, label: str) -> Decimal:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"{label} must be a number") from exc
    if not number.is_finite():
        raise ValueError(f"{label} must be finite")
    return number


def attribute_foreign_return(
    opening_price, closing_price, opening_fx, closing_fx,
    units=1, dividends_per_unit=0, costs_ngn=0,
) -> dict:
    """Exact algebraic price/FX/interaction/dividend/cost decomposition.

    Price and dividends are in the foreign currency.
    FX must be NGN per unit of that foreign currency, recorded on the
    respective valuation dates.
    Costs are cumulative NGN costs for this entire position.
    Dividends are assumed converted at closing FX, not historical payout FX.
    """
    p0 = _decimal(opening_price, "opening_price")
    p1 = _decimal(closing_price, "closing_price")
    f0 = _decimal(opening_fx, "opening_fx")
    f1 = _decimal(closing_fx, "closing_fx")
    n = _decimal(units, "units")
    dividends = _decimal(dividends_per_unit, "dividends_per_unit")
    costs = _decimal(costs_ngn, "costs_ngn")
    if min(p0, p1, f0, f1, n) <= 0 or dividends < 0 or costs < 0:
        raise ValueError("Prices, FX rates and units must be positive; dividends and costs nonnegative")

    opening = n * p0 * f0
    components = {
        "security_price_ngn": n * (p1 - p0) * f0,
        "currency_ngn": n * p0 * (f1 - f0),
        "price_fx_interaction_ngn": n * (p1 - p0) * (f1 - f0),
        "dividends_ngn": n * dividends * f1,
        "costs_ngn": -costs,
    }
    gain = sum(components.values(), Decimal(0))
    ending = n * (p1 + dividends) * f1 - costs
    assert opening + gain == ending

    def cash(x: Decimal) -> float:
        return float(x.quantize(Q, rounding=ROUND_HALF_UP))

    return {
        "opening_value_ngn": cash(opening),
        "closing_value_with_dividends_and_costs_ngn": cash(ending),
        "total_gain_ngn": cash(gain),
        "total_return_pct": round(float(gain / opening * 100), 6),
        "security_price_return_pct_foreign": round(float((p1 / p0 - 1) * 100), 6),
        "fx_change_pct": round(float((f1 / f0 - 1) * 100), 6),
        "components": {key: cash(value) for key, value in components.items()},
        "component_pct_of_opening": {
            key: round(float(value / opening * 100), 6)
            for key, value in components.items()
        },
        "method": "two-point exact algebraic decomposition; not a time-weighted return",
        "assumptions": [
            "No purchases or sales between valuation dates; constant units.",
            "Dividend cash is translated at closing FX; enter a separate analysis for differing actual dividend FX dates.",
            "Costs are aggregate NGN and included as a negative contribution.",
            "No tax law is inferred; tax withholding must be included in costs if applicable.",
            "Real inflation-adjusted performance requires separate CPI observations.",
        ],
    }
