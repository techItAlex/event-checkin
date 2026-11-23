"""QR generation. The QR encodes ONLY the ticket token (never the email)."""
import os

import qrcode
from qrcode.constants import ERROR_CORRECT_M


def qr_dir():
    return os.environ.get("QR_DIR", "qrcodes")


def make_qr(token):
    """Save qrcodes/<token>.png and return its path."""
    os.makedirs(qr_dir(), exist_ok=True)
    path = os.path.join(qr_dir(), f"{token}.png")
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_M, box_size=10, border=4)
    qr.add_data(token)
    qr.make(fit=True)
    qr.make_image(fill_color="black", back_color="white").save(path)
    return path
