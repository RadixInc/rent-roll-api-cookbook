# Radix Rent Roll MCP Server

An MCP (Model Context Protocol) server that connects Claude Desktop to the Radix/redIQ Rent Roll API. Upload rent roll files, monitor processing status, and retrieve cleaned results -- all through natural language.

## Key Design Principles

- **ZIP-first.** The canonical artifact is a batch-level pre-signed ZIP URL (`outputs.download_url`). We never rely on per-file `downloadURLs[]`.
- **Cross-OS by default.** Extraction targets an OS temp directory unless you explicitly opt in to a custom path. Claude never needs to invent a platform-specific path.
- **Model-readable output.** In extract mode the server returns CSV headers, preview rows, and (for small files) the full CSV text inline -- so Claude can answer questions about the data without filesystem access or code execution.
- **Single API key parameter.** All tools accept `api_key_override` (or fall back to the `RADIX_API_KEY` environment variable). There is no separate `api_key` parameter.

## Quick Setup

### 1. Install Dependencies

A local virtual environment is recommended because `xhttp` (a required
dependency) is not commonly pre-installed.

**Local venv (recommended)**

Windows PowerShell:
```powershell
cd radix-rent-roll-mcp
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

macOS / Linux:
```bash
cd radix-rent-roll-mcp
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
```

### 2. Set Your API Key

Set the `RADIX_API_KEY` environment variable with your RedIQ API key.

**Windows (PowerShell):**
```powershell
$env:RADIX_API_KEY = "your-api-key-here"
```

**macOS/Linux:**
```bash
export RADIX_API_KEY="your-api-key-here"
```

### 3. Configure Claude Desktop

Add the following to your Claude Desktop configuration file. Point `command` at
the **venv Python interpreter** so the server can find `xhttp` and the other
installed dependencies.

**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "radix-rent-roll-mcp": {
      "command": "C:\\Users\\YourName\\path\\to\\radix-rent-roll-mcp\\.venv\\Scripts\\python.exe",
      "args": ["C:\\Users\\YourName\\path\\to\\radix-rent-roll-mcp\\server.py"],
      "env": {
        "RADIX_API_KEY": "your-api-key-here",
        "RADIX_API_URL": "https://connect.rediq.io",
        "RADIX_NOTIFICATION_EMAIL": "you@example.com"
      }
    }
  }
}
```

