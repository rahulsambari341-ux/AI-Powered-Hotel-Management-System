/* ============================================================
   ABC Hotel — AI Reception Desk
   Chains: mic -> /voice/transcribe -> /ai/chat -> /voice/synthesize -> speaker
   Also supports typed text as a fallback / for testing without a mic.
   ============================================================ */

const API_BASE = window.HOTEL_API_BASE || "http://localhost:8000";

const micButton     = document.getElementById("micButton");
const micStatus     = document.getElementById("micStatus");
const transcript     = document.getElementById("transcript");
const roomTypeList   = document.getElementById("roomTypeList");
const sessionIdLabel = document.getElementById("sessionIdLabel");
const resetButton    = document.getElementById("resetButton");
const textForm       = document.getElementById("textForm");
const textInput      = document.getElementById("textInput");
const replayAudio    = document.getElementById("replayAudio");

let sessionId = null;
let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;
let isBusy = false; // true while transcribe/chat/synthesize is in flight - blocks overlapping requests

// Voice Call Mode State
let isCallActive = false;
let globalAudioStream = null;
let lastClickTime = 0;
let callGeneration = 0; // Strict token to kill any pending background audio turns on call end

// ---------- session ----------

function newSession() {
  sessionId = "web-" + Math.random().toString(36).slice(2, 10);
  sessionIdLabel.textContent = sessionId;
}

resetButton.addEventListener("click", () => {
  endVoiceCall();
  newSession();
  transcript.innerHTML = "";
  addEntry("ai", "New conversation started. How can I help?");
});

// ---------- transcript rendering ----------

function timeNow() {
  return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function addEntry(role, text, { pending = false, error = false } = {}) {
  const entry = document.createElement("div");
  entry.className = "entry entry--" + (error ? "error" : role);

  const meta = document.createElement("div");
  meta.className = "entry__meta";
  meta.innerHTML =
    `<span class="entry__who">${role === "user" ? "You" : "Reception"}</span>` +
    `<span class="entry__time mono">${timeNow()}</span>`;

  const body = document.createElement("div");
  body.className = "entry__text" + (pending ? " is-pending" : "");
  body.textContent = text;

  entry.appendChild(meta);
  entry.appendChild(body);
  transcript.appendChild(entry);
  transcript.scrollTop = transcript.scrollHeight;
  return body; // returned so callers can update pending text in place
}

// ---------- backend calls ----------

async function transcribeAudio(blob) {
  const form = new FormData();
  form.append("file", blob, "speech.webm");
  const res = await fetch(`${API_BASE}/voice/transcribe`, { method: "POST", body: form });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Could not transcribe audio");
  return {
    text: data.text,
    detectedLanguage: data.language_confident ? data.language : null,
  };
}

async function sendToChat(message, detectedLanguage = null) {
  const res = await fetch(`${API_BASE}/ai/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, message, detected_language: detectedLanguage }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "The AI could not respond");
  return data.reply;
}

async function synthesizeAndPlay(text) {
  const res = await fetch(`${API_BASE}/voice/synthesize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || "Could not synthesize speech");
  }
  const audioBlob = await res.blob();
  replayAudio.src = URL.createObjectURL(audioBlob);
  await replayAudio.play();
  return new Promise((resolve) => {
    replayAudio.onended = resolve;
  });
}

// ---------- the full turn: user text -> chat -> (optional) speech ----------

async function runTurn(userText, { speakReply = false, detectedLanguage = null, currentGen = 0 } = {}) {
  // If it's a voice call turn, check call state validity
  if (speakReply && (!isCallActive || currentGen !== callGeneration)) return;
  if (isBusy) return;
  isBusy = true;

  addEntry("user", userText);
  const pendingBody = addEntry("ai", "…thinking", { pending: true });

  try {
    const reply = await sendToChat(userText, detectedLanguage);
    
    // Check if call was ended during fetch (only if it was a voice call)
    if (speakReply && (!isCallActive || currentGen !== callGeneration)) {
      pendingBody.closest(".entry").remove();
      return;
    }

    pendingBody.textContent = reply;
    pendingBody.classList.remove("is-pending");

    if (speakReply && isCallActive && currentGen === callGeneration) {
      setMicState("speaking", "Speaking…");
      try {
        await synthesizeAndPlay(reply);
      } catch (ttsErr) {
        // Audio playback interrupted
      }
    }
  } catch (err) {
    if (speakReply && (!isCallActive || currentGen !== callGeneration)) return;
    pendingBody.textContent = err.message;
    pendingBody.classList.remove("is-pending");
    pendingBody.closest(".entry").classList.add("entry--error");
  } finally {
    isBusy = false;
    if (speakReply && isCallActive && currentGen === callGeneration) {
      setMicState("listening", "Listening… click mic when done");
      startPersistentRecording();
    } else {
      setMicState("idle", "Tap to speak");
    }
  }
}

// ---------- mic recording ----------

function setMicState(state, statusText) {
  micButton.classList.remove("is-listening", "is-thinking", "is-speaking");
  if (state !== "idle") micButton.classList.add("is-" + state);
  micStatus.textContent = statusText;
}

