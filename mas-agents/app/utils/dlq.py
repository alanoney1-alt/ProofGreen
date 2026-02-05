"""
ProofGreen MAS - Dead Letter Queue (DLQ)
Handles failed operations for later retry or manual intervention.
"""

import json
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import structlog
from prometheus_client import Counter, Gauge


logger = structlog.get_logger(__name__)

# Prometheus metrics
DLQ_MESSAGES_TOTAL = Counter(
    'proofgreen_dlq_messages_total',
    'Total messages sent to DLQ',
    ['queue', 'reason']
)

DLQ_SIZE_GAUGE = Gauge(
    'proofgreen_dlq_size',
    'Current DLQ size',
    ['queue']
)


class DLQReason(str, Enum):
    """Reasons for DLQ entry."""
    MAX_RETRIES_EXCEEDED = "max_retries_exceeded"
    VALIDATION_FAILED = "validation_failed"
    EXTERNAL_SERVICE_ERROR = "external_service_error"
    TIMEOUT = "timeout"
    CIRCUIT_BREAKER_OPEN = "circuit_breaker_open"
    UNKNOWN_ERROR = "unknown_error"


@dataclass
class DLQMessage:
    """Message stored in Dead Letter Queue."""
    id: str
    queue: str
    payload: Dict[str, Any]
    reason: DLQReason
    error_message: str
    original_timestamp: str
    dlq_timestamp: str
    retry_count: int = 0
    max_retries: int = 3
    metadata: Dict[str, Any] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'DLQMessage':
        """Create from dictionary."""
        data['reason'] = DLQReason(data['reason'])
        return cls(**data)


