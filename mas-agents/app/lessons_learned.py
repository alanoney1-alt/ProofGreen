"""
ProofGreen MAS - Lessons Learned Memory System
RLHF-style learning from job outcomes and technician feedback.
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
import hashlib

from config.settings import settings


class LessonType(str, Enum):
    """Types of lessons learned."""
    SUCCESS = "success"              # Job completed successfully
    FAILURE = "failure"              # Job had issues
    OVERRIDE = "override"            # Technician overrode AI recommendation
    CORRECTION = "correction"        # AI calculation was corrected
    BEST_PRACTICE = "best_practice"  # Discovered best practice
    REGULATION = "regulation"        # Regulatory requirement learned
    CUSTOMER_PREF = "customer_pref"  # Customer preference noted


class FeedbackSource(str, Enum):
    """Source of feedback."""
    TECHNICIAN = "technician"
    CUSTOMER = "customer"
    MANAGER = "manager"
    SYSTEM = "system"
    AI_SELF_REFLECTION = "ai_self_reflection"


@dataclass
class Lesson:
    """A lesson learned from a job or interaction."""
    id: str
    lesson_type: LessonType
    source: FeedbackSource
    company_id: str
    job_id: Optional[str]
    customer_id: Optional[str]

    # Context
    context: Dict[str, Any]
    job_type: Optional[str]
    equipment_type: Optional[str]
    state: Optional[str]
    zip_code: Optional[str]

    # The lesson itself
    original_recommendation: Optional[str]
    actual_outcome: str
    correction_reason: Optional[str]
    lesson_learned: str

    # Metrics
    impact_score: float  # -1 to 1 (negative = bad outcome, positive = good)
    confidence: float    # 0 to 1
    times_applied: int = 0
    times_helpful: int = 0

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_applied: Optional[datetime] = None

    # Vector embedding
    embedding: Optional[List[float]] = None


class LessonQuery(BaseModel):
    """Query for retrieving relevant lessons."""
    company_id: str
    context: Dict[str, Any]
    job_type: Optional[str] = None
    equipment_type: Optional[str] = None
    state: Optional[str] = None
    customer_id: Optional[str] = None
    limit: int = 5
    min_confidence: float = 0.5


class LessonsLearned:
    """
    Lessons Learned Memory System.
    Stores job outcomes and feedback for continuous improvement.
    Uses PostgreSQL for storage and Pinecone for semantic search.
    """

    def __init__(
        self,
        db_connection=None,
        pinecone_api_key: Optional[str] = None,
        pinecone_index: str = "lessons-learned"
    ):
        """
        Initialize Lessons Learned system.

        Args:
            db_connection: PostgreSQL connection
            pinecone_api_key: Pinecone API key for vector search
            pinecone_index: Pinecone index name
        """
        self.db = db_connection
        self.pinecone_key = pinecone_api_key or settings.PINECONE_API_KEY
        self.pinecone_index = pinecone_index
        self.pinecone_host = f"https://{pinecone_index}-{settings.PINECONE_ENVIRONMENT}.svc.pinecone.io"

        self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

        # Cache for frequently accessed lessons
        self._lesson_cache: Dict[str, List[Lesson]] = {}
        self._cache_ttl = timedelta(hours=1)
        self._cache_timestamps: Dict[str, datetime] = {}

    # ========== LESSON RECORDING ==========

    async def record_lesson(
        self,
        lesson_type: LessonType,
        source: FeedbackSource,
        company_id: str,
        actual_outcome: str,
        lesson_learned: str,
        context: Dict[str, Any],
        job_id: Optional[str] = None,
        customer_id: Optional[str] = None,
        original_recommendation: Optional[str] = None,
        correction_reason: Optional[str] = None,
        impact_score: float = 0.0,
        confidence: float = 0.8
    ) -> Lesson:
        """
        Record a new lesson learned.

        Args:
            lesson_type: Type of lesson
            source: Who provided the feedback
            company_id: Company identifier
            actual_outcome: What actually happened
            lesson_learned: The insight/lesson
            context: Contextual information
            job_id: Related job ID
            customer_id: Related customer ID
            original_recommendation: What AI recommended
            correction_reason: Why it was corrected
            impact_score: -1 to 1 impact rating
            confidence: Confidence in the lesson

        Returns:
            Recorded Lesson
        """
        import uuid
        lesson_id = f"lesson_{uuid.uuid4().hex[:12]}"

        lesson = Lesson(
            id=lesson_id,
            lesson_type=lesson_type,
            source=source,
            company_id=company_id,
            job_id=job_id,
            customer_id=customer_id,
            context=context,
            job_type=context.get("job_type"),
            equipment_type=context.get("equipment_type"),
            state=context.get("state"),
            zip_code=context.get("zip_code"),
            original_recommendation=original_recommendation,
            actual_outcome=actual_outcome,
            correction_reason=correction_reason,
            lesson_learned=lesson_learned,
            impact_score=impact_score,
            confidence=confidence
        )

        # Generate embedding for semantic search
        lesson.embedding = await self._generate_embedding(lesson)

        # Store in PostgreSQL
        if self.db:
            await self._store_lesson_db(lesson)

        # Store in Pinecone for vector search
        if self.pinecone_key:
            await self._store_lesson_pinecone(lesson)

        # Invalidate cache
        self._invalidate_cache(company_id)

        return lesson

    async def record_technician_override(
        self,
        job_id: str,
        company_id: str,
        field_overridden: str,
        original_value: Any,
        new_value: Any,
        reason: str,
        technician_id: str,
        context: Dict[str, Any]
    ) -> Lesson:
        """
        Record when a technician overrides AI recommendation.
        Implements the "ask why" feedback loop.

        Args:
            job_id: Job identifier
            company_id: Company identifier
            field_overridden: What field was changed
            original_value: AI's recommendation
            new_value: Technician's correction
            reason: Why the technician made this change
            technician_id: Who made the change
            context: Job context

        Returns:
            Recorded Lesson
        """
        # Generate lesson learned from the override
        lesson_text = await self._analyze_override(
            field_overridden, original_value, new_value, reason, context
        )

        return await self.record_lesson(
            lesson_type=LessonType.OVERRIDE,
            source=FeedbackSource.TECHNICIAN,
            company_id=company_id,
            job_id=job_id,
            actual_outcome=f"Technician changed {field_overridden} from {original_value} to {new_value}",
            lesson_learned=lesson_text,
            context={
                **context,
                "field_overridden": field_overridden,
                "original_value": original_value,
                "new_value": new_value,
                "technician_id": technician_id
            },
            original_recommendation=str(original_value),
            correction_reason=reason,
            impact_score=0.3,  # Moderate positive - learning opportunity
            confidence=0.9    # High confidence - direct feedback
        )

    async def record_job_outcome(
        self,
        job_id: str,
        company_id: str,
        customer_id: str,
        context: Dict[str, Any],
        success: bool,
        customer_satisfaction: Optional[int] = None,
        issues_encountered: Optional[List[str]] = None,
        technician_notes: Optional[str] = None
    ) -> Lesson:
        """
        Record job outcome for learning.

        Args:
            job_id: Job identifier
            company_id: Company identifier
            customer_id: Customer identifier
            context: Job context
            success: Whether job was successful
            customer_satisfaction: 1-5 rating
            issues_encountered: List of issues
            technician_notes: Technician's notes

        Returns:
            Recorded Lesson
        """
        # Determine lesson type and impact
        if success and customer_satisfaction and customer_satisfaction >= 4:
            lesson_type = LessonType.SUCCESS
            impact_score = 0.8
        elif not success or (issues_encountered and len(issues_encountered) > 0):
            lesson_type = LessonType.FAILURE
            impact_score = -0.5
        else:
            lesson_type = LessonType.SUCCESS
            impact_score = 0.3

        # Generate lesson from outcome
        outcome_summary = f"Job {'completed successfully' if success else 'had issues'}."
        if issues_encountered:
            outcome_summary += f" Issues: {', '.join(issues_encountered)}"
        if technician_notes:
            outcome_summary += f" Notes: {technician_notes}"

        lesson_text = await self._generate_lesson_from_outcome(
            context, success, issues_encountered, technician_notes
        )

        return await self.record_lesson(
            lesson_type=lesson_type,
            source=FeedbackSource.SYSTEM,
            company_id=company_id,
            job_id=job_id,
            customer_id=customer_id,
            actual_outcome=outcome_summary,
            lesson_learned=lesson_text,
            context={
                **context,
                "success": success,
                "customer_satisfaction": customer_satisfaction,
                "issues_encountered": issues_encountered
            },
            impact_score=impact_score,
            confidence=0.85 if success else 0.75
        )

    # ========== LESSON RETRIEVAL ==========

    async def get_relevant_lessons(
        self,
        company_id: str,
        context: Dict[str, Any],
        limit: int = 5,
        min_confidence: float = 0.5
    ) -> List[Dict]:
        """
        Get lessons relevant to current context.

        Args:
            company_id: Company identifier
            context: Current job/situation context
            limit: Maximum lessons to return
            min_confidence: Minimum confidence threshold

        Returns:
            List of relevant lessons with similarity scores
        """
        # Check cache first
        cache_key = self._get_cache_key(company_id, context)
        if cache_key in self._lesson_cache:
            if datetime.utcnow() - self._cache_timestamps.get(cache_key, datetime.min) < self._cache_ttl:
                return self._lesson_cache[cache_key]

        # Generate embedding for context
        context_embedding = await self._generate_context_embedding(context)

        # Query Pinecone for similar lessons
        if self.pinecone_key and context_embedding:
            lessons = await self._query_pinecone(
                company_id, context_embedding, limit * 2
            )
        else:
            lessons = await self._query_db_fallback(company_id, context, limit * 2)

        # Filter by confidence and rerank
        filtered = [
            l for l in lessons
            if l.get("confidence", 0) >= min_confidence
        ]

        # Sort by relevance and impact
        filtered.sort(key=lambda l: (
            l.get("similarity", 0) * 0.6 +
            abs(l.get("impact_score", 0)) * 0.4
        ), reverse=True)

        result = filtered[:limit]

        # Update cache
        self._lesson_cache[cache_key] = result
        self._cache_timestamps[cache_key] = datetime.utcnow()

        # Update usage statistics
        for lesson in result:
            await self._record_lesson_applied(lesson["id"])

        return result

    async def get_lessons_for_customer(
        self,
        customer_id: str,
        company_id: str,
        limit: int = 3
    ) -> List[Dict]:
        """
        Get lessons specific to a customer (for repeat visits).

        Args:
            customer_id: Customer identifier
            company_id: Company identifier
            limit: Maximum lessons

        Returns:
            Customer-specific lessons
        """
        if self.db:
            rows = await self.db.fetch(
                """SELECT * FROM lessons_learned
                   WHERE customer_id = $1 AND company_id = $2
                   AND confidence >= 0.6
                   ORDER BY impact_score DESC, created_at DESC
                   LIMIT $3""",
                customer_id, company_id, limit
            )
            return [self._row_to_lesson_dict(r) for r in rows]
        return []

    async def cite_lessons_in_proposal(
        self,
        company_id: str,
        job_context: Dict[str, Any],
        proposal_type: str
    ) -> str:
        """
        Generate citations for lessons to include in proposals.
        Example: "In the past, we've found that..."

        Args:
            company_id: Company identifier
            job_context: Current job context
            proposal_type: Type of proposal

        Returns:
            Formatted citation text
        """
        lessons = await self.get_relevant_lessons(
            company_id=company_id,
            context={**job_context, "proposal_type": proposal_type},
            limit=3,
            min_confidence=0.7
        )

        if not lessons:
            return ""

        citations = []
        for lesson in lessons:
            if lesson["lesson_type"] == LessonType.BEST_PRACTICE.value:
                citations.append(f"Based on our experience: {lesson['lesson_learned']}")
            elif lesson["lesson_type"] == LessonType.REGULATION.value:
                citations.append(f"Important note: {lesson['lesson_learned']}")
            elif lesson["lesson_type"] == LessonType.SUCCESS.value:
                citations.append(f"In similar jobs, we've found: {lesson['lesson_learned']}")
            elif lesson["lesson_type"] == LessonType.OVERRIDE.value:
                citations.append(f"Our technicians recommend: {lesson['lesson_learned']}")

        return "\n".join(citations)

    # ========== FEEDBACK PROCESSING ==========

    async def process_feedback(
        self,
        lesson_id: str,
        was_helpful: bool,
        feedback_notes: Optional[str] = None
    ) -> Dict:
        """
        Process feedback on a lesson's usefulness.

        Args:
            lesson_id: Lesson identifier
            was_helpful: Whether the lesson was helpful
            feedback_notes: Additional notes

        Returns:
            Updated lesson stats
        """
        if self.db:
            if was_helpful:
                await self.db.execute(
                    """UPDATE lessons_learned
                       SET times_helpful = times_helpful + 1,
                           confidence = LEAST(1.0, confidence + 0.02)
                       WHERE id = $1""",
                    lesson_id
                )
            else:
                await self.db.execute(
                    """UPDATE lessons_learned
                       SET confidence = GREATEST(0.1, confidence - 0.05)
                       WHERE id = $1""",
                    lesson_id
                )

            if feedback_notes:
                await self.db.execute(
                    """INSERT INTO lesson_feedback (lesson_id, was_helpful, notes, created_at)
                       VALUES ($1, $2, $3, NOW())""",
                    lesson_id, was_helpful, feedback_notes
                )

        return {"lesson_id": lesson_id, "feedback_recorded": True}

    # ========== AI ANALYSIS ==========

    async def _analyze_override(
        self,
        field: str,
        original: Any,
        new: Any,
        reason: str,
        context: Dict
    ) -> str:
        """Use Claude to generate a lesson from an override."""
        prompt = f"""A technician overrode an AI recommendation during a job. Analyze this and generate a concise lesson learned.

