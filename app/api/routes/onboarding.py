"""Onboarding routes.

Endpoints for capturing the user profile: name, age, monthly income,
dependents, existing loans, and optional financial goals. This is the
first step of the app; it returns a user_id the client stores and sends
on subsequent document-upload and pipeline requests.
"""

from fastapi import APIRouter, HTTPException

from app.models.user import User, UserCreate
from app.services import onboarding_service

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.post("", response_model=User, status_code=201)
def onboard_user(payload: UserCreate) -> User:
    """Create a user profile and return it (including the generated id)."""
    return onboarding_service.create_user(payload)


@router.get("/{user_id}", response_model=User)
def get_profile(user_id: str) -> User:
    """Return a previously onboarded user profile."""
    user = onboarding_service.get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user
