"""
ProofGreen MAS - Autonomous Auth Handler
Unified OAuth token management for ServiceTitan, Jobber, and Housecall Pro.
"""

import os
import time
import asyncio
from threading import Lock
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import httpx

from config.settings import settings


class FSMProvider(str, Enum):
    """Supported FSM providers."""
    SERVICETITAN = "SERVICETITAN"
    JOBBER = "JOBBER"
    HOUSECALL_PRO = "HOUSECALL_PRO"


@dataclass
class TokenSet:
    """OAuth token set."""
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_at: float = 0
    token_type: str = "Bearer"
    scope: Optional[str] = None


class AuthHandler:
    """
    Unified OAuth handler for FSM providers.
    Manages the "OAuth Dance," secure token storage, and automatic refreshing.
    """

    # Token endpoint URLs for each provider
    TOKEN_URLS = {
        FSMProvider.SERVICETITAN: "https://auth.servicetitan.io/connect/token",
        FSMProvider.JOBBER: "https://api.getjobber.com/api/oauth/token",
        FSMProvider.HOUSECALL_PRO: "https://api.housecallpro.com/oauth/token"
    }

    # Authorization URLs for initial OAuth flow
    AUTH_URLS = {
        FSMProvider.SERVICETITAN: "https://auth.servicetitan.io/connect/authorize",
        FSMProvider.JOBBER: "https://api.getjobber.com/api/oauth/authorize",
        FSMProvider.HOUSECALL_PRO: "https://api.housecallpro.com/oauth/authorize"
    }

    # Default scopes for each provider
    DEFAULT_SCOPES = {
        FSMProvider.SERVICETITAN: "jobs:read jobs:write customers:read equipment:read",
        FSMProvider.JOBBER: "read:jobs write:jobs read:clients read:invoices",
        FSMProvider.HOUSECALL_PRO: "jobs.read jobs.write customers.read"
    }

    def __init__(
        self,
        provider: str,
        credentials_vault=None,
        company_id: Optional[str] = None
    ):
        """
        Initialize AuthHandler.

        Args:
            provider: FSM provider name (SERVICETITAN, JOBBER, HOUSECALL_PRO)
            credentials_vault: CredentialsVault for secure storage
            company_id: Company identifier for multi-tenant support
        """
        self.provider = FSMProvider(provider.upper())
        self.vault = credentials_vault
        self.company_id = company_id or "default"
        self.lock = Lock()

        # In-memory token cache
        self.tokens = TokenSet()

        # Load credentials from environment
        self.client_id = os.getenv(f"{provider}_CLIENT_ID") or getattr(settings, f"{provider}_CLIENT_ID", None)
        self.client_secret = os.getenv(f"{provider}_CLIENT_SECRET") or getattr(settings, f"{provider}_CLIENT_SECRET", None)
        self.app_key = os.getenv(f"{provider}_APP_KEY")  # ServiceTitan specific

        # Token URL
        self.token_url = self.TOKEN_URLS.get(self.provider)

        # Refresh buffer (5 minutes before expiry)
        self.refresh_buffer_seconds = 300

    # ========== TOKEN MANAGEMENT ==========

    def get_valid_token(self) -> str:
        """
        Ensures the agent always has a fresh token.
        Thread-safe with automatic refresh.

        Returns:
            Valid access token
        """
        with self.lock:
            # Check if token needs refresh (5 min buffer)
            if time.time() > (self.tokens.expires_at - self.refresh_buffer_seconds):
                self._refresh_token_sequence()
            return self.tokens.access_token

    async def get_valid_token_async(self) -> str:
        """
        Async version of get_valid_token.

        Returns:
            Valid access token
        """
        # Check if token needs refresh
        if time.time() > (self.tokens.expires_at - self.refresh_buffer_seconds):
            await self._refresh_token_sequence_async()
        return self.tokens.access_token

    def _refresh_token_sequence(self):
        """Synchronous token refresh."""
        import requests

        print(f"Refreshing {self.provider.value} credentials...")

        payload = self._build_token_payload()

        response = requests.post(
            self.token_url,
            data=payload,
            timeout=30
        )

        if response.status_code == 200:
            self._process_token_response(response.json())
        else:
            raise Exception(f"Failed to refresh {self.provider.value} token: {response.text}")

    async def _refresh_token_sequence_async(self):
        """Asynchronous token refresh."""
        print(f"Refreshing {self.provider.value} credentials...")

        payload = self._build_token_payload()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data=payload,
                timeout=30.0
            )

            if response.status_code == 200:
                self._process_token_response(response.json())
            else:
                raise Exception(f"Failed to refresh {self.provider.value} token: {response.text}")

    def _build_token_payload(self) -> Dict:
        """Build the token request payload based on provider and state."""
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        # Use refresh token if available
        if self.tokens.refresh_token:
            payload["grant_type"] = "refresh_token"
            payload["refresh_token"] = self.tokens.refresh_token
        else:
            # ServiceTitan: Client Credentials for machine-to-machine
            if self.provider == FSMProvider.SERVICETITAN:
                payload["grant_type"] = "client_credentials"
            else:
                # Other providers need initial authorization
                raise Exception(
                    f"No refresh token for {self.provider.value}. "
                    "Complete initial OAuth authorization first."
                )

        return payload

    def _process_token_response(self, data: Dict):
        """Process token response and update state."""
        self.tokens.access_token = data["access_token"]
        # Refresh tokens may be rotated
        self.tokens.refresh_token = data.get("refresh_token", self.tokens.refresh_token)
        self.tokens.expires_at = time.time() + data.get("expires_in", 3600)
        self.tokens.token_type = data.get("token_type", "Bearer")
        self.tokens.scope = data.get("scope")

        # Persist to vault
        self._save_to_vault()

    # ========== INITIAL AUTHORIZATION ==========

    def generate_auth_url(
        self,
        redirect_uri: str,
        scopes: Optional[str] = None,
        state: Optional[str] = None
    ) -> str:
        """
        Generate OAuth Authorization URL for initial handshake.

        Args:
            redirect_uri: Where to redirect after authorization
            scopes: Space-separated scopes (uses defaults if not provided)
            state: CSRF protection state parameter

        Returns:
            Authorization URL for user to visit
        """
        import urllib.parse

        auth_url = self.AUTH_URLS.get(self.provider)
        if not auth_url:
            raise ValueError(f"No auth URL for provider {self.provider.value}")

        scopes = scopes or self.DEFAULT_SCOPES.get(self.provider, "")

        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": scopes,
        }

        if state:
            params["state"] = state

        # Provider-specific parameters
        if self.provider == FSMProvider.SERVICETITAN:
            params["tenant_id"] = os.getenv("SERVICETITAN_TENANT_ID", "")

        return f"{auth_url}?{urllib.parse.urlencode(params)}"

    async def exchange_code_for_tokens(
        self,
        code: str,
        redirect_uri: str
    ) -> TokenSet:
        """
        Exchange authorization code for tokens.

        Args:
            code: Authorization code from redirect
            redirect_uri: Same redirect_uri used in auth request

        Returns:
            TokenSet with access and refresh tokens
        """
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data=payload,
                timeout=30.0
            )

            if response.status_code == 200:
                self._process_token_response(response.json())
                return self.tokens
            else:
                raise Exception(f"Failed to exchange code: {response.text}")

    # ========== VAULT INTEGRATION ==========

    def _save_to_vault(self):
        """Save tokens to encrypted credentials vault."""
        if self.vault:
            asyncio.create_task(self._save_to_vault_async())
        # Also update in-memory for immediate use

    async def _save_to_vault_async(self):
        """Async save to vault."""
        if self.vault:
            await self.vault.store_credentials(
                company_id=self.company_id,
                provider=self.provider.value.lower(),
                credentials={
                    "access_token": self.tokens.access_token,
                    "refresh_token": self.tokens.refresh_token,
                    "expires_at": self.tokens.expires_at,
                    "token_type": self.tokens.token_type,
                    "scope": self.tokens.scope,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                auth_type="oauth2"
            )

    async def load_from_vault(self) -> bool:
        """
        Load tokens from vault on startup.

        Returns:
            True if tokens were loaded successfully
        """
        if not self.vault:
            return False

        credentials = await self.vault.get_credentials(
            self.company_id,
            self.provider.value.lower()
        )

        if credentials:
            self.tokens.access_token = credentials.get("access_token")
            self.tokens.refresh_token = credentials.get("refresh_token")
            self.tokens.expires_at = credentials.get("expires_at", 0)
            self.tokens.token_type = credentials.get("token_type", "Bearer")
            self.tokens.scope = credentials.get("scope")
            return True

        return False

    # ========== REQUEST HELPERS ==========

    def get_auth_headers(self) -> Dict[str, str]:
        """
        Get authorization headers for API requests.

        Returns:
            Headers dict with Authorization and provider-specific headers
        """
        headers = {
            "Authorization": f"{self.tokens.token_type} {self.get_valid_token()}",
            "Content-Type": "application/json",
        }

        # ServiceTitan requires App Key
        if self.provider == FSMProvider.SERVICETITAN and self.app_key:
            headers["ST-App-Key"] = self.app_key

        return headers

    async def get_auth_headers_async(self) -> Dict[str, str]:
        """Async version of get_auth_headers."""
        token = await self.get_valid_token_async()
        headers = {
            "Authorization": f"{self.tokens.token_type} {token}",
            "Content-Type": "application/json",
        }

        if self.provider == FSMProvider.SERVICETITAN and self.app_key:
            headers["ST-App-Key"] = self.app_key

        return headers

    async def make_authenticated_request(
        self,
        method: str,
        url: str,
        **kwargs
    ) -> httpx.Response:
        """
        Make an authenticated API request.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            **kwargs: Additional httpx request arguments

        Returns:
            httpx.Response
        """
        headers = await self.get_auth_headers_async()
        kwargs_headers = kwargs.pop("headers", {})
        headers.update(kwargs_headers)

        async with httpx.AsyncClient() as client:
            response = await client.request(
                method,
                url,
                headers=headers,
                **kwargs
            )

            # Handle token expiration
            if response.status_code == 401:
                # Force refresh and retry
                await self._refresh_token_sequence_async()
                headers = await self.get_auth_headers_async()
                response = await client.request(
                    method,
                    url,
                    headers=headers,
                    **kwargs
                )

            return response


class AuthHealthChecker:
    """
    Background health checker for OAuth tokens.
    Ensures tokens stay fresh across all providers.
    """

    def __init__(self, auth_handlers: Dict[str, AuthHandler]):
        """
        Initialize health checker.

        Args:
            auth_handlers: Dict of company_id -> AuthHandler
        """
        self.handlers = auth_handlers
        self._running = False
        self._task = None

    async def start(self, interval_seconds: int = 3600):
        """
        Start the health check loop.

        Args:
            interval_seconds: Check interval (default 1 hour)
        """
        self._running = True
        self._task = asyncio.create_task(self._health_loop(interval_seconds))

    async def stop(self):
        """Stop the health check loop."""
        self._running = False
        if self._task:
            self._task.cancel()

    async def _health_loop(self, interval: int):
        """Main health check loop."""
        while self._running:
            for company_id, handler in self.handlers.items():
                try:
                    # This will refresh if needed
                    await handler.get_valid_token_async()
                    print(f"[AuthHealth] {company_id}/{handler.provider.value}: Token valid")
                except Exception as e:
                    print(f"[AuthHealth] {company_id}/{handler.provider.value}: Error - {e}")

            await asyncio.sleep(interval)


# Factory function for creating auth handlers
def create_auth_handler(
    provider: str,
    company_id: str = "default",
    credentials_vault=None
) -> AuthHandler:
    """
    Create an AuthHandler for a provider.

    Args:
        provider: Provider name
        company_id: Company identifier
        credentials_vault: Optional vault for secure storage

    Returns:
        Configured AuthHandler
    """
    handler = AuthHandler(
        provider=provider,
        credentials_vault=credentials_vault,
        company_id=company_id
    )

    # Try to load existing tokens from vault
    if credentials_vault:
        asyncio.create_task(handler.load_from_vault())

    return handler
