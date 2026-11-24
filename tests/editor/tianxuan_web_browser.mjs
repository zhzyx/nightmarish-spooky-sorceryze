import assert from "node:assert/strict";
import { readFile, writeFile, rename, unlink } from "node:fs/promises";
import { spawn } from "node:child_process";

// Drive only the disposable headless browser, through its documented DevTools protocol.
const checks = [], errors = [], network = [];
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
async function until(action, description, seconds = 60) {
  const deadline = Date.now() + seconds * 1000;
  while (Date.now() < deadline) {
    if (await action()) { checks.push(description); return; }
    await pause(100);
  }
  throw new Error(description);
}
async function state(stage) {
  let found;
  await until(async () => {
    try { found = JSON.parse(await readFile(process.env.TX_STATE, "utf8")); }
    catch { return false; }
    return found.stage === stage;
  }, `Native counterpart reached ${stage}`);
  return found;
}
async function command(stage) {
  await writeFile(process.env.TX_COMMAND + ".tmp", JSON.stringify({ stage }));
  await rename(process.env.TX_COMMAND + ".tmp", process.env.TX_COMMAND);
}
const chrome = spawn(process.env.TX_CHROME, ["--headless=new", "--remote-debugging-port=0", "--user-data-dir=" + process.env.TX_CHROME_PROFILE,
  "--no-first-run", "--no-default-browser-check", "--disable-background-networking", "--disable-component-update", "--disable-sync", "--no-proxy-server", "--ignore-certificate-errors",
  "--disable-gpu", "--password-store=basic", "--use-mock-keychain", "about:blank"], { stdio: ["ignore", "ignore", "pipe"] });
