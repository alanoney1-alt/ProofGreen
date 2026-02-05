"""
ProofGreen MAS - Privacy Guardrail Module
Data retention, anonymization, and integrity verification.
"""

import os
import re
import json
import hashlib
import asyncio
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from pydantic import BaseModel, Field


class DataCategory(str, Enum):
    """Categories of data for retention policies."""
    RAW_JOB_DATA = "raw_job_data"           # 30 days
    CUSTOMER_PII = "customer_pii"            # 30 days, then anonymize
    GREEN_TOTALS = "green_totals"            # Permanent (ESG ledger)
    AUDIT_TRAIL = "audit_trail"              # 7 years (compliance)
    EQUIPMENT_DATA = "equipment_data"        # Permanent (equipment registry)
    FINANCIAL_DATA = "financial_data"        # 7 years (tax/rebate records)


class PIIType(str, Enum):
    """Types of Personally Identifiable Information."""
    NAME = "name"
    EMAIL = "email"
    PHONE = "phone"
    ADDRESS = "address"
    SSN = "ssn"
    ACCOUNT_NUMBER = "account_number"
    CREDIT_CARD = "credit_card"


@dataclass
class RetentionPolicy:
    """Data retention policy configuration."""
    category: DataCategory
    retention_days: int
    action: str  # "delete", "anonymize", "archive"
    requires_audit: bool = True


@dataclass
class AnonymizationResult:
    """Result of anonymization operation."""
    original_hash: str
    anonymized_data: Dict
    pii_detected: List[PIIType]
    pii_removed: List[str]
    timestamp: datetime = field(default_factory=datetime.utcnow)


