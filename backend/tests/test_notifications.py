"""
Notification tests.

CRITICAL RULE:
A booking must NEVER fail because a notification failed to send.

Twilio and SMTP are mocked in these tests.
These tests verify our notification logic and failure isolation,
not the external providers themselves.

Notification lifecycle tested:

1. Booking confirmation
   - SMS
   - Email

2. Booking modification
   - SMS
   - Email

3. Booking cancellation
   - SMS
   - Email
"""

from unittest.mock import patch, MagicMock


# ============================================================
# TEST HELPERS
# ============================================================

def configure_fake_twilio(config_module):
    """
    Configure fake Twilio credentials for tests.

    These are NOT real credentials.
    """

    config_module.settings.TWILIO_ACCOUNT_SID = (
        "ACfaketest"
    )

    config_module.settings.TWILIO_AUTH_TOKEN = (
        "faketoken"
    )

    config_module.settings.TWILIO_SMS_FROM_NUMBER = (
        "+15005550006"
    )


def configure_fake_email(monkeypatch):
    """
    Configure fake SMTP credentials for tests.

    SMTP itself is mocked, so no real email is sent.
    """

    monkeypatch.setenv(
        "SMTP_HOST",
        "smtp.gmail.com",
    )

    monkeypatch.setenv(
        "SMTP_PORT",
        "587",
    )

    monkeypatch.setenv(
        "SMTP_USERNAME",
        "test@example.com",
    )

    monkeypatch.setenv(
        "SMTP_PASSWORD",
        "fake-app-password",
    )

    monkeypatch.setenv(
        "SMTP_FROM_EMAIL",
        "test@example.com",
    )

    monkeypatch.setenv(
        "SMTP_USE_TLS",
        "true",
    )


# ============================================================
# BOOKING CONFIRMATION
# ============================================================

def test_booking_succeeds_when_notifications_not_configured(
    client,
    sample_room_ids,
):
    """
    conftest.py leaves TWILIO_* unset.

    Booking must still succeed cleanly.
    """

    res = client.post(
        "/bookings",
        json={
            "customer_name": "No Notify",
            "customer_phone": "9444400001",
            "room_id": sample_room_ids["Standard"],
            "check_in": "2027-09-01",
            "check_out": "2027-09-02",
            "adults": 1,
        },
    )

    assert res.status_code == 201


def test_booking_succeeds_even_if_sms_send_throws(
    client,
    sample_room_ids,
):
    """
    Simulates Twilio configured but the actual send()
    call raising.

    The booking API response must still be successful.
    """

    import app.config as config_module

    original_sid = (
        config_module.settings.TWILIO_ACCOUNT_SID
    )

    original_token = (
        config_module.settings.TWILIO_AUTH_TOKEN
    )

    original_from = (
        config_module.settings.TWILIO_SMS_FROM_NUMBER
    )

    try:

        configure_fake_twilio(
            config_module
        )

        with patch(
            "twilio.rest.Client"
        ) as MockClient:

            (
                MockClient
                .return_value
                .messages
                .create
                .side_effect
            ) = Exception(
                "Twilio down"
            )

            res = client.post(
                "/bookings",
                json={
                    "customer_name": "SMS Fail Test",
                    "customer_phone": "9444400002",
                    "room_id": sample_room_ids["Deluxe"],
                    "check_in": "2027-09-05",
                    "check_out": "2027-09-06",
                    "adults": 1,
                },
            )

        assert res.status_code == 201

    finally:

        config_module.settings.TWILIO_ACCOUNT_SID = (
            original_sid
        )

        config_module.settings.TWILIO_AUTH_TOKEN = (
            original_token
        )

        config_module.settings.TWILIO_SMS_FROM_NUMBER = (
            original_from
        )


