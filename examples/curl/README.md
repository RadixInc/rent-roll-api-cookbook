# cURL Example

A shell-based CLI example for the RedIQ external API using `curl` and `jq`.

## Prerequisites

- [curl](https://curl.se/)
- [jq](https://jqlang.github.io/jq/download/)

## Setup

```bash
export RADIX_API_KEY="riq_live_your_api_key_here"
export RADIX_API_URL="https://connect.rediq.io" # optional
chmod +x upload.sh
```

## Commands

```bash
# Upload and poll
./upload.sh upload --email user@example.com rent-roll.xlsx

# Upload with webhook only
./upload.sh upload --webhook https://hooks.example.com/rent-roll rent-roll.xlsx

# Upload and attach the batch to a deal
./upload.sh upload --email user@example.com --deal-id 42 file1.xlsx file2.xlsx

# Upload only, skip polling
./upload.sh upload --email user@example.com --no-poll rent-roll.xlsx

# Check status for an existing batch
./upload.sh status 6af30011-af82-4425-a1ad-406db4b0995c

# Deals CRUD
./upload.sh deals create --deal-name "Sunset Plaza Apartments" --city Austin --state TX --unit-count 128
./upload.sh deals list --search Sunset
./upload.sh deals get 42
./upload.sh deals update 42 --deal-name "Sunset Plaza Phase II" --unit-count 132
./upload.sh deals delete 42
```

## Notes

- Upload requires at least one notification target: `--email`, `--webhook`, or both.
- Only one `--deal-id` can be attached to each upload request, so every file in that batch maps to the same deal.
- Batch polling uses the API batch status directly and surfaces `partially complete` as a non-success terminal state.

## Output

Typical upload output:

```text
Uploading 2 file(s)...

Upload successful.
  Batch ID:       6af30011-af82-4425-a1ad-406db4b0995c
  Files uploaded: 2
  Tracking URL:   https://connect.rediq.io/api/external/v1/job/6af30011-af82-4425-a1ad-406db4b0995c/status
  Deal ID:        42
```
