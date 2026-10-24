"""Explicit configuration; never ship default authentication secrets."""
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

DATABASE_URL = os.getenv("WEALTH_DATABASE_URL", f"sqlite:///{ROOT / 'data' / 'wealth.db'}")
SESSION_SECRET = os.getenv("WEALTH_SESSION_SECRET", "")
USERNAME = os.getenv("WEALTH_USER", "owner")
PASSWORD_HASH = os.getenv("WEALTH_PASSWORD_HASH", "")
SECURE_COOKIE = os.getenv("WEALTH_SECURE_COOKIE", "false").lower() == "true"


def validate_auth_config() -> None:
    if len(SESSION_SECRET) < 32 or not PASSWORD_HASH:
        raise RuntimeError(
            "Authentication not configured. Set WEALTH_SESSION_SECRET (32+ characters) "
            "and WEALTH_PASSWORD_HASH in backend/.env; see README."
        )
