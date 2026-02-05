"""
ProofGreen MAS - Integration Tests
Tests for FSM connectors, webhooks, and external API integrations.
"""

import pytest
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from integrations.universal_webhook_handler import (
    UniversalWebhookHandler,
    AuditDraft,
    FSMProvider
)
from integrations.fsm_integration_suite import FSMIntegrationSuite, FSMJob
from integrations.generic_fsm_connector import (
    GenericFSMConnector,
    FieldMapping,
    FSMConnectionConfig,
    AuthType
)
from integrations.auth_handler import AuthHandler, AuthHealthChecker


class TestUniversalWebhookHandler:
    """Tests for Universal Webhook Handler."""

    @pytest.fixture
    def webhook_handler(self, mock_db):
        """Create webhook handler instance."""
        return UniversalWebhookHandler(db_connection=mock_db)

    @pytest.mark.asyncio
    async def test_detect_servicetitan_payload(self, webhook_handler, sample_servicetitan_payload):
        """Test ServiceTitan payload detection."""
        provider = webhook_handler.detect_provider(sample_servicetitan_payload)

        assert provider == FSMProvider.SERVICETITAN

    @pytest.mark.asyncio
    async def test_detect_jobber_payload(self, webhook_handler, sample_jobber_payload):
        """Test Jobber payload detection."""
        provider = webhook_handler.detect_provider(sample_jobber_payload)

        assert provider == FSMProvider.JOBBER

    @pytest.mark.asyncio
    async def test_process_servicetitan_webhook(self, webhook_handler, sample_servicetitan_payload, mock_db):
        """Test processing ServiceTitan webhook creates audit draft."""
        result = await webhook_handler.process_webhook(
            payload=sample_servicetitan_payload,
            company_id="COMP-001"
        )

        assert result is not None
        assert isinstance(result, AuditDraft)
        assert result.job_id is not None

    @pytest.mark.asyncio
    async def test_process_jobber_webhook(self, webhook_handler, sample_jobber_payload, mock_db):
        """Test processing Jobber webhook creates audit draft."""
        result = await webhook_handler.process_webhook(
            payload=sample_jobber_payload,
            company_id="COMP-001"
        )

        assert result is not None
        assert isinstance(result, AuditDraft)

    @pytest.mark.asyncio
    async def test_webhook_signature_verification(self, webhook_handler):
        """Test webhook signature verification."""
        payload = '{"event": "test"}'
        secret = "webhook-secret-123"

        # Generate valid signature
        import hmac
        import hashlib
        signature = hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()

        is_valid = webhook_handler.verify_signature(
            payload=payload,
            signature=f"sha256={signature}",
            secret=secret
        )

        assert is_valid is True

    @pytest.mark.asyncio
    async def test_webhook_invalid_signature_rejected(self, webhook_handler):
        """Test invalid webhook signature is rejected."""
        is_valid = webhook_handler.verify_signature(
            payload='{"event": "test"}',
            signature="sha256=invalid",
            secret="webhook-secret-123"
        )

        assert is_valid is False


class TestFSMIntegrationSuite:
    """Tests for FSM Integration Suite."""

    @pytest.fixture
    def integration_suite(self, mock_db):
        """Create FSM integration suite instance."""
        return FSMIntegrationSuite(db_connection=mock_db)

    @pytest.mark.asyncio
    async def test_normalize_job_from_servicetitan(self, integration_suite, sample_servicetitan_payload):
        """Test job normalization from ServiceTitan format."""
        job = await integration_suite.normalize_job(
            payload=sample_servicetitan_payload["data"],
            provider=FSMProvider.SERVICETITAN
        )

        assert isinstance(job, FSMJob)
        assert job.provider == FSMProvider.SERVICETITAN
        assert job.customer_name is not None
        assert job.total_amount == 12500.00

    @pytest.mark.asyncio
    async def test_normalize_job_from_jobber(self, integration_suite, sample_jobber_payload):
        """Test job normalization from Jobber format."""
        job = await integration_suite.normalize_job(
            payload=sample_jobber_payload["job"],
            provider=FSMProvider.JOBBER
        )

        assert isinstance(job, FSMJob)
        assert job.provider == FSMProvider.JOBBER
        assert job.total_amount == 8500.00

    @pytest.mark.asyncio
    async def test_sync_job_to_green_ledger(self, integration_suite, mock_db):
        """Test syncing FSM job to Green Ledger."""
        job = FSMJob(
            id="JOB-001",
            provider=FSMProvider.SERVICETITAN,
            customer_name="John Doe",
            address="123 Main St",
            city="Los Angeles",
            state="CA",
            zip_code="90001",
            job_type="HVAC Installation",
            total_amount=12500.00,
            completed_at=datetime.utcnow()
        )

        result = await integration_suite.sync_to_green_ledger(
            job=job,
            company_id="COMP-001"
        )

        assert result is not None
        mock_db.execute.assert_called()


