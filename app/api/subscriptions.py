"""
Subscription and billing API endpoints.

Handles subscription management, checkout, and billing portal.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models import User, Subscription, UsageTracking
from app.schemas.subscription import (
    SubscriptionResponse,
    SubscriptionTierInfo,
    UsageResponse,
    CheckoutSessionCreate,
    CheckoutSessionResponse,
    BillingPortalResponse,
    InvoiceResponse,
    PaymentMethodResponse,
)
from app.services.stripe_service import StripeService
from app.config import SUBSCRIPTION_TIERS, settings

router = APIRouter()


def get_or_create_usage_record(db: Session, user_id, month_start, month_end=None) -> UsageTracking:
    """
    Get or create a UsageTracking record for the given user and month.

    Used by various parts of the system to track usage.
    """
    from calendar import monthrange
    from datetime import datetime

    if month_end is None:
        _, last_day = monthrange(month_start.year, month_start.month)
        month_end = month_start.replace(day=last_day, hour=23, minute=59, second=59)

    usage = db.query(UsageTracking).filter(
        UsageTracking.user_id == user_id,
        UsageTracking.period_start == month_start,
    ).first()

    if not usage:
        import uuid
        usage = UsageTracking(
            id=uuid.uuid4(),
            user_id=user_id,
            period_start=month_start,
            period_end=month_end,
            alerts_sent=0,
            searches_performed=0,
            exports_performed=0,
            api_calls=0,
            opportunities_viewed=0,
            ai_generations=0,
            ai_tokens_used=0,
        )
        db.add(usage)
        db.commit()
        db.refresh(usage)

    return usage


@router.get("/tiers", response_model=List[SubscriptionTierInfo])
async def list_subscription_tiers():
    """
    List available subscription tiers.

    Returns tier information including pricing and limits.
    Public endpoint - no authentication required.
    """
    tiers = []
    for tier_name, config in SUBSCRIPTION_TIERS.items():
        # Convert features dict to list of enabled feature names
        features_dict = config.get("features", {})
        features_list = [k for k, v in features_dict.items() if v] if isinstance(features_dict, dict) else features_dict

        tiers.append(SubscriptionTierInfo(
            tier=tier_name,
            price_monthly=config["price_monthly"],
            price_yearly=config.get("price_yearly", config["price_monthly"] * 10),
            limits=config["limits"],
            features=features_list,
        ))
    return tiers


@router.get("/current", response_model=SubscriptionResponse)
async def get_current_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get current user's subscription details.
    """
    subscription = db.query(Subscription).filter(
        Subscription.user_id == current_user.id
    ).first()

    if not subscription:
        # Return virtual free subscription
        return SubscriptionResponse(
            id=current_user.id,
            user_id=current_user.id,
            tier="free",
            status="active",
            stripe_subscription_id=None,
            stripe_customer_id=current_user.stripe_customer_id,
            current_period_start=None,
            current_period_end=None,
            cancel_at_period_end=False,
            created_at=current_user.created_at,
            updated_at=current_user.updated_at,
        )

    return subscription


