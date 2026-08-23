# AI Hotel Booking Agent — Phases 1–7 (+ Ollama migration)

This is the project so far: FastAPI backend connected to MySQL, database
schema seeded with sample data, working CRUD APIs, an AI conversational
layer with tool/function calling, speech-to-text / text-to-speech, a
browser-based voice UI, and real inbound phone call handling via Twilio.

**Current default AI chat provider: Ollama** (local, free, no API credits
needed). OpenAI remains fully supported as a drop-in alternative - see
"Phase 4 setup" below. Text-to-speech always uses OpenAI regardless of
this setting.

## Prerequisites

- Python 3.10+ installed
- MySQL Server running locally (either installed directly, or via Docker)
- VS Code with the Python extension

## Setup (in VS Code's integrated terminal)

1. Open this folder in VS Code (`File > Open Folder`).

2. Start MySQL. Pick ONE option:

   **Option A — Docker (recommended):**
   ```bash
   docker compose up -d
   ```

   **Option B — MySQL already installed locally:**
   Just make sure the MySQL service is running, then create the database
   and user manually to match `.env`:
   ```sql
   CREATE DATABASE hotel_ai;
   CREATE USER 'hotel_user'@'localhost' IDENTIFIED BY 'hotel_pass_dev';
   GRANT ALL PRIVILEGES ON hotel_ai.* TO 'hotel_user'@'localhost';
   FLUSH PRIVILEGES;
   ```

3. Create and activate a virtual environment:
   ```bash
   cd backend
   python -m venv venv
   ```
   - Windows: `venv\Scripts\activate`
   - Mac/Linux: `source venv/bin/activate`

   In VS Code, also select this venv as your interpreter:
   `Ctrl+Shift+P` → "Python: Select Interpreter" → choose `./backend/venv`.

4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

5. Create the tables and seed sample data:
   ```bash
   python -m app.database.seed
   ```
   Expected output:
   ```
   Creating tables (if they don't already exist)...
   Tables ready.
   Inserted 6 sample rooms.
   Inserted 6 hotel info entries.
   Seed complete.
   ```

6. Run the server:
   ```bash
   uvicorn app.main:app --reload
   ```

7. Check it's working — open in your browser or `curl`:
   - http://localhost:8000/ → `{"status":"ok","message":"AI Hotel Booking Agent backend is running"}`
   - http://localhost:8000/health/db → `{"status":"ok","database":"connected"}`
   - http://localhost:8000/docs → interactive Swagger UI (FastAPI gives you this for free)

## API endpoints (Phase 3)

| Method | Path | Purpose |
|---|---|---|
| GET | `/rooms` | List every room |
| GET | `/rooms/availability?check_in=&check_out=&room_type=&adults=` | Rooms actually free for the date range (real overlap check, not a status flag) |
| POST | `/bookings` | Create a booking (re-validates availability, checks capacity, computes total) |
| GET | `/bookings/{booking_id}` | Look up a booking by its `BKxxxx` code |
| PUT | `/bookings/{booking_id}` | Modify dates/guest counts, re-checked against other bookings |
| DELETE | `/bookings/{booking_id}` | Cancel a booking (frees the room back up) |

Try them interactively at `http://localhost:8000/docs` once the server is running.

### Example: create a booking
```bash
curl -X POST http://localhost:8000/bookings \
  -H "Content-Type: application/json" \
  -d '{"customer_name":"Rahul","customer_phone":"9999999999","room_id":2,"check_in":"2026-08-10","check_out":"2026-08-12","adults":2,"children":0}'
```

## Project structure

```
backend/
├── app/
│   ├── main.py              # FastAPI app, health-check + routers
│   ├── config.py            # loads .env into a Settings object
│   ├── database/
│   │   ├── db.py            # SQLAlchemy engine/session setup
│   │   └── seed.py          # creates tables + inserts sample data
│   ├── models/               # SQLAlchemy ORM tables
│   │   ├── room.py
│   │   ├── customer.py
│   │   ├── booking.py
│   │   └── hotel_info.py
│   ├── schemas/               # Pydantic request/response shapes
│   │   ├── room.py
│   │   └── booking.py
│   ├── services/               # business logic (no DB writes happen outside here)
│   │   ├── availability.py     # the date-overlap query - single source of truth
│   │   └── booking_service.py  # booking creation, booking_id generation
│   └── api/                     # route handlers
│       ├── rooms.py
│       └── bookings.py
└── requirements.txt
```

