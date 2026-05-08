import os
import datetime
import threading
import webbrowser
import socket
import json
from html import escape
from flask import Flask, request, session, redirect, render_template_string

# google imports
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# User-editable settings
CONFIG_FILE = os.environ.get("GSA_CONFIG_FILE", "config.json")
DEFAULT_CONFIG = {
    "sheet_id": "YOUR_GOOGLE_SHEET_ID",
    "flask_secret_key": "change-this-local-secret",
    "oauth_credentials_file": "credentials.json",
    "oauth_token_file": "token.json",
    "entry_types": ["Record Type A", "Record Type B", "Record Type"],
    "targets": ["Target A", "Target B", "Target C"],
    "days_back": 14,
    "option_labels": {
        "1": "Option A",
        "2": "Option B"
    }
}
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                loaded_config = json.load(f)
                return {**DEFAULT_CONFIG, **loaded_config}
        except Exception as e:
            print(f"Error loading config: {e}")
    else:
        # Create default config for the user to edit
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(DEFAULT_CONFIG, f, indent=4)
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()

config_data = load_config()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or config_data.get("flask_secret_key")

SHEET_ID = os.environ.get("GOOGLE_SHEET_ID") or config_data.get("sheet_id")
TOKEN = os.environ.get("GOOGLE_SHEETS_TOKEN_FILE") or config_data.get("oauth_token_file")
CREDS = os.environ.get("GOOGLE_SHEETS_CREDENTIALS_FILE") or config_data.get("oauth_credentials_file")

entry_types = config_data.get("entry_types", [])
targets = config_data.get("targets", [])
days_back = int(config_data.get("days_back", 14))
option_labels = config_data.get("option_labels", DEFAULT_CONFIG["option_labels"])

service = None

# get the google sheet service
def get_service():
    global service
    if service:
        return service

    if not SHEET_ID or SHEET_ID == DEFAULT_CONFIG["sheet_id"]:
        raise RuntimeError("Set sheet_id in config.json or GOOGLE_SHEET_ID before connecting.")

    if not os.path.exists(CREDS):
        raise RuntimeError(f"OAuth credentials file not found: {CREDS}")

    creds = None
    if os.path.exists(TOKEN):
        creds = Credentials.from_authorized_user_file(TOKEN, SCOPES)

    # refresh if needed
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDS, SCOPES)
            creds = flow.run_local_server(port=0)
        
        # save token
        with open(TOKEN, 'w') as token:
            token.write(creds.to_json())

    service = build("sheets", "v4", credentials=creds)
    return service

# background task to save data
def save_data(data):
    try:
        s = get_service()
        sheet_name = data['entry_type']
        
        # find the next empty row
        result = s.spreadsheets().values().get(spreadsheetId=SHEET_ID, range=sheet_name + "!A:A").execute()
        rows = result.get("values", [])
        next_row = len(rows) + 1
        
        # prepare the row
        new_row = [
            data['date'],
            data['weekday'],
            data['reference'],
            option_labels.get(str(data['option']), str(data['option'])),
            data['target']
        ]
        
        # append it
        range_name = sheet_name + "!A" + str(next_row)
        body = {'values': [new_row]}
        
        s.spreadsheets().values().append(
            spreadsheetId=SHEET_ID, 
            range=range_name,
            valueInputOption="USER_ENTERED", 
            body=body
        ).execute()
        print("Data saved successfully")
        
    except Exception as e:
        print("Error saving data: " + str(e))

def append_entry(entry):
    x = threading.Thread(target=save_data, args=(entry,))
    x.start()

# simple header for html
html_header = """
<html>
<head>
<style>
body { font-family: sans-serif; text-align: center; padding: 20px; background-color: #eee; }
.btn { padding: 10px 20px; margin: 5px; background: #007bff; color: white; border: none; cursor: pointer; }
.btn:hover { background: #0056b3; }
</style>
</head>
<body>
"""

