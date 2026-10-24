"""External price-feed response validation; no network calls in tests."""
from datetime import date
import pytest

from app.marketdata import MarketFeedError, parse_alpha_daily


def test_daily_price_parser_requires_provenanced_positive_prices():
    today=date.today().isoformat()
    rows=parse_alpha_daily({"Time Series (Daily)": {
        today: {"4. close": "102.75"},
        "2026-01-02": {"4. close": "101.20"},
    }})
    assert len(rows)==2
    assert rows[0][0] < rows[1][0]
    assert float(rows[-1][1])==pytest.approx(102.75)


def test_daily_parser_rejects_provider_rate_limit_and_incomplete_shape():
    with pytest.raises(MarketFeedError, match="rate limit"):
        parse_alpha_daily({"Note": "please slow down"})
    with pytest.raises(MarketFeedError, match="No supported"):
        parse_alpha_daily({"ok": True})
    with pytest.raises(MarketFeedError, match="Unexpected provider"):
        parse_alpha_daily({"Time Series (Daily)": {"2026-01-02": {"4. close": "-1"}}})
