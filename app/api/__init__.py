"""API routes package."""

from fastapi import APIRouter

from app.api import auth, users, alerts, opportunities, subscriptions, market, webhooks, profile, analytics, celery_tasks, templates, competitors, saved_searches

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
api_router.include_router(opportunities.router, prefix="/opportunities", tags=["opportunities"])
api_router.include_router(subscriptions.router, prefix="/subscriptions", tags=["subscriptions"])
api_router.include_router(market.router, prefix="/market", tags=["market"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(profile.router, prefix="/company", tags=["company"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(celery_tasks.router, prefix="/celery", tags=["celery"])
api_router.include_router(templates.router, prefix="/proposals", tags=["proposals"])
api_router.include_router(competitors.router, tags=["competitor-analytics"])
api_router.include_router(saved_searches.router, prefix="/saved-searches", tags=["saved-searches"])
