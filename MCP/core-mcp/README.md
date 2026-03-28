# Radix Rent Roll Core MCP Server

A lightweight Model Context Protocol (MCP) server for interacting with the Radix / RedIQ Rent Roll Processing API.

This server provides a clean interface for uploading rent rolls, managing deals, monitoring processing status, and retrieving results. It is designed for automation, integrations, and AI assistants that need direct access to the Rent roll API.

---

## What This MCP Provides

The Core MCP exposes a minimal, predictable API surface:

- Create, list, get, update, and delete deals
- Upload rent roll files, including optional `deal_id`
- Check processing status
- Retrieve download URLs for processed outputs

Only one `dealId` is allowed per upload request, so all files in that batch will be linked to the same deal.

This MCP does **not** perform workflow orchestration, ZIP extraction, or data previewing.  
For those capabilities, see the **Agent MCP**.

---

## Typical Use Cases

This MCP is ideal for:

- backend integrations  
- automation pipelines  
- server-side agents  
- CI/CD workflows  
- custom developer tooling  
- AI assistants needing a clean API surface  

---

## Requirements

- Python 3.10+  
- Valid Radix API credentials  

---

## Quick Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
````

---

### 2. Set Your API Key

Set the `RADIX_API_KEY` environment variable with your API key.

**Windows (PowerShell):**

```powershell
$env:RADIX_API_KEY="your-api-key-here"
```

**macOS/Linux:**

```bash
export RADIX_API_KEY="your-api-key-here"
```

---

## 3. Configure Your MCP Client

This MCP server can be used with **any Model Context Protocol (MCP) client**, including automation tools, agent frameworks, and AI assistants.

Register the server by pointing your MCP client to `server.py`.

### Example Configuration

```json
{
  "mcpServers": {
    "radix-rent-roll-core": {
      "command": "python3",
      "args": ["/path/to/rent-roll-api-cookbook-1/MCP/core-mcp/server.py"],
      "env": {
        "RADIX_API_KEY": "your-api-key-here",
        "RADIX_API_URL": "https://connect.rediq.io"
      }
    }
  }
}
```

Restart your MCP client after saving.

---

### Running Directly

You can also run the server directly:

```bash
python server.py
```

This is useful for:

* automation workflows
* backend services
* CI/CD pipelines
* custom agent runners

---

## Usage Examples

Once configured, an MCP-enabled client can issue commands such as:

**Upload files**

> Upload the rent roll at C:\Documents\property.xlsx and notify me at [YourName@example.com](mailto:YourName@example.com)

**Check status**

> Check the status of batch 17a34571-f35b-49ad-98a6-6550bab3c507

**Retrieve download URLs**

> Get the download URLs for batch 17a34571-f35b-49ad-98a6-6550bab3c507

## API Update Note

If your automation needs to organize uploads by redIQ deal, use `create_deal` or `list_deals` / `get_deal` to find the target `counterId`, then send that value as upload `deal_id`. Because the API accepts only one `dealId` per upload request, folder-processing automations should send separate batches for separate deals.

---

## Available Tools

### upload_rent_rolls

Upload rent roll files for processing.

| Parameter            | Type      | Required | Description                        |
| -------------------- | --------- | -------- | ---------------------------------- |
| `file_paths`         | list[str] | Yes      | Absolute paths to rent roll files  |
| `notification_email` | str       | No       | Optional email notification target |
| `webhook_url`        | str       | No       | Optional webhook URL               |
| `deal_id`            | int       | No       | Optional deal counterId for the entire batch |
| `api_key`            | str       | No       | Override the RADIX_API_KEY env var |

Provide at least one of `notification_email` or `webhook_url`.

---

### create_deal

Create a deal and return its `counterId`.

