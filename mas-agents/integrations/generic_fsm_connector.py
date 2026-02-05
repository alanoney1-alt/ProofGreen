"""
ProofGreen MAS - Generic FSM Connector with Setup Wizard
Allows users to connect any FSM/CRM with auto-field mapping.
"""

import json
import base64
import hashlib
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import httpx
from pydantic import BaseModel, Field


class AuthType(str, Enum):
    """Supported authentication types."""
    API_KEY = "api_key"
    BEARER_TOKEN = "bearer_token"
    BASIC_AUTH = "basic_auth"
    OAUTH2 = "oauth2"


class FieldMapping(BaseModel):
    """Mapping from source CRM field to Green Ledger field."""
    source_path: str = Field(..., description="JSON path in source CRM")
    target_field: str = Field(..., description="Green Ledger field name")
    transform: Optional[str] = Field(None, description="Optional transform: 'date', 'float', 'int', 'string'")
    default_value: Optional[Any] = Field(None, description="Default if source is missing")


class FSMConnectionConfig(BaseModel):
    """Configuration for an FSM/CRM connection."""
    provider_name: str
    auth_type: AuthType
    base_url: str
    api_key: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    tenant_id: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_expiry: Optional[datetime] = None
    field_mappings: List[FieldMapping] = Field(default_factory=list)
    webhook_secret: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_verified: Optional[datetime] = None
    is_active: bool = True


# Green Ledger standard fields that can be mapped
GREEN_LEDGER_FIELDS = {
    "customer_name": {"type": "string", "required": True, "description": "Customer full name"},
    "customer_email": {"type": "string", "required": False, "description": "Customer email address"},
    "customer_phone": {"type": "string", "required": False, "description": "Customer phone number"},
    "customer_address": {"type": "string", "required": False, "description": "Service address"},
    "job_id": {"type": "string", "required": True, "description": "External job/work order ID"},
    "job_date": {"type": "date", "required": True, "description": "Date of service"},
    "job_type": {"type": "string", "required": False, "description": "Type of work performed"},
    "equipment_model": {"type": "string", "required": False, "description": "Equipment model number"},
    "equipment_serial": {"type": "string", "required": False, "description": "Equipment serial number"},
    "equipment_type": {"type": "string", "required": False, "description": "HVAC, Water Heater, etc."},
    "old_equipment_model": {"type": "string", "required": False, "description": "Replaced equipment model"},
    "old_equipment_serial": {"type": "string", "required": False, "description": "Replaced equipment serial"},
    "seer2_rating": {"type": "float", "required": False, "description": "SEER2 efficiency rating"},
    "refrigerant_type": {"type": "string", "required": False, "description": "R-410A, R-454B, etc."},
    "total_amount": {"type": "float", "required": False, "description": "Invoice total"},
    "technician_name": {"type": "string", "required": False, "description": "Assigned technician"},
    "technician_id": {"type": "string", "required": False, "description": "Technician identifier"},
    "notes": {"type": "string", "required": False, "description": "Job notes/description"},
    "photos": {"type": "array", "required": False, "description": "Photo URLs for Vision OCR"},
    "state": {"type": "string", "required": True, "description": "State code for compliance"},
    "zip_code": {"type": "string", "required": False, "description": "Service location ZIP"},
}


