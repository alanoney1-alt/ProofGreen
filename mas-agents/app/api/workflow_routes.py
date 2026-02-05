"""
ProofGreen MAS - Workflow API Routes
FastAPI endpoints for ESG LangGraph workflow with FSM webhook integration.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Request, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime
import json
import hmac
import hashlib
import asyncio

from config.settings import settings
from workflows.esg_langgraph import (
    ESGWorkflow,
    AgentState,
    WorkflowStatus,
    get_esg_workflow
)
from app.db.green_ledger import get_green_ledger


router = APIRouter(prefix="/api/v1/workflows", tags=["workflows"])


# ========== REQUEST MODELS ==========

class StartWorkflowRequest(BaseModel):
    """Request to start ESG workflow."""
    job_id: str
    company_id: str
    customer_id: Optional[str] = None
    zip_code: str
    state: str = "CA"
    equipment_photo_url: Optional[str] = None
    equipment_data: Optional[Dict] = None


class ApprovalRequest(BaseModel):
    """Request to approve/reject workflow."""
    job_id: str
    approved: bool
    approver_id: str
    approver_name: str
    notes: Optional[str] = None


class FSMWebhookPayload(BaseModel):
    """Generic FSM webhook payload."""
    event_type: str
    job_id: Optional[str] = None
    data: Dict = Field(default_factory=dict)


# ========== WORKFLOW ENDPOINTS ==========

@router.post("/start")
async def start_workflow(
    request: StartWorkflowRequest,
    background_tasks: BackgroundTasks
):
    """
    Start a new ESG verification workflow.

    The workflow will:
    1. Analyze equipment photo (Vision OCR)
    2. Check regulatory compliance
    3. Calculate incentives
    4. Pause for approval if incentives > $500
    5. Save to Green Ledger on completion
    """
    workflow = await get_esg_workflow()

    # Create initial state
    initial_state: AgentState = {
        "job_id": request.job_id,
        "company_id": request.company_id,
        "customer_id": request.customer_id,
        "zip_code": request.zip_code,
        "state": request.state,
        "equipment_photo_url": request.equipment_photo_url,
        "equipment_data": request.equipment_data,
        "compliance_report": None,
        "is_compliant": False,
        "violations": [],
        "compliance_risk_score": 0,
        "incentives": [],
        "total_incentive_amount": 0.0,
        "carbon_baseline": 0.0,
        "carbon_savings": 0.0,
        "requires_approval": False,
        "approval_status": None,
        "approval_notes": None,
        "status": WorkflowStatus.RUNNING.value,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "checkpointed_at": None
    }

    # Run workflow in background
    background_tasks.add_task(run_workflow_background, workflow, initial_state)

    return {
        "status": "started",
        "job_id": request.job_id,
        "message": "ESG verification workflow started. Check status endpoint for updates."
    }


async def run_workflow_background(workflow: ESGWorkflow, state: AgentState):
    """Run workflow in background and save to ledger on completion."""
    try:
        final_state = await workflow.run(state)

        # Save to Green Ledger if completed
        if final_state.get("status") == WorkflowStatus.COMPLETED.value:
            ledger = await get_green_ledger()
            await ledger.save_entry(
                job_id=final_state["job_id"],
                company_id=final_state["company_id"],
                state=final_state
            )

    except Exception as e:
        print(f"Workflow error for job {state['job_id']}: {e}")


@router.get("/status/{job_id}")
async def get_workflow_status(job_id: str):
    """Get current status of a workflow."""
    workflow = await get_esg_workflow()

    if workflow.checkpointer:
        state = await workflow.checkpointer.load_checkpoint(job_id)
        if state:
            return {
                "job_id": job_id,
                "status": state.get("status"),
                "is_compliant": state.get("is_compliant"),
                "requires_approval": state.get("requires_approval"),
                "approval_status": state.get("approval_status"),
                "total_incentive_amount": state.get("total_incentive_amount"),
                "violations": state.get("violations", []),
                "updated_at": state.get("updated_at")
            }

    # Check Green Ledger for completed workflows
    ledger = await get_green_ledger()
    entry = await ledger.get_entry(job_id)
    if entry:
        return {
            "job_id": job_id,
            "status": entry.get("workflow_status"),
            "is_compliant": entry.get("is_compliant"),
            "total_incentive_amount": entry.get("total_incentive_amount"),
            "completed_at": entry.get("completed_at")
        }

    raise HTTPException(status_code=404, detail=f"Workflow not found for job {job_id}")


@router.post("/approve")
async def approve_workflow(
    request: ApprovalRequest,
    background_tasks: BackgroundTasks
):
    """
    Approve or reject a paused workflow.

    After approval, the workflow will resume and complete.
    """
    workflow = await get_esg_workflow()

    if not workflow.checkpointer:
        raise HTTPException(status_code=500, detail="Checkpointer not configured")

    # Update approval status
    success = await workflow.checkpointer.update_approval(
        job_id=request.job_id,
        approved=request.approved,
        approver_id=request.approver_id,
        notes=request.notes
    )

    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"No pending workflow found for job {request.job_id}"
        )

    # Resume workflow if approved
    if request.approved:
        state = await workflow.checkpointer.load_checkpoint(request.job_id)
        if state:
            background_tasks.add_task(run_workflow_background, workflow, state)

    return {
        "job_id": request.job_id,
        "approved": request.approved,
        "message": "Workflow resumed" if request.approved else "Workflow rejected"
    }


@router.get("/pending")
async def get_pending_approvals(company_id: Optional[str] = None):
    """Get all workflows pending approval."""
    workflow = await get_esg_workflow()

    if not workflow.checkpointer:
        return {"pending": []}

    pending = await workflow.checkpointer.get_pending_approvals(company_id)

    return {
        "count": len(pending),
        "pending": [
            {
                "job_id": p["job_id"],
                "company_id": p.get("company_id"),
                "total_incentive_amount": p["state"].get("total_incentive_amount"),
                "violations": p["state"].get("violations", []),
                "created_at": p["created_at"]
            }
            for p in pending
        ]
    }


# ========== FSM WEBHOOK ENDPOINTS ==========

@router.post("/webhooks/servicetitan")
async def servicetitan_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_st_signature: Optional[str] = Header(None, alias="X-ST-Signature")
):
    """
    ServiceTitan webhook endpoint.
    Triggers ESG workflow when a job is 'Closed'.
    """
    body = await request.body()

    # Verify webhook signature
    if settings.SERVICETITAN_WEBHOOK_SECRET:
        expected_sig = hmac.new(
            settings.SERVICETITAN_WEBHOOK_SECRET.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        if x_st_signature != expected_sig:
            raise HTTPException(status_code=401, detail="Invalid signature")

    payload = json.loads(body)
    event_type = payload.get("event_type", "")
    job_data = payload.get("data", {})

    # Trigger workflow on job closed
    if event_type == "job.closed" or job_data.get("status") == "Closed":
        workflow_request = StartWorkflowRequest(
            job_id=job_data.get("id", job_data.get("job_id")),
            company_id=job_data.get("tenant_id", "servicetitan"),
            customer_id=job_data.get("customer_id"),
            zip_code=job_data.get("location", {}).get("zip", ""),
            state=job_data.get("location", {}).get("state", "CA"),
            equipment_photo_url=job_data.get("photos", [{}])[0].get("url") if job_data.get("photos") else None
        )

        await start_workflow(workflow_request, background_tasks)

        return {"status": "workflow_started", "job_id": workflow_request.job_id}

    return {"status": "acknowledged", "event_type": event_type}


@router.post("/webhooks/jobber")
async def jobber_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_jobber_signature: Optional[str] = Header(None, alias="X-Jobber-Signature")
):
    """
    Jobber webhook endpoint.
    Triggers ESG workflow when a job is completed.
    """
    body = await request.body()

    # Verify webhook signature
    if settings.JOBBER_WEBHOOK_SECRET:
        expected_sig = hmac.new(
            settings.JOBBER_WEBHOOK_SECRET.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        if x_jobber_signature != expected_sig:
            raise HTTPException(status_code=401, detail="Invalid signature")

    payload = json.loads(body)
    event_type = payload.get("event", "")
    job_data = payload.get("job", {})

    # Trigger workflow on job completed
    if event_type == "job.completed" or job_data.get("status") == "completed":
        property_data = job_data.get("property", {})

        workflow_request = StartWorkflowRequest(
            job_id=str(job_data.get("id")),
            company_id=payload.get("account_id", "jobber"),
            customer_id=str(job_data.get("client", {}).get("id")),
            zip_code=property_data.get("postal_code", ""),
            state=property_data.get("province", "CA"),
            equipment_photo_url=job_data.get("attachments", [{}])[0].get("url") if job_data.get("attachments") else None
        )

        await start_workflow(workflow_request, background_tasks)

        return {"status": "workflow_started", "job_id": workflow_request.job_id}

    return {"status": "acknowledged", "event_type": event_type}


@router.post("/webhooks/housecall-pro")
async def housecall_pro_webhook(
    request: Request,
    background_tasks: BackgroundTasks
):
    """
    Housecall Pro webhook endpoint.
    Triggers ESG workflow when a job is marked complete.
    """
    body = await request.body()
    payload = json.loads(body)

    event_type = payload.get("event_type", "")
    job_data = payload.get("job", payload.get("data", {}))

    # Trigger workflow on job completed
    if event_type in ["job.completed", "job.closed"]:
        address = job_data.get("address", {})

        workflow_request = StartWorkflowRequest(
            job_id=str(job_data.get("id")),
            company_id=payload.get("company_id", "housecall"),
            customer_id=str(job_data.get("customer_id")),
            zip_code=address.get("zip", ""),
            state=address.get("state", "CA"),
            equipment_photo_url=None  # Housecall Pro photos handled separately
        )

        await start_workflow(workflow_request, background_tasks)

        return {"status": "workflow_started", "job_id": workflow_request.job_id}

    return {"status": "acknowledged", "event_type": event_type}


@router.post("/webhooks/generic")
async def generic_fsm_webhook(
    request: Request,
    payload: FSMWebhookPayload,
    background_tasks: BackgroundTasks
):
    """
    Generic FSM webhook endpoint.
    Use this for custom integrations or testing.
    """
    # Check for job completion events
    completion_events = ["job.closed", "job.completed", "work_order.completed", "invoice.finalized"]

    if payload.event_type in completion_events:
        job_data = payload.data

        workflow_request = StartWorkflowRequest(
            job_id=payload.job_id or job_data.get("job_id", job_data.get("id")),
            company_id=job_data.get("company_id", "generic"),
            customer_id=job_data.get("customer_id"),
            zip_code=job_data.get("zip_code", job_data.get("zip", "")),
            state=job_data.get("state", "CA"),
            equipment_photo_url=job_data.get("equipment_photo_url"),
            equipment_data=job_data.get("equipment_data")
        )

        await start_workflow(workflow_request, background_tasks)

        return {"status": "workflow_started", "job_id": workflow_request.job_id}

    return {"status": "acknowledged", "event_type": payload.event_type}


# ========== LEDGER ENDPOINTS ==========

@router.get("/ledger/{job_id}")
async def get_ledger_entry(job_id: str):
    """Get Green Ledger entry for a job."""
    ledger = await get_green_ledger()
    entry = await ledger.get_entry(job_id)

    if not entry:
        raise HTTPException(status_code=404, detail=f"Ledger entry not found for job {job_id}")

    return entry


@router.get("/ledger/company/{company_id}")
async def get_company_ledger(
    company_id: str,
    limit: int = 100
):
    """Get all ledger entries for a company."""
    ledger = await get_green_ledger()
    entries = await ledger.get_company_ledger(company_id, limit=limit)

    return {
        "company_id": company_id,
        "count": len(entries),
        "entries": entries
    }


@router.get("/ledger/company/{company_id}/metrics")
async def get_company_metrics(
    company_id: str,
    period: str = "month"
):
    """Get aggregated ESG metrics for a company."""
    ledger = await get_green_ledger()
    metrics = await ledger.get_aggregated_metrics(company_id, period)

    return {
        "company_id": company_id,
        **metrics
    }
