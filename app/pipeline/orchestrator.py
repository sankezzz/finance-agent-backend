"""Pipeline orchestrator.

Sequences the parser, categorizer, analysis, and recommendation agents
by run_id in stage order, updating the run's status in the DB as each
stage starts/completes/fails. A linear sequencer, not a graph executor.
Intended to run in the background (FastAPI BackgroundTasks).
"""

from app.agents.analysis_agent import AnalysisAgent
from app.agents.base import AgentContext, BaseAgent
from app.agents.categorizer_agent import CategorizerAgent
from app.agents.parser_agent import ParserAgent
from app.agents.recommendation_agent import RecommendationAgent
from app.models.pipeline import StageStatus
from app.services import pipeline_service


def _build_agents() -> list[BaseAgent]:
    """Agents in execution order. Built per-run so nothing is created at import time."""
    return [
        ParserAgent(),
        CategorizerAgent(),
        AnalysisAgent(),
        RecommendationAgent(),
    ]


def run_pipeline(run_id: str) -> None:
    """Run every stage in order for a run, updating status as it goes."""
    run = pipeline_service.get_run(run_id)
    if run is None:
        return

    pipeline_service.mark_running(run_id)
    ctx = AgentContext(run_id=run_id, user_id=str(run.user_id))

    for agent in _build_agents():
        pipeline_service.set_stage(run_id, agent.stage, StageStatus.running)
        try:
            agent.run(ctx)
        except Exception as exc:  # noqa: BLE001 — any agent failure fails the run
            pipeline_service.set_stage(
                run_id, agent.stage, StageStatus.failed, error=str(exc)
            )
            pipeline_service.mark_failed(run_id, f"{agent.stage.value}: {exc}")
            return
        pipeline_service.set_stage(run_id, agent.stage, StageStatus.done)

    pipeline_service.mark_done(run_id)
