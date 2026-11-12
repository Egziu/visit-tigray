// Dev helper: add/replace one message key in all locale files.
// Usage: node scripts/add-message.mjs common.pageNotFound '{"en":"...","ti":"...","am":"..."}'
import { readFileSync, writeFileSync } from "node:fs";

const [key, json] = process.argv.slice(2);
const values = JSON.parse(json);
for (const [locale, value] of Object.entries(values)) {
  const file = new URL(`../messages/${locale}.json`, import.meta.url);
  const data = JSON.parse(readFileSync(file, "utf8"));
  const parts = key.split(".");
  let node = data;
  for (const p of parts.slice(0, -1)) node = node[p] ??= {};
  node[parts.at(-1)] = value;
  writeFileSync(file, JSON.stringify(data, null, 2) + "\n");
}
console.log(`set ${key} in ${Object.keys(values).join(", ")}`);
