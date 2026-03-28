# Python Example

A multi-command Python CLI example for the RedIQ external API using `requests`.

## Prerequisites

- Python 3.10+
- [requests](https://pypi.org/project/requests/)

## Setup

```bash
pip install -r requirements.txt
export RADIX_API_KEY="riq_live_your_api_key_here"
export RADIX_API_URL="https://connect.rediq.io" # optional
```

## Commands

```bash
# Upload and poll
python upload.py upload rent-roll.xlsx --email user@example.com

# Upload with webhook only
python upload.py upload rent-roll.xlsx --webhook https://hooks.example.com/rent-roll

# Upload and attach to a deal
python upload.py upload file1.xlsx file2.xlsx --email user@example.com --deal-id 42

# Upload only
python upload.py upload rent-roll.xlsx --email user@example.com --no-poll

# Batch status
python upload.py status 6af30011-af82-4425-a1ad-406db4b0995c

# Deals CRUD
python upload.py deals-create --deal-name "Sunset Plaza Apartments" --city Austin --state TX --unit-count 128
python upload.py deals-list --search Sunset
python upload.py deals-get 42
python upload.py deals-update 42 --deal-name "Sunset Plaza Phase II" --unit-count 132
python upload.py deals-delete 42
```

## Programmatic Usage

```python
import os

from upload import build_notification, create_deal, get_api_key, upload

os.environ["RADIX_API_KEY"] = "riq_live_..."

api_key = get_api_key()
deal = create_deal(api_key, deal_name="Sunset Plaza Apartments", city="Austin", state="TX")
notification = build_notification("user@example.com", None)
batch = upload(api_key, ["rent-roll.xlsx"], notification, deal_id=deal["counterId"])
```

## Tests

```bash
python -m unittest test_upload.py
```

The tests cover notification payloads, deal payloads, Deals CRUD helpers, and status/upload helper behavior.
