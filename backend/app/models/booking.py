"""
Booking model.

Links a customer to a room for a specific date range. `booking_id` is the
short human-friendly code (e.g. "BK1024") we read out to the customer -
it's separate from the internal auto-increment `id` used for foreign keys.

Two rows in this table for the SAME room are only a conflict if their
[check_in, check_out) date ranges overlap. That overlap check is what
Phase 3's availability logic will query for.
"""

from sqlalchemy import Boolean, Column, Integer, String, Date, DECIMAL, Enum, ForeignKey, TIMESTAMP, func
from sqlalchemy.orm import relationship

from app.database.db import Base


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    booking_id = Column(String(20), nullable=False, unique=True)  # e.g. "BK1024"

    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=False)

    check_in = Column(Date, nullable=False)
    check_out = Column(Date, nullable=False)
    adults = Column(Integer, nullable=False)
    children = Column(Integer, nullable=False, default=0)

    total_amount = Column(DECIMAL(10, 2), nullable=False)
    booking_status = Column(
        Enum("confirmed", "cancelled", "completed", name="booking_status_enum"),
        nullable=False,
        default="confirmed",
    )
    is_modified = Column(Boolean, default=False, nullable=False) 
    created_at = Column(TIMESTAMP, server_default=func.now())

    customer = relationship("Customer", back_populates="bookings")
    room = relationship("Room", back_populates="bookings")

    def __repr__(self):
        return f"<Booking {self.booking_id} room={self.room_id} {self.check_in}->{self.check_out}>"
