"""
Tests the /ai/chat endpoint's tool-calling loop with a MOCKED LLM.

No real OpenAI/Ollama call is made.

These tests verify:

- no LLM configured -> 503
- normal AI reply
- tool calling
- real database tool execution
- session persistence
- tool errors
- multilingual language hint
- future date validation
- past date rejection
- invalid date range rejection
- availability rejects past dates
- date validation tool error flows back to LLM
"""

from unittest.mock import patch

from app.agents.llm_client import (
    LLMReply,
    ToolCall,
)

from app.agents.tools import (
    validate_booking_dates,
    check_room_availability,
)


# ============================================================
# No LLM Configured
# ============================================================

def test_chat_without_llm_configured_returns_503(client):
    """
    conftest.py explicitly clears both OPENAI_API_KEY
    and LLM_PROVIDER.

    Therefore the application should reject the request
    with 503 instead of attempting to contact Ollama
    or OpenAI.
    """

    res = client.post(
        "/ai/chat",
        json={
            "session_id": "test1",
            "message": "hi",
        },
    )

    assert res.status_code == 503


# ============================================================
# Simple AI Reply
# ============================================================

def test_chat_simple_reply_no_tools(client):

    with patch(
        "app.agents.conversation.call_llm"
    ) as mock_llm:

        mock_llm.return_value = LLMReply(
            content="Hello! How can I help?",
            tool_calls=[],
        )

        res = client.post(
            "/ai/chat",
            json={
                "session_id": "test2",
                "message": "hi",
            },
        )

    assert res.status_code == 200

    assert (
        res.json()["reply"]
        == "Hello! How can I help?"
    )


# ============================================================
# Tool Calling
# ============================================================

def test_chat_tool_calling_executes_real_tool(
    client,
    sample_room_ids,
):
    """
    Confirms a mocked tool-call request actually executes
    check_room_availability against the REAL TEST DATABASE.
    """

    call_count = {
        "n": 0
    }

    def fake_llm(
        messages,
        tools,
    ):

        call_count["n"] += 1

        # ----------------------------------------------------
        # First LLM call -> request tool
        # ----------------------------------------------------

        if call_count["n"] == 1:

            return LLMReply(
                content=None,
                tool_calls=[
                    ToolCall(
                        id="call_1",
                        name="check_room_availability",
                        arguments={
                            "check_in": "2027-06-01",
                            "check_out": "2027-06-03",
                            "room_type": "Deluxe",
                        },
                    )
                ],
            )

        # ----------------------------------------------------
        # Second call -> verify tool result
        # ----------------------------------------------------

        tool_result_msg = [
            message
            for message in messages
            if message.get("role") == "tool"
        ][-1]

        assert (
            "available_rooms"
            in tool_result_msg["content"]
        )

        return LLMReply(
            content="Yes, a Deluxe room is available.",
            tool_calls=[],
        )

    with patch(
        "app.agents.conversation.call_llm",
        side_effect=fake_llm,
    ):

        res = client.post(
            "/ai/chat",
            json={
                "session_id": "test3",
                "message": "Is a Deluxe room free?",
            },
        )

    assert res.status_code == 200

    assert (
        res.json()["reply"]
        == "Yes, a Deluxe room is available."
    )

    assert call_count["n"] == 2


# ============================================================
# Session Persistence
# ============================================================

def test_chat_session_persists_across_turns(client):

    with patch(
        "app.agents.conversation.call_llm"
    ) as mock_llm:

        mock_llm.return_value = LLMReply(
            content="ok",
            tool_calls=[],
        )

        client.post(
            "/ai/chat",
            json={
                "session_id": "test4",
                "message": "first message",
            },
        )

        client.post(
            "/ai/chat",
            json={
                "session_id": "test4",
                "message": "second message",
            },
        )

    second_call_messages = (
        mock_llm.call_args_list[1][0][0]
    )

    user_messages = [
        message["content"]
        for message in second_call_messages
        if message["role"] == "user"
    ]

    assert "first message" in user_messages

    assert "second message" in user_messages


# ============================================================
# Tool Error
# ============================================================

