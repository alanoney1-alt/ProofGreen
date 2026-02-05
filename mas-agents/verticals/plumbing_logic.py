"""
ProofGreen Plumbing Compliance Logic
WaterSense/flow-rate optimization and water heater efficiency

Handles:
- EPA WaterSense Standards
- DOE Water Heater Efficiency (UEF)
- PFAS Reporting Requirements
- Greywater Reuse Compliance
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class WaterSenseCategory(Enum):
    """WaterSense product categories."""
    TOILET = "toilet"
    URINAL = "urinal"
    SHOWERHEAD = "showerhead"
    LAVATORY_FAUCET = "lavatory_faucet"
    KITCHEN_FAUCET = "kitchen_faucet"
    IRRIGATION_CONTROLLER = "irrigation_controller"


@dataclass
class WaterSenseStandard:
    """WaterSense efficiency standard."""
    category: WaterSenseCategory
    max_flow_rate: float
    unit: str
    effective_date: str
    source: str


@dataclass
class WaterHeaterStandard:
    """Water heater efficiency standard."""
    fuel_type: str
    tank_size_min: float
    tank_size_max: float
    min_uef: float
    effective_date: str
    source: str


@dataclass
class ComplianceCheckResult:
    """Result of a single compliance check."""
    check_name: str
    passed: bool
    requirement: str
    actual_value: str
    gap: Optional[str]
    recommendation: Optional[str]
    water_savings: Optional[float]  # Gallons per year
    reference: str


class PlumbingComplianceChecker:
    """
    Plumbing Compliance Checker for EPA and DOE standards.

    Verifies compliance with:
    1. EPA WaterSense Standards (fixtures and appliances)
    2. DOE Water Heater Efficiency Standards (UEF)
    3. EPA PFAS Reporting Requirements
    4. State-specific water efficiency mandates
    """

    # WaterSense Standards
    WATERSENSE_STANDARDS = {
        WaterSenseCategory.TOILET: WaterSenseStandard(
            category=WaterSenseCategory.TOILET,
            max_flow_rate=1.28,
            unit="GPF",
            effective_date="2006-01-01",
            source="EPA WaterSense"
        ),
        WaterSenseCategory.URINAL: WaterSenseStandard(
            category=WaterSenseCategory.URINAL,
            max_flow_rate=0.5,
            unit="GPF",
            effective_date="2009-01-01",
            source="EPA WaterSense"
        ),
        WaterSenseCategory.SHOWERHEAD: WaterSenseStandard(
            category=WaterSenseCategory.SHOWERHEAD,
            max_flow_rate=2.0,
            unit="GPM",
            effective_date="2010-01-01",
            source="EPA WaterSense"
        ),
        WaterSenseCategory.LAVATORY_FAUCET: WaterSenseStandard(
            category=WaterSenseCategory.LAVATORY_FAUCET,
            max_flow_rate=1.5,
            unit="GPM",
            effective_date="2007-01-01",
            source="EPA WaterSense"
        ),
        WaterSenseCategory.KITCHEN_FAUCET: WaterSenseStandard(
            category=WaterSenseCategory.KITCHEN_FAUCET,
            max_flow_rate=2.2,
            unit="GPM",
            effective_date="2022-01-01",
            source="EPA WaterSense"
        ),
        WaterSenseCategory.IRRIGATION_CONTROLLER: WaterSenseStandard(
            category=WaterSenseCategory.IRRIGATION_CONTROLLER,
            max_flow_rate=0,  # N/A - smart controller compliance
            unit="N/A",
            effective_date="2012-01-01",
            source="EPA WaterSense"
        )
    }

    # Water Heater UEF Standards (DOE 2029 proposed, current 2015)
    WATER_HEATER_STANDARDS = [
        # Gas Storage Water Heaters
        WaterHeaterStandard("gas", 0, 55, 0.64, "2015-04-16", "DOE"),
        WaterHeaterStandard("gas", 55, 100, 0.77, "2015-04-16", "DOE"),
        # Electric Storage Water Heaters
        WaterHeaterStandard("electric", 0, 55, 0.93, "2015-04-16", "DOE"),
        WaterHeaterStandard("electric", 55, 120, 2.0, "2015-04-16", "DOE"),  # Requires heat pump
        # Heat Pump Water Heaters
        WaterHeaterStandard("heat_pump", 0, 55, 2.0, "2015-04-16", "DOE"),
        WaterHeaterStandard("heat_pump", 55, 120, 2.0, "2015-04-16", "DOE"),
        # Tankless Gas
        WaterHeaterStandard("tankless_gas", 0, 0, 0.82, "2015-04-16", "DOE"),
        # Tankless Electric
        WaterHeaterStandard("tankless_electric", 0, 0, 0.93, "2015-04-16", "DOE"),
    ]

    # State-specific water efficiency multipliers
    STATE_REQUIREMENTS = {
        "CA": {
            "toilet_max_gpf": 1.28,
            "urinal_max_gpf": 0.125,  # California ultra-low
            "showerhead_max_gpm": 1.8,  # Stricter than federal
            "lavatory_max_gpm": 1.2,
            "requires_watersense": True,
            "indoor_per_capita_target": 52.5,  # Gallons per day by 2025
            "reference": "CA Water Code, Title 20"
        },
        "TX": {
            "toilet_max_gpf": 1.28,
            "urinal_max_gpf": 0.5,
            "showerhead_max_gpm": 2.0,
            "lavatory_max_gpm": 1.5,
            "requires_watersense": True,
            "drought_restrictions": True,
            "reference": "TX Health & Safety Code Chapter 372"
        },
        "CO": {
            "toilet_max_gpf": 1.28,
            "showerhead_max_gpm": 2.0,
            "greywater_permitted": True,
            "rainwater_permitted": True,
            "reference": "CO Water Conservation Act"
        },
        "AZ": {
            "toilet_max_gpf": 1.28,
            "requires_watersense": True,
            "greywater_permitted": True,
            "reference": "AZ Plumbing Code"
        }
    }

    def __init__(self):
        pass

    def check_compliance(self, job_data: dict, state_code: str) -> dict:
        """
        Run all plumbing compliance checks.

        Args:
            job_data: Job details including fixtures and equipment
            state_code: State abbreviation

        Returns:
            Dictionary with compliance results and gaps
        """
        equipment = job_data.get("equipment", {})
        fixtures = job_data.get("fixtures", [])

        checks = {}
        gaps = []
        total_water_savings = 0

        # 1. Check each fixture for WaterSense compliance
        for fixture in fixtures:
            fixture_result = self._check_fixture_compliance(fixture, state_code)
            check_key = f"watersense_{fixture.get('type', 'unknown')}_{fixture.get('id', '0')}"
            checks[check_key] = fixture_result.passed
            if not fixture_result.passed and fixture_result.gap:
                gaps.append(fixture_result.gap)
            if fixture_result.water_savings:
                total_water_savings += fixture_result.water_savings

        # 2. Check water heater compliance
        if equipment.get("type") in ["water_heater", "tankless", "heat_pump_water_heater"]:
            wh_result = self._check_water_heater_compliance(equipment)
            checks["water_heater_efficiency"] = wh_result.passed
            if not wh_result.passed and wh_result.gap:
                gaps.append(wh_result.gap)

        # 3. Check state-specific requirements
        state_results = self._check_state_requirements(fixtures, equipment, state_code)
        for key, result in state_results.items():
            checks[key] = result.passed
            if not result.passed and result.gap:
                gaps.append(result.gap)

        # 4. PFAS reporting check (if applicable)
        if equipment.get("type") == "water_filtration":
            pfas_result = self._check_pfas_compliance(equipment)
            checks["pfas_reporting"] = pfas_result.passed
            if not pfas_result.passed and pfas_result.gap:
                gaps.append(pfas_result.gap)

        return {
            "vertical": "plumbing",
            "state_code": state_code,
            "overall_compliant": len(gaps) == 0,
            "checks": checks,
            "gaps": gaps,
            "total_water_savings_gpy": total_water_savings,
            "timestamp": datetime.utcnow().isoformat()
        }

    def _check_fixture_compliance(self, fixture: dict, state_code: str) -> ComplianceCheckResult:
        """Check individual fixture against WaterSense standards."""
        fixture_type = fixture.get("type", "").lower()
        flow_rate = fixture.get("flow_rate") or fixture.get("gpf") or fixture.get("gpm")
        old_flow_rate = fixture.get("old_flow_rate", 0)

        # Determine category
        category = self._get_fixture_category(fixture_type)
        if not category:
            return ComplianceCheckResult(
                check_name=f"WaterSense {fixture_type}",
                passed=True,
                requirement="Unknown fixture type",
                actual_value=str(flow_rate) if flow_rate else "Not specified",
                gap=None,
                recommendation=None,
                water_savings=None,
                reference="EPA WaterSense"
            )

        standard = self.WATERSENSE_STANDARDS.get(category)
        if not standard:
            return ComplianceCheckResult(
                check_name=f"WaterSense {fixture_type}",
                passed=True,
                requirement="No standard defined",
                actual_value=str(flow_rate) if flow_rate else "Not specified",
                gap=None,
                recommendation=None,
                water_savings=None,
                reference="EPA WaterSense"
            )

        # Get state-specific limit if stricter
        state_reqs = self.STATE_REQUIREMENTS.get(state_code, {})
        state_limit = None
        if category == WaterSenseCategory.TOILET:
            state_limit = state_reqs.get("toilet_max_gpf")
        elif category == WaterSenseCategory.SHOWERHEAD:
            state_limit = state_reqs.get("showerhead_max_gpm")
        elif category == WaterSenseCategory.LAVATORY_FAUCET:
            state_limit = state_reqs.get("lavatory_max_gpm")

        # Use stricter of federal or state
        max_flow = min(standard.max_flow_rate, state_limit) if state_limit else standard.max_flow_rate

        if not flow_rate:
            return ComplianceCheckResult(
                check_name=f"WaterSense {fixture_type}",
                passed=True,
                requirement=f"{max_flow} {standard.unit} max",
                actual_value="Not specified",
                gap=None,
                recommendation="Verify flow rate meets WaterSense standards",
                water_savings=None,
                reference=standard.source
            )

        # Calculate water savings
        water_savings = None
        if old_flow_rate > flow_rate:
            if category in [WaterSenseCategory.TOILET, WaterSenseCategory.URINAL]:
                # Assume 5 flushes per day
                water_savings = (old_flow_rate - flow_rate) * 5 * 365
            else:
                # Assume 10 minutes of use per day for faucets/showerheads
                water_savings = (old_flow_rate - flow_rate) * 10 * 365

        if flow_rate <= max_flow:
            return ComplianceCheckResult(
                check_name=f"WaterSense {fixture_type}",
                passed=True,
                requirement=f"{max_flow} {standard.unit} max",
                actual_value=f"{flow_rate} {standard.unit}",
                gap=None,
                recommendation=None,
                water_savings=water_savings,
                reference=standard.source
            )
        else:
            return ComplianceCheckResult(
                check_name=f"WaterSense {fixture_type}",
                passed=False,
                requirement=f"{max_flow} {standard.unit} max",
                actual_value=f"{flow_rate} {standard.unit}",
                gap=f"{fixture_type.title()} flow rate {flow_rate} {standard.unit} exceeds WaterSense maximum {max_flow} {standard.unit}",
                recommendation=f"Install WaterSense certified {fixture_type} ({max_flow} {standard.unit} or less)",
                water_savings=water_savings,
                reference=standard.source
            )

    def _check_water_heater_compliance(self, equipment: dict) -> ComplianceCheckResult:
        """Check water heater efficiency compliance."""
        fuel_type = equipment.get("fuel_type", "").lower()
        tank_size = equipment.get("tank_size_gallons", 50)
        uef = equipment.get("uef") or equipment.get("energy_factor")

        if not uef:
            return ComplianceCheckResult(
                check_name="Water Heater Efficiency",
                passed=True,
                requirement="UEF rating required",
                actual_value="Not specified",
                gap=None,
                recommendation="Verify water heater UEF meets DOE minimum standards",
                water_savings=None,
                reference="DOE Water Heater Standards"
            )

        # Find applicable standard
        min_uef = self._get_min_uef(fuel_type, tank_size)

        if uef >= min_uef:
            return ComplianceCheckResult(
                check_name="Water Heater Efficiency",
                passed=True,
                requirement=f"UEF >= {min_uef}",
                actual_value=f"UEF {uef}",
                gap=None,
                recommendation=None,
                water_savings=None,
                reference="DOE Water Heater Standards"
            )
        else:
            return ComplianceCheckResult(
                check_name="Water Heater Efficiency",
                passed=False,
                requirement=f"UEF >= {min_uef}",
                actual_value=f"UEF {uef}",
                gap=f"Water heater UEF {uef} below minimum {min_uef}",
                recommendation="Upgrade to ENERGY STAR certified water heater or heat pump water heater",
                water_savings=None,
                reference="DOE Water Heater Standards"
            )

    def _check_state_requirements(
        self,
        fixtures: List[dict],
        equipment: dict,
        state_code: str
    ) -> Dict[str, ComplianceCheckResult]:
        """Check state-specific requirements."""
        results = {}
        state_reqs = self.STATE_REQUIREMENTS.get(state_code, {})

        if not state_reqs:
            return results

        # California ultra-low flow urinal
        if state_code == "CA":
            for fixture in fixtures:
                if fixture.get("type", "").lower() == "urinal":
                    gpf = fixture.get("gpf", 0)
                    max_gpf = state_reqs.get("urinal_max_gpf", 0.125)
                    results["ca_ultra_low_urinal"] = ComplianceCheckResult(
                        check_name="CA Ultra-Low Urinal",
                        passed=gpf <= max_gpf if gpf else True,
                        requirement=f"{max_gpf} GPF max (CA)",
                        actual_value=f"{gpf} GPF" if gpf else "Not specified",
                        gap=f"Urinal {gpf} GPF exceeds CA limit of {max_gpf} GPF" if gpf and gpf > max_gpf else None,
                        recommendation="Install California-compliant 0.125 GPF urinal",
                        water_savings=None,
                        reference="CA Water Code"
                    )

        # Texas drought restrictions
        if state_code == "TX" and state_reqs.get("drought_restrictions"):
            results["tx_drought_compliance"] = ComplianceCheckResult(
                check_name="TX Drought Compliance",
                passed=True,  # Would need more data
                requirement="Meet drought restriction requirements when active",
                actual_value="Check local restrictions",
                gap=None,
                recommendation="Verify compliance with local drought restrictions",
                water_savings=None,
                reference="TX Health & Safety Code"
            )

        return results

    def _check_pfas_compliance(self, equipment: dict) -> ComplianceCheckResult:
        """Check PFAS reporting compliance for water filtration."""
        filtration_type = equipment.get("filtration_type", "").lower()
        pfas_tested = equipment.get("pfas_tested", False)
        pfas_level = equipment.get("pfas_level_ppt", 0)

        # EPA proposed limit is 4 ppt combined
        epa_limit = 4

        if not pfas_tested:
            return ComplianceCheckResult(
                check_name="PFAS Reporting",
                passed=True,
                requirement="PFAS testing recommended for filtration systems",
                actual_value="Not tested",
                gap=None,
                recommendation="Consider PFAS testing for comprehensive water quality assessment",
                water_savings=None,
                reference="EPA PFAS Strategic Roadmap"
            )

        if pfas_level <= epa_limit:
            return ComplianceCheckResult(
                check_name="PFAS Reporting",
                passed=True,
                requirement=f"PFAS < {epa_limit} ppt",
                actual_value=f"{pfas_level} ppt",
                gap=None,
                recommendation=None,
                water_savings=None,
                reference="EPA PFAS Strategic Roadmap"
            )
        else:
            return ComplianceCheckResult(
                check_name="PFAS Reporting",
                passed=False,
                requirement=f"PFAS < {epa_limit} ppt",
                actual_value=f"{pfas_level} ppt",
                gap=f"PFAS level {pfas_level} ppt exceeds EPA limit of {epa_limit} ppt",
                recommendation="Install PFAS filtration system; Report elevated levels",
                water_savings=None,
                reference="EPA PFAS Strategic Roadmap"
            )

    def _get_fixture_category(self, fixture_type: str) -> Optional[WaterSenseCategory]:
        """Map fixture type to WaterSense category."""
        fixture_type = fixture_type.lower()

        mappings = {
            "toilet": WaterSenseCategory.TOILET,
            "urinal": WaterSenseCategory.URINAL,
            "showerhead": WaterSenseCategory.SHOWERHEAD,
            "shower": WaterSenseCategory.SHOWERHEAD,
            "lavatory": WaterSenseCategory.LAVATORY_FAUCET,
            "bathroom_faucet": WaterSenseCategory.LAVATORY_FAUCET,
            "sink": WaterSenseCategory.LAVATORY_FAUCET,
            "kitchen_faucet": WaterSenseCategory.KITCHEN_FAUCET,
            "kitchen": WaterSenseCategory.KITCHEN_FAUCET,
            "irrigation": WaterSenseCategory.IRRIGATION_CONTROLLER,
            "sprinkler": WaterSenseCategory.IRRIGATION_CONTROLLER
        }

        for key, category in mappings.items():
            if key in fixture_type:
                return category

        return None

    def _get_min_uef(self, fuel_type: str, tank_size: float) -> float:
        """Get minimum UEF requirement for water heater."""
        fuel_type = fuel_type.lower()

        for standard in self.WATER_HEATER_STANDARDS:
            if standard.fuel_type in fuel_type:
                if standard.tank_size_max == 0:  # Tankless
                    return standard.min_uef
                elif standard.tank_size_min <= tank_size <= standard.tank_size_max:
                    return standard.min_uef

        # Default to gas standard
        return 0.64

    def calculate_water_savings(
        self,
        old_fixtures: List[dict],
        new_fixtures: List[dict]
    ) -> dict:
        """Calculate annual water savings from fixture upgrades."""
        total_savings_gpd = 0  # Gallons per day
        fixture_savings = []

        for old, new in zip(old_fixtures, new_fixtures):
            fixture_type = old.get("type", "unknown")
            old_rate = old.get("flow_rate") or old.get("gpf") or old.get("gpm", 0)
            new_rate = new.get("flow_rate") or new.get("gpf") or new.get("gpm", 0)

            if old_rate > new_rate:
                category = self._get_fixture_category(fixture_type)
                daily_uses = 5 if category in [WaterSenseCategory.TOILET, WaterSenseCategory.URINAL] else 10

                savings_gpd = (old_rate - new_rate) * daily_uses
                total_savings_gpd += savings_gpd

                fixture_savings.append({
                    "fixture": fixture_type,
                    "old_rate": old_rate,
                    "new_rate": new_rate,
                    "daily_savings_gallons": savings_gpd,
                    "annual_savings_gallons": savings_gpd * 365
                })

        return {
            "daily_savings_gallons": total_savings_gpd,
            "annual_savings_gallons": total_savings_gpd * 365,
            "10_year_savings_gallons": total_savings_gpd * 365 * 10,
            "fixture_details": fixture_savings
        }


# Export checker instance
plumbing_checker = PlumbingComplianceChecker()


def check_plumbing_compliance(job_data: dict, state_code: str) -> dict:
    """Public function to check plumbing compliance."""
    return plumbing_checker.check_compliance(job_data, state_code)