class DeadLetterQueue:
    """
    Dead Letter Queue implementation.

    Supports:
    - In-memory storage (for development)
    - PostgreSQL storage (for production)
    - Redis storage (for high throughput)
    """

    def __init__(
        self,
        db_connection=None,
        redis_client=None,
        default_max_retries: int = 3
    ):
        self.db = db_connection
        self.redis = redis_client
        self.default_max_retries = default_max_retries

        # In-memory fallback
        self._in_memory_queues: Dict[str, List[DLQMessage]] = {}

    async def send_to_dlq(
        self,
        queue: str,
        payload: Dict[str, Any],
        reason: DLQReason,
        error_message: str,
        original_timestamp: str = None,
        metadata: Dict[str, Any] = None
    ) -> str:
        """
        Send a failed message to the DLQ.

        Args:
            queue: Queue name (e.g., 'webhook_processing', 'workflow_execution')
            payload: Original message payload
            reason: Reason for DLQ entry
            error_message: Error message from failure
            original_timestamp: When the original operation was attempted
            metadata: Additional metadata

        Returns:
            DLQ message ID
        """
        import uuid

        message = DLQMessage(
            id=str(uuid.uuid4()),
            queue=queue,
            payload=payload,
            reason=reason,
            error_message=error_message,
            original_timestamp=original_timestamp or datetime.utcnow().isoformat(),
            dlq_timestamp=datetime.utcnow().isoformat(),
            retry_count=0,
            max_retries=self.default_max_retries,
            metadata=metadata or {}
        )

        # Store message
        if self.db:
            await self._store_to_postgres(message)
        elif self.redis:
            await self._store_to_redis(message)
        else:
            self._store_in_memory(message)

        # Update metrics
        DLQ_MESSAGES_TOTAL.labels(queue=queue, reason=reason.value).inc()

        logger.warning(
            "dlq_message_added",
            message_id=message.id,
            queue=queue,
            reason=reason.value,
            error=error_message
        )

        return message.id

    async def get_messages(
        self,
        queue: str,
        limit: int = 100,
        include_retried: bool = False
    ) -> List[DLQMessage]:
        """Get messages from DLQ."""
        if self.db:
            return await self._get_from_postgres(queue, limit, include_retried)
        elif self.redis:
            return await self._get_from_redis(queue, limit)
        else:
            return self._get_from_memory(queue, limit)

    async def retry_message(
        self,
        message_id: str,
        processor: Callable[[Dict], Any]
    ) -> bool:
        """
        Retry a DLQ message.

        Args:
            message_id: DLQ message ID
            processor: Function to process the payload

        Returns:
            True if retry succeeded, False otherwise
        """
        message = await self.get_message(message_id)

        if not message:
            logger.error("dlq_message_not_found", message_id=message_id)
            return False

        if message.retry_count >= message.max_retries:
            logger.error(
                "dlq_max_retries_exceeded",
                message_id=message_id,
                retry_count=message.retry_count
            )
            return False

        try:
            # Attempt to process
            await processor(message.payload)

            # Success - remove from DLQ
            await self.remove_message(message_id)

            logger.info(
                "dlq_retry_success",
                message_id=message_id,
                queue=message.queue
            )
            return True

        except Exception as e:
            # Update retry count
            message.retry_count += 1
            await self._update_message(message)

            logger.warning(
                "dlq_retry_failed",
                message_id=message_id,
                retry_count=message.retry_count,
                error=str(e)
            )
            return False

    async def get_message(self, message_id: str) -> Optional[DLQMessage]:
        """Get a specific DLQ message."""
        if self.db:
            return await self._get_message_from_postgres(message_id)
        elif self.redis:
            return await self._get_message_from_redis(message_id)
        else:
            return self._get_message_from_memory(message_id)

    async def remove_message(self, message_id: str) -> bool:
        """Remove a message from DLQ (after successful retry or manual resolution)."""
        if self.db:
            return await self._remove_from_postgres(message_id)
        elif self.redis:
            return await self._remove_from_redis(message_id)
        else:
            return self._remove_from_memory(message_id)

    async def get_queue_stats(self, queue: str = None) -> Dict[str, Any]:
        """Get DLQ statistics."""
        stats = {
            "total_messages": 0,
            "by_reason": {},
            "by_queue": {},
            "oldest_message": None
        }

        if self.db:
            stats = await self._get_stats_from_postgres(queue)
        else:
            # In-memory stats
            for q_name, messages in self._in_memory_queues.items():
                if queue and q_name != queue:
                    continue

                stats["total_messages"] += len(messages)
                stats["by_queue"][q_name] = len(messages)

                for msg in messages:
                    reason = msg.reason.value
                    stats["by_reason"][reason] = stats["by_reason"].get(reason, 0) + 1

        return stats

    # PostgreSQL implementation
    async def _store_to_postgres(self, message: DLQMessage):
        """Store message in PostgreSQL."""
        await self.db.execute("""
            INSERT INTO dead_letter_queue (
                id, queue, payload, reason, error_message,
                original_timestamp, dlq_timestamp, retry_count,
                max_retries, metadata
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        """,
            message.id,
            message.queue,
            json.dumps(message.payload),
            message.reason.value,
            message.error_message,
            message.original_timestamp,
            message.dlq_timestamp,
            message.retry_count,
            message.max_retries,
            json.dumps(message.metadata)
        )

    async def _get_from_postgres(
        self,
        queue: str,
        limit: int,
        include_retried: bool
    ) -> List[DLQMessage]:
        """Get messages from PostgreSQL."""
        query = """
            SELECT * FROM dead_letter_queue
            WHERE queue = $1
        """
        if not include_retried:
            query += " AND retry_count < max_retries"
        query += " ORDER BY dlq_timestamp DESC LIMIT $2"

        rows = await self.db.fetch(query, queue, limit)
        return [self._row_to_message(row) for row in rows]

    async def _get_message_from_postgres(self, message_id: str) -> Optional[DLQMessage]:
        """Get specific message from PostgreSQL."""
        row = await self.db.fetchrow(
            "SELECT * FROM dead_letter_queue WHERE id = $1",
            message_id
        )
        return self._row_to_message(row) if row else None

    async def _remove_from_postgres(self, message_id: str) -> bool:
        """Remove message from PostgreSQL."""
        result = await self.db.execute(
            "DELETE FROM dead_letter_queue WHERE id = $1",
            message_id
        )
        return True

    async def _update_message(self, message: DLQMessage):
        """Update message in storage."""
        if self.db:
            await self.db.execute("""
                UPDATE dead_letter_queue
                SET retry_count = $2
                WHERE id = $1
            """, message.id, message.retry_count)

    async def _get_stats_from_postgres(self, queue: str = None) -> Dict:
        """Get stats from PostgreSQL."""
        where_clause = "WHERE queue = $1" if queue else ""
        params = [queue] if queue else []

        total = await self.db.fetchval(
            f"SELECT COUNT(*) FROM dead_letter_queue {where_clause}",
            *params
        )

        by_reason = await self.db.fetch(f"""
            SELECT reason, COUNT(*) as count
            FROM dead_letter_queue {where_clause}
            GROUP BY reason
        """, *params)

        return {
            "total_messages": total,
            "by_reason": {row['reason']: row['count'] for row in by_reason}
        }

    def _row_to_message(self, row) -> DLQMessage:
        """Convert database row to DLQMessage."""
        return DLQMessage(
            id=row['id'],
            queue=row['queue'],
            payload=json.loads(row['payload']) if isinstance(row['payload'], str) else row['payload'],
            reason=DLQReason(row['reason']),
            error_message=row['error_message'],
            original_timestamp=row['original_timestamp'],
            dlq_timestamp=row['dlq_timestamp'],
            retry_count=row['retry_count'],
            max_retries=row['max_retries'],
            metadata=json.loads(row['metadata']) if isinstance(row['metadata'], str) else row['metadata']
        )

    # In-memory implementation
    def _store_in_memory(self, message: DLQMessage):
        """Store message in memory."""
        if message.queue not in self._in_memory_queues:
            self._in_memory_queues[message.queue] = []
        self._in_memory_queues[message.queue].append(message)

    def _get_from_memory(self, queue: str, limit: int) -> List[DLQMessage]:
        """Get messages from memory."""
        messages = self._in_memory_queues.get(queue, [])
        return messages[:limit]

    def _get_message_from_memory(self, message_id: str) -> Optional[DLQMessage]:
        """Get specific message from memory."""
        for messages in self._in_memory_queues.values():
            for msg in messages:
                if msg.id == message_id:
                    return msg
        return None

    def _remove_from_memory(self, message_id: str) -> bool:
        """Remove message from memory."""
        for queue, messages in self._in_memory_queues.items():
            for i, msg in enumerate(messages):
                if msg.id == message_id:
                    del messages[i]
                    return True
        return False


# Database schema for DLQ
DLQ_SCHEMA = """
CREATE TABLE IF NOT EXISTS dead_letter_queue (
    id VARCHAR(255) PRIMARY KEY,
    queue VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL,
    reason VARCHAR(50) NOT NULL,
    error_message TEXT,
    original_timestamp TIMESTAMP NOT NULL,
    dlq_timestamp TIMESTAMP NOT NULL,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dlq_queue ON dead_letter_queue(queue);
CREATE INDEX IF NOT EXISTS idx_dlq_reason ON dead_letter_queue(reason);
CREATE INDEX IF NOT EXISTS idx_dlq_timestamp ON dead_letter_queue(dlq_timestamp);
"""
