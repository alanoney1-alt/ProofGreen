"""
ProofGreen MAS - Chief of Staff Orchestrator
Coordinates Legal Scout, Incentive Engine, Scheduling Agent, and other specialists.
"""

import asyncio
import json
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from pydantic import BaseModel, Field
import anthropic

from config.settings import settings


class AgentRole(str, Enum):
    """Specialized agent roles in the MAS."""
    LEGAL_SCOUT = "legal_scout"
    INCENTIVE_ENGINE = "incentive_engine"
    SCHEDULING_AGENT = "scheduling_agent"
    COMPLIANCE_CHECKER = "compliance_checker"
    PREDICTIVE_OUTREACH = "predictive_outreach"
    VOICE_TRIAGE = "voice_triage"
    CARBON_ENGINE = "carbon_engine"
    PROPOSAL_GENERATOR = "proposal_generator"


class TaskPriority(str, Enum):
    """Task priority levels."""
    CRITICAL = "critical"    # Emergency calls, compliance deadlines
    HIGH = "high"            # Same-day scheduling, urgent rebates
    MEDIUM = "medium"        # Standard job processing
    LOW = "low"              # Background analysis, reports


class TaskStatus(str, Enum):
    """Task execution status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    AWAITING_HUMAN = "awaiting_human"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AgentTask:
    """A task to be executed by a specialized agent."""
    id: str
    role: AgentRole
    action: str
    parameters: Dict[str, Any]
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict] = None
    error: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    requires_approval: bool = False
    approval_id: Optional[str] = None


@dataclass
class WorkflowContext:
    """Shared context for a workflow execution."""
    workflow_id: str
    company_id: str
    job_id: Optional[str] = None
    customer_id: Optional[str] = None
    trigger: str = "manual"
    data: Dict[str, Any] = field(default_factory=dict)
    tasks_completed: List[str] = field(default_factory=list)
    lessons_cited: List[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.utcnow)


class AgentCapability(BaseModel):
    """Describes what an agent can do."""
    role: AgentRole
    actions: List[str]
    description: str
    requires_approval_for: List[str] = Field(default_factory=list)
    max_concurrent_tasks: int = 5


# Define agent capabilities
AGENT_CAPABILITIES = {
    AgentRole.LEGAL_SCOUT: AgentCapability(
        role=AgentRole.LEGAL_SCOUT,
        actions=["scan_regulations", "check_compliance", "flag_violations", "update_knowledge_base"],
        description="Monitors regulatory changes and checks job compliance",
        requires_approval_for=["update_knowledge_base"]
    ),
    AgentRole.INCENTIVE_ENGINE: AgentCapability(
        role=AgentRole.INCENTIVE_ENGINE,
        actions=["calculate_rebates", "check_eligibility", "generate_rebate_summary", "submit_rebate_application"],
        description="Calculates and processes federal/state rebates and tax credits",
        requires_approval_for=["submit_rebate_application"]
    ),
    AgentRole.SCHEDULING_AGENT: AgentCapability(
        role=AgentRole.SCHEDULING_AGENT,
        actions=["find_available_slots", "schedule_job", "reschedule_job", "optimize_routes", "assign_technician"],
        description="Manages technician scheduling and route optimization",
        requires_approval_for=["schedule_job", "reschedule_job"]
    ),
    AgentRole.COMPLIANCE_CHECKER: AgentCapability(
        role=AgentRole.COMPLIANCE_CHECKER,
        actions=["verify_equipment", "check_refrigerant", "validate_seer2", "generate_certificate"],
        description="Verifies ESG compliance for jobs and equipment",
        requires_approval_for=["generate_certificate"]
    ),
    AgentRole.PREDICTIVE_OUTREACH: AgentCapability(
        role=AgentRole.PREDICTIVE_OUTREACH,
        actions=["analyze_weather", "identify_at_risk_customers", "draft_maintenance_offer", "send_outreach"],
        description="Proactively identifies maintenance opportunities based on weather and history",
        requires_approval_for=["send_outreach"]
    ),
    AgentRole.VOICE_TRIAGE: AgentCapability(
        role=AgentRole.VOICE_TRIAGE,
        actions=["handle_inbound_call", "triage_emergency", "create_service_ticket", "escalate_to_human"],
        description="Handles inbound calls and triages emergencies",
        requires_approval_for=["escalate_to_human"]
    ),
    AgentRole.CARBON_ENGINE: AgentCapability(
        role=AgentRole.CARBON_ENGINE,
        actions=["calculate_emissions", "compute_savings", "generate_esg_report", "update_ledger"],
        description="Calculates carbon footprint and ESG metrics",
        requires_approval_for=["update_ledger"]
    ),
    AgentRole.PROPOSAL_GENERATOR: AgentCapability(
        role=AgentRole.PROPOSAL_GENERATOR,
        actions=["generate_proposal", "create_green_impact_report", "personalize_offer"],
        description="Generates customer proposals with ESG impact",
        requires_approval_for=[]
    ),
}


class ChiefOfStaff:
    """
    Chief of Staff Orchestrator Agent.
    Coordinates all specialized agents, manages workflows, and ensures
    human-in-the-loop for critical decisions.
    """

    def __init__(
        self,
        db_connection=None,
        governance_workflow=None,
        lessons_learned=None
    ):
        """
        Initialize Chief of Staff.

        Args:
            db_connection: PostgreSQL connection
            governance_workflow: GovernanceWorkflow for HITL approvals
            lessons_learned: LessonsLearned for memory/context
        """
        self.db = db_connection
        self.governance = governance_workflow
        self.lessons = lessons_learned
        self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

        # Agent registry
        self.agents: Dict[AgentRole, Any] = {}
        self.capabilities = AGENT_CAPABILITIES

        # Task queue by priority
        self.task_queues: Dict[TaskPriority, asyncio.Queue] = {
            priority: asyncio.Queue() for priority in TaskPriority
        }

        # Active workflows
        self.active_workflows: Dict[str, WorkflowContext] = {}

        # Execution locks per agent
        self.agent_locks: Dict[AgentRole, asyncio.Semaphore] = {
            role: asyncio.Semaphore(cap.max_concurrent_tasks)
            for role, cap in AGENT_CAPABILITIES.items()
        }

    def register_agent(self, role: AgentRole, agent: Any):
        """Register a specialized agent."""
        self.agents[role] = agent

    # ========== WORKFLOW ORCHESTRATION ==========

    async def start_workflow(
        self,
        workflow_type: str,
        company_id: str,
        trigger_data: Dict,
        job_id: Optional[str] = None
    ) -> WorkflowContext:
        """
        Start a new coordinated workflow.

        Args:
            workflow_type: Type of workflow (new_job, emergency_call, weather_alert, etc.)
            company_id: Company identifier
            trigger_data: Data that triggered the workflow
            job_id: Optional job ID if job-specific

        Returns:
            WorkflowContext for tracking
        """
        import uuid
        workflow_id = f"wf_{uuid.uuid4().hex[:12]}"

        context = WorkflowContext(
            workflow_id=workflow_id,
            company_id=company_id,
            job_id=job_id,
            trigger=workflow_type,
            data=trigger_data
        )

        self.active_workflows[workflow_id] = context

        # Consult lessons learned for relevant context
        if self.lessons:
            relevant_lessons = await self.lessons.get_relevant_lessons(
                company_id=company_id,
                context={
                    "workflow_type": workflow_type,
                    "job_type": trigger_data.get("job_type"),
                    "equipment_type": trigger_data.get("equipment_type"),
                    "state": trigger_data.get("state")
                }
            )
            context.lessons_cited = [l["id"] for l in relevant_lessons]
            context.data["lessons_context"] = relevant_lessons

        # Determine workflow tasks based on type
        tasks = await self._plan_workflow(workflow_type, context)

        # Execute workflow
        await self._execute_workflow(context, tasks)

        return context

    async def _plan_workflow(
        self,
        workflow_type: str,
        context: WorkflowContext
    ) -> List[AgentTask]:
        """
        Use Claude to plan the workflow tasks.
        """
        planning_prompt = f"""You are the Chief of Staff orchestrator for ProofGreen ESG Multi-Agent System.

