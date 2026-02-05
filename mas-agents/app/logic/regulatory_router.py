"""
Regulatory Router - Routes compliance checks based on jurisdiction and vertical
Defaults to CA SB 253 for future-proofing nationwide
"""

import json
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class ReportingStandard(str, Enum):
    """Supported reporting standards."""
    CA_SB_253 = "CA_SB_253"  # California Climate Corporate Data Accountability Act
    CA_SB_261 = "CA_SB_261"  # California Climate-Related Financial Risk Act
    SEC_CLIMATE = "SEC_CLIMATE"  # SEC Climate Disclosure Rules
    EPA_GHG = "EPA_GHG"  # EPA Greenhouse Gas Reporting Program
    GRI = "GRI"  # Global Reporting Initiative
    TCFD = "TCFD"  # Task Force on Climate-related Financial Disclosures
    CDP = "CDP"  # Carbon Disclosure Project


@dataclass
class RegulatoryRequirement:
    """A specific regulatory requirement."""
    id: str
    name: str
    regulation: str
    jurisdiction: str  # federal, state code, or local
    vertical: str
    category: str
    description: str
    threshold: Optional[Dict[str, Any]] = None
    effective_date: Optional[datetime] = None
    enforcement_date: Optional[datetime] = None
    penalty: Optional[str] = None
    sources: List[str] = field(default_factory=list)


@dataclass
class ComplianceRoute:
    """Route to specific compliance checks."""
    requirements: List[RegulatoryRequirement]
    reporting_standard: ReportingStandard
    state_overrides: Dict[str, Any]
    future_proof_requirements: List[RegulatoryRequirement]


