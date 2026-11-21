#!/usr/bin/env python3
"""
SQLite persistence layer for AI Personal Finance Advisor.

Tables:
  - users           (id, username, password_hash, salt, created_at)
  - sessions        (token, user_id, created_at)
  - financial_plans (id, user_id, title, health_score, grade, payload_json, created_at, updated_at)

Seeds a default user (`user` / `password`) and a starter plan if not already present.
"""

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

REPO_ROOT = Path(__file__).resolve().parent.parent
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

            CREATE TABLE IF NOT EXISTS skill_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plan_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                skill_name TEXT NOT NULL,
                inputs_json TEXT NOT NULL,
                outputs_json TEXT NOT NULL,
                score REAL,
                updated_at TEXT NOT NULL,
                UNIQUE(plan_id, skill_name),
                FOREIGN KEY (plan_id) REFERENCES financial_plans(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            """
        )

        cols = {r["name"] for r in conn.execute("PRAGMA table_info(sessions)").fetchall()}
        if "expires_at" not in cols:
            conn.execute("ALTER TABLE sessions ADD COLUMN expires_at TEXT;")

        if os.environ.get("AI_FINANCE_SEED_DEFAULT_USER", "1") != "0":
            row = conn.execute("SELECT id FROM users WHERE username = ?", ("user",)).fetchone()
            if row is None:
                salt = secrets.token_hex(16)
                pw_hash = _hash_password("password", salt)
                cur = conn.execute(
                    "INSERT INTO users (username, password_hash, salt, created_at) VALUES (?, ?, ?, ?)",
                    ("user", pw_hash, salt, _utc_now()),
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


def authenticate_user(username: str, password: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    with _connect(db_path) as conn:
        now = _utc_now()
        row = conn.execute(
            "SELECT id, username, password_hash, salt FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        if row is None:
            return None
        if not verify_password(password, row["salt"], row["password_hash"]):
            return None
        token = secrets.token_urlsafe(32)
        conn.execute(
            "DELETE FROM sessions WHERE expires_at IS NOT NULL AND expires_at <= ?",
            (now,),
        )
        conn.execute(
            "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (token, row["id"], now, _utc_expires_at()),
        )
        conn.commit()
        return {"token": token, "user": {"id": row["id"], "username": row["username"]}}


def get_user_by_token(token: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    now = _utc_now()
    with _connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT u.id, u.username, s.expires_at
            FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token = ?
            """,
            (token,),
        ).fetchone()
        if row is None:
            return None
        if row["expires_at"] and row["expires_at"] <= now:
            conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
            conn.commit()
            return None
        return {"id": row["id"], "username": row["username"]}


def revoke_token(token: str, db_path: Optional[str] = None) -> None:
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()


def list_plans(user_id: int, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, title, health_score, grade, created_at, updated_at
            FROM financial_plans
            WHERE user_id = ?
            ORDER BY updated_at DESC, id DESC
            """,
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_plan(user_id: int, plan_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    with _connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT id, user_id, title, health_score, grade, payload_json, created_at, updated_at
            FROM financial_plans
            WHERE id = ? AND user_id = ?
            """,
            (plan_id, user_id),
        ).fetchone()
        if row is None:
            return None
        d = dict(row)
        d["payload"] = json.loads(d.pop("payload_json"))
        return d


def create_plan(
    user_id: int,
    title: str,
    health_score: float,
    grade: str,
    payload: Dict[str, Any],
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    now = _utc_now()
    with _connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO financial_plans
                (user_id, title, health_score, grade, payload_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, title, float(health_score), grade, json.dumps(payload), now, now),
        )
        plan_id = cur.lastrowid
        conn.commit()
    return {
        "id": plan_id,
        "title": title,
        "health_score": float(health_score),
        "grade": grade,
        "payload": payload,
        "created_at": now,
        "updated_at": now,
    }


