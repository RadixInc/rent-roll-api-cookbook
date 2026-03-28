#!/usr/bin/env bash
#
# upload.sh - CLI example for the RedIQ external rent roll API.
#
# Commands:
#   upload
#   status
#   deals create
#   deals list
#   deals get
#   deals update
#   deals delete
#
# Environment:
#   RADIX_API_KEY  - Required API key
#   RADIX_API_URL  - Optional base URL (defaults to production)

set -euo pipefail

BASE_URL="${RADIX_API_URL:-https://connect.rediq.io}"
POLL_INTERVAL=30

require_api_key() {
  if [[ -z "${RADIX_API_KEY:-}" ]]; then
    echo "Error: RADIX_API_KEY environment variable is not set."
    echo '  export RADIX_API_KEY="riq_live_your_key_here"'
    exit 1
  fi
}

require_dependencies() {
  if ! command -v curl >/dev/null 2>&1; then
    echo "Error: curl is required but not installed."
    exit 1
  fi

  if ! command -v jq >/dev/null 2>&1; then
    echo "Error: jq is required but not installed."
    echo "  Install: https://jqlang.github.io/jq/download/"
    exit 1
  fi
}

usage() {
  cat <<'EOF'
Usage:
  ./upload.sh upload [--email EMAIL] [--webhook URL] [--deal-id ID] [--no-poll] FILE [FILE...]
  ./upload.sh status BATCH_ID
  ./upload.sh deals create --deal-name NAME [--address ADDRESS] [--city CITY] [--state STATE] [--zip ZIP] [--unit-count COUNT]
  ./upload.sh deals list [--page PAGE] [--limit LIMIT] [--search TERM]
  ./upload.sh deals get COUNTER_ID
  ./upload.sh deals update COUNTER_ID [--deal-name NAME] [--address ADDRESS] [--city CITY] [--state STATE] [--zip ZIP] [--unit-count COUNT]
  ./upload.sh deals delete COUNTER_ID

Notes:
  - Upload requires at least one notification target: --email, --webhook, or both.
  - Only one --deal-id can be attached to an upload request, so all files in the
    batch will be linked to the same deal.
EOF
}

json_or_raw() {
  local body="$1"
  echo "$body" | jq . 2>/dev/null || echo "$body"
}

print_error_and_exit() {
  local http_code="$1"
  local body="$2"
  echo "Request failed (HTTP $http_code):"
  json_or_raw "$body"
  exit 1
}

build_notification_json() {
  local email="$1"
  local webhook="$2"

  if [[ -z "$email" && -z "$webhook" ]]; then
    echo "Error: upload requires at least one notification target (--email and/or --webhook)." >&2
    exit 1
  fi

  jq -cn --arg email "$email" --arg webhook "$webhook" '
    [
      ($email | select(length > 0) | {type: "email", entry: .}),
      ($webhook | select(length > 0) | {type: "webhook", entry: .})
    ] | map(select(. != null))
  '
}

deal_payload_json() {
  local deal_name="$1"
  local address="$2"
  local city="$3"
  local state="$4"
  local zip="$5"
  local unit_count="$6"

  jq -cn \
    --arg dealName "$deal_name" \
    --arg address "$address" \
    --arg city "$city" \
    --arg state "$state" \
    --arg zip "$zip" \
    --arg unitCount "$unit_count" '
    {
      dealName: ($dealName | select(length > 0)),
      address: ($address | select(length > 0)),
      city: ($city | select(length > 0)),
      state: ($state | select(length > 0)),
      zip: ($zip | select(length > 0)),
      unitCount: ($unitCount | select(length > 0) | tonumber)
    } | with_entries(select(.value != null))
  '
}

perform_json_request() {
  local method="$1"
  local path="$2"
  local body="${3:-}"

  local response
  if [[ -n "$body" ]]; then
    response=$(curl -sS -w "\n%{http_code}" \
      -X "$method" "${BASE_URL}${path}" \
      -H "Authorization: Bearer ${RADIX_API_KEY}" \
      -H "Content-Type: application/json" \
      --data "$body")
  else
    response=$(curl -sS -w "\n%{http_code}" \
      -X "$method" "${BASE_URL}${path}" \
      -H "Authorization: Bearer ${RADIX_API_KEY}")
  fi

  local http_code
  local response_body
  http_code=$(echo "$response" | tail -1)
  response_body=$(echo "$response" | sed '$d')
  printf '%s\n%s' "$http_code" "$response_body"
}

