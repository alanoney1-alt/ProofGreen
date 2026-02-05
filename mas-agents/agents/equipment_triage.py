"""
ProofGreen MAS - Equipment Triage Node
LangGraph node for equipment analysis using Vision OCR and regulatory compliance.
"""

import json
from typing import Dict, List, Optional, Any, TypedDict
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import anthropic

from config.settings import settings, get_seer2_minimum, get_climate_region


class ComplianceStatus(str, Enum):
    """Equipment compliance status."""
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    UPGRADE_OPPORTUNITY = "upgrade_opportunity"
    UNKNOWN = "unknown"


class TriageRecommendation(str, Enum):
    """Triage recommendations."""
    MAINTAIN = "maintain"
    REPAIR = "repair"
    UPGRADE_EFFICIENCY = "upgrade_efficiency"
    MANDATORY_UPGRADE = "mandatory_upgrade"
    IMMEDIATE_REPLACEMENT = "immediate_replacement"


@dataclass
class EquipmentData:
    """Extracted equipment data."""
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    manufacture_year: Optional[int] = None
    equipment_type: Optional[str] = None
    refrigerant: Optional[str] = None
    seer_rating: Optional[float] = None
    seer2_rating: Optional[float] = None
    capacity_tons: Optional[float] = None
    voltage: Optional[str] = None
    gwp: Optional[int] = None
    age_years: Optional[float] = None


@dataclass
class TriageResult:
    """Result of equipment triage."""
    is_compliant: bool
    compliance_status: ComplianceStatus
    triage_recommendation: TriageRecommendation
    carbon_baseline: float
    compliance_risk_score: int  # 0-100
    violations: List[str]
    opportunities: List[str]
    estimated_savings_kwh: float
    estimated_carbon_reduction_kg: float
    urgency: str  # low, medium, high, critical