## Testing procedure for Phase 3

1. Confirm dates work: `GET /rooms/availability?check_in=2026-08-10&check_out=2026-08-12`
2. Create a booking for one of the returned rooms via `POST /bookings`.
3. Re-run the same availability query — that room should no longer appear.
4. Try to `POST /bookings` again for the same room with overlapping dates — expect `409`.
5. Try booking with more guests than the room's capacity — expect `422`.
6. `DELETE /bookings/{booking_id}` to cancel, then re-run the availability query — the room should reappear.
7. `GET /bookings/{booking_id}` for a code that doesn't exist — expect `404`.

## Troubleshooting

- `/health/db` returns `"database": "not connected"` → check the `detail`
  field in the response, it will usually say exactly what's wrong (wrong
  password, MySQL not running, wrong port).
- `ModuleNotFoundError: No module named 'app'` → make sure you're running
  `uvicorn` and `python -m app.database.seed` from inside the `backend/`
  folder, not the project root.
- Port 3306 already in use → you probably have another MySQL instance
  running. Either stop it, or change `MYSQL_PORT` in `.env` and in
  `docker-compose.yml`.

## Phase 4 setup: AI chat

**As of the Phase 4 -> Ollama migration, the default chat provider is
Ollama (free, local, no API credits needed).** OpenAI remains fully
supported as an alternative - see "Switching providers" below. Text-to-speech
(Phase 5/7) always uses real OpenAI regardless of this setting; that's
covered separately in the Phase 5 section.

### Option A (default): Ollama, local and free

1. Install Ollama:
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ```
2. Pull the model:
   ```bash
   ollama pull qwen2.5:7b-instruct
   ```
3. Start Ollama (usually auto-starts as a background service after install;
   if not):
   ```bash
   ollama serve
   ```
4. Confirm `.env` has:
   ```
   LLM_PROVIDER=ollama
   OLLAMA_BASE_URL=http://localhost:11434/v1
   OLLAMA_MODEL=qwen2.5:7b-instruct
   ```
5. Install dependencies and start the server:
   ```bash
   pip install -r requirements.txt
   uvicorn app.main:app --reload
   ```

### Option B: OpenAI instead

1. Get an OpenAI API key from https://platform.openai.com/api-keys
2. Set in `.env`:
   ```
   OPENAI_API_KEY=sk-...your key...
   LLM_PROVIDER=openai
   ```
3. Restart the server.

### Switching providers

Just change `LLM_PROVIDER` in `.env` and restart the server - `run_turn()`,
`/ai/chat`'s request/response contract, tool calling, and session memory
all behave identically regardless of which provider is active. Nothing
else in the codebase needs to change or know which one you picked.

### Endpoint

| Method | Path | Purpose |
|---|---|---|
| POST | `/ai/chat` | Send a message, get the AI's reply. Body: `{"session_id": "...", "message": "..."}` |

`session_id` can be any string you pick (e.g. a UUID per browser tab / caller).
Conversation history is kept in memory per session_id, so send the SAME
session_id on every message in one conversation.

### Example conversation via curl

```bash
curl -X POST http://localhost:8000/ai/chat -H "Content-Type: application/json" \
  -d '{"session_id":"demo1","message":"Hi, I want to book a room for tomorrow, 2 adults"}'

# use the SAME session_id to continue the conversation
curl -X POST http://localhost:8000/ai/chat -H "Content-Type: application/json" \
  -d '{"session_id":"demo1","message":"Deluxe please"}'
