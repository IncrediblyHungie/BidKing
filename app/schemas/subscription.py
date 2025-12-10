"""Subscription and billing Pydantic schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SubscriptionCreate(BaseModel):
    """Schema for creating a subscription."""

    tier: str = Field(..., pattern="^(free|starter|pro)$")
    payment_method_id: Optional[str] = None  # Stripe payment method ID


class SubscriptionResponse(BaseModel):
    """Schema for subscription response."""

    id: UUID
    user_id: UUID
    tier: str
    status: str
    stripe_subscription_id: Optional[str]
    stripe_customer_id: Optional[str]
    current_period_start: Optional[datetime]
    current_period_end: Optional[datetime]
    cancel_at_period_end: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SubscriptionTierInfo(BaseModel):
    """Schema for subscription tier information."""

    tier: str
    price_monthly: int
    price_yearly: int
    limits: dict
    features: list[str]


class UsageResponse(BaseModel):
    """Schema for usage tracking response."""

    user_id: UUID
    period_start: datetime
    period_end: datetime

    # Current usage
    alerts_sent: int
    api_calls: int
    opportunities_viewed: int
    exports_count: int

    # Limits based on tier
    alerts_limit: int
    api_calls_limit: int
    exports_limit: int

    # Percentages
    alerts_usage_percent: float
    api_usage_percent: float

    class Config:
        from_attributes = True


class InvoiceResponse(BaseModel):
    """Schema for invoice response."""

    id: str  # Stripe invoice ID
    amount_due: int  # in cents
    amount_paid: int
    status: str
    created: datetime
    period_start: datetime
    period_end: datetime
    invoice_pdf: Optional[str]
    hosted_invoice_url: Optional[str]


class PaymentMethodResponse(BaseModel):
    """Schema for payment method response."""

    id: str  # Stripe payment method ID
    type: str  # e.g., "card"
    card_brand: Optional[str]
    card_last4: Optional[str]
    card_exp_month: Optional[int]
    card_exp_year: Optional[int]
    is_default: bool


class CheckoutSessionCreate(BaseModel):
    """Schema for creating Stripe checkout session."""

    tier: str = Field(..., pattern="^(starter|pro)$")
    billing_period: str = Field(default="monthly", pattern="^(monthly|yearly)$")
    success_url: str
    cancel_url: str


class CheckoutSessionResponse(BaseModel):
    """Schema for checkout session response."""

    checkout_url: str
    session_id: str


class BillingPortalResponse(BaseModel):
    """Schema for billing portal response."""

    portal_url: str
