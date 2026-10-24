"""Typed API for all fifteen wealth modules and the underlying ledger."""
from __future__ import annotations

import csv
import io
import re
import secrets
from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, File, Header, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import config
from .analytics import (
    compare_allocations, dcf, monte_carlo, net_sale_proceeds, opportunity_cost,
    rebalance, stress_test, validate_backtest,
)
from .database import get_db
from .finance import (
    account_balance, balance_sheet, dec, fx_to_ngn, holdings, money,
    transfer_cash, validate_new_trade,
)
from .intelligence import (
    MODULES, cashflow, event_report, evidence_brief, fund_overlap,
    fundamentals_report, goals_overview, journal_report, quality_report,
    risk_report, signals_report, tax_rules, wealth_health,
)
from .models import (
    Account, BalanceItem, CashEntry, CashPlan, Decision, FundConstituent,
    Fundamental, FXRate, Goal, Instrument, MarketEvent, Price, TaxRule, Trade,
)
from .security import verify_password

public = APIRouter(prefix="/api")
router = APIRouter(prefix="/api")


class Login(BaseModel):
    username: str
    password: str


@public.post("/auth/login")
def login(payload: Login, request: Request):
    config.validate_auth_config()
    if not (
        secrets.compare_digest(payload.username, config.USERNAME)
        and verify_password(payload.password, config.PASSWORD_HASH)
    ):
        raise HTTPException(401, "Incorrect credentials")
    request.session.clear()
    request.session["user"] = config.USERNAME
    request.session["csrf"] = secrets.token_urlsafe(32)
    return {"username": config.USERNAME, "csrf": request.session["csrf"]}


def require_auth(request: Request, x_csrf_token: str | None = Header(default=None)):
    if request.session.get("user") != config.USERNAME:
        raise HTTPException(401, "Authentication required")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        if not x_csrf_token or not secrets.compare_digest(x_csrf_token, request.session.get("csrf", "")):
            raise HTTPException(403, "Missing or invalid anti-CSRF token")
    return request.session["user"]


@router.get("/auth/me")
def whoami(request: Request, _: str = Depends(require_auth)):
    return {"username": config.USERNAME, "csrf": request.session["csrf"]}


@router.post("/auth/logout")
def logout(request: Request, _: str = Depends(require_auth)):
    request.session.clear()
    return {"ok": True}


# All business endpoints protected; login above is the only public mutation.
router.dependencies.append(Depends(require_auth))


def saved(db: Session, obj):
    try:
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Duplicate record or invalid reference") from exc


def existing(db: Session, model, item_id: int):
    obj = db.get(model, item_id)
    if obj is None:
        raise HTTPException(404, f"{model.__name__} {item_id} not found")
    return obj


def invalid(exc):
    raise HTTPException(422, str(exc)) from exc


Currency = str


def clean_currency(value: str) -> str:
    value = value.strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", value):
        raise ValueError("Currency must be a three-letter ISO code")
    return value


class AccountIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    currency: str = "NGN"
    kind: Literal["CASH", "BROKER"] = "BROKER"

    @field_validator("currency")
    @classmethod
    def upper(cls, value):
        return clean_currency(value)


class InstrumentIn(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=180)
    asset_class: Literal["NGX_STOCK", "US_STOCK", "ETF", "MUTUAL_FUND", "BOND", "OTHER_SECURITY"]
    currency: str = "NGN"
    exchange: str = Field(default="", max_length=40)
    country: str = Field(default="", max_length=3)
    sector: str = Field(default="", max_length=100)
    domicile: str = Field(default="", max_length=3)
    isin: str = Field(default="", max_length=20)

    @field_validator("currency")
    @classmethod
    def upper(cls, value):
        return clean_currency(value)


class PriceIn(BaseModel):
    instrument_id: int
    as_of: date
    close: Decimal = Field(gt=0)
    source: str = Field(default="manual", max_length=120)


