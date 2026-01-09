"""
Alert Profile API endpoints.

Handles CRUD operations for user alert profiles.
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user, rate_limit
from app.models import User, AlertProfile
from app.schemas.alert_profile import (
    AlertProfileCreate,
    AlertProfileUpdate,
    AlertProfileResponse,
)
from app.config import SUBSCRIPTION_TIERS

router = APIRouter()


@router.get("", response_model=List[AlertProfileResponse])
async def list_alert_profiles(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List all alert profiles for current user.
    """
    profiles = db.query(AlertProfile).filter(
        AlertProfile.user_id == current_user.id
    ).order_by(AlertProfile.created_at.desc()).all()

    return profiles


@router.post("", response_model=AlertProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_alert_profile(
    profile_data: AlertProfileCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit),
):
    """
    Create a new alert profile.

    Subject to subscription tier limits on number of profiles.
    """
    # Check profile limit
    tier_config = SUBSCRIPTION_TIERS.get(
        current_user.subscription_tier,
        SUBSCRIPTION_TIERS["free"]
    )
    max_profiles = tier_config["limits"]["alert_profiles"]

    current_count = db.query(AlertProfile).filter(
        AlertProfile.user_id == current_user.id
    ).count()

    if current_count >= max_profiles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Profile limit reached ({max_profiles}). Upgrade to create more profiles.",
        )

    # Check realtime alerts availability
    if profile_data.alert_frequency == "realtime":
        if not tier_config["limits"].get("realtime_alerts", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Realtime alerts require Pro tier subscription",
            )

    profile = AlertProfile(
        user_id=current_user.id,
        **profile_data.model_dump(),
    )

    db.add(profile)
    db.commit()
    db.refresh(profile)

    return profile


@router.get("/{profile_id}", response_model=AlertProfileResponse)
async def get_alert_profile(
    profile_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get a specific alert profile.
    """
    profile = db.query(AlertProfile).filter(
        AlertProfile.id == profile_id,
        AlertProfile.user_id == current_user.id,
    ).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert profile not found",
        )

    return profile


@router.patch("/{profile_id}", response_model=AlertProfileResponse)
async def update_alert_profile(
    profile_id: UUID,
    profile_data: AlertProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit),
):
    """
    Update an alert profile.
    """
    profile = db.query(AlertProfile).filter(
        AlertProfile.id == profile_id,
        AlertProfile.user_id == current_user.id,
    ).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert profile not found",
        )

    # Check realtime alerts availability
    if profile_data.alert_frequency == "realtime":
        tier_config = SUBSCRIPTION_TIERS.get(
            current_user.subscription_tier,
            SUBSCRIPTION_TIERS["free"]
        )
        if not tier_config["limits"].get("realtime_alerts", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Realtime alerts require Pro tier subscription",
            )

    update_data = profile_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)

    db.commit()
    db.refresh(profile)

    return profile


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert_profile(
    profile_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete an alert profile.
    """
    profile = db.query(AlertProfile).filter(
        AlertProfile.id == profile_id,
        AlertProfile.user_id == current_user.id,
    ).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert profile not found",
        )

    db.delete(profile)
    db.commit()


@router.post("/{profile_id}/test")
async def test_alert_profile(
    profile_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit),
):
    """
    Test an alert profile by finding matching opportunities.

    Returns sample matches without sending actual alerts.
    """
    from app.models import Opportunity
    from sqlalchemy import or_

    profile = db.query(AlertProfile).filter(
        AlertProfile.id == profile_id,
        AlertProfile.user_id == current_user.id,
    ).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert profile not found",
        )

    # Build query similar to alert matching
    query = db.query(Opportunity).filter(
        Opportunity.status == "active",
        Opportunity.likelihood_score >= profile.min_likelihood_score,
    )

    if profile.naics_codes:
        naics_conditions = [
            Opportunity.naics_code.like(f"{code}%")
            for code in profile.naics_codes
        ]
        query = query.filter(or_(*naics_conditions))

    if profile.states:
        query = query.filter(Opportunity.pop_state.in_(profile.states))

    if profile.keywords:
        keyword_conditions = []
        for keyword in profile.keywords:
            keyword_conditions.append(
                or_(
                    Opportunity.title.ilike(f"%{keyword}%"),
                    Opportunity.description.ilike(f"%{keyword}%"),
                )
            )
        query = query.filter(or_(*keyword_conditions))

    matches = query.order_by(Opportunity.likelihood_score.desc()).limit(10).all()

    return {
        "profile_name": profile.name,
        "match_count": len(matches),
        "sample_matches": [
            {
                "id": str(m.id),
                "title": m.title,
                "agency": m.agency_name,
                "score": m.likelihood_score,
                "deadline": m.response_deadline.isoformat() if m.response_deadline else None,
            }
            for m in matches
        ],
    }