```

### New structure

```
backend/app/
├── agents/
│   ├── tools.py          # the ONLY functions the LLM may call; wraps services/
│   ├── llm_client.py      # provider-abstracted chat client (OpenAI or Ollama),
│   │                       # normalizes both into LLMReply / ToolCall
│   └── conversation.py    # system prompt, session memory, tool-calling loop -
│                            # consumes only the normalized LLMReply/ToolCall,
│                            # has no idea which provider actually answered
├── schemas/chat.py         # ChatRequest / ChatResponse
└── api/chat.py              # POST /ai/chat
```

### Why this design

The LLM never runs SQL and never imports a model directly - it can only
call the 7 functions listed in `TOOL_SCHEMAS`. Each of those functions
calls into `app/services/`, the same layer the REST API uses. That means
availability logic, booking creation, and capacity checks behave
identically whether a booking comes from `POST /bookings` or from the AI
conversation - there's exactly one source of truth.

On top of that, `llm_client.py` normalizes whatever the active provider
returns into a plain `LLMReply`/`ToolCall` shape before `conversation.py`
ever sees it. `conversation.py` has zero provider-specific code - it
doesn't know or care whether OpenAI or Ollama produced the reply. This is
what makes switching providers a one-line `.env` change instead of a
code change, and what protects against needing another migration if a
third provider gets added later.

Ollama specifically works through this same path because it exposes an
OpenAI-compatible `/v1/chat/completions` endpoint (including tool
calling for supported models) - `llm_client.py` reuses the official
`openai` Python SDK as the transport for both providers, just pointed at
a different `base_url`/`api_key`/model depending on `LLM_PROVIDER`.

### Testing procedure for Phase 4

1. With Ollama not running (or `OPENAI_API_KEY` unset if using the OpenAI
   provider), call `/ai/chat` - expect a `503` with a clear, specific
   message (e.g. "Is Ollama running?"), not a crash.
2. Start Ollama / set your API key as appropriate, restart the server.
3. Start a conversation: "I want to book a room for 2 adults tomorrow."
   The AI should ask for missing details (room type or dates if ambiguous)
   rather than inventing them.
4. Confirm a room - the AI should call `create_booking_tool` and read back
   a real `booking_id`. Verify it in the database or via
   `GET /bookings/{booking_id}`.
5. Ask "what time is check-in?" - the AI should call `get_hotel_information`,
   not answer from general knowledge.
6. Ask to cancel a booking by ID - confirm it actually flips to `cancelled`
   in the database.
7. Try giving info across multiple messages ("Deluxe room" then later
   "for tomorrow") - the AI shouldn't re-ask for what you already gave it,
   since the full history is kept per `session_id`.
8. **If using Ollama specifically:** local 7-8B models are noticeably less
   reliable at tool-calling than GPT-4o-mini - watch for the AI stating
   availability/prices without actually calling `check_room_availability`
   first, which the system prompt explicitly forbids. If you see this
   happening, it's worth testing a larger model or switching back to
   `LLM_PROVIDER=openai` for comparison.

### Known limitation (by design, for now)

Conversation history lives in an in-memory Python dict (`_sessions` in
`conversation.py`). Restarting the server clears all conversations, and
this won't work correctly if you ever run multiple server processes at
once. Fine for local development; we'll revisit this if/when we deploy
with multiple workers (Phase 9).

## Phase 5 setup: Speech-to-Text & Text-to-Speech

STT uses **faster-whisper**, which runs locally on your machine (no
per-request API cost). On first use it downloads model weights (~150MB
for the 'base' model) from Hugging Face - this needs a real internet
connection once; after that it's cached on disk and works offline.

TTS uses the **OpenAI TTS API** - this is independent of `LLM_PROVIDER`
and always requires a real `OPENAI_API_KEY` in `.env`, even if you're
using Ollama for chat. TTS has its own dedicated OpenAI client
(`app/services/tts_service.py`) that never touches the chat provider
setting, so switching `LLM_PROVIDER` between `ollama` and `openai` never
affects voice output one way or the other.

If you're running Ollama for chat and don't have an `OPENAI_API_KEY`,
`/ai/chat` will work fine but `/voice/synthesize` (and therefore spoken
replies in Phase 6/7) will return a `503` until you add one.

1. Install the new dependencies (already in requirements.txt):
   ```bash
   pip install -r requirements.txt
   ```
2. Restart the server: `uvicorn app.main:app --reload`

### Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/voice/transcribe` | Upload an audio file (multipart/form-data, field name `file`) -> returns `{"text": "..."}` |
| POST | `/voice/synthesize` | `{"text": "...", "voice": "alloy"}` -> returns raw MP3 audio bytes |

