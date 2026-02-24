# tests/test_main.py
import pytest
from Sheet import main
from google.auth.exceptions import RefreshError

# This runs before every test to make sure we start fresh
def setup_function():
    main._service = None

# Helper class to fake the Google Credentials object
class MockCreds:
    def __init__(self, valid=True, expired=False, token="test_token"):
        self.valid = valid
        self.expired = expired
        self.token = token
        self.refresh_token = "refresh_token"

    def refresh(self, request):
        # Determine if we should fail or succeed
        if self.token == "BAD_TOKEN":
            raise RefreshError("Token is bad")

        # Simulate a refresh
        self.valid = True
        self.expired = False

    def to_json(self):
        return '{"token": "mock_json"}'

# Helper class to fake the Sheets Service
class MockService:
    def __init__(self, rows=None):
        self.rows = rows if rows else []
        self.calls = []  # We will store what functions got called here

    def spreadsheets(self):
        return self

    def values(self):
        return self

    def get(self, spreadsheetId, range):
        self.calls.append(("get", range))
        return self

    def append(self, spreadsheetId, range, valueInputOption, body):
        self.calls.append(("append", range, body))
        return self

    def execute(self):
        # If the last call was a get, return our fake rows
        if self.calls and self.calls[-1][0] == "get":
            return {"values": self.rows}
        return {}


@pytest.fixture
def client():
    main.app.config['TESTING'] = True
    main.app.config['SECRET_KEY'] = 'student-test-key'
    with main.app.test_client() as client:
        yield client


# -----------------------------------------------------------------------------
# Service Tests
# -----------------------------------------------------------------------------

def test_get_service_returns_cached_if_exists():
    # Setup a fake object
    fake_service = "I am a service"
    main._service = fake_service

    # Check if it returns the one we set
    result = main.get_sheets_service()
    assert result == fake_service

def test_uses_existing_token_if_valid(monkeypatch):
    # Create fake credentials that are good
    fake_creds = MockCreds(valid=True, expired=False)

    # Mock the file check so it thinks token.json exists
    monkeypatch.setattr(main.pathlib.Path, "exists", lambda self: True)

    # Mock loading the credentials
    monkeypatch.setattr(main.Credentials, "from_authorized_user_file", lambda filename, scopes: fake_creds)

    # Mock the build function so we don't actually hit Google
    monkeypatch.setattr(main, "build", lambda *args, **kwargs: "built_service")

    # Run the function
    service = main.get_sheets_service()

    assert service == "built_service"

def test_refreshes_token_if_expired(monkeypatch):
    # Create fake credentials that are expired
    fake_creds = MockCreds(valid=False, expired=True)

    monkeypatch.setattr(main.pathlib.Path, "exists", lambda self: True)
    monkeypatch.setattr(main.Credentials, "from_authorized_user_file", lambda filename, scopes: fake_creds)
    monkeypatch.setattr(main, "build", lambda *args, **kwargs: "built_service")

    service = main.get_sheets_service()

    # Check that the service was built and creds are now valid
    assert service == "built_service"
    assert fake_creds.valid == True
    assert fake_creds.expired == False

def test_runs_oauth_flow_if_refresh_fails(monkeypatch):
    # Create creds that will cause an error when refreshed
    bad_creds = MockCreds(valid=False, expired=True, token="BAD_TOKEN")

    monkeypatch.setattr(main.pathlib.Path, "exists", lambda self: True)
    monkeypatch.setattr(main.Credentials, "from_authorized_user_file", lambda f, s: bad_creds)

    # We need to mock unlink (delete file) and write_text (save file)
    log = []
    monkeypatch.setattr(main.pathlib.Path, "unlink", lambda self, missing_ok=False: log.append("deleted"))
    monkeypatch.setattr(main.pathlib.Path, "write_text", lambda self, data: log.append("saved"))

    # Mock the OAuth flow
    class FakeFlow:
        def run_local_server(self, port):
            return MockCreds(valid=True)

    monkeypatch.setattr(main.InstalledAppFlow, "from_client_secrets_file", lambda f, s: FakeFlow())
    monkeypatch.setattr(main, "build", lambda *args, **kwargs: "new_service")

    service = main.get_sheets_service()

    assert service == "new_service"
    assert "deleted" in log
    assert "saved" in log


# -----------------------------------------------------------------------------
# Logic Tests
# -----------------------------------------------------------------------------

def test_append_entry_calculates_row(monkeypatch):
    # 1. Setup our fake service with 2 rows of data
    fake_rows = [["header"], ["data"]]
    mock_service = MockService(rows=fake_rows)

    # Make get_sheets_service return our mock
    monkeypatch.setattr(main, "get_sheets_service", lambda: mock_service)

    # 2. Hack threading so it runs immediately (no background tasks)
    class FakeThread:
        def __init__(self, target, daemon):
            self.target = target
        def start(self):
            self.target()  # run it now

    monkeypatch.setattr(main.threading, "Thread", FakeThread)

    # 3. Call the function
    entry = {
        "store": "Coop",
        "date": "2026-02-24",
        "weekday": "Tue",
        "abo_nr": None,
        "vignette": 1,
        "destination": "Liestal",
    }
    main.append_entry(entry)

    # 4. Assertions
    # First it should get column A
    assert mock_service.calls[0][0] == "get"
    assert mock_service.calls[0][1] == "Coop!A:A"

    # Then it should append to row 3 (because we had 2 rows)
    assert mock_service.calls[1][0] == "append"
    assert mock_service.calls[1][1] == "Coop!A3:E3"

    # Check the data being saved
    saved_values = mock_service.calls[1][2]["values"][0]
    assert saved_values[0] == "2026-02-24"
    assert saved_values[4] == "Liestal"


# -----------------------------------------------------------------------------
# Flask Tests
# -----------------------------------------------------------------------------

def test_wizard_flow(client, monkeypatch):
    # Mock the final database save so we don't need a real service
    saved_data = []
    def fake_append(entry):
        saved_data.append(entry)

    monkeypatch.setattr(main, "append_entry", fake_append)

    # Step 1: Go to home
    response = client.get("/")
    assert response.status_code == 302
    assert "/store" in response.headers["Location"]

    # Step 2: Pick Store
    response = client.post("/store", data={"store": "Coop"})
    assert response.status_code == 302
    assert "/date" in response.headers["Location"]

    # Step 3: Pick Date
    response = client.post("/date", data={"date": "2026-02-24"})
    assert "/abo" in response.headers["Location"]

    # Step 4: Abo (leave number blank)
    response = client.post("/abo", data={"vignette": "1", "abo_nr": ""})
    assert "/destination" in response.headers["Location"]

    # Step 5: Destination
    response = client.post("/destination", data={"destination": "Liestal"})
    assert "/review" in response.headers["Location"]

    # Step 6: Commit
    response = client.post("/review", data={"action": "commit"})
    assert "/success" in response.headers["Location"]

    # Check if data was saved correctly
    assert len(saved_data) == 1
    assert saved_data[0]['store'] == "Coop"
    assert saved_data[0]['destination'] == "Liestal"
    assert saved_data[0]['abo_nr'] is None

def test_restart_button(client):
    # Set some fake session data first
    with client.session_transaction() as sess:
        sess['entry'] = {'store': 'Migros'}

    # Hit the restart button
    response = client.post("/review", data={"action": "restart"})

    # Should go back to start
    assert response.status_code == 302
    assert "/store" in response.headers["Location"]

    # Session should be empty (or new)
    with client.session_transaction() as sess:
        assert sess.get('entry') in (None, {})