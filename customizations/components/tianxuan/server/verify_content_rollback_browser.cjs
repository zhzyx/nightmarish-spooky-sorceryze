/**
 * Run with Node 22.13+, Playwright and Chromium against a disposable HTTPS test deployment.
 * Seed one workspace conversation, confirm its requirement, and publish two distinct accepted
 * selections with an output file through the installed role programs. Supply TX_BROWSER_ORIGIN,
 * TX_BROWSER_CONVERSATION, TX_BROWSER_ENTRY, TX_BROWSER_KEY, TX_BROWSER_NATIVE_DB and TX_BROWSER_PYTHON.
 * The deployment must expose the matching workspace and native database on this host.
 * TX_BROWSER_LOCAL_TLS=1 accepts an ephemeral local test certificate.
 */
const assert = require("node:assert/strict");
const { execFileSync } = require("node:child_process");
const path = require("node:path");
const { createHash } = require("node:crypto");
const { DatabaseSync } = require("node:sqlite");
const { chromium } = require("playwright");

function setting(name) {
  assert(process.env[name], `Missing ${name}`);
  return process.env[name];
}

const origin = new URL(setting("TX_BROWSER_ORIGIN")).origin;
const conversation = setting("TX_BROWSER_CONVERSATION");
const entry = setting("TX_BROWSER_ENTRY");
const historyPath = `/api/v1/native/entry/${encodeURIComponent(entry)}/releases`;
const rollbackPath = historyPath.replace(/releases$/, "rollback");
const hash = (bytes) => createHash("sha256").update(bytes).digest("hex");

function contents(db, event) {
  const composition = db.prepare("SELECT tenant,payload FROM native_compositions WHERE id=?").all(event.candidate);
  assert.equal(composition.length, 1);
  const { tenant, payload } = composition[0];
  assert.equal(hash(payload), event.candidate);
  assert.deepEqual(JSON.parse(payload).modules, event.modules);
  const files = {};
  for (const [module, revision] of Object.entries(event.modules)) {
    const row = db.prepare("SELECT payload FROM native_revisions WHERE tenant=? AND module=? AND id=?")
      .get(tenant, module, revision);
    assert.equal(hash(row.payload), revision);
    for (const [path, digest] of Object.entries(JSON.parse(row.payload).objects)) {
      const blob = db.prepare("SELECT content FROM native_blobs WHERE tenant=? AND digest=?").get(tenant, digest);
      assert.equal(hash(blob.content), digest);
      if (path === "output") files[`${module}/${path}`] = digest;
    }
  }
  assert(Object.keys(files).length > 0, "Expected real fixture output");
  return files;
}

async function run() {
  const browser = await chromium.launch({channel: process.env.TX_BROWSER_CHANNEL || "chrome"});
  const db = new DatabaseSync(setting("TX_BROWSER_NATIVE_DB"), {readOnly: true});
  try {
    const context = await browser.newContext({ ignoreHTTPSErrors: process.env.TX_BROWSER_LOCAL_TLS === "1" });
    const page = await context.newPage();
    await page.goto(origin + "/login");
    await page.locator('input[type="password"]').fill(setting("TX_BROWSER_KEY"));
    await page.locator('form button').first().click();
    await page.waitForURL("**/docs");

    async function openWorkspace(tab) {
      await tab.goto(origin);
      await tab.getByRole("combobox", {name: /对话历史|Conversation history/}).selectOption(conversation);
    }
    async function history() {
      const response = await context.request.get(origin + historyPath);
      assert.equal(response.status(), 200);
      return response.json();
    }
    const before = await history();
    const [a, b] = before.events;
    assert.equal(before.events.length, 2);
    assert(a.accepted && b.accepted);
    assert.equal(before.head, b.selection);
    const original = contents(db, a);
    const second = contents(db, b);
    assert.notDeepEqual(second, original);

    const stale = await context.newPage();
    await Promise.all([openWorkspace(page), openWorkspace(stale)]);
    const versionPicker = (tab) => tab.getByRole("combobox", {name: /历史版本|历史选择|Historical release|Historical selection|Accepted version/i});
    const submit = (tab) => tab.getByRole("button", {name: /回退到|恢复此版本|Rollback to|Restore selected release|Restore version/i});
    await Promise.all([versionPicker(page).selectOption(a.selection), versionPicker(stale).selectOption(a.selection)]);
    async function send(tab) {
      const response = tab.waitForResponse((r) => new URL(r.url()).pathname === rollbackPath && r.request().method() === "POST");
      await submit(tab).click();
      return response;
    }
    const restored = await send(page);
    assert.equal(restored.status(), 200, await restored.text());
    const receipt = await restored.json();
    const conflict = await send(stale);
    assert.equal(conflict.status(), 409);
    const after = await history();
    assert.deepEqual(after.events.slice(0, 2), before.events);
    assert.equal(after.events.length, 3);
    const current = after.events[2];
    assert.equal(current.selection, receipt.selection);
    assert.equal(after.head, current.selection);
    assert(![a.selection, b.selection].includes(current.selection));
    assert.equal(current.previous, b.selection);
    assert.equal(current.restored_from, a.selection);
    assert.equal(current.candidate, a.candidate);
    assert.deepEqual(contents(db, current), original);
    function cli(...args) {
      return JSON.parse(execFileSync(setting("TX_BROWSER_PYTHON"), [
        path.join(__dirname, "tianxuan_cli.py"), "--api", process.env.TX_BROWSER_API || origin,
        "runs", ...args,
      ], { encoding: "utf8", env: { ...process.env, TIANXUAN_TOKEN: setting("TX_BROWSER_KEY") } }));
    }
    assert.deepEqual(cli("releases", entry), after);
    const posted = restored.request().postDataJSON();
    assert.deepEqual(cli("rollback", entry, "--call-id", posted.call_id, "--selection", posted.selection,
      "--expected", posted.expected), receipt);
    assert.deepEqual(cli("releases", entry), after);
    await stale.getByText(/已变化|已更改|已改变|冲突|conflict|changed/i).first().waitFor();
    const progress = await context.request.get(origin + historyPath.replace(/\/releases$/, ""));
    assert.equal(progress.status(), 200);
    const actual = (await progress.json()).progress;
    assert.equal(actual.percent, 100);
    assert.equal(actual.publication.selection, receipt.selection);
    assert.equal(actual.publication.restored_from, a.selection);
    console.log(JSON.stringify({ browser: browser.version(), first: a.selection, second: b.selection,
      restored: current.selection, priorContent: original, secondContent: second, staleStatus: conflict.status(), cliReplayEvents: after.events.length }));
  } finally {
    db.close();
    await browser.close();
  }
}

run().catch((error) => { console.error(error); process.exitCode = 1; });
