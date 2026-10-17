import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
  outputDir: "test-results",
  use: { baseURL: "http://127.0.0.1:4173/", ...devices["Desktop Chrome"], viewport: { width: 1280, height: 800 } },
  webServer: {
    command: "npm run build && npm run preview -- --host 127.0.0.1",
    url: "http://127.0.0.1:4173/",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
