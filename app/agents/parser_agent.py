"""Document Parser Agent (LLM-driven) — STUB.

Will: read this run's uploaded documents, extract text (pdf/csv/excel),
mask PII via core.security, LLM-parse into normalized records, and write
transactions keyed by run_id. No-op for now so the pipeline wiring runs
end-to-end; real implementation is the next step.
"""

from app.agents.base import AgentContext, BaseAgent
from app.pipeline.stages import Stage


class ParserAgent(BaseAgent):
    stage = Stage.parse

    def run(self, ctx: AgentContext) -> None:
        # TODO: extract -> mask -> LLM parse -> persist transactions(run_id).
        return None