class FXIn(BaseModel):
    base: str
    quote: str
    as_of: date
    rate: Decimal = Field(gt=0)
    source: str = Field(default="manual", max_length=120)

    @field_validator("base", "quote")
    @classmethod
    def upper(cls, value):
        return clean_currency(value)


class CashIn(BaseModel):
    account_id: int
    as_of: date
    kind: Literal["DEPOSIT", "WITHDRAWAL", "DIVIDEND", "INTEREST", "EXPENSE", "FEE", "ADJUSTMENT"]
    amount: Decimal
    note: str = Field(default="", max_length=300)


class TransferIn(BaseModel):
    from_account_id: int
    to_account_id: int
    as_of: date
    amount: Decimal = Field(gt=0)
    note: str = Field(default="", max_length=300)


class TradeIn(BaseModel):
    account_id: int
    instrument_id: int
    as_of: date
    side: Literal["BUY", "SELL"]
    quantity: Decimal = Field(gt=0)
    price: Decimal = Field(ge=0)
    fees: Decimal = Field(default=Decimal("0"), ge=0)
    notes: str = Field(default="", max_length=500)
    external_ref: str | None = Field(default=None, max_length=100)


class BalanceItemIn(BaseModel):
    name: str = Field(min_length=1, max_length=140)
    kind: Literal["ASSET", "LIABILITY"]
    category: str = Field(default="other", max_length=60)
    currency: str = "NGN"
    amount: Decimal = Field(ge=0)
    valued_on: date
    notes: str = Field(default="", max_length=500)

    @field_validator("currency")
    @classmethod
    def upper(cls, value):
        return clean_currency(value)


class GoalIn(BaseModel):
    name: str = Field(min_length=1, max_length=140)
    target_today_ngn: Decimal = Field(gt=0)
    due_date: date
    monthly_contribution_ngn: Decimal = Field(default=Decimal("0"), ge=0)
    inflation_pct: Decimal = Field(default=Decimal("0"), gt=-100, lt=1000)
    expected_return_pct: Decimal = Field(default=Decimal("0"), gt=-100, lt=1000)
    priority: int = Field(default=3, ge=1, le=5)


class CashPlanIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    direction: Literal["IN", "OUT"]
    amount_ngn: Decimal = Field(ge=0)
    frequency: Literal["ONCE", "MONTHLY", "QUARTERLY", "YEARLY"]
    start_date: date
    end_date: date | None = None


class FundamentalIn(BaseModel):
    instrument_id: int
    fiscal_year: int = Field(ge=1900, le=2100)
    revenue: Decimal | None = None
    net_income: Decimal | None = None
    free_cash_flow: Decimal | None = None
    total_debt: Decimal | None = None
    cash: Decimal | None = None
    shares_outstanding: Decimal | None = Field(default=None, gt=0)
    source_url: str = Field(default="", max_length=1000)


class ConstituentIn(BaseModel):
    fund_id: int
    constituent_id: int
    as_of: date
    weight_pct: Decimal = Field(ge=0, le=100)
    source: str = Field(default="manual", max_length=250)


class EventIn(BaseModel):
    instrument_id: int
    occurred_on: date
    event_type: str = Field(min_length=1, max_length=50)
    headline: str = Field(min_length=1, max_length=250)
    observed_change: str = Field(default="", max_length=5000)
    source_url: str = Field(min_length=1, max_length=1000)
    thesis_impact: Literal["POSITIVE", "NEGATIVE", "NEUTRAL", "REVIEW"] = "REVIEW"
    confidence: Literal["UNVERIFIED", "SOURCE_CHECKED"] = "UNVERIFIED"


class DecisionIn(BaseModel):
    decided_on: date
    instrument_id: int | None = None
    action: Literal["BUY", "SELL", "HOLD", "AVOID"]
    thesis: str = Field(min_length=1, max_length=5000)
    invalidation: str = Field(default="", max_length=3000)
    planned_horizon_months: int = Field(default=12, ge=1, le=600)
    expected_return_pct: Decimal | None = None


