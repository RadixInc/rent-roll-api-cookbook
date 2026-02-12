#!/usr/bin/env node
/**
 * upload.mjs - Upload rent roll files and poll until processing completes.
 *
 * Zero external dependencies — uses the built-in Node.js fetch API (Node 18+).
 *
 * Usage:
 *   node upload.mjs <file> [--email user@example.com] [--webhook https://...]
 *
 * Environment:
 *   RADIX_API_KEY  - Your API key (required)
 */

import { readFileSync, existsSync } from "node:fs";
import { basename } from "node:path";

const BASE_URL = "https://connect.rediq.io";
const POLL_INTERVAL = 30_000; // 30 seconds

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function parseArgs(argv) {
  const args = { files: [], email: null, webhook: null, noPoll: false };
  let i = 2; // skip node and script path
  while (i < argv.length) {
    const arg = argv[i];
    if (arg === "--email" && argv[i + 1]) {
      args.email = argv[++i];
    } else if (arg === "--webhook" && argv[i + 1]) {
      args.webhook = argv[++i];
    } else if (arg === "--no-poll") {
      args.noPoll = true;
    } else if (!arg.startsWith("--")) {
      args.files.push(arg);
    }
    i++;
  }
  return args;
}

function getApiKey() {
  const key = process.env.RADIX_API_KEY;
  if (!key) {
    console.error("Error: RADIX_API_KEY environment variable is not set.");
    console.error('  export RADIX_API_KEY="riq_live_your_key_here"');
    process.exit(1);
  }
  return key;
}

function buildNotification(email, webhook) {
  const methods = [];
  if (email) methods.push({ type: "email", entry: email });
  if (webhook) methods.push({ type: "webhook", entry: webhook });
  if (methods.length === 0) {
    methods.push({ type: "email", entry: "noreply@example.com" });
  }
  return JSON.stringify(methods);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// ---------------------------------------------------------------------------
// Upload
// ---------------------------------------------------------------------------

async function upload(apiKey, files, notification) {
  const form = new FormData();

  for (const filePath of files) {
    if (!existsSync(filePath)) {
      console.error(`Error: File not found: ${filePath}`);
      process.exit(1);
    }
    const buffer = readFileSync(filePath);
    const blob = new Blob([buffer]);
    form.append("files", blob, basename(filePath));
  }

  form.append("notificationMethod", notification);

  console.log(`Uploading ${files.length} file(s)...`);
  console.log();

  const resp = await fetch(`${BASE_URL}/api/external/v1/upload`, {
    method: "POST",
    headers: { Authorization: `Bearer ${apiKey}` },
    body: form,
  });

  const body = await resp.json();

  if (resp.status !== 202) {
    console.error(`Upload failed (HTTP ${resp.status}):`);
    console.error(JSON.stringify(body, null, 2));
    process.exit(1);
  }

  const data = body.data;
  console.log("Upload successful.");
  console.log(`  Batch ID:       ${data.batchId}`);
  console.log(`  Files uploaded:  ${data.filesUploaded}`);
  console.log(`  Tracking URL:    ${data.trackingUrl}`);
  console.log();
  return data;
}

// ---------------------------------------------------------------------------
// Poll
// ---------------------------------------------------------------------------

async function poll(apiKey, batchId) {
  console.log(`Polling for status every ${POLL_INTERVAL / 1000}s...`);
  console.log();

  while (true) {
    const resp = await fetch(
      `${BASE_URL}/api/external/v1/job/${batchId}/status`,
      { headers: { Authorization: `Bearer ${apiKey}` } }
    );
    const body = await resp.json();
    const data = body.data;

    const status = data.status || "unknown";
    const percent = data.percentComplete ?? 0;
    const completed = data.filesCompleted ?? 0;
    const total = data.fileCount ?? 0;

    console.log(
      `  Status: ${status.padEnd(10)} | Progress: ${percent}% | Files: ${completed}/${total}`
    );

    if (status === "complete") {
      console.log();
      console.log("Processing complete.");
      console.log();

      for (const f of data.files || []) {
        if (f.downloadUrl) {
          console.log(`  ${f.fileName}: ${f.downloadUrl}`);
        }
      }

      const batchDownloads = data.batchDownloads || [];
      if (batchDownloads.length > 0) {
        console.log();
        console.log("Batch downloads:");
        for (const bd of batchDownloads) {
          console.log(`  ${bd.type}: ${bd.downloadUrl}`);
        }
      }

      return data;
    }

    if (status === "failed") {
      console.log();
      console.error(`Processing failed: ${data.errorMessage || "Unknown error"}`);
      process.exit(1);
    }

    await sleep(POLL_INTERVAL);
  }
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

const args = parseArgs(process.argv);

if (args.files.length === 0) {
  console.log("Usage: node upload.mjs <file> [--email addr] [--webhook url] [--no-poll]");
  process.exit(1);
}

const apiKey = getApiKey();
const notification = buildNotification(args.email, args.webhook);
const data = await upload(apiKey, args.files, notification);

if (args.noPoll) {
  console.log("Skipping status polling (--no-poll).");
} else {
  await poll(apiKey, data.batchId);
}


