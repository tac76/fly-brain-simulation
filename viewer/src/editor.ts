// Scene editor (local mode only): set up a threat, press Apply, watch the replay.
import {
  ARENA_RADIUS_MM,
  canvasToWorld,
  estimateSeconds,
  MAX_WAYPOINTS,
  pathLength,
  preset,
  sceneFromState,
  worldToCanvas,
  type EditorState,
  type View,
} from "./editorGeometry";

interface Job {
  id: string;
  state: "queued" | "running" | "complete" | "aborted" | "error";
  progress: number;
  position: number;
  brain: boolean;
  reason: string | null;
  error: string | null;
  duration_s: number;
  created: number;
}

export function replayUrl(job: Pick<Job, "id" | "brain">, title: string): string {
  const q = new URLSearchParams({
    rec: `api/recordings/${job.id}/`,
    title,
    brain: job.brain ? "1" : "0",
  });
  return `?${q.toString()}`;
}

const HANDLE_MM = 6;

export function startEditor(root: HTMLElement): void {
  // static template; all dynamic values are set via textContent / value below
  root.innerHTML = `
    <header class="bar">
      <a href="./" class="back">← gallery</a>
      <h1>Scene editor</h1>
      <span class="hint">drag the fly · drag the arrow tip to turn it · click to add threat waypoints ·
      right-click a waypoint to remove it</span>
    </header>
    <main class="editor">
      <div class="arena-wrap"><canvas class="arena"></canvas></div>
      <form class="controls" novalidate>
        <fieldset><legend>Presets (fly at the centre, facing right)</legend>
          <button type="button" data-preset="left">threat from the left</button>
          <button type="button" data-preset="right">from the right</button>
          <button type="button" data-preset="front">head-on</button>
        </fieldset>
        <fieldset><legend>Threat</legend>
          <label>diameter <input name="size" type="number" min="1" max="30" step="any"> mm</label>
          <label>speed <input name="speed" type="number" min="1" max="400" step="any"> mm/s</label>
          <div class="waypoints"></div>
        </fieldset>
        <fieldset><legend>Run</legend>
          <label>duration <input name="duration" type="number" min="0.02" max="10" step="any"> s</label>
          <label>seed <input name="seed" type="number" min="0" step="1"></label>
          <label class="check"><input name="brain" type="checkbox"> brain model drives the fly</label>
        </fieldset>
        <p class="estimate"></p>
        <button type="submit" class="apply">Apply</button>
        <ul class="errors"></ul>
        <div class="job" hidden>
          <div class="job-text"></div>
          <div class="progress"><div class="progress-bar"></div></div>
          <a class="watch" hidden>Watch replay →</a>
        </div>
      </form>
    </main>
    <section class="recent"><h2>Recent runs</h2><ul></ul></section>`;

  const state: EditorState = {
    fly: { x: 0, y: 0, headingDeg: 0 },
    waypoints: preset("left"),
    sizeMm: 8,
    speedMmS: 100,
    durationS: 3,
    seed: 1,
    brain: true,
  };

  const canvas = root.querySelector<HTMLCanvasElement>("canvas.arena")!;
  const ctx = canvas.getContext("2d")!;
  const form = root.querySelector<HTMLFormElement>("form.controls")!;
  const input = (n: string) => form.querySelector<HTMLInputElement>(`[name="${n}"]`)!;
  const view: View = { width: 600, height: 600, mmPerPx: 0.2 };

  function syncInputs(): void {
    input("size").value = String(state.sizeMm);
    input("speed").value = String(state.speedMmS);
    input("duration").value = String(state.durationS);
    input("seed").value = String(state.seed);
    input("brain").checked = state.brain;
  }

  function renderWaypoints(): void {
    const box = form.querySelector<HTMLElement>(".waypoints")!;
    box.replaceChildren();
    state.waypoints.forEach((w, i) => {
      const row = document.createElement("div");
      row.className = "wp";
      const name = document.createElement("span");
      name.textContent = `${i + 1}: (${w.x.toFixed(1)}, ${w.y.toFixed(1)}) mm, height`;
      const z = document.createElement("input");
      z.type = "range";
      z.min = "0.5";
      z.max = "20";
      z.step = "0.5";
      z.value = String(w.z);
      const zl = document.createElement("span");
      zl.textContent = `${w.z} mm`;
      z.addEventListener("input", () => {
        w.z = Number(z.value);
        zl.textContent = `${w.z} mm`;
        draw();
      });
      const del = document.createElement("button");
      del.type = "button";
      del.textContent = "×";
      del.title = "remove waypoint";
      del.addEventListener("click", () => {
        state.waypoints.splice(i, 1);
        update();
      });
      row.append(name, z, zl, del);
      box.appendChild(row);
    });
    if (state.waypoints.length < 2) {
      const p = document.createElement("p");
      p.className = "small";
      p.textContent = "Click the arena to add waypoints (2–4).";
      box.appendChild(p);
    }
  }

  function updateEstimate(): void {
    const path = state.waypoints.map((w) => [w.x, w.y, w.z] as [number, number, number]);
    const len = pathLength(path);
    const secs = estimateSeconds(state.durationS, state.brain);
    const arrive = len / Math.max(state.speedMmS, 1e-6);
    form.querySelector(".estimate")!.textContent =
      `Path ${len.toFixed(0)} mm, threat arrives after ${arrive.toFixed(2)} s. ` +
      `Simulation takes about ${secs < 90 ? `${secs} s` : `${Math.round(secs / 60)} min`} on the server.`;
  }

  function resize(): void {
    const wrap = canvas.parentElement!;
    const size = Math.max(Math.min(wrap.clientWidth, window.innerHeight - 140), 280);
    const dpr = window.devicePixelRatio || 1;
    canvas.style.width = canvas.style.height = `${size}px`;
    canvas.width = canvas.height = Math.round(size * dpr);
    view.width = view.height = size;
    view.mmPerPx = (2 * (ARENA_RADIUS_MM + 4)) / size;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    draw();
  }

  const toPx = (x: number, y: number) => worldToCanvas([x, y], view);
  const handle = () => {
    const a = (state.fly.headingDeg * Math.PI) / 180;
    return { x: state.fly.x + Math.cos(a) * HANDLE_MM, y: state.fly.y + Math.sin(a) * HANDLE_MM };
  };

  function draw(): void {
    const { width: w, height: h } = view;
    ctx.clearRect(0, 0, w, h);
    const [cx, cy] = toPx(0, 0);
    const rPx = ARENA_RADIUS_MM / view.mmPerPx;
    ctx.fillStyle = "#3b2a1c";
    ctx.beginPath();
    ctx.arc(cx, cy, rPx, 0, Math.PI * 2);
    ctx.fill();
    ctx.save();
    ctx.clip();
    for (let mm = -ARENA_RADIUS_MM; mm <= ARENA_RADIUS_MM; mm += 5) {
      ctx.strokeStyle = mm % 10 === 0 ? "rgba(255,255,255,0.12)" : "rgba(255,255,255,0.05)";
      const [gx] = toPx(mm, 0);
      const [, gy] = toPx(0, mm);
      ctx.beginPath();
      ctx.moveTo(gx, 0);
      ctx.lineTo(gx, h);
      ctx.moveTo(0, gy);
      ctx.lineTo(w, gy);
      ctx.stroke();
    }
    ctx.restore();
    ctx.strokeStyle = "#8b949e";
    ctx.beginPath();
    ctx.arc(cx, cy, rPx, 0, Math.PI * 2);
    ctx.stroke();

    // threat path, size at the start point, waypoints
    const pts = state.waypoints.map((p) => toPx(p.x, p.y));
    if (pts.length) {
      const r = state.sizeMm / 2 / view.mmPerPx;
      ctx.setLineDash([4, 4]);
      ctx.strokeStyle = "rgba(224,80,80,0.7)";
      ctx.beginPath();
      ctx.arc(pts[0][0], pts[0][1], r, 0, Math.PI * 2);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.strokeStyle = "#e05050";
      ctx.lineWidth = 2;
      ctx.beginPath();
      pts.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
      ctx.stroke();
      ctx.lineWidth = 1;
      pts.forEach(([x, y], i) => {
        ctx.fillStyle = "#e05050";
        ctx.beginPath();
        ctx.arc(x, y, 7, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = "#fff";
        ctx.font = "11px system-ui";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(String(i + 1), x, y);
        ctx.textAlign = "left";
        ctx.fillStyle = "#e0a0a0";
        ctx.fillText(`${state.waypoints[i].z} mm high`, x + 10, y - 10);
      });
    }

    // fly (2.5 mm long) and heading handle
    const [fx, fy] = toPx(state.fly.x, state.fly.y);
    const hd = handle();
    const [hx, hy] = toPx(hd.x, hd.y);
    ctx.strokeStyle = "#ffb347";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(fx, fy);
    ctx.lineTo(hx, hy);
    ctx.stroke();
    ctx.lineWidth = 1;
    ctx.fillStyle = "#ffb347";
    ctx.beginPath();
    ctx.arc(hx, hy, 5, 0, Math.PI * 2);
    ctx.fill();
    ctx.save();
    ctx.translate(fx, fy);
    ctx.rotate((-state.fly.headingDeg * Math.PI) / 180);
    ctx.fillStyle = "#d9a066";
    ctx.beginPath();
    ctx.ellipse(0, 0, 1.25 / view.mmPerPx + 3, 0.5 / view.mmPerPx + 2, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();

    // scale bar
    const bar = 10 / view.mmPerPx;
    ctx.strokeStyle = ctx.fillStyle = "#e6edf3";
    ctx.beginPath();
    ctx.moveTo(12, h - 14);
    ctx.lineTo(12 + bar, h - 14);
    ctx.stroke();
    ctx.font = "11px system-ui";
    ctx.fillText("10 mm (the fly is ~2.5 mm long)", 12, h - 22);
  }

  function update(): void {
    renderWaypoints();
    updateEstimate();
    draw();
  }

  // --- canvas interaction
  type Drag = { kind: "fly" } | { kind: "handle" } | { kind: "wp"; i: number } | null;
  let drag: Drag = null;
  const worldAt = (e: PointerEvent | MouseEvent): [number, number] => {
    const r = canvas.getBoundingClientRect();
    return canvasToWorld([e.clientX - r.left, e.clientY - r.top], view);
  };
  const near = (a: [number, number], b: { x: number; y: number }, px: number) =>
    Math.hypot(a[0] - b.x, a[1] - b.y) < px * view.mmPerPx;

  canvas.addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return;
    const p = worldAt(e);
    const wp = state.waypoints.findIndex((w) => near(p, w, 10));
    if (near(p, handle(), 10)) drag = { kind: "handle" };
    else if (wp >= 0) drag = { kind: "wp", i: wp };
    else if (near(p, state.fly, 12)) drag = { kind: "fly" };
    else if (state.waypoints.length < MAX_WAYPOINTS && Math.hypot(p[0], p[1]) <= ARENA_RADIUS_MM) {
      const last = state.waypoints.length === 0;
      state.waypoints.push({ x: p[0], y: p[1], z: last ? 6 : 2 });
      drag = { kind: "wp", i: state.waypoints.length - 1 };
      update();
    }
    if (drag) canvas.setPointerCapture(e.pointerId);
  });
  canvas.addEventListener("pointermove", (e) => {
    if (!drag) return;
    const [x, y] = worldAt(e);
    if (drag.kind === "fly") {
      const r = Math.hypot(x, y);
      const k = r > ARENA_RADIUS_MM - 2 ? (ARENA_RADIUS_MM - 2) / r : 1;
      state.fly.x = x * k;
      state.fly.y = y * k;
    } else if (drag.kind === "handle") {
      state.fly.headingDeg = (Math.atan2(y - state.fly.y, x - state.fly.x) * 180) / Math.PI;
    } else {
      state.waypoints[drag.i].x = x;
      state.waypoints[drag.i].y = y;
    }
    update();
  });
  canvas.addEventListener("pointerup", () => (drag = null));
  canvas.addEventListener("contextmenu", (e) => {
    e.preventDefault();
    const p = worldAt(e);
    const i = state.waypoints.findIndex((w) => near(p, w, 10));
    if (i >= 0) {
      state.waypoints.splice(i, 1);
      update();
    }
  });

  // --- form
  form.querySelectorAll<HTMLButtonElement>("[data-preset]").forEach((b) =>
    b.addEventListener("click", () => {
      state.fly = { x: 0, y: 0, headingDeg: 0 };
      state.waypoints = preset(b.dataset.preset as "left" | "right" | "front");
      update();
    }),
  );
  form.addEventListener("input", (e) => {
    const t = e.target as HTMLInputElement;
    if (t.name === "size") state.sizeMm = Number(t.value);
    if (t.name === "speed") state.speedMmS = Number(t.value);
    if (t.name === "duration") state.durationS = Number(t.value);
    if (t.name === "seed") state.seed = Number(t.value);
    if (t.name === "brain") state.brain = t.checked;
    updateEstimate();
    draw();
  });

  const errors = form.querySelector<HTMLUListElement>(".errors")!;
  const jobBox = form.querySelector<HTMLElement>(".job")!;
  const jobText = form.querySelector<HTMLElement>(".job-text")!;
  const bar = form.querySelector<HTMLElement>(".progress-bar")!;
  const watch = form.querySelector<HTMLAnchorElement>(".watch")!;
  const applyBtn = form.querySelector<HTMLButtonElement>(".apply")!;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    errors.replaceChildren();
    watch.hidden = true;
    applyBtn.disabled = true;
    try {
      const res = await fetch("api/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scene: sceneFromState(state), brain: state.brain }),
      });
      const body = await res.json();
      if (res.status === 422) {
        for (const err of body.errors as { field: string; message: string }[]) {
          const li = document.createElement("li");
          li.textContent = `${err.field}: ${err.message}`;
          errors.appendChild(li);
        }
        return;
      }
      if (!res.ok) throw new Error(`server answered HTTP ${res.status}`);
      await follow(body.id as string);
    } catch (err) {
      const li = document.createElement("li");
      li.textContent = String(err);
      errors.appendChild(li);
    } finally {
      applyBtn.disabled = false;
      void refreshRecent();
    }
  });

  async function follow(id: string): Promise<void> {
    jobBox.hidden = false;
    for (;;) {
      const job = (await (await fetch(`api/jobs/${id}`)).json()) as Job;
      bar.style.width = `${Math.round(job.progress * 100)}%`;
      if (job.state === "queued") jobText.textContent = `Waiting in queue (position ${job.position})…`;
      else if (job.state === "running")
        jobText.textContent = `Simulating… ${Math.round(job.progress * 100)} %`;
      else {
        jobText.textContent =
          job.state === "complete"
            ? "Done."
            : job.state === "aborted"
              ? `Run stopped early: ${job.reason}. The partial replay is available.`
              : `Error: ${job.error}`;
        watch.href = replayUrl(job, "Your scene");
        watch.hidden = false;
        return;
      }
      await new Promise((r) => setTimeout(r, 1000));
    }
  }

  async function refreshRecent(): Promise<void> {
    const list = root.querySelector<HTMLUListElement>(".recent ul")!;
    const jobs = (await (await fetch("api/jobs")).json()) as Job[];
    list.replaceChildren();
    for (const j of jobs.slice(0, 10)) {
      const li = document.createElement("li");
      const when = new Date(j.created * 1000).toLocaleTimeString();
      const label = `${when} · ${j.duration_s} s · ${j.brain ? "brain" : "no brain"} · ${j.state}`;
      if (j.state === "queued" || j.state === "running") li.textContent = label;
      else {
        const a = document.createElement("a");
        a.href = replayUrl(j, `Your scene (${when})`);
        a.textContent = label;
        li.appendChild(a);
      }
      list.appendChild(li);
    }
  }

  syncInputs();
  update();
  new ResizeObserver(resize).observe(canvas.parentElement!);
  resize();
  void refreshRecent();
  document.body.dataset.ready = "true";
}
