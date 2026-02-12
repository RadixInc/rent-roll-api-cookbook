# Python Example

Upload rent roll files and poll for results using Python and the `requests` library.

## Prerequisites

- Python 3.10+
- [requests](https://pypi.org/project/requests/)

## Setup

```bash
pip install -r requirements.txt
export RADIX_API_KEY="riq_live_your_api_key_here"
```

## Usage

```bash
# Upload a single file with email notification
python upload.py rent-roll.xlsx --email user@example.com

# Upload multiple files
python upload.py file1.xlsx file2.xlsx --email user@example.com

# Upload with a webhook callback
python upload.py rent-roll.xlsx --webhook https://hooks.example.com/abc

# Upload only (skip polling)
python upload.py rent-roll.xlsx --no-poll
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

## Programmatic Usage

You can also import the functions directly in your own scripts:

```python
import os
os.environ["RADIX_API_KEY"] = "riq_live_..."

from upload import get_api_key, upload, poll, build_notification

api_key = get_api_key()
notification = build_notification(email="user@example.com", webhook=None)
data = upload(api_key, ["rent-roll.xlsx"], notification)
result = poll(api_key, data["batchId"])
```


