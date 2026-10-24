"""Local single-owner authentication with PBKDF2 and constant-time checks.

The app intentionally does not implement public sign-up or social auth.
Secrets belong in .env, never in source control.
"""
import base64
import hashlib
import hmac
import os
import sys


def password_hash(password: str, iterations: int = 390_000) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return "pbkdf2_sha256$%d$%s$%s" % (
        iterations,
        base64.urlsafe_b64encode(salt).decode(),
        base64.urlsafe_b64encode(digest).decode(),
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, rounds, salt, expected = encoded.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        rounds_int = int(rounds)
        if not 100_000 <= rounds_int <= 2_000_000:
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), base64.urlsafe_b64decode(salt), rounds_int
        )
        return hmac.compare_digest(actual, base64.urlsafe_b64decode(expected))
    except (ValueError, TypeError, IndexError):
        return False


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "hash-password":
    import getpass
    pwd = getpass.getpass("New owner password: ")
    if len(pwd) < 12:
        raise SystemExit("Use a password of at least 12 characters.")
    print(password_hash(pwd))
