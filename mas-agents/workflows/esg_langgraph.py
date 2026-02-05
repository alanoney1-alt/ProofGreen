"""
ProofGreen MAS - ESG LangGraph Workflow
State-managed workflow with PostgreSQL checkpointing for HITL approval.
"""

import os
import json
import asyncio
from typing import Dict, List, Optional, Any, TypedDict, Annotated
from datetime import datetime
from enum import Enum
import asyncpg

from config.settings import settings


# ========== STATE DEFINITION ==========

class AgentState(TypedDict):
    """Shared state for the ESG verification workflow."""
    # Job identification
    job_id: str
    company_id: str
    customer_id: Optional[str]
    zip_code: str
    state: str

    # Equipment data (from Vision OCR)
    equipment_photo_url: Optional[str]
    equipment_data: Optional[Dict]

    # Compliance results
    compliance_report: Optional[str]
    is_compliant: bool
    violations: List[str]
    compliance_risk_score: int

    # Incentives (from Rewiring America)
    incentives: List[Dict]
    total_incentive_amount: float

    # Carbon calculations
    carbon_baseline: float
    carbon_savings: float

    # Workflow control
    requires_approval: bool
    approval_status: Optional[str]  # pending, approved, rejected
    approval_notes: Optional[str]
    status: str  # running, paused, completed, failed

    # Metadata
    created_at: str
    updated_at: str
    checkpointed_at: Optional[str]


class WorkflowStatus(str, Enum):
    """Workflow execution status."""
    RUNNING = "running"
    PAUSED = "paused"  # Waiting for HITL approval
    COMPLETED = "completed"
    FAILED = "failed"


# ========== NODE FUNCTIONS ==========

def vision_triage_node(state: AgentState) -> Dict:
    """
    Uses Claude Vision to audit the job site photo.
    Extracts equipment Model, SEER, refrigerant type.
    """
    from agents.equipment_triage import equipment_triage_node

    # Run equipment triage
    result = equipment_triage_node(state)

    return {
        "equipment_data": result.get("equipment_data"),
        "carbon_baseline": result.get("carbon_baseline", 0),
        "status": WorkflowStatus.RUNNING.value
    }


def regulatory_scout_node(state: AgentState) -> Dict:
    """
    Checks the 2026 regulatory database for mandates.
    Queries Pinecone for relevant regulations.
    """
    from agents.equipment_triage import EquipmentTriageNode

    # Create triage node for compliance checking
    node = EquipmentTriageNode(state)

    equipment = state.get("equipment_data", {})
    violations = []
    compliance_report_parts = []

    # Check refrigerant compliance
    refrigerant = equipment.get("refrigerant")
    if refrigerant:
        ref_result = node._check_refrigerant_compliance(refrigerant)
        if not ref_result["compliant"]:
            violations.append(ref_result["violation"])
            compliance_report_parts.append(f"Refrigerant: {ref_result['violation']}")

    # Check SEER2 compliance
    seer = equipment.get("seer2") or equipment.get("seer_rating")
    if seer:
        seer_result = node._check_seer2_compliance(seer, state.get("state", "CA"))
        if not seer_result["compliant"]:
            violations.append(seer_result["message"])
            compliance_report_parts.append(f"Efficiency: {seer_result['message']}")

    # Build compliance report
    if violations:
        report = f"NON-COMPLIANT: {'; '.join(compliance_report_parts)}"
        is_compliant = False
    else:
        report = "COMPLIANT: Equipment meets all 2026 regulatory requirements."
        is_compliant = True

    return {
        "compliance_report": report,
        "is_compliant": is_compliant,
        "violations": violations,
        "compliance_risk_score": len(violations) * 20,
        "status": WorkflowStatus.RUNNING.value
    }


