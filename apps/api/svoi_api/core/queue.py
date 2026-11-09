"""Job producer: enqueue(job, queue) with _job_id=dedupe_key (docs/tech.md section 8)."""

from typing import Literal, Protocol

from arq.connections import ArqRedis
from svoi_contracts.jobs import JobBase

QueueName = Literal["api", "bot"]


class Queue(Protocol):
    """Where services put jobs."""

    async def enqueue(self, job: JobBase, queue: QueueName) -> None:
        """Put the job on the queue unless the same dedupe_key is still waiting."""


class ArqQueue:
    """arq over Redis."""

    def __init__(self, redis: ArqRedis) -> None:
        self._redis = redis

    async def enqueue(self, job: JobBase, queue: QueueName) -> None:
        """arq skips a job whose _job_id is already queued."""
        await self._redis.enqueue_job(
            job.topic, job.model_dump(mode="json"), _job_id=job.dedupe_key, _queue_name=queue
        )


class RecordingQueue:
    """Tests: keeps jobs instead of sending them."""

    def __init__(self) -> None:
        self.jobs: list[tuple[QueueName, JobBase]] = []

    async def enqueue(self, job: JobBase, queue: QueueName) -> None:
        """Record once per dedupe_key, like arq."""
        if all(j.dedupe_key != job.dedupe_key for _, j in self.jobs):
            self.jobs.append((queue, job))

    def of(self, kind: type[JobBase]) -> list[JobBase]:
        """Recorded jobs of one payload type."""
        return [j for _, j in self.jobs if isinstance(j, kind)]
