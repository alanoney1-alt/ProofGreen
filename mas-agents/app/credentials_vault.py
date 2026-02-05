"""
ProofGreen MAS - Credentials Vault
Secure credential storage with AES-256 encryption and OAuth refresh logic.
"""

import os
import json
import base64
import hashlib
import secrets
from typing import Dict, Optional, Any, List
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import asyncio
import httpx
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from pydantic import BaseModel, Field


class ConnectionStatus(str, Enum):
    """Connection status indicators."""
    CONNECTED = "connected"       # Green light
    AUTH_FAILED = "auth_failed"   # Red light
    EXPIRED = "expired"           # Yellow light
    UNKNOWN = "unknown"           # Gray light
    REFRESHING = "refreshing"     # Blue light


class CredentialType(str, Enum):
    """Types of credentials."""
    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    BASIC_AUTH = "basic_auth"


class StoredCredential(BaseModel):
    """Encrypted credential record."""
    id: str
    company_id: str
    provider: str
    credential_type: CredentialType
    encrypted_data: str  # AES-256 encrypted
    salt: str
    iv: str
    created_at: datetime
    updated_at: datetime
    last_verified: Optional[datetime] = None
    status: ConnectionStatus = ConnectionStatus.UNKNOWN
    token_expiry: Optional[datetime] = None
    refresh_scheduled: bool = False


class OAuthTokens(BaseModel):
    """OAuth token pair."""
    access_token: str
    refresh_token: Optional[str] = None
    expires_in: int = 3600
    token_type: str = "Bearer"
    scope: Optional[str] = None


