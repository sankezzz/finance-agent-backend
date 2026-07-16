"""Financial Analysis Agent (thin wrapper over core/finance) — NO LLM.

Reads this run's categorized transactions + facts (and the user's declared
income as a fallback), delegates ALL arithmetic to the pure functions in
core.finance.calculations, and saves the resulting Metrics as the run's
snapshot. Deterministic and auditable — the LLM's job (interpreting these
numbers) belongs to the recommendation agent.
"""

from app.agents.base import AgentContext, BaseAgent
from app.core.finance.calculations import compute_metrics
from app.pipeline.stages import Stage
from app.services import (
    fact_service,
    financial_service,
    onboarding_service,
    transaction_service,
)


class AnalysisAgent(BaseAgent):
    stage = Stage.analyze

    def run(self, ctx: AgentContext) -> None:
        transactions = transaction_service.list_transactions(ctx.run_id)
        facts = fact_service.list_facts(ctx.run_id)
        user = onboarding_service.get_user(ctx.user_id)
        declared_income = user.monthly_income if user else None

        metrics = compute_metrics(
            transactions=transactions,
            facts=facts,
            declared_income=declared_income,
        )
        financial_service.save_snapshot(ctx.run_id, ctx.user_id, metrics)
