"""
Email sending tasks.

Handles all outbound email communications.
"""

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from celery import shared_task
import resend

from app.database import SessionLocal
from app.models import User, AlertProfile, Opportunity, AlertSent, SavedOpportunity, UsageTracking
from app.config import settings, SUBSCRIPTION_TIERS

logger = logging.getLogger(__name__)

# Initialize Resend
resend.api_key = settings.resend_api_key


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_alert_email(
    self,
    user_id: str,
    profile_id: str,
    opportunity_ids: list[str],
    alert_type: str = "realtime",
):
    """
    Send alert email to user.

    Args:
        user_id: User UUID
        profile_id: Alert profile UUID
        opportunity_ids: List of opportunity UUIDs
        alert_type: Type of alert (realtime, daily_digest, weekly_digest)
    """
    logger.info(f"Sending {alert_type} alert to user {user_id}")

    with SessionLocal() as db:
        user = db.query(User).filter(User.id == UUID(user_id)).first()
        profile = db.query(AlertProfile).filter(AlertProfile.id == UUID(profile_id)).first()
        opportunities = db.query(Opportunity).filter(
            Opportunity.id.in_([UUID(oid) for oid in opportunity_ids])
        ).all()

        if not user or not profile or not opportunities:
            logger.error(f"Missing data for alert: user={user}, profile={profile}, opps={len(opportunities)}")
            return {"error": "Missing data"}

        # Check if user has reached their monthly alert limit
        tier_config = SUBSCRIPTION_TIERS.get(user.subscription_tier, SUBSCRIPTION_TIERS["free"])
        alerts_limit = tier_config["limits"]["alerts_per_month"]

        # Get current month's usage
        from calendar import monthrange
        now = datetime.utcnow()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        usage = db.query(UsageTracking).filter(
            UsageTracking.user_id == user.id,
            UsageTracking.period_start == month_start,
        ).first()

        current_alerts = usage.alerts_sent if usage else 0

        if current_alerts >= alerts_limit:
            logger.warning(f"User {user_id} has reached alert limit ({current_alerts}/{alerts_limit})")
            return {"error": "Alert limit reached", "current": current_alerts, "limit": alerts_limit}

        # Build email content
        subject = _build_subject(profile.name, alert_type, len(opportunities))
        html_content = _build_html_content(user, profile, opportunities, alert_type)

        try:
            # Send via Resend
            params = {
                "from": f"BidKing Alerts <alerts@{settings.email_domain}>",
                "to": [user.email],
                "subject": subject,
                "html": html_content,
            }

            response = resend.Emails.send(params)
            logger.info(f"Email sent successfully: {response}")

            # Record sent alerts
            for opp in opportunities:
                alert_sent = AlertSent(
                    user_id=user.id,
                    alert_profile_id=profile.id,
                    opportunity_id=opp.id,
                    sent_via="email",
                    email_message_id=response.get("id"),
                )
                db.add(alert_sent)

            # Update usage tracking
            if not usage:
                import uuid as uuid_module
                _, last_day = monthrange(now.year, now.month)
                month_end = month_start.replace(day=last_day, hour=23, minute=59, second=59)
                usage = UsageTracking(
                    id=uuid_module.uuid4(),
                    user_id=user.id,
                    period_start=month_start,
                    period_end=month_end,
                    alerts_sent=0,
                )
                db.add(usage)

            usage.alerts_sent = (usage.alerts_sent or 0) + len(opportunities)

            db.commit()

            return {
                "status": "sent",
                "message_id": response.get("id"),
                "opportunities": len(opportunities),
            }

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_welcome_email(self, user_id: str):
    """
    Send welcome email to new user.

    Args:
        user_id: User UUID
    """
    logger.info(f"Sending welcome email to user {user_id}")

    with SessionLocal() as db:
        user = db.query(User).filter(User.id == UUID(user_id)).first()

        if not user:
            logger.error(f"User not found: {user_id}")
            return {"error": "User not found"}

        try:
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background: #1a56db; color: white; padding: 20px; text-align: center; }}
                    .content {{ padding: 20px; }}
                    .button {{ display: inline-block; background: #1a56db; color: white; padding: 12px 24px;
                               text-decoration: none; border-radius: 4px; margin: 10px 0; }}
                    .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>Welcome to BidKing!</h1>
                    </div>
                    <div class="content">
                        <p>Hi{' ' + user.company_name if user.company_name else ''},</p>
                        <p>Thank you for signing up for BidKing! You're now ready to discover federal
                           contracting opportunities tailored to your business.</p>

                        <h3>Getting Started:</h3>
                        <ol>
                            <li><strong>Create Alert Profiles</strong> - Set up filters for NAICS codes,
                                keywords, and locations</li>
                            <li><strong>Get Matched</strong> - We'll automatically find opportunities
                                that match your criteria</li>
                            <li><strong>Stay Informed</strong> - Receive alerts via email based on your
                                preferred frequency</li>
                        </ol>

                        <p>
                            <a href="{settings.frontend_url}/dashboard" class="button">
                                Go to Dashboard
                            </a>
                        </p>

                        <h3>Your Current Plan: {user.subscription_tier.title()}</h3>
                        <p>Want more features? <a href="{settings.frontend_url}/pricing">Upgrade your plan</a>
                           to unlock unlimited alerts and market intelligence.</p>
                    </div>
                    <div class="footer">
                        <p>BidKing - Find Your Next Federal Contract</p>
                        <p><a href="{settings.frontend_url}/unsubscribe">Unsubscribe</a></p>
                    </div>
                </div>
            </body>
            </html>
            """

            params = {
                "from": f"BidKing <welcome@{settings.email_domain}>",
                "to": [user.email],
                "subject": "Welcome to BidKing - Your Federal Contract Finder",
                "html": html_content,
            }

            response = resend.Emails.send(params)
            logger.info(f"Welcome email sent: {response}")

            return {"status": "sent", "message_id": response.get("id")}

        except Exception as e:
            logger.error(f"Failed to send welcome email: {e}")
            raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_password_reset_email(self, user_id: str, reset_token: str):
    """Send password reset email."""
    with SessionLocal() as db:
        user = db.query(User).filter(User.id == UUID(user_id)).first()

        if not user:
            return {"error": "User not found"}

        reset_url = f"{settings.frontend_url}/reset-password?token={reset_token}"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .button {{ display: inline-block; background: #1a56db; color: white; padding: 12px 24px;
                           text-decoration: none; border-radius: 4px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>Reset Your Password</h2>
                <p>We received a request to reset your password. Click the button below to create a new password:</p>
                <p><a href="{reset_url}" class="button">Reset Password</a></p>
                <p>This link will expire in 1 hour.</p>
                <p>If you didn't request this, you can safely ignore this email.</p>
            </div>
        </body>
        </html>
        """

        try:
            params = {
                "from": f"BidKing <security@{settings.email_domain}>",
                "to": [user.email],
                "subject": "Reset Your BidKing Password",
                "html": html_content,
            }

            response = resend.Emails.send(params)
            return {"status": "sent", "message_id": response.get("id")}

        except Exception as e:
            logger.error(f"Failed to send password reset email: {e}")
            raise self.retry(exc=e)