class DecisionReviewIn(BaseModel):
    actual_return_pct: Decimal
    benchmark_return_pct: Decimal | None = None
    process_rating: Literal["GOOD", "POOR"]
    mistake_tags: str = Field(default="", max_length=250)
    notes: str = Field(default="", max_length=3000)


class TaxRuleIn(BaseModel):
    asset_class: str = Field(min_length=1, max_length=24)
    sale_tax_pct: Decimal = Field(ge=0, le=100)
    sale_tax_basis: Literal["GAIN", "PROCEEDS"]
    exit_fee_pct: Decimal = Field(ge=0, le=100)
    effective_on: date
    notes: str = Field(default="", max_length=5000)


@router.get("/modules")
def modules():
    return {"modules": [
        {"id": slug, "name": title, "category": category, "maturity": maturity, "description": description}
        for slug, title, category, maturity, description in MODULES
    ]}


@router.get("/accounts")
def get_accounts(db: Session = Depends(get_db)):
    return [{"id": a.id, "name": a.name, "currency": a.currency, "kind": a.kind,
             "balance": money(account_balance(db, a, date.today()))}
            for a in db.scalars(select(Account).order_by(Account.name)).all()]


@router.post("/accounts", status_code=201)
def create_account(payload: AccountIn, db: Session = Depends(get_db)):
    a = saved(db, Account(**payload.model_dump()))
    return {"id": a.id, "name": a.name}


@router.get("/instruments")
def get_instruments(db: Session = Depends(get_db)):
    return [{"id": i.id, "symbol": i.symbol, "name": i.name, "asset_class": i.asset_class,
             "currency": i.currency, "exchange": i.exchange, "sector": i.sector,
             "country": i.country, "domicile": i.domicile, "isin": i.isin}
            for i in db.scalars(select(Instrument).order_by(Instrument.symbol)).all()]


@router.post("/instruments", status_code=201)
def create_instrument(payload: InstrumentIn, db: Session = Depends(get_db)):
    data = payload.model_dump()
    data["symbol"] = data["symbol"].strip().upper()
    data["exchange"] = data["exchange"].strip().upper()
    data["country"] = data["country"].strip().upper()
    data["domicile"] = data["domicile"].strip().upper()
    i = saved(db, Instrument(**data))
    return {"id": i.id, "symbol": i.symbol}


@router.post("/prices")
def record_price(payload: PriceIn, db: Session = Depends(get_db)):
    existing(db, Instrument, payload.instrument_id)
    if payload.as_of > date.today():
        raise HTTPException(422, "Cannot record future market close")
    row = db.scalar(select(Price).where(
        Price.instrument_id == payload.instrument_id, Price.as_of == payload.as_of
    ))
    if row is None:
        row = Price(**payload.model_dump())
    else:
        row.close = payload.close
        row.source = payload.source
    saved(db, row)
    return {"id": row.id, "updated": True}


@router.post("/fx")
def record_fx(payload: FXIn, db: Session = Depends(get_db)):
    if payload.base == payload.quote or payload.as_of > date.today():
        raise HTTPException(422, "FX rate must have distinct currencies and a valid past date")
    row = db.scalar(select(FXRate).where(
        FXRate.base == payload.base, FXRate.quote == payload.quote, FXRate.as_of == payload.as_of
    ))
    if row is None:
        row = FXRate(**payload.model_dump())
    else:
        row.rate, row.source = payload.rate, payload.source
    saved(db, row)
    return {"id": row.id}


@router.post("/cash")
def create_cash(payload: CashIn, db: Session = Depends(get_db)):
    account = existing(db, Account, payload.account_id)
    if payload.as_of > date.today() or payload.amount == 0:
        raise HTTPException(422, "Cash entry must be nonzero and not future-dated")
    kind_sign = {
        "DEPOSIT": 1, "DIVIDEND": 1, "INTEREST": 1,
        "WITHDRAWAL": -1, "EXPENSE": -1, "FEE": -1,
    }
    if payload.kind in kind_sign and payload.amount * kind_sign[payload.kind] <= 0:
        raise HTTPException(422, f"{payload.kind} must have the correct positive/negative sign")
    if payload.amount < 0 and account_balance(db, account, payload.as_of) + payload.amount < 0:
        raise HTTPException(422, "Entry would overdraw cash on its effective date")
    row = saved(db, CashEntry(**payload.model_dump()))
    return {"id": row.id}


