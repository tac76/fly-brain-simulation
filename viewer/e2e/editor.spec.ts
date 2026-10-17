import { expect, test, type Page } from "@playwright/test";

async function mockApi(page: Page, opts: { invalid?: boolean } = {}) {
  const posted: unknown[] = [];
  let polls = 0;
  await page.route("**/api/health", (r) => r.fulfill({ json: { ok: true, editor: true } }));
  await page.route("**/api/jobs", async (r) => {
    if (r.request().method() === "POST") {
      posted.push(r.request().postDataJSON());
      if (opts.invalid) {
        return r.fulfill({
          status: 422,
          json: { errors: [{ field: "shadow.path", message: "path point below the ground" }] },
        });
      }
      return r.fulfill({ status: 202, json: { id: "job1" } });
    }
    return r.fulfill({ json: [] });
  });
  await page.route("**/api/jobs/job1", (r) => {
    polls += 1;
    const done = polls > 1;
    return r.fulfill({
      json: {
        id: "job1", state: done ? "complete" : "running", progress: done ? 1 : 0.4,
        position: 0, brain: true, reason: null, error: null, duration_s: 3, created: 0,
      },
    });
  });
  return posted;
}

test("editor posts the scene and links to the replay", async ({ page }) => {
  const posted = await mockApi(page);
  await page.goto("./?editor");
  await expect(page.locator("body")).toHaveAttribute("data-ready", "true");
  await page.locator('[data-preset="right"]').click();
  await page.locator('input[name="duration"]').fill("2");
  await page.locator(".apply").click();
  const watch = page.locator(".watch");
  await expect(watch).toBeVisible({ timeout: 10_000 });
  expect(await watch.getAttribute("href")).toContain("rec=api%2Frecordings%2Fjob1%2F");
  const body = posted[0] as { scene: Record<string, unknown>; brain: boolean };
  expect(body.brain).toBe(true);
  expect(body.scene).toMatchObject({
    duration_s: 2,
    fly: { pos: [0, 0], heading_deg: 0 },
    shadow: { size_mm: 8, speed_mm_s: 100, path: [[0, -30, 6], [0, -2, 2]] },
  });
});

test("editor shows field errors from the server", async ({ page }) => {
  await mockApi(page, { invalid: true });
  await page.goto("./?editor");
  await page.locator(".apply").click();
  await expect(page.locator(".errors")).toContainText("shadow.path: path point below the ground");
});

test("static hosting: no editor card, editor route explains the server is needed", async ({ page }) => {
  await page.goto("./");
  await expect(page.locator("body")).toHaveAttribute("data-ready", "true");
  await expect(page.locator(".editor-card")).toHaveCount(0);
  await page.goto("./?editor");
  await expect(page.locator(".error")).toContainText("flybrain serve");
});
