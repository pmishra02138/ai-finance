"""Modular SQLite persistence package for FinPlan."""

from .auth_repo import authenticate_user, get_user_by_token, register_user, revoke_token
from .plans_repo import (
    create_plan,
    delete_plan,
    get_module_run,
    get_plan,
    list_module_runs,
    list_plans,
    reset_plan,
    update_plan,
    upsert_module_run,
)
from .schema import (
    DEFAULT_DB_PATH,
    DEFAULT_SESSION_TTL_SECONDS,
    USERNAME_RE,
    DuplicateUserError,
    _connect,
    _hash_password,
    get_db_path,
    get_session_ttl_seconds,
    init_db,
    verify_password,
)

__all__ = [
    "DEFAULT_DB_PATH",
    "DEFAULT_SESSION_TTL_SECONDS",
    "DuplicateUserError",
    "USERNAME_RE",
    "_connect",
    "_hash_password",
    "authenticate_user",
    "create_plan",
    "delete_plan",
    "get_db_path",
    "get_module_run",
    "get_plan",
    "get_session_ttl_seconds",
    "get_user_by_token",
    "init_db",
    "list_module_runs",
    "list_plans",
    "register_user",
    "reset_plan",
    "revoke_token",
    "update_plan",
    "upsert_module_run",
    "verify_password",
]
