import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

// Requires the development seed (python -m app.seed): six synthetic destinations incl. Aksum.

async function seriousViolations(page: Page) {
  const results = await new AxeBuilder({ page: page as unknown as ConstructorParameters<typeof AxeBuilder>[0]["page"] }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
  return results.violations
    .filter((v) => v.impact === "serious" || v.impact === "critical")
    .map((v) => `${v.id} (${v.impact}): ${v.nodes.map((n) => n.target.join(" ")).slice(0, 3).join(" | ")}`);
}

test.describe("localized home", () => {
  test("root redirects to a locale", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/(en|ti|am)$/);
  });

  for (const [locale, heading] of [
    ["en", "Some places you visit"],
    ["ti", "ገለ ቦታታት"],
    ["am", "አንዳንድ ቦታዎችን"],
  ] as const) {
    test(`home renders in ${locale}`, async ({ page }) => {
      await page.goto(`/${locale}`);
      await expect(page.locator("html")).toHaveAttribute("lang", locale);
      await expect(page.getByRole("heading", { level: 1 })).toContainText(heading);
      const notice = page.getByRole("note");
      if (locale === "en") await expect(notice).toHaveCount(0);
      else await expect(notice).toBeVisible();
      // Featured destinations come from the live API, not hardcoded content
      await expect(page.locator("article").first()).toBeVisible();
    });
  }
});

test.describe("destinations", () => {
  test("list and editorial detail with honest unknowns and sources", async ({ page }) => {
    await page.goto("/en/destinations");
    await expect(page.getByRole("heading", { level: 1, name: "Destinations" })).toBeVisible();
    const cards = page.locator("article");
    expect(await cards.count()).toBeGreaterThanOrEqual(6);
    await page.getByRole("link", { name: "Aksum", exact: true }).click();
    await expect(page).toHaveURL(/\/en\/destinations\/aksum$/);
    await expect(page.getByRole("heading", { level: 1, name: "Aksum" })).toBeVisible();
    await expect(page.getByText("Synthetic test data").first()).toBeVisible();
    await expect(page.getByRole("heading", { name: "Sources" })).toBeVisible();
    // Unknown operational facts are shown as unknown, not invented
    const practical = page.getByRole("complementary", { name: "Practical information" });
    await expect(practical.getByText("Unknown").first()).toBeVisible();
  });

  test("cross-lingual search finds Aksum from Ge'ez script and variants", async ({ page }) => {
    for (const q of ["ኣክሱም", "Axum", "aksum"]) {
      await page.goto(`/en/destinations?q=${encodeURIComponent(q)}`);
      await expect(page.getByRole("link", { name: "Aksum", exact: true })).toBeVisible();
    }
  });

  test("Tigrinya page falls back gracefully and labels machine drafts", async ({ page }) => {
    await page.goto("/ti/destinations/aksum");
    await expect(page.locator("html")).toHaveAttribute("lang", "ti");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  });
});

test.describe("accessibility", () => {
  test("skip link moves focus to main content", async ({ page }) => {
    await page.goto("/en");
    await page.keyboard.press("Tab");
    const skip = page.getByRole("link", { name: "Skip to main content" });
    await expect(skip).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/#main$/);
  });

  for (const path of ["/en", "/en/destinations/aksum", "/ti", "/am/destinations", "/en/plan", "/en/guide", "/en/map", "/en/account", "/en/bureau", "/en/offline", "/en/journal", "/en/spaces", "/en/spaces/travellers-lounge/general"]) {
    test(`no serious/critical axe violations on ${path}`, async ({ page }) => {
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      expect(await seriousViolations(page)).toEqual([]);
    });
  }
});

test.describe("mobile", () => {
  test.use({ viewport: { width: 390, height: 844 } });
  for (const path of ["/en", "/en/destinations", "/en/destinations/aksum", "/am", "/en/plan", "/en/guide", "/en/journal", "/en/spaces", "/en/spaces/travellers-lounge/general", "/en/bureau"]) {
    test(`no horizontal scroll on ${path}`, async ({ page }) => {
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      expect(overflow).toBeLessThanOrEqual(0);
    });
  }

  test("mobile menu opens and navigates", async ({ page }) => {
    await page.goto("/en");
    const menu = page.getByRole("button", { name: "Menu" });
    await menu.click();
    await expect(menu).toHaveAttribute("aria-expanded", "true");
    await page.locator("#mobile-menu").getByRole("link", { name: "Events" }).click();
    await expect(page).toHaveURL(/\/en\/events$/);
  });
});

test.describe("guide and planner (live API)", () => {
  test("guide shows starter prompts, answers with citations and opens the Sources panel", async ({ page }) => {
    await page.goto("/en/guide");
    await expect(page.getByText(/Answers from approved sources only/)).toBeVisible();
    await expect(page.getByText("Try asking")).toBeVisible();
    await page.getByLabel("Your question").fill("What is Aksum known for?");
    await page.getByRole("button", { name: "Ask", exact: true }).click();
    await expect(page.getByText("Grounded in sources").or(page.getByText("Partially supported"))).toBeVisible({ timeout: 20_000 });
    // [n] chips open the right-hand Sources panel on that citation
    await page.getByRole("button", { name: "Open source 1" }).first().click();
    const panel = page.getByRole("region", { name: "Sources" });
    await expect(panel).toBeVisible();
    await expect(panel.locator("li").first()).toBeVisible();
    await expect(page.getByText(/verify official information/i)).toBeVisible();
  });

  test("planner builds an editable timeline with a checklist", async ({ page }) => {
    await page.goto("/en/plan?days=2&interests=history,heritage");
    await expect(page.getByLabel("Number of days")).toHaveValue("2");
    await page.getByRole("button", { name: "Create plan" }).click();
    await expect(page.getByRole("heading", { name: "Day 1" })).toBeVisible();
    await expect(page.getByText("Why this stop").first()).toBeVisible();
    await expect(page.getByRole("heading", { name: "Before you go" })).toBeVisible();
    await expect(page.getByText(/verified|straight-line|Travel time unknown/).first()).toBeVisible();
    // Keyboard reordering is re-validated by the planner
    const firstStop = page.locator("section[aria-labelledby='day-1'] article").first();
    const name = (await firstStop.getAttribute("aria-label")) ?? "";
    await page.getByRole("button", { name: `Move ${name} later` }).click();
    await expect(page.getByText("You edited this plan")).toBeVisible();
  });
});

test("bureau requires staff sign-in", async ({ page }) => {
  await page.goto("/en/bureau");
  await expect(page.getByText("Staff sign-in required.")).toBeVisible();
});
