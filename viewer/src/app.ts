// Replay page: world + brain panel + timeline + charts for one recording.
import { WebGLRenderer } from "three";
import { BrainPanel, HeatState, loadBrainPoints } from "./brain";
import { Charts } from "./charts";
import { footer } from "./footer";
import { loadFly } from "./fly";
import { HOW_IT_WORKS, hasBrain, statusBadges } from "./overlay";
import { Playback } from "./playback";
import { loadRecording } from "./recording";
import { World, type Viewport } from "./world";

const ASSETS = "assets/";

function rectViewport(el: HTMLElement, canvas: HTMLCanvasElement): Viewport {
  const c = canvas.getBoundingClientRect();
  const r = el.getBoundingClientRect();
  // WebGL viewports count from the bottom-left corner
  return { x: r.left - c.left, y: c.bottom - r.bottom, width: r.width, height: r.height };
}

export interface ReplaySource {
  title: string;
  url: string; // recording folder
  brain?: boolean; // fallback if the recording has no brain flag
}

export async function startReplay(root: HTMLElement, entry: ReplaySource): Promise<void> {
  // static template only; entry text is inserted below via textContent
  root.innerHTML = `
    <header class="bar">
      <a href="./" class="back">← all runs</a>
      <h1 class="run-title"></h1>
      <div class="badges"></div>
      <button class="how">How it works</button>
    </header>
    <section class="stage">
      <canvas class="gl"></canvas>
      <div class="view world-view"><span class="view-label">fly · drag to orbit · C: follow camera</span></div>
      <div class="view brain-view"><span class="view-label">brain · 139k neurons · spikes glow</span>
        <div class="labels"></div>
        <ul class="legend">
          <li><i style="background:#4fd1ff"></i>looming input (LPLC2, LC4)</li>
          <li><i style="background:#ffd700"></i>giant fiber (escape)</li>
          <li><i style="background:#ff6b9d"></i>steering (DNa01, DNa02)</li>
          <li><i style="background:#4a6fa5"></i>all other neurons</li>
          <li><i style="background:#ffb347"></i>spike</li>
        </ul></div>
    </section>
    <section class="timeline">
      <button class="play">▶</button>
      <input class="scrub" type="range" min="0" step="0.01" value="0" />
      <span class="time">0.00 s</span>
      <select class="speed">
        <option value="0.1">0.1×</option><option value="0.25">0.25×</option>
        <option value="0.5" selected>0.5×</option><option value="1">1×</option>
        <option value="2">2×</option>
      </select>
    </section>
    <section class="charts"></section>
    <aside class="how-panel" hidden></aside>`;
  root.appendChild(footer());
  root.querySelector(".run-title")!.textContent = entry.title;
  if (entry.url.startsWith("api/")) {
    const back = root.querySelector<HTMLAnchorElement>(".back")!;
    back.href = "?editor";
    back.textContent = "← editor";
  }
  const howPanel = root.querySelector<HTMLElement>(".how-panel")!;
  howPanel.innerHTML = HOW_IT_WORKS; // static, trusted text
  root.querySelector(".how")!.addEventListener("click", () => {
    howPanel.hidden = !howPanel.hidden;
  });

  const [rec, fly, points] = await Promise.all([
    loadRecording(entry.url),
    loadFly(`${ASSETS}fly.glb`),
    loadBrainPoints(`${ASSETS}brain_points.bin`, `${ASSETS}brain_points.json`),
  ]);

  const badges = root.querySelector(".badges")!;
  for (const b of statusBadges(rec, entry.brain)) {
    const s = document.createElement("span");
    s.className = b.startsWith("aborted") ? "badge bad" : "badge";
    s.textContent = b;
    badges.appendChild(s);
  }

  const canvas = root.querySelector<HTMLCanvasElement>("canvas.gl")!;
  const renderer = new WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setScissorTest(true);
  const world = new World(renderer, fly);
  world.setRecording(rec);
  const brain = new BrainPanel(points, root.querySelector<HTMLElement>(".labels")!);
  brain.setNoBrain(!hasBrain(rec, entry.brain));
  const heat = new HeatState(points.n);
  const charts = new Charts(root.querySelector<HTMLElement>(".charts")!, rec);

  const playback = new Playback(rec.nFrames, rec.meta.fps || 50);
  const playBtn = root.querySelector<HTMLButtonElement>(".play")!;
  const scrub = root.querySelector<HTMLInputElement>(".scrub")!;
  const timeLabel = root.querySelector<HTMLElement>(".time")!;
  scrub.max = String(playback.last);
  playBtn.addEventListener("click", () => (playback.playing ? playback.pause() : playback.play()));
  scrub.addEventListener("input", () => playback.seek(Number(scrub.value)));
  root.querySelector<HTMLSelectElement>(".speed")!.addEventListener("change", (e) => {
    playback.speed = Number((e.target as HTMLSelectElement).value);
  });
  const worldLabel = root.querySelector<HTMLElement>(".world-view .view-label")!;
  window.addEventListener("keydown", (e) => {
    if (e.key === "c" || e.key === "C") {
      const on = world.toggleFollow();
      worldLabel.textContent = on
        ? "fly · follow camera ON (C to switch off)"
        : "fly · drag to orbit · C: follow camera";
    }
    const tag = (e.target as HTMLElement | null)?.tagName ?? "";
    if (e.key === " " && !["SELECT", "INPUT", "BUTTON"].includes(tag)) {
      e.preventDefault();
      if (playback.playing) playback.pause();
      else playback.play();
    }
  });

  const worldEl = root.querySelector<HTMLElement>(".world-view")!;
  const brainEl = root.querySelector<HTMLElement>(".brain-view")!;
  const stage = root.querySelector<HTMLElement>(".stage")!;
  const resize = () => {
    renderer.setSize(stage.clientWidth, stage.clientHeight, false);
    charts.resize();
  };
  const observer = new ResizeObserver(resize);
  observer.observe(stage);
  observer.observe(root.querySelector<HTMLElement>(".charts")!);
  resize();

  let last = performance.now();
  let first = true;
  const loop = (now: number) => {
    const dt = Math.min((now - last) / 1000, 0.1);
    last = now;
    const f = playback.tick(dt);
    world.update(f);
    brain.update(heat.advanceTo(rec, f));
    const tS = (f + 1) / playback.fps;
    charts.setTime(tS);
    scrub.value = String(f);
    timeLabel.textContent = `${tS.toFixed(2)} s`;
    playBtn.textContent = playback.playing ? "❚❚" : "▶";
    world.render(renderer, rectViewport(worldEl, canvas));
    brain.render(renderer, rectViewport(brainEl, canvas), dt);
    if (first) {
      first = false;
      document.body.dataset.ready = "true";
    }
    requestAnimationFrame(loop);
  };
  requestAnimationFrame(loop);
  const autoplay = new URLSearchParams(location.search).get("autoplay");
  if (autoplay !== "0") playback.play();
}
