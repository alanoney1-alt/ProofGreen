"""
ProofGreen MAS - Voice Triage Agent
24/7 AI voice dispatcher for emergency calls via Twilio/Vapi.
"""

import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from pydantic import BaseModel, Field
import anthropic
import httpx
import json
import base64
import hmac
import hashlib

from config.settings import settings


class EmergencyLevel(str, Enum):
    """Emergency severity levels."""
    CRITICAL = "critical"      # Life safety (gas leak, fire, flooding)
    URGENT = "urgent"          # Same-day required (no heat in winter, no AC in extreme heat)
    STANDARD = "standard"      # Normal service call
    INFORMATIONAL = "info"     # Question, scheduling, follow-up


class CallStatus(str, Enum):
    """Call handling status."""
    INCOMING = "incoming"
    IN_PROGRESS = "in_progress"
    TRIAGED = "triaged"
    DISPATCHED = "dispatched"
    ESCALATED = "escalated"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class DispositionCode(str, Enum):
    """Call disposition codes."""
    EMERGENCY_DISPATCH = "emergency_dispatch"
    SAME_DAY_SCHEDULED = "same_day_scheduled"
    APPOINTMENT_SCHEDULED = "appointment_scheduled"
    CALLBACK_REQUESTED = "callback_requested"
    INFORMATION_PROVIDED = "information_provided"
    ESCALATED_TO_HUMAN = "escalated_to_human"
    NO_SERVICE_NEEDED = "no_service_needed"


@dataclass
class CallSession:
    """Active call session tracking."""
    call_id: str
    phone_number: str
    customer_id: Optional[str]
    customer_name: Optional[str]
    started_at: datetime
    status: CallStatus
    emergency_level: Optional[EmergencyLevel] = None
    transcript: List[Dict] = field(default_factory=list)
    detected_issues: List[str] = field(default_factory=list)
    equipment_mentioned: List[str] = field(default_factory=list)
    address: Optional[str] = None
    triage_result: Optional[Dict] = None
    disposition: Optional[DispositionCode] = None
    job_id: Optional[str] = None


@dataclass
class TriageResult:
    """Result of emergency triage."""
    emergency_level: EmergencyLevel
    issue_summary: str
    detected_problems: List[str]
    safety_instructions: List[str]
    recommended_action: str
    requires_immediate_dispatch: bool
    estimated_response_time: Optional[str] = None
    preliminary_quote_range: Optional[Tuple[float, float]] = None


