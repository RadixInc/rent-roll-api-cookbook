#!/usr/bin/env node
/**
 * upload.mjs - Multi-command CLI example for the RedIQ external rent roll API.
 */

import { existsSync, readFileSync } from "node:fs";
import { basename } from "node:path";
import { pathToFileURL } from "node:url";

export const BASE_URL = (process.env.RADIX_API_URL || "https://connect.rediq.io").replace(/\/$/, "");
export const POLL_INTERVAL = 30_000;

export function normalizeStatus(value) {
  return String(value || "").trim().toLowerCase();
}

export function isTerminalStatus(value) {
  return ["complete", "failed", "partially complete"].includes(normalizeStatus(value));
}

export function buildNotification(email, webhook) {
  const methods = [];
  if (email) methods.push({ type: "email", entry: email });
  if (webhook) methods.push({ type: "webhook", entry: webhook });
  if (methods.length === 0) {
    throw new Error("Provide at least one notification target using --email, --webhook, or both.");
  }
  return JSON.stringify(methods);
}

export function buildDealPayload(options = {}) {
  const payload = {
    dealName: options.dealName,
    address: options.address,
    city: options.city,
    state: options.state,
    zip: options.zip,
    unitCount: options.unitCount,
  };

  return Object.fromEntries(
    Object.entries(payload).filter(([, value]) => value !== undefined && value !== null)
  );
}

export function parseCli(argv) {
  const rawArgs = argv.slice(2);
  if (rawArgs.length === 0) {
    return { command: null, options: {}, positionals: [] };
  }

  let command = rawArgs[0];
  let index = 1;
  if (command === "deals" && rawArgs[1]) {
    command = `deals:${rawArgs[1]}`;
    index = 2;
  }

  const options = {};
  const positionals = [];
  while (index < rawArgs.length) {
    const arg = rawArgs[index];
    if (arg === "--no-poll") {
      options.noPoll = true;
      index += 1;
      continue;
    }
    if (arg.startsWith("--")) {
      const key = arg.slice(2).replace(/-([a-z])/g, (_, c) => c.toUpperCase());
      options[key] = rawArgs[index + 1];
      index += 2;
      continue;
    }
    positionals.push(arg);
    index += 1;
  }

  return { command, options, positionals };
}

function usage() {
  console.log(`Usage:
  node upload.mjs upload [--email EMAIL] [--webhook URL] [--deal-id ID] [--no-poll] FILE [FILE...]
  node upload.mjs status BATCH_ID
  node upload.mjs deals:create --deal-name NAME [--address ADDRESS] [--city CITY] [--state STATE] [--zip ZIP] [--unit-count COUNT]
  node upload.mjs deals:list [--page PAGE] [--limit LIMIT] [--search TERM]
  node upload.mjs deals:get COUNTER_ID
  node upload.mjs deals:update COUNTER_ID [--deal-name NAME] [--address ADDRESS] [--city CITY] [--state STATE] [--zip ZIP] [--unit-count COUNT]
  node upload.mjs deals:delete COUNTER_ID

You can also write the deal commands as:
  node upload.mjs deals create ...
`);
}

function getApiKey() {
  const key = process.env.RADIX_API_KEY;
  if (!key) {
    throw new Error('RADIX_API_KEY environment variable is not set.');
  }
  return key;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function parseJsonResponse(resp) {
  try {
    return await resp.json();
  } catch (error) {
    throw new Error("Could not parse JSON response from API.");
  }
}

function parseApiError(body, status) {
  if (typeof body?.error === "string") return body.error;
  if (body?.error?.message) return body.error.message;
  return JSON.stringify(body ?? { status }, null, 2);
}

async function jsonRequest(apiKey, method, path, { expectedStatus, body, query } = {}) {
  const url = new URL(`${BASE_URL}${path}`);
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== null && value !== "") {
        url.searchParams.set(key, String(value));
      }
    }
  }

  const headers = { Authorization: `Bearer ${apiKey}` };
  const init = { method, headers };
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }

  const resp = await fetch(url, init);
  const parsed = await parseJsonResponse(resp);
  const expected = Array.isArray(expectedStatus) ? expectedStatus : [expectedStatus];
  if (!expected.includes(resp.status)) {
    throw new Error(`API request failed (HTTP ${resp.status}): ${parseApiError(parsed, resp.status)}`);
  }
  return parsed;
}

