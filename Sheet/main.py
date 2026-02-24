

import os
import pathlib
import datetime
import threading
import socket
import webbrowser
import warnings

import urllib3
warnings.filterwarnings(
    "ignore",
    category=urllib3.exceptions.NotOpenSSLWarning,
    message="urllib3 v2 only supports OpenSSL 1.1.1+",
)

from flask import Flask, request, session, redirect, url_for, render_template_string
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ──────── CONFIG ────────a
SPREADSHEET_ID = "1igokZF1o_inrjyGNN6Tctg-2BLD_hXLmm0lDSR0C3J4"

TABS         = ["Coop", "Migros", "Paff", "Milchhüsli", "Diverse"]
DESTINATIONS = ["Liestal", "Seltisberg", "Frenkendorf", "Buebendorf", "Lausen"]
DAYS_BACK    = 14
SCOPES       = ["https://www.googleapis.com/auth/spreadsheets"]

TOKEN_FILE   = "token.json"
SECRETS_FILE = "credentials.json"          # ⇦ desktop-app JSON from Cloud Console
# ─────────────────────────

app = Flask(__name__)
app.secret_key = os.urandom(24)
_service = None                               # cached Sheets client


# ─────── GOOGLE SHEETS HELPER ───────
def get_sheets_service():
    """Return an authorised Sheets service, recovering if token is invalid."""
    global _service
    if _service:
        return _service

    creds = None
    if pathlib.Path(TOKEN_FILE).exists():
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    # Try refreshing existing creds
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except RefreshError:
            print("Saved Google token expired or revoked – re-authorising…")
            creds = None
            pathlib.Path(TOKEN_FILE).unlink(missing_ok=True)

    # Launch OAuth flow if no valid creds
    if not creds or not creds.valid:
        flow  = InstalledAppFlow.from_client_secrets_file(SECRETS_FILE, SCOPES)
        creds = flow.run_local_server(port=0)           # any free port
        pathlib.Path(TOKEN_FILE).write_text(creds.to_json())

    _service = build("sheets", "v4", credentials=creds)
    return _service


def append_entry(entry):
    """Append a single row (runs in a background thread)."""
    def task():
        try:
            sheet     = get_sheets_service()
            tab_range = f"{entry['store']}!A:A"
            existing  = sheet.spreadsheets().values().get(
                spreadsheetId=SPREADSHEET_ID, range=tab_range
            ).execute().get("values", [])
            next_row  = len(existing) + 1
            row       = [
                entry['date'],
                entry['weekday'],
                entry['abo_nr'] or '',
                str(entry['vignette']),
                entry['destination'],
            ]
            sheet.spreadsheets().values().append(
                spreadsheetId=SPREADSHEET_ID,
                range=f"{entry['store']}!A{next_row}:E{next_row}",
                valueInputOption="USER_ENTERED",
                body={"values": [row]},
            ).execute()
        except HttpError as e:
            print("Error appending entry:", e)
    threading.Thread(target=task, daemon=True).start()


# ─────── HTML SNIPPETS ───────
BASE_HEADER = '''<!doctype html><html><head><meta charset="utf-8">
<title>{{ title }}</title><style>
  body { font-family: Arial, sans-serif; text-align:center; padding:2rem; background:#f9f9f9; }
  h2   { margin-bottom:1rem; }
  .btn { margin:0.5rem; padding:0.75rem 1.5rem; font-size:1rem; border:none; border-radius:0.3rem;
         background:#007acc; color:#fff; cursor:pointer; }
  .btn:hover { background:#005fab; }
  form { display:inline-block; }
</style></head><body>'''
BASE_FOOTER = "</body></html>"


# ─────── ROUTES ───────
@app.route("/")
def index():
    return redirect(url_for("store"))


