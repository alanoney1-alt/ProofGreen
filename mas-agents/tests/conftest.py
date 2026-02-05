"""
ProofGreen MAS - Pytest Configuration & Fixtures
"""

import asyncio
import os
from datetime import datetime
from typing import AsyncGenerator, Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient


# Set test environment
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/proofgreen_test"
os.environ["REDIS_URL"] = "redis://localhost:6379/1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"
os.environ["ENCRYPTION_KEY"] = "test-encryption-key-32-bytes!!"
os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-key"


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_db():
    """Mock PostgreSQL database connection."""
    db = AsyncMock()
    db.execute = AsyncMock(return_value=None)
    db.fetch = AsyncMock(return_value=[])
    db.fetchrow = AsyncMock(return_value=None)
    db.fetchval = AsyncMock(return_value=None)
    return db


@pytest.fixture
def mock_redis():
    """Mock Redis connection."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=True)
    redis.expire = AsyncMock(return_value=True)
    return redis


@pytest.fixture
def mock_anthropic():
    """Mock Anthropic API client."""
    with patch("anthropic.Anthropic") as mock:
        client = MagicMock()
        client.messages.create = MagicMock(return_value=MagicMock(
            content=[MagicMock(text="Test AI response")]
        ))
        mock.return_value = client
        yield client


@pytest.fixture
def sample_job_data() -> Dict[str, Any]:
    """Sample HVAC job data for testing."""
    return {
        "job_id": "JOB-2026-001",
        "company_id": "COMP-001",
        "customer": {
            "name": "John Doe",
            "address": "123 Main St",
            "city": "Los Angeles",
            "state": "CA",
            "zip": "90001",
            "phone": "555-123-4567",
            "email": "john@example.com"
        },
        "equipment": {
            "old": {
                "type": "Split System AC",
                "model": "Carrier 24ACC636A003",
                "refrigerant": "R-410A",
                "seer": 14.0,
                "age_years": 15
            },
            "new": {
                "type": "Heat Pump",
                "model": "Carrier 25VNA036A003",
                "refrigerant": "R-454B",
                "seer": 20.5,
                "hspf": 10.0
            }
        },
        "job_cost": 12500.00,
        "created_at": datetime.utcnow().isoformat()
    }


@pytest.fixture
def sample_servicetitan_payload() -> Dict[str, Any]:
    """Sample ServiceTitan webhook payload."""
    return {
        "eventType": "job.completed",
        "timestamp": datetime.utcnow().isoformat(),
        "data": {
            "id": 12345,
            "number": "JOB-2026-001",
            "status": "Completed",
            "customer": {
                "id": 67890,
                "name": "John Doe",
                "address": {
                    "street": "123 Main St",
                    "city": "Los Angeles",
                    "state": "CA",
                    "zip": "90001"
                }
            },
            "location": {
                "id": 11111,
                "address": {
                    "street": "123 Main St",
                    "city": "Los Angeles",
                    "state": "CA",
                    "zip": "90001"
                }
            },
            "jobType": {
                "name": "HVAC Installation"
            },
            "total": 12500.00,
            "completedOn": datetime.utcnow().isoformat()
        }
    }


@pytest.fixture
def sample_jobber_payload() -> Dict[str, Any]:
    """Sample Jobber webhook payload."""
    return {
        "event": "job_completed",
        "occurred_at": datetime.utcnow().isoformat(),
        "job": {
            "id": "abc123",
            "job_number": "JOB-2026-002",
            "status": "completed",
            "client": {
                "id": "client456",
                "first_name": "Jane",
                "last_name": "Smith",
                "email": "jane@example.com"
            },
            "property": {
                "address": {
                    "street1": "456 Oak Ave",
                    "city": "San Francisco",
                    "state_province": "CA",
                    "postal_code": "94102"
                }
            },
            "total": 8500.00
        }
    }


@pytest.fixture
def sample_workflow_state() -> Dict[str, Any]:
    """Sample workflow state for LangGraph tests."""
    return {
        "job_id": "JOB-2026-001",
        "company_id": "COMP-001",
        "current_node": "vision_audit",
        "status": "in_progress",
        "equipment_analysis": None,
        "compliance_check": None,
        "incentives_calculated": None,
        "proposal_drafted": None,
        "human_approved": None,
        "errors": [],
        "metadata": {
            "started_at": datetime.utcnow().isoformat(),
            "thread_id": "thread-001"
        }
    }


@pytest.fixture
def sample_equipment_image_analysis() -> Dict[str, Any]:
    """Sample equipment analysis result from Claude Vision."""
    return {
        "manufacturer": "Carrier",
        "model_number": "24ACC636A003",
        "serial_number": "1234567890",
        "equipment_type": "Split System AC",
        "refrigerant": "R-410A",
        "seer_rating": 14.0,
        "manufacture_date": "2010-06",
        "tonnage": 3.0,
        "confidence": 0.92,
        "compliance": {
            "epa_aim_compliant": False,
            "seer2_compliant": False,
            "issues": [
                "R-410A phase-out by 2025 - replacement recommended",
                "SEER 14 below minimum 15 SEER2 for Southern region"
            ]
        }
    }


@pytest.fixture
def sample_incentive_calculation() -> Dict[str, Any]:
    """Sample incentive calculation result."""
    return {
        "federal_rebate": 2000.00,
        "state_rebate": 1500.00,
        "utility_rebate": 750.00,
        "total_incentives": 4250.00,
        "customer_net_cost": 8250.00,
        "programs": [
            {
                "name": "IRA 25C Tax Credit",
                "amount": 2000.00,
                "type": "federal",
                "requirements": "Must be primary residence"
            },
            {
                "name": "CA TECH Clean Energy",
                "amount": 1500.00,
                "type": "state",
                "requirements": "Income-qualified"
            },
            {
                "name": "LADWP Heat Pump Rebate",
                "amount": 750.00,
                "type": "utility",
                "requirements": "Must be LADWP customer"
            }
        ],
        "co2_avoided_lbs": 4500.0,
        "kwh_saved_annual": 2200.0
    }


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Create async HTTP client for API testing."""
    from app.main import app  # Import here to avoid circular imports

    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client