def incentive_engine_node(state: AgentState) -> Dict:
    """
    Queries Rewiring America API for available credits.
    Calculates HEEHRA, 25C, 25D incentives.
    """
    # Simulated incentive calculation (integrate with actual API)
    incentives = []
    total_amount = 0.0

    equipment = state.get("equipment_data", {})
    seer = equipment.get("seer2", 0)

    # HEEHRA (for low-income households)
    # In production: check AMI levels via Rewiring America API
    heehra_eligible = True  # Simplified - would check income
    if heehra_eligible and seer >= 16:
        incentives.append({
            "type": "HEEHRA",
            "amount": 8000,
            "description": "Home Energy Efficiency Rebate (Heat Pump)",
            "requirements": ["Income verification", "Certified installer"],
            "confidence": 0.85
        })
        total_amount += 8000

    # 25C Tax Credit (up to $2000 for heat pumps)
    if seer >= 16:
        credit_25c = min(2000, state.get("equipment_cost", 10000) * 0.30)
        incentives.append({
            "type": "25C",
            "amount": credit_25c,
            "description": "Energy Efficient Home Improvement Credit",
            "requirements": ["Meets CEE highest tier", "Primary residence"],
            "confidence": 0.95
        })
        total_amount += credit_25c

    # 25D Tax Credit (30% for solar/geothermal)
    equipment_type = equipment.get("equipment_type", "")
    if "geothermal" in equipment_type.lower() or "solar" in equipment_type.lower():
        credit_25d = state.get("equipment_cost", 15000) * 0.30
        incentives.append({
            "type": "25D",
            "amount": credit_25d,
            "description": "Residential Clean Energy Credit",
            "requirements": ["New installation", "Primary or secondary residence"],
            "confidence": 0.95
        })
        total_amount += credit_25d

    # Determine if approval required (threshold: $500)
    requires_approval = total_amount > 500

    return {
        "incentives": incentives,
        "total_incentive_amount": total_amount,
        "requires_approval": requires_approval,
        "status": WorkflowStatus.PAUSED.value if requires_approval else WorkflowStatus.RUNNING.value
    }


def self_correction_node(state: AgentState) -> Dict:
    """
    Self-correction node for low-confidence incentive calculations.
    Re-verifies calculations before sending to human approval.
    """
    incentives = state.get("incentives", [])
    corrected_incentives = []

    for incentive in incentives:
        confidence = incentive.get("confidence", 1.0)

        if confidence < 0.9:
            # Flag for review
            incentive["flagged_for_review"] = True
            incentive["review_reason"] = f"Confidence {confidence:.0%} below 90% threshold"

        corrected_incentives.append(incentive)

    # Recalculate total
    total_amount = sum(i["amount"] for i in corrected_incentives)

    return {
        "incentives": corrected_incentives,
        "total_incentive_amount": total_amount,
        "status": WorkflowStatus.PAUSED.value  # Always pause after correction for review
    }


def human_gatekeeper_node(state: AgentState) -> Dict:
    """
    Human-in-the-loop pause point.
    Workflow pauses here until human approval.
    """
    # This node doesn't modify state - it's just a checkpoint
    # The workflow will pause here due to interrupt_before configuration
    return {
        "status": WorkflowStatus.PAUSED.value,
        "checkpointed_at": datetime.utcnow().isoformat()
    }


def finalize_node(state: AgentState) -> Dict:
    """
    Finalize the workflow and update Green Ledger.
    """
    return {
        "status": WorkflowStatus.COMPLETED.value,
        "updated_at": datetime.utcnow().isoformat()
    }


# ========== CONDITIONAL EDGES ==========

def should_self_correct(state: AgentState) -> str:
    """Determine if self-correction is needed."""
    incentives = state.get("incentives", [])

    # Check if any incentive has low confidence
    for incentive in incentives:
        if incentive.get("confidence", 1.0) < 0.9:
            return "self_correction"

    # Check if approval is required
    if state.get("requires_approval"):
        return "human_gatekeeper"

    return "finalize"


def check_approval(state: AgentState) -> str:
    """Check approval status and route accordingly."""
    approval_status = state.get("approval_status")

    if approval_status == "approved":
        return "finalize"
    elif approval_status == "rejected":
        return "end"  # Or route to revision node
    else:
        return "wait"  # Stay in paused state


# ========== POSTGRESQL CHECKPOINTER ==========

