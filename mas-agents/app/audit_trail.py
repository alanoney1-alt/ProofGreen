"""
ProofGreen MAS - Immutable Audit Trail System
Provides tamper-proof logging for SB 253 and SEC compliance.

This module implements a blockchain-style audit log where each entry
is cryptographically linked to the previous one, making tampering detectable.
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


class AuditAction(str, Enum):
    """Types of auditable actions."""
    # Approval actions
    TASK_CREATED = "task_created"
    TASK_APPROVED = "task_approved"
    TASK_REJECTED = "task_rejected"
    TASK_EXPIRED = "task_expired"

    # Agent actions
    AGENT_DECISION = "agent_decision"
    AGENT_CALCULATION = "agent_calculation"
    AGENT_FILING = "agent_filing"

    # Document actions
    DOCUMENT_GENERATED = "document_generated"
    CERTIFICATE_ISSUED = "certificate_issued"
    REPORT_SUBMITTED = "report_submitted"

    # Compliance actions
    COMPLIANCE_CHECK = "compliance_check"
    REBATE_SUBMITTED = "rebate_submitted"
    TAX_CREDIT_FILED = "tax_credit_filed"

    # Ledger actions
    TRANSACTION_RECORDED = "transaction_recorded"
    LEDGER_RECALCULATED = "ledger_recalculated"


class AuditSeverity(str, Enum):
    """Severity levels for audit entries."""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AuditEntry:
    """
    Immutable audit log entry with cryptographic integrity.

    Each entry contains:
    - Unique ID and timestamp
    - Action type and severity
    - Agent and human actor identifiers
    - Decision logic/reasoning from AI
    - Evidence hash (SHA-256 of source documents)
    - Previous entry hash (blockchain-style linking)
    """
    id: UUID = field(default_factory=uuid4)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Action details
    action: AuditAction = AuditAction.AGENT_DECISION
    severity: AuditSeverity = AuditSeverity.INFO
    description: str = ""

    # Actor identification
    agent_id: Optional[str] = None  # AI agent that made the decision
    human_approver_id: Optional[str] = None  # Human who approved (for HITL)
    human_approver_name: Optional[str] = None

    # Decision context
    task_id: Optional[str] = None
    job_id: Optional[str] = None
    company_id: Optional[str] = None

    # AI reasoning (critical for audits)
    decision_logic: Optional[str] = None  # The prompt/reasoning used by Claude
    model_used: Optional[str] = None  # e.g., "claude-3-opus-20240229"
    confidence_score: Optional[float] = None

    # Evidence integrity
    evidence_documents: List[str] = field(default_factory=list)  # Document IDs/paths
    evidence_hash: Optional[str] = None  # SHA-256 of combined evidence

    # Financial details (for tax/rebate audits)
    amount_dollars: Optional[float] = None
    program_name: Optional[str] = None  # e.g., "IRA Section 25C"

    # Compliance details
    regulation_reference: Optional[str] = None  # e.g., "CA SB 253"
    compliance_status: Optional[str] = None

    # Chain integrity
    previous_hash: Optional[str] = None

    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def entry_hash(self) -> str:
        """Generate SHA-256 hash of this entry for chain integrity."""
        hash_content = {
            "id": str(self.id),
            "timestamp": self.timestamp.isoformat(),
            "action": self.action.value,
            "agent_id": self.agent_id,
            "human_approver_id": self.human_approver_id,
            "task_id": self.task_id,
            "decision_logic": self.decision_logic,
            "evidence_hash": self.evidence_hash,
            "amount_dollars": self.amount_dollars,
            "previous_hash": self.previous_hash
        }
        content_str = json.dumps(hash_content, sort_keys=True, default=str)
        return hashlib.sha256(content_str.encode()).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        """Convert entry to dictionary for storage/API."""
        return {
            "id": str(self.id),
            "timestamp": self.timestamp.isoformat(),
            "action": self.action.value,
            "severity": self.severity.value,
            "description": self.description,
            "agent_id": self.agent_id,
            "human_approver_id": self.human_approver_id,
            "human_approver_name": self.human_approver_name,
            "task_id": self.task_id,
            "job_id": self.job_id,
            "company_id": self.company_id,
            "decision_logic": self.decision_logic,
            "model_used": self.model_used,
            "confidence_score": self.confidence_score,
            "evidence_documents": self.evidence_documents,
            "evidence_hash": self.evidence_hash,
            "amount_dollars": self.amount_dollars,
            "program_name": self.program_name,
            "regulation_reference": self.regulation_reference,
            "compliance_status": self.compliance_status,
            "previous_hash": self.previous_hash,
            "entry_hash": self.entry_hash,
            "metadata": self.metadata
        }


class ImmutableAuditTrail:
    """
    Immutable audit trail with blockchain-style integrity verification.

    Provides:
    - Tamper-proof logging of all agent decisions
    - Human approval tracking for HITL workflows
    - Evidence hashing for document integrity
    - Chain verification for audit completeness
    - Export functions for regulatory submissions
    """

    def __init__(self, db_connection: Optional[Any] = None):
        self._entries: Dict[str, AuditEntry] = {}
        self._chain: List[str] = []  # Chain of entry hashes
        self._db = db_connection

    def _calculate_evidence_hash(self, documents: List[str]) -> str:
        """Calculate combined SHA-256 hash of evidence documents."""
        combined = "|".join(sorted(documents))
        return hashlib.sha256(combined.encode()).hexdigest()

    def log_agent_decision(
        self,
        agent_id: str,
        action: AuditAction,
        description: str,
        decision_logic: str,
        task_id: Optional[str] = None,
        job_id: Optional[str] = None,
        company_id: Optional[str] = None,
        evidence_documents: Optional[List[str]] = None,
        model_used: Optional[str] = None,
        confidence_score: Optional[float] = None,
        amount_dollars: Optional[float] = None,
        program_name: Optional[str] = None,
        severity: AuditSeverity = AuditSeverity.INFO,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AuditEntry:
        """
        Log an AI agent decision to the audit trail.

        This is the primary method for recording agent actions that
        may be subject to regulatory review.
        """
        previous_hash = self._chain[-1] if self._chain else None

        evidence_hash = None
        if evidence_documents:
            evidence_hash = self._calculate_evidence_hash(evidence_documents)

        entry = AuditEntry(
            action=action,
            severity=severity,
            description=description,
            agent_id=agent_id,
            task_id=task_id,
            job_id=job_id,
            company_id=company_id,
            decision_logic=decision_logic,
            model_used=model_used,
            confidence_score=confidence_score,
            evidence_documents=evidence_documents or [],
            evidence_hash=evidence_hash,
            amount_dollars=amount_dollars,
            program_name=program_name,
            previous_hash=previous_hash,
            metadata=metadata or {}
        )

        self._store_entry(entry)
        logger.info(f"Audit: {action.value} by agent {agent_id}")
        return entry

    def log_human_approval(
        self,
        task_id: str,
        human_approver_id: str,
        human_approver_name: str,
        approved: bool,
        agent_id: Optional[str] = None,
        decision_logic: Optional[str] = None,
        job_id: Optional[str] = None,
        company_id: Optional[str] = None,
        amount_dollars: Optional[float] = None,
        program_name: Optional[str] = None,
        evidence_hash: Optional[str] = None,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AuditEntry:
        """
        Log a human approval/rejection decision.

        Critical for HITL workflows - records who approved what and when.
        """
        previous_hash = self._chain[-1] if self._chain else None

        action = AuditAction.TASK_APPROVED if approved else AuditAction.TASK_REJECTED
        severity = AuditSeverity.HIGH if amount_dollars and amount_dollars > 1000 else AuditSeverity.MEDIUM

        entry = AuditEntry(
            action=action,
            severity=severity,
            description=f"Task {task_id} {'approved' if approved else 'rejected'} by {human_approver_name}",
            agent_id=agent_id,
            human_approver_id=human_approver_id,
            human_approver_name=human_approver_name,
            task_id=task_id,
            job_id=job_id,
            company_id=company_id,
            decision_logic=decision_logic,
            evidence_hash=evidence_hash,
            amount_dollars=amount_dollars,
            program_name=program_name,
            previous_hash=previous_hash,
            metadata={
                **(metadata or {}),
                "approval_reason": reason if reason else None,
                "approved": approved
            }
        )

        self._store_entry(entry)
        logger.info(f"Audit: Human {'approval' if approved else 'rejection'} by {human_approver_name}")
        return entry

    def log_compliance_check(
        self,
        agent_id: str,
        job_id: str,
        company_id: str,
        regulation_reference: str,
        compliance_status: str,
        decision_logic: str,
        evidence_documents: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AuditEntry:
        """Log a compliance check result."""
        previous_hash = self._chain[-1] if self._chain else None

        evidence_hash = None
        if evidence_documents:
            evidence_hash = self._calculate_evidence_hash(evidence_documents)

        entry = AuditEntry(
            action=AuditAction.COMPLIANCE_CHECK,
            severity=AuditSeverity.MEDIUM,
            description=f"Compliance check for {regulation_reference}: {compliance_status}",
            agent_id=agent_id,
            job_id=job_id,
            company_id=company_id,
            decision_logic=decision_logic,
            evidence_documents=evidence_documents or [],
            evidence_hash=evidence_hash,
            regulation_reference=regulation_reference,
            compliance_status=compliance_status,
            previous_hash=previous_hash,
            metadata=metadata or {}
        )

        self._store_entry(entry)
        return entry

    def log_financial_filing(
        self,
        agent_id: str,
        task_id: str,
        job_id: str,
        company_id: str,
        filing_type: str,  # "tax_credit" or "rebate"
        program_name: str,
        amount_dollars: float,
        decision_logic: str,
        human_approver_id: Optional[str] = None,
        human_approver_name: Optional[str] = None,
        evidence_documents: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AuditEntry:
        """Log a tax credit or rebate filing."""
        previous_hash = self._chain[-1] if self._chain else None

        action = AuditAction.TAX_CREDIT_FILED if filing_type == "tax_credit" else AuditAction.REBATE_SUBMITTED
        severity = AuditSeverity.HIGH if amount_dollars > 500 else AuditSeverity.MEDIUM

        evidence_hash = None
        if evidence_documents:
            evidence_hash = self._calculate_evidence_hash(evidence_documents)

        entry = AuditEntry(
            action=action,
            severity=severity,
            description=f"{filing_type.replace('_', ' ').title()}: ${amount_dollars:,.2f} ({program_name})",
            agent_id=agent_id,
            human_approver_id=human_approver_id,
            human_approver_name=human_approver_name,
            task_id=task_id,
            job_id=job_id,
            company_id=company_id,
            decision_logic=decision_logic,
            evidence_documents=evidence_documents or [],
            evidence_hash=evidence_hash,
            amount_dollars=amount_dollars,
            program_name=program_name,
            previous_hash=previous_hash,
            metadata=metadata or {}
        )

        self._store_entry(entry)
        logger.info(f"Audit: {filing_type} filed for ${amount_dollars:,.2f}")
        return entry

    def _store_entry(self, entry: AuditEntry):
        """Store entry and update chain."""
        self._entries[str(entry.id)] = entry
        self._chain.append(entry.entry_hash)

        # Persist to database if available
        if self._db:
            self._persist_entry(entry)

    def _persist_entry(self, entry: AuditEntry):
        """Persist entry to database (implement based on DB choice)."""
        # In production, this would write to PostgreSQL, MongoDB, etc.
        pass

    def verify_chain_integrity(self) -> Dict[str, Any]:
        """
        Verify the integrity of the entire audit chain.

        Returns verification result with any detected tampering.
        """
        if not self._chain:
            return {"valid": True, "message": "Empty chain"}

        issues = []
        entries_list = sorted(self._entries.values(), key=lambda e: e.timestamp)

        for i, entry in enumerate(entries_list):
            # Verify hash matches
            if entry.entry_hash != self._chain[i]:
                issues.append({
                    "entry_id": str(entry.id),
                    "issue": "Hash mismatch - possible tampering detected"
                })

            # Verify chain linkage
            if i > 0:
                if entry.previous_hash != self._chain[i - 1]:
                    issues.append({
                        "entry_id": str(entry.id),
                        "issue": "Chain broken - previous hash mismatch"
                    })

        return {
            "valid": len(issues) == 0,
            "total_entries": len(self._chain),
            "issues": issues,
            "verified_at": datetime.now(timezone.utc).isoformat()
        }

    def get_entry(self, entry_id: str) -> Optional[AuditEntry]:
        """Retrieve a specific audit entry."""
        return self._entries.get(entry_id)

    def get_entries_by_task(self, task_id: str) -> List[AuditEntry]:
        """Get all audit entries for a specific task."""
        return [
            entry for entry in self._entries.values()
            if entry.task_id == task_id
        ]

    def get_entries_by_job(self, job_id: str) -> List[AuditEntry]:
        """Get all audit entries for a specific job."""
        return [
            entry for entry in self._entries.values()
            if entry.job_id == job_id
        ]

    def get_entries_by_company(
        self,
        company_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[AuditEntry]:
        """Get audit entries for a company within date range."""
        entries = [
            entry for entry in self._entries.values()
            if entry.company_id == company_id
        ]

        if start_date:
            entries = [e for e in entries if e.timestamp >= start_date]
        if end_date:
            entries = [e for e in entries if e.timestamp <= end_date]

        return sorted(entries, key=lambda e: e.timestamp, reverse=True)

    def get_human_approvals(
        self,
        company_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[AuditEntry]:
        """Get all human approval/rejection entries."""
        entries = [
            entry for entry in self._entries.values()
            if entry.action in [AuditAction.TASK_APPROVED, AuditAction.TASK_REJECTED]
        ]

        if company_id:
            entries = [e for e in entries if e.company_id == company_id]
        if start_date:
            entries = [e for e in entries if e.timestamp >= start_date]
        if end_date:
            entries = [e for e in entries if e.timestamp <= end_date]

        return sorted(entries, key=lambda e: e.timestamp, reverse=True)

    def export_for_regulatory_submission(
        self,
        company_id: str,
        regulation: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Export audit trail for regulatory submission (SB 253, SEC, etc.).

        Returns formatted data suitable for compliance reporting.
        """
        entries = self.get_entries_by_company(company_id, start_date, end_date)

        # Filter by regulation if specified
        if regulation:
            entries = [
                e for e in entries
                if e.regulation_reference == regulation or
                e.program_name and regulation.lower() in e.program_name.lower()
            ]

        # Calculate summary statistics
        total_filings = len([e for e in entries if e.action in [
            AuditAction.TAX_CREDIT_FILED,
            AuditAction.REBATE_SUBMITTED
        ]])
        total_amount = sum(e.amount_dollars or 0 for e in entries)
        human_approvals = len([e for e in entries if e.action == AuditAction.TASK_APPROVED])

        return {
            "company_id": company_id,
            "regulation": regulation,
            "period_start": start_date.isoformat(),
            "period_end": end_date.isoformat(),
            "export_timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_entries": len(entries),
                "total_filings": total_filings,
                "total_amount_dollars": total_amount,
                "human_approvals": human_approvals,
                "chain_integrity": self.verify_chain_integrity()
            },
            "entries": [e.to_dict() for e in entries],
            "certification": {
                "statement": "This audit trail has been maintained in accordance with immutable logging standards.",
                "chain_verified": self.verify_chain_integrity()["valid"],
                "export_hash": hashlib.sha256(
                    json.dumps([e.to_dict() for e in entries], sort_keys=True, default=str).encode()
                ).hexdigest()
            }
        }

    def generate_compliance_report(
        self,
        company_id: str,
        reporting_year: int
    ) -> str:
        """Generate a human-readable compliance report."""
        start_date = datetime(reporting_year, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(reporting_year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)

        entries = self.get_entries_by_company(company_id, start_date, end_date)
        integrity = self.verify_chain_integrity()

        lines = [
            "=" * 60,
            "PROOFGREEN AUDIT TRAIL COMPLIANCE REPORT",
            "=" * 60,
            f"Company ID: {company_id}",
            f"Reporting Period: {reporting_year}",
            f"Generated: {datetime.now(timezone.utc).isoformat()}",
            "",
            "SUMMARY",
            "-" * 40,
            f"Total Audit Entries: {len(entries)}",
            f"Chain Integrity: {'VERIFIED' if integrity['valid'] else 'COMPROMISED'}",
            "",
            "ACTIONS BY TYPE",
            "-" * 40
        ]

        # Count by action type
        action_counts = {}
        for entry in entries:
            action_counts[entry.action.value] = action_counts.get(entry.action.value, 0) + 1

        for action, count in sorted(action_counts.items()):
            lines.append(f"  {action}: {count}")

        # Human approvals section
        approvals = [e for e in entries if e.action == AuditAction.TASK_APPROVED]
        rejections = [e for e in entries if e.action == AuditAction.TASK_REJECTED]

        lines.extend([
            "",
            "HUMAN-IN-THE-LOOP DECISIONS",
            "-" * 40,
            f"Total Approvals: {len(approvals)}",
            f"Total Rejections: {len(rejections)}",
            f"Approval Rate: {len(approvals) / (len(approvals) + len(rejections)) * 100:.1f}%" if approvals or rejections else "N/A"
        ])

        # Financial summary
        financial_entries = [
            e for e in entries
            if e.action in [AuditAction.TAX_CREDIT_FILED, AuditAction.REBATE_SUBMITTED]
        ]
        total_filed = sum(e.amount_dollars or 0 for e in financial_entries)

        lines.extend([
            "",
            "FINANCIAL FILINGS",
            "-" * 40,
            f"Total Filings: {len(financial_entries)}",
            f"Total Amount: ${total_filed:,.2f}"
        ])

        lines.extend([
            "",
            "=" * 60,
            "END OF REPORT",
            "=" * 60
        ])

        return "\n".join(lines)


# Factory function
def create_audit_trail(db_connection: Optional[Any] = None) -> ImmutableAuditTrail:
    """Create a new audit trail instance."""
    return ImmutableAuditTrail(db_connection)