print_deal() {
  local body="$1"
  local prefix="${2:-Deal}"
  echo "$prefix:"
  echo "  Counter ID:     $(echo "$body" | jq -r '.counterId // .counter_id // "-"')"
  echo "  Name:           $(echo "$body" | jq -r '.dealName // .deal_name // "-"')"
  echo "  Address:        $(echo "$body" | jq -r '.address // "-"')"
  echo "  City:           $(echo "$body" | jq -r '.city // "-"')"
  echo "  State:          $(echo "$body" | jq -r '.state // "-"')"
  echo "  ZIP:            $(echo "$body" | jq -r '.zip // "-"')"
  echo "  Unit Count:     $(echo "$body" | jq -r '.unitCount // .unit_count // "-"')"
  echo "  Created On:     $(echo "$body" | jq -r '.createdOn // .created_on // "-"')"
  echo "  Last Modified:  $(echo "$body" | jq -r '.lastModifiedOn // .last_modified_on // "-"')"
}

print_deal_list() {
  local body="$1"
  echo "Deals:"
  echo "$body" | jq -r '
    .deals[]? |
    "  [\(.counterId)] \(.dealName) | \(.city // "-"), \(.state // "-") | units=\(.unitCount // "-")"
  '
  echo ""
  echo "Page:  $(echo "$body" | jq -r '.page // 1')"
  echo "Limit: $(echo "$body" | jq -r '.limit // 20')"
  echo "Total: $(echo "$body" | jq -r '.total // 0')"
}

print_batch_downloads() {
  local status_response="$1"
  local batch_downloads
  batch_downloads=$(echo "$status_response" | jq -r '.data.batchDownloads[]? | "  \(.type): \(.downloadUrl)"')
  if [[ -n "$batch_downloads" ]]; then
    echo ""
    echo "Batch downloads:"
    echo "$batch_downloads"
  fi
}

poll_batch_status() {
  local batch_id="$1"

  echo "Polling for status every ${POLL_INTERVAL}s..."
  echo ""

  while true; do
    local response
    response=$(curl -sS -w "\n%{http_code}" \
      -H "Authorization: Bearer ${RADIX_API_KEY}" \
      "${BASE_URL}/api/external/v1/job/${batch_id}/status")

    local http_code
    local body
    http_code=$(echo "$response" | tail -1)
    body=$(echo "$response" | sed '$d')

    if [[ "$http_code" != "200" ]]; then
      print_error_and_exit "$http_code" "$body"
    fi

    local status
    local percent
    local completed
    local total
    status=$(echo "$body" | jq -r '.data.status // "unknown"')
    percent=$(echo "$body" | jq -r '.data.percentComplete // 0')
    completed=$(echo "$body" | jq -r '.data.filesCompleted // 0')
    total=$(echo "$body" | jq -r '.data.fileCount // 0')

    echo "  Status: ${status}  |  Progress: ${percent}%  |  Files: ${completed}/${total}"

    case "${status,,}" in
      complete)
        echo ""
        echo "Processing complete."
        echo ""
        echo "$body" | jq -r '.data.files[]? | select(.downloadUrl != null) | "  \(.fileName): \(.downloadUrl)"' \
          | { read -r first_line || true; if [[ -n "${first_line:-}" ]]; then echo "Download URLs:"; echo "$first_line"; cat; fi; }
        print_batch_downloads "$body"
        return 0
        ;;
      "partially complete")
        echo ""
        echo "Processing partially complete."
        echo "Batch error: $(echo "$body" | jq -r '.data.errorMessage // "One or more files failed."')"
        echo ""
        echo "Completed file downloads:"
        echo "$body" | jq -r '.data.files[]? | select(.downloadUrl != null) | "  \(.fileName): \(.downloadUrl)"'
        echo ""
        echo "Failed files:"
        echo "$body" | jq -r '.data.files[]? | select((.status // "") | ascii_downcase | contains("fail")) | "  \(.fileName): \(.errorMessage // "Unknown error")"'
        print_batch_downloads "$body"
        return 1
        ;;
      failed)
        echo ""
        echo "Processing failed: $(echo "$body" | jq -r '.data.errorMessage // "Unknown error"')"
        return 1
        ;;
    esac

    sleep "$POLL_INTERVAL"
  done
}

