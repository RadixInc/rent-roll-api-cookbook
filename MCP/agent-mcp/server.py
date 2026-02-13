"""
Radix Rent Roll MCP Server

FastMCP server that integrates Claude Desktop with the Radix/RedIQ Rent Roll API.
Upload rent roll files, monitor processing status, and download cleaned results
through natural language in Claude Desktop.
"""

# ---------------------------------------------------------------------------
# Startup diagnostics (runs before any third-party imports)
# ---------------------------------------------------------------------------

import sys
import os
import platform

_PYTHON = sys.executable

print(
    "[radix-rent-roll-mcp] Starting...\n"
    f"  Python : {sys.version}\n"
    f"  OS     : {platform.system()} {platform.release()}\n"
    f"  CWD    : {os.getcwd()}",
    file=sys.stderr,
)

# ---------------------------------------------------------------------------
# Third-party dependency guard
# ---------------------------------------------------------------------------

try:
    import httpx
except ImportError:
    print(
        "[radix-rent-roll-mcp] Missing required package: httpx\n"
        f"  Run: {_PYTHON} -m pip install -r requirements.txt",
        file=sys.stderr,
    )
    sys.exit(1)

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print(
        "[radix-rent-roll-mcp] Missing required package: mcp\n"
        f"  Run: {_PYTHON} -m pip install -r requirements.txt",
        file=sys.stderr,
    )
    sys.exit(1)

# ---------------------------------------------------------------------------
# Environment variable warnings (non-fatal)
# ---------------------------------------------------------------------------

for _var in ("RADIX_API_KEY", "RADIX_API_URL"):
    if not os.environ.get(_var):
        print(
            f"[radix-rent-roll-mcp] WARNING: {_var} is not set. "
            "You can still pass it per-request via tool parameters.",
            file=sys.stderr,
        )

# ---------------------------------------------------------------------------
# Standard library imports
# ---------------------------------------------------------------------------

import asyncio
import csv
import json
import re
import shutil
import tempfile
import time
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Optional, Literal
from urllib.parse import unquote, urlparse

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
    "radix-rent-roll-mcp",
    dependencies=["httpx"],
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_api_key(
    api_key_override: Optional[str] = None,
) -> str | dict[str, Any]:
    """Resolve the API key from override or environment variable.

    Returns the key string on success, or an error dict if missing.
    """
    key = api_key_override or os.environ.get("RADIX_API_KEY")
    if not key:
        return {
            "success": False,
            "error": "Missing API key",
            "details": (
                "Provide api_key_override or set the RADIX_API_KEY "
                "environment variable."
            ),
        }
    return key


def _get_api_key_optional(
    api_key_override: Optional[str] = None,
) -> Optional[str]:
    """Resolve an API key if available, else return None.

    This is used for tools that may operate on pre-signed URLs (no key needed),
    but can also handle API-proxied downloads (key required).
    """
    return api_key_override or os.environ.get("RADIX_API_KEY")


def _get_base_url() -> str:
    """Return the configured API base URL."""
    return os.environ.get("RADIX_API_URL", DEFAULT_BASE_URL).rstrip("/")


def _get_content_type(extension: str) -> str:
    """Map a file extension to its MIME type."""
    return MIME_TYPES.get(extension.lower(), "application/octet-stream")


def _unwrap_api_payload(body: dict[str, Any]) -> dict[str, Any]:
    """Return the API payload dict for either {data:{...}} or flat shapes."""
    data = body.get("data")
    if isinstance(data, dict):
        return data
    return body


def _normalize_status(value: Any) -> str:
    """Normalize status values to a lowercase string."""
    if value is None:
        return ""
    return str(value).strip().lower()


def _is_terminal_status(status: str) -> bool:
    s = _normalize_status(status)
    return s in {
        "complete",
        "completed",
        "failed",
        "partially complete",
        "partially completed",
    }


