"""
ProofGreen HVAC Compliance Logic
EPA 608/SEER2 compliance and A2L refrigerant transition verification

Handles:
- EPA 2026 Refrigerant Mandates (GWP < 700)
- SEER2 Efficiency Standards
- EPA Section 608 Certification
- A2L Refrigerant Safety Requirements
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, date
from enum import Enum

import sys
sys.path.append('..')
from config.settings import get_climate_region, get_seer2_minimum


class RefrigerantClass(Enum):
    """Refrigerant safety classifications per ASHRAE 34."""
    A1 = "A1"  # Lower toxicity, no flame propagation (R-410A, R-22)
    A2L = "A2L"  # Lower toxicity, lower flammability (R-454B, R-32)
    A2 = "A2"  # Lower toxicity, flammable (R-152a)
    A3 = "A3"  # Lower toxicity, higher flammability (R-290)
    B1 = "B1"  # Higher toxicity, no flame propagation
    B2L = "B2L"  # Higher toxicity, lower flammability


@dataclass
class Refrigerant:
    """Refrigerant properties and compliance data."""
    name: str
    gwp: int  # Global Warming Potential (100-year)
    classification: RefrigerantClass
    ozone_depleting: bool
    epa_2026_compliant: bool
    phase_out_date: Optional[date]
    replacement_options: List[str]


@dataclass
class HVACEquipment:
    """HVAC equipment specifications."""
    model_number: str
    manufacturer: str
    equipment_type: str  # ac, heat_pump, furnace, etc.
    tonnage: float
    seer: Optional[float]
    seer2: Optional[float]
    hspf: Optional[float]
    hspf2: Optional[float]
    afue: Optional[float]
    refrigerant_type: Optional[str]
    refrigerant_charge_oz: Optional[float]
    install_date: Optional[date]


@dataclass
class ComplianceCheckResult:
    """Result of a single compliance check."""
    check_name: str
    passed: bool
    requirement: str
    actual_value: str
    gap: Optional[str]
    recommendation: Optional[str]
    deadline: Optional[str]
    reference: str


class HVACComplianceChecker:
    """
    HVAC Compliance Checker for EPA and DOE standards.

    Verifies compliance with:
    1. EPA AIM Act - Refrigerant GWP limits (2026)
    2. DOE SEER2 Standards (2023+)
    3. EPA Section 608 - Refrigerant handling
    4. ASHRAE 15 - A2L Safety Requirements
    """

    # Refrigerant Database
    REFRIGERANTS = {
        "R-410A": Refrigerant(
            name="R-410A",
            gwp=2088,
            classification=RefrigerantClass.A1,
            ozone_depleting=False,
            epa_2026_compliant=False,
            phase_out_date=date(2026, 1, 1),
            replacement_options=["R-454B", "R-32"]
        ),
        "R-22": Refrigerant(
            name="R-22",
            gwp=1810,
            classification=RefrigerantClass.A1,
            ozone_depleting=True,
            epa_2026_compliant=False,
            phase_out_date=date(2020, 1, 1),
            replacement_options=["R-410A", "R-454B"]
        ),
        "R-454B": Refrigerant(
            name="R-454B",
            gwp=466,
            classification=RefrigerantClass.A2L,
            ozone_depleting=False,
            epa_2026_compliant=True,
            phase_out_date=None,
            replacement_options=[]
        ),
        "R-32": Refrigerant(
            name="R-32",
            gwp=675,
            classification=RefrigerantClass.A2L,
            ozone_depleting=False,
            epa_2026_compliant=True,
            phase_out_date=None,
            replacement_options=[]
        ),
        "R-290": Refrigerant(
            name="R-290",
            gwp=3,
            classification=RefrigerantClass.A3,
            ozone_depleting=False,
            epa_2026_compliant=True,
            phase_out_date=None,
            replacement_options=[]
        ),
        "R-407C": Refrigerant(
            name="R-407C",
            gwp=1774,
            classification=RefrigerantClass.A1,
            ozone_depleting=False,
            epa_2026_compliant=False,
            phase_out_date=date(2026, 1, 1),
            replacement_options=["R-454B", "R-32"]
        ),
        "R-134a": Refrigerant(
            name="R-134a",
            gwp=1430,
            classification=RefrigerantClass.A1,
            ozone_depleting=False,
            epa_2026_compliant=False,
            phase_out_date=date(2026, 1, 1),
            replacement_options=["R-1234yf"]
        )
    }

    # SEER2 Requirements by Region (effective 2023-01-01)
    SEER2_REQUIREMENTS = {
        "north": {
            "ac_split": 13.4,
            "ac_packaged": 13.4,
            "heat_pump_split": 14.3,
            "heat_pump_packaged": 13.4
        },
        "south": {
            "ac_split": 14.3,
            "ac_packaged": 13.4,
            "heat_pump_split": 14.3,
            "heat_pump_packaged": 13.4
        },
        "southwest": {
            "ac_split": 14.3,
            "ac_packaged": 13.4,
            "heat_pump_split": 14.3,
            "heat_pump_packaged": 13.4
        }
    }

    # HSPF2 Requirements
    HSPF2_REQUIREMENTS = {
        "north": 7.5,
        "south": 7.5,
        "southwest": 7.5
    }

    # AFUE Requirements (Furnaces)
    AFUE_REQUIREMENTS = {
        "non_weatherized_gas": 0.80,
        "weatherized_gas": 0.81,
        "mobile_home": 0.80
    }

    # EPA 2026 GWP Limit
    EPA_2026_GWP_LIMIT = 700

    def __init__(self):
        self.today = date.today()

    def check_compliance(self, job_data: dict, state_code: str) -> dict:
        """
        Run all HVAC compliance checks.

        Args:
            job_data: Job details including equipment
            state_code: State abbreviation

        Returns:
            Dictionary with compliance results and gaps
        """
        equipment = job_data.get("equipment", {})
        technician = job_data.get("technician", {})

        checks = {}
        gaps = []

        # 1. EPA 2026 Refrigerant Check
        refrigerant_result = self._check_refrigerant_compliance(equipment)
        checks["epa_2026_refrigerant"] = refrigerant_result.passed
        if not refrigerant_result.passed and refrigerant_result.gap:
            gaps.append(refrigerant_result.gap)

        # 2. SEER2 Efficiency Check
        seer2_result = self._check_seer2_compliance(equipment, state_code)
        checks["seer2_efficiency"] = seer2_result.passed
        if not seer2_result.passed and seer2_result.gap:
            gaps.append(seer2_result.gap)

        # 3. HSPF2 Check (Heat Pumps)
        if self._is_heat_pump(equipment):
            hspf2_result = self._check_hspf2_compliance(equipment, state_code)
            checks["hspf2_efficiency"] = hspf2_result.passed
            if not hspf2_result.passed and hspf2_result.gap:
                gaps.append(hspf2_result.gap)

        # 4. AFUE Check (Furnaces)
        if self._is_furnace(equipment):
            afue_result = self._check_afue_compliance(equipment)
            checks["afue_efficiency"] = afue_result.passed
            if not afue_result.passed and afue_result.gap:
                gaps.append(afue_result.gap)

        # 5. EPA 608 Certification Check
        epa608_result = self._check_epa_608_certification(technician)
        checks["epa_608_certified"] = epa608_result.passed
        if not epa608_result.passed and epa608_result.gap:
            gaps.append(epa608_result.gap)

        # 6. A2L Safety Requirements (if applicable)
        if self._requires_a2l_safety(equipment):
            a2l_result = self._check_a2l_safety_requirements(job_data)
            checks["a2l_safety_compliant"] = a2l_result.passed
            if not a2l_result.passed and a2l_result.gap:
                gaps.append(a2l_result.gap)

        # 7. Recovery Requirement Check
        recovery_result = self._check_recovery_compliance(job_data)
        checks["refrigerant_recovery"] = recovery_result.passed
        if not recovery_result.passed and recovery_result.gap:
            gaps.append(recovery_result.gap)

        return {
            "vertical": "hvac",
            "state_code": state_code,
            "overall_compliant": len(gaps) == 0,
            "checks": checks,
            "gaps": gaps,
            "timestamp": datetime.utcnow().isoformat()
        }

    def _check_refrigerant_compliance(self, equipment: dict) -> ComplianceCheckResult:
        """Check EPA 2026 refrigerant GWP compliance."""
        refrigerant_type = equipment.get("refrigerant_type", "").upper().replace("-", "")

        # Normalize refrigerant name
        normalized = f"R-{refrigerant_type.replace('R', '')}" if refrigerant_type else None

        if not normalized or normalized not in self.REFRIGERANTS:
            return ComplianceCheckResult(
                check_name="EPA 2026 Refrigerant",
                passed=True,  # No refrigerant specified
                requirement=f"GWP < {self.EPA_2026_GWP_LIMIT}",
                actual_value="Not specified",
                gap=None,
                recommendation=None,
                deadline=None,
                reference="EPA AIM Act Final Rule"
            )

        refrigerant = self.REFRIGERANTS[normalized]

        if refrigerant.epa_2026_compliant:
            return ComplianceCheckResult(
                check_name="EPA 2026 Refrigerant",
                passed=True,
                requirement=f"GWP < {self.EPA_2026_GWP_LIMIT}",
                actual_value=f"{normalized} (GWP: {refrigerant.gwp})",
                gap=None,
                recommendation=None,
                deadline=None,
                reference="EPA AIM Act Final Rule"
            )
        else:
            replacements = ", ".join(refrigerant.replacement_options)
            return ComplianceCheckResult(
                check_name="EPA 2026 Refrigerant",
                passed=False,
                requirement=f"GWP < {self.EPA_2026_GWP_LIMIT}",
                actual_value=f"{normalized} (GWP: {refrigerant.gwp})",
                gap=f"Refrigerant {normalized} (GWP {refrigerant.gwp}) exceeds EPA 2026 limit of {self.EPA_2026_GWP_LIMIT}",
                recommendation=f"Transition to compliant refrigerant: {replacements}",
                deadline="2026-01-01",
                reference="EPA AIM Act Final Rule"
            )

    def _check_seer2_compliance(self, equipment: dict, state_code: str) -> ComplianceCheckResult:
        """Check SEER2 efficiency compliance."""
        seer2 = equipment.get("seer2") or equipment.get("seer")
        equipment_type = equipment.get("type", "ac_split").lower()

        if not seer2:
            return ComplianceCheckResult(
                check_name="SEER2 Efficiency",
                passed=True,
                requirement="SEER2 rating required",
                actual_value="Not specified",
                gap=None,
                recommendation="Verify equipment SEER2 rating meets regional requirements",
                deadline=None,
                reference="DOE Energy Conservation Standards"
            )

        region = get_climate_region(state_code)

        # Determine equipment category
        if "heat_pump" in equipment_type:
            category = "heat_pump_split" if "packaged" not in equipment_type else "heat_pump_packaged"
        else:
            category = "ac_split" if "packaged" not in equipment_type else "ac_packaged"

        min_seer2 = self.SEER2_REQUIREMENTS[region].get(category, 14.3)

        if seer2 >= min_seer2:
            return ComplianceCheckResult(
                check_name="SEER2 Efficiency",
                passed=True,
                requirement=f"SEER2 >= {min_seer2} ({region} region)",
                actual_value=f"SEER2 {seer2}",
                gap=None,
                recommendation=None,
                deadline=None,
                reference="DOE Energy Conservation Standards"
            )
        else:
            return ComplianceCheckResult(
                check_name="SEER2 Efficiency",
                passed=False,
                requirement=f"SEER2 >= {min_seer2} ({region} region)",
                actual_value=f"SEER2 {seer2}",
                gap=f"SEER2 {seer2} below minimum {min_seer2} for {region} region",
                recommendation=f"Upgrade to equipment with SEER2 {min_seer2}+ rating",
                deadline="Immediate for new installations",
                reference="DOE Energy Conservation Standards"
            )

    def _check_hspf2_compliance(self, equipment: dict, state_code: str) -> ComplianceCheckResult:
        """Check HSPF2 (heating efficiency) compliance for heat pumps."""
        hspf2 = equipment.get("hspf2") or equipment.get("hspf")

        if not hspf2:
            return ComplianceCheckResult(
                check_name="HSPF2 Efficiency",
                passed=True,
                requirement="HSPF2 rating required for heat pumps",
                actual_value="Not specified",
                gap=None,
                recommendation="Verify equipment HSPF2 rating",
                deadline=None,
                reference="DOE Energy Conservation Standards"
            )

        region = get_climate_region(state_code)
        min_hspf2 = self.HSPF2_REQUIREMENTS.get(region, 7.5)

        if hspf2 >= min_hspf2:
            return ComplianceCheckResult(
                check_name="HSPF2 Efficiency",
                passed=True,
                requirement=f"HSPF2 >= {min_hspf2}",
                actual_value=f"HSPF2 {hspf2}",
                gap=None,
                recommendation=None,
                deadline=None,
                reference="DOE Energy Conservation Standards"
            )
        else:
            return ComplianceCheckResult(
                check_name="HSPF2 Efficiency",
                passed=False,
                requirement=f"HSPF2 >= {min_hspf2}",
                actual_value=f"HSPF2 {hspf2}",
                gap=f"HSPF2 {hspf2} below minimum {min_hspf2}",
                recommendation=f"Upgrade to heat pump with HSPF2 {min_hspf2}+ rating",
                deadline="Immediate for new installations",
                reference="DOE Energy Conservation Standards"
            )

    def _check_afue_compliance(self, equipment: dict) -> ComplianceCheckResult:
        """Check AFUE (furnace efficiency) compliance."""
        afue = equipment.get("afue")

        if not afue:
            return ComplianceCheckResult(
                check_name="AFUE Efficiency",
                passed=True,
                requirement="AFUE rating required for furnaces",
                actual_value="Not specified",
                gap=None,
                recommendation="Verify furnace AFUE rating",
                deadline=None,
                reference="DOE Energy Conservation Standards"
            )

        min_afue = self.AFUE_REQUIREMENTS.get("non_weatherized_gas", 0.80)

        if afue >= min_afue:
            return ComplianceCheckResult(
                check_name="AFUE Efficiency",
                passed=True,
                requirement=f"AFUE >= {min_afue * 100}%",
                actual_value=f"AFUE {afue * 100 if afue <= 1 else afue}%",
                gap=None,
                recommendation=None,
                deadline=None,
                reference="DOE Energy Conservation Standards"
            )
        else:
            return ComplianceCheckResult(
                check_name="AFUE Efficiency",
                passed=False,
                requirement=f"AFUE >= {min_afue * 100}%",
                actual_value=f"AFUE {afue * 100 if afue <= 1 else afue}%",
                gap=f"AFUE {afue * 100 if afue <= 1 else afue}% below minimum {min_afue * 100}%",
                recommendation="Upgrade to furnace with 95%+ AFUE for best efficiency",
                deadline="Immediate for new installations",
                reference="DOE Energy Conservation Standards"
            )

    def _check_epa_608_certification(self, technician: dict) -> ComplianceCheckResult:
        """Check technician EPA 608 certification."""
        is_certified = technician.get("epa_608_certified", False)
        cert_type = technician.get("epa_608_type", "")

        if is_certified:
            return ComplianceCheckResult(
                check_name="EPA 608 Certification",
                passed=True,
                requirement="EPA 608 certification required for refrigerant handling",
                actual_value=f"Certified ({cert_type})" if cert_type else "Certified",
                gap=None,
                recommendation=None,
                deadline=None,
                reference="EPA Section 608"
            )
        else:
            return ComplianceCheckResult(
                check_name="EPA 608 Certification",
                passed=False,
                requirement="EPA 608 certification required for refrigerant handling",
                actual_value="Not certified or not verified",
                gap="Technician must have valid EPA 608 certification for refrigerant work",
                recommendation="Obtain EPA 608 Universal certification",
                deadline="Before performing refrigerant work",
                reference="EPA Section 608"
            )

    def _check_a2l_safety_requirements(self, job_data: dict) -> ComplianceCheckResult:
        """Check A2L refrigerant safety requirements."""
        equipment = job_data.get("equipment", {})
        a2l_training = job_data.get("technician", {}).get("a2l_trained", False)
        leak_detection = job_data.get("has_leak_detection", False)

        issues = []

        if not a2l_training:
            issues.append("A2L refrigerant handling training required")

        if not leak_detection:
            issues.append("Refrigerant leak detection system recommended")

        if not issues:
            return ComplianceCheckResult(
                check_name="A2L Safety Requirements",
                passed=True,
                requirement="A2L handling training and safety equipment",
                actual_value="Training verified, safety equipment present",
                gap=None,
                recommendation=None,
                deadline=None,
                reference="ASHRAE 15, UL 60335-2-40"
            )
        else:
            return ComplianceCheckResult(
                check_name="A2L Safety Requirements",
                passed=False,
                requirement="A2L handling training and safety equipment",
                actual_value=", ".join(issues),
                gap="; ".join(issues),
                recommendation="Complete A2L refrigerant training; Install leak detection",
                deadline="Before working with A2L refrigerants",
                reference="ASHRAE 15, UL 60335-2-40"
            )

    def _check_recovery_compliance(self, job_data: dict) -> ComplianceCheckResult:
        """Check refrigerant recovery compliance."""
        recovered_oz = job_data.get("refrigerant_recovered_oz", 0)
        removed_oz = job_data.get("refrigerant_removed_oz", 0)

        if removed_oz == 0:
            return ComplianceCheckResult(
                check_name="Refrigerant Recovery",
                passed=True,
                requirement="90% minimum recovery rate",
                actual_value="No refrigerant removed",
                gap=None,
                recommendation=None,
                deadline=None,
                reference="EPA Section 608"
            )

        recovery_rate = (recovered_oz / removed_oz) * 100 if removed_oz > 0 else 100

        if recovery_rate >= 90:
            return ComplianceCheckResult(
                check_name="Refrigerant Recovery",
                passed=True,
                requirement="90% minimum recovery rate",
                actual_value=f"{recovery_rate:.1f}% recovered ({recovered_oz}oz of {removed_oz}oz)",
                gap=None,
                recommendation=None,
                deadline=None,
                reference="EPA Section 608"
            )
        else:
            return ComplianceCheckResult(
                check_name="Refrigerant Recovery",
                passed=False,
                requirement="90% minimum recovery rate",
                actual_value=f"{recovery_rate:.1f}% recovered",
                gap=f"Recovery rate {recovery_rate:.1f}% below 90% EPA requirement",
                recommendation="Improve recovery procedures; Document all recovered refrigerant",
                deadline="Immediate",
                reference="EPA Section 608"
            )

    def _is_heat_pump(self, equipment: dict) -> bool:
        """Check if equipment is a heat pump."""
        equipment_type = str(equipment.get("type", "")).lower()
        return "heat_pump" in equipment_type or "heat pump" in equipment_type

    def _is_furnace(self, equipment: dict) -> bool:
        """Check if equipment is a furnace."""
        equipment_type = str(equipment.get("type", "")).lower()
        return "furnace" in equipment_type

    def _requires_a2l_safety(self, equipment: dict) -> bool:
        """Check if A2L safety requirements apply."""
        refrigerant_type = equipment.get("refrigerant_type", "").upper().replace("-", "")
        normalized = f"R-{refrigerant_type.replace('R', '')}" if refrigerant_type else None

        if normalized and normalized in self.REFRIGERANTS:
            return self.REFRIGERANTS[normalized].classification == RefrigerantClass.A2L

        return False

    def get_refrigerant_info(self, refrigerant_name: str) -> Optional[Refrigerant]:
        """Get detailed information about a refrigerant."""
        normalized = f"R-{refrigerant_name.upper().replace('R', '').replace('-', '')}"
        return self.REFRIGERANTS.get(normalized)

    def get_compliant_refrigerants(self) -> List[str]:
        """Get list of EPA 2026 compliant refrigerants."""
        return [
            name for name, ref in self.REFRIGERANTS.items()
            if ref.epa_2026_compliant
        ]


# Export checker instance
hvac_checker = HVACComplianceChecker()


def check_hvac_compliance(job_data: dict, state_code: str) -> dict:
    """Public function to check HVAC compliance."""
    return hvac_checker.check_compliance(job_data, state_code)