export async function upload(apiKey, files, notification, dealId) {
  const form = new FormData();

  for (const filePath of files) {
    if (!existsSync(filePath)) {
      throw new Error(`File not found: ${filePath}`);
    }
    const buffer = readFileSync(filePath);
    const blob = new Blob([buffer]);
    form.append("files", blob, basename(filePath));
  }

  form.append("notificationMethod", notification);
  if (dealId !== undefined && dealId !== null) {
    form.append("dealId", String(dealId));
  }

  console.log(`Uploading ${files.length} file(s)...`);
  console.log();

  const resp = await fetch(`${BASE_URL}/api/external/v1/upload`, {
    method: "POST",
    headers: { Authorization: `Bearer ${apiKey}` },
    body: form,
  });
  const body = await parseJsonResponse(resp);

  if (resp.status !== 202) {
    throw new Error(`Upload failed (HTTP ${resp.status}): ${parseApiError(body, resp.status)}`);
  }

  const data = body.data || {};
  console.log("Upload successful.");
  console.log(`  Batch ID:       ${data.batchId}`);
  console.log(`  Files uploaded: ${data.filesUploaded}`);
  console.log(`  Tracking URL:   ${data.trackingUrl}`);
  if (dealId !== undefined && dealId !== null) {
    console.log(`  Deal ID:        ${dealId}`);
  }
  console.log();
  return data;
}

export async function statusRequest(apiKey, batchId) {
  const body = await jsonRequest(apiKey, "GET", `/api/external/v1/job/${batchId}/status`, {
    expectedStatus: 200,
  });
  return body.data || {};
}

function printDownloads(data) {
  const fileDownloads = (data.files || []).filter((file) => file.downloadUrl);
  if (fileDownloads.length > 0) {
    console.log("Download URLs:");
    for (const item of fileDownloads) {
      console.log(`  ${item.fileName}: ${item.downloadUrl}`);
    }
  }

  const batchDownloads = data.batchDownloads || [];
  if (batchDownloads.length > 0) {
    console.log();
    console.log("Batch downloads:");
    for (const item of batchDownloads) {
      console.log(`  ${item.type}: ${item.downloadUrl}`);
    }
  }
}

function printFailedFiles(data) {
  const failed = (data.files || []).filter((file) => normalizeStatus(file.status).includes("fail"));
  if (failed.length > 0) {
    console.log("Failed files:");
    for (const item of failed) {
      console.log(`  ${item.fileName}: ${item.errorMessage || "Unknown error"}`);
    }
  }
}

export async function poll(apiKey, batchId) {
  console.log(`Polling for status every ${POLL_INTERVAL / 1000}s...`);
  console.log();

  while (true) {
    const data = await statusRequest(apiKey, batchId);
    const status = data.status || "unknown";
    const percent = data.percentComplete ?? 0;
    const completed = data.filesCompleted ?? 0;
    const total = data.fileCount ?? 0;

    console.log(
      `  Status: ${String(status).padEnd(18)} | Progress: ${percent}% | Files: ${completed}/${total}`
    );

    const normalized = normalizeStatus(status);
    if (normalized === "complete") {
      console.log();
      console.log("Processing complete.");
      console.log();
      printDownloads(data);
      return data;
    }

    if (normalized === "partially complete") {
      console.log();
      console.log(`Processing partially complete: ${data.errorMessage || "One or more files failed."}`);
      console.log();
      printDownloads(data);
      console.log();
      printFailedFiles(data);
      throw new Error("Batch completed partially.");
    }

    if (normalized === "failed") {
      throw new Error(`Processing failed: ${data.errorMessage || "Unknown error"}`);
    }

    await sleep(POLL_INTERVAL);
  }
}

async function createDeal(apiKey, options) {
  const body = await jsonRequest(apiKey, "POST", "/api/external/v1/deals", {
    expectedStatus: [200, 201],
    body: buildDealPayload(options),
  });
  return body.data || {};
}

async function listDeals(apiKey, options) {
  const body = await jsonRequest(apiKey, "GET", "/api/external/v1/deals", {
    expectedStatus: 200,
    query: {
      page: options.page ?? 1,
      limit: options.limit ?? 20,
      search: options.search,
    },
  });
  return body.data || {};
}

async function getDeal(apiKey, counterId) {
  const body = await jsonRequest(apiKey, "GET", `/api/external/v1/deals/${counterId}`, {
    expectedStatus: 200,
  });
  return body.data || {};
}

async function updateDeal(apiKey, counterId, options) {
  const payload = buildDealPayload(options);
  if (Object.keys(payload).length === 0) {
    throw new Error("Provide at least one deal field to update.");
  }
  const body = await jsonRequest(apiKey, "PUT", `/api/external/v1/deals/${counterId}`, {
    expectedStatus: 200,
    body: payload,
  });
  return body.data || {};
}

