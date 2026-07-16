"""Dashboard routes.

Composes one payload for the frontend dashboard from a user's most recent
completed run: profile + metrics snapshot + recommendations + asset/liability
lists + subscriptions.
"""

from fastapi import APIRouter, HTTPException

from app.models.dashboard import DashboardResponse, SubscriptionItem
from app.models.fact import FactKind
from app.services import (
    fact_service,
    financial_service,
    onboarding_service,
    pipeline_service,
    recommendation_service,
    transaction_service,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/{user_id}", response_model=DashboardResponse)
def get_dashboard(user_id: str) -> DashboardResponse:
    """Return the composed dashboard from the user's latest analysis."""
    user = onboarding_service.get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    snapshot = financial_service.get_latest_snapshot(user_id)
    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail="No analysis yet. Upload documents and run the pipeline first.",
        )
    run_id = str(snapshot.run_id)
    run = pipeline_service.get_run(run_id)

    facts = fact_service.list_facts(run_id)
    recs = recommendation_service.get(run_id)
    subs = transaction_service.list_subscriptions(run_id)

    # Distinct subscriptions by merchant (a merchant charged monthly appears once).
    seen: set[str] = set()
    subscriptions: list[SubscriptionItem] = []
    for t in subs:
        name = (t.merchant or t.description).strip()
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        subscriptions.append(SubscriptionItem(merchant=name, amount=t.amount, category=t.category))

    return DashboardResponse(
        user=user,
        run_id=snapshot.run_id,
        run_status=run.status.value if run else "done",
        generated_at=snapshot.created_at,
        metrics=snapshot,
        recommendations_summary=recs.summary if recs else "",
        recommendations=recs.recommendations if recs else [],
        assets=[f for f in facts if f.kind == FactKind.asset],
        liabilities=[f for f in facts if f.kind == FactKind.liability],
        subscriptions=subscriptions,
    )
