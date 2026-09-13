from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select

PROJECT_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = PROJECT_DIR.parent
load_dotenv(PROJECT_DIR / ".env")
load_dotenv(REPO_DIR / ".env")

from cal_client import CalAPIError, CalClient  # noqa: E402
from database import SessionLocal, create_tables  # noqa: E402
from gmail_client import GmailClient  # noqa: E402
from models import AuditEvent, VoiceSession  # noqa: E402
from sheets_client import SheetsClient  # noqa: E402


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_tables()
    yield


app = FastAPI(title="VoiceForm", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class AvailabilityRequest(BaseModel):
    start: str = Field(description="Start as an ISO 8601 date or UTC datetime")
    end: str = Field(description="End as an ISO 8601 date or UTC datetime")
    timezone: str = "Asia/Karachi"


class SessionCreate(BaseModel):
    session_id: str | None = None


class CapturedContact(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None


class VerifiedContact(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    phone: str = Field(min_length=5, max_length=50)


class BookingRequest(BaseModel):
    start: str = Field(description="Exact slot returned by checkAvailability")
    session_id: str | None = None
    name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    timezone: str = "Asia/Karachi"


class RescheduleRequest(BaseModel):
    booking_uid: str = Field(min_length=1)
    new_start: str
    reason: str = "Customer requested reschedule"


class CancelRequest(BaseModel):
    booking_uid: str = Field(min_length=1)
    reason: str = "Customer requested cancellation"


def add_event(db, session_id: str, event_type: str, data: dict[str, Any] | None = None):
    db.add(AuditEvent(session_id=session_id, event_type=event_type, event_data=data or {}))


def find_session(db, session_id: str) -> VoiceSession:
    record = db.scalar(select(VoiceSession).where(VoiceSession.session_id == session_id))
    if not record:
        raise HTTPException(status_code=404, detail="Voice session not found")
    return record


def cal_client() -> CalClient:
    try:
        return CalClient()
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


async def append_sheet_audit(**values) -> tuple[str, str | None]:
    try:
        sheets = SheetsClient()
    except RuntimeError:
        return "not_configured", None
    try:
        await sheets.append_audit(**values)
        return "recorded", None
    # Audit delivery must never invalidate a completed calendar action.
    except Exception as exc:
        return "failed", str(exc)


async def run_cal(operation):
    try:
        return await operation
    except CalAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
async def health() -> dict[str, Any]:
    google_variables = (
        "GOOGLE_CLIENT_ID",
        "GOOGLE_CLIENT_SECRET",
        "GOOGLE_REFRESH_TOKEN",
        "GMAIL_SENDER_EMAIL",
        "GOOGLE_SHEET_ID",
    )
    missing_variables = [name for name in google_variables if not os.getenv(name)]
    gmail_configured = not any(
        name in missing_variables for name in google_variables[:4]
    )
    return {
        "status": "healthy",
        "service": "voiceform",
        "integrations": {
            "gmail": "configured" if gmail_configured else "missing",
            "google_sheets": "configured"
            if gmail_configured and os.getenv("GOOGLE_SHEET_ID")
            else "missing",
        },
        "missing_variables": missing_variables,
    }


@app.get("/api/config")
async def public_config() -> dict[str, str]:
    return {
        "vapiPublicKey": os.getenv("VAPI_PUBLIC_KEY", ""),
        "vapiAssistantId": os.getenv("VAPI_ASSISTANT_ID", ""),
    }


@app.post("/api/sessions")
async def create_session(body: SessionCreate) -> dict[str, str]:
    session_id = body.session_id or str(uuid.uuid4())
    with SessionLocal() as db:
        existing = db.scalar(
            select(VoiceSession).where(VoiceSession.session_id == session_id)
        )
        if not existing:
            db.add(VoiceSession(session_id=session_id))
            db.flush()
            add_event(db, session_id, "session_created")
            db.commit()
    return {"session_id": session_id}


@app.post("/api/sessions/{session_id}/captured-contact")
async def save_captured_contact(session_id: str, body: CapturedContact):
    with SessionLocal() as db:
        record = find_session(db, session_id)
        record.captured_name = body.name
        record.captured_email = body.email
        record.captured_phone = body.phone
        add_event(db, session_id, "voice_contact_rejected", body.model_dump())
        db.commit()
    return {"success": True, "session_id": session_id}


@app.post("/api/sessions/{session_id}/verified-contact")
async def save_verified_contact(session_id: str, body: VerifiedContact):
    with SessionLocal() as db:
        record = find_session(db, session_id)
        record.verified_name = body.name.strip()
        record.verified_email = str(body.email).lower()
        record.verified_phone = body.phone.strip()
        record.form_submitted = True
        record.contact_source = "form"
        add_event(
            db,
            session_id,
            "contact_form_submitted",
            {"email": record.verified_email, "contact_source": "form"},
        )
        db.commit()
    return {
        "success": True,
        "session_id": session_id,
        "message": "Verified contact details saved. Continue the voice conversation.",
    }


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    with SessionLocal() as db:
        record = find_session(db, session_id)
        integration_events = db.scalars(
            select(AuditEvent)
            .where(
                AuditEvent.session_id == session_id,
                AuditEvent.event_type.in_(
                    (
                        "gmail_confirmation_sent",
                        "gmail_confirmation_failed",
                        "google_sheets_audit_recorded",
                        "google_sheets_audit_failed",
                    )
                ),
            )
            .order_by(AuditEvent.created_at)
        ).all()
        return {
            "session_id": record.session_id,
            "form_submitted": record.form_submitted,
            "contact_source": record.contact_source,
            "verified_name": record.verified_name,
            "verified_email": record.verified_email,
            "verified_phone": record.verified_phone,
            "booking_uid": record.booking_uid,
            "booking_status": record.booking_status,
            "integration_events": [
                {
                    "type": event.event_type,
                    "data": event.event_data,
                    "created_at": event.created_at.isoformat(),
                }
                for event in integration_events
            ],
        }


@app.post("/tools/check-availability")
async def check_availability(body: AvailabilityRequest):
    client = cal_client()
    return await run_cal(client.check_availability(body.start, body.end, body.timezone))


@app.post("/tools/book-appointment")
async def book_appointment(body: BookingRequest):
    name = body.name
    email = str(body.email) if body.email else None
    phone = body.phone
    session_record: VoiceSession | None = None
    contact_source = "voice"

    with SessionLocal() as db:
        if body.session_id:
            session_record = find_session(db, body.session_id)
            if session_record.form_submitted:
                name = session_record.verified_name
                email = session_record.verified_email
                phone = session_record.verified_phone
                contact_source = session_record.contact_source or "form"
                add_event(db, body.session_id, "verified_contact_used_for_booking")
                db.commit()

    if not name or not email:
        raise HTTPException(
            status_code=422,
            detail="Confirmed name and email, or a session with verified contact, is required",
        )

    client = cal_client()
    try:
        result = await run_cal(
            client.book_appointment(body.start, name, email, phone, body.timezone)
        )
    except HTTPException:
        if body.session_id:
            with SessionLocal() as db:
                record = find_session(db, body.session_id)
                record.booking_status = "failed"
                add_event(db, body.session_id, "booking_failed")
                db.commit()
        raise

    data = result.get("data", {}) if isinstance(result, dict) else {}
    uid = data.get("uid") if isinstance(data, dict) else None
    if body.session_id:
        with SessionLocal() as db:
            record = find_session(db, body.session_id)
            record.booking_uid = uid
            record.booking_status = "booked"
            add_event(db, body.session_id, "booking_created", {"booking_uid": uid})
            db.commit()

    email_status = "not_configured"
    try:
        gmail = GmailClient()
    except RuntimeError:
        gmail = None

    if gmail:
        try:
            email_result = await gmail.send_booking_confirmation(
                recipient=email,
                name=name,
                start=body.start,
                timezone=body.timezone,
                booking_uid=uid,
            )
            email_status = "sent"
            if body.session_id:
                with SessionLocal() as db:
                    find_session(db, body.session_id)
                    add_event(
                        db,
                        body.session_id,
                        "gmail_confirmation_sent",
                        {"gmail_message_id": email_result.get("id")},
                    )
                    db.commit()
        # Confirmation delivery must never invalidate a completed booking.
        except Exception as exc:
            email_status = "failed"
            if body.session_id:
                with SessionLocal() as db:
                    find_session(db, body.session_id)
                    add_event(
                        db,
                        body.session_id,
                        "gmail_confirmation_failed",
                        {"error": str(exc)},
                    )
                    db.commit()

    if isinstance(result, dict):
        result["voiceform"] = {"gmail_confirmation": email_status}

    sheet_status, sheet_error = await append_sheet_audit(
        session_id=body.session_id,
        customer_name=name,
        email=email,
        phone=phone,
        action="appointment_booked",
        booking_uid=uid,
        gmail_status=email_status,
        details={
            "start": body.start,
            "timezone": body.timezone,
            "contact_source": contact_source,
        },
    )
    if body.session_id:
        with SessionLocal() as db:
            find_session(db, body.session_id)
            add_event(
                db,
                body.session_id,
                "google_sheets_audit_recorded"
                if sheet_status == "recorded"
                else "google_sheets_audit_failed",
                {"status": sheet_status, **({"error": sheet_error} if sheet_error else {})},
            )
            db.commit()
    if isinstance(result, dict):
        result["voiceform"]["google_sheets_audit"] = sheet_status

    return result


@app.post("/tools/reschedule-appointment")
async def reschedule_appointment(body: RescheduleRequest):
    result = await run_cal(
        cal_client().reschedule_appointment(body.booking_uid, body.new_start, body.reason)
    )
    sheet_status, _ = await append_sheet_audit(
        action="appointment_rescheduled",
        booking_uid=body.booking_uid,
        details={"new_start": body.new_start, "reason": body.reason},
    )
    if isinstance(result, dict):
        result["voiceform"] = {"google_sheets_audit": sheet_status}
    return result


@app.post("/tools/cancel-appointment")
async def cancel_appointment(body: CancelRequest):
    result = await run_cal(
        cal_client().cancel_appointment(body.booking_uid, body.reason)
    )
    sheet_status, _ = await append_sheet_audit(
        action="appointment_cancelled",
        booking_uid=body.booking_uid,
        details={"reason": body.reason},
    )
    if isinstance(result, dict):
        result["voiceform"] = {"google_sheets_audit": sheet_status}
    return result
