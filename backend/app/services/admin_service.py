"""
Admin dashboard service (Phase 8.1).

Pure read-only aggregation over existing tables - no new tables, no
duplicated booking/room logic. Every number here comes from a real query
against the same `rooms`, `bookings`, `customers` tables the rest of the
app already uses.

Occupancy definition: a room counts as "occupied" if it has at least one
CONFIRMED booking whose date range includes TODAY. Cancelled bookings
never count. This deliberately reuses the same half-open-range overlap
logic as app/services/availability.py (check_in <= today < check_out)
rather than inventing a different definition of "occupied" for the
dashboard.
"""

from datetime import date


from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Room, Booking, Customer


def get_admin_stats(db: Session) -> dict:
    today = date.today()

    total_rooms = db.query(Room).count()

    # Rooms with a confirmed booking covering today.
    occupied_room_ids = {
        row[0] for row in db.query(Booking.room_id).filter(
            Booking.booking_status == "confirmed",
            Booking.check_in <= today,
            today < Booking.check_out,
        ).all()
    }
    occupied_rooms = len(occupied_room_ids)
    available_rooms = total_rooms - occupied_rooms

    occupancy_percentage = round((occupied_rooms / total_rooms) * 100, 1) if total_rooms else 0.0

    total_bookings = db.query(Booking).count()
    confirmed_bookings = db.query(Booking).filter(Booking.booking_status == "confirmed").count()
    cancelled_bookings = db.query(Booking).filter(Booking.booking_status == "cancelled").count()
    modified_bookings = (
    db.query(Booking)
    .filter(Booking.is_modified.is_(True))
    .count()
    )
    completed_bookings = db.query(Booking).filter(Booking.booking_status == "completed").count()

    # Revenue: sum of total_amount for confirmed + completed bookings only.
    # Cancelled bookings never contributed real revenue, so they're excluded.
    revenue = db.query(func.coalesce(func.sum(Booking.total_amount), 0)).filter(
        Booking.booking_status.in_(["confirmed", "completed"])
    ).scalar()

    # "Today's bookings" = bookings CREATED today (new reservations made today),
    # not bookings whose stay includes today - these are different things and
    # the dashboard should be unambiguous about which one this is.
    today_bookings = db.query(Booking).filter(
        func.date(Booking.created_at) == today
    ).count()

    total_customers = db.query(Customer).count()

    return {
        "total_rooms": total_rooms,
        "available_rooms": available_rooms,
        "occupied_rooms": occupied_rooms,
        "occupancy_percentage": occupancy_percentage,
        "total_bookings": total_bookings,
        "confirmed_bookings": confirmed_bookings,
        "cancelled_bookings": cancelled_bookings,
        "modified_bookings": modified_bookings,
        "completed_bookings": completed_bookings,
        "revenue": float(revenue),
        "today_bookings": today_bookings,
        "total_customers": total_customers,
    }


def get_recent_bookings(db: Session, limit: int = 20) -> list[dict]:
    bookings = (
        db.query(Booking)
        .order_by(Booking.created_at.desc())
        .limit(limit)
        .all()
    )
    result = []
    for b in bookings:
        result.append({
            "booking_id": b.booking_id,
            "customer_name": b.customer.name if b.customer else None,
            "room_number": b.room.room_number if b.room else None,
            "room_type": b.room.room_type if b.room else None,
            "check_in": str(b.check_in),
            "check_out": str(b.check_out),
            "adults": b.adults,
            "children": b.children,
            "total_amount": float(b.total_amount),
            "booking_status": b.booking_status,
            "created_at": b.created_at.isoformat() if b.created_at else None,
        })
    return result


def get_customers(db: Session) -> list[dict]:
    """
    Only the fields an admin dashboard actually needs - name, phone,
    email, and a booking count. No internal IDs beyond what's needed to
    key the row, no other tables' data joined in beyond that count.
    """
    customers = db.query(Customer).order_by(Customer.name).all()
    result = []
    for c in customers:
        result.append({
            "id": c.id,
            "name": c.name,
            "phone": c.phone,
            "email": c.email,
            "booking_count": len(c.bookings),
        })
    return result

