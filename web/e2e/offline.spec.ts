import { expect, test } from "@playwright/test";

test("saved destination and offline page work without a network", async ({ page, context }) => {
  await page.goto("/en/destinations/aksum");
  // Wait for the service worker to control the page (it registers in production builds).
  await page.evaluate(async () => {
    await navigator.serviceWorker.ready;
  });
  await page.reload();
  await expect.poll(() => page.evaluate(() => !!navigator.serviceWorker.controller)).toBe(true);

  await page.getByRole("button", { name: "Save for offline" }).click();
  await expect(page.getByText("Saved for offline use")).toBeVisible();
  // let the SW finish caching the pages it was asked to store
  await page.goto("/en/offline");
  await expect(page.getByRole("heading", { level: 1, name: "Saved for offline use" })).toBeVisible();

  await context.setOffline(true);

  // Previously visited destination page is served from the cache
  await page.goto("/en/destinations/aksum");
  await expect(page.getByRole("heading", { level: 1, name: "Aksum" })).toBeVisible();

  // Offline library lists saved content with its saved date and opens it without network
  await page.goto("/en/offline");
  await expect(page.getByText("You are offline. Showing saved content.").first()).toBeVisible();
  await page.getByRole("button", { name: "Aksum" }).click();
  await expect(page.getByRole("article", { name: "Aksum" })).toBeVisible();

  // An unvisited page falls back to the offline page instead of a browser error
  await page.goto("/en/events");
  await expect(page.getByRole("heading", { level: 1, name: /Saved for offline use|Festivals and events/ })).toBeVisible();

  await context.setOffline(false);
});

test("private pages are never cached by the service worker", async ({ page }) => {
  await page.goto("/en");
  await page.evaluate(async () => {
    await navigator.serviceWorker.ready;
  });
  await page.goto("/en/account");
  await page.goto("/en/bureau");
  const cachedPrivate = await page.evaluate(async () => {
    const out: string[] = [];
    for (const name of await caches.keys()) {
      const c = await caches.open(name);
      for (const req of await c.keys()) {
        const p = new URL(req.url).pathname;
        if (/\/(bureau|account)(\/|$)/.test(p) || p.startsWith("/api/me") || p.startsWith("/api/auth")) out.push(p);
      }
    }
    return out;
  });
  expect(cachedPrivate).toEqual([]);
});
