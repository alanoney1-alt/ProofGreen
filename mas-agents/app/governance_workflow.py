"""
ProofGreen MAS - LangGraph Governance Workflow
Implements Human-in-the-Loop (HITL) approval flows with state persistence.

Uses LangGraph-style state management for:
- Pausing workflows for human approval
- Resuming after approval/rejection
- Persistent checkpointing for audit trail
"""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypedDict
from uuid import UUID, uuid4
import asyncio
import hashlib

logger = logging.getLogger(__name__)


class WorkflowStatus(str, Enum):
    """Status of a governance workflow."""
    PENDING = "pending"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


class RiskLevel(str, Enum):
    """Risk level for governance decisions."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TaskType(str, Enum):
    """Types of tasks requiring governance."""
    TAX_CREDIT_FILING = "tax_credit_filing"
    REBATE_APPLICATION = "rebate_application"
    ESG_REPORT = "esg_report"
    COMPLIANCE_FILING = "compliance_filing"
    CERTIFICATE_GENERATION = "certificate_generation"
    FINANCIAL_AUDIT = "financial_audit"


class WorkflowState(TypedDict):
    """State object for governance workflows."""
    workflow_id: str
    thread_id: str
    task_type: str
    status: str
    risk_level: str

    # Task details
    job_id: Optional[str]
    company_id: str
    amount_dollars: float
    description: str

    # AI reasoning
    agent_id: str
    decision_logic: str
    model_used: str
    confidence_score: float

    # Evidence
    evidence_documents: List[str]
    evidence_hash: str

    # Approval
    requires_approval: bool
    approval_threshold: float
    approver_id: Optional[str]
    approver_name: Optional[str]
    approval_timestamp: Optional[str]
    rejection_reason: Optional[str]

    # Results
    result: Optional[Dict[str, Any]]
    error: Optional[str]

    # Timestamps
    created_at: str
    updated_at: str
    expires_at: Optional[str]

    # Checkpointing
    checkpoint_data: Dict[str, Any]
    previous_states: List[Dict[str, Any]]


@dataclass
class GovernanceTask:
    """A task requiring governance review."""
    id: UUID = field(default_factory=uuid4)
    task_type: TaskType = TaskType.TAX_CREDIT_FILING
    risk_level: RiskLevel = RiskLevel.MEDIUM

    # Task details
    job_id: Optional[str] = None
    company_id: str = ""
    amount_dollars: float = 0.0
    title: str = ""
    description: str = ""

    # AI context
    agent_id: str = ""
    decision_logic: str = ""
    model_used: str = "claude-sonnet-4-20250514"
    confidence_score: float = 0.0

    # Evidence
    evidence_documents: List[str] = field(default_factory=list)

    # Approval settings
    approval_threshold: float = 500.0  # Dollar amount requiring approval
    expires_hours: int = 72  # Hours until task expires

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "task_type": self.task_type.value,
            "risk_level": self.risk_level.value,
            "job_id": self.job_id,
            "company_id": self.company_id,
            "amount_dollars": self.amount_dollars,
            "title": self.title,
            "description": self.description,
            "agent_id": self.agent_id,
            "decision_logic": self.decision_logic,
            "model_used": self.model_used,
            "confidence_score": self.confidence_score,
            "evidence_documents": self.evidence_documents,
            "approval_threshold": self.approval_threshold
        }


class WorkflowCheckpointer:
    """
    Persistent state checkpointer for governance workflows.
    Stores workflow states for audit trail and resumption.
    """

    def __init__(self, storage_path: Optional[str] = None, db_connection: Optional[Any] = None):
        self.storage_path = storage_path or os.path.join(
            os.path.dirname(__file__), "..", "data", "checkpoints"
        )
        self._db = db_connection
        self._states: Dict[str, WorkflowState] = {}

        # Ensure storage directory exists
        os.makedirs(self.storage_path, exist_ok=True)

    def save_checkpoint(self, thread_id: str, state: WorkflowState) -> str:
        """Save a workflow checkpoint."""
        checkpoint_id = f"{thread_id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

        # Store in memory
        self._states[thread_id] = state

        # Persist to file (or database in production)
        checkpoint_path = os.path.join(self.storage_path, f"{thread_id}.json")
        try:
            # Load existing checkpoints for this thread
            existing = []
            if os.path.exists(checkpoint_path):
                with open(checkpoint_path, "r") as f:
                    existing = json.load(f)

            # Add new checkpoint
            existing.append({
                "checkpoint_id": checkpoint_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "state": state
            })

            # Save back
            with open(checkpoint_path, "w") as f:
                json.dump(existing, f, indent=2, default=str)

            logger.info(f"Saved checkpoint: {checkpoint_id}")

        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")

        return checkpoint_id

    def load_checkpoint(self, thread_id: str) -> Optional[WorkflowState]:
        """Load the latest checkpoint for a thread."""
        # Check memory first
        if thread_id in self._states:
            return self._states[thread_id]

        # Load from storage
        checkpoint_path = os.path.join(self.storage_path, f"{thread_id}.json")
        try:
            if os.path.exists(checkpoint_path):
                with open(checkpoint_path, "r") as f:
                    checkpoints = json.load(f)
                    if checkpoints:
                        return checkpoints[-1]["state"]

        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")

        return None

    def get_checkpoint_history(self, thread_id: str) -> List[Dict[str, Any]]:
        """Get all checkpoints for a thread (for audit trail)."""
        checkpoint_path = os.path.join(self.storage_path, f"{thread_id}.json")
        try:
            if os.path.exists(checkpoint_path):
                with open(checkpoint_path, "r") as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load checkpoint history: {e}")
        return []


class GovernanceWorkflow:
    """
    LangGraph-style governance workflow with HITL support.

    Workflow stages:
    1. Calculate/Audit - AI performs analysis
    2. Gatekeeper - Check if approval required
    3. Human Review - Pause for approval if needed
    4. Execute - Complete the action after approval
    5. Audit Log - Record everything for compliance
    """

    def __init__(
        self,
        checkpointer: Optional[WorkflowCheckpointer] = None,
        audit_trail: Optional[Any] = None
    ):
        self.checkpointer = checkpointer or WorkflowCheckpointer()
        self.audit_trail = audit_trail
        self._pending_approvals: Dict[str, WorkflowState] = {}
        self._node_handlers: Dict[str, Callable] = {}
        self._approval_callbacks: List[Callable] = []

        # Risk-based approval thresholds
        self.approval_thresholds = {
            RiskLevel.LOW: 1000,      # $1,000+
            RiskLevel.MEDIUM: 500,    # $500+
            RiskLevel.HIGH: 100,      # $100+
            RiskLevel.CRITICAL: 0     # Always requires approval
        }

    def register_node(self, name: str, handler: Callable):
        """Register a node handler for the workflow."""
        self._node_handlers[name] = handler

    def on_approval_needed(self, callback: Callable):
        """Register callback for when approval is needed."""
        self._approval_callbacks.append(callback)

    async def start_workflow(self, task: GovernanceTask) -> WorkflowState:
        """
        Start a new governance workflow for a task.
        Returns the initial state (may be paused awaiting approval).
        """
        thread_id = f"workflow_{task.id}"
        evidence_hash = self._calculate_evidence_hash(task.evidence_documents)

        # Create initial state
        state: WorkflowState = {
            "workflow_id": str(uuid4()),
            "thread_id": thread_id,
            "task_type": task.task_type.value,
            "status": WorkflowStatus.RUNNING.value,
            "risk_level": task.risk_level.value,
            "job_id": task.job_id,
            "company_id": task.company_id,
            "amount_dollars": task.amount_dollars,
            "description": task.description,
            "agent_id": task.agent_id,
            "decision_logic": task.decision_logic,
            "model_used": task.model_used,
            "confidence_score": task.confidence_score,
            "evidence_documents": task.evidence_documents,
            "evidence_hash": evidence_hash,
            "requires_approval": False,
            "approval_threshold": task.approval_threshold,
            "approver_id": None,
            "approver_name": None,
            "approval_timestamp": None,
            "rejection_reason": None,
            "result": None,
            "error": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": None,
            "checkpoint_data": {},
            "previous_states": []
        }

        # Save initial checkpoint
        self.checkpointer.save_checkpoint(thread_id, state)

        # Run gatekeeper to check if approval needed
        state = await self._run_gatekeeper(state, task)

        # If approval needed, pause workflow
        if state["requires_approval"]:
            state["status"] = WorkflowStatus.AWAITING_APPROVAL.value
            state["expires_at"] = self._calculate_expiry(task.expires_hours)
            self._pending_approvals[thread_id] = state

            # Save checkpoint at approval point
            self.checkpointer.save_checkpoint(thread_id, state)

            # Notify callbacks
            for callback in self._approval_callbacks:
                try:
                    await callback(state) if asyncio.iscoroutinefunction(callback) else callback(state)
                except Exception as e:
                    logger.error(f"Approval callback error: {e}")

            logger.info(f"Workflow {thread_id} paused for approval (${task.amount_dollars})")
            return state

        # If no approval needed, execute immediately
        state = await self._execute_action(state, task)
        return state

    async def _run_gatekeeper(self, state: WorkflowState, task: GovernanceTask) -> WorkflowState:
        """
        Gatekeeper node - determine if human approval is required.
        """
        risk_level = RiskLevel(task.risk_level)
        threshold = self.approval_thresholds.get(risk_level, 500)

        # Check if approval required based on amount and risk
        requires_approval = (
            task.amount_dollars >= threshold or
            risk_level == RiskLevel.CRITICAL or
            (risk_level == RiskLevel.HIGH and task.amount_dollars > 0)
        )

        state["requires_approval"] = requires_approval

        # Log gatekeeper decision
        if self.audit_trail:
            from app.audit_trail import AuditAction
            self.audit_trail.log_agent_decision(
                agent_id="gatekeeper",
                action=AuditAction.AGENT_DECISION,
                description=f"Gatekeeper: approval {'required' if requires_approval else 'not required'}",
                decision_logic=f"Amount ${task.amount_dollars} vs threshold ${threshold}, risk={risk_level.value}",
                task_id=str(task.id),
                job_id=task.job_id,
                company_id=task.company_id,
                amount_dollars=task.amount_dollars
            )

        return state

    async def _execute_action(self, state: WorkflowState, task: GovernanceTask) -> WorkflowState:
        """
        Execute the actual action after approval (or if no approval needed).
        """
        try:
            # Get the appropriate handler
            handler = self._node_handlers.get(task.task_type.value)

            if handler:
                result = await handler(task) if asyncio.iscoroutinefunction(handler) else handler(task)
                state["result"] = result
                state["status"] = WorkflowStatus.COMPLETED.value
            else:
                # Default execution - just mark complete
                state["result"] = {"message": "Task processed", "task_id": str(task.id)}
                state["status"] = WorkflowStatus.COMPLETED.value

            # Log execution
            if self.audit_trail:
                from app.audit_trail import AuditAction
                self.audit_trail.log_agent_decision(
                    agent_id=task.agent_id,
                    action=AuditAction.AGENT_FILING if "filing" in task.task_type.value else AuditAction.AGENT_DECISION,
                    description=f"Executed: {task.title}",
                    decision_logic=task.decision_logic,
                    task_id=str(task.id),
                    job_id=task.job_id,
                    company_id=task.company_id,
                    amount_dollars=task.amount_dollars,
                    evidence_documents=task.evidence_documents
                )

        except Exception as e:
            state["status"] = WorkflowStatus.FAILED.value
            state["error"] = str(e)
            logger.error(f"Workflow execution failed: {e}")

        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.checkpointer.save_checkpoint(state["thread_id"], state)

        return state

    async def approve(
        self,
        thread_id: str,
        approver_id: str,
        approver_name: str
    ) -> WorkflowState:
        """
        Approve a pending workflow and resume execution.
        """
        # Load state
        state = self._pending_approvals.get(thread_id)
        if not state:
            state = self.checkpointer.load_checkpoint(thread_id)

        if not state:
            raise ValueError(f"Workflow not found: {thread_id}")

        if state["status"] != WorkflowStatus.AWAITING_APPROVAL.value:
            raise ValueError(f"Workflow not awaiting approval: {state['status']}")

        # Check expiry
        if state.get("expires_at"):
            expires = datetime.fromisoformat(state["expires_at"])
            if datetime.now(timezone.utc) > expires:
                state["status"] = WorkflowStatus.EXPIRED.value
                self.checkpointer.save_checkpoint(thread_id, state)
                raise ValueError("Approval window expired")

        # Record approval
        state["status"] = WorkflowStatus.APPROVED.value
        state["approver_id"] = approver_id
        state["approver_name"] = approver_name
        state["approval_timestamp"] = datetime.now(timezone.utc).isoformat()
        state["updated_at"] = datetime.now(timezone.utc).isoformat()

        # Log approval in audit trail
        if self.audit_trail:
            self.audit_trail.log_human_approval(
                task_id=state["thread_id"],
                human_approver_id=approver_id,
                human_approver_name=approver_name,
                approved=True,
                agent_id=state["agent_id"],
                decision_logic=state["decision_logic"],
                job_id=state.get("job_id"),
                company_id=state["company_id"],
                amount_dollars=state["amount_dollars"],
                evidence_hash=state["evidence_hash"]
            )

        # Save approved state
        self.checkpointer.save_checkpoint(thread_id, state)

        # Remove from pending
        if thread_id in self._pending_approvals:
            del self._pending_approvals[thread_id]

        # Resume execution
        task = self._state_to_task(state)
        state = await self._execute_action(state, task)

        logger.info(f"Workflow {thread_id} approved by {approver_name}")
        return state

    async def reject(
        self,
        thread_id: str,
        approver_id: str,
        approver_name: str,
        reason: Optional[str] = None
    ) -> WorkflowState:
        """
        Reject a pending workflow.
        """
        state = self._pending_approvals.get(thread_id)
        if not state:
            state = self.checkpointer.load_checkpoint(thread_id)

        if not state:
            raise ValueError(f"Workflow not found: {thread_id}")

        # Record rejection
        state["status"] = WorkflowStatus.REJECTED.value
        state["approver_id"] = approver_id
        state["approver_name"] = approver_name
        state["approval_timestamp"] = datetime.now(timezone.utc).isoformat()
        state["rejection_reason"] = reason
        state["updated_at"] = datetime.now(timezone.utc).isoformat()

        # Log rejection in audit trail
        if self.audit_trail:
            self.audit_trail.log_human_approval(
                task_id=state["thread_id"],
                human_approver_id=approver_id,
                human_approver_name=approver_name,
                approved=False,
                agent_id=state["agent_id"],
                decision_logic=state["decision_logic"],
                job_id=state.get("job_id"),
                company_id=state["company_id"],
                amount_dollars=state["amount_dollars"],
                reason=reason
            )

        # Save rejected state
        self.checkpointer.save_checkpoint(thread_id, state)

        # Remove from pending
        if thread_id in self._pending_approvals:
            del self._pending_approvals[thread_id]

        logger.info(f"Workflow {thread_id} rejected by {approver_name}: {reason}")
        return state

    def get_pending_approvals(self, company_id: Optional[str] = None) -> List[WorkflowState]:
        """Get all workflows awaiting approval."""
        pending = list(self._pending_approvals.values())

        if company_id:
            pending = [p for p in pending if p["company_id"] == company_id]

        return sorted(pending, key=lambda x: x["created_at"], reverse=True)

    def get_workflow_status(self, thread_id: str) -> Optional[WorkflowState]:
        """Get current status of a workflow."""
        if thread_id in self._pending_approvals:
            return self._pending_approvals[thread_id]
        return self.checkpointer.load_checkpoint(thread_id)

    def _calculate_evidence_hash(self, documents: List[str]) -> str:
        """Calculate SHA-256 hash of evidence documents."""
        if not documents:
            return ""
        combined = "|".join(sorted(documents))
        return hashlib.sha256(combined.encode()).hexdigest()

    def _calculate_expiry(self, hours: int) -> str:
        """Calculate expiry timestamp."""
        from datetime import timedelta
        expiry = datetime.now(timezone.utc) + timedelta(hours=hours)
        return expiry.isoformat()

    def _state_to_task(self, state: WorkflowState) -> GovernanceTask:
        """Convert state back to task for execution."""
        return GovernanceTask(
            id=UUID(state["thread_id"].replace("workflow_", "")),
            task_type=TaskType(state["task_type"]),
            risk_level=RiskLevel(state["risk_level"]),
            job_id=state.get("job_id"),
            company_id=state["company_id"],
            amount_dollars=state["amount_dollars"],
            description=state["description"],
            agent_id=state["agent_id"],
            decision_logic=state["decision_logic"],
            model_used=state["model_used"],
            confidence_score=state["confidence_score"],
            evidence_documents=state["evidence_documents"]
        )


# Factory function
def create_governance_workflow(
    checkpointer: Optional[WorkflowCheckpointer] = None,
    audit_trail: Optional[Any] = None
) -> GovernanceWorkflow:
    """Create a new governance workflow instance."""
    return GovernanceWorkflow(checkpointer, audit_trail)


# API endpoint handlers for FastAPI integration
async def get_pending_tasks(workflow: GovernanceWorkflow, company_id: Optional[str] = None):
    """Get pending approval tasks for API."""
    pending = workflow.get_pending_approvals(company_id)
    return [
        {
            "id": p["thread_id"],
            "task_type": p["task_type"],
            "title": p.get("description", "")[:100],
            "detail": p.get("description", ""),
            "risk": p["risk_level"],
            "status": p["status"],
            "amount": p["amount_dollars"],
            "job_id": p.get("job_id"),
            "created_at": p["created_at"],
            "ai_reasoning": p["decision_logic"],
            "evidence_hash": p["evidence_hash"]
        }
        for p in pending
    ]


async def approve_task(
    workflow: GovernanceWorkflow,
    task_id: str,
    approver_id: str,
    approver_name: str
):
    """Approve a task via API."""
    state = await workflow.approve(task_id, approver_id, approver_name)
    return {
        "status": "approved",
        "task_id": task_id,
        "result": state.get("result")
    }


async def reject_task(
    workflow: GovernanceWorkflow,
    task_id: str,
    approver_id: str,
    approver_name: str,
    reason: Optional[str] = None
):
    """Reject a task via API."""
    state = await workflow.reject(task_id, approver_id, approver_name, reason)
    return {
        "status": "rejected",
        "task_id": task_id,
        "reason": reason
    }
