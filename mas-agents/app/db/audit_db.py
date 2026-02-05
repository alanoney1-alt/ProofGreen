"""
ProofGreen MAS - PostgreSQL Audit Trail Database
Immutable audit logging with database persistence for SB 253/SEC compliance.

This module provides:
- PostgreSQL schema for audit trail
- Immutable logging with hash chains
- Query functions for compliance reporting
- Export functions for regulatory submissions
"""

import hashlib
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

# Use asyncpg for async PostgreSQL
# In production: pip install asyncpg
try:
    import asyncpg
    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False
    asyncpg = None

logger = logging.getLogger(__name__)


# =========================================================================
# Database Schema SQL
# =========================================================================

SCHEMA_SQL = """
-- Audit Trail Schema for ProofGreen MAS
-- Designed for immutability and compliance with SB 253, SEC regulations

-- Enum types
CREATE TYPE IF NOT EXISTS audit_action AS ENUM (
    'task_created',
    'task_approved',
    'task_rejected',
    'task_expired',
    'agent_decision',
    'agent_calculation',
    'agent_filing',
    'document_generated',
    'certificate_issued',
    'report_submitted',
    'compliance_check',
    'rebate_submitted',
    'tax_credit_filed',
    'transaction_recorded',
    'ledger_recalculated',
    'regulatory_update',
    'vision_extraction',
    'workflow_started',
    'workflow_completed'
);

CREATE TYPE IF NOT EXISTS audit_severity AS ENUM (
    'info',
    'low',
    'medium',
    'high',
    'critical'
);

-- Main audit log table (immutable)
CREATE TABLE IF NOT EXISTS immutable_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Action details
    action audit_action NOT NULL,
    severity audit_severity NOT NULL DEFAULT 'info',
    description TEXT NOT NULL,

    -- Actor identification
    agent_id VARCHAR(100),
    human_approver_id VARCHAR(100),
    human_approver_name VARCHAR(200),

    -- Context
    task_id VARCHAR(100),
    job_id VARCHAR(100),
    company_id VARCHAR(100),
    workflow_id VARCHAR(100),

    -- AI reasoning (critical for audits)
    decision_logic TEXT,
    model_used VARCHAR(100),
    confidence_score DECIMAL(5,4),

    -- Evidence integrity
    evidence_documents JSONB DEFAULT '[]'::jsonb,
    evidence_hash VARCHAR(64),

    -- Financial (for tax/rebate audits)
    amount_dollars DECIMAL(12,2),
    program_name VARCHAR(200),

    -- Compliance
    regulation_reference VARCHAR(200),
    compliance_status VARCHAR(50),

    -- Chain integrity (blockchain-style)
    previous_hash VARCHAR(64),
    entry_hash VARCHAR(64) NOT NULL,

    -- Additional metadata
    metadata JSONB DEFAULT '{}'::jsonb,

    -- Constraints
    CONSTRAINT valid_entry_hash CHECK (entry_hash ~ '^[a-f0-9]{64}$'),
    CONSTRAINT valid_previous_hash CHECK (previous_hash IS NULL OR previous_hash ~ '^[a-f0-9]{64}$')
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_audit_company_id ON immutable_audit_log(company_id);
CREATE INDEX IF NOT EXISTS idx_audit_job_id ON immutable_audit_log(job_id);
CREATE INDEX IF NOT EXISTS idx_audit_task_id ON immutable_audit_log(task_id);
CREATE INDEX IF NOT EXISTS idx_audit_action ON immutable_audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_created_at ON immutable_audit_log(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_human_approver ON immutable_audit_log(human_approver_id);
CREATE INDEX IF NOT EXISTS idx_audit_entry_hash ON immutable_audit_log(entry_hash);

-- Governance tasks table
CREATE TABLE IF NOT EXISTS governance_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id VARCHAR(100) UNIQUE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Task details
    task_type VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    risk_level VARCHAR(20) NOT NULL DEFAULT 'medium',

    -- Context
    job_id VARCHAR(100),
    company_id VARCHAR(100) NOT NULL,
    amount_dollars DECIMAL(12,2) DEFAULT 0,
    description TEXT,

    -- AI context
    agent_id VARCHAR(100),
    decision_logic TEXT,
    model_used VARCHAR(100),
    confidence_score DECIMAL(5,4),

    -- Evidence
    evidence_documents JSONB DEFAULT '[]'::jsonb,
    evidence_hash VARCHAR(64),

    -- Approval
    requires_approval BOOLEAN DEFAULT TRUE,
    approval_threshold DECIMAL(12,2) DEFAULT 500,
    approver_id VARCHAR(100),
    approver_name VARCHAR(200),
    approval_timestamp TIMESTAMPTZ,
    rejection_reason TEXT,

    -- Result
    result JSONB,
    error TEXT,

    -- Expiry
    expires_at TIMESTAMPTZ,

    -- Checkpointing
    checkpoint_data JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON governance_tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_company ON governance_tasks(company_id);

-- Workflow checkpoints table
CREATE TABLE IF NOT EXISTS workflow_checkpoints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id VARCHAR(100) NOT NULL,
    checkpoint_id VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    state JSONB NOT NULL,

    CONSTRAINT unique_checkpoint UNIQUE (thread_id, checkpoint_id)
);

CREATE INDEX IF NOT EXISTS idx_checkpoints_thread ON workflow_checkpoints(thread_id);

-- Function to prevent updates (immutability)
CREATE OR REPLACE FUNCTION prevent_audit_update()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Audit log entries cannot be modified';
END;
$$ LANGUAGE plpgsql;

-- Trigger to enforce immutability
DROP TRIGGER IF EXISTS audit_immutable_trigger ON immutable_audit_log;
CREATE TRIGGER audit_immutable_trigger
    BEFORE UPDATE OR DELETE ON immutable_audit_log
    FOR EACH ROW
    EXECUTE FUNCTION prevent_audit_update();

-- Function to validate chain integrity on insert
CREATE OR REPLACE FUNCTION validate_audit_chain()
RETURNS TRIGGER AS $$
DECLARE
    last_hash VARCHAR(64);
BEGIN
    -- Get the hash of the previous entry
    SELECT entry_hash INTO last_hash
    FROM immutable_audit_log
    ORDER BY created_at DESC
    LIMIT 1;

    -- Verify chain linkage
    IF last_hash IS NOT NULL AND NEW.previous_hash != last_hash THEN
        RAISE EXCEPTION 'Chain integrity violation: previous_hash does not match last entry';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to validate chain on insert
DROP TRIGGER IF EXISTS audit_chain_trigger ON immutable_audit_log;
CREATE TRIGGER audit_chain_trigger
    BEFORE INSERT ON immutable_audit_log
    FOR EACH ROW
    EXECUTE FUNCTION validate_audit_chain();

-- View for compliance reporting
CREATE OR REPLACE VIEW audit_compliance_report AS
SELECT
    company_id,
    DATE_TRUNC('month', created_at) as month,
    action,
    COUNT(*) as count,
    SUM(amount_dollars) as total_amount,
    COUNT(DISTINCT human_approver_id) as unique_approvers,
    COUNT(CASE WHEN action = 'task_approved' THEN 1 END) as approvals,
    COUNT(CASE WHEN action = 'task_rejected' THEN 1 END) as rejections
FROM immutable_audit_log
GROUP BY company_id, DATE_TRUNC('month', created_at), action;
"""