@router.post("/transfers")
def transfer(payload: TransferIn, db: Session = Depends(get_db)):
    if payload.as_of > date.today():
        raise HTTPException(422, "Future transfer dates are not supported")
    try:
        a, b = transfer_cash(db, payload.from_account_id, payload.to_account_id,
                             payload.amount, payload.as_of, payload.note)
    except ValueError as exc:
        invalid(exc)
    return {"debit_id": a.id, "credit_id": b.id, "balanced": True}


@router.post("/trades", status_code=201)
def create_trade(payload: TradeIn, db: Session = Depends(get_db)):
    account = existing(db, Account, payload.account_id)
    ins = existing(db, Instrument, payload.instrument_id)
    if account.currency != ins.currency:
        raise HTTPException(422, "Trade account and instrument must use the same currency")
    if payload.as_of > date.today():
        raise HTTPException(422, "Future-dated trades not supported")
    if payload.side == "BUY" and account_balance(db, account, payload.as_of) < payload.quantity * payload.price + payload.fees:
        raise HTTPException(422, "Insufficient cash for trade on selected date")
    try:
        validate_new_trade(db, payload.account_id, payload.instrument_id,
                           payload.as_of, payload.side, payload.quantity)
    except ValueError as exc:
        invalid(exc)
    t = saved(db, Trade(**payload.model_dump()))
    return {"id": t.id, "account_id": t.account_id, "instrument_id": t.instrument_id}


@router.get("/trades")
def list_trades(db: Session = Depends(get_db)):
    return [{"id": t.id, "as_of": str(t.as_of), "side": t.side, "quantity": float(t.quantity),
             "price": float(t.price), "fees": float(t.fees), "account_id": t.account_id,
             "instrument_id": t.instrument_id}
            for t in db.scalars(select(Trade).order_by(Trade.as_of.desc())).all()]


@router.post("/balance-items")
def add_balance_item(payload: BalanceItemIn, db: Session = Depends(get_db)):
    row = saved(db, BalanceItem(**payload.model_dump()))
    return {"id": row.id}


@router.get("/portfolio")
def portfolio(db: Session = Depends(get_db)):
    return balance_sheet(db)


@router.get("/holdings")
def get_holdings(db: Session = Depends(get_db)):
    return holdings(db)


@router.get("/quality")
def quality(db: Session = Depends(get_db)):
    return quality_report(db)


@router.get("/health-score")
def health_score(db: Session = Depends(get_db)):
    return wealth_health(db)


@router.post("/goals", status_code=201)
def create_goal(payload: GoalIn, db: Session = Depends(get_db)):
    g = saved(db, Goal(**payload.model_dump()))
    return {"id": g.id}


@router.get("/goals")
def goals(db: Session = Depends(get_db)):
    return {"goals": goals_overview(db)}


@router.post("/cash-plans", status_code=201)
def create_cash_plan(payload: CashPlanIn, db: Session = Depends(get_db)):
    if payload.end_date and payload.end_date < payload.start_date:
        raise HTTPException(422, "End date must follow start date")
    p = saved(db, CashPlan(**payload.model_dump()))
    return {"id": p.id}


@router.get("/liquidity")
def liquidity(horizon: int = 12, reserve_months: int = 6, db: Session = Depends(get_db)):
    try:
        return cashflow(db, horizon, reserve_months)
    except ValueError as exc:
        invalid(exc)


@router.get("/risk")
def risk(db: Session = Depends(get_db)):
    return risk_report(db)


@router.post("/fundamentals")
def add_fundamentals(payload: FundamentalIn, db: Session = Depends(get_db)):
    existing(db, Instrument, payload.instrument_id)
    row = saved(db, Fundamental(**payload.model_dump()))
    return {"id": row.id}


