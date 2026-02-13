"""
Radix Rent Roll MCP Server

FastMCP server that integrates Claude Desktop with the Radix/RedIQ Rent Roll API.
Upload rent roll files, monitor processing status, and download cleaned results
through natural language in Claude Desktop.
"""

import json
import os
import re
from pathlib import Path
from typing import Any, Optional
from urllib.parse import unquote, urlparse

import httpx
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_BASE_URL = "https://connect.rediq.io"
SUPPORTED_EXTENSIONS = {".xlsx", ".xls", ".xlsm", ".csv", ".ods"}
MAX_FILES_PER_BATCH = 20
MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024  # 2 MB

MIME_TYPES = {
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
    ".xlsm": "application/vnd.ms-excel.sheet.macroEnabled.12",
    ".csv": "text/csv",
    ".ods": "application/vnd.oasis.opendocument.spreadsheet",
}

# ---------------------------------------------------------------------------
# FastMCP server instance
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "Radix Rent Roll",
    dependencies=["httpx"],
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_api_key(api_key: Optional[str] = None) -> str | dict[str, Any]:
    """Resolve the API key from the parameter or environment variable.

    Returns the key string on success, or an error dict if missing.
    """
    key = api_key or os.environ.get("RADIX_API_KEY")
    if not key:
        return {
            "success": False,
            "error": "Missing API key",
            "details": (
                "Provide an api_key parameter or set the RADIX_API_KEY "
                "environment variable."
            ),
        }
    return key


def _get_base_url() -> str:
    """Return the configured API base URL."""
    return os.environ.get("RADIX_API_URL", DEFAULT_BASE_URL).rstrip("/")


def _get_content_type(extension: str) -> str:
    """Map a file extension to its MIME type."""
    return MIME_TYPES.get(extension.lower(), "application/octet-stream")


def _extract_filename(
    response: httpx.Response, url: str, index: int
) -> str:
    """Extract the filename from a download response.

    Priority:
      1. Content-Disposition header
      2. response-content-disposition query param (pre-signed S3 URLs)
      3. Last segment of the URL path
      4. Fallback default name
    """
    # 1. Content-Disposition header
    cd = response.headers.get("content-disposition", "")
    if cd:
        match = re.search(r'filename[*]?=["\']?([^"\';]+)', cd)
        if match:
            return match.group(1).strip()

    # 2. Pre-signed S3 URL: response-content-disposition query param
    parsed = urlparse(url)
    query = unquote(parsed.query)
    disp_match = re.search(r'filename="?([^"&]+)"?', query)
    if disp_match:
        return disp_match.group(1).strip()

    # 3. URL path segment
    path_name = Path(parsed.path).name
    if path_name and "." in path_name:
        return path_name

    # 4. Fallback
    return f"downloaded_{index}.xlsx"


# ---------------------------------------------------------------------------
# Tool 1: upload_rent_rolls
# ---------------------------------------------------------------------------


