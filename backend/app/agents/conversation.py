"""
Deterministic conversation controller for the AI Hotel Booking Agent.
Hardened: Prevents LLM fake confirmation text, enforces strict database transaction gates,
and ensures proper modification persistence and admin sync.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from typing import Any

from app.agents.llm_client import call_llm
from app.agents.tools import TOOL_FUNCTIONS, TOOL_SCHEMAS
from app.config import settings
from app.storage import delete as storage_delete
from app.storage import get_json, set_json


SUPPORTED_LANGUAGES = {
    "en": "English",
    "hi": "Hindi",
    "te": "Telugu",
    "ta": "Tamil",
}
DEFAULT_LANGUAGE = "en"

_SESSION_PREFIX = "conversation:"
_MAX_HISTORY = 40
_MAX_TOOL_HOPS = 8

_ROOM_TYPES = {
    "standard": "Standard",
    "deluxe": "Deluxe",
    "premium": "Premium",
    "suite": "Suite",
}
_BASE_PROMPT = """
You are Chitti, the AI receptionist and virtual assistant for ABC Hotel. 
MANDATORY IDENTITY RULE: If any customer asks your name, who you are, or what you are called, you MUST always reply: "I am Chitti, the AI receptionist of ABC Hotel." Never say you are just a generic virtual assistant.
-->> CURRENT EXACT DATETIME: Today is {{current_date}} {{current_month}} (Year: {{current_year}}) {{current_time}}. <<--

You help customers:
- check room availability
- make a new reservation
- cancel an existing reservation
- modify an existing reservation
- Modification Details: When a customer asks to modify a booking (like changing room, dates, or contact info), ensure the specific change is explicitly captured and passed to the modification tool before asking for confirmation.
- answer factual hotel questions

CRITICAL DATE & YEAR VALIDATION RULE:
- Always verify if the dates or years provided by the customer are in the future relative to the current year ({current_year}).
- If a customer specifies a past year or date (e.g., any year in the past), politely correct them: "That date is in the past. Our hotel bookings are open for future dates like {current_year} or later. Could you please provide valid future dates?"

Never invent availability, prices, booking IDs, room numbers, or policies.
Never invent hotel names (the only hotel name is ABC Hotel).
Never invent room types or features outside of: Standard, Deluxe, Premium, and Suite.
Use the supplied tools for factual information.

IMPORTANT FLOW RULES:
1. Information already present in controller state is authoritative.
2. Never ask again for information already known.
3. A complete date range must be validated before availability is checked.
4. Never guess a missing year.
5. Never silently change a customer-provided year.
6. When repeating or displaying booking dates to the customer, ALWAYS use the exact structured ISO format from controller state:
   Check-in: YYYY-MM-DD
   Check-out: YYYY-MM-DD
7. Never convert controller dates into natural-language formats such as "October 10th, 2029".
8. The customer's spoken date format may be natural, but the displayed date must always be YYYY-MM-DD.
9. Customers choose human-facing room numbers, not internal room IDs.
10. A new booking requires an actual available room.
11. A booking is created only after explicit customer confirmation.
12. Cancellation requires explicit customer confirmation.
13. Modification requires explicit customer confirmation.
14. Never turn a modification into a new booking.
15. Never expose internal database IDs or tool JSON.
16. Reply naturally in the customer's language.
17. If a tool reports an error, explain it naturally.