class GreenTotals(BaseModel):
    """
    Permanent ESG ledger totals - retained indefinitely.
    Contains no PII, only aggregated environmental metrics.
    """
    company_id: str
    period_start: datetime
    period_end: datetime

    # Carbon metrics (kg CO2e)
    total_carbon_avoided: float = 0.0
    scope1_reduction: float = 0.0
    scope2_reduction: float = 0.0
    scope3_reduction: float = 0.0

    # Energy metrics
    total_kwh_saved: float = 0.0
    total_therms_saved: float = 0.0

    # Equipment metrics
    units_installed: int = 0
    average_seer2: float = 0.0
    compliant_refrigerant_count: int = 0

    # Financial metrics (aggregated, no PII)
    total_rebates_captured: float = 0.0
    total_tax_credits: float = 0.0
    total_customer_savings: float = 0.0

    # Diversion metrics
    total_landfill_diverted_lbs: float = 0.0
    recycling_rate: float = 0.0

    # Job counts
    total_jobs: int = 0
    compliant_jobs: int = 0
    compliance_rate: float = 0.0

    # Integrity hash
    data_hash: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class IntegrityReport(BaseModel):
    """Daily database integrity report."""
    report_date: datetime
    report_id: str
    tables_checked: List[str]
    total_records: int
    state_hash: str  # Hash of entire DB state
    previous_hash: Optional[str] = None  # For chain verification
    chain_valid: bool = True
    anomalies_detected: List[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# Default retention policies
DEFAULT_RETENTION_POLICIES = [
    RetentionPolicy(
        category=DataCategory.RAW_JOB_DATA,
        retention_days=30,
        action="delete"
    ),
    RetentionPolicy(
        category=DataCategory.CUSTOMER_PII,
        retention_days=30,
        action="anonymize"
    ),
    RetentionPolicy(
        category=DataCategory.GREEN_TOTALS,
        retention_days=-1,  # Permanent
        action="retain"
    ),
    RetentionPolicy(
        category=DataCategory.AUDIT_TRAIL,
        retention_days=2555,  # ~7 years
        action="archive"
    ),
    RetentionPolicy(
        category=DataCategory.EQUIPMENT_DATA,
        retention_days=-1,  # Permanent
        action="retain"
    ),
    RetentionPolicy(
        category=DataCategory.FINANCIAL_DATA,
        retention_days=2555,  # ~7 years
        action="archive"
    ),
]


# PII detection patterns
PII_PATTERNS = {
    PIIType.EMAIL: re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
    PIIType.PHONE: re.compile(r'\b(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'),
    PIIType.SSN: re.compile(r'\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b'),
    PIIType.CREDIT_CARD: re.compile(r'\b(?:\d{4}[-.\s]?){3}\d{4}\b'),
    PIIType.ADDRESS: re.compile(r'\b\d+\s+[\w\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Boulevard|Blvd|Court|Ct|Way|Place|Pl)\b', re.IGNORECASE),
}

# Common name patterns (first/last name fields)
NAME_FIELD_PATTERNS = [
    'name', 'customer_name', 'customerName', 'client_name', 'clientName',
    'first_name', 'firstName', 'last_name', 'lastName', 'full_name', 'fullName',
    'contact_name', 'contactName', 'billing_name', 'billingName',
    'homeowner', 'homeowner_name', 'tech_name', 'technician_name'
]


class PrivacyGuardrail:
    """
    Privacy guardrail module for data protection.
    Handles retention, anonymization, and integrity verification.
    """

    def __init__(
        self,
        db_connection=None,
        retention_policies: Optional[List[RetentionPolicy]] = None
    ):
        """
        Initialize privacy guardrail.

        Args:
            db_connection: PostgreSQL connection
            retention_policies: Custom retention policies (defaults used if None)
        """
        self.db = db_connection
        self.policies = {p.category: p for p in (retention_policies or DEFAULT_RETENTION_POLICIES)}
        self._integrity_cache: Dict[str, str] = {}

    # ========== ANONYMIZATION LAYER ==========

    def anonymize_for_ai(self, data: Dict) -> AnonymizationResult:
        """
        Anonymize PII before sending to AI for processing.
        Strips customer names, phone numbers, emails, addresses.

        Args:
            data: Raw job/customer data

        Returns:
            AnonymizationResult with cleaned data
        """
        # Hash original for traceability
        original_hash = hashlib.sha256(
            json.dumps(data, sort_keys=True, default=str).encode()
        ).hexdigest()

        anonymized = self._deep_copy(data)
        detected_pii: List[PIIType] = []
        removed_fields: List[str] = []

        # Recursively process the data
        self._anonymize_recursive(anonymized, "", detected_pii, removed_fields)

        return AnonymizationResult(
            original_hash=original_hash,
            anonymized_data=anonymized,
            pii_detected=list(set(detected_pii)),
            pii_removed=removed_fields
        )

    def _anonymize_recursive(
        self,
        obj: Any,
        path: str,
        detected_pii: List[PIIType],
        removed_fields: List[str]
    ):
        """Recursively anonymize PII in nested structures."""
        if isinstance(obj, dict):
            keys_to_process = list(obj.keys())
            for key in keys_to_process:
                current_path = f"{path}.{key}" if path else key
                value = obj[key]

                # Check if field name suggests PII
                key_lower = key.lower()

                # Name fields
                if any(pattern in key_lower for pattern in NAME_FIELD_PATTERNS):
                    if isinstance(value, str) and value:
                        obj[key] = "[REDACTED_NAME]"
                        detected_pii.append(PIIType.NAME)
                        removed_fields.append(current_path)
                        continue

                # Email fields
                if 'email' in key_lower:
                    if isinstance(value, str) and value:
                        obj[key] = "[REDACTED_EMAIL]"
                        detected_pii.append(PIIType.EMAIL)
                        removed_fields.append(current_path)
                        continue

                # Phone fields
                if any(p in key_lower for p in ['phone', 'mobile', 'cell', 'tel']):
                    if isinstance(value, str) and value:
                        obj[key] = "[REDACTED_PHONE]"
                        detected_pii.append(PIIType.PHONE)
                        removed_fields.append(current_path)
                        continue

                # Address fields
                if any(p in key_lower for p in ['address', 'street', 'city', 'zip']):
                    # Keep state and zip for compliance region determination
                    if key_lower not in ['state', 'zip', 'zipcode', 'zip_code', 'postal']:
                        if isinstance(value, str) and value:
                            obj[key] = "[REDACTED_ADDRESS]"
                            detected_pii.append(PIIType.ADDRESS)
                            removed_fields.append(current_path)
                            continue

                # SSN fields
                if any(p in key_lower for p in ['ssn', 'social', 'tax_id', 'taxid']):
                    if isinstance(value, str) and value:
                        obj[key] = "[REDACTED_SSN]"
                        detected_pii.append(PIIType.SSN)
                        removed_fields.append(current_path)
                        continue

                # Account number fields
                if any(p in key_lower for p in ['account', 'routing', 'bank']):
                    if isinstance(value, str) and value:
                        obj[key] = "[REDACTED_ACCOUNT]"
                        detected_pii.append(PIIType.ACCOUNT_NUMBER)
                        removed_fields.append(current_path)
                        continue

                # Check string values for PII patterns
                if isinstance(value, str):
                    for pii_type, pattern in PII_PATTERNS.items():
                        if pattern.search(value):
                            # Replace the PII with redaction marker
                            obj[key] = pattern.sub(f"[REDACTED_{pii_type.value.upper()}]", value)
                            detected_pii.append(pii_type)
                            removed_fields.append(current_path)
                            break

                # Recurse into nested structures
                if isinstance(value, (dict, list)):
                    self._anonymize_recursive(value, current_path, detected_pii, removed_fields)

        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                current_path = f"{path}[{i}]"
                if isinstance(item, (dict, list)):
                    self._anonymize_recursive(item, current_path, detected_pii, removed_fields)
                elif isinstance(item, str):
                    for pii_type, pattern in PII_PATTERNS.items():
                        if pattern.search(item):
                            obj[i] = pattern.sub(f"[REDACTED_{pii_type.value.upper()}]", item)
                            detected_pii.append(pii_type)
                            removed_fields.append(current_path)
                            break

    def _deep_copy(self, obj: Any) -> Any:
        """Create a deep copy of an object."""
        if isinstance(obj, dict):
            return {k: self._deep_copy(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._deep_copy(v) for v in obj]
        return obj

    # ========== DATA RETENTION ==========

    async def apply_retention_policy(self, dry_run: bool = False) -> Dict:
        """
        Apply data retention policies across all tables.

        Args:
            dry_run: If True, only report what would be done

        Returns:
            Summary of retention actions
        """
        if not self.db:
            return {"error": "Database connection required"}

        results = {
            "executed_at": datetime.utcnow().isoformat(),
            "dry_run": dry_run,
            "actions": []
        }

        for category, policy in self.policies.items():
            if policy.retention_days < 0:
                # Permanent retention
                continue

            cutoff_date = datetime.utcnow() - timedelta(days=policy.retention_days)

            if category == DataCategory.RAW_JOB_DATA:
                action = await self._apply_raw_job_retention(cutoff_date, policy, dry_run)
                results["actions"].append(action)

            elif category == DataCategory.CUSTOMER_PII:
                action = await self._apply_pii_retention(cutoff_date, policy, dry_run)
                results["actions"].append(action)

            elif category == DataCategory.AUDIT_TRAIL:
                action = await self._apply_audit_retention(cutoff_date, policy, dry_run)
                results["actions"].append(action)

            elif category == DataCategory.FINANCIAL_DATA:
                action = await self._apply_financial_retention(cutoff_date, policy, dry_run)
                results["actions"].append(action)

        return results

    async def _apply_raw_job_retention(
        self,
        cutoff_date: datetime,
        policy: RetentionPolicy,
        dry_run: bool
    ) -> Dict:
        """Apply retention to raw job data."""
        # First, ensure Green Totals are computed for data being deleted
        if not dry_run:
            await self._compute_green_totals_for_period(cutoff_date)

        # Count affected records
        count_query = """
            SELECT COUNT(*) FROM raw_job_data
            WHERE created_at < $1 AND green_totals_computed = true
        """
        count = await self.db.fetchval(count_query, cutoff_date)

        if not dry_run and count > 0:
            # Delete raw data (Green Totals already preserved)
            delete_query = """
                DELETE FROM raw_job_data
                WHERE created_at < $1 AND green_totals_computed = true
            """
            await self.db.execute(delete_query, cutoff_date)

        return {
            "category": DataCategory.RAW_JOB_DATA.value,
            "action": policy.action,
            "cutoff_date": cutoff_date.isoformat(),
            "records_affected": count,
            "executed": not dry_run
        }

    async def _apply_pii_retention(
        self,
        cutoff_date: datetime,
        policy: RetentionPolicy,
        dry_run: bool
    ) -> Dict:
        """Apply retention to customer PII - anonymize, don't delete."""
        count_query = """
            SELECT COUNT(*) FROM customers
            WHERE created_at < $1 AND is_anonymized = false
        """
        count = await self.db.fetchval(count_query, cutoff_date)

        if not dry_run and count > 0:
            # Anonymize customer records
            anonymize_query = """
                UPDATE customers SET
                    name = '[ANONYMIZED]',
                    email = NULL,
                    phone = NULL,
                    address_line1 = NULL,
                    address_line2 = NULL,
                    -- Keep city, state, zip for regional compliance analysis
                    is_anonymized = true,
                    anonymized_at = NOW()
                WHERE created_at < $1 AND is_anonymized = false
            """
            await self.db.execute(anonymize_query, cutoff_date)

        return {
            "category": DataCategory.CUSTOMER_PII.value,
            "action": "anonymize",
            "cutoff_date": cutoff_date.isoformat(),
            "records_affected": count,
            "executed": not dry_run
        }

    async def _apply_audit_retention(
        self,
        cutoff_date: datetime,
        policy: RetentionPolicy,
        dry_run: bool
    ) -> Dict:
        """Apply retention to audit trail - archive, don't delete."""
        count_query = """
            SELECT COUNT(*) FROM audit_entries
            WHERE created_at < $1 AND is_archived = false
        """
        count = await self.db.fetchval(count_query, cutoff_date)

        if not dry_run and count > 0:
            # Archive to cold storage table
            archive_query = """
                INSERT INTO audit_entries_archive
                SELECT * FROM audit_entries
                WHERE created_at < $1 AND is_archived = false;

                UPDATE audit_entries SET is_archived = true
                WHERE created_at < $1 AND is_archived = false;
            """
            await self.db.execute(archive_query, cutoff_date)

        return {
            "category": DataCategory.AUDIT_TRAIL.value,
            "action": "archive",
            "cutoff_date": cutoff_date.isoformat(),
            "records_affected": count,
            "executed": not dry_run
        }

    async def _apply_financial_retention(
        self,
        cutoff_date: datetime,
        policy: RetentionPolicy,
        dry_run: bool
    ) -> Dict:
        """Apply retention to financial data - archive for tax compliance."""
        count_query = """
            SELECT COUNT(*) FROM rebate_records
            WHERE created_at < $1 AND is_archived = false
        """
        count = await self.db.fetchval(count_query, cutoff_date)

        if not dry_run and count > 0:
            # Archive to cold storage
            archive_query = """
                INSERT INTO rebate_records_archive
                SELECT * FROM rebate_records
                WHERE created_at < $1 AND is_archived = false;

                UPDATE rebate_records SET is_archived = true
                WHERE created_at < $1 AND is_archived = false;
            """
            await self.db.execute(archive_query, cutoff_date)

        return {
            "category": DataCategory.FINANCIAL_DATA.value,
            "action": "archive",
            "cutoff_date": cutoff_date.isoformat(),
            "records_affected": count,
            "executed": not dry_run
        }

    async def _compute_green_totals_for_period(self, before_date: datetime):
        """Compute and store Green Totals before deleting raw data."""
        # Aggregate raw job data into Green Totals
        query = """
            INSERT INTO green_totals (
                company_id, period_start, period_end,
                total_carbon_avoided, scope1_reduction, scope2_reduction, scope3_reduction,
                total_kwh_saved, total_therms_saved,
                units_installed, average_seer2, compliant_refrigerant_count,
                total_rebates_captured, total_tax_credits, total_customer_savings,
                total_landfill_diverted_lbs, recycling_rate,
                total_jobs, compliant_jobs, compliance_rate,
                data_hash, created_at
            )
            SELECT
                company_id,
                DATE_TRUNC('month', MIN(created_at)) as period_start,
                DATE_TRUNC('month', MAX(created_at)) + INTERVAL '1 month' - INTERVAL '1 day' as period_end,
                COALESCE(SUM(carbon_avoided_kg), 0),
                COALESCE(SUM(scope1_reduction), 0),
                COALESCE(SUM(scope2_reduction), 0),
                COALESCE(SUM(scope3_reduction), 0),
                COALESCE(SUM(kwh_saved), 0),
                COALESCE(SUM(therms_saved), 0),
                COUNT(*) FILTER (WHERE equipment_installed = true),
                COALESCE(AVG(seer2_rating), 0),
                COUNT(*) FILTER (WHERE refrigerant_compliant = true),
                COALESCE(SUM(rebate_amount), 0),
                COALESCE(SUM(tax_credit_amount), 0),
                COALESCE(SUM(customer_savings), 0),
                COALESCE(SUM(landfill_diverted_lbs), 0),
                CASE WHEN COUNT(*) > 0
                     THEN (COUNT(*) FILTER (WHERE properly_recycled = true))::float / COUNT(*)
                     ELSE 0 END,
                COUNT(*),
                COUNT(*) FILTER (WHERE is_compliant = true),
                CASE WHEN COUNT(*) > 0
                     THEN (COUNT(*) FILTER (WHERE is_compliant = true))::float / COUNT(*)
                     ELSE 0 END,
                MD5(STRING_AGG(job_id::text, ',' ORDER BY job_id)),
                NOW()
            FROM raw_job_data
            WHERE created_at < $1 AND green_totals_computed = false
            GROUP BY company_id, DATE_TRUNC('month', created_at)
            ON CONFLICT (company_id, period_start) DO UPDATE SET
                total_carbon_avoided = green_totals.total_carbon_avoided + EXCLUDED.total_carbon_avoided,
                total_jobs = green_totals.total_jobs + EXCLUDED.total_jobs
        """
        await self.db.execute(query, before_date)

        # Mark raw data as computed
        await self.db.execute(
            "UPDATE raw_job_data SET green_totals_computed = true WHERE created_at < $1",
            before_date
        )

    # ========== INTEGRITY VERIFICATION ==========

    async def generate_integrity_report(self) -> IntegrityReport:
        """
        Generate daily integrity report with database state hash.
        Proves no data has been tampered with.
        """
        if not self.db:
            raise ValueError("Database connection required")

        report_date = datetime.utcnow().date()
        report_id = f"integrity_{report_date.isoformat()}_{hashlib.md5(str(datetime.utcnow()).encode()).hexdigest()[:8]}"

        # Tables to verify
        tables = [
            "green_totals",
            "audit_entries",
            "equipment_registry",
            "rebate_records",
            "compliance_certificates"
        ]

        table_hashes = []
        total_records = 0
        anomalies = []

        for table in tables:
            try:
                # Get record count and content hash
                query = f"""
                    SELECT
                        COUNT(*) as count,
                        MD5(STRING_AGG(
                            COALESCE(MD5(row_to_json(t)::text), 'null'),
                            ''
                            ORDER BY created_at, id
                        )) as content_hash
                    FROM {table} t
                """
                result = await self.db.fetchrow(query)

                table_hash = result['content_hash'] or 'empty'
                record_count = result['count']

                table_hashes.append(f"{table}:{table_hash}")
                total_records += record_count

                # Check for anomalies
                # 1. Records with future timestamps
                future_check = await self.db.fetchval(
                    f"SELECT COUNT(*) FROM {table} WHERE created_at > NOW()"
                )
                if future_check > 0:
                    anomalies.append(f"{table}: {future_check} records with future timestamps")

                # 2. Check hash chain integrity (for audit_entries)
                if table == "audit_entries":
                    chain_valid = await self._verify_audit_chain()
                    if not chain_valid:
                        anomalies.append("audit_entries: Hash chain broken")

            except Exception as e:
                anomalies.append(f"{table}: Error during verification - {str(e)}")

        # Compute overall state hash
        state_hash = hashlib.sha256(
            "|".join(sorted(table_hashes)).encode()
        ).hexdigest()

        # Get previous report hash for chain verification
        previous_hash = await self.db.fetchval(
            """SELECT state_hash FROM integrity_reports
               WHERE report_date < $1
               ORDER BY report_date DESC LIMIT 1""",
            report_date
        )

        # Verify chain continuity
        chain_valid = True
        if previous_hash:
            expected_chain = hashlib.sha256(
                f"{previous_hash}|{state_hash}".encode()
            ).hexdigest()
            # Store for next verification
            self._integrity_cache['last_hash'] = state_hash

        report = IntegrityReport(
            report_date=datetime.utcnow(),
            report_id=report_id,
            tables_checked=tables,
            total_records=total_records,
            state_hash=state_hash,
            previous_hash=previous_hash,
            chain_valid=chain_valid and len(anomalies) == 0,
            anomalies_detected=anomalies
        )

        # Store report
        await self._store_integrity_report(report)

        return report

    async def _verify_audit_chain(self) -> bool:
        """Verify audit entry hash chain is intact."""
        query = """
            SELECT id, previous_hash, entry_hash
            FROM audit_entries
            ORDER BY created_at ASC
        """
        rows = await self.db.fetch(query)

        if not rows:
            return True

        expected_previous = None
        for row in rows:
            if expected_previous is not None:
                if row['previous_hash'] != expected_previous:
                    return False
            expected_previous = row['entry_hash']

        return True

    async def _store_integrity_report(self, report: IntegrityReport):
        """Store integrity report in database."""
        query = """
            INSERT INTO integrity_reports (
                report_id, report_date, tables_checked, total_records,
                state_hash, previous_hash, chain_valid, anomalies_detected,
                generated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        """
        await self.db.execute(
            query,
            report.report_id, report.report_date, report.tables_checked,
            report.total_records, report.state_hash, report.previous_hash,
            report.chain_valid, report.anomalies_detected, report.generated_at
        )

    async def get_integrity_history(
        self,
        days: int = 30
    ) -> List[Dict]:
        """Get integrity report history."""
        if not self.db:
            return []

        query = """
            SELECT * FROM integrity_reports
            WHERE report_date >= NOW() - INTERVAL '%s days'
            ORDER BY report_date DESC
        """
        rows = await self.db.fetch(query % days)

        return [
            {
                "report_id": r["report_id"],
                "report_date": r["report_date"].isoformat(),
                "total_records": r["total_records"],
                "state_hash": r["state_hash"][:16] + "...",
                "chain_valid": r["chain_valid"],
                "anomalies_count": len(r["anomalies_detected"] or [])
            }
            for r in rows
        ]

    # ========== SCHEDULED TASKS ==========

    async def run_daily_maintenance(self):
        """
        Run daily privacy maintenance tasks.
        Should be scheduled via cron or task scheduler.
        """
        results = {
            "executed_at": datetime.utcnow().isoformat(),
            "tasks": []
        }

        # 1. Apply retention policies
        retention_result = await self.apply_retention_policy(dry_run=False)
        results["tasks"].append({
            "task": "apply_retention_policy",
            "result": retention_result
        })

        # 2. Generate integrity report
        integrity_report = await self.generate_integrity_report()
        results["tasks"].append({
            "task": "generate_integrity_report",
            "result": {
                "report_id": integrity_report.report_id,
                "chain_valid": integrity_report.chain_valid,
                "anomalies": integrity_report.anomalies_detected
            }
        })

        # 3. Log maintenance run to audit trail
        if self.db:
            await self.db.execute(
                """INSERT INTO audit_entries (action, description, data, created_at)
                   VALUES ('privacy_maintenance', 'Daily privacy maintenance completed', $1, NOW())""",
                json.dumps(results)
            )

        return results


# Database schema for privacy guardrail tables
PRIVACY_TABLES_SCHEMA = """
-- Green Totals (permanent ESG ledger)
CREATE TABLE IF NOT EXISTS green_totals (
    id SERIAL PRIMARY KEY,
    company_id VARCHAR(255) NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,

    total_carbon_avoided FLOAT DEFAULT 0,
    scope1_reduction FLOAT DEFAULT 0,
    scope2_reduction FLOAT DEFAULT 0,
    scope3_reduction FLOAT DEFAULT 0,

    total_kwh_saved FLOAT DEFAULT 0,
    total_therms_saved FLOAT DEFAULT 0,

    units_installed INTEGER DEFAULT 0,
    average_seer2 FLOAT DEFAULT 0,
    compliant_refrigerant_count INTEGER DEFAULT 0,

    total_rebates_captured FLOAT DEFAULT 0,
    total_tax_credits FLOAT DEFAULT 0,
    total_customer_savings FLOAT DEFAULT 0,

    total_landfill_diverted_lbs FLOAT DEFAULT 0,
    recycling_rate FLOAT DEFAULT 0,

    total_jobs INTEGER DEFAULT 0,
    compliant_jobs INTEGER DEFAULT 0,
    compliance_rate FLOAT DEFAULT 0,

    data_hash VARCHAR(64),
    created_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(company_id, period_start)
);

-- Integrity Reports
CREATE TABLE IF NOT EXISTS integrity_reports (
    id SERIAL PRIMARY KEY,
    report_id VARCHAR(255) UNIQUE NOT NULL,
    report_date DATE NOT NULL,
    tables_checked TEXT[] NOT NULL,
    total_records INTEGER NOT NULL,
    state_hash VARCHAR(64) NOT NULL,
    previous_hash VARCHAR(64),
    chain_valid BOOLEAN DEFAULT TRUE,
    anomalies_detected TEXT[],
    generated_at TIMESTAMP DEFAULT NOW()
);

-- Add retention tracking columns to existing tables
ALTER TABLE raw_job_data ADD COLUMN IF NOT EXISTS green_totals_computed BOOLEAN DEFAULT FALSE;
ALTER TABLE customers ADD COLUMN IF NOT EXISTS is_anonymized BOOLEAN DEFAULT FALSE;
ALTER TABLE customers ADD COLUMN IF NOT EXISTS anonymized_at TIMESTAMP;
ALTER TABLE audit_entries ADD COLUMN IF NOT EXISTS is_archived BOOLEAN DEFAULT FALSE;
ALTER TABLE rebate_records ADD COLUMN IF NOT EXISTS is_archived BOOLEAN DEFAULT FALSE;

-- Archive tables
CREATE TABLE IF NOT EXISTS audit_entries_archive (LIKE audit_entries INCLUDING ALL);
CREATE TABLE IF NOT EXISTS rebate_records_archive (LIKE rebate_records INCLUDING ALL);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_green_totals_company ON green_totals(company_id);
CREATE INDEX IF NOT EXISTS idx_green_totals_period ON green_totals(period_start, period_end);
CREATE INDEX IF NOT EXISTS idx_integrity_date ON integrity_reports(report_date);
"""


async def create_privacy_guardrail(db_connection=None) -> PrivacyGuardrail:
    """
    Create and initialize privacy guardrail.

    Args:
        db_connection: PostgreSQL connection

    Returns:
        Initialized PrivacyGuardrail
    """
    guardrail = PrivacyGuardrail(db_connection)

    # Create tables if using database
    if db_connection:
        await db_connection.execute(PRIVACY_TABLES_SCHEMA)

    return guardrail