### Example via curl

```bash
# Transcribe (record a short WAV/MP3 first, e.g. with your phone's voice memo app)
curl -X POST http://localhost:8000/voice/transcribe -F "file=@my_recording.wav"

# Synthesize - saves the reply as an MP3 you can play
curl -X POST http://localhost:8000/voice/synthesize \
  -H "Content-Type: application/json" \
  -d '{"text":"Your Deluxe Room has been booked. Your booking ID is BK1024."}' \
  --output reply.mp3
```

### New structure

```
backend/app/
├── services/
│   ├── stt_service.py   # faster-whisper wrapper, lazy model loading
│   └── tts_service.py    # OpenAI TTS wrapper
├── schemas/voice.py        # TranscribeResponse, SynthesizeRequest
└── api/voice.py              # POST /voice/transcribe, POST /voice/synthesize
```

### Testing procedure for Phase 5

1. `POST /voice/synthesize` with empty text -> expect `422`.
2. `POST /voice/transcribe` with an empty file -> expect `422`.
3. Record yourself saying something like "I want to book a Deluxe room for
   two adults tomorrow" as a WAV or MP3, and POST it to `/voice/transcribe`.
   The first call will be slow (downloading the model) - expect it to
   speed up on subsequent calls.
4. Check the returned text roughly matches what you said.
5. POST that same text to `/ai/chat`, then feed the reply into
   `/voice/synthesize` and play the resulting MP3 - confirm it sounds
   natural.
6. Try an unusual accent, background noise, or a long pause mid-sentence,
   and see how the transcription holds up - this is where you'll judge if
   `base` model size is enough or if you need to bump up to `small`.

### A transparency note on how this phase was built

I don't have access to Hugging Face or the OpenAI API from my sandbox
here, so I built and tested the endpoint logic, file-upload handling,
input validation, and error handling thoroughly - but I could not run a
real transcription or hear real synthesized audio. I confirmed the
failure paths behave correctly (clean `503` errors, not crashes) when
those services are unreachable, since that's exactly the situation I'm
in. You are the first real test of actual voice quality - if the `base`
Whisper model isn't accurate enough, or a synthesized voice sounds off,
tell me and we'll tune model size / voice choice.

## Phase 6 setup: Browser voice UI

No new dependencies or env vars - this phase is pure frontend, talking to
the backend endpoints you already built.

1. Make sure the backend is running: `uvicorn app.main:app --reload` (from `backend/`)
2. Serve the frontend as static files (don't just double-click `index.html` -
   `getUserMedia` for the microphone requires a proper origin, not `file://`):
   ```bash
   cd frontend
   python3 -m http.server 5500
   ```
3. Open `http://localhost:5500/index.html` in your browser.

### What's in the UI

- **Hold-to-talk mic** - press and hold the brass circle, speak, release.
  Recorded audio goes to `/voice/transcribe`, the text goes to `/ai/chat`,
  and the reply is spoken back via `/voice/synthesize`.
- **Text fallback** - the input box at the bottom sends straight to
  `/ai/chat` with no audio involved. Useful for testing the AI's logic
  without needing a working microphone/TTS setup.
- **Room type sidebar** - pulled live from `GET /rooms` on page load.
- **Session control** - each browser session gets a random `session_id`;
  "New conversation" resets it (matching the in-memory session store from
  Phase 4 - a fresh ID means the AI has no memory of the old conversation).
- Errors (no mic permission, no API key, transcription failure, etc.)
  appear inline in the transcript instead of breaking the page.

### New structure

```
frontend/
├── index.html    # reception-desk layout: mic panel + conversation ledger
├── styles.css     # ink-navy / brass visual identity
└── script.js       # recording, the transcribe -> chat -> synthesize chain, text fallback
```

### Testing procedure for Phase 6

