"""Flask app + routes for the event registration / QR ticket / check-in system."""
import csv
import hmac
import io
import logging
import os
import re
import secrets
import sqlite3
import threading
from functools import wraps

from dotenv import load_dotenv
from flask import (Flask, Response, abort, jsonify, redirect, render_template,
                   request, session, url_for)

load_dotenv()

import db  # noqa: E402  (after load_dotenv so DB_PATH from .env is honoured)
import mailer  # noqa: E402
import qr_utils  # noqa: E402

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-me")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+?\d{10,13}$")


@app.context_processor
def inject_event():
    return {"event_name": os.environ.get("EVENT_NAME", "EVENT_NAME")}


# ---------- staff PIN protection ----------
def staff_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get("staff"):
            if request.path.startswith("/api/"):
                return jsonify(status="error", message="Login required"), 401
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapper


@app.route("/login", methods=["GET", "POST"])
def login():
    nxt = request.values.get("next", "/checkin")
    if not nxt.startswith("/") or nxt.startswith("//"):  # avoid open redirect
        nxt = "/checkin"
    error = None
    if request.method == "POST":
        pin = os.environ.get("STAFF_PIN", "1234")
        if hmac.compare_digest(request.form.get("pin", ""), pin):
            session["staff"] = True
            return redirect(nxt)
        error = "Wrong PIN"
    return render_template("login.html", error=error, next=nxt)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("register"))


# ---------- Task 1 + 2: registration ----------
def validate(form):
    name = form.get("full_name", "").strip()
    email = form.get("email", "").strip().lower()
    org = form.get("organization", "").strip()
    contact = re.sub(r"[\s-]", "", form.get("contact_number", ""))
    errors = {}
    if not 2 <= len(name) <= 100:
        errors["full_name"] = "Name must be 2 to 100 characters."
    if not EMAIL_RE.match(email) or len(email) > 254:
        errors["email"] = "Enter a valid email address."
    if not 2 <= len(org) <= 100:
        errors["organization"] = "Organization must be 2 to 100 characters."
    if not PHONE_RE.match(contact):
        errors["contact_number"] = "Use a format like 09171234567 or +639171234567."
    return dict(full_name=name, email=email, organization=org,
                contact_number=contact), errors


@app.route("/")
def register():
    return render_template("register.html", values={}, errors={})


@app.route("/register", methods=["POST"])
def register_post():
    values, errors = validate(request.form)
    if errors:
        return render_template("register.html", values=values, errors=errors), 400

    token = secrets.token_urlsafe(16)
    try:
        att_id = db.add_attendee(values["full_name"], values["email"],
                                 values["organization"], values["contact_number"], token)
    except sqlite3.IntegrityError:
        errors["email"] = "This email is already registered."
        return render_template("register.html", values=values, errors=errors), 409

    db.set_qr_path(att_id, qr_utils.make_qr(token))

    # Send email in the background so the form responds fast.
    if os.environ.get("SYNC_EMAIL") == "1":  # used by tests
        mailer.send_ticket(att_id)
    else:
        threading.Thread(target=mailer.send_ticket, args=(att_id,), daemon=True).start()
    return redirect(url_for("success"))


@app.route("/success")
def success():
    return render_template("success.html")


# ---------- Task 4: check-in ----------
@app.route("/checkin")
@staff_required
def checkin_page():
    return render_template("checkin.html")


@app.route("/api/checkin", methods=["POST"])
@staff_required
def api_checkin():
    token = str((request.get_json(silent=True) or {}).get("token", "")).strip()
    result, row = db.check_in(token) if token else ("invalid", None)
    if result == "invalid":
        return jsonify(status="invalid", message="Invalid ticket")
    data = dict(name=row["full_name"], organization=row["organization"])
    if result == "ok":
        return jsonify(status="ok", message="Checked in", **data)
    return jsonify(status="already", message="Already checked in at "
                   + row["checked_in_at"][11:16], **data)


# ---------- admin ----------
@app.route("/attendees")
@staff_required
def attendees():
    rows = db.list_attendees()
    checked = sum(1 for r in rows if r["status"] == "Checked In")
    return render_template("attendees.html", rows=rows, total=len(rows), checked=checked)


@app.route("/attendees.csv")
@staff_required
def attendees_csv():
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Name", "Email", "Organization", "Contact", "Status",
                "Email Status", "Registered At", "Checked In At"])
    for r in db.list_attendees():
        # Prefix risky leading chars so spreadsheets don't run user input as formulas
        safe = lambda s: "'" + s if s[:1] in ("=", "+", "-", "@") else s  # noqa: E731
        w.writerow([safe(r["full_name"]), safe(r["email"]), safe(r["organization"]),
                    r["contact_number"], r["status"], r["email_status"],
                    r["registered_at"], r["checked_in_at"] or ""])
    return Response(out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=attendees.csv"})


@app.route("/admin/resend/<int:att_id>", methods=["POST"])
@staff_required
def resend(att_id):
    if db.get_attendee(att_id) is None:
        abort(404)
    threading.Thread(target=mailer.send_ticket, args=(att_id,), daemon=True).start()
    return redirect(url_for("attendees"))


db.init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
