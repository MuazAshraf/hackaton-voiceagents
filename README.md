# VoiceForm

VoiceForm is a multimodal voice appointment agent for service businesses. A
customer can talk naturally to a Vapi voice assistant, check real availability,
book an appointment, and receive confirmation without a human receptionist.

The key problem it solves is voice reliability. Names, emails, and phone numbers
are painful to spell over a call. When the assistant is unsure or the user wants
to correct their contact details, VoiceForm opens a live text form during the
same call. The verified form data is stored in PostgreSQL and used directly for
the booking, so the language model does not have to guess important contact
information.

## Project Overview

VoiceForm combines voice, tools, and a lightweight web interface:

- Starts a browser voice call with a Vapi assistant.
- Checks real appointment slots from Cal.com before offering times.
- Collects contact details by voice, with a text-form fallback for corrections.
- Books the appointment in Cal.com using verified contact data.
- Sends a custom Gmail confirmation after booking.
- Writes an audit row to Google Sheets for demo and operations visibility.
- Stores session state, verified contact data, booking UID, and audit events in
  PostgreSQL.

Production demo app:

```text
https://voice.muazashraf.org
```

Demo video:

```text
https://youtu.be/uOgN7AENyn4
```

## External Apps Used

This project connects to more than the required three external apps:

- Vapi: live voice assistant, browser call, and tool calling.
- Cal.com: real availability, booking, rescheduling, and cancellation.
- Gmail API: sends a custom appointment confirmation email.
- Google Sheets API: appends booking/audit records to a spreadsheet.
- Railway: hosts the FastAPI app and PostgreSQL database.
- Cloudflare DNS: routes `voice.muazashraf.org` to the Railway deployment.

## How It Works

1. The frontend creates a VoiceForm session in the backend.
2. The user starts a Vapi browser call.
3. Vapi calls the backend tools:
   - `checkAvailability`
   - `bookAppointment`
   - `rescheduleAppointment`
   - `cancelAppointment`
   - `showContactForm`
4. If contact details are hard to capture by voice, `showContactForm` opens the
   in-call form.
5. The user submits verified name, email, and phone.
6. The backend stores the verified contact in PostgreSQL.
7. When Vapi books the appointment, the backend uses verified session data
   instead of unreliable voice-transcribed placeholders.
8. After Cal.com confirms the booking, the backend sends Gmail confirmation and
   appends a Google Sheets audit row.

## Setup Instructions

### 1. Install dependencies

```bash
npm install
pip install -r backend/requirements.txt
```

### 2. Configure environment variables

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Fill these values:

```env
CAL_API_KEY=cal_your_api_key_here
CAL_EVENT_TYPE_ID=3093253
DATABASE_URL=postgresql://user:password@host:5432/database
VAPI_PUBLIC_KEY=your_restricted_public_vapi_key
VAPI_ASSISTANT_ID=your_vapi_assistant_id
GOOGLE_CLIENT_ID=your_google_oauth_client_id
GOOGLE_CLIENT_SECRET=your_google_oauth_client_secret
GOOGLE_REFRESH_TOKEN=your_google_oauth_refresh_token
GMAIL_SENDER_EMAIL=your_sender@gmail.com
GOOGLE_SHEET_ID=your_google_spreadsheet_id
```

Notes:

- `VAPI_PUBLIC_KEY` must be a restricted public key. Do not expose a private Vapi
  API key in the browser.
- `DATABASE_URL` should point to Postgres. Tables are created automatically when
  the FastAPI app starts.
- The Google refresh token needs Gmail send and Google Sheets scopes.

### 3. Build the browser bundle

```bash
npm run build:web
```

### 4. Run locally

```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8080
```

Open:

```text
http://localhost:8080
```

Useful health checks:

```text
http://localhost:8080/health
http://localhost:8080/health/google
```

### 5. Deploy

The production version is deployed on Railway.

Recommended Railway settings:

- Build command: `npm install && npm run build:web && pip install -r backend/requirements.txt`
- Start command: `cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT`
- Public domain: `voice.muazashraf.org`
- Required service: PostgreSQL

Add the same environment variables from `.env.example` to Railway.

## Vapi Tool Endpoints

Configure Vapi API request tools with these endpoints:

```text
POST https://voice.muazashraf.org/tools/check-availability
POST https://voice.muazashraf.org/tools/book-appointment
POST https://voice.muazashraf.org/tools/reschedule-appointment
POST https://voice.muazashraf.org/tools/cancel-appointment
```

The browser client also handles the client-side `showContactForm` tool so the
assistant can request typed contact confirmation during the call.

## Reliability Testing

VoiceForm was tested against the full production flow:

- Verified `/health` returns healthy from the deployed Railway app.
- Verified Google integration health with Gmail and Sheets scopes.
- Tested Cal.com availability through the backend tool endpoint.
- Completed a real voice booking and confirmed the booking appeared in Cal.com.
- Confirmed the customer received an appointment email.
- Tested the contact correction path where the form data overrides empty or
  incorrect voice-transcribed name/email/phone values.
- Stored session state in PostgreSQL, including verified contact fields,
  booking UID, form submitted status, and audit events.
- Added unit tests for Gmail and Google Sheets client payload behavior.

Known reliability design choices:

- The agent must call availability before offering appointment slots.
- Booking uses the exact slot returned by Cal.com.
- Gmail and Google Sheets failures are recorded as audit events but do not undo a
  successful Cal.com booking.
- Contact details are validated after the verified session override, which avoids
  failed bookings when Vapi sends empty voice placeholders.

## Demo Video

Replace this placeholder with the final YouTube link:

```text
https://youtube.com/watch?v=REPLACE_WITH_DEMO_LINK
```
