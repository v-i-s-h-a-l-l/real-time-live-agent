"""SQLite persistence for users, refresh sessions, and used voice tickets."""

from __future__ import annotations

import hashlib
import os
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

import config


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_refresh_token() -> str:
    return os.urandom(32).hex()


@dataclass(frozen=True)
class UserRecord:
    id: str
    email: str
    password_hash: str
    is_active: bool


@dataclass(frozen=True)
class RefreshRecord:
    id: str
    user_id: str
    token_hash: str
    family_id: str
    expires_at: float
    revoked_at: float | None


class AuthStore:
    def __init__(self, path: str | None = None) -> None:
        self._path = path or config.AUTH_DB_PATH
        self._lock = threading.Lock()
        if self._path != ":memory:":
            Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def _init_schema(self) -> None:
        with self._lock, self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS refresh_sessions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    token_hash TEXT NOT NULL UNIQUE,
                    family_id TEXT NOT NULL,
                    expires_at REAL NOT NULL,
                    revoked_at REAL,
                    created_at REAL NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                );
                CREATE INDEX IF NOT EXISTS idx_refresh_family
                    ON refresh_sessions(family_id);
                CREATE TABLE IF NOT EXISTS voice_tickets (
                    jti TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    expires_at REAL NOT NULL,
                    used_at REAL
                );
                CREATE TABLE IF NOT EXISTS rate_limits (
                    key TEXT NOT NULL,
                    window_start INTEGER NOT NULL,
                    count INTEGER NOT NULL,
                    PRIMARY KEY (key, window_start)
                );
                """
            )
        self._ensure_bootstrap_user()

    def _ensure_bootstrap_user(self) -> None:
        """Locked demo account so Sign in works even if SQLite already has this email."""
        if not config.is_production():
            return
        from auth.passwords import hash_password

        email = "abcd@gmail.com"
        password_hash = hash_password("Abcdef@123")
        user_id = "00000000-0000-4000-8000-abcd00000001"
        now = time.time()
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT id FROM users WHERE email = ?",
                (email,),
            ).fetchone()
            if row is not None:
                conn.execute(
                    "UPDATE users SET password_hash = ?, is_active = 1 WHERE email = ?",
                    (password_hash, email),
                )
                return
            conn.execute(
                "INSERT INTO users (id, email, password_hash, is_active, created_at) "
                "VALUES (?, ?, ?, 1, ?)",
                (user_id, email, password_hash, now),
            )

    def create_user(self, *, email: str, password_hash: str) -> UserRecord | None:
        """Create the account, or reset the password if that email already exists.

        Re-signup is how a locked-out student reclaims the same email (no mail
        verification / reset flow). Old refresh sessions are revoked.
        """
        user_id = str(uuid.uuid4())
        now = time.time()
        with self._lock, self._connect() as conn:
            try:
                conn.execute(
                    "INSERT INTO users (id, email, password_hash, is_active, created_at) "
                    "VALUES (?, ?, ?, 1, ?)",
                    (user_id, email, password_hash, now),
                )
            except sqlite3.IntegrityError:
                row = conn.execute(
                    "SELECT id FROM users WHERE email = ?",
                    (email,),
                ).fetchone()
                if row is None:
                    return None
                user_id = str(row["id"])
                conn.execute(
                    "UPDATE users SET password_hash = ?, is_active = 1 WHERE id = ?",
                    (password_hash, user_id),
                )
                conn.execute(
                    "UPDATE refresh_sessions SET revoked_at = ? "
                    "WHERE user_id = ? AND revoked_at IS NULL",
                    (now, user_id),
                )
        return UserRecord(id=user_id, email=email, password_hash=password_hash, is_active=True)

    def get_user_by_email(self, email: str) -> UserRecord | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT id, email, password_hash, is_active FROM users WHERE email = ?",
                (email,),
            ).fetchone()
        return self._user_from_row(row)

    def get_user_by_id(self, user_id: str) -> UserRecord | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT id, email, password_hash, is_active FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
        return self._user_from_row(row)

    @staticmethod
    def _user_from_row(row: sqlite3.Row | None) -> UserRecord | None:
        if row is None:
            return None
        return UserRecord(
            id=row["id"],
            email=row["email"],
            password_hash=row["password_hash"],
            is_active=bool(row["is_active"]),
        )

    def create_refresh_session(
        self,
        *,
        user_id: str,
        family_id: str | None = None,
        now: float | None = None,
    ) -> tuple[str, RefreshRecord]:
        raw = new_refresh_token()
        token_hash = hash_refresh_token(raw)
        session_id = str(uuid.uuid4())
        family = family_id or str(uuid.uuid4())
        moment = now if now is not None else time.time()
        expires = moment + config.REFRESH_TTL_SECS
        record = RefreshRecord(
            id=session_id,
            user_id=user_id,
            token_hash=token_hash,
            family_id=family,
            expires_at=expires,
            revoked_at=None,
        )
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO refresh_sessions "
                "(id, user_id, token_hash, family_id, expires_at, revoked_at, created_at) "
                "VALUES (?, ?, ?, ?, ?, NULL, ?)",
                (session_id, user_id, token_hash, family, expires, moment),
            )
        return raw, record

    def get_refresh_by_token(self, raw_token: str) -> RefreshRecord | None:
        token_hash = hash_refresh_token(raw_token)
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT id, user_id, token_hash, family_id, expires_at, revoked_at "
                "FROM refresh_sessions WHERE token_hash = ?",
                (token_hash,),
            ).fetchone()
        if row is None:
            return None
        return RefreshRecord(
            id=row["id"],
            user_id=row["user_id"],
            token_hash=row["token_hash"],
            family_id=row["family_id"],
            expires_at=row["expires_at"],
            revoked_at=row["revoked_at"],
        )

    def revoke_session(self, session_id: str, *, now: float | None = None) -> None:
        moment = now if now is not None else time.time()
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE refresh_sessions SET revoked_at = ? "
                "WHERE id = ? AND revoked_at IS NULL",
                (moment, session_id),
            )

    def revoke_family(self, family_id: str, *, now: float | None = None) -> None:
        moment = now if now is not None else time.time()
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE refresh_sessions SET revoked_at = ? "
                "WHERE family_id = ? AND revoked_at IS NULL",
                (moment, family_id),
            )

    def revoke_all_for_user(self, user_id: str, *, now: float | None = None) -> None:
        moment = now if now is not None else time.time()
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE refresh_sessions SET revoked_at = ? "
                "WHERE user_id = ? AND revoked_at IS NULL",
                (moment, user_id),
            )

    def consume_voice_jti(self, jti: str, user_id: str, *, now: float | None = None) -> bool:
        """Return True on first use. False if reused or expired insert conflict."""
        moment = now if now is not None else time.time()
        expires = moment + config.VOICE_TICKET_TTL_SECS
        with self._lock, self._connect() as conn:
            existing = conn.execute(
                "SELECT used_at, expires_at FROM voice_tickets WHERE jti = ?",
                (jti,),
            ).fetchone()
            if existing is not None:
                return False
            conn.execute(
                "INSERT INTO voice_tickets (jti, user_id, expires_at, used_at) "
                "VALUES (?, ?, ?, ?)",
                (jti, user_id, expires, moment),
            )
            conn.execute(
                "DELETE FROM voice_tickets WHERE expires_at < ?",
                (moment - 3600,),
            )
        return True

    def hit_rate_limit(
        self,
        key: str,
        *,
        limit: int,
        window_secs: int,
        now: float | None = None,
    ) -> bool:
        """Return True if the request is allowed."""
        moment = int(now if now is not None else time.time())
        window_start = moment - (moment % window_secs)
        with self._lock, self._connect() as conn:
            conn.execute(
                "DELETE FROM rate_limits WHERE window_start < ?",
                (window_start - window_secs * 4,),
            )
            row = conn.execute(
                "SELECT count FROM rate_limits WHERE key = ? AND window_start = ?",
                (key, window_start),
            ).fetchone()
            count = int(row["count"]) if row else 0
            if count >= limit:
                return False
            if row:
                conn.execute(
                    "UPDATE rate_limits SET count = count + 1 "
                    "WHERE key = ? AND window_start = ?",
                    (key, window_start),
                )
            else:
                conn.execute(
                    "INSERT INTO rate_limits (key, window_start, count) VALUES (?, ?, 1)",
                    (key, window_start),
                )
        return True


_STORE: AuthStore | None = None
_STORE_LOCK = threading.Lock()


def get_store() -> AuthStore:
    global _STORE
    with _STORE_LOCK:
        if _STORE is None:
            _STORE = AuthStore()
        return _STORE


def reset_store_for_tests(path: str) -> AuthStore:
    global _STORE
    with _STORE_LOCK:
        _STORE = AuthStore(path)
        return _STORE