class PostgreSQLCheckpointer:
    """
    PostgreSQL-based checkpointer for LangGraph workflow state.
    Enables HITL approval by persisting state across sessions.
    """

    def __init__(self, connection_string: Optional[str] = None):
        """Initialize checkpointer with database connection."""
        self.conn_string = connection_string or settings.DATABASE_URL
        self.pool = None

    async def initialize(self):
        """Create connection pool and ensure tables exist."""
        self.pool = await asyncpg.create_pool(self.conn_string)

        await self._create_tables()

    async def _create_tables(self):
        """Create checkpoint tables if they don't exist."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS workflow_checkpoints (
                    checkpoint_id VARCHAR(255) PRIMARY KEY,
                    job_id VARCHAR(255) NOT NULL,
                    company_id VARCHAR(255) NOT NULL,
                    thread_id VARCHAR(255),
                    state JSONB NOT NULL,
                    current_node VARCHAR(100),
                    status VARCHAR(50) NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW(),

                    CONSTRAINT unique_job_thread UNIQUE (job_id, thread_id)
                );

                CREATE INDEX IF NOT EXISTS idx_checkpoint_job ON workflow_checkpoints(job_id);
                CREATE INDEX IF NOT EXISTS idx_checkpoint_status ON workflow_checkpoints(status);
                CREATE INDEX IF NOT EXISTS idx_checkpoint_company ON workflow_checkpoints(company_id);
            """)

    async def save_checkpoint(
        self,
        job_id: str,
        state: AgentState,
        current_node: str,
        thread_id: Optional[str] = None
    ) -> str:
        """
        Save workflow checkpoint.

        Args:
            job_id: Job identifier
            state: Current workflow state
            current_node: Name of current node
            thread_id: Optional thread identifier

        Returns:
            Checkpoint ID
        """
        import uuid
        checkpoint_id = f"ckpt_{uuid.uuid4().hex[:12]}"
        thread_id = thread_id or f"thread_{job_id}"

        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO workflow_checkpoints
                (checkpoint_id, job_id, company_id, thread_id, state, current_node, status, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
                ON CONFLICT (job_id, thread_id) DO UPDATE SET
                    checkpoint_id = EXCLUDED.checkpoint_id,
                    state = EXCLUDED.state,
                    current_node = EXCLUDED.current_node,
                    status = EXCLUDED.status,
                    updated_at = NOW()
            """,
                checkpoint_id,
                job_id,
                state.get("company_id", ""),
                thread_id,
                json.dumps(state, default=str),
                current_node,
                state.get("status", WorkflowStatus.RUNNING.value)
            )

        return checkpoint_id

    async def load_checkpoint(
        self,
        job_id: str,
        thread_id: Optional[str] = None
    ) -> Optional[AgentState]:
        """
        Load workflow checkpoint.

        Args:
            job_id: Job identifier
            thread_id: Optional thread identifier

        Returns:
            AgentState if checkpoint exists
        """
        thread_id = thread_id or f"thread_{job_id}"

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT state, current_node, status
                FROM workflow_checkpoints
                WHERE job_id = $1 AND thread_id = $2
            """, job_id, thread_id)

            if row:
                state = json.loads(row["state"])
                return state

        return None

    async def update_approval(
        self,
        job_id: str,
        approved: bool,
        approver_id: str,
        notes: Optional[str] = None,
        thread_id: Optional[str] = None
    ) -> bool:
        """
        Update checkpoint with approval decision.

        Args:
            job_id: Job identifier
            approved: Whether approved
            approver_id: Who approved
            notes: Approval notes
            thread_id: Optional thread identifier

        Returns:
            True if updated successfully
        """
        thread_id = thread_id or f"thread_{job_id}"

        async with self.pool.acquire() as conn:
            # Load current state
            row = await conn.fetchrow("""
                SELECT state FROM workflow_checkpoints
                WHERE job_id = $1 AND thread_id = $2
            """, job_id, thread_id)

            if not row:
                return False

            state = json.loads(row["state"])
            state["approval_status"] = "approved" if approved else "rejected"
            state["approval_notes"] = notes
            state["status"] = WorkflowStatus.RUNNING.value if approved else WorkflowStatus.FAILED.value

            # Update checkpoint
            await conn.execute("""
                UPDATE workflow_checkpoints
                SET state = $1, status = $2, updated_at = NOW()
                WHERE job_id = $3 AND thread_id = $4
            """,
                json.dumps(state, default=str),
                state["status"],
                job_id,
                thread_id
            )

            return True

    async def get_pending_approvals(
        self,
        company_id: Optional[str] = None
    ) -> List[Dict]:
        """Get all workflows pending approval."""
        async with self.pool.acquire() as conn:
            if company_id:
                rows = await conn.fetch("""
                    SELECT checkpoint_id, job_id, state, current_node, created_at
                    FROM workflow_checkpoints
                    WHERE status = 'paused' AND company_id = $1
                    ORDER BY created_at DESC
                """, company_id)
            else:
                rows = await conn.fetch("""
                    SELECT checkpoint_id, job_id, company_id, state, current_node, created_at
                    FROM workflow_checkpoints
                    WHERE status = 'paused'
                    ORDER BY created_at DESC
                """)

            return [
                {
                    "checkpoint_id": r["checkpoint_id"],
                    "job_id": r["job_id"],
                    "company_id": r.get("company_id"),
                    "state": json.loads(r["state"]),
                    "current_node": r["current_node"],
                    "created_at": r["created_at"].isoformat()
                }
                for r in rows
            ]


