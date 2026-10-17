import { readFile } from "node:fs/promises";
import { expect, test, type Page } from "@playwright/test";

function collectErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (m) => {
    if (m.type() === "error") errors.push(m.text());
  });
  page.on("pageerror", (e) => errors.push(String(e)));
  return errors;
}

async function ready(page: Page) {
  await expect(page.locator("body")).toHaveAttribute("data-ready", "true", { timeout: 30_000 });
}

test("gallery lists the runs", async ({ page }) => {
  const errors = collectErrors(page);
  await page.goto("./");
  await ready(page);
  await expect(page.locator(".card")).toHaveCount(3);
  await expect(page.locator(".card").first()).toContainText("Threat from the left");
  expect(errors).toEqual([]);
});

test("replay renders fly, threat and brain without errors", async ({ page }) => {
  const errors = collectErrors(page);
  await page.goto("./?run=loom_left&autoplay=0");
  await ready(page);
  await page.locator(".scrub").evaluate((el: HTMLInputElement) => {
    el.value = "12";
    el.dispatchEvent(new Event("input"));
  });
  await page.waitForTimeout(1000);
  await expect(page.locator(".chart")).toHaveCount(3);
  await expect(page.locator(".brain-label").first()).toBeVisible();
  await page.screenshot({ path: "test-results/replay.png" });
  expect(errors).toEqual([]);
});

test("unknown run shows an error instead of a blank page", async ({ page }) => {
  await page.goto("./?run=missing");
  await expect(page.locator(".error")).toContainText('no run called "missing"');
});

test("aborted run shows a badge and still replays", async ({ page }) => {
  const fixture = new URL("./fixtures/aborted/", import.meta.url);
  await page.route("**/gallery/index.json", async (route) => {
    const res = await route.fetch();
    const list = await res.json();
    list.push({ id: "aborted", title: "Aborted", description: "", path: "aborted/", brain: false });
    await route.fulfill({ json: list });
  });
  await page.route("**/gallery/aborted/*", async (route) => {
    const name = route.request().url().split("/").pop()!;
    await route.fulfill({ body: await readFile(new URL(name, fixture)) });
  });
  await page.goto("./?run=aborted&autoplay=0");
  await ready(page);
  await expect(page.locator(".badge.bad")).toContainText("aborted: out_of_arena");
  await expect(page.locator(".badge", { hasText: "no brain in this run" })).toBeVisible();
});

test("narrow screens stack the panels", async ({ page }) => {
  await page.setViewportSize({ width: 600, height: 900 });
  await page.goto("./?run=loom_left&autoplay=0");
  await ready(page);
  const world = await page.locator(".world-view").boundingBox();
  const brain = await page.locator(".brain-view").boundingBox();
  expect(brain!.y).toBeGreaterThanOrEqual(world!.y + world!.height - 1);
  await page.screenshot({ path: "test-results/narrow.png", fullPage: true });
});
