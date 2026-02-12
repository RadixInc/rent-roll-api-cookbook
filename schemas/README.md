# Webhook Schemas

When you include a webhook URL in your upload request, the API sends an HTTP POST to your endpoint when the batch completes processing.

## Event Type

Currently one event type is supported:

| Event | Trigger |
|-------|---------|
| `batch.completed` | All files in a batch have finished processing (success, partial, or failure) |

## Payload

See [webhook-payload.json](webhook-payload.json) for a complete example.

| Field | Type | Description |
|-------|------|-------------|
| `batch_id` | string (UUID) | The batch identifier from the upload response |
| `status` | string | One of: `completed`, `partial`, `failed` |
| `summary.files_uploaded` | integer | Total files in the batch |
| `summary.files_succeeded` | integer | Files processed successfully |
| `summary.files_failed` | integer | Files that failed processing |
| `summary.fully_processed` | integer | Files with extracted unit data |
| `summary.validation_required` | integer | Reserved for future use |
| `summary.unprocessable` | integer | Files that could not be processed |
| `summary.total_units_processed` | integer | Total rent roll units extracted |
| `summary.credits_used` | integer | Credits consumed by this batch |
| `outputs.download_url` | string or null | Pre-signed S3 URL to download results (expires after 24 hours) |
| `presigned_url_expiry` | string (ISO 8601) | When the download URL expires |
| `created_at` | string (ISO 8601) | When the batch was created |
| `completed_at` | string (ISO 8601) | When processing finished |

## Headers

See [webhook-headers.json](webhook-headers.json) for a complete example.

Every webhook request includes these headers:

| Header | Description |
|--------|-------------|
| `Content-Type` | Always `application/json` |
| `User-Agent` | `RedIQ-External-API/1.0` |
| `X-Batch-ID` | The batch UUID |
| `X-Batch-Status` | Same as `status` in the payload body |
| `X-Event-Type` | `batch.completed` |
| `X-Timestamp` | ISO 8601 timestamp of when the webhook was sent |

## Retry Behavior

If your endpoint returns a non-2xx status code or times out (10 second limit), the API retries up to 3 times with exponential backoff.

## Receiving Webhooks

Your webhook endpoint must:

1. Accept HTTP POST requests.
2. Use HTTPS (HTTP URLs are rejected at upload time).
3. Return a 2xx status code within 10 seconds.

### Example: Express.js

```javascript
app.post('/webhook/radix', (req, res) => {
  const { batch_id, status, summary, outputs } = req.body;

  console.log(`Batch ${batch_id} ${status}`);
  console.log(`Units processed: ${summary.total_units_processed}`);

  if (outputs.download_url) {
    console.log(`Download: ${outputs.download_url}`);
  }

  res.sendStatus(200);
});
```

### Example: Python Flask

```python
from flask import Flask, request

app = Flask(__name__)

@app.route("/webhook/radix", methods=["POST"])
def handle_webhook():
    data = request.json
    print(f"Batch {data['batch_id']} {data['status']}")
    print(f"Units processed: {data['summary']['total_units_processed']}")

    if data["outputs"]["download_url"]:
        print(f"Download: {data['outputs']['download_url']}")

    return "", 200
```