# ========== ESG WORKFLOW BUILDER ==========

class ESGWorkflow:
    """
    ESG Verification Workflow using LangGraph-style execution.
    Supports PostgreSQL checkpointing and HITL approval.
    """

    def __init__(self, checkpointer: Optional[PostgreSQLCheckpointer] = None):
        """Initialize workflow."""
        self.checkpointer = checkpointer
        self.nodes = {
            "vision_audit": vision_triage_node,
            "compliance_check": regulatory_scout_node,
            "calculate_cash": incentive_engine_node,
            "self_correction": self_correction_node,
            "human_gatekeeper": human_gatekeeper_node,
            "finalize": finalize_node,
        }
        self.edges = [
            ("vision_audit", "compliance_check"),
            ("compliance_check", "calculate_cash"),
            ("self_correction", "human_gatekeeper"),
            ("human_gatekeeper", "finalize"),
        ]
        self.conditional_edges = {
            "calculate_cash": should_self_correct,
        }
        self.entry_point = "vision_audit"
        self.interrupt_before = ["human_gatekeeper"]

    async def run(
        self,
        initial_state: AgentState,
        thread_id: Optional[str] = None
    ) -> AgentState:
        """
        Run the workflow from start or resume from checkpoint.

        Args:
            initial_state: Initial workflow state
            thread_id: Optional thread ID for checkpointing

        Returns:
            Final workflow state
        """
        job_id = initial_state["job_id"]
        thread_id = thread_id or f"thread_{job_id}"

        # Check for existing checkpoint
        if self.checkpointer:
            existing_state = await self.checkpointer.load_checkpoint(job_id, thread_id)
            if existing_state:
                # Resume from checkpoint if approved
                if existing_state.get("approval_status") == "approved":
                    initial_state = existing_state
                elif existing_state.get("status") == WorkflowStatus.PAUSED.value:
                    # Still waiting for approval
                    return existing_state

        state = initial_state
        current_node = self.entry_point

        while current_node:
            # Check for interrupt before this node
            if current_node in self.interrupt_before:
                if state.get("approval_status") not in ["approved"]:
                    # Save checkpoint and pause
                    if self.checkpointer:
                        await self.checkpointer.save_checkpoint(
                            job_id, state, current_node, thread_id
                        )
                    state["status"] = WorkflowStatus.PAUSED.value
                    return state

            # Execute node
            node_fn = self.nodes.get(current_node)
            if node_fn:
                result = node_fn(state)
                state.update(result)

            # Save checkpoint after each node
            if self.checkpointer:
                await self.checkpointer.save_checkpoint(
                    job_id, state, current_node, thread_id
                )

            # Determine next node
            if current_node in self.conditional_edges:
                next_node = self.conditional_edges[current_node](state)
                if next_node == "finalize":
                    current_node = "finalize"
                elif next_node == "end":
                    break
                else:
                    current_node = next_node
            else:
                # Follow static edge
                next_node = None
                for start, end in self.edges:
                    if start == current_node:
                        next_node = end
                        break
                current_node = next_node

        return state


# Factory function
async def create_esg_workflow() -> ESGWorkflow:
    """Create and initialize ESG workflow with checkpointing."""
    checkpointer = PostgreSQLCheckpointer()
    await checkpointer.initialize()
    return ESGWorkflow(checkpointer=checkpointer)


# Singleton for FastAPI
_workflow_instance = None


async def get_esg_workflow() -> ESGWorkflow:
    """Get or create singleton workflow instance."""
    global _workflow_instance
    if _workflow_instance is None:
        _workflow_instance = await create_esg_workflow()
    return _workflow_instance
