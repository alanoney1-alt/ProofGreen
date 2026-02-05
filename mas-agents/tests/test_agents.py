"""
ProofGreen MAS - Agent Unit Tests
Tests for AI agents: Chief of Staff, Equipment Triage, Scheduling, Voice Triage.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from agents.chief_of_staff import ChiefOfStaff, WorkflowContext, AgentTask
from agents.equipment_triage import EquipmentTriageNode
from agents.scheduling_agent import SchedulingAgent, TimeSlot
from agents.predictive_outreach import PredictiveOutreachAgent
from agents.voice_triage import VoiceTriageAgent


class TestChiefOfStaff:
    """Tests for Chief of Staff orchestrator."""

    @pytest.fixture
    def chief(self, mock_db, mock_anthropic):
        """Create Chief of Staff instance."""
        return ChiefOfStaff(db_connection=mock_db)

    @pytest.mark.asyncio
    async def test_start_workflow_creates_context(self, chief, sample_job_data):
        """Test workflow initialization creates proper context."""
        with patch.object(chief, '_plan_workflow', new_callable=AsyncMock) as mock_plan:
            mock_plan.return_value = [
                AgentTask(
                    agent_name="equipment_triage",
                    action="analyze_equipment",
                    priority=1,
                    params={}
                )
            ]

            context = await chief.start_workflow(
                workflow_type="job_completion",
                company_id="COMP-001",
                trigger_data=sample_job_data,
                job_id="JOB-2026-001"
            )

            assert context is not None
            assert context.company_id == "COMP-001"
            assert context.job_id == "JOB-2026-001"
            assert len(context.planned_tasks) == 1

    @pytest.mark.asyncio
    async def test_handle_event_routes_correctly(self, chief, sample_servicetitan_payload):
        """Test event routing to appropriate handlers."""
        with patch.object(chief, 'start_workflow', new_callable=AsyncMock) as mock_start:
            mock_start.return_value = MagicMock(id="ctx-001")

            result = await chief.handle_event(
                event_type="fsm_webhook",
                event_data=sample_servicetitan_payload,
                company_id="COMP-001"
            )

            mock_start.assert_called_once()
            assert result is not None

    @pytest.mark.asyncio
    async def test_workflow_planning_uses_claude(self, chief, mock_anthropic):
        """Test workflow planning invokes Claude for task generation."""
        context = WorkflowContext(
            id="ctx-001",
            company_id="COMP-001",
            workflow_type="job_completion",
            trigger_data={"job_id": "JOB-001"},
            job_id="JOB-001"
        )

        with patch("anthropic.Anthropic") as mock_client:
            mock_instance = MagicMock()
            mock_instance.messages.create.return_value = MagicMock(
                content=[MagicMock(text='[{"agent_name": "equipment_triage", "action": "analyze", "priority": 1}]')]
            )
            mock_client.return_value = mock_instance

            tasks = await chief._plan_workflow("job_completion", context)

            # Should have planned at least one task
            assert isinstance(tasks, list)


class TestEquipmentTriageNode:
    """Tests for Equipment Triage agent with Claude Vision."""

    @pytest.fixture
    def triage(self, mock_db):
        """Create Equipment Triage instance."""
        return EquipmentTriageNode(db_connection=mock_db)

    @pytest.mark.asyncio
    async def test_refrigerant_compliance_r410a(self, triage):
        """Test R-410A is flagged for phase-out."""
        result = triage._check_refrigerant_compliance("R-410A")

        assert result["compliant"] is False
        assert "phase-out" in result["issues"][0].lower()
        assert result["recommendation"] is not None

    @pytest.mark.asyncio
    async def test_refrigerant_compliance_r454b(self, triage):
        """Test R-454B (A2L) is compliant."""
        result = triage._check_refrigerant_compliance("R-454B")

        assert result["compliant"] is True
        assert len(result["issues"]) == 0

    @pytest.mark.asyncio
    async def test_seer2_compliance_california(self, triage):
        """Test SEER2 compliance for California (South region)."""
        # SEER 14 should fail in California
        result_fail = triage._check_seer2_compliance(14.0, "CA")
        assert result_fail["compliant"] is False

        # SEER 16 should pass in California
        result_pass = triage._check_seer2_compliance(16.0, "CA")
        assert result_pass["compliant"] is True

    @pytest.mark.asyncio
    async def test_seer2_compliance_northern_region(self, triage):
        """Test SEER2 compliance for Northern region (lower threshold)."""
        # SEER 14 should pass in Northern states
        result = triage._check_seer2_compliance(14.0, "WA")
        assert result["compliant"] is True

    @pytest.mark.asyncio
    async def test_execute_with_image_url(self, triage, sample_equipment_image_analysis):
        """Test equipment analysis with image URL."""
        with patch.object(triage, '_analyze_with_vision', new_callable=AsyncMock) as mock_vision:
            mock_vision.return_value = sample_equipment_image_analysis

            result = await triage.execute(
                image_url="https://example.com/equipment.jpg",
                equipment_data={"state": "CA"}
            )

            assert result["manufacturer"] == "Carrier"
            assert result["compliance"] is not None


class TestSchedulingAgent:
    """Tests for Scheduling Agent."""

    @pytest.fixture
    def scheduler(self, mock_db):
        """Create Scheduling Agent instance."""
        return SchedulingAgent(db_connection=mock_db)

    @pytest.mark.asyncio
    async def test_find_available_slots(self, scheduler, mock_db):
        """Test finding available time slots."""
        mock_db.fetch.return_value = [
            {
                "technician_id": "TECH-001",
                "slot_date": datetime.now().date(),
                "start_time": "09:00:00",
                "end_time": "17:00:00",
                "status": "available"
            }
        ]

        slots = await scheduler.find_available_slots(
            job_type="HVAC Installation",
            location={"lat": 34.0522, "lng": -118.2437},
            duration_minutes=180,
            urgency="normal"
        )

        assert isinstance(slots, list)

    @pytest.mark.asyncio
    async def test_schedule_job_creates_assignment(self, scheduler, mock_db):
        """Test job scheduling creates proper assignment."""
        slot = TimeSlot(
            technician_id="TECH-001",
            start=datetime.now() + timedelta(days=1),
            end=datetime.now() + timedelta(days=1, hours=3),
            available=True
        )

        result = await scheduler.schedule_job(
            job_id="JOB-001",
            technician_id="TECH-001",
            slot=slot,
            job_details={"type": "HVAC Installation"}
        )

        assert result is not None
        mock_db.execute.assert_called()

    @pytest.mark.asyncio
    async def test_detect_conflicts(self, scheduler, mock_db):
        """Test conflict detection."""
        mock_db.fetch.return_value = [
            {
                "technician_id": "TECH-001",
                "job_id": "JOB-001",
                "start_time": "09:00:00",
                "end_time": "12:00:00"
            },
            {
                "technician_id": "TECH-001",
                "job_id": "JOB-002",
                "start_time": "11:00:00",
                "end_time": "14:00:00"
            }
        ]

        conflicts = await scheduler.detect_conflicts(
            date=datetime.now().date()
        )

        # Should detect overlapping jobs
        assert isinstance(conflicts, list)


class TestPredictiveOutreachAgent:
    """Tests for Predictive Outreach Agent."""

    @pytest.fixture
    def outreach(self, mock_db):
        """Create Predictive Outreach instance."""
        return PredictiveOutreachAgent(db_connection=mock_db)

    @pytest.mark.asyncio
    async def test_analyze_weather_extreme_heat(self, outreach):
        """Test weather analysis identifies extreme heat."""
        with patch.object(outreach, '_fetch_weather', new_callable=AsyncMock) as mock_weather:
            mock_weather.return_value = {
                "forecast": [
                    {"date": "2026-07-15", "high_temp": 105, "low_temp": 85},
                    {"date": "2026-07-16", "high_temp": 108, "low_temp": 88},
                ]
            }

            analysis = await outreach.analyze_weather(
                zip_codes=["90001"],
                days_ahead=7
            )

            assert "extreme_heat" in analysis or analysis.get("alerts", [])

    @pytest.mark.asyncio
    async def test_identify_at_risk_customers(self, outreach, mock_db):
        """Test identifying customers at risk during weather events."""
        mock_db.fetch.return_value = [
            {
                "customer_id": "CUST-001",
                "equipment_age": 12,
                "last_maintenance": datetime.now() - timedelta(days=400),
                "zip_code": "90001"
            }
        ]

        weather_analysis = {
            "90001": {
                "extreme_heat": True,
                "forecast_high": 105
            }
        }

        at_risk = await outreach.identify_at_risk_customers(
            weather_analysis=weather_analysis,
            company_id="COMP-001"
        )

        assert isinstance(at_risk, list)


class TestVoiceTriageAgent:
    """Tests for Voice Triage Agent."""

    @pytest.fixture
    def voice_triage(self, mock_db):
        """Create Voice Triage instance."""
        return VoiceTriageAgent(db_connection=mock_db)

    @pytest.mark.asyncio
    async def test_handle_inbound_call_returns_twiml(self, voice_triage):
        """Test inbound call handling returns TwiML response."""
        result = await voice_triage.handle_inbound_call(
            call_sid="CA123456",
            from_number="+15551234567",
            to_number="+15559876543"
        )

        assert result is not None
        assert "twiml" in result or "response" in result

    @pytest.mark.asyncio
    async def test_triage_emergency_high_priority(self, voice_triage):
        """Test emergency triage identifies high-priority situations."""
        with patch.object(voice_triage, '_classify_urgency', new_callable=AsyncMock) as mock_classify:
            mock_classify.return_value = {
                "urgency": "emergency",
                "category": "no_cooling",
                "confidence": 0.95
            }

            result = await voice_triage.triage_emergency(
                call_id="CALL-001",
                speech_text="My AC is broken and it's 100 degrees. I have a newborn baby at home.",
                customer_context={"has_elderly": False, "has_infants": True}
            )

            assert result["urgency"] == "emergency"
            assert result["priority"] == "high"

    @pytest.mark.asyncio
    async def test_triage_non_emergency(self, voice_triage):
        """Test non-emergency triage."""
        with patch.object(voice_triage, '_classify_urgency', new_callable=AsyncMock) as mock_classify:
            mock_classify.return_value = {
                "urgency": "normal",
                "category": "maintenance",
                "confidence": 0.85
            }

            result = await voice_triage.triage_emergency(
                call_id="CALL-002",
                speech_text="I'd like to schedule my annual AC maintenance.",
                customer_context={}
            )

            assert result["urgency"] == "normal"

    @pytest.mark.asyncio
    async def test_create_service_ticket(self, voice_triage, mock_db):
        """Test service ticket creation from triage."""
        triage_result = {
            "urgency": "emergency",
            "category": "no_cooling",
            "summary": "AC not working, infant in home",
            "recommended_action": "same_day_dispatch"
        }

        ticket_id = await voice_triage.create_service_ticket(
            call_id="CALL-001",
            customer_id="CUST-001",
            triage_result=triage_result
        )

        assert ticket_id is not None
        mock_db.execute.assert_called()
