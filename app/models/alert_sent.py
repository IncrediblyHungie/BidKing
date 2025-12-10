"""
Alert Sent Model

Tracking of alerts sent to users.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class AlertSent(Base):
    """Record of alerts sent to users."""

    __tablename__ = "alerts_sent"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Relationships
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    alert_profile_id = Column(UUID(as_uuid=True), ForeignKey("alert_profiles.id", ondelete="CASCADE"), nullable=True, index=True)
    opportunity_id = Column(UUID(as_uuid=True), ForeignKey("opportunities.id", ondelete="SET NULL"), nullable=True, index=True)

    # Delivery details
    delivery_method = Column(String(20), nullable=False)  # email, sms, in_app
    delivery_status = Column(String(20), default="pending")  # pending, sent, delivered, bounced, failed

    # Email-specific
    email_message_id = Column(String(255), nullable=True)

    # Alert type
    alert_type = Column(String(50), nullable=False)  # instant, daily_digest, weekly_digest

    # Engagement tracking
    sent_at = Column(DateTime, nullable=True)
    opened_at = Column(DateTime, nullable=True)
    clicked_at = Column(DateTime, nullable=True)

    # Error tracking
    error_message = Column(String(500), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="alerts_sent")
    alert_profile = relationship("AlertProfile", back_populates="alerts_sent")
    opportunity = relationship("Opportunity", back_populates="alerts_sent")

    def __repr__(self):
        return f"<AlertSent {self.delivery_method} - {self.delivery_status}>"