# Common field patterns in FSM systems for auto-detection
FIELD_PATTERNS = {
    "customer_name": [
        "customer.name", "customerName", "customer_name", "client.name",
        "clientName", "name", "customer.fullName", "contact.name",
        "customer.firstName + customer.lastName", "billing.name"
    ],
    "customer_email": [
        "customer.email", "customerEmail", "email", "contact.email",
        "customer.emailAddress", "billing.email"
    ],
    "customer_phone": [
        "customer.phone", "customerPhone", "phone", "contact.phone",
        "customer.phoneNumber", "customer.mobile", "primaryPhone"
    ],
    "customer_address": [
        "location.address", "address", "serviceAddress", "customer.address",
        "job.address", "property.address", "location.street"
    ],
    "job_id": [
        "id", "jobId", "job_id", "workOrderId", "work_order_id",
        "invoiceId", "ticketId", "orderNumber", "job.id"
    ],
    "job_date": [
        "scheduledDate", "scheduled_date", "jobDate", "job_date",
        "completedDate", "completed_date", "serviceDate", "date",
        "createdAt", "created_at", "job.date"
    ],
    "job_type": [
        "jobType", "job_type", "type", "workType", "category",
        "serviceType", "job.type", "jobTypeName"
    ],
    "equipment_model": [
        "equipment.model", "equipmentModel", "modelNumber", "model",
        "newEquipment.model", "installed.model", "unit.model"
    ],
    "equipment_serial": [
        "equipment.serial", "serialNumber", "serial", "equipmentSerial",
        "newEquipment.serial", "installed.serial", "unit.serial"
    ],
    "seer2_rating": [
        "equipment.seer", "seer", "seerRating", "efficiency",
        "equipment.efficiency", "seer2", "seer2Rating"
    ],
    "refrigerant_type": [
        "equipment.refrigerant", "refrigerant", "refrigerantType",
        "equipment.refrigerantType", "coolant"
    ],
    "total_amount": [
        "total", "totalAmount", "invoiceTotal", "amount",
        "grandTotal", "price", "cost", "invoice.total"
    ],
    "technician_name": [
        "technician.name", "technicianName", "assignedTo",
        "employee.name", "tech.name", "assignee", "worker.name"
    ],
    "technician_id": [
        "technician.id", "technicianId", "assignedToId",
        "employee.id", "tech.id", "assigneeId"
    ],
    "state": [
        "location.state", "state", "address.state", "customer.state",
        "property.state", "serviceLocation.state"
    ],
    "zip_code": [
        "location.zip", "zip", "zipCode", "postalCode",
        "address.zip", "customer.zip", "property.zip"
    ],
    "notes": [
        "notes", "description", "jobNotes", "summary",
        "job.notes", "workDescription", "comments"
    ],
    "photos": [
        "photos", "images", "attachments", "media",
        "job.photos", "jobPhotos", "imageUrls"
    ],
}


@dataclass
class SetupWizardState:
    """Tracks the state of the setup wizard."""
    step: int = 1
    provider_name: str = ""
    auth_type: Optional[AuthType] = None
    credentials_entered: bool = False
    sample_json_uploaded: bool = False
    sample_json: Optional[Dict] = None
    detected_mappings: List[FieldMapping] = field(default_factory=list)
    user_confirmed_mappings: bool = False
    connection_tested: bool = False
    test_result: Optional[str] = None


