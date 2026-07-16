"""Base agent contract.

Defines the BaseAgent ABC that every pipeline agent implements. Agents
do not call each other directly: each agent reads its input for a given
run_id from the DB and writes its output back to the DB, so the
orchestrator can sequence them linearly without shared in-memory state.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.pipeline.stages import Stage


@dataclass(slots=True)
class AgentContext:
    """The minimal handle an agent needs to locate its DB input/output."""

    run_id: str
    user_id: str


class BaseAgent(ABC):
    """Contract shared by every pipeline agent."""

    #: The pipeline stage this agent fulfills (set by each subclass).
    stage: Stage

    @abstractmethod
    def run(self, ctx: AgentContext) -> None:
        """Read this stage's input for ctx.run_id, do the work, write output back."""
