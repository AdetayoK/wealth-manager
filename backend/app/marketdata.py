"""Optional US equity/ETF daily-close adapter with explicit provenance.

Uses Alpha Vantage TIME_SERIES_DAILY raw, unadjusted EOD data. Must not
be used for total-return backtests without split/dividend adjustments.
Only manually triggered, one instrument per call; no background polling.
"""
from __future__ import annotations

import os
from datetime import date
from decimal import Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from .finance import dec
from .models import Instrument, Price

URL = "https://www.alphavantage.co/query"


class MarketFeedError(RuntimeError):
    pass


def parse_alpha_daily(payload: dict) -> list[tuple[date, Decimal]]:
    if not isinstance(payload, dict):
        raise MarketFeedError("Provider response is not a JSON object")
    if any(k in payload for k in ("Note", "Information", "Error Message")):
        raise MarketFeedError("Provider reported an error or rate limit; no prices were written")
    series = payload.get("Time Series (Daily)")
    if not isinstance(series, dict) or not series:
        raise MarketFeedError("No supported daily close series in response")
    result = []
    try:
        for ds, values in series.items():
            d = date.fromisoformat(ds)
            value = dec(values["4. close"])
            if value <= 0:
                raise ValueError("close <= 0")
            if d <= date.today():
                result.append((d, value))
    except (TypeError, KeyError, ValueError) as exc:
        raise MarketFeedError("Unexpected provider date or price shape; no prices were written") from exc
    if not result:
        raise MarketFeedError("Provider supplied no usable dated prices")
    return sorted(result)


def fetch_alpha_daily(symbol: str, key: str, requester=None) -> list[tuple[date, Decimal]]:
    if not key:
        raise MarketFeedError("Set ALPHAVANTAGE_API_KEY in .env before syncing prices")
    own_client = requester is None
    client = requester or httpx.Client(timeout=18.0)
    try:
        response = client.get(
            URL,
            params={"function": "TIME_SERIES_DAILY", "symbol": symbol,
                    "outputsize": "compact", "apikey": key},
        )
        response.raise_for_status()
        return parse_alpha_daily(response.json())
    except (httpx.HTTPError, ValueError) as exc:
        raise MarketFeedError("US daily-close provider request failed; no prices were written") from exc
    finally:
        if own_client:
            client.close()


def sync_us_instrument(db: Session, instrument_id: int) -> dict:
    inst = db.get(Instrument, instrument_id)
    if not inst:
        raise ValueError("Instrument does not exist")
    if inst.currency != "USD" or inst.asset_class not in {"US_STOCK", "ETF"}:
        raise ValueError("Only USD-denominated US equities and ETFs can use this adapter")
    if inst.asset_class == "ETF" and inst.exchange.upper() not in {"XNAS", "XNYS", "ARCX"}:
        raise ValueError("ETF exchange must identify a supported US listing (XNAS, XNYS, ARCX)")
    key = os.getenv("ALPHAVANTAGE_API_KEY", "").strip()
    quotes = fetch_alpha_daily(inst.symbol, key)
    existing = {p.as_of: p for p in db.scalars(
        select(Price).where(Price.instrument_id == inst.id)
    ).all()}
    try:
        for d, close in quotes:
            row = existing.get(d)
            if row is None:
                db.add(Price(instrument_id=inst.id, as_of=d, close=close,
                             source="alpha_vantage_raw_daily"))
            else:
                row.close = close
                row.source = "alpha_vantage_raw_daily"
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {
        "instrument_id": inst.id,
        "symbol": inst.symbol, "rows": len(quotes),
        "earliest": str(quotes[0][0]), "latest": str(quotes[-1][0]),
        "source": "Alpha Vantage TIME_SERIES_DAILY (raw, not split/dividend adjusted)",
        "limitations": [
            "Raw daily closes are not sufficient to compute a dividend/split-adjusted total return.",
            "Alpha Vantage price history, usage limits and redistribution require compliance with provider terms.",
            "FX is stored separately; these prices are USD values and do not automatically provide NGN performance.",
            "An upstream API key must be configured by the owner; no other market feed is silently used.",
        ],
    }
