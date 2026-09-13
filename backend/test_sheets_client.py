import os
import unittest
from unittest.mock import patch

from sheets_client import SheetsClient


class SheetsClientTests(unittest.TestCase):
    @patch.dict(
        os.environ,
        {
            "GOOGLE_CLIENT_ID": "client-id",
            "GOOGLE_CLIENT_SECRET": "client-secret",
            "GOOGLE_REFRESH_TOKEN": "refresh-token",
            "GOOGLE_SHEET_ID": "spreadsheet-id",
        },
        clear=False,
    )
    def test_audit_row_matches_sheet_columns(self):
        client = SheetsClient()
        row = client.build_audit_row(
            session_id="session-123",
            customer_name="Patient Name",
            email="patient@example.com",
            phone="+923001234567",
            action="appointment_booked",
            booking_uid="booking-123",
            gmail_status="sent",
            details={"contact_source": "form"},
        )

        self.assertEqual(len(row), 9)
        self.assertEqual(row[1:8], [
            "session-123",
            "Patient Name",
            "patient@example.com",
            "+923001234567",
            "appointment_booked",
            "booking-123",
            "sent",
        ])
        self.assertIn('"contact_source":"form"', row[8])


if __name__ == "__main__":
    unittest.main()
