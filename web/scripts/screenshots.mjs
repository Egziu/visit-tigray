// Capture documentation screenshots (deviceScaleFactor 2) of a running build.
// Usage: BASE=http://localhost:3100 ADMIN_EMAIL=... ADMIN_PASSWORD=... node scripts/screenshots.mjs ../docs/screenshots
// The admin account must be a development seed account (python -m app.seed --dev-admin ...).
import { createHmac } from "node:crypto";
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://localhost:3100";
const OUT = process.argv[2] ?? "../docs/screenshots";
mkdirSync(OUT, { recursive: true });

function base32Decode(s) {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  let bits = "";
  for (const c of s.replace(/=+$/, "").toUpperCase()) bits += alphabet.indexOf(c).toString(2).padStart(5, "0");
  const bytes = [];
  for (let i = 0; i + 8 <= bits.length; i += 8) bytes.push(parseInt(bits.slice(i, i + 8), 2));
  return Buffer.from(bytes);
}

/** RFC 6238 TOTP (SHA-1, 30 s, 6 digits). */
function totp(secret, now = Date.now()) {
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(Math.floor(now / 30000)));
  const h = createHmac("sha1", base32Decode(secret)).update(counter).digest();
  const o = h[h.length - 1] & 0xf;
  const code = ((h.readUInt32BE(o) & 0x7fffffff) % 1_000_000).toString();
  return code.padStart(6, "0");
}

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
const page = await ctx.newPage();

async function shot(path, file, prepare) {
  await page.goto(`${BASE}${path}`, { waitUntil: "networkidle" });
  if (prepare) await prepare();
  await page.waitForTimeout(900); // let entrance animations settle
  await page.screenshot({ path: `${OUT}/${file}`, fullPage: false });
  console.log("wrote", file);
}

await shot("/en", "home.png");
await shot("/en/destinations/aksum", "destination-detail.png");
await shot("/en/guide", "guide.png", async () => {
  await page.getByLabel("Your question").fill("What is Aksum known for?");
  await page.getByRole("button", { name: "Ask" }).click();
  await page.locator("summary", { hasText: "Sources" }).waitFor();
});

if (process.env.ADMIN_EMAIL && process.env.ADMIN_PASSWORD) {
  const api = page.request;
  const login = await api.post(`${BASE}/api/auth/login`, { data: { email: process.env.ADMIN_EMAIL, password: process.env.ADMIN_PASSWORD } });
  const body = await login.json();
  const csrf = body.user.csrf_token;
  let secret = process.env.ADMIN_TOTP_SECRET;
  if (!secret) {
    const setup = await (await api.post(`${BASE}/api/auth/mfa/setup`, { headers: { "x-csrf-token": csrf } })).json();
    secret = setup.secret;
    await api.post(`${BASE}/api/auth/mfa/enable`, { headers: { "x-csrf-token": csrf }, data: { code: totp(secret) } });
    console.log("enrolled TOTP for dev admin (secret printed for reuse):", secret);
  } else {
    await api.post(`${BASE}/api/auth/mfa/verify`, { headers: { "x-csrf-token": csrf }, data: { code: totp(secret) } });
  }
  await shot("/en/bureau", "bureau-dashboard.png", async () => {
    await page.getByRole("heading", { level: 1 }).waitFor();
  });
  await shot("/en/bureau/destinations", "bureau-destinations.png");
}

await browser.close();
