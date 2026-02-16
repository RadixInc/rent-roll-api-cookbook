# redIQ Rent Roll Uploader - Windows Right-Click

Upload rent rolls to redIQ directly from File Explorer.
Right-click any spreadsheet, select **Upload Rent Roll (redIQ)**, done.

**Supported formats:** `.xlsx`, `.xls`, `.xlsm`, `.csv`, `.ods`

---

## Quick Start

1. **Download** - clone this repo (or download the ZIP) to a permanent location (e.g. local, NOT a cloud storage location like OneDrive or Google Drive)
2. **Run Setup** - double-click `Run Setup.cmd` and follow the prompts
3. **Upload** - right-click any supported file and select **Upload Rent Roll (redIQ)**

> On Windows 11 you may need to click **Show more options** first.

Multi-file select is supported - select several files, right-click, and they all upload in one batch (up to 20).

---

## What Setup Does

Setup walks you through three steps:

1. **API Key** - stored securely in Windows Credential Manager (DPAPI-encrypted)
2. **Notifications** - email and/or webhook URL for upload status updates
3. **Context Menu** - registers the right-click menu entry in File Explorer

Configuration is saved to `%APPDATA%\RedIQ\RentRollUploader\config.json`.

---

## Reconfigure

Run `Run Setup.cmd` again at any time and choose **Setup / Configure**. If existing settings are detected you'll get a menu to update individual items without re-entering everything:

- **API Key** - rotate or replace your key
- **Notification Email** - change or clear
- **Webhook URL** - change or clear
- **Reinstall Context Menu** - re-register the right-click entry (useful after moving the folder)
- **Update All** - wipe and redo all settings from scratch

---

## Uninstall

Double-click `Run Setup.cmd` again and choose **Uninstall**. This removes:

- The right-click context menu entry
- Your stored API key from Windows Credential Manager
- All configuration and log files

---

## Files

| File | Description |
|------|-------------|
| `Run Setup.cmd` | **Start here.** Double-click to launch the setup wizard. |
| `setup.ps1` | Setup, install, and uninstall logic (called by the .cmd file) |
| `upload.ps1` | Upload logic (called automatically by the right-click context menu) |

---

## Logs

Upload logs are written to `%APPDATA%\RedIQ\RentRollUploader\uploader.log`.
