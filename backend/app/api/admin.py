"""
Admin dashboard endpoints (Phase 8.1).

    GET /admin/stats             -> dashboard summary numbers
    GET /admin/bookings/recent   -> most recent bookings (any status)
    GET /admin/customers         -> customer list with booking counts

All read-only, all backed by real queries in app/services/admin_service.py -
nothing here duplicates booking/room/availability logic that already
exists elsewhere.

SECURITY NOTE (explicitly deferred, not overlooked): these endpoints have
NO authentication yet. That's intentional for this phase - the project
had no auth system before this, and the task spec says not to add auth
unless it already exists. Authentication/authorization for admin routes
is real, necessary work that belongs in Phase 9.4 (security hardening)
before this is ever exposed publicly. Do not deploy this dashboard to a
public URL without adding auth first.

None of these endpoints expose secrets: no API keys, no database
passwords, no Twilio credentials, no LLM credentials. The customer list
only returns name/phone/email/booking_count - not internal booking
history details beyond a count.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date
from pydantic import BaseModel
from typing import Optional
import random

from app.database.db import get_db
from app.admin_auth import require_admin
from app.schemas.admin import AdminStats, RecentBooking, AdminCustomer
from app.models import Booking, Room, Customer
from app.services.admin_service import (
    get_admin_stats,
    get_recent_bookings,
    get_customers,
    get_occupied_rooms,
    get_available_rooms,
    get_today_bookings,
    get_all_bookings,
    get_cancelled_bookings,
    get_modified_bookings,
    get_room_revenue,
)

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)


@router.get("/stats", response_model=AdminStats)
def stats(db: Session = Depends(get_db)):
    return get_admin_stats(db)


@router.get("/bookings/recent", response_model=list[RecentBooking])
def recent_bookings(limit: int = 20, db: Session = Depends(get_db)):
    return get_recent_bookings(db, limit=limit)


@router.get("/customers", response_model=list[AdminCustomer])
def customers(db: Session = Depends(get_db)):
    return get_customers(db)

@router.get("/rooms/occupied")
def occupied_rooms(db: Session = Depends(get_db)):
    return get_occupied_rooms(db)


@router.get("/rooms/available")
def available_rooms(db: Session = Depends(get_db)):
    return get_available_rooms(db)


@router.get("/bookings/today")
def today_bookings(db: Session = Depends(get_db)):
    return get_today_bookings(db)


@router.get("/bookings/all")
def all_bookings(db: Session = Depends(get_db)):
    return get_all_bookings(db)


@router.get("/bookings/cancelled")
def cancelled_bookings(db: Session = Depends(get_db)):
    return get_cancelled_bookings(db)


@router.get("/bookings/modified")
def modified_bookings(db: Session = Depends(get_db)):
    return get_modified_bookings(db)


@router.get("/revenue/rooms")
def room_revenue(db: Session = Depends(get_db)):
    return get_room_revenue(db)


@router.post("/bookings/{booking_id}/cancel")
def admin_cancel_booking(booking_id: str, db: Session = Depends(get_db)):
    booking = db.query(Booking).filter(Booking.booking_id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    booking.booking_status = "cancelled"
    db.commit()
    return {"message": f"Booking {booking_id} cancelled successfully"}


@router.post("/bookings/{booking_id}/modify")
def admin_modify_booking(booking_id: str, db: Session = Depends(get_db)):
    booking = db.query(Booking).filter(Booking.booking_id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    booking.is_modified = True
    db.commit()
    return {"message": f"Booking {booking_id} marked as modified"}


class BookingUpdate(BaseModel):
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None
    room_id: Optional[int] = None
    check_in: Optional[date] = None
    check_out: Optional[date] = None
    adults: Optional[int] = None
    children: Optional[int] = None
    booking_status: Optional[str] = None


@router.put("/bookings/{booking_id}/update")
def admin_update_booking(booking_id: str, payload: BookingUpdate, db: Session = Depends(get_db)):
    booking = db.query(Booking).filter(Booking.booking_id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    if booking.customer:
        if payload.customer_name is not None:
            booking.customer.name = payload.customer_name
        if payload.customer_phone is not None:
            booking.customer.phone = payload.customer_phone
        if payload.customer_email is not None:
            booking.customer.email = payload.customer_email

    if payload.room_id is not None:
        room = db.query(Room).filter(Room.id == payload.room_id).first()
        if not room:
            raise HTTPException(status_code=404, detail="Room not found")
        booking.room_id = payload.room_id

    if payload.check_in is not None:
        booking.check_in = payload.check_in
    if payload.check_out is not None:
        booking.check_out = payload.check_out
    if payload.adults is not None:
        booking.adults = payload.adults
    if payload.children is not None:
        booking.children = payload.children
    if payload.booking_status is not None:
        booking.booking_status = payload.booking_status

    # Recalculate total amount after modification
    room = db.query(Room).filter(Room.id == booking.room_id).first()
    if not room:
         raise HTTPException(status_code=404, detail="Room not found")

    nights = (booking.check_out - booking.check_in).days
    if nights <= 0:
         raise HTTPException(status_code=400, detail="Check-out must be after check-in")

    booking.total_amount = room.price_per_night * nights
        
    booking.is_modified = True
    db.commit()

    return {"message": f"Booking {booking_id} updated successfully"}


class NewBookingPayload(BaseModel):
    customer_name: str
    customer_phone: str
    customer_email: Optional[str] = None
    room_id: int
    check_in: date
    check_out: date
    total_amount: float
    adults: int = 1
    children: int = 0


@router.post("/bookings/create")
def admin_create_booking(payload: NewBookingPayload, db: Session = Depends(get_db)):
    # 1. Find or create customer
    customer = db.query(Customer).filter(Customer.phone == payload.customer_phone).first()
    if not customer:
        customer = Customer(
            name=payload.customer_name,
            phone=payload.customer_phone,
            email=payload.customer_email
        )
        db.add(customer)
        db.commit()
        db.refresh(customer)

    # 2. Generate unique booking ID
    booking_id = f"BK{random.randint(1000, 9999)}"

    # 3. Create booking record with adults, children, and defaults
    new_booking = Booking(
        booking_id=booking_id,
        customer_id=customer.id,
        room_id=payload.room_id,
        check_in=payload.check_in,
        check_out=payload.check_out,
        adults=payload.adults,
        children=payload.children,
        total_amount=payload.total_amount,
        booking_status="confirmed",
        is_modified=False
    )
    db.add(new_booking)
    db.commit()
    return {"message": f"Booking {booking_id} created successfully", "booking_id": booking_id}
