# Radix Rent Roll Cookbook

[![API Version](https://img.shields.io/badge/API-v1.0-blue)](https://connect.rediq.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![OpenAPI](https://img.shields.io/badge/OpenAPI-3.0-6BA539)](openapi/rent-roll-api.yaml)

Integration recipes and code examples for the **Radix Underwriting Rent Roll API** -- upload raw rent roll files (Excel, CSV) and receive standardized, structured data back.

---

## Quick Start

Upload a file in one command:

```bash
curl -X POST https://connect.rediq.io/api/external/v1/upload \
  -H "Authorization: Bearer $RADIX_API_KEY" \
  -F "files=@rent-roll.xlsx" \
  -F 'notificationMethod=[{"type":"email","entry":"you@company.com"}]'
```

You will receive an email when processing completes. Or poll for status:

```bash
curl -H "Authorization: Bearer $RADIX_API_KEY" \
  https://connect.rediq.io/api/external/v1/job/{batchId}/status
```

---

## Table of Contents

| Folder | Description |
| ------ | ----------- |
| [openapi/](openapi/) | OpenAPI 3.0 specification (YAML) |
| [schemas/](schemas/) | Webhook payload and header examples |
| [postman/](postman/) | Postman collection (import and go) |
| [examples/curl/](examples/curl/) | Bash script with upload + poll loop |
| [examples/python/](examples/python/) | Python script using `requests` |
| [examples/node/](examples/node/) | Node.js script using built-in `fetch` (zero deps) |
| [examples/web-ui/](examples/web-ui/) | Standalone browser-based upload page |
| [examples/desktop-scripts/windows/](examples/desktop-scripts/windows/) | Windows "Send To" batch script |
| [examples/desktop-scripts/mac/](examples/desktop-scripts/mac/) | macOS Quick Action shell script |

---

## Authentication

All API requests require an API key in the `Authorization` header:

```
Authorization: Bearer riq_live_your_api_key_here
```

API keys are available in the redIQ platform under **External API** settings. Keys follow the format:

- Production: `riq_live_...`
- Development: `riq_dev_...`

Set it as an environment variable to use with the examples in this repo:

```bash
export RADIX_API_KEY="riq_live_your_api_key_here"
```

---

## How It Works

1. **Upload** one or more rent roll files (`.xlsx`, `.xls`, `.xlsm`, `.csv`, `.ods`) to the `/upload` endpoint.
2. Files are **queued** for asynchronous processing.
3. **Poll** the `/job/{batchId}/status` endpoint, or wait for an **email/webhook notification**.
4. **Download** the standardized output from the pre-signed URLs in the response.

```
POST /api/external/v1/upload          -->  202 Accepted  { batchId, trackingUrl }
GET  /api/external/v1/job/{id}/status -->  200 OK        { status, files[], batchDownloads[] }
```

---

## Webhooks

If you include a webhook URL in the `notificationMethod` field, the API will send a POST request to your URL when processing completes. See [schemas/](schemas/) for the exact payload and header format.

---

## Limits

| Constraint | Value |
| ---------- | ----- |
| Max file size | 2 MB per file |
| Max files per request | 20 |
| Supported formats | `.xlsx`, `.xls`, `.xlsm`, `.csv`, `.ods` |
| Monthly credits | Per-account limit (check redIQ dashboard) |

---

## API Documentation

- **Interactive docs**: [https://connect.rediq.io/api/docs](https://connect.rediq.io/api/docs)
- **OpenAPI spec**: [openapi/rent-roll-api.yaml](openapi/rent-roll-api.yaml) (import into Swagger UI, Redocly, or Postman)

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## License

This project is licensed under the [MIT License](LICENSE).

---

## Support

- Email: [support@rediq.io](mailto:support@rediq.io)
- Documentation: [https://connect.rediq.io/api/docs](https://connect.rediq.io/api/docs)


