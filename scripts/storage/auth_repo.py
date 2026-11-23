"""User authentication, registration, and session token persistence."""

from __future__ import annotations

import json
import secrets
from typing import Any, Dict, Optional

from .schema import (
    USERNAME_RE,
    DuplicateUserError,
    _connect,
    _hash_password,
    _utc_expires_at,
    _utc_now,
    verify_password,
)

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

