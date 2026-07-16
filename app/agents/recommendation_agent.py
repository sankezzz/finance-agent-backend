"""Recommendation Agent (LLM-driven, grounded in the snapshot) — STUB.

Will: read this run's financial snapshot/metrics, generate actionable
recommendations grounded in those numbers, and write them keyed by
run_id. No-op for now.
"""

from app.agents.base import AgentContext, BaseAgent
from app.pipeline.stages import Stage


class RecommendationAgent(BaseAgent):
    stage = Stage.recommend

    def run(self, ctx: AgentContext) -> None:
        # TODO: read snapshot -> LLM recommendations -> persist recommendations(run_id).
        return None