@router.get("/fundamentals")
def fundamentals(db: Session = Depends(get_db)):
    return {"records": fundamentals_report(db)}


@router.post("/constituents")
def add_constituent(payload: ConstituentIn, db: Session = Depends(get_db)):
    fund = existing(db, Instrument, payload.fund_id)
    existing(db, Instrument, payload.constituent_id)
    if fund.id == payload.constituent_id or fund.asset_class not in {"ETF", "MUTUAL_FUND"}:
        raise HTTPException(422, "Parent must be a fund and cannot own itself")
    row = saved(db, FundConstituent(**payload.model_dump()))
    return {"id": row.id}


@router.get("/lookthrough")
def lookthrough(db: Session = Depends(get_db)):
    return fund_overlap(db)


class DCFIn(BaseModel):
    base_free_cash_flow: float
    growth_pct: float
    discount_pct: float
    terminal_growth_pct: float
    years: int = Field(ge=1, le=20)
    net_debt: float = 0
    shares_outstanding: float = Field(gt=0)


@router.post("/research/dcf")
def valuation(payload: DCFIn):
    try:
        return dcf(payload.base_free_cash_flow, payload.growth_pct, payload.discount_pct,
                   payload.terminal_growth_pct, payload.years, payload.net_debt, payload.shares_outstanding)
    except (ValueError, OverflowError) as exc:
        invalid(exc)


@router.get("/signals")
def signals(lookback: int = 20, db: Session = Depends(get_db)):
    try:
        return signals_report(db, lookback)
    except ValueError as exc:
        invalid(exc)


@router.post("/events", status_code=201)
def add_event(payload: EventIn, db: Session = Depends(get_db)):
    existing(db, Instrument, payload.instrument_id)
    if not payload.source_url.startswith(("https://", "http://")):
        raise HTTPException(422, "Event must contain a source link")
    row = saved(db, MarketEvent(**payload.model_dump()))
    return {"id": row.id}


@router.get("/events")
def events(db: Session = Depends(get_db)):
    return event_report(db)


@router.post("/tax-rules")
def create_tax_rule(payload: TaxRuleIn, db: Session = Depends(get_db)):
    row = db.scalar(select(TaxRule).where(TaxRule.asset_class == payload.asset_class))
    if row is None:
        row = TaxRule(**payload.model_dump())
    else:
        for key, value in payload.model_dump().items():
            setattr(row, key, value)
    saved(db, row)
    return {"id": row.id}


@router.get("/tax-rules")
def get_tax_rules(db: Session = Depends(get_db)):
    return {"rules": tax_rules(db)}


class NetReturnIn(BaseModel):
    gross_value: float = Field(ge=0)
    cost_basis: float = Field(ge=0)
    tax_pct: float = Field(ge=0, le=100)
    fee_pct: float = Field(ge=0, le=100)
    tax_basis: Literal["GAIN", "PROCEEDS"] = "GAIN"


@router.post("/net-return")
def net_return(payload: NetReturnIn):
    try:
        return net_sale_proceeds(payload.gross_value, payload.cost_basis,
                                 payload.tax_pct, payload.fee_pct, payload.tax_basis)
    except ValueError as exc:
        invalid(exc)


class ForecastIn(BaseModel):
    initial_ngn: float = Field(ge=0)
    monthly_ngn: float = Field(ge=0)
    years: int = Field(ge=1, le=60)
    return_pct: float = Field(gt=-100, lt=1000)
    volatility_pct: float = Field(ge=0, le=200)
    goal_ngn: float = Field(ge=0)
    inflation_pct: float = Field(default=0, gt=-100, lt=1000)


@router.post("/forecast")
def forecast(payload: ForecastIn):
    try:
        return monte_carlo(payload.initial_ngn, payload.monthly_ngn, payload.years,
                           payload.return_pct, payload.volatility_pct, payload.goal_ngn,
                           payload.inflation_pct)
    except ValueError as exc:
        invalid(exc)