def get_occupied_rooms(db: Session) -> list[dict]:
    today = date.today()

    bookings = (
        db.query(Booking)
        .filter(
            Booking.booking_status == "confirmed",
            Booking.check_in <= today,
            today < Booking.check_out,
        )
        .all()
    )

    result = []
    seen_rooms = set()

    for b in bookings:
        if b.room_id in seen_rooms:
            continue

        seen_rooms.add(b.room_id)

        result.append({
            "room_id": b.room_id,
            "room_number": b.room.room_number if b.room else None,
            "room_type": b.room.room_type if b.room else None,
            "booking_id": b.booking_id,
            "customer_name": b.customer.name if b.customer else None,
            "check_in": str(b.check_in),
            "check_out": str(b.check_out),
        })

    return result


def get_available_rooms(db: Session) -> list[dict]:
    today = date.today()

    occupied_room_ids = {
        row[0]
        for row in db.query(Booking.room_id)
        .filter(
            Booking.booking_status == "confirmed",
            Booking.check_in <= today,
            today < Booking.check_out,
        )
        .all()
    }

    rooms = (
        db.query(Room)
        .filter(~Room.id.in_(occupied_room_ids))
        .all()
    ) if occupied_room_ids else db.query(Room).all()

    return [
        {
            "room_id": room.id,
            "room_number": room.room_number,
            "room_type": room.room_type,
        }
        for room in rooms
    ]


def get_today_bookings(db: Session) -> list[dict]:
    today = date.today()

    bookings = (
        db.query(Booking)
        .filter(func.date(Booking.created_at) == today)
        .order_by(Booking.created_at.desc())
        .all()
    )

    return [
        {
            "booking_id": b.booking_id,
            "customer_name": b.customer.name if b.customer else None,
            "room_number": b.room.room_number if b.room else None,
            "room_type": b.room.room_type if b.room else None,
            "check_in": str(b.check_in),
            "check_out": str(b.check_out),
            "total_amount": float(b.total_amount),
            "booking_status": b.booking_status,
            "created_at": b.created_at.isoformat() if b.created_at else None,
        }
        for b in bookings
    ]


def get_all_bookings(db: Session) -> list[dict]:
    bookings = (
        db.query(Booking)
        .order_by(Booking.created_at.desc())
        .all()
    )

    return [
        {
            "booking_id": b.booking_id,
            "customer_name": b.customer.name if b.customer else None,
            "room_number": b.room.room_number if b.room else None,
            "room_type": b.room.room_type if b.room else None,
            "check_in": str(b.check_in),
            "check_out": str(b.check_out),
            "total_amount": float(b.total_amount),
            "booking_status": b.booking_status,
            "created_at": b.created_at.isoformat() if b.created_at else None,
        }
        for b in bookings
    ]


def get_cancelled_bookings(db: Session) -> list[dict]:
    bookings = (
        db.query(Booking)
        .filter(Booking.booking_status == "cancelled")
        .order_by(Booking.created_at.desc())
        .all()
    )

    return [
        {
            "booking_id": b.booking_id,
            "customer_name": b.customer.name if b.customer else None,
            "room_number": b.room.room_number if b.room else None,
            "room_type": b.room.room_type if b.room else None,
            "check_in": str(b.check_in),
            "check_out": str(b.check_out),
            "total_amount": float(b.total_amount),
            "booking_status": b.booking_status,
            "created_at": b.created_at.isoformat() if b.created_at else None,
        }
        for b in bookings
    ]


def get_modified_bookings(db: Session) -> list[dict]:
    bookings = (
        db.query(Booking)
        .filter(Booking.is_modified.is_(True))
        .order_by(Booking.created_at.desc())
        .all()
    )

    return [
        {
            "booking_id": b.booking_id,
            "customer_name": b.customer.name if b.customer else None,
            "room_number": b.room.room_number if b.room else None,
            "room_type": b.room.room_type if b.room else None,
            "check_in": str(b.check_in),
            "check_out": str(b.check_out),
            "total_amount": float(b.total_amount),
            "booking_status": b.booking_status,
            "created_at": b.created_at.isoformat() if b.created_at else None,
        }
        for b in bookings
    ]


def get_room_revenue(db: Session) -> list[dict]:
    rows = (
        db.query(
            Room.id,
            Room.room_number,
            Room.room_type,
            func.coalesce(func.sum(Booking.total_amount), 0)
        )
        .outerjoin(
            Booking,
            (Booking.room_id == Room.id)
            & Booking.booking_status.in_(["confirmed", "completed"])
        )
        .group_by(Room.id, Room.room_number, Room.room_type)
        .order_by(Room.room_number)
        .all()
    )

    return [
        {
            "room_id": row[0],
            "room_number": row[1],
            "room_type": row[2],
            "revenue": float(row[3]),
        }
        for row in rows
    ]