CRITICAL RULE: The LLM MUST NEVER claim that a booking is confirmed, created, or successful unless the backend database has successfully generated a real booking ID (BKxxxx).
"""

_TRANSACTIONAL_TOOL_NAMES = {
    "create_booking_tool",
    "cancel_booking_tool",
    "modify_booking_tool",
}

SAFE_TOOL_SCHEMAS = [
    s for s in TOOL_SCHEMAS
    if s.get("function", {}).get("name") not in _TRANSACTIONAL_TOOL_NAMES
]


def _new_booking_state() -> dict[str, Any]:
    return {
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


def _new_session() -> dict[str, Any]:
    return {
        "messages": [],
        "language": "en",
        "flow_stage": "idle",
        "pending_action": None,
        "last_booking_id": None,
        "booking_state": _new_booking_state(),
    }


def _session_key(session_id: str) -> str:
    return f"{_SESSION_PREFIX}{session_id}"


def _load_session(session_id: str) -> dict[str, Any]:
    raw = get_json(_session_key(session_id))
    if not isinstance(raw, dict):
        return _new_session()

    session = _new_session()
    session.update(raw)

    state = _new_booking_state()
    stored_state = raw.get("booking_state")
    if isinstance(stored_state, dict):
        state.update(stored_state)

    if not isinstance(state.get("modification"), dict):
        state["modification"] = {}
    if not isinstance(state.get("available_rooms"), list):
        state["available_rooms"] = []
    if not isinstance(session.get("messages"), list):
        session["messages"] = []

    session["booking_state"] = state
    return session


def _save_session(session_id: str, session: dict[str, Any]) -> None:
    messages = session.get("messages", [])
    if isinstance(messages, list) and len(messages) > _MAX_HISTORY:
        session["messages"] = messages[-_MAX_HISTORY:]

    set_json(
        _session_key(session_id),
        session,
        ttl_seconds=settings.SESSION_TTL_SECONDS,
    )


def reset_session(session_id: str) -> None:
    storage_delete(_session_key(session_id))


def get_or_create_session(session_id: str) -> list[dict]:
    return _load_session(session_id)["messages"]


def _clean(text: str) -> str:
    return " ".join(str(text).strip().split())


def _room_type(text: str) -> str | None:
    lowered = text.lower()
    for key, value in _ROOM_TYPES.items():
        if re.search(rf"\b{re.escape(key)}\b", lowered):
            return value
    return None


def _booking_id(text: str) -> str | None:
    match = re.search(r"\bBK\s*[-#]?\s*(\d{4,})\b", text, re.I)
    return f"BK{match.group(1)}" if match else None


def _room_number(text: str) -> str | None:
    patterns = (
        r"\broom\s+(?:number\s+|no\.?\s+|#\s*)?(\d{2,5})\b",
        r"\broom\s*#\s*(\d{2,5})\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return match.group(1)
    standalone = re.search(r"\b(\d{3})\b", text)
    if standalone and not re.search(r"\b(adult|guest|child|people|phone|date)\b", text, re.I):
        return standalone.group(1)
    return None


def _guest_counts(text: str) -> tuple[int | None, int | None]:
    lowered = text.lower()
    adult_match = re.search(r"\b(\d+)\s*adults?\b", lowered)
    child_match = re.search(r"\b(\d+)\s*(?:children|child|kids?)\b", lowered)

    adults = int(adult_match.group(1)) if adult_match else None
    children = int(child_match.group(1)) if child_match else None

    if adults is None:
        people = re.search(r"\b(\d+)\s*(?:people|guests|persons|audlts|adults)\b", lowered)
        if people:
            adults = int(people.group(1))

    return adults, children


def _parse_month_date(raw: str) -> str | None:
    cleaned = re.sub(r"(\d{1,2})(st|nd|rd|th)", r"\1", raw, flags=re.I)
    cleaned = cleaned.replace(",", " ").strip()

    formats = (
        "%B %d %Y",
        "%b %d %Y",
        "%d %B %Y",
        "%d %b %Y",
    )

    for fmt in formats:
        try:
            parsed = datetime.strptime(cleaned, fmt).date()
            today = date.today()
            if parsed < today:
                return None
            return parsed.isoformat()
        except ValueError:
            continue

    return None

def _extract_dates(text: str) -> tuple[str | None, str | None]:
    """
    Extract exactly two booking dates.

    Supported:
        2027-01-01
        January 1st, 2027
        1 January 2027
        01/01/2027
        01-01-2027

    Important:
        The year is never guessed.
        Past dates and impossible calendar dates are rejected.
    """

    # --------------------------------------------------------
    # ISO dates
    # --------------------------------------------------------

    iso_matches = re.findall(
        r"\b\d{4}-\d{1,2}-\d{1,2}\b",
        text,
    )

    if len(iso_matches) >= 2:
        parsed = []

        for value in iso_matches[:2]:
            try:
                parsed_date = date.fromisoformat(value)
                today = date.today()
                if parsed_date < today:
                    return None, None
                parsed.append(parsed_date.isoformat())
            except ValueError:
                return None, None

        return parsed[0], parsed[1]

    # --------------------------------------------------------
    # Month-name dates
    # --------------------------------------------------------

    month = (
        r"(?:January|February|March|April|May|June|July|August|"
        r"September|October|November|December|"
        r"Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)"
    )

    month_pattern = (
        rf"\b{month}\s+"
        r"\d{1,2}"
        r"(?:st|nd|rd|th)?"
        r"[,]?\s+"
        r"\d{4}\b"
    )

    month_matches = re.findall(
        month_pattern,
        text,
        re.I,
    )

    if len(month_matches) >= 2:
        first = _parse_month_date(month_matches[0])
        second = _parse_month_date(month_matches[1])

        if first and second:
            return first, second

    # --------------------------------------------------------
    # Numeric dates (MM/DD/YYYY or DD/MM/YYYY)
    # --------------------------------------------------------

    numeric = re.findall(
        r"\b\d{1,2}[/-]\d{1,2}[/-]\d{4}\b",
        text,
    )

    if len(numeric) >= 2:
        parsed = []
        today = date.today()

        for value in numeric[:2]:
            a, b, year = [
                int(x)
                for x in re.split(r"[/-]", value)
            ]

            candidates = (
                (year, b, a),  # DD/MM/YYYY
                (year, a, b),  # MM/DD/YYYY
            )

            valid_date = None

            for y, month_value, day_value in candidates:
                try:
                    candidate_date = date(y, month_value, day_value)
                    if candidate_date < today:
                        continue
                    valid_date = candidate_date.isoformat()
                    break
                except ValueError:
                    continue

            if valid_date is None:
                return None, None

            parsed.append(valid_date)

        return parsed[0], parsed[1]

    return None, None

def _validate_date_range(
    check_in: str | None,
    check_out: str | None,
) -> tuple[bool, str | None]:
    """
    Controller-level date safety check.

    Does not replace validate_booking_dates tool.
    It prevents obviously invalid dates from entering
    the booking state.
    """

    if not check_in or not check_out:
        return False, "Both check-in and check-out dates are required."

    try:
        check_in_date = date.fromisoformat(check_in)
        check_out_date = date.fromisoformat(check_out)
    except ValueError:
        return False, "The provided booking dates are invalid."

    today = date.today()

    if check_in_date < today:
        return False, "The check-in date is in the past."

    if check_out_date <= check_in_date:
        return False, "Check-out must be after check-in."

    return True, None

def _normalize_phone_number(raw_phone: str) -> str | None:
    """
    Normalize and validate an Indian mobile number.

    Accepted:
        9098909890
        +91 9098909890
        +91-9098909890
        91 9098909890

    Returns exactly 10 digits or None.
    """

    if not raw_phone:
        return None

    digits = re.sub(r"\D", "", raw_phone)

    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]

    if len(digits) != 10:
        return None

    if digits[0] not in "6789":
        return None

    return digits


def _customer_details(text: str) -> dict[str, str | None]:
    result: dict[str, str | None] = {
        "customer_name": None,
        "customer_phone": None,
        "customer_email": None,
    }

    # --------------------------------------------------------
    # Phone number
    # --------------------------------------------------------

    phone_patterns = (
        r"(?<!\d)(?:\+?91[\s-]?)?[6-9](?:[\s-]?\d){9}(?!\d)",
        r"(?<!\d)91[\s-]?[6-9](?:[\s-]?\d){9}(?!\d)",
    )

    for pattern in phone_patterns:
        phone = re.search(pattern, text, re.I)
        if phone:
            normalized_phone = _normalize_phone_number(phone.group(0))
            if normalized_phone:
                result["customer_phone"] = normalized_phone
                break

    # --------------------------------------------------------
    # Email - Standard format
    # --------------------------------------------------------
     # Normalize common STT email speech
    email_text = re.sub(r"\s+at\s+", "@", text, flags=re.I)
    email_text = re.sub(r"\s+dot\s+", ".", email_text, flags=re.I)

    email = re.search(
        r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
        text,
        re.I,
    )
    

    if email:
        result["customer_email"] = email.group(0).lower()
    else:
        # --------------------------------------------------------
        # Email - Voice patterns: "sundar at gmail dot com"
        # --------------------------------------------------------
        
        # Voice email forms:
        #   "sundar at gmail dot com"
        #   "sundar at gmail.com"
        # Normalize only when the complete address is unambiguous.
        voice_email_patterns = (
            r"\b([A-Za-z0-9._%+-]+)\s+at\s+([A-Za-z0-9.-]+)\s+dot\s+([A-Za-z]{2,})\b",
            r"\b([A-Za-z0-9._%+-]+)\s+at\s+([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b",
        )

        for voice_email_pattern in voice_email_patterns:
            voice_match = re.search(voice_email_pattern, text, re.I)
            if not voice_match:
                continue

            if len(voice_match.groups()) == 3:
                username, domain, tld = (g.lower() for g in voice_match.groups())
                normalized_email = f"{username}@{domain}.{tld}"
            else:
                username, domain = (g.lower() for g in voice_match.groups())
                normalized_email = f"{username}@{domain}"

            if re.fullmatch(
                r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
                normalized_email,
            ):
                result["customer_email"] = normalized_email
                break

    # --------------------------------------------------------
    # Customer name
    # --------------------------------------------------------

    patterns = (
        r"\bmy name is\s+([A-Za-z][A-Za-z .'-]{1,60})",
        r"\bname is\s+([A-Za-z][A-Za-z .'-]{1,60})",
        r"\bi am\s+([A-Za-z][A-Za-z .'-]{1,60})",
    )

    for pattern in patterns:
        match = re.search(pattern, text, re.I)

        if match:
            name = re.split(
                r"\b(?:my phone|phone number|mobile|email|and)\b",
                match.group(1),
                maxsplit=1,
                flags=re.I,
            )[0].strip(" .,-")

            if name:
                result["customer_name"] = name
                break

    # --------------------------------------------------------
    # "Samir 9098909890" style input
    # --------------------------------------------------------

    if not result["customer_name"] and result["customer_phone"]:
        without_email = re.sub(
            r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
            "",
            text,
            flags=re.I,
        )

        without_phone = re.sub(
            r"(?:\+?91[\s-]?)?[6-9](?:[\s-]?\d){9}",
            "",
            without_email,
            flags=re.I,
        ).strip(" ,.-")

        if re.fullmatch(
            r"[A-Za-z][A-Za-z .'-]{1,60}",
            without_phone,
        ):
            lowered_name = without_phone.lower()

            if not any(
                word in lowered_name
                for word in (
                    "room",
                    "deluxe",
                    "standard",
                    "premium",
                    "suite",
                    "yes",
                    "phone",
                    "mobile",
                )
            ):
                result["customer_name"] = without_phone
                result["customer_phone"] = normalized_phone

    return result

def _hotel_info_topic(text: str) -> str | None:
    lowered = _clean(text).lower()
    if re.search(r"\b(?:check[\s-]?in)\b", lowered) and re.search(r"\b(?:time|when|hour|hours)\b", lowered):
        return "checkin_time"
    if re.search(r"\b(?:check[\s-]?out|checkout)\b", lowered) and re.search(r"\b(?:time|when|hour|hours)\b", lowered):
        return "checkout_time"
    if re.search(r"\b(?:wi[\s-]?fi|wifi|internet)\b", lowered):
        return "wifi"
    if re.search(r"\bbreakfast\b", lowered):
        return "breakfast"
    if re.search(r"\bparking\b", lowered):
        return "parking"
    if re.search(r"\b(?:cancellation policy|refund policy)\b", lowered):
        return "cancellation_policy"
    return None


def _is_cancel(text: str) -> bool:
    lowered = text.lower()
    if "policy" in lowered or "rules" in lowered or "what is" in lowered:
        return False
    return bool(re.search(r"\b(?:cancel|cancellation)\b", text, re.I))


def _is_modify(text: str) -> bool:
    lowered = text.lower()
    modify_phrases_and_keywords = [
        "modify", "change", "update", "alter", "edit", "reschedule",
        "change my booking", "modify my reservation", "update my dates",
        "change my check out", "change checkin", "update details",
        "మార్చు", "మార్చాలి", "మార్పు", "మార్చండి", "marchu", "maarchu", "marchandi",
        "modify cheyyandi", "change cheyyandi", "update cheyyandi", "booking marchandi",
        "बदलो", "बदलना", "परिवर्तन", "संशोधन", "badlo", "badalna", 
        "modify karo", "change karo", "update karo",
        "மாற்று", "மாற்ற வேண்டும்", "booking maatru"
    ]
    return bool(any(phrase in lowered for phrase in modify_phrases_and_keywords))


def _is_new_booking(text: str) -> bool:
    lowered = text.lower()
    fresh_start = bool(
        re.search(r"\b(?:fresh|restart|new booking|start over)\b", lowered) or
        (re.search(r"\b(?:want|need|looking for|book|reserve)\b", lowered) and not _is_modify(text) and not _is_cancel(text))
    )
    return fresh_start


# --- ADDED: Helper to safely catch requests asking for booking details ---
def _is_details_request(text: str) -> bool:
    lowered = text.lower()
    keywords = ["details", "my details", "booking details", "show me", "information", "status", "summary"]
    return any(k in lowered for k in keywords) and not _is_modify(text) and not _is_cancel(text) and not _is_new_booking(text)


def _affirmative(text: str) -> bool:
    return bool(re.search(r"\b(?:yes|yeah|yep|sure|correct|confirm|confirmed|go ahead|do it|book it|proceed)\b", text, re.I))


def _is_explicit_booking_confirmation(text: str) -> bool:
    """
    Detect EXPLICIT booking confirmation intent.
    
    Only return True for clear confirmation phrases:
    - "yes confirm"
    - "confirm the booking"
    - "yes book it"
    - "yes proceed"
    - etc.
    
    NOT triggered by:
    - "yes I'm thankful"
    - "yes that's fine"
    - "yes exactly"
    - "yes check availability"
    """
    lowered = text.lower()
    
    explicit_patterns = [
        r"\byes.*(?:confirm|book|proceed|create|reserve)",
        r"\b(?:confirm|book|reserve|proceed).*(?:the booking|it|reservation)",
        r"\b(?:go ahead|do it|book it)\b",
    ]
    
    for pattern in explicit_patterns:
        if re.search(pattern, lowered):
            return True
    
    return False


def _build_booking_summary(state: dict[str, Any]) -> str:
    """
    Build a deterministic summary of the booking state.
    
    Shows all validated booking details.
    """
    lines = ["Here is your booking summary:"]
    
    guest = state.get("customer_name", "N/A")
    phone = state.get("customer_phone", "N/A")
    email = state.get("customer_email") or "Not provided"
    room_num = state.get("selected_room_number", "N/A")
    room_type = state.get("room_type", "N/A")
    checkin = state.get("check_in", "N/A")
    checkout = state.get("check_out", "N/A")
    adults = state.get("adults", "N/A")
    children = state.get("children", 0)
    
    lines.append(f"  Guest: {guest}")
    lines.append(f"  Phone: {phone}")
    lines.append(f"  Email: {email}")
    lines.append(f"  Room: {room_type} (#{room_num})")
    lines.append(f"  Check-in: {checkin}")
    lines.append(f"  Check-out: {checkout}")
    lines.append(f"  Guests: {adults} adult(s), {children} child(ren)")
    
    return "\n".join(lines)


def _negative(text: str) -> bool:
    return bool(re.search(r"\b(?:no|nope|don't|do not|not now|stop)\b", text, re.I))


def _route(session: dict[str, Any], text: str) -> str:
    if _is_cancel(text) or _is_modify(text):
        return "existing_booking_action"
    if _is_new_booking(text):
        session["booking_state"] = _new_booking_state()
        session["pending_action"] = None
        return "new_booking"
    if session.get("booking_state", {}).get("check_in"):
        return "new_booking"
    existing = session.get("flow_stage")
    if existing in {"new_booking", "existing_booking_action"}:
        return existing
    return "idle"


def _invalidate_room_state(state: dict[str, Any]) -> None:
    state["available_rooms"] = []
    state["availability_checked"] = False
    state["selected_room_id"] = None
    state["selected_room_number"] = None


def _update_state(state: dict[str, Any], text: str) -> None:
    check_in, check_out = _extract_dates(text)
    if check_in and check_out:
        valid_range, _ = _validate_date_range(
            check_in,
            check_out,
        )

        if not valid_range:
            return
    if check_in and check_in != state.get("check_in"):
        state["check_in"] = check_in
        state["dates_validated"] = False
        _invalidate_room_state(state)
        if isinstance(state.get("modification"), dict):
            state["modification"]["check_in"] = check_in
            
    if check_out and check_out != state.get("check_out"):
        state["check_out"] = check_out
        state["dates_validated"] = False
        _invalidate_room_state(state)
        if isinstance(state.get("modification"), dict):
            state["modification"]["check_out"] = check_out

    adults, children = _guest_counts(text)
    if adults is None and state.get("adults") is None and re.fullmatch(r"\d{1,2}", text):
        val = int(text)
        if 1 <= val <= 20:
            adults = val
    if adults is not None:
        if adults != state.get("adults"):
            state["adults"] = adults
            state["available_rooms"] = []
            state["availability_checked"] = False
            state["selected_room_id"] = None
            state["selected_room_number"] = None
            if isinstance(state.get("modification"), dict):
                state["modification"]["adults"] = adults

    if children is not None:
        state["children"] = children
        if isinstance(state.get("modification"), dict):
            state["modification"]["children"] = children

    room_type = _room_type(text)
    if room_type:
        if room_type != state.get("room_type"):
            state["room_type"] = room_type
            _invalidate_room_state(state)
            if isinstance(state.get("modification"), dict):
                state["modification"]["room_type"] = room_type

    room = _room_number(text)
    if room:
        state["selected_room_number"] = room
        state["selected_room_id"] = None
        if isinstance(state.get("modification"), dict):
            state["modification"]["room_number"] = room

    details = _customer_details(text)
    for key, value in details.items():
        if value:
            state[key] = value
            if isinstance(state.get("modification"), dict):
                state["modification"][key] = value


def _modify_after_confirmation(session: dict[str, Any]) -> str:
    booking_id = session.get("last_booking_id")
    if not booking_id:
        return "Please provide your booking ID so I can modify it."

    state = session["booking_state"]
    mod = state.get("modification", {})
    
    arguments: dict[str, Any] = {"booking_id": booking_id}
    if mod.get("check_in"):
        arguments["check_in"] = mod["check_in"]
    if mod.get("check_out"):
        arguments["check_out"] = mod["check_out"]
    if mod.get("adults") is not None:
        arguments["adults"] = mod["adults"]
    if mod.get("children") is not None:
        arguments["children"] = mod["children"]
    if mod.get("room_type"):
        arguments["room_type"] = mod["room_type"]
    if mod.get("room_number"):
        arguments["room_number"] = mod["room_number"]
    if mod.get("customer_name"):
        arguments["customer_name"] = mod["customer_name"]       
    if mod.get("customer_phone"):
        arguments["customer_phone"] = mod["customer_phone"] 
    if mod.get("customer_email"):
        arguments["customer_email"] = mod["customer_email"]

    result = _safe_tool("modify_booking_tool", arguments)
    _apply_tool_result(session, "modify_booking_tool", result)

    if result.get("booking_id") and "error" not in result:
        changes_desc = []
        if result.get("room_id") or mod.get("room_number"):
            changes_desc.append(f"Room: {mod.get('room_number') or result.get('room_id')}")
        if result.get("check_in"):
            changes_desc.append(f"Check-in: {result.get('check_in')}")
        if result.get("check_out"):
            changes_desc.append(f"Check-out: {result.get('check_out')}")
        if result.get("adults") is not None:
            changes_desc.append(f"Adults: {result.get('adults')}")
        if result.get("children") is not None:
            changes_desc.append(f"Children: {result.get('children')}")
        if result.get("customer_name"):
            changes_desc.append(f"Name: {result.get('customer_name')}")
        if result.get("customer_phone"):
            changes_desc.append(f"Phone: {result.get('customer_phone')}")
        if result.get("customer_email"):
            changes_desc.append(f"Email: {result.get('customer_email')}")
    
        summary_text = ", ".join(changes_desc) if changes_desc else "details"
        state["modification"] = {}
        return f"Booking {booking_id} has been successfully modified in the database! Updated {summary_text}."
    
    err = result.get('error', 'Unknown modification error')
    return f"I couldn't modify that booking: {err}"


def _safe_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    func = TOOL_FUNCTIONS.get(name)
    if func is None:
        return {"error": "That operation is unavailable."}
    try:
        res = func(**arguments)
        return res if isinstance(res, dict) else {"result": res}
    except Exception:
        return {"error": "The requested operation could not be completed."}


def _apply_tool_result(session: dict[str, Any], tool_name: str, result: dict[str, Any]) -> None:
    state = session["booking_state"]

    if tool_name == "validate_booking_dates":
        state["dates_validated"] = bool(result.get("valid"))
        if result.get("valid"):
            state["check_in"] = result.get("check_in")
            state["check_out"] = result.get("check_out")

    elif tool_name == "check_room_availability":
        rooms = result.get("available_rooms")
        if isinstance(rooms, list):
            state["available_rooms"] = rooms
            state["availability_checked"] = True

            wanted = str(state.get("selected_room_number") or "")
            state["selected_room_id"] = None
            for room in rooms:
                if str(room.get("room_number")) == wanted:
                    state["selected_room_id"] = room.get("room_id")
                    break
            
            # Only auto-select by room_type if explicitly EXACTLY ONE matches
            if not state.get("selected_room_id") and state.get("room_type"):
                matching = [r for r in rooms if r.get("room_type", "").lower() == state["room_type"].lower()]
                # Auto-select ONLY if exactly one room of that type is available
                # If multiple rooms of the same type, we MUST ask the user
                if len(matching) == 1:
                    state["selected_room_id"] = matching[0].get("room_id")
                    state["selected_room_number"] = str(matching[0].get("room_number"))

    elif tool_name == "get_room_details":
        if result.get("room_id") is not None and str(result.get("room_number")) == str(state.get("selected_room_number")):
            state["selected_room_id"] = result["room_id"]

    elif tool_name == "create_booking_tool":
        booking_id = result.get("booking_id")
        if booking_id:
            session["last_booking_id"] = booking_id
            session["pending_action"] = None
            session["flow_stage"] = "existing_booking_action"

    elif tool_name == "cancel_booking_tool":
        if result.get("status") == "cancelled":
            session["pending_action"] = None
            session["flow_stage"] = "idle"

    elif tool_name == "modify_booking_tool":
        if result.get("booking_id") and "error" not in result:
            session["last_booking_id"] = result["booking_id"]
            session["pending_action"] = None
            session["flow_stage"] = "existing_booking_action"


def _get_available_rooms_for_selection(state: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Return available rooms that the user may need to choose from.
    
    If a room_type is specified, return only rooms of that type.
    Otherwise, return all available rooms.
    """
    available = state.get("available_rooms", [])
    
    if state.get("room_type"):
        return [r for r in available if r.get("room_type", "").lower() == state["room_type"].lower()]
    
    return available


