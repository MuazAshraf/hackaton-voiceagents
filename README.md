# VoiceForm

An adaptive multimodal appointment agent. Customers begin naturally by voice;
when speech recognition gets precise contact details wrong, the same live call
opens a text form. User-verified data is persisted and sent directly to Cal.com
without passing back through the language model.

## Stack

- Vapi Web SDK for the live voice call
- FastAPI for the frontend and tool APIs
- PostgreSQL for verified session data and audit events
- Cal.com for appointment availability and booking

## Environment

Copy `.env.example` to `.env` and configure the values. `VAPI_PUBLIC_KEY` must
be a restricted public key; never expose a private Vapi API key in the browser.

## Run

```bash
pip install -r backend/requirements.txt
cd backend
uvicorn main:app --host 0.0.0.0 --port 8080
```

Open `http://localhost:8080`.
