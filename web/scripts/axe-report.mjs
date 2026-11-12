// Dev helper: print detailed axe findings (colours, targets) for a URL.
// Usage: node scripts/axe-report.mjs http://localhost:3100/en
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const { AxeBuilder } = require("@axe-core/playwright");

const url = process.argv[2] ?? "http://localhost:3100/en";
const browser = await chromium.launch();
const page = await (await browser.newContext()).newPage();
await page.goto(url, { waitUntil: "networkidle" });
await page.waitForTimeout(1200); // let entrance animations finish
const r = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
for (const v of r.violations) {
  console.log(`${v.id} [${v.impact}] ${v.help}`);
  for (const n of v.nodes.slice(0, 6)) console.log("   ", n.target.join(" "), "|", (n.any[0]?.message ?? n.failureSummary ?? "").slice(0, 160));
}
console.log(`violations: ${r.violations.length}`);
await browser.close();
