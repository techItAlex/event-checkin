# Event Registration + QR Ticket + Email + Check-in

Flask + SQLite app: register → unique QR → emailed ticket → scan at the door.

## Setup

```
python -m venv venv
venv\Scripts\activate          # Windows  (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env         # then edit .env
python app.py
```

Open http://localhost:5000 (form), `/checkin` and `/attendees` (staff PIN, default `1234`).

## `.env`

| Key | Meaning |
|---|---|
| FLASK_SECRET_KEY | Signs the login cookie. Change it. |
| STAFF_PIN | PIN for `/checkin`, `/attendees`, CSV, resend |
| EVENT_NAME / EVENT_DATE / EVENT_VENUE | Shown on the form and in the email |
| SMTP_HOST / SMTP_PORT | `smtp.gmail.com` / `465` (SSL). Any other port uses STARTTLS (587) |
| SMTP_USER / SMTP_APP_PASSWORD | Gmail address + 16-char App Password |
| MAIL_FROM_NAME | Sender display name |

**Dry-run mode:** if `SMTP_USER`/`SMTP_APP_PASSWORD` are empty, emails are not sent. The full `.eml` and the QR PNG are saved in `outbox/` and `email_status` becomes `dry_run`. Add credentials and real sending turns on automatically (restart the app).

## Testing

```
pip install -r requirements-test.txt     # adds opencv, used to decode the QR PNGs
python tests/test_flow.py
```
The test uses a temporary database, so your real `data/event.db` stays clean. It covers V1–V8 (form, validation, duplicate, QR decode, unique QRs, dry-run email, check-in, already/invalid, PIN protection).

## How the 4 tasks map to code

| Task | Where |
|---|---|
| 1. Registration form | `templates/register.html`, `static/register.js` (client checks), `validate()` in `app.py` (server checks), duplicate email caught via the UNIQUE constraint |
| 2. Database + QR | `db.py` (SQLite), `qr_utils.py` (QR of `ticket_token` only), `POST /register` in `app.py` runs: validate → token → insert → QR → update path → email |
| 3. Email | `mailer.py`: HTML + plain text, QR inline via `cid:qrcode` + `ticket.png` attachment, sent in a background thread; failures set `email_status = failed` but never break registration. `POST /admin/resend/<id>` resends |
| 4. Check-in | `templates/checkin.html`, `static/checkin.js` (html5-qrcode camera + always-focused input for USB scanners, 2 s debounce), `POST /api/checkin` → `db.check_in()` (one atomic UPDATE, so a ticket can't be checked in twice) |

Design decisions: the QR holds a random token, not the email; the PIN is one shared value stored in a session cookie (no user accounts); if the SQLite insert hits a duplicate email the user sees a friendly error and no second row is made.

## Phone camera needs HTTPS

Browsers only allow camera access on `https://` or `http://localhost`. On a laptop `localhost` is fine. For a phone, run a free tunnel while the app is running:

```
cloudflared tunnel --url http://localhost:5000
```
(install: `winget install Cloudflare.cloudflared`). Open the printed `https://….trycloudflare.com/checkin` on the phone. If that's a hassle, use the laptop webcam or a USB scanner.

## Notes
- html5-qrcode loads from a CDN (unpkg), so the scanner page needs internet.
- Before the demo, make sure `data/event.db`, `qrcodes/` and `outbox/` don't contain test rows (delete them; the DB is recreated on start).
