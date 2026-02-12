# Web UI Example

A standalone single-page upload interface for the Radix Rent Roll API. Open `index.html` in any modern browser — no build step, no server, no dependencies.

## Features

- Drag-and-drop file selection
- API key input with show/hide toggle
- Email and webhook notification options
- Real-time processing status with auto-refresh every 30 seconds
- Progress bar and per-file status tracking
- Responsive design (works on mobile)

## Quick Start

1. Open `index.html` in your browser (double-click the file or use a local server).
2. Drag rent roll files onto the drop zone (or click to browse).
3. Enter your API key.
4. Select a notification method (email and/or webhook).
5. Click **Submit for Processing**.

The page will show a live status tracker that polls the API every 30 seconds until processing is complete.

## Configuration

By default the UI sends requests to the production API:

```
https://connect.rediq.io
```

To target a different environment, edit the `API_BASE_URL` variable at the top of `app.js`:

```js
var API_BASE_URL = 'https://connect.rediq.io'; // change this
```

## CORS Note

Because the page makes cross-origin requests to `connect.rediq.io`, you may need to serve the files from a local HTTP server instead of opening them directly from disk. Any static file server will work:

```bash
# Python
python -m http.server 8080

# Node.js (npx, no install)
npx serve .

# Then open http://localhost:8080
```

## File Structure

```
web-ui/
  index.html   - Page markup
  styles.css   - Styling (Inter font, responsive layout)
  app.js       - Application logic (upload, poll, status display)
```

## Customisation

| What                  | Where                             |
| --------------------- | --------------------------------- |
| API base URL          | `app.js` → `API_BASE_URL`        |
| Max files per upload  | `app.js` → `MAX_FILES`           |
| Max file size         | `app.js` → `MAX_FILE_SIZE`       |
| Allowed extensions    | `app.js` → `ALLOWED_EXTENSIONS`  |
| Poll interval         | `app.js` → `STATUS_POLL_INTERVAL`|
| Colours / branding    | `styles.css` → CSS custom properties in `:root` |


