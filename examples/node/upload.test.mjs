import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";

import { buildDealPayload, buildNotification, isTerminalStatus, parseCli, upload } from "./upload.mjs";

async function run(name, fn) {
  try {
    await fn();
    console.log(`PASS ${name}`);
  } catch (error) {
    console.error(`FAIL ${name}`);
    console.error(error);
    process.exitCode = 1;
  }
}

await run("buildNotification supports webhook-only", async () => {
  const value = JSON.parse(buildNotification(null, "https://hooks.example.com/callback"));
  assert.deepEqual(value, [{ type: "webhook", entry: "https://hooks.example.com/callback" }]);
});

await run("buildNotification requires at least one target", async () => {
  assert.throws(() => buildNotification(null, null), /Provide at least one notification target/);
});

await run("buildDealPayload omits undefined values", async () => {
  const payload = buildDealPayload({ dealName: "Sunset Plaza", city: "Austin", unitCount: 128 });
  assert.deepEqual(payload, { dealName: "Sunset Plaza", city: "Austin", unitCount: 128 });
});

await run("isTerminalStatus covers partial complete", async () => {
  assert.equal(isTerminalStatus("complete"), true);
  assert.equal(isTerminalStatus("partially complete"), true);
  assert.equal(isTerminalStatus("failed"), true);
  assert.equal(isTerminalStatus("queued"), false);
});

await run("parseCli supports upload flags", async () => {
  const parsed = parseCli([
    "node",
    "upload.mjs",
    "upload",
    "--email",
    "user@example.com",
    "--deal-id",
    "42",
    "--no-poll",
    "rent-roll.xlsx",
  ]);

  assert.equal(parsed.command, "upload");
  assert.equal(parsed.options.email, "user@example.com");
  assert.equal(parsed.options.dealId, "42");
  assert.equal(parsed.options.noPoll, true);
  assert.deepEqual(parsed.positionals, ["rent-roll.xlsx"]);
});

await run("parseCli supports deals subcommand syntax", async () => {
  const parsed = parseCli(["node", "upload.mjs", "deals", "list", "--search", "Sunset"]);
  assert.equal(parsed.command, "deals:list");
  assert.equal(parsed.options.search, "Sunset");
});

await run("upload appends dealId to FormData", async () => {
  const dir = mkdtempSync(join(tmpdir(), "rent-roll-node-test-"));
  const filePath = join(dir, "sample.csv");
  writeFileSync(filePath, "a,b\n1,2\n");

  const originalFetch = global.fetch;
  let capturedForm = null;
  global.fetch = async (_url, init) => {
    capturedForm = init.body;
    return {
      status: 202,
      async json() {
        return { data: { batchId: "batch-1", filesUploaded: 1, trackingUrl: "https://example.com" } };
      },
    };
  };

  try {
    await upload("api-key", [filePath], buildNotification("user@example.com", null), 42);
    assert.ok(capturedForm);
    assert.equal(capturedForm.get("dealId"), "42");
    assert.ok(capturedForm.get("notificationMethod").includes("user@example.com"));
  } finally {
    global.fetch = originalFetch;
    rmSync(dir, { recursive: true, force: true });
  }
});

if (process.exitCode && process.exitCode !== 0) {
  throw new Error("One or more Node example tests failed.");
}
