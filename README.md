# 🎟 Event Registration, QR Ticket & Check-in

A small web app that takes an event from sign-up to the front door:

**Register → unique QR ticket → emailed to the participant → scanned at the entrance.**

Built with **Flask** and **SQLite**. No accounts for participants, no database server to install.

---

## ✨ Features

| | |
|---|---|
| 📝 **Registration form** | Name, email, organization and contact number, validated in the browser *and* on the server |
| 🔳 **Unique QR ticket** | Each ticket holds a random token, never the person's email or phone number |
| ✉️ **Ticket email** | HTML email with the QR inline, `ticket.png` attached, a plain-text version, and the **ticket code as text** as a fallback when a QR can't be scanned |
| ✅ **Check-in** | Camera scan, USB scanner, or type/paste the ticket code. Green = checked in, yellow = already used, red = invalid |
| 🔒 **One-time tickets** | Check-in is a single atomic database update, so a ticket can never be used twice |
| 📋 **Staff dashboard** | Live counters, search, status badges, CSV export, resend ticket email |
| 🔄 **Reset tools** | Staff can reset all check-ins, or delete all attendees, to run a demo again |
| 🧪 **Dry-run email mode** | With no Gmail login set, emails are saved to `outbox/` instead of sent |

---

## 🧭 How it works

```
Participant                         Server                              Staff
-----------                         ------                              -----
fills the form  ───────────►  validate → save (random token)
                              create QR image (qrcodes/<token>.png)
inbox  ◄──────────────────── email QR + ticket code (background thread)
                                                                  scans QR / types code
                              POST /api/checkin  ◄──────────────────────────┘
                              UPDATE ... WHERE status='Registered'
                              green / yellow / red result  ─────────────────►
```

---

## 🚀 Quick start

```bash
python -m venv venv
venv\Scripts\activate            # Windows   (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env           # Mac/Linux: cp .env.example .env  - then edit .env
python app.py
```

Open **http://localhost:5000** for the registration form. Staff pages are `/checkin` and `/attendees` (PIN protected).

### Configuration (`.env`)

| Key | Meaning |
|---|---|
| `FLASK_SECRET_KEY` | Signs the login cookie. **Set long random text.** |
| `STAFF_PIN` | PIN for `/checkin`, `/attendees`, CSV, resend and reset. **Change the default `1234`.** |
| `EVENT_NAME` / `EVENT_DATE` / `EVENT_VENUE` | Shown on the pages and in the email |
| `SMTP_HOST` / `SMTP_PORT` | `smtp.gmail.com` / `465` (SSL). Any other port uses STARTTLS (587) |
| `SMTP_USER` / `SMTP_APP_PASSWORD` | Gmail address and a 16-character Google App Password |
| `MAIL_FROM_NAME` | Sender display name |

> **Sending real email with Gmail:** turn on 2-Step Verification, create an **App password** (Google Account → Security → App passwords), put it in `SMTP_APP_PASSWORD`, then restart the app.
>
> **Dry-run mode:** if `SMTP_USER` or `SMTP_APP_PASSWORD` is empty, nothing is sent. The full `.eml` and QR PNG are saved in `outbox/` and the attendee's `email_status` becomes `dry_run`.

---

## 👥 Using it

### Participant
1. Open the site and fill in the form, then press **Register**.
2. Open the email. It contains the **QR code** and a **ticket code**.
3. At the entrance, show the QR. If it can't be scanned, give staff the ticket code.

### Staff
1. Go to **/checkin** and log in with the staff PIN.
2. Scan the QR with the camera, or type/paste the ticket code and press **Enter**.
3. Read the result card:

| Card | Meaning |
|---|---|
| 🟩 Green | Checked in. Shows name and organization |
| 🟨 Yellow | Already checked in. Shows the time of the first check-in |
| 🟥 Red | Invalid ticket |

4. **/attendees** shows registered / checked-in / not-yet-arrived counters, a search box, status badges, **Download CSV**, and a **Resend** button per person.

### Resetting for a demo
At the bottom of **/attendees** (staff only, each asks for confirmation):
- **Reset all check-ins** sets everyone back to *Registered* and keeps the registrations.
- **Delete all attendees** removes everyone and their QR files, so the same emails can register again.

---

## 🗂 Project structure

```
event-checkin/
├── app.py            Flask app: routes, validation, staff PIN login
├── db.py             SQLite helpers (add, list, check in, reset, delete)
├── qr_utils.py       Generates qrcodes/<token>.png
├── mailer.py         Builds and sends the ticket email (or dry-run)
├── templates/        register, success, login, checkin, attendees pages
├── static/           style.css, register.js, checkin.js
├── tests/            test_flow.py (end-to-end test)
├── .env.example      Settings template
└── requirements*.txt
```

### Routes

| Route | Access | Purpose |
|---|---|---|
| `GET /` · `POST /register` · `GET /success` | Public | Registration form, submit, confirmation |
| `GET /login` · `GET /logout` | Public | Staff PIN login |
| `GET /checkin` · `POST /api/checkin` | Staff | Scanner page and check-in API |
| `GET /attendees` · `GET /attendees.csv` | Staff | Attendee list and CSV export |
| `POST /admin/resend/<id>` | Staff | Re-send a ticket email |
| `POST /admin/reset-checkins` · `POST /admin/delete-all` | Staff | Reset tools |

### Database

One table, `attendees`: `id`, `full_name`, `email` (UNIQUE), `organization`, `contact_number`, `ticket_token` (UNIQUE), `qr_path`, `email_status` (`pending` / `sent` / `failed` / `dry_run`), `status` (`Registered` / `Checked In`), `registered_at`, `checked_in_at`.

---

## 🛡 Design & security decisions

- The **QR holds only a random token**, so a photographed ticket reveals nothing personal.
- **Atomic check-in:** one `UPDATE ... WHERE status='Registered'` means two simultaneous scans can't both succeed.
- **Duplicate emails** hit the `UNIQUE` constraint and show a friendly error. No second row is created.
- **Email never blocks registration:** it is sent in a background thread. A failure sets `email_status = failed` and can be retried with **Resend**.
- **Staff PIN** is one shared value kept in a signed session cookie (no user accounts), compared in constant time, with an open-redirect guard on `next`.
- **Cookie** uses `SameSite=Lax`, so other websites can't trigger the staff reset actions.
- **CSV export** prefixes cells starting with `=`, `+`, `-` or `@` so spreadsheets don't run them as formulas.

---

## 🧪 Testing

```bash
pip install -r requirements-test.txt     # adds OpenCV, used to decode the QR PNGs
python tests/test_flow.py
```

The test uses a temporary database, so your real `data/event.db` stays untouched. It covers the form and validation, duplicate emails, QR decoding, unique QRs, the dry-run email, check-in, already-used and invalid tickets, and PIN protection.

---

## 📱 Scanning with a phone camera

Browsers only allow camera access on `https://` or `http://localhost`. A laptop on `localhost` is fine. For a phone, run a free tunnel while the app is running:

```bash
winget install Cloudflare.cloudflared
cloudflared tunnel --url http://localhost:5000
```

Open the printed `https://….trycloudflare.com/checkin` on the phone. No camera? Use the ticket-code box or a USB scanner instead.

---

## ⚠️ Notes & limitations

- The scanner library (`html5-qrcode`) loads from a CDN (unpkg), so the check-in page needs internet.
- One shared staff PIN, with no limit on wrong attempts.
- No CAPTCHA on the public form.
- Email delivery depends on Gmail's sending limits.
- Before a real event, clear test data with the **Delete all attendees** button. The local `data/`, `qrcodes/` and `outbox/` folders are git-ignored.
