import Vapi from "@vapi-ai/web";

const callButton = document.querySelector("#callButton");
const callLabel = document.querySelector("#callLabel");
const status = document.querySelector("#status");
const hint = document.querySelector("#hint");
const orb = document.querySelector("#orb");
const modal = document.querySelector("#contactModal");
const form = document.querySelector("#contactForm");
const formError = document.querySelector("#formError");
const toast = document.querySelector("#toast");

let vapi;
let assistantId;
let sessionId;
let callActive = false;
let heardLocalAudio = false;
let audioWarningTimer;

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || "Request failed");
  return data;
}

function setCallState(active) {
  callActive = active;
  callButton.classList.toggle("active", active);
  orb.classList.toggle("live", active);
  callLabel.textContent = active ? "End voice call" : "Start voice call";
  status.textContent = active ? "Call connected" : "Ready to start";
  if (!active) clearTimeout(audioWarningTimer);
}

function describeMediaError(error) {
  if (error?.name === "NotAllowedError") return "Microphone permission is blocked. Click the lock icon beside the address, allow Microphone, then reload.";
  if (error?.name === "NotFoundError") return "No microphone was found. Connect or enable a microphone, then try again.";
  if (error?.name === "NotReadableError") return "The microphone is busy or unavailable. Close other call apps and try again.";
  return `Microphone error: ${error?.message || "unable to open the microphone"}`;
}

async function verifyMicrophone() {
  if (!navigator.mediaDevices?.getUserMedia) {
    throw new Error("This browser cannot access a microphone. Use an up-to-date Chrome or Edge browser.");
  }

  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    });
    const track = stream.getAudioTracks()[0];
    if (!track || track.readyState !== "live") throw new DOMException("Microphone track is not live", "NotReadableError");
    return track.getSettings().label || track.label || "microphone";
  } catch (error) {
    throw new Error(describeMediaError(error));
  } finally {
    stream?.getTracks().forEach((track) => track.stop());
  }
}

function showContactForm(prefill = {}) {
  document.querySelector("#name").value = prefill.name || "";
  document.querySelector("#email").value = prefill.email || "";
  document.querySelector("#phoneInput").value = prefill.phone || "";
  modal.hidden = false;
  document.querySelector("#name").focus();
}

async function initialize() {
  const config = await api("/api/config");
  if (!config.vapiPublicKey || !config.vapiAssistantId) {
    callButton.disabled = true;
    hint.textContent = "VAPI_PUBLIC_KEY and VAPI_ASSISTANT_ID must be configured on Railway.";
    return;
  }

  vapi = new Vapi(config.vapiPublicKey);
  assistantId = config.vapiAssistantId;
  vapi.on("call-start", () => {
    setCallState(true);
    heardLocalAudio = false;
    hint.textContent = "Speak now — your microphone level is being checked.";
    audioWarningTimer = setTimeout(() => {
      if (!heardLocalAudio && callActive) {
        hint.textContent = "No microphone sound detected. Check the selected input device and browser microphone permission.";
      }
    }, 6000);
  });
  vapi.on("call-end", () => setCallState(false));
  vapi.on("speech-start", () => { status.textContent = "Ava is speaking"; });
  vapi.on("speech-end", () => { status.textContent = "Listening — speak now"; });
  vapi.on("local-volume-level", (level) => {
    const volume = Number(level) || 0;
    orb.style.setProperty("--mic-glow", `${20 + (Math.min(1, volume) * 28)}px`);
    if (volume > 0.01) {
      heardLocalAudio = true;
      clearTimeout(audioWarningTimer);
      if (callActive) hint.textContent = "Microphone active. Speak naturally.";
    }
  });
  vapi.on("error", (error) => {
    console.error("Vapi call error", error);
    const detail = error?.error?.message || error?.message || "Unknown voice call error";
    hint.textContent = `Call error: ${detail}`;
    setCallState(false);
  });
  vapi.on("message", (message) => {
    if (message.type !== "tool-calls") return;
    const calls = message.toolCallList || [];
    const request = calls.find((item) => item.name === "showContactForm");
    if (request) showContactForm(request.parameters || {});
  });
}

callButton.addEventListener("click", async () => {
  if (!vapi) return;
  if (callActive) {
    vapi.stop();
    return;
  }
  callButton.disabled = true;
  try {
    status.textContent = "Checking microphone";
    const microphone = await verifyMicrophone();
    hint.textContent = `Microphone ready: ${microphone}`;
    const created = await api("/api/sessions", { method: "POST", body: "{}" });
    sessionId = created.session_id;
    status.textContent = "Connecting";
    await vapi.start(assistantId, {
      variableValues: { session_id: sessionId },
    });
  } catch (error) {
    console.error(error);
    hint.textContent = error.message;
    setCallState(false);
  } finally {
    callButton.disabled = false;
  }
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  formError.textContent = "";
  const body = {
    name: document.querySelector("#name").value.trim(),
    email: document.querySelector("#email").value.trim(),
    phone: document.querySelector("#phoneInput").value.trim(),
  };
  try {
    await api(`/api/sessions/${sessionId}/verified-contact`, {
      method: "POST",
      body: JSON.stringify(body),
    });
    modal.hidden = true;
    toast.hidden = false;
    setTimeout(() => { toast.hidden = true; }, 3500);
    vapi.addMessage({
      role: "system",
      content: `The user submitted the secure contact form. The verified contact is now stored under session_id ${sessionId}. Do not ask them to spell it or repeat it. Tell them the form was received and continue with appointment selection.`,
    });
  } catch (error) {
    formError.textContent = error.message;
  }
});

initialize().catch((error) => {
  console.error(error);
  callButton.disabled = true;
  hint.textContent = "Unable to load VoiceForm configuration.";
});