def _needs_room_selection(state: dict[str, Any]) -> bool:
    """
    Returns True if the user needs to select a room.
    
    Returns False only if:
    1. A specific room_number has been selected and exists in available rooms, OR
    2. A room_type is specified and exactly one room of that type is available
    """
    
    if not state.get("availability_checked"):
        return False
    
    if state.get("selected_room_id"):
        return False
    
    available_for_selection = _get_available_rooms_for_selection(state)
    
    if len(available_for_selection) == 0:
        return False
    
    if len(available_for_selection) == 1:
        return False
    
    return True


def _selected_room_id(state: dict[str, Any]) -> int | None:
    selected = state.get("selected_room_id")
    if isinstance(selected, int):
        return selected
    if isinstance(selected, str) and selected.isdigit():
        return int(selected)

    number = str(state.get("selected_room_number") or "")
    for room in state.get("available_rooms", []):
        if str(room.get("room_number")) != number:
            continue
        val = room.get("room_id")
        if isinstance(val, int):
            return val
        if isinstance(val, str) and val.isdigit():
            return int(val)
    
    rt = state.get("room_type")
    if rt:
        matching = [r for r in state.get("available_rooms", []) if str(r.get("room_type", "")).lower() == rt.lower()]
        if len(matching) == 1:
            return matching[0].get("room_id")

    return None