class AllocateIn(BaseModel):
    candidates: dict[str, dict[str, float]]
    returns_pct: dict[str, float]
    volatility_pct: dict[str, float]
    initial_ngn: float = Field(ge=0)
    monthly_ngn: float = Field(ge=0)
    goal_ngn: float = Field(gt=0)
    years: int = Field(ge=1, le=40)
    min_cash_pct: float = Field(default=0, ge=0, le=100)


@router.post("/allocation/compare")
def allocate(payload: AllocateIn):
    try:
        return compare_allocations(payload.candidates, payload.returns_pct, payload.volatility_pct,
                                   payload.initial_ngn, payload.monthly_ngn, payload.goal_ngn,
                                   payload.years, payload.min_cash_pct)
    except (ValueError, OverflowError) as exc:
        invalid(exc)


@router.post("/decisions", status_code=201)
def add_decision(payload: DecisionIn, db: Session = Depends(get_db)):
    if payload.instrument_id is not None:
        existing(db, Instrument, payload.instrument_id)
    row = saved(db, Decision(**payload.model_dump()))
    return {"id": row.id}


@router.post("/decisions/{decision_id}/review")
def review_decision(decision_id: int, payload: DecisionReviewIn, db: Session = Depends(get_db)):
    row = existing(db, Decision, decision_id)
    row.reviewed_on = date.today()
    for k, v in payload.model_dump().items():
        setattr(row, k, v)
    saved(db, row)
    return {"id": row.id, "reviewed": True}


@router.get("/decisions")
def decisions(db: Session = Depends(get_db)):
    return journal_report(db)


class RebalanceIn(BaseModel):
    targets_pct: dict[str, float]
    contribution_ngn: float = Field(ge=0)


@router.post("/rebalance")
def rebalancer(payload: RebalanceIn, db: Session = Depends(get_db)):
    current = balance_sheet(db)["allocation_ngn"]
    if not current:
        raise HTTPException(422, "Record priced assets before planning contributions")
    try:
        return rebalance(current, payload.targets_pct, payload.contribution_ngn)
    except ValueError as exc:
        invalid(exc)


class StressIn(BaseModel):
    shocks_pct: dict[str, float]
    emergency_expense_ngn: float = Field(default=0, ge=0)
    monthly_income_loss_ngn: float = Field(default=0, ge=0)
    income_loss_months: int = Field(default=0, ge=0, le=60)


@router.post("/twin/stress")
def twin(payload: StressIn, db: Session = Depends(get_db)):
    book = balance_sheet(db)
    try:
        return stress_test(book["allocation_ngn"], payload.shocks_pct,
                           book["liabilities_ngn"], payload.emergency_expense_ngn,
                           payload.monthly_income_loss_ngn, payload.income_loss_months)
    except ValueError as exc:
        invalid(exc)


class OpportunityIn(BaseModel):
    amount_ngn: float = Field(ge=0)
    years: float = Field(ge=0, le=80)
    assumed_return_pct: float = Field(gt=-100, lt=1000)
    inflation_pct: float = Field(default=0, gt=-100, lt=1000)
    replacement_monthly_ngn: float = Field(default=0, ge=0)


@router.post("/opportunity")
def opportunity(payload: OpportunityIn):
    try:
        return opportunity_cost(payload.amount_ngn, payload.years,
                                payload.assumed_return_pct, payload.inflation_pct,
                                payload.replacement_monthly_ngn)
    except ValueError as exc:
        invalid(exc)


@router.get("/analyst/brief")
def analyst(db: Session = Depends(get_db)):
    return evidence_brief(db)


class BacktestIn(BaseModel):
    strategy_pct: list[float] = Field(min_length=12, max_length=5000)
    benchmark_pct: list[float] = Field(min_length=12, max_length=5000)
    fee_pct: float = Field(default=0, ge=0, lt=100)
    train_fraction: float = Field(default=.7, ge=.5, le=.9)


