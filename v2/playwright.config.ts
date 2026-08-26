import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e/specs",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: "http://127.0.0.1:3011",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    permissions: ["camera", "microphone", "geolocation"],
    geolocation: { latitude: -25.998, longitude: 28.126 },
    launchOptions: {
      args: [
        "--use-fake-ui-for-media-stream",
        "--use-fake-device-for-media-stream",
      ],
    },
  },
  webServer: [
    {
      command: "../.venv/bin/python e2e/start-test-backend.py",
      url: "http://127.0.0.1:8011/docs",
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command:
        "BACKEND_URL=http://127.0.0.1:8011 npm run dev -- --hostname 127.0.0.1 --port 3011",
      url: "http://127.0.0.1:3011",
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
