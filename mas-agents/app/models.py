"""
Pydantic Models for ProofGreen MAS
Request/Response schemas and database models
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4


# Enums
class JobStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class ServiceVertical(str, Enum):
    HVAC = "hvac"
    PLUMBING = "plumbing"
    ELECTRICAL = "electrical"
    LANDSCAPING = "landscaping"
    GENERAL = "general"


class ComplianceStatus(str, Enum):
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PARTIAL = "partial"
    PENDING_REVIEW = "pending_review"


class CertificateType(str, Enum):
    GREEN_VERIFIED = "green_verified"
    ESG_AUDIT = "esg_audit"
    REBATE_SUMMARY = "rebate_summary"
    COMPLIANCE_REPORT = "compliance_report"


class EmissionScope(str, Enum):
    SCOPE_1 = "scope_1"
    SCOPE_2 = "scope_2"
    SCOPE_3 = "scope_3"


class FSMProvider(str, Enum):
    SERVICETITAN = "servicetitan"
    JOBBER = "jobber"
    HOUSECALL_PRO = "housecall_pro"


# Base Models
class AddressModel(BaseModel):
    """Address information."""
    street: str
    city: str
    state: str
    zip_code: str = Field(..., pattern=r"^\d{5}(-\d{4})?$")
    country: str = "US"


class EquipmentModel(BaseModel):
    """Equipment details."""
    id: Optional[str] = None
    type: str
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    fuel_type: Optional[str] = None
    efficiency: Optional[float] = None
    capacity_btu: Optional[int] = None
    refrigerant_type: Optional[str] = None
    refrigerant_charge_kg: Optional[float] = None
    installation_date: Optional[datetime] = None
    custom_fields: Dict[str, Any] = Field(default_factory=dict)


class MaterialModel(BaseModel):
    """Material/part used in job."""
    name: str
    quantity: float
    unit: str
    weight_lbs: Optional[float] = None
    disposal_method: Optional[str] = None  # recycle, landfill, reuse


# Job Models
class JobCreateRequest(BaseModel):
    """Request to create a new job for analysis."""
    external_id: str
    provider: FSMProvider
    customer_name: str
    address: AddressModel
    vertical: ServiceVertical
    job_type: str
    description: Optional[str] = None
    technician_id: Optional[str] = None
    scheduled_start: Optional[datetime] = None
    equipment_installed: List[EquipmentModel] = Field(default_factory=list)
    equipment_removed: List[EquipmentModel] = Field(default_factory=list)
    materials_used: List[MaterialModel] = Field(default_factory=list)
    travel_distance_miles: Optional[float] = None
    custom_fields: Dict[str, Any] = Field(default_factory=dict)


class JobResponse(BaseModel):
    """Job response with analysis results."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    external_id: str
    provider: FSMProvider
    status: JobStatus
    customer_name: str
    address: AddressModel
    vertical: ServiceVertical
    job_type: str
    compliance_status: Optional[ComplianceStatus] = None
    carbon_footprint_kg: Optional[float] = None
    certificates: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


# Compliance Models
class ComplianceCheckRequest(BaseModel):
    """Request for compliance check."""
    job_id: Optional[UUID] = None
    state: str = Field(..., min_length=2, max_length=2)
    vertical: ServiceVertical
    equipment: List[EquipmentModel]
    materials: Optional[List[MaterialModel]] = None
    reporting_standard: str = "CA_SB_253"


class ComplianceIssue(BaseModel):
    """Individual compliance issue."""
    code: str
    severity: str  # critical, warning, info
    category: str
    description: str
    regulation: str
    recommendation: str
    deadline: Optional[datetime] = None


class ComplianceCheckResponse(BaseModel):
    """Response from compliance check."""
    status: ComplianceStatus
    score: float = Field(..., ge=0, le=100)
    issues: List[ComplianceIssue] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    regulations_checked: List[str] = Field(default_factory=list)
    future_proof_alerts: List[str] = Field(default_factory=list)
    checked_at: datetime = Field(default_factory=lambda: datetime.now())


# Carbon/ESG Models
class CarbonCalculationRequest(BaseModel):
    """Request for carbon footprint calculation."""
    job_id: Optional[UUID] = None
    state: str
    vertical: ServiceVertical
    travel_distance_miles: Optional[float] = None
    vehicle_type: str = "gasoline"
    vehicle_mpg: float = 25.0
    electricity_kwh: Optional[float] = None
    fuel_used: Optional[List[Dict[str, Any]]] = None
    refrigerant: Optional[Dict[str, Any]] = None
    waste: Optional[List[Dict[str, Any]]] = None
    equipment_installed: Optional[List[Dict[str, Any]]] = None
    old_equipment: Optional[Dict[str, Any]] = None
    new_equipment: Optional[Dict[str, Any]] = None


