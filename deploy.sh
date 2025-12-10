#!/bin/bash
# BidKing Deployment Script
# Deploys to Fly.io with proper configuration

set -e

echo "=========================================="
echo "BidKing Deployment Script"
echo "=========================================="

# Check for flyctl
if ! command -v flyctl &> /dev/null; then
    echo "Error: flyctl not found. Install from https://fly.io/docs/hands-on/install-flyctl/"
    exit 1
fi

# Check if logged in
if ! flyctl auth whoami &> /dev/null; then
    echo "Error: Not logged in to Fly.io. Run 'flyctl auth login'"
    exit 1
fi

# Parse arguments
DEPLOY_ALL=false
DEPLOY_DB=false
DEPLOY_REDIS=false
MIGRATE=false

for arg in "$@"; do
    case $arg in
        --all)
            DEPLOY_ALL=true
            ;;
        --db)
            DEPLOY_DB=true
            ;;
        --redis)
            DEPLOY_REDIS=true
            ;;
        --migrate)
            MIGRATE=true
            ;;
        --help)
            echo "Usage: ./deploy.sh [options]"
            echo ""
            echo "Options:"
            echo "  --all     Deploy all services (app, db, redis)"
            echo "  --db      Create/configure PostgreSQL database"
            echo "  --redis   Create/configure Redis"
            echo "  --migrate Run database migrations"
            echo "  --help    Show this help"
            exit 0
            ;;
    esac
done

# Create app if it doesn't exist
APP_NAME="bidking-api"
if ! flyctl apps list | grep -q "$APP_NAME"; then
    echo "Creating Fly.io app: $APP_NAME"
    flyctl apps create "$APP_NAME" --org personal
fi

# Deploy PostgreSQL if requested
if [ "$DEPLOY_ALL" = true ] || [ "$DEPLOY_DB" = true ]; then
    echo ""
    echo "Setting up PostgreSQL..."

    if ! flyctl postgres list | grep -q "bidking-db"; then
        flyctl postgres create \
            --name bidking-db \
            --region sjc \
            --vm-size shared-cpu-1x \
            --initial-cluster-size 1 \
            --volume-size 10
    fi

    # Attach to app
    flyctl postgres attach bidking-db --app "$APP_NAME" || true
    echo "PostgreSQL configured!"
fi

# Deploy Redis if requested
if [ "$DEPLOY_ALL" = true ] || [ "$DEPLOY_REDIS" = true ]; then
    echo ""
    echo "Setting up Redis..."

    if ! flyctl redis list | grep -q "bidking-redis"; then
        flyctl redis create \
            --name bidking-redis \
            --region sjc \
            --no-replicas
    fi

    echo "Redis configured!"
    echo "Note: Get Redis URL with 'flyctl redis status bidking-redis'"
fi

# Set secrets if not already set
echo ""
echo "Checking secrets..."

REQUIRED_SECRETS=(
    "SECRET_KEY"
    "SAM_GOV_API_KEY"
    "STRIPE_SECRET_KEY"
    "STRIPE_WEBHOOK_SECRET"
    "RESEND_API_KEY"
)

for secret in "${REQUIRED_SECRETS[@]}"; do
    if ! flyctl secrets list --app "$APP_NAME" | grep -q "$secret"; then
        echo "Warning: Secret $secret not set!"
        echo "Set it with: flyctl secrets set $secret=your_value --app $APP_NAME"
    fi
done

# Run migrations if requested
if [ "$MIGRATE" = true ]; then
    echo ""
    echo "Running database migrations..."
    flyctl ssh console --app "$APP_NAME" -C "cd /app && alembic upgrade head"
    echo "Migrations complete!"
fi

# Deploy application
echo ""
echo "Deploying application..."
flyctl deploy --app "$APP_NAME" --no-cache --strategy immediate

echo ""
echo "=========================================="
echo "Deployment complete!"
echo "=========================================="
echo ""
echo "App URL: https://$APP_NAME.fly.dev"
echo "Logs: flyctl logs --app $APP_NAME"
echo "Console: flyctl ssh console --app $APP_NAME"
echo ""
