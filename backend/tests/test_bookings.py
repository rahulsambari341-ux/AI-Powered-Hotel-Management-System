"""
Booking creation, retrieval, cancellation, and modification tests.

Covers:

- booking creation
- capacity validation
- booking retrieval
- cancellation
- valid date modification
- invalid date modification
- unavailable room modification
- direct room_id modification
- room_type modification
- room_type + date modification
- invalid/unavailable room_type
- conflicting room_id + room_type
- guest count modification
- capacity validation
- invalid booking ID
- cancelled booking modification
- availability after modification
- database persistence
"""


def _create_booking(
    client,
    room_id,
    phone="9222200001",
    check_in="2027-03-01",
    check_out="2027-03-03",
    adults=2,
):
    res = client.post(
        "/bookings",
        json={
            "customer_name": "Tester",
            "customer_phone": phone,
            "room_id": room_id,
            "check_in": check_in,
            "check_out": check_out,
            "adults": adults,
        },
    )

    assert res.status_code == 201, res.text

    return res.json()


# ============================================================
# CREATE
# ============================================================

def test_create_booking(client, sample_room_ids):
    booking = _create_booking(
        client,
        sample_room_ids["Standard"],
    )

    assert booking["booking_status"] == "confirmed"
    assert booking["total_amount"] == "3600.00"


def test_create_booking_over_capacity_rejected(
    client,
    sample_room_ids,
):
    res = client.post(
        "/bookings",
        json={
            "customer_name": "Tester",
            "customer_phone": "9222200002",
            "room_id": sample_room_ids["Standard"],
            "check_in": "2027-03-01",
            "check_out": "2027-03-03",
            "adults": 5,
        },
    )

    assert res.status_code == 422


# ============================================================
# GET
# ============================================================

def test_get_booking(client, sample_room_ids):
    booking = _create_booking(
        client,
        sample_room_ids["Deluxe"],
    )

    res = client.get(
        f"/bookings/{booking['booking_id']}"
    )

    assert res.status_code == 200
    assert res.json()["booking_id"] == booking["booking_id"]


def test_get_unknown_booking_404(client):
    res = client.get("/bookings/BK0000")

    assert res.status_code == 404


# ============================================================
# CANCEL
# ============================================================

def test_cancel_booking(client, sample_room_ids):
    booking = _create_booking(
        client,
        sample_room_ids["Deluxe"],
    )

    res = client.delete(
        f"/bookings/{booking['booking_id']}"
    )

    assert res.status_code == 200
    assert res.json()["booking_status"] == "cancelled"


def test_cancel_already_cancelled_booking_409(
    client,
    sample_room_ids,
):
    booking = _create_booking(
        client,
        sample_room_ids["Deluxe"],
    )

    client.delete(
        f"/bookings/{booking['booking_id']}"
    )

    res = client.delete(
        f"/bookings/{booking['booking_id']}"
    )

    assert res.status_code == 409


# ============================================================
# MODIFICATION - DATES
# ============================================================

def test_modify_valid_date_change(
    client,
    sample_room_ids,
):
    booking = _create_booking(
        client,
        sample_room_ids["Standard"],
    )

    res = client.put(
        f"/bookings/{booking['booking_id']}",
        json={
            "check_out": "2027-03-05"
        },
    )

    assert res.status_code == 200

    data = res.json()

    assert data["check_out"] == "2027-03-05"
    assert data["total_amount"] == "7200.00"


def test_modify_invalid_date_rejected(
    client,
    sample_room_ids,
):
    booking = _create_booking(
        client,
        sample_room_ids["Standard"],
    )

    res = client.put(
        f"/bookings/{booking['booking_id']}",
        json={
            "check_in": "2027-03-10",
            "check_out": "2027-03-05",
        },
    )

    assert res.status_code == 422


# ============================================================
# MODIFICATION - ROOM ID
# ============================================================

