"""End-to-end test (V1-V8). Run from the project folder:  python tests/test_flow.py
Uses a temp DB / qrcodes / outbox so your real data is never touched."""
import os
import sys
import tempfile
import unittest

TMP = tempfile.mkdtemp()
os.environ.update(
    DB_PATH=os.path.join(TMP, "test.db"), QR_DIR=os.path.join(TMP, "qrcodes"),
    OUTBOX_DIR=os.path.join(TMP, "outbox"), SYNC_EMAIL="1",
    SMTP_USER="", SMTP_APP_PASSWORD="", STAFF_PIN="4321",
)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db  # noqa: E402
from app import app  # noqa: E402

VALID = dict(full_name="Test User", email="test@example.com",
             organization="Test Org", contact_number="09171234567")


def decode_qr(path):
    import cv2
    text, _, _ = cv2.QRCodeDetector().detectAndDecode(cv2.imread(path))
    return text


class Flow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = app.test_client()

    def test_flow(self):
        c = self.client
        # V8: auth redirects
        for path in ("/checkin", "/attendees", "/attendees.csv"):
            r = c.get(path)
            self.assertEqual(r.status_code, 302, path)
            self.assertIn("/login", r.headers["Location"])
        self.assertEqual(c.post("/api/checkin", json={"token": "x"}).status_code, 401)

        # V2: invalid input and nothing saved
        bad = [dict(VALID, full_name="A"), dict(VALID, email="nope"),
               dict(VALID, organization=""), dict(VALID, contact_number="123"),
               dict(VALID, contact_number="abc4567890123")]
        for b in bad:
            self.assertEqual(c.post("/register", data=b).status_code, 400, b)
        self.assertEqual(len(db.list_attendees()), 0)

        # V1: valid registration
        r = c.post("/register", data=dict(VALID, email="Test@Example.com"))
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r.headers["Location"].endswith("/success"))
        rows = db.list_attendees()
        self.assertEqual(len(rows), 1)
        a = rows[0]
        self.assertEqual((a["full_name"], a["email"], a["organization"], a["contact_number"]),
                         ("Test User", "test@example.com", "Test Org", "09171234567"))

        # V2: duplicate email (case-insensitive)
        r = c.post("/register", data=dict(VALID, full_name="Other"))
        self.assertEqual(r.status_code, 409)
        self.assertIn(b"already registered", r.data)
        self.assertEqual(len(db.list_attendees()), 1)

        # V3: QR file decodes to exact token
        token = a["ticket_token"]
        png = os.path.join(os.environ["QR_DIR"], f"{token}.png")
        self.assertTrue(os.path.exists(png))
        self.assertEqual(decode_qr(png), token)

        # V4: second attendee gets different token and PNG
        c.post("/register", data=dict(VALID, full_name="Second", email="second@example.com"))
        b = db.list_attendees()[1]
        self.assertNotEqual(b["ticket_token"], token)
        self.assertTrue(os.path.exists(os.path.join(os.environ["QR_DIR"], b["ticket_token"] + ".png")))
        self.assertEqual(decode_qr(os.path.join(os.environ["QR_DIR"], b["ticket_token"] + ".png")),
                         b["ticket_token"])

        # V5: dry-run email
        outbox = os.environ["OUTBOX_DIR"]
        eml = open(os.path.join(outbox, token + ".eml"), "rb").read().decode()
        self.assertTrue(os.path.exists(os.path.join(outbox, token + ".png")))
        self.assertIn("Content-ID: <qrcode>", eml)
        self.assertIn("cid:qrcode", eml)
        self.assertIn("ticket.png", eml)
        self.assertEqual(db.get_attendee(a["id"])["email_status"], "dry_run")

        # Login: wrong then right PIN
        self.assertIn(b"Wrong PIN", c.post("/login", data={"pin": "0000"}).data)
        self.assertEqual(c.post("/login", data={"pin": "4321", "next": "/checkin"}).status_code, 302)
        self.assertEqual(c.get("/checkin").status_code, 200)

        # V6: check in
        j = c.post("/api/checkin", json={"token": token}).get_json()
        self.assertEqual(j["status"], "ok")
        self.assertEqual(j["name"], "Test User")
        row = db.get_attendee(a["id"])
        self.assertEqual(row["status"], "Checked In")
        self.assertTrue(row["checked_in_at"])

        # V7: again -> already; random -> invalid
        self.assertEqual(c.post("/api/checkin", json={"token": token}).get_json()["status"], "already")
        self.assertEqual(c.post("/api/checkin", json={"token": "random-bad"}).get_json()["status"], "invalid")

        # Admin pages
        self.assertIn(b"Checked In", c.get("/attendees").data)
        self.assertIn(b"Test User", c.get("/attendees.csv").data)
        self.assertEqual(c.post(f"/admin/resend/{a['id']}").status_code, 302)


if __name__ == "__main__":
    unittest.main(verbosity=2)
