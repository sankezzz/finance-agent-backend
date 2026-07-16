"""Categorization Agent (hybrid: rules first, LLM fallback) — STUB.

Will: read this run's normalized transactions, categorize them (rules for
known merchants, LLM fallback for unknown), flag recurring expenses and
subscriptions, and write the categories back. No-op for now.
"""

from app.agents.base import AgentContext, BaseAgent
from app.pipeline.stages import Stage


class CategorizerAgent(BaseAgent):
    stage = Stage.categorize

    def run(self, ctx: AgentContext) -> None:
        # TODO: rules -> LLM fallback -> update transaction categories/flags.
        return None