@mcp.tool()
async def upload_rent_rolls(
    file_paths: list[str],
    notification_email: str,
    webhook_url: Optional[str] = None,
    api_key: Optional[str] = None,
) -> dict[str, Any]:
    """Upload rent roll files to the Radix/RedIQ API for processing.

    Accepts .xlsx, .xls, .xlsm, .csv, and .ods files (max 20 files, 2 MB each).
    Returns a batchId you can use with check_batch_status to track progress.

    Args:
        file_paths: Absolute paths to rent roll files on your local filesystem.
        notification_email: Email address to receive completion notifications.
        webhook_url: Optional webhook URL for completion callbacks.
        api_key: Optional API key override (uses RADIX_API_KEY env var by default).
    """
    # --- Resolve API key ---
    key = _get_api_key(api_key)
    if isinstance(key, dict):
        return key

    base_url = _get_base_url()

    # --- Validate file count ---
    if not file_paths:
        return {
            "success": False,
            "error": "No files provided",
            "details": "Provide at least one file path to upload.",
        }

    if len(file_paths) > MAX_FILES_PER_BATCH:
        return {
            "success": False,
            "error": f"Too many files ({len(file_paths)})",
            "details": f"Maximum {MAX_FILES_PER_BATCH} files per batch.",
        }

    # --- Validate each file ---
    resolved_paths: list[Path] = []
    for fp in file_paths:
        p = Path(fp)
        if not p.exists():
            return {
                "success": False,
                "error": "File not found",
                "details": f"File does not exist: {fp}",
            }
        if not p.is_file():
            return {
                "success": False,
                "error": "Not a file",
                "details": f"Path is not a file: {fp}",
            }
        ext = p.suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            return {
                "success": False,
                "error": "Unsupported file type",
                "details": (
                    f"File '{p.name}' has unsupported extension '{ext}'. "
                    f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
                ),
            }
        if p.stat().st_size > MAX_FILE_SIZE_BYTES:
            size_mb = p.stat().st_size / (1024 * 1024)
            return {
                "success": False,
                "error": "File too large",
                "details": (
                    f"File '{p.name}' is {size_mb:.1f} MB. Maximum is 2 MB per file."
                ),
            }
        resolved_paths.append(p)

    # --- Build notification method JSON ---
    notifications: list[dict[str, str]] = [
        {"type": "email", "entry": notification_email}
    ]
    if webhook_url:
        notifications.append({"type": "webhook", "entry": webhook_url})
    notification_json = json.dumps(notifications)

    # --- Upload via multipart form ---
    file_handles = []
    try:
        files_for_upload = []
        for p in resolved_paths:
            fh = open(p, "rb")  # noqa: SIM115
            file_handles.append(fh)
            mime = _get_content_type(p.suffix)
            files_for_upload.append(("files", (p.name, fh, mime)))

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{base_url}/api/external/v1/upload",
                headers={"Authorization": f"Bearer {key}"},
                files=files_for_upload,
                data={"notificationMethod": notification_json},
            )
    except httpx.TimeoutException:
        return {
            "success": False,
            "error": "Request timed out",
            "details": "The upload request timed out. Try again or upload fewer files.",
        }
    except httpx.RequestError as exc:
        return {
            "success": False,
            "error": "Network error",
            "details": f"Could not connect to {base_url}: {exc}",
        }
    finally:
        for fh in file_handles:
            fh.close()

    # --- Parse response ---
    if resp.status_code not in (200, 201, 202):
        return {
            "success": False,
            "error": f"API error (HTTP {resp.status_code})",
            "details": resp.text[:1000],
        }

    try:
        body = resp.json()
    except Exception:
        return {
            "success": False,
            "error": "Invalid API response",
            "details": "Could not parse JSON from API response.",
        }

    data = body.get("data", {})

    return {
        "success": True,
        "batchId": data.get("batchId"),
        "status": data.get("status", "queued"),
        "filesUploaded": data.get("filesUploaded", len(resolved_paths)),
        "filesQueued": data.get("filesQueued", len(resolved_paths)),
        "estimatedCompletionMinutes": data.get("estimatedCompletionMinutes"),
        "trackingUrl": data.get("trackingUrl"),
        "message": data.get(
            "message",
            f"Successfully uploaded {len(resolved_paths)} file(s) for processing.",
        ),
    }


# ---------------------------------------------------------------------------
# Tool 2: check_batch_status
# ---------------------------------------------------------------------------


@mcp.tool()
async def check_batch_status(
    batch_id: str,
    api_key: Optional[str] = None,
) -> dict[str, Any]:
    """Check the processing status of a rent roll batch.

    Returns current status, per-file progress, and download URLs when complete.

    Args:
        batch_id: The batchId UUID returned from upload_rent_rolls.
        api_key: Optional API key override (uses RADIX_API_KEY env var by default).
    """
    key = _get_api_key(api_key)
    if isinstance(key, dict):
        return key

    base_url = _get_base_url()

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(
                f"{base_url}/api/external/v1/job/{batch_id}/status",
                headers={"Authorization": f"Bearer {key}"},
            )
    except httpx.TimeoutException:
        return {
            "success": False,
            "error": "Request timed out",
            "details": "The status check request timed out. Try again shortly.",
        }
    except httpx.RequestError as exc:
        return {
            "success": False,
            "error": "Network error",
            "details": f"Could not connect to {base_url}: {exc}",
        }

    if resp.status_code == 404:
        return {
            "success": False,
            "error": "Batch not found",
            "details": f"No batch found with ID: {batch_id}",
        }

    if resp.status_code not in (200, 201):
        return {
            "success": False,
            "error": f"API error (HTTP {resp.status_code})",
            "details": resp.text[:1000],
        }

    try:
        body = resp.json()
    except Exception:
        return {
            "success": False,
            "error": "Invalid API response",
            "details": "Could not parse JSON from API response.",
        }

    data = body.get("data", {})

    # Build per-file summaries
    files_info = []
    for f in data.get("files", []):
        file_entry: dict[str, Any] = {
            "fileId": f.get("fileId"),
            "fileName": f.get("fileName"),
            "status": f.get("status"),
        }
        if f.get("downloadUrl"):
            file_entry["downloadUrl"] = f["downloadUrl"]
        if f.get("errorMessage"):
            file_entry["errorMessage"] = f["errorMessage"]
        files_info.append(file_entry)

    # Build batch download summaries
    batch_downloads = []
    for bd in data.get("batchDownloads", []):
        batch_downloads.append({
            "type": bd.get("type"),
            "downloadUrl": bd.get("downloadUrl"),
            "expiresAt": bd.get("expiresAt"),
        })

    result: dict[str, Any] = {
        "success": True,
        "batchId": data.get("batchId", batch_id),
        "status": data.get("status"),
        "fileCount": data.get("fileCount", 0),
        "filesCompleted": data.get("filesCompleted", 0),
        "filesInProgress": data.get("filesInProgress", 0),
        "filesFailed": data.get("filesFailed", 0),
        "percentComplete": data.get("percentComplete", 0),
        "files": files_info,
        "createdAt": data.get("createdAt"),
        "updatedAt": data.get("updatedAt"),
    }

    if batch_downloads:
        result["batchDownloads"] = batch_downloads

    if data.get("errorMessage"):
        result["errorMessage"] = data["errorMessage"]

    if data.get("actualTotalUnits") is not None:
        result["actualTotalUnits"] = data["actualTotalUnits"]

    if data.get("estimatedTotalUnits") is not None:
        result["estimatedTotalUnits"] = data["estimatedTotalUnits"]

    return result


