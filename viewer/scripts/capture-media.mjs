// Capture gallery thumbnails and the README GIF frames from the built viewer.
//   cd viewer && npm run build && node scripts/capture-media.mjs
// Starts `vite preview`, renders with headless Chromium, then encodes the GIF with ffmpeg.
import { spawn, execFileSync } from "node:child_process";
import { mkdirSync, readFileSync, rmSync } from "node:fs";
import { chromium } from "@playwright/test";

const BASE = "http://127.0.0.1:4174/";
const GIF_RUN = "loom_left";
const GIF_FRAMES = [0, 70]; // frame range of the recording (50 fps)
const GIF_OUT = "../docs/media/escape.gif";

const preview = spawn("npx", ["vite", "preview", "--port", "4174", "--host", "127.0.0.1"], {
  stdio: "ignore",
});
await new Promise((r) => setTimeout(r, 2500));

const browser = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader"] });
try {
  const page = await browser.newPage({ viewport: { width: 1200, height: 640 } });
  const seek = async (frame) => {
    await page.locator(".scrub").evaluate((el, f) => {
      el.value = String(f);
      el.dispatchEvent(new Event("input"));
    }, frame);
  };
  const open = async (id) => {
    await page.goto(`${BASE}?run=${id}&autoplay=0`);
    await page.waitForSelector("body[data-ready=true]", { timeout: 60_000 });
    await page.waitForTimeout(1500);
  };

  const entries = JSON.parse(readFileSync("public/gallery/index.json", "utf8"));
  for (const e of entries) {
    await open(e.id);
    await seek(14);
    await page.waitForTimeout(2500);
    const box = await page.locator(".stage").boundingBox();
    await page.screenshot({
      path: `public/gallery/${e.path}thumb.jpg`,
      type: "jpeg",
      quality: 80,
      clip: box,
    });
    console.log("thumb", e.id);
  }

  const dir = "../out/gif-frames";
  rmSync(dir, { recursive: true, force: true });
  mkdirSync(dir, { recursive: true });
  await open(GIF_RUN);
  const box = await page.locator(".stage").boundingBox();
  let n = 0;
  for (let f = GIF_FRAMES[0]; f <= GIF_FRAMES[1]; f++) {
    await seek(f);
    await page.waitForTimeout(700); // software rendering is slow
    await page.screenshot({ path: `${dir}/f${String(n++).padStart(4, "0")}.png`, clip: box });
  }
  console.log("frames", n);
  mkdirSync("../docs/media", { recursive: true });
  execFileSync("ffmpeg", [
    "-loglevel", "error", "-y", "-framerate", "20", "-i", `${dir}/f%04d.png`,
    "-vf", "scale=800:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=sierra2_4a",
    GIF_OUT,
  ]);
  console.log("gif", GIF_OUT);
} finally {
  await browser.close();
  preview.kill();
}
