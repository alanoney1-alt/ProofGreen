"""
ProofGreen MAS - Pydantic Guardrails
Input validation schemas that "fail closed" for invalid data.

These guardrails ensure:
- All tool inputs are validated before processing
- Invalid model numbers, equipment specs, etc. are rejected
- Security vulnerabilities from injection attacks are prevented
- Data integrity is maintained throughout the pipeline
"""

import re
from datetime import datetime, date
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
    ConfigDict,
    ValidationError
)


# =========================================================================
# Enums for Type Safety
# =========================================================================

class ServiceVertical(str, Enum):
    """Valid service verticals."""
    HVAC = "hvac"
    PLUMBING = "plumbing"
    ELECTRICAL = "electrical"
    LANDSCAPING = "landscaping"
    ROOFING = "roofing"
    SOLAR = "solar"
    GENERAL = "general"


class RefrigerantType(str, Enum):
    """Valid refrigerant types."""
    R22 = "R-22"
    R410A = "R-410A"
    R407C = "R-407C"
    R454B = "R-454B"
    R32 = "R-32"
    R290 = "R-290"
    R744 = "R-744"
    R1234YF = "R-1234yf"


class RiskLevel(str, Enum):
    """Risk levels for governance."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class USState(str, Enum):
    """US States for validation."""
    AL = "AL"
    AK = "AK"
    AZ = "AZ"
    AR = "AR"
    CA = "CA"
    CO = "CO"
    CT = "CT"
    DE = "DE"
    FL = "FL"
    GA = "GA"
    HI = "HI"
    ID = "ID"
    IL = "IL"
    IN = "IN"
    IA = "IA"
    KS = "KS"
    KY = "KY"
    LA = "LA"
    ME = "ME"
    MD = "MD"
    MA = "MA"
    MI = "MI"
    MN = "MN"
    MS = "MS"
    MO = "MO"
    MT = "MT"
    NE = "NE"
    NV = "NV"
    NH = "NH"
    NJ = "NJ"
    NM = "NM"
    NY = "NY"
    NC = "NC"
    ND = "ND"
    OH = "OH"
    OK = "OK"
    OR = "OR"
    PA = "PA"
    RI = "RI"
    SC = "SC"
    SD = "SD"
    TN = "TN"
    TX = "TX"
    UT = "UT"
    VT = "VT"
    VA = "VA"
    WA = "WA"
    WV = "WV"
    WI = "WI"
    WY = "WY"
    DC = "DC"


# =========================================================================
# Base Guardrail Models
# =========================================================================

class GuardrailBase(BaseModel):
    """Base model with strict configuration."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",  # Fail on unexpected fields
        frozen=False
    )


# =========================================================================
# Equipment Validation Schemas
# =========================================================================

class ModelNumberInput(GuardrailBase):
    """Validates equipment model numbers."""
    model_number: str = Field(..., min_length=3, max_length=50)

    @field_validator("model_number")
    @classmethod
    def validate_model_number(cls, v: str) -> str:
        # Remove common separators for validation
        cleaned = re.sub(r'[-_\s]', '', v)

        # Must be alphanumeric (with some special chars)
        if not re.match(r'^[A-Za-z0-9\-_/]+$', v):
            raise ValueError(
                f"Invalid model number format: '{v}'. "
                "Model numbers must be alphanumeric with optional hyphens/underscores."
            )

        # Check for obviously invalid patterns
        invalid_patterns = [
            r'^0+$',           # All zeros
            r'^[A-Za-z]+$',    # All letters (no numbers)
            r'^test',          # Test data
            r'^xxx',           # Placeholder
            r'^n/?a$',         # N/A
        ]
        for pattern in invalid_patterns:
            if re.match(pattern, v.lower()):
                raise ValueError(f"Invalid model number: '{v}' appears to be placeholder data.")

        return v.upper()


class SerialNumberInput(GuardrailBase):
    """Validates equipment serial numbers."""
    serial_number: str = Field(..., min_length=5, max_length=30)

    @field_validator("serial_number")
    @classmethod
    def validate_serial_number(cls, v: str) -> str:
        # Must be alphanumeric
        if not re.match(r'^[A-Za-z0-9\-]+$', v):
            raise ValueError(
                f"Invalid serial number format: '{v}'. "
                "Serial numbers must be alphanumeric."
            )

        # Check for sequential or repeating patterns (likely invalid)
        if re.match(r'^(.)\1+$', v) or v in ["12345", "00000", "AAAAA"]:
            raise ValueError(f"Invalid serial number: '{v}' appears to be test data.")

        return v.upper()


