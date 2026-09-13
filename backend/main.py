from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr, Field

from cal_client import CalAPIError, CalClient


PROJECT_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = PROJECT_DIR.parent
load_dotenv(PROJECT_DIR / ".env")
load_dotenv(REPO_DIR / ".env")

app = FastAPI(title="VoiceOps Guardian Tools", version="0.1.0")


class AvailabilityRequest(BaseModel):
    start: str = Field(description="Start of range as an ISO 8601 date or UTC datetime")
    end: str = Field(description="End of range as an ISO 8601 date or UTC datetime")
    timezone: str = "Asia/Karachi"


class BookingRequest(BaseModel):
    start: str = Field(description="Exact available slot in ISO 8601 UTC format")
    name: str = Field(min_length=1)
    email: EmailStr
    phone: str | None = None
    timezone: str = "Asia/Karachi"


class RescheduleRequest(BaseModel):
    booking_uid: str = Field(min_length=1)
    new_start: str = Field(description="Exact available slot in ISO 8601 UTC format")
    reason: str = "Customer requested reschedule"


class CancelRequest(BaseModel):
    booking_uid: str = Field(min_length=1)
    reason: str = "Customer requested cancellation"


def cal_client() -> CalClient:
    try:
        return CalClient()
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


async def run_cal(operation):
    try:
        return await operation
    except CalAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.post("/tools/check-availability")
async def check_availability(body: AvailabilityRequest):
    client = cal_client()
    return await run_cal(
        client.check_availability(body.start, body.end, body.timezone)
    )


@app.post("/tools/book-appointment")
async def book_appointment(body: BookingRequest):
    client = cal_client()
    return await run_cal(
        client.book_appointment(
            body.start,
            body.name,
            str(body.email),
            body.phone,
            body.timezone,
        )
    )


@app.post("/tools/reschedule-appointment")
async def reschedule_appointment(body: RescheduleRequest):
    client = cal_client()
    return await run_cal(
        client.reschedule_appointment(body.booking_uid, body.new_start, body.reason)
    )


@app.post("/tools/cancel-appointment")
async def cancel_appointment(body: CancelRequest):
    client = cal_client()
    return await run_cal(
        client.cancel_appointment(body.booking_uid, body.reason)
    )
