"""
MCP FSM Connector for ServiceTitan/Jobber/Housecall Pro
Model Context Protocol server for Field Service Management integrations
"""

import asyncio
import json
import httpx
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class FSMProvider(str, Enum):
    """Supported FSM platforms."""
    SERVICETITAN = "servicetitan"
    JOBBER = "jobber"
    HOUSECALL_PRO = "housecall_pro"


class JobStatus(str, Enum):
    """Standard job statuses across FSM platforms."""
    SCHEDULED = "scheduled"
    DISPATCHED = "dispatched"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CLOSED = "closed"
    CANCELLED = "cancelled"


@dataclass
class NormalizedJob:
    """Normalized job data across FSM platforms."""
    id: str
    external_id: str
    provider: FSMProvider
    status: JobStatus
    customer_id: str
    customer_name: str
    customer_address: str
    zip_code: str
    state: str
    vertical: str  # hvac, plumbing, electrical, landscaping
    job_type: str
    description: str
    technician_id: Optional[str] = None
    technician_name: Optional[str] = None
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    equipment_installed: List[Dict[str, Any]] = field(default_factory=list)
    materials_used: List[Dict[str, Any]] = field(default_factory=list)
    invoice_total: Optional[float] = None
    notes: str = ""
    custom_fields: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MCPToolCall:
    """MCP Tool call structure."""
    name: str
    arguments: Dict[str, Any]
    call_id: str


@dataclass
class MCPToolResult:
    """MCP Tool result structure."""
    call_id: str
    result: Any
    error: Optional[str] = None


