"""Merchant discovery: Google Places (New) text search + website email extraction."""
import re
import urllib.parse

import requests

import config

PLACES_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"

# Fields we ask Places to return (billed by field mask).
_FIELD_MASK = (
    "places.id,"
    "places.displayName,"
    "places.formattedAddress,"
    "places.websiteUri,"
    "places.primaryTypeDisplayName,"
    "places.types"
)

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
# Addresses that are almost never a real contact and that we skip.
_JUNK_EMAIL_HINTS = ("example.com", "sentry", "wixpress", ".png", ".jpg", ".webp",
                     "@2x", "domain.com", "email.com", "yourdomain")
# Preferred local-parts when several emails are found.
_PREFERRED_LOCALPARTS = ("info", "contact", "hello", "hi", "sales", "events",
                         "office", "admin", "mail")

_HEADERS_BROWSERISH = {
    "User-Agent": "Mozilla/5.0 (compatible; BazaarOutreachBot/1.0)"
}


class DiscoveryError(Exception):
    pass


def search_places(query, location=None, radius_m=None, max_results=20):
    """Call Places Text Search (New). Returns a list of place dicts.

    `query` e.g. "craft shops"; `location` is appended as free text e.g. "Austin, TX".
    """
    if not config.GOOGLE_PLACES_API_KEY:
        raise DiscoveryError("GOOGLE_PLACES_API_KEY is not set.")

    text_query = query.strip()
    if location:
        text_query = f"{text_query} in {location.strip()}"

    body = {
        "textQuery": text_query,
        "maxResultCount": max(1, min(int(max_results or 20), 20)),
    }
    # Optional location bias (circle) if a radius is provided along with no
    # textual location. We keep it simple and rely mainly on the text query.
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": config.GOOGLE_PLACES_API_KEY,
        "X-Goog-FieldMask": _FIELD_MASK,
    }
    try:
        resp = requests.post(PLACES_SEARCH_URL, json=body, headers=headers, timeout=20)
    except requests.RequestException as exc:
        raise DiscoveryError(f"Network error calling Google Places: {exc}") from exc

    if resp.status_code != 200:
        detail = ""
        try:
            detail = resp.json().get("error", {}).get("message", "")
        except Exception:
            detail = resp.text[:200]
        raise DiscoveryError(
            f"Google Places returned HTTP {resp.status_code}. {detail}".strip()
        )

    data = resp.json()
    return data.get("places", [])


def _score_email(email):
    local = email.split("@", 1)[0].lower()
    for i, pref in enumerate(_PREFERRED_LOCALPARTS):
        if local == pref or local.startswith(pref):
            return i
    return len(_PREFERRED_LOCALPARTS) + 1


def _emails_from_html(html):
    found = set()
    # mailto links first
    for m in re.findall(r'mailto:([^"\'>?\s]+)', html, flags=re.IGNORECASE):
        e = urllib.parse.unquote(m).strip()
        if _EMAIL_RE.fullmatch(e):
            found.add(e)
    # bare addresses in text
    for m in _EMAIL_RE.findall(html):
        found.add(m.strip())
    # filter junk
    clean = [
        e for e in found
        if not any(h in e.lower() for h in _JUNK_EMAIL_HINTS)
    ]
    return clean


def extract_email_from_site(website, max_pages=3):
    """Fetch the homepage and a couple of likely contact pages, return best email.

    Returns the chosen email string, or None. Never raises on network issues.
    """
    if not website:
        return None

    base = website.rstrip("/")
    candidates = [base]
    for path in ("/contact", "/contact-us", "/about"):
        candidates.append(base + path)
    candidates = candidates[: max(1, max_pages + 1)]

    emails = []
    for url in candidates:
        try:
            resp = requests.get(
                url, headers=_HEADERS_BROWSERISH, timeout=12, allow_redirects=True
            )
        except requests.RequestException:
            continue
        if resp.status_code != 200 or not resp.text:
            continue
        emails.extend(_emails_from_html(resp.text))
        if emails and url == base:
            # homepage already had something; still check one contact page then stop
            pass

    if not emails:
        return None

    # de-dupe preserving best score
    unique = sorted(set(e.lower() for e in emails), key=_score_email)
    return unique[0]


def place_to_record(place):
    """Flatten a Places result into the fields we store."""
    name = (place.get("displayName") or {}).get("text") or "(unknown)"
    website = place.get("websiteUri") or ""
    category = (place.get("primaryTypeDisplayName") or {}).get("text") or ""
    place_id = place.get("id") or ""
    address = place.get("formattedAddress") or ""
    return {
        "name": name,
        "website": website,
        "category": category,
        "place_id": place_id,
        "address": address,
    }
