"""Recommendation schemas.

An actionable recommendation produced by the recommendation agent, grounded
in the run's financial snapshot. RecommendationSet is the LLM output (a short
summary + a prioritized list); StoredRecommendations adds DB fields.
"""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class Priority(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class RecommendationCategory(str, Enum):
    savings = "savings"
    debt = "debt"
    spending = "spending"
    emergency_fund = "emergency_fund"
    investment = "investment"
    income = "income"
    general = "general"


class Recommendation(BaseModel):
    title: str = Field(min_length=1)
    category: RecommendationCategory
    priority: Priority
    rationale: str = Field(min_length=1)   # must cite the actual figures
    action: str = Field(min_length=1)      # a concrete next step


class RecommendationSet(BaseModel):
    """The LLM's output for one run."""

    summary: str = Field(default="")
    recommendations: list[Recommendation] = Field(default_factory=list)


class StoredRecommendations(RecommendationSet):
    """A stored recommendation set (one row per run)."""

    id: UUID
    run_id: UUID
    user_id: UUID
    created_at: datetime
