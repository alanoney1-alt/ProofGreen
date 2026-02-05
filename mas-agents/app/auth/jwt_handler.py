"""
ProofGreen MAS - JWT Token Handler
Handles JWT token creation, validation, and refresh.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from dataclasses import dataclass
from jose import jwt, JWTError
from passlib.context import CryptContext

from config.settings import settings


# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@dataclass
class TokenPayload:
    """JWT token payload."""
    sub: str  # Subject (user ID)
    company_id: str
    role: str
    permissions: list
    exp: datetime
    iat: datetime
    jti: Optional[str] = None  # JWT ID for revocation
    token_type: str = "access"


class JWTHandler:
    """
    JWT token handler with access and refresh token support.
    """

    def __init__(
        self,
        secret_key: str = None,
        algorithm: str = "HS256",
        access_token_expire_minutes: int = 30,
        refresh_token_expire_days: int = 7
    ):
        self.secret_key = secret_key or settings.JWT_SECRET_KEY
        self.algorithm = algorithm or settings.JWT_ALGORITHM
        self.access_expire = access_token_expire_minutes
        self.refresh_expire = refresh_token_expire_days

    def create_access_token(
        self,
        user_id: str,
        company_id: str,
        role: str,
        permissions: list = None,
        additional_claims: Dict = None
    ) -> str:
        """
        Create a new access token.

        Args:
            user_id: User identifier
            company_id: Company identifier
            role: User role (admin, manager, technician)
            permissions: List of permissions
            additional_claims: Additional JWT claims

        Returns:
            Encoded JWT token string
        """
        now = datetime.utcnow()
        expire = now + timedelta(minutes=self.access_expire)

        payload = {
            "sub": user_id,
            "company_id": company_id,
            "role": role,
            "permissions": permissions or [],
            "exp": expire,
            "iat": now,
            "token_type": "access"
        }

        if additional_claims:
            payload.update(additional_claims)

        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def create_refresh_token(
        self,
        user_id: str,
        company_id: str,
        jti: str = None
    ) -> str:
        """
        Create a new refresh token.

        Args:
            user_id: User identifier
            company_id: Company identifier
            jti: JWT ID for token tracking/revocation

        Returns:
            Encoded refresh token string
        """
        import uuid

        now = datetime.utcnow()
        expire = now + timedelta(days=self.refresh_expire)

        payload = {
            "sub": user_id,
            "company_id": company_id,
            "exp": expire,
            "iat": now,
            "jti": jti or str(uuid.uuid4()),
            "token_type": "refresh"
        }

        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def verify_token(
        self,
        token: str,
        expected_type: str = "access"
    ) -> Optional[TokenPayload]:
        """
        Verify and decode a JWT token.

        Args:
            token: JWT token string
            expected_type: Expected token type (access/refresh)

        Returns:
            TokenPayload if valid, None if invalid
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )

            # Verify token type
            if payload.get("token_type") != expected_type:
                return None

            return TokenPayload(
                sub=payload.get("sub"),
                company_id=payload.get("company_id"),
                role=payload.get("role", "user"),
                permissions=payload.get("permissions", []),
                exp=datetime.fromtimestamp(payload.get("exp")),
                iat=datetime.fromtimestamp(payload.get("iat")),
                jti=payload.get("jti"),
                token_type=payload.get("token_type")
            )

        except JWTError:
            return None

    def refresh_access_token(
        self,
        refresh_token: str,
        user_role: str = None,
        permissions: list = None
    ) -> Optional[Dict[str, str]]:
        """
        Generate new access token using refresh token.

        Args:
            refresh_token: Valid refresh token
            user_role: Updated user role (optional)
            permissions: Updated permissions (optional)

        Returns:
            Dict with new access_token and refresh_token
        """
        payload = self.verify_token(refresh_token, expected_type="refresh")

        if not payload:
            return None

        # Create new tokens
        new_access = self.create_access_token(
            user_id=payload.sub,
            company_id=payload.company_id,
            role=user_role or payload.role,
            permissions=permissions or payload.permissions
        )

        # Optionally rotate refresh token
        new_refresh = self.create_refresh_token(
            user_id=payload.sub,
            company_id=payload.company_id
        )

        return {
            "access_token": new_access,
            "refresh_token": new_refresh,
            "token_type": "bearer"
        }

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password for storage."""
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return pwd_context.verify(plain_password, hashed_password)


# Convenience functions using default settings
_default_handler = JWTHandler()


def create_access_token(
    user_id: str,
    company_id: str,
    role: str,
    permissions: list = None
) -> str:
    """Create access token with default settings."""
    return _default_handler.create_access_token(
        user_id, company_id, role, permissions
    )


def create_refresh_token(user_id: str, company_id: str) -> str:
    """Create refresh token with default settings."""
    return _default_handler.create_refresh_token(user_id, company_id)


def verify_token(token: str, expected_type: str = "access") -> Optional[TokenPayload]:
    """Verify token with default settings."""
    return _default_handler.verify_token(token, expected_type)
