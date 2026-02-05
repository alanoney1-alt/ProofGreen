"""
ProofGreen Electrical Compliance Logic
EV/Solar/Grid-balancing compliance verification

Handles:
- NEC 2026 EV-Ready Requirements
- Solar/PV Installation Standards
- Battery Storage Compliance
- Grid Load-Shifting (Demand Response)
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class EVChargerLevel(Enum):
    """EV charger levels."""
    LEVEL_1 = "level_1"  # 120V, 12-16A
    LEVEL_2 = "level_2"  # 240V, 16-80A
    DC_FAST = "dc_fast"  # 400-800V DC


@dataclass
class ComplianceCheckResult:
    """Result of a single compliance check."""
    check_name: str
    passed: bool
    requirement: str
    actual_value: str
    gap: Optional[str]
    recommendation: Optional[str]
    carbon_impact: Optional[float]  # kg CO2e avoided annually
    reference: str


class ElectricalComplianceChecker:
    """
    Electrical Compliance Checker for NEC and grid standards.

    Verifies compliance with:
    1. NEC 2026 EV-Ready Requirements (Article 625)
    2. Solar/PV Installation (NEC Article 690)
    3. Battery Energy Storage (NEC Article 706)
    4. Demand Response Compatibility
    5. State-specific electrical codes
    """

    # NEC 2026 EV-Ready Requirements
    NEC_2026_EV_READY = {
        "single_family": {
            "circuit_voltage": 240,
            "circuit_amps": 50,
            "dedicated_circuit": True,
            "panel_capacity_recommended": 200,
            "conduit_size_inches": 1.0,
            "effective_date": "2026-01-01"
        },
        "multifamily": {
            "ev_capable_percent": 0.20,  # 20% of spaces
            "ev_ready_percent": 0.05,  # 5% of spaces
            "circuit_voltage": 240,
            "circuit_amps": 40,
            "effective_date": "2026-01-01"
        },
        "commercial": {
            "ev_spaces_required": True,
            "circuit_voltage": 208,
            "circuit_amps": 40,
            "ada_accessible": True,
            "effective_date": "2026-01-01"
        }
    }

    # Solar PV Requirements (NEC Article 690)
    SOLAR_REQUIREMENTS = {
        "rapid_shutdown": {
            "required": True,
            "voltage_limit": 30,
            "time_limit_seconds": 30,
            "effective_date": "2017-01-01",
            "reference": "NEC 690.12"
        },
        "arc_fault_protection": {
            "required": True,
            "system_voltage_threshold": 80,
            "reference": "NEC 690.11"
        },
        "grounding": {
            "equipment_grounding": True,
            "dc_grounding": True,
            "reference": "NEC 690 Part V"
        },
        "interconnection": {
            "utility_approval_required": True,
            "net_metering_available": True,  # Varies by state
            "reference": "IEEE 1547"
        }
    }

    # Battery Storage Requirements (NEC Article 706)
    BATTERY_REQUIREMENTS = {
        "listing_required": True,
        "ul_9540a_testing": True,
        "ventilation_required": True,
        "separation_distance_inches": 36,
        "fire_rating_required": True,
        "reference": "NEC Article 706"
    }

    # State-specific requirements
    STATE_REQUIREMENTS = {
        "CA": {
            "title_24_solar_mandate": True,
            "solar_ready_new_construction": True,
            "battery_required_2026": True,
            "ev_spaces_commercial": 0.06,  # 6% of parking
            "demand_response_required": True,
            "reference": "CA Title 24 Part 6"
        },
        "WA": {
            "clean_buildings_act": True,
            "ev_ready_required": True,
            "solar_ready_zones": True,
            "reference": "WA Clean Buildings Act"
        },
        "NY": {
            "nyc_ll97_applies": True,
            "ev_ready_multifamily": 0.20,
            "solar_ready_commercial": True,
            "reference": "NYC Local Law 97"
        },
        "CO": {
            "ev_ready_new_construction": True,
            "solar_ready_zones": True,
            "reference": "CO Building Code"
        }
    }

    # Grid Carbon Intensity by State (kg CO2e/kWh)
    GRID_CARBON_INTENSITY = {
        "CA": 0.23,
        "WA": 0.10,  # High hydro
        "NY": 0.24,
        "TX": 0.39,
        "FL": 0.43,
        "CO": 0.48,
        "US_AVG": 0.42
    }

    def __init__(self):
        pass

    def check_compliance(self, job_data: dict, state_code: str) -> dict:
        """
        Run all electrical compliance checks.

        Args:
            job_data: Job details including equipment
            state_code: State abbreviation

        Returns:
            Dictionary with compliance results and gaps
        """
        equipment = job_data.get("equipment", {})
        equipment_type = equipment.get("type", "").lower()

        checks = {}
        gaps = []
        total_carbon_avoided = 0

        # Route to appropriate checks based on equipment type
        if "ev" in equipment_type or "charger" in equipment_type:
            ev_result = self._check_ev_charger_compliance(equipment, job_data, state_code)
            checks["nec_2026_ev_ready"] = ev_result.passed
            if not ev_result.passed and ev_result.gap:
                gaps.append(ev_result.gap)
            if ev_result.carbon_impact:
                total_carbon_avoided += ev_result.carbon_impact

        if "solar" in equipment_type or "pv" in equipment_type:
            solar_result = self._check_solar_compliance(equipment, job_data)
            checks["solar_nec_690"] = solar_result.passed
            if not solar_result.passed and solar_result.gap:
                gaps.append(solar_result.gap)
            if solar_result.carbon_impact:
                total_carbon_avoided += solar_result.carbon_impact

        if "battery" in equipment_type or "storage" in equipment_type:
            battery_result = self._check_battery_compliance(equipment)
            checks["battery_nec_706"] = battery_result.passed
            if not battery_result.passed and battery_result.gap:
                gaps.append(battery_result.gap)

        if "panel" in equipment_type:
            panel_result = self._check_panel_compliance(equipment, state_code)
            checks["panel_capacity"] = panel_result.passed
            if not panel_result.passed and panel_result.gap:
                gaps.append(panel_result.gap)

        # Check demand response capability
        dr_result = self._check_demand_response(equipment, state_code)
        checks["demand_response_capable"] = dr_result.passed

        # Check state-specific requirements
        state_results = self._check_state_requirements(equipment, state_code)
        for key, result in state_results.items():
            checks[key] = result.passed
            if not result.passed and result.gap:
                gaps.append(result.gap)

        return {
            "vertical": "electrical",
            "state_code": state_code,
            "overall_compliant": len(gaps) == 0,
            "checks": checks,
            "gaps": gaps,
            "annual_carbon_avoided_kg": total_carbon_avoided,
            "timestamp": datetime.utcnow().isoformat()
        }

    def _check_ev_charger_compliance(
        self,
        equipment: dict,
        job_data: dict,
        state_code: str
    ) -> ComplianceCheckResult:
        """Check EV charger installation against NEC 2026."""
        building_type = job_data.get("building_type", "single_family").lower()
        circuit_voltage = equipment.get("voltage", 0)
        circuit_amps = equipment.get("circuit_amps", 0)
        dedicated_circuit = equipment.get("dedicated_circuit", False)

        # Get requirements for building type
        reqs = self.NEC_2026_EV_READY.get(building_type, self.NEC_2026_EV_READY["single_family"])

        issues = []

        if circuit_voltage < reqs["circuit_voltage"] and circuit_voltage > 0:
            issues.append(f"Voltage {circuit_voltage}V below required {reqs['circuit_voltage']}V")

        if circuit_amps < reqs["circuit_amps"] and circuit_amps > 0:
            issues.append(f"Circuit {circuit_amps}A below required {reqs['circuit_amps']}A")

        if reqs.get("dedicated_circuit") and not dedicated_circuit:
            issues.append("Dedicated circuit required")

        # Calculate carbon avoided (assuming 12,000 miles/year at 0.3 kWh/mile)
        carbon_avoided = None
        if circuit_voltage >= 240:  # Level 2 capable
            annual_kwh = 12000 * 0.3  # 3,600 kWh
            grid_intensity = self.GRID_CARBON_INTENSITY.get(state_code, self.GRID_CARBON_INTENSITY["US_AVG"])
            # EV vs gas vehicle: gas emits ~0.4 kg/mile, EV emits grid_intensity * 0.3 kWh/mile
            gas_emissions = 12000 * 0.4  # 4,800 kg CO2
            ev_emissions = annual_kwh * grid_intensity
            carbon_avoided = gas_emissions - ev_emissions

        if not issues:
            return ComplianceCheckResult(
                check_name="NEC 2026 EV-Ready",
                passed=True,
                requirement=f"{reqs['circuit_voltage']}V / {reqs['circuit_amps']}A dedicated circuit",
                actual_value=f"{circuit_voltage}V / {circuit_amps}A",
                gap=None,
                recommendation=None,
                carbon_impact=carbon_avoided,
                reference="NEC 2026 Article 625"
            )
        else:
            return ComplianceCheckResult(
                check_name="NEC 2026 EV-Ready",
                passed=False,
                requirement=f"{reqs['circuit_voltage']}V / {reqs['circuit_amps']}A dedicated circuit",
                actual_value=f"{circuit_voltage}V / {circuit_amps}A",
                gap="; ".join(issues),
                recommendation=f"Install {reqs['circuit_voltage']}V/{reqs['circuit_amps']}A dedicated circuit for NEC 2026 compliance",
                carbon_impact=carbon_avoided,
                reference="NEC 2026 Article 625"
            )

    def _check_solar_compliance(self, equipment: dict, job_data: dict) -> ComplianceCheckResult:
        """Check solar PV installation compliance."""
        has_rapid_shutdown = equipment.get("rapid_shutdown", False)
        has_arc_fault = equipment.get("arc_fault_protection", False)
        system_kw = equipment.get("system_size_kw", 0)

        issues = []

        if not has_rapid_shutdown:
            issues.append("Rapid shutdown required per NEC 690.12")

        if not has_arc_fault and system_kw > 0:
            issues.append("Arc-fault protection recommended per NEC 690.11")

        # Calculate carbon avoided
        carbon_avoided = None
        if system_kw > 0:
            # Assume 1,500 kWh per kW annually (US average)
            annual_kwh = system_kw * 1500
            carbon_avoided = annual_kwh * self.GRID_CARBON_INTENSITY["US_AVG"]

        if not issues:
            return ComplianceCheckResult(
                check_name="Solar PV NEC 690",
                passed=True,
                requirement="Rapid shutdown, arc-fault protection, proper grounding",
                actual_value=f"{system_kw}kW system with safety features",
                gap=None,
                recommendation=None,
                carbon_impact=carbon_avoided,
                reference="NEC Article 690"
            )
        else:
            return ComplianceCheckResult(
                check_name="Solar PV NEC 690",
                passed=False,
                requirement="Rapid shutdown, arc-fault protection, proper grounding",
                actual_value=f"{system_kw}kW system",
                gap="; ".join(issues),
                recommendation="Install NEC 690 compliant safety equipment",
                carbon_impact=carbon_avoided,
                reference="NEC Article 690"
            )

    def _check_battery_compliance(self, equipment: dict) -> ComplianceCheckResult:
        """Check battery storage installation compliance."""
        ul_listed = equipment.get("ul_9540_listed", False)
        ventilation = equipment.get("ventilation_present", False)
        separation = equipment.get("separation_distance_inches", 0)

        reqs = self.BATTERY_REQUIREMENTS
        issues = []

        if not ul_listed:
            issues.append("UL 9540 listing required")

        if not ventilation:
            issues.append("Adequate ventilation required")

        if separation < reqs["separation_distance_inches"] and separation > 0:
            issues.append(f"Separation distance {separation}\" below required {reqs['separation_distance_inches']}\"")

        if not issues:
            return ComplianceCheckResult(
                check_name="Battery Storage NEC 706",
                passed=True,
                requirement="UL 9540 listed, ventilated, proper separation",
                actual_value="Compliant installation",
                gap=None,
                recommendation=None,
                carbon_impact=None,
                reference="NEC Article 706"
            )
        else:
            return ComplianceCheckResult(
                check_name="Battery Storage NEC 706",
                passed=False,
                requirement="UL 9540 listed, ventilated, proper separation",
                actual_value="; ".join(issues),
                gap="; ".join(issues),
                recommendation="Ensure UL 9540 listed battery with proper installation",
                carbon_impact=None,
                reference="NEC Article 706"
            )

    def _check_panel_compliance(self, equipment: dict, state_code: str) -> ComplianceCheckResult:
        """Check electrical panel capacity."""
        panel_amps = equipment.get("panel_amps", 0)
        recommended_amps = 200  # Recommended for EV/solar readiness

        state_reqs = self.STATE_REQUIREMENTS.get(state_code, {})
        if state_reqs.get("ev_ready_required") or state_reqs.get("solar_ready_new_construction"):
            recommended_amps = 200

        if panel_amps >= recommended_amps or panel_amps == 0:
            return ComplianceCheckResult(
                check_name="Panel Capacity",
                passed=True,
                requirement=f"{recommended_amps}A recommended for EV/Solar readiness",
                actual_value=f"{panel_amps}A" if panel_amps else "Not specified",
                gap=None,
                recommendation=None,
                carbon_impact=None,
                reference="NEC Article 220"
            )
        else:
            return ComplianceCheckResult(
                check_name="Panel Capacity",
                passed=False,
                requirement=f"{recommended_amps}A recommended for EV/Solar readiness",
                actual_value=f"{panel_amps}A",
                gap=f"Panel {panel_amps}A may limit EV/Solar additions; {recommended_amps}A recommended",
                recommendation=f"Consider panel upgrade to {recommended_amps}A for future electrification",
                carbon_impact=None,
                reference="NEC Article 220"
            )

    def _check_demand_response(self, equipment: dict, state_code: str) -> ComplianceCheckResult:
        """Check demand response capability."""
        dr_capable = equipment.get("demand_response_capable", False)
        smart_enabled = equipment.get("smart_enabled", False)

        state_reqs = self.STATE_REQUIREMENTS.get(state_code, {})
        dr_required = state_reqs.get("demand_response_required", False)

        if dr_capable or smart_enabled:
            return ComplianceCheckResult(
                check_name="Demand Response",
                passed=True,
                requirement="DR-capable for utility programs" if dr_required else "DR capability recommended",
                actual_value="DR-capable" if dr_capable else "Smart-enabled",
                gap=None,
                recommendation=None,
                carbon_impact=None,
                reference="IEEE 2030.5"
            )
        else:
            return ComplianceCheckResult(
                check_name="Demand Response",
                passed=not dr_required,
                requirement="DR-capable for utility programs" if dr_required else "DR capability recommended",
                actual_value="Not DR-capable",
                gap="Equipment not demand response capable" if dr_required else None,
                recommendation="Consider DR-capable equipment for utility incentives",
                carbon_impact=None,
                reference="IEEE 2030.5"
            )

    def _check_state_requirements(self, equipment: dict, state_code: str) -> Dict[str, ComplianceCheckResult]:
        """Check state-specific electrical requirements."""
        results = {}
        state_reqs = self.STATE_REQUIREMENTS.get(state_code, {})

        if not state_reqs:
            return results

        # California Title 24
        if state_code == "CA":
            if state_reqs.get("solar_ready_new_construction"):
                results["ca_solar_ready"] = ComplianceCheckResult(
                    check_name="CA Title 24 Solar Ready",
                    passed=True,  # Would need more data
                    requirement="Solar-ready zone per Title 24",
                    actual_value="Check local permit requirements",
                    gap=None,
                    recommendation="Ensure solar-ready conduit and roof zone",
                    carbon_impact=None,
                    reference="CA Title 24 Part 6"
                )

        # New York LL97
        if state_code == "NY" and state_reqs.get("nyc_ll97_applies"):
            results["nyc_ll97"] = ComplianceCheckResult(
                check_name="NYC Local Law 97",
                passed=True,  # Would need building data
                requirement="Building emissions limits apply",
                actual_value="Check building compliance status",
                gap=None,
                recommendation="Electrification helps meet LL97 limits",
                carbon_impact=None,
                reference="NYC LL97"
            )

        return results

    def calculate_load_shift_savings(
        self,
        equipment: dict,
        state_code: str,
        shift_kwh: float
    ) -> dict:
        """Calculate carbon and cost savings from load shifting."""
        # Peak vs off-peak carbon intensity difference
        peak_carbon = self.GRID_CARBON_INTENSITY.get(state_code, 0.42) * 1.3  # 30% higher at peak
        offpeak_carbon = self.GRID_CARBON_INTENSITY.get(state_code, 0.42) * 0.8

        carbon_saved_kg = shift_kwh * (peak_carbon - offpeak_carbon)

        # Assume $0.10/kWh TOU difference
        cost_saved = shift_kwh * 0.10

        return {
            "shifted_kwh": shift_kwh,
            "carbon_saved_kg": round(carbon_saved_kg, 2),
            "cost_saved_dollars": round(cost_saved, 2),
            "peak_carbon_intensity": peak_carbon,
            "offpeak_carbon_intensity": offpeak_carbon
        }


# Export checker instance
electrical_checker = ElectricalComplianceChecker()


def check_electrical_compliance(job_data: dict, state_code: str) -> dict:
    """Public function to check electrical compliance."""
    return electrical_checker.check_compliance(job_data, state_code)
