import { expect, test } from "@playwright/test";

// Requires the development seed (python -m app.seed), which creates three spaces with no messages
// and no journal stories. Signed-in posting flows are covered by backend tests (tests/test_social.py).

test("header shows the Visit Tigray logo and the social nav", async ({ page }) => {
  await page.goto("/en");
  const header = page.getByRole("banner");
  // Two sizes of the lockup exist (desktop and mobile); exactly one is shown per breakpoint.
  await expect(header.getByRole("img", { name: "Visit Tigray" }).filter({ visible: true })).toHaveCount(1);
  const nav = header.getByRole("navigation", { name: "Primary" });
  for (const label of ["Discover", "Guide", "Plan", "Journal", "Spaces", "Memories", "Events"]) {
    // "Guide" is labelled "AI Guide" on purpose: the AI is disclosed in the nav itself.
    await expect(nav.getByRole("link", { name: new RegExp(`(^|AI )${label}$`) }).first()).toBeVisible();
  }
  await nav.getByRole("button", { name: "More" }).click();
  await expect(nav.getByRole("link", { name: "Map" })).toBeVisible();
  await page.keyboard.press("Escape");
});

test("journal feed renders with tabs, filters and the review notice", async ({ page }) => {
  await page.goto("/en/journal");
  await expect(page.getByRole("heading", { level: 1, name: "Journal" })).toBeVisible();
  const tabs = page.getByRole("group", { name: "Journal feed" });
  await expect(tabs.getByRole("button", { name: "Latest" })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByLabel("Destination")).toBeVisible();
  // Seed has no stories: an honest empty state, not fake content
  await expect(page.getByText(/No stories/).first()).toBeVisible();
  await tabs.getByRole("button", { name: "Following" }).click();
  await expect(page.getByText(/Sign in to see stories/)).toBeVisible();
});

test("spaces directory and a channel work signed out", async ({ page }) => {
  await page.goto("/en/spaces");
  await expect(page.getByRole("heading", { level: 1, name: "Spaces" })).toBeVisible();
  await expect(page.getByRole("note").filter({ hasText: "Community guidelines" })).toBeVisible();
  await page.getByRole("button", { name: "I understand" }).click();
  await expect(page.getByText("Community guidelines")).toHaveCount(0);

  await page.goto("/en/spaces/travellers-lounge/general");
  await expect(page.getByRole("heading", { name: "general" })).toBeVisible();
  const log = page.getByRole("log");
  await expect(log).toHaveAttribute("aria-live", "polite");
  await expect(page.getByText("No messages yet")).toBeVisible();
  await expect(page.getByText(/to join the conversation/)).toBeVisible();
  // Live status settles on SSE or the polling fallback
  await expect(page.getByText(/Live|Updating every few seconds/)).toBeVisible({ timeout: 15_000 });
  // The guidelines dismissal persisted in localStorage
  await expect(page.getByText("Community guidelines")).toHaveCount(0);

  await page.goto("/en/spaces/travellers-lounge/welcome");
  await expect(page.getByRole("heading", { name: "welcome" })).toBeVisible();
});

test.describe("mobile spaces", () => {
  test.use({ viewport: { width: 390, height: 844 } });
  test("single-pane navigation with a back button", async ({ page }) => {
    await page.goto("/en/spaces/travellers-lounge/general");
    await expect(page.getByRole("log")).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Spaces" })).toBeHidden();
    await page.getByRole("link", { name: "Back to channels" }).click();
    await expect(page).toHaveURL(/\/en\/spaces\/travellers-lounge$/);
    await expect(page.getByRole("link", { name: /general/ })).toBeVisible();
  });
});

test("destination page opens the mini guide drawer", async ({ page }) => {
  await page.goto("/en/destinations/aksum");
  await page.getByRole("button", { name: /Ask the guide about Aksum/ }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(dialog.getByLabel("Your question")).toBeVisible();
});