1. Load the page - confirm the room type list populates from the real database.
2. Type a message in the text box and send it - confirm you get a real AI reply
   (needs either Ollama running, or `OPENAI_API_KEY` set with `LLM_PROVIDER=openai` -
   see Phase 4).
3. Hold the mic button and say something - release it and watch the status
   text change: "Listening…" -> "Transcribing…" -> "Speaking…" -> "Tap to speak".
4. Confirm what you said was transcribed correctly and the AI responded
   sensibly, and that you can hear the spoken reply.
5. Deny microphone permission (or test in a browser tab where it's blocked)
   - confirm you get a clear inline message, not a silent failure.
6. Click "New conversation" mid-chat, then ask something that depended on
   earlier context - confirm the AI no longer remembers it (proving the
   session actually reset).
7. Have a full conversation start to finish: ask availability, pick a
   room, give your name and phone number, get a real booking ID read back
   to you. Verify that booking exists via `GET /bookings/{booking_id}`.

### How I tested this without a microphone or working STT/TTS network access

I used Playwright (a browser automation tool) with a fake virtual
microphone device to drive the actual UI in a real Chromium browser:
confirmed the room list loads from the live database, confirmed the
mic button correctly enters/exits its "listening" state on press/release,
confirmed a recorded clip is correctly sent to `/voice/transcribe`, and
confirmed the text-only conversation path works end-to-end through
`/ai/chat` with errors displayed cleanly in the transcript. What I could
not verify is real transcription accuracy or how the synthesized voice
actually sounds - same limitation as Phase 5, for the same reason
(no Hugging Face / OpenAI network access in this sandbox). You're doing
the real audio test on your machine.

## Phase 7 setup: Real phone calls (Twilio)

### 1. Get a Twilio trial account and phone number
1. Sign up at https://www.twilio.com/try-twilio (free trial gives you credit and a number).
2. From the Twilio Console dashboard, copy your **Account SID** and **Auth Token**.
3. Buy/claim a trial phone number under Phone Numbers -> Manage -> Buy a number
   (any number with Voice capability works).

### 2. Expose your local server to the internet
Twilio needs a real public URL to send webhooks to - `localhost` means
nothing to Twilio's servers. Use ngrok for local development:
```bash
# install ngrok (https://ngrok.com/download), then:
ngrok http 8000
```
This prints a public URL like `https://a1b2c3d4.ngrok-free.app`. Keep this
terminal open while testing - the URL changes every time you restart ngrok
on a free plan.

### 3. Configure your `.env`
```
TWILIO_ACCOUNT_SID=AC...your sid...
TWILIO_AUTH_TOKEN=...your auth token...
PUBLIC_BASE_URL=https://a1b2c3d4.ngrok-free.app
```
Restart the backend after changing `.env`.

### 4. Point your Twilio number at your webhook
In the Twilio Console: Phone Numbers -> your number -> **Voice Configuration**:
- "A call comes in" -> Webhook -> `https://a1b2c3d4.ngrok-free.app/telephony/incoming` -> HTTP POST

Save.

### 5. Call it
Dial your Twilio number from any phone. You should hear the AI greeting,
be able to speak naturally, and get a real spoken response back.

### How the call flow works

```
Customer dials Twilio number
        |
Twilio POSTs to  /telephony/incoming
        |
We reply with TwiML: greet + <Gather> (start listening)
        |
Twilio transcribes the customer's speech itself (built-in ASR,
tuned for phone-quality audio) and POSTs the text to /telephony/gather
        |
We run that text through the SAME run_turn() engine as /ai/chat,
using the call's CallSid as the session_id
        |
We synthesize the reply with our own TTS, cache the audio, and reply
with TwiML: <Play> that audio + <Gather> again for the next turn
        |
Loop continues until the caller hangs up or a Gather times out
```

Reusing `run_turn()` (the exact same function `/ai/chat` uses) means a
booking made over the phone behaves identically to one made through the
browser or a direct API call - same tools, same database, same rules.

### Critical reliability rule

Every route in `app/api/telephony.py` catches its own exceptions and
**always** returns valid TwiML with a `200` status, never a raw JSON
error. If a webhook ever returns something Twilio can't parse as TwiML,
the caller hears a dead line or a generic error tone with zero
explanation - unacceptable for a real receptionist. I verified this by
simulating a total AI failure (no `OPENAI_API_KEY` set) and confirming
the caller still gets a graceful, valid, speakable response asking them
to try again - never a broken call.

### Security: verifying requests really came from Twilio

`app/api/telephony.py` includes signature validation using
`TWILIO_AUTH_TOKEN` - without it, anyone who discovers your public
webhook URL could POST fake "customer speech" directly and trigger real
bookings or cancellations without ever calling the hotel.

**This validation is automatically skipped if `TWILIO_AUTH_TOKEN` is
unset** (so local testing without a real Twilio account still works) -
but that also means it's OFF by default. Once you add your real
`TWILIO_AUTH_TOKEN` to `.env` in step 3 above, validation turns on
automatically. Do not expose this publicly with an empty
`TWILIO_AUTH_TOKEN`.

### New structure

```
backend/app/
└── api/telephony.py
    ├── POST /telephony/incoming     # call starts - greet + start listening
    ├── POST /telephony/gather        # customer's speech arrives as text
    ├── GET  /telephony/audio/{id}.mp3 # serves generated reply audio to Twilio
    └── POST /telephony/status         # optional call status callbacks
```

### Testing procedure for Phase 7

1. Without a real Twilio account, simulate its webhooks with curl (exactly
   what I did - see below) to confirm the TwiML is well-formed.
2. With the active chat provider unavailable (Ollama not running, or
   `OPENAI_API_KEY` unset if `LLM_PROVIDER=openai`), POST to `/telephony/gather`
   with some `SpeechResult` text - confirm you still get valid TwiML back (a
   graceful "trouble processing" message), not a crash. This proves the
   call would survive a real AI outage.
3. Once you have a Twilio account + ngrok tunnel configured, call your
   number for real. Have a full conversation: ask about room availability,
   book a room, get a spoken booking ID back.
4. Verify that booking exists via `GET /bookings/{booking_id}`.
5. Call again and ask to cancel that booking by ID - confirm it actually
   cancels in the database.
6. Try staying silent after the greeting - confirm you get the
   "didn't catch that" reprompt, not a dead call.

```bash
# Simulating Twilio's webhook calls directly, no real phone needed:
curl -X POST http://localhost:8000/telephony/incoming \
  -d "CallSid=CA_test1" -d "From=%2B919999999999"

curl -X POST http://localhost:8000/telephony/gather \
  -d "CallSid=CA_test1" -d "SpeechResult=I want to book a Deluxe room for tomorrow"
```

### A transparency note on how this phase was built

I don't have a Twilio account or a public tunnel available in this
sandbox, so I could not receive a real inbound phone call here. What I
did verify: simulated Twilio's exact webhook request format with curl
and confirmed the TwiML responses are valid XML in every case, including
deliberately breaking the AI layer (no API key) to confirm the call
still gets a graceful spoken response instead of dying. The in-memory
audio cache's store/serve/expire cycle was tested directly. You'll be
doing the first real phone call test - if the ASR mishears you, or a
response feels slow, tell me and we'll tune the Gather settings or
switch strategies (e.g. Twilio Media Streams for lower latency, a bigger
Phase 9 topic).

### Known limitations (by design, for now)

- The audio cache (`_audio_cache`) and conversation memory (`_sessions`
  from Phase 4) are both plain in-memory Python dicts - fine for one
  local server process, not safe for multiple workers/instances. Flagged
  again here since Phase 7 makes this more visible (concurrent calls).
- On a free ngrok plan, your public URL changes every restart, so you'll
  need to re-paste it into Twilio's console each time. A paid ngrok plan
  or a real deployment (Phase 9) fixes this.
- Trial Twilio accounts can only call verified phone numbers and prepend
  a "trial account" disclaimer to calls - upgrade the Twilio account to
  remove this once you're ready for real customers.

## What's next (Phase 8)

Advanced features: multilingual support, booking modification via voice,
and an admin dashboard for hotel staff to see bookings, occupancy, and revenue.
