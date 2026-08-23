"""
Room-related endpoints:
    GET /rooms                -> list all rooms
    GET /rooms/availability   -> rooms actually free for given dates
"""

from datetime import date
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.models import Room
from app.schemas.room import RoomOut
from app.services.availability import get_available_rooms

router = APIRouter(prefix="/rooms", tags=["rooms"])


@router.get("", response_model=list[RoomOut])
def list_rooms(db: Session = Depends(get_db)):
    """Returns every room in the hotel, regardless of booking status."""
    return db.query(Room).all()


@router.get("/availability", response_model=list[RoomOut])
def check_availability(
    check_in: date = Query(..., description="Check-in date, e.g. 2026-08-10"),
    check_out: date = Query(..., description="Check-out date, e.g. 2026-08-12"),
    room_type: str | None = Query(None, description="Optional filter, e.g. 'Deluxe'"),
    adults: int | None = Query(None, description="Optional minimum capacity filter"),
    db: Session = Depends(get_db),
):
    """
    Returns rooms that are actually free for the given date range -
    this is a real overlap check against existing bookings, not a
    static status flag. See app/services/availability.py.
    """
    if check_out <= check_in:
        raise HTTPException(status_code=422, detail="check_out must be after check_in")

    return get_available_rooms(db, check_in, check_out, room_type=room_type, min_capacity=adults)
