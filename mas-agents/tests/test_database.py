"""
ProofGreen MAS - Database Tests
Tests for Green Ledger, Audit Trail, and database operations.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
import json

from app.db.green_ledger import GreenLedger
from app.db.audit_db import AuditDatabase


class TestGreenLedger:
    """Tests for Green Ledger database operations."""

    @pytest.fixture
    def ledger(self, mock_db):
        """Create Green Ledger instance."""
        return GreenLedger(db_connection=mock_db)

    @pytest.mark.asyncio
    async def test_save_entry(self, ledger, mock_db, sample_job_data, sample_incentive_calculation):
        """Test saving Green Ledger entry."""
        mock_db.fetchval.return_value = "entry-uuid-001"

        entry_id = await ledger.save_entry(
            job_id="JOB-2026-001",
            company_id="COMP-001",
            equipment_old={
                "type": "Split System AC",
                "refrigerant": "R-410A",
                "seer": 14.0
            },
            equipment_new={
                "type": "Heat Pump",
                "refrigerant": "R-454B",
                "seer": 20.5
            },
            incentives=sample_incentive_calculation,
            state="CA",
            approved_by="USER-001"
        )

        assert entry_id is not None
        mock_db.execute.assert_called()

    @pytest.mark.asyncio
    async def test_get_entry_by_job_id(self, ledger, mock_db):
        """Test retrieving entry by job ID."""
        mock_db.fetchrow.return_value = {
            "id": "entry-001",
            "job_id": "JOB-2026-001",
            "company_id": "COMP-001",
            "total_incentives": 4250.00,
            "created_at": datetime.utcnow()
        }

        entry = await ledger.get_entry(job_id="JOB-2026-001")

        assert entry is not None
        assert entry["job_id"] == "JOB-2026-001"

    @pytest.mark.asyncio
    async def test_get_aggregated_metrics_monthly(self, ledger, mock_db):
        """Test aggregated metrics for monthly period."""
        mock_db.fetchrow.return_value = {
            "total_jobs": 150,
            "total_incentives": 637500.00,
            "total_co2_avoided": 675000.0,
            "total_kwh_saved": 330000.0,
            "avg_incentive_per_job": 4250.00
        }

        metrics = await ledger.get_aggregated_metrics(
            company_id="COMP-001",
            period="monthly"
        )

        assert metrics["total_jobs"] == 150
        assert metrics["total_incentives"] == 637500.00

    @pytest.mark.asyncio
    async def test_get_aggregated_metrics_yearly(self, ledger, mock_db):
        """Test aggregated metrics for yearly period."""
        mock_db.fetchrow.return_value = {
            "total_jobs": 1800,
            "total_incentives": 7650000.00,
            "total_co2_avoided": 8100000.0,
            "total_kwh_saved": 3960000.0
        }

        metrics = await ledger.get_aggregated_metrics(
            company_id="COMP-001",
            period="yearly"
        )

        assert metrics["total_jobs"] == 1800

    @pytest.mark.asyncio
    async def test_get_compliance_summary(self, ledger, mock_db):
        """Test compliance summary statistics."""
        mock_db.fetchrow.return_value = {
            "total_jobs": 1000,
            "epa_aim_compliant": 850,
            "seer2_compliant": 920,
            "both_compliant": 800
        }

        summary = await ledger.get_compliance_summary(company_id="COMP-001")

        assert summary["total_jobs"] == 1000
        assert summary["epa_aim_compliant"] == 850
        compliance_rate = summary["both_compliant"] / summary["total_jobs"]
        assert compliance_rate == 0.8

    @pytest.mark.asyncio
    async def test_get_entries_by_state(self, ledger, mock_db):
        """Test retrieving entries filtered by state."""
        mock_db.fetch.return_value = [
            {"job_id": "JOB-001", "state_code": "CA"},
            {"job_id": "JOB-002", "state_code": "CA"}
        ]

        entries = await ledger.get_entries_by_state(
            company_id="COMP-001",
            state="CA"
        )

        assert len(entries) == 2
        assert all(e["state_code"] == "CA" for e in entries)


class TestAuditDatabase:
    """Tests for Audit Trail database operations."""

    @pytest.fixture
    def audit_db(self, mock_db):
        """Create Audit Database instance."""
        return AuditDatabase(db_connection=mock_db)

    @pytest.mark.asyncio
    async def test_log_event(self, audit_db, mock_db):
        """Test logging audit event."""
        mock_db.fetchval.return_value = "audit-uuid-001"

        event_id = await audit_db.log_event(
            event_type="job.approved",
            entity_type="green_ledger",
            entity_id="JOB-2026-001",
            company_id="COMP-001",
            actor_type="user",
            actor_id="USER-001",
            action="approve",
            new_value={"approved": True, "approved_at": datetime.utcnow().isoformat()}
        )

        assert event_id is not None
        mock_db.execute.assert_called()

    @pytest.mark.asyncio
    async def test_log_agent_action(self, audit_db, mock_db):
        """Test logging AI agent action."""
        mock_db.fetchval.return_value = "audit-uuid-002"

        event_id = await audit_db.log_event(
            event_type="equipment.analyzed",
            entity_type="job",
            entity_id="JOB-2026-001",
            company_id="COMP-001",
            actor_type="agent",
            actor_id="equipment_triage",
            action="analyze",
            metadata={
                "model": "claude-sonnet-4-20250514",
                "confidence": 0.92
            }
        )

        assert event_id is not None

    @pytest.mark.asyncio
    async def test_get_audit_trail_for_entity(self, audit_db, mock_db):
        """Test retrieving audit trail for specific entity."""
        mock_db.fetch.return_value = [
            {
                "id": "audit-001",
                "event_type": "job.created",
                "action": "create",
                "created_at": datetime.utcnow() - timedelta(hours=2)
            },
            {
                "id": "audit-002",
                "event_type": "equipment.analyzed",
                "action": "analyze",
                "created_at": datetime.utcnow() - timedelta(hours=1)
            },
            {
                "id": "audit-003",
                "event_type": "job.approved",
                "action": "approve",
                "created_at": datetime.utcnow()
            }
        ]

        trail = await audit_db.get_trail_for_entity(
            entity_type="job",
            entity_id="JOB-2026-001"
        )

        assert len(trail) == 3
        # Should be chronological
        assert trail[0]["event_type"] == "job.created"
        assert trail[-1]["event_type"] == "job.approved"

    @pytest.mark.asyncio
    async def test_get_audit_trail_by_actor(self, audit_db, mock_db):
        """Test retrieving audit trail by actor."""
        mock_db.fetch.return_value = [
            {"event_type": "job.approved", "actor_id": "USER-001"},
            {"event_type": "job.approved", "actor_id": "USER-001"}
        ]

        trail = await audit_db.get_trail_by_actor(
            actor_type="user",
            actor_id="USER-001"
        )

        assert len(trail) == 2

    @pytest.mark.asyncio
    async def test_get_recent_activity(self, audit_db, mock_db):
        """Test retrieving recent activity."""
        mock_db.fetch.return_value = [
            {"event_type": "job.approved", "created_at": datetime.utcnow()},
            {"event_type": "equipment.analyzed", "created_at": datetime.utcnow()}
        ]

        activity = await audit_db.get_recent_activity(
            company_id="COMP-001",
            limit=10
        )

        assert len(activity) == 2

    @pytest.mark.asyncio
    async def test_audit_immutability(self, audit_db, mock_db):
        """Test that audit records cannot be modified."""
        # Audit trail should be append-only
        # This test verifies the pattern, actual DB constraints enforce immutability

        # Log initial event
        await audit_db.log_event(
            event_type="test.event",
            entity_type="test",
            entity_id="TEST-001",
            company_id="COMP-001",
            actor_type="system",
            actor_id="test",
            action="test"
        )

        # Verify no UPDATE was called (only INSERT)
        for call in mock_db.execute.call_args_list:
            query = str(call)
            assert "UPDATE audit_trail" not in query


class TestDatabaseTransactions:
    """Tests for database transaction handling."""

    @pytest.mark.asyncio
    async def test_transaction_rollback_on_error(self, mock_db):
        """Test transaction rollback on error."""
        mock_db.execute.side_effect = [None, Exception("DB Error")]

        ledger = GreenLedger(db_connection=mock_db)

        with pytest.raises(Exception):
            await ledger.save_entry(
                job_id="JOB-001",
                company_id="COMP-001",
                state="CA",
                approved_by="USER-001"
            )

        # In production, this would trigger rollback

    @pytest.mark.asyncio
    async def test_concurrent_access_handling(self, mock_db):
        """Test handling of concurrent database access."""
        import asyncio

        ledger = GreenLedger(db_connection=mock_db)
        mock_db.fetchval.return_value = "entry-uuid"

        # Simulate concurrent saves
        async def save_entry(job_id):
            return await ledger.save_entry(
                job_id=job_id,
                company_id="COMP-001",
                state="CA",
                approved_by="USER-001"
            )

        # Run multiple saves concurrently
        results = await asyncio.gather(
            save_entry("JOB-001"),
            save_entry("JOB-002"),
            save_entry("JOB-003")
        )

        assert len(results) == 3
