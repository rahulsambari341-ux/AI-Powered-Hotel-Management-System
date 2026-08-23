#!/usr/bin/env python
"""
Tests for the current deterministic booking-state extraction and update logic.

IMPORTANT:
These tests are aligned with the CURRENT conversation.py API.

conversation.py is intentionally NOT modified by these tests.
"""

import sys

sys.path.insert(0, ".")

from app.agents.conversation import (
    _build_system_prompt,
    _customer_details,
    _extract_dates,
    _guest_counts,
    _room_number,
    _room_type,
    _update_state,
)


def test_dates():
    print("=" * 60)
    print("TEST: Date Extraction")
    print("=" * 60)

    test_cases = [
        (
            "I want a room from December 20, 2027 to December 22, 2027",
            ("2027-12-20", "2027-12-22"),
        ),
        (
            "2027-12-20 to 2027-12-22",
            ("2027-12-20", "2027-12-22"),
        ),
        (
            "December 20, 2027 to December 22, 2027",
            ("2027-12-20", "2027-12-22"),
        ),
    ]

    for text, expected in test_cases:
        check_in, check_out = _extract_dates(text)

        print(f"\nInput: {text}")
        print(f"Output: check_in={check_in}, check_out={check_out}")

        assert check_in == expected[0], (
            f"Expected check-in {expected[0]}, got {check_in}"
        )

        assert check_out == expected[1], (
            f"Expected check-out {expected[1]}, got {check_out}"
        )

    print("\n✓ Date extraction tests passed!")


def test_guests():
    print("\n" + "=" * 60)
    print("TEST: Guest Count Extraction")
    print("=" * 60)

    test_cases = [
        ("for 2 adults", 2, None),
        ("3 guests", 3, None),
        ("2 adults and 1 child", 2, 1),
    ]

    for text, expected_adults, expected_children in test_cases:
        adults, children = _guest_counts(text)

        print(f"\nInput: {text}")
        print(f"Output: adults={adults}, children={children}")

        assert adults == expected_adults, (
            f"Expected adults={expected_adults}, got {adults}"
        )

        if expected_children is not None:
            assert children == expected_children, (
                f"Expected children={expected_children}, got {children}"
            )

    print("\n✓ Guest extraction tests passed!")


def test_room_type():
    print("\n" + "=" * 60)
    print("TEST: Room Type Extraction")
    print("=" * 60)

    test_cases = [
        ("I want a Deluxe room", "Deluxe"),
        ("book a premium room", "Premium"),
        ("Suite please", "Suite"),
    ]

    for text, expected in test_cases:
        result = _room_type(text)

        print(f"\nInput: {text}")
        print(f"Output: {result}")

        assert result == expected, (
            f"Expected {expected}, got {result}"
        )

    print("\n✓ Room type extraction tests passed!")


def test_customer_details():
    print("\n" + "=" * 60)
    print("TEST: Customer Details Extraction")
    print("=" * 60)

    test_cases = [
        ("My name is Rahul", {"customer_name": "Rahul"}),
        ("My phone is 9876543210", {"customer_phone": "9876543210"}),
        (
            "Contact me at test@example.com",
            {"customer_email": "test@example.com"},
        ),
    ]

    for text, expected in test_cases:
        result = _customer_details(text)

        print(f"\nInput: {text}")
        print(f"Output: {result}")

        for key, expected_value in expected.items():
            assert result.get(key) == expected_value, (
                f"Expected {key}={expected_value}, "
                f"got {result.get(key)}"
            )

    print("\n✓ Customer details extraction tests passed!")


def test_room_selection():
    print("\n" + "=" * 60)
    print("TEST: Room Selection Extraction")
    print("=" * 60)

    test_cases = [
        ("I want Room 102", "102"),
        ("Book room number 106", "106"),
        ("Can I get Room 104?", "104"),
    ]

    for text, expected_room_number in test_cases:
        result = _room_number(text)

        print(f"\nInput: {text}")
        print(f"Output: {result}")

        assert result == expected_room_number, (
            f"Expected room {expected_room_number}, got {result}"
        )

    print("\n✓ Room selection extraction tests passed!")


