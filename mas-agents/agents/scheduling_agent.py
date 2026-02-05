"""
ProofGreen MAS - Scheduling Agent
Manages technician scheduling, route optimization, and conflict resolution.
"""

import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta, time
from dataclasses import dataclass, field
from enum import Enum
from pydantic import BaseModel, Field
import anthropic
import httpx
import math

from config.settings import settings


class TechnicianStatus(str, Enum):
    """Technician availability status."""
    AVAILABLE = "available"
    ON_JOB = "on_job"
    EN_ROUTE = "en_route"
    ON_BREAK = "on_break"
    OFF_DUTY = "off_duty"
    ON_CALL = "on_call"


class JobUrgency(str, Enum):
    """Job urgency levels."""
    EMERGENCY = "emergency"     # Same-hour dispatch
    URGENT = "urgent"           # Same-day
    STANDARD = "standard"       # 1-3 days
    FLEXIBLE = "flexible"       # Customer's preferred time


class SkillLevel(str, Enum):
    """Technician certification levels."""
    APPRENTICE = "apprentice"
    JOURNEYMAN = "journeyman"
    MASTER = "master"
    SPECIALIST = "specialist"   # EPA 608, specific equipment certs


@dataclass
class Technician:
    """Technician profile and current status."""
    id: str
    name: str
    status: TechnicianStatus
    current_location: Tuple[float, float]  # lat, lng
    skills: List[str]
    certifications: List[str]
    skill_level: SkillLevel
    avg_job_duration_minutes: int = 90
    esg_score: float = 0.0  # ESG performance score
    current_job_id: Optional[str] = None
    shift_start: time = time(8, 0)
    shift_end: time = time(18, 0)
    home_base: Tuple[float, float] = (0, 0)


@dataclass
class TimeSlot:
    """Available time slot."""
    technician_id: str
    technician_name: str
    start_time: datetime
    end_time: datetime
    travel_time_minutes: int
    distance_miles: float
    confidence: float  # 0-1, based on typical job durations


@dataclass
class ScheduleConflict:
    """Detected scheduling conflict."""
    conflict_type: str
    description: str
    affected_jobs: List[str]
    affected_technicians: List[str]
    severity: str  # "blocking", "warning"
    resolution_options: List[Dict]