cmd_upload() {
  local email=""
  local webhook=""
  local deal_id=""
  local no_poll="false"
  local files=()

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --email)
        email="${2:-}"
        shift 2
        ;;
      --webhook)
        webhook="${2:-}"
        shift 2
        ;;
      --deal-id)
        deal_id="${2:-}"
        shift 2
        ;;
      --no-poll)
        no_poll="true"
        shift
        ;;
      --help|-h)
        usage
        exit 0
        ;;
      --*)
        echo "Unknown upload option: $1"
        usage
        exit 1
        ;;
      *)
        files+=("$1")
        shift
        ;;
    esac
  done

  if [[ ${#files[@]} -eq 0 ]]; then
    echo "Error: upload requires at least one file."
    usage
    exit 1
  fi

  local notification_json
  notification_json=$(build_notification_json "$email" "$webhook")

  for file in "${files[@]}"; do
    if [[ ! -f "$file" ]]; then
      echo "Error: File not found: $file"
      exit 1
    fi
  done

  echo "Uploading ${#files[@]} file(s)..."
  echo ""

  local curl_args=(
    -sS -w "\n%{http_code}"
    -X POST "${BASE_URL}/api/external/v1/upload"
    -H "Authorization: Bearer ${RADIX_API_KEY}"
    -F "notificationMethod=${notification_json}"
  )

  if [[ -n "$deal_id" ]]; then
    curl_args+=(-F "dealId=${deal_id}")
  fi

  for file in "${files[@]}"; do
    curl_args+=(-F "files=@${file}")
  done

  local response
  response=$(curl "${curl_args[@]}")

  local http_code
  local body
  http_code=$(echo "$response" | tail -1)
  body=$(echo "$response" | sed '$d')

  if [[ "$http_code" != "202" ]]; then
    print_error_and_exit "$http_code" "$body"
  fi

  local batch_id
  batch_id=$(echo "$body" | jq -r '.data.batchId')

  echo "Upload successful."
  echo "  Batch ID:       ${batch_id}"
  echo "  Files uploaded: $(echo "$body" | jq -r '.data.filesUploaded')"
  echo "  Tracking URL:   $(echo "$body" | jq -r '.data.trackingUrl')"
  if [[ -n "$deal_id" ]]; then
    echo "  Deal ID:        ${deal_id}"
  fi
  echo ""

  if [[ "$no_poll" == "true" ]]; then
    echo "Skipping status polling (--no-poll)."
    return 0
  fi

  poll_batch_status "$batch_id"
}

cmd_status() {
  local batch_id="${1:-}"
  if [[ -z "$batch_id" ]]; then
    echo "Error: status requires a batch ID."
    usage
    exit 1
  fi
  poll_batch_status "$batch_id"
}

cmd_deals_create() {
  local deal_name=""
  local address=""
  local city=""
  local state=""
  local zip=""
  local unit_count=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --deal-name) deal_name="${2:-}"; shift 2 ;;
      --address) address="${2:-}"; shift 2 ;;
      --city) city="${2:-}"; shift 2 ;;
      --state) state="${2:-}"; shift 2 ;;
      --zip) zip="${2:-}"; shift 2 ;;
      --unit-count) unit_count="${2:-}"; shift 2 ;;
      *) echo "Unknown deals create option: $1"; usage; exit 1 ;;
    esac
  done

  if [[ -z "$deal_name" ]]; then
    echo "Error: deals create requires --deal-name."
    exit 1
  fi

  local payload
  payload=$(deal_payload_json "$deal_name" "$address" "$city" "$state" "$zip" "$unit_count")

  local response
  response=$(perform_json_request "POST" "/api/external/v1/deals" "$payload")
  local http_code
  local body
  http_code=$(echo "$response" | head -1)
  body=$(echo "$response" | tail -n +2)
  [[ "$http_code" == "201" || "$http_code" == "200" ]] || print_error_and_exit "$http_code" "$body"

  print_deal "$(echo "$body" | jq '.data')"
}

