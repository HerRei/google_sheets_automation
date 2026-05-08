# Google Sheets Automation

A small Flask/Python application for writing structured records to Google Sheets.

Showcase: https://herrei.github.io/google_sheets_automation/

This project was built for a real production bookkeeping workflow where the same kinds of information had to be entered repeatedly. The app turns that repeated typing into a short guided flow with configurable buttons, then writes the finished record to a Google Sheet through the Google Sheets API.

## Why It Helped

- Reduced repetitive manual entry in a recurring bookkeeping process.
- Kept the workflow lightweight instead of introducing a large internal tool.
- Made the input flow easier to repeat consistently.
- Kept private setup values outside source code through local configuration.

## Configuration

On first run, the app creates a local `config.json` file. Edit that file with your own Google Sheet id, entry types, targets, option labels, and local OAuth file paths.

`config.json`, OAuth credentials, and OAuth tokens are ignored by git so private setup values do not get committed.

## Run

```bash
python Sheet/main.py
```

## Test

```bash
pytest
```