# ---------------------------------------------------------------------------
# Tool 3: download_processed_files
# ---------------------------------------------------------------------------


@mcp.tool()
async def download_processed_files(
    download_urls: list[str],
    output_directory: str,
    api_key: Optional[str] = None,
) -> dict[str, Any]:
    """Download processed rent roll files to a local directory.

    Use the download URLs from check_batch_status (either from individual
    files[].downloadUrl or batchDownloads[].downloadUrl).

    Args:
        download_urls: List of download URLs from the status response.
        output_directory: Local directory path to save downloaded files.
        api_key: Optional API key override (uses RADIX_API_KEY env var by default).
    """
    try:
        return await _download_processed_files_impl(
            download_urls, output_directory, api_key
        )
    except Exception as exc:
        return {
            "success": False,
            "error": "Unexpected download error",
            "details": f"{type(exc).__name__}: {exc}",
        }


async def _download_processed_files_impl(
    download_urls: list[str],
    output_directory: str,
    api_key: Optional[str] = None,
) -> dict[str, Any]:
    """Internal implementation for download_processed_files."""
    key = _get_api_key(api_key)
    if isinstance(key, dict):
        return key

    if not download_urls:
        return {
            "success": False,
            "error": "No download URLs provided",
            "details": "Provide at least one download URL.",
        }

    # Create output directory
    out_dir = Path(output_directory)
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return {
            "success": False,
            "error": "Cannot create output directory",
            "details": f"Failed to create '{output_directory}': {exc}",
        }

    downloaded_files: list[str] = []
    errors: list[str] = []

    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        for i, url in enumerate(download_urls):
            try:
                # Pre-signed S3 URLs already contain auth in query params.
                # Sending an Authorization header to S3 causes signature
                # conflicts and errors.  Only add the header for non-S3
                # (API-proxied) download URLs.
                is_presigned = "X-Amz-" in url or "amazonaws.com" in url
                headers = {} if is_presigned else {"Authorization": f"Bearer {key}"}

                resp = await client.get(url, headers=headers)

                # If we guessed wrong and got a 401, retry with auth
                if resp.status_code == 401 and is_presigned:
                    resp = await client.get(
                        url,
                        headers={"Authorization": f"Bearer {key}"},
                    )

                if resp.status_code != 200:
                    errors.append(
                        f"URL {i + 1}: HTTP {resp.status_code} - {resp.text[:200]}"
                    )
                    continue

                filename = _extract_filename(resp, url, i + 1)
                file_path = out_dir / filename

                # Avoid overwriting: add suffix if file exists
                if file_path.exists():
                    stem = file_path.stem
                    suffix = file_path.suffix
                    counter = 1
                    while file_path.exists():
                        file_path = out_dir / f"{stem}_{counter}{suffix}"
                        counter += 1

                file_path.write_bytes(resp.content)
                downloaded_files.append(str(file_path.resolve()))

            except httpx.TimeoutException:
                errors.append(f"URL {i + 1}: Download timed out")
            except httpx.RequestError as exc:
                errors.append(f"URL {i + 1}: Network error - {exc}")
            except OSError as exc:
                errors.append(f"URL {i + 1}: File save error - {exc}")

    success = len(downloaded_files) > 0
    result: dict[str, Any] = {
        "success": success,
        "downloadedFiles": downloaded_files,
        "downloadedCount": len(downloaded_files),
    }
    if errors:
        result["errors"] = errors

    return result


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
