"""Pipeline run schemas.

Defines RunStatus / StageStatus enums and the run schema that tracks a
single pipeline execution (keyed by run_id) as it moves through the
parse -> categorize -> analyze -> recommend stages. The `stages` list is
what the frontend polls to show which agent is currently running.
"""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field

from app.pipeline.stages import STAGE_ORDER, Stage


class RunStatus(str, Enum):
    pending = "pending"
    running = "running"
    done = "done"
    failed = "failed"


class StageStatus(str, Enum):
    pending = "pending"
    running = "running"
    done = "done"
    failed = "failed"


class StageState(BaseModel):
    """Per-stage progress within a run."""

    stage: Stage
    status: StageStatus = StageStatus.pending
    error: str | None = None


class RunRequest(BaseModel):
    """Body for triggering a new pipeline run."""

    user_id: UUID


class Run(BaseModel):
    """A pipeline run as stored/returned by the API."""

    id: UUID
    user_id: UUID
    status: RunStatus = RunStatus.pending
    current_stage: Stage | None = None
    stages: list[StageState] = Field(default_factory=list)
    error: str | None = None
    created_at: datetime
    updated_at: datetime


def initial_stages() -> list[StageState]:
    """The default stage list (all pending) for a freshly created run."""
    return [StageState(stage=stage) for stage in STAGE_ORDER]
