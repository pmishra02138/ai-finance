"""FastAPI route modules for FinPlan."""

from .auth_routes import router as auth_router
from .plans_routes import router as plans_router

__all__ = ["auth_router", "plans_router"]
