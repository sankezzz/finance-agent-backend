"""Dashboard composition schema.

The single payload the frontend dashboard needs: the user's profile, which run
it reflects, the computed metrics snapshot, the recommendations, the asset /
liability lists (for the debt & asset overview), and the subscriptions list.
`persona` is reserved for the future persona-generation feature.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.fact import FinancialFact
from app.models.financial import Snapshot
from app.models.recommendation import Recommendation
from app.models.user import User


class SubscriptionItem(BaseModel):
    merchant: str
    amount: float
    category: str | None = None


class DashboardResponse(BaseModel):
    user: User
    run_id: UUID
    run_status: str
    generated_at: datetime

    metrics: Snapshot
    recommendations_summary: str = ""
    recommendations: list[Recommendation] = []

    assets: list[FinancialFact] = []
    liabilities: list[FinancialFact] = []
    subscriptions: list[SubscriptionItem] = []

    persona: dict | None = None  # future: generated financial persona