class EquipmentTriageNode:
    """
    LangGraph node for equipment triage.
    Analyzes equipment photos, checks 2026 regulatory compliance,
    and generates recommendations.
    """

    # 2026 Refrigerant Standards (EPA AIM Act)
    COMPLIANT_REFRIGERANTS = {
        "R-32": {"gwp": 675, "status": "compliant", "class": "A2L"},
        "R-454B": {"gwp": 466, "status": "compliant", "class": "A2L"},
        "R-290": {"gwp": 3, "status": "compliant", "class": "A3"},
        "R-744": {"gwp": 1, "status": "compliant", "class": "A1"},
    }

    NON_COMPLIANT_REFRIGERANTS = {
        "R-410A": {"gwp": 2088, "status": "phase_out_2025", "class": "A1"},
        "R-22": {"gwp": 1810, "status": "banned", "class": "A1"},
        "R-407C": {"gwp": 1774, "status": "phase_out_2025", "class": "A1"},
        "R-134A": {"gwp": 1430, "status": "restricted", "class": "A1"},
    }

    # 2026 Efficiency Standards
    SEER2_MINIMUMS = {
        "north": 14.3,
        "south": 15.2,
        "southwest": 15.2,
    }

    def __init__(self, state: Dict[str, Any]):
        """
        Initialize EquipmentTriageNode.

        Args:
            state: LangGraph state containing job_id, zip_code, etc.
        """
        self.state = state
        self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    async def execute(
        self,
        image_url: Optional[str] = None,
        image_data: Optional[bytes] = None,
        equipment_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Execute equipment triage.

        Args:
            image_url: URL to equipment photo
            image_data: Raw image bytes
            equipment_data: Pre-extracted equipment data (if available)

        Returns:
            Triage result dict for LangGraph state
        """
        # 1. Extract equipment data from image or use provided data
        if equipment_data:
            extracted = EquipmentData(**equipment_data)
        elif image_url or image_data:
            extracted = await self._parse_equipment_photo(image_url, image_data)
        else:
            raise ValueError("Must provide either image_url, image_data, or equipment_data")

        # 2. Get regulatory mandates for location
        zip_code = self.state.get("zip_code", "")
        state_code = self.state.get("state", "CA")
        mandates = self._get_vertical_mandates(state_code)

        # 3. Perform compliance checks
        violations = []
        opportunities = []
        risk_score = 0

        # Refrigerant compliance check
        refrigerant_result = self._check_refrigerant_compliance(extracted.refrigerant)
        if not refrigerant_result["compliant"]:
            violations.append(refrigerant_result["violation"])
            risk_score += refrigerant_result["risk_score"]

        # SEER2 efficiency check
        seer2_result = self._check_seer2_compliance(
            extracted.seer2_rating or extracted.seer_rating,
            state_code
        )
        if not seer2_result["compliant"]:
            if seer2_result["is_opportunity"]:
                opportunities.append(seer2_result["message"])
                risk_score += 10
            else:
                violations.append(seer2_result["message"])
                risk_score += seer2_result["risk_score"]

        # Age check
        age_result = self._check_equipment_age(extracted.age_years)
        if age_result["concern"]:
            opportunities.append(age_result["message"])
            risk_score += age_result["risk_score"]

        # 4. Determine compliance status and recommendation
        is_compliant = len(violations) == 0
        compliance_status = self._determine_compliance_status(violations, opportunities)
        recommendation = self._determine_recommendation(
            violations, opportunities, extracted
        )

        # 5. Calculate carbon baseline and potential savings
        carbon_baseline = self._calculate_carbon_baseline(extracted)
        savings = self._estimate_upgrade_savings(extracted, mandates)

        # 6. Build result
        result = TriageResult(
            is_compliant=is_compliant,
            compliance_status=compliance_status,
            triage_recommendation=recommendation,
            carbon_baseline=carbon_baseline,
            compliance_risk_score=min(100, risk_score),
            violations=violations,
            opportunities=opportunities,
            estimated_savings_kwh=savings["kwh"],
            estimated_carbon_reduction_kg=savings["carbon_kg"],
            urgency=self._determine_urgency(risk_score, violations)
        )

        # Return state update for LangGraph
        return {
            "equipment_data": {
                "manufacturer": extracted.manufacturer,
                "model": extracted.model,
                "serial_number": extracted.serial_number,
                "refrigerant": extracted.refrigerant,
                "seer2": extracted.seer2_rating or extracted.seer_rating,
                "capacity_tons": extracted.capacity_tons,
                "age_years": extracted.age_years,
            },
            "is_compliant": result.is_compliant,
            "compliance_status": result.compliance_status.value,
            "triage_recommendation": result.triage_recommendation.value,
            "carbon_baseline": result.carbon_baseline,
            "compliance_risk_score": result.compliance_risk_score,
            "violations": result.violations,
            "opportunities": result.opportunities,
            "estimated_savings": {
                "kwh_annually": result.estimated_savings_kwh,
                "carbon_kg_annually": result.estimated_carbon_reduction_kg
            },
            "urgency": result.urgency
        }

    async def _parse_equipment_photo(
        self,
        image_url: Optional[str] = None,
        image_data: Optional[bytes] = None
    ) -> EquipmentData:
        """Use Claude Vision to extract equipment data from photo."""
        import base64

        prompt = """Analyze this HVAC equipment nameplate/label photo and extract:

1. Manufacturer/Brand name
2. Model number
3. Serial number
4. Manufacture date/year
5. Equipment type (AC, Heat Pump, Furnace, etc.)
6. Refrigerant type (R-410A, R-454B, R-32, etc.)
7. SEER/SEER2 rating
8. Capacity (BTU or Tons)
9. Voltage/Phase

Return as JSON:
{
    "manufacturer": "Carrier",
    "model": "24ACC636A003",
    "serial_number": "1234567890",
    "manufacture_year": 2018,
    "equipment_type": "air_conditioner",
    "refrigerant": "R-410A",
    "seer_rating": 16.0,
    "seer2_rating": 15.2,
    "capacity_tons": 3.0,
    "voltage": "208-230V"
}

If a field cannot be determined, use null."""

        content = [{"type": "text", "text": prompt}]

        if image_url:
            content.insert(0, {
                "type": "image",
                "source": {"type": "url", "url": image_url}
            })
        elif image_data:
            content.insert(0, {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": base64.b64encode(image_data).decode()
                }
            })

        try:
            response = self.client.messages.create(
                model=settings.VISION_MODEL,
                max_tokens=1000,
                messages=[{"role": "user", "content": content}]
            )

            data = json.loads(response.content[0].text)

            # Calculate age if year is available
            age_years = None
            if data.get("manufacture_year"):
                age_years = datetime.now().year - data["manufacture_year"]

            # Look up GWP for refrigerant
            gwp = None
            refrigerant = data.get("refrigerant")
            if refrigerant:
                if refrigerant in self.COMPLIANT_REFRIGERANTS:
                    gwp = self.COMPLIANT_REFRIGERANTS[refrigerant]["gwp"]
                elif refrigerant in self.NON_COMPLIANT_REFRIGERANTS:
                    gwp = self.NON_COMPLIANT_REFRIGERANTS[refrigerant]["gwp"]

            return EquipmentData(
                manufacturer=data.get("manufacturer"),
                model=data.get("model"),
                serial_number=data.get("serial_number"),
                manufacture_year=data.get("manufacture_year"),
                equipment_type=data.get("equipment_type"),
                refrigerant=refrigerant,
                seer_rating=data.get("seer_rating"),
                seer2_rating=data.get("seer2_rating"),
                capacity_tons=data.get("capacity_tons"),
                voltage=data.get("voltage"),
                gwp=gwp,
                age_years=age_years
            )

        except Exception as e:
            print(f"Vision parsing error: {e}")
            return EquipmentData()

    def _get_vertical_mandates(self, state_code: str) -> Dict:
        """Get regulatory mandates for HVAC in given state."""
        region = get_climate_region(state_code)
        min_seer2 = get_seer2_minimum(state_code)

        return {
            "region": region,
            "min_seer2": min_seer2,
            "refrigerant_gwp_limit": 700,  # EPA AIM Act 2025
            "required_refrigerant_class": "A2L",  # Low-GWP requirement
            "phase_out_deadline": "2025-01-01",
            "state_specific": self._get_state_specific_mandates(state_code)
        }

    def _get_state_specific_mandates(self, state_code: str) -> Dict:
        """Get state-specific additional mandates."""
        state_mandates = {
            "CA": {
                "carb_compliance": True,
                "title_24_required": True,
                "min_seer2_override": 15.2,
                "requires_permit_photo": True,
            },
            "WA": {
                "clean_energy_act": True,
                "min_seer2_override": 15.0,
            },
            "NY": {
                "clcpa_compliance": True,
                "heat_pump_incentive": True,
            },
        }
        return state_mandates.get(state_code, {})

    def _check_refrigerant_compliance(self, refrigerant: Optional[str]) -> Dict:
        """Check refrigerant compliance with EPA AIM Act."""
        if not refrigerant:
            return {
                "compliant": True,  # Unknown = can't fail
                "violation": None,
                "risk_score": 0
            }

        refrigerant_upper = refrigerant.upper().replace("-", "").replace(" ", "")

        # Check compliant refrigerants
        for ref, info in self.COMPLIANT_REFRIGERANTS.items():
            if ref.upper().replace("-", "") == refrigerant_upper:
                return {
                    "compliant": True,
                    "violation": None,
                    "risk_score": 0,
                    "gwp": info["gwp"],
                    "class": info["class"]
                }

        # Check non-compliant refrigerants
        for ref, info in self.NON_COMPLIANT_REFRIGERANTS.items():
            if ref.upper().replace("-", "") == refrigerant_upper:
                if info["status"] == "banned":
                    return {
                        "compliant": False,
                        "violation": f"CRITICAL: {refrigerant} is BANNED under EPA regulations",
                        "risk_score": 50,
                        "gwp": info["gwp"]
                    }
                elif info["status"] == "phase_out_2025":
                    return {
                        "compliant": False,
                        "violation": f"Mandatory Upgrade Required: {refrigerant} (GWP {info['gwp']}) phased out under EPA AIM Act 2025",
                        "risk_score": 40,
                        "gwp": info["gwp"]
                    }
                else:
                    return {
                        "compliant": False,
                        "violation": f"Restricted: {refrigerant} (GWP {info['gwp']}) - transition to A2L refrigerant recommended",
                        "risk_score": 20,
                        "gwp": info["gwp"]
                    }

        # Unknown refrigerant
        return {
            "compliant": True,
            "violation": None,
            "risk_score": 5,
            "note": f"Unknown refrigerant: {refrigerant}"
        }

    def _check_seer2_compliance(
        self,
        seer_rating: Optional[float],
        state_code: str
    ) -> Dict:
        """Check SEER2 efficiency compliance."""
        if not seer_rating:
            return {
                "compliant": True,
                "is_opportunity": False,
                "message": None,
                "risk_score": 0
            }

        min_seer2 = get_seer2_minimum(state_code)

        if seer_rating < min_seer2:
            return {
                "compliant": False,
                "is_opportunity": True,
                "message": f"Efficiency below {min_seer2} SEER2 minimum for this region (current: {seer_rating})",
                "risk_score": 15
            }

        # Check for upgrade opportunity (even if compliant)
        if seer_rating < 18:
            return {
                "compliant": True,
                "is_opportunity": True,
                "message": f"Upgrade opportunity: Current {seer_rating} SEER2 could be improved to 18+ for significant savings",
                "risk_score": 0
            }

        return {
            "compliant": True,
            "is_opportunity": False,
            "message": None,
            "risk_score": 0
        }

    def _check_equipment_age(self, age_years: Optional[float]) -> Dict:
        """Check equipment age and lifespan concerns."""
        if not age_years:
            return {"concern": False, "message": None, "risk_score": 0}

        if age_years >= 15:
            return {
                "concern": True,
                "message": f"Equipment is {age_years:.0f} years old - approaching/past typical lifespan (15 years)",
                "risk_score": 25
            }
        elif age_years >= 10:
            return {
                "concern": True,
                "message": f"Equipment is {age_years:.0f} years old - consider proactive replacement planning",
                "risk_score": 10
            }

        return {"concern": False, "message": None, "risk_score": 0}

    def _determine_compliance_status(
        self,
        violations: List[str],
        opportunities: List[str]
    ) -> ComplianceStatus:
        """Determine overall compliance status."""
        if any("CRITICAL" in v or "BANNED" in v for v in violations):
            return ComplianceStatus.NON_COMPLIANT
        elif any("Mandatory" in v for v in violations):
            return ComplianceStatus.NON_COMPLIANT
        elif violations:
            return ComplianceStatus.NON_COMPLIANT
        elif opportunities:
            return ComplianceStatus.UPGRADE_OPPORTUNITY
        return ComplianceStatus.COMPLIANT

    def _determine_recommendation(
        self,
        violations: List[str],
        opportunities: List[str],
        equipment: EquipmentData
    ) -> TriageRecommendation:
        """Determine triage recommendation."""
        # Critical violations
        if any("BANNED" in v or "CRITICAL" in v for v in violations):
            return TriageRecommendation.IMMEDIATE_REPLACEMENT

        # Mandatory upgrade (refrigerant phase-out)
        if any("Mandatory Upgrade" in v for v in violations):
            return TriageRecommendation.MANDATORY_UPGRADE

        # Efficiency upgrade opportunity
        if any("Efficiency" in v or "SEER2" in v.upper() for v in violations + opportunities):
            return TriageRecommendation.UPGRADE_EFFICIENCY

        # Age-based recommendation
        if equipment.age_years and equipment.age_years >= 15:
            return TriageRecommendation.UPGRADE_EFFICIENCY

        # Default - equipment is compliant
        return TriageRecommendation.MAINTAIN

    def _calculate_carbon_baseline(self, equipment: EquipmentData) -> float:
        """Calculate current carbon footprint baseline."""
        # Estimate annual kWh based on SEER and capacity
        if not equipment.seer2_rating and not equipment.seer_rating:
            return 0.0

        seer = equipment.seer2_rating or equipment.seer_rating
        capacity_btu = (equipment.capacity_tons or 3) * 12000

        # Estimate annual cooling hours (varies by region, use 1000 as average)
        annual_cooling_hours = 1000

        # Annual kWh = (BTU * hours) / (SEER * 1000)
        annual_kwh = (capacity_btu * annual_cooling_hours) / (seer * 1000)

        # Convert to kg CO2 (US grid average: ~0.42 kg CO2/kWh)
        carbon_kg = annual_kwh * 0.42

        return round(carbon_kg, 2)

    def _estimate_upgrade_savings(
        self,
        equipment: EquipmentData,
        mandates: Dict
    ) -> Dict:
        """Estimate savings from upgrading to compliant equipment."""
        if not equipment.seer2_rating and not equipment.seer_rating:
            return {"kwh": 0, "carbon_kg": 0}

        current_seer = equipment.seer2_rating or equipment.seer_rating
        target_seer = 20.0  # High-efficiency target
        capacity_btu = (equipment.capacity_tons or 3) * 12000
        annual_cooling_hours = 1000

        # Current consumption
        current_kwh = (capacity_btu * annual_cooling_hours) / (current_seer * 1000)

        # Target consumption
        target_kwh = (capacity_btu * annual_cooling_hours) / (target_seer * 1000)

        savings_kwh = current_kwh - target_kwh
        savings_carbon = savings_kwh * 0.42

        return {
            "kwh": round(savings_kwh, 2),
            "carbon_kg": round(savings_carbon, 2)
        }

    def _determine_urgency(self, risk_score: int, violations: List[str]) -> str:
        """Determine urgency level."""
        if risk_score >= 50 or any("CRITICAL" in v or "BANNED" in v for v in violations):
            return "critical"
        elif risk_score >= 30 or any("Mandatory" in v for v in violations):
            return "high"
        elif risk_score >= 15:
            return "medium"
        return "low"


# LangGraph node function wrapper
def equipment_triage_node(state: Dict) -> Dict:
    """LangGraph node function for equipment triage."""
    import asyncio

    node = EquipmentTriageNode(state)

    # Get image from state
    image_url = state.get("equipment_photo_url")
    equipment_data = state.get("manual_equipment_data")

    # Run async in sync context
    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(
            node.execute(image_url=image_url, equipment_data=equipment_data)
        )
        return result
    finally:
        loop.close()
