"""Application bootstrap: protected API, signed session cookies, static SPA."""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from . import config
from .api import public, router
from .database import create_schema

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.validate_auth_config()
    create_schema()
    yield


app = FastAPI(
    title="Wealth Manager — Personal Wealth Intelligence",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url="/api/openapi.json",
)
app.add_middleware(
    SessionMiddleware,
    secret_key=config.SESSION_SECRET or "unconfigured-do-not-start",
    same_site="lax",
    https_only=config.SECURE_COOKIE,
    session_cookie="wm_session",
    max_age=60 * 60 * 8,
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        "connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'self'"
    )
    response.headers["Cache-Control"] = "no-store" if request.url.path.startswith("/api/") else "no-cache"
    return response


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "wealth-manager"}


app.include_router(public)
app.include_router(router)
app.mount("/", StaticFiles(directory=str(FRONTEND), html=True), name="frontend")