| Parameter | Type | Required | Description |
| --------- | ---- | -------- | ----------- |
| `deal_name` | str | Yes | Deal name |
| `address` | str | No | Property address |
| `city` | str | No | Property city |
| `state` | str | No | Property state |
| `zip` | str | No | Property zip code |
| `unit_count` | int | No | Property unit count |
| `api_key` | str | No | Override the RADIX_API_KEY env var |

---

### list_deals

List deals for the authenticated account.

| Parameter | Type | Required | Description |
| --------- | ---- | -------- | ----------- |
| `page` | int | No | Page number, default `1` |
| `limit` | int | No | Page size, default `20` |
| `search` | str | No | Optional deal name search |
| `api_key` | str | No | Override the RADIX_API_KEY env var |

---

### get_deal

Retrieve one deal by its `counterId`.

| Parameter | Type | Required | Description |
| --------- | ---- | -------- | ----------- |
| `counter_id` | int | Yes | Deal counterId |
| `api_key` | str | No | Override the RADIX_API_KEY env var |

---

### update_deal

Update one or more fields on an existing deal.

| Parameter | Type | Required | Description |
| --------- | ---- | -------- | ----------- |
| `counter_id` | int | Yes | Deal counterId |
| `deal_name` | str | No | Updated deal name |
| `address` | str | No | Updated property address |
| `city` | str | No | Updated property city |
| `state` | str | No | Updated property state |
| `zip` | str | No | Updated property zip code |
| `unit_count` | int | No | Updated unit count |
| `api_key` | str | No | Override the RADIX_API_KEY env var |

---

### delete_deal

Soft-delete a deal by its `counterId`.

| Parameter | Type | Required | Description |
| --------- | ---- | -------- | ----------- |
| `counter_id` | int | Yes | Deal counterId |
| `api_key` | str | No | Override the RADIX_API_KEY env var |

---

### check_batch_status

Check the processing status of a batch.

| Parameter  | Type | Required | Description                        |
| ---------- | ---- | -------- | ---------------------------------- |
| `batch_id` | str  | Yes      | The batchId from upload response   |
| `api_key`  | str  | No       | Override the RADIX_API_KEY env var |

---

### download_processed_files

Download completed files using the URLs returned from the status response.

| Parameter          | Type      | Required | Description                        |
| ------------------ | --------- | -------- | ---------------------------------- |
| `download_urls`    | list[str] | Yes      | URLs from status response          |
| `output_directory` | str       | Yes      | Local path to save files           |
| `api_key`          | str       | No       | Override the RADIX_API_KEY env var |

---

## Supported File Types

| Extension | Format                   |
| --------- | ------------------------ |
| `.xlsx`   | Excel (OpenXML)          |
| `.xls`    | Excel (Legacy)           |
| `.xlsm`   | Excel with Macros        |
| `.csv`    | Comma-Separated Values   |
| `.ods`    | OpenDocument Spreadsheet |

**Limits:**

* Maximum 20 files per batch
* Maximum 2 MB per file

---

## Environment Variables

| Variable        | Required | Default                                              | Description  |
| --------------- | -------- | ---------------------------------------------------- | ------------ |
| `RADIX_API_KEY` | Yes      | —                                                    | Your API key |
| `RADIX_API_URL` | No       | [https://connect.rediq.io](https://connect.rediq.io) | API base URL |

---

## Troubleshooting

### Missing API key

Ensure `RADIX_API_KEY` is set in your environment or MCP configuration.

### File not found

* Use **absolute paths**
* Verify file location and permissions

### HTTP 401

Invalid or expired API key.

### HTTP 403

API access not enabled or insufficient credits.

### HTTP 429

Rate limit exceeded. Retry shortly.

### MCP tools not visible

* Verify path to `server.py`
* Confirm dependencies installed
* Restart your MCP client

---

## Related MCP

For AI assistants and local workflows that need automated download, extraction, and preview of processed data, see:

**Agent MCP** (in the MCP folder)

---

## Security Note

This MCP runs locally and requires a valid API key.
Never share API keys publicly.

---