def test_notification_service_sends_correct_message_content(
    db_session,
    sample_room_ids,
):
    """
    Verifies SMS message content and recipient directly
    against the notification service.

    Twilio is mocked.
    """

    import app.config as config_module

    from app.services.booking_service import (
        create_booking,
    )

    from app.services.notification_service import (
        send_booking_confirmation,
    )

    from datetime import date, timedelta

    original_sid = (
        config_module.settings.TWILIO_ACCOUNT_SID
    )

    original_token = (
        config_module.settings.TWILIO_AUTH_TOKEN
    )

    original_from = (
        config_module.settings.TWILIO_SMS_FROM_NUMBER
    )

    try:

        configure_fake_twilio(
            config_module
        )

        booking = create_booking(
            db=db_session,
            room_id=sample_room_ids["Suite"],
            customer_name="Direct Test",
            customer_phone="9444400003",
            customer_email=None,
            check_in=(
                date.today()
                + timedelta(days=10)
            ),
            check_out=(
                date.today()
                + timedelta(days=12)
            ),
            adults=2,
            children=0,
        )

        with patch(
            "twilio.rest.Client"
        ) as MockClient:

            mock_msg = MagicMock(
                sid="SMabc123"
            )

            (
                MockClient
                .return_value
                .messages
                .create
                .return_value
            ) = mock_msg

            result = send_booking_confirmation(
                db_session,
                booking,
            )

        assert result["sms"]["sent"] is True

        assert (
            result["sms"]["message_sid"]
            == "SMabc123"
        )

        call_kwargs = (
            MockClient
            .return_value
            .messages
            .create
            .call_args
            .kwargs
        )

        assert (
            call_kwargs["to"]
            == "9444400003"
        )

        assert (
            booking.booking_id
            in call_kwargs["body"]
        )

        assert (
            "Suite"
            in call_kwargs["body"]
        )

    finally:

        config_module.settings.TWILIO_ACCOUNT_SID = (
            original_sid
        )

        config_module.settings.TWILIO_AUTH_TOKEN = (
            original_token
        )

        config_module.settings.TWILIO_SMS_FROM_NUMBER = (
            original_from
        )


def test_notification_skipped_when_no_phone_on_file(
    db_session,
    sample_room_ids,
):
    """
    If the customer has no phone number,
    SMS should be skipped cleanly.
    """

    from app.services.notification_service import (
        send_booking_confirmation,
    )

    from app.services.booking_service import (
        create_booking,
    )

    from datetime import date, timedelta

    import app.config as config_module

    original_sid = (
        config_module.settings.TWILIO_ACCOUNT_SID
    )

    original_token = (
        config_module.settings.TWILIO_AUTH_TOKEN
    )

    original_from = (
        config_module.settings.TWILIO_SMS_FROM_NUMBER
    )

    try:

        configure_fake_twilio(
            config_module
        )

        booking = create_booking(
            db=db_session,
            room_id=sample_room_ids["Standard"],
            customer_name="No Phone somehow",
            customer_phone="9444400004",
            customer_email=None,
            check_in=(
                date.today()
                + timedelta(days=20)
            ),
            check_out=(
                date.today()
                + timedelta(days=21)
            ),
            adults=1,
            children=0,
        )

        booking.customer.phone = ""

        db_session.commit()

        result = send_booking_confirmation(
            db_session,
            booking,
        )

        assert (
            result["sms"]["sent"]
            is False
        )

        assert (
            result["sms"]["reason"]
            == "no_customer_phone"
        )

    finally:

        config_module.settings.TWILIO_ACCOUNT_SID = (
            original_sid
        )

        config_module.settings.TWILIO_AUTH_TOKEN = (
            original_token
        )

        config_module.settings.TWILIO_SMS_FROM_NUMBER = (
            original_from
        )


# ============================================================
# BOOKING CONFIRMATION EMAIL
# ============================================================

def test_booking_confirmation_email(
    db_session,
    sample_room_ids,
    monkeypatch,
):
    """
    Verifies booking confirmation email content.

    SMTP is mocked.
    No real email is sent.
    """

    import app.config as config_module

    from app.services.booking_service import (
        create_booking,
    )

    from app.services.notification_service import (
        send_booking_confirmation,
    )

    from datetime import date, timedelta

    booking = create_booking(
        db=db_session,
        room_id=sample_room_ids["Suite"],
        customer_name="Email Test",
        customer_phone="9444400010",
        customer_email="customer@example.com",
        check_in=(
            date.today()
            + timedelta(days=30)
        ),
        check_out=(
            date.today()
            + timedelta(days=32)
        ),
        adults=2,
        children=1,
    )

    original_sid = (
        config_module.settings.TWILIO_ACCOUNT_SID
    )

    original_token = (
        config_module.settings.TWILIO_AUTH_TOKEN
    )

    original_from = (
        config_module.settings.TWILIO_SMS_FROM_NUMBER
    )

    try:

        # Disable SMS for this email-focused test.

        config_module.settings.TWILIO_ACCOUNT_SID = ""

        config_module.settings.TWILIO_AUTH_TOKEN = ""

        config_module.settings.TWILIO_SMS_FROM_NUMBER = ""

        configure_fake_email(
            monkeypatch
        )

        with patch(
            "app.services.notification_service.smtplib.SMTP"
        ) as MockSMTP:

            mock_server = (
                MockSMTP
                .return_value
                .__enter__
                .return_value
            )

            result = send_booking_confirmation(
                db_session,
                booking,
            )

        assert (
            result["email"]["sent"]
            is True
        )

        assert (
            result["email"]["recipient"]
            == "customer@example.com"
        )

        mock_server.login.assert_called_once()

        mock_server.send_message.assert_called_once()

        email_message = (
            mock_server
            .send_message
            .call_args
            .args[0]
        )

        assert (
            "ABC Hotel"
            in email_message["Subject"]
        )

        assert (
            booking.booking_id
            in email_message.get_content()
        )

        assert (
            "Suite"
            in email_message.get_content()
        )

        assert (
            "Email Test"
            in email_message.get_content()
        )

    finally:

        config_module.settings.TWILIO_ACCOUNT_SID = (
            original_sid
        )

        config_module.settings.TWILIO_AUTH_TOKEN = (
            original_token
        )

        config_module.settings.TWILIO_SMS_FROM_NUMBER = (
            original_from
        )


