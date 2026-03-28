# Node.js Example

A zero-dependency Node.js CLI example for the RedIQ external API using the built-in `fetch` and `FormData` APIs.

## Prerequisites

- Node.js 18+

## Setup

```bash
export RADIX_API_KEY="riq_live_your_api_key_here"
export RADIX_API_URL="https://connect.rediq.io" # optional
```

## Commands

```bash
# Upload and poll
node upload.mjs upload rent-roll.xlsx --email user@example.com

# Upload with webhook only
node upload.mjs upload rent-roll.xlsx --webhook https://hooks.example.com/rent-roll

# Upload and attach to a deal
node upload.mjs upload file1.xlsx file2.xlsx --email user@example.com --deal-id 42

# Upload only
node upload.mjs upload rent-roll.xlsx --email user@example.com --no-poll

# Batch status
node upload.mjs status 6af30011-af82-4425-a1ad-406db4b0995c

# Deals CRUD
node upload.mjs deals:create --deal-name "Sunset Plaza Apartments" --city Austin --state TX --unit-count 128
node upload.mjs deals:list --search Sunset
node upload.mjs deals:get 42
node upload.mjs deals:update 42 --deal-name "Sunset Plaza Phase II" --unit-count 132
node upload.mjs deals:delete 42
```

You can also write deal commands as `node upload.mjs deals list ...` if you prefer a space-separated form.

## Tests

```bash
npm test
```

The tests use the built-in `node:test` runner and cover CLI parsing, notification and deal payload helpers, and upload `dealId` form data behavior.
