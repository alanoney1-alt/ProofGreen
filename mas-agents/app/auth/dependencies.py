"""
ProofGreen MAS - Authentication Dependencies
FastAPI dependencies for route protection.
"""

from typing import Optional, List
from dataclasses import dataclass
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .jwt_handler import JWTHandler, TokenPayload


# HTTP Bearer token scheme
security = HTTPBearer(auto_error=False)

# Default JWT handler
jwt_handler = JWTHandler()


@dataclass
class CurrentUser:
    """Authenticated user context."""
    id: str
    company_id: str
    role: str
    permissions: List[str]


async def get_token_from_header(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Optional[str]:
    """Extract token from Authorization header."""
    if credentials:
        return credentials.credentials
    return None


async def get_token_from_cookie(request: Request) -> Optional[str]:
    """Extract token from cookie (for web clients)."""
    return request.cookies.get("access_token")


async def get_current_user(
    header_token: Optional[str] = Depends(get_token_from_header),
    cookie_token: Optional[str] = Depends(get_token_from_cookie)
) -> CurrentUser:
    """
    Get current authenticated user from JWT token.

    Checks both Authorization header and cookies.
    Raises 401 if no valid token found.
    """
    token = header_token or cookie_token

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"}
        )

    payload = jwt_handler.verify_token(token, expected_type="access")

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"}
        )

    return CurrentUser(
        id=payload.sub,
        company_id=payload.company_id,
        role=payload.role,
        permissions=payload.permissions
    )


async def get_current_active_user(
    current_user: CurrentUser = Depends(get_current_user)
) -> CurrentUser:
    """
    Get current active user.

    In production, add additional checks like:
    - User account status (active/suspended)
    - Email verification status
    - Subscription status
    """
    # Add user status validation here if needed
    # e.g., check database for user.is_active
    return current_user


async def get_optional_user(
    header_token: Optional[str] = Depends(get_token_from_header),
    cookie_token: Optional[str] = Depends(get_token_from_cookie)
) -> Optional[CurrentUser]:
    """
    Get current user if authenticated, None otherwise.

    Use for routes that work with or without authentication.
    """
    token = header_token or cookie_token

    if not token:
        return None

    payload = jwt_handler.verify_token(token, expected_type="access")

    if not payload:
        return None

    return CurrentUser(
        id=payload.sub,
        company_id=payload.company_id,
        role=payload.role,
        permissions=payload.permissions
    )


class RoleChecker:
    """
    Dependency class for role-based access control.

    Usage:
        @router.get("/admin-only", dependencies=[Depends(RoleChecker(["admin"]))])
        async def admin_route():
            pass
    """

    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles

    async def __call__(
        self,
        current_user: CurrentUser = Depends(get_current_user)
    ) -> CurrentUser:
        if current_user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role}' not authorized. Required: {self.allowed_roles}"
            )
        return current_user


class PermissionChecker:
    """
    Dependency class for permission-based access control.

    Usage:
        @router.post("/approve", dependencies=[Depends(PermissionChecker(["approve_jobs"]))])
        async def approve_job():
            pass
    """

    def __init__(self, required_permissions: List[str], require_all: bool = True):
        self.required_permissions = required_permissions
        self.require_all = require_all

    async def __call__(
        self,
        current_user: CurrentUser = Depends(get_current_user)
    ) -> CurrentUser:
        user_perms = set(current_user.permissions)
        required = set(self.required_permissions)

        if self.require_all:
            # User must have ALL required permissions
            if not required.issubset(user_perms):
                missing = required - user_perms
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Missing required permissions: {list(missing)}"
                )
        else:
            # User must have AT LEAST ONE required permission
            if not required.intersection(user_perms):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Requires at least one of: {self.required_permissions}"
                )

        return current_user


class CompanyAccessChecker:
    """
    Dependency to verify user has access to requested company data.

    Prevents users from accessing other companies' data.
    """

    async def __call__(
        self,
        company_id: str,
        current_user: CurrentUser = Depends(get_current_user)
    ) -> CurrentUser:
        # Admins can access any company (for support purposes)
        if current_user.role == "super_admin":
            return current_user

        if current_user.company_id != company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this company's data"
            )

        return current_user


# Convenience dependency functions
def require_role(allowed_roles: List[str]):
    """Create a role requirement dependency."""
    return Depends(RoleChecker(allowed_roles))


def require_permission(permissions: List[str], require_all: bool = True):
    """Create a permission requirement dependency."""
    return Depends(PermissionChecker(permissions, require_all))


def require_company_access():
    """Create a company access check dependency."""
    return Depends(CompanyAccessChecker())


# Pre-configured role checkers for common use cases
require_admin = require_role(["admin", "super_admin"])
require_manager = require_role(["admin", "super_admin", "manager"])
require_technician = require_role(["admin", "super_admin", "manager", "technician"])