# ============================================================
# BOOKING MODIFICATION - SMS
# ============================================================

def test_booking_modification_notification(
    db_session,
    sample_room_ids,
):
    """
    Verifies booking modification SMS notification.

    Twilio is mocked.
    """

    import app.config as config_module

    from app.services.booking_service import (
        create_booking,
        modify_booking,
    )

    from app.services.notification_service import (
        send_booking_modification,
    )

    from datetime import date, timedelta

    original_sid = (
        config_module.settings.TWILIO_ACCOUNT_SID
    )

    original_token = (
        config_module.settings.TWILIO_AUTH_TOKEN
    )

    original_from = (
        config_module.settings.TWILIO_SMS_FROM_NUMBER
    )

    try:

        configure_fake_twilio(
            config_module
        )

        booking = create_booking(
            db=db_session,
            room_id=sample_room_ids["Standard"],
            customer_name="Modify Test",
            customer_phone="9444400020",
            customer_email=None,
            check_in=(
                date.today()
                + timedelta(days=40)
            ),
            check_out=(
                date.today()
                + timedelta(days=42)
            ),
            adults=1,
            children=0,
        )

        modified_booking = modify_booking(
            db=db_session,
            booking_id=booking.booking_id,
            new_check_in=(
                date.today()
                + timedelta(days=41)
            ),
            new_check_out=(
                date.today()
                + timedelta(days=43)
            ),
        )

        with patch(
            "twilio.rest.Client"
        ) as MockClient:

            mock_msg = MagicMock(
                sid="SMmodify123"
            )

            (
                MockClient
                .return_value
                .messages
                .create
                .return_value
            ) = mock_msg

            result = send_booking_modification(
                db_session,
                modified_booking,
            )

        assert (
            result["sms"]["sent"]
            is True
        )

        assert (
            result["sms"]["message_sid"]
            == "SMmodify123"
        )

        call_kwargs = (
            MockClient
            .return_value
            .messages
            .create
            .call_args
            .kwargs
        )

        assert (
            call_kwargs["to"]
            == "9444400020"
        )

        assert (
            booking.booking_id
            in call_kwargs["body"]
        )

        assert (
            "Modified"
            in call_kwargs["body"]
        )

        assert (
            result["email"]["sent"]
            is False
        )

        assert (
            result["email"]["reason"]
            == "no_customer_email"
        )

    finally:

        config_module.settings.TWILIO_ACCOUNT_SID = (
            original_sid
        )

        config_module.settings.TWILIO_AUTH_TOKEN = (
            original_token
        )

        config_module.settings.TWILIO_SMS_FROM_NUMBER = (
            original_from
        )


# ============================================================
# BOOKING CANCELLATION - SMS
# ============================================================

def test_booking_cancellation_notification(
    db_session,
    sample_room_ids,
):
    """
    Verifies booking cancellation SMS notification.

    Twilio is mocked.
    """

    import app.config as config_module

    from app.services.booking_service import (
        create_booking,
    )

    from app.services.notification_service import (
        send_booking_cancellation,
    )

    from datetime import date, timedelta

    original_sid = (
        config_module.settings.TWILIO_ACCOUNT_SID
    )

    original_token = (
        config_module.settings.TWILIO_AUTH_TOKEN
    )

    original_from = (
        config_module.settings.TWILIO_SMS_FROM_NUMBER
    )

    try:

        configure_fake_twilio(
            config_module
        )

        booking = create_booking(
            db=db_session,
            room_id=sample_room_ids["Deluxe"],
            customer_name="Cancel Test",
            customer_phone="9444400030",
            customer_email=None,
            check_in=(
                date.today()
                + timedelta(days=50)
            ),
            check_out=(
                date.today()
                + timedelta(days=52)
            ),
            adults=2,
            children=0,
        )

        booking.booking_status = "cancelled"

        db_session.commit()

        with patch(
            "twilio.rest.Client"
        ) as MockClient:

            mock_msg = MagicMock(
                sid="SMcancel123"
            )

            (
                MockClient
                .return_value
                .messages
                .create
                .return_value
            ) = mock_msg

            result = send_booking_cancellation(
                db_session,
                booking,
            )

        assert (
            result["sms"]["sent"]
            is True
        )

        assert (
            result["sms"]["message_sid"]
            == "SMcancel123"
        )

        call_kwargs = (
            MockClient
            .return_value
            .messages
            .create
            .call_args
            .kwargs
        )

        assert (
            call_kwargs["to"]
            == "9444400030"
        )

        assert (
            booking.booking_id
            in call_kwargs["body"]
        )

        assert (
            "Cancelled"
            in call_kwargs["body"]
        )

        assert (
            result["email"]["sent"]
            is False
        )

        assert (
            result["email"]["reason"]
            == "no_customer_email"
        )

    finally:

        config_module.settings.TWILIO_ACCOUNT_SID = (
            original_sid
        )

        config_module.settings.TWILIO_AUTH_TOKEN = (
            original_token
        )

        config_module.settings.TWILIO_SMS_FROM_NUMBER = (
            original_from
        )


