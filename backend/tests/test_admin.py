def test_admin_stats_empty_database(client):
    res = client.get("/admin/stats")
    assert res.status_code == 200
    data = res.json()
    assert data["total_bookings"] == 0
    assert data["revenue"] == 0
    assert data["occupied_rooms"] == 0
    assert data["total_rooms"] == 4


def test_admin_stats_reflects_real_bookings(client, sample_room_ids):
    client.post("/bookings", json={
        "customer_name": "Stats Test", "customer_phone": "9333300001",
        "room_id": sample_room_ids["Deluxe"], "check_in": "2027-07-01", "check_out": "2027-07-03", "adults": 2,
    })
    res = client.get("/admin/stats")
    data = res.json()
    assert data["total_bookings"] == 1
    assert data["confirmed_bookings"] == 1
    assert data["revenue"] == 5000.0  # 2 nights * 2500


def test_admin_stats_cancelled_not_counted_as_occupied_or_revenue(client, sample_room_ids):
    res = client.post("/bookings", json={
        "customer_name": "Cancel Test", "customer_phone": "9333300002",
        "room_id": sample_room_ids["Suite"], "check_in": "2027-07-01", "check_out": "2027-07-03", "adults": 2,
    })
    booking_id = res.json()["booking_id"]
    client.delete(f"/bookings/{booking_id}")

    data = client.get("/admin/stats").json()
    assert data["cancelled_bookings"] == 1
    assert data["confirmed_bookings"] == 0
    assert data["revenue"] == 0  # cancelled booking's amount excluded


def test_admin_stats_occupancy_uses_todays_date(client, sample_room_ids):
    from datetime import date, timedelta
    today = date.today()
    client.post("/bookings", json={
        "customer_name": "Today Guest", "customer_phone": "9333300003",
        "room_id": sample_room_ids["Premium"],
        "check_in": str(today - timedelta(days=1)),
        "check_out": str(today + timedelta(days=1)),
        "adults": 2,
    })
    data = client.get("/admin/stats").json()
    assert data["occupied_rooms"] == 1
    assert data["available_rooms"] == 3


def test_admin_recent_bookings(client, sample_room_ids):
    client.post("/bookings", json={
        "customer_name": "Recent Test", "customer_phone": "9333300004",
        "room_id": sample_room_ids["Standard"], "check_in": "2027-08-01", "check_out": "2027-08-02", "adults": 1,
    })
    res = client.get("/admin/bookings/recent")
    assert res.status_code == 200
    bookings = res.json()
    assert len(bookings) == 1
    assert bookings[0]["customer_name"] == "Recent Test"
    assert bookings[0]["room_type"] == "Standard"


def test_admin_customers_list(client, sample_room_ids):
    client.post("/bookings", json={
        "customer_name": "Customer One", "customer_phone": "9333300005",
        "room_id": sample_room_ids["Standard"], "check_in": "2027-08-01", "check_out": "2027-08-02", "adults": 1,
    })
    res = client.get("/admin/customers")
    assert res.status_code == 200
    customers = res.json()
    assert len(customers) == 1
    assert customers[0]["name"] == "Customer One"
    assert customers[0]["booking_count"] == 1
    # Only the expected fields are exposed - no secrets/extra internal data
    assert set(customers[0].keys()) == {"id", "name", "phone", "email", "booking_count"}