class RegulatoryRouter:
    """
    Routes compliance checks based on location, vertical, and equipment type.
    Defaults to CA SB 253 requirements for future-proofing all businesses.
    """

    def __init__(self, knowledge_path: Optional[str] = None):
        """Initialize with regulatory knowledge base."""
        self.knowledge_path = knowledge_path or str(
            Path(__file__).parent.parent.parent / "config" / "regulatory_knowledge.json"
        )
        self._load_knowledge()

    def _load_knowledge(self):
        """Load regulatory knowledge from JSON."""
        try:
            with open(self.knowledge_path, "r") as f:
                self.knowledge = json.load(f)
        except FileNotFoundError:
            logger.warning(f"Knowledge file not found: {self.knowledge_path}")
            self.knowledge = self._get_default_knowledge()

    def _get_default_knowledge(self) -> Dict[str, Any]:
        """Return default knowledge if file not found."""
        return {
            "nationwide_standards": {
                "hvac": {
                    "epa_2026_refrigerant": {
                        "name": "EPA AIM Act Refrigerant Phase-down",
                        "effective_date": "2026-01-01",
                        "requirement": "Residential/commercial AC must use refrigerants with GWP < 700",
                        "approved_refrigerants": ["R-454B", "R-32", "R-290"],
                        "prohibited_refrigerants": ["R-410A", "R-22"],
                        "penalty": "Significant fines for non-compliance"
                    }
                }
            },
            "state_overrides": {
                "CA": {
                    "sb_253": {
                        "name": "Climate Corporate Data Accountability Act",
                        "effective_date": "2026-01-01",
                        "requirement": "Companies with >$1B revenue must report Scope 1, 2, 3 emissions",
                        "threshold_revenue": 1000000000
                    }
                }
            }
        }

    def get_applicable_regulations(
        self,
        state: str,
        vertical: str,
        equipment_type: Optional[str] = None,
        reporting_standard: str = "CA_SB_253"
    ) -> ComplianceRoute:
        """
        Get all applicable regulations for a given context.

        Args:
            state: Two-letter state code
            vertical: Service vertical (hvac, plumbing, electrical, landscaping)
            equipment_type: Specific equipment type (optional)
            reporting_standard: Reporting standard to use (default: CA_SB_253)

        Returns:
            ComplianceRoute with all applicable requirements
        """

        requirements = []
        future_proof = []
        state_overrides = {}

        # 1. Get nationwide standards for the vertical
        vertical_standards = self.knowledge.get("nationwide_standards", {}).get(vertical, {})
        for reg_id, reg_data in vertical_standards.items():
            req = self._create_requirement(reg_id, reg_data, "federal", vertical)
            if self._is_currently_effective(req):
                requirements.append(req)
            else:
                future_proof.append(req)

        # 2. Get state-specific overrides
        state_data = self.knowledge.get("state_overrides", {}).get(state.upper(), {})
        state_overrides = state_data

        for reg_id, reg_data in state_data.items():
            # Skip non-regulation keys
            if not isinstance(reg_data, dict) or "name" not in reg_data:
                continue

            req = self._create_requirement(reg_id, reg_data, state, vertical)
            if self._is_currently_effective(req):
                requirements.append(req)
            else:
                future_proof.append(req)

        # 3. Always include CA SB 253 requirements for future-proofing
        # Even if not in California, prepare for nationwide adoption
        if reporting_standard == "CA_SB_253":
            sb253_req = self._get_sb253_requirements(vertical)
            # Add as future-proof if company doesn't meet revenue threshold
            future_proof.extend(sb253_req)

        # 4. Get equipment-specific requirements
        if equipment_type:
            equipment_reqs = self._get_equipment_requirements(
                vertical, equipment_type, state
            )
            requirements.extend(equipment_reqs)

        return ComplianceRoute(
            requirements=requirements,
            reporting_standard=ReportingStandard(reporting_standard),
            state_overrides=state_overrides,
            future_proof_requirements=future_proof
        )

    def _create_requirement(
        self,
        reg_id: str,
        reg_data: Dict[str, Any],
        jurisdiction: str,
        vertical: str
    ) -> RegulatoryRequirement:
        """Create a RegulatoryRequirement from data."""
        effective_date = None
        if reg_data.get("effective_date"):
            try:
                effective_date = datetime.fromisoformat(reg_data["effective_date"])
            except (ValueError, TypeError):
                pass

        return RegulatoryRequirement(
            id=reg_id,
            name=reg_data.get("name", reg_id),
            regulation=reg_data.get("regulation", reg_id),
            jurisdiction=jurisdiction,
            vertical=vertical,
            category=reg_data.get("category", "general"),
            description=reg_data.get("requirement", reg_data.get("description", "")),
            threshold=reg_data.get("threshold") or reg_data.get("requirements"),
            effective_date=effective_date,
            penalty=reg_data.get("penalty"),
            sources=reg_data.get("sources", [])
        )

    def _is_currently_effective(self, req: RegulatoryRequirement) -> bool:
        """Check if requirement is currently in effect."""
        if not req.effective_date:
            return True
        return datetime.now() >= req.effective_date

    def _get_sb253_requirements(self, vertical: str) -> List[RegulatoryRequirement]:
        """Get CA SB 253 requirements for future-proofing."""
        return [
            RegulatoryRequirement(
                id="sb253_scope1",
                name="SB 253 Scope 1 Reporting",
                regulation="CA SB 253",
                jurisdiction="CA",
                vertical=vertical,
                category="ghg_reporting",
                description="Track and report direct emissions (fuel combustion, refrigerant leaks)",
                threshold={"revenue_threshold": 1000000000},
                effective_date=datetime(2026, 1, 1),
                sources=["California Climate Corporate Data Accountability Act"]
            ),
            RegulatoryRequirement(
                id="sb253_scope2",
                name="SB 253 Scope 2 Reporting",
                regulation="CA SB 253",
                jurisdiction="CA",
                vertical=vertical,
                category="ghg_reporting",
                description="Track and report indirect emissions from purchased electricity",
                threshold={"revenue_threshold": 1000000000},
                effective_date=datetime(2026, 1, 1),
                sources=["California Climate Corporate Data Accountability Act"]
            ),
            RegulatoryRequirement(
                id="sb253_scope3",
                name="SB 253 Scope 3 Reporting",
                regulation="CA SB 253",
                jurisdiction="CA",
                vertical=vertical,
                category="ghg_reporting",
                description="Track and report value chain emissions (materials, waste, transport)",
                threshold={"revenue_threshold": 500000000},
                effective_date=datetime(2027, 1, 1),
                sources=["California Climate Corporate Data Accountability Act"]
            )
        ]

    def _get_equipment_requirements(
        self,
        vertical: str,
        equipment_type: str,
        state: str
    ) -> List[RegulatoryRequirement]:
        """Get equipment-specific requirements."""
        requirements = []

        # HVAC equipment requirements
        if vertical == "hvac":
            if "air_conditioner" in equipment_type.lower() or "heat_pump" in equipment_type.lower():
                requirements.append(RegulatoryRequirement(
                    id="seer2_efficiency",
                    name="SEER2 Efficiency Standard",
                    regulation="DOE Efficiency Standards",
                    jurisdiction="federal",
                    vertical="hvac",
                    category="efficiency",
                    description=f"Minimum SEER2 rating required: {self._get_seer2_min(state)}",
                    threshold={"min_seer2": self._get_seer2_min(state)},
                    effective_date=datetime(2023, 1, 1),
                    sources=["DOE 10 CFR 430"]
                ))

            # Refrigerant requirements
            requirements.append(RegulatoryRequirement(
                id="epa_608_certification",
                name="EPA Section 608 Certification",
                regulation="Clean Air Act Section 608",
                jurisdiction="federal",
                vertical="hvac",
                category="certification",
                description="Technicians handling refrigerants must be EPA 608 certified",
                sources=["40 CFR Part 82"]
            ))

        # Plumbing equipment requirements
        elif vertical == "plumbing":
            if "water_heater" in equipment_type.lower():
                requirements.append(RegulatoryRequirement(
                    id="water_heater_uef",
                    name="Water Heater UEF Standard",
                    regulation="DOE Efficiency Standards",
                    jurisdiction="federal",
                    vertical="plumbing",
                    category="efficiency",
                    description="Minimum UEF (Uniform Energy Factor) required",
                    threshold={"min_uef": 0.93},
                    effective_date=datetime(2023, 4, 15),
                    sources=["DOE 10 CFR 430"]
                ))

            if "fixture" in equipment_type.lower() or "faucet" in equipment_type.lower():
                requirements.append(RegulatoryRequirement(
                    id="watersense_certification",
                    name="WaterSense Certification",
                    regulation="EPA WaterSense Program",
                    jurisdiction="federal",
                    vertical="plumbing",
                    category="efficiency",
                    description="Fixtures should meet WaterSense flow rate standards",
                    sources=["EPA WaterSense"]
                ))

        # Electrical equipment requirements
        elif vertical == "electrical":
            if "ev_charger" in equipment_type.lower():
                requirements.append(RegulatoryRequirement(
                    id="nec_ev_ready",
                    name="NEC EV-Ready Requirements",
                    regulation="NEC 2026",
                    jurisdiction="federal",
                    vertical="electrical",
                    category="infrastructure",
                    description="New construction requires EV-ready infrastructure (240V/50A dedicated circuit)",
                    effective_date=datetime(2026, 1, 1),
                    sources=["NFPA 70 (NEC)"]
                ))

            if "solar" in equipment_type.lower():
                requirements.append(RegulatoryRequirement(
                    id="nec_690_solar",
                    name="NEC 690 Solar PV Requirements",
                    regulation="NEC 690",
                    jurisdiction="federal",
                    vertical="electrical",
                    category="safety",
                    description="Solar PV systems must comply with rapid shutdown and arc-fault requirements",
                    sources=["NFPA 70 Article 690"]
                ))

        # Landscaping equipment requirements
        elif vertical == "landscaping":
            if state == "CA":
                requirements.append(RegulatoryRequirement(
                    id="carb_sore",
                    name="CARB SORE Rule",
                    regulation="CARB Small Off-Road Engine Regulation",
                    jurisdiction="CA",
                    vertical="landscaping",
                    category="emissions",
                    description="Phase-out of gas-powered lawn equipment; new sales banned 2024+",
                    effective_date=datetime(2024, 1, 1),
                    sources=["California Air Resources Board"]
                ))

        return requirements

    def _get_seer2_min(self, state: str) -> float:
        """Get minimum SEER2 requirement based on state/climate region."""
        north_states = [
            "AK", "CT", "ID", "IL", "IN", "IA", "KS", "ME", "MA", "MI", "MN",
            "MO", "MT", "NE", "NH", "NJ", "NY", "ND", "OH", "OR", "PA", "RI",
            "SD", "VT", "WA", "WI", "WY"
        ]
        if state.upper() in north_states:
            return 14.3
        return 15.0  # South and Southwest regions

    def check_compliance(
        self,
        state: str,
        vertical: str,
        equipment_data: Dict[str, Any],
        reporting_standard: str = "CA_SB_253"
    ) -> Dict[str, Any]:
        """
        Check compliance against applicable regulations.

        Returns:
            Dict with compliance status, issues, and recommendations
        """

        route = self.get_applicable_regulations(
            state=state,
            vertical=vertical,
            equipment_type=equipment_data.get("type"),
            reporting_standard=reporting_standard
        )

        issues = []
        warnings = []
        compliant_items = []

        for req in route.requirements:
            result = self._check_requirement(req, equipment_data, state)
            if result["status"] == "fail":
                issues.append({
                    "requirement_id": req.id,
                    "name": req.name,
                    "severity": "critical",
                    "description": result["message"],
                    "regulation": req.regulation,
                    "recommendation": result.get("recommendation", "")
                })
            elif result["status"] == "warning":
                warnings.append({
                    "requirement_id": req.id,
                    "name": req.name,
                    "severity": "warning",
                    "description": result["message"],
                    "regulation": req.regulation
                })
            else:
                compliant_items.append(req.id)

        # Add future-proof warnings
        future_alerts = []
        for req in route.future_proof_requirements:
            if req.effective_date:
                days_until = (req.effective_date - datetime.now()).days
                if 0 < days_until <= 365:
                    future_alerts.append({
                        "requirement_id": req.id,
                        "name": req.name,
                        "effective_date": req.effective_date.isoformat(),
                        "days_until_effective": days_until,
                        "description": req.description
                    })

        # Calculate compliance score
        total_checks = len(route.requirements)
        passed_checks = len(compliant_items)
        score = (passed_checks / total_checks * 100) if total_checks > 0 else 100

        status = "compliant"
        if issues:
            status = "non_compliant"
        elif warnings:
            status = "partial"

        return {
            "status": status,
            "score": round(score, 1),
            "issues": issues,
            "warnings": warnings,
            "compliant_items": compliant_items,
            "future_alerts": future_alerts,
            "reporting_standard": route.reporting_standard.value,
            "regulations_checked": [req.id for req in route.requirements],
            "state": state,
            "vertical": vertical
        }

    def _check_requirement(
        self,
        req: RegulatoryRequirement,
        equipment_data: Dict[str, Any],
        state: str
    ) -> Dict[str, Any]:
        """Check a single requirement against equipment data."""

        # SEER2 efficiency check
        if req.id == "seer2_efficiency":
            seer2 = equipment_data.get("seer2") or equipment_data.get("efficiency")
            min_seer2 = req.threshold.get("min_seer2", 14.3)
            if seer2 and seer2 < min_seer2:
                return {
                    "status": "fail",
                    "message": f"SEER2 rating {seer2} is below minimum {min_seer2} for {state}",
                    "recommendation": f"Install equipment with SEER2 >= {min_seer2}"
                }
            elif not seer2:
                return {
                    "status": "warning",
                    "message": "SEER2 rating not provided - cannot verify efficiency compliance"
                }

        # Refrigerant check
        if "refrigerant" in req.id.lower():
            refrigerant = equipment_data.get("refrigerant_type", "").upper()
            if refrigerant in ["R-410A", "R-22", "R410A", "R22"]:
                return {
                    "status": "fail" if req.id == "epa_2026_refrigerant" else "warning",
                    "message": f"Refrigerant {refrigerant} will be prohibited under EPA 2026 rules",
                    "recommendation": "Consider equipment using R-454B or R-32 refrigerants"
                }

        # Water heater UEF check
        if req.id == "water_heater_uef":
            uef = equipment_data.get("uef") or equipment_data.get("efficiency")
            min_uef = req.threshold.get("min_uef", 0.93)
            if uef and uef < min_uef:
                return {
                    "status": "fail",
                    "message": f"UEF {uef} is below minimum {min_uef}",
                    "recommendation": f"Install water heater with UEF >= {min_uef}"
                }

        # Default: pass
        return {"status": "pass", "message": "Compliant"}

    def get_vertical_checklist(
        self,
        vertical: str,
        state: str
    ) -> List[Dict[str, Any]]:
        """Get compliance checklist for a vertical."""
        route = self.get_applicable_regulations(state, vertical)

        checklist = []
        for req in route.requirements:
            checklist.append({
                "id": req.id,
                "name": req.name,
                "category": req.category,
                "description": req.description,
                "jurisdiction": req.jurisdiction,
                "required": True
            })

        for req in route.future_proof_requirements:
            checklist.append({
                "id": req.id,
                "name": req.name,
                "category": req.category,
                "description": req.description,
                "jurisdiction": req.jurisdiction,
                "required": False,
                "effective_date": req.effective_date.isoformat() if req.effective_date else None,
                "future_proof": True
            })

        return checklist


# Convenience function
def get_compliance_requirements(
    state: str,
    vertical: str,
    equipment_type: Optional[str] = None
) -> Dict[str, Any]:
    """Quick access to get compliance requirements."""
    router = RegulatoryRouter()
    route = router.get_applicable_regulations(state, vertical, equipment_type)

    return {
        "current_requirements": [
            {
                "id": r.id,
                "name": r.name,
                "description": r.description,
                "regulation": r.regulation
            }
            for r in route.requirements
        ],
        "future_requirements": [
            {
                "id": r.id,
                "name": r.name,
                "description": r.description,
                "effective_date": r.effective_date.isoformat() if r.effective_date else None
            }
            for r in route.future_proof_requirements
        ],
        "state_overrides": route.state_overrides,
        "reporting_standard": route.reporting_standard.value
    }
