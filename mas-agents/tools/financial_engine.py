"""
Financial Engine - Incentive Calculator with Rewiring America API Integration
Calculates federal tax credits, state rebates, and utility incentives
"""

import asyncio
import httpx
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class IncentiveType(str, Enum):
    """Types of financial incentives."""
    FEDERAL_TAX_CREDIT = "federal_tax_credit"
    STATE_REBATE = "state_rebate"
    UTILITY_REBATE = "utility_rebate"
    LOCAL_INCENTIVE = "local_incentive"
    HEEHRA = "heehra"  # Home Energy Efficiency Rebate Act
    INCOME_QUALIFIED = "income_qualified"


class AMILevel(str, Enum):
    """Area Median Income levels for HEEHRA eligibility."""
    BELOW_80 = "below_80"  # Low-income: up to 100% rebate
    BETWEEN_80_150 = "80_to_150"  # Moderate-income: up to 50% rebate
    ABOVE_150 = "above_150"  # Not eligible for income-qualified


@dataclass
class Incentive:
    """A financial incentive or rebate."""
    id: str
    name: str
    type: IncentiveType
    amount: float
    percentage: Optional[float] = None
    max_amount: Optional[float] = None
    min_amount: Optional[float] = None
    vertical: str = ""
    equipment_types: List[str] = field(default_factory=list)
    requirements: List[str] = field(default_factory=list)
    expiration_date: Optional[datetime] = None
    source: str = ""
    apply_url: Optional[str] = None
    program_name: str = ""
    income_qualified: bool = False
    ami_requirement: Optional[AMILevel] = None


@dataclass
class FinancialSummary:
    """Summary of all available financial incentives."""
    total_available: float
    federal_credits: List[Incentive]
    state_rebates: List[Incentive]
    utility_rebates: List[Incentive]
    heehra_rebates: List[Incentive]
    income_qualified_bonuses: List[Incentive]
    net_cost_after_incentives: float
    gross_equipment_cost: float
    breakdown: Dict[str, float]