def test_chat_tool_error_does_not_crash_turn(client):
    """
    A tool called with invalid data should return an error
    to the LLM instead of crashing the request.
    """

    call_count = {
        "n": 0
    }

    def fake_llm(
        messages,
        tools,
    ):

        call_count["n"] += 1

        if call_count["n"] == 1:

            return LLMReply(
                content=None,
                tool_calls=[
                    ToolCall(
                        id="call_1",
                        name="get_room_details",
                        arguments={
                            "room_id": 99999
                        },
                    )
                ],
            )

        tool_result_msg = [
            message
            for message in messages
            if message.get("role") == "tool"
        ][-1]

        assert (
            "error"
            in tool_result_msg["content"]
        )

        return LLMReply(
            content="Sorry, I couldn't find that room.",
            tool_calls=[],
        )

    with patch(
        "app.agents.conversation.call_llm",
        side_effect=fake_llm,
    ):

        res = client.post(
            "/ai/chat",
            json={
                "session_id": "test5",
                "message": "tell me about room 99999",
            },
        )

    assert res.status_code == 200

    assert (
        "couldn't find"
        in res.json()["reply"]
    )


# ============================================================
# Multilingual Language Hint
# ============================================================

def test_chat_multilingual_language_hint_affects_system_prompt(
    client,
):

    captured = []

    def fake_llm(
        messages,
        tools,
    ):

        captured.append(
            messages[0]["content"]
        )

        return LLMReply(
            content="ok",
            tool_calls=[],
        )

    with patch(
        "app.agents.conversation.call_llm",
        side_effect=fake_llm,
    ):

        client.post(
            "/ai/chat",
            json={
                "session_id": "test6",
                "message": "hi",
                "detected_language": "hi",
            },
        )

    # IMPORTANT:
    #
    # The system prompt contains:
    #
    # The customer has been speaking
    # Hindi
    # in this conversation.
    #
    # "speaking Hindi" is NOT one continuous substring
    # because "Hindi" is on the next line.
    #
    # Therefore verify the meaningful parts separately.

    assert (
        "The customer has been speaking"
        in captured[0]
    )

    assert (
        "Hindi"
        in captured[0]
    )

    assert (
        "Continue replying in"
        in captured[0]
    )


# ============================================================
# Date Validation - Future Dates
# ============================================================

def test_validate_booking_dates_accepts_future_dates():

    result = validate_booking_dates(
        check_in="2027-06-01",
        check_out="2027-06-03",
    )

    assert "error" not in result


# ============================================================
# Date Validation - Past Dates
# ============================================================

def test_validate_booking_dates_rejects_past_dates():

    result = validate_booking_dates(
        check_in="2025-08-01",
        check_out="2025-08-03",
    )

    assert "error" in result

    assert (
        "past"
        in result["error"].lower()
    )


# ============================================================
# Date Validation - Invalid Range
# ============================================================

def test_validate_booking_dates_rejects_invalid_range():

    result = validate_booking_dates(
        check_in="2027-06-05",
        check_out="2027-06-03",
    )

    assert "error" in result

    assert (
        "check_out"
        in result["error"]
        or "after"
        in result["error"].lower()
    )


# ============================================================
# Availability - Past Dates
# ============================================================

def test_check_room_availability_rejects_past_dates():

    result = check_room_availability(
        check_in="2025-08-01",
        check_out="2025-08-03",
        room_type="Deluxe",
        adults=2,
    )

    assert "error" in result

    assert (
        "past"
        in result["error"].lower()
    )


# ============================================================
# Date Validation Tool Error Flows To LLM
# ============================================================

def test_chat_date_validation_tool_error_flows_to_llm(
    client,
):

    call_count = {
        "n": 0
    }

    def fake_llm(
        messages,
        tools,
    ):

        call_count["n"] += 1

        # ----------------------------------------------------
        # First LLM call
        # ----------------------------------------------------

        if call_count["n"] == 1:

            return LLMReply(
                content=None,
                tool_calls=[
                    ToolCall(
                        id="date_call_1",
                        name="validate_booking_dates",
                        arguments={
                            "check_in": "2025-08-01",
                            "check_out": "2025-08-03",
                        },
                    )
                ],
            )

        # ----------------------------------------------------
        # Second LLM call
        # ----------------------------------------------------

        tool_result_msg = [
            message
            for message in messages
            if message.get("role") == "tool"
        ][-1]

        assert (
            "error"
            in tool_result_msg["content"]
        )

        return LLMReply(
            content=(
                "Those dates are in the past. "
                "Please provide future check-in "
                "and check-out dates."
            ),
            tool_calls=[],
        )

    with patch(
        "app.agents.conversation.call_llm",
        side_effect=fake_llm,
    ):

        res = client.post(
            "/ai/chat",
            json={
                "session_id": "date-test-001",
                "message": (
                    "I want to book a room "
                    "from August 1 to August 3, 2025."
                ),
            },
        )

    assert res.status_code == 200

    assert (
        "past"
        in res.json()["reply"].lower()
    )

    assert call_count["n"] == 2