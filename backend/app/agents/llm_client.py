"""
LLM client - provider-abstracted chat/tool-calling layer.

Phase 9.5 hardening:
- Supports Ollama and OpenAI through the OpenAI-compatible client.
- Normalizes structured tool calls.
- Parses Qwen/Ollama textual tool-call formats defensively.
- Never lets raw provider tool syntax leak to the customer.
"""

import json
import re
from dataclasses import dataclass, field

from openai import OpenAI

from app.config import settings

_OLLAMA_DUMMY_API_KEY = "ollama-local-no-key-required"


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class LLMReply:
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)


_openai_client: OpenAI | None = None
_ollama_client: OpenAI | None = None
_groq_client: OpenAI | None = None

def _get_groq_client() -> OpenAI:
    global _groq_client

    if not settings.LLM_API_KEY:
        raise RuntimeError(
            "LLM_API_KEY is not set. Add your Groq API key to Railway variables."
        )

    if not settings.LLM_BASE_URL:
        raise RuntimeError(
            "LLM_BASE_URL is not set. Add the Groq OpenAI-compatible base URL."
        )

    if _groq_client is None:
        _groq_client = OpenAI(
            base_url=settings.LLM_BASE_URL,
            api_key=settings.LLM_API_KEY,
        )

    return _groq_client


def _get_openai_client() -> OpenAI:
    global _openai_client
    if not settings.OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Add it to your .env file, "
            "or set LLM_PROVIDER=ollama in .env to use a local model for chat instead."
        )
    if _openai_client is None:
        _openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _openai_client


def _get_ollama_client() -> OpenAI:
    global _ollama_client
    if _ollama_client is None:
        _ollama_client = OpenAI(
            base_url=settings.OLLAMA_BASE_URL,
            api_key=_OLLAMA_DUMMY_API_KEY,
        )
    return _ollama_client


def _get_active_client_and_model() -> tuple[OpenAI, str]:
    provider = settings.LLM_PROVIDER

    if provider == "ollama":
        return _get_ollama_client(), settings.OLLAMA_MODEL

    if provider == "openai":
        return _get_openai_client(), "gpt-4o-mini"

    if provider == "groq":
        return _get_groq_client(), settings.LLM_MODEL

    raise RuntimeError(
        f"Unknown LLM_PROVIDER '{provider}'. "
        "Set it to 'openai', 'ollama', or 'groq' in .env."
    ) 


def get_client() -> OpenAI:
    return _get_openai_client()


def _normalize_tool_call_arguments(raw_arguments) -> dict:
    if isinstance(raw_arguments, dict):
        return raw_arguments
    if isinstance(raw_arguments, str):
        if not raw_arguments.strip():
            return {}
        try:
            parsed = json.loads(raw_arguments)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"LLM returned tool arguments that are not valid JSON: {raw_arguments!r}"
            ) from exc
        if not isinstance(parsed, dict):
            raise RuntimeError("LLM tool arguments JSON must be an object.")
        return parsed
    raise RuntimeError(f"Unexpected tool arguments type from LLM: {type(raw_arguments)}")


def _tool_names(tools: list[dict] | None) -> set[str]:
    names: set[str] = set()
    for tool in tools or []:
        fn = tool.get("function", {}) if isinstance(tool, dict) else {}
        name = fn.get("name")
        if isinstance(name, str) and name:
            names.add(name)
    return names


def _parse_one_json_object(text: str, start: int) -> tuple[dict | None, int]:
    """Parse one JSON object from text starting at an opening '{'."""
    try:
        decoder = json.JSONDecoder()
        value, consumed = decoder.raw_decode(text[start:])
        if isinstance(value, dict):
            return value, start + consumed
    except json.JSONDecodeError:
        pass
    return None, start