Field Changed: {field}
AI Recommendation: {original}
Technician's Value: {new}
Technician's Reason: {reason}

Job Context:
{json.dumps(context, indent=2, default=str)}

Generate a single, actionable lesson learned that can be applied to similar future situations.
Format: "For [situation], [specific recommendation] because [reason]."

Keep it under 100 words. Be specific and actionable."""

        try:
            response = self.client.messages.create(
                model=settings.AGENT_MODEL,
                max_tokens=200,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text.strip()
        except Exception:
            return f"When {context.get('job_type', 'performing similar work')}, consider {field} value of {new} instead of {original}. Reason: {reason}"

    async def _generate_lesson_from_outcome(
        self,
        context: Dict,
        success: bool,
        issues: Optional[List[str]],
        notes: Optional[str]
    ) -> str:
        """Generate lesson from job outcome."""
        prompt = f"""A job was completed. Generate a brief lesson learned.

Job Type: {context.get('job_type', 'Unknown')}
Equipment: {context.get('equipment_type', 'Unknown')}
Location: {context.get('state', 'Unknown')}
Success: {success}
Issues: {issues or 'None'}
Technician Notes: {notes or 'None'}

Generate a concise, actionable lesson that can help with similar future jobs.
If successful, note what worked well. If issues occurred, note what to watch for.
Keep it under 75 words."""

        try:
            response = self.client.messages.create(
                model=settings.AGENT_MODEL,
                max_tokens=150,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text.strip()
        except Exception:
            if success:
                return f"Job type '{context.get('job_type')}' completed successfully following standard procedures."
            return f"Job type '{context.get('job_type')}' encountered issues: {', '.join(issues or ['Unknown'])}. Review before similar jobs."

    # ========== EMBEDDING & VECTOR SEARCH ==========

    async def _generate_embedding(self, lesson: Lesson) -> Optional[List[float]]:
        """Generate embedding for a lesson."""
        text = f"{lesson.lesson_type.value}: {lesson.lesson_learned}. Context: {lesson.job_type} {lesson.equipment_type} {lesson.state}"
        return await self._generate_context_embedding({"text": text})

    async def _generate_context_embedding(self, context: Dict) -> Optional[List[float]]:
        """Generate embedding for context using a simple approach."""
        # In production, use OpenAI or Cohere embeddings
        # For now, create a simple hash-based pseudo-embedding
        text = json.dumps(context, sort_keys=True, default=str)
        hash_bytes = hashlib.sha256(text.encode()).digest()

        # Convert to list of floats (simplified embedding)
        embedding = [float(b) / 255.0 for b in hash_bytes]

        # Pad to standard dimension (1536 for OpenAI compatibility)
        while len(embedding) < 1536:
            embedding.extend(embedding[:min(len(embedding), 1536 - len(embedding))])

        return embedding[:1536]

    async def _query_pinecone(
        self,
        company_id: str,
        embedding: List[float],
        limit: int
    ) -> List[Dict]:
        """Query Pinecone for similar lessons."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.pinecone_host}/query",
                    headers={
                        "Api-Key": self.pinecone_key,
                        "Content-Type": "application/json"
                    },
                    json={
                        "vector": embedding,
                        "topK": limit,
                        "filter": {"company_id": company_id},
                        "includeMetadata": True
                    },
                    timeout=10.0
                )

                if response.status_code == 200:
                    data = response.json()
                    return [
                        {
                            **match.get("metadata", {}),
                            "id": match["id"],
                            "similarity": match["score"]
                        }
                        for match in data.get("matches", [])
                    ]
        except Exception:
            pass

        return await self._query_db_fallback(company_id, {}, limit)

    async def _store_lesson_pinecone(self, lesson: Lesson):
        """Store lesson embedding in Pinecone."""
        if not lesson.embedding:
            return

        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{self.pinecone_host}/vectors/upsert",
                    headers={
                        "Api-Key": self.pinecone_key,
                        "Content-Type": "application/json"
                    },
                    json={
                        "vectors": [{
                            "id": lesson.id,
                            "values": lesson.embedding,
                            "metadata": {
                                "company_id": lesson.company_id,
                                "lesson_type": lesson.lesson_type.value,
                                "job_type": lesson.job_type,
                                "equipment_type": lesson.equipment_type,
                                "state": lesson.state,
                                "lesson_learned": lesson.lesson_learned,
                                "impact_score": lesson.impact_score,
                                "confidence": lesson.confidence,
                                "created_at": lesson.created_at.isoformat()
                            }
                        }]
                    },
                    timeout=10.0
                )
        except Exception:
            pass

    # ========== DATABASE OPERATIONS ==========

    async def _store_lesson_db(self, lesson: Lesson):
        """Store lesson in PostgreSQL."""
        if not self.db:
            return

        await self.db.execute(
            """INSERT INTO lessons_learned (
                id, lesson_type, source, company_id, job_id, customer_id,
                context, job_type, equipment_type, state, zip_code,
                original_recommendation, actual_outcome, correction_reason,
                lesson_learned, impact_score, confidence,
                times_applied, times_helpful, created_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20)""",
            lesson.id, lesson.lesson_type.value, lesson.source.value,
            lesson.company_id, lesson.job_id, lesson.customer_id,
            json.dumps(lesson.context, default=str),
            lesson.job_type, lesson.equipment_type, lesson.state, lesson.zip_code,
            lesson.original_recommendation, lesson.actual_outcome, lesson.correction_reason,
            lesson.lesson_learned, lesson.impact_score, lesson.confidence,
            lesson.times_applied, lesson.times_helpful, lesson.created_at
        )

    async def _query_db_fallback(
        self,
        company_id: str,
        context: Dict,
        limit: int
    ) -> List[Dict]:
        """Fallback query using PostgreSQL."""
        if not self.db:
            return []

        # Build query with optional filters
        query = """
            SELECT * FROM lessons_learned
            WHERE company_id = $1
            AND confidence >= 0.5
        """
        params = [company_id]
        param_count = 1

        if context.get("job_type"):
            param_count += 1
            query += f" AND job_type = ${param_count}"
            params.append(context["job_type"])

        if context.get("equipment_type"):
            param_count += 1
            query += f" AND equipment_type = ${param_count}"
            params.append(context["equipment_type"])

        if context.get("state"):
            param_count += 1
            query += f" AND state = ${param_count}"
            params.append(context["state"])

        query += f" ORDER BY impact_score DESC, confidence DESC, created_at DESC LIMIT {limit}"

        rows = await self.db.fetch(query, *params)
        return [self._row_to_lesson_dict(r) for r in rows]

    async def _record_lesson_applied(self, lesson_id: str):
        """Record that a lesson was applied."""
        if self.db:
            await self.db.execute(
                """UPDATE lessons_learned
                   SET times_applied = times_applied + 1,
                       last_applied = NOW()
                   WHERE id = $1""",
                lesson_id
            )

    def _row_to_lesson_dict(self, row) -> Dict:
        """Convert database row to lesson dictionary."""
        return {
            "id": row["id"],
            "lesson_type": row["lesson_type"],
            "source": row["source"],
            "job_type": row["job_type"],
            "equipment_type": row["equipment_type"],
            "state": row["state"],
            "lesson_learned": row["lesson_learned"],
            "impact_score": row["impact_score"],
            "confidence": row["confidence"],
            "times_applied": row["times_applied"],
            "times_helpful": row["times_helpful"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None
        }

    # ========== CACHE MANAGEMENT ==========

    def _get_cache_key(self, company_id: str, context: Dict) -> str:
        """Generate cache key from company and context."""
        context_str = json.dumps(context, sort_keys=True, default=str)
        return hashlib.md5(f"{company_id}:{context_str}".encode()).hexdigest()

    def _invalidate_cache(self, company_id: str):
        """Invalidate cache for a company."""
        keys_to_remove = [
            k for k in self._lesson_cache.keys()
            if k.startswith(company_id) or company_id in str(self._lesson_cache.get(k, []))
        ]
        for key in keys_to_remove:
            self._lesson_cache.pop(key, None)
            self._cache_timestamps.pop(key, None)


# Database schema
LESSONS_LEARNED_SCHEMA = """
CREATE TABLE IF NOT EXISTS lessons_learned (
    id VARCHAR(255) PRIMARY KEY,
    lesson_type VARCHAR(50) NOT NULL,
    source VARCHAR(50) NOT NULL,
    company_id VARCHAR(255) NOT NULL,
    job_id VARCHAR(255),
    customer_id VARCHAR(255),

    context JSONB,
    job_type VARCHAR(100),
    equipment_type VARCHAR(100),
    state VARCHAR(10),
    zip_code VARCHAR(20),

    original_recommendation TEXT,
    actual_outcome TEXT NOT NULL,
    correction_reason TEXT,
    lesson_learned TEXT NOT NULL,

    impact_score FLOAT DEFAULT 0,
    confidence FLOAT DEFAULT 0.5,
    times_applied INTEGER DEFAULT 0,
    times_helpful INTEGER DEFAULT 0,

    created_at TIMESTAMP DEFAULT NOW(),
    last_applied TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_lessons_company ON lessons_learned(company_id);
CREATE INDEX IF NOT EXISTS idx_lessons_type ON lessons_learned(lesson_type);
CREATE INDEX IF NOT EXISTS idx_lessons_job_type ON lessons_learned(job_type);
CREATE INDEX IF NOT EXISTS idx_lessons_equipment ON lessons_learned(equipment_type);
CREATE INDEX IF NOT EXISTS idx_lessons_state ON lessons_learned(state);
CREATE INDEX IF NOT EXISTS idx_lessons_customer ON lessons_learned(customer_id);
CREATE INDEX IF NOT EXISTS idx_lessons_confidence ON lessons_learned(confidence);

CREATE TABLE IF NOT EXISTS lesson_feedback (
    id SERIAL PRIMARY KEY,
    lesson_id VARCHAR(255) REFERENCES lessons_learned(id),
    was_helpful BOOLEAN NOT NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
"""


async def create_lessons_learned(db_connection=None) -> LessonsLearned:
    """
    Create and initialize Lessons Learned system.

    Args:
        db_connection: PostgreSQL connection

    Returns:
        Initialized LessonsLearned
    """
    lessons = LessonsLearned(db_connection)

    if db_connection:
        await db_connection.execute(LESSONS_LEARNED_SCHEMA)

    return lessons
