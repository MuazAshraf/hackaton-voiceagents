from __future__ import annotations

import base64
import os
from email.message import EmailMessage
from typing import Any

import httpx


class GmailAPIError(RuntimeError):
    pass


class GmailClient:
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"

    def __init__(self) -> None:
        self.client_id = os.getenv("GOOGLE_CLIENT_ID")
        self.client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        self.refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN")
        self.sender_email = os.getenv("GMAIL_SENDER_EMAIL")

        missing = [
            name
            for name, value in {
                "GOOGLE_CLIENT_ID": self.client_id,
                "GOOGLE_CLIENT_SECRET": self.client_secret,
                "GOOGLE_REFRESH_TOKEN": self.refresh_token,
                "GMAIL_SENDER_EMAIL": self.sender_email,
            }.items()
            if not value
        ]
        if missing:
            raise RuntimeError(f"Missing Gmail configuration: {', '.join(missing)}")

    async def _get_access_token(self) -> str:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                self.TOKEN_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": self.refresh_token,
                    "grant_type": "refresh_token",
                },
            )

        try:
            payload = response.json()
        except ValueError:
            payload = {}
        if response.is_error or not payload.get("access_token"):
            description = payload.get("error_description") or payload.get("error")
            raise GmailAPIError(f"Google OAuth token refresh failed: {description or response.status_code}")
        return str(payload["access_token"])

    @staticmethod
    def _build_message(
        *,
        sender: str,
        recipient: str,
        name: str,
        start: str,
        timezone: str,
        booking_uid: str | None,
    ) -> str:
        message = EmailMessage()
        message["To"] = recipient
        message["From"] = sender
        message["Subject"] = "Your BrightSmile Dental appointment is confirmed"
        reference = booking_uid or "Available in your Cal.com confirmation"
        message.set_content(
            f"""Hi {name},

Your appointment with BrightSmile Dental has been confirmed.

Appointment time: {start}
Timezone: {timezone}
Booking reference: {reference}

Cal.com will provide the official calendar invitation and meeting details.

Thank you,
VoiceForm for BrightSmile Dental
"""
        )
        return base64.urlsafe_b64encode(message.as_bytes()).decode("ascii").rstrip("=")

    async def send_booking_confirmation(
        self,
        *,
        recipient: str,
        name: str,
        start: str,
        timezone: str,
        booking_uid: str | None,
    ) -> dict[str, Any]:
        access_token = await self._get_access_token()
        raw = self._build_message(
            sender=str(self.sender_email),
            recipient=recipient,
            name=name,
            start=start,
            timezone=timezone,
            booking_uid=booking_uid,
        )
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                self.SEND_URL,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                json={"raw": raw},
            )

        try:
            payload = response.json()
        except ValueError:
            payload = {}
        if response.is_error:
            error = payload.get("error", {})
            detail = error.get("message") if isinstance(error, dict) else error
            raise GmailAPIError(f"Gmail send failed: {detail or response.status_code}")
        return payload
