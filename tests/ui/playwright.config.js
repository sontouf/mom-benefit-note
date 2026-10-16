// 실제 브라우저 UI 테스트. 먼저 `python run.py build` 로 public/ 을 만든 뒤 실행한다.
//   npm test                         # 모든 환경
//   npx playwright test --project=desktop-chrome
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  timeout: 30_000,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: { baseURL: "http://localhost:8765", trace: "retain-on-failure", screenshot: "only-on-failure" },
  webServer: {
    command: "python3 -m http.server -d ../../public 8765",
    url: "http://localhost:8765/",
    reuseExistingServer: true,
  },
  projects: [
    { name: "desktop-chrome", use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 900 } } },
    { name: "android-chrome", use: { ...devices["Pixel 7"] } },
    { name: "iphone-safari", use: { ...devices["iPhone 14"] } },
  ],
});