# ============================================================
# BOOKING CANCELLATION - EMAIL
# ============================================================

def test_cancellation_email(
    db_session,
    sample_room_ids,
    monkeypatch,
):
    """
    Verifies booking cancellation email content.

    SMTP is mocked.
    """

    from app.services.booking_service import (
        create_booking,
    )

    from app.services.notification_service import (
        send_booking_cancellation,
    )

    from datetime import date, timedelta

    booking = create_booking(
        db=db_session,
        room_id=sample_room_ids["Suite"],
        customer_name="Cancel Email Test",
        customer_phone="9444400040",
        customer_email="cancel@example.com",
        check_in=(
            date.today()
            + timedelta(days=60)
        ),
        check_out=(
            date.today()
            + timedelta(days=62)
        ),
        adults=2,
        children=0,
    )

    booking.booking_status = "cancelled"

    db_session.commit()

    configure_fake_email(
        monkeypatch
    )

    with patch(
        "app.services.notification_service.smtplib.SMTP"
    ) as MockSMTP:

        mock_server = (
            MockSMTP
            .return_value
            .__enter__
            .return_value
        )

        result = send_booking_cancellation(
            db_session,
            booking,
        )

    assert (
        result["email"]["sent"]
        is True
    )

    assert (
        result["email"]["recipient"]
        == "cancel@example.com"
    )

    mock_server.login.assert_called_once()

    mock_server.send_message.assert_called_once()

    email_message = (
        mock_server
        .send_message
        .call_args
        .args[0]
    )

    assert (
        "Cancelled"
        in email_message["Subject"]
    )

    assert (
        booking.booking_id
        in email_message.get_content()
    )

    assert (
        "Cancel Email Test"
        in email_message.get_content()
    )

    assert (
        "cancelled"
        in email_message.get_content().lower()
    )


# ============================================================
# BOOKING MODIFICATION - EMAIL
# ============================================================

def test_modification_email(
    db_session,
    sample_room_ids,
    monkeypatch,
):
    """
    Verifies booking modification email content.

    SMTP is mocked.
    """

    from app.services.booking_service import (
        create_booking,
    )

    from app.services.notification_service import (
        send_booking_modification,
    )

    from datetime import date, timedelta

    booking = create_booking(
        db=db_session,
        room_id=sample_room_ids["Premium"],
        customer_name="Modify Email Test",
        customer_phone="9444400050",
        customer_email="modify@example.com",
        check_in=(
            date.today()
            + timedelta(days=70)
        ),
        check_out=(
            date.today()
            + timedelta(days=72)
        ),
        adults=2,
        children=1,
    )

    configure_fake_email(
        monkeypatch
    )

    with patch(
        "app.services.notification_service.smtplib.SMTP"
    ) as MockSMTP:

        mock_server = (
            MockSMTP
            .return_value
            .__enter__
            .return_value
        )

        result = send_booking_modification(
            db_session,
            booking,
        )

    assert (
        result["email"]["sent"]
        is True
    )

    assert (
        result["email"]["recipient"]
        == "modify@example.com"
    )

    mock_server.login.assert_called_once()

    mock_server.send_message.assert_called_once()

    email_message = (
        mock_server
        .send_message
        .call_args
        .args[0]
    )

    assert (
        "Modified"
        in email_message["Subject"]
    )

    assert (
        booking.booking_id
        in email_message.get_content()
    )

    assert (
        "Modify Email Test"
        in email_message.get_content()
    )

    assert (
        "Premium"
        in email_message.get_content()
    )