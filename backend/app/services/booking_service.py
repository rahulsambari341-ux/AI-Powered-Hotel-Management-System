"""
Booking service.

Handles the actual booking-creation transaction:
1. Re-check availability.
2. Get-or-create the customer by phone number.
3. Generate a unique booking_id.
4. Insert the booking row.
5. Compute total_amount.
6. Send best-effort booking confirmation notification.

Modification:
- Uses the same canonical modify_booking() function for both
  API and AI tool calls.
- Sends SMS + email after successful modification.

Notification failures NEVER roll back or fail the booking operation.
"""

import logging
import random
import string
from datetime import date

from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models import Room, Customer, Booking
from app.services.availability import room_is_available


logger = logging.getLogger("booking_service")


# ============================================================
# BOOKING ID
# ============================================================

def generate_booking_id(
    db: Session,
) -> str:
    """
    Generates a short booking code like BK4821.
    """

    for _ in range(10):

        candidate = (
            "BK"
            + "".join(
                random.choices(
                    string.digits,
                    k=4,
                )
            )
        )

        exists = (
            db.query(Booking)
            .filter(
                Booking.booking_id == candidate
            )
            .first()
        )

        if not exists:
            return candidate

    raise RuntimeError(
        "Could not generate a unique booking_id after 10 attempts"
    )


# ============================================================
# CUSTOMER
# ============================================================

def get_or_create_customer(
    db: Session,
    name: str,
    phone: str,
    email: str | None,
) -> Customer:

    customer = (
        db.query(Customer)
        .filter(
            Customer.phone == phone
        )
        .first()
    )

    if customer:

        # Keep existing customer data updated if the
        # latest booking contains an email/name.

        if name:
            customer.name = name

        if email:
            customer.email = email

        db.flush()

        return customer

    customer = Customer(
        name=name,
        phone=phone,
        email=email,
    )

    db.add(customer)

    db.flush()

    return customer


# ============================================================
# CREATE BOOKING
# ============================================================

def create_booking(
    db: Session,
    room_id: int,
    customer_name: str,
    customer_phone: str,
    customer_email: str | None,
    check_in: date,
    check_out: date,
    adults: int,
    children: int,
) -> Booking:

    room = (
        db.query(Room)
        .filter(
            Room.id == room_id
        )
        .first()
    )

    if room is None:

        raise HTTPException(
            status_code=404,
            detail=(
                f"Room {room_id} does not exist"
            ),
        )

    if room.status == "maintenance":

        raise HTTPException(
            status_code=409,
            detail=(
                f"Room {room.room_number} "
                "is under maintenance"
            ),
        )

    if adults + children > room.capacity:

        raise HTTPException(
            status_code=422,
            detail=(
                f"Room {room.room_number} has capacity "
                f"{room.capacity}, but "
                f"{adults + children} guests requested"
            ),
        )

    # --------------------------------------------------------
    # Re-check availability immediately before booking
    # --------------------------------------------------------

    if not room_is_available(
        db,
        room_id,
        check_in,
        check_out,
    ):

        raise HTTPException(
            status_code=409,
            detail=(
                f"Room {room.room_number} is no longer "
                f"available for {check_in} to {check_out}"
            ),
        )

    # --------------------------------------------------------
    # Calculate total
    # --------------------------------------------------------

    nights = (
        check_out - check_in
    ).days

    total_amount = (
        nights * room.price_per_night
    )

    # --------------------------------------------------------
    # Customer
    # --------------------------------------------------------

    customer = get_or_create_customer(
        db=db,
        name=customer_name,
        phone=customer_phone,
        email=customer_email,
    )

    # --------------------------------------------------------
    # Create booking
    # --------------------------------------------------------

    booking = Booking(
        booking_id=generate_booking_id(db),
        customer_id=customer.id,
        room_id=room.id,
        check_in=check_in,
        check_out=check_out,
        adults=adults,
        children=children,
        total_amount=total_amount,
        booking_status="confirmed",
    )

    db.add(booking)

    # --------------------------------------------------------
    # IMPORTANT:
    # Booking must commit before notifications.
    # --------------------------------------------------------

    db.commit()

    db.refresh(booking)

    # --------------------------------------------------------
    # BOOKING CONFIRMATION
    #
    # Notification failure NEVER affects booking.
    # --------------------------------------------------------

    try:

        from app.services.notification_service import (
            send_booking_confirmation,
        )

        notification_result = (
            send_booking_confirmation(
                db,
                booking,
            )
        )

        logger.info(
            "Booking confirmation notification result for %s: %s",
            booking.booking_id,
            notification_result,
        )

    except Exception:

        logger.exception(
            "Booking confirmation notification failed for %s "
            "(booking still created successfully)",
            booking.booking_id,
        )

    return booking


# ============================================================
# MODIFICATION ERROR
# ============================================================

class BookingModificationError(Exception):
    """
    Raised by modify_booking() for validation/availability failures.

    HTTP and AI layers translate this error independently.
    """

    def __init__(
        self,
        message: str,
        status_code: int = 422,
    ):

        self.message = message
        self.status_code = status_code

        super().__init__(
            message
        )


