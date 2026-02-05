"""
ProofGreen MAS - Integrations Package
FSM/CRM integrations, webhook handling, and connector management.
"""

from .universal_webhook_handler import (
    UniversalWebhookHandler,
    AuditDraft,
    FSMProvider,
    universal_webhook_handler
)
from .fsm_integration_suite import (
    FSMIntegrationSuite,
    FSMJob,
    fsm_integration_suite
)
from .generic_fsm_connector import (
    GenericFSMConnector,
    FieldMapping,
    FSMConnectionConfig,
    AuthType,
    GREEN_LEDGER_FIELDS,
    generic_fsm_connector
)
from .auth_handler import (
    AuthHandler,
    AuthHealthChecker,
    FSMProvider as AuthFSMProvider,
    create_auth_handler
)

__all__ = [
    # Webhook Handler
    "UniversalWebhookHandler",
    "AuditDraft",
    "FSMProvider",
    "universal_webhook_handler",

    # Integration Suite
    "FSMIntegrationSuite",
    "FSMJob",
    "fsm_integration_suite",

    # Generic Connector
    "GenericFSMConnector",
    "FieldMapping",
    "FSMConnectionConfig",
    "AuthType",
    "GREEN_LEDGER_FIELDS",
    "generic_fsm_connector",

    # Auth Handler
    "AuthHandler",
    "AuthHealthChecker",
    "AuthFSMProvider",
    "create_auth_handler",
]