cmd_deals_list() {
  local page="1"
  local limit="20"
  local search=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --page) page="${2:-}"; shift 2 ;;
      --limit) limit="${2:-}"; shift 2 ;;
      --search) search="${2:-}"; shift 2 ;;
      *) echo "Unknown deals list option: $1"; usage; exit 1 ;;
    esac
  done

  local path="/api/external/v1/deals?page=${page}&limit=${limit}"
  if [[ -n "$search" ]]; then
    path="${path}&search=$(printf '%s' "$search" | jq -sRr @uri)"
  fi

  local response
  response=$(perform_json_request "GET" "$path")
  local http_code
  local body
  http_code=$(echo "$response" | head -1)
  body=$(echo "$response" | tail -n +2)
  [[ "$http_code" == "200" ]] || print_error_and_exit "$http_code" "$body"

  print_deal_list "$(echo "$body" | jq '.data')"
}

cmd_deals_get() {
  local counter_id="${1:-}"
  if [[ -z "$counter_id" ]]; then
    echo "Error: deals get requires COUNTER_ID."
    exit 1
  fi

  local response
  response=$(perform_json_request "GET" "/api/external/v1/deals/${counter_id}")
  local http_code
  local body
  http_code=$(echo "$response" | head -1)
  body=$(echo "$response" | tail -n +2)
  [[ "$http_code" == "200" ]] || print_error_and_exit "$http_code" "$body"

  print_deal "$(echo "$body" | jq '.data')"
}

cmd_deals_update() {
  local counter_id="${1:-}"
  shift || true
  local deal_name=""
  local address=""
  local city=""
  local state=""
  local zip=""
  local unit_count=""

  if [[ -z "$counter_id" ]]; then
    echo "Error: deals update requires COUNTER_ID."
    exit 1
  fi

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --deal-name) deal_name="${2:-}"; shift 2 ;;
      --address) address="${2:-}"; shift 2 ;;
      --city) city="${2:-}"; shift 2 ;;
      --state) state="${2:-}"; shift 2 ;;
      --zip) zip="${2:-}"; shift 2 ;;
      --unit-count) unit_count="${2:-}"; shift 2 ;;
      *) echo "Unknown deals update option: $1"; usage; exit 1 ;;
    esac
  done

  if [[ -z "$deal_name" && -z "$address" && -z "$city" && -z "$state" && -z "$zip" && -z "$unit_count" ]]; then
    echo "Error: deals update requires at least one field to update."
    exit 1
  fi

  local payload
  payload=$(deal_payload_json "$deal_name" "$address" "$city" "$state" "$zip" "$unit_count")

  local response
  response=$(perform_json_request "PUT" "/api/external/v1/deals/${counter_id}" "$payload")
  local http_code
  local body
  http_code=$(echo "$response" | head -1)
  body=$(echo "$response" | tail -n +2)
  [[ "$http_code" == "200" ]] || print_error_and_exit "$http_code" "$body"

  print_deal "$(echo "$body" | jq '.data')" "Updated deal"
}

cmd_deals_delete() {
  local counter_id="${1:-}"
  if [[ -z "$counter_id" ]]; then
    echo "Error: deals delete requires COUNTER_ID."
    exit 1
  fi

  local response
  response=$(perform_json_request "DELETE" "/api/external/v1/deals/${counter_id}")
  local http_code
  local body
  http_code=$(echo "$response" | head -1)
  body=$(echo "$response" | tail -n +2)
  [[ "$http_code" == "200" ]] || print_error_and_exit "$http_code" "$body"

  echo "$(echo "$body" | jq -r '.data.message // "Deal deleted successfully."')"
}

main() {
  require_api_key
  require_dependencies

  local command="${1:-}"
  case "$command" in
    upload)
      shift
      cmd_upload "$@"
      ;;
    status)
      shift
      cmd_status "$@"
      ;;
    deals)
      local subcommand="${2:-}"
      case "$subcommand" in
        create) shift 2; cmd_deals_create "$@" ;;
        list) shift 2; cmd_deals_list "$@" ;;
        get) shift 2; cmd_deals_get "$@" ;;
        update) shift 2; cmd_deals_update "$@" ;;
        delete) shift 2; cmd_deals_delete "$@" ;;
        *)
          usage
          exit 1
          ;;
      esac
      ;;
    --help|-h|"")
      usage
      ;;
    *)
      echo "Unknown command: $command"
      usage
      exit 1
      ;;
  esac
}

main "$@"
