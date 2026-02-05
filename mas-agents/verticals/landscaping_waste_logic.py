"""
ProofGreen Landscaping & Waste Compliance Logic
Electrification tracking, diversion metrics, and green practices

Handles:
- CARB SORE (Small Off-Road Engine) Rule Compliance
- Gas-to-Electric Equipment Transition Tracking
- EPA WaterSense Smart Irrigation
- Landfill Diversion Metrics (EPA WARM)
- Construction & Demolition Waste Diversion
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, date
from enum import Enum


class EquipmentType(Enum):
    """Landscaping equipment types."""
    MOWER = "mower"
    BLOWER = "blower"
    TRIMMER = "trimmer"
    CHAINSAW = "chainsaw"
    EDGER = "edger"
    PRESSURE_WASHER = "pressure_washer"
    GENERATOR = "generator"
    HEDGE_TRIMMER = "hedge_trimmer"


class FuelType(Enum):
    """Equipment fuel types."""
    GAS = "gas"
    ELECTRIC = "electric"
    BATTERY = "battery"
    PROPANE = "propane"
    DIESEL = "diesel"


class WasteCategory(Enum):
    """Waste categories for tracking."""
    GREEN_WASTE = "green_waste"
    METAL = "metal"
    CONCRETE = "concrete"
    WOOD = "wood"
    PLASTIC = "plastic"
    CARDBOARD = "cardboard"
    MIXED_C_AND_D = "mixed_c_and_d"
    HAZMAT = "hazmat"
    E_WASTE = "e_waste"
    APPLIANCES = "appliances"


@dataclass
class ComplianceCheckResult:
    """Result of a single compliance check."""
    check_name: str
    passed: bool
    requirement: str
    actual_value: str
    gap: Optional[str]
    recommendation: Optional[str]
    environmental_impact: Optional[dict]
    reference: str


class LandscapingWasteComplianceChecker:
    """
    Landscaping & Waste Compliance Checker.

    Verifies compliance with:
    1. CARB SORE Rule (California Small Off-Road Engine phase-out)
    2. Gas-to-Electric Fleet Transition Goals
    3. EPA WaterSense Smart Irrigation
    4. Landfill Diversion Requirements
    5. NOAA Weather-Based Irrigation Logic
    """

    # CARB SORE Rule Timeline
    CARB_SORE_TIMELINE = {
        "2024-01-01": {
            "banned_equipment": ["blower", "leaf_blower"],
            "hp_limit": None,  # All new sales
            "description": "New small off-road engine leaf blowers banned"
        },
        "2028-01-01": {
            "banned_equipment": ["all_sore"],
            "hp_limit": 25,
            "description": "All new SORE equipment under 25HP banned"
        }
    }

    # Equipment emission factors (kg CO2e per hour of operation)
    EQUIPMENT_EMISSIONS = {
        "mower_gas": {"co2_per_hour": 2.5, "nox_per_hour": 0.015, "pm_per_hour": 0.002},
        "mower_electric": {"co2_per_hour": 0.3, "nox_per_hour": 0, "pm_per_hour": 0},
        "blower_gas": {"co2_per_hour": 1.8, "nox_per_hour": 0.020, "pm_per_hour": 0.003},
        "blower_electric": {"co2_per_hour": 0.1, "nox_per_hour": 0, "pm_per_hour": 0},
        "trimmer_gas": {"co2_per_hour": 1.2, "nox_per_hour": 0.012, "pm_per_hour": 0.002},
        "trimmer_electric": {"co2_per_hour": 0.08, "nox_per_hour": 0, "pm_per_hour": 0},
        "chainsaw_gas": {"co2_per_hour": 2.0, "nox_per_hour": 0.018, "pm_per_hour": 0.003},
        "chainsaw_electric": {"co2_per_hour": 0.2, "nox_per_hour": 0, "pm_per_hour": 0},
    }

    # Waste disposal emission factors (EPA WARM model, kg CO2e per ton)
    WASTE_EMISSION_FACTORS = {
        WasteCategory.GREEN_WASTE: {
            "landfill": 580,
            "compost": -100,  # Carbon benefit
            "mulch": -120
        },
        WasteCategory.METAL: {
            "landfill": 50,
            "recycle": -3000  # Significant benefit
        },
        WasteCategory.CONCRETE: {
            "landfill": 20,
            "recycle": -10
        },
        WasteCategory.WOOD: {
            "landfill": 1200,
            "recycle": -500,
            "biomass_energy": -800
        },
        WasteCategory.PLASTIC: {
            "landfill": 50,
            "recycle": -1800
        },
        WasteCategory.CARDBOARD: {
            "landfill": 2500,
            "recycle": -3100
        },
        WasteCategory.APPLIANCES: {
            "landfill": 100,
            "recycle": -2000,
            "rac_program": -2500  # EPA RAD program
        }
    }

    # State landfill diversion requirements
    STATE_DIVERSION_REQUIREMENTS = {
        "CA": {
            "ab_939_target": 0.50,  # 50% diversion
            "sb_1383_organic_target": 0.75,  # 75% organic waste diversion
            "c_and_d_target": 0.65,  # Construction & demolition
            "effective_dates": {
                "ab_939": "2000-01-01",
                "sb_1383": "2022-01-01"
            }
        },
        "WA": {
            "general_target": 0.50,
            "c_and_d_target": 0.70
        },
        "MA": {
            "commercial_ban": ["food_waste", "organic"],
            "diversion_target": 0.30
        },
        "NY": {
            "nyc_ll97_organics": True,
            "commercial_diversion": 0.50
        }
    }

    # Smart irrigation requirements
    SMART_IRRIGATION_REQUIREMENTS = {
        "watersense_controller": True,
        "weather_based_adjustment": True,
        "rain_sensor_required": True,
        "soil_moisture_recommended": True,
        "max_outdoor_budget_ca": 0.55  # 55% of ET0 for CA
    }

    def __init__(self):
        self.today = date.today()

    def check_compliance(self, job_data: dict, state_code: str) -> dict:
        """
        Run all landscaping and waste compliance checks.

        Args:
            job_data: Job details including equipment and waste
            state_code: State abbreviation

        Returns:
            Dictionary with compliance results and gaps
        """
        equipment_list = job_data.get("equipment_list", [])
        waste_data = job_data.get("waste", {})
        irrigation = job_data.get("irrigation", {})

        checks = {}
        gaps = []
        environmental_impact = {
            "co2_avoided_kg": 0,
            "water_saved_gallons": 0,
            "waste_diverted_tons": 0
        }

        # 1. Check fleet electrification
        fleet_result = self._check_fleet_electrification(equipment_list, state_code)
        checks["fleet_electrification"] = fleet_result.passed
        if not fleet_result.passed and fleet_result.gap:
            gaps.append(fleet_result.gap)
        if fleet_result.environmental_impact:
            environmental_impact["co2_avoided_kg"] += fleet_result.environmental_impact.get("co2_avoided_kg", 0)

        # 2. Check CARB SORE compliance (if CA)
        if state_code == "CA":
            sore_result = self._check_carb_sore_compliance(equipment_list)
            checks["carb_sore_compliant"] = sore_result.passed
            if not sore_result.passed and sore_result.gap:
                gaps.append(sore_result.gap)

        # 3. Check waste diversion
        diversion_result = self._check_waste_diversion(waste_data, state_code)
        checks["waste_diversion"] = diversion_result.passed
        if not diversion_result.passed and diversion_result.gap:
            gaps.append(diversion_result.gap)
        if diversion_result.environmental_impact:
            environmental_impact["waste_diverted_tons"] += diversion_result.environmental_impact.get("diverted_tons", 0)
            environmental_impact["co2_avoided_kg"] += diversion_result.environmental_impact.get("co2_avoided_kg", 0)

        # 4. Check smart irrigation
        if irrigation:
            irrigation_result = self._check_smart_irrigation(irrigation, state_code)
            checks["smart_irrigation"] = irrigation_result.passed
            if not irrigation_result.passed and irrigation_result.gap:
                gaps.append(irrigation_result.gap)
            if irrigation_result.environmental_impact:
                environmental_impact["water_saved_gallons"] += irrigation_result.environmental_impact.get("water_saved_gallons", 0)

        # 5. Check hazmat compliance
        if waste_data.get("hazmat_present"):
            hazmat_result = self._check_hazmat_compliance(waste_data)
            checks["hazmat_disposal"] = hazmat_result.passed
            if not hazmat_result.passed and hazmat_result.gap:
                gaps.append(hazmat_result.gap)

        return {
            "vertical": "landscaping_waste",
            "state_code": state_code,
            "overall_compliant": len(gaps) == 0,
            "checks": checks,
            "gaps": gaps,
            "environmental_impact": environmental_impact,
            "timestamp": datetime.utcnow().isoformat()
        }

    def _check_fleet_electrification(
        self,
        equipment_list: List[dict],
        state_code: str
    ) -> ComplianceCheckResult:
        """Check fleet electrification ratio."""
        if not equipment_list:
            return ComplianceCheckResult(
                check_name="Fleet Electrification",
                passed=True,
                requirement="Track gas vs electric equipment ratio",
                actual_value="No equipment specified",
                gap=None,
                recommendation="Document equipment fleet for tracking",
                environmental_impact=None,
                reference="CARB SORE Rule"
            )

        total_equipment = len(equipment_list)
        electric_count = sum(
            1 for e in equipment_list
            if e.get("fuel_type", "").lower() in ["electric", "battery"]
        )

        electric_ratio = electric_count / total_equipment if total_equipment > 0 else 0
        target_ratio = 0.75  # 75% target

        # Calculate emissions avoided
        gas_hours = sum(
            e.get("annual_hours", 200)
            for e in equipment_list
            if e.get("fuel_type", "").lower() in ["gas", "gasoline"]
        )

        # If electric, calculate avoided emissions
        co2_avoided = 0
        for e in equipment_list:
            if e.get("fuel_type", "").lower() in ["electric", "battery"]:
                equipment_type = e.get("type", "").lower()
                gas_key = f"{equipment_type}_gas"
                elec_key = f"{equipment_type}_electric"

                if gas_key in self.EQUIPMENT_EMISSIONS and elec_key in self.EQUIPMENT_EMISSIONS:
                    hours = e.get("annual_hours", 200)
                    gas_emissions = self.EQUIPMENT_EMISSIONS[gas_key]["co2_per_hour"] * hours
                    elec_emissions = self.EQUIPMENT_EMISSIONS[elec_key]["co2_per_hour"] * hours
                    co2_avoided += gas_emissions - elec_emissions

        if electric_ratio >= target_ratio:
            return ComplianceCheckResult(
                check_name="Fleet Electrification",
                passed=True,
                requirement=f"{target_ratio * 100:.0f}% electric target",
                actual_value=f"{electric_ratio * 100:.0f}% electric ({electric_count}/{total_equipment})",
                gap=None,
                recommendation=None,
                environmental_impact={"co2_avoided_kg": round(co2_avoided, 2)},
                reference="CARB SORE Rule / Green Fleet Goals"
            )
        else:
            equipment_to_convert = int((target_ratio - electric_ratio) * total_equipment) + 1
            return ComplianceCheckResult(
                check_name="Fleet Electrification",
                passed=False,
                requirement=f"{target_ratio * 100:.0f}% electric target",
                actual_value=f"{electric_ratio * 100:.0f}% electric ({electric_count}/{total_equipment})",
                gap=f"Fleet electrification {electric_ratio * 100:.0f}% below {target_ratio * 100:.0f}% target",
                recommendation=f"Convert {equipment_to_convert} more equipment to electric/battery",
                environmental_impact={"co2_avoided_kg": round(co2_avoided, 2)},
                reference="CARB SORE Rule / Green Fleet Goals"
            )

    def _check_carb_sore_compliance(self, equipment_list: List[dict]) -> ComplianceCheckResult:
        """Check CARB SORE (Small Off-Road Engine) rule compliance."""
        non_compliant = []

        for equipment in equipment_list:
            equipment_type = equipment.get("type", "").lower()
            fuel_type = equipment.get("fuel_type", "").lower()
            purchase_date = equipment.get("purchase_date", "")

            # Check if gas-powered leaf blower purchased after 2024
            if fuel_type in ["gas", "gasoline"]:
                if "blower" in equipment_type or "leaf" in equipment_type:
                    if purchase_date and purchase_date >= "2024-01-01":
                        non_compliant.append(f"Gas {equipment_type} (purchased {purchase_date})")
                    elif not purchase_date:
                        non_compliant.append(f"Gas {equipment_type} (purchase date unknown)")

        if not non_compliant:
            return ComplianceCheckResult(
                check_name="CARB SORE Compliance",
                passed=True,
                requirement="No new gas-powered SORE equipment after phase-out dates",
                actual_value="Fleet compliant with CARB SORE timeline",
                gap=None,
                recommendation=None,
                environmental_impact=None,
                reference="CARB Small Off-Road Engine Rule"
            )
        else:
            return ComplianceCheckResult(
                check_name="CARB SORE Compliance",
                passed=False,
                requirement="No new gas-powered SORE equipment after phase-out dates",
                actual_value=f"Non-compliant: {', '.join(non_compliant)}",
                gap=f"Gas-powered equipment violates CARB SORE rule: {', '.join(non_compliant)}",
                recommendation="Replace with electric/battery equipment; phase-out gas by 2028",
                environmental_impact=None,
                reference="CARB Small Off-Road Engine Rule"
            )

    def _check_waste_diversion(self, waste_data: dict, state_code: str) -> ComplianceCheckResult:
        """Check waste diversion compliance."""
        total_waste_tons = waste_data.get("total_tons", 0)
        diverted_tons = waste_data.get("diverted_tons", 0)
        landfill_tons = waste_data.get("landfill_tons", 0)

        if total_waste_tons == 0:
            return ComplianceCheckResult(
                check_name="Waste Diversion",
                passed=True,
                requirement="Track waste diversion rate",
                actual_value="No waste data provided",
                gap=None,
                recommendation="Document waste handling for compliance tracking",
                environmental_impact=None,
                reference="EPA WARM Model"
            )

        diversion_rate = diverted_tons / total_waste_tons if total_waste_tons > 0 else 0

        # Get state requirement
        state_reqs = self.STATE_DIVERSION_REQUIREMENTS.get(state_code, {})
        target_rate = state_reqs.get("general_target") or state_reqs.get("ab_939_target") or 0.50

        # Calculate CO2 impact
        # Simplified: assume 1 ton diverted from landfill = 1.5 tons CO2 avoided
        co2_avoided = diverted_tons * 1500  # kg

        if diversion_rate >= target_rate:
            return ComplianceCheckResult(
                check_name="Waste Diversion",
                passed=True,
                requirement=f"{target_rate * 100:.0f}% diversion rate",
                actual_value=f"{diversion_rate * 100:.0f}% ({diverted_tons:.2f} of {total_waste_tons:.2f} tons diverted)",
                gap=None,
                recommendation=None,
                environmental_impact={
                    "diverted_tons": diverted_tons,
                    "co2_avoided_kg": round(co2_avoided, 2)
                },
                reference=state_reqs.get("reference", "EPA WARM Model")
            )
        else:
            additional_needed = (target_rate * total_waste_tons) - diverted_tons
            return ComplianceCheckResult(
                check_name="Waste Diversion",
                passed=False,
                requirement=f"{target_rate * 100:.0f}% diversion rate",
                actual_value=f"{diversion_rate * 100:.0f}% ({diverted_tons:.2f} of {total_waste_tons:.2f} tons)",
                gap=f"Diversion rate {diversion_rate * 100:.0f}% below {target_rate * 100:.0f}% requirement",
                recommendation=f"Divert additional {additional_needed:.2f} tons through recycling/composting",
                environmental_impact={
                    "diverted_tons": diverted_tons,
                    "co2_avoided_kg": round(co2_avoided, 2)
                },
                reference=state_reqs.get("reference", "EPA WARM Model")
            )

    def _check_smart_irrigation(self, irrigation: dict, state_code: str) -> ComplianceCheckResult:
        """Check smart irrigation compliance."""
        has_smart_controller = irrigation.get("smart_controller", False)
        has_weather_adjustment = irrigation.get("weather_based", False)
        has_rain_sensor = irrigation.get("rain_sensor", False)

        issues = []
        water_saved = 0

        if not has_smart_controller:
            issues.append("WaterSense smart controller recommended")

        if not has_weather_adjustment:
            issues.append("Weather-based adjustment recommended")

        if not has_rain_sensor:
            issues.append("Rain sensor required in many jurisdictions")

        # Calculate water savings (estimate)
        if has_smart_controller:
            # Smart controllers save ~15,000-30,000 gallons/year for typical landscape
            monthly_water = irrigation.get("monthly_gallons", 5000)
            water_saved = monthly_water * 12 * 0.30  # 30% savings estimate

        if not issues:
            return ComplianceCheckResult(
                check_name="Smart Irrigation",
                passed=True,
                requirement="WaterSense controller with weather adjustment",
                actual_value="Smart irrigation system installed",
                gap=None,
                recommendation=None,
                environmental_impact={"water_saved_gallons": round(water_saved, 0)},
                reference="EPA WaterSense Smart Controller"
            )
        else:
            return ComplianceCheckResult(
                check_name="Smart Irrigation",
                passed=False,
                requirement="WaterSense controller with weather adjustment",
                actual_value="; ".join(issues),
                gap="; ".join(issues),
                recommendation="Install WaterSense certified smart irrigation controller",
                environmental_impact={"water_saved_gallons": round(water_saved, 0)},
                reference="EPA WaterSense Smart Controller"
            )

    def _check_hazmat_compliance(self, waste_data: dict) -> ComplianceCheckResult:
        """Check hazardous material disposal compliance."""
        hazmat_types = waste_data.get("hazmat_types", [])
        proper_disposal = waste_data.get("hazmat_proper_disposal", False)
        disposal_manifest = waste_data.get("disposal_manifest", False)

        if not hazmat_types:
            return ComplianceCheckResult(
                check_name="Hazmat Disposal",
                passed=True,
                requirement="EPA RCRA compliance for hazardous waste",
                actual_value="No hazardous materials reported",
                gap=None,
                recommendation=None,
                environmental_impact=None,
                reference="EPA RCRA"
            )

        if proper_disposal and disposal_manifest:
            return ComplianceCheckResult(
                check_name="Hazmat Disposal",
                passed=True,
                requirement="EPA RCRA compliance for hazardous waste",
                actual_value=f"Proper disposal documented for: {', '.join(hazmat_types)}",
                gap=None,
                recommendation=None,
                environmental_impact=None,
                reference="EPA RCRA"
            )
        else:
            issues = []
            if not proper_disposal:
                issues.append("Proper disposal method not documented")
            if not disposal_manifest:
                issues.append("Disposal manifest required")

            return ComplianceCheckResult(
                check_name="Hazmat Disposal",
                passed=False,
                requirement="EPA RCRA compliance for hazardous waste",
                actual_value=f"Issues: {'; '.join(issues)}",
                gap="; ".join(issues),
                recommendation="Use licensed hazmat disposal; Maintain manifests",
                environmental_impact=None,
                reference="EPA RCRA"
            )

    def calculate_fleet_emissions(self, equipment_list: List[dict]) -> dict:
        """Calculate total fleet emissions."""
        total_co2 = 0
        total_nox = 0
        total_pm = 0
        equipment_details = []

        for equipment in equipment_list:
            equipment_type = equipment.get("type", "").lower()
            fuel_type = equipment.get("fuel_type", "").lower()
            annual_hours = equipment.get("annual_hours", 200)

            key = f"{equipment_type}_{fuel_type}"
            if key in self.EQUIPMENT_EMISSIONS:
                factors = self.EQUIPMENT_EMISSIONS[key]
                co2 = factors["co2_per_hour"] * annual_hours
                nox = factors["nox_per_hour"] * annual_hours
                pm = factors["pm_per_hour"] * annual_hours

                total_co2 += co2
                total_nox += nox
                total_pm += pm

                equipment_details.append({
                    "equipment": equipment_type,
                    "fuel": fuel_type,
                    "hours": annual_hours,
                    "co2_kg": round(co2, 2),
                    "nox_kg": round(nox, 4),
                    "pm_kg": round(pm, 4)
                })

        return {
            "total_co2_kg": round(total_co2, 2),
            "total_nox_kg": round(total_nox, 4),
            "total_pm_kg": round(total_pm, 4),
            "equipment_breakdown": equipment_details
        }


# Export checker instance
landscaping_waste_checker = LandscapingWasteComplianceChecker()


def check_landscaping_waste_compliance(job_data: dict, state_code: str) -> dict:
    """Public function to check landscaping and waste compliance."""
    return landscaping_waste_checker.check_compliance(job_data, state_code)
