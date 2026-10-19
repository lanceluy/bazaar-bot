"""Bazaar Merchant Outreach Bot — local Flask web UI.

Run:  python app.py   then open http://localhost:5000
"""
from flask import (Flask, flash, redirect, render_template, request, url_for)

import config
import db
import drafts
import discovery
import emailer

app = Flask(__name__)
app.secret_key = config.FLASK_SECRET_KEY

db.init_db()


@app.route("/")
def dashboard():
    return render_template(
        "dashboard.html",
        counts=db.status_counts(),
        event=config.EVENT,
        discovery_problems=config.missing_discovery_config(),
        email_problems=config.missing_email_config(),
        recent=db.recent_sends(limit=15),
    )


@app.route("/discover", methods=["POST"])
def discover():
    query = (request.form.get("query") or "").strip()
    location = (request.form.get("location") or "").strip()
    max_results = request.form.get("max_results") or "20"
    find_emails = request.form.get("find_emails") == "on"

    if not query:
        flash("Enter what kind of merchants to search for.", "error")
        return redirect(url_for("dashboard"))

    problems = config.missing_discovery_config()
    if problems:
        flash("Cannot search: " + "; ".join(problems), "error")
        return redirect(url_for("dashboard"))

    try:
        places = discovery.search_places(query, location or None, max_results=max_results)
    except discovery.DiscoveryError as exc:
        flash(str(exc), "error")
        return redirect(url_for("dashboard"))

    source_query = query + (f" in {location}" if location else "")
    added, skipped_dup, skipped_suppressed = 0, 0, 0

    for place in places:
        rec = discovery.place_to_record(place)
        email = None
        if find_emails and rec["website"]:
            try:
                email = discovery.extract_email_from_site(rec["website"])
            except Exception:
                email = None
        if email and db.is_suppressed(email):
            skipped_suppressed += 1
            continue

        merchant_id, created = db.upsert_merchant(
            name=rec["name"],
            category=rec["category"],
            website=rec["website"],
            email=email,
            place_id=rec["place_id"],
            source_query=source_query,
        )
        if not created:
            skipped_dup += 1
            continue

        # Pre-generate a draft so review is one click.
        merchant = db.get_merchant(merchant_id)
        subject, body = drafts.render_draft(merchant)
        db.save_draft(merchant_id, subject, body)
        db.set_status(merchant_id, "drafted")
        added += 1

    msg = f"Found {len(places)} places · added {added} new merchant(s)."
    if skipped_dup:
        msg += f" Skipped {skipped_dup} already in your list."
    if skipped_suppressed:
        msg += f" Skipped {skipped_suppressed} on the do-not-contact list."
    flash(msg, "success")
    return redirect(url_for("review"))


@app.route("/review")
def review():
    merchants = db.list_merchants()
    rows = []
    for m in merchants:
        draft = db.get_draft(m["id"])
        rows.append({"merchant": m, "draft": draft})
    return render_template("review.html", rows=rows, event=config.EVENT)


@app.route("/merchant/<int:merchant_id>/save", methods=["POST"])
def save_merchant(merchant_id):
    merchant = db.get_merchant(merchant_id)
    if not merchant:
        flash("Merchant not found.", "error")
        return redirect(url_for("review"))

    email = (request.form.get("email") or "").strip()
    subject = (request.form.get("subject") or "").strip()
    body = (request.form.get("body") or "").strip()

    db.set_email(merchant_id, email)
    db.save_draft(merchant_id, subject, body)
    flash(f"Saved changes for {merchant['name']}.", "success")
    return redirect(url_for("review"))


@app.route("/merchant/<int:merchant_id>/approve", methods=["POST"])
def approve(merchant_id):
    merchant = db.get_merchant(merchant_id)
    if not merchant:
        flash("Merchant not found.", "error")
    elif not (merchant["email"] or "").strip():
        flash(f"Can't approve {merchant['name']}: no email address.", "error")
    else:
        db.set_status(merchant_id, "approved")
        flash(f"Approved {merchant['name']}.", "success")
    return redirect(url_for("review"))


