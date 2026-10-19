"""Gmail SMTP sending. Single choke point so compliance rules can't be bypassed."""
import smtplib
import time
from email.message import EmailMessage
from email.utils import formataddr

import config
import db

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

_last_send_ts = 0.0


class EmailError(Exception):
    pass


def _footer(to_email):
    """CAN-SPAM style footer: who it's from, how to opt out, physical address."""
    return (
        "\n\n---\n"
        f"You received this because we think {config.EVENT['event_name']} may be "
        "relevant to your business.\n"
        f"To opt out of future emails, reply with \"unsubscribe\" and we will add "
        f"{to_email} to our do-not-contact list.\n"
        f"{config.SENDER_POSTAL_ADDRESS}\n"
    )


def build_message(to_email, subject, body):
    msg = EmailMessage()
    msg["From"] = formataddr((config.SENDER_NAME, config.GMAIL_ADDRESS))
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body.rstrip() + _footer(to_email))
    return msg


def _throttle():
    global _last_send_ts
    wait = config.SEND_THROTTLE_SECONDS - (time.time() - _last_send_ts)
    if wait > 0:
        time.sleep(wait)
    _last_send_ts = time.time()


def send_email(to_email, subject, body, throttle=True):
    """Send a single email through Gmail SMTP. Raises EmailError on failure."""
    problems = config.missing_email_config()
    if problems:
        raise EmailError("Email not configured: " + "; ".join(problems))

    to_email = (to_email or "").strip()
    if not to_email:
        raise EmailError("No recipient email address.")
    if db.is_suppressed(to_email):
        raise EmailError(f"{to_email} is on the suppression (do-not-contact) list.")

    if throttle:
        _throttle()

    msg = build_message(to_email, subject, body)
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.starttls()
            server.login(config.GMAIL_ADDRESS, config.GMAIL_APP_PASSWORD)
            server.send_message(msg)
    except smtplib.SMTPAuthenticationError as exc:
        raise EmailError(
            "Gmail rejected the login. Check GMAIL_ADDRESS and that "
            "GMAIL_APP_PASSWORD is a valid App Password (not your normal password). "
            f"[{exc.smtp_code}]"
        ) from exc
    except (smtplib.SMTPException, OSError) as exc:
        raise EmailError(f"Failed to send: {exc}") from exc
