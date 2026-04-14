#!/usr/bin/env python3
"""
upload.py - Multi-command CLI example for the RedIQ external rent roll API.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from contextlib import ExitStack
from typing import Any

import requests

BASE_URL = os.environ.get("RADIX_API_URL", "https://connect.rediq.io").rstrip("/")
POLL_INTERVAL = 30
TERMINAL_STATUSES = {"complete", "failed", "partially complete"}


def get_api_key() -> str:
    """Read the API key from the environment."""
    key = os.environ.get("RADIX_API_KEY", "")
    if not key:
        print("Error: RADIX_API_KEY environment variable is not set.")
        print('  export RADIX_API_KEY="riq_live_your_key_here"')
        sys.exit(1)
    return key


def normalize_status(value: str | None) -> str:
    return (value or "").strip().lower()


def is_terminal_status(value: str | None) -> bool:
    return normalize_status(value) in TERMINAL_STATUSES


def build_notification(email: str | None, webhook: str | None) -> str:
    """Build the notificationMethod JSON string."""
    methods: list[dict[str, str]] = []
    if email:
        methods.append({"type": "email", "entry": email})
    if webhook:
        methods.append({"type": "webhook", "entry": webhook})
    if not methods:
        raise ValueError(
            "Provide at least one notification target using --email, --webhook, or both."
        )
    return json.dumps(methods)


def build_deal_payload(
    deal_name: str | None = None,
    address: str | None = None,
    city: str | None = None,
    state: str | None = None,
    zip_code: str | None = None,
    unit_count: int | None = None,
) -> dict[str, Any]:
    payload = {
        "dealName": deal_name,
        "address": address,
        "city": city,
        "state": state,
        "zip": zip_code,
        "unitCount": unit_count,
    }
    return {key: value for key, value in payload.items() if value is not None}


def parse_error_body(resp: requests.Response) -> str:
    try:
        body = resp.json()
    except ValueError:
        return resp.text[:1000] or f"HTTP {resp.status_code}"

    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, str):
            return error
        if isinstance(error, dict):
            message = error.get("message")
            details = error.get("details")
            if isinstance(details, list) and details:
                rendered = ", ".join(str(item.get("message") or item) for item in details)
                return f"{message}: {rendered}" if message else rendered
            if message:
                return str(message)
        return json.dumps(body, indent=2)
    return str(body)


def api_request(
    api_key: str,
    method: str,
    path: str,
    *,
    expected_status: int | tuple[int, ...],
    timeout: int = 60,
    **kwargs: Any,
) -> dict[str, Any]:
    """Perform an authenticated JSON API request."""
    if isinstance(expected_status, int):
        expected = (expected_status,)
    else:
        expected = expected_status

    headers = {"Authorization": f"Bearer {api_key}"}
    if "headers" in kwargs:
        headers.update(kwargs.pop("headers"))

    resp = requests.request(
        method,
        f"{BASE_URL}{path}",
        headers=headers,
        timeout=timeout,
        **kwargs,
    )

    try:
        body = resp.json()
    except ValueError as exc:
        raise RuntimeError("Could not parse JSON response from API.") from exc

    if resp.status_code not in expected:
        raise RuntimeError(
            f"API request failed (HTTP {resp.status_code}): {parse_error_body(resp)}"
        )

    return body


def print_json(data: Any) -> None:
    print(json.dumps(data, indent=2))


def print_deal_summary(prefix: str, deal: dict[str, Any]) -> None:
    print(f"{prefix}:")
    print(f"  Counter ID:     {deal.get('counterId', '-')}")
    print(f"  Name:           {deal.get('dealName', '-')}")
    print(f"  Address:        {deal.get('address') or '-'}")
    print(f"  City:           {deal.get('city') or '-'}")
    print(f"  State:          {deal.get('state') or '-'}")
    print(f"  ZIP:            {deal.get('zip') or '-'}")
    print(f"  Unit Count:     {deal.get('unitCount') if deal.get('unitCount') is not None else '-'}")
    print(f"  Created On:     {deal.get('createdOn') or '-'}")
    print(f"  Last Modified:  {deal.get('lastModifiedOn') or '-'}")


def upload(
    api_key: str,
    files: list[str],
    notification: str,
    deal_id: int | None = None,
) -> dict[str, Any]:
    """Upload one or more files and return the parsed response payload."""
    with ExitStack() as stack:
        multipart_files = []
        for path in files:
            if not os.path.isfile(path):
                raise FileNotFoundError(f"File not found: {path}")
            handle = stack.enter_context(open(path, "rb"))
            multipart_files.append(("files", (os.path.basename(path), handle)))

        print(f"Uploading {len(files)} file(s)...")
        print()

        data = {"notificationMethod": notification}
        if deal_id is not None:
            data["dealId"] = str(deal_id)

        body = api_request(
            api_key,
            "POST",
            "/api/external/v1/upload",
            expected_status=202,
            timeout=120,
            files=multipart_files,
            data=data,
        )

    payload = body.get("data", {})
    print("Upload successful.")
    print(f"  Batch ID:       {payload.get('batchId')}")
    print(f"  Files uploaded: {payload.get('filesUploaded')}")
    print(f"  Tracking URL:   {payload.get('trackingUrl')}")
    if deal_id is not None:
        print(f"  Deal ID:        {deal_id}")
    print()
    return payload


def status_request(api_key: str, batch_id: str) -> dict[str, Any]:
    body = api_request(
        api_key,
        "GET",
        f"/api/external/v1/job/{batch_id}/status",
        expected_status=200,
        timeout=30,
    )
    return body.get("data", {})


def print_status_summary(data: dict[str, Any]) -> None:
    status = data.get("status", "unknown")
    print(f"Status:              {status}")
    print(f"Percent complete:    {data.get('percentComplete', 0)}%")
    print(f"Files completed:     {data.get('filesCompleted', 0)} / {data.get('fileCount', 0)}")
    print(f"Files in progress:   {data.get('filesInProgress', 0)}")
    print(f"Files failed:        {data.get('filesFailed', 0)}")
    if data.get("errorMessage"):
        print(f"Batch error:         {data.get('errorMessage')}")


def print_downloads(data: dict[str, Any]) -> None:
    files = data.get("files") or []
    downloads = [f"  {item['fileName']}: {item['downloadUrl']}" for item in files if item.get("downloadUrl")]
    if downloads:
        print("Download URLs:")
        print("\n".join(downloads))

    batch_downloads = data.get("batchDownloads") or []
    if batch_downloads:
        print()
        print("Batch downloads:")
        for item in batch_downloads:
            print(f"  {item.get('type')}: {item.get('downloadUrl')}")


def print_failed_files(data: dict[str, Any]) -> None:
    files = data.get("files") or []
    failed = [
        f"  {item.get('fileName')}: {item.get('errorMessage') or 'Unknown error'}"
        for item in files
        if "fail" in normalize_status(item.get("status"))
    ]
    if failed:
        print("Failed files:")
        print("\n".join(failed))


def poll(api_key: str, batch_id: str) -> dict[str, Any]:
    """Poll the status endpoint until the batch reaches a terminal state."""
    print(f"Polling for status every {POLL_INTERVAL}s...")
    print()

    while True:
        data = status_request(api_key, batch_id)

        status = data.get("status", "unknown")
        percent = data.get("percentComplete", 0)
        completed = data.get("filesCompleted", 0)
        total = data.get("fileCount", 0)

        print(f"  Status: {status:<18} | Progress: {percent}% | Files: {completed}/{total}")

        normalized = normalize_status(status)
        if normalized == "complete":
            print()
            print("Processing complete.")
            print()
            print_downloads(data)
            return data

        if normalized == "partially complete":
            print()
            print("Processing partially complete.")
            print(f"Batch error: {data.get('errorMessage') or 'One or more files failed.'}")
            print()
            print_downloads(data)
            if data.get("filesFailed", 0):
                print()
                print_failed_files(data)
            raise RuntimeError("Batch completed partially.")

        if normalized == "failed":
            raise RuntimeError(f"Processing failed: {data.get('errorMessage') or 'Unknown error'}")

        time.sleep(POLL_INTERVAL)


def create_deal(
    api_key: str,
    *,
    deal_name: str,
    address: str | None = None,
    city: str | None = None,
    state: str | None = None,
    zip_code: str | None = None,
    unit_count: int | None = None,
) -> dict[str, Any]:
    body = api_request(
        api_key,
        "POST",
        "/api/external/v1/deals",
        expected_status=(200, 201),
        json=build_deal_payload(deal_name, address, city, state, zip_code, unit_count),
    )
    return body.get("data", {})


def list_deals(
    api_key: str,
    *,
    page: int = 1,
    limit: int = 20,
    search: str | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {"page": page, "limit": limit}
    if search:
        params["search"] = search
    body = api_request(
        api_key,
        "GET",
        "/api/external/v1/deals",
        expected_status=200,
        params=params,
    )
    return body.get("data", {})


def get_deal(api_key: str, counter_id: int) -> dict[str, Any]:
    body = api_request(
        api_key,
        "GET",
        f"/api/external/v1/deals/{counter_id}",
        expected_status=200,
    )
    return body.get("data", {})


def update_deal(
    api_key: str,
    counter_id: int,
    *,
    deal_name: str | None = None,
    address: str | None = None,
    city: str | None = None,
    state: str | None = None,
    zip_code: str | None = None,
    unit_count: int | None = None,
) -> dict[str, Any]:
    payload = build_deal_payload(deal_name, address, city, state, zip_code, unit_count)
    if not payload:
        raise ValueError("Provide at least one deal field to update.")
    body = api_request(
        api_key,
        "PUT",
        f"/api/external/v1/deals/{counter_id}",
        expected_status=200,
        json=payload,
    )
    return body.get("data", {})


def delete_deal(api_key: str, counter_id: int) -> dict[str, Any]:
    body = api_request(
        api_key,
        "DELETE",
        f"/api/external/v1/deals/{counter_id}",
        expected_status=200,
    )
    return body.get("data", {})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Interact with the RedIQ external rent roll API.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    upload_parser = subparsers.add_parser("upload", help="Upload rent roll files")
    upload_parser.add_argument("files", nargs="+", help="One or more rent roll files")
    upload_parser.add_argument("--email", help="Email address for completion notification")
    upload_parser.add_argument("--webhook", help="HTTPS webhook URL for completion notification")
    upload_parser.add_argument("--deal-id", type=int, help="Optional deal counterId for the batch")
    upload_parser.add_argument("--no-poll", action="store_true", help="Upload only; do not poll")

    status_parser = subparsers.add_parser("status", help="Check batch status")
    status_parser.add_argument("batch_id", help="Batch ID returned from upload")

    deals_create = subparsers.add_parser("deals-create", help="Create a deal")
    deals_create.add_argument("--deal-name", required=True, help="Deal name")
    deals_create.add_argument("--address")
    deals_create.add_argument("--city")
    deals_create.add_argument("--state")
    deals_create.add_argument("--zip")
    deals_create.add_argument("--unit-count", type=int)

    deals_list = subparsers.add_parser("deals-list", help="List deals")
    deals_list.add_argument("--page", type=int, default=1)
    deals_list.add_argument("--limit", type=int, default=20)
    deals_list.add_argument("--search")

    deals_get = subparsers.add_parser("deals-get", help="Get deal details")
    deals_get.add_argument("counter_id", type=int)

    deals_update = subparsers.add_parser("deals-update", help="Update a deal")
    deals_update.add_argument("counter_id", type=int)
    deals_update.add_argument("--deal-name")
    deals_update.add_argument("--address")
    deals_update.add_argument("--city")
    deals_update.add_argument("--state")
    deals_update.add_argument("--zip")
    deals_update.add_argument("--unit-count", type=int)

    deals_delete = subparsers.add_parser("deals-delete", help="Delete a deal")
    deals_delete.add_argument("counter_id", type=int)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    api_key = get_api_key()

    try:
        if args.command == "upload":
            notification = build_notification(args.email, args.webhook)
            data = upload(api_key, args.files, notification, deal_id=args.deal_id)
            if args.no_poll:
                print("Skipping status polling (--no-poll).")
                return
            poll(api_key, data["batchId"])
            return

        if args.command == "status":
            data = status_request(api_key, args.batch_id)
            print_status_summary(data)
            print()
            print_downloads(data)
            if normalize_status(data.get("status")) == "partially complete":
                print()
                print_failed_files(data)
            return

        if args.command == "deals-create":
            deal = create_deal(
                api_key,
                deal_name=args.deal_name,
                address=args.address,
                city=args.city,
                state=args.state,
                zip_code=args.zip,
                unit_count=args.unit_count,
            )
            print_deal_summary("Created deal", deal)
            return

        if args.command == "deals-list":
            data = list_deals(api_key, page=args.page, limit=args.limit, search=args.search)
            print_json(data)
            return

        if args.command == "deals-get":
            deal = get_deal(api_key, args.counter_id)
            print_deal_summary("Deal", deal)
            return

        if args.command == "deals-update":
            deal = update_deal(
                api_key,
                args.counter_id,
                deal_name=args.deal_name,
                address=args.address,
                city=args.city,
                state=args.state,
                zip_code=args.zip,
                unit_count=args.unit_count,
            )
            print_deal_summary("Updated deal", deal)
            return

        if args.command == "deals-delete":
            data = delete_deal(api_key, args.counter_id)
            print(data.get("message", f"Deal {args.counter_id} deleted successfully."))
            return
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"Error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