def update_plan(
    user_id: int,
    plan_id: int,
    title: str,
    health_score: float,
    grade: str,
    payload: Dict[str, Any],
    db_path: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    now = _utc_now()
    with _connect(db_path) as conn:
        cur = conn.execute(
            """
            UPDATE financial_plans
            SET title = ?, health_score = ?, grade = ?, payload_json = ?, updated_at = ?
            WHERE id = ? AND user_id = ?
            """,
            (title, float(health_score), grade, json.dumps(payload), now, plan_id, user_id),
        )
        conn.commit()
        if cur.rowcount == 0:
            return None
    return get_plan(user_id, plan_id, db_path=db_path)


def delete_plan(user_id: int, plan_id: int, db_path: Optional[str] = None) -> bool:
    with _connect(db_path) as conn:
        cur = conn.execute(
            "DELETE FROM financial_plans WHERE id = ? AND user_id = ?",
            (plan_id, user_id),
        )
        conn.commit()
        return cur.rowcount > 0


def register_user(
    username: str,
    password: str,
    seed_demo_payload: Optional[Dict[str, Any]] = None,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    clean_user = (username or "").strip()
    if not USERNAME_RE.match(clean_user):
        raise ValueError("Username must be 3-32 characters (letters, digits, _, ., -).")
    if not password or len(password) < 4:
        raise ValueError("Password must be at least 4 characters.")

    with _connect(db_path) as conn:
        existing = conn.execute("SELECT id FROM users WHERE username = ?", (clean_user,)).fetchone()
        if existing is not None:
            raise DuplicateUserError(f"Username '{clean_user}' already exists.")
        salt = secrets.token_hex(16)
        pw_hash = _hash_password(password, salt)
        now = _utc_now()
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, salt, created_at) VALUES (?, ?, ?, ?)",
            (clean_user, pw_hash, salt, now),
        )
        user_id = cur.lastrowid
        assert user_id is not None
        if seed_demo_payload is not None:
            starter = dict(seed_demo_payload)
            starter["client_name"] = f"{clean_user}'s Financial Plan"
            conn.execute(
                """
                INSERT INTO financial_plans
                    (user_id, title, health_score, grade, payload_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    starter["client_name"],
                    float(starter.get("health_score", 0)),
                    str(starter.get("grade") or "B-"),
                    json.dumps(starter),
                    now,
                    now,
                ),
            )
        token = secrets.token_urlsafe(32)
        conn.execute(
            "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (token, user_id, now, _utc_expires_at()),
        )
        conn.commit()
        return {"token": token, "user": {"id": user_id, "username": clean_user}}


def upsert_skill_run(
    user_id: int,
    plan_id: int,
    skill_name: str,
    inputs: Dict[str, Any],
    outputs: Dict[str, Any],
    score: Optional[float] = None,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    now = _utc_now()
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO skill_runs (plan_id, user_id, skill_name, inputs_json, outputs_json, score, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(plan_id, skill_name) DO UPDATE SET
                inputs_json = excluded.inputs_json,
                outputs_json = excluded.outputs_json,
                score = excluded.score,
                updated_at = excluded.updated_at
            """,
            (plan_id, user_id, skill_name, json.dumps(inputs), json.dumps(outputs), score, now),
        )
        conn.commit()
    return {
        "plan_id": plan_id,
        "skill_name": skill_name,
        "inputs": inputs,
        "outputs": outputs,
        "score": score,
        "updated_at": now,
    }


def list_skill_runs(user_id: int, plan_id: int, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, plan_id, skill_name, inputs_json, outputs_json, score, updated_at
            FROM skill_runs
            WHERE user_id = ? AND plan_id = ?
            ORDER BY updated_at DESC
            """,
            (user_id, plan_id),
        ).fetchall()
        result: List[Dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            d["inputs"] = json.loads(d.pop("inputs_json"))
            d["outputs"] = json.loads(d.pop("outputs_json"))
            result.append(d)
        return result


def get_skill_run(
    user_id: int,
    plan_id: int,
    skill_name: str,
    db_path: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    with _connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT id, plan_id, skill_name, inputs_json, outputs_json, score, updated_at
            FROM skill_runs
            WHERE user_id = ? AND plan_id = ? AND skill_name = ?
            """,
            (user_id, plan_id, skill_name),
        ).fetchone()
        if row is None:
            return None
        d = dict(row)
        d["inputs"] = json.loads(d.pop("inputs_json"))
        d["outputs"] = json.loads(d.pop("outputs_json"))
        return d
