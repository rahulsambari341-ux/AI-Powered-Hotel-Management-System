"""
Booking lifecycle notifications.

Supports:
- SMS via Twilio
- Email via SMTP

Notifications are best-effort only.

IMPORTANT:
A booking, modification, or cancellation must NEVER fail or
roll back because SMS or email notification failed.

Notification lifecycle:

1. Booking confirmation
   -> SMS + Email

2. Booking modification
   -> SMS + Email

3. Booking cancellation
   -> SMS + Email

SMS configuration:
    TWILIO_ACCOUNT_SID
    TWILIO_AUTH_TOKEN
    TWILIO_SMS_FROM_NUMBER

Email configuration:
    SMTP_HOST
    SMTP_PORT
    SMTP_USERNAME
    SMTP_PASSWORD
    SMTP_FROM_EMAIL
    SMTP_USE_TLS

Example Gmail configuration:

    SMTP_HOST=smtp.gmail.com
    SMTP_PORT=587
    SMTP_USERNAME=your-email@gmail.com
    SMTP_PASSWORD=your-app-password
    SMTP_FROM_EMAIL=your-email@gmail.com
    SMTP_USE_TLS=true
"""

import logging
import os
import smtplib

from email.message import EmailMessage

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Booking, Customer, Room


logger = logging.getLogger("notifications")


# ============================================================
# CONFIG HELPERS
# ============================================================

def _get_env(name: str, default=None):
    """
    Safely read an environment variable.

    Email configuration is read directly from environment
    variables so no new settings model is required just to
    support SMTP.
    """

    value = os.getenv(name)

    if value is None:
        return default

    return value.strip()


def _smtp_use_tls() -> bool:
    value = _get_env(
        "SMTP_USE_TLS",
        "true",
    )

    return str(value).lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _smtp_port() -> int:
    value = _get_env(
        "SMTP_PORT",
        "587",
    )

    try:
        return int(value)
    except (TypeError, ValueError):
        return 587


# ============================================================
# CUSTOMER / ROOM HELPERS
# ============================================================

def _get_customer(
    db: Session,
    booking: Booking,
):
    return (
        db.query(Customer)
        .filter(
            Customer.id == booking.customer_id
        )
        .first()
    )


def _get_room(
    db: Session,
    booking: Booking,
):
    return (
        db.query(Room)
        .filter(
            Room.id == booking.room_id
        )
        .first()
    )


# ============================================================
# BOOKING MESSAGE
# ============================================================

def _format_confirmation_message(
    booking: Booking,
    room: Room,
) -> str:
    """
    SMS confirmation message.
    """

    return (
        "ABC Hotel Booking Confirmed\n\n"
        f"Booking ID: {booking.booking_id}\n"
        f"Room: {room.room_number} ({room.room_type})\n"
        f"Check-in: {booking.check_in.strftime('%d %b %Y')}\n"
        f"Check-out: {booking.check_out.strftime('%d %b %Y')}\n"
        f"Guests: {booking.adults + booking.children}\n"
        f"Total: ₹{booking.total_amount:,.0f}"
    )


def _format_modification_message(
    booking: Booking,
    room: Room,
) -> str:
    """
    SMS modification message.
    """

    return (
        "ABC Hotel Booking Modified\n\n"
        f"Booking ID: {booking.booking_id}\n"
        f"Room: {room.room_number} ({room.room_type})\n"
        f"Check-in: {booking.check_in.strftime('%d %b %Y')}\n"
        f"Check-out: {booking.check_out.strftime('%d %b %Y')}\n"
        f"Guests: {booking.adults + booking.children}\n"
        f"Total: ₹{booking.total_amount:,.0f}"
    )


def _format_cancellation_message(
    booking: Booking,
    room: Room,
) -> str:
    """
    SMS cancellation message.
    """

    return (
        "ABC Hotel Booking Cancelled\n\n"
        f"Booking ID: {booking.booking_id}\n"
        f"Room: {room.room_number} ({room.room_type})\n"
        f"Check-in: {booking.check_in.strftime('%d %b %Y')}\n"
        f"Check-out: {booking.check_out.strftime('%d %b %Y')}\n"
        f"Total: ₹{booking.total_amount:,.0f}\n\n"
        "Your reservation has been cancelled successfully."
    )


