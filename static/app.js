import Vapi from "https://cdn.jsdelivr.net/npm/@vapi-ai/web/+esm";

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
  vapi.on("call-start", () => setCallState(true));
  vapi.on("call-end", () => setCallState(false));
  vapi.on("speech-start", () => { status.textContent = "Ava is speaking"; });
  vapi.on("speech-end", () => { status.textContent = "Listening"; });
  vapi.on("error", (error) => {
    console.error(error);
    hint.textContent = "The voice call hit an error. Please try again.";
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
  try {
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
