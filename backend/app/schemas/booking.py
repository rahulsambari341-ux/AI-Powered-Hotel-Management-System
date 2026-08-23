"""
Pydantic schemas for Booking (and the Customer info embedded in a booking request).
"""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator


class BookingCreate(BaseModel):
    """What the client sends us to create a new booking."""
    customer_name: str
    customer_phone: str
    customer_email: str | None = None

    room_id: int
    check_in: date
    check_out: date
    adults: int
    children: int = 0

    @field_validator("check_out")
    @classmethod
    def check_out_after_check_in(cls, v, info):
        check_in = info.data.get("check_in")
        if check_in and v <= check_in:
            raise ValueError("check_out must be after check_in")
        return v

    @field_validator("adults")
    @classmethod
    def adults_at_least_one(cls, v):
        if v < 1:
            raise ValueError("adults must be at least 1")
        return v


class BookingOut(BaseModel):
    """What we send back after creating/fetching a booking."""
    model_config = ConfigDict(from_attributes=True)

    booking_id: str
    room_id: int
    check_in: date
    check_out: date
    adults: int
    children: int
    total_amount: Decimal
    booking_status: str
    created_at: datetime | None = None


class BookingUpdate(BaseModel):
    """What the client can change on an existing booking."""

    check_in: date | None = None
    check_out: date | None = None

    adults: int | None = None
    children: int | None = None

    # Direct room selection by internal room ID.
    room_id: int | None = None

    # User-friendly room-type selection.
    # Example: "Deluxe", "Premium", "Suite", "Standard".
    room_type: str | None = None