# ============================================================
# EMAIL CONTENT
# ============================================================

def _format_confirmation_email(
    booking: Booking,
    room: Room,
    customer: Customer,
) -> tuple[str, str]:
    """
    Returns:

        subject
        body
    """

    subject = (
        f"ABC Hotel - Booking Confirmed "
        f"({booking.booking_id})"
    )

    body = (
        f"Dear {customer.name},\n\n"
        "Your ABC Hotel booking has been confirmed.\n\n"
        "BOOKING DETAILS\n"
        "-------------------------\n"
        f"Customer: {customer.name}\n"
        f"Booking ID: {booking.booking_id}\n"
        f"Room Number: {room.room_number}\n"
        f"Room Type: {room.room_type}\n"
        f"Check-in: {booking.check_in.strftime('%d %B %Y')}\n"
        f"Check-out: {booking.check_out.strftime('%d %B %Y')}\n"
        f"Adults: {booking.adults}\n"
        f"Children: {booking.children}\n"
        f"Total Amount: ₹{booking.total_amount:,.2f}\n\n"
        "Thank you for choosing ABC Hotel.\n\n"
        "Regards,\n"
        "ABC Hotel"
    )

    return subject, body


def _format_modification_email(
    booking: Booking,
    room: Room,
    customer: Customer,
) -> tuple[str, str]:
    """
    Returns modification email subject and body.
    """

    subject = (
        f"ABC Hotel - Booking Modified "
        f"({booking.booking_id})"
    )

    body = (
        f"Dear {customer.name},\n\n"
        "Your ABC Hotel booking has been successfully modified.\n\n"
        "UPDATED BOOKING DETAILS\n"
        "-------------------------\n"
        f"Customer: {customer.name}\n"
        f"Booking ID: {booking.booking_id}\n"
        f"Room Number: {room.room_number}\n"
        f"Room Type: {room.room_type}\n"
        f"Check-in: {booking.check_in.strftime('%d %B %Y')}\n"
        f"Check-out: {booking.check_out.strftime('%d %B %Y')}\n"
        f"Adults: {booking.adults}\n"
        f"Children: {booking.children}\n"
        f"Total Amount: ₹{booking.total_amount:,.2f}\n\n"
        "Your reservation details have been updated successfully.\n\n"
        "Regards,\n"
        "ABC Hotel"
    )

    return subject, body


def _format_cancellation_email(
    booking: Booking,
    room: Room,
    customer: Customer,
) -> tuple[str, str]:
    """
    Returns cancellation email subject and body.
    """

    subject = (
        f"ABC Hotel - Booking Cancelled "
        f"({booking.booking_id})"
    )

    body = (
        f"Dear {customer.name},\n\n"
        "Your ABC Hotel reservation has been successfully cancelled.\n\n"
        "CANCELLED BOOKING DETAILS\n"
        "-------------------------\n"
        f"Customer: {customer.name}\n"
        f"Booking ID: {booking.booking_id}\n"
        f"Room Number: {room.room_number}\n"
        f"Room Type: {room.room_type}\n"
        f"Check-in: {booking.check_in.strftime('%d %B %Y')}\n"
        f"Check-out: {booking.check_out.strftime('%d %B %Y')}\n"
        f"Adults: {booking.adults}\n"
        f"Children: {booking.children}\n"
        f"Total Amount: ₹{booking.total_amount:,.2f}\n"
        f"Status: {booking.booking_status}\n\n"
        "Your reservation has been cancelled successfully.\n\n"
        "Regards,\n"
        "ABC Hotel"
    )

    return subject, body


# ============================================================
# SMS
# ============================================================

