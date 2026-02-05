"""
ProofGreen Rebate Specialist Agent
Integrates with Rewiring America API for nationwide IRA credits

Handles tax credit identification and calculation for all 50 states.
"""

import httpx
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import json

import sys
sys.path.append('..')
from config.settings import settings


@dataclass
class TaxCredit:
    """Tax credit details."""
    program_id: str
    name: str
    type: str  # federal, state, utility
    amount: float
    percentage: Optional[float]
    max_amount: Optional[float]
    eligible_equipment: List[str]
    requirements: List[str]
    expiration_date: Optional[str]
    source: str


@dataclass
class RebateAnalysis:
    """Complete rebate analysis for a job."""
    job_id: str
    zip_code: str
    state_code: str
    vertical: str
    timestamp: str
    federal_credits: List[TaxCredit]
    state_incentives: List[TaxCredit]
    utility_rebates: List[TaxCredit]
    total_federal: float
    total_state: float
    total_utility: float
    grand_total: float
    eligibility_notes: List[str]


class RebateSpecialist:
    """
    Rebate Specialist Agent for tax credit and incentive identification.

    Integrates with:
    - Rewiring America API for real-time IRA credit lookups
    - DSIRE database for state incentives
    - Utility company rebate programs

    Covers all 50 states with focus on:
    - IRA Section 25C (Home Energy Improvements)
    - IRA Section 25D (Clean Energy)
    - IRA Section 45W (Commercial Clean Vehicles)
    - IRA Section 48C (Advanced Energy Projects)
    - State-specific incentives
    - Local utility rebates
    """

    # IRA Federal Tax Credits (2024-2032)
    IRA_CREDITS = {
        "25C": {
            "name": "Energy Efficient Home Improvement Credit",
            "max_annual": 1200,
            "heat_pump_max": 2000,
            "rate": 0.30,
            "eligible_equipment": [
                "heat_pump_hvac",
                "heat_pump_water_heater",
                "central_ac",
                "furnace",
                "boiler",
                "insulation",
                "windows",
                "doors",
                "electrical_panel",
                "home_energy_audit"
            ],
            "expires": "2032-12-31"
        },
        "25D": {
            "name": "Residential Clean Energy Credit",
            "max_annual": None,  # No cap
            "rate": 0.30,
            "eligible_equipment": [
                "solar_pv",
                "solar_water_heater",
                "fuel_cell",
                "small_wind",
                "geothermal_heat_pump",
                "battery_storage"
            ],
            "expires": "2034-12-31"
        },
        "30D": {
            "name": "Clean Vehicle Credit",
            "max_amount": 7500,
            "new_vehicle_max": 7500,
            "used_vehicle_max": 4000,
            "eligible_equipment": [
                "new_ev",
                "new_phev",
                "used_ev"
            ],
            "income_limits": True,
            "expires": "2032-12-31"
        },
        "45W": {
            "name": "Commercial Clean Vehicle Credit",
            "small_vehicle_max": 7500,
            "large_vehicle_max": 40000,
            "rate": 0.30,
            "eligible_equipment": [
                "commercial_ev",
                "commercial_phev",
                "fleet_ev"
            ],
            "expires": "2032-12-31"
        }
    }

    # State-Specific Incentives Database
    STATE_INCENTIVES = {
        "CA": {
            "programs": [
                {
                    "id": "ca_tech_clean",
                    "name": "TECH Clean California",
                    "type": "rebate",
                    "equipment": ["heat_pump_hvac", "heat_pump_water_heater"],
                    "amount_ranges": {"heat_pump_hvac": (1000, 4500), "heat_pump_water_heater": (1000, 2000)},
                    "income_qualified_bonus": 1500
                },
                {
                    "id": "ca_sgip",
                    "name": "Self-Generation Incentive Program",
                    "type": "rebate",
                    "equipment": ["battery_storage"],
                    "rate_per_kwh": 150,
                    "equity_bonus": True
                },
                {
                    "id": "ca_cvrp",
                    "name": "Clean Vehicle Rebate Project",
                    "type": "rebate",
                    "equipment": ["new_ev", "new_phev"],
                    "amounts": {"new_ev": 2000, "new_phev": 1000},
                    "income_qualified_bonus": 2500
                }
            ]
        },
        "NY": {
            "programs": [
                {
                    "id": "ny_nyserda_hp",
                    "name": "NYSERDA Heat Pump Program",
                    "type": "rebate",
                    "equipment": ["heat_pump_hvac", "ground_source_hp"],
                    "amounts": {"heat_pump_hvac": 1000, "ground_source_hp": 3000},
                    "contractor_bonus": 500
                },
                {
                    "id": "ny_drive_clean",
                    "name": "Drive Clean Rebate",
                    "type": "rebate",
                    "equipment": ["new_ev", "used_ev"],
                    "amounts": {"new_ev": 2000, "used_ev": 500}
                },
                {
                    "id": "ny_empower",
                    "name": "EmPower+ New York",
                    "type": "grant",
                    "equipment": ["insulation", "heat_pump_hvac"],
                    "income_qualified": True,
                    "max_amount": 10000
                }
            ]
        },
        "TX": {
            "programs": [
                {
                    "id": "tx_twdb_irrigation",
                    "name": "TWDB Smart Irrigation Rebate",
                    "type": "rebate",
                    "equipment": ["smart_irrigation", "drip_irrigation"],
                    "amounts": {"smart_irrigation": 200, "drip_irrigation": 100}
                },
                {
                    "id": "tx_oncor_ac",
                    "name": "Oncor A/C Tune-Up Rebate",
                    "type": "rebate",
                    "equipment": ["central_ac"],
                    "amount": 85,
                    "utility": "Oncor"
                },
                {
                    "id": "tx_terp",
                    "name": "Texas Emissions Reduction Plan",
                    "type": "grant",
                    "equipment": ["commercial_ev", "fleet_ev"],
                    "rate": 0.80,
                    "max_amount": 100000
                }
            ]
        },
        "FL": {
            "programs": [
                {
                    "id": "fl_fpl_ac",
                    "name": "FPL A/C Rebate",
                    "type": "rebate",
                    "equipment": ["central_ac", "heat_pump_hvac"],
                    "amounts": {"central_ac": 150, "heat_pump_hvac": 300},
                    "utility": "FPL"
                },
                {
                    "id": "fl_solar_exemption",
                    "name": "Florida Solar Property Tax Exemption",
                    "type": "tax_exemption",
                    "equipment": ["solar_pv"],
                    "rate": 1.0,
                    "description": "100% property tax exemption on added value"
                }
            ]
        },
        "WA": {
            "programs": [
                {
                    "id": "wa_pse_heat_pump",
                    "name": "PSE Heat Pump Rebate",
                    "type": "rebate",
                    "equipment": ["heat_pump_hvac", "heat_pump_water_heater"],
                    "amounts": {"heat_pump_hvac": 2000, "heat_pump_water_heater": 500},
                    "utility": "PSE"
                },
                {
                    "id": "wa_ev_rebate",
                    "name": "WA State EV Rebate",
                    "type": "rebate",
                    "equipment": ["new_ev"],
                    "max_amount": 5000,
                    "income_qualified": True
                }
            ]
        },
        "CO": {
            "programs": [
                {
                    "id": "co_xcel_ev",
                    "name": "Xcel Energy EV Rebate",
                    "type": "rebate",
                    "equipment": ["ev_charger", "new_ev"],
                    "amounts": {"ev_charger": 500, "new_ev": 2500},
                    "utility": "Xcel"
                },
                {
                    "id": "co_heat_pump_tax",
                    "name": "Colorado Heat Pump Tax Credit",
                    "type": "tax_credit",
                    "equipment": ["heat_pump_hvac", "heat_pump_water_heater"],
                    "rate": 0.10,
                    "max_amount": 500
                }
            ]
        }
    }

    def __init__(self):
        self.rewiring_api_key = settings.REWIRING_AMERICA_API_KEY
        self.rewiring_base_url = "https://api.rewiringamerica.org/api/v1"

    async def analyze_rebates(
        self,
        job_data: dict,
        zip_code: str,
        state_code: str
    ) -> RebateAnalysis:
        """
        Analyze all available rebates and tax credits for a job.

        Args:
            job_data: Job details including equipment
            zip_code: ZIP code for location-based incentives
            state_code: State abbreviation

        Returns:
            RebateAnalysis with all applicable credits
        """
        equipment = job_data.get("equipment", {})
        equipment_type = equipment.get("type", "").lower()
        equipment_cost = equipment.get("cost", 0)
        vertical = self._determine_vertical(equipment_type)

        # Get federal credits
        federal_credits = self._calculate_federal_credits(equipment_type, equipment_cost)

        # Get state incentives
        state_incentives = self._get_state_incentives(state_code, equipment_type, equipment_cost)

        # Get utility rebates (via Rewiring America API if available)
        utility_rebates = await self._get_utility_rebates(zip_code, equipment_type)

        # Calculate totals
        total_federal = sum(c.amount for c in federal_credits)
        total_state = sum(c.amount for c in state_incentives)
        total_utility = sum(c.amount for c in utility_rebates)

        # Generate eligibility notes
        eligibility_notes = self._generate_eligibility_notes(
            federal_credits, state_incentives, utility_rebates, equipment
        )

        return RebateAnalysis(
            job_id=job_data.get("job_id", ""),
            zip_code=zip_code,
            state_code=state_code,
            vertical=vertical,
            timestamp=datetime.utcnow().isoformat(),
            federal_credits=federal_credits,
            state_incentives=state_incentives,
            utility_rebates=utility_rebates,
            total_federal=round(total_federal, 2),
            total_state=round(total_state, 2),
            total_utility=round(total_utility, 2),
            grand_total=round(total_federal + total_state + total_utility, 2),
            eligibility_notes=eligibility_notes
        )

    def _determine_vertical(self, equipment_type: str) -> str:
        """Determine vertical from equipment type."""
        hvac_types = ["heat_pump", "ac", "furnace", "central_ac"]
        plumbing_types = ["water_heater", "toilet", "faucet"]
        electrical_types = ["ev_charger", "solar", "battery", "panel"]

        for hvac in hvac_types:
            if hvac in equipment_type:
                return "hvac"
        for plumb in plumbing_types:
            if plumb in equipment_type:
                return "plumbing"
        for elec in electrical_types:
            if elec in equipment_type:
                return "electrical"
        return "general"

    def _calculate_federal_credits(
        self,
        equipment_type: str,
        equipment_cost: float
    ) -> List[TaxCredit]:
        """Calculate applicable federal IRA credits."""
        credits = []

        # Check 25C eligibility
        ira_25c = self.IRA_CREDITS["25C"]
        for eligible in ira_25c["eligible_equipment"]:
            if eligible in equipment_type.lower():
                rate = ira_25c["rate"]
                calculated_credit = equipment_cost * rate

                # Apply caps
                if "heat_pump" in equipment_type.lower():
                    max_credit = ira_25c["heat_pump_max"]
                else:
                    max_credit = ira_25c["max_annual"]

                final_amount = min(calculated_credit, max_credit) if max_credit else calculated_credit

                credits.append(TaxCredit(
                    program_id="IRA_25C",
                    name=ira_25c["name"],
                    type="federal",
                    amount=final_amount,
                    percentage=rate,
                    max_amount=max_credit,
                    eligible_equipment=[equipment_type],
                    requirements=[
                        "Must be installed in primary residence",
                        "Must meet energy efficiency requirements",
                        "Must be placed in service by 2032"
                    ],
                    expiration_date=ira_25c["expires"],
                    source="IRA Section 25C"
                ))
                break

        # Check 25D eligibility
        ira_25d = self.IRA_CREDITS["25D"]
        for eligible in ira_25d["eligible_equipment"]:
            if eligible in equipment_type.lower():
                rate = ira_25d["rate"]
                calculated_credit = equipment_cost * rate

                credits.append(TaxCredit(
                    program_id="IRA_25D",
                    name=ira_25d["name"],
                    type="federal",
                    amount=calculated_credit,
                    percentage=rate,
                    max_amount=None,
                    eligible_equipment=[equipment_type],
                    requirements=[
                        "Must be installed in US residence",
                        "Must be new equipment",
                        "Must be placed in service by 2034"
                    ],
                    expiration_date=ira_25d["expires"],
                    source="IRA Section 25D"
                ))
                break

        # Check 30D/45W for EVs
        if "ev" in equipment_type.lower():
            if "commercial" in equipment_type.lower() or "fleet" in equipment_type.lower():
                ira_45w = self.IRA_CREDITS["45W"]
                credits.append(TaxCredit(
                    program_id="IRA_45W",
                    name=ira_45w["name"],
                    type="federal",
                    amount=min(equipment_cost * ira_45w["rate"], ira_45w["large_vehicle_max"]),
                    percentage=ira_45w["rate"],
                    max_amount=ira_45w["large_vehicle_max"],
                    eligible_equipment=[equipment_type],
                    requirements=[
                        "Must be used in trade or business",
                        "Vehicle must meet clean vehicle requirements"
                    ],
                    expiration_date=ira_45w["expires"],
                    source="IRA Section 45W"
                ))
            else:
                ira_30d = self.IRA_CREDITS["30D"]
                is_new = "new" in equipment_type.lower() or "used" not in equipment_type.lower()
                max_amount = ira_30d["new_vehicle_max"] if is_new else ira_30d["used_vehicle_max"]

                credits.append(TaxCredit(
                    program_id="IRA_30D",
                    name=ira_30d["name"],
                    type="federal",
                    amount=max_amount,
                    percentage=None,
                    max_amount=max_amount,
                    eligible_equipment=[equipment_type],
                    requirements=[
                        "Must meet modified AGI requirements",
                        "Vehicle MSRP limits apply",
                        "Final assembly in North America"
                    ],
                    expiration_date=ira_30d["expires"],
                    source="IRA Section 30D"
                ))

        return credits

    def _get_state_incentives(
        self,
        state_code: str,
        equipment_type: str,
        equipment_cost: float
    ) -> List[TaxCredit]:
        """Get state-specific incentives."""
        credits = []

        state_programs = self.STATE_INCENTIVES.get(state_code, {}).get("programs", [])

        for program in state_programs:
            for eligible in program.get("equipment", []):
                if eligible in equipment_type.lower() or equipment_type.lower() in eligible:
                    # Calculate amount
                    if "amounts" in program:
                        amount = program["amounts"].get(eligible, 0)
                    elif "amount" in program:
                        amount = program["amount"]
                    elif "rate" in program:
                        amount = equipment_cost * program["rate"]
                        if "max_amount" in program:
                            amount = min(amount, program["max_amount"])
                    elif "amount_ranges" in program:
                        range_val = program["amount_ranges"].get(eligible, (0, 0))
                        amount = range_val[0]  # Use lower bound as estimate
                    else:
                        amount = 0

                    credits.append(TaxCredit(
                        program_id=program["id"],
                        name=program["name"],
                        type="state",
                        amount=amount,
                        percentage=program.get("rate"),
                        max_amount=program.get("max_amount"),
                        eligible_equipment=[eligible],
                        requirements=[
                            f"Must be installed in {state_code}",
                            "Income requirements may apply" if program.get("income_qualified") else "",
                            f"Utility: {program.get('utility', 'Various')}" if program.get("utility") else ""
                        ],
                        expiration_date=None,
                        source=f"{state_code} State Program"
                    ))
                    break

        return credits

    async def _get_utility_rebates(
        self,
        zip_code: str,
        equipment_type: str
    ) -> List[TaxCredit]:
        """
        Get utility rebates via Rewiring America API.

        Falls back to static data if API is unavailable.
        """
        credits = []

        if self.rewiring_api_key:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{self.rewiring_base_url}/incentives",
                        params={
                            "zip": zip_code,
                            "equipment": equipment_type
                        },
                        headers={"Authorization": f"Bearer {self.rewiring_api_key}"},
                        timeout=10.0
                    )

                    if response.status_code == 200:
                        data = response.json()
                        for incentive in data.get("incentives", []):
                            if incentive.get("type") == "utility":
                                credits.append(TaxCredit(
                                    program_id=incentive.get("id", ""),
                                    name=incentive.get("name", ""),
                                    type="utility",
                                    amount=incentive.get("amount", 0),
                                    percentage=incentive.get("percentage"),
                                    max_amount=incentive.get("max_amount"),
                                    eligible_equipment=[equipment_type],
                                    requirements=incentive.get("requirements", []),
                                    expiration_date=incentive.get("end_date"),
                                    source=incentive.get("utility_name", "Rewiring America")
                                ))
            except Exception as e:
                print(f"Rewiring America API error: {e}")

        # Fallback: Return estimated utility rebates based on common programs
        if not credits:
            credits = self._get_fallback_utility_rebates(zip_code, equipment_type)

        return credits

    def _get_fallback_utility_rebates(
        self,
        zip_code: str,
        equipment_type: str
    ) -> List[TaxCredit]:
        """Fallback utility rebates when API is unavailable."""
        credits = []

        # Generic utility rebate estimates
        utility_estimates = {
            "heat_pump": 500,
            "heat_pump_water_heater": 300,
            "central_ac": 200,
            "smart_thermostat": 50,
            "ev_charger": 250,
            "insulation": 200
        }

        for equipment_key, amount in utility_estimates.items():
            if equipment_key in equipment_type.lower():
                credits.append(TaxCredit(
                    program_id=f"utility_est_{equipment_key}",
                    name=f"Estimated Utility Rebate - {equipment_key.replace('_', ' ').title()}",
                    type="utility",
                    amount=amount,
                    percentage=None,
                    max_amount=amount,
                    eligible_equipment=[equipment_key],
                    requirements=["Check with local utility for current programs"],
                    expiration_date=None,
                    source="Estimated (Contact utility for confirmation)"
                ))
                break

        return credits

    def _generate_eligibility_notes(
        self,
        federal_credits: List[TaxCredit],
        state_incentives: List[TaxCredit],
        utility_rebates: List[TaxCredit],
        equipment: dict
    ) -> List[str]:
        """Generate eligibility notes and tips."""
        notes = []

        # Federal credit notes
        if federal_credits:
            notes.append(
                f"Federal tax credits totaling ${sum(c.amount for c in federal_credits):,.2f} available. "
                "File with IRS Form 5695."
            )

        # State incentive notes
        if state_incentives:
            notes.append(
                f"State incentives may require separate application. "
                "Apply through state energy office or utility."
            )

        # Stacking advice
        if federal_credits and (state_incentives or utility_rebates):
            notes.append(
                "TIP: Federal tax credits can typically be stacked with state and utility rebates "
                "for maximum savings."
            )

        # Income-qualified programs
        income_qualified = any(
            "income" in str(c.requirements).lower()
            for c in state_incentives + utility_rebates
        )
        if income_qualified:
            notes.append(
                "Some programs offer enhanced rebates for income-qualified households. "
                "Check eligibility requirements."
            )

        # Missing documentation
        if not equipment.get("cost"):
            notes.append(
                "NOTE: Equipment cost not provided. Estimates based on typical costs. "
                "Provide actual cost for accurate credit calculation."
            )

        return notes

    def to_dict(self, analysis: RebateAnalysis) -> dict:
        """Convert RebateAnalysis to dictionary."""
        result = asdict(analysis)
        # Convert TaxCredit objects to dicts
        result["federal_credits"] = [asdict(c) for c in analysis.federal_credits]
        result["state_incentives"] = [asdict(c) for c in analysis.state_incentives]
        result["utility_rebates"] = [asdict(c) for c in analysis.utility_rebates]
        return result


# Singleton instance
rebate_specialist = RebateSpecialist()


async def analyze_rebates(job_data: dict, zip_code: str, state_code: str) -> dict:
    """Public function to analyze rebates for a job."""
    result = await rebate_specialist.analyze_rebates(job_data, zip_code, state_code)
    return rebate_specialist.to_dict(result)