class HVACEquipmentInput(GuardrailBase):
    """Validates HVAC equipment specifications."""
    model_number: str = Field(..., min_length=3, max_length=50)
    manufacturer: Optional[str] = Field(None, max_length=100)

    # Efficiency ratings
    seer_rating: Optional[float] = Field(None, ge=8.0, le=30.0)
    seer2_rating: Optional[float] = Field(None, ge=8.0, le=30.0)
    hspf_rating: Optional[float] = Field(None, ge=5.0, le=15.0)
    hspf2_rating: Optional[float] = Field(None, ge=5.0, le=15.0)
    eer_rating: Optional[float] = Field(None, ge=5.0, le=20.0)

    # Refrigerant
    refrigerant_type: Optional[RefrigerantType] = None
    refrigerant_charge_oz: Optional[float] = Field(None, ge=0, le=500)

    # Capacity
    btu_capacity: Optional[int] = Field(None, ge=5000, le=200000)
    tonnage: Optional[float] = Field(None, ge=0.5, le=20.0)

    @field_validator("seer2_rating")
    @classmethod
    def validate_seer2_realistic(cls, v: Optional[float]) -> Optional[float]:
        if v is not None:
            # 2026 minimum is ~14.3, max practical is ~26
            if v < 10.0:
                raise ValueError(
                    f"SEER2 rating {v} is below realistic minimum. "
                    "Verify the equipment label."
                )
        return v

    @model_validator(mode="after")
    def validate_tonnage_btu_match(self):
        """Verify tonnage and BTU are consistent."""
        if self.tonnage and self.btu_capacity:
            expected_btu = self.tonnage * 12000
            tolerance = 0.15  # 15% tolerance
            if abs(self.btu_capacity - expected_btu) / expected_btu > tolerance:
                raise ValueError(
                    f"BTU ({self.btu_capacity}) and tonnage ({self.tonnage}) don't match. "
                    f"Expected ~{int(expected_btu)} BTU for {self.tonnage} tons."
                )
        return self