def _parse_textual_tool_calls(
    content: str | None,
    tools: list[dict] | None = None,
) -> tuple[str | None, list[ToolCall]]:
    """
    Parse both normal Qwen markers and common marker-less provider output.

    Supported examples:

      <tool_call>{"name":"check_room_availability", "arguments": {...}}</tool_call>

      check_room_availability {"check_in":"2027-12-20", ...}

      autocall_get_hotel_information {"topic":"wifi"}

    The last form is important: it has appeared in local Qwen/Ollama output.
    It is an internal model representation and must never be shown to the user.
    """
    if not content or not content.strip():
        return content, []

    known_names = _tool_names(tools)
    tool_calls: list[ToolCall] = []
    consumed_spans: list[tuple[int, int]] = []

    # ------------------------------------------------------------
    # 1. Standard <tool_call> blocks.
    # ------------------------------------------------------------
    for match in re.finditer(r"<tool_call>(.*?)</tool_call>", content, re.IGNORECASE | re.DOTALL):
        block = match.group(1)
        brace = block.find("{")
        if brace < 0:
            continue
        parsed, _ = _parse_one_json_object(block, brace)
        if not parsed:
            continue
        name = parsed.get("name")
        arguments = parsed.get("arguments", {})
        if isinstance(name, str) and name in known_names and isinstance(arguments, dict):
            tool_calls.append(
                ToolCall(
                    id=f"text-tool-call-{len(tool_calls) + 1}",
                    name=name,
                    arguments=arguments,
                )
            )
            consumed_spans.append(match.span())

    # ------------------------------------------------------------
    # 2. Marker-less tool output.
    # ------------------------------------------------------------
    if not tool_calls and known_names:
        # Longest names first prevents accidental partial matches.
        names_pattern = "|".join(re.escape(n) for n in sorted(known_names, key=len, reverse=True))
        pattern = re.compile(
            rf"(?:autocall[_\s]+)?({names_pattern})\s*(\{{)",
            re.IGNORECASE,
        )
        for match in pattern.finditer(content):
            name = match.group(1)
            # Recover canonical case from the registered tool names.
            canonical = next((n for n in known_names if n.lower() == name.lower()), name)
            parsed, end = _parse_one_json_object(content, match.start(2))
            if not parsed:
                continue
            arguments = parsed.get("arguments") if "arguments" in parsed else parsed
            if not isinstance(arguments, dict):
                continue
            tool_calls.append(
                ToolCall(
                    id=f"text-tool-call-{len(tool_calls) + 1}",
                    name=canonical,
                    arguments=arguments,
                )
            )
            consumed_spans.append((match.start(), end))

    if not tool_calls:
        # Remove orphan markers from content if a malformed provider response
        # contained them, but do not attempt to invent a tool call.
        cleaned = re.sub(r"</?tool_call>", "", content, flags=re.IGNORECASE).strip()
        return cleaned or None, []

    # Remove internal tool syntax from the visible assistant content.
    pieces: list[str] = []
    cursor = 0
    for start, end in sorted(consumed_spans):
        if start > cursor:
            pieces.append(content[cursor:start])
        cursor = max(cursor, end)
    if cursor < len(content):
        pieces.append(content[cursor:])

    cleaned = "\n".join(p.strip() for p in pieces if p.strip())
    # Never expose a bare internal tool invocation as an assistant message.
    if re.search(r"(?:autocall[_\s]+)?[a-zA-Z_]+\s*\{", cleaned):
        cleaned = None

    return cleaned or None, tool_calls


def _normalize_message(raw_message, tools: list[dict] | None = None) -> LLMReply:
    raw_tool_calls = getattr(raw_message, "tool_calls", None) or []
    tool_calls: list[ToolCall] = []

    for tc in raw_tool_calls:
        tc_type = getattr(tc, "type", "function")
        if tc_type != "function" or not hasattr(tc, "function"):
            raise RuntimeError(
                f"Received unsupported tool call type '{tc_type}' from the LLM "
                f"(id={getattr(tc, 'id', '?')}). Only function-type tools are supported."
            )
        tool_calls.append(
            ToolCall(
                id=tc.id,
                name=tc.function.name,
                arguments=_normalize_tool_call_arguments(tc.function.arguments),
            )
        )

    raw_content = getattr(raw_message, "content", None)

    if not tool_calls:
        cleaned_content, textual_tool_calls = _parse_textual_tool_calls(raw_content, tools)
        if textual_tool_calls:
            return LLMReply(content=cleaned_content, tool_calls=textual_tool_calls)
        return LLMReply(content=cleaned_content, tool_calls=[])

    return LLMReply(content=raw_content, tool_calls=tool_calls)


def call_llm(messages: list[dict], tools: list[dict]) -> LLMReply:
    client, model = _get_active_client_and_model()

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )
    except Exception as e:
        provider = settings.LLM_PROVIDER
        if provider == "ollama":
            raise RuntimeError(
                f"Could not reach Ollama at {settings.OLLAMA_BASE_URL} "
                f"(model '{settings.OLLAMA_MODEL}'). Is Ollama running and has the model "
                f"been pulled ('ollama pull {settings.OLLAMA_MODEL}')? Original error: {e}"
            ) from e
        if provider == "groq":
            raise RuntimeError(
                f"Groq API request failed: {e}"
            ) from e

        raise RuntimeError(f"OpenAI API request failed: {e}") from e
    raw_message = response.choices[0].message
    return _normalize_message(raw_message, tools)