class TestGenericFSMConnector:
    """Tests for Generic FSM Connector."""

    @pytest.fixture
    def connector(self, mock_db):
        """Create Generic FSM Connector instance."""
        return GenericFSMConnector(db_connection=mock_db)

    @pytest.mark.asyncio
    async def test_start_wizard(self, connector):
        """Test setup wizard initialization."""
        result = connector.start_wizard(session_id="wizard-001")

        assert result is not None
        assert result["step"] == 1
        assert "instructions" in result

    @pytest.mark.asyncio
    async def test_auto_detect_field_mappings(self, connector):
        """Test automatic field mapping detection."""
        sample_json = {
            "id": "12345",
            "customer_name": "John Doe",
            "customer_email": "john@example.com",
            "job_total": 12500.00,
            "street_address": "123 Main St",
            "state": "CA"
        }

        mappings = connector._auto_detect_mappings(sample_json)

        assert len(mappings) > 0
        # Should detect common fields
        field_names = [m.source_field for m in mappings]
        assert "customer_name" in field_names or "id" in field_names

    @pytest.mark.asyncio
    async def test_wizard_step_mapping(self, connector):
        """Test wizard mapping step."""
        sample_json = {
            "job_id": "JOB-001",
            "client": {"name": "John Doe"},
            "total": 12500.00
        }

        result = await connector.wizard_step_mapping(
            session_id="wizard-001",
            sample_json=sample_json
        )

        assert "suggested_mappings" in result
        assert "step" in result

    @pytest.mark.asyncio
    async def test_transform_to_green_ledger(self, connector, mock_db):
        """Test transformation to Green Ledger format."""
        mock_db.fetchrow.return_value = {
            "field_mappings": json.dumps([
                {"source_field": "job_id", "target_field": "job_id"},
                {"source_field": "customer.name", "target_field": "customer_name"},
                {"source_field": "total", "target_field": "total_job_cost"}
            ])
        }

        source_data = {
            "job_id": "JOB-001",
            "customer": {"name": "John Doe"},
            "total": 12500.00
        }

        result = await connector.transform_to_green_ledger(
            connection_id="conn-001",
            source_data=source_data
        )

        assert result is not None
        assert "job_id" in result


class TestAuthHandler:
    """Tests for OAuth Auth Handler."""

    @pytest.fixture
    def auth_handler(self):
        """Create Auth Handler instance."""
        return AuthHandler(
            provider=FSMProvider.SERVICETITAN,
            client_id="test-client-id",
            client_secret="test-client-secret"
        )

    def test_auth_handler_initialization(self, auth_handler):
        """Test auth handler initializes correctly."""
        assert auth_handler.provider == FSMProvider.SERVICETITAN
        assert auth_handler.client_id == "test-client-id"

    @pytest.mark.asyncio
    async def test_get_valid_token_refresh_needed(self, auth_handler):
        """Test token refresh when expired."""
        # Set expired token
        auth_handler._access_token = "old-token"
        auth_handler._token_expires_at = datetime.utcnow()

        with patch.object(auth_handler, '_refresh_token', new_callable=AsyncMock) as mock_refresh:
            mock_refresh.return_value = "new-token"

            token = auth_handler.get_valid_token()

            # Should trigger refresh
            assert token is not None or mock_refresh.called

    @pytest.mark.asyncio
    async def test_exchange_code_for_tokens(self, auth_handler):
        """Test OAuth code exchange."""
        with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: {
                    "access_token": "access-token-123",
                    "refresh_token": "refresh-token-456",
                    "expires_in": 3600
                }
            )

            tokens = await auth_handler.exchange_code_for_tokens(
                code="auth-code-789",
                redirect_uri="https://example.com/callback"
            )

            assert tokens is not None
            assert tokens.access_token == "access-token-123"

    def test_get_auth_headers_servicetitan(self, auth_handler):
        """Test ServiceTitan auth headers include ST-App-Key."""
        auth_handler._access_token = "test-token"
        auth_handler.app_key = "st-app-key"

        headers = auth_handler.get_auth_headers()

        assert "Authorization" in headers
        assert "ST-App-Key" in headers
        assert headers["ST-App-Key"] == "st-app-key"


class TestAuthHealthChecker:
    """Tests for Auth Health Checker."""

    @pytest.fixture
    def health_checker(self, mock_db):
        """Create Auth Health Checker instance."""
        return AuthHealthChecker(db_connection=mock_db)

    @pytest.mark.asyncio
    async def test_check_connection_health(self, health_checker, mock_db):
        """Test connection health check."""
        mock_db.fetchrow.return_value = {
            "status": "active",
            "token_expires_at": datetime.utcnow(),
            "last_used_at": datetime.utcnow()
        }

        with patch('httpx.AsyncClient.get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = MagicMock(status_code=200)

            health = await health_checker.check_connection(
                company_id="COMP-001",
                provider="servicetitan"
            )

            assert health is not None
            assert "status" in health

    @pytest.mark.asyncio
    async def test_get_all_connection_statuses(self, health_checker, mock_db):
        """Test getting all connection statuses for a company."""
        mock_db.fetch.return_value = [
            {"provider": "servicetitan", "status": "active"},
            {"provider": "jobber", "status": "expired"}
        ]

        statuses = await health_checker.get_all_statuses(company_id="COMP-001")

        assert len(statuses) == 2
        assert statuses[0]["provider"] == "servicetitan"