class VoiceTriageAgent:
    """
    Voice Triage Agent for 24/7 emergency call handling.
    Integrates with Twilio/Vapi for voice calls.
    """

    def __init__(
        self,
        db_connection=None,
        scheduling_agent=None,
        twilio_account_sid: Optional[str] = None,
        twilio_auth_token: Optional[str] = None,
        twilio_phone_number: Optional[str] = None,
        vapi_api_key: Optional[str] = None
    ):
        """
        Initialize Voice Triage Agent.

        Args:
            db_connection: PostgreSQL connection
            scheduling_agent: SchedulingAgent for dispatch
            twilio_account_sid: Twilio account SID
            twilio_auth_token: Twilio auth token
            twilio_phone_number: Twilio phone number
            vapi_api_key: Vapi API key (alternative to Twilio)
        """
        self.db = db_connection
        self.scheduling = scheduling_agent

        # Twilio credentials
        self.twilio_sid = twilio_account_sid or settings.TWILIO_ACCOUNT_SID
        self.twilio_token = twilio_auth_token or settings.TWILIO_AUTH_TOKEN
        self.twilio_phone = twilio_phone_number or settings.TWILIO_PHONE_NUMBER

        # Vapi credentials
        self.vapi_key = vapi_api_key

        # Claude client for reasoning
        self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

        # Active call sessions
        self.sessions: Dict[str, CallSession] = {}

        # Emergency keywords for quick detection
        self.emergency_keywords = {
            "critical": [
                "gas leak", "smell gas", "fire", "smoke", "flooding",
                "water everywhere", "electrical fire", "sparking",
                "carbon monoxide", "co detector", "explosion"
            ],
            "urgent": [
                "no heat", "no air conditioning", "no ac", "freezing",
                "extremely hot", "pipe burst", "water damage",
                "no hot water", "sewage", "backed up"
            ]
        }

        # Issue classification patterns
        self.issue_patterns = {
            "hvac": ["air conditioner", "ac", "heating", "furnace", "heat pump", "thermostat", "ductwork"],
            "plumbing": ["water heater", "pipe", "drain", "toilet", "faucet", "leak", "sewer"],
            "electrical": ["outlet", "breaker", "wire", "power", "light", "panel", "circuit"],
        }

    # ========== TWILIO WEBHOOK HANDLERS ==========

    async def handle_inbound_call(
        self,
        call_sid: str,
        from_number: str,
        to_number: str,
        **kwargs
    ) -> Dict:
        """
        Handle incoming Twilio call webhook.

        Args:
            call_sid: Twilio call SID
            from_number: Caller phone number
            to_number: Called number

        Returns:
            TwiML response for call handling
        """
        # Look up customer by phone number
        customer = await self._lookup_customer(from_number)

        # Create call session
        session = CallSession(
            call_id=call_sid,
            phone_number=from_number,
            customer_id=customer.get("id") if customer else None,
            customer_name=customer.get("name") if customer else None,
            started_at=datetime.utcnow(),
            status=CallStatus.INCOMING,
            address=customer.get("address") if customer else None
        )
        self.sessions[call_sid] = session

        # Log call start
        if self.db:
            await self._log_call_event(call_sid, "call_started", {
                "from": from_number,
                "customer_id": session.customer_id
            })

        # Generate TwiML response
        greeting = self._generate_greeting(customer)

        return {
            "twiml": f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna">{greeting}</Say>
    <Gather input="speech" timeout="10" speechTimeout="auto"
            action="/api/v1/voice/process-speech" method="POST">
        <Say voice="Polly.Joanna">Please describe your issue or emergency.</Say>
    </Gather>
    <Say voice="Polly.Joanna">I didn't hear anything. Let me connect you with our team.</Say>
    <Redirect>/api/v1/voice/escalate</Redirect>
</Response>""",
            "session_id": call_sid
        }

    async def process_speech(
        self,
        call_sid: str,
        speech_result: str,
        confidence: float = 0.0,
        **kwargs
    ) -> Dict:
        """
        Process speech input from caller.

        Args:
            call_sid: Twilio call SID
            speech_result: Transcribed speech
            confidence: Speech recognition confidence

        Returns:
            TwiML response with next action
        """
        session = self.sessions.get(call_sid)
        if not session:
            return {"error": "Session not found"}

        session.status = CallStatus.IN_PROGRESS

        # Add to transcript
        session.transcript.append({
            "speaker": "customer",
            "text": speech_result,
            "timestamp": datetime.utcnow().isoformat(),
            "confidence": confidence
        })

        # Quick emergency keyword detection
        emergency_level = self._detect_emergency_keywords(speech_result)

        if emergency_level == EmergencyLevel.CRITICAL:
            # Immediate safety response
            return await self._handle_critical_emergency(session, speech_result)

        # Use Claude to analyze the issue
        triage_result = await self.triage_emergency(
            call_id=call_sid,
            speech_text=speech_result,
            customer_context=self._get_customer_context(session)
        )

        session.triage_result = triage_result
        session.emergency_level = triage_result["emergency_level"]
        session.detected_issues = triage_result["detected_problems"]
        session.status = CallStatus.TRIAGED

        # Generate response based on triage
        return await self._generate_triage_response(session, triage_result)

    async def _handle_critical_emergency(
        self,
        session: CallSession,
        speech_text: str
    ) -> Dict:
        """Handle critical life-safety emergencies."""
        session.emergency_level = EmergencyLevel.CRITICAL
        session.status = CallStatus.TRIAGED

        # Detect specific emergency type
        emergency_type = "emergency"
        safety_instructions = []

        if any(kw in speech_text.lower() for kw in ["gas", "smell"]):
            emergency_type = "gas leak"
            safety_instructions = [
                "Leave the building immediately",
                "Do not use any electrical switches or phones inside",
                "Call 911 from outside",
                "Do not re-enter until cleared by emergency services"
            ]
        elif any(kw in speech_text.lower() for kw in ["fire", "smoke", "burning"]):
            emergency_type = "fire"
            safety_instructions = [
                "Evacuate immediately if safe to do so",
                "Call 911",
                "Do not use elevators",
                "Meet at a safe distance from the building"
            ]
        elif any(kw in speech_text.lower() for kw in ["flood", "water everywhere"]):
            emergency_type = "flooding"
            safety_instructions = [
                "Turn off main water supply if safe",
                "Do not touch electrical equipment in wet areas",
                "Move valuables to higher ground",
                "Document damage with photos"
            ]

        safety_message = " ".join(safety_instructions)

        # Log critical emergency
        if self.db:
            await self._log_call_event(session.call_id, "critical_emergency", {
                "type": emergency_type,
                "speech": speech_text
            })

        return {
            "twiml": f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna">I understand this is a {emergency_type} emergency. Your safety is the priority.</Say>
    <Pause length="1"/>
    <Say voice="Polly.Joanna">{safety_message}</Say>
    <Pause length="1"/>
    <Say voice="Polly.Joanna">I'm dispatching emergency service immediately and connecting you with our on-call technician.</Say>
    <Dial timeout="30" callerId="{self.twilio_phone}">
        <Number>+1ONCALLNUMBER</Number>
    </Dial>
    <Say voice="Polly.Joanna">Our technician will call you back shortly. Please stay safe.</Say>
</Response>""",
            "emergency_dispatch": True,
            "emergency_type": emergency_type,
            "safety_instructions": safety_instructions
        }

    async def triage_emergency(
        self,
        call_id: str,
        speech_text: str,
        customer_context: Optional[Dict] = None,
        **kwargs
    ) -> Dict:
        """
        Use LLM reasoning to triage the emergency.

        Args:
            call_id: Call identifier
            speech_text: Customer's description
            customer_context: Previous service history, equipment info

        Returns:
            TriageResult as dictionary
        """
        context_str = json.dumps(customer_context, indent=2, default=str) if customer_context else "No previous history"

        prompt = f"""You are an AI emergency triage agent for a home services company (HVAC, Plumbing, Electrical).

Analyze this customer call and provide a triage assessment.

Customer Statement:
"{speech_text}"

Customer Context:
{context_str}

Assess:
1. Emergency Level: critical (life safety), urgent (same-day needed), standard (normal appointment), info (question only)
2. Main Issue Summary (1 sentence)
3. Detected Problems (list specific issues mentioned)
4. Safety Instructions (if any immediate safety concerns)
5. Recommended Action
6. Requires Immediate Dispatch? (true/false)
7. Estimated Response Time (if urgent/critical)
8. Preliminary Quote Range (if you can estimate)

Return as JSON:
{{
    "emergency_level": "urgent",
    "issue_summary": "...",
    "detected_problems": ["..."],
    "safety_instructions": ["..."],
    "recommended_action": "...",
    "requires_immediate_dispatch": false,
    "estimated_response_time": "2-4 hours",
    "preliminary_quote_range": [150, 350]
}}"""

        try:
            response = self.client.messages.create(
                model=settings.AGENT_MODEL,
                max_tokens=1000,
                temperature=0.1,
                messages=[{"role": "user", "content": prompt}]
            )

            result = json.loads(response.content[0].text)
            result["emergency_level"] = EmergencyLevel(result["emergency_level"])
            return result

        except Exception as e:
            # Fallback to basic triage
            return {
                "emergency_level": EmergencyLevel.STANDARD,
                "issue_summary": "Service request received",
                "detected_problems": [speech_text[:100]],
                "safety_instructions": [],
                "recommended_action": "Schedule service appointment",
                "requires_immediate_dispatch": False,
                "estimated_response_time": None,
                "preliminary_quote_range": None
            }

    async def _generate_triage_response(
        self,
        session: CallSession,
        triage: Dict
    ) -> Dict:
        """Generate TwiML response based on triage result."""
        emergency_level = triage["emergency_level"]
        issue_summary = triage["issue_summary"]
        safety_instructions = triage.get("safety_instructions", [])
        quote_range = triage.get("preliminary_quote_range")

        # Build response message
        response_parts = []

        if emergency_level == EmergencyLevel.URGENT:
            response_parts.append(f"I understand you're dealing with {issue_summary}. This requires same-day service.")

            if safety_instructions:
                response_parts.append(f"For your safety: {'. '.join(safety_instructions)}")

            if quote_range:
                response_parts.append(f"Based on similar issues, this typically costs between ${quote_range[0]} and ${quote_range[1]}.")

            response_parts.append("I'm checking technician availability now.")

            # Auto-dispatch for urgent
            return await self._initiate_dispatch(session, triage)

        elif emergency_level == EmergencyLevel.STANDARD:
            response_parts.append(f"Thank you for describing the issue. {issue_summary}")

            if quote_range:
                response_parts.append(f"Similar repairs typically range from ${quote_range[0]} to ${quote_range[1]}.")

            response_parts.append("Would you like to schedule an appointment? Please say yes to continue or say a preferred date and time.")

            return {
                "twiml": f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna">{' '.join(response_parts)}</Say>
    <Gather input="speech" timeout="10" speechTimeout="auto"
            action="/api/v1/voice/schedule" method="POST">
    </Gather>
    <Redirect>/api/v1/voice/confirm-callback</Redirect>
</Response>""",
                "triage_complete": True,
                "emergency_level": emergency_level.value
            }

        else:  # INFORMATIONAL
            response_parts.append(f"I can help with that. {triage['recommended_action']}")
            response_parts.append("Is there anything else I can help you with?")

            return {
                "twiml": f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna">{' '.join(response_parts)}</Say>
    <Gather input="speech" timeout="10" speechTimeout="auto"
            action="/api/v1/voice/process-speech" method="POST">
    </Gather>
    <Say voice="Polly.Joanna">Thank you for calling. Have a great day!</Say>
    <Hangup/>
</Response>""",
                "triage_complete": True,
                "emergency_level": emergency_level.value
            }

    async def _initiate_dispatch(
        self,
        session: CallSession,
        triage: Dict
    ) -> Dict:
        """Initiate emergency dispatch through scheduling agent."""
        if self.scheduling:
            # Find available technician
            from agents.scheduling_agent import JobUrgency

            urgency = JobUrgency.EMERGENCY if triage["emergency_level"] == EmergencyLevel.CRITICAL else JobUrgency.URGENT

            slots = await self.scheduling.find_available_slots(
                job_type=self._detect_job_type(triage["detected_problems"]),
                location=await self._get_customer_location(session.customer_id) or (0, 0),
                urgency=urgency,
                required_skills=self._get_required_skills(triage["detected_problems"])
            )

            if slots:
                best_slot = slots[0]

                # Create service ticket
                job_id = await self.create_service_ticket(
                    call_id=session.call_id,
                    customer_id=session.customer_id,
                    triage_result=triage,
                    scheduled_slot=best_slot
                )

                session.job_id = job_id
                session.status = CallStatus.DISPATCHED
                session.disposition = DispositionCode.EMERGENCY_DISPATCH

                eta = triage.get("estimated_response_time", "within 2 hours")

                return {
                    "twiml": f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna">Great news. I've dispatched {best_slot.technician_name} to your location. They should arrive {eta}.</Say>
    <Pause length="1"/>
    <Say voice="Polly.Joanna">You'll receive a text message with their contact information and a tracking link.</Say>
    <Say voice="Polly.Joanna">Is there anything else you need before they arrive?</Say>
    <Gather input="speech" timeout="5" speechTimeout="auto"
            action="/api/v1/voice/final-questions" method="POST">
    </Gather>
    <Say voice="Polly.Joanna">Thank you for calling. Help is on the way!</Say>
    <Hangup/>
</Response>""",
                    "dispatched": True,
                    "job_id": job_id,
                    "technician": best_slot.technician_name,
                    "eta": eta
                }

        # No slots available - escalate to human
        return await self.escalate_to_human(
            call_id=session.call_id,
            reason="No technicians available for emergency dispatch"
        )

    async def create_service_ticket(
        self,
        call_id: str,
        customer_id: Optional[str],
        triage_result: Dict,
        scheduled_slot: Optional[Any] = None,
        **kwargs
    ) -> str:
        """
        Create a service ticket in the FSM system.

        Args:
            call_id: Call identifier
            customer_id: Customer ID if known
            triage_result: Triage assessment
            scheduled_slot: Scheduled time slot if available

        Returns:
            Job/ticket ID
        """
        import uuid
        job_id = f"job_{uuid.uuid4().hex[:12]}"

        session = self.sessions.get(call_id)

        ticket = {
            "job_id": job_id,
            "source": "voice_triage",
            "call_id": call_id,
            "customer_id": customer_id,
            "customer_phone": session.phone_number if session else None,
            "customer_address": session.address if session else None,
            "emergency_level": triage_result["emergency_level"].value,
            "issue_summary": triage_result["issue_summary"],
            "detected_problems": triage_result["detected_problems"],
            "preliminary_quote_range": triage_result.get("preliminary_quote_range"),
            "transcript": session.transcript if session else [],
            "created_at": datetime.utcnow().isoformat()
        }

        if scheduled_slot:
            ticket["technician_id"] = scheduled_slot.technician_id
            ticket["technician_name"] = scheduled_slot.technician_name
            ticket["scheduled_start"] = scheduled_slot.start_time.isoformat()
            ticket["scheduled_end"] = scheduled_slot.end_time.isoformat()

        # Store in database
        if self.db:
            await self.db.execute(
                """INSERT INTO service_tickets (
                    job_id, source, call_id, customer_id, customer_phone,
                    emergency_level, issue_summary, detected_problems,
                    transcript, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())""",
                job_id, "voice_triage", call_id, customer_id,
                session.phone_number if session else None,
                triage_result["emergency_level"].value,
                triage_result["issue_summary"],
                json.dumps(triage_result["detected_problems"]),
                json.dumps(session.transcript if session else [])
            )

        return job_id

    async def escalate_to_human(
        self,
        call_id: str,
        reason: str,
        **kwargs
    ) -> Dict:
        """
        Escalate call to human operator.

        Args:
            call_id: Call identifier
            reason: Reason for escalation

        Returns:
            TwiML for call transfer
        """
        session = self.sessions.get(call_id)
        if session:
            session.status = CallStatus.ESCALATED
            session.disposition = DispositionCode.ESCALATED_TO_HUMAN

        # Log escalation
        if self.db:
            await self._log_call_event(call_id, "escalated", {"reason": reason})

        return {
            "twiml": f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna">I'm connecting you with a member of our team who can better assist you. Please hold.</Say>
    <Play>https://api.twilio.com/cowbell.mp3</Play>
    <Dial timeout="60" callerId="{self.twilio_phone}">
        <Queue>support-queue</Queue>
    </Dial>
    <Say voice="Polly.Joanna">We're sorry, all representatives are busy. Please leave a message and we'll call you back shortly.</Say>
    <Record maxLength="120" action="/api/v1/voice/voicemail" />
</Response>""",
            "escalated": True,
            "reason": reason
        }

    # ========== VAPI INTEGRATION ==========

    async def handle_vapi_webhook(
        self,
        event_type: str,
        payload: Dict,
        **kwargs
    ) -> Dict:
        """
        Handle Vapi webhook events.

        Args:
            event_type: Vapi event type
            payload: Event payload

        Returns:
            Response for Vapi
        """
        if event_type == "call.started":
            return await self._vapi_call_started(payload)
        elif event_type == "transcript.partial":
            return await self._vapi_transcript_update(payload)
        elif event_type == "call.ended":
            return await self._vapi_call_ended(payload)
        elif event_type == "function.call":
            return await self._vapi_function_call(payload)

        return {"status": "acknowledged"}

    async def _vapi_call_started(self, payload: Dict) -> Dict:
        """Handle Vapi call start."""
        call_id = payload.get("call_id")
        phone = payload.get("customer", {}).get("phone")

        customer = await self._lookup_customer(phone) if phone else None

        session = CallSession(
            call_id=call_id,
            phone_number=phone or "unknown",
            customer_id=customer.get("id") if customer else None,
            customer_name=customer.get("name") if customer else None,
            started_at=datetime.utcnow(),
            status=CallStatus.INCOMING,
            address=customer.get("address") if customer else None
        )
        self.sessions[call_id] = session

        # Return assistant configuration for Vapi
        return {
            "assistant": {
                "firstMessage": self._generate_greeting(customer),
                "model": {
                    "provider": "anthropic",
                    "model": "claude-sonnet-4-20250514"
                },
                "functions": [
                    {
                        "name": "triage_issue",
                        "description": "Triage the customer's issue",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "issue_description": {"type": "string"},
                                "urgency": {"type": "string", "enum": ["critical", "urgent", "standard", "info"]}
                            }
                        }
                    },
                    {
                        "name": "schedule_appointment",
                        "description": "Schedule a service appointment",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "preferred_date": {"type": "string"},
                                "preferred_time": {"type": "string"}
                            }
                        }
                    },
                    {
                        "name": "dispatch_emergency",
                        "description": "Dispatch emergency service",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "issue_type": {"type": "string"},
                                "safety_concern": {"type": "boolean"}
                            }
                        }
                    }
                ]
            }
        }

    async def _vapi_function_call(self, payload: Dict) -> Dict:
        """Handle Vapi function calls."""
        function_name = payload.get("function_name")
        arguments = payload.get("arguments", {})
        call_id = payload.get("call_id")

        if function_name == "triage_issue":
            triage_result = await self.triage_emergency(
                call_id=call_id,
                speech_text=arguments.get("issue_description", ""),
                customer_context=self._get_customer_context(self.sessions.get(call_id))
            )
            return {
                "result": {
                    "emergency_level": triage_result["emergency_level"].value,
                    "summary": triage_result["issue_summary"],
                    "action": triage_result["recommended_action"]
                }
            }

        elif function_name == "schedule_appointment":
            # Schedule through scheduling agent
            return {"result": {"scheduled": True, "message": "Appointment scheduled"}}

        elif function_name == "dispatch_emergency":
            session = self.sessions.get(call_id)
            if session:
                job_id = await self.create_service_ticket(
                    call_id=call_id,
                    customer_id=session.customer_id,
                    triage_result={
                        "emergency_level": EmergencyLevel.URGENT,
                        "issue_summary": arguments.get("issue_type", "Emergency"),
                        "detected_problems": [arguments.get("issue_type", "")],
                        "safety_instructions": [],
                        "recommended_action": "Dispatch immediately",
                        "requires_immediate_dispatch": True
                    }
                )
                return {"result": {"dispatched": True, "job_id": job_id}}

        return {"result": {"error": "Unknown function"}}

    # ========== VIDEO TRIAGE ==========

    async def initiate_video_triage(
        self,
        call_id: str,
        customer_phone: str
    ) -> Dict:
        """
        Send video triage link to customer.

        Args:
            call_id: Call identifier
            customer_phone: Customer phone number

        Returns:
            Video session info
        """
        import uuid
        video_session_id = f"video_{uuid.uuid4().hex[:12]}"

        # Generate video link (would integrate with video service)
        video_link = f"https://video.proofgreen.io/session/{video_session_id}"

        # Send SMS with link
        if self.twilio_sid and self.twilio_token:
            await self._send_sms(
                customer_phone,
                f"ProofGreen Video Triage: Please click the link to show us the issue. Our AI will provide an instant preliminary assessment. {video_link}"
            )

        return {
            "video_session_id": video_session_id,
            "video_link": video_link,
            "sms_sent": True,
            "message": "Video triage link sent to customer"
        }

    async def process_video_frame(
        self,
        video_session_id: str,
        image_data: bytes,
        **kwargs
    ) -> Dict:
        """
        Process video frame for visual triage.

        Args:
            video_session_id: Video session identifier
            image_data: Image bytes

        Returns:
            Visual analysis result
        """
        # Encode image for Claude Vision
        image_base64 = base64.b64encode(image_data).decode("utf-8")

        prompt = """Analyze this image from a home services video triage session.

Identify:
1. What equipment or system is shown (HVAC, water heater, electrical panel, plumbing, etc.)
2. Any visible damage, leaks, corrosion, or safety hazards
3. Model numbers or labels visible
4. Estimated severity (critical, urgent, standard)
5. Immediate safety concerns
6. Preliminary diagnosis

Return as JSON:
{
    "equipment_type": "...",
    "visible_issues": ["..."],
    "model_info": "...",
    "severity": "...",
    "safety_concerns": ["..."],
    "preliminary_diagnosis": "...",
    "recommended_action": "...",
    "estimated_repair_cost_range": [min, max]
}"""

        try:
            response = self.client.messages.create(
                model=settings.VISION_MODEL,
                max_tokens=1000,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": image_base64
                            }
                        },
                        {"type": "text", "text": prompt}
                    ]
                }]
            )

            analysis = json.loads(response.content[0].text)

            # Store analysis
            if self.db:
                await self.db.execute(
                    """INSERT INTO video_triage_analyses (
                        session_id, equipment_type, visible_issues, severity,
                        preliminary_diagnosis, analyzed_at
                    ) VALUES ($1, $2, $3, $4, $5, NOW())""",
                    video_session_id,
                    analysis.get("equipment_type"),
                    json.dumps(analysis.get("visible_issues", [])),
                    analysis.get("severity"),
                    analysis.get("preliminary_diagnosis")
                )

            return analysis

        except Exception as e:
            return {"error": str(e), "analysis_failed": True}

    # ========== HELPER METHODS ==========

    def _generate_greeting(self, customer: Optional[Dict]) -> str:
        """Generate personalized greeting."""
        hour = datetime.utcnow().hour
        if hour < 12:
            time_greeting = "Good morning"
        elif hour < 17:
            time_greeting = "Good afternoon"
        else:
            time_greeting = "Good evening"

        if customer and customer.get("name"):
            return f"{time_greeting}, {customer['name']}. Thank you for calling ProofGreen. How can I help you today?"
        return f"{time_greeting}. Thank you for calling ProofGreen. How can I help you today?"

    def _detect_emergency_keywords(self, text: str) -> Optional[EmergencyLevel]:
        """Quick keyword detection for emergencies."""
        text_lower = text.lower()

        for keyword in self.emergency_keywords["critical"]:
            if keyword in text_lower:
                return EmergencyLevel.CRITICAL

        for keyword in self.emergency_keywords["urgent"]:
            if keyword in text_lower:
                return EmergencyLevel.URGENT

        return None

    def _get_customer_context(self, session: Optional[CallSession]) -> Optional[Dict]:
        """Get customer context for triage."""
        if not session:
            return None

        return {
            "customer_name": session.customer_name,
            "address": session.address,
            "previous_issues": session.detected_issues,
            "transcript_so_far": session.transcript
        }

    def _detect_job_type(self, problems: List[str]) -> str:
        """Detect job type from problems."""
        problems_text = " ".join(problems).lower()

        for job_type, keywords in self.issue_patterns.items():
            if any(kw in problems_text for kw in keywords):
                return job_type

        return "general"

    def _get_required_skills(self, problems: List[str]) -> List[str]:
        """Determine required skills from problems."""
        skills = []
        problems_text = " ".join(problems).lower()

        if any(kw in problems_text for kw in ["refrigerant", "r-410a", "r-454b"]):
            skills.append("EPA_608")
        if any(kw in problems_text for kw in ["gas", "furnace"]):
            skills.append("gas_certified")

        return skills

    async def _lookup_customer(self, phone: str) -> Optional[Dict]:
        """Look up customer by phone number."""
        if self.db:
            row = await self.db.fetchrow(
                "SELECT id, name, address, zip_code FROM customers WHERE phone = $1",
                phone
            )
            if row:
                return dict(row)
        return None

    async def _get_customer_location(self, customer_id: Optional[str]) -> Optional[Tuple[float, float]]:
        """Get customer location coordinates."""
        if customer_id and self.db:
            row = await self.db.fetchrow(
                "SELECT latitude, longitude FROM customers WHERE id = $1",
                customer_id
            )
            if row and row["latitude"] and row["longitude"]:
                return (row["latitude"], row["longitude"])
        return None

    async def _send_sms(self, to_number: str, message: str):
        """Send SMS via Twilio."""
        if not all([self.twilio_sid, self.twilio_token, self.twilio_phone]):
            return

        async with httpx.AsyncClient() as client:
            await client.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{self.twilio_sid}/Messages.json",
                auth=(self.twilio_sid, self.twilio_token),
                data={
                    "From": self.twilio_phone,
                    "To": to_number,
                    "Body": message
                }
            )

    async def _log_call_event(self, call_id: str, event: str, data: Dict):
        """Log call event to database."""
        if self.db:
            await self.db.execute(
                """INSERT INTO call_events (call_id, event, data, created_at)
                   VALUES ($1, $2, $3, NOW())""",
                call_id, event, json.dumps(data, default=str)
            )

    # ========== BROADCAST HANDLER ==========

    async def receive_broadcast(self, message: str, data: Dict) -> Dict:
        """Handle broadcast messages from Chief of Staff."""
        return {"acknowledged": True, "active_calls": len(self.sessions)}


# Singleton instance
voice_triage_agent = VoiceTriageAgent()
