"""Render a personalized invitation draft from the editable template."""
import config


def _load_template():
    try:
        with open(config.TEMPLATE_FILE, encoding="utf-8") as fh:
            return fh.read()
    except FileNotFoundError:
        return (
            "Subject: Invitation to {event_name}\n\n"
            "Hi {merchant_name} team,\n\n"
            "We'd love to invite you to {event_name} on {event_date} at "
            "{event_location}. Details: {event_details_url}\n\n"
            "Best,\n{organizer_name}\n"
        )


def save_template(text):
    with open(config.TEMPLATE_FILE, "w", encoding="utf-8") as fh:
        fh.write(text)


def load_template_text():
    return _load_template()


def _context_for(merchant):
    ctx = dict(config.EVENT)
    ctx["merchant_name"] = merchant["name"]
    ctx["merchant_category"] = merchant["category"] or ""
    return ctx


def render_draft(merchant):
    """Return (subject, body). The template's first `Subject:` line becomes the subject."""
    template = _load_template()
    ctx = _context_for(merchant)
    try:
        rendered = template.format(**ctx)
    except KeyError as exc:
        # Unknown placeholder in the template; surface it rather than crashing.
        rendered = template + f"\n\n[template error: unknown placeholder {exc}]"

    subject = f"Invitation to {ctx['event_name']}"
    body = rendered
    lines = rendered.splitlines()
    if lines and lines[0].lower().startswith("subject:"):
        subject = lines[0].split(":", 1)[1].strip()
        body = "\n".join(lines[1:]).lstrip("\n")
    return subject, body
