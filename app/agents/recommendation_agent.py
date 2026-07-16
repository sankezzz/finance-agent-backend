"""Recommendation Agent (LLM-driven, grounded in the snapshot).

Reads this run's financial snapshot (Agent 3's computed metrics) + the user's
profile, and asks the LLM for a short summary plus 3-5 prioritized, actionable
recommendations. The model only ever sees aggregated numbers (no raw
transactions → no PII) and is instructed to cite the real figures, so it can
reason about the finances but never fabricate them.
"""

from app.agents.base import AgentContext, BaseAgent
from app.config import get_settings
from app.llm.client import get_structured_llm
from app.llm.prompts.recommendation import RECOMMENDATION_SYSTEM, build_recommendation_prompt
from app.models.recommendation import RecommendationSet
from app.pipeline.stages import Stage
from app.services import financial_service, onboarding_service, recommendation_service


class RecommendationAgent(BaseAgent):
    stage = Stage.recommend

    def run(self, ctx: AgentContext) -> None:
        snapshot = financial_service.get_snapshot(ctx.run_id)
        if snapshot is None:
            # No metrics (analysis produced nothing) → nothing to recommend.
            return

        user = onboarding_service.get_user(ctx.user_id)
        rec_set = self._generate(snapshot, user)
        recommendation_service.save(ctx.run_id, ctx.user_id, rec_set)

    def _generate(self, snapshot, user) -> RecommendationSet:
        client = get_structured_llm("json")
        settings = get_settings()
        return client.chat.completions.create(
            model=settings.RECOMMENDATION_GROQ_MODEL,
            response_model=RecommendationSet,
            temperature=0.3,
            max_tokens=2048,
            max_retries=2,
            messages=[
                {"role": "system", "content": RECOMMENDATION_SYSTEM},
                {"role": "user", "content": build_recommendation_prompt(snapshot, user)},
            ],
        )