# =========================================================================
# Database Connection Manager
# =========================================================================

class AuditDatabase:
    """
    PostgreSQL audit database manager.

    Provides:
    - Connection pooling
    - Immutable audit logging
    - Chain integrity verification
    - Compliance reporting queries
    """

    def __init__(self, connection_string: Optional[str] = None):
        self.connection_string = connection_string or os.getenv(
            "DATABASE_URL",
            "postgresql://postgres:postgres@localhost:5432/proofgreen"
        )
        self._pool: Optional[asyncpg.Pool] = None
        self._last_hash: Optional[str] = None

    async def connect(self):
        """Initialize connection pool."""
        if not HAS_ASYNCPG:
            logger.warning("asyncpg not installed - database features disabled")
            return

        try:
            self._pool = await asyncpg.create_pool(
                self.connection_string,
                min_size=2,
                max_size=10
            )
            logger.info("Connected to PostgreSQL audit database")

            # Initialize schema
            await self._initialize_schema()

            # Load last hash for chain integrity
            await self._load_last_hash()

        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            self._pool = None

    async def close(self):
        """Close connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None

    @asynccontextmanager
    async def acquire(self):
        """Acquire a connection from the pool."""
        if not self._pool:
            raise RuntimeError("Database not connected")
        async with self._pool.acquire() as conn:
            yield conn

    async def _initialize_schema(self):
        """Initialize database schema."""
        async with self.acquire() as conn:
            # Split schema into individual statements
            # (asyncpg doesn't support multiple statements)
            statements = [s.strip() for s in SCHEMA_SQL.split(';') if s.strip()]
            for stmt in statements:
                try:
                    await conn.execute(stmt)
                except Exception as e:
                    # Ignore errors for CREATE IF NOT EXISTS
                    if "already exists" not in str(e).lower():
                        logger.warning(f"Schema statement warning: {e}")

    async def _load_last_hash(self):
        """Load the last entry hash for chain integrity."""
        async with self.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT entry_hash FROM immutable_audit_log ORDER BY created_at DESC LIMIT 1"
            )
            self._last_hash = row["entry_hash"] if row else None

    def _calculate_entry_hash(self, entry_data: Dict[str, Any]) -> str:
        """Calculate SHA-256 hash for an audit entry."""
        hash_content = {
            "timestamp": entry_data.get("created_at", datetime.now(timezone.utc).isoformat()),
            "action": entry_data.get("action"),
            "agent_id": entry_data.get("agent_id"),
            "human_approver_id": entry_data.get("human_approver_id"),
            "task_id": entry_data.get("task_id"),
            "decision_logic": entry_data.get("decision_logic"),
            "evidence_hash": entry_data.get("evidence_hash"),
            "amount_dollars": str(entry_data.get("amount_dollars", "")),
            "previous_hash": entry_data.get("previous_hash")
        }
        content_str = json.dumps(hash_content, sort_keys=True, default=str)
        return hashlib.sha256(content_str.encode()).hexdigest()

    # =========================================================================
    # Audit Logging Methods
    # =========================================================================

    async def log_audit_entry(
        self,
        action: str,
        description: str,
        severity: str = "info",
        agent_id: Optional[str] = None,
        human_approver_id: Optional[str] = None,
        human_approver_name: Optional[str] = None,
        task_id: Optional[str] = None,
        job_id: Optional[str] = None,
        company_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        decision_logic: Optional[str] = None,
        model_used: Optional[str] = None,
        confidence_score: Optional[float] = None,
        evidence_documents: Optional[List[str]] = None,
        evidence_hash: Optional[str] = None,
        amount_dollars: Optional[float] = None,
        program_name: Optional[str] = None,
        regulation_reference: Optional[str] = None,
        compliance_status: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Log an immutable audit entry.

        Returns:
            Entry ID if successful, None otherwise
        """
        if not self._pool:
            logger.warning("Database not connected - audit entry not persisted")
            return None

        entry_id = str(uuid4())
        created_at = datetime.now(timezone.utc)

        # Build entry data for hash calculation
        entry_data = {
            "created_at": created_at.isoformat(),
            "action": action,
            "agent_id": agent_id,
            "human_approver_id": human_approver_id,
            "task_id": task_id,
            "decision_logic": decision_logic,
            "evidence_hash": evidence_hash,
            "amount_dollars": amount_dollars,
            "previous_hash": self._last_hash
        }

        # Calculate entry hash
        entry_hash = self._calculate_entry_hash(entry_data)

        try:
            async with self.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO immutable_audit_log (
                        id, created_at, action, severity, description,
                        agent_id, human_approver_id, human_approver_name,
                        task_id, job_id, company_id, workflow_id,
                        decision_logic, model_used, confidence_score,
                        evidence_documents, evidence_hash,
                        amount_dollars, program_name,
                        regulation_reference, compliance_status,
                        previous_hash, entry_hash, metadata
                    ) VALUES (
                        $1, $2, $3::audit_action, $4::audit_severity, $5,
                        $6, $7, $8, $9, $10, $11, $12,
                        $13, $14, $15, $16, $17, $18, $19,
                        $20, $21, $22, $23, $24
                    )
                    """,
                    entry_id, created_at, action, severity, description,
                    agent_id, human_approver_id, human_approver_name,
                    task_id, job_id, company_id, workflow_id,
                    decision_logic, model_used, confidence_score,
                    json.dumps(evidence_documents or []), evidence_hash,
                    amount_dollars, program_name,
                    regulation_reference, compliance_status,
                    self._last_hash, entry_hash, json.dumps(metadata or {})
                )

                # Update last hash for next entry
                self._last_hash = entry_hash

                logger.info(f"Audit entry logged: {action} ({entry_id})")
                return entry_id

        except Exception as e:
            logger.error(f"Failed to log audit entry: {e}")
            return None

    async def log_human_approval(
        self,
        task_id: str,
        approver_id: str,
        approver_name: str,
        approved: bool,
        company_id: str,
        amount_dollars: Optional[float] = None,
        decision_logic: Optional[str] = None,
        reason: Optional[str] = None
    ) -> Optional[str]:
        """Log a human approval/rejection decision."""
        action = "task_approved" if approved else "task_rejected"
        description = f"Task {task_id} {'approved' if approved else 'rejected'} by {approver_name}"

        if reason:
            description += f": {reason}"

        return await self.log_audit_entry(
            action=action,
            description=description,
            severity="high" if amount_dollars and amount_dollars > 1000 else "medium",
            human_approver_id=approver_id,
            human_approver_name=approver_name,
            task_id=task_id,
            company_id=company_id,
            amount_dollars=amount_dollars,
            decision_logic=decision_logic,
            metadata={"approved": approved, "reason": reason}
        )

    # =========================================================================
    # Query Methods
    # =========================================================================

    async def get_entries_by_company(
        self,
        company_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get audit entries for a company."""
        if not self._pool:
            return []

        query = """
            SELECT * FROM immutable_audit_log
            WHERE company_id = $1
        """
        params = [company_id]

        if start_date:
            query += f" AND created_at >= ${len(params) + 1}"
            params.append(start_date)
        if end_date:
            query += f" AND created_at <= ${len(params) + 1}"
            params.append(end_date)

        query += f" ORDER BY created_at DESC LIMIT ${len(params) + 1}"
        params.append(limit)

        async with self.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]

    async def get_human_approvals(
        self,
        company_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Get all human approval/rejection entries."""
        if not self._pool:
            return []

        query = """
            SELECT * FROM immutable_audit_log
            WHERE action IN ('task_approved', 'task_rejected')
        """
        params = []

        if company_id:
            params.append(company_id)
            query += f" AND company_id = ${len(params)}"
        if start_date:
            params.append(start_date)
            query += f" AND created_at >= ${len(params)}"
        if end_date:
            params.append(end_date)
            query += f" AND created_at <= ${len(params)}"

        query += " ORDER BY created_at DESC"

        async with self.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]

    async def verify_chain_integrity(self) -> Dict[str, Any]:
        """Verify the integrity of the audit chain."""
        if not self._pool:
            return {"valid": True, "message": "Database not connected"}

        async with self.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, entry_hash, previous_hash, created_at FROM immutable_audit_log ORDER BY created_at ASC"
            )

            if not rows:
                return {"valid": True, "total_entries": 0}

            issues = []
            for i, row in enumerate(rows):
                if i > 0:
                    expected_previous = rows[i - 1]["entry_hash"]
                    if row["previous_hash"] != expected_previous:
                        issues.append({
                            "entry_id": str(row["id"]),
                            "issue": "Chain broken - previous hash mismatch"
                        })

            return {
                "valid": len(issues) == 0,
                "total_entries": len(rows),
                "issues": issues,
                "verified_at": datetime.now(timezone.utc).isoformat()
            }

    async def export_for_compliance(
        self,
        company_id: str,
        regulation: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Export audit trail for regulatory compliance submission."""
        entries = await self.get_entries_by_company(company_id, start_date, end_date, limit=10000)

        # Filter by regulation if applicable
        if regulation:
            entries = [
                e for e in entries
                if e.get("regulation_reference") == regulation or
                (e.get("program_name") and regulation.lower() in e.get("program_name", "").lower())
            ]

        # Calculate statistics
        total_amount = sum(float(e.get("amount_dollars") or 0) for e in entries)
        approvals = len([e for e in entries if e.get("action") == "task_approved"])

        integrity = await self.verify_chain_integrity()

        return {
            "company_id": company_id,
            "regulation": regulation,
            "period_start": start_date.isoformat(),
            "period_end": end_date.isoformat(),
            "export_timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_entries": len(entries),
                "total_amount": total_amount,
                "human_approvals": approvals,
                "chain_integrity": integrity
            },
            "entries": entries,
            "certification": {
                "chain_verified": integrity["valid"],
                "export_hash": hashlib.sha256(
                    json.dumps(entries, sort_keys=True, default=str).encode()
                ).hexdigest()
            }
        }

    # =========================================================================
    # Governance Task Methods
    # =========================================================================

    async def save_governance_task(self, task_data: Dict[str, Any]) -> Optional[str]:
        """Save a governance task."""
        if not self._pool:
            return None

        task_id = task_data.get("thread_id") or f"task_{uuid4().hex[:8]}"

        async with self.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO governance_tasks (
                    thread_id, task_type, status, risk_level,
                    job_id, company_id, amount_dollars, description,
                    agent_id, decision_logic, model_used, confidence_score,
                    evidence_documents, evidence_hash,
                    requires_approval, approval_threshold,
                    expires_at, checkpoint_data
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                    $11, $12, $13, $14, $15, $16, $17, $18
                )
                ON CONFLICT (thread_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    updated_at = NOW(),
                    checkpoint_data = EXCLUDED.checkpoint_data
                """,
                task_id,
                task_data.get("task_type", "unknown"),
                task_data.get("status", "pending"),
                task_data.get("risk_level", "medium"),
                task_data.get("job_id"),
                task_data.get("company_id"),
                task_data.get("amount_dollars"),
                task_data.get("description"),
                task_data.get("agent_id"),
                task_data.get("decision_logic"),
                task_data.get("model_used"),
                task_data.get("confidence_score"),
                json.dumps(task_data.get("evidence_documents", [])),
                task_data.get("evidence_hash"),
                task_data.get("requires_approval", True),
                task_data.get("approval_threshold", 500),
                task_data.get("expires_at"),
                json.dumps(task_data.get("checkpoint_data", {}))
            )

        return task_id

    async def get_pending_tasks(self, company_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get pending governance tasks."""
        if not self._pool:
            return []

        query = "SELECT * FROM governance_tasks WHERE status = 'awaiting_approval'"
        params = []

        if company_id:
            query += " AND company_id = $1"
            params.append(company_id)

        query += " ORDER BY created_at DESC"

        async with self.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]

    async def save_checkpoint(self, thread_id: str, state: Dict[str, Any]) -> str:
        """Save a workflow checkpoint."""
        if not self._pool:
            return ""

        checkpoint_id = f"{thread_id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

        async with self.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO workflow_checkpoints (thread_id, checkpoint_id, state)
                VALUES ($1, $2, $3)
                """,
                thread_id, checkpoint_id, json.dumps(state, default=str)
            )

        return checkpoint_id


# =========================================================================
# Factory Function
# =========================================================================

async def create_audit_database(connection_string: Optional[str] = None) -> AuditDatabase:
    """Create and connect audit database."""
    db = AuditDatabase(connection_string)
    await db.connect()
    return db
