"""
ProofGreen MAS - FastAPI Main Application
Multi-Agent System for ESG Compliance and Green Verification
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional
from uuid import UUID, uuid4
from datetime import datetime

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import hmac
import hashlib

# Local imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from app.models import (
    JobCreateRequest, JobResponse, JobStatus,
    ComplianceCheckRequest, ComplianceCheckResponse, ComplianceStatus,
    CarbonCalculationRequest, CarbonCalculationResponse,
    RebateSearchRequest, RebateSearchResponse,
    CertificateGenerateRequest, CertificateResponse,
    WebhookEvent, WebhookResponse,
    AgentTaskRequest, AgentTaskResponse,
    LedgerSummary, CarbonTransaction,
    HealthCheckResponse, SuccessResponse, ErrorResponse,
    ServiceVertical, FSMProvider, EmissionScope
)
from app.logic.regulatory_router import RegulatoryRouter, get_compliance_requirements
from tools.carbon_engine import CarbonEngine
from tools.fsm_connector import FSMConnector, FSMWebhookHandler, NormalizedJob
from agents.orchestrator import GreenVerificationOrchestrator
from agents.auditor import ESGAuditor
from agents.rebate_specialist import RebateSpecialist

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Application state
class AppState:
    """Application state container."""
    orchestrator: Optional[GreenVerificationOrchestrator] = None
    carbon_engine: Optional[CarbonEngine] = None
    fsm_connector: Optional[FSMConnector] = None
    webhook_handler: Optional[FSMWebhookHandler] = None
    regulatory_router: Optional[RegulatoryRouter] = None
    auditor: Optional[ESGAuditor] = None
    rebate_specialist: Optional[RebateSpecialist] = None


app_state = AppState()


# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup application resources."""
    logger.info("Starting ProofGreen MAS...")

    # Initialize components
    app_state.regulatory_router = RegulatoryRouter()

    app_state.carbon_engine = CarbonEngine(
        watttime_username=settings.WATTTIME_USERNAME,
        watttime_password=settings.WATTTIME_PASSWORD
    )

    app_state.fsm_connector = FSMConnector(
        servicetitan_api_key=settings.SERVICETITAN_API_KEY,
        servicetitan_tenant_id=settings.SERVICETITAN_TENANT_ID,
        jobber_api_key=settings.JOBBER_API_KEY,
        housecall_pro_api_key=settings.HOUSECALL_PRO_API_KEY
    )

    app_state.webhook_handler = FSMWebhookHandler(app_state.fsm_connector)

    # Register webhook handlers
    app_state.webhook_handler.on_job_closed(handle_job_closed)

    app_state.auditor = ESGAuditor()
    app_state.rebate_specialist = RebateSpecialist(
        rewiring_america_api_key=settings.REWIRING_AMERICA_API_KEY
    )

    # Initialize orchestrator
    if settings.ANTHROPIC_API_KEY:
        app_state.orchestrator = GreenVerificationOrchestrator(
            anthropic_api_key=settings.ANTHROPIC_API_KEY,
            model=settings.AGENT_MODEL
        )
        logger.info("Agent orchestrator initialized")
    else:
        logger.warning("ANTHROPIC_API_KEY not set - agent features disabled")

    logger.info("ProofGreen MAS started successfully")

    yield

    # Cleanup
    logger.info("Shutting down ProofGreen MAS...")
    if app_state.carbon_engine:
        await app_state.carbon_engine.close()
    if app_state.fsm_connector:
        await app_state.fsm_connector.close()


