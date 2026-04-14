# Web UI Example

A standalone single-page API demo for the RedIQ external API. Open `index.html` in a browser and use one API key for both deal management and rent roll uploads.

## Features

- Create, search, inspect, update, and delete deals
- Drag-and-drop file selection
- Upload with email, webhook, or both
- Optional upload-to-deal attachment using a selected deal
- Real-time batch status polling using the API batch status values
- Batch download and failed-file display
- Responsive layout for desktop and mobile

## Quick Start

1. Open `index.html` in your browser, or serve the folder locally.
2. Enter your API key.
3. Create a deal or load an existing one in the Deals section.
4. Optionally click **Use For Upload** to attach the selected deal to the next upload batch.
5. Add one or more files, configure notifications, and submit the batch.
6. Review the status, batch downloads, and any failed files in the success view.

## Configuration

The page targets production by default:

```js
var API_BASE_URL = 'https://connect.rediq.io';
```

Edit that constant in `app.js` to point at another environment if needed.

## Manual Test Checklist

- Create a deal and confirm it appears in the picker.
- Search for a deal by name.
- Load deal details, update fields, and save them.
- Delete a deal.
- Upload with email only.
- Upload with webhook only.
- Upload with email + webhook + attached deal.
- Confirm the success view shows the attached deal.
- Confirm batch status handles `queued`, `in progress`, `complete`, `failed`, and `partially complete`.
- Confirm batch downloads and failed files render when present.

## CORS Note

If direct file access causes CORS issues, serve the folder locally:

```bash
python -m http.server 8080
```

Then open `http://localhost:8080`.
