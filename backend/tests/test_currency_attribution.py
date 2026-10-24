"""Foreign return attribution: exact decomposition invariants."""
import pytest

from app.currency_attribution import attribute_foreign_return


def test_exact_ngn_decomposition_with_dividends():
    result = attribute_foreign_return(100, 110, 1500, 1650, units=10, dividends_per_unit=2, costs_ngn=500)
    assert result["opening_value_ngn"] == 1_500_000
    assert result["components"] == {
        "security_price_ngn": 150000.0,
        "currency_ngn": 150000.0,
        "price_fx_interaction_ngn": 15000.0,
        "dividends_ngn": 33000.0,
        "costs_ngn": -500.0,
    }
    assert result["total_gain_ngn"] == 347500.0
    assert result["closing_value_with_dividends_and_costs_ngn"] == 1847500.0
    assert result["total_return_pct"] == pytest.approx(23.166667, rel=1e-6)


def test_unchanged_price_deteriorating_fx():
    result = attribute_foreign_return(100, 100, 1500, 1200, units=1)
    assert result["security_price_return_pct_foreign"] == 0
    assert result["total_return_pct"] == -20
    assert result["components"]["currency_ngn"] == -30000


@pytest.mark.parametrize("kwargs", [
    {"opening_price": 0, "closing_price": 1, "opening_fx": 1, "closing_fx": 1},
    {"opening_price": 1, "closing_price": 1, "opening_fx": -1, "closing_fx": 1},
    {"opening_price": 1, "closing_price": 1, "opening_fx": 1, "closing_fx": 1, "units": 0},
    {"opening_price": "nan", "closing_price": 1, "opening_fx": 1, "closing_fx": 1},
])
def test_invalid_financial_inputs(kwargs):
    with pytest.raises(ValueError):
        attribute_foreign_return(**kwargs)