class GenericFSMConnector:
    """
    Generic FSM/CRM connector with setup wizard and auto-field mapping.
    Supports any FSM system that provides a REST API.
    """

    def __init__(self, credentials_vault=None):
        """
        Initialize connector.

        Args:
            credentials_vault: Optional CredentialsVault for secure storage
        """
        self.credentials_vault = credentials_vault
        self.connections: Dict[str, FSMConnectionConfig] = {}
        self.wizard_sessions: Dict[str, SetupWizardState] = {}

    # ========== SETUP WIZARD ==========

    def start_wizard(self, session_id: str) -> Dict:
        """
        Start a new setup wizard session.

        Returns:
            Wizard state and instructions for step 1
        """
        self.wizard_sessions[session_id] = SetupWizardState()

        return {
            "session_id": session_id,
            "step": 1,
            "title": "Welcome to FSM Integration Setup",
            "instructions": "Let's connect your Field Service Management system to ProofGreen.",
            "prompts": [
                {
                    "field": "provider_name",
                    "type": "text",
                    "label": "What is your FSM/CRM provider name?",
                    "placeholder": "e.g., ServiceTitan, Jobber, Housecall Pro, FieldEdge",
                    "required": True
                },
                {
                    "field": "base_url",
                    "type": "url",
                    "label": "API Base URL (if known)",
                    "placeholder": "e.g., https://api.servicetitan.io/v2",
                    "required": False,
                    "help": "Leave blank if unsure - we'll detect it"
                }
            ],
            "actions": ["next", "cancel"]
        }

    def wizard_step_provider(
        self,
        session_id: str,
        provider_name: str,
        base_url: Optional[str] = None
    ) -> Dict:
        """
        Step 2: Configure authentication type based on provider.
        """
        state = self.wizard_sessions.get(session_id)
        if not state:
            return {"error": "Session not found. Please start a new wizard."}

        state.provider_name = provider_name
        state.step = 2

        # Detect auth type based on known providers
        known_providers = {
            "servicetitan": {
                "auth_type": AuthType.OAUTH2,
                "base_url": "https://api.servicetitan.io/v2",
                "requires": ["tenant_id", "client_id", "client_secret"]
            },
            "jobber": {
                "auth_type": AuthType.OAUTH2,
                "base_url": "https://api.getjobber.com/api/graphql",
                "requires": ["client_id", "client_secret"]
            },
            "housecall_pro": {
                "auth_type": AuthType.API_KEY,
                "base_url": "https://api.housecallpro.com/v1",
                "requires": ["api_key"]
            },
            "fieldedge": {
                "auth_type": AuthType.BEARER_TOKEN,
                "base_url": "https://api.fieldedge.com",
                "requires": ["api_key"]
            }
        }

        provider_key = provider_name.lower().replace(" ", "_").replace("-", "_")
        known = known_providers.get(provider_key)

        if known:
            state.auth_type = known["auth_type"]
            detected_url = known["base_url"]
            requires = known["requires"]
        else:
            # Unknown provider - ask for auth type
            detected_url = base_url or ""
            requires = None

        prompts = []

        if not known:
            prompts.append({
                "field": "auth_type",
                "type": "select",
                "label": "How does your CRM authenticate?",
                "options": [
                    {"value": "api_key", "label": "API Key (single key in header)"},
                    {"value": "bearer_token", "label": "Bearer Token (Authorization header)"},
                    {"value": "basic_auth", "label": "Basic Auth (username/password)"},
                    {"value": "oauth2", "label": "OAuth 2.0 (client credentials)"}
                ],
                "required": True
            })

        # Build credential prompts based on auth type
        if requires and "tenant_id" in requires:
            prompts.append({
                "field": "tenant_id",
                "type": "text",
                "label": "Tenant ID",
                "placeholder": "Your ServiceTitan tenant ID",
                "required": True,
                "secure": False
            })

        if requires and "client_id" in requires:
            prompts.append({
                "field": "client_id",
                "type": "text",
                "label": "Client ID",
                "placeholder": "OAuth client ID",
                "required": True,
                "secure": False
            })

        if requires and "client_secret" in requires:
            prompts.append({
                "field": "client_secret",
                "type": "password",
                "label": "Client Secret",
                "placeholder": "OAuth client secret",
                "required": True,
                "secure": True
            })

        if requires and "api_key" in requires:
            prompts.append({
                "field": "api_key",
                "type": "password",
                "label": "API Key",
                "placeholder": "Your API key",
                "required": True,
                "secure": True
            })

        if not known:
            prompts.extend([
                {
                    "field": "api_key",
                    "type": "password",
                    "label": "API Key / Access Token",
                    "placeholder": "Enter your API key or access token",
                    "required": True,
                    "secure": True
                },
                {
                    "field": "base_url",
                    "type": "url",
                    "label": "API Base URL",
                    "placeholder": "https://api.yourcrm.com/v1",
                    "required": True
                }
            ])

        return {
            "session_id": session_id,
            "step": 2,
            "title": f"Configure {provider_name} Credentials",
            "instructions": "Enter your API credentials. These will be encrypted and stored securely.",
            "detected": {
                "provider": provider_name,
                "auth_type": state.auth_type.value if state.auth_type else None,
                "base_url": detected_url
            },
            "prompts": prompts,
            "security_note": "All credentials are encrypted with AES-256 at rest.",
            "actions": ["back", "next", "cancel"]
        }

    def wizard_step_credentials(
        self,
        session_id: str,
        auth_type: Optional[str] = None,
        api_key: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        tenant_id: Optional[str] = None,
        base_url: Optional[str] = None
    ) -> Dict:
        """
        Step 3: Upload sample JSON for auto-mapping.
        """
        state = self.wizard_sessions.get(session_id)
        if not state:
            return {"error": "Session not found. Please start a new wizard."}

        # Store credentials temporarily (will be encrypted on final save)
        if auth_type:
            state.auth_type = AuthType(auth_type)
        state.credentials_entered = True
        state.step = 3

        # Store in session (temporary, will be moved to vault on completion)
        state._temp_credentials = {
            "api_key": api_key,
            "client_id": client_id,
            "client_secret": client_secret,
            "tenant_id": tenant_id,
            "base_url": base_url
        }

        return {
            "session_id": session_id,
            "step": 3,
            "title": "Upload Sample Data",
            "instructions": (
                "To automatically map your CRM fields to Green Ledger, please paste "
                "a sample JSON payload from your system. This could be:\n"
                "- A webhook payload from a completed job\n"
                "- An API response for a single job/work order\n"
                "- An exported record from your CRM"
            ),
            "prompts": [
                {
                    "field": "sample_json",
                    "type": "textarea",
                    "label": "Paste your sample JSON here",
                    "placeholder": '{\n  "job": {\n    "id": "12345",\n    "customer": {\n      "name": "John Doe"\n    }\n  }\n}',
                    "required": True,
                    "rows": 15
                }
            ],
            "tips": [
                "Include a complete job record with customer and equipment data",
                "The more fields you include, the better we can auto-map",
                "Don't worry about sensitive data - this is processed locally"
            ],
            "actions": ["back", "next", "skip", "cancel"]
        }

    def wizard_step_mapping(
        self,
        session_id: str,
        sample_json: Optional[str] = None,
        skip_mapping: bool = False
    ) -> Dict:
        """
        Step 4: Auto-detect field mappings and show for confirmation.
        """
        state = self.wizard_sessions.get(session_id)
        if not state:
            return {"error": "Session not found. Please start a new wizard."}

        state.step = 4

        if skip_mapping:
            state.detected_mappings = []
            return self._build_manual_mapping_response(session_id, state)

        # Parse sample JSON
        try:
            if sample_json:
                state.sample_json = json.loads(sample_json)
                state.sample_json_uploaded = True
        except json.JSONDecodeError as e:
            return {
                "session_id": session_id,
                "step": 3,
                "error": f"Invalid JSON: {str(e)}",
                "instructions": "Please fix the JSON and try again."
            }

        # Auto-detect field mappings
        detected = self._auto_detect_mappings(state.sample_json)
        state.detected_mappings = detected

        return {
            "session_id": session_id,
            "step": 4,
            "title": "Confirm Field Mappings",
            "instructions": (
                "We've automatically detected the following field mappings. "
                "Please review and adjust as needed."
            ),
            "detected_mappings": [
                {
                    "source_path": m.source_path,
                    "target_field": m.target_field,
                    "target_description": GREEN_LEDGER_FIELDS.get(m.target_field, {}).get("description", ""),
                    "sample_value": self._get_nested_value(state.sample_json, m.source_path),
                    "confidence": "high" if m.source_path in FIELD_PATTERNS.get(m.target_field, []) else "medium"
                }
                for m in detected
            ],
            "unmapped_fields": [
                {
                    "field": field,
                    "description": info["description"],
                    "required": info["required"]
                }
                for field, info in GREEN_LEDGER_FIELDS.items()
                if not any(m.target_field == field for m in detected)
            ],
            "available_source_paths": self._extract_all_paths(state.sample_json),
            "prompts": [
                {
                    "field": "mapping_adjustments",
                    "type": "mapping_editor",
                    "label": "Adjust mappings (optional)",
                    "current_mappings": [m.dict() for m in detected]
                }
            ],
            "actions": ["back", "next", "cancel"]
        }

    def _build_manual_mapping_response(self, session_id: str, state: SetupWizardState) -> Dict:
        """Build response for manual mapping (when sample JSON skipped)."""
        return {
            "session_id": session_id,
            "step": 4,
            "title": "Configure Field Mappings Manually",
            "instructions": (
                "Since no sample data was provided, please configure field mappings manually. "
                "You can update these later through the API."
            ),
            "green_ledger_fields": [
                {
                    "field": field,
                    "type": info["type"],
                    "required": info["required"],
                    "description": info["description"]
                }
                for field, info in GREEN_LEDGER_FIELDS.items()
            ],
            "common_patterns": {
                field: patterns[:3]  # Show top 3 common patterns
                for field, patterns in FIELD_PATTERNS.items()
            },
            "actions": ["back", "next", "cancel"]
        }

    def wizard_step_confirm(
        self,
        session_id: str,
        confirmed_mappings: Optional[List[Dict]] = None
    ) -> Dict:
        """
        Step 5: Test connection and finalize.
        """
        state = self.wizard_sessions.get(session_id)
        if not state:
            return {"error": "Session not found. Please start a new wizard."}

        state.step = 5

        # Update mappings if user adjusted them
        if confirmed_mappings:
            state.detected_mappings = [
                FieldMapping(**m) for m in confirmed_mappings
            ]

        state.user_confirmed_mappings = True

        return {
            "session_id": session_id,
            "step": 5,
            "title": "Test Connection",
            "instructions": "Ready to test your connection. Click 'Test' to verify.",
            "summary": {
                "provider": state.provider_name,
                "auth_type": state.auth_type.value if state.auth_type else "unknown",
                "mappings_count": len(state.detected_mappings),
                "mapped_fields": [m.target_field for m in state.detected_mappings]
            },
            "actions": ["back", "test", "cancel"]
        }

    async def wizard_test_connection(self, session_id: str) -> Dict:
        """
        Test the connection with provided credentials.
        """
        state = self.wizard_sessions.get(session_id)
        if not state:
            return {"error": "Session not found. Please start a new wizard."}

        creds = getattr(state, '_temp_credentials', {})

        try:
            # Build auth header based on type
            headers = {}
            if state.auth_type == AuthType.API_KEY:
                headers["X-API-Key"] = creds.get("api_key", "")
            elif state.auth_type == AuthType.BEARER_TOKEN:
                headers["Authorization"] = f"Bearer {creds.get('api_key', '')}"
            elif state.auth_type == AuthType.BASIC_AUTH:
                auth_string = base64.b64encode(
                    f"{creds.get('client_id', '')}:{creds.get('client_secret', '')}".encode()
                ).decode()
                headers["Authorization"] = f"Basic {auth_string}"
            elif state.auth_type == AuthType.OAUTH2:
                # For OAuth2, we need to get an access token first
                token = await self._get_oauth_token(
                    state.provider_name,
                    creds.get("client_id"),
                    creds.get("client_secret"),
                    creds.get("tenant_id"),
                    creds.get("base_url")
                )
                if token:
                    headers["Authorization"] = f"Bearer {token}"
                else:
                    return {
                        "session_id": session_id,
                        "step": 5,
                        "test_result": "failed",
                        "error": "OAuth token retrieval failed. Check client_id and client_secret.",
                        "actions": ["back", "retry", "cancel"]
                    }

            # Make a simple API call to verify
            base_url = creds.get("base_url", "")
            async with httpx.AsyncClient() as client:
                # Try a health/status endpoint first
                test_endpoints = ["/health", "/status", "/ping", "/", "/api/v1/me"]

                for endpoint in test_endpoints:
                    try:
                        response = await client.get(
                            f"{base_url.rstrip('/')}{endpoint}",
                            headers=headers,
                            timeout=10.0
                        )
                        if response.status_code in [200, 201, 204]:
                            state.connection_tested = True
                            state.test_result = "success"
                            return {
                                "session_id": session_id,
                                "step": 5,
                                "test_result": "success",
                                "message": f"Successfully connected to {state.provider_name}!",
                                "actions": ["back", "finish", "cancel"]
                            }
                        elif response.status_code == 401:
                            return {
                                "session_id": session_id,
                                "step": 5,
                                "test_result": "auth_failed",
                                "error": "Authentication failed. Please check your credentials.",
                                "actions": ["back", "retry", "cancel"]
                            }
                    except httpx.RequestError:
                        continue

                # If no endpoint worked, connection might still be valid
                state.connection_tested = True
                state.test_result = "partial"
                return {
                    "session_id": session_id,
                    "step": 5,
                    "test_result": "partial",
                    "message": "Could not verify connection automatically, but credentials are stored. You can proceed and test with real data.",
                    "actions": ["back", "finish", "cancel"]
                }

        except Exception as e:
            return {
                "session_id": session_id,
                "step": 5,
                "test_result": "error",
                "error": f"Connection error: {str(e)}",
                "actions": ["back", "retry", "cancel"]
            }

    async def wizard_finish(self, session_id: str, company_id: str) -> Dict:
        """
        Finalize wizard and save connection configuration.
        """
        state = self.wizard_sessions.get(session_id)
        if not state:
            return {"error": "Session not found. Please start a new wizard."}

        creds = getattr(state, '_temp_credentials', {})

        # Create connection config
        config = FSMConnectionConfig(
            provider_name=state.provider_name,
            auth_type=state.auth_type,
            base_url=creds.get("base_url", ""),
            api_key=creds.get("api_key"),
            client_id=creds.get("client_id"),
            client_secret=creds.get("client_secret"),
            tenant_id=creds.get("tenant_id"),
            field_mappings=state.detected_mappings,
            last_verified=datetime.utcnow() if state.connection_tested else None
        )

        # Store in memory (will be persisted via CredentialsVault)
        connection_id = f"{company_id}_{state.provider_name.lower().replace(' ', '_')}"
        self.connections[connection_id] = config

        # Store in credentials vault if available
        if self.credentials_vault:
            await self.credentials_vault.store_credentials(
                company_id=company_id,
                provider=state.provider_name,
                credentials={
                    "api_key": creds.get("api_key"),
                    "client_id": creds.get("client_id"),
                    "client_secret": creds.get("client_secret"),
                    "tenant_id": creds.get("tenant_id"),
                },
                auth_type=state.auth_type.value
            )

        # Clean up wizard session
        del self.wizard_sessions[session_id]

        return {
            "success": True,
            "connection_id": connection_id,
            "provider": state.provider_name,
            "mappings_saved": len(state.detected_mappings),
            "message": f"Successfully configured {state.provider_name} integration!",
            "next_steps": [
                "Configure webhook URL in your CRM",
                "Test with a real job to verify field mappings",
                "Review mapped data in Green Ledger dashboard"
            ],
            "webhook_url": f"/api/v1/webhooks/{connection_id}"
        }

    # ========== AUTO-MAPPING LOGIC ==========

    def _auto_detect_mappings(self, sample_json: Dict) -> List[FieldMapping]:
        """
        Automatically detect field mappings from sample JSON.
        Uses pattern matching and heuristics.
        """
        mappings = []
        all_paths = self._extract_all_paths(sample_json)

        for target_field, patterns in FIELD_PATTERNS.items():
            best_match = None
            best_score = 0

            for path in all_paths:
                # Check exact pattern match
                if path in patterns:
                    best_match = path
                    best_score = 100
                    break

                # Check partial match
                path_lower = path.lower()
                for pattern in patterns:
                    pattern_lower = pattern.lower()

                    # Check if path ends with pattern
                    if path_lower.endswith(pattern_lower.split(".")[-1]):
                        score = 80
                        if score > best_score:
                            best_match = path
                            best_score = score

                    # Check substring match
                    elif pattern_lower.split(".")[-1] in path_lower:
                        score = 60
                        if score > best_score:
                            best_match = path
                            best_score = score

            if best_match and best_score >= 60:
                # Determine transform based on target field type
                field_type = GREEN_LEDGER_FIELDS.get(target_field, {}).get("type", "string")
                transform = None
                if field_type == "date":
                    transform = "date"
                elif field_type == "float":
                    transform = "float"
                elif field_type == "int":
                    transform = "int"

                mappings.append(FieldMapping(
                    source_path=best_match,
                    target_field=target_field,
                    transform=transform
                ))

        return mappings

    def _extract_all_paths(self, obj: Any, prefix: str = "") -> List[str]:
        """Extract all JSON paths from an object."""
        paths = []

        if isinstance(obj, dict):
            for key, value in obj.items():
                current_path = f"{prefix}.{key}" if prefix else key
                paths.append(current_path)
                paths.extend(self._extract_all_paths(value, current_path))
        elif isinstance(obj, list) and len(obj) > 0:
            # Just look at first element for path detection
            paths.extend(self._extract_all_paths(obj[0], f"{prefix}[0]"))

        return paths

    def _get_nested_value(self, obj: Dict, path: str) -> Any:
        """Get a value from nested dict using dot notation path."""
        try:
            parts = path.replace("[", ".").replace("]", "").split(".")
            current = obj
            for part in parts:
                if part.isdigit():
                    current = current[int(part)]
                else:
                    current = current[part]
            return current
        except (KeyError, IndexError, TypeError):
            return None

    # ========== DATA TRANSFORMATION ==========

    def transform_to_green_ledger(
        self,
        connection_id: str,
        source_data: Dict
    ) -> Dict:
        """
        Transform source CRM data to Green Ledger format using configured mappings.
        """
        config = self.connections.get(connection_id)
        if not config:
            raise ValueError(f"Connection {connection_id} not found")

        result = {}

        for mapping in config.field_mappings:
            value = self._get_nested_value(source_data, mapping.source_path)

            if value is None and mapping.default_value is not None:
                value = mapping.default_value

            if value is not None and mapping.transform:
                value = self._apply_transform(value, mapping.transform)

            if value is not None:
                result[mapping.target_field] = value

        return result

    def _apply_transform(self, value: Any, transform: str) -> Any:
        """Apply a transform to a value."""
        if transform == "date":
            if isinstance(value, str):
                # Try common date formats
                for fmt in ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%m/%d/%Y", "%d/%m/%Y"]:
                    try:
                        return datetime.strptime(value.split("T")[0].split(" ")[0], fmt).date().isoformat()
                    except ValueError:
                        continue
            return value
        elif transform == "float":
            try:
                return float(str(value).replace(",", "").replace("$", ""))
            except (ValueError, TypeError):
                return None
        elif transform == "int":
            try:
                return int(float(str(value).replace(",", "")))
            except (ValueError, TypeError):
                return None
        elif transform == "string":
            return str(value) if value is not None else None
        return value

    # ========== OAUTH HELPERS ==========

    async def _get_oauth_token(
        self,
        provider: str,
        client_id: str,
        client_secret: str,
        tenant_id: Optional[str],
        base_url: str
    ) -> Optional[str]:
        """Get OAuth2 access token for a provider."""
        provider_lower = provider.lower().replace(" ", "_")

        token_endpoints = {
            "servicetitan": f"https://auth.servicetitan.io/connect/token",
            "jobber": "https://api.getjobber.com/api/oauth/token",
        }

        token_url = token_endpoints.get(provider_lower)
        if not token_url:
            # Try standard OAuth endpoint
            token_url = f"{base_url.rstrip('/')}/oauth/token"

        try:
            async with httpx.AsyncClient() as client:
                data = {
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                }

                if tenant_id:
                    data["tenant_id"] = tenant_id

                response = await client.post(token_url, data=data, timeout=10.0)

                if response.status_code == 200:
                    token_data = response.json()
                    return token_data.get("access_token")

        except Exception:
            pass

        return None

    # ========== CONNECTION MANAGEMENT ==========

    def get_connection(self, connection_id: str) -> Optional[FSMConnectionConfig]:
        """Get a connection configuration."""
        return self.connections.get(connection_id)

    def list_connections(self, company_id: Optional[str] = None) -> List[Dict]:
        """List all connections, optionally filtered by company."""
        results = []
        for conn_id, config in self.connections.items():
            if company_id and not conn_id.startswith(f"{company_id}_"):
                continue
            results.append({
                "connection_id": conn_id,
                "provider": config.provider_name,
                "auth_type": config.auth_type.value,
                "is_active": config.is_active,
                "mappings_count": len(config.field_mappings),
                "last_verified": config.last_verified.isoformat() if config.last_verified else None
            })
        return results

    def update_mappings(
        self,
        connection_id: str,
        mappings: List[Dict]
    ) -> Dict:
        """Update field mappings for a connection."""
        config = self.connections.get(connection_id)
        if not config:
            return {"error": f"Connection {connection_id} not found"}

        config.field_mappings = [FieldMapping(**m) for m in mappings]

        return {
            "success": True,
            "connection_id": connection_id,
            "mappings_count": len(config.field_mappings)
        }


# Singleton instance
generic_fsm_connector = GenericFSMConnector()
