# cURL Example

Upload a rent roll file and poll for results using cURL and jq.

## Prerequisites

- [curl](https://curl.se/) (pre-installed on macOS and most Linux distributions; ships with Windows 10+)
- [jq](https://jqlang.github.io/jq/download/) for JSON parsing

## Setup

```bash
export RADIX_API_KEY="riq_live_your_api_key_here"
```

## Usage

```bash
# Upload a file with email notification
./upload.sh rent-roll.xlsx user@example.com

# Upload a file (no email)
./upload.sh rent-roll.xlsx
```

The script will:

1. Upload the file to the API.
2. Print the batch ID and tracking URL.
3. Poll the status endpoint every 30 seconds.
4. Print download URLs when processing completes.

## Quick One-Liner

If you just want to upload without the polling loop:

```bash
curl -X POST https://connect.rediq.io/api/external/v1/upload \
  -H "Authorization: Bearer $RADIX_API_KEY" \
  -F "files=@rent-roll.xlsx" \
  -F 'notificationMethod=[{"type":"email","entry":"user@example.com"}]'
```

## Output

```
Uploading: rent-roll.xlsx

Upload successful.
  Batch ID:       6af30011-af82-4425-a1ad-406db4b0995c
  Files uploaded:  1
  Tracking URL:    https://connect.rediq.io/api/external/v1/job/6af30011-.../status

Polling for status every 30s...

  Status: queued      |  Progress: 0%    |  Files: 0/1
  Status: complete    |  Progress: 100%  |  Files: 1/1

Processing complete.

Download URLs:
  rent-roll.xlsx: https://external-api-rent-rolls.s3.amazonaws.com/...

Batch downloads:
  json: https://external-api-rent-rolls.s3.amazonaws.com/...
  excel: https://external-api-rent-rolls.s3.amazonaws.com/...
```


