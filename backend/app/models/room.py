"""
Room model.

Represents a physical room in the hotel. `status` is a coarse flag
(available / booked / maintenance) used mainly for maintenance holds.

IMPORTANT: `status` alone does NOT tell you if a room is free for a given
date range. A room can be "available" today but already have a future
booking for next week. Real availability is computed in Phase 3 by
checking for overlapping bookings in the `bookings` table, not by
reading this column. We'll build that query in Phase 3.
"""

from sqlalchemy import Column, Integer, String, DECIMAL, Enum
from sqlalchemy.orm import relationship

from app.database.db import Base


class Room(Base):
    __tablename__ = "rooms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    room_number = Column(String(10), nullable=False, unique=True)
    room_type = Column(String(50), nullable=False)
    price_per_night = Column(DECIMAL(10, 2), nullable=False)
    capacity = Column(Integer, nullable=False)
    status = Column(
        Enum("available", "booked", "maintenance", name="room_status_enum"),
        nullable=False,
        default="available",
    )

    # One room can appear in many bookings over time (different date ranges).
    bookings = relationship("Booking", back_populates="room")

    def __repr__(self):
        return f"<Room {self.room_number} ({self.room_type})>"
