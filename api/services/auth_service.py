import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
STORAGE_DIR = Path(os.getenv("TRAVELMIND_STORAGE_DIR", str(PROJECT_ROOT / "data")))
PROFILE_DB_PATH = STORAGE_DIR / "traveler_profiles.sqlite3"
TOKEN_TTL_SECONDS = 8 * 60 * 60
PASSWORD_ITERATIONS = 310_000


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


class AuthService:
    def __init__(self):
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(PROFILE_DB_PATH) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS accounts ("
                "account_id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "email TEXT NOT NULL UNIQUE, password_salt BLOB NOT NULL, "
                "password_hash BLOB NOT NULL, created_at INTEGER NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS revoked_tokens (token_id TEXT PRIMARY KEY, expires_at INTEGER NOT NULL)"
            )
            columns = {
                row[1] for row in connection.execute("PRAGMA table_info(traveler_profiles)")
            }
            if "owner_account_id" not in columns:
                connection.execute(
                    "ALTER TABLE traveler_profiles ADD COLUMN owner_account_id INTEGER"
                )
        configured_secret = os.getenv("TRAVELMIND_AUTH_SECRET")
        secret_path = STORAGE_DIR / ".travelmind_auth_secret"
        if configured_secret:
            if len(configured_secret.encode("utf-8")) < 32:
                raise ValueError("TRAVELMIND_AUTH_SECRET must contain at least 32 bytes.")
            self._secret = configured_secret.encode("utf-8")
        elif secret_path.exists():
            self._secret = secret_path.read_bytes()
        else:
            self._secret = secrets.token_bytes(32)
            secret_path.write_bytes(self._secret)

    @staticmethod
    def _password_hash(password: str, salt: bytes) -> bytes:
        return hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS
        )

    def _issue_token(self, account_id: int, email: str) -> str:
        payload = _b64encode(json.dumps({
            "account_id": account_id,
            "email": email,
            "exp": int(time.time()) + TOKEN_TTL_SECONDS,
            "jti": secrets.token_urlsafe(18),
        }, separators=(",", ":")).encode("utf-8"))
        signature = _b64encode(hmac.new(self._secret, payload.encode("ascii"), hashlib.sha256).digest())
        return f"{payload}.{signature}"

    def _session(self, account_id: int, email: str) -> dict:
        return {
            "access_token": self._issue_token(account_id, email),
            "token_type": "bearer",
            "expires_in": TOKEN_TTL_SECONDS,
            "account": {"id": account_id, "email": email},
        }

    def register(self, email: str, password: str, claim_profile_id: str | None = None) -> dict:
        normalized_email = email.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", normalized_email):
            raise ValueError("Enter a valid email address.")
        if len(password) < 10:
            raise ValueError("Use a password with at least 10 characters.")
        salt = secrets.token_bytes(16)
        password_hash = self._password_hash(password, salt)
        try:
            with sqlite3.connect(PROFILE_DB_PATH) as connection:
                cursor = connection.execute(
                    "INSERT INTO accounts (email, password_salt, password_hash, created_at) "
                    "VALUES (?, ?, ?, ?)",
                    (normalized_email, salt, password_hash, int(time.time())),
                )
                account_id = int(cursor.lastrowid)
                if claim_profile_id:
                    claimed = connection.execute(
                        "UPDATE traveler_profiles SET owner_account_id=? "
                        "WHERE user_id=? AND owner_account_id IS NULL",
                        (account_id, claim_profile_id),
                    )
                    if claimed.rowcount != 1:
                        raise ValueError("That guest profile cannot be linked to this account.")
        except sqlite3.IntegrityError as error:
            raise ValueError("An account with that email already exists.") from error
        return self._session(account_id, normalized_email)

    def login(self, email: str, password: str) -> dict:
        normalized_email = email.strip().lower()
        with sqlite3.connect(PROFILE_DB_PATH) as connection:
            row = connection.execute(
                "SELECT account_id, email, password_salt, password_hash "
                "FROM accounts WHERE email=?",
                (normalized_email,),
            ).fetchone()
        if row is None:
            raise ValueError("Email or password is incorrect.")
        account_id, stored_email, salt, expected_hash = row
        actual_hash = self._password_hash(password, salt)
        if not hmac.compare_digest(actual_hash, expected_hash):
            raise ValueError("Email or password is incorrect.")
        return self._session(int(account_id), stored_email)

    def verify_token(self, token: str) -> dict:
        try:
            payload, provided_signature = token.split(".", 1)
            expected_signature = _b64encode(
                hmac.new(self._secret, payload.encode("ascii"), hashlib.sha256).digest()
            )
            if not hmac.compare_digest(provided_signature, expected_signature):
                raise ValueError
            data = json.loads(_b64decode(payload))
            if int(data["exp"]) <= int(time.time()):
                raise ValueError
            with sqlite3.connect(PROFILE_DB_PATH) as connection:
                revoked = connection.execute(
                    "SELECT 1 FROM revoked_tokens WHERE token_id=?", (data["jti"],)
                ).fetchone()
            if revoked:
                raise ValueError
            return {"id": int(data["account_id"]), "email": str(data["email"])}
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
            raise ValueError("Your session is invalid or expired. Please sign in again.") from error

    def revoke_token(self, token: str) -> None:
        payload, signature = token.split(".", 1)
        expected = _b64encode(hmac.new(self._secret, payload.encode("ascii"), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise ValueError("Your session is invalid or expired. Please sign in again.")
        data = json.loads(_b64decode(payload))
        with sqlite3.connect(PROFILE_DB_PATH) as connection:
            connection.execute(
                "INSERT OR IGNORE INTO revoked_tokens (token_id, expires_at) VALUES (?, ?)",
                (data["jti"], int(data["exp"])),
            )
            connection.execute("DELETE FROM revoked_tokens WHERE expires_at <= ?", (int(time.time()),))

    def get_profile_owner(self, user_id: str) -> int | None:
        with sqlite3.connect(PROFILE_DB_PATH) as connection:
            row = connection.execute(
                "SELECT owner_account_id FROM traveler_profiles WHERE user_id=?", (user_id,)
            ).fetchone()
        return None if row is None or row[0] is None else int(row[0])

    def get_account_profiles(self, account_id: int) -> list[dict[str, str]]:
        with sqlite3.connect(PROFILE_DB_PATH) as connection:
            rows = connection.execute(
                "SELECT user_id, name FROM traveler_profiles WHERE owner_account_id=? ORDER BY rowid",
                (account_id,),
            ).fetchall()
        return [{"user_id": user_id, "name": name} for user_id, name in rows]
