"""Pure deterministic numerical tests."""
import math

import pytest

from app.analytics import (
    compare_allocations, dcf, future_value, goal_projection, momentum_signal,
    monte_carlo, net_sale_proceeds, opportunity_cost, rebalance, risk_from_aligned_returns,
    stress_test, validate_backtest,
)


def test_future_value_zero_rate_and_goal():
    assert future_value(1_000_000, 10_000, 0, 1) == pytest.approx(1_120_000)
    g = goal_projection(100, 500, 10, 10, 8, 6)
    assert g["target_future_ngn"] > 500
    assert g["required_monthly_ngn"] >= 0


def test_monte_carlo_is_seeded_and_exposes_risk():
    a = monte_carlo(1000, 10, 5, 6, 20, 3000, 4, simulations=200, seed=23)
    b = monte_carlo(1000, 10, 5, 6, 20, 3000, 4, simulations=200, seed=23)
    assert a == b
    assert 0 <= a["goal_probability"] <= 1
    assert a["percentiles_ngn"]["p10"] <= a["percentiles_ngn"]["p90"]


def test_dcf_transparency_and_invalid_rates():
    a = dcf(100, 5, 12, 3, 5, 100, 10)
    assert a["fair_value_per_share"] > 0
    assert a["terminal_value_share_pct"] > 0
    assert len(a["forecast"]) == 5
    with pytest.raises(ValueError, match="exceed"):
        dcf(100, 5, 5, 5, 5)


def test_net_return_computes_positive_gain_tax():
    a = net_sale_proceeds(1250, 1000, 10, 2, "GAIN")
    # 25 fee; 225 taxable gain; 22.5 tax
    assert a["estimated_fees"] == 25
    assert a["estimated_tax"] == 22.5
    assert a["net_proceeds"] == 1202.5
    with pytest.raises(ValueError):
        net_sale_proceeds(1200, 1000, -1, 0)


def test_transfer_and_rebalancing_preserve_money():
    a = rebalance({"NGX_STOCK": 700, "CASH": 300}, {"NGX_STOCK": 50, "CASH": 50}, 200)
    assert sum(a["contribute_ngn"].values()) == pytest.approx(200)
    assert a["contribute_ngn"]["CASH"] >= a["contribute_ngn"]["NGX_STOCK"]
    assert sum(a["after_pct"].values()) == pytest.approx(100)


def test_stress_combines_asset_and_income_shocks():
    a = stress_test({"STOCK": 600, "CASH": 400}, {"STOCK": -50}, 100, 50, 100, 2)
    assert a["net_worth_before"] == 900
    assert a["net_worth_after"] == 350
    assert a["loss_ngn"] == 550
    with pytest.raises(ValueError, match="Unknown"):
        stress_test({"STOCK": 100}, {"X": -20})


def test_price_signal_has_sample_gate():
    assert momentum_signal([10, 11], 5)["available"] is False
    good = momentum_signal([10, 10.2, 10.3, 10.5, 10.7, 11], 5)
    assert good["available"] and good["momentum_pct"] == pytest.approx(10)


def test_allocation_checks_weights_and_seed():
    a = compare_allocations(
        {"Risky": {"CASH": 0, "NGX_STOCK": 100}, "Safe": {"CASH": 100, "NGX_STOCK": 0}},
        {"CASH": 5, "NGX_STOCK": 8},
        {"CASH": 1, "NGX_STOCK": 30},
        1000, 0, 2000, 5, simulations=300,
    )
    assert len(a["ranked"]) == 2
    assert {x["name"] for x in a["ranked"]} == {"Risky", "Safe"}
    with pytest.raises(ValueError, match="total"):
        compare_allocations({"x":{"CASH":80,"NGX_STOCK":10}},
                            {"CASH":5,"NGX_STOCK":8},
                            {"CASH":1,"NGX_STOCK":30},1000,0,2000,5)


def test_backtest_uses_chronological_holdout():
    s = [1.0] * 10 + [-2.0] * 10
    b = [0.1] * 20
    result = validate_backtest(s, b, 0.1, .5)
    assert result["segments"]["development"]["strategy"]["total_return_pct"] > 0
    assert result["segments"]["holdout"]["strategy"]["total_return_pct"] < 0
    assert result["segments"]["holdout"]["strategy"]["periods"] == 10


def test_historical_risk_requires_26_periods():
    with pytest.raises(ValueError):
        risk_from_aligned_returns([[.01]] * 12, [1])
    result = risk_from_aligned_returns([[.01], [-.02]] * 15, [1])
    assert result["observations"] == 30
    assert result["max_drawdown_pct"] < 0


def test_opportunity_cost_is_a_scenario_not_a_predicted_return():
    r = opportunity_cost(100000, 10, 8, 4)
    assert r["hypothetical_future_ngn"] > 100000
    assert "not a judgment" in r["disclosure"]
