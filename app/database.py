"""
BidKing Database Configuration

SQLAlchemy async engine and session management.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from typing import Generator

from app.config import settings

# =============================================================================
# Database Engine
# =============================================================================

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=30,  # Increased from 10 to handle 50+ concurrent users
    max_overflow=10,  # Reduced overflow - prefer persistent connections
    pool_recycle=3600,  # Recycle connections after 1 hour
    echo=False,  # Disable SQL logging in production (was settings.debug)
)

# =============================================================================
# Session Factory
# =============================================================================

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# =============================================================================
# Base Model
# =============================================================================

Base = declarative_base()


# =============================================================================
# Dependency
# =============================================================================

def get_db() -> Generator[Session, None, None]:
    """
    Database session dependency for FastAPI.

    Yields a database session and ensures it's closed after use.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
