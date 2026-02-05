"""
ProofGreen Multi-Agent Orchestrator
The 'Brain' that routes ESG verification by Zip Code and Vertical

Uses LangGraph for multi-agent orchestration with state management.
"""

import json
from typing import TypedDict, Annotated, Sequence, Literal, Optional
from datetime import datetime
import operator

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolExecutor

import sys
sys.path.append('..')
from config.settings import settings, get_climate_region, get_seer2_minimum


# Agent State Definition
class AgentState(TypedDict):
    """State shared across all agents in the workflow."""
    messages: Annotated[Sequence[BaseMessage], operator.add]
    job_data: dict
    vertical: str
    zip_code: str
    state_code: str
    climate_region: str
    compliance_results: dict
    carbon_calculation: dict
    tax_credits: dict
    certificate: Optional[dict]
    gaps: list
    next_agent: str
    final_output: dict


# Vertical Types
VERTICALS = Literal["hvac", "plumbing", "electrical", "landscaping", "waste", "solar", "general"]


class GreenVerificationOrchestrator:
    """
    Main orchestrator for the Green Verification Multi-Agent System.

    Routes incoming job data through:
    1. Router Agent - Determines vertical and state compliance requirements
    2. Auditor Agent - Performs ESG audit against green expectations
    3. Rebate Specialist - Looks up applicable IRA credits
    4. Certificate Generator - Creates Green-Verified certificate or flags gaps
    """

    def __init__(self):
        self.llm = ChatAnthropic(
            model=settings.AGENT_MODEL,
            temperature=settings.AGENT_TEMPERATURE,
            max_tokens=settings.AGENT_MAX_TOKENS,
            api_key=settings.ANTHROPIC_API_KEY
        )
        self.workflow = self._build_workflow()

    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow for multi-agent orchestration."""

        # Create the state graph
        workflow = StateGraph(AgentState)

        # Add nodes for each agent
        workflow.add_node("router", self._router_agent)
        workflow.add_node("auditor", self._auditor_agent)
        workflow.add_node("rebate_specialist", self._rebate_specialist_agent)
        workflow.add_node("certificate_generator", self._certificate_generator)

        # Set entry point
        workflow.set_entry_point("router")

        # Add edges
        workflow.add_edge("router", "auditor")
        workflow.add_edge("auditor", "rebate_specialist")
        workflow.add_edge("rebate_specialist", "certificate_generator")
        workflow.add_edge("certificate_generator", END)

        return workflow.compile()

    def _router_agent(self, state: AgentState) -> AgentState:
        """
        Router Agent: Analyzes job data and determines routing.

        Responsibilities:
        - Parse zip code to determine state and climate region
        - Identify the vertical (HVAC, Plumbing, etc.)
        - Load appropriate compliance standards
        """
        job_data = state["job_data"]
        zip_code = job_data.get("zip_code", "")

        # Extract state from zip code (simplified - in production use a ZIP database)
        state_code = self._zip_to_state(zip_code)
        climate_region = get_climate_region(state_code)

        # Determine vertical from job type
        vertical = self._determine_vertical(job_data)

        # Build routing context message
        routing_prompt = f"""
        Analyzing job for Green Verification routing:

        Job ID: {job_data.get('job_id')}
        Vertical: {vertical}
        Zip Code: {zip_code}
        State: {state_code}
        Climate Region: {climate_region}

        Equipment: {job_data.get('equipment', {})}
        Service Type: {job_data.get('service_type')}

        Routing to {vertical} compliance audit with {state_code} state requirements.
        Default reporting standard: CA SB 253 (future-proofing enabled).
        """

        messages = state["messages"] + [
            AIMessage(content=f"[Router Agent] {routing_prompt}")
        ]

        return {
            **state,
            "messages": messages,
            "vertical": vertical,
            "zip_code": zip_code,
            "state_code": state_code,
            "climate_region": climate_region,
            "next_agent": "auditor"
        }

    def _auditor_agent(self, state: AgentState) -> AgentState:
        """
        Auditor Agent: Performs ESG compliance audit.

        Responsibilities:
        - Check equipment against Green Expectations
        - Calculate Scope 1, 2, 3 emissions
        - Identify compliance gaps
        """
        job_data = state["job_data"]
        vertical = state["vertical"]
        state_code = state["state_code"]

        # Build audit prompt
        audit_prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content=self._get_auditor_system_prompt()),
            MessagesPlaceholder(variable_name="messages"),
            HumanMessage(content=f"""
            Perform ESG audit for this {vertical} job:

            Job Data: {json.dumps(job_data, indent=2)}
            State: {state_code}
            Climate Region: {state["climate_region"]}

            Check against:
            1. Federal standards (EPA 2026 mandates)
            2. State-specific requirements ({state_code})
            3. CA SB 253 reporting standards (default future-proofing)

            Return compliance results and any gaps found.
            """)
        ])

        # Run LLM for audit analysis
        response = self.llm.invoke(audit_prompt.format_messages(messages=state["messages"]))

        # Parse compliance results (in production, use structured output)
        compliance_results = self._analyze_compliance(job_data, vertical, state_code)
        gaps = compliance_results.get("gaps", [])

        carbon_calculation = self._calculate_carbon(job_data, vertical)

        messages = state["messages"] + [
            AIMessage(content=f"[Auditor Agent] Compliance audit complete.\n{response.content}")
        ]

        return {
            **state,
            "messages": messages,
            "compliance_results": compliance_results,
            "carbon_calculation": carbon_calculation,
            "gaps": gaps,
            "next_agent": "rebate_specialist"
        }

    def _rebate_specialist_agent(self, state: AgentState) -> AgentState:
        """
        Rebate Specialist Agent: Looks up applicable tax credits.

        Responsibilities:
        - Query Rewiring America API for IRA credits
        - Calculate federal and state incentives
        - Match equipment to eligible programs
        """
        job_data = state["job_data"]
        state_code = state["state_code"]
        vertical = state["vertical"]

        # Calculate applicable tax credits
        tax_credits = self._lookup_tax_credits(job_data, state_code, vertical)

        rebate_summary = f"""
        Tax Credit Analysis for {state_code}:

        Federal Credits:
        - IRA Section 25C: ${tax_credits.get('ira_25c', 0):,.2f}
        - IRA Section 25D: ${tax_credits.get('ira_25d', 0):,.2f}
        - IRA Section 45W: ${tax_credits.get('ira_45w', 0):,.2f}

        State Incentives ({state_code}):
        - Utility Rebates: ${tax_credits.get('utility_rebate', 0):,.2f}
        - State Tax Credit: ${tax_credits.get('state_credit', 0):,.2f}

        Total Estimated Savings: ${tax_credits.get('total', 0):,.2f}
        """

        messages = state["messages"] + [
            AIMessage(content=f"[Rebate Specialist] {rebate_summary}")
        ]

        return {
            **state,
            "messages": messages,
            "tax_credits": tax_credits,
            "next_agent": "certificate_generator"
        }

    def _certificate_generator(self, state: AgentState) -> AgentState:
        """
        Certificate Generator: Creates Green-Verified certificate or flags gaps.

        Responsibilities:
        - Generate certificate if compliant
        - Flag gaps for non-compliant jobs
        - Create actionable recommendations
        """
        compliance_results = state["compliance_results"]
        gaps = state["gaps"]
        carbon_calculation = state["carbon_calculation"]
        tax_credits = state["tax_credits"]
        job_data = state["job_data"]

        is_compliant = len(gaps) == 0 and compliance_results.get("overall_compliant", False)

        if is_compliant:
            certificate = self._generate_certificate(
                job_data=job_data,
                compliance_results=compliance_results,
                carbon_calculation=carbon_calculation,
                tax_credits=tax_credits,
                state_code=state["state_code"]
            )
            output_message = f"""
            ✅ GREEN-VERIFIED CERTIFICATE GENERATED

            Certificate ID: {certificate['certificate_id']}
            Job ID: {job_data.get('job_id')}
            Vertical: {state['vertical'].upper()}

            Carbon Impact:
            - Emissions Avoided: {carbon_calculation.get('avoided_kg', 0):.2f} kg CO2e
            - Net Impact: {carbon_calculation.get('net_impact_kg', 0):.2f} kg CO2e

            Tax Credits Captured: ${tax_credits.get('total', 0):,.2f}

            Compliance: CA SB 253 Ready ✓
            """
        else:
            certificate = None
            gap_list = "\n".join([f"  - {gap}" for gap in gaps])
            output_message = f"""
            ⚠️ COMPLIANCE GAPS DETECTED

            Job ID: {job_data.get('job_id')}
            Vertical: {state['vertical'].upper()}

            Gaps Found:
            {gap_list}

            Recommended Actions:
            {self._get_recommendations(gaps, state['vertical'])}

            Note: Certificate cannot be issued until gaps are resolved.
            """

        messages = state["messages"] + [
            AIMessage(content=f"[Certificate Generator] {output_message}")
        ]

        final_output = {
            "job_id": job_data.get("job_id"),
            "vertical": state["vertical"],
            "state_code": state["state_code"],
            "is_compliant": is_compliant,
            "certificate": certificate,
            "gaps": gaps,
            "compliance_results": compliance_results,
            "carbon_calculation": carbon_calculation,
            "tax_credits": tax_credits,
            "timestamp": datetime.utcnow().isoformat()
        }

        return {
            **state,
            "messages": messages,
            "certificate": certificate,
            "final_output": final_output,
            "next_agent": END
        }

    # Helper Methods

    def _get_auditor_system_prompt(self) -> str:
        """System prompt for the Auditor Agent."""
        return """
        You are the ESG Auditor Agent for ProofGreen, a Green Verification platform for Home Services.

        Your role is to audit jobs against environmental compliance standards:

        1. FEDERAL STANDARDS (Hard Floor):
           - EPA 2026 Refrigerant Mandates (GWP < 700)
           - DOE Efficiency Standards (SEER2, UEF, etc.)
           - EPA Section 608 Certification

        2. STATE REQUIREMENTS:
           - Apply state-specific regulations
           - Note stricter local requirements

        3. FUTURE-PROOFING (CA SB 253):
           - Apply California SB 253 Scope 1-3 reporting standards
           - This prepares businesses for likely federal adoption

        4. EMISSIONS CALCULATION:
           - Scope 1: Direct emissions (fuel, refrigerants)
           - Scope 2: Indirect emissions (purchased electricity)
           - Scope 3: Value chain emissions (equipment manufacturing, disposal)

        Always identify gaps clearly and provide actionable recommendations.
        """

    def _zip_to_state(self, zip_code: str) -> str:
        """Convert ZIP code to state abbreviation."""
        # Simplified ZIP prefix mapping (production would use full ZIP database)
        zip_prefix = zip_code[:3] if zip_code else "900"

        zip_state_map = {
            # California
            "900": "CA", "901": "CA", "902": "CA", "903": "CA", "904": "CA",
            "905": "CA", "906": "CA", "907": "CA", "908": "CA", "910": "CA",
            "911": "CA", "912": "CA", "913": "CA", "914": "CA", "915": "CA",
            "916": "CA", "917": "CA", "918": "CA", "919": "CA", "920": "CA",
            "921": "CA", "922": "CA", "923": "CA", "924": "CA", "925": "CA",
            "926": "CA", "927": "CA", "928": "CA", "930": "CA", "931": "CA",
            "932": "CA", "933": "CA", "934": "CA", "935": "CA", "936": "CA",
            "937": "CA", "938": "CA", "939": "CA", "940": "CA", "941": "CA",
            "942": "CA", "943": "CA", "944": "CA", "945": "CA", "946": "CA",
            "947": "CA", "948": "CA", "949": "CA", "950": "CA", "951": "CA",
            "952": "CA", "953": "CA", "954": "CA", "955": "CA", "956": "CA",
            "957": "CA", "958": "CA", "959": "CA", "960": "CA", "961": "CA",
            # Texas
            "750": "TX", "751": "TX", "752": "TX", "753": "TX", "754": "TX",
            "755": "TX", "756": "TX", "757": "TX", "758": "TX", "759": "TX",
            "760": "TX", "761": "TX", "762": "TX", "763": "TX", "764": "TX",
            "765": "TX", "766": "TX", "767": "TX", "768": "TX", "769": "TX",
            "770": "TX", "772": "TX", "773": "TX", "774": "TX", "775": "TX",
            "776": "TX", "777": "TX", "778": "TX", "779": "TX", "780": "TX",
            "781": "TX", "782": "TX", "783": "TX", "784": "TX", "785": "TX",
            "786": "TX", "787": "TX", "788": "TX", "789": "TX", "790": "TX",
            "791": "TX", "792": "TX", "793": "TX", "794": "TX", "795": "TX",
            "796": "TX", "797": "TX", "798": "TX", "799": "TX",
            # New York
            "100": "NY", "101": "NY", "102": "NY", "103": "NY", "104": "NY",
            "105": "NY", "106": "NY", "107": "NY", "108": "NY", "109": "NY",
            "110": "NY", "111": "NY", "112": "NY", "113": "NY", "114": "NY",
            "115": "NY", "116": "NY", "117": "NY", "118": "NY", "119": "NY",
            "120": "NY", "121": "NY", "122": "NY", "123": "NY", "124": "NY",
            "125": "NY", "126": "NY", "127": "NY", "128": "NY", "129": "NY",
            "130": "NY", "131": "NY", "132": "NY", "133": "NY", "134": "NY",
            "135": "NY", "136": "NY", "137": "NY", "138": "NY", "139": "NY",
            "140": "NY", "141": "NY", "142": "NY", "143": "NY", "144": "NY",
            "145": "NY", "146": "NY", "147": "NY", "148": "NY", "149": "NY",
            # Florida
            "320": "FL", "321": "FL", "322": "FL", "323": "FL", "324": "FL",
            "325": "FL", "326": "FL", "327": "FL", "328": "FL", "329": "FL",
            "330": "FL", "331": "FL", "332": "FL", "333": "FL", "334": "FL",
            "335": "FL", "336": "FL", "337": "FL", "338": "FL", "339": "FL",
            "340": "FL", "341": "FL", "342": "FL", "344": "FL", "346": "FL",
            # Washington
            "980": "WA", "981": "WA", "982": "WA", "983": "WA", "984": "WA",
            "985": "WA", "986": "WA", "988": "WA", "989": "WA", "990": "WA",
            "991": "WA", "992": "WA", "993": "WA", "994": "WA",
            # Colorado
            "800": "CO", "801": "CO", "802": "CO", "803": "CO", "804": "CO",
            "805": "CO", "806": "CO", "807": "CO", "808": "CO", "809": "CO",
            "810": "CO", "811": "CO", "812": "CO", "813": "CO", "814": "CO",
            "815": "CO", "816": "CO",
        }

        return zip_state_map.get(zip_prefix, "CA")  # Default to CA for SB 253

    def _determine_vertical(self, job_data: dict) -> str:
        """Determine the vertical from job data."""
        job_type = job_data.get("job_type", "").lower()
        service_type = job_data.get("service_type", "").lower()
        equipment = job_data.get("equipment", {})
        equipment_type = equipment.get("type", "").lower()

        # Mapping keywords to verticals
        hvac_keywords = ["hvac", "air conditioning", "ac", "heating", "furnace", "heat pump", "refrigerant"]
        plumbing_keywords = ["plumbing", "water heater", "toilet", "faucet", "pipe", "drain", "sewer"]
        electrical_keywords = ["electrical", "ev charger", "panel", "circuit", "solar", "battery", "wiring"]
        landscaping_keywords = ["landscaping", "irrigation", "lawn", "mower", "blower", "garden"]
        waste_keywords = ["waste", "disposal", "recycling", "debris", "removal", "haul"]

        combined_text = f"{job_type} {service_type} {equipment_type}"

        if any(kw in combined_text for kw in hvac_keywords):
            return "hvac"
        elif any(kw in combined_text for kw in plumbing_keywords):
            return "plumbing"
        elif any(kw in combined_text for kw in electrical_keywords):
            return "electrical"
        elif any(kw in combined_text for kw in landscaping_keywords):
            return "landscaping"
        elif any(kw in combined_text for kw in waste_keywords):
            return "waste"
        else:
            return "general"

    def _analyze_compliance(self, job_data: dict, vertical: str, state_code: str) -> dict:
        """Analyze compliance against green expectations."""
        # Import vertical-specific logic
        gaps = []
        checks = {}

        if vertical == "hvac":
            from verticals.hvac_logic import HVACComplianceChecker
            checker = HVACComplianceChecker()
            result = checker.check_compliance(job_data, state_code)
            gaps = result.get("gaps", [])
            checks = result.get("checks", {})
        elif vertical == "plumbing":
            from verticals.plumbing_logic import PlumbingComplianceChecker
            checker = PlumbingComplianceChecker()
            result = checker.check_compliance(job_data, state_code)
            gaps = result.get("gaps", [])
            checks = result.get("checks", {})
        elif vertical == "electrical":
            from verticals.electrical_logic import ElectricalComplianceChecker
            checker = ElectricalComplianceChecker()
            result = checker.check_compliance(job_data, state_code)
            gaps = result.get("gaps", [])
            checks = result.get("checks", {})
        # Add other verticals...

        return {
            "vertical": vertical,
            "state_code": state_code,
            "overall_compliant": len(gaps) == 0,
            "checks": checks,
            "gaps": gaps,
            "timestamp": datetime.utcnow().isoformat()
        }

    def _calculate_carbon(self, job_data: dict, vertical: str) -> dict:
        """Calculate carbon impact of the job."""
        from tools.carbon_engine import CarbonEngine
        engine = CarbonEngine()
        return engine.calculate_job_impact(job_data, vertical)

    def _lookup_tax_credits(self, job_data: dict, state_code: str, vertical: str) -> dict:
        """Look up applicable tax credits."""
        # Base federal credits
        equipment = job_data.get("equipment", {})
        equipment_cost = equipment.get("cost", 0)

        tax_credits = {
            "ira_25c": 0,
            "ira_25d": 0,
            "ira_45w": 0,
            "utility_rebate": 0,
            "state_credit": 0,
            "total": 0
        }

        # Calculate IRA 25C (Home Improvement)
        if vertical == "hvac":
            if equipment.get("type") in ["heat_pump", "heat_pump_water_heater"]:
                tax_credits["ira_25c"] = min(equipment_cost * 0.30, 2000)
            else:
                tax_credits["ira_25c"] = min(equipment_cost * 0.30, 600)

        # Calculate IRA 25D (Clean Energy)
        if vertical == "electrical":
            if equipment.get("type") in ["solar_pv", "battery_storage"]:
                tax_credits["ira_25d"] = equipment_cost * 0.30

        # State-specific credits
        if state_code == "CA":
            tax_credits["utility_rebate"] = self._get_ca_rebates(job_data, vertical)
        elif state_code == "NY":
            tax_credits["state_credit"] = self._get_ny_credits(job_data, vertical)
        elif state_code == "TX":
            tax_credits["utility_rebate"] = self._get_tx_rebates(job_data, vertical)

        tax_credits["total"] = sum([
            tax_credits["ira_25c"],
            tax_credits["ira_25d"],
            tax_credits["ira_45w"],
            tax_credits["utility_rebate"],
            tax_credits["state_credit"]
        ])

        return tax_credits

    def _get_ca_rebates(self, job_data: dict, vertical: str) -> float:
        """Get California utility rebates."""
        rebate = 0
        equipment = job_data.get("equipment", {})

        if vertical == "hvac":
            if equipment.get("type") == "heat_pump":
                rebate = 3000  # TECH Clean California
        elif vertical == "electrical":
            if equipment.get("type") == "ev_charger":
                rebate = 1000  # PG&E EV Charger rebate
        elif vertical == "plumbing":
            if equipment.get("type") == "heat_pump_water_heater":
                rebate = 1000  # SGIP Water Heater

        return rebate

    def _get_ny_credits(self, job_data: dict, vertical: str) -> float:
        """Get New York state credits."""
        credit = 0
        equipment = job_data.get("equipment", {})

        if vertical == "hvac":
            if equipment.get("type") == "heat_pump":
                credit = min(equipment.get("cost", 0) * 0.25, 14000)  # NYSERDA
        elif vertical == "electrical":
            if equipment.get("type") == "ev_charger":
                credit = 500  # ChargeNY

        return credit

    def _get_tx_credits(self, job_data: dict, vertical: str) -> float:
        """Get Texas rebates."""
        rebate = 0
        equipment = job_data.get("equipment", {})

        if vertical == "plumbing":
            if "smart_irrigation" in str(equipment.get("features", [])).lower():
                rebate = 200  # TWDB Smart Irrigation

        return rebate

    def _generate_certificate(
        self,
        job_data: dict,
        compliance_results: dict,
        carbon_calculation: dict,
        tax_credits: dict,
        state_code: str
    ) -> dict:
        """Generate a Green-Verified certificate."""
        import hashlib
        from datetime import datetime, timedelta

        timestamp = datetime.utcnow()

        # Generate unique certificate ID
        cert_data = f"{job_data.get('job_id')}-{timestamp.isoformat()}"
        cert_hash = hashlib.sha256(cert_data.encode()).hexdigest()[:12].upper()
        certificate_id = f"PG-GRN-{cert_hash}"

        return {
            "certificate_id": certificate_id,
            "type": "GREEN_VERIFIED",
            "job_id": job_data.get("job_id"),
            "company_id": job_data.get("company_id"),
            "vertical": compliance_results.get("vertical"),
            "state_code": state_code,
            "issued_at": timestamp.isoformat(),
            "valid_until": (timestamp + timedelta(days=365)).isoformat(),
            "compliance": {
                "federal_standards": True,
                "state_requirements": True,
                "sb_253_ready": True,
                "checks_passed": compliance_results.get("checks", {})
            },
            "carbon_impact": {
                "avoided_kg": carbon_calculation.get("avoided_kg", 0),
                "net_impact_kg": carbon_calculation.get("net_impact_kg", 0),
                "scope_1": carbon_calculation.get("scope_1", 0),
                "scope_2": carbon_calculation.get("scope_2", 0),
                "scope_3": carbon_calculation.get("scope_3", 0)
            },
            "tax_credits_captured": tax_credits.get("total", 0),
            "verification_url": f"https://proofgreen.io/verify/{certificate_id}",
            "qr_data": {
                "cert_id": certificate_id,
                "issued_by": "ProofGreen",
                "timestamp": timestamp.isoformat()
            }
        }

    def _get_recommendations(self, gaps: list, vertical: str) -> str:
        """Generate recommendations based on gaps."""
        recommendations = []

        for gap in gaps:
            gap_lower = gap.lower()

            if "refrigerant" in gap_lower:
                recommendations.append(
                    "- Transition to A2L refrigerant (R-454B or R-32) before EPA 2026 deadline"
                )
            elif "seer" in gap_lower:
                recommendations.append(
                    "- Upgrade to SEER2 15.0+ equipment for compliance"
                )
            elif "epa 608" in gap_lower:
                recommendations.append(
                    "- Ensure technician EPA 608 certification is current"
                )
            elif "watersense" in gap_lower:
                recommendations.append(
                    "- Install WaterSense certified fixtures (1.28 GPF toilets, 1.5 GPM faucets)"
                )
            elif "ev-ready" in gap_lower:
                recommendations.append(
                    "- Install 240V/50A circuit per NEC 2026 EV-Ready requirements"
                )
            else:
                recommendations.append(f"- Address: {gap}")

        return "\n".join(recommendations) if recommendations else "- Review job details and resubmit"

    async def process_job(self, job_data: dict) -> dict:
        """
        Main entry point: Process a job through the verification workflow.

        Args:
            job_data: Dictionary containing job details

        Returns:
            Final verification output including certificate or gaps
        """
        initial_state: AgentState = {
            "messages": [HumanMessage(content=f"Processing job: {job_data.get('job_id')}")],
            "job_data": job_data,
            "vertical": "",
            "zip_code": job_data.get("zip_code", ""),
            "state_code": "",
            "climate_region": "",
            "compliance_results": {},
            "carbon_calculation": {},
            "tax_credits": {},
            "certificate": None,
            "gaps": [],
            "next_agent": "router",
            "final_output": {}
        }

        # Run the workflow
        final_state = self.workflow.invoke(initial_state)

        return final_state["final_output"]


# Singleton instance
orchestrator = GreenVerificationOrchestrator()


async def verify_job(job_data: dict) -> dict:
    """Public function to verify a job."""
    return await orchestrator.process_job(job_data)