def _build_subject(profile_name: str, alert_type: str, count: int) -> str:
    """Build email subject line."""
    if alert_type == "realtime":
        return f"[BidKing] {count} new opportunities matching '{profile_name}'"
    elif alert_type == "daily_digest":
        return f"[BidKing] Daily Digest: {count} opportunities for '{profile_name}'"
    elif alert_type == "weekly_digest":
        return f"[BidKing] Weekly Digest: {count} opportunities for '{profile_name}'"
    return f"[BidKing] {count} opportunities found"


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_reminder_email(self, user_id: str, saved_opportunity_id: str, reminder_type: str = "custom"):
    """
    Send reminder email for a saved/pipeline opportunity.

    Args:
        user_id: User UUID
        saved_opportunity_id: SavedOpportunity UUID
        reminder_type: "custom" (user-set date) or "deadline" (response deadline warning)
    """
    logger.info(f"Sending {reminder_type} reminder to user {user_id}")

    with SessionLocal() as db:
        user = db.query(User).filter(User.id == UUID(user_id)).first()
        saved_opp = db.query(SavedOpportunity).filter(
            SavedOpportunity.id == UUID(saved_opportunity_id)
        ).first()

        if not user or not saved_opp:
            logger.error(f"Missing data for reminder: user={user}, saved_opp={saved_opp}")
            return {"error": "Missing data"}

        opportunity = saved_opp.opportunity
        if not opportunity:
            logger.error(f"Opportunity not found for saved_opp {saved_opportunity_id}")
            return {"error": "Opportunity not found"}

        # Build email content
        if reminder_type == "deadline":
            subject = f"[BidKing] Deadline in {_days_until(opportunity.response_deadline)} days: {opportunity.title[:50]}"
            email_heading = "Deadline Reminder"
            urgency_text = f"The response deadline for this opportunity is in <strong>{_days_until(opportunity.response_deadline)} days</strong>."
        else:
            subject = f"[BidKing] Reminder: {opportunity.title[:50]}"
            email_heading = "Opportunity Reminder"
            urgency_text = "You set a reminder for this opportunity."

        deadline_str = opportunity.response_deadline.strftime("%B %d, %Y at %I:%M %p") if opportunity.response_deadline else "Not specified"
        status_color = _get_status_color(saved_opp.status)

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; background: #f9fafb; }}
                .container {{ max-width: 600px; margin: 0 auto; background: white; }}
                .header {{ background: #1a56db; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; }}
                .opp-card {{ border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; margin: 16px 0; }}
                .button {{ display: inline-block; background: #1a56db; color: white; padding: 12px 24px;
                           text-decoration: none; border-radius: 4px; margin: 10px 5px 10px 0; }}
                .button-secondary {{ background: #6b7280; }}
                .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; background: #f3f4f6; }}
                .status-badge {{ display: inline-block; background: {status_color}; color: white; padding: 4px 12px;
                                 border-radius: 4px; font-size: 12px; text-transform: uppercase; }}
                .meta {{ color: #6b7280; font-size: 14px; margin: 8px 0; }}
                .urgency {{ background: #fef3c7; border-left: 4px solid #f59e0b; padding: 12px; margin: 16px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1 style="margin: 0;">{email_heading}</h1>
                </div>
                <div class="content">
                    <div class="urgency">
                        {urgency_text}
                    </div>

                    <div class="opp-card">
                        <span class="status-badge">{saved_opp.status}</span>
                        <h2 style="margin: 12px 0 8px 0; color: #1a56db;">
                            {opportunity.title}
                        </h2>
                        <p class="meta">
                            <strong>Agency:</strong> {opportunity.agency_name or 'N/A'}<br>
                            <strong>NAICS:</strong> {opportunity.naics_code or 'N/A'}<br>
                            <strong>Deadline:</strong> {deadline_str}<br>
                            <strong>Notice ID:</strong> {opportunity.notice_id}
                        </p>
                        {f'<p><strong>Your Notes:</strong> {saved_opp.notes}</p>' if saved_opp.notes else ''}
                    </div>

                    <p>
                        <a href="{settings.frontend_url}/pipeline" class="button">
                            View in Pipeline
                        </a>
                        <a href="{opportunity.ui_link}" class="button button-secondary">
                            View on SAM.gov
                        </a>
                    </p>
                </div>
                <div class="footer">
                    <p>
                        <a href="{settings.frontend_url}/settings">Manage Notification Settings</a> |
                        <a href="{settings.frontend_url}/unsubscribe">Unsubscribe</a>
                    </p>
                    <p>BidKing - Find Your Next Federal Contract</p>
                </div>
            </div>
        </body>
        </html>
        """

        try:
            params = {
                "from": f"BidKing Reminders <reminders@{settings.email_domain}>",
                "to": [user.email],
                "subject": subject,
                "html": html_content,
            }

            response = resend.Emails.send(params)
            logger.info(f"Reminder email sent: {response}")

            # Mark reminder as sent
            if reminder_type == "deadline":
                saved_opp.deadline_reminder_sent = True
            else:
                saved_opp.reminder_sent = True
            db.commit()

            return {"status": "sent", "message_id": response.get("id")}

        except Exception as e:
            logger.error(f"Failed to send reminder email: {e}")
            raise self.retry(exc=e)


def _days_until(deadline) -> int:
    """Calculate days until deadline."""
    if not deadline:
        return 0
    from datetime import date
    if hasattr(deadline, 'date'):
        deadline = deadline.date()
    today = date.today()
    return max(0, (deadline - today).days)


def _get_status_color(status: str) -> str:
    """Get color for pipeline status."""
    colors = {
        "watching": "#3b82f6",  # blue
        "researching": "#8b5cf6",  # purple
        "preparing": "#f59e0b",  # amber
        "submitted": "#10b981",  # green
        "won": "#22c55e",  # green
        "lost": "#ef4444",  # red
        "archived": "#6b7280",  # gray
    }
    return colors.get(status, "#6b7280")


def _build_html_content(
    user: User,
    profile: AlertProfile,
    opportunities: list[Opportunity],
    alert_type: str,
) -> str:
    """Build HTML email content."""

    # Build opportunity list HTML
    opp_html = ""
    for opp in opportunities[:20]:  # Limit to 20 in email
        deadline = opp.response_deadline.strftime("%b %d, %Y") if opp.response_deadline else "Not specified"
        score_color = "#22c55e" if opp.likelihood_score >= 70 else "#f59e0b" if opp.likelihood_score >= 50 else "#ef4444"

        opp_html += f"""
        <div style="border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; margin-bottom: 16px;">
            <div style="display: flex; justify-content: space-between; align-items: start;">
                <h3 style="margin: 0 0 8px 0; color: #1a56db;">
                    <a href="{opp.sam_gov_link}" style="color: #1a56db; text-decoration: none;">
                        {opp.title[:100]}{'...' if len(opp.title) > 100 else ''}
                    </a>
                </h3>
                <span style="background: {score_color}; color: white; padding: 4px 8px; border-radius: 4px; font-size: 12px;">
                    Score: {opp.likelihood_score}
                </span>
            </div>
            <p style="color: #6b7280; margin: 8px 0; font-size: 14px;">
                <strong>{opp.agency_name or 'Agency N/A'}</strong>
                {' | ' + opp.naics_code if opp.naics_code else ''}
                {' | ' + opp.pop_state if opp.pop_state else ''}
            </p>
            <p style="color: #374151; margin: 8px 0; font-size: 14px;">
                {(opp.description or '')[:200]}{'...' if opp.description and len(opp.description) > 200 else ''}
            </p>
            <p style="color: #9ca3af; font-size: 12px; margin: 8px 0 0 0;">
                <strong>Deadline:</strong> {deadline}
                {' | <strong>Set-Aside:</strong> ' + opp.set_aside_description if opp.set_aside_description else ''}
            </p>
        </div>
        """

    more_text = f"<p style='text-align: center;'>...and {len(opportunities) - 20} more opportunities. <a href='{settings.frontend_url}/opportunities'>View all</a></p>" if len(opportunities) > 20 else ""

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; background: #f9fafb; }}
            .container {{ max-width: 700px; margin: 0 auto; background: white; }}
            .header {{ background: #1a56db; color: white; padding: 20px; text-align: center; }}
            .content {{ padding: 20px; }}
            .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; background: #f3f4f6; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1 style="margin: 0;">BidKing Alert</h1>
                <p style="margin: 5px 0 0 0; opacity: 0.9;">{len(opportunities)} opportunities matching "{profile.name}"</p>
            </div>
            <div class="content">
                {opp_html}
                {more_text}
            </div>
            <div class="footer">
                <p>
                    <a href="{settings.frontend_url}/alerts/{profile.id}">Edit Alert</a> |
                    <a href="{settings.frontend_url}/alerts">Manage Alerts</a> |
                    <a href="{settings.frontend_url}/unsubscribe">Unsubscribe</a>
                </p>
                <p>BidKing - Find Your Next Federal Contract</p>
            </div>
        </div>
    </body>
    </html>
    """
