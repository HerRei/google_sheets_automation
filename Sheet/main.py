import os
import datetime
import threading
import webbrowser
import socket
from flask import Flask, request, session, redirect, render_template_string

# google imports
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

app = Flask(__name__)
app.secret_key = "supersecretkey" # changed for safety

# settings
SHEET_ID = "1igokZF1o_inrjyGNN6Tctg-2BLD_hXLmm0lDSR0C3J4"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
TOKEN = "token.json"
CREDS = "credentials.json"

stores = ["Coop", "Migros", "Paff", "Milchhüsli", "Diverse"]
destinations = ["Liestal", "Seltisberg", "Frenkendorf", "Buebendorf", "Lausen"]
days_back = 14

service = None

# get the google sheet service
def get_service():
    global service
    if service:
        return service

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
        store_name = data['store']
        
        # find the next empty row
        result = s.spreadsheets().values().get(spreadsheetId=SHEET_ID, range=store_name + "!A:A").execute()
        rows = result.get("values", [])
        next_row = len(rows) + 1
        
        # prepare the row
        new_row = [
            data['date'],
            data['weekday'],
            data['abo_nr'],
            str(data['vignette']),
            data['destination']
        ]
        
        # append it
        range_name = store_name + "!A" + str(next_row)
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
    return redirect("/store")

@app.route("/store", methods=["GET", "POST"])
def store():
    if request.method == "POST":
        session.clear() # reset session
        session["entry"] = {"store": request.form["store"]}
        return redirect("/date")

    buttons = ""
    for s in stores:
        buttons = buttons + '<button class="btn" name="store" value="' + s + '">' + s + '</button>'
    
    return render_template_string(html_header + "<h2>Select Store</h2><form method='post'>" + buttons + "</form></body></html>")

@app.route("/date", methods=["GET", "POST"])
def date():
    if request.method == "POST":
        entry = session.get("entry", {})
        entry["date"] = request.form["date"]
        
        # get weekday
        d = datetime.datetime.strptime(entry["date"], "%Y-%m-%d")
        entry["weekday"] = d.strftime("%a")
        
        session["entry"] = entry
        return redirect("/abo")

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

@app.route("/abo", methods=["GET", "POST"])
def abo():
    if request.method == "POST":
        entry = session.get("entry", {})
        
        val = request.form.get("abo_nr")
        if val == "":
            entry["abo_nr"] = None
        else:
            entry["abo_nr"] = val
            
        entry["vignette"] = int(request.form["vignette"])
        session["entry"] = entry
        return redirect("/destination")

    form = """
    <h2>Abo info</h2>
    <form method='post'>
    <input type='text' name='abo_nr' placeholder='Abo Number'><br><br>
    <button class='btn' name='vignette' value='1'>Normal</button>
    <button class='btn' name='vignette' value='2'>Express</button>
    </form>
    """
    return render_template_string(html_header + form + "</body></html>")

@app.route("/destination", methods=["GET", "POST"])
def dest():
    if request.method == "POST":
        entry = session.get("entry", {})
        entry["destination"] = request.form["destination"]
        session["entry"] = entry
        return redirect("/review")

    buttons = ""
    for d in destinations:
        buttons = buttons + '<button class="btn" name="destination" value="' + d + '">' + d + '</button>'
    
    return render_template_string(html_header + "<h2>Destination</h2><form method='post'>" + buttons + "</form></body></html>")

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

    data_str = str(entry)
    
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