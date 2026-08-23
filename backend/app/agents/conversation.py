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
You are the AI receptionist for ABC Hotel.

-->> THE CURRENT YEAR IS 2026. <<--

You help customers:
- check room availability
- make a new reservation
- cancel an existing reservation
- modify an existing reservation
- Modification Details: When a customer asks to modify a booking (like changing room, dates, or contact info), ensure the specific change is explicitly captured and passed to the modification tool before asking for confirmation.
- answer factual hotel questions

CRITICAL DATE & YEAR VALIDATION RULE:
- Always verify if the dates or years provided by the customer are in the future relative to the current year (2026).
- If a customer specifies a past year or date (e.g., 2019, 2021, or any year in the past), politely correct them: "That date is in the past. Our hotel bookings are open for future dates like 2026 or 2029. Could you please provide valid future dates?"

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
6. Customers choose human-facing room numbers, not internal room IDs.
7. A new booking requires an actual available room.
8. A booking is created only after explicit customer confirmation.
9. Cancellation requires explicit customer confirmation.
10. Modification requires explicit customer confirmation.
11. Never turn a modification into a new booking.
12. Never expose internal database IDs or tool JSON.
13. Reply naturally in the customer's language.
14. If a tool reports an error, explain it naturally.

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
    cleaned = re.sub(r"(\d{1,2})(st|nd|rd|th)", r"\1", raw)
    cleaned = cleaned.replace(",", " ").strip()

    formats = ("%B %d %Y", "%b %d %Y", "%d %B %Y", "%d %b %Y")
    for fmt in formats:
        try:
            return datetime.strptime(cleaned, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _extract_dates(text: str) -> tuple[str | None, str | None]:
    iso = re.findall(r"\b\d{4}-\d{1,2}-\d{1,2}\b", text)
    if len(iso) >= 2:
        try:
            return date.fromisoformat(iso[0]).isoformat(), date.fromisoformat(iso[1]).isoformat()
        except ValueError:
            return None, None

    month = (
        r"(?:January|February|March|April|May|June|July|August|"
        r"September|October|November|December|Jan|Feb|Mar|Apr|"
        r"Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)"
    )
    month_pattern = rf"\b{month}\s+\d{{1,2}}(?:st|nd|rd|th)?[,]?\s+\d{{4}}\b"
    month_matches = re.findall(month_pattern, text, re.I)

    if len(month_matches) >= 2:
        return _parse_month_date(month_matches[0]), _parse_month_date(month_matches[1])

    numeric = re.findall(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{4}\b", text)
    if len(numeric) >= 2:
        parsed = []
        for value in numeric[:2]:
            a, b, year = [int(x) for x in re.split(r"[/-]", value)]
            try:
                parsed.append(date(year, b, a).isoformat())
            except ValueError:
                try:
                    parsed.append(date(year, a, b).isoformat())
                except ValueError:
                    return None, None
        return parsed[0], parsed[1]

    return None, None


def _customer_details(text: str) -> dict[str, str | None]:
    result: dict[str, str | None] = {
        "customer_name": None,
        "customer_phone": None,
        "customer_email": None,
    }

    phone = re.search(r"(?<!\d)(?:\+?91[-\s]?)?[6-9]\d{9}(?!\d)", text)
    if phone:
        result["customer_phone"] = re.sub(r"\D", "", phone.group(0))[-10:]

    email = re.search(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", text, re.I)
    if email:
        result["customer_email"] = email.group(0)

    patterns = (
        r"\bmy name is\s+([A-Za-z][A-Za-z .'-]{1,60})",
        r"\bname is\s+([A-Za-z][A-Za-z .'-]{1,60})",
        r"\bi am\s+([A-Za-z][A-Za-z .'-]{1,60})",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            name = re.split(r"\b(?:my phone|phone number|email|and)\b", match.group(1), maxsplit=1, flags=re.I)[0].strip(" .,-")
            if name:
                result["customer_name"] = name
                break

    if not result["customer_name"] and result["customer_phone"]:
        without_email = re.sub(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", "", text, flags=re.I)
        without_phone = re.sub(r"(?:\+?91[-\s]?)?[6-9]\d{9}", "", without_email).strip(" ,.-")
        if re.fullmatch(r"[A-Za-z][A-Za-z .'-]{1,60}", without_phone) and not any(k in without_phone.lower() for k in ["room", "deluxe", "standard", "yes"]):
            result["customer_name"] = without_phone

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
        # English
        "modify", "change", "update", "alter", "edit", "reschedule",
        "change my booking", "modify my reservation", "update my dates",
        "change my check out", "change checkin", "update details",
        # Telugu / Tanglish
        "మార్చు", "మార్చాలి", "మార్పు", "మార్చండి", "marchu", "maarchu", "marchandi",
        "modify cheyyandi", "change cheyyandi", "update cheyyandi", "booking marchandi",
        # Hindi / Hinglish
        "बदलो", "बदलना", "परिवर्तन", "संशोधन", "badlo", "badalna", 
        "modify karo", "change karo", "update karo",
        # Tamil / Tanglish
        "மாற்று", "மாற்ற வேண்டும்", "booking maatru"
    ]
    has_keyword = any(phrase in lowered for phrase in modify_phrases_and_keywords)
    return bool(has_keyword)


def _is_new_booking(text: str) -> bool:
    return bool(
        re.search(r"\b(?:book|booking|reserve|reservation)\b", text, re.I) or
        re.search(r"\b(?:want|need|looking for|get|find)\s+(?:a|an|the)?\s*room\b", text, re.I) or
        re.search(r"\b(?:adults?|suite|deluxe|standard|premium)\b", text, re.I)
    )


def _affirmative(text: str) -> bool:
    return bool(re.search(r"\b(?:yes|yeah|yep|sure|correct|confirm|confirmed|go ahead|do it|book it|proceed)\b", text, re.I))


def _negative(text: str) -> bool:
    return bool(re.search(r"\b(?:no|nope|don't|do not|not now|stop)\b", text, re.I))


def _route(session: dict[str, Any], text: str) -> str:
    if _is_cancel(text) or _is_modify(text):
        return "existing_booking_action"
    if _is_new_booking(text) or session.get("booking_state", {}).get("check_in"):
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

    # Debug print to terminal
    print(f"DEBUG MODIFY ARGUMENTS: {arguments}")

    result = _safe_tool("modify_booking_tool", arguments)
    _apply_tool_result(session, "modify_booking_tool", result)

    if result.get("booking_id") and "error" not in result:
        # Dynamically build summary of what was successfully changed
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
        state["modification"] = {}  # Clear pending modifications
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
            
            if not state.get("selected_room_id") and state.get("room_type"):
                matching = [r for r in rooms if r.get("room_type", "").lower() == state["room_type"].lower()]
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
    prompt = _BASE_PROMPT
    
    # Language handling
    if language and language in SUPPORTED_LANGUAGES and language != "en":
        lang_name = SUPPORTED_LANGUAGES[language]
        prompt += f"""

UNIVERSAL LANGUAGE RULE: The customer has been speaking
{lang_name}
in this conversation.
- Continue replying in {lang_name}.
- STYLE MATCHING: Match the exact style and language used in the user's latest message:
  * If the user typed in native script (e.g., తెలుగు, हिन्दी, தமிழ்), reply back in that same native script.
  * If the user typed using English letters / phonetic script (Tanglish, Hinglish), reply back using English letters (phonetic script).
- Never output database error strings like `:mysqlUnicode:`.
- Keep all hotel facts, room types (Standard, Deluxe, Premium, Suite), prices, and ABC Hotel identity strictly accurate.
"""
    else:
        prompt += """

UNIVERSAL LANGUAGE RULE: 
- You MUST communicate strictly in standard, professional English. 
- Never switch to any other unrequested language remember it.
- Keep all hotel facts, room types (Standard, Deluxe, Premium, Suite), prices, and ABC Hotel identity strictly accurate.
"""

    if booking_state:
        prompt += "\nCURRENT CONTROLLER STATE:\n" + json.dumps(booking_state, ensure_ascii=False) + "\n"
        
    return prompt
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
    if ready and session["flow_stage"] == "new_booking":
        if _affirmative(text) or session.get("pending_action") == "confirm_booking":
            if session.get("last_booking_id"):
                reply = f"Your booking is already confirmed under booking ID {session['last_booking_id']}."
            else:
                room_id = _selected_room_id(state)
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
                
                if bk_id:
                    session["last_booking_id"] = bk_id
                    session["pending_action"] = None
                    session["flow_stage"] = "existing_booking_action"
                    reply = f"Booking confirmed! Your booking ID is {bk_id}. Room is reserved from {tool_res.get('check_in', state['check_in'])} to {tool_res.get('check_out', state['check_out'])}. Total amount: ₹{tool_res.get('total_amount')}."
                else:
                    err = tool_res.get("error", "Room unavailable")
                    reply = f"Could not complete booking: {err}"
            
            session["messages"].append({"role": "user", "content": text})
            session["messages"].append({"role": "assistant", "content": reply})
            _save_session(session_id, session)
            return reply
        else:
            session["pending_action"] = "confirm_booking"
            reply = f"I have all your details from {state.get('check_in')} to {state.get('check_out')}. Would you like me to confirm this booking?"
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