> `RADIX_API_URL` and `RADIX_NOTIFICATION_EMAIL` are optional. See
> [Environment Variables](#environment-variables) for defaults and details.

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "radix-rent-roll-mcp": {
      "command": "/Users/yourname/path/to/radix-rent-roll-mcp/.venv/bin/python",
      "args": ["/Users/yourname/path/to/radix-rent-roll-mcp/server.py"],
      "env": {
        "RADIX_API_KEY": "your-api-key-here",
        "RADIX_API_URL": "https://connect.rediq.io",
        "RADIX_NOTIFICATION_EMAIL": "you@example.com"
      }
    }
  }
}
```

### 4. Restart Claude Desktop

You must **fully quit** Claude Desktop — not just close the window. On Windows, if system tray mode or global keyboard shortcuts are enabled, Claude processes will continue running in the background even after the window is closed. Open **Task Manager** (`Ctrl+Shift+Esc`), end all `Claude` processes, and then relaunch the application. Once restarted, you should see the Radix Rent Roll tools available in the tools menu.

### 5. Quick Verification

Paste a prompt like this into Claude Desktop to confirm everything is working:

> Have Radix process this rent roll using process_rent_roll_workflow in extract
> mode and show me the detected columns and first 10 preview rows.
> C:\Users\YourName\Documents\sample_rent_roll.xlsx

Replace the path with the **absolute path** to a real rent roll file on your
machine.

**Important -- always pass files as local paths, not chat attachments.**
The MCP server reads files directly from your filesystem by path. Dragging a
file into the Claude Desktop chat window or using an attachment will **not**
send it through the MCP server and cannot be processed by the Radix API.
Always reference files by their full absolute path in your prompt
(e.g. `C:\Users\YourName\Documents\property.xlsx` or
`/Users/YourName/Documents/property.xlsx`).

---

## Recommended Usage

### One-call workflow: `process_rent_roll_workflow`

This is the tool you should use for almost everything. It uploads, polls until
complete, and returns results -- all in a single call.

#### URLs only (lightest)

```
process_rent_roll_workflow(
    file_paths=["C:\\Users\\YourName\\property.xlsx"],
    notification_email="user@example.com",
    result_mode="urls",
)
```

Returns `zip_download_url` and `zip_presigned_expires_at`. No extraction, no
temp files.

#### Extract with model-readable CSV (recommended)

```
process_rent_roll_workflow(
    file_paths=["C:\\Users\\YourName\\property.xlsx"],
    notification_email="user@example.com",
    result_mode="extract",
)
```

This extracts to an OS temp directory automatically and returns:

- `output_dir_used` -- the actual path on the host (temp unless overridden)
- `host_os` -- `"Windows"`, `"Darwin"`, or `"Linux"`
- `extracted_files` -- list of host paths (for humans / downstream tools)
- `processed_csv` -- list of model-readable artifacts, each containing:
  - `entry_name` -- e.g. `Rent Roll (52).csv`
  - `header` -- list of column names
  - `preview_rows` -- first N rows as `list[dict]` (default 200)
  - `inline_csv` -- full CSV text (included when the file is under 250 KB)
  - `local_path`, `size_bytes`

Claude can answer arbitrary questions about the rent roll data directly from
`processed_csv` without needing to read files or run code.

#### Extract to a specific directory

```
process_rent_roll_workflow(
    file_paths=["C:\\Users\\YourName\\property.xlsx"],
    notification_email="user@example.com",
    result_mode="extract",
    output_dir="C:\\Users\\YourName\\output",
    output_dir_strategy="use_output_dir",
)
```

The `output_dir_strategy` flag controls the behavior:

| Strategy | Behavior |
|---|---|
| `"temp"` (default) | Always use an OS temp directory. Ignores `output_dir`. |
| `"use_output_dir"` | Validate `output_dir` is absolute and writable; fall back to temp with a warning if not. |

#### Manifest only (no extraction)

```
process_rent_roll_workflow(
    file_paths=["C:\\Users\\YourName\\property.xlsx"],
    notification_email="user@example.com",
    result_mode="manifest",
)
```

Returns a lightweight ZIP manifest listing all entries and which ones match
`extract_patterns`. No files are written to disk.

---

## Natural Language Examples

Once configured, you can talk to Claude Desktop naturally:

> "Upload the rent roll at C:\Users\YourName\Documents\property_123.xlsx and send
> notifications to user@example.com"

> "Check the status of batch 17a34571-f35b-49ad-98a6-6550bab3c507"

> "Process the rent rolls in my documents folder, extract the cleaned CSVs,
> and summarize the unit count and average rent"

---

## Available Tools

### process_rent_roll_workflow (recommended)

Deterministic end-to-end workflow: upload, poll, and return results in a single
call.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `file_paths` | list[str] | *(required)* | Absolute paths to rent roll files |
| `notification_email` | str | `""` | Email for notifications (or set `RADIX_NOTIFICATION_EMAIL`) |
| `webhook_url` | str \| null | `null` | Optional webhook URL |
| `poll_interval_seconds` | number | `7.5` | Seconds between status polls |
| `timeout_seconds` | number | `900` | Max wait before timeout |
| `result_mode` | `"urls"` \| `"manifest"` \| `"extract"` | `"urls"` | What to return |
| `output_dir` | str \| null | `null` | Only used when `output_dir_strategy="use_output_dir"` |
| `output_dir_strategy` | `"temp"` \| `"use_output_dir"` | `"temp"` | Where to extract files |
| `extract_patterns` | list[str] | `["processed-csv/**"]` | ZIP entry patterns to target |
| `include_summary` | bool | `true` | Include API summary when available |
| `preview_rows` | int | `200` | Number of CSV rows per preview |
| `inline_max_bytes` | int | `250000` | Max file size to include as `inline_csv` |
| `api_key_override` | str \| null | `null` | Override the `RADIX_API_KEY` env var |

**Response fields (always present):**
`success`, `batch_id`, `status`, `zip_download_url`, `zip_presigned_expires_at`,
`output_dir_used`, `host_os`, `warnings`

**Additional fields by result_mode:**

| Mode | Extra fields |
|---|---|
| `"urls"` | *(none beyond the base fields)* |
| `"manifest"` | `zip_manifest` (entries + matched_entries) |
| `"extract"` | `extracted_files`, `extracted_count`, `processed_csv` |

### upload_rent_rolls

Upload rent roll files for processing. Returns a `batchId` for status tracking.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `file_paths` | list[str] | *(required)* | Absolute paths to rent roll files |
| `notification_email` | str | *(required)* | Email for completion notifications |
| `webhook_url` | str \| null | `null` | Optional webhook URL |
| `api_key_override` | str \| null | `null` | Override the `RADIX_API_KEY` env var |

### check_batch_status

Check the processing status of a batch.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `batch_id` | str | *(required)* | The batchId UUID from upload response |
| `api_key_override` | str \| null | `null` | Override the `RADIX_API_KEY` env var |

### get_batch_zip_manifest

Download the canonical batch ZIP to a temp file and return a lightweight manifest
(entries + matched entries). The temp file is deleted automatically after reading.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `zip_download_url` | str | *(required)* | Canonical pre-signed ZIP URL |
| `extract_patterns` | list[str] | `["processed-csv/**"]` | Patterns to match |
| `api_key_override` | str \| null | `null` | Override the `RADIX_API_KEY` env var |

### download_and_extract_batch_zip

Download the canonical batch ZIP to a temp file, then optionally extract matched
entries with zip-slip protection.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `zip_download_url` | str | *(required)* | Canonical pre-signed ZIP URL |
| `patterns` | list[str] | `["processed-csv/**"]` | Patterns to extract |
| `output_dir` | str \| null | `null` | Destination directory; if null, manifest-only |
| `api_key_override` | str \| null | `null` | Override the `RADIX_API_KEY` env var |

### download_processed_files

Download completed files to a local directory. Prefer `process_rent_roll_workflow`
for deterministic ZIP handling.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `download_urls` | list[str] | *(required)* | URLs from status response |
| `output_directory` | str | *(required)* | Local path to save files |
| `api_key_override` | str \| null | `null` | Override the `RADIX_API_KEY` env var |

---

## Supported File Types

| Extension | Format |
|---|---|
| `.xlsx` | Excel (OpenXML) |
| `.xls` | Excel (Legacy) |
| `.xlsm` | Excel with Macros |
| `.csv` | Comma-Separated Values |
| `.ods` | OpenDocument Spreadsheet |

**Limits:**
- Maximum 20 files per batch
- Maximum 2 MB per file

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `RADIX_API_KEY` | Yes | -- | Your RedIQ API key |
| `RADIX_API_URL` | No | `https://connect.rediq.io` | API base URL |
| `RADIX_NOTIFICATION_EMAIL` | No | -- | Default notification email (used when `notification_email` is empty) |

