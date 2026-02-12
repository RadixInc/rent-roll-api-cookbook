# Node.js Example

Upload rent roll files and poll for results using Node.js with zero external dependencies.

Uses the built-in `fetch` and `FormData` APIs available in Node.js 18+.

## Prerequisites

- Node.js 18+

No `npm install` required.

## Setup

```bash
export RADIX_API_KEY="riq_live_your_api_key_here"
```

## Usage

```bash
# Upload a single file with email notification
node upload.mjs rent-roll.xlsx --email user@example.com

# Upload multiple files
node upload.mjs file1.xlsx file2.xlsx --email user@example.com

# Upload with a webhook callback
node upload.mjs rent-roll.xlsx --webhook https://hooks.example.com/abc

# Upload only (skip polling)
node upload.mjs rent-roll.xlsx --no-poll
```

## Options

| Flag        | Description                                   |
| ----------- | --------------------------------------------- |
| `--email`   | Email address for completion notification      |
| `--webhook` | HTTPS webhook URL for completion notification  |
| `--no-poll` | Upload files and exit without polling status   |

## Output

```
Uploading 1 file(s)...

Upload successful.
  Batch ID:       6af30011-af82-4425-a1ad-406db4b0995c
  Files uploaded:  1
  Tracking URL:    https://connect.rediq.io/api/external/v1/job/6af30011-.../status

Polling for status every 30s...

  Status: queued     | Progress: 0% | Files: 0/1
  Status: complete   | Progress: 100% | Files: 1/1

Processing complete.

  rent-roll.xlsx: https://external-api-rent-rolls.s3.amazonaws.com/...

Batch downloads:
  json: https://external-api-rent-rolls.s3.amazonaws.com/...
  excel: https://external-api-rent-rolls.s3.amazonaws.com/...
```


