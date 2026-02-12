# Postman Collection

A ready-to-use Postman collection for the Radix Rent Roll API.

## Import

1. Open Postman.
2. Click **Import** (top left).
3. Select `Radix-Rent-Roll-API.postman_collection.json`.
4. The collection appears in your sidebar.

## Setup

Before sending requests, set the `api_key` variable:

1. Click the collection name in the sidebar.
2. Go to the **Variables** tab.
3. Replace `riq_live_your_api_key_here` with your actual API key.
4. Click **Save**.

## Requests

### 1. Upload Rent Roll Files

- **Method:** POST
- **Body:** Select your `.xlsx` / `.csv` file(s) in the `files` field.
- **notificationMethod:** Pre-filled with an email example. Change the email address to yours.
- On success (202), the `batch_id` variable is automatically saved for the next request.

### 2. Get Job Status

- **Method:** GET
- **Path:** Uses the `batch_id` saved from the upload request.
- Run this request to check processing progress.
- Repeat every 30 seconds until `status` is `complete`.

## Collection Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `base_url` | `https://connect.rediq.io` | API base URL |
| `api_key` | `riq_live_your_api_key_here` | Your API key (replace this) |
| `batch_id` | (empty) | Auto-populated after upload |

## Works with Insomnia Too

This collection can also be imported into Insomnia:

1. Open Insomnia.
2. Click **Create** > **Import from File**.
3. Select `Radix-Rent-Roll-API.postman_collection.json`.