def _extract_zip_pointer(payload: dict[str, Any]) -> dict[str, Optional[str]]:
    """Extract canonical ZIP pointer (snake_case) with transitional fallback.

    Preference order:
      1) payload.outputs.download_url + payload.presigned_url_expiry (canonical)
      2) legacy payload.batchDownloads (type == 'zip' or first *.zip)
    """
    url: Optional[str] = None
    expires_at: Optional[str] = None

    outputs = payload.get("outputs")
    if isinstance(outputs, dict):
        dl = outputs.get("download_url")
        if isinstance(dl, str) and dl.strip():
            url = dl
            exp = payload.get("presigned_url_expiry")
            if isinstance(exp, str) and exp.strip():
                expires_at = exp
            return {
                "zip_download_url": url,
                "zip_presigned_expires_at": expires_at,
            }

    # Transitional fallback only
    batch_downloads = payload.get("batchDownloads")
    if isinstance(batch_downloads, list):
        zip_entry: Optional[dict[str, Any]] = None
        for bd in batch_downloads:
            if isinstance(bd, dict) and str(bd.get("type", "")).lower() == "zip":
                zip_entry = bd
                break
        if not zip_entry:
            for bd in batch_downloads:
                if not isinstance(bd, dict):
                    continue
                dl = bd.get("downloadUrl")
                if isinstance(dl, str) and dl.lower().endswith(".zip"):
                    zip_entry = bd
                    break
        if zip_entry:
            dl = zip_entry.get("downloadUrl")
            if isinstance(dl, str) and dl.strip():
                url = dl
            exp = zip_entry.get("expiresAt")
            if isinstance(exp, str) and exp.strip():
                expires_at = exp

    return {"zip_download_url": url, "zip_presigned_expires_at": expires_at}


def _is_presigned_s3_url(url: str) -> bool:
    u = url or ""
    return ("X-Amz-" in u) or ("amazonaws.com" in u)


def _match_zip_patterns(entry_name: str, patterns: list[str]) -> bool:
    """Match a ZIP entry name (POSIX-style) against glob-like patterns."""
    if not patterns:
        return False
    name = (entry_name or "").replace("\\", "/").lstrip("/")
    for pattern in patterns:
        if not pattern:
            continue
        pat = pattern.replace("\\", "/").lstrip("/")
        # Explicit support for common "directory globstar" semantics.
        # pathlib's PurePosixPath.match does NOT treat "dir/**" as "any depth under dir"
        # in the way most users expect, so we implement that behavior here.
        if pat in {"**", "**/*"}:
            return True
        if pat.endswith("/**"):
            prefix = pat[: -len("/**")]
            if name == prefix or name.startswith(prefix + "/"):
                return True

        if PurePosixPath(name).match(pat):
            return True
    return False


def _safe_zip_member_name(name: str) -> Optional[str]:
    """Return a normalized safe member name, or None if unsafe."""
    n = (name or "").replace("\\", "/")
    if not n or n.startswith("/") or n.startswith("\\"):
        return None
    # Block Windows drive / URI-ish entries
    if ":" in n.split("/")[0]:
        return None
    parts = PurePosixPath(n).parts
    if any(part == ".." for part in parts):
        return None
    return "/".join(parts)


def _resolve_path_loose(p: Path) -> Path:
    try:
        return p.resolve(strict=False)  # type: ignore[call-arg]
    except TypeError:
        return p.resolve()


def _resolve_output_dir(
    output_dir: Optional[str],
    strategy: Literal["temp", "use_output_dir"],
) -> tuple[str, list[dict[str, Any]]]:
    """Resolve the extraction output directory based on strategy.

    Returns (output_dir_used, warnings).

    - "temp" (default): always creates a fresh OS temp directory.
    - "use_output_dir": validates and uses the supplied path; falls back
      to temp with a warning if the path is not absolute or cannot be created.
    """
    warnings: list[dict[str, Any]] = []

    if strategy == "use_output_dir" and output_dir:
        p = Path(output_dir)
        if not p.is_absolute():
            warnings.append({
                "type": "output_dir_not_absolute",
                "requested": output_dir,
                "action": "falling_back_to_temp",
            })
        else:
            try:
                p.mkdir(parents=True, exist_ok=True)
                return str(p), warnings
            except OSError as exc:
                warnings.append({
                    "type": "output_dir_create_failed",
                    "requested": output_dir,
                    "error": str(exc),
                    "action": "falling_back_to_temp",
                })

    # Default / fallback: OS temp directory
    tmp = tempfile.mkdtemp(prefix="radix-rent-roll-")
    return tmp, warnings


