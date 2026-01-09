"""
Saved Searches API endpoints.

Handles CRUD operations for user saved searches (filter combinations).
"""

from datetime import datetime
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user, rate_limit
from app.models import User, SavedSearch
from app.schemas.saved_search import (
    SavedSearchCreate,
    SavedSearchUpdate,
    SavedSearchResponse,
)
from app.config import SUBSCRIPTION_TIERS

router = APIRouter()

# Tier limits for saved searches
SAVED_SEARCH_LIMITS = {
    "free": 3,
    "starter": 10,
    "pro": 50,  # Effectively unlimited
}


@router.get("", response_model=List[SavedSearchResponse])
async def list_saved_searches(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List all saved searches for current user.
    """
    searches = db.query(SavedSearch).filter(
        SavedSearch.user_id == current_user.id
    ).order_by(SavedSearch.is_default.desc(), SavedSearch.last_used_at.desc().nullslast()).all()

    return searches


@router.post("", response_model=SavedSearchResponse, status_code=status.HTTP_201_CREATED)
async def create_saved_search(
    search_data: SavedSearchCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit),
):
    """
    Create a new saved search.

    Subject to subscription tier limits on number of saved searches.
    """
    # Check saved search limit
    max_searches = SAVED_SEARCH_LIMITS.get(
        current_user.subscription_tier,
        SAVED_SEARCH_LIMITS["free"]
    )

    current_count = db.query(SavedSearch).filter(
        SavedSearch.user_id == current_user.id
    ).count()

    if current_count >= max_searches:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Saved search limit reached ({max_searches}). Upgrade to save more searches.",
        )

    # If this is set as default, unset any existing default
    if search_data.is_default:
        db.query(SavedSearch).filter(
            SavedSearch.user_id == current_user.id,
            SavedSearch.is_default == True,
        ).update({SavedSearch.is_default: False})

    search = SavedSearch(
        user_id=current_user.id,
        **search_data.model_dump(),
    )

    db.add(search)
    db.commit()
    db.refresh(search)

    return search


@router.get("/{search_id}", response_model=SavedSearchResponse)
async def get_saved_search(
    search_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get a specific saved search.
    """
    search = db.query(SavedSearch).filter(
        SavedSearch.id == search_id,
        SavedSearch.user_id == current_user.id,
    ).first()

    if not search:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved search not found",
        )

    return search


@router.patch("/{search_id}", response_model=SavedSearchResponse)
async def update_saved_search(
    search_id: UUID,
    search_data: SavedSearchUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit),
):
    """
    Update a saved search.
    """
    search = db.query(SavedSearch).filter(
        SavedSearch.id == search_id,
        SavedSearch.user_id == current_user.id,
    ).first()

    if not search:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved search not found",
        )

    # If setting as default, unset any existing default
    if search_data.is_default:
        db.query(SavedSearch).filter(
            SavedSearch.user_id == current_user.id,
            SavedSearch.id != search_id,
            SavedSearch.is_default == True,
        ).update({SavedSearch.is_default: False})

    update_data = search_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(search, field, value)

    db.commit()
    db.refresh(search)

    return search


@router.delete("/{search_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saved_search(
    search_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete a saved search.
    """
    search = db.query(SavedSearch).filter(
        SavedSearch.id == search_id,
        SavedSearch.user_id == current_user.id,
    ).first()

    if not search:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved search not found",
        )

    db.delete(search)
    db.commit()


@router.post("/{search_id}/use", response_model=SavedSearchResponse)
async def use_saved_search(
    search_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Mark a saved search as used (increments use count and updates last_used_at).

    Returns the search with its filters for the frontend to apply.
    """
    search = db.query(SavedSearch).filter(
        SavedSearch.id == search_id,
        SavedSearch.user_id == current_user.id,
    ).first()

    if not search:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved search not found",
        )

    # Update usage stats
    search.use_count = (search.use_count or 0) + 1
    search.last_used_at = datetime.utcnow()

    db.commit()
    db.refresh(search)

    return search


@router.post("/{search_id}/set-default", response_model=SavedSearchResponse)
async def set_default_search(
    search_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Set a saved search as the default search.

    Only one search can be default at a time.
    """
    search = db.query(SavedSearch).filter(
        SavedSearch.id == search_id,
        SavedSearch.user_id == current_user.id,
    ).first()

    if not search:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved search not found",
        )

    # Unset any existing default
    db.query(SavedSearch).filter(
        SavedSearch.user_id == current_user.id,
        SavedSearch.is_default == True,
    ).update({SavedSearch.is_default: False})

    # Set this one as default
    search.is_default = True

    db.commit()
    db.refresh(search)

    return search


@router.get("/default/filters")
async def get_default_search_filters(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get the filters from the user's default saved search (if any).

    Returns null if no default is set.
    """
    search = db.query(SavedSearch).filter(
        SavedSearch.user_id == current_user.id,
        SavedSearch.is_default == True,
    ).first()

    if not search:
        return None

    return search.to_filters_dict()
