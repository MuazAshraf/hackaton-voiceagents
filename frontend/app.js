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
const inputDevice = document.querySelector("#inputDevice");

let vapi;
let assistantId;
let sessionId;
let callActive = false;
let heardLocalAudio = false;
let callStarting = false;

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
}

function errorText(value) {
  if (!value) return "Unknown error";
  if (typeof value === "string") return value;
  if (value.message && typeof value.message === "string") return value.message;
  if (value.errorMsg) return String(value.errorMsg);
  if (value.error) return errorText(value.error);
  if (value.message) return errorText(value.message);
  try { return JSON.stringify(value); } catch { return String(value); }
}

function isExpectedMeetingEnd(error) {
  const detail = errorText(error).toLowerCase();
  return error?.type === "daily-error" && (detail.includes("meeting has ended") || detail.includes("ejected"));
}

async function refreshInputDevices(preferredDeviceId = "") {
  const devices = await navigator.mediaDevices.enumerateDevices();
  const microphones = devices.filter((device) => device.kind === "audioinput");
  const selected = preferredDeviceId || inputDevice.value;
  inputDevice.replaceChildren(new Option("System default microphone", ""));
  microphones.forEach((device, index) => {
    inputDevice.add(new Option(device.label || `Microphone ${index + 1}`, device.deviceId));
  });
  if ([...inputDevice.options].some((option) => option.value === selected)) inputDevice.value = selected;
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
    const chosenDeviceId = inputDevice.value;
    stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        ...(chosenDeviceId ? { deviceId: { exact: chosenDeviceId } } : {}),
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });
    const track = stream.getAudioTracks()[0];
    if (!track || track.readyState !== "live") throw new DOMException("Microphone track is not live", "NotReadableError");
    const deviceId = track.getSettings().deviceId || chosenDeviceId;
    await refreshInputDevices(deviceId);
    return { deviceId, label: track.label || "microphone" };
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

function parseToolCall(toolCall) {
  const name = toolCall.name || toolCall.function?.name;
  const raw = toolCall.parameters ?? toolCall.arguments ?? toolCall.function?.arguments ?? {};
  if (typeof raw !== "string") return { name, parameters: raw || {} };
  try {
    return { name, parameters: JSON.parse(raw || "{}") };
  } catch (error) {
    console.error("Unable to parse client tool arguments", error, raw);
    return { name, parameters: {} };
  }
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
    hint.textContent = `Using ${inputDevice.selectedOptions[0]?.text || "system microphone"}. Speak naturally.`;
  });
  vapi.on("call-end", () => setCallState(false));
  vapi.on("speech-start", () => { status.textContent = "Ava is speaking"; });
  vapi.on("speech-end", () => { status.textContent = "Listening — speak now"; });
  vapi.on("local-volume-level", (level) => {
    const volume = Number(level) || 0;
    orb.style.setProperty("--mic-glow", `${20 + (Math.min(1, volume) * 28)}px`);
    if (volume > 0.01) {
      heardLocalAudio = true;
      if (callActive) hint.textContent = "Microphone active. Speak naturally.";
    }
  });
  vapi.on("error", (error) => {
    console.error("Vapi call error", error);
    if (isExpectedMeetingEnd(error)) return;
    hint.textContent = `Call warning: ${errorText(error)}`;
  });
  vapi.on("message", (message) => {
    if (message.type === "status-update" && message.status === "ended") {
      setCallState(false);
      if (message.endedReason === "silence-timed-out") {
        hint.textContent = "Call ended after a period of inactivity. Start a new call when ready.";
      }
      return;
    }
    if (message.type !== "tool-calls") return;
    const calls = message.toolCallList || [];
    const request = calls.map(parseToolCall).find((item) => item.name === "showContactForm");
    if (request) {
      showContactForm(request.parameters);
      status.textContent = "Waiting for secure form";
      hint.textContent = "The voice call is still connected. Submit the form to continue.";
    }
  });
}

callButton.addEventListener("click", async () => {
  if (!vapi || callStarting) return;
  if (callActive) {
    vapi.stop();
    return;
  }
  callStarting = true;
  callButton.disabled = true;
  try {
    status.textContent = "Checking microphone";
    const microphone = await verifyMicrophone();
    hint.textContent = `Microphone ready: ${microphone.label}`;
    const created = await api("/api/sessions", { method: "POST", body: "{}" });
    sessionId = created.session_id;
    status.textContent = "Connecting";
    const call = await vapi.start(assistantId, {
      variableValues: { session_id: sessionId },
    });
    if (!call) throw new Error("Vapi could not start the call.");
    if (microphone.deviceId) {
      try {
        await vapi.setInputDevicesAsync({ audioSource: microphone.deviceId });
      } catch (deviceError) {
        console.warn("Could not force the selected microphone; using browser default", deviceError);
        hint.textContent = `Call connected with browser default microphone. ${errorText(deviceError)}`;
      }
    }
  } catch (error) {
    console.error(error);
    hint.textContent = error.message;
    setCallState(false);
  } finally {
    callStarting = false;
    callButton.disabled = false;
  }
});

navigator.mediaDevices?.addEventListener?.("devicechange", () => {
  if (!callActive && !callStarting) refreshInputDevices().catch(console.error);
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
    vapi.send({
      type: "add-message",
      message: {
        role: "system",
        content: `The user submitted the secure contact form. The verified contact is now stored under session_id ${sessionId}. Do not ask them to spell it, repeat it, or generate contact values for booking. Tell them the form was received and continue with appointment selection.`,
      },
      triggerResponseEnabled: true,
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
