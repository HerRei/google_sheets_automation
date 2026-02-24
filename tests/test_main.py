import pytest
import os
from unittest.mock import mock_open 
from Sheet import main

# This runs before every test to make sure we start fresh
def setup_function():
    main.service = None

# Helper class to fake the Google Credentials object
class MockCreds:
    def __init__(self, valid=True, expired=False, token="test_token"):
        self.valid = valid
        self.expired = expired
        self.token = token
        self.refresh_token = "refresh_token"

    def refresh(self, request):
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
    fake_service = "I am a service"
    main.service = fake_service
    result = main.get_service()
    assert result == fake_service

def test_uses_existing_token_if_valid(monkeypatch):
    fake_creds = MockCreds(valid=True, expired=False)
    
    # Mock os.path.exists
    monkeypatch.setattr(main.os.path, "exists", lambda x: True)
    monkeypatch.setattr(main.Credentials, "from_authorized_user_file", lambda filename, scopes: fake_creds)
    monkeypatch.setattr(main, "build", lambda *args, **kwargs: "built_service")

    service = main.get_service()
    assert service == "built_service"

def test_refreshes_token_if_expired(monkeypatch):
    fake_creds = MockCreds(valid=False, expired=True)

    monkeypatch.setattr(main.os.path, "exists", lambda x: True)
    monkeypatch.setattr(main.Credentials, "from_authorized_user_file", lambda filename, scopes: fake_creds)
    monkeypatch.setattr(main, "build", lambda *args, **kwargs: "built_service")

    # FIX: Use the imported mock_open
    m_open = mock_open()
    monkeypatch.setattr("builtins.open", m_open)

    service = main.get_service()

    assert service == "built_service"
    assert fake_creds.valid == True
    assert fake_creds.expired == False


# -----------------------------------------------------------------------------
# Logic Tests
# -----------------------------------------------------------------------------

def test_append_entry_calculates_row(monkeypatch):
    fake_rows = [["header"], ["data"]]
    mock_service = MockService(rows=fake_rows)

    monkeypatch.setattr(main, "get_service", lambda: mock_service)

    # Hack threading so it runs immediately
    class FakeThread:
        def __init__(self, target, args):
            self.target = target
            self.args = args
        def start(self):
            self.target(*self.args) 

    monkeypatch.setattr(main.threading, "Thread", FakeThread)

    entry = {
        "store": "Coop",
        "date": "2026-02-24",
        "weekday": "Tue",
        "abo_nr": None,
        "vignette": 1,
        "destination": "Liestal",
    }
    main.append_entry(entry)

    # Check that it gets column A
    assert mock_service.calls[0][0] == "get"
    assert mock_service.calls[0][1] == "Coop!A:A"

    # Check that it appends to row 3
    assert mock_service.calls[1][0] == "append"
    assert mock_service.calls[1][1] == "Coop!A3"

    saved_values = mock_service.calls[1][2]["values"][0]
    assert saved_values[0] == "2026-02-24"
    assert saved_values[4] == "Liestal"


# -----------------------------------------------------------------------------
# Flask Tests
# -----------------------------------------------------------------------------

def test_wizard_flow(client, monkeypatch):
    saved_data = []
    def fake_append(entry):
        saved_data.append(entry)

    monkeypatch.setattr(main, "append_entry", fake_append)

    # 1. Home
    response = client.get("/")
    assert response.status_code == 302
    assert "/store" in response.headers["Location"]

    # 2. Store
    response = client.post("/store", data={"store": "Coop"})
    assert response.status_code == 302
    assert "/date" in response.headers["Location"]

    # 3. Date
    response = client.post("/date", data={"date": "2026-02-24"})
    assert "/abo" in response.headers["Location"]

    # 4. Abo
    response = client.post("/abo", data={"vignette": "1", "abo_nr": ""})
    assert "/destination" in response.headers["Location"]

    # 5. Destination
    response = client.post("/destination", data={"destination": "Liestal"})
    assert "/review" in response.headers["Location"]

    # 6. Commit
    response = client.post("/review", data={"action": "commit"})
    assert "/success" in response.headers["Location"]

    assert len(saved_data) == 1
    assert saved_data[0]['store'] == "Coop"

def test_restart_button(client):
    with client.session_transaction() as sess:
        sess['entry'] = {'store': 'Migros'}

    response = client.post("/review", data={"action": "restart"})

    assert response.status_code == 302
    # Redirects to "/" then "/store"
    assert "/" in response.headers["Location"]

    with client.session_transaction() as sess:
        assert sess.get('entry') in (None, {})