let socket, endpoint = "", chromeLog = "", sequence = 0, session;
const pending = new Map();
chrome.stderr.on("data", chunk => {
  chromeLog = (chromeLog + chunk.toString()).slice(-10000);
  endpoint = chromeLog.match(/DevTools listening on (ws:\/\/[^\s]+)/)?.[1] ?? endpoint;
});
function call(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ++sequence;
    const timeout = setTimeout(() => { pending.delete(id); reject(new Error(`CDP timeout: ${method}`)); }, 60000);
    pending.set(id, { resolve: value => { clearTimeout(timeout); resolve(value); }, reject: error => { clearTimeout(timeout); reject(error); } });
    socket.send(JSON.stringify({ id, method, params, ...(session ? { sessionId: session } : {}) }));
  });
}
async function evaluate(expression) {
  const value = await call("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true, userGesture: true });
  if (value.exceptionDetails) throw new Error(value.exceptionDetails.text);
  return value.result.value;
}
async function waitDOM(expression, description) {
  await until(async () => { try { return await evaluate(expression); } catch { return false; } }, description);
}
async function fill(selector, value) {
  await waitDOM(`Boolean(document.querySelector(${JSON.stringify(selector)}))`, `Input available: ${selector}`);
  await evaluate(`(() => { const element = document.querySelector(${JSON.stringify(selector)}); const prototype = element instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype; Object.getOwnPropertyDescriptor(prototype, 'value').set.call(element, ${JSON.stringify(value)}); element.dispatchEvent(new Event('input', {bubbles:true})); element.dispatchEvent(new Event('change', {bubbles:true})); })()`);
}
async function click(selector) {
  await waitDOM(`Boolean(document.querySelector(${JSON.stringify(selector)}) && !document.querySelector(${JSON.stringify(selector)}).disabled)`, `Action enabled: ${selector}`);
  await evaluate(`document.querySelector(${JSON.stringify(selector)}).click()`);
}
async function go(path) {
  await call("Page.navigate", { url: process.env.TX_WEB + path });
  await waitDOM(`location.pathname === ${JSON.stringify(path)} && document.readyState === 'complete'`, `Web page loaded: ${path}`);
}
try {
  await until(() => Boolean(endpoint), "Isolated headless Chrome starts", 20);
  socket = new WebSocket(endpoint);
  await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject; });
  socket.onmessage = ({ data }) => {
    const message = JSON.parse(data);
    if (message.id && pending.has(message.id)) {
      const item = pending.get(message.id); pending.delete(message.id);
      if (message.error) item.reject(new Error(message.error.message)); else item.resolve(message.result);
    } else if (message.method === "Runtime.exceptionThrown") errors.push(message.params.exceptionDetails.text);
    else if (message.method === "Network.requestWillBeSent") network.push({url: message.params.request.url.split("?")[0], event: "request"});
    else if (message.method === "Network.loadingFailed") network.push({event: "failed", reason: message.params.errorText});
  };
  const browserVersion = await call("Browser.getVersion");
  const { targetId } = await call("Target.createTarget", { url: "about:blank" });
  session = (await call("Target.attachToTarget", { targetId, flatten: true })).sessionId;
  await call("Page.enable"); await call("Runtime.enable"); await call("Network.enable");
  await call("Security.setIgnoreCertificateErrors", { ignore: true });
  assert.equal(await evaluate("1 + 1"), 2);
  await go("/login");
  await fill('input[type="email"]', "second@example.invalid");
  await fill('input[type="password"]', process.env.TX_PASSWORD);
  await click("form.sign-in-form button.btn-primary");
  await waitDOM("location.pathname === '/docs'", "Web login authenticates a separate editor account with its secure session cookie");
  const native = await state("native_saved");
  await go("/docs/" + native.document);
  const body = () => evaluate("document.querySelector('textarea.markdown-textarea')?.value");
  const save = () => click(".doc-editor-actions button.btn-primary");
  const readServer = () => evaluate(`fetch('/api/v1/docs/${native.document}').then(async response => { if (!response.ok) throw new Error('Document read: '+response.status); return response.json(); })`);
  await until(async () => await body() === "原生段落 A\n\n共同段落 B", "Web reads the exact native-created content");
  await fill("textarea.markdown-textarea", "原生段落 A\n\nWeb 修改 B"); await save();
  await until(async () => (await readServer()).body_md === "原生段落 A\n\nWeb 修改 B", "Web controls persist their edit through the actual service");
  await command("web_saved"); await state("web_observed");
  await writeFile(process.env.TX_NETWORK_DOWN, "offline"); await command("native_offline");
  await state("native_offline_retained");
  assert.equal((await readServer()).body_md, "原生段落 A\n\nWeb 修改 B");
  checks.push("Native transport outage leaves the last confirmed server content intact");
  await unlink(process.env.TX_NETWORK_DOWN); await command("native_online"); await state("native_resynced");
  await until(async () => await body() === "原生离线修改 A\n\nWeb 修改 B", "Web observes the native reconnect save without reloading");
  await call("Network.emulateNetworkConditions", { offline: true, latency: 0, downloadThroughput: -1, uploadThroughput: -1 });
  await fill("textarea.markdown-textarea", "原生离线修改 A\n\nWeb 离线修改 B"); await save();
  await waitDOM("Object.keys(localStorage).some(key => localStorage.getItem(key)?.includes('Web 离线修改 B'))", "Web persists its offline draft locally");
  await call("Network.emulateNetworkConditions", { offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1 });
  await save();
  await until(async () => (await readServer()).body_md === "原生离线修改 A\n\nWeb 离线修改 B", "Web saves its recovered offline draft");
  await command("web_offline_saved"); await state("web_resynced");
  await fill("textarea.markdown-textarea", "Web 待确认修改 A\n\nWeb 离线修改 B");
  await command("web_conflicting_draft"); await state("native_conflicting_saved"); await save();
  await waitDOM("document.querySelector('section.restore-banner[role=alert]')?.textContent.includes('远端已保存版本')", "Web exposes the overlapping native edit as a conflict");
  assert.equal(await body(), "Web 待确认修改 A\n\nWeb 离线修改 B");
  assert.equal((await readServer()).body_md, "原生最终修改 A\n\nWeb 离线修改 B");
  checks.push("Conflict retains both the Web draft and native server version");
  await fill("textarea.markdown-textarea", "双方确认的最终内容 A\n\nWeb 离线修改 B");
  await click("section.restore-banner[role=alert] button"); await save();
  await until(async () => (await readServer()).body_md === "双方确认的最终内容 A\n\nWeb 离线修改 B", "Explicit Web resolution creates a new shared version");
  await command("web_resolved"); await state("complete");
  assert.deepEqual(errors, []);
  console.log(JSON.stringify({ passed: true, checks, browser_version: browserVersion.product, page_errors: errors }));
} catch (error) {
  console.error(JSON.stringify({chrome: chromeLog.slice(-4000), network: network.slice(-12)}));
  throw error;
} finally {
  for (const item of pending.values()) item.reject(new Error("Browser test ended"));
  pending.clear();
  socket?.close();
  chrome.kill("SIGTERM");
  await Promise.race([new Promise(resolve => chrome.once("exit", resolve)), pause(5000)]);
  if (chrome.exitCode === null) chrome.kill("SIGKILL");
}
