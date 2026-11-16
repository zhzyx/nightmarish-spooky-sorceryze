// Capture the main Tianxuan web pages from a running stack.
//
// Usage:
//   BASE_URL=http://127.0.0.1:8080 node screenshots.mjs
//
// Requires Playwright (`npm install playwright` plus a Chromium install).
import { mkdir } from "node:fs/promises";
import { chromium } from "playwright";

const base = (process.env.BASE_URL ?? "http://127.0.0.1:8080").replace(/\/$/, "");
const pages = [
  ["home", "/"],
  ["docs", "/docs"],
  ["issues", "/issues"],
  ["repos", "/repos"],
  ["requirements", "/requirements"],
  ["search", "/search"],
  ["settings", "/settings"],
  ["login", "/login"],
];

await mkdir("artifacts", { recursive: true });
const token = process.env.TIANXUAN_TOKEN ?? "";
const prefix = token ? "auth-" : "";
const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
if (token) {
  await context.addInitScript(
    ({ key, value }) => window.localStorage.setItem(key, value),
    { key: "tianxuan_token", value: token },
  );
}
const page = await context.newPage();
try {
  for (const [name, path] of pages) {
    await page.goto(`${base}${path}`, { waitUntil: "networkidle", timeout: 30_000 }).catch(() => {});
    await page.waitForTimeout(1200);
    await page.screenshot({ path: `artifacts/${prefix}${name}.png`, fullPage: true });
    console.log(`captured ${path}`);
  }
} finally {
  await browser.close();
}