# Create FastAPI app
app = FastAPI(
    title="ProofGreen MAS",
    description="Multi-Agent System for ESG Compliance and Green Verification",
    version=settings.APP_VERSION,
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Event handler for job closed
async def handle_job_closed(job: NormalizedJob):
    """Handle job closed event - trigger ESG audit."""
    logger.info(f"Processing closed job: {job.id} ({job.vertical})")

    try:
        if app_state.orchestrator:
            # Run full verification workflow
            result = await app_state.orchestrator.process_job({
                "job_id": job.external_id,
                "provider": job.provider.value,
                "zip_code": job.zip_code,
                "state": job.state,
                "vertical": job.vertical,
                "equipment": job.equipment_installed,
                "materials": job.materials_used,
                "notes": job.notes
            })

            # Update FSM with results
            if result.get("certificate_url"):
                await app_state.fsm_connector.attach_document(
                    job.provider,
                    job.external_id,
                    result["certificate_url"],
                    "green_verified"
                )

            # Update Green Verified status
            await app_state.fsm_connector.update_custom_field(
                job.provider,
                job.external_id,
                "ProofGreen_Status",
                "Verified" if result.get("compliance_status") == "compliant" else "Review Required"
            )

            # Create follow-up tasks for compliance gaps
            for issue in result.get("compliance_issues", []):
                await app_state.fsm_connector.create_follow_up_task(
                    job.provider,
                    job.external_id,
                    f"Compliance: {issue['code']}",
                    issue['description'],
                    due_days=14
                )

            logger.info(f"Job {job.id} verification complete: {result.get('compliance_status')}")

    except Exception as e:
        logger.error(f"Error processing job {job.id}: {e}")


# Health check endpoint
@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Health check endpoint."""
    components = {
        "orchestrator": "ok" if app_state.orchestrator else "disabled",
        "carbon_engine": "ok" if app_state.carbon_engine else "error",
        "fsm_connector": "ok" if app_state.fsm_connector else "error",
        "regulatory_router": "ok" if app_state.regulatory_router else "error"
    }

    return HealthCheckResponse(
        status="healthy" if all(v in ["ok", "disabled"] for v in components.values()) else "degraded",
        version=settings.APP_VERSION,
        components=components
    )


# Webhook endpoints
@app.post("/webhooks/servicetitan", response_model=WebhookResponse)
async def servicetitan_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_st_signature: Optional[str] = Header(None)
):
    """ServiceTitan webhook endpoint."""
    body = await request.body()
    payload = await request.json()

    # Verify signature if configured
    # (Signature verification logic would go here)

    event = WebhookEvent(
        provider=FSMProvider.SERVICETITAN,
        event_type=payload.get("eventType", "unknown"),
        timestamp=datetime.now(),
        payload=payload,
        signature=x_st_signature
    )

    # Process webhook in background
    background_tasks.add_task(
        app_state.webhook_handler.process_webhook,
        FSMProvider.SERVICETITAN,
        event.event_type,
        event.payload
    )

    return WebhookResponse(
        status="accepted",
        message="Webhook received and queued for processing",
        processing_id=str(uuid4())
    )


@app.post("/webhooks/jobber", response_model=WebhookResponse)
async def jobber_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_jobber_signature: Optional[str] = Header(None)
):
    """Jobber webhook endpoint."""
    payload = await request.json()

    event = WebhookEvent(
        provider=FSMProvider.JOBBER,
        event_type=payload.get("type", "unknown"),
        timestamp=datetime.now(),
        payload=payload,
        signature=x_jobber_signature
    )

    background_tasks.add_task(
        app_state.webhook_handler.process_webhook,
        FSMProvider.JOBBER,
        event.event_type,
        event.payload
    )

    return WebhookResponse(
        status="accepted",
        message="Webhook received and queued for processing",
        processing_id=str(uuid4())
    )


@app.post("/webhooks/housecall", response_model=WebhookResponse)
async def housecall_webhook(
    request: Request,
    background_tasks: BackgroundTasks
):
    """Housecall Pro webhook endpoint."""
    payload = await request.json()

    event = WebhookEvent(
        provider=FSMProvider.HOUSECALL_PRO,
        event_type=payload.get("event", "unknown"),
        timestamp=datetime.now(),
        payload=payload
    )

    background_tasks.add_task(
        app_state.webhook_handler.process_webhook,
        FSMProvider.HOUSECALL_PRO,
        event.event_type,
        event.payload
    )

    return WebhookResponse(
        status="accepted",
        message="Webhook received and queued for processing",
        processing_id=str(uuid4())
    )


# Compliance endpoints
@app.post("/api/v1/compliance/check", response_model=ComplianceCheckResponse)
async def check_compliance(request: ComplianceCheckRequest):
    """Check compliance for equipment/job."""

    equipment_data = {}
    if request.equipment:
        equipment_data = request.equipment[0].model_dump() if request.equipment else {}

    result = app_state.regulatory_router.check_compliance(
        state=request.state,
        vertical=request.vertical.value,
        equipment_data=equipment_data,
        reporting_standard=request.reporting_standard
    )

    issues = [
        {
            "code": issue["requirement_id"],
            "severity": issue["severity"],
            "category": "compliance",
            "description": issue["description"],
            "regulation": issue["regulation"],
            "recommendation": issue.get("recommendation", "")
        }
        for issue in result.get("issues", [])
    ]

    return ComplianceCheckResponse(
        status=ComplianceStatus(result["status"]),
        score=result["score"],
        issues=issues,
        recommendations=[issue.get("recommendation", "") for issue in result.get("issues", []) if issue.get("recommendation")],
        regulations_checked=result.get("regulations_checked", []),
        future_proof_alerts=[alert["description"] for alert in result.get("future_alerts", [])]
    )


@app.get("/api/v1/compliance/requirements/{state}/{vertical}")
async def get_requirements(state: str, vertical: str):
    """Get compliance requirements for state and vertical."""
    return get_compliance_requirements(state, vertical)


@app.get("/api/v1/compliance/checklist/{state}/{vertical}")
async def get_checklist(state: str, vertical: str):
    """Get compliance checklist for a vertical."""
    return app_state.regulatory_router.get_vertical_checklist(vertical, state)


# Carbon calculation endpoints
@app.post("/api/v1/carbon/calculate", response_model=CarbonCalculationResponse)
async def calculate_carbon(request: CarbonCalculationRequest):
    """Calculate carbon footprint for a job."""

    job_data = {
        "state": request.state,
        "vertical": request.vertical.value,
        "travel_distance_miles": request.travel_distance_miles,
        "vehicle_type": request.vehicle_type,
        "vehicle_mpg": request.vehicle_mpg,
        "electricity_kwh": request.electricity_kwh,
        "fuel_used": request.fuel_used,
        "refrigerant": request.refrigerant,
        "waste": request.waste,
        "equipment_installed": request.equipment_installed,
        "old_equipment": request.old_equipment,
        "new_equipment": request.new_equipment
    }

    result = app_state.carbon_engine.calculate_job_carbon_footprint(job_data)

    scope_breakdown = []
    for scope in ["scope_1", "scope_2", "scope_3"]:
        if result.get(scope):
            scope_breakdown.append({
                "scope": scope,
                "total_kg_co2e": result["totals"][scope],
                "categories": result[scope]
            })

    return CarbonCalculationResponse(
        job_id=request.job_id,
        total_kg_co2e=result["totals"]["total"],
        scope_1_kg=result["totals"]["scope_1"],
        scope_2_kg=result["totals"]["scope_2"],
        scope_3_kg=result["totals"]["scope_3"],
        scope_breakdown=scope_breakdown,
        avoided_emissions_kg=result.get("avoided_emissions", {}).get("avoided_emissions_kg") if result.get("avoided_emissions") else None,
        methodology=result.get("methodology", "GHG Protocol"),
        sources=result.get("sources", [])
    )


@app.get("/api/v1/carbon/grid/{state}")
async def get_grid_carbon(state: str):
    """Get grid carbon intensity for a state."""
    factor, region = app_state.carbon_engine.state_to_egrid.get(state.upper()), None
    egrid_region = app_state.carbon_engine.state_to_egrid.get(state.upper(), "US_AVG")
    factor_obj = app_state.carbon_engine.egrid_factors.get(egrid_region)

    return {
        "state": state,
        "egrid_region": egrid_region,
        "carbon_intensity_kg_kwh": factor_obj.value if factor_obj else 0.386,
        "source": factor_obj.source if factor_obj else "EPA eGRID 2022",
        "year": factor_obj.year if factor_obj else 2024
    }


# Rebate search endpoints
@app.post("/api/v1/rebates/search", response_model=RebateSearchResponse)
async def search_rebates(request: RebateSearchRequest):
    """Search for available rebates and incentives."""

    result = await app_state.rebate_specialist.find_all_incentives(
        state=request.state,
        zip_code=request.zip_code,
        vertical=request.vertical.value,
        equipment_type=request.equipment_type,
        equipment_cost=request.equipment_cost
    )

    return RebateSearchResponse(
        total_available=result.get("total_available", 0),
        federal_credits=result.get("federal_credits", []),
        state_rebates=result.get("state_rebates", []),
        utility_rebates=result.get("utility_rebates", []),
        local_incentives=result.get("local_incentives", []),
        income_qualified_bonuses=result.get("income_qualified", []) if request.income_qualified else []
    )


@app.get("/api/v1/rebates/federal/{equipment_type}")
async def get_federal_credits(equipment_type: str, cost: Optional[float] = None):
    """Get federal tax credits for equipment type."""
    return app_state.rebate_specialist.calculate_federal_credits(
        equipment_type=equipment_type,
        equipment_cost=cost or 10000
    )


# Agent/Task endpoints
@app.post("/api/v1/agents/task", response_model=AgentTaskResponse)
async def run_agent_task(
    request: AgentTaskRequest,
    background_tasks: BackgroundTasks
):
    """Run an agent task."""

    if not app_state.orchestrator:
        raise HTTPException(
            status_code=503,
            detail="Agent orchestrator not available"
        )

    task_id = uuid4()

    # Queue task for background processing
    async def process_task():
        try:
            if request.task_type == "audit":
                result = await app_state.auditor.run_audit(request.parameters)
            elif request.task_type == "rebate_search":
                result = await app_state.rebate_specialist.find_all_incentives(**request.parameters)
            elif request.task_type == "compliance_check":
                result = app_state.regulatory_router.check_compliance(**request.parameters)
            elif request.task_type == "full_verification":
                result = await app_state.orchestrator.process_job(request.parameters)
            else:
                raise ValueError(f"Unknown task type: {request.task_type}")

            # Store result (would go to database in production)
            logger.info(f"Task {task_id} completed")

        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")

    background_tasks.add_task(process_task)

    return AgentTaskResponse(
        task_id=task_id,
        status="queued",
        started_at=datetime.now()
    )


@app.post("/api/v1/agents/verify-job")
async def verify_job(job_data: Dict[str, Any]):
    """Run full verification workflow on a job."""

    if not app_state.orchestrator:
        raise HTTPException(
            status_code=503,
            detail="Agent orchestrator not available"
        )

    result = await app_state.orchestrator.process_job(job_data)
    return result


# Green Ledger endpoints
@app.get("/api/v1/ledger/summary/{company_id}")
async def get_ledger_summary(
    company_id: UUID,
    period: str = "month"  # month, quarter, year
):
    """Get carbon ledger summary for a company."""
    # In production, this would query the database
    return {
        "company_id": str(company_id),
        "period": period,
        "total_emissions_kg": 0,
        "scope_1_total": 0,
        "scope_2_total": 0,
        "scope_3_total": 0,
        "avoided_emissions_kg": 0,
        "job_count": 0,
        "sb253_ready": True,
        "message": "Ledger data would be retrieved from database"
    }


@app.post("/api/v1/ledger/transaction")
async def record_transaction(transaction: CarbonTransaction):
    """Record a carbon transaction to the ledger."""
    # In production, this would save to database
    return {
        "status": "recorded",
        "transaction_id": str(transaction.id),
        "amount_kg_co2e": transaction.amount_kg_co2e
    }


# Certificate endpoints
@app.post("/api/v1/certificates/generate", response_model=CertificateResponse)
async def generate_certificate(request: CertificateGenerateRequest):
    """Generate a Green Verification certificate."""

    # In production, this would generate actual PDF
    verification_code = f"PG-{request.job_id.hex[:8].upper()}"

    return CertificateResponse(
        job_id=request.job_id,
        certificate_type=request.certificate_type,
        public_url=f"https://proofgreen.io/verify/{verification_code}",
        pdf_url=f"https://proofgreen.io/certificates/{verification_code}.pdf",
        qr_code_url=f"https://proofgreen.io/qr/{verification_code}",
        verification_code=verification_code,
        metadata={
            "include_carbon": request.include_carbon_footprint,
            "include_compliance": request.include_compliance_details,
            "include_rebates": request.include_rebates
        }
    )


@app.get("/api/v1/certificates/verify/{code}")
async def verify_certificate(code: str):
    """Verify a certificate by its code."""
    # In production, this would lookup in database
    return {
        "valid": True,
        "code": code,
        "message": "Certificate verification would check database"
    }


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=exc.detail,
            code=str(exc.status_code)
        ).model_dump()
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Internal server error",
            detail=str(exc) if settings.DEBUG else None
        ).model_dump()
    )


# Main entry point
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        workers=1 if settings.DEBUG else settings.WORKERS
    )
