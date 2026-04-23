"""
database.py
SQLAlchemy engine and session factory for the MMM backend.
Uses lazy engine initialization so FastAPI starts cleanly even if the
DB container is still coming up — pool_pre_ping handles reconnection.
"""

import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv

load_dotenv()

_engine = None


def get_database_url() -> str:
    host     = os.getenv("POSTGRES_HOST",     "db")
    port     = os.getenv("POSTGRES_PORT",     "5432")
    db       = os.getenv("POSTGRES_DB",       "mmm_db")
    user     = os.getenv("POSTGRES_USER",     "mmm_user")
    password = os.getenv("POSTGRES_PASSWORD", "mmm_pass")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"


def get_engine():
    """
    Returns the shared SQLAlchemy engine, creating it on first call.
    Lazy init means FastAPI won't crash at startup if the DB isn't ready yet.
    pool_pre_ping=True re-checks the connection before each use.
    """
    global _engine
    if _engine is None:
        _engine = create_engine(
            get_database_url(),
            pool_pre_ping=True,   # verify connection before each use
            pool_size=5,
            max_overflow=10,
        )
    return _engine


def get_session_factory():
    return sessionmaker(autocommit=False, autoflush=False, bind=get_engine())


def get_db():
    """
    FastAPI dependency — yields one DB session per request, always closes it.

    Usage in any endpoint:
        from database import get_db
        from sqlalchemy.orm import Session
        from fastapi import Depends

        @app.get("/something")
        def my_endpoint(db: Session = Depends(get_db)):
            ...
    """
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_connection() -> bool:
    """Returns True if the database is reachable."""
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"DB connection failed: {e}")
        return False