async function deleteDeal(apiKey, counterId) {
  const body = await jsonRequest(apiKey, "DELETE", `/api/external/v1/deals/${counterId}`, {
    expectedStatus: 200,
  });
  return body.data || {};
}

function printDealSummary(prefix, deal) {
  console.log(`${prefix}:`);
  console.log(`  Counter ID:     ${deal.counterId ?? "-"}`);
  console.log(`  Name:           ${deal.dealName ?? "-"}`);
  console.log(`  Address:        ${deal.address || "-"}`);
  console.log(`  City:           ${deal.city || "-"}`);
  console.log(`  State:          ${deal.state || "-"}`);
  console.log(`  ZIP:            ${deal.zip || "-"}`);
  console.log(`  Unit Count:     ${deal.unitCount ?? "-"}`);
  console.log(`  Created On:     ${deal.createdOn || "-"}`);
  console.log(`  Last Modified:  ${deal.lastModifiedOn || "-"}`);
}

async function main(argv = process.argv) {
  const { command, options, positionals } = parseCli(argv);
  if (!command || command === "--help" || command === "-h") {
    usage();
    return;
  }

  const apiKey = getApiKey();

  switch (command) {
    case "upload": {
      if (positionals.length === 0) {
        throw new Error("upload requires at least one file.");
      }
      const notification = buildNotification(options.email, options.webhook);
      const dealId =
        options.dealId !== undefined ? Number.parseInt(options.dealId, 10) : undefined;
      const data = await upload(apiKey, positionals, notification, dealId);
      if (options.noPoll) {
        console.log("Skipping status polling (--no-poll).");
        return;
      }
      await poll(apiKey, data.batchId);
      return;
    }
    case "status": {
      const batchId = positionals[0];
      if (!batchId) throw new Error("status requires a batch ID.");
      const data = await statusRequest(apiKey, batchId);
      console.log(`Status:              ${data.status || "unknown"}`);
      console.log(`Percent complete:    ${data.percentComplete ?? 0}%`);
      console.log(`Files completed:     ${data.filesCompleted ?? 0} / ${data.fileCount ?? 0}`);
      console.log(`Files in progress:   ${data.filesInProgress ?? 0}`);
      console.log(`Files failed:        ${data.filesFailed ?? 0}`);
      if (data.errorMessage) {
        console.log(`Batch error:         ${data.errorMessage}`);
      }
      console.log();
      printDownloads(data);
      if (normalizeStatus(data.status) === "partially complete") {
        console.log();
        printFailedFiles(data);
      }
      return;
    }
    case "deals:create": {
      if (!options.dealName) throw new Error("deals:create requires --deal-name.");
      const deal = await createDeal(apiKey, {
        dealName: options.dealName,
        address: options.address,
        city: options.city,
        state: options.state,
        zip: options.zip,
        unitCount: options.unitCount !== undefined ? Number.parseInt(options.unitCount, 10) : undefined,
      });
      printDealSummary("Created deal", deal);
      return;
    }
    case "deals:list": {
      const data = await listDeals(apiKey, {
        page: options.page !== undefined ? Number.parseInt(options.page, 10) : 1,
        limit: options.limit !== undefined ? Number.parseInt(options.limit, 10) : 20,
        search: options.search,
      });
      console.log(JSON.stringify(data, null, 2));
      return;
    }
    case "deals:get": {
      const counterId = positionals[0];
      if (!counterId) throw new Error("deals:get requires COUNTER_ID.");
      const deal = await getDeal(apiKey, counterId);
      printDealSummary("Deal", deal);
      return;
    }
    case "deals:update": {
      const counterId = positionals[0];
      if (!counterId) throw new Error("deals:update requires COUNTER_ID.");
      const deal = await updateDeal(apiKey, counterId, {
        dealName: options.dealName,
        address: options.address,
        city: options.city,
        state: options.state,
        zip: options.zip,
        unitCount: options.unitCount !== undefined ? Number.parseInt(options.unitCount, 10) : undefined,
      });
      printDealSummary("Updated deal", deal);
      return;
    }
    case "deals:delete": {
      const counterId = positionals[0];
      if (!counterId) throw new Error("deals:delete requires COUNTER_ID.");
      const data = await deleteDeal(apiKey, counterId);
      console.log(data.message || `Deal ${counterId} deleted successfully.`);
      return;
    }
    default:
      usage();
      throw new Error(`Unknown command: ${command}`);
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((error) => {
    console.error(`Error: ${error.message}`);
    process.exit(1);
  });
}

export { main };