@router.post("/backtest")
def backtest(payload: BacktestIn):
    try:
        return validate_backtest(payload.strategy_pct, payload.benchmark_pct,
                                 payload.fee_pct, payload.train_fraction)
    except ValueError as exc:
        invalid(exc)


@router.post("/import/prices")
async def import_prices(upload: UploadFile = File(...), db: Session = Depends(get_db)):
    raw = await upload.read(2_000_001)
    if len(raw) > 2_000_000:
        raise HTTPException(413, "CSV must be 2 MB or smaller")
    try:
        text = raw.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames or not {"symbol", "exchange", "date", "close"}.issubset(reader.fieldnames):
            raise ValueError("CSV headers: symbol,exchange,date,close[,source]")
        instruments = {(i.symbol, i.exchange): i.id for i in db.scalars(select(Instrument)).all()}
        validated = []
        for index, row in enumerate(reader, 2):
            if index > 5001:
                raise ValueError("Maximum 5000 quote rows per import")
            key = (row["symbol"].strip().upper(), row["exchange"].strip().upper())
            if key not in instruments:
                raise ValueError(f"Row {index}: unknown instrument {key}")
            day = date.fromisoformat(row["date"].strip())
            close = dec(row["close"])
            if day > date.today() or close <= 0:
                raise ValueError(f"Row {index}: future date or nonpositive close")
            validated.append((instruments[key], day, close, (row.get("source") or "csv")[:120]))
    except (ValueError, UnicodeError, KeyError) as exc:
        raise HTTPException(422, str(exc)) from exc
    for iid, day, close, source in validated:
        existing_row = db.scalar(select(Price).where(
            Price.instrument_id == iid, Price.as_of == day
        ))
        if existing_row:
            existing_row.close, existing_row.source = close, source
        else:
            db.add(Price(instrument_id=iid, as_of=day, close=close, source=source))
    db.commit()
    return {"imported": len(validated), "deduplication": "instrument+date upsert"}


# ML experiments are deliberately stateless; no data-mining job runs implicitly.
class MLEvaluateIn(BaseModel):
    feature_names: list[str] = Field(min_length=1, max_length=30)
    dates: list[date] = Field(min_length=100, max_length=30000)
    features: list[list[float]] = Field(min_length=100, max_length=30000)
    labels: list[int] = Field(min_length=100, max_length=30000)
    label_horizon: int = Field(default=5, ge=1, le=60)
    holdout_fraction: float = Field(default=.25, ge=.15, le=.4)


@router.post("/ml/evaluate")
def ml_evaluate(payload: MLEvaluateIn):
    from .ml import evaluate_classifier
    try:
        return evaluate_classifier(
            payload.feature_names, payload.dates, payload.features, payload.labels,
            payload.label_horizon, payload.holdout_fraction
        )
    except (ValueError, FloatingPointError) as exc:
        invalid(exc)


class AnalystQuestionIn(BaseModel):
    question: str = Field(min_length=1, max_length=400)
    consent_to_external_processing: bool


@router.post("/analyst/ask")
def ask_analyst(payload: AnalystQuestionIn, db: Session = Depends(get_db)):
    from .assistant import AnalystProviderError, generate_analysis
    evidence = evidence_brief(db)
    try:
        return generate_analysis(
            payload.question, evidence, payload.consent_to_external_processing
        )
    except ValueError as exc:
        invalid(exc)
    except AnalystProviderError as exc:
        raise HTTPException(503, str(exc)) from exc


class SyncUSPricesIn(BaseModel):
    instrument_id: int = Field(ge=1)


@router.post("/providers/us-daily-sync")
def sync_us_daily(payload: SyncUSPricesIn, db: Session = Depends(get_db)):
    from .marketdata import MarketFeedError, sync_us_instrument
    try:
        return sync_us_instrument(db, payload.instrument_id)
    except ValueError as exc:
        invalid(exc)
    except MarketFeedError as exc:
        raise HTTPException(503, str(exc)) from exc
