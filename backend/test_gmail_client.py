import base64
import email
import os
import unittest
from unittest.mock import patch

from gmail_client import GmailClient


class GmailClientTests(unittest.TestCase):
    @patch.dict(
        os.environ,
        {
            "GOOGLE_CLIENT_ID": "client-id",
            "GOOGLE_CLIENT_SECRET": "client-secret",
            "GOOGLE_REFRESH_TOKEN": "refresh-token",
            "GMAIL_SENDER_EMAIL": "sender@example.com",
        },
        clear=False,
    )
    def test_confirmation_message_contains_booking_details(self):
        client = GmailClient()
        raw = client._build_message(
            sender="sender@example.com",
            recipient="patient@example.com",
            name="Patient Name",
            start="2026-09-15T16:00:00+05:00",
            timezone="Asia/Karachi",
            booking_uid="booking-123",
        )
        decoded = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
        message = email.message_from_bytes(decoded)

        self.assertEqual(message["To"], "patient@example.com")
        self.assertEqual(message["From"], "sender@example.com")
        content = message.get_payload(decode=True).decode()
        self.assertIn("Patient Name", content)
        self.assertIn("booking-123", content)
        self.assertIn("Asia/Karachi", content)


if __name__ == "__main__":
    unittest.main()