def _send_sms(
    phone: str,
    body: str,
) -> dict:
    """
    Sends SMS through Twilio.

    Never raises.
    """

    try:

        if (
            not settings.TWILIO_ACCOUNT_SID
            or not settings.TWILIO_AUTH_TOKEN
        ):

            return {
                "sent": False,
                "reason": "twilio_not_configured",
            }

        if not settings.TWILIO_SMS_FROM_NUMBER:

            return {
                "sent": False,
                "reason": "sms_from_number_not_configured",
            }

        from twilio.rest import Client

        client = Client(
            settings.TWILIO_ACCOUNT_SID,
            settings.TWILIO_AUTH_TOKEN,
        )

        message = client.messages.create(
            to=phone,
            from_=settings.TWILIO_SMS_FROM_NUMBER,
            body=body,
        )

        return {
            "sent": True,
            "channel": "sms",
            "message_sid": message.sid,
        }

    except Exception as e:

        logger.warning(
            "SMS send failed: %s",
            e,
        )

        return {
            "sent": False,
            "reason": "send_failed",
            "detail": str(e),
        }


# ============================================================
# EMAIL
# ============================================================

def _send_email(
    recipient: str,
    subject: str,
    body: str,
) -> dict:
    """
    Sends email through SMTP.

    Uses Python's standard library.

    Never raises.
    """

    smtp_host = _get_env(
        "SMTP_HOST"
    )

    smtp_username = _get_env(
        "SMTP_USERNAME"
    )

    smtp_password = _get_env(
        "SMTP_PASSWORD"
    )

    smtp_from_email = _get_env(
        "SMTP_FROM_EMAIL"
    )

    if not smtp_host:
        return {
            "sent": False,
            "reason": "smtp_host_not_configured",
        }

    if not smtp_username:
        return {
            "sent": False,
            "reason": "smtp_username_not_configured",
        }

    if not smtp_password:
        return {
            "sent": False,
            "reason": "smtp_password_not_configured",
        }

    if not smtp_from_email:
        return {
            "sent": False,
            "reason": "smtp_from_email_not_configured",
        }

    if not recipient:
        return {
            "sent": False,
            "reason": "no_customer_email",
        }

    try:

        message = EmailMessage()

        message["Subject"] = subject
        message["From"] = smtp_from_email
        message["To"] = recipient

        message.set_content(body)

        with smtplib.SMTP(
            smtp_host,
            _smtp_port(),
            timeout=20,
        ) as server:

            if _smtp_use_tls():

                server.starttls()

            server.login(
                smtp_username,
                smtp_password,
            )

            server.send_message(
                message
            )

        return {
            "sent": True,
            "channel": "email",
            "recipient": recipient,
        }

    except Exception as e:

        logger.warning(
            "Email send failed: %s",
            e,
        )

        return {
            "sent": False,
            "reason": "send_failed",
            "detail": str(e),
        }


# ============================================================
# BOOKING CONFIRMATION
# ============================================================

def send_booking_confirmation(
    db: Session,
    booking: Booking,
) -> dict:
    """
    Sends booking confirmation through SMS and email.

    Never raises.
    """

    result = {
        "booking_id": booking.booking_id,
        "sms": None,
        "email": None,
    }

    try:

        customer = _get_customer(
            db,
            booking,
        )

        if customer is None:

            logger.warning(
                "Customer not found for booking %s",
                booking.booking_id,
            )

            result["sms"] = {
                "sent": False,
                "reason": "customer_not_found",
            }

            result["email"] = {
                "sent": False,
                "reason": "customer_not_found",
            }

            return result

        room = _get_room(
            db,
            booking,
        )

        if room is None:

            logger.warning(
                "Room not found for booking %s",
                booking.booking_id,
            )

            result["sms"] = {
                "sent": False,
                "reason": "room_not_found",
            }

            result["email"] = {
                "sent": False,
                "reason": "room_not_found",
            }

            return result

        # SMS

        if customer.phone:

            result["sms"] = _send_sms(
                customer.phone,
                _format_confirmation_message(
                    booking,
                    room,
                ),
            )

        else:

            result["sms"] = {
                "sent": False,
                "reason": "no_customer_phone",
            }

        # Email

        if customer.email:

            subject, body = (
                _format_confirmation_email(
                    booking,
                    room,
                    customer,
                )
            )

            result["email"] = _send_email(
                customer.email,
                subject,
                body,
            )

        else:

            result["email"] = {
                "sent": False,
                "reason": "no_customer_email",
            }

        logger.info(
            "Booking confirmation notifications processed for %s",
            booking.booking_id,
        )

        return result

    except Exception as e:

        logger.exception(
            "Booking confirmation notification processing failed "
            "for %s",
            booking.booking_id,
        )

        return {
            "booking_id": booking.booking_id,
            "sms": result["sms"],
            "email": result["email"],
            "error": str(e),
        }