@app.route("/store", methods=["GET", "POST"])
def store():
    if request.method == "POST":
        session.clear()
        session["entry"] = {"store": request.form["store"]}
        return redirect(url_for("date"))

    buttons = "".join(
        f'<button class="btn" name="store" value="{s}">{s}</button>' for s in TABS
    )
    return render_template_string(
        BASE_HEADER + "<h2>Select store</h2><form method='post'>"
        + buttons
        + "</form>"
        + BASE_FOOTER,
        title="Select store",
    )


@app.route("/date", methods=["GET", "POST"])
def date():
    if request.method == "POST":
        entry            = session.get("entry", {})
        entry["date"]    = request.form["date"]
        entry["weekday"] = datetime.datetime.strptime(
            entry["date"], "%Y-%m-%d"
        ).strftime("%a")
        session["entry"] = entry
        return redirect(url_for("abo"))

    dates   = [
        (datetime.date.today() - datetime.timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range(DAYS_BACK + 1)
    ]
    buttons = "".join(
        f'<button class="btn" name="date" value="{d}">{d[5:]}</button>' for d in dates
    )
    return render_template_string(
        BASE_HEADER + "<h2>Select date</h2><form method='post'>"
        + buttons
        + "</form>"
        + BASE_FOOTER,
        title="Select date",
    )


@app.route("/abo", methods=["GET", "POST"])
def abo():
    if request.method == "POST":
        entry             = session.get("entry", {})
        entry["abo_nr"]   = request.form.get("abo_nr") or None
        entry["vignette"] = int(request.form["vignette"])
        session["entry"]  = entry
        return redirect(url_for("destination"))

    return render_template_string(
        BASE_HEADER
        + "<h2>Abo / Vignette</h2><form method='post'>"
        "<input type='text' name='abo_nr' placeholder='Abo number' "
        "style='padding:0.5rem;font-size:1rem;margin-bottom:1rem;'><br>"
        "<button class='btn' name='vignette' value='1'>Normal</button>"
        "<button class='btn' name='vignette' value='2'>Express</button></form>"
        + BASE_FOOTER,
        title="Abo / Vignette",
    )


@app.route("/destination", methods=["GET", "POST"])
def destination():
    if request.method == "POST":
        entry                = session.get("entry", {})
        entry["destination"] = request.form["destination"]
        session["entry"]     = entry
        return redirect(url_for("review"))

    buttons = "".join(
        f'<button class="btn" name="destination" value="{d}">{d}</button>'
        for d in DESTINATIONS
    )
    return render_template_string(
        BASE_HEADER + "<h2>Select destination</h2><form method='post'>"
        + buttons
        + "</form>"
        + BASE_FOOTER,
        title="Select destination",
    )


@app.route("/review", methods=["GET", "POST"])
def review():
    entry = session.get("entry", {})

    if request.method == "POST":
        action = request.form.get("action")
        if action == "commit":
            append_entry(entry)
            return redirect(url_for("success"))

        # restart
        session.clear()
        return redirect(url_for("store"))

    ...

    return render_template_string(
        BASE_HEADER
        + "<h2>Review</h2>"
        f"<pre style='text-align:left;display:inline-block;'>{summary}</pre>"
        "<form method='post'>"
        "<button class='btn' name='action' value='commit'>Commit</button>"
        "<button class='btn' name='action' value='restart'>Restart</button></form>"
        + BASE_FOOTER,
        title="Review",
    )


@app.route("/success")
def success():
    return render_template_string(
        BASE_HEADER
        + "<h2>Entry committed!</h2>"
        "<button class='btn' onclick=\"window.location.href='/'\">New entry</button>"
        + BASE_FOOTER,
        title="Success",
    )


# ─────── MAIN ───────
if __name__ == "__main__":
    # Ensure credentials exist before the UI starts
    get_sheets_service()

    # Find a free port for Flask
    sock = socket.socket()
    port = 5000
    while True:
        try:
            sock.bind(("127.0.0.1", port))
            sock.close()
            break
        except OSError:
            port += 1

    url = f"http://localhost:{port}"
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    app.run(host="127.0.0.1", port=port, debug=False)
