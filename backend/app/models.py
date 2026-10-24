"""Canonical financial records. Financial amounts use Decimal/Numeric, never Float.

Ledger rules: deposits/withdrawals are cash entries; security trades change
account cash via signed trade consideration. Portfolio net worth counts cash
plus *current* investment market values without double-counting capital.
"""
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base

D = Numeric(24, 8, asdecimal=True)


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Account(Base):
    __tablename__ = "accounts"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), default="BROKER", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Instrument(Base):
    __tablename__ = "instruments"
    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    asset_class: Mapped[str] = mapped_column(String(24), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    exchange: Mapped[str] = mapped_column(String(40), default="")
    country: Mapped[str] = mapped_column(String(3), default="")
    sector: Mapped[str] = mapped_column(String(100), default="")
    domicile: Mapped[str] = mapped_column(String(3), default="")
    isin: Mapped[str] = mapped_column(String(20), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    __table_args__ = (UniqueConstraint("symbol", "exchange", name="uq_symbol_exchange"),)


class Price(Base):
    __tablename__ = "prices"
    id: Mapped[int] = mapped_column(primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"), index=True)
    as_of: Mapped[date] = mapped_column(Date, nullable=False)
    close: Mapped[Decimal] = mapped_column(D, nullable=False)
    source: Mapped[str] = mapped_column(String(120), default="manual", nullable=False)
    __table_args__ = (UniqueConstraint("instrument_id", "as_of"), CheckConstraint("close > 0"),)


class FXRate(Base):
    __tablename__ = "fx_rates"
    id: Mapped[int] = mapped_column(primary_key=True)
    base: Mapped[str] = mapped_column(String(3), nullable=False)
    quote: Mapped[str] = mapped_column(String(3), nullable=False)
    as_of: Mapped[date] = mapped_column(Date, nullable=False)
    rate: Mapped[Decimal] = mapped_column(D, nullable=False)
    source: Mapped[str] = mapped_column(String(120), default="manual")
    __table_args__ = (UniqueConstraint("base", "quote", "as_of"), CheckConstraint("rate > 0"),)


class Trade(Base):
    __tablename__ = "trades"
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"), index=True)
    as_of: Mapped[date] = mapped_column(Date, nullable=False)
    side: Mapped[str] = mapped_column(String(4), nullable=False)  # BUY | SELL
    quantity: Mapped[Decimal] = mapped_column(D, nullable=False)
    price: Mapped[Decimal] = mapped_column(D, nullable=False)
    fees: Mapped[Decimal] = mapped_column(D, default=Decimal("0"), nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="")
    external_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    __table_args__ = (
        CheckConstraint("quantity > 0"), CheckConstraint("price >= 0"),
        CheckConstraint("fees >= 0"), CheckConstraint("side IN ('BUY','SELL')"),
        UniqueConstraint("account_id", "external_ref", name="uq_trade_external_ref"),
    )


class CashEntry(Base):
    __tablename__ = "cash_entries"
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    as_of: Mapped[date] = mapped_column(Date, nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    amount: Mapped[Decimal] = mapped_column(D, nullable=False)  # signed
    note: Mapped[str] = mapped_column(String(300), default="")
    transfer_group: Mapped[str | None] = mapped_column(String(40), nullable=True)


class BalanceItem(Base):
    __tablename__ = "balance_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(140), nullable=False)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)  # ASSET | LIABILITY
    category: Mapped[str] = mapped_column(String(60), default="other")
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    amount: Mapped[Decimal] = mapped_column(D, nullable=False)
    valued_on: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str] = mapped_column(String(500), default="")
    __table_args__ = (CheckConstraint("amount >= 0"), CheckConstraint("kind IN ('ASSET','LIABILITY')"),)


class Goal(Base):
    __tablename__ = "goals"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(140), nullable=False)
    target_today_ngn: Mapped[Decimal] = mapped_column(D, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    monthly_contribution_ngn: Mapped[Decimal] = mapped_column(D, default=Decimal("0"))
    inflation_pct: Mapped[Decimal] = mapped_column(D, default=Decimal("0"))
    expected_return_pct: Mapped[Decimal] = mapped_column(D, default=Decimal("0"))
    priority: Mapped[int] = mapped_column(Integer, default=3)


class CashPlan(Base):
    __tablename__ = "cash_plans"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)  # IN | OUT
    amount_ngn: Mapped[Decimal] = mapped_column(D, nullable=False)
    frequency: Mapped[str] = mapped_column(String(12), nullable=False)  # ONCE | MONTHLY | QUARTERLY | YEARLY
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    __table_args__ = (CheckConstraint("amount_ngn >= 0"),)


class Fundamental(Base):
    __tablename__ = "fundamentals"
    id: Mapped[int] = mapped_column(primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"), index=True)
    fiscal_year: Mapped[int] = mapped_column(Integer)
    revenue: Mapped[Decimal | None] = mapped_column(D, nullable=True)
    net_income: Mapped[Decimal | None] = mapped_column(D, nullable=True)
    free_cash_flow: Mapped[Decimal | None] = mapped_column(D, nullable=True)
    total_debt: Mapped[Decimal | None] = mapped_column(D, nullable=True)
    cash: Mapped[Decimal | None] = mapped_column(D, nullable=True)
    shares_outstanding: Mapped[Decimal | None] = mapped_column(D, nullable=True)
    source_url: Mapped[str] = mapped_column(String(1000), default="")
    __table_args__ = (UniqueConstraint("instrument_id", "fiscal_year"),)


class FundConstituent(Base):
    __tablename__ = "fund_constituents"
    id: Mapped[int] = mapped_column(primary_key=True)
    fund_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"), index=True)
    constituent_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"), index=True)
    as_of: Mapped[date] = mapped_column(Date)
    weight_pct: Mapped[Decimal] = mapped_column(D)
    source: Mapped[str] = mapped_column(String(250), default="manual")
    __table_args__ = (UniqueConstraint("fund_id", "constituent_id", "as_of"),)


class MarketEvent(Base):
    __tablename__ = "market_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"), index=True)
    occurred_on: Mapped[date] = mapped_column(Date)
    event_type: Mapped[str] = mapped_column(String(50))
    headline: Mapped[str] = mapped_column(String(250))
    observed_change: Mapped[str] = mapped_column(Text, default="")
    source_url: Mapped[str] = mapped_column(String(1000))
    thesis_impact: Mapped[str] = mapped_column(String(24), default="REVIEW")
    confidence: Mapped[str] = mapped_column(String(16), default="UNVERIFIED")


class Decision(Base):
    __tablename__ = "decisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    decided_on: Mapped[date] = mapped_column(Date)
    instrument_id: Mapped[int | None] = mapped_column(ForeignKey("instruments.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(12))
    thesis: Mapped[str] = mapped_column(Text)
    invalidation: Mapped[str] = mapped_column(Text, default="")
    planned_horizon_months: Mapped[int] = mapped_column(Integer, default=12)
    expected_return_pct: Mapped[Decimal | None] = mapped_column(D, nullable=True)
    reviewed_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_return_pct: Mapped[Decimal | None] = mapped_column(D, nullable=True)
    benchmark_return_pct: Mapped[Decimal | None] = mapped_column(D, nullable=True)
    process_rating: Mapped[str | None] = mapped_column(String(12), nullable=True)
    mistake_tags: Mapped[str] = mapped_column(String(250), default="")
    notes: Mapped[str] = mapped_column(Text, default="")


class TaxRule(Base):
    __tablename__ = "tax_rules"
    id: Mapped[int] = mapped_column(primary_key=True)
    asset_class: Mapped[str] = mapped_column(String(24), unique=True)
    sale_tax_pct: Mapped[Decimal] = mapped_column(D, default=Decimal("0"))
    sale_tax_basis: Mapped[str] = mapped_column(String(10), default="GAIN")
    exit_fee_pct: Mapped[Decimal] = mapped_column(D, default=Decimal("0"))
    effective_on: Mapped[date] = mapped_column(Date)
    notes: Mapped[str] = mapped_column(Text, default="")
