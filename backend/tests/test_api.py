"""Integration tests using a fresh in-memory SQLite database per test."""
import os
os.environ["WEALTH_SESSION_SECRET"] = "test-only-session-key-longer-than-32-characters"
os.environ["WEALTH_USER"] = "owner"
from app.security import password_hash
os.environ["WEALTH_PASSWORD_HASH"] = password_hash("correct-horse-battery-staple")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.database import Base, get_db
from app import models
from app.main import app


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    def session():
        with Session(engine) as s:
            yield s
    app.dependency_overrides[get_db] = session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    engine.dispose()


def auth(c):
    r=c.post("/api/auth/login",json={"username":"owner","password":"correct-horse-battery-staple"})
    assert r.status_code == 200, r.text
    return {"X-CSRF-Token":r.json()["csrf"]}


def post(c,path,payload,headers):
    r=c.post("/api"+path,json=payload,headers=headers)
    assert r.status_code in (200,201), (r.status_code,r.text)
    return r.json()


def test_authentication_and_csrf(client):
    assert client.get("/api/portfolio").status_code == 401
    assert client.post("/api/auth/login",json={"username":"owner","password":"bad"}).status_code == 401
    h=auth(client)
    assert client.get("/api/portfolio").status_code == 200
    assert client.post("/api/accounts",json={"name":"Unsafe","currency":"NGN"}).status_code == 403
    assert post(client,"/accounts",{"name":"Safe","currency":"NGN"},h)["id"] > 0
    assert len(client.get("/api/modules").json()["modules"]) == 15


def test_trade_cash_balances_and_oversell(client):
    h=auth(client)
    aid=post(client,"/accounts",{"name":"Broker","currency":"NGN"},h)["id"]
    sid=post(client,"/instruments",{
        "symbol":"DEMO","name":"Example PLC","asset_class":"NGX_STOCK",
        "currency":"NGN","exchange":"XNSA",
    },h)["id"]
    post(client,"/cash",{"account_id":aid,"as_of":"2026-01-01",
         "kind":"DEPOSIT","amount":2000},h)
    post(client,"/trades",{"account_id":aid,"instrument_id":sid,
         "as_of":"2026-01-02","side":"BUY","quantity":10,"price":50,"fees":5},h)
    post(client,"/prices",{"instrument_id":sid,"as_of":"2026-01-03",
         "close":60,"source":"verified-fixture"},h)
    portfolio=client.get("/api/portfolio").json()
    assert portfolio["assets_ngn"] == pytest.approx(2095)
    assert client.get("/api/holdings").json()["positions"][0]["cost_native"] == pytest.approx(505)
    bad=client.post("/api/trades",headers=h,json={"account_id":aid,"instrument_id":sid,
         "as_of":"2026-01-04","side":"SELL","quantity":20,"price":60,"fees":0})
    assert bad.status_code == 422


def test_no_double_counting_transfers(client):
    h=auth(client)
    a=post(client,"/accounts",{"name":"A","currency":"NGN"},h)["id"]
    b=post(client,"/accounts",{"name":"B","currency":"NGN"},h)["id"]
    post(client,"/cash",{"account_id":a,"as_of":"2026-01-01","kind":"DEPOSIT","amount":1000},h)
    before=client.get("/api/portfolio").json()["assets_ngn"]
    post(client,"/transfers",{"from_account_id":a,"to_account_id":b,
         "amount":250,"as_of":"2026-01-02"},h)
    assert before == client.get("/api/portfolio").json()["assets_ngn"] == 1000


def test_fx_missing_then_converted(client):
    h=auth(client)
    a=post(client,"/accounts",{"name":"Dollar account","currency":"USD"},h)["id"]
    post(client,"/cash",{"account_id":a,"as_of":"2026-01-01","kind":"DEPOSIT","amount":100},h)
    report=client.get("/api/portfolio").json()
    assert report["assets_ngn"] == 0 and not report["complete"]
    assert any(i["type"]=="MISSING_FX" for i in report["data_issues"])
    post(client,"/fx",{"base":"USD","quote":"NGN","as_of":"2026-01-01","rate":1500},h)
    assert client.get("/api/portfolio").json()["assets_ngn"] == 150000


def test_goal_cashflow_and_decision_tools(client):
    h=auth(client)
    post(client,"/goals",{"name":"Freedom","target_today_ngn":10000000,
         "due_date":"2036-12-31","monthly_contribution_ngn":100000,
         "inflation_pct":8,"expected_return_pct":10,"priority":1},h)
    assert client.get("/api/goals").json()["goals"][0]["target_future_ngn"] > 10000000
    post(client,"/cash-plans",{"name":"Rent","direction":"OUT",
         "amount_ngn":100000,"frequency":"MONTHLY","start_date":"2026-01-01"},h)
    assert len(client.get("/api/liquidity").json()["months"]) == 12
    assert "recommended_reviews" in client.get("/api/analyst/brief").json()
    f=post(client,"/forecast",{"initial_ngn":100000,"monthly_ngn":1000,
         "years":5,"return_pct":8,"volatility_pct":15,"goal_ngn":200000},h)
    assert 0 <= f["goal_probability"] <= 1
    b=post(client,"/backtest",{"strategy_pct":[1]*12,
         "benchmark_pct":[.5]*12,"fee_pct":.1},h)
    assert "holdout" in b["segments"]
