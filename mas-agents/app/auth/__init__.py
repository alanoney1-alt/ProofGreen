"""
ProofGreen MAS - Authentication Package
JWT-based authentication for API routes.
"""

from .jwt_handler import (
    JWTHandler,
    TokenPayload,
    create_access_token,
    create_refresh_token,
    verify_token
)
from .dependencies import (
    get_current_user,
    get_current_active_user,
    require_role,
    RoleChecker
)
from .routes import router as auth_router

__all__ = [
    # JWT Handler
    "JWTHandler",
    "TokenPayload",
    "create_access_token",
    "create_refresh_token",
    "verify_token",

    # Dependencies
    "get_current_user",
    "get_current_active_user",
    "require_role",
    "RoleChecker",

    # Routes
    "auth_router"
]
