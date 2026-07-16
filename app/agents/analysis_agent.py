"""Financial Analysis Agent (thin wrapper over core/finance) — STUB.

Will: read this run's categorized transactions, delegate to the pure
functions in core.finance to compute monthly spending, savings rate, debt
ratio, emergency runway, and health score, and write the snapshot +
metrics. Does NO LLM work. No-op for now.
"""

from app.agents.base import AgentContext, BaseAgent
from app.pipeline.stages import Stage


class AnalysisAgent(BaseAgent):
    stage = Stage.analyze

    def run(self, ctx: AgentContext) -> None:
        # TODO: aggregate transactions -> core.finance calcs -> persist snapshot/metrics.
        return None