# ============================================================
# MODIFY BOOKING
# ============================================================

def modify_booking(
    db: Session,
    booking_id: str,
    new_check_in: date | None = None,
    new_check_out: date | None = None,
    new_adults: int | None = None,
    new_children: int | None = None,
    new_room_id: int | None = None,
    customer_name: str | None = None,
    customer_phone: str | None = None,
    customer_email: str | None = None,
) -> Booking:
    """
    Canonical booking modification function.

    After successful commit:
        SMS + email notification are sent.

    Notification failure NEVER rolls back the modification.
    """

    # --------------------------------------------------------
    # Find booking
    # --------------------------------------------------------

    booking = (
        db.query(Booking)
        .filter(
            Booking.booking_id == booking_id
        )
        .first()
    )

    if booking is None:

        raise BookingModificationError(
            f"No booking found with ID {booking_id}",
            status_code=404,
        )

    # --------------------------------------------------------
    # Booking must be confirmed
    # --------------------------------------------------------

    if booking.booking_status != "confirmed":

        raise BookingModificationError(
            f"Booking {booking_id} is "
            f"{booking.booking_status}, cannot modify",
            status_code=409,
        )

    # --------------------------------------------------------
    # Update Customer Details if provided
    # --------------------------------------------------------

    if customer_name or customer_phone or customer_email:
        customer = booking.customer
        if customer:
            if customer_name is not None:
                customer.name = customer_name
            if customer_phone is not None:
                customer.phone = customer_phone
            if customer_email is not None:
                customer.email = customer_email
            db.flush()

    # --------------------------------------------------------
    # Resolve values
    # --------------------------------------------------------

    resolved_check_in = (
        new_check_in
        if new_check_in is not None
        else booking.check_in
    )

    resolved_check_out = (
        new_check_out
        if new_check_out is not None
        else booking.check_out
    )

    resolved_adults = (
        new_adults
        if new_adults is not None
        else booking.adults
    )

    resolved_children = (
        new_children
        if new_children is not None
        else booking.children
    )

    resolved_room_id = (
        new_room_id
        if new_room_id is not None
        else booking.room_id
    )



    # --------------------------------------------------------
    # Date validation
    # --------------------------------------------------------

    if resolved_check_out <= resolved_check_in:

        raise BookingModificationError(
            "check_out must be after check_in",
            status_code=422,
        )

    # --------------------------------------------------------
    # Room
    # --------------------------------------------------------

    room = (
        db.query(Room)
        .filter(
            Room.id == resolved_room_id
        )
        .first()
    )

    if room is None:

        raise BookingModificationError(
            f"Room {resolved_room_id} does not exist",
            status_code=404,
        )

    if room.status == "maintenance":

        raise BookingModificationError(
            f"Room {room.room_number} is under maintenance",
            status_code=409,
        )

    # --------------------------------------------------------
    # Capacity
    # --------------------------------------------------------

    if (
        resolved_adults
        + resolved_children
        > room.capacity
    ):

        raise BookingModificationError(
            f"Room {room.room_number} has capacity "
            f"{room.capacity}, but "
            f"{resolved_adults + resolved_children} "
            "guests requested",
            status_code=422,
        )

    # --------------------------------------------------------
    # Availability
    # --------------------------------------------------------

    conflict_query = (
        db.query(Booking)
        .filter(
            Booking.room_id == resolved_room_id,
            Booking.booking_status == "confirmed",
            Booking.id != booking.id,
            Booking.check_in < resolved_check_out,
            resolved_check_in < Booking.check_out,
        )
    )

    if conflict_query.first() is not None:

        raise BookingModificationError(
            f"Room {room.room_number} is not available "
            f"for {resolved_check_in} to "
            f"{resolved_check_out}",
            status_code=409,
        )

    # --------------------------------------------------------
    # Calculate new total
    # --------------------------------------------------------

    nights = (
        resolved_check_out
        - resolved_check_in
    ).days

    booking.check_in = resolved_check_in
    booking.check_out = resolved_check_out
    booking.adults = resolved_adults
    booking.children = resolved_children
    booking.room_id = resolved_room_id
    booking.total_amount = (
        nights * room.price_per_night
    )
    
    # --------------------------------------------------------
    # IMPORTANT:
    # Commit modification BEFORE notification.
    # --------------------------------------------------------
    booking.is_modified = True
    db.commit()

    db.refresh(booking)

    # --------------------------------------------------------
    # MODIFICATION NOTIFICATION
    # --------------------------------------------------------

    try:

        from app.services.notification_service import (
            send_booking_modification,
        )

        notification_result = (
            send_booking_modification(
                db,
                booking,
            )
        )

        logger.info(
            "Booking modification notification result for %s: %s",
            booking.booking_id,
            notification_result,
        )

    except Exception:

        logger.exception(
            "Booking modification notification failed for %s "
            "(modification still succeeded)",
            booking.booking_id,
        )

    return booking