Plan the workflow for: {workflow_type}

Context:
{json.dumps(context.data, indent=2, default=str)}

Available Agents and their capabilities:
{json.dumps({role.value: cap.dict() for role, cap in self.capabilities.items()}, indent=2)}

Lessons from past jobs (cite these when relevant):
{json.dumps(context.data.get('lessons_context', []), indent=2, default=str)}

Return a JSON array of tasks in execution order. Each task should have:
- id: unique task ID
- role: agent role (from available agents)
- action: specific action to perform
- parameters: dict of parameters
- priority: critical/high/medium/low
- dependencies: list of task IDs that must complete first
- requires_approval: boolean if human approval needed

Example:
[
  {{"id": "t1", "role": "legal_scout", "action": "check_compliance", "parameters": {{"state": "CA"}}, "priority": "high", "dependencies": [], "requires_approval": false}},
  {{"id": "t2", "role": "incentive_engine", "action": "calculate_rebates", "parameters": {{}}, "priority": "medium", "dependencies": ["t1"], "requires_approval": false}}
]

Return ONLY the JSON array, no other text."""

        response = self.client.messages.create(
            model=settings.AGENT_MODEL,
            max_tokens=2000,
            temperature=0.1,
            messages=[{"role": "user", "content": planning_prompt}]
        )

        try:
            tasks_json = json.loads(response.content[0].text)
            tasks = []
            for t in tasks_json:
                task = AgentTask(
                    id=t["id"],
                    role=AgentRole(t["role"]),
                    action=t["action"],
                    parameters=t.get("parameters", {}),
                    priority=TaskPriority(t.get("priority", "medium")),
                    dependencies=t.get("dependencies", []),
                    requires_approval=t.get("requires_approval", False)
                )
                tasks.append(task)
            return tasks
        except (json.JSONDecodeError, KeyError) as e:
            # Fallback to standard workflow
            return self._get_standard_workflow(workflow_type, context)

    def _get_standard_workflow(
        self,
        workflow_type: str,
        context: WorkflowContext
    ) -> List[AgentTask]:
        """Fallback standard workflows when planning fails."""
        workflows = {
            "new_job": [
                AgentTask(id="t1", role=AgentRole.LEGAL_SCOUT, action="check_compliance",
                         parameters={"state": context.data.get("state", "CA")}),
                AgentTask(id="t2", role=AgentRole.COMPLIANCE_CHECKER, action="verify_equipment",
                         parameters={}, dependencies=["t1"]),
                AgentTask(id="t3", role=AgentRole.INCENTIVE_ENGINE, action="calculate_rebates",
                         parameters={}, dependencies=["t2"]),
                AgentTask(id="t4", role=AgentRole.CARBON_ENGINE, action="calculate_emissions",
                         parameters={}, dependencies=["t2"]),
                AgentTask(id="t5", role=AgentRole.PROPOSAL_GENERATOR, action="generate_proposal",
                         parameters={}, dependencies=["t3", "t4"]),
            ],
            "emergency_call": [
                AgentTask(id="t1", role=AgentRole.VOICE_TRIAGE, action="triage_emergency",
                         parameters={}, priority=TaskPriority.CRITICAL),
                AgentTask(id="t2", role=AgentRole.SCHEDULING_AGENT, action="find_available_slots",
                         parameters={"urgent": True}, dependencies=["t1"], priority=TaskPriority.CRITICAL),
                AgentTask(id="t3", role=AgentRole.SCHEDULING_AGENT, action="assign_technician",
                         parameters={}, dependencies=["t2"], requires_approval=True),
            ],
            "weather_alert": [
                AgentTask(id="t1", role=AgentRole.PREDICTIVE_OUTREACH, action="analyze_weather",
                         parameters={}),
                AgentTask(id="t2", role=AgentRole.PREDICTIVE_OUTREACH, action="identify_at_risk_customers",
                         parameters={}, dependencies=["t1"]),
                AgentTask(id="t3", role=AgentRole.PREDICTIVE_OUTREACH, action="draft_maintenance_offer",
                         parameters={}, dependencies=["t2"]),
                AgentTask(id="t4", role=AgentRole.PREDICTIVE_OUTREACH, action="send_outreach",
                         parameters={}, dependencies=["t3"], requires_approval=True),
            ],
            "job_complete": [
                AgentTask(id="t1", role=AgentRole.COMPLIANCE_CHECKER, action="verify_equipment",
                         parameters={}),
                AgentTask(id="t2", role=AgentRole.CARBON_ENGINE, action="calculate_emissions",
                         parameters={}, dependencies=["t1"]),
                AgentTask(id="t3", role=AgentRole.CARBON_ENGINE, action="update_ledger",
                         parameters={}, dependencies=["t2"], requires_approval=True),
                AgentTask(id="t4", role=AgentRole.COMPLIANCE_CHECKER, action="generate_certificate",
                         parameters={}, dependencies=["t3"], requires_approval=True),
            ],
        }

        return workflows.get(workflow_type, workflows["new_job"])

    async def _execute_workflow(
        self,
        context: WorkflowContext,
        tasks: List[AgentTask]
    ):
        """Execute workflow tasks respecting dependencies and approvals."""
        task_map = {t.id: t for t in tasks}
        completed = set()
        pending = {t.id for t in tasks}

        while pending:
            # Find tasks ready to execute (dependencies satisfied)
            ready = [
                task_map[tid] for tid in pending
                if all(dep in completed for dep in task_map[tid].dependencies)
            ]

            if not ready:
                # Deadlock or waiting for approvals
                await asyncio.sleep(1)
                continue

            # Execute ready tasks in parallel (respecting priority)
            ready.sort(key=lambda t: list(TaskPriority).index(t.priority))

            execution_tasks = []
            for task in ready:
                execution_tasks.append(self._execute_task(task, context))

            results = await asyncio.gather(*execution_tasks, return_exceptions=True)

            # Process results
            for task, result in zip(ready, results):
                if isinstance(result, Exception):
                    task.status = TaskStatus.FAILED
                    task.error = str(result)
                else:
                    task.result = result
                    if task.status != TaskStatus.AWAITING_HUMAN:
                        task.status = TaskStatus.COMPLETED
                        completed.add(task.id)
                        context.tasks_completed.append(task.id)

                pending.discard(task.id)

    async def _execute_task(
        self,
        task: AgentTask,
        context: WorkflowContext
    ) -> Dict:
        """Execute a single task using the appropriate agent."""
        task.status = TaskStatus.IN_PROGRESS
        task.started_at = datetime.utcnow()

        # Check if approval required
        if task.requires_approval and self.governance:
            approval_result = await self.governance.request_approval(
                action=f"{task.role.value}.{task.action}",
                description=f"Execute {task.action} for workflow {context.workflow_id}",
                data=task.parameters,
                company_id=context.company_id,
                job_id=context.job_id
            )
            task.approval_id = approval_result.get("approval_id")
            task.status = TaskStatus.AWAITING_HUMAN
            return {"awaiting_approval": True, "approval_id": task.approval_id}

        # Get agent and execute
        agent = self.agents.get(task.role)
        if not agent:
            raise ValueError(f"Agent {task.role.value} not registered")

        # Acquire semaphore for rate limiting
        async with self.agent_locks[task.role]:
            # Inject context and lessons into parameters
            params = {
                **task.parameters,
                "workflow_context": context.data,
                "lessons_cited": context.data.get("lessons_context", [])
            }

            # Call agent method
            method = getattr(agent, task.action, None)
            if not method:
                raise ValueError(f"Agent {task.role.value} has no action {task.action}")

            if asyncio.iscoroutinefunction(method):
                result = await method(**params)
            else:
                result = method(**params)

            task.completed_at = datetime.utcnow()
            return result

    # ========== REAL-TIME COORDINATION ==========

    async def handle_event(
        self,
        event_type: str,
        event_data: Dict,
        company_id: str
    ) -> Dict:
        """
        Handle real-time events and coordinate appropriate response.

        Args:
            event_type: Type of event (webhook, call, alert, etc.)
            event_data: Event payload
            company_id: Company identifier

        Returns:
            Response with workflow status
        """
        # Map events to workflow types
        event_workflow_map = {
            "fsm.job.created": "new_job",
            "fsm.job.completed": "job_complete",
            "fsm.estimate.approved": "new_job",
            "voice.inbound_call": "emergency_call",
            "weather.severe_alert": "weather_alert",
            "schedule.conflict": "reschedule",
            "compliance.violation_detected": "compliance_review",
        }

        workflow_type = event_workflow_map.get(event_type, "generic")

        context = await self.start_workflow(
            workflow_type=workflow_type,
            company_id=company_id,
            trigger_data=event_data,
            job_id=event_data.get("job_id")
        )

        return {
            "workflow_id": context.workflow_id,
            "status": "started",
            "tasks_planned": len(context.tasks_completed),
            "lessons_applied": len(context.lessons_cited)
        }

    async def process_approval(
        self,
        approval_id: str,
        approved: bool,
        approver_id: str,
        approver_notes: Optional[str] = None
    ) -> Dict:
        """
        Process a human approval decision and continue workflow.
        """
        # Find workflow with this approval
        for workflow_id, context in self.active_workflows.items():
            # Check if any task is awaiting this approval
            # (In production, this would query the database)
            pass

        if self.governance:
            result = await self.governance.process_approval(
                approval_id=approval_id,
                approved=approved,
                approver_id=approver_id,
                notes=approver_notes
            )
            return result

        return {"error": "Governance workflow not configured"}

    # ========== AGENT COMMUNICATION ==========

    async def delegate_to_agent(
        self,
        role: AgentRole,
        action: str,
        parameters: Dict,
        priority: TaskPriority = TaskPriority.MEDIUM,
        requires_approval: bool = False
    ) -> Dict:
        """
        Directly delegate a task to a specific agent.
        """
        import uuid
        task = AgentTask(
            id=f"task_{uuid.uuid4().hex[:8]}",
            role=role,
            action=action,
            parameters=parameters,
            priority=priority,
            requires_approval=requires_approval
        )

        # Create minimal context
        context = WorkflowContext(
            workflow_id=f"direct_{task.id}",
            company_id=parameters.get("company_id", "default"),
            data=parameters
        )

        result = await self._execute_task(task, context)
        return result

    async def broadcast_to_agents(
        self,
        message: str,
        data: Dict,
        roles: Optional[List[AgentRole]] = None
    ) -> Dict[AgentRole, Any]:
        """
        Broadcast information to multiple agents.
        Useful for regulatory updates, system alerts, etc.
        """
        target_roles = roles or list(self.agents.keys())
        results = {}

        for role in target_roles:
            agent = self.agents.get(role)
            if agent and hasattr(agent, "receive_broadcast"):
                try:
                    if asyncio.iscoroutinefunction(agent.receive_broadcast):
                        result = await agent.receive_broadcast(message, data)
                    else:
                        result = agent.receive_broadcast(message, data)
                    results[role] = result
                except Exception as e:
                    results[role] = {"error": str(e)}

        return results

    # ========== STATUS & MONITORING ==========

    def get_workflow_status(self, workflow_id: str) -> Optional[Dict]:
        """Get status of a workflow."""
        context = self.active_workflows.get(workflow_id)
        if not context:
            return None

        return {
            "workflow_id": workflow_id,
            "company_id": context.company_id,
            "job_id": context.job_id,
            "trigger": context.trigger,
            "started_at": context.started_at.isoformat(),
            "tasks_completed": context.tasks_completed,
            "lessons_cited": context.lessons_cited
        }

    def get_agent_status(self) -> Dict:
        """Get status of all registered agents."""
        return {
            role.value: {
                "registered": role in self.agents,
                "capabilities": self.capabilities[role].actions if role in self.capabilities else [],
                "active_tasks": self.capabilities[role].max_concurrent_tasks - self.agent_locks[role]._value
            }
            for role in AgentRole
        }


# Singleton instance
chief_of_staff = ChiefOfStaff()