class CredentialsVault:
    """
    Secure credentials vault with AES-256 encryption.
    Supports PostgreSQL storage and automatic OAuth token refresh.
    """

    def __init__(self, db_connection=None, master_key: Optional[str] = None):
        """
        Initialize credentials vault.

        Args:
            db_connection: PostgreSQL connection for persistent storage
            master_key: Master encryption key (defaults to env var)
        """
        self.db = db_connection
        self._master_key = master_key or os.getenv("CREDENTIALS_MASTER_KEY", "")

        if not self._master_key:
            # Generate a deterministic key from JWT secret for development
            jwt_secret = os.getenv("JWT_SECRET_KEY", "default_dev_key")
            self._master_key = hashlib.sha256(jwt_secret.encode()).hexdigest()[:32]

        # In-memory cache for decrypted credentials
        self._cache: Dict[str, Dict] = {}
        self._refresh_tasks: Dict[str, asyncio.Task] = {}

    # ========== ENCRYPTION ==========

    def _derive_key(self, salt: bytes) -> bytes:
        """Derive encryption key from master key and salt using PBKDF2."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        return base64.urlsafe_b64encode(kdf.derive(self._master_key.encode()))

    def _encrypt(self, data: Dict) -> tuple[str, str]:
        """
        Encrypt data using AES-256 (Fernet).

        Returns:
            Tuple of (encrypted_data, salt) both as base64 strings
        """
        salt = secrets.token_bytes(16)
        key = self._derive_key(salt)
        fernet = Fernet(key)

        plaintext = json.dumps(data).encode()
        encrypted = fernet.encrypt(plaintext)

        return base64.b64encode(encrypted).decode(), base64.b64encode(salt).decode()

    def _decrypt(self, encrypted_data: str, salt: str) -> Dict:
        """Decrypt AES-256 encrypted data."""
        salt_bytes = base64.b64decode(salt)
        key = self._derive_key(salt_bytes)
        fernet = Fernet(key)

        ciphertext = base64.b64decode(encrypted_data)
        plaintext = fernet.decrypt(ciphertext)

        return json.loads(plaintext.decode())

    # ========== CREDENTIAL STORAGE ==========

    async def store_credentials(
        self,
        company_id: str,
        provider: str,
        credentials: Dict,
        auth_type: str = "api_key"
    ) -> StoredCredential:
        """
        Store credentials securely with AES-256 encryption.

        Args:
            company_id: Company identifier
            provider: FSM provider name (servicetitan, jobber, etc.)
            credentials: Dict containing api_key, client_id, client_secret, etc.
            auth_type: Type of authentication (api_key, oauth2, basic_auth)

        Returns:
            StoredCredential record
        """
        credential_id = f"{company_id}_{provider.lower().replace(' ', '_')}"

        # Encrypt the credentials
        encrypted_data, salt = self._encrypt(credentials)

        # Determine credential type
        cred_type = CredentialType(auth_type) if auth_type in [e.value for e in CredentialType] else CredentialType.API_KEY

        now = datetime.utcnow()
        record = StoredCredential(
            id=credential_id,
            company_id=company_id,
            provider=provider,
            credential_type=cred_type,
            encrypted_data=encrypted_data,
            salt=salt,
            iv="",  # Fernet handles IV internally
            created_at=now,
            updated_at=now,
            status=ConnectionStatus.UNKNOWN
        )

        # Store in database if available
        if self.db:
            await self._store_to_db(record)

        # Cache decrypted credentials
        self._cache[credential_id] = credentials

        return record

    async def _store_to_db(self, record: StoredCredential):
        """Store credential record in PostgreSQL."""
        query = """
            INSERT INTO encrypted_credentials (
                id, company_id, provider, credential_type,
                encrypted_data, salt, iv, created_at, updated_at,
                last_verified, status, token_expiry, refresh_scheduled
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            ON CONFLICT (id) DO UPDATE SET
                encrypted_data = EXCLUDED.encrypted_data,
                salt = EXCLUDED.salt,
                updated_at = EXCLUDED.updated_at,
                last_verified = EXCLUDED.last_verified,
                status = EXCLUDED.status,
                token_expiry = EXCLUDED.token_expiry,
                refresh_scheduled = EXCLUDED.refresh_scheduled
        """
        await self.db.execute(
            query,
            record.id, record.company_id, record.provider,
            record.credential_type.value, record.encrypted_data,
            record.salt, record.iv, record.created_at, record.updated_at,
            record.last_verified, record.status.value, record.token_expiry,
            record.refresh_scheduled
        )

    async def get_credentials(
        self,
        company_id: str,
        provider: str
    ) -> Optional[Dict]:
        """
        Retrieve decrypted credentials.

        Returns:
            Decrypted credentials dict or None if not found
        """
        credential_id = f"{company_id}_{provider.lower().replace(' ', '_')}"

        # Check cache first
        if credential_id in self._cache:
            return self._cache[credential_id]

        # Load from database
        if self.db:
            record = await self._load_from_db(credential_id)
            if record:
                credentials = self._decrypt(record.encrypted_data, record.salt)
                self._cache[credential_id] = credentials
                return credentials

        return None

    async def _load_from_db(self, credential_id: str) -> Optional[StoredCredential]:
        """Load credential record from PostgreSQL."""
        query = "SELECT * FROM encrypted_credentials WHERE id = $1"
        row = await self.db.fetchrow(query, credential_id)

        if row:
            return StoredCredential(
                id=row["id"],
                company_id=row["company_id"],
                provider=row["provider"],
                credential_type=CredentialType(row["credential_type"]),
                encrypted_data=row["encrypted_data"],
                salt=row["salt"],
                iv=row["iv"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                last_verified=row["last_verified"],
                status=ConnectionStatus(row["status"]),
                token_expiry=row["token_expiry"],
                refresh_scheduled=row["refresh_scheduled"]
            )
        return None

    async def delete_credentials(self, company_id: str, provider: str) -> bool:
        """Delete stored credentials."""
        credential_id = f"{company_id}_{provider.lower().replace(' ', '_')}"

        # Remove from cache
        if credential_id in self._cache:
            del self._cache[credential_id]

        # Cancel any refresh tasks
        if credential_id in self._refresh_tasks:
            self._refresh_tasks[credential_id].cancel()
            del self._refresh_tasks[credential_id]

        # Remove from database
        if self.db:
            await self.db.execute(
                "DELETE FROM encrypted_credentials WHERE id = $1",
                credential_id
            )

        return True

    # ========== CONNECTION STATUS ==========

    async def get_connection_status(
        self,
        company_id: str,
        provider: str
    ) -> Dict:
        """
        Get connection status for UI display.

        Returns:
            Dict with status, color, message
        """
        credential_id = f"{company_id}_{provider.lower().replace(' ', '_')}"

        # Load record to check status
        if self.db:
            record = await self._load_from_db(credential_id)
            if record:
                # Check if token is expired
                if record.token_expiry and record.token_expiry < datetime.utcnow():
                    status = ConnectionStatus.EXPIRED
                else:
                    status = record.status
            else:
                status = ConnectionStatus.UNKNOWN
        else:
            status = ConnectionStatus.CONNECTED if credential_id in self._cache else ConnectionStatus.UNKNOWN

        status_map = {
            ConnectionStatus.CONNECTED: {
                "status": "connected",
                "color": "green",
                "message": "Connected and authenticated"
            },
            ConnectionStatus.AUTH_FAILED: {
                "status": "auth_failed",
                "color": "red",
                "message": "Authentication failed - check credentials"
            },
            ConnectionStatus.EXPIRED: {
                "status": "expired",
                "color": "yellow",
                "message": "Token expired - refreshing..."
            },
            ConnectionStatus.REFRESHING: {
                "status": "refreshing",
                "color": "blue",
                "message": "Refreshing authentication..."
            },
            ConnectionStatus.UNKNOWN: {
                "status": "unknown",
                "color": "gray",
                "message": "Connection not configured"
            }
        }

        return {
            "provider": provider,
            "company_id": company_id,
            **status_map.get(status, status_map[ConnectionStatus.UNKNOWN])
        }

    async def verify_connection(
        self,
        company_id: str,
        provider: str
    ) -> Dict:
        """
        Verify connection by making a test API call.

        Returns:
            Verification result with status update
        """
        credentials = await self.get_credentials(company_id, provider)
        if not credentials:
            return {
                "success": False,
                "status": ConnectionStatus.UNKNOWN,
                "error": "No credentials found"
            }

        credential_id = f"{company_id}_{provider.lower().replace(' ', '_')}"

        try:
            # Build appropriate auth header
            headers = await self._build_auth_header(provider, credentials)

            # Get test endpoint for provider
            test_url = self._get_test_endpoint(provider, credentials)

            async with httpx.AsyncClient() as client:
                response = await client.get(test_url, headers=headers, timeout=10.0)

                if response.status_code in [200, 201, 204]:
                    status = ConnectionStatus.CONNECTED
                    success = True
                    error = None
                elif response.status_code == 401:
                    status = ConnectionStatus.AUTH_FAILED
                    success = False
                    error = "Authentication failed"
                else:
                    status = ConnectionStatus.UNKNOWN
                    success = False
                    error = f"HTTP {response.status_code}"

        except Exception as e:
            status = ConnectionStatus.AUTH_FAILED
            success = False
            error = str(e)

        # Update status in database
        if self.db:
            await self.db.execute(
                "UPDATE encrypted_credentials SET status = $1, last_verified = $2 WHERE id = $3",
                status.value, datetime.utcnow(), credential_id
            )

        return {
            "success": success,
            "status": status,
            "error": error,
            "verified_at": datetime.utcnow().isoformat()
        }

    async def _build_auth_header(self, provider: str, credentials: Dict) -> Dict:
        """Build authentication header for provider."""
        provider_lower = provider.lower().replace(" ", "_")

        if provider_lower in ["servicetitan", "jobber"]:
            # OAuth2 - use access token
            access_token = credentials.get("access_token")
            if not access_token:
                # Need to get initial token
                tokens = await self._oauth_authenticate(provider, credentials)
                if tokens:
                    access_token = tokens.access_token
                    # Update cached credentials with token
                    credentials["access_token"] = access_token
                    if tokens.refresh_token:
                        credentials["refresh_token"] = tokens.refresh_token
            return {"Authorization": f"Bearer {access_token}"}

        elif provider_lower == "housecall_pro":
            # API Key in header
            return {"X-API-Key": credentials.get("api_key", "")}

        else:
            # Default to Bearer token
            api_key = credentials.get("api_key", "")
            return {"Authorization": f"Bearer {api_key}"}

    def _get_test_endpoint(self, provider: str, credentials: Dict) -> str:
        """Get test endpoint URL for provider."""
        provider_lower = provider.lower().replace(" ", "_")

        endpoints = {
            "servicetitan": f"https://api.servicetitan.io/settings/v2/tenant/{credentials.get('tenant_id')}/employees",
            "jobber": "https://api.getjobber.com/api/graphql",
            "housecall_pro": "https://api.housecallpro.com/v1/companies/me",
        }

        base_url = credentials.get("base_url", "")
        return endpoints.get(provider_lower, f"{base_url}/health")

    # ========== OAUTH REFRESH LOGIC ==========

    async def _oauth_authenticate(
        self,
        provider: str,
        credentials: Dict
    ) -> Optional[OAuthTokens]:
        """Get initial OAuth tokens using client credentials."""
        provider_lower = provider.lower().replace(" ", "_")

        token_endpoints = {
            "servicetitan": "https://auth.servicetitan.io/connect/token",
            "jobber": "https://api.getjobber.com/api/oauth/token",
        }

        token_url = token_endpoints.get(provider_lower)
        if not token_url:
            return None

        try:
            async with httpx.AsyncClient() as client:
                data = {
                    "grant_type": "client_credentials",
                    "client_id": credentials.get("client_id"),
                    "client_secret": credentials.get("client_secret"),
                }

                if credentials.get("tenant_id"):
                    data["tenant_id"] = credentials.get("tenant_id")

                response = await client.post(token_url, data=data, timeout=10.0)

                if response.status_code == 200:
                    token_data = response.json()
                    return OAuthTokens(
                        access_token=token_data.get("access_token"),
                        refresh_token=token_data.get("refresh_token"),
                        expires_in=token_data.get("expires_in", 3600),
                        token_type=token_data.get("token_type", "Bearer"),
                        scope=token_data.get("scope")
                    )

        except Exception:
            pass

        return None

    async def refresh_oauth_token(
        self,
        company_id: str,
        provider: str
    ) -> Optional[OAuthTokens]:
        """
        Refresh OAuth token using refresh_token.
        Critical for Jobber to maintain long-running audit sessions.
        """
        credentials = await self.get_credentials(company_id, provider)
        if not credentials:
            return None

        refresh_token = credentials.get("refresh_token")
        if not refresh_token:
            # No refresh token - try client credentials
            return await self._oauth_authenticate(provider, credentials)

        provider_lower = provider.lower().replace(" ", "_")

        token_endpoints = {
            "servicetitan": "https://auth.servicetitan.io/connect/token",
            "jobber": "https://api.getjobber.com/api/oauth/token",
        }

        token_url = token_endpoints.get(provider_lower)
        if not token_url:
            return None

        credential_id = f"{company_id}_{provider_lower}"

        # Update status to refreshing
        if self.db:
            await self.db.execute(
                "UPDATE encrypted_credentials SET status = $1 WHERE id = $2",
                ConnectionStatus.REFRESHING.value, credential_id
            )

        try:
            async with httpx.AsyncClient() as client:
                data = {
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": credentials.get("client_id"),
                    "client_secret": credentials.get("client_secret"),
                }

                response = await client.post(token_url, data=data, timeout=10.0)

                if response.status_code == 200:
                    token_data = response.json()
                    tokens = OAuthTokens(
                        access_token=token_data.get("access_token"),
                        refresh_token=token_data.get("refresh_token", refresh_token),
                        expires_in=token_data.get("expires_in", 3600),
                        token_type=token_data.get("token_type", "Bearer"),
                        scope=token_data.get("scope")
                    )

                    # Update stored credentials with new tokens
                    credentials["access_token"] = tokens.access_token
                    if tokens.refresh_token:
                        credentials["refresh_token"] = tokens.refresh_token

                    # Calculate token expiry
                    token_expiry = datetime.utcnow() + timedelta(seconds=tokens.expires_in)

                    # Re-encrypt and store
                    encrypted_data, salt = self._encrypt(credentials)

                    if self.db:
                        await self.db.execute(
                            """UPDATE encrypted_credentials
                               SET encrypted_data = $1, salt = $2,
                                   status = $3, token_expiry = $4, updated_at = $5
                               WHERE id = $6""",
                            encrypted_data, salt, ConnectionStatus.CONNECTED.value,
                            token_expiry, datetime.utcnow(), credential_id
                        )

                    # Update cache
                    self._cache[credential_id] = credentials

                    return tokens

                else:
                    # Refresh failed - mark as auth failed
                    if self.db:
                        await self.db.execute(
                            "UPDATE encrypted_credentials SET status = $1 WHERE id = $2",
                            ConnectionStatus.AUTH_FAILED.value, credential_id
                        )

        except Exception:
            if self.db:
                await self.db.execute(
                    "UPDATE encrypted_credentials SET status = $1 WHERE id = $2",
                    ConnectionStatus.AUTH_FAILED.value, credential_id
                )

        return None

    async def start_token_refresh_loop(
        self,
        company_id: str,
        provider: str,
        refresh_before_expiry_seconds: int = 300
    ):
        """
        Start automatic token refresh loop.
        Ensures tokens are refreshed before expiry during long audits.
        """
        credential_id = f"{company_id}_{provider.lower().replace(' ', '_')}"

        # Cancel existing refresh task if any
        if credential_id in self._refresh_tasks:
            self._refresh_tasks[credential_id].cancel()

        async def refresh_loop():
            while True:
                try:
                    # Get current token expiry
                    if self.db:
                        row = await self.db.fetchrow(
                            "SELECT token_expiry FROM encrypted_credentials WHERE id = $1",
                            credential_id
                        )
                        if row and row["token_expiry"]:
                            expiry = row["token_expiry"]
                            now = datetime.utcnow()

                            # Calculate time until refresh needed
                            refresh_at = expiry - timedelta(seconds=refresh_before_expiry_seconds)
                            sleep_time = (refresh_at - now).total_seconds()

                            if sleep_time > 0:
                                await asyncio.sleep(sleep_time)

                            # Refresh the token
                            await self.refresh_oauth_token(company_id, provider)
                        else:
                            # No expiry set, check every hour
                            await asyncio.sleep(3600)
                    else:
                        await asyncio.sleep(3600)

                except asyncio.CancelledError:
                    break
                except Exception:
                    # On error, retry after 5 minutes
                    await asyncio.sleep(300)

        # Start the refresh loop
        task = asyncio.create_task(refresh_loop())
        self._refresh_tasks[credential_id] = task

        # Mark as scheduled in DB
        if self.db:
            await self.db.execute(
                "UPDATE encrypted_credentials SET refresh_scheduled = true WHERE id = $1",
                credential_id
            )

    def stop_token_refresh_loop(self, company_id: str, provider: str):
        """Stop automatic token refresh loop."""
        credential_id = f"{company_id}_{provider.lower().replace(' ', '_')}"

        if credential_id in self._refresh_tasks:
            self._refresh_tasks[credential_id].cancel()
            del self._refresh_tasks[credential_id]

    # ========== BULK OPERATIONS ==========

    async def get_all_connection_statuses(
        self,
        company_id: str
    ) -> List[Dict]:
        """Get connection status for all providers for a company."""
        if not self.db:
            return []

        rows = await self.db.fetch(
            """SELECT id, provider, status, last_verified, token_expiry
               FROM encrypted_credentials WHERE company_id = $1""",
            company_id
        )

        results = []
        for row in rows:
            status = ConnectionStatus(row["status"])

            # Check for expired token
            if row["token_expiry"] and row["token_expiry"] < datetime.utcnow():
                status = ConnectionStatus.EXPIRED

            status_info = await self.get_connection_status(company_id, row["provider"])
            status_info["last_verified"] = row["last_verified"].isoformat() if row["last_verified"] else None
            results.append(status_info)

        return results


# Database schema for encrypted_credentials table
CREDENTIALS_TABLE_SCHEMA = """
CREATE TABLE IF NOT EXISTS encrypted_credentials (
    id VARCHAR(255) PRIMARY KEY,
    company_id VARCHAR(255) NOT NULL,
    provider VARCHAR(100) NOT NULL,
    credential_type VARCHAR(50) NOT NULL,
    encrypted_data TEXT NOT NULL,
    salt VARCHAR(64) NOT NULL,
    iv VARCHAR(64) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    last_verified TIMESTAMP,
    status VARCHAR(50) NOT NULL DEFAULT 'unknown',
    token_expiry TIMESTAMP,
    refresh_scheduled BOOLEAN DEFAULT FALSE,

    UNIQUE(company_id, provider)
);

CREATE INDEX IF NOT EXISTS idx_credentials_company ON encrypted_credentials(company_id);
CREATE INDEX IF NOT EXISTS idx_credentials_status ON encrypted_credentials(status);
CREATE INDEX IF NOT EXISTS idx_credentials_expiry ON encrypted_credentials(token_expiry) WHERE token_expiry IS NOT NULL;
"""


async def create_credentials_vault(db_connection=None) -> CredentialsVault:
    """
    Create and initialize credentials vault.

    Args:
        db_connection: PostgreSQL connection

    Returns:
        Initialized CredentialsVault
    """
    vault = CredentialsVault(db_connection)

    # Create table if using database
    if db_connection:
        await db_connection.execute(CREDENTIALS_TABLE_SCHEMA)

    return vault
