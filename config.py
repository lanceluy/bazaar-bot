"""Central configuration loaded from the environment (.env)."""
import os
from dotenv import load_dotenv

load_dotenv()


def _get(key, default=""):
    return os.environ.get(key, default).strip()


# Google Places
GOOGLE_PLACES_API_KEY = _get("GOOGLE_PLACES_API_KEY")

# Gmail
GMAIL_ADDRESS = _get("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = _get("GMAIL_APP_PASSWORD")
SENDER_NAME = _get("SENDER_NAME", "Bazaar Team")

# Sending behaviour
try:
    SEND_THROTTLE_SECONDS = float(_get("SEND_THROTTLE_SECONDS", "8"))
except ValueError:
    SEND_THROTTLE_SECONDS = 8.0

# Event details (available to the invitation template)
EVENT = {
    "event_name": _get("EVENT_NAME", "Our Bazaar"),
    "event_date": _get("EVENT_DATE", "TBD"),
    "event_location": _get("EVENT_LOCATION", "TBD"),
    "event_details_url": _get("EVENT_DETAILS_URL", ""),
    "organizer_name": _get("ORGANIZER_NAME", "The Organizer"),
}

# Compliance
SENDER_POSTAL_ADDRESS = _get(
    "SENDER_POSTAL_ADDRESS", "(set SENDER_POSTAL_ADDRESS in .env)"
)

# Flask
FLASK_SECRET_KEY = _get("FLASK_SECRET_KEY", "dev-insecure-key")

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "bazaar.db")
TEMPLATE_FILE = os.path.join(BASE_DIR, "invitation.txt")


def missing_email_config():
    """Return a list of human-readable config problems that block sending."""
    problems = []
    if not GMAIL_ADDRESS:
        problems.append("GMAIL_ADDRESS is not set")
    if not GMAIL_APP_PASSWORD:
        problems.append("GMAIL_APP_PASSWORD is not set")
    if "set SENDER_POSTAL_ADDRESS" in SENDER_POSTAL_ADDRESS:
        problems.append("SENDER_POSTAL_ADDRESS is not set (required for a compliant footer)")
    return problems


def missing_discovery_config():
    problems = []
    if not GOOGLE_PLACES_API_KEY:
        problems.append("GOOGLE_PLACES_API_KEY is not set")
    return problems
