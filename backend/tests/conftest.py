"""
Shared pytest fixtures.

CRITICAL: this sets MYSQL_DATABASE to a separate "hotel_ai_test" database
BEFORE importing anything from the app - so every part of the codebase
(FastAPI dependency-injected sessions AND app/agents/tools.py's direct
SessionLocal() calls) transparently uses the test database, with zero
risk of ever touching real development/production data. This is why
the env override happens at module import time, at the very top of this
file, before any `from app...` import runs.

Test isolation strategy:
- rooms/hotel_info are seeded once per test session
- bookings/customers are truncated before EVERY test function
- in-memory storage is cleared between tests
"""

import os


# ============================================================
# Test Environment
# ============================================================

os.environ["MYSQL_DATABASE"] = "hotel_ai_test"

os.environ.setdefault(
    "MYSQL_HOST",
    "localhost",
)

os.environ.setdefault(
    "MYSQL_USER",
    "hotel_user",
)

# Never use real Redis during tests.
os.environ["REDIS_URL"] = ""

# Never accidentally hit real external services in tests.
os.environ["OPENAI_API_KEY"] = ""

# IMPORTANT:
# The application defaults LLM_PROVIDER to "ollama".
# For the "no LLM configured" test, explicitly clear it.
os.environ["LLM_PROVIDER"] = ""

os.environ["TWILIO_ACCOUNT_SID"] = ""
os.environ["TWILIO_AUTH_TOKEN"] = ""
os.environ["TWILIO_SMS_FROM_NUMBER"] = ""

# Rate limiting is tested separately.
os.environ["RATE_LIMIT_ENABLED"] = "false"


# ============================================================
# Imports
# ============================================================


import pytest

from fastapi.testclient import TestClient

from app.database.db import (
    Base,
    engine,
    SessionLocal,
)

from app.models import (
    Room,
    HotelInfo,
)

from app.main import app

import app.storage as storage


# ============================================================
# Test Database Setup
# ============================================================

@pytest.fixture(
    scope="session",
    autouse=True,
)
def _setup_test_database():
    """
    Creates tables and seeds minimal reference data once
    for the whole test run.
    """

    Base.metadata.create_all(
        bind=engine
    )

    db = SessionLocal()

    try:

        # ----------------------------------------------------
        # Reset and seed canonical test rooms
        # ----------------------------------------------------

        db.execute(
          __import__("sqlalchemy").text(
            "SET FOREIGN_KEY_CHECKS=0"
          )
       )

        db.execute(
          __import__("sqlalchemy").text(
            "TRUNCATE TABLE rooms"
          )
        )

        db.execute(
          __import__("sqlalchemy").text(
            "SET FOREIGN_KEY_CHECKS=1"
          )
        )

        db.add_all(
         [
          Room(
            room_number="101",
            room_type="Standard",
            price_per_night=1800,
            capacity=2,
            status="available",
        ),

        Room(
            room_number="102",
            room_type="Deluxe",
            price_per_night=2500,
            capacity=2,
            status="available",
        ),

        Room(
            room_number="103",
            room_type="Premium",
            price_per_night=4000,
            capacity=3,
            status="available",
        ),

        Room(
            room_number="104",
            room_type="Suite",
            price_per_night=7000,
            capacity=4,
            status="available",
        ),
    ]
)

        # ----------------------------------------------------
        # Seed hotel information
        # ----------------------------------------------------

        if db.query(HotelInfo).count() == 0:

            db.add_all(
                [
                    HotelInfo(
                        topic="checkin_time",
                        answer="Check-in time is 12:00 PM.",
                    ),

                    HotelInfo(
                        topic="wifi",
                        answer="Yes, free Wi-Fi is available.",
                    ),
                ]
            )

        db.commit()

    finally:

        db.close()

    yield


# ============================================================
# Clean Transactional Data
# ============================================================

@pytest.fixture(
    autouse=True
)
def _clean_transactional_data():
    """
    Truncates bookings/customers before every test.

    Each test therefore starts from a known-empty transactional state.
    """

    db = SessionLocal()

    try:

        db.execute(
            __import__("sqlalchemy").text(
                "SET FOREIGN_KEY_CHECKS=0"
            )
        )

        db.execute(
            __import__("sqlalchemy").text(
                "TRUNCATE TABLE bookings"
            )
        )

        db.execute(
            __import__("sqlalchemy").text(
                "TRUNCATE TABLE customers"
            )
        )

        db.execute(
            __import__("sqlalchemy").text(
                "SET FOREIGN_KEY_CHECKS=1"
            )
        )

        db.commit()

    finally:

        db.close()

    # --------------------------------------------------------
    # Clear in-memory storage between tests
    # --------------------------------------------------------

    storage._memory_store.clear()

    yield


# ============================================================
# Database Fixture
# ============================================================

@pytest.fixture
def db_session():

    db = SessionLocal()

    try:

        yield db

    finally:

        db.close()


# ============================================================
# FastAPI Test Client
# ============================================================

@pytest.fixture
def client():
    return TestClient(
        app,
        headers={
            "Authorization": "Bearer change-this-development-admin-token"
        },
    )

# ============================================================
# Sample Room IDs
# ============================================================

@pytest.fixture
def sample_room_ids(db_session):

    rooms = (
        db_session
        .query(Room)
        .order_by(Room.id)
        .all()
    )

    return {
        room.room_type: room.id
        for room in rooms
    }