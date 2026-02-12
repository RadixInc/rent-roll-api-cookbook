#!/usr/bin/env python3
"""
upload.py - Upload rent roll files and poll until processing completes.

Usage:
    python upload.py rent-roll.xlsx
    python upload.py rent-roll.xlsx --email user@example.com
    python upload.py file1.xlsx file2.xlsx --webhook https://hooks.example.com/abc

Environment:
    RADIX_API_KEY  - Your API key (required)
"""

import argparse
import json
import os
import sys
import time

import requests

BASE_URL = "https://connect.rediq.io"
POLL_INTERVAL = 30  # seconds


def get_api_key() -> str:
    """Read the API key from the environment."""
    key = os.environ.get("RADIX_API_KEY", "")
    if not key:
        print("Error: RADIX_API_KEY environment variable is not set.")
        print('  export RADIX_API_KEY="riq_live_your_key_here"')
        sys.exit(1)
    return key


def build_notification(email: str | None, webhook: str | None) -> str:
    """Build the notificationMethod JSON string."""
    methods: list[dict[str, str]] = []
    if email:
        methods.append({"type": "email", "entry": email})
    if webhook:
        methods.append({"type": "webhook", "entry": webhook})
    if not methods:
        # A notification method is required; default to a placeholder email.
        methods.append({"type": "email", "entry": "noreply@example.com"})
    return json.dumps(methods)


def upload(api_key: str, files: list[str], notification: str) -> dict:
    """Upload one or more files and return the parsed response body."""
    multipart_files = []
    for path in files:
        if not os.path.isfile(path):
            print(f"Error: File not found: {path}")
            sys.exit(1)
        multipart_files.append(("files", (os.path.basename(path), open(path, "rb"))))

    print(f"Uploading {len(files)} file(s)...")
    print()

    resp = requests.post(
        f"{BASE_URL}/api/external/v1/upload",
        headers={"Authorization": f"Bearer {api_key}"},
        files=multipart_files,
        data={"notificationMethod": notification},
        timeout=120,
    )

    # Close file handles
    for _, (_, fh) in multipart_files:
        fh.close()

    body = resp.json()

    if resp.status_code != 202:
        print(f"Upload failed (HTTP {resp.status_code}):")
        print(json.dumps(body, indent=2))
        sys.exit(1)

    data = body.get("data", {})
    print("Upload successful.")
    print(f"  Batch ID:       {data.get('batchId')}")
    print(f"  Files uploaded:  {data.get('filesUploaded')}")
    print(f"  Tracking URL:    {data.get('trackingUrl')}")
    print()
    return data


def poll(api_key: str, batch_id: str) -> dict:
    """Poll the status endpoint until the batch is complete or failed."""
    print(f"Polling for status every {POLL_INTERVAL}s...")
    print()

    while True:
        resp = requests.get(
            f"{BASE_URL}/api/external/v1/job/{batch_id}/status",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30,
        )
        body = resp.json()
        data = body.get("data", {})

        status = data.get("status", "unknown")
        percent = data.get("percentComplete", 0)
        completed = data.get("filesCompleted", 0)
        total = data.get("fileCount", 0)

        print(f"  Status: {status:<10} | Progress: {percent}% | Files: {completed}/{total}")

        if status == "complete":
            print()
            print("Processing complete.")
            print()

            # Individual file downloads
            for f in data.get("files", []):
                url = f.get("downloadUrl")
                if url:
                    print(f"  {f['fileName']}: {url}")

            # Batch downloads
            batch_downloads = data.get("batchDownloads") or []
            if batch_downloads:
                print()
                print("Batch downloads:")
                for bd in batch_downloads:
                    print(f"  {bd['type']}: {bd['downloadUrl']}")

            return data

        if status == "failed":
            print()
            error = data.get("errorMessage", "Unknown error")
            print(f"Processing failed: {error}")
            sys.exit(1)

        time.sleep(POLL_INTERVAL)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Upload rent roll files to the Radix Underwriting API.",
    )
    parser.add_argument(
        "files",
        nargs="+",
        help="One or more rent roll files (.xlsx, .xls, .csv, .ods)",
    )
    parser.add_argument(
        "--email",
        help="Email address for completion notification",
    )
    parser.add_argument(
        "--webhook",
        help="Webhook URL (HTTPS) for completion notification",
    )
    parser.add_argument(
        "--no-poll",
        action="store_true",
        help="Upload only; do not poll for status",
    )
    args = parser.parse_args()

    api_key = get_api_key()
    notification = build_notification(args.email, args.webhook)

    data = upload(api_key, args.files, notification)

    if args.no_poll:
        print("Skipping status polling (--no-poll).")
        return

    poll(api_key, data["batchId"])


if __name__ == "__main__":
    main()


