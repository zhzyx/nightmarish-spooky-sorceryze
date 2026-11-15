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
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
try {
  for (const [name, path] of pages) {
    await page.goto(`${base}${path}`, { waitUntil: "networkidle", timeout: 30_000 }).catch(() => {});
    await page.waitForTimeout(500);
    await page.screenshot({ path: `artifacts/${name}.png`, fullPage: true });
    console.log(`captured ${path}`);
  }
} finally {
  await browser.close();
}
