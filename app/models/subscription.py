"""
Subscription Model

Stripe subscription tracking.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer
from sqlalchemy.orm import relationship

from app.database import Base
from app.utils.uuid_type import GUID


class Subscription(Base):
    """Stripe subscription model."""

    __tablename__ = "subscriptions"

    # Primary key
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)

    # User relationship
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Stripe IDs
    stripe_subscription_id = Column(String(255), unique=True, nullable=True, index=True)
    stripe_price_id = Column(String(255), nullable=True)

    # Subscription details
    tier = Column(String(50), nullable=False, default="free")
    status = Column(String(50), nullable=False, default="active")
    # Status: active, canceled, past_due, trialing, incomplete, incomplete_expired, unpaid

    # Billing period
    current_period_start = Column(DateTime, nullable=True)
    current_period_end = Column(DateTime, nullable=True)
    billing_cycle = Column(String(20), default="monthly")  # monthly, yearly

    # Cancellation
    cancel_at_period_end = Column(String(5), default="false")
    canceled_at = Column(DateTime, nullable=True)

    # Trial
    trial_start = Column(DateTime, nullable=True)
    trial_end = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="subscriptions")

    def __repr__(self):
        return f"<Subscription {self.tier} - {self.status}>"

    @property
    def is_active(self) -> bool:
        """Check if subscription is active."""
        return self.status in ("active", "trialing")

    @property
    def is_paid(self) -> bool:
        """Check if this is a paid subscription."""
        return self.tier in ("starter", "pro")


class UsageTracking(Base):
    """Monthly usage tracking for tier limits."""

    __tablename__ = "usage_tracking"

    # Primary key
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)

    # User relationship
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Period tracking
    period_start = Column(DateTime, nullable=False)  # First of month
    period_end = Column(DateTime, nullable=True)  # Last of month

    # Usage counters
    alerts_sent = Column(Integer, default=0)
    searches_performed = Column(Integer, default=0)
    exports_performed = Column(Integer, default=0)
    api_calls = Column(Integer, default=0)
    opportunities_viewed = Column(Integer, default=0)

    # AI generation tracking
    ai_generations = Column(Integer, default=0)
    ai_tokens_used = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    class Meta:
        unique_together = ("user_id", "period_start")

    def __repr__(self):
        return f"<UsageTracking {self.user_id} - {self.period_start}>"
