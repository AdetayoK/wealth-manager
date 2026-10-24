"""Financial system of record: positions, cash, FX, valuations and safeguards.

All authoritative money arithmetic uses Decimal. Missing market inputs are
explicit data-quality errors rather than silently fabricated zeros.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Account, BalanceItem, CashEntry, FXRate, Instrument, Price, Trade

ZERO = Decimal("0")
ONE = Decimal("1")
CENTS = Decimal("0.01")


def dec(value: Any) -> Decimal:
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError("Number must be finite")
    return result


def money(value: Decimal) -> float:
    """JSON boundary conversion; never use this in accounting equations."""
    return float(value.quantize(CENTS))


def fx_to_ngn(db: Session, currency: str, as_of: date) -> tuple[Decimal | None, date | None]:
    curr = currency.upper()
    if curr == "NGN":
        return ONE, as_of
    direct = db.scalar(
        select(FXRate).where(
            FXRate.base == curr, FXRate.quote == "NGN", FXRate.as_of <= as_of
        ).order_by(FXRate.as_of.desc())
    )
    if direct is not None:
        return direct.rate, direct.as_of
    inverse = db.scalar(
        select(FXRate).where(
            FXRate.base == "NGN", FXRate.quote == curr, FXRate.as_of <= as_of
        ).order_by(FXRate.as_of.desc())
    )
    if inverse is not None:
        return ONE / inverse.rate, inverse.as_of
    return None, None


def last_price(db: Session, instrument_id: int, as_of: date) -> Price | None:
    return db.scalar(select(Price).where(
        Price.instrument_id == instrument_id, Price.as_of <= as_of
    ).order_by(Price.as_of.desc()))


def _trades(db: Session, as_of: date, account_id: int | None = None) -> list[Trade]:
    q = select(Trade).where(Trade.as_of <= as_of)
    if account_id is not None:
        q = q.where(Trade.account_id == account_id)
    return list(db.scalars(q.order_by(Trade.as_of, Trade.id)).all())


def position_costs(db: Session, as_of: date) -> dict[tuple[int, int], dict]:
    """Weighted-average cost basis per account and instrument, including buy fees.

    Historical validation will fail for any chronology containing a short sale.
    This is intentional: a bad ledger must not produce a credible valuation.
    """
    positions: dict[tuple[int, int], dict] = {}
    for trade in _trades(db, as_of):
        key = (trade.account_id, trade.instrument_id)
        pos = positions.setdefault(key, {"quantity": ZERO, "cost": ZERO, "realized": ZERO})
        qty, price, fees = dec(trade.quantity), dec(trade.price), dec(trade.fees)
        if trade.side == "BUY":
            pos["quantity"] += qty
            pos["cost"] += qty * price + fees
        else:
            if qty > pos["quantity"] + Decimal("0.0000001"):
                raise ValueError(f"Invalid sell history: trade {trade.id} exceeds owned quantity")
            per_unit = pos["cost"] / pos["quantity"] if pos["quantity"] else ZERO
            consumed = per_unit * qty
            pos["realized"] += qty * price - fees - consumed
            pos["cost"] -= consumed
            pos["quantity"] -= qty
            if pos["quantity"] <= Decimal("0.0000001"):
                pos["quantity"], pos["cost"] = ZERO, ZERO
    return positions


def validate_new_trade(
    db: Session, account_id: int, instrument_id: int, as_of: date,
    side: str, quantity: Decimal,
) -> None:
    if side != "SELL":
        return
    # Backdated inserts also must not make *later* holdings go negative.
    existing = db.scalars(select(Trade).where(
        Trade.account_id == account_id,
        Trade.instrument_id == instrument_id,
    ).order_by(Trade.as_of, Trade.id)).all()
    owned = ZERO
    inserted = False
    for trade in existing:
        if not inserted and trade.as_of > as_of:
            if quantity > owned + Decimal("0.0000001"):
                raise ValueError("Cannot sell more units than held on that date")
            owned -= quantity
            inserted = True
        owned += dec(trade.quantity) if trade.side == "BUY" else -dec(trade.quantity)
        if owned < -Decimal("0.0000001"):
            raise ValueError("Backdated sale would create a future short position")
    if not inserted and quantity > owned + Decimal("0.0000001"):
        raise ValueError("Cannot sell more units than held on that date")


def account_balance(db: Session, account: Account, as_of: date) -> Decimal:
    entries = db.scalars(select(CashEntry).where(
        CashEntry.account_id == account.id, CashEntry.as_of <= as_of
    )).all()
    balance = sum((dec(e.amount) for e in entries), ZERO)
    for t in _trades(db, as_of, account.id):
        consideration = dec(t.quantity) * dec(t.price)
        balance += (-consideration - dec(t.fees)) if t.side == "BUY" else (consideration - dec(t.fees))
    return balance


def balance_sheet(db: Session, as_of: date | None = None) -> dict:
    as_of = as_of or date.today()
    assets: list[dict] = []
    liabilities: list[dict] = []
    issues: list[dict] = []
    by_class: dict[str, Decimal] = defaultdict(lambda: ZERO)
    by_currency: dict[str, Decimal] = defaultdict(lambda: ZERO)

    def add(label: str, kind: str, currency: str, value: Decimal, source: str, stale_on: date | None, stale_after_days: int = 7):
        rate, rate_date = fx_to_ngn(db, currency, as_of)
        if rate is None:
            issues.append({"type": "MISSING_FX", "name": label, "currency": currency})
            return
        if rate_date and (as_of - rate_date).days > 7 and currency != "NGN":
            issues.append({"type": "STALE_FX", "name": label, "currency": currency, "date": str(rate_date)})
        translated = value * rate
        if stale_on and (as_of - stale_on).days > stale_after_days:
            issues.append({"type": "STALE_PRICE", "name": label, "date": str(stale_on)})
        item = {
            "name": label, "class": kind, "currency": currency,
            "native_value": money(value), "value_ngn": money(translated),
            "source": source, "as_of": str(stale_on or as_of),
        }
        if kind == "LIABILITY" or (kind == "CASH" and translated < 0):
            liabilities.append({**item, "value_ngn": money(abs(translated))})
        else:
            assets.append(item)
            by_class[kind] += translated
            by_currency[currency] += translated

    accounts = {a.id: a for a in db.scalars(select(Account)).all()}
    instruments = {i.id: i for i in db.scalars(select(Instrument)).all()}
    for account in accounts.values():
        bal = account_balance(db, account, as_of)
        if bal != 0:
            add(account.name, "CASH", account.currency, bal, "cash ledger", None)

    for (account_id, instrument_id), p in position_costs(db, as_of).items():
        if p["quantity"] <= 0:
            continue
        instrument = instruments[instrument_id]
        px = last_price(db, instrument.id, as_of)
        if px is None:
            issues.append({"type": "MISSING_PRICE", "name": instrument.symbol})
            continue
        value = p["quantity"] * px.close
        add(instrument.symbol, instrument.asset_class, instrument.currency, value, px.source, px.as_of)

    for item in db.scalars(select(BalanceItem).where(BalanceItem.valued_on <= as_of)).all():
        add(item.name, "LIABILITY" if item.kind == "LIABILITY" else item.category.upper(),
            item.currency, dec(item.amount), "manual other asset/liability", item.valued_on, 180)

    if not assets and not liabilities and not issues:\n        issues.append({"type": "INFO", "name": "No financial records valued yet"})\n\n    total_assets = sum((dec(r["value_ngn"]) for r in assets), ZERO)
    total_liabs = sum((dec(r["value_ngn"]) for r in liabilities), ZERO)
    worth = total_assets - total_liabs
    rate, rate_date = fx_to_ngn(db, "USD", as_of)
    return {
        "as_of": as_of.isoformat(),
        "assets_ngn": money(total_assets),
        "liabilities_ngn": money(total_liabs),
        "net_worth_ngn": money(worth),
        "net_worth_usd": money(worth / rate) if rate else None,
        "usd_ngn": money(rate) if rate else None,
        "assets": assets, "liabilities": liabilities,
        "allocation_ngn": {k: money(v) for k, v in sorted(by_class.items())},
        "currency_exposure_ngn": {k: money(v) for k, v in sorted(by_currency.items())},
        "data_issues": issues,
        "complete": bool(assets or liabilities) and not any(i["type"].startswith("MISSING") for i in issues),
        "disclosure": "Unpriced or unconverted holdings are excluded, not valued at zero. Values are not investment performance.",
    }


def holdings(db: Session, as_of: date | None = None) -> dict:
    as_of = as_of or date.today()
    accounts = {a.id: a for a in db.scalars(select(Account)).all()}
    instruments = {i.id: i for i in db.scalars(select(Instrument)).all()}
    result = []
    for (account_id, iid), p in position_costs(db, as_of).items():
        if p["quantity"] <= 0:
            continue
        ins = instruments[iid]
        px = last_price(db, iid, as_of)
        rate, rate_date = fx_to_ngn(db, ins.currency, as_of)
        value = p["quantity"] * px.close if px else None
        result.append({
            "account": accounts[account_id].name, "instrument_id": iid,
            "symbol": ins.symbol, "name": ins.name, "asset_class": ins.asset_class,
            "country": ins.country, "sector": ins.sector, "currency": ins.currency,
            "quantity": float(p["quantity"]), "cost_native": money(p["cost"]),
            "realized_pnl_native": money(p["realized"]),
            "price": float(px.close) if px else None,
            "price_as_of": str(px.as_of) if px else None,
            "value_native": money(value) if value is not None else None,
            "value_ngn": money(value * rate) if value is not None and rate else None,
            "unrealized_native": money(value - p["cost"]) if value is not None else None,
            "fx_as_of": str(rate_date) if rate else None,
            "priced": px is not None and rate is not None,
        })
    return {
        "as_of": as_of.isoformat(), "positions": result,
        "notice": "Unrealized return excludes distributions and pre-conversion FX gains. No price is fabricated.",
    }


def transfer_cash(
    db: Session, source_id: int, dest_id: int, amount: Decimal, as_of: date, note: str = ""
) -> tuple[CashEntry, CashEntry]:
    import uuid
    src, dest = db.get(Account, source_id), db.get(Account, dest_id)
    if not src or not dest or src.id == dest.id:
        raise ValueError("Transfer requires different existing accounts")
    if src.currency != dest.currency:
        raise ValueError("Cross-currency transfer requires two explicit FX conversion entries")
    if amount <= 0:
        raise ValueError("Transfer amount must be positive")
    if account_balance(db, src, as_of) < amount:
        raise ValueError("Insufficient cash on transfer date")
    key = str(uuid.uuid4())
    debit = CashEntry(account_id=src.id, as_of=as_of, kind="TRANSFER", amount=-amount,
                      transfer_group=key, note=note)
    credit = CashEntry(account_id=dest.id, as_of=as_of, kind="TRANSFER", amount=amount,
                       transfer_group=key, note=note)
    db.add_all([debit, credit])
    db.commit()
    return debit, credit
