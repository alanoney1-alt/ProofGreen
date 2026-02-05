"""
ProofGreen ESG Simulation Workflow
Full end-to-end simulation of ESG verification with HITL approval.

This simulation demonstrates:
1. Tech uploads photo of old HVAC unit
2. Agent baselines current equipment (Vision OCR)
3. Agent finds A2L-compliant replacement
4. Agent calculates HEEHRA/IRA rebates
5. Workflow PAUSES for human approval
6. After approval, generates Green Certificate
7. Updates Carbon Ledger with transaction
8. Logs everything to immutable audit trail
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class SimulationJob:
    """Simulated job data."""
    job_id: str = field(default_factory=lambda: f"SIM-{uuid4().hex[:8].upper()}")
    company_id: str = "DEMO_HVAC_CO"
    technician_id: str = "TECH_001"
    technician_name: str = "John Smith"

    # Location
    state: str = "FL"
    zip_code: str = "33139"
    address: str = "1234 Ocean Drive, Miami Beach, FL 33139"

    # Job type
    vertical: str = "hvac"
    job_type: str = "heat_pump_installation"

    # Customer
    customer_name: str = "Jane Homeowner"
    property_type: str = "residential"
    household_income: float = 65000.0
    household_size: int = 3

    # Old equipment (to be removed)
    old_equipment: Dict[str, Any] = field(default_factory=lambda: {
        "type": "air_conditioner",
        "manufacturer": "Carrier",
        "model_number": "24ACC636A003",
        "serial_number": "3215F12345",
        "seer_rating": 13.0,
        "refrigerant_type": "R-410A",
        "tonnage": 3.0,
        "install_year": 2010
    })

    # New equipment (to be installed)
    new_equipment: Dict[str, Any] = field(default_factory=lambda: {
        "type": "heat_pump",
        "manufacturer": "Carrier",
        "model_number": "25VNA048A003",
        "serial_number": "2026A2L789",
        "seer2_rating": 18.0,
        "hspf2_rating": 9.5,
        "refrigerant_type": "R-454B",
        "tonnage": 4.0,
        "btu_capacity": 48000,
        "energy_star_certified": True,
        "ahri_reference_number": "AHRI12345678"
    })

    # Costs
    equipment_cost: float = 12500.0
    installation_cost: float = 3500.0
    total_cost: float = 16000.0


@dataclass
class SimulationStep:
    """A step in the simulation."""
    step_number: int
    name: str
    status: str  # pending, running, completed, paused, failed
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    requires_approval: bool = False


class ESGSimulation:
    """
    Full ESG verification simulation with Human-in-the-Loop.

    Workflow:
    1. Photo Upload & Vision OCR
    2. Baseline Analysis
    3. Compliance Check
    4. Rebate/Credit Calculation
    5. Human Approval (PAUSE)
    6. Certificate Generation
    7. Ledger Update
    8. Audit Logging
    """

    def __init__(
        self,
        anthropic_api_key: Optional[str] = None,
        auto_approve: bool = False
    ):
        self.anthropic_api_key = anthropic_api_key
        self.auto_approve = auto_approve  # For testing without HITL
        self.steps: List[SimulationStep] = []
        self.job: Optional[SimulationJob] = None
        self.is_paused = False
        self.approval_callback = None

        self._initialize_steps()

    def _initialize_steps(self):
        """Initialize simulation steps."""
        self.steps = [
            SimulationStep(1, "Photo Upload & Vision OCR", "pending"),
            SimulationStep(2, "Baseline Analysis", "pending"),
            SimulationStep(3, "Compliance Check (2026 Regulations)", "pending"),
            SimulationStep(4, "Rebate & Credit Calculation", "pending"),
            SimulationStep(5, "Human Approval", "pending", requires_approval=True),
            SimulationStep(6, "Green Certificate Generation", "pending"),
            SimulationStep(7, "Carbon Ledger Update", "pending"),
            SimulationStep(8, "Audit Trail Logging", "pending"),
        ]

    async def run_simulation(
        self,
        job: Optional[SimulationJob] = None,
        old_equipment_photo: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Run the full ESG simulation.

        Args:
            job: Optional custom job data
            old_equipment_photo: Optional path to equipment photo

        Returns:
            Simulation results including all steps and final status
        """
        self.job = job or SimulationJob()
        logger.info(f"Starting ESG Simulation for job {self.job.job_id}")

        simulation_result = {
            "job_id": self.job.job_id,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "steps": [],
            "final_status": "pending",
            "rebate_total": 0,
            "carbon_saved_kg": 0,
            "certificate_id": None
        }

        try:
            # Step 1: Photo Upload & Vision OCR
            await self._run_step(1, self._step_vision_ocr, old_equipment_photo)

            # Step 2: Baseline Analysis
            await self._run_step(2, self._step_baseline_analysis)

            # Step 3: Compliance Check
            await self._run_step(3, self._step_compliance_check)

            # Step 4: Rebate Calculation
            await self._run_step(4, self._step_rebate_calculation)

            # Step 5: Human Approval (PAUSE)
            approval_result = await self._run_step(5, self._step_human_approval)

            if not approval_result.get("approved"):
                simulation_result["final_status"] = "rejected"
                simulation_result["rejection_reason"] = approval_result.get("reason")
                logger.info(f"Simulation rejected: {approval_result.get('reason')}")
            else:
                # Step 6: Certificate Generation
                await self._run_step(6, self._step_certificate_generation)

                # Step 7: Ledger Update
                await self._run_step(7, self._step_ledger_update)

                # Step 8: Audit Logging
                await self._run_step(8, self._step_audit_logging)

                simulation_result["final_status"] = "completed"

        except Exception as e:
            logger.error(f"Simulation failed: {e}")
            simulation_result["final_status"] = "failed"
            simulation_result["error"] = str(e)

        # Compile results
        simulation_result["steps"] = [
            {
                "step": s.step_number,
                "name": s.name,
                "status": s.status,
                "result": s.result
            }
            for s in self.steps
        ]

        # Calculate totals
        rebate_step = next((s for s in self.steps if s.step_number == 4), None)
        if rebate_step and rebate_step.result:
            simulation_result["rebate_total"] = rebate_step.result.get("total_incentives", 0)

        cert_step = next((s for s in self.steps if s.step_number == 6), None)
        if cert_step and cert_step.result:
            simulation_result["certificate_id"] = cert_step.result.get("certificate_id")

        ledger_step = next((s for s in self.steps if s.step_number == 7), None)
        if ledger_step and ledger_step.result:
            simulation_result["carbon_saved_kg"] = ledger_step.result.get("carbon_avoided_kg", 0)

        simulation_result["completed_at"] = datetime.now(timezone.utc).isoformat()

        logger.info(f"Simulation complete: {simulation_result['final_status']}")
        return simulation_result

    async def _run_step(self, step_number: int, step_func, *args) -> Dict[str, Any]:
        """Run a single simulation step."""
        step = self.steps[step_number - 1]
        step.status = "running"
        step.started_at = datetime.now(timezone.utc)

        logger.info(f"Step {step_number}: {step.name} - STARTED")

        try:
            result = await step_func(*args)
            step.result = result
            step.status = "completed"
            step.completed_at = datetime.now(timezone.utc)

            logger.info(f"Step {step_number}: {step.name} - COMPLETED")
            return result

        except Exception as e:
            step.status = "failed"
            step.result = {"error": str(e)}
            logger.error(f"Step {step_number}: {step.name} - FAILED: {e}")
            raise

    # =========================================================================
    # Step Implementations
    # =========================================================================

    async def _step_vision_ocr(self, photo_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Step 1: Use Claude Vision to extract equipment data from photo.
        """
        if photo_path:
            # In production, use the EquipmentVisionParser
            # For simulation, we use mock data
            pass

        # Simulate Vision OCR extraction
        extracted_data = {
            "ocr_performed": True,
            "image_quality": "good",
            "extracted_fields": {
                "manufacturer": self.job.old_equipment["manufacturer"],
                "model_number": self.job.old_equipment["model_number"],
                "serial_number": self.job.old_equipment["serial_number"],
                "seer_rating": self.job.old_equipment["seer_rating"],
                "refrigerant_type": self.job.old_equipment["refrigerant_type"],
                "tonnage": self.job.old_equipment["tonnage"]
            },
            "confidence_score": 0.94,
            "warnings": []
        }

        # Add warning if old refrigerant
        if self.job.old_equipment["refrigerant_type"] == "R-410A":
            extracted_data["warnings"].append(
                "R-410A detected - equipment uses high-GWP refrigerant (GWP: 2088)"
            )

        return extracted_data

    async def _step_baseline_analysis(self) -> Dict[str, Any]:
        """
        Step 2: Analyze baseline equipment and calculate current footprint.
        """
        old_equipment = self.job.old_equipment
        new_equipment = self.job.new_equipment

        # Calculate energy consumption
        # Old unit: SEER 13, assume 2000 cooling hours/year in FL
        old_seer = old_equipment["seer_rating"]
        new_seer2 = new_equipment["seer2_rating"]
        btu = new_equipment["btu_capacity"]

        cooling_hours = 2000  # FL average
        old_kwh_year = (btu * cooling_hours) / (old_seer * 1000)
        new_kwh_year = (btu * cooling_hours) / (new_seer2 * 1000)

        # Florida grid emissions factor (kg CO2/kWh)
        grid_factor = 0.38

        old_emissions_kg = old_kwh_year * grid_factor
        new_emissions_kg = new_kwh_year * grid_factor
        avoided_emissions = old_emissions_kg - new_emissions_kg

        # Equipment lifetime (15 years)
        lifetime_savings = avoided_emissions * 15

        return {
            "baseline_established": True,
            "old_equipment_summary": {
                "type": old_equipment["type"],
                "efficiency": f"SEER {old_seer}",
                "refrigerant": old_equipment["refrigerant_type"],
                "refrigerant_gwp": 2088,
                "annual_kwh": round(old_kwh_year),
                "annual_emissions_kg_co2": round(old_emissions_kg)
            },
            "new_equipment_summary": {
                "type": new_equipment["type"],
                "efficiency": f"SEER2 {new_seer2}",
                "refrigerant": new_equipment["refrigerant_type"],
                "refrigerant_gwp": 466,
                "annual_kwh": round(new_kwh_year),
                "annual_emissions_kg_co2": round(new_emissions_kg)
            },
            "improvement": {
                "efficiency_gain_percent": round((new_seer2 - old_seer) / old_seer * 100, 1),
                "gwp_reduction_percent": round((2088 - 466) / 2088 * 100, 1),
                "annual_kwh_savings": round(old_kwh_year - new_kwh_year),
                "annual_co2_avoided_kg": round(avoided_emissions),
                "lifetime_co2_avoided_kg": round(lifetime_savings)
            }
        }

    async def _step_compliance_check(self) -> Dict[str, Any]:
        """
        Step 3: Check compliance with 2026 regulations.
        """
        new_equipment = self.job.new_equipment
        state = self.job.state

        # 2026 requirements for FL (southern region)
        requirements = {
            "seer2_minimum": 15.2,  # Southern states
            "hspf2_minimum": 7.5,
            "gwp_maximum": 700,
            "a2l_required": True,
            "energy_star_recommended": True
        }

        # Check each requirement
        checks = []
        is_compliant = True

        # SEER2 check
        seer2 = new_equipment["seer2_rating"]
        seer2_pass = seer2 >= requirements["seer2_minimum"]
        checks.append({
            "requirement": "DOE SEER2 2023 (Southern)",
            "required": f">= {requirements['seer2_minimum']}",
            "actual": seer2,
            "status": "PASS" if seer2_pass else "FAIL"
        })
        if not seer2_pass:
            is_compliant = False

        # HSPF2 check
        hspf2 = new_equipment["hspf2_rating"]
        hspf2_pass = hspf2 >= requirements["hspf2_minimum"]
        checks.append({
            "requirement": "DOE HSPF2 2023",
            "required": f">= {requirements['hspf2_minimum']}",
            "actual": hspf2,
            "status": "PASS" if hspf2_pass else "FAIL"
        })
        if not hspf2_pass:
            is_compliant = False

        # Refrigerant GWP check
        refrigerant_gwp = {"R-454B": 466, "R-32": 675, "R-410A": 2088}.get(
            new_equipment["refrigerant_type"], 0
        )
        gwp_pass = refrigerant_gwp <= requirements["gwp_maximum"]
        checks.append({
            "requirement": "EPA AIM Act 2024 (GWP < 700)",
            "required": f"<= {requirements['gwp_maximum']}",
            "actual": refrigerant_gwp,
            "status": "PASS" if gwp_pass else "FAIL"
        })
        if not gwp_pass:
            is_compliant = False

        # A2L compliance
        a2l_refrigerants = ["R-454B", "R-32", "R-1234yf"]
        a2l_pass = new_equipment["refrigerant_type"] in a2l_refrigerants
        checks.append({
            "requirement": "2025 A2L Refrigerant Mandate",
            "required": "A2L refrigerant required",
            "actual": new_equipment["refrigerant_type"],
            "status": "PASS" if a2l_pass else "FAIL"
        })
        if not a2l_pass:
            is_compliant = False

        # Energy Star
        energy_star = new_equipment["energy_star_certified"]
        checks.append({
            "requirement": "Energy Star 2026 (recommended)",
            "required": "Certified",
            "actual": "Yes" if energy_star else "No",
            "status": "PASS" if energy_star else "WARNING"
        })

        return {
            "compliance_checked": True,
            "is_compliant": is_compliant,
            "compliance_score": sum(1 for c in checks if c["status"] == "PASS") / len(checks) * 100,
            "regulations_checked": [
                "DOE SEER2 2023",
                "DOE HSPF2 2023",
                "EPA AIM Act 2024",
                "2025 A2L Refrigerant Mandate",
                "Energy Star 2026"
            ],
            "checks": checks,
            "state": state,
            "vertical": self.job.vertical
        }

    async def _step_rebate_calculation(self) -> Dict[str, Any]:
        """
        Step 4: Calculate all available rebates and tax credits.
        """
        job = self.job
        new_equipment = job.new_equipment

        incentives = []

        # Section 25C - Energy Efficient Home Improvement Credit
        # Heat pumps qualify for 30% up to $2,000
        credit_25c = min(job.equipment_cost * 0.30, 2000)
        incentives.append({
            "program": "IRA Section 25C",
            "type": "federal_tax_credit",
            "amount": credit_25c,
            "description": "30% of equipment cost, max $2,000 for heat pumps",
            "requirements_met": [
                "Heat pump meets efficiency requirements",
                "SEER2 >= 15.2",
                "HSPF2 >= 9.0"
            ]
        })

        # HEEHRA - Home Efficiency Rebate
        # Check AMI (Area Median Income) qualification
        # Miami-Dade AMI ~$77,300 for family of 3
        ami_threshold_80 = 77300 * 0.80  # $61,840
        ami_threshold_150 = 77300 * 1.50  # $115,950

        heehra_amount = 0
        heehra_coverage = 0
        if job.household_income <= ami_threshold_80:
            # Low income: up to 100% of costs, max $8,000 for heat pump
            heehra_coverage = 1.0
            heehra_amount = min(job.equipment_cost, 8000)
            heehra_tier = "Low Income (<80% AMI)"
        elif job.household_income <= ami_threshold_150:
            # Moderate income: up to 50% of costs, max $8,000
            heehra_coverage = 0.5
            heehra_amount = min(job.equipment_cost * 0.5, 8000)
            heehra_tier = "Moderate Income (80-150% AMI)"
        else:
            heehra_tier = "Above 150% AMI - Not Eligible"

        if heehra_amount > 0:
            incentives.append({
                "program": "HEEHRA (IRA)",
                "type": "point_of_sale_rebate",
                "amount": heehra_amount,
                "description": f"{heehra_tier} - {int(heehra_coverage*100)}% coverage",
                "requirements_met": [
                    f"Household income: ${job.household_income:,.0f}",
                    f"AMI threshold: {heehra_tier}",
                    "Heat pump installation qualifies"
                ]
            })

        # Florida state rebate (example - check current programs)
        fl_rebate = 500  # Example state rebate
        incentives.append({
            "program": "Florida Energy Rebate",
            "type": "state_rebate",
            "amount": fl_rebate,
            "description": "Florida heat pump installation rebate",
            "requirements_met": [
                "Florida resident",
                "Energy Star certified equipment"
            ]
        })

        # Utility rebate (FPL example)
        utility_rebate = 300
        incentives.append({
            "program": "FPL Residential Rebate",
            "type": "utility_rebate",
            "amount": utility_rebate,
            "description": "FPL high-efficiency heat pump rebate",
            "requirements_met": [
                "FPL customer",
                "SEER2 >= 16"
            ]
        })

        total_incentives = sum(i["amount"] for i in incentives)
        net_cost = job.total_cost - total_incentives

        return {
            "calculation_complete": True,
            "incentives": incentives,
            "total_incentives": total_incentives,
            "equipment_cost": job.equipment_cost,
            "installation_cost": job.installation_cost,
            "gross_cost": job.total_cost,
            "net_cost_after_incentives": net_cost,
            "savings_percentage": round(total_incentives / job.total_cost * 100, 1),
            "approval_required": total_incentives > 500,  # HITL threshold
            "risk_level": "high" if total_incentives > 2000 else "medium"
        }

    async def _step_human_approval(self) -> Dict[str, Any]:
        """
        Step 5: PAUSE for human approval.
        """
        rebate_step = self.steps[3]  # Step 4 is index 3
        rebate_result = rebate_step.result or {}
        total_incentives = rebate_result.get("total_incentives", 0)

        logger.info("=" * 60)
        logger.info("SIMULATION PAUSED - AWAITING HUMAN APPROVAL")
        logger.info("=" * 60)
        logger.info(f"Job ID: {self.job.job_id}")
        logger.info(f"Total Rebates/Credits: ${total_incentives:,.2f}")
        logger.info(f"Customer: {self.job.customer_name}")
        logger.info(f"Equipment: {self.job.new_equipment['manufacturer']} Heat Pump")
        logger.info("=" * 60)

        if self.auto_approve:
            # For automated testing
            logger.info("AUTO-APPROVE enabled - approving automatically")
            return {
                "approved": True,
                "approver_id": "AUTO",
                "approver_name": "Automated Test",
                "approval_timestamp": datetime.now(timezone.utc).isoformat(),
                "reason": "Auto-approved for simulation"
            }

        # In production, this would:
        # 1. Create a pending approval in the governance workflow
        # 2. Notify the dashboard
        # 3. Wait for human response
        # For simulation, we'll prompt for approval

        self.is_paused = True

        # Simulate approval (in real system, this would wait for dashboard input)
        approval_data = {
            "task_id": f"approval_{self.job.job_id}",
            "amount": total_incentives,
            "risk_level": rebate_result.get("risk_level", "medium"),
            "job_summary": {
                "customer": self.job.customer_name,
                "equipment": f"{self.job.new_equipment['manufacturer']} Heat Pump",
                "location": f"{self.job.state} {self.job.zip_code}"
            },
            "ai_reasoning": (
                f"Equipment meets all 2026 compliance requirements. "
                f"Customer qualifies for HEEHRA at household income ${self.job.household_income:,.0f}. "
                f"Total incentives ${total_incentives:,.2f} represent {rebate_result.get('savings_percentage', 0)}% savings."
            ),
            "awaiting_approval": True,
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        # For simulation, auto-approve after logging
        logger.info("Simulating human approval...")
        await asyncio.sleep(1)  # Simulate delay

        return {
            "approved": True,
            "approver_id": "SIM_USER_001",
            "approver_name": "Simulation Approver",
            "approval_timestamp": datetime.now(timezone.utc).isoformat(),
            "approval_data": approval_data,
            "reason": "Approved - all compliance checks passed"
        }

    async def _step_certificate_generation(self) -> Dict[str, Any]:
        """
        Step 6: Generate Green Verification Certificate.
        """
        certificate_id = f"GV-{self.job.job_id}-{uuid4().hex[:6].upper()}"

        # Get results from previous steps
        compliance_result = self.steps[2].result or {}
        rebate_result = self.steps[3].result or {}
        baseline_result = self.steps[1].result or {}

        certificate = {
            "certificate_id": certificate_id,
            "job_id": self.job.job_id,
            "company_id": self.job.company_id,
            "issued_at": datetime.now(timezone.utc).isoformat(),
            "valid_until": "2027-12-31",

            # Equipment details
            "equipment": {
                "type": "Heat Pump",
                "manufacturer": self.job.new_equipment["manufacturer"],
                "model": self.job.new_equipment["model_number"],
                "efficiency": f"SEER2 {self.job.new_equipment['seer2_rating']}",
                "refrigerant": self.job.new_equipment["refrigerant_type"]
            },

            # Compliance
            "compliance_status": "FULLY COMPLIANT",
            "compliance_score": compliance_result.get("compliance_score", 100),
            "regulations_verified": compliance_result.get("regulations_checked", []),

            # Environmental impact
            "environmental_impact": {
                "annual_co2_avoided_kg": baseline_result.get("improvement", {}).get("annual_co2_avoided_kg", 0),
                "lifetime_co2_avoided_kg": baseline_result.get("improvement", {}).get("lifetime_co2_avoided_kg", 0),
                "efficiency_improvement": f"{baseline_result.get('improvement', {}).get('efficiency_gain_percent', 0)}%",
                "gwp_reduction": f"{baseline_result.get('improvement', {}).get('gwp_reduction_percent', 0)}%"
            },

            # Financial
            "financial_summary": {
                "total_incentives": rebate_result.get("total_incentives", 0),
                "net_cost": rebate_result.get("net_cost_after_incentives", 0)
            },

            # Verification
            "verification_qr_url": f"https://proofgreen.io/verify/{certificate_id}",
            "pdf_url": f"https://proofgreen.io/certificates/{certificate_id}.pdf",

            # Metadata
            "certifying_agent": "ProofGreen ESG Auditor",
            "methodology": "GHG Protocol Corporate Standard",
            "third_party_verified": True
        }

        return certificate

    async def _step_ledger_update(self) -> Dict[str, Any]:
        """
        Step 7: Update Carbon Ledger with transaction.
        """
        baseline_result = self.steps[1].result or {}
        rebate_result = self.steps[3].result or {}
        certificate_result = self.steps[5].result or {}

        improvement = baseline_result.get("improvement", {})

        ledger_entry = {
            "transaction_id": f"TXN-{uuid4().hex[:8].upper()}",
            "job_id": self.job.job_id,
            "company_id": self.job.company_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),

            # Carbon accounting
            "carbon_entries": [
                {
                    "type": "avoided_emissions",
                    "scope": "scope_2",
                    "amount_kg_co2e": improvement.get("annual_co2_avoided_kg", 0),
                    "description": "Annual emissions avoided from efficiency upgrade",
                    "methodology": "GHG Protocol"
                },
                {
                    "type": "refrigerant_transition",
                    "scope": "scope_1",
                    "gwp_reduction": improvement.get("gwp_reduction_percent", 0),
                    "description": "GWP reduction from R-410A to R-454B transition"
                }
            ],

            # Financial
            "financial_entries": [
                {
                    "type": "federal_credit",
                    "amount": next(
                        (i["amount"] for i in rebate_result.get("incentives", [])
                         if i["program"] == "IRA Section 25C"), 0
                    ),
                    "program": "IRA Section 25C"
                },
                {
                    "type": "heehra_rebate",
                    "amount": next(
                        (i["amount"] for i in rebate_result.get("incentives", [])
                         if i["program"] == "HEEHRA (IRA)"), 0
                    ),
                    "program": "HEEHRA"
                }
            ],

            # Summary
            "carbon_avoided_kg": improvement.get("annual_co2_avoided_kg", 0),
            "lifetime_carbon_avoided_kg": improvement.get("lifetime_co2_avoided_kg", 0),
            "captured_revenue": rebate_result.get("total_incentives", 0),
            "certificate_id": certificate_result.get("certificate_id"),

            # Status
            "verification_status": "verified",
            "ledger_status": "committed"
        }

        return ledger_entry

    async def _step_audit_logging(self) -> Dict[str, Any]:
        """
        Step 8: Log everything to immutable audit trail.
        """
        # Compile all audit entries
        audit_entries = []

        # Entry for each major decision
        audit_entries.append({
            "entry_id": f"AUDIT-{uuid4().hex[:8]}",
            "action": "vision_ocr_extraction",
            "agent_id": "equipment_vision_parser",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "decision_logic": "Extracted equipment specifications from photo using Claude Vision",
            "evidence_hash": f"sha256:{uuid4().hex}",
            "confidence_score": 0.94
        })

        audit_entries.append({
            "entry_id": f"AUDIT-{uuid4().hex[:8]}",
            "action": "compliance_check",
            "agent_id": "regulatory_router",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "decision_logic": "Verified equipment meets all 2026 regulatory requirements",
            "regulations_checked": ["DOE SEER2", "EPA AIM Act", "A2L Mandate"],
            "result": "compliant"
        })

        audit_entries.append({
            "entry_id": f"AUDIT-{uuid4().hex[:8]}",
            "action": "rebate_calculation",
            "agent_id": "financial_engine",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "decision_logic": "Calculated federal credits and HEEHRA rebates based on customer eligibility",
            "amount_dollars": self.steps[3].result.get("total_incentives", 0),
            "programs": ["25C", "HEEHRA", "FL State", "FPL Utility"]
        })

        approval_result = self.steps[4].result or {}
        audit_entries.append({
            "entry_id": f"AUDIT-{uuid4().hex[:8]}",
            "action": "human_approval",
            "agent_id": "governance_workflow",
            "timestamp": approval_result.get("approval_timestamp"),
            "human_approver_id": approval_result.get("approver_id"),
            "human_approver_name": approval_result.get("approver_name"),
            "decision": "approved",
            "reason": approval_result.get("reason")
        })

        certificate_result = self.steps[5].result or {}
        audit_entries.append({
            "entry_id": f"AUDIT-{uuid4().hex[:8]}",
            "action": "certificate_issued",
            "agent_id": "certificate_generator",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "certificate_id": certificate_result.get("certificate_id"),
            "verification_url": certificate_result.get("verification_qr_url")
        })

        return {
            "audit_complete": True,
            "entries_logged": len(audit_entries),
            "audit_entries": audit_entries,
            "chain_integrity": "verified",
            "sb253_compliant": True,
            "sec_compliant": True
        }


# =========================================================================
# CLI Entry Point
# =========================================================================

async def run_demo_simulation():
    """Run a demo simulation."""
    print("\n" + "=" * 70)
    print("PROOFGREEN ESG SIMULATION - HEAT PUMP INSTALLATION IN FLORIDA")
    print("=" * 70 + "\n")

    simulation = ESGSimulation(auto_approve=True)
    result = await simulation.run_simulation()

    print("\n" + "=" * 70)
    print("SIMULATION RESULTS")
    print("=" * 70)
    print(f"Job ID: {result['job_id']}")
    print(f"Status: {result['final_status'].upper()}")
    print(f"Total Rebates: ${result['rebate_total']:,.2f}")
    print(f"Carbon Avoided: {result['carbon_saved_kg']:,.0f} kg CO2e")
    print(f"Certificate ID: {result['certificate_id']}")
    print("\nSteps Completed:")
    for step in result['steps']:
        status_icon = "✅" if step['status'] == 'completed' else "❌"
        print(f"  {status_icon} {step['name']}")

    print("\n" + "=" * 70 + "\n")

    return result


if __name__ == "__main__":
    asyncio.run(run_demo_simulation())
