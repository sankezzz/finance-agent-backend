"""User and onboarding schemas.

Captures the user profile fields collected at onboarding: name, age,
monthly income, dependents, existing loans, and optional financial goals.
"""

from datetime import date, datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class LoanType(str, Enum):
    home = "home"
    personal = "personal"
    auto = "auto"
    education = "education"
    credit_card = "credit_card"
    other = "other"


class Loan(BaseModel):
    """A self-declared existing loan (feeds debt-ratio / EMI calcs)."""

    type: LoanType
    outstanding: float = Field(ge=0, description="Remaining principal owed")
    monthly_emi: float = Field(ge=0, description="Monthly EMI payment")


class FinancialGoal(BaseModel):
    """An optional financial goal (feeds goal-planning projections)."""

    name: str = Field(min_length=1)
    target_amount: float = Field(gt=0)
    target_date: date | None = None


class UserCreate(BaseModel):
    """Payload submitted from the onboarding form to create a profile."""

    name: str = Field(min_length=1)
    age: int = Field(ge=1, le=120)
    monthly_income: float = Field(ge=0)
    dependents: int = Field(ge=0, default=0)
    existing_loans: list[Loan] = Field(default_factory=list)
    financial_goals: list[FinancialGoal] = Field(default_factory=list)


class User(UserCreate):
    """A stored user profile as returned by the API."""

    id: UUID
    created_at: datetime
