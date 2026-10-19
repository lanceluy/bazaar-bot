# Bazaar Merchant Outreach Bot

A small local web app that helps a bazaar organizer recruit merchants:

1. **Find** merchants by category + location (Google Places API).
2. **Look up** a contact email from each merchant's website.
3. **Draft** a personalized invitation for each one.
4. **Review** every draft and approve the ones you want.
5. **Send** approved invitations through your Gmail — throttled, with an
   automatic opt-out line and your postal address on every message.

> **Nothing is ever sent without your approval.** This is deliberate: unsolicited
> bulk email is regulated (CAN-SPAM, CASL, GDPR/PECR) and careless sending can get
> your Gmail account throttled or blocked.

---

## Setup

### 1. Install Python deps
```bash
cd bazaar-bot
python -m venv .venv
# Windows:  .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Google Places API key
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a project, then enable **Places API (New)**.
3. Create an **API key** under *APIs & Services → Credentials*.
4. (Recommended) restrict the key to the Places API.

> Places gives you business names and websites but rarely an email, so the app
> visits each website and extracts a likely contact address. Some sites won't
> have one — you can type it in manually on the Review page.

### 3. Gmail App Password
1. Enable **2-Step Verification** on the Gmail account.
2. Create an **App Password** at <https://myaccount.google.com/apppasswords>.
3. Use that 16-character password (not your normal password).

### 4. Configure
Copy `.env.example` to `.env` and fill in your values:
```bash
cp .env.example .env   # Windows: copy .env.example .env
```
Fill in the API key, Gmail address + app password, your event details, and a real
**postal address** (required for a compliant footer).

### 5. Run
```bash
python app.py
```
Open <http://localhost:5000>.

---

## How to use it

- **Dashboard** → enter a search ("craft shops", "Austin, TX") and click
  *Search & draft*. Merchants are added and drafts generated automatically.
  Duplicates and do-not-contact addresses are skipped.
- **Review & Send** → edit the email address and message for each merchant,
  **Approve**, then **Send all approved** (or *Send now* on a single row).
- **Template** → edit the invitation wording and placeholders.
- **Do-not-contact** → anyone here is excluded from discovery and sending. The
  footer tells recipients to reply "unsubscribe"; add those replies here.

### Recommended first test
Before contacting anyone real, approve a single row whose email is **your own
address** and press *Send now*. Confirm it arrives with the correct footer.

---

## Good-practice tips

- Start small (10–20 at a time); Gmail limits ~500 recipients/day and dislikes
  sudden bulk.
- Keep the message genuinely relevant and easy to opt out of.
- Honor every opt-out immediately via the Do-not-contact page.
- Consider warming up a dedicated address rather than your personal Gmail.

## Files
| File | Purpose |
|------|---------|
| `app.py` | Flask routes / web UI |
| `discovery.py` | Google Places search + website email extraction |
| `drafts.py` | Renders the invitation template per merchant |
| `emailer.py` | Gmail SMTP send (footer + throttle) — the only send path |
| `db.py` | SQLite storage (merchants, drafts, send log, suppression) |
| `config.py` | Loads `.env` |
| `invitation.txt` | Editable email body template |

## Swapping Gmail for a bulk provider
For higher volume or better deliverability, `emailer.send_email()` is the single
send path — reimplement it against SendGrid / Mailgun / Amazon SES and nothing
else needs to change.
