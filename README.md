# Google Sheets Tracker

This was a tool i built for a place i worked for, to autmate the bookkeeping, where logging all of the sheets by hand into an Excel sheet took about 2h twice a week, with this - it was about 30min once a week. 


## How it works
The app acts as a bridge between a simple web form and your Google Sheet.
1. **Store/Tab Selection:** Choose which category (tab) the entry belongs to.
2. **Data Input:** Enter the date, Abo/Vignette details, and destination.
3. **Automated Logging:** The app finds the next empty row in the selected tab and appends your data instantly.

---

## Setup

### 1. Install Libraries
Ensure you have Python installed, then run the following command to install the required dependencies:

```bash
pip install flask google-api-python-client google-auth-httplib2 google-auth-oauthlib

2. Google Cloud Credentials

To allow the app to access your sheets, you need to set up a project in the Google Cloud Console:

    Go to the Google Cloud Console.

    Create a new project and enable the Google Sheets API.

    Navigate to Credentials → Create Credentials → OAuth client ID.

    Select Desktop App as the type.

    Download the JSON file, rename it to credentials.json, and place it in the project folder.

3. Sheet Configuration

Open main.py and update the SHEET_ID variable with the ID of your own Google Sheet (found in the browser URL). Ensure your sheet has tabs named: Coop, Migros, Paff, Milchhüsli, and Diverse.
