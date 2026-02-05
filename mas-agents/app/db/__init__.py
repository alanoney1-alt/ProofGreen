"""
ProofGreen MAS - Database Package
PostgreSQL integration for audit trails and governance workflows.
"""

from .audit_db import AuditDatabase, create_audit_database

__all__ = ["AuditDatabase", "create_audit_database"]