async function getPersistentStream() {
  if (!globalAudioStream) {
    globalAudioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
  }
  return globalAudioStream;
}

async function startVoiceCall() {
  if (isCallActive) return;

  try {
    const stream = await getPersistentStream();
    isCallActive = true;
    callGeneration++; // New call session token
    const activeGen = callGeneration;
    micButton.title = "End Call (Double-click to hang up)";

    const greeting = "Hey, I'm the voice assistant reception AI of ABC Hotel. How can I help you today?";
    addEntry("ai", greeting);
    setMicState("speaking", "AI speaking…");

    try {
      await synthesizeAndPlay(greeting);
    } catch (e) {
      // Audio playback interrupted/handled
    }

    if (isCallActive && activeGen === callGeneration) {
      setMicState("listening", "Listening…");
      startPersistentRecording();
    }
  } catch (err) {
    isCallActive = false;
    setMicState("idle", "Tap to speak");
  }
}

function endVoiceCall() {
  isCallActive = false;
  isBusy = false;
  isRecording = false;
  callGeneration++; // Invalidate any pending background turns instantly

  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    try { mediaRecorder.stop(); } catch(e) {}
  }
  if (replayAudio) {
    replayAudio.pause();
    replayAudio.currentTime = 0;
  }
  if (globalAudioStream) {
    globalAudioStream.getTracks().forEach((t) => t.stop());
    globalAudioStream = null;
  }
  setMicState("idle", "Tap to speak");
  micButton.title = "Tap to speak";
}

function startPersistentRecording() {
  if (!isCallActive || isBusy || isRecording) return;

  const activeGen = callGeneration;
  getPersistentStream().then((stream) => {
    if (!isCallActive || activeGen !== callGeneration) return;
    audioChunks = [];
    mediaRecorder = new MediaRecorder(stream);
    mediaRecorder.ondataavailable = (e) => audioChunks.push(e.data);
    mediaRecorder.onstop = () => handleRecordingStop(activeGen);
    mediaRecorder.start();
    isRecording = true;
    setMicState("listening", "Listening… click mic when done");
  }).catch((err) => {
    endVoiceCall();
  });
}

function stopPersistentRecording() {
  if (!isRecording || !mediaRecorder) return;
  isRecording = false;
  try {
    mediaRecorder.stop();
  } catch (e) {
    isRecording = false;
  }
}

async function handleRecordingStop(activeGen) {
  if (!isCallActive || activeGen !== callGeneration) return;
  if (audioChunks.length === 0) {
    if (isCallActive && activeGen === callGeneration) {
      setMicState("listening", "Listening…");
      startPersistentRecording();
    }
    return;
  }
  setMicState("thinking", "Transcribing…");
  const blob = new Blob(audioChunks, { type: "audio/webm" });

  try {
    const { text, detectedLanguage } = await transcribeAudio(blob);
    if (!isCallActive || activeGen !== callGeneration) return;
    if (!text) {
      if (isCallActive && activeGen === callGeneration) {
        setMicState("listening", "Didn't catch that — try again");
        startPersistentRecording();
      }
      return;
    }
    await runTurn(text, { speakReply: true, detectedLanguage, currentGen: activeGen });
  } catch (err) {
    if (isCallActive && activeGen === callGeneration) {
      setMicState("listening", "Listening…");
      startPersistentRecording();
    }
  }
}

// Click handling: Single click interrupts AI speech or sends recording. Double-click ends call.
micButton.addEventListener("click", () => {
  const now = Date.now();

  if (isCallActive && (now - lastClickTime < 400)) {
    endVoiceCall();
    addEntry("ai", "Voice call ended.");
    lastClickTime = 0;
    return;
  }
  lastClickTime = now;

  if (!isCallActive) {
    startVoiceCall();
  } else {
    if (!replayAudio.paused) {
      replayAudio.pause();
      replayAudio.currentTime = 0;
      isBusy = false;
      setMicState("listening", "Listening…");
      startPersistentRecording();
      return;
    }

    if (isRecording) {
      stopPersistentRecording();
    } else if (!isBusy) {
      startPersistentRecording();
    }
  }
});

// ---------- text fallback ----------

textForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const value = textInput.value.trim();
  if (!value || isBusy) return;
  textInput.value = "";
  // speakReply: false means text messages display normally in chat
  runTurn(value, { speakReply: false });
});

// ---------- load room types for the sidebar ----------

async function loadRoomTypes() {
  try {
    const res = await fetch(`${API_BASE}/rooms`);
    if (!res.ok) throw new Error();
    const rooms = await res.json();

    const byType = {};
    for (const r of rooms) {
      if (!byType[r.room_type]) byType[r.room_type] = r.price_per_night;
    }

    roomTypeList.innerHTML = "";
    Object.entries(byType).forEach(([type, price]) => {
      const li = document.createElement("li");
      li.innerHTML = `<span>${type}</span><span class="price">₹${Number(price).toLocaleString("en-IN")}</span>`;
      roomTypeList.appendChild(li);
    });
  } catch {
    roomTypeList.innerHTML = "<li>Could not reach backend</li>";
  }
}

// ---------- init ----------

document.querySelector(".entry__time").textContent = timeNow();
newSession();
loadRoomTypes();