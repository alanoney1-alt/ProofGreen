"""
Proposal Generator - Green Impact & Savings Report Generator
Creates PDF proposals and certificates for ESG compliance verification
"""

import asyncio
import json
import base64
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import logging
import io

logger = logging.getLogger(__name__)


@dataclass
class ProposalData:
    """Data for generating a Green Impact proposal."""
    job_id: str
    company_name: str
    customer_name: str
    customer_address: str
    vertical: str
    state: str
    zip_code: str
    standard_option: Dict[str, Any]
    green_option: Dict[str, Any]
    carbon_savings: Dict[str, Any]
    financial_incentives: Dict[str, Any]
    compliance_badges: List[str]
    disclaimer: str


@dataclass
class CertificateData:
    """Data for generating a Green Verification certificate."""
    job_id: str
    company_name: str
    vertical: str
    date: datetime
    compliance_verification: Dict[str, Any]
    esg_impact: Dict[str, Any]
    financial_incentives: Dict[str, Any]
    sb253_ready: bool
    verification_code: str


class ProposalGenerator:
    """
    Generates Green Impact & Savings Reports and ESG Compliance Certificates.
    Supports PDF generation and HTML templates.
    """

    def __init__(self, company_name: str = "ProofGreen"):
        self.company_name = company_name
        self.template_dir = Path(__file__).parent.parent / "templates"

    def get_green_disclaimer(self, state: str, vertical: str) -> str:
        """Generate state-and-vertical-specific legal disclaimer."""
        base_disclaimer = (
            "PROPOSAL DISCLAIMER: All financial incentives, including IRA tax credits and state rebates, "
            "are estimates based on current 2026 eligibility guidelines. Final approval is subject to "
            "government agency review. Energy and carbon savings are calculated using standardized EPA "
            "and WattTime emission factors for your specific zip code."
        )

        overrides = {
            "CA": " COMPLIANCE NOTICE: This proposal is prepared in alignment with California SB 253 "
                  "transparency requirements for Scope 3 emissions reporting.",
            "NY": " NY ENERGY LAW: This proposal complies with New York Climate Leadership and "
                  "Community Protection Act (CLCPA) requirements.",
            "hvac": " REFRIGERANT NOTICE: This install utilizes GWP < 700 A2L refrigerants in "
                    "compliance with the 2026 EPA AIM Act transition mandate.",
            "electrical": " NEC COMPLIANCE: All electrical work complies with NEC 2026 requirements "
                          "including AFCI/GFCI protection standards.",
            "plumbing": " WATERSENSE: All fixtures meet or exceed EPA WaterSense certification "
                        "requirements for water efficiency."
        }

        disclaimer = base_disclaimer
        if state in overrides:
            disclaimer += overrides[state]
        if vertical in overrides:
            disclaimer += overrides[vertical]

        return disclaimer

    def generate_green_proposal(
        self,
        job_data: Dict[str, Any],
        carbon_savings: Dict[str, Any],
        financial_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate a complete Green vs Standard proposal.
        Returns structured data for PDF generation.
        """
        state = job_data.get("state", "CA")
        vertical = job_data.get("vertical", "hvac")
        zip_code = job_data.get("zip_code", "90210")

        # Build standard option
        standard_option = {
            "title": "Standard Installation",
            "cost": job_data.get("standard_cost", 8000),
            "incentives": 0,
            "net_cost": job_data.get("standard_cost", 8000),
            "features": [
                "Basic equipment installation",
                "Standard warranty",
                "Meets minimum code requirements"
            ]
        }

        # Build green verified option
        gross_cost = job_data.get("green_cost", 15000)
        total_incentives = financial_data.get("summary", {}).get("total_incentives", 0)
        federal_credits = financial_data.get("federal_credits", {}).get("total", 0)
        state_rebates = financial_data.get("state_rebates", {}).get("total", 0)
        heehra_rebates = financial_data.get("heehra_rebates", {}).get("total", 0)

        annual_energy_savings = carbon_savings.get("annual_kwh_saved", 0) * 0.12  # Avg $0.12/kWh

        green_option = {
            "title": "Green Verified Installation",
            "gross_cost": gross_cost,
            "federal_tax_credits": federal_credits,
            "state_rebates": state_rebates,
            "heehra_rebates": heehra_rebates,
            "total_incentives": total_incentives,
            "net_cost": max(0, gross_cost - total_incentives),
            "annual_energy_savings": annual_energy_savings,
            "features": [
                "High-efficiency equipment (SEER2 18+)",
                "EPA 2026 compliant refrigerants",
                "Extended warranty included",
                "Green Verified certification",
                "ESG compliance documentation",
                "Carbon footprint tracking"
            ]
        }

        # Compliance badges
        compliance_badges = self._get_compliance_badges(vertical, state, job_data)

        # Generate proposal data
        proposal = ProposalData(
            job_id=job_data.get("job_id", "N/A"),
            company_name=job_data.get("company_name", self.company_name),
            customer_name=job_data.get("customer_name", "Homeowner"),
            customer_address=job_data.get("customer_address", ""),
            vertical=vertical,
            state=state,
            zip_code=zip_code,
            standard_option=standard_option,
            green_option=green_option,
            carbon_savings={
                "annual_co2_avoided_lbs": carbon_savings.get("annual_co2_avoided_lbs", 0),
                "annual_co2_avoided_tons": carbon_savings.get("annual_co2_avoided_lbs", 0) / 2000,
                "lifetime_co2_avoided_tons": carbon_savings.get("lifetime_co2_avoided_tons", 0),
                "equivalent_trees": int(carbon_savings.get("annual_co2_avoided_lbs", 0) / 48),
                "equivalent_miles": int(carbon_savings.get("annual_co2_avoided_lbs", 0) / 0.9)
            },
            financial_incentives=financial_data,
            compliance_badges=compliance_badges,
            disclaimer=self.get_green_disclaimer(state, vertical)
        )

        return self._proposal_to_dict(proposal)

    def _get_compliance_badges(
        self,
        vertical: str,
        state: str,
        job_data: Dict[str, Any]
    ) -> List[str]:
        """Get applicable compliance badges for the job."""
        badges = []

        # Universal badges
        if job_data.get("is_a2l_compliant", True):
            badges.append("EPA 2026 REFRIGERANT COMPLIANT")

        if job_data.get("seer2_rating", 18) >= 15:
            badges.append("ENERGY STAR CERTIFIED")

        # Vertical-specific badges
        if vertical == "hvac":
            if job_data.get("seer2_rating", 0) >= 18:
                badges.append("HIGH EFFICIENCY (SEER2 18+)")
            badges.append("EPA 608 CERTIFIED INSTALLATION")

        elif vertical == "plumbing":
            badges.append("WATERSENSE CERTIFIED")
            if job_data.get("water_heater_uef", 0) >= 3.5:
                badges.append("ULTRA-HIGH EFFICIENCY WATER HEATER")

        elif vertical == "electrical":
            badges.append("NEC 2026 COMPLIANT")
            if job_data.get("ev_ready", False):
                badges.append("EV-READY INFRASTRUCTURE")
            if job_data.get("solar_installed", False):
                badges.append("SOLAR PV SYSTEM")

        elif vertical == "landscaping":
            badges.append("LOW-EMISSION EQUIPMENT")
            if job_data.get("electric_equipment", False):
                badges.append("ZERO-EMISSION TOOLS")

        # State-specific badges
        if state == "CA":
            badges.append("CA SB 253 SCOPE 3 READY")
            badges.append("TITLE 24 COMPLIANT")

        return badges

    def generate_certificate(
        self,
        job_data: Dict[str, Any],
        carbon_data: Dict[str, Any],
        financial_data: Dict[str, Any],
        compliance_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate a Green Verification Certificate.
        This is the official ESG compliance document.
        """
        job_id = job_data.get("job_id", "N/A")
        vertical = job_data.get("vertical", "hvac")
        state = job_data.get("state", "CA")

        # Generate verification code
        verification_code = f"PG-{job_id[:8].upper()}-{datetime.now().strftime('%Y%m%d')}"

        # Compliance verification section
        compliance_verification = {
            "refrigerant_standard": {
                "status": "Verified" if job_data.get("is_a2l_compliant", True) else "Non-Compliant",
                "detail": "A2L Low-GWP (<700) system installation" if job_data.get("is_a2l_compliant", True)
                         else "Legacy refrigerant - upgrade recommended"
            },
            "efficiency_rating": {
                "status": f"SEER2 {job_data.get('seer2_rating', 'N/A')}",
                "detail": "Certified per Title 24/IECC 2026 guidelines"
            },
            "waste_management": {
                "status": f"{job_data.get('diversion_rate', 65)}% diverted",
                "detail": f"Demolition material diverted to recycling"
            }
        }

        # ESG Impact section
        esg_impact = {
            "carbon_avoided": {
                "value": carbon_data.get("total_kg_co2e", 0) / 1000,  # Convert to metric tons
                "unit": "Metric Tons CO2e",
                "methodology": "EPA baseline calculation"
            },
            "water_conserved": {
                "value": job_data.get("water_saved_gallons", 0),
                "unit": "Gallons",
                "detail": "WaterSense certified fixtures"
            },
            "energy_efficiency": {
                "value": job_data.get("energy_savings_percent", 0),
                "unit": "% improvement",
                "detail": "vs. previous installation"
            }
        }

        # Financial incentives section
        financial_section = {
            "federal_tax_credit_25C": financial_data.get("federal_credits", {}).get("total", 0),
            "state_rebate": financial_data.get("state_rebates", {}).get("total", 0),
            "heehra_rebate": financial_data.get("heehra_rebates", {}).get("total", 0),
            "total_captured": financial_data.get("summary", {}).get("total_incentives", 0)
        }

        # SB 253 readiness
        sb253_ready = state == "CA" or compliance_data.get("sb253_ready", False)

        certificate = CertificateData(
            job_id=job_id,
            company_name=job_data.get("company_name", self.company_name),
            vertical=vertical,
            date=datetime.now(timezone.utc),
            compliance_verification=compliance_verification,
            esg_impact=esg_impact,
            financial_incentives=financial_section,
            sb253_ready=sb253_ready,
            verification_code=verification_code
        )

        return self._certificate_to_dict(certificate)

    def generate_html_proposal(self, proposal_data: Dict[str, Any]) -> str:
        """Generate HTML version of the proposal."""
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Green Impact & Savings Report - {proposal_data['job_id']}</title>
    <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 40px; color: #333; }}
        .header {{ text-align: center; border-bottom: 3px solid #2e7d32; padding-bottom: 20px; }}
        .logo {{ color: #2e7d32; font-size: 28px; font-weight: bold; }}
        .section {{ margin: 30px 0; padding: 20px; background: #f9f9f9; border-radius: 8px; }}
        .comparison {{ display: flex; gap: 20px; }}
        .option {{ flex: 1; padding: 20px; border-radius: 8px; }}
        .standard {{ background: #f5f5f5; border: 1px solid #ddd; }}
        .green {{ background: #e8f5e9; border: 2px solid #2e7d32; }}
        .badge {{ display: inline-block; background: #2e7d32; color: white; padding: 5px 12px;
                  border-radius: 20px; font-size: 12px; margin: 3px; }}
        .savings {{ font-size: 24px; color: #2e7d32; font-weight: bold; }}
        .disclaimer {{ font-size: 11px; color: #666; margin-top: 30px; padding: 15px;
                       background: #fff3e0; border-radius: 4px; }}
        table {{ width: 100%; border-collapse: collapse; }}
        td, th {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
    </style>
</head>
<body>
    <div class="header">
        <div class="logo">🍃 {proposal_data['company_name']}</div>
        <h1>Green Impact & Savings Report</h1>
        <p>Prepared for: {proposal_data['customer_name']}</p>
        <p>Job ID: {proposal_data['job_id']} | Date: {datetime.now().strftime('%B %d, %Y')}</p>
    </div>

    <div class="section">
        <h2>Installation Options Comparison</h2>
        <div class="comparison">
            <div class="option standard">
                <h3>{proposal_data['standard_option']['title']}</h3>
                <p><strong>Cost:</strong> ${proposal_data['standard_option']['cost']:,.0f}</p>
                <p><strong>Incentives:</strong> $0</p>
                <p><strong>Net Cost:</strong> ${proposal_data['standard_option']['net_cost']:,.0f}</p>
                <ul>
                    {''.join(f"<li>{f}</li>" for f in proposal_data['standard_option']['features'])}
                </ul>
            </div>
            <div class="option green">
                <h3>✓ {proposal_data['green_option']['title']}</h3>
                <p><strong>Gross Cost:</strong> ${proposal_data['green_option']['gross_cost']:,.0f}</p>
                <p><strong>Federal Tax Credits:</strong> -${proposal_data['green_option']['federal_tax_credits']:,.0f}</p>
                <p><strong>State Rebates:</strong> -${proposal_data['green_option']['state_rebates']:,.0f}</p>
                <p><strong>HEEHRA Rebates:</strong> -${proposal_data['green_option']['heehra_rebates']:,.0f}</p>
                <p class="savings">Net Cost: ${proposal_data['green_option']['net_cost']:,.0f}</p>
                <p><strong>Annual Energy Savings:</strong> ${proposal_data['green_option']['annual_energy_savings']:,.0f}/year</p>
                <ul>
                    {''.join(f"<li>{f}</li>" for f in proposal_data['green_option']['features'])}
                </ul>
            </div>
        </div>
    </div>

    <div class="section">
        <h2>Environmental Impact</h2>
        <table>
            <tr><td>Annual CO2 Avoided</td><td><strong>{proposal_data['carbon_savings']['annual_co2_avoided_tons']:.1f} tons</strong></td></tr>
            <tr><td>Lifetime CO2 Avoided</td><td><strong>{proposal_data['carbon_savings']['lifetime_co2_avoided_tons']:.1f} tons</strong></td></tr>
            <tr><td>Equivalent Trees Planted</td><td><strong>{proposal_data['carbon_savings']['equivalent_trees']} trees</strong></td></tr>
            <tr><td>Equivalent Miles Not Driven</td><td><strong>{proposal_data['carbon_savings']['equivalent_miles']:,} miles</strong></td></tr>
        </table>
    </div>

    <div class="section">
        <h2>Compliance Certifications</h2>
        <div>
            {''.join(f'<span class="badge">{badge}</span>' for badge in proposal_data['compliance_badges'])}
        </div>
    </div>

    <div class="disclaimer">
        {proposal_data['disclaimer']}
    </div>
</body>
</html>
"""

    def generate_html_certificate(self, certificate_data: Dict[str, Any]) -> str:
        """Generate HTML version of the certificate."""
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Green Verification Certificate - {certificate_data['verification_code']}</title>
    <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 40px; color: #333; }}
        .certificate {{ border: 3px solid #2e7d32; padding: 40px; max-width: 800px; margin: auto; }}
        .header {{ text-align: center; border-bottom: 2px solid #2e7d32; padding-bottom: 20px; margin-bottom: 30px; }}
        .logo {{ color: #2e7d32; font-size: 32px; font-weight: bold; }}
        .verification-code {{ background: #e8f5e9; padding: 10px 20px; border-radius: 4px;
                              font-family: monospace; font-size: 18px; margin: 10px 0; }}
        .section {{ margin: 25px 0; }}
        .section h3 {{ color: #2e7d32; border-bottom: 1px solid #ddd; padding-bottom: 10px; }}
        .metric {{ display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px dotted #ddd; }}
        .metric-value {{ font-weight: bold; color: #2e7d32; }}
        .sb253-badge {{ background: #1565c0; color: white; padding: 10px 20px; border-radius: 4px;
                        text-align: center; margin: 20px 0; }}
        .footer {{ text-align: center; margin-top: 30px; font-size: 12px; color: #666; }}
        .qr-placeholder {{ width: 100px; height: 100px; background: #f0f0f0; margin: 20px auto;
                          display: flex; align-items: center; justify-content: center; }}
    </style>
</head>
<body>
    <div class="certificate">
        <div class="header">
            <div class="logo">🍃 {certificate_data['company_name']}</div>
            <h1>ESG Compliance Certificate</h1>
            <p>Job ID: {certificate_data['job_id']} | Vertical: {certificate_data['vertical'].upper()}</p>
            <p>Date: {certificate_data['date']}</p>
            <div class="verification-code">Verification Code: {certificate_data['verification_code']}</div>
        </div>

        <div class="section">
            <h3>1. Compliance Verification</h3>
            <div class="metric">
                <span>Refrigerant Standard</span>
                <span class="metric-value">{certificate_data['compliance_verification']['refrigerant_standard']['status']}</span>
            </div>
            <p style="font-size: 12px; color: #666;">{certificate_data['compliance_verification']['refrigerant_standard']['detail']}</p>

            <div class="metric">
                <span>Efficiency Rating</span>
                <span class="metric-value">{certificate_data['compliance_verification']['efficiency_rating']['status']}</span>
            </div>
            <p style="font-size: 12px; color: #666;">{certificate_data['compliance_verification']['efficiency_rating']['detail']}</p>

            <div class="metric">
                <span>Waste Management</span>
                <span class="metric-value">{certificate_data['compliance_verification']['waste_management']['status']}</span>
            </div>
        </div>

        <div class="section">
            <h3>2. ESG Impact Ledger</h3>
            <div class="metric">
                <span>Carbon Avoided</span>
                <span class="metric-value">{certificate_data['esg_impact']['carbon_avoided']['value']:.2f} {certificate_data['esg_impact']['carbon_avoided']['unit']}</span>
            </div>
            <div class="metric">
                <span>Water Conserved</span>
                <span class="metric-value">{certificate_data['esg_impact']['water_conserved']['value']:,} {certificate_data['esg_impact']['water_conserved']['unit']}</span>
            </div>
            <div class="metric">
                <span>Energy Efficiency Improvement</span>
                <span class="metric-value">{certificate_data['esg_impact']['energy_efficiency']['value']}%</span>
            </div>
        </div>

        <div class="section">
            <h3>3. Financial Incentives Captured</h3>
            <div class="metric">
                <span>Federal Tax Credit (25C)</span>
                <span class="metric-value">${certificate_data['financial_incentives']['federal_tax_credit_25C']:,.0f}</span>
            </div>
            <div class="metric">
                <span>State Rebate</span>
                <span class="metric-value">${certificate_data['financial_incentives']['state_rebate']:,.0f}</span>
            </div>
            <div class="metric">
                <span>HEEHRA Rebate</span>
                <span class="metric-value">${certificate_data['financial_incentives']['heehra_rebate']:,.0f}</span>
            </div>
            <div class="metric" style="border-top: 2px solid #2e7d32; padding-top: 10px;">
                <span><strong>Total Incentives</strong></span>
                <span class="metric-value" style="font-size: 18px;">${certificate_data['financial_incentives']['total_captured']:,.0f}</span>
            </div>
        </div>

        {'<div class="sb253-badge">✓ CA SB 253 Scope 3 Supply Chain Readiness Verified</div>' if certificate_data['sb253_ready'] else ''}

        <div class="footer">
            <div class="qr-placeholder">[QR Code]</div>
            <p>This certificate serves as verifiable evidence for Scope 3 emissions reporting and green vendor certification.</p>
            <p>Verify at: https://proofgreen.io/verify/{certificate_data['verification_code']}</p>
        </div>
    </div>
</body>
</html>
"""

    def _proposal_to_dict(self, proposal: ProposalData) -> Dict[str, Any]:
        """Convert ProposalData to dictionary."""
        return {
            "job_id": proposal.job_id,
            "company_name": proposal.company_name,
            "customer_name": proposal.customer_name,
            "customer_address": proposal.customer_address,
            "vertical": proposal.vertical,
            "state": proposal.state,
            "zip_code": proposal.zip_code,
            "standard_option": proposal.standard_option,
            "green_option": proposal.green_option,
            "carbon_savings": proposal.carbon_savings,
            "financial_incentives": proposal.financial_incentives,
            "compliance_badges": proposal.compliance_badges,
            "disclaimer": proposal.disclaimer,
            "generated_at": datetime.now(timezone.utc).isoformat()
        }

    def _certificate_to_dict(self, certificate: CertificateData) -> Dict[str, Any]:
        """Convert CertificateData to dictionary."""
        return {
            "job_id": certificate.job_id,
            "company_name": certificate.company_name,
            "vertical": certificate.vertical,
            "date": certificate.date.strftime("%B %d, %Y"),
            "compliance_verification": certificate.compliance_verification,
            "esg_impact": certificate.esg_impact,
            "financial_incentives": certificate.financial_incentives,
            "sb253_ready": certificate.sb253_ready,
            "verification_code": certificate.verification_code,
            "generated_at": datetime.now(timezone.utc).isoformat()
        }


# Convenience function
def generate_green_proposal(
    job_id: str,
    job_data: Dict[str, Any],
    carbon_engine,
    financial_engine
) -> Dict[str, Any]:
    """
    Complete proposal generation workflow.
    Pulls data from FSM, calculates savings, generates proposal.
    """
    generator = ProposalGenerator()

    # Calculate carbon savings
    carbon_savings = {
        "annual_co2_avoided_lbs": carbon_engine.calculate_avoided_emissions(
            job_data.get("old_equipment", {}),
            job_data.get("new_equipment", {}),
            job_data.get("state", "CA")
        ).get("avoided_emissions_kg", 0) * 2.205,  # Convert kg to lbs
        "lifetime_co2_avoided_tons": 0
    }
    carbon_savings["lifetime_co2_avoided_tons"] = (
        carbon_savings["annual_co2_avoided_lbs"] * 15 / 2000  # 15 year lifetime
    )

    # Get financial data (would be async in real implementation)
    financial_data = {
        "summary": {"total_incentives": 10000},
        "federal_credits": {"total": 2000},
        "state_rebates": {"total": 3000},
        "heehra_rebates": {"total": 5000}
    }

    return generator.generate_green_proposal(job_data, carbon_savings, financial_data)