# ============================================================
# BOOKING MODIFICATION
# ============================================================

def send_booking_modification(
    db: Session,
    booking: Booking,
) -> dict:
    """
    Sends booking modification notification through SMS and email.

    Never raises.
    """

    result = {
        "booking_id": booking.booking_id,
        "sms": None,
        "email": None,
    }

    try:

        customer = _get_customer(
            db,
            booking,
        )

        if customer is None:

            result["sms"] = {
                "sent": False,
                "reason": "customer_not_found",
            }

            result["email"] = {
                "sent": False,
                "reason": "customer_not_found",
            }

            return result

        room = _get_room(
            db,
            booking,
        )

        if room is None:

            result["sms"] = {
                "sent": False,
                "reason": "room_not_found",
            }

            result["email"] = {
                "sent": False,
                "reason": "room_not_found",
            }

            return result

        # SMS

        if customer.phone:

            result["sms"] = _send_sms(
                customer.phone,
                _format_modification_message(
                    booking,
                    room,
                ),
            )

        else:

            result["sms"] = {
                "sent": False,
                "reason": "no_customer_phone",
            }

        # Email

        if customer.email:

            subject, body = (
                _format_modification_email(
                    booking,
                    room,
                    customer,
                )
            )

            result["email"] = _send_email(
                customer.email,
                subject,
                body,
            )

        else:

            result["email"] = {
                "sent": False,
                "reason": "no_customer_email",
            }

        logger.info(
            "Booking modification notifications processed for %s",
            booking.booking_id,
        )

        return result

    except Exception as e:

        logger.exception(
            "Booking modification notification processing failed "
            "for %s",
            booking.booking_id,
        )

        return {
            "booking_id": booking.booking_id,
            "sms": result["sms"],
            "email": result["email"],
            "error": str(e),
        }


# ============================================================
# BOOKING CANCELLATION
# ============================================================

def send_booking_cancellation(
    db: Session,
    booking: Booking,
) -> dict:
    """
    Sends booking cancellation notification through SMS and email.

    Never raises.
    """

    result = {
        "booking_id": booking.booking_id,
        "sms": None,
        "email": None,
    }

    try:

        customer = _get_customer(
            db,
            booking,
        )

        if customer is None:

            result["sms"] = {
                "sent": False,
                "reason": "customer_not_found",
            }

            result["email"] = {
                "sent": False,
                "reason": "customer_not_found",
            }

            return result

        room = _get_room(
            db,
            booking,
        )

        if room is None:

            result["sms"] = {
                "sent": False,
                "reason": "room_not_found",
            }

            result["email"] = {
                "sent": False,
                "reason": "room_not_found",
            }

            return result

        # SMS

        if customer.phone:

            result["sms"] = _send_sms(
                customer.phone,
                _format_cancellation_message(
                    booking,
                    room,
                ),
            )

        else:

            result["sms"] = {
                "sent": False,
                "reason": "no_customer_phone",
            }

        # Email

        if customer.email:

            subject, body = (
                _format_cancellation_email(
                    booking,
                    room,
                    customer,
                )
            )

            result["email"] = _send_email(
                customer.email,
                subject,
                body,
            )

        else:

            result["email"] = {
                "sent": False,
                "reason": "no_customer_email",
            }

        logger.info(
            "Booking cancellation notifications processed for %s",
            booking.booking_id,
        )

        return result

    except Exception as e:

        logger.exception(
            "Booking cancellation notification processing failed "
            "for %s",
            booking.booking_id,
        )

        return {
            "booking_id": booking.booking_id,
            "sms": result["sms"],
            "email": result["email"],
            "error": str(e),
        }