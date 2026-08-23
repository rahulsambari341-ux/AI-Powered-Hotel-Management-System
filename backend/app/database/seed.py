"""
Database initialization / seed script for Phase 2.

Run this ONCE (from the backend/ folder, with venv activated) to:
1. Create all tables defined in app/models/ if they don't exist yet.
2. Insert a handful of sample rooms and hotel FAQ entries, so Phase 3's
   API endpoints have real data to return.

Usage:
    python -m app.database.seed

Safe to re-run: it checks for existing rows before inserting, so it
won't create duplicates if you run it twice.
"""

from app.database.db import engine, SessionLocal, Base
from app.models import Room, HotelInfo


def create_tables():
    print("Creating tables (if they don't already exist)...")
    Base.metadata.create_all(bind=engine)
    print("Tables ready.")


def seed_rooms(db):
    if db.query(Room).count() > 0:
        print("Rooms table already has data - skipping room seed.")
        return

    sample_rooms = [
        Room(room_number="101", room_type="Standard", price_per_night=1800, capacity=2, status="available"),
        Room(room_number="102", room_type="Deluxe", price_per_night=2500, capacity=2, status="available"),
        Room(room_number="103", room_type="Premium", price_per_night=4000, capacity=3, status="available"),
        Room(room_number="104", room_type="Suite", price_per_night=7000, capacity=4, status="available"),
        Room(room_number="105", room_type="Standard", price_per_night=1800, capacity=2, status="available"),
        Room(room_number="106", room_type="Deluxe", price_per_night=2500, capacity=2, status="available"),
    ]
    db.add_all(sample_rooms)
    db.commit()
    print(f"Inserted {len(sample_rooms)} sample rooms.")


def seed_hotel_info(db):
    if db.query(HotelInfo).count() > 0:
        print("hotel_info table already has data - skipping info seed.")
        return

    sample_info = [
        HotelInfo(topic="checkin_time", answer="Check-in time is 12:00 PM (noon)."),
        HotelInfo(topic="checkout_time", answer="Check-out time is 11:00 AM."),
        HotelInfo(topic="wifi", answer="Yes, we provide free high-speed Wi-Fi in all rooms and common areas."),
        HotelInfo(topic="breakfast", answer="Complimentary breakfast is included with all bookings, served 7 AM to 10 AM."),
        HotelInfo(topic="parking", answer="Yes, free on-site parking is available for all guests."),
        HotelInfo(
            topic="cancellation_policy",
            answer="Bookings can be cancelled free of charge up to 24 hours before check-in. "
                   "Cancellations within 24 hours are charged one night's stay.",
        ),
    ]
    db.add_all(sample_info)
    db.commit()
    print(f"Inserted {len(sample_info)} hotel info entries.")


def main():
    create_tables()
    db = SessionLocal()
    try:
        seed_rooms(db)
        seed_hotel_info(db)
    finally:
        db.close()
    print("Seed complete.")


if __name__ == "__main__":
    main()