@app.route("/merchant/<int:merchant_id>/skip", methods=["POST"])
def skip(merchant_id):
    db.set_status(merchant_id, "skipped")
    return redirect(url_for("review"))


@app.route("/merchant/<int:merchant_id>/suppress", methods=["POST"])
def suppress(merchant_id):
    merchant = db.get_merchant(merchant_id)
    if merchant and merchant["email"]:
        db.add_suppression(merchant["email"], reason="manual do-not-contact")
    db.set_status(merchant_id, "skipped")
    flash("Added to do-not-contact list.", "success")
    return redirect(url_for("review"))


@app.route("/send", methods=["POST"])
def send_approved():
    problems = config.missing_email_config()
    if problems:
        flash("Cannot send: " + "; ".join(problems), "error")
        return redirect(url_for("review"))

    approved = db.list_merchants(status="approved")
    if not approved:
        flash("Nothing approved to send. Approve some merchants first.", "error")
        return redirect(url_for("review"))

    sent, failed = 0, 0
    for m in approved:
        draft = db.get_draft(m["id"])
        if not draft:
            continue
        try:
            emailer.send_email(m["email"], draft["subject"], draft["body"])
            db.set_status(m["id"], "sent")
            db.log_send(m["id"], "ok")
            sent += 1
        except emailer.EmailError as exc:
            db.set_status(m["id"], "failed")
            db.log_send(m["id"], "error", str(exc))
            failed += 1

    flash(f"Sent {sent} email(s)." + (f" {failed} failed." if failed else ""),
          "success" if not failed else "error")
    return redirect(url_for("review"))


@app.route("/merchant/<int:merchant_id>/send", methods=["POST"])
def send_one(merchant_id):
    merchant = db.get_merchant(merchant_id)
    draft = db.get_draft(merchant_id) if merchant else None
    if not merchant or not draft:
        flash("Merchant or draft not found.", "error")
        return redirect(url_for("review"))
    try:
        emailer.send_email(merchant["email"], draft["subject"], draft["body"])
        db.set_status(merchant_id, "sent")
        db.log_send(merchant_id, "ok")
        flash(f"Sent to {merchant['name']}.", "success")
    except emailer.EmailError as exc:
        db.set_status(merchant_id, "failed")
        db.log_send(merchant_id, "error", str(exc))
        flash(f"Failed: {exc}", "error")
    return redirect(url_for("review"))


@app.route("/template", methods=["GET", "POST"])
def template_editor():
    if request.method == "POST":
        text = request.form.get("template") or ""
        drafts.save_template(text)
        flash("Template saved. New merchants will use it; "
              "re-generate existing drafts from Review if needed.", "success")
        return redirect(url_for("template_editor"))
    return render_template(
        "template.html", template_text=drafts.load_template_text(), event=config.EVENT
    )


@app.route("/merchant/<int:merchant_id>/regenerate", methods=["POST"])
def regenerate(merchant_id):
    merchant = db.get_merchant(merchant_id)
    if merchant:
        subject, body = drafts.render_draft(merchant)
        db.save_draft(merchant_id, subject, body)
        if merchant["status"] in ("found",):
            db.set_status(merchant_id, "drafted")
        flash(f"Regenerated draft for {merchant['name']}.", "success")
    return redirect(url_for("review"))


@app.route("/suppression", methods=["GET", "POST"])
def suppression():
    if request.method == "POST":
        email = request.form.get("email") or ""
        db.add_suppression(email, reason="manual")
        flash(f"Added {email} to do-not-contact list.", "success")
        return redirect(url_for("suppression"))
    return render_template("suppression.html", rows=db.list_suppression())


if __name__ == "__main__":
    app.run(debug=True, port=5000)
