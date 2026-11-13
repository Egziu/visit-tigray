import { defineConfig, devices } from "@playwright/test";

// E2E runs against a production build (`npm run build` first) so the service worker is active.
// The API must be reachable at API_ORIGIN (default http://localhost:8000) with seed data loaded
// (`python -m app.seed`). See docs/FRONTEND.md.
const PORT = Number(process.env.E2E_PORT ?? 3100);

export default defineConfig({
  testDir: "./e2e",
  timeout: 45_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: "off",
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
      ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH } : {},
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: `npx next start -p ${PORT}`,
    url: `http://localhost:${PORT}/en`,
    reuseExistingServer: true,
    timeout: 60_000,
    env: { API_ORIGIN: process.env.API_ORIGIN ?? "http://localhost:8000" },
  },
});
