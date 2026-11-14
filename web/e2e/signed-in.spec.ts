import { expect, test, type Browser, type BrowserContext } from "@playwright/test";

// Signed-in flows against the real API. The e2e runner creates two synthetic, verified visitors in a
// throwaway database and passes their credentials through E2E_USER_A/B_EMAIL and E2E_PASSWORD.
const A = process.env.E2E_USER_A_EMAIL;
const B = process.env.E2E_USER_B_EMAIL;
const PASSWORD = process.env.E2E_PASSWORD;

test.skip(!A || !B || !PASSWORD, "signed-in e2e needs E2E_USER_A_EMAIL / E2E_USER_B_EMAIL / E2E_PASSWORD");

async function signedIn(browser: Browser, email: string): Promise<BrowserContext> {
  const ctx = await browser.newContext();
  const r = await ctx.request.post("/api/auth/login", { data: { email, password: PASSWORD } });
  expect(r.status()).toBe(200);
  return ctx;
}

test("two members chat live in a Space: delivery and reactions arrive without reload", async ({ browser }) => {
  const a = await signedIn(browser, A!);
  const b = await signedIn(browser, B!);
  const pa = await a.newPage();
  const pb = await b.newPage();
  const url = "/en/spaces/travellers-lounge/trip-planning";
  for (const p of [pa, pb]) {
    await p.goto(url);
    await p.getByRole("button", { name: "Join space" }).first().click();
    await expect(p.getByLabel("Message #trip-planning")).toBeVisible();
  }
  const text = `Selam from the e2e test ${Date.now()}`;
  await pa.getByLabel("Message #trip-planning").fill(text);
  await pa.getByLabel("Message #trip-planning").press("Enter");
  // B never reloads: the message must arrive through the live stream (and the badge must say Live, not polling).
  await expect(pb.getByRole("status").filter({ hasText: /Live/ })).toHaveText(/^\W*Live$/, { timeout: 10_000 });
  const logB = pb.getByRole("log");
  await expect(logB).toContainText(text, { timeout: 15_000 });
  const msgB = logB.getByRole("article").filter({ hasText: text });
  await msgB.hover();
  await msgB.getByRole("button", { name: "Add reaction" }).click();
  await msgB.getByRole("button", { name: "🎉" }).click();
  await expect(msgB.getByRole("button", { name: /🎉 reaction, 1/ })).toBeVisible();
  // ...and A sees the reaction appear live as an update event.
  const msgA = pa.getByRole("log").getByRole("article").filter({ hasText: text });
  await expect(msgA.getByRole("button", { name: /🎉 reaction, 1/ })).toBeVisible({ timeout: 15_000 });
  await a.close();
  await b.close();
});

test("writing a Journal story requires consent and enters human review", async ({ browser }) => {
  const a = await signedIn(browser, A!);
  const p = await a.newPage();
  await p.goto("/en/journal/new");
  await p.getByRole("textbox", { name: "Title", exact: true }).fill("Morning light over the Gheralta cliffs");
  const block = p.locator('textarea[id^="blk-"]').first();
  await block.fill(
    "We started before sunrise and climbed slowly while the sandstone turned from grey to gold. Our guide spoke " +
      "quietly about the paintings inside and asked us to remove our shoes and keep our voices low. It was unforgettable.",
  );
  await p.getByRole("button", { name: "Submit for review" }).click();
  await expect(p.getByText("Please give consent to publish after review.")).toBeVisible();
  await p.getByLabel(/I consent to Visit Tigray publishing this story/).check();
  await p.getByRole("button", { name: "Submit for review" }).click();
  // The author lands on their own story, clearly marked as private until reviewed.
  await expect(p.getByText("Awaiting review — only you can see this story.")).toBeVisible({ timeout: 15_000 });
  // Not public until a moderator approves it.
  const feed = await a.request.get("/api/journal");
  expect((await feed.json()).items).toEqual([]);
  await a.close();
});

test("a signed-in visitor saves a planned itinerary", async ({ browser }) => {
  const b = await signedIn(browser, B!);
  const p = await b.newPage();
  await p.goto("/en/plan?days=2&interests=history");
  const build = p.getByRole("button", { name: /Create|Build|Plan/ }).last();
  if (await build.isVisible()) await build.click();
  await expect(p.getByRole("button", { name: "Save itinerary" })).toBeVisible({ timeout: 15_000 });
  await p.getByRole("button", { name: "Save itinerary" }).click();
  await expect(p.getByText("Itinerary saved.")).toBeVisible({ timeout: 15_000 });
  const mine = await b.request.get("/api/itineraries");
  expect((await mine.json()).length).toBe(1);
  await b.close();
});
