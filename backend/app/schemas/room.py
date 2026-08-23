"""
Pydantic schemas for Room.

These are NOT the same as app/models/room.py. The ORM model describes the
database table; these schemas describe the JSON shape that goes over the API.
Keeping them separate means we can change the DB structure without
automatically changing the public API contract, and vice versa.
"""

from decimal import Decimal
from pydantic import BaseModel, ConfigDict


class RoomOut(BaseModel):
    """What we send back to the client when returning a room."""
    model_config = ConfigDict(from_attributes=True)  # lets us build this from an ORM object directly

    id: int
    room_number: str
    room_type: str
    price_per_night: Decimal
    capacity: int
    status: str


class RoomAvailabilityQuery(BaseModel):
    """Query params for checking availability, validated as a group."""
    check_in: str   # ISO date string, e.g. "2026-08-10"
    check_out: str
    room_type: str | None = None
    adults: int | None = None