def _booking_ready(state: dict[str, Any]) -> tuple[bool, str | None]:
    if state.get("selected_room_number") and state.get("selected_room_id") is None:
        state["selected_room_id"] = _selected_room_id(state)
    elif not state.get("selected_room_id") and state.get("room_type"):
        state["selected_room_id"] = _selected_room_id(state)
    phone = str(state.get("customer_phone") or "")

    if not re.fullmatch(r"[6-9]\d{9}", phone):
        return False, "valid 10-digit phone number"

    # Revalidate the date range at the final controller gate.
    valid_dates, date_error = _validate_date_range(
        state.get("check_in"),
        state.get("check_out"),
    )
    if not valid_dates:
        return False, date_error or "valid booking dates"

    # If an email is present, it must be a complete normalized address.
    email = state.get("customer_email")
    if email and not re.fullmatch(
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        str(email),
    ):
        return False, "valid email address"

    # The selected room must belong to the CURRENT availability result.
    selected_room_id = state.get("selected_room_id")
    if selected_room_id is not None:
        current_room = next(
            (
                room for room in state.get("available_rooms", [])
                if str(room.get("room_id")) == str(selected_room_id)
            ),
            None,
        )
        if current_room is None:
            state["selected_room_id"] = None
            return False, "a currently available room"

    required = (
        ("check_in", "check-in date"),
        ("check_out", "check-out date"),
        ("adults", "number of adults"),
        ("customer_name", "name"),
        ("customer_phone", "phone number"),
        ("selected_room_id", "room selection"),
    )
    for key, label in required:
        if state.get(key) in (None, ""):
            return False, label

    if not state.get("dates_validated"):
        return False, "validated booking dates"
    if not state.get("availability_checked"):
        return False, "room availability"

    return True, None