def _read_csv_previews(
    extracted_files: list[str],
    preview_row_count: int = 200,
    max_inline_bytes: int = 250_000,
) -> list[dict[str, Any]]:
    """Build model-readable CSV preview artifacts from extracted files.

    For each extracted file that is a CSV under a ``processed-csv`` path
    segment, this returns a dict containing:
      - entry_name: the file's base name
      - local_path: the host-OS path (for humans / downstream tools)
      - header: list of column names
      - preview_rows: first *preview_row_count* rows as list[dict]
      - size_bytes: file size
      - inline_csv (optional): full CSV text when <= *max_inline_bytes*
    """
    results: list[dict[str, Any]] = []

    for fpath in extracted_files:
        fp = Path(fpath)
        # Only process CSVs that came from a processed-csv directory
        if fp.suffix.lower() != ".csv":
            continue
        normalized = fpath.replace("\\", "/")
        if "processed-csv" not in normalized:
            continue

        try:
            size = fp.stat().st_size
        except OSError:
            continue

        entry: dict[str, Any] = {
            "entry_name": fp.name,
            "local_path": str(fp),
            "size_bytes": size,
        }

        # Read header + preview rows
        try:
            with open(fp, newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                entry["header"] = list(reader.fieldnames or [])
                rows: list[dict[str, Any]] = []
                for _i, row in enumerate(reader):
                    if _i >= preview_row_count:
                        break
                    rows.append(dict(row))
                entry["preview_rows"] = rows
        except Exception:
            # If we can't read the CSV, still include what we can
            entry["header"] = []
            entry["preview_rows"] = []

        # Include full text if small enough
        if size <= max_inline_bytes:
            try:
                entry["inline_csv"] = fp.read_text(encoding="utf-8-sig")
            except Exception:
                pass

        results.append(entry)

    return results


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
    api_key_override: Optional[str] = None,
) -> dict[str, Any]:
    """Upload rent roll files to the Radix/RedIQ API for processing.

    Accepts .xlsx, .xls, .xlsm, .csv, and .ods files (max 20 files, 2 MB each).
    Returns a batchId you can use with check_batch_status to track progress.
    For most callers, prefer the higher-level process_rent_roll_workflow tool.

    Args:
        file_paths: Absolute paths to rent roll files on your local filesystem.
        notification_email: Email address to receive completion notifications.
        webhook_url: Optional webhook URL for completion callbacks.
        api_key_override: Optional API key (or set RADIX_API_KEY env var).
    """
    # --- Resolve API key ---
    key = _get_api_key(api_key_override=api_key_override)
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
    api_key_override: Optional[str] = None,
) -> dict[str, Any]:
    """Check the processing status of a rent roll batch.

    Returns current status, per-file progress, and (when available) the canonical
    batch ZIP pointer fields:
      - zip_download_url (snake_case canonical)
      - zip_presigned_expires_at (snake_case canonical)

    Args:
        batch_id: The batchId UUID returned from upload_rent_rolls.
        api_key_override: Optional API key (or set RADIX_API_KEY env var).
    """
    key = _get_api_key(api_key_override=api_key_override)
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

    payload = _unwrap_api_payload(body)
    zip_ptr = _extract_zip_pointer(payload)

    # Build per-file summaries
    files_info = []
    files_raw = payload.get("files")
    if isinstance(files_raw, list):
        for f in files_raw:
            if not isinstance(f, dict):
                continue
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
    bd_raw = payload.get("batchDownloads")
    if isinstance(bd_raw, list):
        for bd in bd_raw:
            if not isinstance(bd, dict):
                continue
            batch_downloads.append(
                {
                    "type": bd.get("type"),
                    "downloadUrl": bd.get("downloadUrl"),
                    "expiresAt": bd.get("expiresAt"),
                }
            )

    status_val = payload.get("status")
    batch_id_val = payload.get("batchId") or payload.get("batch_id") or batch_id
    summary_val = payload.get("summary") if isinstance(payload.get("summary"), dict) else None

    result: dict[str, Any] = {
        "success": True,
        "batchId": batch_id_val,
        "status": status_val,
        "fileCount": payload.get("fileCount", 0),
        "filesCompleted": payload.get("filesCompleted", 0),
        "filesInProgress": payload.get("filesInProgress", 0),
        "filesFailed": payload.get("filesFailed", 0),
        "percentComplete": payload.get("percentComplete", 0),
        "files": files_info,
        "createdAt": payload.get("createdAt") or payload.get("created_at"),
        "updatedAt": payload.get("updatedAt") or payload.get("completed_at") or payload.get("updated_at"),
    }

    # Canonical ZIP pointer (snake_case) + optional camelCase aliases
    result["zip_download_url"] = zip_ptr.get("zip_download_url")
    result["zip_presigned_expires_at"] = zip_ptr.get("zip_presigned_expires_at")
    result["zipDownloadUrl"] = result["zip_download_url"]
    result["zipPresignedExpiresAt"] = result["zip_presigned_expires_at"]

    if batch_downloads:
        result["batchDownloads"] = batch_downloads

    if payload.get("errorMessage"):
        result["errorMessage"] = payload["errorMessage"]

    if payload.get("actualTotalUnits") is not None:
        result["actualTotalUnits"] = payload["actualTotalUnits"]

    if payload.get("estimatedTotalUnits") is not None:
        result["estimatedTotalUnits"] = payload["estimatedTotalUnits"]

    if summary_val is not None:
        result["summary"] = summary_val

    return result


