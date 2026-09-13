from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import httpx


class SheetsAPIError(RuntimeError):
    pass


class SheetsClient:
    TOKEN_URL = "https://oauth2.googleapis.com/token"

    def __init__(self) -> None:
        self.client_id = os.getenv("GOOGLE_CLIENT_ID")
        self.client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        self.refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN")
        self.spreadsheet_id = os.getenv("GOOGLE_SHEET_ID")

        missing = [
            name
            for name, value in {
                "GOOGLE_CLIENT_ID": self.client_id,
                "GOOGLE_CLIENT_SECRET": self.client_secret,
                "GOOGLE_REFRESH_TOKEN": self.refresh_token,
                "GOOGLE_SHEET_ID": self.spreadsheet_id,
            }.items()
            if not value
        ]
        if missing:
            raise RuntimeError(f"Missing Google Sheets configuration: {', '.join(missing)}")

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
            raise SheetsAPIError(f"Google OAuth token refresh failed: {description or response.status_code}")
        return str(payload["access_token"])

    @staticmethod
    def build_audit_row(
        *,
        session_id: str | None,
        customer_name: str | None,
        email: str | None,
        phone: str | None,
        action: str,
        booking_uid: str | None,
        gmail_status: str | None,
        details: dict[str, Any] | None = None,
    ) -> list[str]:
        return [
            datetime.now(UTC).isoformat(),
            session_id or "",
            customer_name or "",
            email or "",
            phone or "",
            action,
            booking_uid or "",
            gmail_status or "",
            json.dumps(details or {}, separators=(",", ":"), ensure_ascii=True),
        ]

    async def append_audit(
        self,
        *,
        session_id: str | None = None,
        customer_name: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        action: str,
        booking_uid: str | None = None,
        gmail_status: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        access_token = await self._get_access_token()
        spreadsheet_id = quote(str(self.spreadsheet_id), safe="")
        url = (
            f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}"
            "/values/A:I:append?valueInputOption=RAW&insertDataOption=INSERT_ROWS"
        )
        row = self.build_audit_row(
            session_id=session_id,
            customer_name=customer_name,
            email=email,
            phone=phone,
            action=action,
            booking_uid=booking_uid,
            gmail_status=gmail_status,
            details=details,
        )
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                json={"majorDimension": "ROWS", "values": [row]},
            )

        try:
            payload = response.json()
        except ValueError:
            payload = {}
        if response.is_error:
            error = payload.get("error", {})
            detail = error.get("message") if isinstance(error, dict) else error
            raise SheetsAPIError(f"Google Sheets append failed: {detail or response.status_code}")
        return payload