def _run_booking_preflight(session: dict[str, Any]) -> None:
    if session.get("flow_stage") != "new_booking":
        return

    state = session["booking_state"]
    if not state.get("check_in") or not state.get("check_out"):
        return

    if not state.get("dates_validated"):
        result = _safe_tool("validate_booking_dates", {"check_in": state["check_in"], "check_out": state["check_out"]})
        _apply_tool_result(session, "validate_booking_dates", result)
        if not result.get("valid"):
            return

    if state.get("availability_checked"):
        return

    if state.get("room_type") is None and state.get("adults") is None:
        return

    args: dict[str, Any] = {"check_in": state["check_in"], "check_out": state["check_out"]}
    if state.get("room_type"):
        args["room_type"] = state["room_type"]
    if state.get("adults") is not None:
        args["adults"] = int(state["adults"])

    result = _safe_tool("check_room_availability", args)
    _apply_tool_result(session, "check_room_availability", result)


def _build_system_prompt(language: str | None, booking_state: dict[str, Any] | None = None) -> str:
    today = datetime.today()
    current_year = today.year
    current_date = today.strftime("%A, %B %d, %Y")
    current_month = today.strftime("%B")
    current_time = today.strftime("%I:%M %p")
    
    # Safely format all datetime values into the base prompt
    prompt = _BASE_PROMPT.format(
        current_year=current_year, 
        current_date=current_date, 
        current_month=current_month,
        current_time=current_time
    )
    
    if language and language in SUPPORTED_LANGUAGES and language != "en":
        lang_name = SUPPORTED_LANGUAGES[language]
        prompt += f"""

UNIVERSAL LANGUAGE RULE:
- The customer has been speaking {lang_name} in this conversation.
- The detected conversation language is {lang_name}.
- Continue replying in {lang_name} unless the customer's latest message clearly uses another language.
- STYLE MATCHING: Match the exact style and script used in the user's latest message.
  * If the user uses native script, reply in the same native script.
  * If the user uses English letters / phonetic script, reply using the same style when appropriate.
  * If the user mixes languages, understand the complete meaning and reply naturally in the dominant language.
- Never output database error strings like `:mysqlUnicode:`.
- Preserve names, phone numbers, email addresses, dates, room numbers, booking IDs, room types, and prices exactly.
- Keep all hotel facts, room types (Standard, Deluxe, Premium, Suite), prices, and ABC Hotel identity strictly accurate.
"""
    else:
       prompt += """

UNIVERSAL LANGUAGE RULE:
- Understand and respond naturally in the language used by the customer.
- The customer may use ANY human language, including languages not listed in SUPPORTED_LANGUAGES.
- Do NOT force English when the customer speaks another language.
- If the customer mixes languages, understand the complete meaning and reply naturally using the dominant language of the latest message.
- If the customer uses native script, reply in the same native script.
- If the customer uses phonetic English letters for another language, reply naturally in the same phonetic style when appropriate.
- Do not translate the customer's message into English unless the customer asks for translation.
- Preserve all important booking entities exactly: names, phone numbers, email addresses, dates, room numbers, booking IDs, room types, and prices.
- Never invent missing information.
- Keep all hotel facts, room types (Standard, Deluxe, Premium, Suite), prices, and ABC Hotel identity strictly accurate.
"""

    if booking_state:
        prompt += "\nCURRENT CONTROLLER STATE:\n" + json.dumps(booking_state, ensure_ascii=False) + "\n"
        
    return prompt