class PlumbingEquipmentInput(GuardrailBase):
    """Validates plumbing equipment specifications."""
    model_number: str = Field(..., min_length=3, max_length=50)
    fixture_type: str = Field(..., pattern=r'^(showerhead|faucet|toilet|water_heater|urinal)$')

    # Flow rates
    gpm: Optional[float] = Field(None, ge=0.1, le=10.0)
    gpf: Optional[float] = Field(None, ge=0.1, le=5.0)

    # Water heater specific
    uef: Optional[float] = Field(None, ge=0.1, le=5.0)
    tank_capacity_gallons: Optional[float] = Field(None, ge=0, le=120)
    first_hour_rating: Optional[float] = Field(None, ge=10, le=200)

    @field_validator("gpm")
    @classmethod
    def validate_gpm_realistic(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v > 5.0:
            raise ValueError(
                f"GPM of {v} is unusually high. "
                "WaterSense fixtures are typically 1.2-2.0 GPM."
            )
        return v


# =========================================================================
# Job Input Validation
# =========================================================================

class JobInput(GuardrailBase):
    """Validates job submission data."""
    job_id: Optional[str] = Field(None, pattern=r'^[A-Za-z0-9\-_]+$')
    external_id: Optional[str] = Field(None, max_length=50)

    # Location
    state: USState
    zip_code: str = Field(..., pattern=r'^\d{5}(-\d{4})?$')

    # Job details
    vertical: ServiceVertical
    job_type: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = Field(None, max_length=2000)

    # Equipment
    equipment_installed: Optional[List[Dict[str, Any]]] = None
    old_equipment_removed: Optional[List[Dict[str, Any]]] = None

    # Customer info (limited)
    customer_name: Optional[str] = Field(None, max_length=100)
    property_type: Optional[str] = Field(
        None, pattern=r'^(residential|commercial|industrial)$'
    )

    @field_validator("zip_code")
    @classmethod
    def validate_zip_exists(cls, v: str) -> str:
        # Basic validation - in production, verify against USPS database
        zip_num = int(v[:5])
        if zip_num < 501 or zip_num > 99950:
            raise ValueError(f"ZIP code {v} is not valid.")
        return v

    @field_validator("description")
    @classmethod
    def sanitize_description(cls, v: Optional[str]) -> Optional[str]:
        if v:
            # Remove potential injection attempts
            dangerous_patterns = [
                r'<script',
                r'javascript:',
                r'on\w+\s*=',
                r'\{\{.*\}\}',  # Template injection
                r'\$\{.*\}',    # String interpolation
            ]
            for pattern in dangerous_patterns:
                if re.search(pattern, v, re.IGNORECASE):
                    raise ValueError("Description contains invalid characters.")
        return v


# =========================================================================
# Financial Input Validation
# =========================================================================

class FinancialInput(GuardrailBase):
    """Validates financial data for rebate/credit calculations."""
    amount_dollars: float = Field(..., ge=0, le=100000)
    program_type: str = Field(..., pattern=r'^(federal_credit|state_rebate|heehra|utility)$')

    # Income qualification
    household_income: Optional[float] = Field(None, ge=0, le=10000000)
    household_size: Optional[int] = Field(None, ge=1, le=20)

    # Equipment details
    equipment_cost: float = Field(..., ge=0, le=500000)
    installation_cost: Optional[float] = Field(None, ge=0, le=100000)

    @model_validator(mode="after")
    def validate_amount_vs_cost(self):
        """Ensure rebate amount doesn't exceed equipment cost."""
        if self.amount_dollars > self.equipment_cost:
            raise ValueError(
                f"Rebate amount ${self.amount_dollars} cannot exceed "
                f"equipment cost ${self.equipment_cost}."
            )
        return self


class TaxCreditInput(GuardrailBase):
    """Validates tax credit filing inputs."""
    credit_type: str = Field(..., pattern=r'^(25C|25D|30D|45L|45W)$')
    tax_year: int = Field(..., ge=2022, le=2030)
    amount_claimed: float = Field(..., ge=0, le=50000)

    # Equipment
    equipment_type: str = Field(..., max_length=100)
    equipment_cost: float = Field(..., ge=0, le=500000)
    installation_date: date

    # Verification
    energy_star_certified: bool = False
    ahri_certificate_number: Optional[str] = Field(None, pattern=r'^[A-Z0-9]+$')

    @model_validator(mode="after")
    def validate_credit_limits(self):
        """Validate credit amount against IRA limits."""
        limits = {
            "25C": 1200,   # Home improvement credit annual limit
            "25D": None,   # No dollar limit, 30% of cost
            "30D": 7500,   # Clean vehicle credit
            "45L": 5000,   # New energy efficient home
            "45W": 40000,  # Commercial clean vehicle
        }

        limit = limits.get(self.credit_type)
        if limit and self.amount_claimed > limit:
            raise ValueError(
                f"Credit amount ${self.amount_claimed} exceeds "
                f"Section {self.credit_type} limit of ${limit}."
            )

        # 25D is 30% of cost
        if self.credit_type == "25D":
            max_credit = self.equipment_cost * 0.30
            if self.amount_claimed > max_credit:
                raise ValueError(
                    f"Section 25D credit cannot exceed 30% of cost "
                    f"(${max_credit:.2f})."
                )

        return self


# =========================================================================
# Governance Input Validation
# =========================================================================

class ApprovalInput(GuardrailBase):
    """Validates approval/rejection inputs."""
    task_id: str = Field(..., pattern=r'^[A-Za-z0-9\-_]+$')
    approver_id: str = Field(..., min_length=1, max_length=50)
    approver_name: str = Field(..., min_length=2, max_length=100)
    action: str = Field(..., pattern=r'^(approve|reject)$')
    reason: Optional[str] = Field(None, max_length=500)

    @field_validator("approver_name")
    @classmethod
    def validate_approver_name(cls, v: str) -> str:
        # Basic name validation
        if not re.match(r'^[A-Za-z\s\-\.]+$', v):
            raise ValueError("Approver name contains invalid characters.")
        return v


# =========================================================================
# Photo/Document Input Validation
# =========================================================================

class PhotoUploadInput(GuardrailBase):
    """Validates photo upload inputs."""
    file_path: str = Field(..., max_length=500)
    file_type: str = Field(..., pattern=r'^(image/jpeg|image/png|image/webp)$')
    file_size_bytes: int = Field(..., gt=0, le=20_000_000)  # Max 20MB

    @field_validator("file_path")
    @classmethod
    def validate_file_path(cls, v: str) -> str:
        # Prevent path traversal attacks
        dangerous_patterns = [
            r'\.\.',        # Parent directory
            r'^/',          # Absolute path (adjust for your use case)
            r'~',           # Home directory
            r'\$',          # Environment variables
            r'%',           # URL encoding
        ]
        for pattern in dangerous_patterns:
            if re.search(pattern, v):
                raise ValueError(f"Invalid file path: potential security issue detected.")
        return v


# =========================================================================
# Validation Helper Functions
# =========================================================================

def validate_input(schema: type[GuardrailBase], data: Dict[str, Any]) -> tuple[bool, Any, Optional[str]]:
    """
    Validate input data against a schema.

    Returns:
        tuple: (is_valid, validated_data or None, error_message or None)
    """
    try:
        validated = schema(**data)
        return True, validated, None
    except ValidationError as e:
        error_messages = []
        for error in e.errors():
            field = ".".join(str(loc) for loc in error["loc"])
            msg = error["msg"]
            error_messages.append(f"{field}: {msg}")
        return False, None, "; ".join(error_messages)


def fail_closed(schema: type[GuardrailBase], data: Dict[str, Any], action: str = "process") -> GuardrailBase:
    """
    Validate input and fail closed if invalid.

    Raises:
        ValueError: If validation fails

    Returns:
        Validated model instance
    """
    is_valid, result, error = validate_input(schema, data)
    if not is_valid:
        raise ValueError(f"Cannot {action}: {error}")
    return result


# =========================================================================
# Guardrail Decorators
# =========================================================================

def validate_with(schema: type[GuardrailBase]):
    """Decorator to validate function inputs against a schema."""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            # Validate kwargs against schema
            is_valid, validated, error = validate_input(schema, kwargs)
            if not is_valid:
                raise ValueError(f"Input validation failed: {error}")
            return await func(*args, **validated.model_dump())

        def sync_wrapper(*args, **kwargs):
            is_valid, validated, error = validate_input(schema, kwargs)
            if not is_valid:
                raise ValueError(f"Input validation failed: {error}")
            return func(*args, **validated.model_dump())

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
