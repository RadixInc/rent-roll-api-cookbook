#!/usr/bin/env bash
#
# upload.sh - Upload a rent roll file and poll until processing completes.
#
# Usage:
#   ./upload.sh <file> [email]
#
# Environment:
#   RADIX_API_KEY  - Your API key (required)
#
# Dependencies:
#   curl, jq
#
# Example:
#   export RADIX_API_KEY="riq_live_..."
#   ./upload.sh rent-roll.xlsx user@example.com

set -euo pipefail

BASE_URL="https://connect.rediq.io"
POLL_INTERVAL=30

# ---------------------------------------------------------------------------
# Validate inputs
# ---------------------------------------------------------------------------

if [ -z "${RADIX_API_KEY:-}" ]; then
  echo "Error: RADIX_API_KEY environment variable is not set."
  echo "  export RADIX_API_KEY=\"riq_live_your_key_here\""
  exit 1
fi

if ! command -v jq &> /dev/null; then
  echo "Error: jq is required but not installed."
  echo "  Install: https://jqlang.github.io/jq/download/"
  exit 1
fi

FILE="${1:-}"
EMAIL="${2:-}"

if [ -z "$FILE" ]; then
  echo "Usage: ./upload.sh <file> [email]"
  exit 1
fi

if [ ! -f "$FILE" ]; then
  echo "Error: File not found: $FILE"
  exit 1
fi

# Build notification method
if [ -n "$EMAIL" ]; then
  NOTIFICATION="[{\"type\":\"email\",\"entry\":\"$EMAIL\"}]"
else
  NOTIFICATION="[{\"type\":\"email\",\"entry\":\"noreply@example.com\"}]"
fi

# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

echo "Uploading: $FILE"
echo ""

RESPONSE=$(curl -s -w "\n%{http_code}" \
  -X POST "${BASE_URL}/api/external/v1/upload" \
  -H "Authorization: Bearer ${RADIX_API_KEY}" \
  -F "files=@${FILE}" \
  -F "notificationMethod=${NOTIFICATION}")

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" != "202" ]; then
  echo "Upload failed (HTTP $HTTP_CODE):"
  echo "$BODY" | jq . 2>/dev/null || echo "$BODY"
  exit 1
fi

BATCH_ID=$(echo "$BODY" | jq -r '.data.batchId')
TRACKING_URL=$(echo "$BODY" | jq -r '.data.trackingUrl')
FILES_UPLOADED=$(echo "$BODY" | jq -r '.data.filesUploaded')

echo "Upload successful."
echo "  Batch ID:       $BATCH_ID"
echo "  Files uploaded:  $FILES_UPLOADED"
echo "  Tracking URL:    $TRACKING_URL"
echo ""

# ---------------------------------------------------------------------------
# Poll for status
# ---------------------------------------------------------------------------

echo "Polling for status every ${POLL_INTERVAL}s..."
echo ""

while true; do
  STATUS_RESPONSE=$(curl -s \
    -H "Authorization: Bearer ${RADIX_API_KEY}" \
    "${BASE_URL}/api/external/v1/job/${BATCH_ID}/status")

  STATUS=$(echo "$STATUS_RESPONSE" | jq -r '.data.status')
  PERCENT=$(echo "$STATUS_RESPONSE" | jq -r '.data.percentComplete')
  COMPLETED=$(echo "$STATUS_RESPONSE" | jq -r '.data.filesCompleted')
  TOTAL=$(echo "$STATUS_RESPONSE" | jq -r '.data.fileCount')

  echo "  Status: $STATUS  |  Progress: ${PERCENT}%  |  Files: ${COMPLETED}/${TOTAL}"

  case "$STATUS" in
    complete)
      echo ""
      echo "Processing complete."
      echo ""

      # Print download URLs
      DOWNLOADS=$(echo "$STATUS_RESPONSE" | jq -r '.data.files[] | select(.downloadUrl != null) | "  \(.fileName): \(.downloadUrl)"')
      if [ -n "$DOWNLOADS" ]; then
        echo "Download URLs:"
        echo "$DOWNLOADS"
      fi

      BATCH_DOWNLOADS=$(echo "$STATUS_RESPONSE" | jq -r '.data.batchDownloads[]? | "  \(.type): \(.downloadUrl)"')
      if [ -n "$BATCH_DOWNLOADS" ]; then
        echo ""
        echo "Batch downloads:"
        echo "$BATCH_DOWNLOADS"
      fi

      exit 0
      ;;
    failed)
      echo ""
      ERROR=$(echo "$STATUS_RESPONSE" | jq -r '.data.errorMessage // "Unknown error"')
      echo "Processing failed: $ERROR"
      exit 1
      ;;
  esac

  sleep "$POLL_INTERVAL"
done


