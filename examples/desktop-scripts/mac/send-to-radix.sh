#!/usr/bin/env bash
# ===========================================================================
#  send-to-radix.sh
#  macOS Quick Action / Automator script.
#  Uploads one or more rent roll files to the Radix Underwriting API.
#
#  Setup (Quick Action):
#    1. Set your API key and email below.
#    2. Open Automator → New → Quick Action.
#    3. Set "Workflow receives" to "files or folders" in "Finder".
#    4. Add a "Run Shell Script" action, set "Pass input" to "as arguments".
#    5. Paste the contents of this script into the action.
#    6. Save as "Send to Radix".
#    7. Right-click any file(s) in Finder → Quick Actions → Send to Radix.
#
#  Or run directly from Terminal:
#    ./send-to-radix.sh rent-roll.xlsx
#
#  Dependencies: curl (pre-installed on macOS)
# ===========================================================================

set -euo pipefail

# --- Configuration (edit these) ---------------------------------------------
API_KEY="riq_live_your_api_key_here"
NOTIFY_EMAIL="you@company.com"
API_URL="https://connect.rediq.io/api/external/v1/upload"
# ----------------------------------------------------------------------------

if [ "$API_KEY" = "riq_live_your_api_key_here" ]; then
  echo "ERROR: Please edit this script and set your API_KEY."
  echo "Open $(realpath "$0") in a text editor and replace the placeholder."
  exit 1
fi

if [ $# -eq 0 ]; then
  echo "Usage: ./send-to-radix.sh <file1> [file2] ..."
  exit 1
fi

# Build the curl file arguments
FILE_ARGS=()
COUNT=0
for FILE in "$@"; do
  if [ -f "$FILE" ]; then
    FILE_ARGS+=(-F "files=@${FILE}")
    COUNT=$((COUNT + 1))
  else
    echo "Warning: Skipping non-file argument: $FILE"
  fi
done

if [ "$COUNT" -eq 0 ]; then
  echo "Error: No valid files provided."
  exit 1
fi

echo ""
echo "  Radix Rent Roll Uploader"
echo "  ========================"
echo "  Uploading $COUNT file(s)..."
echo ""

NOTIFICATION="[{\"type\":\"email\",\"entry\":\"${NOTIFY_EMAIL}\"}]"

HTTP_CODE=$(curl -s -o /tmp/radix-response.json -w "%{http_code}" \
  -X POST "$API_URL" \
  -H "Authorization: Bearer ${API_KEY}" \
  "${FILE_ARGS[@]}" \
  -F "notificationMethod=${NOTIFICATION}")

if [ "$HTTP_CODE" = "202" ]; then
  echo "  Upload successful! (HTTP 202)"
  echo ""
  if command -v jq &>/dev/null; then
    jq . /tmp/radix-response.json
  else
    cat /tmp/radix-response.json
    echo ""
  fi
  echo ""
  echo "  You will receive an email at $NOTIFY_EMAIL when processing completes."
else
  echo "  Upload FAILED (HTTP $HTTP_CODE)"
  echo ""
  if command -v jq &>/dev/null; then
    jq . /tmp/radix-response.json
  else
    cat /tmp/radix-response.json
    echo ""
  fi
fi

rm -f /tmp/radix-response.json
echo ""


