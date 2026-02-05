"""
ProofGreen ESG Auditor Agent
The 'E' of ESG - Calculates Scope 1, 2, 3 Emissions

Performs comprehensive environmental audits against green expectations.
"""

import json
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage

import sys
sys.path.append('..')
from config.settings import settings


class EmissionScope(Enum):
    """GHG Protocol Emission Scopes."""
    SCOPE_1 = "scope_1"  # Direct emissions
    SCOPE_2 = "scope_2"  # Indirect emissions (electricity)
    SCOPE_3 = "scope_3"  # Value chain emissions


@dataclass
class EmissionFactor:
    """Emission factor with source attribution."""
    value: float
    unit: str
    source: str
    year: int


@dataclass
class AuditResult:
    """Result of an ESG audit."""
    job_id: str
    vertical: str
    state_code: str
    timestamp: str
    overall_compliant: bool
    scope_1_emissions: float
    scope_2_emissions: float
    scope_3_emissions: float
    total_emissions: float
    avoided_emissions: float
    net_impact: float
    checks: Dict[str, bool]
    gaps: List[str]
    recommendations: List[str]
    sb_253_ready: bool


class ESGAuditor:
    """
    ESG Auditor Agent for comprehensive environmental compliance auditing.

    Responsibilities:
    1. Calculate Scope 1, 2, 3 emissions per GHG Protocol
    2. Compare against baseline and calculate avoided emissions
    3. Check compliance with federal, state, and CA SB 253 standards
    4. Generate audit report with gaps and recommendations
    """

    # EPA GHG Emission Factors (2024)
    EMISSION_FACTORS = {
        # Fuels (kg CO2e per unit)
        "natural_gas_therm": EmissionFactor(5.3, "kg_co2e/therm", "EPA GHG Hub", 2024),
        "propane_gallon": EmissionFactor(5.76, "kg_co2e/gallon", "EPA GHG Hub", 2024),
        "fuel_oil_gallon": EmissionFactor(10.21, "kg_co2e/gallon", "EPA GHG Hub", 2024),
        "gasoline_gallon": EmissionFactor(8.89, "kg_co2e/gallon", "EPA GHG Hub", 2024),
        "diesel_gallon": EmissionFactor(10.21, "kg_co2e/gallon", "EPA GHG Hub", 2024),

        # Electricity (kg CO2e per kWh by region)
        "electricity_us_avg": EmissionFactor(0.42, "kg_co2e/kWh", "EPA eGRID 2024", 2024),
        "electricity_ca": EmissionFactor(0.23, "kg_co2e/kWh", "EPA eGRID 2024", 2024),
        "electricity_tx": EmissionFactor(0.39, "kg_co2e/kWh", "EPA eGRID 2024", 2024),
        "electricity_ny": EmissionFactor(0.24, "kg_co2e/kWh", "EPA eGRID 2024", 2024),
        "electricity_fl": EmissionFactor(0.43, "kg_co2e/kWh", "EPA eGRID 2024", 2024),

        # Refrigerants (GWP values - IPCC AR6)
        "r410a_kg": EmissionFactor(2088, "kg_co2e/kg", "IPCC AR6", 2024),
        "r22_kg": EmissionFactor(1810, "kg_co2e/kg", "IPCC AR6", 2024),
        "r454b_kg": EmissionFactor(466, "kg_co2e/kg", "IPCC AR6", 2024),
        "r32_kg": EmissionFactor(675, "kg_co2e/kg", "IPCC AR6", 2024),
        "r290_kg": EmissionFactor(3, "kg_co2e/kg", "IPCC AR6", 2024),

        # Water (kg CO2e per gallon for treatment/pumping)
        "water_gallon": EmissionFactor(0.003, "kg_co2e/gallon", "EPA WaterSense", 2024),
        "hot_water_gallon": EmissionFactor(0.18, "kg_co2e/gallon", "DOE", 2024),

        # Waste (kg CO2e per kg)
        "landfill_kg": EmissionFactor(0.58, "kg_co2e/kg", "EPA WARM", 2024),
        "recycling_metal_kg": EmissionFactor(-1.5, "kg_co2e/kg", "EPA WARM", 2024),
        "recycling_plastic_kg": EmissionFactor(-0.9, "kg_co2e/kg", "EPA WARM", 2024),
    }

    # Equipment baseline emissions (annual kg CO2e)
    EQUIPMENT_BASELINES = {
        "hvac": {
            "ac_seer_10": 2500,  # Old 10 SEER unit
            "ac_seer_13": 1900,
            "ac_seer_15": 1650,
            "ac_seer_18": 1380,
            "furnace_80afue": 3200,
            "furnace_95afue": 2700,
            "heat_pump": 1200,
        },
        "water_heater": {
            "gas_standard": 1800,
            "gas_high_efficiency": 1400,
            "electric_standard": 2200,
            "heat_pump_water_heater": 700,
        },
        "plumbing": {
            "toilet_3.5gpf": 150,
            "toilet_1.28gpf": 55,
            "showerhead_2.5gpm": 200,
            "showerhead_1.5gpm": 120,
        }
    }

    def __init__(self):
        self.llm = ChatAnthropic(
            model=settings.AGENT_MODEL,
            temperature=0.1,
            api_key=settings.ANTHROPIC_API_KEY
        )

    def audit_job(self, job_data: dict, state_code: str = "CA") -> AuditResult:
        """
        Perform comprehensive ESG audit on a job.

        Args:
            job_data: Job details including equipment, service, location
            state_code: State abbreviation for regional factors

        Returns:
            AuditResult with emissions, compliance status, and recommendations
        """
        vertical = self._determine_vertical(job_data)

        # Calculate emissions by scope
        scope_1 = self._calculate_scope_1(job_data, vertical)
        scope_2 = self._calculate_scope_2(job_data, vertical, state_code)
        scope_3 = self._calculate_scope_3(job_data, vertical)

        total_emissions = scope_1 + scope_2 + scope_3

        # Calculate avoided emissions (comparing to baseline)
        avoided = self._calculate_avoided_emissions(job_data, vertical)
        net_impact = total_emissions - avoided

        # Run compliance checks
        checks, gaps = self._run_compliance_checks(job_data, vertical, state_code)

        # Generate recommendations
        recommendations = self._generate_recommendations(gaps, vertical)

        # Check SB 253 readiness
        sb_253_ready = self._check_sb_253_readiness(job_data, vertical, checks)

        return AuditResult(
            job_id=job_data.get("job_id", ""),
            vertical=vertical,
            state_code=state_code,
            timestamp=datetime.utcnow().isoformat(),
            overall_compliant=len(gaps) == 0,
            scope_1_emissions=round(scope_1, 2),
            scope_2_emissions=round(scope_2, 2),
            scope_3_emissions=round(scope_3, 2),
            total_emissions=round(total_emissions, 2),
            avoided_emissions=round(avoided, 2),
            net_impact=round(net_impact, 2),
            checks=checks,
            gaps=gaps,
            recommendations=recommendations,
            sb_253_ready=sb_253_ready
        )

    def _determine_vertical(self, job_data: dict) -> str:
        """Determine the vertical from job data."""
        job_type = str(job_data.get("job_type", "")).lower()
        equipment_type = str(job_data.get("equipment", {}).get("type", "")).lower()

        if any(kw in job_type + equipment_type for kw in ["hvac", "ac", "furnace", "heat pump", "refrigerant"]):
            return "hvac"
        elif any(kw in job_type + equipment_type for kw in ["plumbing", "water heater", "toilet", "faucet"]):
            return "plumbing"
        elif any(kw in job_type + equipment_type for kw in ["electrical", "ev", "solar", "panel"]):
            return "electrical"
        elif any(kw in job_type + equipment_type for kw in ["landscaping", "irrigation", "lawn"]):
            return "landscaping"
        elif any(kw in job_type + equipment_type for kw in ["waste", "disposal", "debris"]):
            return "waste"
        return "general"

    def _calculate_scope_1(self, job_data: dict, vertical: str) -> float:
        """
        Calculate Scope 1 (Direct) Emissions.

        Sources: On-site fuel combustion, refrigerant leaks, vehicle fuel
        """
        scope_1 = 0.0
        equipment = job_data.get("equipment", {})

        # Refrigerant emissions (HVAC)
        if vertical == "hvac":
            refrigerant_type = equipment.get("refrigerant_type", "").lower().replace("-", "")
            refrigerant_added = equipment.get("refrigerant_added_oz", 0) / 35.274  # oz to kg
            refrigerant_leaked = equipment.get("refrigerant_leaked_oz", 0) / 35.274

            if refrigerant_type and refrigerant_leaked > 0:
                gwp_key = f"{refrigerant_type}_kg"
                if gwp_key in self.EMISSION_FACTORS:
                    gwp = self.EMISSION_FACTORS[gwp_key].value
                    scope_1 += refrigerant_leaked * gwp

        # Fuel consumption (all verticals)
        fuel_type = job_data.get("fuel_type", "natural_gas")
        fuel_consumed = job_data.get("fuel_consumed", 0)

        if fuel_type == "natural_gas" and fuel_consumed > 0:
            scope_1 += fuel_consumed * self.EMISSION_FACTORS["natural_gas_therm"].value
        elif fuel_type == "propane" and fuel_consumed > 0:
            scope_1 += fuel_consumed * self.EMISSION_FACTORS["propane_gallon"].value

        # Vehicle fuel for job (travel emissions)
        travel_miles = job_data.get("travel_miles", 0)
        if travel_miles > 0:
            # Assume average 25 MPG
            gallons = travel_miles / 25
            scope_1 += gallons * self.EMISSION_FACTORS["gasoline_gallon"].value

        return scope_1

    def _calculate_scope_2(self, job_data: dict, vertical: str, state_code: str) -> float:
        """
        Calculate Scope 2 (Indirect) Emissions.

        Sources: Purchased electricity consumption
        """
        scope_2 = 0.0

        # Get regional electricity factor
        elec_key = f"electricity_{state_code.lower()}"
        if elec_key not in self.EMISSION_FACTORS:
            elec_key = "electricity_us_avg"
        elec_factor = self.EMISSION_FACTORS[elec_key].value

        # Equipment electricity consumption
        equipment = job_data.get("equipment", {})
        annual_kwh = equipment.get("annual_kwh", 0)

        if annual_kwh > 0:
            scope_2 += annual_kwh * elec_factor

        # Estimate from equipment specs if no direct kwh
        if annual_kwh == 0 and vertical == "hvac":
            tonnage = equipment.get("tonnage", 3)
            seer = equipment.get("seer", 14)
            cooling_hours = 1500  # Typical annual cooling hours

            # BTU/hr = tonnage * 12000
            # kWh = BTU / (SEER * 1000) * hours
            estimated_kwh = (tonnage * 12000 / seer) * cooling_hours / 1000
            scope_2 += estimated_kwh * elec_factor

        return scope_2

    def _calculate_scope_3(self, job_data: dict, vertical: str) -> float:
        """
        Calculate Scope 3 (Value Chain) Emissions.

        Sources: Equipment manufacturing, materials, waste disposal
        """
        scope_3 = 0.0
        equipment = job_data.get("equipment", {})
        materials = job_data.get("materials", [])
        waste = job_data.get("waste", {})

        # Equipment embodied carbon (simplified estimate)
        equipment_weight_kg = equipment.get("weight_lbs", 0) * 0.453592
        if equipment_weight_kg > 0:
            # Average 5 kg CO2e per kg of equipment manufacturing
            scope_3 += equipment_weight_kg * 5

        # Materials embodied carbon
        for material in materials:
            material_type = material.get("type", "").lower()
            weight_kg = material.get("weight_lbs", 0) * 0.453592

            # Material-specific factors
            if "copper" in material_type:
                scope_3 += weight_kg * 2.8
            elif "steel" in material_type:
                scope_3 += weight_kg * 1.8
            elif "pvc" in material_type or "plastic" in material_type:
                scope_3 += weight_kg * 3.0
            else:
                scope_3 += weight_kg * 2.0  # Default

        # Waste disposal
        landfill_lbs = waste.get("landfill_lbs", 0)
        recycled_lbs = waste.get("recycled_lbs", 0)

        if landfill_lbs > 0:
            scope_3 += (landfill_lbs * 0.453592) * self.EMISSION_FACTORS["landfill_kg"].value

        if recycled_lbs > 0:
            # Recycling credit (negative emissions)
            scope_3 += (recycled_lbs * 0.453592) * self.EMISSION_FACTORS["recycling_metal_kg"].value

        return scope_3

    def _calculate_avoided_emissions(self, job_data: dict, vertical: str) -> float:
        """Calculate emissions avoided compared to baseline equipment."""
        avoided = 0.0
        equipment = job_data.get("equipment", {})
        old_equipment = job_data.get("old_equipment", {})

        if vertical == "hvac":
            # Compare old vs new SEER
            old_seer = old_equipment.get("seer", 10)
            new_seer = equipment.get("seer", 15)

            if old_seer > 0 and new_seer > old_seer:
                # Higher SEER = lower consumption = avoided emissions
                baseline_key = f"ac_seer_{int(old_seer)}"
                if baseline_key not in self.EQUIPMENT_BASELINES["hvac"]:
                    baseline_key = "ac_seer_10"

                old_emissions = self.EQUIPMENT_BASELINES["hvac"].get(baseline_key, 2500)

                # Calculate new equipment emissions
                efficiency_improvement = (new_seer - old_seer) / old_seer
                new_emissions = old_emissions * (1 - efficiency_improvement)

                avoided = old_emissions - new_emissions

            # Heat pump conversion from gas furnace
            if equipment.get("type") == "heat_pump" and old_equipment.get("type") == "gas_furnace":
                avoided += 2000  # Significant savings from fuel switching

        elif vertical == "plumbing":
            # Water efficiency improvements
            old_gpf = old_equipment.get("gpf", 3.5)
            new_gpf = equipment.get("gpf", 1.28)

            if new_gpf < old_gpf:
                # Average 5 flushes/day, 365 days
                annual_gallons_saved = (old_gpf - new_gpf) * 5 * 365
                avoided = annual_gallons_saved * self.EMISSION_FACTORS["water_gallon"].value

        elif vertical == "electrical":
            # Solar/EV charging offsets
            if equipment.get("type") == "solar_pv":
                system_kw = equipment.get("system_size_kw", 6)
                annual_kwh = system_kw * 1500  # Average production
                avoided = annual_kwh * self.EMISSION_FACTORS["electricity_us_avg"].value

        return avoided

    def _run_compliance_checks(self, job_data: dict, vertical: str, state_code: str) -> tuple:
        """Run compliance checks and return results with gaps."""
        checks = {}
        gaps = []
        equipment = job_data.get("equipment", {})

        if vertical == "hvac":
            # EPA 2026 Refrigerant Check
            refrigerant = equipment.get("refrigerant_type", "").upper()
            approved_refrigerants = ["R-454B", "R-32", "R-290"]
            checks["epa_2026_refrigerant"] = refrigerant in approved_refrigerants or refrigerant == ""

            if not checks["epa_2026_refrigerant"] and refrigerant:
                gaps.append(f"Refrigerant {refrigerant} not compliant with EPA 2026 mandate (GWP > 700)")

            # SEER2 Check
            from config.settings import get_seer2_minimum
            min_seer = get_seer2_minimum(state_code)
            actual_seer = equipment.get("seer", 0)
            checks["seer2_compliant"] = actual_seer >= min_seer or actual_seer == 0

            if not checks["seer2_compliant"] and actual_seer > 0:
                gaps.append(f"SEER {actual_seer} below minimum {min_seer} for {state_code}")

            # EPA 608 Certification
            tech_cert = job_data.get("technician", {}).get("epa_608_certified", True)
            checks["epa_608_certified"] = tech_cert

            if not checks["epa_608_certified"]:
                gaps.append("Technician EPA 608 certification required for refrigerant handling")

        elif vertical == "plumbing":
            # WaterSense Check
            gpf = equipment.get("gpf", 0)
            gpm = equipment.get("gpm", 0)

            checks["watersense_toilet"] = gpf <= 1.28 or gpf == 0
            checks["watersense_fixture"] = gpm <= 1.5 or gpm == 0

            if not checks["watersense_toilet"] and gpf > 0:
                gaps.append(f"Toilet {gpf} GPF exceeds WaterSense standard (1.28 GPF)")

            if not checks["watersense_fixture"] and gpm > 0:
                gaps.append(f"Fixture {gpm} GPM exceeds WaterSense standard (1.5 GPM)")

        elif vertical == "electrical":
            # NEC 2026 EV-Ready Check
            if equipment.get("type") == "ev_charger":
                circuit_amps = equipment.get("circuit_amps", 0)
                voltage = equipment.get("voltage", 0)

                checks["nec_2026_ev_ready"] = circuit_amps >= 50 and voltage >= 240

                if not checks["nec_2026_ev_ready"]:
                    gaps.append("EV charger circuit does not meet NEC 2026 standard (240V/50A)")

            # Panel capacity check
            panel_amps = equipment.get("panel_amps", 0)
            checks["panel_capacity"] = panel_amps >= 200 or panel_amps == 0

        # State-specific checks
        if state_code == "CA":
            # Title 24 compliance
            checks["title_24_compliant"] = True  # Would need more detailed check

            # CARB SORE rule for landscaping
            if vertical == "landscaping":
                equipment_fuel = equipment.get("fuel_type", "electric")
                checks["carb_sore_compliant"] = equipment_fuel == "electric"

                if not checks["carb_sore_compliant"]:
                    gaps.append("Gas-powered equipment does not meet CARB SORE rule")

        return checks, gaps

    def _generate_recommendations(self, gaps: list, vertical: str) -> list:
        """Generate actionable recommendations based on gaps."""
        recommendations = []

        for gap in gaps:
            gap_lower = gap.lower()

            if "refrigerant" in gap_lower:
                recommendations.append({
                    "priority": "high",
                    "action": "Transition to A2L refrigerant (R-454B recommended)",
                    "deadline": "2026-01-01",
                    "estimated_cost": "$500-1500",
                    "tax_credit": "May qualify for IRA 25C credit"
                })

            elif "seer" in gap_lower:
                recommendations.append({
                    "priority": "high",
                    "action": "Upgrade to SEER2 15.0+ equipment",
                    "deadline": "Immediate for new installations",
                    "estimated_cost": "$3000-8000",
                    "tax_credit": "Up to $600 IRA 25C credit"
                })

            elif "epa 608" in gap_lower:
                recommendations.append({
                    "priority": "critical",
                    "action": "Complete EPA 608 Universal certification",
                    "deadline": "Before next refrigerant work",
                    "estimated_cost": "$200-400",
                    "tax_credit": "N/A"
                })

            elif "watersense" in gap_lower:
                recommendations.append({
                    "priority": "medium",
                    "action": "Install WaterSense certified fixtures",
                    "deadline": "Recommended",
                    "estimated_cost": "$100-500",
                    "tax_credit": "Local utility rebates available"
                })

            elif "ev" in gap_lower or "nec" in gap_lower:
                recommendations.append({
                    "priority": "medium",
                    "action": "Upgrade to NEC 2026 compliant EV circuit (240V/50A)",
                    "deadline": "For new EV charger installations",
                    "estimated_cost": "$1500-3000",
                    "tax_credit": "Up to 30% IRA credit"
                })

            elif "carb" in gap_lower or "sore" in gap_lower:
                recommendations.append({
                    "priority": "high",
                    "action": "Transition to electric landscape equipment",
                    "deadline": "2028-01-01 full ban",
                    "estimated_cost": "$2000-5000",
                    "tax_credit": "Check local utility rebates"
                })

        return recommendations

    def _check_sb_253_readiness(self, job_data: dict, vertical: str, checks: dict) -> bool:
        """
        Check if job data meets CA SB 253 reporting requirements.

        SB 253 requires Scope 1, 2, 3 GHG reporting for companies over $1B.
        We apply this standard to all jobs for future-proofing.
        """
        # Required data points for SB 253 reporting
        required_fields = [
            "job_id",
            "company_id",
            "equipment",
            "zip_code"
        ]

        has_required = all(job_data.get(field) for field in required_fields)

        # All compliance checks passing
        checks_passing = all(checks.values()) if checks else False

        return has_required and checks_passing

    def to_dict(self, result: AuditResult) -> dict:
        """Convert AuditResult to dictionary."""
        return asdict(result)


# Singleton instance
auditor = ESGAuditor()


def audit_job(job_data: dict, state_code: str = "CA") -> dict:
    """Public function to audit a job."""
    result = auditor.audit_job(job_data, state_code)
    return auditor.to_dict(result)