# 1. First define the helper function here
def _is_date_inquiry(text: str) -> bool:
    lowered = text.lower()
    keywords = ["today", "current date", "what date", "what is today", "date today", "month today", "year today"]
    return any(k in lowered for k in keywords)

def run_turn(
    session_id: str,
    user_message: str,
    detected_language: str | None = None,
    max_tool_hops: int = _MAX_TOOL_HOPS,
) -> str:
    text = _clean(user_message)
    if not session_id or not text:
        raise ValueError("session_id and message are required")

    session = _load_session(session_id)
    if detected_language in SUPPORTED_LANGUAGES:
        session["language"] = detected_language

    state = session["booking_state"]

# --- ADD THIS: Date Inquiry Handler ---
    if _is_date_inquiry(text):
        today_str = date.today().strftime("%B %d, %Y")
        reply = f"Today is {today_str}. How can I help you with your room reservation?"
        session["messages"].append({"role": "user", "content": text})
        session["messages"].append({"role": "assistant", "content": reply})
        _save_session(session_id, session)
        return reply

    # --- ADDED: Handle details request smoothly without re-confirming booking ---
    if _is_details_request(text):
        target_id = session.get("last_booking_id")
        if target_id:
            reply = (
                f"Here are your booking details for ID {target_id}:\n"
                f"- **Guest Name**: {state.get('customer_name', 'N/A')}\n"
                f"- **Phone**: {state.get('customer_phone', 'N/A')}\n"
                f"- **Room**: {state.get('selected_room_number', 'N/A')} ({state.get('room_type', 'Standard')})\n"
                f"- **Check-in**: {state.get('check_in', 'N/A')}\n"
                f"- **Check-out**: {state.get('check_out', 'N/A')}\n"
                f"- **Adults**: {state.get('adults', 1)}, **Children**: {state.get('children', 0)}"
            )
        else:
            reply = "You don't have an active booking session right now. Would you like to check room availability and make a reservation?"
        
        session["messages"].append({"role": "user", "content": text})
        session["messages"].append({"role": "assistant", "content": reply})
        _save_session(session_id, session)
        return reply

    _update_state(state, text)

    found_id = _booking_id(text)
    if found_id:
        session["last_booking_id"] = found_id

    faq_topic = _hotel_info_topic(text)
    if faq_topic and not state.get("check_in") and session.get("flow_stage") == "idle":
        session["messages"].append({"role": "user", "content": text})
        tool_res = _safe_tool("get_hotel_information", {"topic": faq_topic})
        answer = tool_res.get("answer") if isinstance(tool_res, dict) else None
        reply = answer.strip() if answer else "I couldn't find that information in hotel records."
        session["messages"].append({"role": "assistant", "content": reply})
        _save_session(session_id, session)
        return reply

    route = _route(session, text)
    session["flow_stage"] = route

    if _is_cancel(text) or session.get("pending_action") == "confirm_cancel":
        target_id = session.get("last_booking_id")
        if not target_id:
            reply = "Please provide your booking ID so I can process the cancellation."
            session["pending_action"] = "confirm_cancel"
        elif session.get("pending_action") == "confirm_cancel" and _affirmative(text):
            tool_res = _safe_tool("cancel_booking_tool", {"booking_id": target_id})
            _apply_tool_result(session, "cancel_booking_tool", tool_res)
            session["pending_action"] = None
            reply = f"Booking {target_id} has been successfully cancelled." if tool_res.get("status") == "cancelled" else f"Could not cancel booking: {tool_res.get('error')}"
        elif session.get("pending_action") == "confirm_cancel" and _negative(text):
            session["pending_action"] = None
            session["flow_stage"] = "idle"
            reply = "Okay, I won't cancel the booking."
        else:
            session["pending_action"] = "confirm_cancel"
            reply = f"Are you sure you want to cancel booking {target_id}? Please reply 'Yes' to confirm."

        session["messages"].append({"role": "user", "content": text})
        session["messages"].append({"role": "assistant", "content": reply})
        _save_session(session_id, session)
        return reply

    if _is_modify(text) or session.get("pending_action") == "confirm_modify":
        session["flow_stage"] = "existing_booking_action"
        check_in, check_out = _extract_dates(text)
        if check_in:
            state["modification"]["check_in"] = check_in
        if check_out:
            state["modification"]["check_out"] = check_out
        adults, children = _guest_counts(text)
        if adults is not None:
            state["modification"]["adults"] = adults
        if children is not None:
            state["modification"]["children"] = children
        rt = _room_type(text)
        if rt:
            state["modification"]["room_type"] = rt
        rn = _room_number(text)
        if rn:
            state["modification"]["room_number"] = rn

        cust_details = _customer_details(text)
        for k, v in cust_details.items():
            if v:
                state["modification"][k] = v

        target_id = session.get("last_booking_id")
        if not target_id:
            reply = "Please provide your booking ID so I can modify it."
            session["pending_action"] = "confirm_modify"
        elif session.get("pending_action") == "confirm_modify" and _affirmative(text):
            reply = _modify_after_confirmation(session)
        elif session.get("pending_action") == "confirm_modify" and _negative(text):
            session["pending_action"] = None
            session["flow_stage"] = "idle"
            reply = "Okay, I won't modify the booking."
        else:
            session["pending_action"] = "confirm_modify"
            mod_summary = []
            if state["modification"].get("check_in"): mod_summary.append(f"check-in: {state['modification']['check_in']}")
            if state["modification"].get("check_out"): mod_summary.append(f"check-out: {state['modification']['check_out']}")
            if state["modification"].get("adults"): mod_summary.append(f"adults: {state['modification']['adults']}")
            if state["modification"].get("children"): mod_summary.append(f"children: {state['modification']['children']}")
            if state["modification"].get("room_number"): mod_summary.append(f"room: {state['modification']['room_number']}")
            if state["modification"].get("room_type"): mod_summary.append(f"room type: {state['modification']['room_type']}")
            if state["modification"].get("customer_name"): mod_summary.append(f"name: {state['modification']['customer_name']}")
            if state["modification"].get("customer_phone"): mod_summary.append(f"phone: {state['modification']['customer_phone']}")
            if state["modification"].get("customer_email"): mod_summary.append(f"email: {state['modification']['customer_email']}") 

            summary_str = f" with changes ({', '.join(mod_summary)})" if mod_summary else ""
            reply = f"I have prepared the modification for booking {target_id}{summary_str}. Would you like me to confirm and apply these changes to the database?"
        session["messages"].append({"role": "user", "content": text})
        session["messages"].append({"role": "assistant", "content": reply})
        _save_session(session_id, session)
        return reply

    if session["flow_stage"] == "new_booking":
        _run_booking_preflight(session)

    ready, missing = _booking_ready(state)
    
    # Handle room selection when multiple rooms available
    if ready and _needs_room_selection(state):
        available_for_selection = _get_available_rooms_for_selection(state)
        room_numbers = ", ".join(str(r.get("room_number")) for r in available_for_selection)
        reply = f"We have {len(available_for_selection)} {state.get('room_type', 'rooms')} available: {room_numbers}. Which room would you like?"
        session["messages"].append({"role": "user", "content": text})
        session["messages"].append({"role": "assistant", "content": reply})
        _save_session(session_id, session)
        return reply
    
    if ready and session["flow_stage"] == "new_booking":
        # Check for explicit booking confirmation only when pending_action is confirm_booking
        if session.get("pending_action") == "confirm_booking" and _is_explicit_booking_confirmation(text):
            # Final gate check before creating booking
            if session.get("last_booking_id") and not _is_new_booking(text):
                reply = f"Your booking is already confirmed under booking ID {session['last_booking_id']}."
            else:
                room_id = _selected_room_id(state)
                
                # Re-verify all booking gates one final time
                final_ready, final_missing = _booking_ready(state)
                if not final_ready:
                    reply = f"Before proceeding, I need: {final_missing}."
                else:
                    tool_res = _safe_tool("create_booking_tool", {
                        "room_id": room_id,
                        "customer_name": state["customer_name"],
                        "customer_phone": state["customer_phone"],
                        "customer_email": state.get("customer_email"),
                        "check_in": state["check_in"],
                        "check_out": state["check_out"],
                        "adults": int(state["adults"]),
                        "children": int(state.get("children") or 0),
                    })
                    _apply_tool_result(session, "create_booking_tool", tool_res)
                    bk_id = tool_res.get("booking_id")
                    
                    if isinstance(bk_id, str) and re.fullmatch(r"BK\d{4,}", bk_id):
                        session["last_booking_id"] = bk_id
                        session["pending_action"] = None
                        session["flow_stage"] = "existing_booking_action"
                        reply = f"Booking confirmed! Your booking ID is {bk_id}. Room is reserved from {tool_res.get('check_in', state['check_in'])} to {tool_res.get('check_out', state['check_out'])}. Total amount: ₹{tool_res.get('total_amount')}."
                    else:
                        err = tool_res.get("error", "The booking was not confirmed by the database.")
                        reply = f"Could not complete booking: {err}"
            
            session["messages"].append({"role": "user", "content": text})
            session["messages"].append({"role": "assistant", "content": reply})
            _save_session(session_id, session)
            return reply
        elif session.get("pending_action") != "confirm_booking":
            # Show summary and ask for confirmation
            session["pending_action"] = "confirm_booking"
            summary = _build_booking_summary(state)
            reply = summary + "\n\nEverything looks correct? Please say 'yes, confirm the booking' to proceed."
            session["messages"].append({"role": "user", "content": text})
            session["messages"].append({"role": "assistant", "content": reply})
            _save_session(session_id, session)
            return reply
        else:
            # pending_action == "confirm_booking" but not explicit confirmation
            reply = "I'm ready to book! Please confirm by saying 'yes, confirm the booking' or 'yes, book it'."
            session["messages"].append({"role": "user", "content": text})
            session["messages"].append({"role": "assistant", "content": reply})
            _save_session(session_id, session)
            return reply

    session["messages"].append({"role": "user", "content": text})
    messages = [
        {"role": "system", "content": _build_system_prompt(session.get("language"), session.get("booking_state"))}
    ]
    for m in session.get("messages", []):
        if isinstance(m, dict) and m.get("role") in {"user", "assistant", "tool"}:
            messages.append(m)

    for _ in range(max(1, max_tool_hops)):
        reply = call_llm(messages, SAFE_TOOL_SCHEMAS)

        if not reply.has_tool_calls:
            content = (reply.content or "").strip() or "How can I help you with your stay?"
            
            if re.search(r"\bconfirmed\b", content, re.I) and not session.get("last_booking_id"):
                content = "I have noted your preferences, but I still need to complete the reservation details and check availability before confirming. Would you like to proceed with checking availability?"

            if ready and session["flow_stage"] == "new_booking" and not session.get("last_booking_id"):
                session["pending_action"] = "confirm_booking"
                content += " Would you like me to confirm this booking?"

            session["messages"].append({"role": "assistant", "content": content})
            _save_session(session_id, session)
            return content

        assistant_message: dict[str, Any] = {
            "role": "assistant",
            "content": reply.content,
            "tool_calls": [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": json.dumps(call.arguments, ensure_ascii=False),
                    },
                }
                for call in reply.tool_calls
            ],
        }
        messages.append(assistant_message)
        session["messages"].append(assistant_message)

        for call in reply.tool_calls:
            name = call.name
            if name in _TRANSACTIONAL_TOOL_NAMES:
                res = {"error": "Transactions require explicit controller confirmation."}
            else:
                res = _safe_tool(name, call.arguments)
            
            _apply_tool_result(session, name, res)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(res, ensure_ascii=False)})

        session["messages"] = [m for m in messages if m.get("role") != "system"]
        _save_session(session_id, session)

    fallback = "I'm having trouble completing that. Could you please rephrase your request?"
    session["messages"].append({"role": "assistant", "content": fallback})
    _save_session(session_id, session)
    return fallback