@app.route("/")
def index():
    return redirect("/entry-type")

@app.route("/entry-type", methods=["GET", "POST"])
def entry_type():
    if request.method == "POST":
        session.clear() # reset session
        session["entry"] = {"entry_type": request.form["entry_type"]}
        return redirect("/date")

    buttons = ""
    for item in entry_types:
        safe_item = escape(item)
        buttons = buttons + '<button class="btn" name="entry_type" value="' + safe_item + '">' + safe_item + '</button>'
    
    return render_template_string(html_header + "<h2>Select Entry Type</h2><form method='post'>" + buttons + "</form></body></html>")

@app.route("/date", methods=["GET", "POST"])
def date():
    if request.method == "POST":
        entry = session.get("entry", {})
        entry["date"] = request.form["date"]
        
        # get weekday
        d = datetime.datetime.strptime(entry["date"], "%Y-%m-%d")
        entry["weekday"] = d.strftime("%a")
        
        session["entry"] = entry
        return redirect("/details")

    buttons = ""
    today = datetime.date.today()
    
    # loop for dates
    for i in range(days_back + 1):
        delta = datetime.timedelta(days=i)
        d = today - delta
        d_str = d.strftime("%Y-%m-%d")
        label = d_str[5:] # remove year
        buttons = buttons + '<button class="btn" name="date" value="' + d_str + '">' + label + '</button>'

    return render_template_string(html_header + "<h2>Select Date</h2><form method='post'>" + buttons + "</form></body></html>")

@app.route("/details", methods=["GET", "POST"])
def details():
    if request.method == "POST":
        entry = session.get("entry", {})
        
        val = request.form.get("reference")
        if val == "":
            entry["reference"] = None
        else:
            entry["reference"] = val
            
        entry["option"] = int(request.form["option"])
        session["entry"] = entry
        return redirect("/target")

    form = """
    <h2>Record Details</h2>
    <form method='post'>
    <input type='text' name='reference' placeholder='Reference'><br><br>
    <button class='btn' name='option' value='1'>Option A</button>
    <button class='btn' name='option' value='2'>Option B</button>
    </form>
    """
    return render_template_string(html_header + form + "</body></html>")

@app.route("/target", methods=["GET", "POST"])
def target():
    if request.method == "POST":
        entry = session.get("entry", {})
        entry["target"] = request.form["target"]
        session["entry"] = entry
        return redirect("/review")

    buttons = ""
    for item in targets:
        safe_item = escape(item)
        buttons = buttons + '<button class="btn" name="target" value="' + safe_item + '">' + safe_item + '</button>'
    
    return render_template_string(html_header + "<h2>Target</h2><form method='post'>" + buttons + "</form></body></html>")

@app.route("/review", methods=["GET", "POST"])
def review():
    entry = session.get("entry", {})
    
    if request.method == "POST":
        act = request.form.get("action")
        if act == "commit":
            append_entry(entry)
            return redirect("/success")
        else:
            session.clear()
            return redirect("/")

    data_str = escape(json.dumps(entry, indent=2))
    
    html = html_header + "<h2>Review</h2><pre>" + data_str + "</pre>"
    html += "<form method='post'>"
    html += "<button class='btn' name='action' value='commit'>Submit</button>"
    html += "<button class='btn' name='action' value='restart'>Restart</button>"
    html += "</form></body></html>"
    
    return render_template_string(html)

@app.route("/success")
def success():
    return render_template_string(html_header + "<h2>Success!</h2><a href='/' class='btn'>New Entry</a></body></html>")

if __name__ == "__main__":
    # login first
    get_service()
    
    # try to find open port
    port = 5000
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    while True:
        try:
            s.bind(("127.0.0.1", port))
            s.close()
            break
        except:
            port = port + 1
            
    # open browser in 1 second
    def open_browser():
        webbrowser.open("http://localhost:" + str(port))
        
    t = threading.Timer(1, open_browser)
    t.start()
    
    app.run(port=port)
