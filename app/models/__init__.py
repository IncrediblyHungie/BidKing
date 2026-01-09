"""
BidKing Database Models

All SQLAlchemy models are imported here for easy access.
"""

from app.models.user import User
from app.models.subscription import Subscription, UsageTracking
from app.models.alert_profile import AlertProfile
from app.models.opportunity import Opportunity, PointOfContact, SavedOpportunity, OpportunityAttachment, OpportunityHistory
from app.models.alert_sent import AlertSent
from app.models.market_data import (
    ContractAward,
    NAICSStatistics,
    Recipient,
    RecompeteOpportunity,
    LaborRateCache,
    CommonJobTitle,
)
from app.models.company import (
    CompanyProfile,
    CompanyNAICS,
    CompanyCertification,
    PastPerformance,
    CapabilityStatement,
    OpportunityMetadata,
    OpportunityScore,
    OpportunityDecision,
)
from app.models.proposal_template import (
    ProposalTemplate,
    GeneratedSection,
)

__all__ = [
    "User",
    "Subscription",
    "AlertProfile",
    "Opportunity",
    "PointOfContact",
    "SavedOpportunity",
    "OpportunityAttachment",
    "OpportunityHistory",
    "AlertSent",
    "ContractAward",
    "NAICSStatistics",
    "Recipient",
    "RecompeteOpportunity",
    "LaborRateCache",
    "CommonJobTitle",
    "UsageTracking",
    # Company & Scoring models
    "CompanyProfile",
    "CompanyNAICS",
    "CompanyCertification",
    "PastPerformance",
    "CapabilityStatement",
    "OpportunityMetadata",
    "OpportunityScore",
    "OpportunityDecision",
    # Proposal Templates
    "ProposalTemplate",
    "GeneratedSection",
]