class FinancialEngine:
    """
    Financial incentive calculator with Rewiring America API integration.
    Calculates federal 25C/25D credits, HEEHRA rebates, and state/utility incentives.
    """

    def __init__(
        self,
        rewiring_america_api_key: Optional[str] = None,
        zip_code: Optional[str] = None,
        household_income: Optional[float] = None,
        household_size: int = 4
    ):
        self.api_key = rewiring_america_api_key
        self.zip_code = zip_code
        self.household_income = household_income
        self.household_size = household_size
        self._client = httpx.AsyncClient(timeout=30.0)

        # 2026 Federal Tax Credit Limits (IRA Section 25C and 25D)
        self.federal_credits = {
            "25C": {
                "name": "Energy Efficient Home Improvement Credit",
                "rate": 0.30,  # 30% of cost
                "max_annual": 1200,  # General annual limit
                "heat_pump_max": 2000,  # Heat pump bonus limit
                "eligible_equipment": [
                    "heat_pump_hvac", "heat_pump_water_heater",
                    "insulation", "windows", "doors", "electrical_panel"
                ],
                "equipment_caps": {
                    "heat_pump_hvac": 2000,
                    "heat_pump_water_heater": 2000,
                    "insulation": 1200,
                    "windows": 600,
                    "doors": 500,
                    "electrical_panel": 600
                }
            },
            "25D": {
                "name": "Residential Clean Energy Credit",
                "rate": 0.30,  # 30% of cost
                "max_annual": None,  # No annual cap
                "eligible_equipment": [
                    "solar_pv", "solar_water_heater", "geothermal",
                    "battery_storage", "small_wind"
                ]
            },
            "30D": {
                "name": "Clean Vehicle Credit",
                "max_credit": 7500,
                "msrp_cap_car": 55000,
                "msrp_cap_suv": 80000,
                "eligible_equipment": ["ev_new"]
            },
            "45W": {
                "name": "Commercial Clean Vehicle Credit",
                "rate": 0.30,
                "max_credit": 40000,
                "eligible_equipment": ["ev_commercial", "ev_fleet"]
            }
        }

        # 2026 HEEHRA Rebate Limits (IRA Section 50122)
        self.heehra_limits = {
            "heat_pump_hvac": {"low_income": 8000, "moderate_income": 4000},
            "heat_pump_water_heater": {"low_income": 1750, "moderate_income": 875},
            "electrical_panel": {"low_income": 4000, "moderate_income": 2000},
            "insulation": {"low_income": 1600, "moderate_income": 800},
            "wiring": {"low_income": 2500, "moderate_income": 1250},
            "electric_stove": {"low_income": 840, "moderate_income": 420},
            "electric_dryer": {"low_income": 840, "moderate_income": 420}
        }

        # State-specific rebate programs (2026 data)
        self.state_programs = {
            "CA": {
                "name": "California Clean Energy Programs",
                "programs": [
                    {
                        "name": "TECH Clean California",
                        "equipment": ["heat_pump_hvac", "heat_pump_water_heater"],
                        "amount": 3000,
                        "type": "rebate"
                    },
                    {
                        "name": "SGIP Battery Storage",
                        "equipment": ["battery_storage"],
                        "rate": 0.20,
                        "max": 5000,
                        "type": "rebate"
                    },
                    {
                        "name": "Self-Generation Incentive",
                        "equipment": ["solar_pv"],
                        "rate_per_watt": 0.25,
                        "type": "rebate"
                    }
                ]
            },
            "NY": {
                "name": "NYSERDA Programs",
                "programs": [
                    {
                        "name": "EmPower NY",
                        "equipment": ["heat_pump_hvac", "insulation"],
                        "income_qualified": True,
                        "amount": 10000,
                        "type": "rebate"
                    },
                    {
                        "name": "NY-Sun Solar Incentive",
                        "equipment": ["solar_pv"],
                        "rate_per_watt": 0.35,
                        "type": "rebate"
                    }
                ]
            },
            "TX": {
                "name": "Texas Utility Programs",
                "programs": [
                    {
                        "name": "Oncor Efficiency Rebate",
                        "equipment": ["heat_pump_hvac"],
                        "amount": 1500,
                        "type": "rebate"
                    }
                ]
            },
            "FL": {
                "name": "Florida Solar Programs",
                "programs": [
                    {
                        "name": "Solar Rights Exemption",
                        "equipment": ["solar_pv"],
                        "type": "tax_exemption",
                        "description": "Property tax exemption for solar installations"
                    }
                ]
            },
            "WA": {
                "name": "Washington Clean Energy",
                "programs": [
                    {
                        "name": "PSE Heat Pump Rebate",
                        "equipment": ["heat_pump_hvac"],
                        "amount": 2000,
                        "type": "rebate"
                    }
                ]
            },
            "CO": {
                "name": "Colorado Energy Programs",
                "programs": [
                    {
                        "name": "Xcel Energy Rebate",
                        "equipment": ["heat_pump_hvac", "heat_pump_water_heater"],
                        "amount": 1800,
                        "type": "rebate"
                    }
                ]
            }
        }

        # Area Median Income thresholds (2026 estimates by state)
        self.ami_thresholds = {
            "CA": {"80_pct": 72000, "150_pct": 135000},
            "NY": {"80_pct": 68000, "150_pct": 127500},
            "TX": {"80_pct": 58000, "150_pct": 108750},
            "FL": {"80_pct": 52000, "150_pct": 97500},
            "WA": {"80_pct": 70000, "150_pct": 131250},
            "default": {"80_pct": 60000, "150_pct": 112500}
        }

    async def get_eligible_incentives(
        self,
        zip_code: str,
        household_income: Optional[float] = None,
        household_size: int = 4,
        state: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fetch all eligible incentives from Rewiring America API.
        Falls back to local database if API unavailable.
        """
        if self.api_key:
            try:
                return await self._fetch_rewiring_america(
                    zip_code, household_income, household_size
                )
            except Exception as e:
                logger.warning(f"Rewiring America API error: {e}, using local data")

        # Use local incentive database
        return self._get_local_incentives(zip_code, household_income, state)

    async def _fetch_rewiring_america(
        self,
        zip_code: str,
        household_income: Optional[float],
        household_size: int
    ) -> Dict[str, Any]:
        """Fetch incentives from Rewiring America API."""
        headers = {"Authorization": f"Bearer {self.api_key}"}
        params = {
            "zip": zip_code,
            "household_size": household_size
        }
        if household_income:
            params["household_income"] = int(household_income)

        response = await self._client.get(
            "https://api.rewiringamerica.org/api/v1/incentives",
            headers=headers,
            params=params
        )
        response.raise_for_status()
        return response.json()

    def _get_local_incentives(
        self,
        zip_code: str,
        household_income: Optional[float],
        state: Optional[str]
    ) -> Dict[str, Any]:
        """Get incentives from local database."""
        # Determine state from zip code if not provided
        if not state:
            state = self._zip_to_state(zip_code)

        # Determine AMI level
        ami_level = self._get_ami_level(household_income, state)

        incentives = {
            "federal_credits": [],
            "state_rebates": [],
            "utility_rebates": [],
            "heehra_rebates": [],
            "location": {"zip": zip_code, "state": state},
            "ami_level": ami_level.value if ami_level else None
        }

        # Add federal credits (always available)
        for credit_id, credit in self.federal_credits.items():
            incentives["federal_credits"].append({
                "id": credit_id,
                "name": credit["name"],
                "rate": credit.get("rate"),
                "max_amount": credit.get("max_annual") or credit.get("max_credit"),
                "eligible_equipment": credit.get("eligible_equipment", [])
            })

        # Add HEEHRA rebates if income-qualified
        if ami_level in [AMILevel.BELOW_80, AMILevel.BETWEEN_80_150]:
            income_key = "low_income" if ami_level == AMILevel.BELOW_80 else "moderate_income"
            for equip, limits in self.heehra_limits.items():
                incentives["heehra_rebates"].append({
                    "id": f"heehra_{equip}",
                    "name": f"HEEHRA {equip.replace('_', ' ').title()} Rebate",
                    "amount": limits[income_key],
                    "equipment": equip,
                    "income_qualified": True
                })

        # Add state-specific rebates
        state_data = self.state_programs.get(state, {})
        for program in state_data.get("programs", []):
            incentives["state_rebates"].append({
                "id": f"state_{state}_{program['name'][:10]}",
                "name": program["name"],
                "amount": program.get("amount"),
                "rate": program.get("rate"),
                "equipment": program.get("equipment", []),
                "type": program.get("type", "rebate")
            })

        return incentives

    def _get_ami_level(self, household_income: Optional[float], state: str) -> Optional[AMILevel]:
        """Determine Area Median Income level."""
        if not household_income:
            return None

        thresholds = self.ami_thresholds.get(state, self.ami_thresholds["default"])

        if household_income <= thresholds["80_pct"]:
            return AMILevel.BELOW_80
        elif household_income <= thresholds["150_pct"]:
            return AMILevel.BETWEEN_80_150
        return AMILevel.ABOVE_150

    def _zip_to_state(self, zip_code: str) -> str:
        """Map ZIP code to state (simplified)."""
        zip_prefix = int(zip_code[:3])

        # Simplified ZIP to state mapping
        if 900 <= zip_prefix <= 961:
            return "CA"
        elif 750 <= zip_prefix <= 799:
            return "TX"
        elif 320 <= zip_prefix <= 349:
            return "FL"
        elif 100 <= zip_prefix <= 149:
            return "NY"
        elif 980 <= zip_prefix <= 994:
            return "WA"
        elif 800 <= zip_prefix <= 816:
            return "CO"
        return "CA"  # Default

    def calculate_federal_credits(
        self,
        vertical: str,
        equipment_type: str,
        equipment_cost: float
    ) -> Dict[str, Any]:
        """Calculate federal tax credits for equipment."""
        credits = []

        # Check 25C eligibility (home improvement)
        credit_25c = self.federal_credits["25C"]
        if equipment_type in credit_25c.get("eligible_equipment", []):
            cap = credit_25c["equipment_caps"].get(equipment_type, credit_25c["max_annual"])
            credit_amount = min(equipment_cost * credit_25c["rate"], cap)

            credits.append({
                "type": "25C",
                "name": credit_25c["name"],
                "amount": credit_amount,
                "rate": credit_25c["rate"],
                "cap_applied": cap,
                "equipment": equipment_type
            })

        # Check 25D eligibility (clean energy)
        credit_25d = self.federal_credits["25D"]
        if equipment_type in credit_25d.get("eligible_equipment", []):
            credit_amount = equipment_cost * credit_25d["rate"]

            credits.append({
                "type": "25D",
                "name": credit_25d["name"],
                "amount": credit_amount,
                "rate": credit_25d["rate"],
                "cap_applied": None,
                "equipment": equipment_type
            })

        # Check 30D/45W for EVs
        if equipment_type in ["ev_charger", "ev_new"]:
            credit_30d = self.federal_credits["30D"]
            credits.append({
                "type": "30D",
                "name": credit_30d["name"],
                "amount": min(equipment_cost * 0.30, credit_30d["max_credit"]),
                "rate": 0.30,
                "cap_applied": credit_30d["max_credit"],
                "equipment": equipment_type
            })

        return {
            "credits": credits,
            "total_federal_credit": sum(c["amount"] for c in credits),
            "equipment_cost": equipment_cost
        }

    def calculate_heehra_rebates(
        self,
        equipment_type: str,
        equipment_cost: float,
        household_income: Optional[float],
        state: str
    ) -> Dict[str, Any]:
        """Calculate HEEHRA rebates based on income qualification."""
        ami_level = self._get_ami_level(household_income, state)

        if not ami_level or ami_level == AMILevel.ABOVE_150:
            return {
                "eligible": False,
                "reason": "Household income exceeds 150% AMI threshold",
                "rebates": [],
                "total": 0
            }

        limits = self.heehra_limits.get(equipment_type)
        if not limits:
            return {
                "eligible": False,
                "reason": f"Equipment type {equipment_type} not eligible for HEEHRA",
                "rebates": [],
                "total": 0
            }

        income_key = "low_income" if ami_level == AMILevel.BELOW_80 else "moderate_income"
        max_rebate = limits[income_key]

        # Low-income gets 100% of cost up to cap, moderate gets 50%
        if ami_level == AMILevel.BELOW_80:
            rebate_amount = min(equipment_cost, max_rebate)
        else:
            rebate_amount = min(equipment_cost * 0.5, max_rebate)

        return {
            "eligible": True,
            "ami_level": ami_level.value,
            "rebates": [{
                "name": f"HEEHRA {equipment_type.replace('_', ' ').title()}",
                "amount": rebate_amount,
                "max_available": max_rebate,
                "coverage_rate": 1.0 if ami_level == AMILevel.BELOW_80 else 0.5
            }],
            "total": rebate_amount
        }

    async def calculate_all_incentives(
        self,
        vertical: str,
        equipment_type: str,
        equipment_cost: float,
        zip_code: str,
        household_income: Optional[float] = None,
        household_size: int = 4
    ) -> FinancialSummary:
        """
        Calculate all available incentives for an equipment purchase.
        Combines federal credits, HEEHRA, and state/utility rebates.
        """
        state = self._zip_to_state(zip_code)

        # Get all incentive data
        all_incentives = await self.get_eligible_incentives(
            zip_code, household_income, household_size, state
        )

        # Calculate federal credits
        federal_result = self.calculate_federal_credits(vertical, equipment_type, equipment_cost)

        # Calculate HEEHRA rebates
        heehra_result = self.calculate_heehra_rebates(
            equipment_type, equipment_cost, household_income, state
        )

        # Build incentive lists
        federal_credits = [
            Incentive(
                id=c["type"],
                name=c["name"],
                type=IncentiveType.FEDERAL_TAX_CREDIT,
                amount=c["amount"],
                percentage=c["rate"],
                max_amount=c.get("cap_applied"),
                vertical=vertical,
                equipment_types=[c["equipment"]],
                source="IRS"
            )
            for c in federal_result["credits"]
        ]

        heehra_rebates = []
        if heehra_result["eligible"]:
            for r in heehra_result["rebates"]:
                heehra_rebates.append(Incentive(
                    id=f"heehra_{equipment_type}",
                    name=r["name"],
                    type=IncentiveType.HEEHRA,
                    amount=r["amount"],
                    max_amount=r["max_available"],
                    vertical=vertical,
                    equipment_types=[equipment_type],
                    income_qualified=True,
                    ami_requirement=AMILevel(heehra_result["ami_level"]),
                    source="DOE HEEHRA"
                ))

        # State rebates
        state_rebates = []
        for rebate in all_incentives.get("state_rebates", []):
            if equipment_type in rebate.get("equipment", []) or not rebate.get("equipment"):
                amount = rebate.get("amount", 0)
                if rebate.get("rate"):
                    amount = equipment_cost * rebate["rate"]

                state_rebates.append(Incentive(
                    id=rebate["id"],
                    name=rebate["name"],
                    type=IncentiveType.STATE_REBATE,
                    amount=amount,
                    percentage=rebate.get("rate"),
                    vertical=vertical,
                    equipment_types=rebate.get("equipment", []),
                    source=f"State of {state}"
                ))

        # Calculate totals
        total_federal = sum(c.amount for c in federal_credits)
        total_heehra = sum(r.amount for r in heehra_rebates)
        total_state = sum(r.amount for r in state_rebates)
        total_available = total_federal + total_heehra + total_state

        net_cost = max(0, equipment_cost - total_available)

        return FinancialSummary(
            total_available=total_available,
            federal_credits=federal_credits,
            state_rebates=state_rebates,
            utility_rebates=[],  # Would come from utility API
            heehra_rebates=heehra_rebates,
            income_qualified_bonuses=[r for r in heehra_rebates if r.income_qualified],
            net_cost_after_incentives=net_cost,
            gross_equipment_cost=equipment_cost,
            breakdown={
                "federal_credits": total_federal,
                "heehra_rebates": total_heehra,
                "state_rebates": total_state,
                "utility_rebates": 0,
                "gross_cost": equipment_cost,
                "net_cost": net_cost,
                "total_savings": total_available,
                "savings_percentage": (total_available / equipment_cost * 100) if equipment_cost > 0 else 0
            }
        )

    async def generate_tax_savings_summary(
        self,
        job_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate a Tax Savings Summary for a completed job.
        Called automatically when a job is closed via FSM webhook.
        """
        vertical = job_data.get("vertical", "hvac")
        equipment = job_data.get("equipment", [])
        zip_code = job_data.get("zip_code", "90210")
        household_income = job_data.get("household_income")
        total_cost = job_data.get("total_cost", 0)

        # Calculate incentives for each piece of equipment
        all_summaries = []
        for equip in equipment:
            equip_type = equip.get("type", "heat_pump_hvac")
            equip_cost = equip.get("cost", total_cost / max(len(equipment), 1))

            summary = await self.calculate_all_incentives(
                vertical=vertical,
                equipment_type=equip_type,
                equipment_cost=equip_cost,
                zip_code=zip_code,
                household_income=household_income
            )
            all_summaries.append(summary)

        # Aggregate results
        total_federal = sum(s.breakdown["federal_credits"] for s in all_summaries)
        total_heehra = sum(s.breakdown["heehra_rebates"] for s in all_summaries)
        total_state = sum(s.breakdown["state_rebates"] for s in all_summaries)
        total_savings = total_federal + total_heehra + total_state

        return {
            "job_id": job_data.get("job_id"),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "gross_cost": total_cost,
                "total_incentives": total_savings,
                "net_cost": max(0, total_cost - total_savings),
                "savings_percentage": (total_savings / total_cost * 100) if total_cost > 0 else 0
            },
            "federal_credits": {
                "total": total_federal,
                "credits": [
                    {"type": c.id, "amount": c.amount}
                    for s in all_summaries for c in s.federal_credits
                ]
            },
            "heehra_rebates": {
                "total": total_heehra,
                "income_qualified": bool(total_heehra > 0),
                "rebates": [
                    {"name": r.name, "amount": r.amount}
                    for s in all_summaries for r in s.heehra_rebates
                ]
            },
            "state_rebates": {
                "total": total_state,
                "rebates": [
                    {"name": r.name, "amount": r.amount}
                    for s in all_summaries for r in s.state_rebates
                ]
            },
            "disclaimer": (
                "All financial incentives are estimates based on current 2026 eligibility guidelines. "
                "Final approval is subject to government agency review. Consult a tax professional "
                "for specific advice regarding your situation."
            )
        }

    async def close(self):
        """Close HTTP client."""
        await self._client.aclose()


# Convenience function
async def calculate_max_rebate(
    vertical: str,
    job_data: Dict[str, Any],
    rewiring_america_api_key: Optional[str] = None
) -> Dict[str, Any]:
    """Quick calculation of maximum available rebates for a job."""
    engine = FinancialEngine(rewiring_america_api_key=rewiring_america_api_key)
    try:
        return await engine.generate_tax_savings_summary(job_data)
    finally:
        await engine.close()
