def test_list_rooms(client):
    res = client.get("/rooms")
    assert res.status_code == 200
    rooms = res.json()
    assert len(rooms) == 4
    types = {r["room_type"] for r in rooms}
    assert types == {"Standard", "Deluxe", "Premium", "Suite"}


def test_availability_returns_all_rooms_when_none_booked(client):
    res = client.get("/rooms/availability", params={"check_in": "2027-01-10", "check_out": "2027-01-12"})
    assert res.status_code == 200
    assert len(res.json()) == 4


def test_availability_invalid_dates_rejected(client):
    res = client.get("/rooms/availability", params={"check_in": "2027-01-12", "check_out": "2027-01-10"})
    assert res.status_code == 422


def test_availability_excludes_booked_room(client, sample_room_ids):
    room_id = sample_room_ids["Deluxe"]
    client.post("/bookings", json={
        "customer_name": "Test", "customer_phone": "9111100001", "room_id": room_id,
        "check_in": "2027-02-01", "check_out": "2027-02-03", "adults": 2,
    })
    res = client.get("/rooms/availability", params={"check_in": "2027-02-01", "check_out": "2027-02-03"})
    returned_ids = {r["id"] for r in res.json()}
    assert room_id not in returned_ids


def test_availability_room_type_filter(client):
    res = client.get("/rooms/availability", params={
        "check_in": "2027-01-10", "check_out": "2027-01-12", "room_type": "Suite",
    })
    rooms = res.json()
    assert all(r["room_type"] == "Suite" for r in rooms)