class SchedulingAgent:
    """
    Scheduling Agent for technician dispatch and route optimization.
    Coordinates with Chief of Staff to prevent conflicts.
    """

    def __init__(
        self,
        db_connection=None,
        fsm_connector=None,
        google_maps_api_key: Optional[str] = None
    ):
        """
        Initialize Scheduling Agent.

        Args:
            db_connection: PostgreSQL connection
            fsm_connector: FSM integration for syncing schedules
            google_maps_api_key: For route optimization (optional)
        """
        self.db = db_connection
        self.fsm = fsm_connector
        self.maps_api_key = google_maps_api_key

        self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

        # In-memory technician cache
        self.technicians: Dict[str, Technician] = {}

        # Scheduled jobs cache
        self.scheduled_jobs: Dict[str, Dict] = {}

        # Policy constraints
        self.policies = {
            "max_daily_jobs_per_tech": 6,
            "min_break_between_jobs_minutes": 15,
            "max_travel_time_minutes": 45,
            "overtime_requires_approval": True,
            "emergency_override_enabled": True,
            "min_profit_margin_percent": 15.0,
        }

    # ========== SLOT FINDING ==========

    async def find_available_slots(
        self,
        job_type: str,
        location: Tuple[float, float],
        duration_minutes: int = 90,
        urgency: JobUrgency = JobUrgency.STANDARD,
        required_skills: Optional[List[str]] = None,
        preferred_date: Optional[datetime] = None,
        **kwargs
    ) -> List[TimeSlot]:
        """
        Find available time slots for a job.

        Args:
            job_type: Type of job (hvac_install, plumbing_repair, etc.)
            location: Customer location (lat, lng)
            duration_minutes: Expected job duration
            urgency: How urgent is the job
            required_skills: Required technician skills/certs
            preferred_date: Customer's preferred date

        Returns:
            List of available TimeSlots sorted by suitability
        """
        required_skills = required_skills or []

        # Determine search window based on urgency
        now = datetime.utcnow()
        if urgency == JobUrgency.EMERGENCY:
            start_window = now
            end_window = now + timedelta(hours=4)
        elif urgency == JobUrgency.URGENT:
            start_window = now
            end_window = now + timedelta(hours=12)
        elif urgency == JobUrgency.STANDARD:
            start_window = preferred_date or now + timedelta(days=1)
            end_window = start_window + timedelta(days=3)
        else:  # FLEXIBLE
            start_window = preferred_date or now + timedelta(days=1)
            end_window = start_window + timedelta(days=7)

        # Get qualified technicians
        qualified_techs = self._get_qualified_technicians(job_type, required_skills)

        slots = []
        for tech in qualified_techs:
            tech_slots = await self._find_technician_slots(
                technician=tech,
                start_window=start_window,
                end_window=end_window,
                duration_minutes=duration_minutes,
                job_location=location
            )
            slots.extend(tech_slots)

        # Sort by suitability (travel time, tech skill, ESG score)
        slots.sort(key=lambda s: (
            s.travel_time_minutes,
            -self.technicians.get(s.technician_id, Technician("", "", TechnicianStatus.OFF_DUTY, (0,0), [], [], SkillLevel.APPRENTICE)).esg_score
        ))

        return slots[:10]  # Return top 10 options

    async def _find_technician_slots(
        self,
        technician: Technician,
        start_window: datetime,
        end_window: datetime,
        duration_minutes: int,
        job_location: Tuple[float, float]
    ) -> List[TimeSlot]:
        """Find available slots for a specific technician."""
        slots = []

        # Get technician's existing schedule
        existing_jobs = await self._get_technician_schedule(
            technician.id, start_window, end_window
        )

        # Calculate travel time to job location
        travel_time = self._estimate_travel_time(
            technician.current_location, job_location
        )
        travel_distance = self._estimate_distance(
            technician.current_location, job_location
        )

        # Check policy constraints
        if travel_time > self.policies["max_travel_time_minutes"]:
            return []  # Too far

        # Find gaps in schedule
        current_time = start_window
        while current_time < end_window:
            # Check if within shift hours
            if not self._is_within_shift(technician, current_time):
                current_time += timedelta(hours=1)
                continue

            # Check for conflicts
            slot_end = current_time + timedelta(minutes=duration_minutes + travel_time)
            conflict = self._check_slot_conflict(
                technician.id, current_time, slot_end, existing_jobs
            )

            if not conflict:
                confidence = self._calculate_slot_confidence(
                    technician, current_time, duration_minutes
                )
                slots.append(TimeSlot(
                    technician_id=technician.id,
                    technician_name=technician.name,
                    start_time=current_time,
                    end_time=slot_end,
                    travel_time_minutes=travel_time,
                    distance_miles=travel_distance,
                    confidence=confidence
                ))

            current_time += timedelta(minutes=30)  # 30-min increments

        return slots

    def _is_within_shift(self, technician: Technician, check_time: datetime) -> bool:
        """Check if time is within technician's shift."""
        check_time_only = check_time.time()
        return technician.shift_start <= check_time_only <= technician.shift_end

    def _check_slot_conflict(
        self,
        tech_id: str,
        start: datetime,
        end: datetime,
        existing_jobs: List[Dict]
    ) -> Optional[str]:
        """Check if slot conflicts with existing jobs."""
        buffer = timedelta(minutes=self.policies["min_break_between_jobs_minutes"])

        for job in existing_jobs:
            job_start = job["scheduled_start"]
            job_end = job["scheduled_end"]

            # Check overlap with buffer
            if (start - buffer) < job_end and (end + buffer) > job_start:
                return f"Conflicts with job {job['id']}"

        return None

    def _calculate_slot_confidence(
        self,
        technician: Technician,
        slot_time: datetime,
        duration_minutes: int
    ) -> float:
        """Calculate confidence that job will finish on time."""
        base_confidence = 0.85

        # Adjust for technician's skill level
        skill_bonus = {
            SkillLevel.MASTER: 0.10,
            SkillLevel.SPECIALIST: 0.10,
            SkillLevel.JOURNEYMAN: 0.05,
            SkillLevel.APPRENTICE: -0.10,
        }
        base_confidence += skill_bonus.get(technician.skill_level, 0)

        # Adjust for time of day (morning jobs more reliable)
        if slot_time.hour < 12:
            base_confidence += 0.05

        # Adjust for job duration (longer jobs less predictable)
        if duration_minutes > 180:
            base_confidence -= 0.10
        elif duration_minutes > 120:
            base_confidence -= 0.05

        return min(0.99, max(0.50, base_confidence))

    # ========== JOB SCHEDULING ==========

    async def schedule_job(
        self,
        job_id: str,
        technician_id: str,
        slot: TimeSlot,
        job_details: Dict,
        requires_approval: bool = True,
        **kwargs
    ) -> Dict:
        """
        Schedule a job for a specific time slot.

        Args:
            job_id: Job identifier
            technician_id: Assigned technician
            slot: Selected time slot
            job_details: Full job information
            requires_approval: If True, requires HITL approval

        Returns:
            Scheduling result
        """
        # Validate slot is still available
        is_available = await self._validate_slot_availability(
            technician_id, slot.start_time, slot.end_time
        )
        if not is_available:
            return {
                "success": False,
                "error": "Slot no longer available",
                "alternative_slots": await self.find_available_slots(
                    job_type=job_details.get("job_type", "general"),
                    location=job_details.get("location", (0, 0)),
                    urgency=JobUrgency.URGENT
                )
            }

        # Check for policy violations
        violations = self._check_policy_violations(technician_id, slot, job_details)
        if violations and not job_details.get("override_policies"):
            return {
                "success": False,
                "error": "Policy violations detected",
                "violations": violations,
                "requires_override": True
            }

        # Create schedule entry
        schedule_entry = {
            "job_id": job_id,
            "technician_id": technician_id,
            "scheduled_start": slot.start_time,
            "scheduled_end": slot.end_time,
            "travel_time_minutes": slot.travel_time_minutes,
            "customer_name": job_details.get("customer_name"),
            "customer_address": job_details.get("address"),
            "job_type": job_details.get("job_type"),
            "status": "scheduled",
            "created_at": datetime.utcnow()
        }

        # Store in cache
        self.scheduled_jobs[job_id] = schedule_entry

        # Sync to FSM if connected
        if self.fsm:
            await self._sync_to_fsm(schedule_entry)

        # Store in database
        if self.db:
            await self._store_schedule(schedule_entry)

        return {
            "success": True,
            "job_id": job_id,
            "technician": {
                "id": technician_id,
                "name": slot.technician_name
            },
            "scheduled_time": {
                "start": slot.start_time.isoformat(),
                "end": slot.end_time.isoformat(),
                "travel_time_minutes": slot.travel_time_minutes
            },
            "confidence": slot.confidence
        }

    async def reschedule_job(
        self,
        job_id: str,
        new_slot: TimeSlot,
        reason: str,
        notify_customer: bool = True,
        **kwargs
    ) -> Dict:
        """Reschedule an existing job."""
        existing = self.scheduled_jobs.get(job_id)
        if not existing:
            return {"success": False, "error": "Job not found"}

        # Store old schedule for audit
        old_schedule = existing.copy()

        # Update schedule
        existing["technician_id"] = new_slot.technician_id
        existing["scheduled_start"] = new_slot.start_time
        existing["scheduled_end"] = new_slot.end_time
        existing["travel_time_minutes"] = new_slot.travel_time_minutes
        existing["reschedule_reason"] = reason
        existing["reschedule_count"] = existing.get("reschedule_count", 0) + 1
        existing["updated_at"] = datetime.utcnow()

        # Sync changes
        if self.fsm:
            await self._sync_to_fsm(existing)

        if self.db:
            await self._store_schedule(existing)
            await self._log_reschedule(job_id, old_schedule, existing, reason)

        return {
            "success": True,
            "job_id": job_id,
            "old_time": old_schedule["scheduled_start"].isoformat(),
            "new_time": new_slot.start_time.isoformat(),
            "reason": reason,
            "customer_notified": notify_customer
        }

    # ========== ROUTE OPTIMIZATION ==========

    async def optimize_routes(
        self,
        technician_id: str,
        date: datetime,
        **kwargs
    ) -> Dict:
        """
        Optimize route for a technician's daily jobs.
        Uses nearest-neighbor algorithm with time window constraints.
        """
        # Get all jobs for the day
        jobs = await self._get_technician_schedule(
            technician_id,
            date.replace(hour=0, minute=0),
            date.replace(hour=23, minute=59)
        )

        if len(jobs) < 2:
            return {"message": "Not enough jobs to optimize", "jobs": jobs}

        tech = self.technicians.get(technician_id)
        if not tech:
            return {"error": "Technician not found"}

        # Build distance matrix
        locations = [tech.home_base] + [j.get("location", (0, 0)) for j in jobs]
        optimized_order = self._nearest_neighbor_route(locations)

        # Reorder jobs
        reordered_jobs = [jobs[i - 1] for i in optimized_order[1:-1]]  # Exclude home base

        # Calculate time savings
        original_distance = sum(
            self._estimate_distance(locations[i], locations[i + 1])
            for i in range(len(locations) - 1)
        )
        optimized_distance = sum(
            self._estimate_distance(locations[optimized_order[i]], locations[optimized_order[i + 1]])
            for i in range(len(optimized_order) - 1)
        )

        savings_miles = original_distance - optimized_distance
        savings_minutes = int(savings_miles * 2)  # Rough estimate: 2 min/mile

        return {
            "technician_id": technician_id,
            "date": date.isoformat(),
            "jobs_count": len(jobs),
            "optimized_order": [j["job_id"] for j in reordered_jobs],
            "savings": {
                "miles": round(savings_miles, 1),
                "minutes": savings_minutes,
                "fuel_gallons": round(savings_miles / 25, 2)  # ~25 mpg
            }
        }

    def _nearest_neighbor_route(self, locations: List[Tuple[float, float]]) -> List[int]:
        """Simple nearest-neighbor route optimization."""
        n = len(locations)
        if n <= 2:
            return list(range(n))

        visited = [False] * n
        route = [0]  # Start at home base
        visited[0] = True

        for _ in range(n - 1):
            current = route[-1]
            nearest = -1
            nearest_dist = float('inf')

            for j in range(n):
                if not visited[j]:
                    dist = self._estimate_distance(locations[current], locations[j])
                    if dist < nearest_dist:
                        nearest_dist = dist
                        nearest = j

            if nearest >= 0:
                route.append(nearest)
                visited[nearest] = True

        route.append(0)  # Return to home base
        return route

    # ========== TECHNICIAN ASSIGNMENT ==========

    async def assign_technician(
        self,
        job_id: str,
        job_details: Dict,
        preferred_tech_id: Optional[str] = None,
        **kwargs
    ) -> Dict:
        """
        Intelligently assign the best technician for a job.
        Considers skills, ESG score, proximity, and workload.
        """
        required_skills = job_details.get("required_skills", [])
        location = job_details.get("location", (0, 0))
        job_type = job_details.get("job_type", "general")

        # Get qualified technicians
        candidates = self._get_qualified_technicians(job_type, required_skills)

        if not candidates:
            return {
                "success": False,
                "error": "No qualified technicians available",
                "required_skills": required_skills
            }

        # Score each candidate
        scored_candidates = []
        for tech in candidates:
            score = self._score_technician_for_job(tech, job_details, location)
            scored_candidates.append((tech, score))

        # Sort by score (higher is better)
        scored_candidates.sort(key=lambda x: x[1], reverse=True)

        # Prefer specified technician if qualified
        if preferred_tech_id:
            for tech, score in scored_candidates:
                if tech.id == preferred_tech_id:
                    return {
                        "success": True,
                        "technician": {
                            "id": tech.id,
                            "name": tech.name,
                            "score": score,
                            "skills": tech.skills
                        },
                        "reason": "Customer preferred technician"
                    }

        # Return best candidate
        best_tech, best_score = scored_candidates[0]
        return {
            "success": True,
            "technician": {
                "id": best_tech.id,
                "name": best_tech.name,
                "score": round(best_score, 2),
                "skills": best_tech.skills,
                "esg_score": best_tech.esg_score
            },
            "alternatives": [
                {"id": t.id, "name": t.name, "score": round(s, 2)}
                for t, s in scored_candidates[1:4]
            ],
            "reason": self._explain_assignment(best_tech, job_details)
        }

    def _score_technician_for_job(
        self,
        tech: Technician,
        job_details: Dict,
        location: Tuple[float, float]
    ) -> float:
        """Score a technician for a specific job."""
        score = 50.0  # Base score

        # Skill level bonus
        skill_scores = {
            SkillLevel.MASTER: 20,
            SkillLevel.SPECIALIST: 18,
            SkillLevel.JOURNEYMAN: 10,
            SkillLevel.APPRENTICE: 0
        }
        score += skill_scores.get(tech.skill_level, 0)

        # ESG performance bonus (0-15 points)
        score += tech.esg_score * 15

        # Proximity bonus (closer is better)
        distance = self._estimate_distance(tech.current_location, location)
        if distance < 5:
            score += 15
        elif distance < 10:
            score += 10
        elif distance < 20:
            score += 5

        # Current workload penalty
        if tech.status == TechnicianStatus.AVAILABLE:
            score += 10
        elif tech.status == TechnicianStatus.ON_CALL:
            score += 5

        # Certification match bonus
        required_certs = job_details.get("required_certifications", [])
        matching_certs = set(required_certs) & set(tech.certifications)
        score += len(matching_certs) * 5

        return score

    def _explain_assignment(self, tech: Technician, job_details: Dict) -> str:
        """Generate explanation for technician assignment."""
        reasons = []

        if tech.skill_level in [SkillLevel.MASTER, SkillLevel.SPECIALIST]:
            reasons.append(f"{tech.skill_level.value} level technician")

        if tech.esg_score > 0.8:
            reasons.append(f"high ESG performance ({tech.esg_score:.0%})")

        if tech.status == TechnicianStatus.AVAILABLE:
            reasons.append("immediately available")

        job_type = job_details.get("job_type", "")
        if job_type in tech.skills:
            reasons.append(f"specializes in {job_type}")

        return "Selected because: " + ", ".join(reasons) if reasons else "Best available match"

    # ========== CONFLICT RESOLUTION ==========

    async def detect_conflicts(self, date: Optional[datetime] = None) -> List[ScheduleConflict]:
        """Detect scheduling conflicts for a given day."""
        check_date = date or datetime.utcnow()
        conflicts = []

        # Check all technicians
        for tech_id, tech in self.technicians.items():
            jobs = await self._get_technician_schedule(
                tech_id,
                check_date.replace(hour=0, minute=0),
                check_date.replace(hour=23, minute=59)
            )

            # Check for overlapping jobs
            for i, job1 in enumerate(jobs):
                for job2 in jobs[i + 1:]:
                    if self._jobs_overlap(job1, job2):
                        conflicts.append(ScheduleConflict(
                            conflict_type="time_overlap",
                            description=f"Jobs {job1['job_id']} and {job2['job_id']} overlap",
                            affected_jobs=[job1["job_id"], job2["job_id"]],
                            affected_technicians=[tech_id],
                            severity="blocking",
                            resolution_options=[
                                {"action": "reschedule", "job_id": job2["job_id"]},
                                {"action": "reassign", "job_id": job2["job_id"]}
                            ]
                        ))

            # Check for impossible travel times
            for i in range(len(jobs) - 1):
                travel_time = self._estimate_travel_time(
                    jobs[i].get("location", (0, 0)),
                    jobs[i + 1].get("location", (0, 0))
                )
                gap = (jobs[i + 1]["scheduled_start"] - jobs[i]["scheduled_end"]).total_seconds() / 60

                if travel_time > gap:
                    conflicts.append(ScheduleConflict(
                        conflict_type="impossible_travel",
                        description=f"Not enough time to travel between jobs (need {travel_time}min, have {gap}min)",
                        affected_jobs=[jobs[i]["job_id"], jobs[i + 1]["job_id"]],
                        affected_technicians=[tech_id],
                        severity="blocking",
                        resolution_options=[
                            {"action": "reschedule", "job_id": jobs[i + 1]["job_id"]},
                            {"action": "optimize_route", "technician_id": tech_id}
                        ]
                    ))

            # Check for overtime
            if jobs:
                last_job_end = max(j["scheduled_end"] for j in jobs)
                if last_job_end.time() > tech.shift_end:
                    conflicts.append(ScheduleConflict(
                        conflict_type="overtime",
                        description=f"Jobs extend past shift end ({tech.shift_end})",
                        affected_jobs=[j["job_id"] for j in jobs if j["scheduled_end"].time() > tech.shift_end],
                        affected_technicians=[tech_id],
                        severity="warning",
                        resolution_options=[
                            {"action": "approve_overtime", "technician_id": tech_id},
                            {"action": "reassign_last_job"}
                        ]
                    ))

        return conflicts

    def _jobs_overlap(self, job1: Dict, job2: Dict) -> bool:
        """Check if two jobs have overlapping time windows."""
        return job1["scheduled_start"] < job2["scheduled_end"] and job1["scheduled_end"] > job2["scheduled_start"]

    # ========== POLICY ENFORCEMENT ==========

    def _check_policy_violations(
        self,
        tech_id: str,
        slot: TimeSlot,
        job_details: Dict
    ) -> List[Dict]:
        """Check for policy violations before scheduling."""
        violations = []

        # Check profit margin
        revenue = job_details.get("revenue", 0)
        cost = job_details.get("cost", 0)
        if revenue > 0:
            margin = (revenue - cost) / revenue * 100
            if margin < self.policies["min_profit_margin_percent"]:
                violations.append({
                    "policy": "min_profit_margin",
                    "threshold": self.policies["min_profit_margin_percent"],
                    "actual": margin,
                    "message": f"Job margin {margin:.1f}% below minimum {self.policies['min_profit_margin_percent']}%"
                })

        # Check travel time
        if slot.travel_time_minutes > self.policies["max_travel_time_minutes"]:
            violations.append({
                "policy": "max_travel_time",
                "threshold": self.policies["max_travel_time_minutes"],
                "actual": slot.travel_time_minutes,
                "message": f"Travel time {slot.travel_time_minutes}min exceeds maximum"
            })

        return violations

    # ========== HELPER METHODS ==========

    def _get_qualified_technicians(
        self,
        job_type: str,
        required_skills: List[str]
    ) -> List[Technician]:
        """Get technicians qualified for a job."""
        qualified = []
        for tech in self.technicians.values():
            if tech.status == TechnicianStatus.OFF_DUTY:
                continue
            # Check skills
            if required_skills and not set(required_skills).issubset(set(tech.skills)):
                continue
            qualified.append(tech)
        return qualified

    def _estimate_travel_time(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float]
    ) -> int:
        """Estimate travel time in minutes (simple calculation)."""
        distance = self._estimate_distance(origin, destination)
        # Assume average 30 mph in urban areas
        return int(distance / 30 * 60) + 5  # +5 min buffer

    def _estimate_distance(
        self,
        point1: Tuple[float, float],
        point2: Tuple[float, float]
    ) -> float:
        """Estimate distance in miles using Haversine formula."""
        lat1, lon1 = point1
        lat2, lon2 = point2

        R = 3959  # Earth's radius in miles

        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)

        a = math.sin(delta_lat / 2) ** 2 + \
            math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c

    async def _get_technician_schedule(
        self,
        tech_id: str,
        start: datetime,
        end: datetime
    ) -> List[Dict]:
        """Get technician's scheduled jobs for a time range."""
        jobs = []
        for job_id, job in self.scheduled_jobs.items():
            if job["technician_id"] == tech_id:
                if start <= job["scheduled_start"] <= end:
                    jobs.append(job)
        jobs.sort(key=lambda j: j["scheduled_start"])
        return jobs

    async def _validate_slot_availability(
        self,
        tech_id: str,
        start: datetime,
        end: datetime
    ) -> bool:
        """Validate that a time slot is still available."""
        jobs = await self._get_technician_schedule(tech_id, start, end)
        for job in jobs:
            if self._jobs_overlap(
                {"scheduled_start": start, "scheduled_end": end},
                job
            ):
                return False
        return True

    async def _sync_to_fsm(self, schedule_entry: Dict):
        """Sync schedule to FSM system."""
        if self.fsm and hasattr(self.fsm, "sync_schedule"):
            await self.fsm.sync_schedule(schedule_entry)

    async def _store_schedule(self, schedule_entry: Dict):
        """Store schedule in database."""
        if self.db:
            query = """
                INSERT INTO job_schedules (
                    job_id, technician_id, scheduled_start, scheduled_end,
                    travel_time_minutes, status, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (job_id) DO UPDATE SET
                    technician_id = EXCLUDED.technician_id,
                    scheduled_start = EXCLUDED.scheduled_start,
                    scheduled_end = EXCLUDED.scheduled_end,
                    updated_at = EXCLUDED.updated_at
            """
            await self.db.execute(
                query,
                schedule_entry["job_id"],
                schedule_entry["technician_id"],
                schedule_entry["scheduled_start"],
                schedule_entry["scheduled_end"],
                schedule_entry["travel_time_minutes"],
                schedule_entry["status"],
                schedule_entry["created_at"],
                schedule_entry.get("updated_at", datetime.utcnow())
            )

    async def _log_reschedule(
        self,
        job_id: str,
        old_schedule: Dict,
        new_schedule: Dict,
        reason: str
    ):
        """Log reschedule event for audit."""
        if self.db:
            query = """
                INSERT INTO schedule_changes (
                    job_id, old_start, new_start, old_tech, new_tech,
                    reason, changed_at
                ) VALUES ($1, $2, $3, $4, $5, $6, NOW())
            """
            await self.db.execute(
                query,
                job_id,
                old_schedule["scheduled_start"],
                new_schedule["scheduled_start"],
                old_schedule["technician_id"],
                new_schedule["technician_id"],
                reason
            )

    # ========== BROADCAST HANDLER ==========

    async def receive_broadcast(self, message: str, data: Dict) -> Dict:
        """Handle broadcast messages from Chief of Staff."""
        if "regulatory_update" in message.lower():
            # Regulatory change might affect scheduling policies
            return {"acknowledged": True, "action": "policies_reviewed"}
        elif "weather_alert" in message.lower():
            # Weather might require rescheduling
            return {"acknowledged": True, "action": "schedules_flagged_for_review"}
        return {"acknowledged": True}


# Singleton instance
scheduling_agent = SchedulingAgent()