# ---------------------------------------------------------------------------
# Tool 3: download_processed_files
# ---------------------------------------------------------------------------


@mcp.tool()
async def download_processed_files(
    download_urls: list[str],
    output_directory: str,
    api_key_override: Optional[str] = None,
) -> dict[str, Any]:
    """Download processed rent roll files to a local directory.

    ZIP-first model: This tool is intended to download the batch-level ZIP
    artifact (canonical pointer: outputs.download_url exposed as zip_download_url).

    If you pass multiple URLs, this will download them, but you should prefer
    process_rent_roll_workflow (or the ZIP tools) to deterministically use the
    single canonical ZIP pointer.

    Args:
        download_urls: List of download URLs from the status response.
        output_directory: Local directory path to save downloaded files.
        api_key_override: Optional API key (or set RADIX_API_KEY env var).
    """
    try:
        return await _download_processed_files_impl(
            download_urls, output_directory, api_key_override
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
    api_key_override: Optional[str] = None,
) -> dict[str, Any]:
    """Internal implementation for download_processed_files."""
    key = _get_api_key(api_key_override=api_key_override)
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
    warnings: list[str] = []
    if len(download_urls) > 1:
        warnings.append(
            "Multiple download_urls were provided. Prefer process_rent_roll_workflow "
            "to deterministically use the canonical batch ZIP (zip_download_url)."
        )

    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        for i, url in enumerate(download_urls):
            try:
                # Pre-signed S3 URLs already contain auth in query params.
                # Sending an Authorization header to S3 causes signature
                # conflicts and errors.  Only add the header for non-S3
                # (API-proxied) download URLs.
                is_presigned = _is_presigned_s3_url(url)
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
    if warnings:
        result["warnings"] = warnings

    return result


# ---------------------------------------------------------------------------
# ZIP utilities (ZIP-first, temp-file based)
# ---------------------------------------------------------------------------


async def _download_zip_to_temp_file(
    zip_download_url: str,
    *,
    api_key_override: Optional[str] = None,
    temp_dir: Optional[str] = None,
) -> dict[str, Any]:
    """Download a ZIP URL to a temp file without loading it into memory."""
    if not zip_download_url:
        return {
            "success": False,
            "error": "Missing zip_download_url",
        }

    target_dir = None
    if temp_dir:
        try:
            td = Path(temp_dir)
            td.mkdir(parents=True, exist_ok=True)
            target_dir = str(td)
        except OSError as exc:
            return {
                "success": False,
                "error": "Cannot create temp directory",
                "details": f"Failed to create '{temp_dir}': {exc}",
            }

    fd, tmp_path = tempfile.mkstemp(
        suffix=".zip",
        dir=target_dir,
    )
    os.close(fd)

    try:
        headers: dict[str, str] = {}
        if not _is_presigned_s3_url(zip_download_url):
            key = _get_api_key_optional(api_key_override=api_key_override)
            if key:
                headers = {"Authorization": f"Bearer {key}"}

        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            async with client.stream("GET", zip_download_url, headers=headers) as resp:
                if resp.status_code != 200:
                    try:
                        body = (await resp.aread())[:1000]
                        text = body.decode(errors="replace")
                    except Exception:
                        text = ""
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass
                    return {
                        "success": False,
                        "error": "ZIP download failed",
                        "http_status": resp.status_code,
                        "details": text,
                    }

                with open(tmp_path, "wb") as f:
                    async for chunk in resp.aiter_bytes():
                        f.write(chunk)

        return {
            "success": True,
            "temp_zip_path": tmp_path,
        }
    except httpx.TimeoutException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        return {
            "success": False,
            "error": "ZIP download timed out",
        }
    except httpx.RequestError as exc:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        return {
            "success": False,
            "error": "Network error",
            "details": str(exc),
        }
    except OSError as exc:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        return {
            "success": False,
            "error": "File error",
            "details": str(exc),
        }