---

## Architecture Notes

### ZIP pointer resolution

When the workflow polls for completion, it resolves the ZIP URL in two steps:

1. **Canonical field:** `zip_download_url` from `check_batch_status`
   (set from `outputs.download_url` in the API response).
2. **Fallback scan:** If the canonical field is empty, re-scan `batchDownloads`
   for the first entry with `type == "zip"` or a `.zip` URL.

This prevents "Missing zip_download_url" failures when the API returns the URL
only in the legacy `batchDownloads` array.

### Output directory strategy

The `output_dir_strategy` parameter eliminates cross-OS path confusion:

- With `"temp"` (the default), the server calls `tempfile.mkdtemp()` and
  returns the actual path in `output_dir_used`. Claude never needs to guess a
  platform-specific path.
- With `"use_output_dir"`, the server validates that `output_dir` is absolute
  for the host OS and can be created. If validation fails, it falls back to
  temp and includes a warning.

### Model-readable CSV previews

After extraction, the server reads each CSV under `processed-csv/` and builds
a `processed_csv` list containing headers, preview rows (default 200), and
optionally the full CSV text (when under `inline_max_bytes`). This allows
Claude to answer data questions entirely from the tool response, with no
filesystem access or code execution required.

### Pre-signed URL expiry and 403 retry

ZIP URLs are pre-signed and expire. If a ZIP download returns HTTP 403, the
workflow re-checks batch status to obtain a fresh `zip_download_url` and
retries once automatically.

---

## Troubleshooting

### "Missing API key"

Make sure `RADIX_API_KEY` is set in the `env` section of your Claude Desktop
config. Only use `api_key_override` if you need to switch keys at runtime.

### "File not found" errors

- Use **absolute paths** (e.g. `C:\Users\YourName\file.xlsx`, not `.\file.xlsx`)
- On Windows, both forward slashes and backslashes work
- Verify the file exists at the specified path

### "API error (HTTP 401)"

Your API key is invalid, expired, or revoked. Check that you have the correct key.

### "API error (HTTP 403)"

Your account may not have API access enabled, or you may have insufficient
credits. Contact RedIQ support.

### "API error (HTTP 429)"

You've hit the rate limit. Wait a moment and try again.

### "Request timed out"

Large files or many files may take longer to upload. Try uploading fewer files
at once, or check your internet connection.

### "output_dir_not_absolute" warning

You passed a relative or invalid path with `output_dir_strategy="use_output_dir"`.
The server fell back to an OS temp directory. Use an absolute path or switch to
the default `"temp"` strategy.

### Claude Desktop doesn't show the tools

1. Verify the path to `server.py` in your config is correct
2. Make sure Python is on your PATH
3. Check that dependencies are installed (`pip install -r requirements.txt`)
4. Restart Claude Desktop completely

---

## Development

### Running Tests

```bash
python test_server.py
```

To run end-to-end tests with a live API key:

**PowerShell:**
```powershell
$env:RADIX_API_KEY = "your-key"
python test_server.py
```

**Bash:**
```bash
RADIX_API_KEY="your-key" python test_server.py
```

### Project Structure

```
radix-rent-roll-mcp/
  server.py              # MCP server with workflow + ZIP-first tools
  requirements.txt       # Python dependencies
  README.md              # This file
  test_server.py         # Test suite
  example_config.json    # Claude Desktop config template
  .gitignore             # Excludes docs/, test data, credentials
  scripts/               # Manual smoke runners (not CI)
  docs/                  # API spec and examples (git ignored)
    RentRoll-API-Spec.json
    Example-Success-Response.json
```
