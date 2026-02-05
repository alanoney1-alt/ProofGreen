"""
ProofGreen MAS - Authentication Routes
Login, logout, token refresh, and password management endpoints.
"""

from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from pydantic import BaseModel, EmailStr
import structlog

from .jwt_handler import JWTHandler, TokenPayload
from .dependencies import get_current_user, CurrentUser


logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])

# JWT handler instance
jwt_handler = JWTHandler()


# Request/Response Models
class LoginRequest(BaseModel):
    """Login request body."""
    email: EmailStr
    password: str
    remember_me: bool = False


class TokenResponse(BaseModel):
    """Token response body."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class RefreshRequest(BaseModel):
    """Token refresh request."""
    refresh_token: str


class PasswordChangeRequest(BaseModel):
    """Password change request."""
    current_password: str
    new_password: str


class UserResponse(BaseModel):
    """Current user response."""
    id: str
    email: str
    name: str
    company_id: str
    role: str
    permissions: list


# Mock user database (replace with actual DB in production)
MOCK_USERS = {
    "admin@proofgreen.io": {
        "id": "user-001",
        "email": "admin@proofgreen.io",
        "name": "Admin User",
        "password_hash": JWTHandler.hash_password("admin123"),
        "company_id": "COMP-001",
        "role": "admin",
        "permissions": ["read", "write", "approve", "delete", "manage_users"],
        "is_active": True
    },
    "tech@proofgreen.io": {
        "id": "user-002",
        "email": "tech@proofgreen.io",
        "name": "John Technician",
        "password_hash": JWTHandler.hash_password("tech123"),
        "company_id": "COMP-001",
        "role": "technician",
        "permissions": ["read", "write"],
        "is_active": True
    }
}


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    response: Response
):
    """
    Authenticate user and return JWT tokens.

    - **email**: User email address
    - **password**: User password
    - **remember_me**: Extend refresh token validity (optional)
    """
    # Look up user (replace with actual DB query)
    user = MOCK_USERS.get(request.email)

    if not user:
        logger.warning("login_failed", email=request.email, reason="user_not_found")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Verify password
    if not JWTHandler.verify_password(request.password, user["password_hash"]):
        logger.warning("login_failed", email=request.email, reason="invalid_password")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Check if user is active
    if not user.get("is_active", True):
        logger.warning("login_failed", email=request.email, reason="account_disabled")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled"
        )

    # Create tokens
    access_token = jwt_handler.create_access_token(
        user_id=user["id"],
        company_id=user["company_id"],
        role=user["role"],
        permissions=user["permissions"]
    )

    refresh_token = jwt_handler.create_refresh_token(
        user_id=user["id"],
        company_id=user["company_id"]
    )

    # Calculate expiry
    expires_in = jwt_handler.access_expire * 60  # Convert to seconds

    # Set HTTP-only cookie for web clients
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=True,  # HTTPS only
        samesite="lax",
        max_age=expires_in
    )

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=jwt_handler.refresh_expire * 24 * 60 * 60  # Days to seconds
    )

    logger.info("login_success", user_id=user["id"], company_id=user["company_id"])

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshRequest,
    response: Response,
    req: Request
):
    """
    Refresh access token using refresh token.

    Can receive refresh token from:
    - Request body
    - HTTP-only cookie
    """
    # Try to get refresh token from body or cookie
    token = request.refresh_token or req.cookies.get("refresh_token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token required"
        )

    # Verify refresh token
    payload = jwt_handler.verify_token(token, expected_type="refresh")

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )

    # Look up user to get current role/permissions
    user = None
    for u in MOCK_USERS.values():
        if u["id"] == payload.sub:
            user = u
            break

    if not user or not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or disabled"
        )

    # Generate new tokens
    new_access = jwt_handler.create_access_token(
        user_id=user["id"],
        company_id=user["company_id"],
        role=user["role"],
        permissions=user["permissions"]
    )

    new_refresh = jwt_handler.create_refresh_token(
        user_id=user["id"],
        company_id=user["company_id"]
    )

    expires_in = jwt_handler.access_expire * 60

    # Update cookies
    response.set_cookie(
        key="access_token",
        value=new_access,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=expires_in
    )

    response.set_cookie(
        key="refresh_token",
        value=new_refresh,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=jwt_handler.refresh_expire * 24 * 60 * 60
    )

    logger.info("token_refreshed", user_id=payload.sub)

    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        expires_in=expires_in
    )


@router.post("/logout")
async def logout(response: Response, current_user: CurrentUser = Depends(get_current_user)):
    """
    Logout user by clearing cookies.

    In production, also:
    - Add refresh token to blacklist
    - Invalidate any active sessions
    """
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")

    logger.info("logout", user_id=current_user.id)

    return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: CurrentUser = Depends(get_current_user)):
    """
    Get current authenticated user information.
    """
    # Look up full user details
    user = None
    for u in MOCK_USERS.values():
        if u["id"] == current_user.id:
            user = u
            break

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return UserResponse(
        id=user["id"],
        email=user["email"],
        name=user["name"],
        company_id=user["company_id"],
        role=user["role"],
        permissions=user["permissions"]
    )


@router.post("/change-password")
async def change_password(
    request: PasswordChangeRequest,
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Change current user's password.
    """
    # Look up user
    user = None
    for u in MOCK_USERS.values():
        if u["id"] == current_user.id:
            user = u
            break

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Verify current password
    if not JWTHandler.verify_password(request.current_password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )

    # Validate new password strength
    if len(request.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters"
        )

    # Update password (in production, update database)
    user["password_hash"] = JWTHandler.hash_password(request.new_password)

    logger.info("password_changed", user_id=current_user.id)

    return {"message": "Password changed successfully"}


@router.post("/verify-token")
async def verify_token_endpoint(current_user: CurrentUser = Depends(get_current_user)):
    """
    Verify if current token is valid.

    Useful for frontend to check authentication status.
    """
    return {
        "valid": True,
        "user_id": current_user.id,
        "company_id": current_user.company_id,
        "role": current_user.role
    }