def _build_zip_manifest(
    zip_path: str,
    *,
    patterns: list[str],
) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    matched_entries: list[dict[str, Any]] = []

    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            name = (info.filename or "").replace("\\", "/")
            entry = {
                "name": name,
                "size": info.file_size,
                "compressed_size": info.compress_size,
                "is_dir": bool(getattr(info, "is_dir", lambda: name.endswith("/"))()),
            }
            entries.append(entry)
            if _match_zip_patterns(name, patterns):
                matched_entries.append(entry)

    return {
        "entries": entries,
        "matched_entries": matched_entries,
    }


def _extract_zip_members(
    zip_path: str,
    *,
    patterns: list[str],
    output_dir: str,
) -> dict[str, Any]:
    warnings: list[dict[str, Any]] = []
    extracted_files: list[str] = []

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    root_resolved = _resolve_path_loose(root)

    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            raw_name = (info.filename or "").replace("\\", "/")
            safe_name = _safe_zip_member_name(raw_name)
            if safe_name is None:
                warnings.append(
                    {
                        "type": "zip_slip_skipped",
                        "entry": raw_name,
                        "reason": "unsafe_member_name",
                    }
                )
                continue

            if getattr(info, "is_dir", lambda: raw_name.endswith("/"))():
                continue

            if not _match_zip_patterns(safe_name, patterns):
                continue

            parts = PurePosixPath(safe_name).parts
            dest = root.joinpath(*parts)
            dest_resolved = _resolve_path_loose(dest)

            if dest_resolved != root_resolved and root_resolved not in dest_resolved.parents:
                warnings.append(
                    {
                        "type": "zip_slip_skipped",
                        "entry": raw_name,
                        "reason": "path_escapes_output_dir",
                    }
                )
                continue

            dest.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info, "r") as src, open(dest, "wb") as out:
                shutil.copyfileobj(src, out)

            extracted_files.append(str(dest_resolved))

    return {
        "extracted_files": extracted_files,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Tool 4: get_batch_zip_manifest
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_batch_zip_manifest(
    zip_download_url: str,
    extract_patterns: list[str] = ["processed-csv/**"],
    api_key_override: Optional[str] = None,
) -> dict[str, Any]:
    """Get a manifest of entries inside the canonical batch ZIP (temp-file based).

    This tool treats zip_download_url as the authoritative artifact pointer.
    It downloads the ZIP to a temp file (no full memory load), reads the ZIP
    manifest, then deletes the temp file.
    """
    dl = await _download_zip_to_temp_file(
        zip_download_url,
        api_key_override=api_key_override,
    )
    if not dl.get("success"):
        return {
            "success": False,
            "zip_download_url": zip_download_url,
            "error": dl.get("error"),
            "http_status": dl.get("http_status"),
            "details": dl.get("details"),
        }

    tmp_path = dl["temp_zip_path"]
    try:
        manifest = _build_zip_manifest(tmp_path, patterns=extract_patterns)
        return {
            "success": True,
            "zip_download_url": zip_download_url,
            "entries": manifest["entries"],
            "matched_entries": manifest["matched_entries"],
        }
    except zipfile.BadZipFile:
        return {
            "success": False,
            "zip_download_url": zip_download_url,
            "error": "Invalid ZIP file",
        }
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Tool 5: download_and_extract_batch_zip
# ---------------------------------------------------------------------------


@mcp.tool()
async def download_and_extract_batch_zip(
    zip_download_url: str,
    patterns: list[str] = ["processed-csv/**"],
    output_dir: Optional[str] = None,
    api_key_override: Optional[str] = None,
) -> dict[str, Any]:
    """Download the canonical batch ZIP and optionally extract matched entries.

    - Always downloads ZIP to a temp file first (no full memory load).
    - If output_dir is None, returns manifest-only mode.
    - If output_dir is set, extracts entries matching patterns with zip-slip protection.
    """
    temp_dir = output_dir if output_dir else None
    dl = await _download_zip_to_temp_file(
        zip_download_url,
        api_key_override=api_key_override,
        temp_dir=temp_dir,
    )
    if not dl.get("success"):
        return {
            "success": False,
            "zip_download_url": zip_download_url,
            "error": dl.get("error"),
            "http_status": dl.get("http_status"),
            "details": dl.get("details"),
        }

    tmp_path = dl["temp_zip_path"]
    try:
        manifest = _build_zip_manifest(tmp_path, patterns=patterns)
        if not output_dir:
            return {
                "success": True,
                "zip_download_url": zip_download_url,
                "manifest": manifest,
                "extracted_files": [],
                "extracted_count": 0,
                "warnings": [],
            }

        extracted = _extract_zip_members(
            tmp_path,
            patterns=patterns,
            output_dir=output_dir,
        )
        return {
            "success": True,
            "zip_download_url": zip_download_url,
            "output_dir": str(Path(output_dir).resolve()),
            "manifest": manifest,
            "extracted_files": extracted["extracted_files"],
            "extracted_count": len(extracted["extracted_files"]),
            "warnings": extracted["warnings"],
        }
    except zipfile.BadZipFile:
        return {
            "success": False,
            "zip_download_url": zip_download_url,
            "error": "Invalid ZIP file",
        }
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Tool 6: process_rent_roll_workflow (deterministic end-to-end)
# ---------------------------------------------------------------------------


@mcp.tool()
async def process_rent_roll_workflow(
    file_paths: list[str],
    notification_email: str = "",
    webhook_url: Optional[str] = None,
    poll_interval_seconds: float = 7.5,
    timeout_seconds: float = 900.0,
    result_mode: Literal["urls", "manifest", "extract"] = "urls",
    output_dir: Optional[str] = None,
    output_dir_strategy: Literal["temp", "use_output_dir"] = "temp",
    extract_patterns: list[str] = ["processed-csv/**"],
    include_summary: bool = True,
    preview_rows: int = 200,
    inline_max_bytes: int = 250_000,
    api_key_override: Optional[str] = None,
) -> dict[str, Any]:
    """Upload → poll → return canonical ZIP pointer, optionally manifest/extract.

    Canonical artifact pointer:
      - zip_download_url := outputs.download_url (preferred when available)
      - zip_presigned_expires_at := presigned_url_expiry

    result_mode:
      - "urls":     return batch_id + status + zip pointer only
      - "manifest": include a lightweight ZIP manifest (temp-file based)
      - "extract":  extract matching entries and return model-readable CSV previews

    output_dir_strategy:
      - "temp" (default): always extract to a fresh OS temp directory.
        Prevents cross-OS path issues (e.g. Linux paths on a Windows host).
      - "use_output_dir": use the provided output_dir (must be an absolute path
        valid for the host OS).  Falls back to temp with a warning if invalid.

    preview_rows: number of CSV rows to include in each processed_csv preview.
    inline_max_bytes: if a CSV file is smaller than this, include the full text
        as inline_csv so the model can answer questions without filesystem access.
    """
    email = (notification_email or "").strip() or os.environ.get("RADIX_NOTIFICATION_EMAIL", "").strip()
    if not email:
        return {
            "success": False,
            "error": "Missing notification_email",
            "details": "Provide notification_email or set RADIX_NOTIFICATION_EMAIL.",
        }

    upload = await upload_rent_rolls(
        file_paths=file_paths,
        notification_email=email,
        webhook_url=webhook_url,
        api_key_override=api_key_override,
    )
    if not upload.get("success"):
        return upload

    batch_id = upload.get("batchId")
    if not batch_id:
        return {
            "success": False,
            "error": "Upload did not return batchId",
        }

    deadline = time.monotonic() + float(timeout_seconds)
    last_status: dict[str, Any] = {}

    while True:
        status_resp = await check_batch_status(
            batch_id=batch_id,
            api_key_override=api_key_override,
        )
        last_status = status_resp
        if not status_resp.get("success"):
            return status_resp

        status_val = status_resp.get("status", "")
        if _is_terminal_status(status_val):
            break

        if time.monotonic() >= deadline:
            break

        await asyncio.sleep(float(poll_interval_seconds))

    # --- Resolve ZIP pointer with fallback ---
    zip_download_url = last_status.get("zip_download_url")
    zip_presigned_expires_at = last_status.get("zip_presigned_expires_at")

    # Fallback: re-scan batchDownloads if canonical field is empty
    if not zip_download_url:
        zip_ptr = _extract_zip_pointer(last_status)
        zip_download_url = zip_ptr.get("zip_download_url")
        zip_presigned_expires_at = (
            zip_ptr.get("zip_presigned_expires_at") or zip_presigned_expires_at
        )

    warnings: list[Any] = []
    if last_status.get("filesFailed", 0):
        for f in last_status.get("files", []):
            if isinstance(f, dict) and f.get("status") == "failed":
                warnings.append(
                    {
                        "type": "file_failed",
                        "file_name": f.get("fileName"),
                        "error_message": f.get("errorMessage"),
                    }
                )
        warnings.append(
            {
                "type": "batch_failed_files",
                "files_failed": last_status.get("filesFailed"),
            }
        )

    # --- Resolve output directory (OS-agnostic) ---
    output_dir_used, dir_warnings = _resolve_output_dir(output_dir, output_dir_strategy)
    warnings.extend(dir_warnings)

    result: dict[str, Any] = {
        "success": True,
        "batch_id": batch_id,
        "status": last_status.get("status"),
        "zip_download_url": zip_download_url,
        "zip_presigned_expires_at": zip_presigned_expires_at,
        "output_dir_used": output_dir_used,
        "host_os": platform.system(),
        "warnings": warnings,
    }

    # Optional camelCase aliases for compatibility
    result["batchId"] = batch_id
    result["zipDownloadUrl"] = zip_download_url
    result["zipPresignedExpiresAt"] = zip_presigned_expires_at

    if include_summary and last_status.get("summary") is not None:
        result["summary"] = last_status.get("summary")

    if time.monotonic() >= deadline and not _is_terminal_status(last_status.get("status", "")):
        result["success"] = False
        result["error"] = "Workflow timed out"
        result["details"] = "Batch did not reach a terminal state within timeout_seconds."
        return result

    if result_mode == "urls":
        return result

    if not zip_download_url:
        result["success"] = False
        result["error"] = "Missing zip_download_url"
        result["details"] = "Batch completed but no canonical ZIP URL was available."
        return result

    async def _zip_op_with_one_refresh(
        op: Literal["manifest", "extract"],
        current_url: str,
        effective_output_dir: Optional[str] = None,
    ) -> dict[str, Any]:
        if op == "manifest":
            return await get_batch_zip_manifest(
                zip_download_url=current_url,
                extract_patterns=extract_patterns,
                api_key_override=api_key_override,
            )
        return await download_and_extract_batch_zip(
            zip_download_url=current_url,
            patterns=extract_patterns,
            output_dir=effective_output_dir,
            api_key_override=api_key_override,
        )

    zip_result = await _zip_op_with_one_refresh(
        result_mode, zip_download_url, output_dir_used,
    )
    if not zip_result.get("success") and zip_result.get("http_status") == 403:
        # Refresh ZIP pointer once by re-checking status
        refreshed = await check_batch_status(
            batch_id=batch_id,
            api_key_override=api_key_override,
        )
        if refreshed.get("success"):
            new_url = refreshed.get("zip_download_url") or zip_download_url
            if new_url:
                result["zip_download_url"] = new_url
                result["zipDownloadUrl"] = new_url
                zip_result = await _zip_op_with_one_refresh(
                    result_mode, new_url, output_dir_used,
                )

    if result_mode == "manifest":
        result["zip_manifest"] = {
            "entries": zip_result.get("entries", []),
            "matched_entries": zip_result.get("matched_entries", []),
        }
        if not zip_result.get("success"):
            result["warnings"].append(
                {
                    "type": "zip_manifest_failed",
                    "error": zip_result.get("error"),
                    "details": zip_result.get("details"),
                    "http_status": zip_result.get("http_status"),
                }
            )
        return result

    # --- Extract mode: always extract (temp dir guarantees output_dir_used) ---
    result["extracted_files"] = zip_result.get("extracted_files", [])
    result["extracted_count"] = zip_result.get("extracted_count", 0)
    if zip_result.get("warnings"):
        result["warnings"].extend(zip_result.get("warnings", []))
    if not zip_result.get("success"):
        result["warnings"].append(
            {
                "type": "zip_extract_failed",
                "error": zip_result.get("error"),
                "details": zip_result.get("details"),
                "http_status": zip_result.get("http_status"),
            }
        )

    # --- Build model-readable CSV previews ---
    extracted = result.get("extracted_files", [])
    if extracted:
        result["processed_csv"] = _read_csv_previews(
            extracted,
            preview_row_count=preview_rows,
            max_inline_bytes=inline_max_bytes,
        )
    else:
        result["processed_csv"] = []

    return result


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
