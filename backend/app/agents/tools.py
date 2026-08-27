"""
Tool boundary for the AI Hotel Booking Agent.

Design
------
LLM
 |
 v
TOOL_SCHEMAS
 |
 v
TOOL_FUNCTIONS
 |
 v
app.services
 |
 v
MySQL

The LLM never receives a database session and never writes SQL.

Transactional functions exist here because the conversation controller needs
a single JSON-safe interface to the existing service layer. The controller,
not the LLM, decides when create/cancel/modify is authorized.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from app.database.db import SessionLocal
from app.models import Booking, HotelInfo, Room
from app.services.availability import get_available_rooms
from app.services.booking_service import create_booking as _create_booking


# ---------------------------------------------------------------------------
# Date handling
# ---------------------------------------------------------------------------

def _parse_date(value: str) -> date:
    if not isinstance(value, str):
        raise ValueError("Date must be a string in YYYY-MM-DD format")
    return datetime.strptime(value, "%Y-%m-%d").date()


def _date_error(check_in: date, check_out: date) -> str | None:
    today = date.today()

    if check_in < today:
        return (
            f"Check-in date {check_in.isoformat()} is in the past. "
            "Please provide a future check-in date."
        )

    if check_out <= check_in:
        return "check_out must be after check_in"

    return None


def validate_booking_dates(
    check_in: str,
    check_out: str,
) -> dict[str, Any]:
    """Deterministically validate a complete booking date range."""
    try:
        ci = _parse_date(check_in)
        co = _parse_date(check_out)
    except (TypeError, ValueError):
        return {
            "valid": False,
            "error": "Dates must be in YYYY-MM-DD format",
        }

    error = _date_error(ci, co)
    if error:
        return {
            "valid": False,
            "error": error,
            "date_error": True,
        }

    return {
        "valid": True,
        "check_in": ci.isoformat(),
        "check_out": co.isoformat(),
    }


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------

def check_room_availability(
    check_in: str,
    check_out: str,
    room_type: str | None = None,
    adults: int | None = None,
) -> dict[str, Any]:
    """
    Return real available rooms.

    No availability is invented here. The canonical availability service is
    the only source of room availability.
    """
    try:
        ci = _parse_date(check_in)
        co = _parse_date(check_out)
    except (TypeError, ValueError):
        return {"error": "Dates must be in YYYY-MM-DD format"}

    error = _date_error(ci, co)
    if error:
        return {"error": error, "date_error": True}

    db = SessionLocal()
    try:
        rooms = get_available_rooms(
            db,
            ci,
            co,
            room_type=room_type,
            min_capacity=adults,
        )

        return {
            "available_rooms": [
                {
                    "room_id": room.id,
                    "room_number": str(room.room_number),
                    "room_type": room.room_type,
                    "price_per_night": float(room.price_per_night),
                    "capacity": room.capacity,
                }
                for room in rooms
            ]
        }
    except Exception:
        return {"error": "Unable to check room availability."}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Room details
# ---------------------------------------------------------------------------

def get_room_details(room_id: int) -> dict[str, Any]:
    db = SessionLocal()
    try:
        room = db.query(Room).filter(Room.id == room_id).first()

        if room is None:
            return {"error": f"No room with id {room_id}"}

        return {
            "room_id": room.id,
            "room_number": str(room.room_number),
            "room_type": room.room_type,
            "price_per_night": float(room.price_per_night),
            "capacity": room.capacity,
            "status": room.status,
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Create booking
# ---------------------------------------------------------------------------

def create_booking_tool(
    room_id: int,
    customer_name: str,
    customer_phone: str,
    check_in: str,
    check_out: str,
    adults: int,
    children: int = 0,
    customer_email: str | None = None,
) -> dict[str, Any]:
    """
    Create a real booking through the canonical booking service.

    This function itself does not decide whether the customer authorized the
    transaction. That authorization belongs to conversation.py.
    """
    try:
        ci = _parse_date(check_in)
        co = _parse_date(check_out)
    except (TypeError, ValueError):
        return {"error": "Dates must be in YYYY-MM-DD format"}

    error = _date_error(ci, co)
    if error:
        return {"error": error, "date_error": True}

    if int(adults) < 1:
        return {"error": "At least one adult is required"}

    if int(children) < 0:
        return {"error": "Children cannot be negative"}

    db = SessionLocal()
    try:
        booking = _create_booking(
            db=db,
            room_id=room_id,
            customer_name=customer_name,
            customer_phone=customer_phone,
            customer_email=customer_email,
            check_in=ci,
            check_out=co,
            adults=int(adults),
            children=int(children),
        )

        return {
            "booking_id": booking.booking_id,
            "room_id": booking.room_id,
            "check_in": str(booking.check_in),
            "check_out": str(booking.check_out),
            "total_amount": float(booking.total_amount),
            "status": booking.booking_status,
        }
    except Exception as exc:
        detail = getattr(exc, "detail", None)
        return {
            "error": str(detail if detail is not None else exc)
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Existing booking lookup
# ---------------------------------------------------------------------------

def get_booking_details(booking_id: str) -> dict[str, Any]:
    db = SessionLocal()
    try:
        booking = (
            db.query(Booking)
            .filter(Booking.booking_id == booking_id)
            .first()
        )

        if booking is None:
            return {
                "error": f"No booking found with ID {booking_id}"
            }

        return {
            "booking_id": booking.booking_id,
            "room_id": booking.room_id,
            "check_in": str(booking.check_in),
            "check_out": str(booking.check_out),
            "adults": booking.adults,
            "children": booking.children,
            "total_amount": float(booking.total_amount),
            "status": booking.booking_status,
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Cancellation
# ---------------------------------------------------------------------------

def cancel_booking_tool(booking_id: str) -> dict[str, Any]:
    db = SessionLocal()
    try:
        booking = (
            db.query(Booking)
            .filter(Booking.booking_id == booking_id)
            .first()
        )

        if booking is None:
            return {"error": f"No booking found with ID {booking_id}"}

        if booking.booking_status == "cancelled":
            return {
                "error": f"Booking {booking_id} is already cancelled"
            }

        booking.booking_status = "cancelled"
        db.commit()

        return {
            "booking_id": booking_id,
            "status": "cancelled",
        }
    except Exception:
        db.rollback()
        return {"error": "Unable to cancel the booking."}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Modification
# ---------------------------------------------------------------------------

def modify_booking_tool(
    booking_id: str,
    check_in: str | None = None,
    check_out: str | None = None,
    adults: int | None = None,
    children: int | None = None,
    room_type: str | None = None,
    room_number: str | None = None,
    customer_name: str | None = None,
    customer_phone: str | None = None,
    customer_email: str | None = None,
) -> dict[str, Any]:
    """
    Modify an existing booking through the canonical booking service.

    If a room type maps to multiple rooms, no room is selected automatically.
    The caller receives the actual choices.
    """
    from app.services.booking_service import (
        BookingModificationError,
        modify_booking as _modify_booking,
    )

    ci = None
    co = None

    try:
        if check_in:
            ci = _parse_date(check_in)
        if check_out:
            co = _parse_date(check_out)
    except (TypeError, ValueError):
        return {"error": "Dates must be in YYYY-MM-DD format"}

    if ci is not None and co is not None:
        error = _date_error(ci, co)
        if error:
            return {"error": error, "date_error": True}
    elif ci is not None and ci < date.today():
        return {
            "error": (
                f"Check-in date {ci.isoformat()} is in the past. "
                "Please provide a future check-in date."
            ),
            "date_error": True,
        }
    elif co is not None and co <= date.today():
        return {
            "error": (
                f"Check-out date {co.isoformat()} is not a future date."
            ),
            "date_error": True,
        }

    db = SessionLocal()
    try:
        booking = (
            db.query(Booking)
            .filter(Booking.booking_id == booking_id)
            .first()
        )

        if booking is None:
            return {"error": f"No booking found with ID {booking_id}"}

        new_room_id = None

        if room_number:
            room = (
                db.query(Room)
                .filter(Room.room_number == str(room_number))
                .first()
            )
            if room is None:
                return {
                    "error": f"Room {room_number} was not found."
                }

            new_room_id = room.id

        elif room_type:
            lookup_ci = ci or booking.check_in
            lookup_co = co or booking.check_out

            candidates = get_available_rooms(
                db,
                lookup_ci,
                lookup_co,
                room_type=room_type,
                min_capacity=adults,
            )

            if not candidates:
                return {
                    "error": (
                        f"No available {room_type} room for those dates"
                    )
                }

            if len(candidates) > 1:
                return {
                    "room_selection_required": True,
                    "room_type": room_type,
                    "available_rooms": [
                        {
                            "room_id": room.id,
                            "room_number": str(room.room_number),
                            "room_type": room.room_type,
                            "price_per_night": float(room.price_per_night),
                            "capacity": room.capacity,
                        }
                        for room in candidates
                    ],
                }

            new_room_id = candidates[0].id

        try:
            updated = _modify_booking(
                db=db,
                booking_id=booking_id,
                new_check_in=ci,
                new_check_out=co,
                new_adults=adults,
                new_children=children,
                new_room_id=new_room_id,
                customer_name=customer_name,
                customer_phone=customer_phone,
                customer_email=customer_email,
            )
        except BookingModificationError as exc:
            return {"error": exc.message}

        return {
            "booking_id": updated.booking_id,
            "room_id": updated.room_id,
            "check_in": str(updated.check_in),
            "check_out": str(updated.check_out),
            "adults": updated.adults,
            "children": updated.children,
            "total_amount": float(updated.total_amount),
            "status": updated.booking_status,
        }

    except Exception:
        db.rollback()
        return {"error": "Unable to modify the booking."}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Hotel information
# ---------------------------------------------------------------------------

def get_hotel_information(topic: str) -> dict[str, Any]:
    db = SessionLocal()
    try:
        info = (
            db.query(HotelInfo)
            .filter(HotelInfo.topic.ilike(topic))
            .first()
        )

        if info is None:
            known_topics = [
                row.topic
                for row in db.query(HotelInfo.topic).all()
            ]
            return {
                "error": f"No information found for topic '{topic}'",
                "known_topics": known_topics,
            }

        return {
            "topic": info.topic,
            "answer": info.answer,
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------

def _function_schema(
    name: str,
    description: str,
    properties: dict[str, Any],
    required: list[str],
) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


TOOL_SCHEMAS = [
    _function_schema(
        "validate_booking_dates",
        "Validate a complete booking date range. Never guess a missing year.",
        {
            "check_in": {"type": "string", "description": "YYYY-MM-DD"},
            "check_out": {"type": "string", "description": "YYYY-MM-DD"},
        },
        ["check_in", "check_out"],
    ),

    _function_schema(
        "check_room_availability",
        "Return real rooms available for the requested dates and number of adults. "
        "Only call this tool when check_in, check_out, and adults are known. "
        "Never send null, empty, or missing values.",
        {
            "check_in": {
                "type": "string",
                "description": "Required. Check-in date in YYYY-MM-DD format.",
            },
            "check_out": {
                "type": "string",
                "description": "Required. Check-out date in YYYY-MM-DD format.",
            },
            "room_type": {
                "type": "string",
                "description": "Optional. Standard, Deluxe, Premium, or Suite.",
            },
            "adults": {
                "type": "integer",
                "description": "Required. Number of adults staying. Must be at least 1.",
            },
        },
        ["check_in", "check_out", "adults"],
    ),
    _function_schema(
        "get_room_details",
        "Get factual details for a room using its internal room ID.",
        {
            "room_id": {"type": "integer"},
        },
        ["room_id"],
    ),
    _function_schema(
        "get_booking_details",
        "Look up an existing booking by booking ID.",
        {
            "booking_id": {"type": "string"},
        },
        ["booking_id"],
    ),
    _function_schema(
        "get_hotel_information",
        "Look up factual hotel policies and facilities.",
        {
            "topic": {
                "type": "string",
                "description": (
                    "Examples: checkin_time, checkout_time, "
                    "wifi, breakfast, parking, cancellation_policy"
                ),
            },
        },
        ["topic"],
    ),
    _function_schema(
        "create_booking_tool",
        "Create a real booking after the controller has obtained explicit confirmation.",
        {
            "room_id": {"type": "integer"},
            "customer_name": {"type": "string"},
            "customer_phone": {"type": "string"},
            "customer_email": {"type": "string"},
            "check_in": {"type": "string", "description": "YYYY-MM-DD"},
            "check_out": {"type": "string", "description": "YYYY-MM-DD"},
            "adults": {"type": "integer"},
            "children": {"type": "integer"},
        },
        [
            "room_id",
            "customer_name",
            "customer_phone",
            "check_in",
            "check_out",
            "adults",
        ],
    ),
    _function_schema(
        "cancel_booking_tool",
        "Cancel an existing booking after explicit customer confirmation.",
        {
            "booking_id": {"type": "string"},
        },
        ["booking_id"],
    ),
    _function_schema(
        "modify_booking_tool",
        "Modify an existing booking after explicit customer confirmation.",
        {
            "booking_id": {"type": "string"},
            "check_in": {"type": "string", "description": "YYYY-MM-DD"},
            "check_out": {"type": "string", "description": "YYYY-MM-DD"},
            "adults": {"type": "integer"},
            "children": {"type": "integer"},
            "room_type": {"type": "string"},
            "room_number": {"type": "string"},
        },
        ["booking_id"],
    ),
]


TOOL_FUNCTIONS = {
    "validate_booking_dates": validate_booking_dates,
    "check_room_availability": check_room_availability,
    "get_room_details": get_room_details,
    "get_booking_details": get_booking_details,
    "create_booking_tool": create_booking_tool,
    "cancel_booking_tool": cancel_booking_tool,
    "modify_booking_tool": modify_booking_tool,
    "get_hotel_information": get_hotel_information,
}
