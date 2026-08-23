"""
Availability service.

This is the single source of truth for "is this room actually free for
these dates?" Every place that needs to check availability - the /rooms
endpoint, booking creation, and later the AI's check_room_availability()
tool - must go through this function instead of re-implementing the logic.

THE OVERLAP RULE:
Two date ranges [a_start, a_end) and [b_start, b_end) overlap if and only if:
    a_start < b_end AND b_start < a_end

We use half-open ranges (check-out day itself is NOT occupied), which
matches how hotels actually work: a guest checking out on the 12th and
another checking in on the 12th is fine, not a conflict.

Only 'confirmed' bookings block a room. Cancelled bookings don't count.
"""

from datetime import date

from sqlalchemy.orm import Session

from app.models import Room, Booking


def room_is_available(
    db: Session,
    room_id: int,
    check_in: date,
    check_out: date,
    exclude_booking_id: int | None = None,
) -> bool:
    """
    Returns True if the given room has no confirmed booking whose date
    range overlaps [check_in, check_out).

    exclude_booking_id:
        Optional database Booking.id to ignore. This is useful when
        modifying an existing booking, because that booking's own
        current reservation should not block its modification.
    """

    query = (
        db.query(Booking)
        .filter(
            Booking.room_id == room_id,
            Booking.booking_status == "confirmed",
            Booking.check_in < check_out,
            check_in < Booking.check_out,
        )
    )

    if exclude_booking_id is not None:
        query = query.filter(
            Booking.id != exclude_booking_id
        )

    conflicting_booking = query.first()

    return conflicting_booking is None


def get_available_rooms(
    db: Session,
    check_in: date,
    check_out: date,
    room_type: str | None = None,
    min_capacity: int | None = None,
    exclude_booking_id: int | None = None,
) -> list[Room]:
    """
    Returns all rooms (optionally filtered by type/capacity) that are:

    - not under maintenance
    - free for the requested date range
    - not occupied by another confirmed booking

    exclude_booking_id:
        Optional database Booking.id to ignore while checking
        availability. This allows an existing booking to move/change
        within its own reservation without treating itself as a conflict.
    """

    query = db.query(Room).filter(
        Room.status != "maintenance"
    )

    if room_type:
        query = query.filter(
            Room.room_type.ilike(room_type)
        )

    if min_capacity:
        query = query.filter(
            Room.capacity >= min_capacity
        )

    candidate_rooms = query.all()

    return [
        room
        for room in candidate_rooms
        if room_is_available(
            db,
            room.id,
            check_in,
            check_out,
            exclude_booking_id=exclude_booking_id,
        )
    ]