def test_state_update():
    print("\n" + "=" * 60)
    print("TEST: Booking State Update")
    print("=" * 60)

    initial_state = {
        "check_in": None,
        "check_out": None,
        "adults": None,
        "children": 0,
        "room_type": None,
        "selected_room_id": None,
        "selected_room_number": None,
        "available_rooms": [],
        "availability_checked": False,
        "dates_validated": False,
        "customer_name": None,
        "customer_phone": None,
        "customer_email": None,
        "modification": {},
    }

    # ---------------------------------------------------------
    # TEST 1: Add dates and adults
    # ---------------------------------------------------------

    message1 = (
        "I want a room from December 20, 2027 "
        "to December 22, 2027 for 2 adults"
    )

    # IMPORTANT:
    # _update_state() modifies the dictionary in-place.
    # It does NOT return the dictionary.
    _update_state(initial_state, message1)

    state1 = initial_state

    print(f"\nMessage 1: {message1}")
    print(
        f"State: check_in={state1['check_in']}, "
        f"check_out={state1['check_out']}, "
        f"adults={state1['adults']}"
    )

    assert state1["check_in"] == "2027-12-20"
    assert state1["check_out"] == "2027-12-22"
    assert state1["adults"] == 2

    # No availability should be marked as checked
    # merely by updating controller state.
    assert state1["availability_checked"] is False

    # Dates are not automatically marked validated here.
    assert state1["dates_validated"] is False

    # ---------------------------------------------------------
    # TEST 2: Add room type
    # ---------------------------------------------------------

    message2 = "I prefer Deluxe rooms"

    _update_state(state1, message2)

    state2 = state1

    print(f"\nMessage 2: {message2}")
    print(
        f"State: room_type={state2['room_type']}, "
        f"check_in={state2['check_in']}, "
        f"check_out={state2['check_out']}"
    )

    assert state2["room_type"] == "Deluxe"

    # Existing dates must remain intact.
    assert state2["check_in"] == "2027-12-20"
    assert state2["check_out"] == "2027-12-22"

    # Current conversation.py intentionally invalidates
    # availability/room selection when room type changes.
    assert state2["availability_checked"] is False
    assert state2["selected_room_id"] is None
    assert state2["selected_room_number"] is None

    # ---------------------------------------------------------
    # TEST 3: Add customer details
    # ---------------------------------------------------------

    message3 = "My name is Rahul and my phone is 9876543210"

    _update_state(state2, message3)

    state3 = state2

    print(f"\nMessage 3: {message3}")
    print(
        f"State: name={state3['customer_name']}, "
        f"phone={state3['customer_phone']}"
    )

    assert state3["customer_name"] == "Rahul"
    assert state3["customer_phone"] == "9876543210"

    # Existing booking information must remain intact.
    assert state3["check_in"] == "2027-12-20"
    assert state3["check_out"] == "2027-12-22"
    assert state3["adults"] == 2
    assert state3["room_type"] == "Deluxe"

    print("\n✓ State update tests passed!")


def test_state_formatting():
    """
    The old version of the controller exposed:

        _format_booking_state_for_prompt()

    The CURRENT conversation.py no longer has that helper.

    The current implementation places the booking state into
    the system prompt through:

        _build_system_prompt(language, booking_state)

    Therefore this test verifies the CURRENT implementation.
    """

    print("\n" + "=" * 60)
    print("TEST: Booking State in System Prompt")
    print("=" * 60)

    state = {
        "check_in": "2027-12-20",
        "check_out": "2027-12-22",
        "adults": 2,
        "children": 0,
        "room_type": "Deluxe",
        "selected_room_id": None,
        "selected_room_number": None,
        "available_rooms": [],
        "availability_checked": False,
        "dates_validated": False,
        "customer_name": "Rahul",
        "customer_phone": "9876543210",
        "customer_email": None,
        "modification": {},
    }

    formatted = _build_system_prompt("en", state)

    print("\nSystem prompt contains booking state:")
    print(formatted)

    assert "2027-12-20" in formatted
    assert "2027-12-22" in formatted

    assert '"adults": 2' in formatted
    assert '"children": 0' in formatted

    assert '"room_type": "Deluxe"' in formatted

    assert '"customer_name": "Rahul"' in formatted
    assert '"customer_phone": "9876543210"' in formatted

    print("\n✓ Booking state prompt test passed!")


if __name__ == "__main__":
    try:
        test_dates()
        test_guests()
        test_room_type()
        test_customer_details()
        test_room_selection()
        test_state_update()
        test_state_formatting()

        print("\n" + "=" * 60)
        print("✅ ALL BOOKING STATE TESTS PASSED!")
        print("=" * 60)

    except Exception as e:
        print("\n❌ TEST FAILED:")
        print(e)

        import traceback

        traceback.print_exc()
        sys.exit(1)