class ScopeEmissions(BaseModel):
    """Emissions by scope."""
    scope: EmissionScope
    total_kg_co2e: float
    categories: List[Dict[str, Any]] = Field(default_factory=list)


class CarbonCalculationResponse(BaseModel):
    """Response from carbon calculation."""
    job_id: Optional[UUID] = None
    total_kg_co2e: float
    scope_1_kg: float
    scope_2_kg: float
    scope_3_kg: float
    scope_breakdown: List[ScopeEmissions] = Field(default_factory=list)
    avoided_emissions_kg: Optional[float] = None
    methodology: str
    sources: List[str] = Field(default_factory=list)
    calculated_at: datetime = Field(default_factory=lambda: datetime.now())


# Rebate/Incentive Models
class RebateSearchRequest(BaseModel):
    """Request to search for rebates."""
    zip_code: str = Field(..., pattern=r"^\d{5}$")
    state: str
    vertical: ServiceVertical
    equipment_type: str
    equipment_cost: Optional[float] = None
    income_qualified: bool = False
    utility_provider: Optional[str] = None


class RebateItem(BaseModel):
    """Individual rebate/incentive."""
    id: str
    name: str
    type: str  # federal_credit, state_rebate, utility_rebate
    amount: float
    percentage: Optional[float] = None
    max_amount: Optional[float] = None
    description: str
    requirements: List[str] = Field(default_factory=list)
    expiration_date: Optional[datetime] = None
    source: str
    apply_url: Optional[str] = None


class RebateSearchResponse(BaseModel):
    """Response from rebate search."""
    total_available: float
    federal_credits: List[RebateItem] = Field(default_factory=list)
    state_rebates: List[RebateItem] = Field(default_factory=list)
    utility_rebates: List[RebateItem] = Field(default_factory=list)
    local_incentives: List[RebateItem] = Field(default_factory=list)
    income_qualified_bonuses: List[RebateItem] = Field(default_factory=list)


# Certificate Models
class CertificateGenerateRequest(BaseModel):
    """Request to generate a certificate."""
    job_id: UUID
    certificate_type: CertificateType
    include_carbon_footprint: bool = True
    include_compliance_details: bool = True
    include_rebates: bool = True


class CertificateResponse(BaseModel):
    """Generated certificate response."""
    id: UUID = Field(default_factory=uuid4)
    job_id: UUID
    certificate_type: CertificateType
    public_url: str
    pdf_url: Optional[str] = None
    qr_code_url: Optional[str] = None
    verification_code: str
    issued_at: datetime = Field(default_factory=lambda: datetime.now())
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# Green Ledger Models
class CarbonTransaction(BaseModel):
    """Carbon transaction for ledger."""
    id: UUID = Field(default_factory=uuid4)
    job_id: UUID
    company_id: UUID
    transaction_type: str  # emission, offset, avoidance
    scope: EmissionScope
    amount_kg_co2e: float
    category: str
    description: str
    methodology: str
    sources: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now())
    verified: bool = False


class LedgerSummary(BaseModel):
    """Monthly/annual ledger summary."""
    company_id: UUID
    period_start: datetime
    period_end: datetime
    total_emissions_kg: float
    scope_1_total: float
    scope_2_total: float
    scope_3_total: float
    total_avoided_kg: float
    total_offset_kg: float
    net_emissions_kg: float
    job_count: int
    transactions: List[CarbonTransaction] = Field(default_factory=list)
    by_vertical: Dict[str, float] = Field(default_factory=dict)
    by_category: Dict[str, float] = Field(default_factory=dict)
    trend_vs_previous: Optional[float] = None  # Percentage change
    sb253_ready: bool = False


# Webhook Models
class WebhookEvent(BaseModel):
    """Incoming webhook event."""
    provider: FSMProvider
    event_type: str
    timestamp: datetime
    payload: Dict[str, Any]
    signature: Optional[str] = None


class WebhookResponse(BaseModel):
    """Webhook processing response."""
    status: str
    message: str
    job_id: Optional[UUID] = None
    processing_id: Optional[str] = None


# Agent Models
class AgentTaskRequest(BaseModel):
    """Request to run an agent task."""
    task_type: str  # audit, rebate_search, compliance_check, certificate
    job_id: Optional[UUID] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    priority: str = "normal"  # low, normal, high, urgent


class AgentTaskResponse(BaseModel):
    """Response from agent task."""
    task_id: UUID = Field(default_factory=uuid4)
    status: str  # queued, processing, completed, failed
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


# API Response Wrappers
class SuccessResponse(BaseModel):
    """Generic success response."""
    success: bool = True
    message: str
    data: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    """Generic error response."""
    success: bool = False
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None


class PaginatedResponse(BaseModel):
    """Paginated list response."""
    items: List[Any]
    total: int
    page: int
    page_size: int
    has_more: bool


# Health Check
class HealthCheckResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now())
    components: Dict[str, str] = Field(default_factory=dict)
