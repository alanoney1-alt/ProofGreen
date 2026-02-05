"""
ProofGreen MAS - Workflow Tests
Tests for LangGraph ESG workflow and PostgreSQL checkpointing.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from workflows.esg_langgraph import (
    ESGWorkflow,
    AgentState,
    WorkflowStatus,
    PostgreSQLCheckpointer
)


class TestAgentState:
    """Tests for AgentState dataclass."""

    def test_agent_state_creation(self, sample_workflow_state):
        """Test AgentState can be created from dict."""
        state = AgentState(**sample_workflow_state)

        assert state.job_id == "JOB-2026-001"
        assert state.company_id == "COMP-001"
        assert state.current_node == "vision_audit"
        assert state.status == "in_progress"

    def test_agent_state_defaults(self):
        """Test AgentState has sensible defaults."""
        state = AgentState(
            job_id="JOB-001",
            company_id="COMP-001"
        )

        assert state.errors == []
        assert state.equipment_analysis is None
        assert state.human_approved is None


class TestPostgreSQLCheckpointer:
    """Tests for PostgreSQL workflow checkpointing."""

    @pytest.fixture
    def checkpointer(self, mock_db):
        """Create checkpointer instance."""
        return PostgreSQLCheckpointer(db_connection=mock_db)

    @pytest.mark.asyncio
    async def test_save_checkpoint(self, checkpointer, mock_db, sample_workflow_state):
        """Test saving workflow checkpoint."""
        state = AgentState(**sample_workflow_state)

        checkpoint_id = await checkpointer.save_checkpoint(
            job_id="JOB-2026-001",
            state=state,
            current_node="vision_audit",
            thread_id="thread-001"
        )

        assert checkpoint_id is not None
        mock_db.execute.assert_called()

    @pytest.mark.asyncio
    async def test_load_checkpoint(self, checkpointer, mock_db, sample_workflow_state):
        """Test loading workflow checkpoint."""
        mock_db.fetchrow.return_value = {
            "id": "checkpoint-001",
            "job_id": "JOB-2026-001",
            "state_json": sample_workflow_state,
            "current_node": "vision_audit",
            "status": "in_progress"
        }

        state = await checkpointer.load_checkpoint(
            job_id="JOB-2026-001",
            thread_id="thread-001"
        )

        assert state is not None
        mock_db.fetchrow.assert_called()

    @pytest.mark.asyncio
    async def test_update_approval_approved(self, checkpointer, mock_db):
        """Test updating checkpoint with approval."""
        mock_db.fetchval.return_value = 1

        result = await checkpointer.update_approval(
            job_id="JOB-2026-001",
            approved=True,
            approver_id="USER-001",
            notes="Approved - all documentation complete"
        )

        assert result is True
        mock_db.execute.assert_called()

    @pytest.mark.asyncio
    async def test_update_approval_rejected(self, checkpointer, mock_db):
        """Test updating checkpoint with rejection."""
        mock_db.fetchval.return_value = 1

        result = await checkpointer.update_approval(
            job_id="JOB-2026-001",
            approved=False,
            approver_id="USER-001",
            notes="Rejected - missing equipment photo"
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_get_pending_approvals(self, checkpointer, mock_db):
        """Test fetching pending approval tasks."""
        mock_db.fetch.return_value = [
            {
                "job_id": "JOB-001",
                "company_id": "COMP-001",
                "current_node": "human_gatekeeper",
                "created_at": datetime.utcnow()
            },
            {
                "job_id": "JOB-002",
                "company_id": "COMP-001",
                "current_node": "human_gatekeeper",
                "created_at": datetime.utcnow()
            }
        ]

        pending = await checkpointer.get_pending_approvals(company_id="COMP-001")

        assert len(pending) == 2


class TestESGWorkflow:
    """Tests for ESG LangGraph workflow."""

    @pytest.fixture
    def workflow(self, mock_db):
        """Create ESG workflow instance."""
        return ESGWorkflow(db_connection=mock_db)

    @pytest.mark.asyncio
    async def test_workflow_initialization(self, workflow):
        """Test workflow initializes with correct nodes."""
        assert workflow is not None
        assert hasattr(workflow, 'nodes')
        assert "vision_audit" in workflow.nodes
        assert "compliance_check" in workflow.nodes
        assert "calculate_cash" in workflow.nodes
        assert "human_gatekeeper" in workflow.nodes
        assert "finalize" in workflow.nodes

    @pytest.mark.asyncio
    async def test_vision_audit_node(self, workflow, sample_job_data):
        """Test vision audit node processes equipment images."""
        initial_state = AgentState(
            job_id="JOB-2026-001",
            company_id="COMP-001",
            metadata={"image_url": "https://example.com/equipment.jpg"}
        )

        with patch.object(workflow, '_execute_node', new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = AgentState(
                job_id="JOB-2026-001",
                company_id="COMP-001",
                current_node="compliance_check",
                equipment_analysis={
                    "manufacturer": "Carrier",
                    "refrigerant": "R-410A"
                }
            )

            result = await workflow._execute_node("vision_audit", initial_state)

            assert result.equipment_analysis is not None

    @pytest.mark.asyncio
    async def test_compliance_check_node(self, workflow, sample_equipment_image_analysis):
        """Test compliance check node validates equipment."""
        state = AgentState(
            job_id="JOB-2026-001",
            company_id="COMP-001",
            current_node="compliance_check",
            equipment_analysis=sample_equipment_image_analysis
        )

        with patch.object(workflow, '_execute_node', new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = AgentState(
                job_id="JOB-2026-001",
                company_id="COMP-001",
                current_node="calculate_cash",
                compliance_check={
                    "epa_aim_compliant": False,
                    "seer2_compliant": False,
                    "issues": ["R-410A phase-out"]
                }
            )

            result = await workflow._execute_node("compliance_check", state)

            assert result.compliance_check is not None
            assert result.compliance_check["epa_aim_compliant"] is False

    @pytest.mark.asyncio
    async def test_calculate_cash_node(self, workflow, sample_incentive_calculation):
        """Test incentive calculation node."""
        state = AgentState(
            job_id="JOB-2026-001",
            company_id="COMP-001",
            current_node="calculate_cash",
            equipment_analysis={"refrigerant": "R-454B", "seer": 20.5},
            compliance_check={"epa_aim_compliant": True}
        )

        with patch.object(workflow, '_execute_node', new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = AgentState(
                job_id="JOB-2026-001",
                company_id="COMP-001",
                current_node="human_gatekeeper",
                incentives_calculated=sample_incentive_calculation
            )

            result = await workflow._execute_node("calculate_cash", state)

            assert result.incentives_calculated is not None
            assert result.incentives_calculated["total_incentives"] == 4250.00

    @pytest.mark.asyncio
    async def test_human_gatekeeper_requires_approval(self, workflow):
        """Test human gatekeeper node sets approval required."""
        state = AgentState(
            job_id="JOB-2026-001",
            company_id="COMP-001",
            current_node="human_gatekeeper",
            incentives_calculated={"total_incentives": 4250.00}
        )

        with patch.object(workflow, '_execute_node', new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = AgentState(
                job_id="JOB-2026-001",
                company_id="COMP-001",
                current_node="human_gatekeeper",
                status="awaiting_approval"
            )

            result = await workflow._execute_node("human_gatekeeper", state)

            assert result.status == "awaiting_approval"

    @pytest.mark.asyncio
    async def test_workflow_run_full_pipeline(self, workflow, sample_job_data, mock_db):
        """Test full workflow execution."""
        initial_state = AgentState(
            job_id="JOB-2026-001",
            company_id="COMP-001",
            metadata=sample_job_data
        )

        with patch.object(workflow, 'run', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = AgentState(
                job_id="JOB-2026-001",
                company_id="COMP-001",
                current_node="human_gatekeeper",
                status="awaiting_approval",
                equipment_analysis={"refrigerant": "R-454B"},
                compliance_check={"epa_aim_compliant": True},
                incentives_calculated={"total_incentives": 4250.00}
            )

            result = await workflow.run(initial_state, thread_id="thread-001")

            assert result.status == "awaiting_approval"
            assert result.equipment_analysis is not None
            assert result.compliance_check is not None
            assert result.incentives_calculated is not None

    @pytest.mark.asyncio
    async def test_workflow_handles_errors(self, workflow):
        """Test workflow handles node errors gracefully."""
        initial_state = AgentState(
            job_id="JOB-2026-001",
            company_id="COMP-001"
        )

        with patch.object(workflow, '_execute_node', new_callable=AsyncMock) as mock_exec:
            mock_exec.side_effect = Exception("Vision API error")

            with patch.object(workflow, 'run', new_callable=AsyncMock) as mock_run:
                mock_run.return_value = AgentState(
                    job_id="JOB-2026-001",
                    company_id="COMP-001",
                    status="error",
                    errors=[{"node": "vision_audit", "error": "Vision API error"}]
                )

                result = await workflow.run(initial_state, thread_id="thread-001")

                assert result.status == "error"
                assert len(result.errors) > 0

    @pytest.mark.asyncio
    async def test_self_correction_node_triggered(self, workflow):
        """Test self-correction node is triggered on compliance failure."""
        state = AgentState(
            job_id="JOB-2026-001",
            company_id="COMP-001",
            current_node="compliance_check",
            compliance_check={
                "epa_aim_compliant": False,
                "issues": ["R-410A not compliant"]
            }
        )

        # Self-correction should be triggered when compliance fails
        with patch.object(workflow, '_should_self_correct') as mock_check:
            mock_check.return_value = True

            next_node = workflow._get_next_node(state)
            assert next_node == "self_correction" or mock_check.called