class FSMConnector:
    """
    Model Context Protocol (MCP) server for FSM integrations.
    Provides unified interface for ServiceTitan, Jobber, and Housecall Pro.
    """

    def __init__(
        self,
        servicetitan_api_key: Optional[str] = None,
        servicetitan_tenant_id: Optional[str] = None,
        jobber_api_key: Optional[str] = None,
        housecall_pro_api_key: Optional[str] = None
    ):
        self.credentials = {
            FSMProvider.SERVICETITAN: {
                "api_key": servicetitan_api_key,
                "tenant_id": servicetitan_tenant_id,
                "base_url": "https://api.servicetitan.io/v2"
            },
            FSMProvider.JOBBER: {
                "api_key": jobber_api_key,
                "base_url": "https://api.getjobber.com/api"
            },
            FSMProvider.HOUSECALL_PRO: {
                "api_key": housecall_pro_api_key,
                "base_url": "https://api.housecallpro.com/v1"
            }
        }
        self._client = httpx.AsyncClient(timeout=30.0)

    # MCP Tool Definitions
    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Return MCP tool definitions for FSM operations."""
        return [
            {
                "name": "fsm_get_job",
                "description": "Retrieve job details from FSM platform",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "provider": {
                            "type": "string",
                            "enum": ["servicetitan", "jobber", "housecall_pro"],
                            "description": "FSM platform provider"
                        },
                        "job_id": {
                            "type": "string",
                            "description": "External job ID in the FSM system"
                        }
                    },
                    "required": ["provider", "job_id"]
                }
            },
            {
                "name": "fsm_list_closed_jobs",
                "description": "List recently closed jobs from FSM platform",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "provider": {
                            "type": "string",
                            "enum": ["servicetitan", "jobber", "housecall_pro"]
                        },
                        "since_hours": {
                            "type": "integer",
                            "description": "Fetch jobs closed within this many hours",
                            "default": 24
                        },
                        "vertical": {
                            "type": "string",
                            "enum": ["hvac", "plumbing", "electrical", "landscaping"],
                            "description": "Filter by service vertical"
                        }
                    },
                    "required": ["provider"]
                }
            },
            {
                "name": "fsm_get_equipment",
                "description": "Get equipment details installed on a job",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "provider": {"type": "string"},
                        "job_id": {"type": "string"}
                    },
                    "required": ["provider", "job_id"]
                }
            },
            {
                "name": "fsm_update_custom_field",
                "description": "Update a custom field on a job (e.g., Green Verified status)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "provider": {"type": "string"},
                        "job_id": {"type": "string"},
                        "field_name": {"type": "string"},
                        "field_value": {"type": "string"}
                    },
                    "required": ["provider", "job_id", "field_name", "field_value"]
                }
            },
            {
                "name": "fsm_attach_certificate",
                "description": "Attach a Green Verification certificate to a job",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "provider": {"type": "string"},
                        "job_id": {"type": "string"},
                        "certificate_url": {"type": "string"},
                        "certificate_type": {
                            "type": "string",
                            "enum": ["green_verified", "esg_audit", "rebate_summary"]
                        }
                    },
                    "required": ["provider", "job_id", "certificate_url", "certificate_type"]
                }
            },
            {
                "name": "fsm_create_follow_up",
                "description": "Create a follow-up task for compliance gaps",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "provider": {"type": "string"},
                        "job_id": {"type": "string"},
                        "task_type": {"type": "string"},
                        "description": {"type": "string"},
                        "due_days": {"type": "integer", "default": 7}
                    },
                    "required": ["provider", "job_id", "task_type", "description"]
                }
            }
        ]

    async def handle_tool_call(self, tool_call: MCPToolCall) -> MCPToolResult:
        """Handle an MCP tool call."""
        try:
            handler = {
                "fsm_get_job": self._handle_get_job,
                "fsm_list_closed_jobs": self._handle_list_closed_jobs,
                "fsm_get_equipment": self._handle_get_equipment,
                "fsm_update_custom_field": self._handle_update_custom_field,
                "fsm_attach_certificate": self._handle_attach_certificate,
                "fsm_create_follow_up": self._handle_create_follow_up
            }.get(tool_call.name)

            if not handler:
                return MCPToolResult(
                    call_id=tool_call.call_id,
                    result=None,
                    error=f"Unknown tool: {tool_call.name}"
                )

            result = await handler(tool_call.arguments)
            return MCPToolResult(call_id=tool_call.call_id, result=result)

        except Exception as e:
            logger.error(f"Tool call failed: {e}")
            return MCPToolResult(
                call_id=tool_call.call_id,
                result=None,
                error=str(e)
            )

    # Tool Handlers
    async def _handle_get_job(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get job details from FSM."""
        provider = FSMProvider(args["provider"])
        job_id = args["job_id"]

        job = await self.get_job(provider, job_id)
        return self._normalize_job_to_dict(job)

    async def _handle_list_closed_jobs(self, args: Dict[str, Any]) -> List[Dict[str, Any]]:
        """List closed jobs from FSM."""
        provider = FSMProvider(args["provider"])
        since_hours = args.get("since_hours", 24)
        vertical = args.get("vertical")

        jobs = await self.list_closed_jobs(provider, since_hours, vertical)
        return [self._normalize_job_to_dict(j) for j in jobs]

    async def _handle_get_equipment(self, args: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get equipment installed on job."""
        provider = FSMProvider(args["provider"])
        job_id = args["job_id"]

        return await self.get_job_equipment(provider, job_id)

    async def _handle_update_custom_field(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Update custom field on job."""
        provider = FSMProvider(args["provider"])
        job_id = args["job_id"]
        field_name = args["field_name"]
        field_value = args["field_value"]

        success = await self.update_custom_field(provider, job_id, field_name, field_value)
        return {"success": success, "job_id": job_id, "field": field_name}

    async def _handle_attach_certificate(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Attach certificate to job."""
        provider = FSMProvider(args["provider"])
        job_id = args["job_id"]
        certificate_url = args["certificate_url"]
        certificate_type = args["certificate_type"]

        success = await self.attach_document(
            provider, job_id, certificate_url, certificate_type
        )
        return {"success": success, "job_id": job_id, "certificate_type": certificate_type}

    async def _handle_create_follow_up(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Create follow-up task."""
        provider = FSMProvider(args["provider"])
        job_id = args["job_id"]
        task_type = args["task_type"]
        description = args["description"]
        due_days = args.get("due_days", 7)

        task_id = await self.create_follow_up_task(
            provider, job_id, task_type, description, due_days
        )
        return {"success": bool(task_id), "task_id": task_id, "job_id": job_id}

    # ServiceTitan API Methods
    async def _servicetitan_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make a ServiceTitan API request."""
        creds = self.credentials[FSMProvider.SERVICETITAN]
        headers = {
            "Authorization": f"Bearer {creds['api_key']}",
            "ST-App-Key": creds.get("tenant_id", ""),
            "Content-Type": "application/json"
        }

        url = f"{creds['base_url']}/{endpoint}"

        response = await self._client.request(
            method=method,
            url=url,
            headers=headers,
            json=data
        )
        response.raise_for_status()
        return response.json()

    async def _servicetitan_get_job(self, job_id: str) -> NormalizedJob:
        """Get job from ServiceTitan."""
        data = await self._servicetitan_request("GET", f"jpm/v2/jobs/{job_id}")

        job_data = data.get("data", data)
        location = job_data.get("location", {})
        address = location.get("address", {})

        return NormalizedJob(
            id=f"st_{job_id}",
            external_id=job_id,
            provider=FSMProvider.SERVICETITAN,
            status=self._map_servicetitan_status(job_data.get("status")),
            customer_id=str(job_data.get("customerId", "")),
            customer_name=job_data.get("customerName", ""),
            customer_address=f"{address.get('street', '')} {address.get('city', '')}, {address.get('state', '')} {address.get('zip', '')}",
            zip_code=address.get("zip", "")[:5],
            state=address.get("state", ""),
            vertical=self._detect_vertical(job_data.get("businessUnitName", ""), job_data.get("type", "")),
            job_type=job_data.get("type", ""),
            description=job_data.get("summary", ""),
            technician_id=str(job_data.get("technicianId")) if job_data.get("technicianId") else None,
            technician_name=job_data.get("technicianName"),
            scheduled_start=self._parse_datetime(job_data.get("start")),
            scheduled_end=self._parse_datetime(job_data.get("end")),
            completed_at=self._parse_datetime(job_data.get("completedOn")),
            invoice_total=job_data.get("invoiceTotal"),
            notes=job_data.get("notes", ""),
            custom_fields=job_data.get("customFields", {})
        )

    # Jobber API Methods
    async def _jobber_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make a Jobber API request."""
        creds = self.credentials[FSMProvider.JOBBER]
        headers = {
            "Authorization": f"Bearer {creds['api_key']}",
            "Content-Type": "application/json",
            "X-JOBBER-GRAPHQL-VERSION": "2024-06"
        }

        url = f"{creds['base_url']}/{endpoint}"

        response = await self._client.request(
            method=method,
            url=url,
            headers=headers,
            json=data
        )
        response.raise_for_status()
        return response.json()

    async def _jobber_get_job(self, job_id: str) -> NormalizedJob:
        """Get job from Jobber using GraphQL."""
        query = """
        query GetJob($id: EncodedId!) {
            job(id: $id) {
                id
                title
                status
                client {
                    id
                    name
                    billingAddress {
                        street
                        city
                        province
                        postalCode
                    }
                }
                property {
                    address {
                        street
                        city
                        province
                        postalCode
                    }
                }
                assignedTo {
                    id
                    name { full }
                }
                startAt
                endAt
                closedAt
                total
                instructions
                customFields {
                    label
                    value
                }
            }
        }
        """

        result = await self._jobber_request(
            "POST",
            "graphql",
            {"query": query, "variables": {"id": job_id}}
        )

        job_data = result.get("data", {}).get("job", {})
        client = job_data.get("client", {})
        prop = job_data.get("property", {})
        address = prop.get("address", {}) or client.get("billingAddress", {})
        assigned = job_data.get("assignedTo", [{}])[0] if job_data.get("assignedTo") else {}

        return NormalizedJob(
            id=f"jb_{job_id}",
            external_id=job_id,
            provider=FSMProvider.JOBBER,
            status=self._map_jobber_status(job_data.get("status")),
            customer_id=str(client.get("id", "")),
            customer_name=client.get("name", ""),
            customer_address=f"{address.get('street', '')} {address.get('city', '')}, {address.get('province', '')} {address.get('postalCode', '')}",
            zip_code=address.get("postalCode", "")[:5],
            state=address.get("province", ""),
            vertical=self._detect_vertical(job_data.get("title", ""), ""),
            job_type=job_data.get("title", ""),
            description=job_data.get("instructions", ""),
            technician_id=str(assigned.get("id")) if assigned.get("id") else None,
            technician_name=assigned.get("name", {}).get("full") if assigned.get("name") else None,
            scheduled_start=self._parse_datetime(job_data.get("startAt")),
            scheduled_end=self._parse_datetime(job_data.get("endAt")),
            completed_at=self._parse_datetime(job_data.get("closedAt")),
            invoice_total=job_data.get("total"),
            notes=job_data.get("instructions", ""),
            custom_fields={cf["label"]: cf["value"] for cf in job_data.get("customFields", [])}
        )

    # Housecall Pro API Methods
    async def _housecall_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make a Housecall Pro API request."""
        creds = self.credentials[FSMProvider.HOUSECALL_PRO]
        headers = {
            "Authorization": f"Token {creds['api_key']}",
            "Content-Type": "application/json"
        }

        url = f"{creds['base_url']}/{endpoint}"

        response = await self._client.request(
            method=method,
            url=url,
            headers=headers,
            json=data
        )
        response.raise_for_status()
        return response.json()

    async def _housecall_get_job(self, job_id: str) -> NormalizedJob:
        """Get job from Housecall Pro."""
        data = await self._housecall_request("GET", f"jobs/{job_id}")

        customer = data.get("customer", {})
        address = data.get("address", {})
        tech = data.get("assigned_employees", [{}])[0] if data.get("assigned_employees") else {}

        return NormalizedJob(
            id=f"hcp_{job_id}",
            external_id=job_id,
            provider=FSMProvider.HOUSECALL_PRO,
            status=self._map_housecall_status(data.get("work_status")),
            customer_id=str(customer.get("id", "")),
            customer_name=f"{customer.get('first_name', '')} {customer.get('last_name', '')}",
            customer_address=f"{address.get('street', '')} {address.get('city', '')}, {address.get('state', '')} {address.get('zip', '')}",
            zip_code=address.get("zip", "")[:5],
            state=address.get("state", ""),
            vertical=self._detect_vertical(data.get("job_type", {}).get("name", ""), ""),
            job_type=data.get("job_type", {}).get("name", ""),
            description=data.get("description", ""),
            technician_id=str(tech.get("id")) if tech.get("id") else None,
            technician_name=f"{tech.get('first_name', '')} {tech.get('last_name', '')}".strip() if tech else None,
            scheduled_start=self._parse_datetime(data.get("schedule", {}).get("scheduled_start")),
            scheduled_end=self._parse_datetime(data.get("schedule", {}).get("scheduled_end")),
            completed_at=self._parse_datetime(data.get("completed_at")),
            invoice_total=data.get("invoice", {}).get("total"),
            notes=data.get("notes", ""),
            custom_fields=data.get("custom_fields", {})
        )

    # Unified Interface Methods
    async def get_job(self, provider: FSMProvider, job_id: str) -> NormalizedJob:
        """Get job from any FSM provider."""
        handlers = {
            FSMProvider.SERVICETITAN: self._servicetitan_get_job,
            FSMProvider.JOBBER: self._jobber_get_job,
            FSMProvider.HOUSECALL_PRO: self._housecall_get_job
        }
        return await handlers[provider](job_id)

    async def list_closed_jobs(
        self,
        provider: FSMProvider,
        since_hours: int = 24,
        vertical: Optional[str] = None
    ) -> List[NormalizedJob]:
        """List recently closed jobs from FSM provider."""
        # Implementation varies by provider
        jobs = []

        if provider == FSMProvider.SERVICETITAN:
            data = await self._servicetitan_request(
                "GET",
                f"jpm/v2/jobs?status=Completed&modifiedOnOrAfter={self._get_since_time(since_hours)}"
            )
            for job_data in data.get("data", []):
                job = await self._servicetitan_get_job(str(job_data.get("id")))
                if not vertical or job.vertical == vertical:
                    jobs.append(job)

        elif provider == FSMProvider.JOBBER:
            # Jobber uses GraphQL for listing
            query = """
            query ListClosedJobs($status: JobStatus!) {
                jobs(status: $status, first: 100) {
                    nodes {
                        id
                    }
                }
            }
            """
            result = await self._jobber_request(
                "POST",
                "graphql",
                {"query": query, "variables": {"status": "CLOSED"}}
            )
            for node in result.get("data", {}).get("jobs", {}).get("nodes", []):
                job = await self._jobber_get_job(node["id"])
                if not vertical or job.vertical == vertical:
                    jobs.append(job)

        elif provider == FSMProvider.HOUSECALL_PRO:
            data = await self._housecall_request(
                "GET",
                f"jobs?work_status=completed"
            )
            for job_data in data.get("jobs", []):
                job = await self._housecall_get_job(str(job_data.get("id")))
                if not vertical or job.vertical == vertical:
                    jobs.append(job)

        return jobs

    async def get_job_equipment(
        self,
        provider: FSMProvider,
        job_id: str
    ) -> List[Dict[str, Any]]:
        """Get equipment installed on a job."""
        equipment = []

        if provider == FSMProvider.SERVICETITAN:
            data = await self._servicetitan_request(
                "GET",
                f"equipment/v2/installed-equipment?jobId={job_id}"
            )
            for item in data.get("data", []):
                equipment.append({
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "type": item.get("equipmentType"),
                    "manufacturer": item.get("manufacturer"),
                    "model": item.get("model"),
                    "serial_number": item.get("serialNumber"),
                    "installation_date": item.get("installedOn"),
                    "custom_fields": item.get("customFields", {})
                })

        elif provider == FSMProvider.JOBBER:
            # Jobber stores equipment in line items/products
            query = """
            query GetJobLineItems($id: EncodedId!) {
                job(id: $id) {
                    lineItems {
                        nodes {
                            id
                            name
                            description
                            quantity
                            unitCost
                        }
                    }
                }
            }
            """
            result = await self._jobber_request(
                "POST",
                "graphql",
                {"query": query, "variables": {"id": job_id}}
            )
            for item in result.get("data", {}).get("job", {}).get("lineItems", {}).get("nodes", []):
                equipment.append({
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "description": item.get("description"),
                    "quantity": item.get("quantity"),
                    "unit_cost": item.get("unitCost")
                })

        elif provider == FSMProvider.HOUSECALL_PRO:
            data = await self._housecall_request("GET", f"jobs/{job_id}/line_items")
            for item in data.get("line_items", []):
                equipment.append({
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "description": item.get("description"),
                    "quantity": item.get("quantity"),
                    "price": item.get("price")
                })

        return equipment

    async def update_custom_field(
        self,
        provider: FSMProvider,
        job_id: str,
        field_name: str,
        field_value: str
    ) -> bool:
        """Update a custom field on a job."""
        try:
            if provider == FSMProvider.SERVICETITAN:
                await self._servicetitan_request(
                    "PATCH",
                    f"jpm/v2/jobs/{job_id}",
                    {"customFields": {field_name: field_value}}
                )

            elif provider == FSMProvider.JOBBER:
                mutation = """
                mutation UpdateJobCustomField($id: EncodedId!, $attributes: JobAttributes!) {
                    jobUpdate(id: $id, attributes: $attributes) {
                        job { id }
                        userErrors { message }
                    }
                }
                """
                await self._jobber_request(
                    "POST",
                    "graphql",
                    {
                        "query": mutation,
                        "variables": {
                            "id": job_id,
                            "attributes": {"customFields": [{
                                "label": field_name,
                                "value": field_value
                            }]}
                        }
                    }
                )

            elif provider == FSMProvider.HOUSECALL_PRO:
                await self._housecall_request(
                    "PATCH",
                    f"jobs/{job_id}",
                    {"custom_fields": {field_name: field_value}}
                )

            return True
        except Exception as e:
            logger.error(f"Failed to update custom field: {e}")
            return False

    async def attach_document(
        self,
        provider: FSMProvider,
        job_id: str,
        document_url: str,
        document_type: str
    ) -> bool:
        """Attach a document/certificate to a job."""
        try:
            if provider == FSMProvider.SERVICETITAN:
                await self._servicetitan_request(
                    "POST",
                    f"jpm/v2/jobs/{job_id}/attachments",
                    {
                        "url": document_url,
                        "name": f"ProofGreen {document_type.replace('_', ' ').title()}",
                        "type": "certificate"
                    }
                )

            elif provider == FSMProvider.JOBBER:
                mutation = """
                mutation AttachFile($input: FileAttachInput!) {
                    fileAttach(input: $input) {
                        success
                        userErrors { message }
                    }
                }
                """
                await self._jobber_request(
                    "POST",
                    "graphql",
                    {
                        "query": mutation,
                        "variables": {
                            "input": {
                                "attachableType": "JOB",
                                "attachableId": job_id,
                                "url": document_url,
                                "fileName": f"ProofGreen_{document_type}.pdf"
                            }
                        }
                    }
                )

            elif provider == FSMProvider.HOUSECALL_PRO:
                await self._housecall_request(
                    "POST",
                    f"jobs/{job_id}/attachments",
                    {
                        "url": document_url,
                        "name": f"ProofGreen {document_type.replace('_', ' ').title()}"
                    }
                )

            return True
        except Exception as e:
            logger.error(f"Failed to attach document: {e}")
            return False

    async def create_follow_up_task(
        self,
        provider: FSMProvider,
        job_id: str,
        task_type: str,
        description: str,
        due_days: int = 7
    ) -> Optional[str]:
        """Create a follow-up task for compliance gaps."""
        try:
            if provider == FSMProvider.SERVICETITAN:
                result = await self._servicetitan_request(
                    "POST",
                    "task-management/v2/tasks",
                    {
                        "jobId": int(job_id),
                        "title": f"ProofGreen: {task_type}",
                        "description": description,
                        "dueDate": self._get_future_date(due_days),
                        "priority": "Normal"
                    }
                )
                return str(result.get("data", {}).get("id"))

            elif provider == FSMProvider.JOBBER:
                mutation = """
                mutation CreateTask($input: TaskCreateInput!) {
                    taskCreate(input: $input) {
                        task { id }
                        userErrors { message }
                    }
                }
                """
                result = await self._jobber_request(
                    "POST",
                    "graphql",
                    {
                        "query": mutation,
                        "variables": {
                            "input": {
                                "title": f"ProofGreen: {task_type}",
                                "description": description,
                                "dueAt": self._get_future_date(due_days),
                                "jobId": job_id
                            }
                        }
                    }
                )
                return result.get("data", {}).get("taskCreate", {}).get("task", {}).get("id")

            elif provider == FSMProvider.HOUSECALL_PRO:
                result = await self._housecall_request(
                    "POST",
                    "tasks",
                    {
                        "job_id": job_id,
                        "title": f"ProofGreen: {task_type}",
                        "description": description,
                        "due_date": self._get_future_date(due_days)
                    }
                )
                return str(result.get("id"))

        except Exception as e:
            logger.error(f"Failed to create follow-up task: {e}")
            return None

    # Helper Methods
    def _map_servicetitan_status(self, status: Optional[str]) -> JobStatus:
        """Map ServiceTitan status to normalized status."""
        mapping = {
            "Scheduled": JobStatus.SCHEDULED,
            "Dispatched": JobStatus.DISPATCHED,
            "Working": JobStatus.IN_PROGRESS,
            "Done": JobStatus.COMPLETED,
            "Completed": JobStatus.CLOSED,
            "Canceled": JobStatus.CANCELLED
        }
        return mapping.get(status or "", JobStatus.SCHEDULED)

    def _map_jobber_status(self, status: Optional[str]) -> JobStatus:
        """Map Jobber status to normalized status."""
        mapping = {
            "UPCOMING": JobStatus.SCHEDULED,
            "IN_PROGRESS": JobStatus.IN_PROGRESS,
            "REQUIRES_INVOICING": JobStatus.COMPLETED,
            "CLOSED": JobStatus.CLOSED,
            "CANCELLED": JobStatus.CANCELLED
        }
        return mapping.get(status or "", JobStatus.SCHEDULED)

    def _map_housecall_status(self, status: Optional[str]) -> JobStatus:
        """Map Housecall Pro status to normalized status."""
        mapping = {
            "scheduled": JobStatus.SCHEDULED,
            "dispatched": JobStatus.DISPATCHED,
            "in_progress": JobStatus.IN_PROGRESS,
            "completed": JobStatus.COMPLETED,
            "closed": JobStatus.CLOSED,
            "cancelled": JobStatus.CANCELLED
        }
        return mapping.get(status or "", JobStatus.SCHEDULED)

    def _detect_vertical(self, business_unit: str, job_type: str) -> str:
        """Detect service vertical from job metadata."""
        text = f"{business_unit} {job_type}".lower()

        if any(kw in text for kw in ["hvac", "air condition", "heating", "cooling", "furnace", "heat pump"]):
            return "hvac"
        elif any(kw in text for kw in ["plumb", "water heater", "drain", "pipe", "toilet", "faucet"]):
            return "plumbing"
        elif any(kw in text for kw in ["electric", "wiring", "panel", "ev charger", "solar", "generator"]):
            return "electrical"
        elif any(kw in text for kw in ["landscape", "lawn", "irrigation", "tree", "garden"]):
            return "landscaping"

        return "general"

    def _parse_datetime(self, value: Optional[str]) -> Optional[datetime]:
        """Parse datetime from various formats."""
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None

    def _get_since_time(self, hours: int) -> str:
        """Get ISO timestamp for N hours ago."""
        dt = datetime.now(timezone.utc).replace(microsecond=0)
        return (dt - __import__("datetime").timedelta(hours=hours)).isoformat()

    def _get_future_date(self, days: int) -> str:
        """Get ISO date for N days in future."""
        dt = datetime.now(timezone.utc).date()
        return (dt + __import__("datetime").timedelta(days=days)).isoformat()

    def _normalize_job_to_dict(self, job: NormalizedJob) -> Dict[str, Any]:
        """Convert NormalizedJob to dictionary."""
        return {
            "id": job.id,
            "external_id": job.external_id,
            "provider": job.provider.value,
            "status": job.status.value,
            "customer_id": job.customer_id,
            "customer_name": job.customer_name,
            "customer_address": job.customer_address,
            "zip_code": job.zip_code,
            "state": job.state,
            "vertical": job.vertical,
            "job_type": job.job_type,
            "description": job.description,
            "technician_id": job.technician_id,
            "technician_name": job.technician_name,
            "scheduled_start": job.scheduled_start.isoformat() if job.scheduled_start else None,
            "scheduled_end": job.scheduled_end.isoformat() if job.scheduled_end else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "equipment_installed": job.equipment_installed,
            "materials_used": job.materials_used,
            "invoice_total": job.invoice_total,
            "notes": job.notes,
            "custom_fields": job.custom_fields
        }

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()


# Webhook Handler for FSM Events
class FSMWebhookHandler:
    """Handle incoming webhooks from FSM platforms."""

    def __init__(self, fsm_connector: FSMConnector):
        self.connector = fsm_connector
        self.event_handlers: Dict[str, List[callable]] = {}

    def on_job_closed(self, handler: callable):
        """Register handler for job closed events."""
        if "job_closed" not in self.event_handlers:
            self.event_handlers["job_closed"] = []
        self.event_handlers["job_closed"].append(handler)

    async def process_webhook(
        self,
        provider: FSMProvider,
        event_type: str,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process incoming FSM webhook."""

        # Normalize the event
        normalized_event = self._normalize_webhook_event(provider, event_type, payload)

        # Trigger handlers
        if normalized_event["type"] == "job_closed":
            job_id = normalized_event.get("job_id")
            if job_id:
                job = await self.connector.get_job(provider, job_id)
                for handler in self.event_handlers.get("job_closed", []):
                    try:
                        await handler(job)
                    except Exception as e:
                        logger.error(f"Webhook handler failed: {e}")

        return {"status": "processed", "event": normalized_event}

    def _normalize_webhook_event(
        self,
        provider: FSMProvider,
        event_type: str,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Normalize webhook event across providers."""

        if provider == FSMProvider.SERVICETITAN:
            if event_type == "job.completed":
                return {
                    "type": "job_closed",
                    "job_id": str(payload.get("jobId")),
                    "timestamp": payload.get("timestamp")
                }

        elif provider == FSMProvider.JOBBER:
            if event_type == "JOB_CLOSED":
                return {
                    "type": "job_closed",
                    "job_id": payload.get("jobId"),
                    "timestamp": payload.get("occurredAt")
                }

        elif provider == FSMProvider.HOUSECALL_PRO:
            if event_type == "job.status.completed":
                return {
                    "type": "job_closed",
                    "job_id": str(payload.get("job", {}).get("id")),
                    "timestamp": payload.get("created_at")
                }

        return {"type": "unknown", "raw_event": event_type, "payload": payload}
