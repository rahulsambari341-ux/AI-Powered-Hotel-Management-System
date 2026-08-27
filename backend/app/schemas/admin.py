from pydantic import BaseModel


class AdminStats(BaseModel):
    total_rooms: int
    available_rooms: int
    occupied_rooms: int
    occupancy_percentage: float
    total_bookings: int
    confirmed_bookings: int
    cancelled_bookings: int
    modified_bookings: int
    completed_bookings: int
    revenue: float
    today_bookings: int
    total_customers: int


class RecentBooking(BaseModel):
    booking_id: str
    customer_name: str | None
    room_number: str | None
    room_type: str | None
    check_in: str
    check_out: str
    adults: int
    children: int
    total_amount: float
    booking_status: str
    created_at: str | None


class AdminCustomer(BaseModel):
    id: int
    name: str
    phone: str
    email: str | None
    booking_count: int
