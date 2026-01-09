"""
Stripe Integration Service

Handles subscription billing, checkout, and webhook processing.
"""

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

import stripe
from sqlalchemy.orm import Session

from app.config import settings, SUBSCRIPTION_TIERS
from app.models import User, Subscription

logger = logging.getLogger(__name__)

# Initialize Stripe with latest API version
stripe.api_key = settings.stripe_secret_key
stripe.api_version = "2025-12-15.clover"  # Latest API version (Dec 2025)

# Price IDs for each tier (set these in Stripe Dashboard)
STRIPE_PRICE_IDS = {
    "starter_monthly": settings.stripe_price_starter_monthly or "",
    "starter_yearly": settings.stripe_price_starter_yearly or "",
    "pro_monthly": settings.stripe_price_pro_monthly or "",
    "pro_yearly": settings.stripe_price_pro_yearly or "",
}


class StripeService:
    """Service for Stripe operations."""

    @staticmethod
    def create_customer(user: User) -> str:
        """
        Create a Stripe customer for a user.

        Args:
            user: User model instance

        Returns:
            Stripe customer ID
        """
        try:
            customer = stripe.Customer.create(
                email=user.email,
                name=user.company_name,
                metadata={
                    "user_id": str(user.id),
                },
            )
            return customer.id
        except stripe.StripeError as e:
            logger.error(f"Error creating Stripe customer: {e}")
            raise

    @staticmethod
    def create_checkout_session(
        user: User,
        tier: str,
        billing_period: str,
        success_url: str,
        cancel_url: str,
    ) -> dict:
        """
        Create a Stripe Checkout session for subscription.

        Args:
            user: User model instance
            tier: Subscription tier (starter, pro)
            billing_period: monthly or yearly
            success_url: URL to redirect on success
            cancel_url: URL to redirect on cancel

        Returns:
            Checkout session data with URL
        """
        price_key = f"{tier}_{billing_period}"
        price_id = STRIPE_PRICE_IDS.get(price_key)

        if not price_id:
            raise ValueError(f"Invalid tier/billing combination: {price_key}")

        try:
            # Ensure customer exists
            customer_id = user.stripe_customer_id
            if not customer_id:
                customer_id = StripeService.create_customer(user)

            session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=["card"],
                line_items=[
                    {
                        "price": price_id,
                        "quantity": 1,
                    }
                ],
                mode="subscription",
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    "user_id": str(user.id),
                    "tier": tier,
                },
                subscription_data={
                    "metadata": {
                        "user_id": str(user.id),
                        "tier": tier,
                    },
                },
            )

            return {
                "checkout_url": session.url,
                "session_id": session.id,
            }

        except stripe.StripeError as e:
            logger.error(f"Error creating checkout session: {e}")
            raise

    @staticmethod
    def create_billing_portal_session(
        user: User,
        return_url: str,
    ) -> dict:
        """
        Create a Stripe Billing Portal session.

        Args:
            user: User model instance
            return_url: URL to return to after portal

        Returns:
            Portal session data with URL
        """
        if not user.stripe_customer_id:
            raise ValueError("User has no Stripe customer ID")

        try:
            session = stripe.billing_portal.Session.create(
                customer=user.stripe_customer_id,
                return_url=return_url,
            )

            return {
                "portal_url": session.url,
            }

        except stripe.StripeError as e:
            logger.error(f"Error creating billing portal: {e}")
            raise

    @staticmethod
    def cancel_subscription(subscription_id: str, at_period_end: bool = True) -> dict:
        """
        Cancel a subscription.

        Args:
            subscription_id: Stripe subscription ID
            at_period_end: If True, cancel at end of period

        Returns:
            Updated subscription data
        """
        try:
            if at_period_end:
                subscription = stripe.Subscription.modify(
                    subscription_id,
                    cancel_at_period_end=True,
                )
            else:
                subscription = stripe.Subscription.delete(subscription_id)

            return {
                "id": subscription.id,
                "status": subscription.status,
                "cancel_at_period_end": subscription.cancel_at_period_end,
            }

        except stripe.StripeError as e:
            logger.error(f"Error canceling subscription: {e}")
            raise

    @staticmethod
    def get_subscription(subscription_id: str) -> Optional[dict]:
        """
        Get subscription details from Stripe.

        Args:
            subscription_id: Stripe subscription ID

        Returns:
            Subscription data or None
        """
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
            return {
                "id": subscription.id,
                "status": subscription.status,
                "current_period_start": datetime.fromtimestamp(subscription.current_period_start),
                "current_period_end": datetime.fromtimestamp(subscription.current_period_end),
                "cancel_at_period_end": subscription.cancel_at_period_end,
            }

        except stripe.StripeError as e:
            logger.error(f"Error getting subscription: {e}")
            return None

    @staticmethod
    def get_invoices(customer_id: str, limit: int = 10) -> list[dict]:
        """
        Get invoices for a customer.

        Args:
            customer_id: Stripe customer ID
            limit: Maximum invoices to return

        Returns:
            List of invoice data
        """
        try:
            invoices = stripe.Invoice.list(
                customer=customer_id,
                limit=limit,
            )

            return [
                {
                    "id": inv.id,
                    "amount_due": inv.amount_due,
                    "amount_paid": inv.amount_paid,
                    "status": inv.status,
                    "created": datetime.fromtimestamp(inv.created),
                    "period_start": datetime.fromtimestamp(inv.period_start) if inv.period_start else None,
                    "period_end": datetime.fromtimestamp(inv.period_end) if inv.period_end else None,
                    "invoice_pdf": inv.invoice_pdf,
                    "hosted_invoice_url": inv.hosted_invoice_url,
                }
                for inv in invoices.data
            ]

        except stripe.StripeError as e:
            logger.error(f"Error getting invoices: {e}")
            return []

    @staticmethod
    def get_payment_methods(customer_id: str) -> list[dict]:
        """
        Get payment methods for a customer.

        Args:
            customer_id: Stripe customer ID

        Returns:
            List of payment method data
        """
        try:
            payment_methods = stripe.PaymentMethod.list(
                customer=customer_id,
                type="card",
            )

            # Get default payment method
            customer = stripe.Customer.retrieve(customer_id)
            default_pm_id = customer.invoice_settings.default_payment_method

            return [
                {
                    "id": pm.id,
                    "type": pm.type,
                    "card_brand": pm.card.brand if pm.card else None,
                    "card_last4": pm.card.last4 if pm.card else None,
                    "card_exp_month": pm.card.exp_month if pm.card else None,
                    "card_exp_year": pm.card.exp_year if pm.card else None,
                    "is_default": pm.id == default_pm_id,
                }
                for pm in payment_methods.data
            ]

        except stripe.StripeError as e:
            logger.error(f"Error getting payment methods: {e}")
            return []

    @staticmethod
    def handle_webhook_event(payload: bytes, sig_header: str) -> dict:
        """
        Handle Stripe webhook event.

        Args:
            payload: Raw webhook payload
            sig_header: Stripe signature header

        Returns:
            Processing result
        """
        try:
            event = stripe.Webhook.construct_event(
                payload,
                sig_header,
                settings.stripe_webhook_secret,
            )
        except ValueError as e:
            logger.error(f"Invalid webhook payload: {e}")
            raise
        except stripe.SignatureVerificationError as e:
            logger.error(f"Invalid webhook signature: {e}")
            raise

        event_type = event["type"]
        data = event["data"]["object"]

        logger.info(f"Processing webhook: {event_type}")

        # Handle different event types
        handlers = {
            "checkout.session.completed": StripeService._handle_checkout_completed,
            "customer.subscription.updated": StripeService._handle_subscription_updated,
            "customer.subscription.deleted": StripeService._handle_subscription_deleted,
            "invoice.paid": StripeService._handle_invoice_paid,
            "invoice.payment_failed": StripeService._handle_payment_failed,
        }

        handler = handlers.get(event_type)
        if handler:
            return handler(data)

        return {"status": "ignored", "event_type": event_type}

    @staticmethod
    def _handle_checkout_completed(data: dict) -> dict:
        """Handle successful checkout."""
        from app.database import SessionLocal

        user_id = data.get("metadata", {}).get("user_id")
        tier = data.get("metadata", {}).get("tier")
        subscription_id = data.get("subscription")
        customer_id = data.get("customer")

        if not all([user_id, tier, subscription_id]):
            return {"status": "error", "message": "Missing metadata"}

        with SessionLocal() as db:
            user = db.query(User).filter(User.id == UUID(user_id)).first()
            if not user:
                return {"status": "error", "message": "User not found"}

            # Update user
            user.stripe_customer_id = customer_id
            user.subscription_tier = tier

            # Create or update subscription record
            subscription = db.query(Subscription).filter(
                Subscription.user_id == user.id
            ).first()

            if subscription:
                subscription.stripe_subscription_id = subscription_id
                subscription.tier = tier
                subscription.status = "active"
            else:
                subscription = Subscription(
                    user_id=user.id,
                    stripe_subscription_id=subscription_id,
                    stripe_customer_id=customer_id,
                    tier=tier,
                    status="active",
                )
                db.add(subscription)

            db.commit()

        return {"status": "success", "user_id": user_id, "tier": tier}

    @staticmethod
    def _handle_subscription_updated(data: dict) -> dict:
        """Handle subscription update."""
        from app.database import SessionLocal

        subscription_id = data.get("id")
        status = data.get("status")

        with SessionLocal() as db:
            subscription = db.query(Subscription).filter(
                Subscription.stripe_subscription_id == subscription_id
            ).first()

            if subscription:
                subscription.status = status
                subscription.cancel_at_period_end = data.get("cancel_at_period_end", False)

                if data.get("current_period_start"):
                    subscription.current_period_start = datetime.fromtimestamp(
                        data["current_period_start"]
                    )
                if data.get("current_period_end"):
                    subscription.current_period_end = datetime.fromtimestamp(
                        data["current_period_end"]
                    )

                db.commit()

        return {"status": "success", "subscription_id": subscription_id}

    @staticmethod
    def _handle_subscription_deleted(data: dict) -> dict:
        """Handle subscription cancellation."""
        from app.database import SessionLocal

        subscription_id = data.get("id")

        with SessionLocal() as db:
            subscription = db.query(Subscription).filter(
                Subscription.stripe_subscription_id == subscription_id
            ).first()

            if subscription:
                subscription.status = "canceled"

                # Downgrade user to free tier
                user = db.query(User).filter(User.id == subscription.user_id).first()
                if user:
                    user.subscription_tier = "free"

                db.commit()

        return {"status": "success", "subscription_id": subscription_id}

    @staticmethod
    def _handle_invoice_paid(data: dict) -> dict:
        """Handle successful invoice payment."""
        logger.info(f"Invoice paid: {data.get('id')}")
        return {"status": "success", "invoice_id": data.get("id")}

    @staticmethod
    def _handle_payment_failed(data: dict) -> dict:
        """Handle failed payment."""
        from app.database import SessionLocal
        from worker.tasks.email_sending import send_payment_failed_email

        customer_id = data.get("customer")

        with SessionLocal() as db:
            user = db.query(User).filter(
                User.stripe_customer_id == customer_id
            ).first()

            if user:
                # Could send email notification here
                logger.warning(f"Payment failed for user {user.id}")

        return {"status": "processed", "invoice_id": data.get("id")}