@router.get("/usage", response_model=UsageResponse)
async def get_usage(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get current user's usage statistics for the current billing period.

    Returns usage counters and tier limits for:
    - Alerts sent this month
    - API calls
    - Exports performed
    - AI generations
    """
    from datetime import datetime
    from calendar import monthrange

    # Get current month boundaries
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    _, last_day = monthrange(now.year, now.month)
    month_end = month_start.replace(day=last_day, hour=23, minute=59, second=59)

    # Get or create current month's usage record
    usage = db.query(UsageTracking).filter(
        UsageTracking.user_id == current_user.id,
        UsageTracking.period_start == month_start,
    ).first()

    # Get tier limits
    tier_config = SUBSCRIPTION_TIERS.get(
        current_user.subscription_tier,
        SUBSCRIPTION_TIERS["free"]
    )
    limits = tier_config["limits"]
    alerts_limit = limits["alerts_per_month"]
    api_limit = limits["api_calls_per_hour"] * 24 * 30  # Rough monthly estimate

    if not usage:
        return UsageResponse(
            user_id=current_user.id,
            period_start=month_start,
            period_end=month_end,
            alerts_sent=0,
            api_calls=0,
            opportunities_viewed=0,
            exports_count=0,
            alerts_limit=alerts_limit,
            api_calls_limit=api_limit,
            exports_limit=limits.get("exports_per_month", 0),
            alerts_usage_percent=0,
            api_usage_percent=0,
        )

    return UsageResponse(
        user_id=current_user.id,
        period_start=usage.period_start,
        period_end=usage.period_end or month_end,
        alerts_sent=usage.alerts_sent or 0,
        api_calls=usage.api_calls or 0,
        opportunities_viewed=usage.opportunities_viewed or 0,
        exports_count=usage.exports_performed or 0,
        alerts_limit=alerts_limit,
        api_calls_limit=api_limit,
        exports_limit=limits.get("exports_per_month", 0),
        alerts_usage_percent=(usage.alerts_sent / alerts_limit * 100) if alerts_limit and usage.alerts_sent else 0,
        api_usage_percent=(usage.api_calls / api_limit * 100) if api_limit and usage.api_calls else 0,
    )


@router.post("/checkout", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    data: CheckoutSessionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a Stripe checkout session for upgrading subscription.
    """
    if data.tier not in ["starter", "pro"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid tier. Must be 'starter' or 'pro'",
        )

    try:
        result = StripeService.create_checkout_session(
            user=current_user,
            tier=data.tier,
            billing_period=data.billing_period,
            success_url=data.success_url,
            cancel_url=data.cancel_url,
        )

        # Update customer ID if new
        if not current_user.stripe_customer_id:
            db.commit()

        return CheckoutSessionResponse(**result)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create checkout session: {str(e)}",
        )


@router.post("/portal", response_model=BillingPortalResponse)
async def create_billing_portal(
    return_url: str,
    current_user: User = Depends(get_current_user),
):
    """
    Create a Stripe billing portal session.

    Allows users to manage payment methods and view invoices.
    """
    if not current_user.stripe_customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No billing account found. Please subscribe first.",
        )

    try:
        result = StripeService.create_billing_portal_session(
            user=current_user,
            return_url=return_url,
        )
        return BillingPortalResponse(**result)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create billing portal: {str(e)}",
        )


@router.post("/cancel")
async def cancel_subscription(
    at_period_end: bool = True,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Cancel current subscription.

    By default, cancels at the end of the current billing period.
    """
    subscription = db.query(Subscription).filter(
        Subscription.user_id == current_user.id,
        Subscription.status == "active",
    ).first()

    if not subscription or not subscription.stripe_subscription_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active subscription found",
        )

    try:
        result = StripeService.cancel_subscription(
            subscription.stripe_subscription_id,
            at_period_end=at_period_end,
        )

        subscription.cancel_at_period_end = at_period_end
        if not at_period_end:
            subscription.status = "canceled"
            current_user.subscription_tier = "free"

        db.commit()

        return {
            "message": "Subscription canceled" if not at_period_end else "Subscription will cancel at period end",
            "cancel_at_period_end": at_period_end,
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel subscription: {str(e)}",
        )


@router.get("/invoices", response_model=List[InvoiceResponse])
async def list_invoices(
    limit: int = 10,
    current_user: User = Depends(get_current_user),
):
    """
    List user's invoices.
    """
    if not current_user.stripe_customer_id:
        return []

    invoices = StripeService.get_invoices(
        current_user.stripe_customer_id,
        limit=limit,
    )
    return invoices


@router.get("/payment-methods", response_model=List[PaymentMethodResponse])
async def list_payment_methods(
    current_user: User = Depends(get_current_user),
):
    """
    List user's payment methods.
    """
    if not current_user.stripe_customer_id:
        return []

    methods = StripeService.get_payment_methods(current_user.stripe_customer_id)
    return methods
