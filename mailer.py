"""Email sending: Gmail SMTP, or dry-run (.eml saved to outbox/) when no credentials."""
import html
import logging
import os
import smtplib
from email.message import EmailMessage
from email.utils import formataddr

import db

log = logging.getLogger("mailer")


def build_message(att, qr_path, sender):
    name = att["full_name"]
    event = os.environ.get("EVENT_NAME", "EVENT_NAME")
    date = os.environ.get("EVENT_DATE", "")
    venue = os.environ.get("EVENT_VENUE", "")

    msg = EmailMessage()
    msg["Subject"] = f"Your ticket for {event}"
    msg["From"] = formataddr((os.environ.get("MAIL_FROM_NAME", "Event Registration"), sender))
    msg["To"] = att["email"]

    # Plain-text fallback
    msg.set_content(
        f"Hi {name},\n\nYou're registered for {event}.\nDate: {date}\nVenue: {venue}\n\n"
        "Show the QR code (attached as ticket.png) at the entrance.\n"
    )
    # HTML version with the QR shown inline via CID
    msg.add_alternative(
        f"""<html><body style="font-family:Arial,sans-serif;color:#222">
<h2>Hi {html.escape(name)},</h2>
<p>You're registered for <b>{html.escape(event)}</b>.</p>
<p>&#128197; {html.escape(date)}<br>&#128205; {html.escape(venue)}</p>
<p>Show this QR code at the entrance:</p>
<p><img src="cid:qrcode" alt="Your QR ticket" width="260" height="260"></p>
<p style="color:#666;font-size:13px">The same image is attached as ticket.png as a backup.</p>
</body></html>""",
        subtype="html",
    )
    with open(qr_path, "rb") as f:
        data = f.read()
    # Inline image (related to the HTML part) + separate attachment backup
    msg.get_payload()[1].add_related(data, "image", "png", cid="<qrcode>")
    msg.add_attachment(data, maintype="image", subtype="png", filename="ticket.png")
    return msg


def send_ticket(att_id):
    """Send (or dry-run) the ticket email and record the result. Never raises."""
    try:
        att = db.get_attendee(att_id)
        user = os.environ.get("SMTP_USER", "").strip()
        password = os.environ.get("SMTP_APP_PASSWORD", "").strip()
        msg = build_message(att, att["qr_path"], user or "noreply@example.com")

        if not user or not password:
            outbox = os.environ.get("OUTBOX_DIR", "outbox")
            os.makedirs(outbox, exist_ok=True)
            token = att["ticket_token"]
            with open(os.path.join(outbox, f"{token}.eml"), "wb") as f:
                f.write(bytes(msg))
            with open(att["qr_path"], "rb") as src, open(
                os.path.join(outbox, f"{token}.png"), "wb"
            ) as dst:
                dst.write(src.read())
            db.set_email_status(att_id, "dry_run")
            log.warning("DRY RUN: saved email for %s to %s/", att["email"], outbox)
            return

        host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
        port = int(os.environ.get("SMTP_PORT", "465"))
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=30) as s:
                s.login(user, password)
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=30) as s:
                s.starttls()
                s.login(user, password)
                s.send_message(msg)
        db.set_email_status(att_id, "sent")
        log.info("Email sent to %s", att["email"])
    except Exception:
        log.exception("Email failed for attendee %s", att_id)
        try:
            db.set_email_status(att_id, "failed")
        except Exception:
            pass