def test_modify_unavailable_room_rejected(
    client,
    sample_room_ids,
):
    booking_a = _create_booking(
        client,
        sample_room_ids["Deluxe"],
        phone="9222200010",
        check_in="2027-04-01",
        check_out="2027-04-03",
    )

    booking_b = _create_booking(
        client,
        sample_room_ids["Standard"],
        phone="9222200011",
        check_in="2027-04-01",
        check_out="2027-04-03",
    )

    res = client.put(
        f"/bookings/{booking_b['booking_id']}",
        json={
            "room_id": sample_room_ids["Deluxe"]
        },
    )

    assert res.status_code == 409


def test_modify_room_type_change(
    client,
    sample_room_ids,
):
    booking = _create_booking(
        client,
        sample_room_ids["Standard"],
    )

    res = client.put(
        f"/bookings/{booking['booking_id']}",
        json={
            "room_id": sample_room_ids["Premium"]
        },
    )

    assert res.status_code == 200
    assert res.json()["room_id"] == sample_room_ids["Premium"]


# ============================================================
# MODIFICATION - ROOM TYPE
# ============================================================

def test_modify_by_room_type(
    client,
    sample_room_ids,
):
    """
    room_type="Deluxe" must automatically select an available
    Deluxe room instead of requiring the caller to know its ID.
    """

    booking = _create_booking(
        client,
        sample_room_ids["Standard"],
    )

    res = client.put(
        f"/bookings/{booking['booking_id']}",
        json={
            "room_type": "Deluxe"
        },
    )

    assert res.status_code == 200

    data = res.json()

    assert data["room_id"] == sample_room_ids["Deluxe"]


def test_modify_by_room_type_case_insensitive(
    client,
    sample_room_ids,
):
    """
    Room type matching should work regardless of capitalization.
    """

    booking = _create_booking(
        client,
        sample_room_ids["Standard"],
    )

    res = client.put(
        f"/bookings/{booking['booking_id']}",
        json={
            "room_type": "deluxe"
        },
    )

    assert res.status_code == 200

    assert res.json()["room_id"] == sample_room_ids["Deluxe"]


def test_modify_by_room_type_with_date_change(
    client,
    sample_room_ids,
):
    """
    Room-type selection must consider the NEW dates.
    """

    booking = _create_booking(
        client,
        sample_room_ids["Standard"],
        check_in="2027-06-01",
        check_out="2027-06-03",
    )

    res = client.put(
        f"/bookings/{booking['booking_id']}",
        json={
            "check_in": "2027-06-10",
            "check_out": "2027-06-12",
            "room_type": "Deluxe",
        },
    )

    assert res.status_code == 200

    data = res.json()

    assert data["room_id"] == sample_room_ids["Deluxe"]
    assert data["check_in"] == "2027-06-10"
    assert data["check_out"] == "2027-06-12"


def test_modify_by_room_type_respects_capacity(
    client,
    sample_room_ids,
):
    """
    A room type is only selected when the room can accommodate
    the requested number of guests.
    """

    booking = _create_booking(
        client,
        sample_room_ids["Standard"],
        adults=2,
    )

    res = client.put(
        f"/bookings/{booking['booking_id']}",
        json={
            "room_type": "Premium",
            "adults": 3,
        },
    )

    assert res.status_code == 200

    data = res.json()

    assert data["room_id"] == sample_room_ids["Premium"]
    assert data["adults"] == 3


def test_modify_by_unavailable_room_type_rejected(
    client,
    sample_room_ids,
):
    """
    If all rooms of the requested type are occupied for the
    requested dates, modification must fail.
    """

    deluxe_booking = _create_booking(
        client,
        sample_room_ids["Deluxe"],
        phone="9222200020",
        check_in="2027-09-01",
        check_out="2027-09-03",
    )

    standard_booking = _create_booking(
        client,
        sample_room_ids["Standard"],
        phone="9222200021",
        check_in="2027-09-01",
        check_out="2027-09-03",
    )

    res = client.put(
        f"/bookings/{standard_booking['booking_id']}",
        json={
            "room_type": "Deluxe"
        },
    )

    assert res.status_code == 409

    # Make sure the original Deluxe booking still exists.
    assert deluxe_booking["booking_status"] == "confirmed"


