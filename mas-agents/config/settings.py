"""
ProofGreen MAS Configuration Settings
"""

from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "ProofGreen MAS"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"

    # API Keys
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: Optional[str] = None
    PINECONE_API_KEY: str = ""
    TAVILY_API_KEY: Optional[str] = None
    WATTTIME_API_KEY: Optional[str] = None
    WATTTIME_USERNAME: Optional[str] = None
    WATTTIME_PASSWORD: Optional[str] = None
    REWIRING_AMERICA_API_KEY: Optional[str] = None
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_PHONE_NUMBER: Optional[str] = None

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://localhost/proofgreen_mas"
    SUPABASE_URL: Optional[str] = None
    SUPABASE_SERVICE_KEY: Optional[str] = None

    # Vector Database
    PINECONE_ENVIRONMENT: str = "us-east-1"
    PINECONE_INDEX_NAME: str = "esg-regulations"

    # FSM Integration
    SERVICETITAN_API_KEY: Optional[str] = None
    SERVICETITAN_TENANT_ID: Optional[str] = None
    JOBBER_API_KEY: Optional[str] = None
    HOUSECALL_PRO_API_KEY: Optional[str] = None

    # Node.js Backend Integration
    NODEJS_BACKEND_URL: str = "http://localhost:3001"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4

    # CORS
    ALLOWED_ORIGINS: list = ["http://localhost:5173", "http://localhost:3000"]

    # Regulatory Defaults
    DEFAULT_REPORTING_STANDARD: str = "CA_SB_253"
    FUTURE_PROOF_MODE: bool = True

    # Agent Configuration
    AGENT_MODEL: str = "claude-sonnet-4-20250514"
    AGENT_TEMPERATURE: float = 0.1
    AGENT_MAX_TOKENS: int = 4096
    VISION_MODEL: str = "claude-sonnet-4-20250514"

    # Knowledge Base
    KNOWLEDGE_UPDATE_INTERVAL_HOURS: int = 168  # Weekly
    AUTO_SCOUT_ENABLED: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()


# State abbreviation to region mapping for SEER2 standards
CLIMATE_REGIONS = {
    "north": [
        "AK", "CT", "ID", "IL", "IN", "IA", "KS", "ME", "MA", "MI", "MN",
        "MO", "MT", "NE", "NH", "NJ", "NY", "ND", "OH", "OR", "PA", "RI",
        "SD", "VT", "WA", "WI", "WY"
    ],
    "south": [
        "AL", "AR", "DE", "FL", "GA", "KY", "LA", "MD", "MS", "NC", "OK",
        "SC", "TN", "TX", "VA", "WV"
    ],
    "southwest": [
        "AZ", "CA", "CO", "HI", "NV", "NM", "UT"
    ]
}


def get_climate_region(state_code: str) -> str:
    """Get climate region for SEER2 compliance based on state."""
    state_upper = state_code.upper()
    for region, states in CLIMATE_REGIONS.items():
        if state_upper in states:
            return region
    return "north"  # Default to most restrictive


def get_seer2_minimum(state_code: str) -> float:
    """Get minimum SEER2 requirement based on state."""
    region = get_climate_region(state_code)
    if region == "north":
        return 14.3
    return 15.0  # South and Southwest
