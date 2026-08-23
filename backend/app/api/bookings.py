"""
Booking-related endpoints:

    POST   /bookings
        -> create a booking

    GET    /bookings/{booking_id}
        -> look up a booking by its BK code

    PUT    /bookings/{booking_id}
        -> modify dates / guest counts / room / room type

    DELETE /bookings/{booking_id}
        -> cancel a booking

Booking modification uses the canonical
app/services/booking_service.modify_booking() function.

Both direct API modification and AI modification ultimately use the
same booking-service validation/update logic.
"""

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
)

from sqlalchemy.orm import Session

from app.database.db import get_db
from app.models import Booking

from app.schemas.booking import (
    BookingCreate,
    BookingOut,
    BookingUpdate,
)

from app.services.booking_service import (
    create_booking,
    modify_booking,
    BookingModificationError,
)

from app.services.notification_service import (
    send_booking_cancellation,
)

from app.services.availability import (
    get_available_rooms,
)

from app.rate_limit import limiter


router = APIRouter(
    prefix="/bookings",
    tags=["bookings"],
)


# ============================================================
# CREATE BOOKING
# ============================================================

@router.post(
    "",
    response_model=BookingOut,
    status_code=201,
)
@limiter.limit("10/minute")
def make_booking(
    request: Request,
    payload: BookingCreate,
    db: Session = Depends(get_db),
):
    booking = create_booking(
        db=db,
        room_id=payload.room_id,
        customer_name=payload.customer_name,
        customer_phone=payload.customer_phone,
        customer_email=payload.customer_email,
        check_in=payload.check_in,
        check_out=payload.check_out,
        adults=payload.adults,
        children=payload.children,
    )

    return booking


# ============================================================
# GET BOOKING
# ============================================================

@router.get(
    "/{booking_id}",
    response_model=BookingOut,
)
def get_booking(
    booking_id: str,
    db: Session = Depends(get_db),
):
    booking = (
        db.query(Booking)
        .filter(
            Booking.booking_id == booking_id
        )
        .first()
    )

    if booking is None:
        raise HTTPException(
            status_code=404,
            detail=f"Booking {booking_id} not found",
        )

    return booking


# ============================================================
# MODIFY BOOKING
# ============================================================

@router.put(
    "/{booking_id}",
    response_model=BookingOut,
)
def update_booking(
    booking_id: str,
    payload: BookingUpdate,
    db: Session = Depends(get_db),
):
    """
    Modify an existing booking.

    Room selection supports two mutually exclusive methods:

    1. room_id
       Directly select a specific room.

    2. room_type
       Select an available room of that type automatically.

    If both are supplied, the request is rejected because they may
    describe two different rooms.
    """

    # --------------------------------------------------------
    # Find the existing booking first.
    # --------------------------------------------------------

    booking = (
        db.query(Booking)
        .filter(
            Booking.booking_id == booking_id
        )
        .first()
    )

    if booking is None:
        raise HTTPException(
            status_code=404,
            detail=f"Booking {booking_id} not found",
        )

    # --------------------------------------------------------
    # A cancelled/completed booking cannot be modified.
    # The canonical service will also enforce this, but checking
    # here allows room_type resolution to happen safely.
    # --------------------------------------------------------

    if booking.booking_status != "confirmed":
        raise HTTPException(
            status_code=409,
            detail=(
                f"Booking {booking_id} is "
                f"{booking.booking_status}, cannot modify"
            ),
        )

    # --------------------------------------------------------
    # room_id + room_type together are ambiguous.
    # --------------------------------------------------------

    if (
        payload.room_id is not None
        and payload.room_type is not None
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "Provide either room_id or room_type, "
                "not both"
            ),
        )

    # --------------------------------------------------------
    # Determine the dates that the modified booking will use.
    # If the client doesn't change a date, keep the existing one.
    # --------------------------------------------------------

    resolved_check_in = (
        payload.check_in
        if payload.check_in is not None
        else booking.check_in
    )

    resolved_check_out = (
        payload.check_out
        if payload.check_out is not None
        else booking.check_out
    )

    if resolved_check_out <= resolved_check_in:
        raise HTTPException(
            status_code=422,
            detail="check_out must be after check_in",
        )

    # --------------------------------------------------------
    # Determine guest count for room-type capacity filtering.
    # --------------------------------------------------------

    resolved_adults = (
        payload.adults
        if payload.adults is not None
        else booking.adults
    )

    resolved_children = (
        payload.children
        if payload.children is not None
        else booking.children
    )

    total_guests = (
        resolved_adults + resolved_children
    )

    # --------------------------------------------------------
    # Resolve room_type -> actual room_id.
    # --------------------------------------------------------

    resolved_room_id = payload.room_id

    if payload.room_type is not None:

        room_type = payload.room_type.strip()

        if not room_type:
            raise HTTPException(
                status_code=422,
                detail="room_type must not be empty",
            )

        available_rooms = get_available_rooms(
            db=db,
            check_in=resolved_check_in,
            check_out=resolved_check_out,
            room_type=room_type,
            min_capacity=total_guests,
            exclude_booking_id=booking.id,
        )

        if not available_rooms:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"No available {room_type} room "
                    f"for {resolved_check_in} to "
                    f"{resolved_check_out} "
                    f"with capacity for {total_guests} guests"
                ),
            )

        # Deterministic selection:
        # choose the first available room returned by the database.
        resolved_room_id = available_rooms[0].id

    # --------------------------------------------------------
    # Call the SAME canonical modification service.
    # --------------------------------------------------------

    try:

        updated_booking = modify_booking(
            db=db,
            booking_id=booking_id,
            new_check_in=payload.check_in,
            new_check_out=payload.check_out,
            new_adults=payload.adults,
            new_children=payload.children,
            new_room_id=resolved_room_id,
        )

    except BookingModificationError as e:

        raise HTTPException(
            status_code=e.status_code,
            detail=e.message,
        )

    return updated_booking


# ============================================================
# CANCEL BOOKING
# ============================================================

@router.delete(
    "/{booking_id}",
    response_model=BookingOut,
)
def cancel_booking(
    booking_id: str,
    db: Session = Depends(get_db),
):
    booking = (
        db.query(Booking)
        .filter(
            Booking.booking_id == booking_id
        )
        .first()
    )

    if booking is None:
        raise HTTPException(
            status_code=404,
            detail=f"Booking {booking_id} not found",
        )

    if booking.booking_status == "cancelled":
        raise HTTPException(
            status_code=409,
            detail=(
                f"Booking {booking_id} "
                "is already cancelled"
            ),
        )

    booking.booking_status = "cancelled"

    db.commit()
    db.refresh(booking)

    # --------------------------------------------------------
    # CANCELLATION NOTIFICATION
    #
    # Notification failure NEVER affects cancellation.
    # --------------------------------------------------------

    try:

        notification_result = (
            send_booking_cancellation(
                db,
                booking,
            )
        )

        import logging

        logging.getLogger("bookings").info(
            "Booking cancellation notification result for %s: %s",
            booking.booking_id,
            notification_result,
        )

    except Exception:

        import logging

        logging.getLogger("bookings").exception(
            "Booking cancellation notification failed for %s "
            "(cancellation still succeeded)",
            booking.booking_id,
        )

    return booking