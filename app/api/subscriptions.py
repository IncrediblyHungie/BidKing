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


@router.get("/tiers", response_model=List[SubscriptionTierInfo])
async def list_subscription_tiers():
    """
    List available subscription tiers.

    Returns tier information including pricing and limits.
    Public endpoint - no authentication required.
    """
    tiers = []
    for tier_name, config in SUBSCRIPTION_TIERS.items():
        tiers.append(SubscriptionTierInfo(
            tier=tier_name,
            price_monthly=config["price_monthly"],
            price_yearly=config.get("price_yearly", config["price_monthly"] * 10),
            limits=config["limits"],
            features=config.get("features", []),
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
    Get current user's usage statistics.
    """
    from datetime import datetime

    # Get current month's usage
    month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    usage = db.query(UsageTracking).filter(
        UsageTracking.user_id == current_user.id,
        UsageTracking.period_start >= month_start,
    ).first()

    # Get tier limits
    tier_config = SUBSCRIPTION_TIERS.get(
        current_user.subscription_tier,
        SUBSCRIPTION_TIERS["free"]
    )
    limits = tier_config["limits"]

    if not usage:
        return UsageResponse(
            user_id=current_user.id,
            period_start=month_start,
            period_end=month_start.replace(month=month_start.month + 1 if month_start.month < 12 else 1),
            alerts_sent=0,
            api_calls=0,
            opportunities_viewed=0,
            exports_count=0,
            alerts_limit=limits["alerts_per_month"],
            api_calls_limit=limits["api_calls_per_hour"] * 24 * 30,  # Rough monthly estimate
            exports_limit=limits.get("exports_per_month", 0),
            alerts_usage_percent=0,
            api_usage_percent=0,
        )

    alerts_limit = limits["alerts_per_month"]
    api_limit = limits["api_calls_per_hour"] * 24 * 30

    return UsageResponse(
        user_id=current_user.id,
        period_start=usage.period_start,
        period_end=usage.period_end,
        alerts_sent=usage.alerts_sent,
        api_calls=usage.api_calls,
        opportunities_viewed=usage.opportunities_viewed,
        exports_count=usage.exports_count,
        alerts_limit=alerts_limit,
        api_calls_limit=api_limit,
        exports_limit=limits.get("exports_per_month", 0),
        alerts_usage_percent=(usage.alerts_sent / alerts_limit * 100) if alerts_limit else 0,
        api_usage_percent=(usage.api_calls / api_limit * 100) if api_limit else 0,
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
