"""SQLite connection, schema initialization, and password hashing."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DB_PATH = str(REPO_ROOT / "data" / "ai_finance.db")
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")
DEFAULT_SESSION_TTL_SECONDS = 7 * 24 * 3600


class DuplicateUserError(Exception):
    """Raised when attempting to register an already-existing username."""


def get_db_path() -> str:
    return os.environ.get("AI_FINANCE_DB_PATH") or DEFAULT_DB_PATH


def get_session_ttl_seconds() -> int:
    try:
        return max(60, int(os.environ.get("AI_FINANCE_SESSION_TTL_SECONDS", str(DEFAULT_SESSION_TTL_SECONDS))))
    except ValueError:
        return DEFAULT_SESSION_TTL_SECONDS


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _utc_expires_at() -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=get_session_ttl_seconds())).isoformat()


def _hash_password(password: str, salt: str) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
    return dk.hex()


def verify_password(password: str, salt: str, expected_hash: str) -> bool:
    actual = _hash_password(password, salt)
    return hmac.compare_digest(actual, expected_hash)


@contextmanager
def _connect(db_path: Optional[str] = None) -> Iterator[sqlite3.Connection]:
    path = db_path or get_db_path()
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = sqlite3.connect(path, timeout=15.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA busy_timeout = 15000;")
        conn.execute("PRAGMA foreign_keys = ON;")
        with conn:
            yield conn
    finally:
        conn.close()


def init_db(db_path: Optional[str] = None, seed_demo_payload: Optional[Dict[str, Any]] = None) -> None:
    """Create tables and seed default user (`user` / `password`)."""
    with _connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS financial_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                health_score REAL NOT NULL,
                grade TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS module_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plan_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                module_name TEXT NOT NULL,
                inputs_json TEXT NOT NULL,
                outputs_json TEXT NOT NULL,
                score REAL,
                updated_at TEXT NOT NULL,
                UNIQUE(plan_id, module_name),
                FOREIGN KEY (plan_id) REFERENCES financial_plans(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            """
        )

        # Seamless migration if an older local DB still has the legacy table
        legacy_tbl = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='skill_runs'"
        ).fetchone()
        if legacy_tbl is not None:
            conn.execute(
                """
                INSERT OR IGNORE INTO module_runs
                    (plan_id, user_id, module_name, inputs_json, outputs_json, score, updated_at)
                SELECT plan_id, user_id, skill_name, inputs_json, outputs_json, score, updated_at
                FROM skill_runs
                """
            )
            conn.execute("DROP TABLE skill_runs;")

        cols = {r["name"] for r in conn.execute("PRAGMA table_info(sessions)").fetchall()}
        if "expires_at" not in cols:
            conn.execute("ALTER TABLE sessions ADD COLUMN expires_at TEXT;")

        if os.environ.get("AI_FINANCE_SEED_DEFAULT_USER", "1") != "0":
            default_user = (os.environ.get("FINPLAN_DEFAULT_USER") or "user").strip() or "user"
            default_pass = os.environ.get("FINPLAN_DEFAULT_PASSWORD") or "password"
            row = conn.execute("SELECT id FROM users WHERE username = ?", (default_user,)).fetchone()
            if row is None:
                salt = secrets.token_hex(16)
                pw_hash = _hash_password(default_pass, salt)
                cur = conn.execute(
                    "INSERT INTO users (username, password_hash, salt, created_at) VALUES (?, ?, ?, ?)",
                    (default_user, pw_hash, salt, _utc_now()),
                )
                user_id = cur.lastrowid
                if seed_demo_payload is not None and user_id is not None:
                    now = _utc_now()
                    conn.execute(
                        """
                        INSERT INTO financial_plans
                            (user_id, title, health_score, grade, payload_json, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            user_id,
                            seed_demo_payload.get("client_name") or "Sample Financial Plan",
                            float(seed_demo_payload.get("health_score", 0)),
                            str(seed_demo_payload.get("grade") or "B-"),
                            json.dumps(seed_demo_payload),
                            now,
                            now,
                        ),
                    )
        conn.commit()

