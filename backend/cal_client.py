from __future__ import annotations

import os
from typing import Any

import httpx


class CalAPIError(RuntimeError):
    def __init__(self, status_code: int, detail: Any):
        super().__init__(f"Cal.com API returned HTTP {status_code}")
        self.status_code = status_code
        self.detail = detail


class CalClient:
    BASE_URL = "https://api.cal.com/v2"
    SLOTS_API_VERSION = "2024-09-04"
    BOOKINGS_API_VERSION = "2026-02-25"

    def __init__(self) -> None:
        self.api_key = (
            os.getenv("CAL_API_KEY")
            or os.getenv("CALCOM_API_KEY")
            or os.getenv("CALCOM_LICENSE_KEY")
        )
        self.event_type_id = int(os.getenv("CAL_EVENT_TYPE_ID", "3093253"))

        if not self.api_key:
            raise RuntimeError("CAL_API_KEY is not configured")

    def _headers(self, version: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "cal-api-version": version,
        }

    async def _request(
        self,
        method: str,
        path: str,
        *,
        version: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.request(
                method,
                f"{self.BASE_URL}{path}",
                headers=self._headers(version),
                params=params,
                json=json,
            )

        try:
            payload = response.json()
        except ValueError:
            payload = {"message": response.text or "Invalid response from Cal.com"}

        if response.is_error:
            raise CalAPIError(response.status_code, payload)

        return payload

    async def check_availability(
        self,
        start: str,
        end: str,
        timezone: str = "Asia/Karachi",
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            "/slots",
            version=self.SLOTS_API_VERSION,
            params={
                "eventTypeId": self.event_type_id,
                "start": start,
                "end": end,
                "timeZone": timezone,
            },
        )

    async def book_appointment(
        self,
        start: str,
        name: str,
        email: str,
        phone: str | None,
        timezone: str = "Asia/Karachi",
    ) -> dict[str, Any]:
        attendee: dict[str, Any] = {
            "name": name,
            "email": email,
            "timeZone": timezone,
            "language": "en",
        }
        if phone:
            attendee["phoneNumber"] = phone

        return await self._request(
            "POST",
            "/bookings",
            version=self.BOOKINGS_API_VERSION,
            json={
                "eventTypeId": self.event_type_id,
                "start": start,
                "attendee": attendee,
            },
        )

    async def reschedule_appointment(
        self,
        booking_uid: str,
        new_start: str,
        reason: str,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/bookings/{booking_uid}/reschedule",
            version=self.BOOKINGS_API_VERSION,
            json={
                "start": new_start,
                "reschedulingReason": reason,
            },
        )

    async def cancel_appointment(
        self,
        booking_uid: str,
        reason: str,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/bookings/{booking_uid}/cancel",
            version=self.BOOKINGS_API_VERSION,
            json={"cancellationReason": reason},
        )