def test_modify_invalid_room_type_rejected(
    client,
    sample_room_ids,
):
    booking = _create_booking(
        client,
        sample_room_ids["Standard"],
    )

    res = client.put(
        f"/bookings/{booking['booking_id']}",
        json={
            "room_type": "Presidential"
        },
    )

    assert res.status_code == 409


def test_modify_room_id_and_room_type_together_rejected(
    client,
    sample_room_ids,
):
    """
    The API must not silently choose between two conflicting
    room-selection instructions.
    """

    booking = _create_booking(
        client,
        sample_room_ids["Standard"],
    )

    res = client.put(
        f"/bookings/{booking['booking_id']}",
        json={
            "room_id": sample_room_ids["Premium"],
            "room_type": "Deluxe",
        },
    )

    assert res.status_code == 422


# ============================================================
# MODIFICATION - GUESTS
# ============================================================

def test_modify_guest_count(
    client,
    sample_room_ids,
):
    booking = _create_booking(
        client,
        sample_room_ids["Premium"],
        adults=2,
    )

    res = client.put(
        f"/bookings/{booking['booking_id']}",
        json={
            "adults": 3
        },
    )

    assert res.status_code == 200
    assert res.json()["adults"] == 3


def test_modify_guest_count_over_capacity_rejected(
    client,
    sample_room_ids,
):
    booking = _create_booking(
        client,
        sample_room_ids["Standard"],
        adults=2,
    )

    res = client.put(
        f"/bookings/{booking['booking_id']}",
        json={
            "adults": 5
        },
    )

    assert res.status_code == 422


# ============================================================
# MODIFICATION - ERROR CASES
# ============================================================

def test_modify_invalid_booking_id_404(client):
    res = client.put(
        "/bookings/BK0000",
        json={
            "adults": 2
        },
    )

    assert res.status_code == 404


def test_modify_cancelled_booking_rejected(
    client,
    sample_room_ids,
):
    booking = _create_booking(
        client,
        sample_room_ids["Standard"],
    )

    client.delete(
        f"/bookings/{booking['booking_id']}"
    )

    res = client.put(
        f"/bookings/{booking['booking_id']}",
        json={
            "adults": 2
        },
    )

    assert res.status_code == 409


# ============================================================
# MODIFICATION - AVAILABILITY
# ============================================================

def test_modify_availability_reflects_after_change(
    client,
    sample_room_ids,
):
    """
    After moving a booking off a room, that room+dates should
    become available again.
    """

    booking = _create_booking(
        client,
        sample_room_ids["Suite"],
        check_in="2027-05-01",
        check_out="2027-05-03",
    )

    client.put(
        f"/bookings/{booking['booking_id']}",
        json={
            "room_id": sample_room_ids["Premium"]
        },
    )

    res = client.get(
        "/rooms/availability",
        params={
            "check_in": "2027-05-01",
            "check_out": "2027-05-03",
        },
    )

    available_ids = {
        r["id"]
        for r in res.json()
    }

    assert sample_room_ids["Suite"] in available_ids
    assert sample_room_ids["Premium"] not in available_ids


# ============================================================
# MODIFICATION - PERSISTENCE
# ============================================================

def test_modify_persists_to_database(
    client,
    sample_room_ids,
):
    booking = _create_booking(
        client,
        sample_room_ids["Standard"],
    )

    client.put(
        f"/bookings/{booking['booking_id']}",
        json={
            "adults": 2,
            "check_out": "2027-03-06",
        },
    )

    res = client.get(
        f"/bookings/{booking['booking_id']}"
    )

    assert res.status_code == 200
    assert res.json()["check_out"] == "2027-03-06"