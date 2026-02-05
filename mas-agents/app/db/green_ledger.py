"""
ProofGreen MAS - Green Ledger Database
PostgreSQL schema for final AgentState storage with encrypted incentives.
"""

import os
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import asyncpg

from config.settings import settings


# ========== ENCRYPTION ==========

class IncentiveEncryption:
    """AES-256 encryption for incentive data."""

    def __init__(self, master_key: Optional[str] = None):
        """Initialize with master key."""
        self._master_key = master_key or os.getenv(
            "INCENTIVE_ENCRYPTION_KEY",
            settings.JWT_SECRET_KEY
        )
        self._salt = b"proofgreen_incentive_salt_2026"
        self._fernet = self._create_fernet()

    def _create_fernet(self) -> Fernet:
        """Create Fernet cipher from master key."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self._salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(self._master_key.encode()))
        return Fernet(key)

    def encrypt(self, data: Any) -> str:
        """Encrypt data and return base64 string."""
        plaintext = json.dumps(data, default=str).encode()
        encrypted = self._fernet.encrypt(plaintext)
        return base64.b64encode(encrypted).decode()

    def decrypt(self, encrypted_data: str) -> Any:
        """Decrypt base64 string and return data."""
        ciphertext = base64.b64decode(encrypted_data)
        plaintext = self._fernet.decrypt(ciphertext)
        return json.loads(plaintext.decode())


# Global encryption instance
_encryption = IncentiveEncryption()


# ========== DATA CLASSES ==========

@dataclass
class GreenLedgerEntry:
    """A single entry in the Green Ledger."""
    id: str
    job_id: str
    company_id: str
    customer_id: Optional[str]

    # Equipment data
    equipment_model: Optional[str]
    equipment_serial: Optional[str]
    equipment_type: Optional[str]
    refrigerant: Optional[str]
    seer2_rating: Optional[float]

    # Compliance
    is_compliant: bool
    compliance_status: str
    violations: List[str]
    compliance_risk_score: int

    # Incentives (encrypted at rest)
    incentives_encrypted: str
    total_incentive_amount: float

    # Carbon metrics
    carbon_baseline: float
    carbon_savings: float
    carbon_avoided_kg: float

    # Workflow state
    workflow_status: str
    approval_status: Optional[str]
    approved_by: Optional[str]
    approved_at: Optional[datetime]

    # Location
    state: str
    zip_code: str

    # Timestamps
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]


# ========== DATABASE SCHEMA ==========

GREEN_LEDGER_SCHEMA = """
-- Green Ledger: Final AgentState storage with encrypted incentives
CREATE TABLE IF NOT EXISTS green_ledger (
    id VARCHAR(255) PRIMARY KEY,
    job_id VARCHAR(255) UNIQUE NOT NULL,
    company_id VARCHAR(255) NOT NULL,
    customer_id VARCHAR(255),

    -- Equipment Data
    equipment_model VARCHAR(255),
    equipment_serial VARCHAR(255),
    equipment_type VARCHAR(100),
    refrigerant VARCHAR(50),
    seer2_rating FLOAT,

    -- Compliance
    is_compliant BOOLEAN DEFAULT FALSE,
    compliance_status VARCHAR(50),
    violations TEXT[],
    compliance_risk_score INTEGER DEFAULT 0,

    -- Incentives (AES-256 Encrypted)
    incentives_encrypted TEXT NOT NULL,
    total_incentive_amount FLOAT DEFAULT 0,

    -- Carbon Metrics
    carbon_baseline FLOAT DEFAULT 0,
    carbon_savings FLOAT DEFAULT 0,
    carbon_avoided_kg FLOAT DEFAULT 0,

    -- Workflow State
    workflow_status VARCHAR(50) NOT NULL,
    approval_status VARCHAR(50),
    approved_by VARCHAR(255),
    approved_at TIMESTAMP,

    -- Location
    state VARCHAR(10),
    zip_code VARCHAR(20),

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,

    -- Indexes
    CONSTRAINT fk_company FOREIGN KEY (company_id)
        REFERENCES companies(id) ON DELETE SET NULL
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_ledger_company ON green_ledger(company_id);
CREATE INDEX IF NOT EXISTS idx_ledger_customer ON green_ledger(customer_id);
CREATE INDEX IF NOT EXISTS idx_ledger_status ON green_ledger(workflow_status);
CREATE INDEX IF NOT EXISTS idx_ledger_compliance ON green_ledger(is_compliant);
CREATE INDEX IF NOT EXISTS idx_ledger_state ON green_ledger(state);
CREATE INDEX IF NOT EXISTS idx_ledger_created ON green_ledger(created_at);

-- Trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_green_ledger_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_ledger_updated ON green_ledger;
CREATE TRIGGER trigger_ledger_updated
    BEFORE UPDATE ON green_ledger
    FOR EACH ROW
    EXECUTE FUNCTION update_green_ledger_timestamp();

-- Audit log for ledger changes
CREATE TABLE IF NOT EXISTS green_ledger_audit (
    id SERIAL PRIMARY KEY,
    ledger_id VARCHAR(255) NOT NULL,
    action VARCHAR(50) NOT NULL,
    old_values JSONB,
    new_values JSONB,
    changed_by VARCHAR(255),
    changed_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_ledger ON green_ledger_audit(ledger_id);
"""


# ========== GREEN LEDGER CLASS ==========

class GreenLedger:
    """
    Green Ledger database interface.
    Stores final AgentState with encrypted incentives.
    """

    def __init__(self, db_pool: Optional[asyncpg.Pool] = None):
        """Initialize with database pool."""
        self.pool = db_pool
        self.encryption = _encryption

    async def initialize(self, connection_string: Optional[str] = None):
        """Initialize database connection and schema."""
        if not self.pool:
            conn_string = connection_string or settings.DATABASE_URL
            self.pool = await asyncpg.create_pool(conn_string)

        async with self.pool.acquire() as conn:
            # Create companies table if not exists (referenced by foreign key)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS companies (
                    id VARCHAR(255) PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            await conn.execute(GREEN_LEDGER_SCHEMA)

    async def save_entry(
        self,
        job_id: str,
        company_id: str,
        state: Dict,
        approved_by: Optional[str] = None
    ) -> str:
        """
        Save workflow state to Green Ledger.

        Args:
            job_id: Job identifier
            company_id: Company identifier
            state: Final AgentState from workflow
            approved_by: Approver ID if applicable

        Returns:
            Ledger entry ID
        """
        import uuid
        entry_id = f"ledger_{uuid.uuid4().hex[:12]}"

        # Encrypt incentives
        incentives = state.get("incentives", [])
        incentives_encrypted = self.encryption.encrypt(incentives)

        # Extract equipment data
        equipment = state.get("equipment_data", {})

        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO green_ledger (
                    id, job_id, company_id, customer_id,
                    equipment_model, equipment_serial, equipment_type,
                    refrigerant, seer2_rating,
                    is_compliant, compliance_status, violations, compliance_risk_score,
                    incentives_encrypted, total_incentive_amount,
                    carbon_baseline, carbon_savings, carbon_avoided_kg,
                    workflow_status, approval_status, approved_by, approved_at,
                    state, zip_code, completed_at
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13,
                    $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25
                )
                ON CONFLICT (job_id) DO UPDATE SET
                    is_compliant = EXCLUDED.is_compliant,
                    compliance_status = EXCLUDED.compliance_status,
                    violations = EXCLUDED.violations,
                    incentives_encrypted = EXCLUDED.incentives_encrypted,
                    total_incentive_amount = EXCLUDED.total_incentive_amount,
                    carbon_savings = EXCLUDED.carbon_savings,
                    carbon_avoided_kg = EXCLUDED.carbon_avoided_kg,
                    workflow_status = EXCLUDED.workflow_status,
                    approval_status = EXCLUDED.approval_status,
                    approved_by = EXCLUDED.approved_by,
                    approved_at = EXCLUDED.approved_at,
                    completed_at = EXCLUDED.completed_at
            """,
                entry_id,
                job_id,
                company_id,
                state.get("customer_id"),
                equipment.get("model"),
                equipment.get("serial_number"),
                equipment.get("equipment_type"),
                equipment.get("refrigerant"),
                equipment.get("seer2"),
                state.get("is_compliant", False),
                state.get("compliance_status", "unknown"),
                state.get("violations", []),
                state.get("compliance_risk_score", 0),
                incentives_encrypted,
                state.get("total_incentive_amount", 0),
                state.get("carbon_baseline", 0),
                state.get("carbon_savings", 0),
                state.get("carbon_baseline", 0) - state.get("carbon_savings", 0),
                state.get("status", "completed"),
                state.get("approval_status"),
                approved_by,
                datetime.utcnow() if approved_by else None,
                state.get("state", "CA"),
                state.get("zip_code", ""),
                datetime.utcnow() if state.get("status") == "completed" else None
            )

        return entry_id

    async def get_entry(self, job_id: str) -> Optional[Dict]:
        """
        Get ledger entry by job ID.

        Args:
            job_id: Job identifier

        Returns:
            Ledger entry with decrypted incentives
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM green_ledger WHERE job_id = $1
            """, job_id)

            if row:
                entry = dict(row)
                # Decrypt incentives
                if entry.get("incentives_encrypted"):
                    entry["incentives"] = self.encryption.decrypt(
                        entry["incentives_encrypted"]
                    )
                    del entry["incentives_encrypted"]
                return entry

        return None

    async def get_company_ledger(
        self,
        company_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        Get all ledger entries for a company.

        Args:
            company_id: Company identifier
            start_date: Optional start date filter
            end_date: Optional end date filter
            limit: Maximum entries to return

        Returns:
            List of ledger entries
        """
        query = """
            SELECT * FROM green_ledger
            WHERE company_id = $1
        """
        params = [company_id]
        param_idx = 2

        if start_date:
            query += f" AND created_at >= ${param_idx}"
            params.append(start_date)
            param_idx += 1

        if end_date:
            query += f" AND created_at <= ${param_idx}"
            params.append(end_date)
            param_idx += 1

        query += f" ORDER BY created_at DESC LIMIT ${param_idx}"
        params.append(limit)

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

            entries = []
            for row in rows:
                entry = dict(row)
                if entry.get("incentives_encrypted"):
                    entry["incentives"] = self.encryption.decrypt(
                        entry["incentives_encrypted"]
                    )
                    del entry["incentives_encrypted"]
                entries.append(entry)

            return entries

    async def get_aggregated_metrics(
        self,
        company_id: str,
        period: str = "month"
    ) -> Dict:
        """
        Get aggregated ESG metrics for a company.

        Args:
            company_id: Company identifier
            period: Aggregation period (day, week, month, year)

        Returns:
            Aggregated metrics
        """
        date_trunc = {
            "day": "day",
            "week": "week",
            "month": "month",
            "year": "year"
        }.get(period, "month")

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(f"""
                SELECT
                    COUNT(*) as total_jobs,
                    COUNT(*) FILTER (WHERE is_compliant = true) as compliant_jobs,
                    SUM(total_incentive_amount) as total_incentives,
                    SUM(carbon_avoided_kg) as total_carbon_avoided,
                    AVG(seer2_rating) FILTER (WHERE seer2_rating IS NOT NULL) as avg_seer2,
                    COUNT(DISTINCT customer_id) as unique_customers
                FROM green_ledger
                WHERE company_id = $1
                  AND created_at >= DATE_TRUNC('{date_trunc}', NOW())
            """, company_id)

            return {
                "period": period,
                "total_jobs": row["total_jobs"],
                "compliant_jobs": row["compliant_jobs"],
                "compliance_rate": (row["compliant_jobs"] / row["total_jobs"] * 100)
                    if row["total_jobs"] > 0 else 0,
                "total_incentives": float(row["total_incentives"] or 0),
                "total_carbon_avoided_kg": float(row["total_carbon_avoided"] or 0),
                "avg_seer2": float(row["avg_seer2"] or 0),
                "unique_customers": row["unique_customers"]
            }


# Factory function
async def create_green_ledger() -> GreenLedger:
    """Create and initialize Green Ledger."""
    ledger = GreenLedger()
    await ledger.initialize()
    return ledger


# Singleton instance
_ledger_instance = None


async def get_green_ledger() -> GreenLedger:
    """Get or create singleton Green Ledger instance."""
    global _ledger_instance
    if _ledger_instance is None:
        _ledger_instance = await create_green_ledger()
    return _ledger_instance
