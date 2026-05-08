# Google Sheets Automation

A small Flask/Python application for writing structured records to Google Sheets.

The app is meant for situations where the same kinds of details need to be typed repeatedly. Instead of entering every field by hand each time, the user can choose from editable options such as `Record Type A`, `Entry Type`, `Record A`, and `Timestamp`, then send the structured record to a configured Google Sheet.

## Configuration

On first run, the app creates a local `config.json` file. Edit that file with your own Google Sheet id, entry types, targets, and local OAuth file paths.

`config.json`, OAuth credentials, and OAuth tokens are ignored by git so private setup values do not get committed.

## Run

```bash
python Sheet/main.py
```

## Test

```bash
pytest
```
