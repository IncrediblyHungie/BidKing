"""
Usage Tracking Model

Tracks monthly usage limits for users based on subscription tier.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class UsageTracking(Base):
    """Monthly usage tracking for subscription limits."""

    __tablename__ = "usage_tracking"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign key to user
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    # Tracking period
    period_start = Column(DateTime, nullable=False, index=True)
    period_end = Column(DateTime, nullable=False)

    # Usage counts
    alerts_sent = Column(Integer, default=0)
    api_calls = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", backref="usage_tracking")

    def __repr__(self):
        return f"<UsageTracking user={self.user_id} period={self.period_start}>"
