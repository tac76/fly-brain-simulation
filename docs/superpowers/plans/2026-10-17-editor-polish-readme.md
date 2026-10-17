# Editor, Polish and README Implementation Plan (Plan 3a)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (chosen: native). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Everything up to (not including) going public: the local scene editor with Apply, a job server, gallery polish, Docker files, and a README with a GIF — ready for Marvin to test through an SSH tunnel.

**Architecture:** A FastAPI app (`server/`) wraps `run_scene` in a single-worker job queue, keeps the connectome loaded, serves recordings and the built viewer. The viewer detects the server (`GET /api/health`) and shows an editor page; finished jobs open in the existing replay via a recording URL. Publishing (GitHub repo, Pages) is Plan 3b and needs Marvin's go.

**Tech Stack:** FastAPI, uvicorn, httpx (tests); existing viewer stack; Playwright + ffmpeg for thumbnails and the GIF.

**Spec:** `docs/superpowers/specs/2026-10-14-fly-brain-simulation-design.md` (§6, §7, §8, §11)

## Global Constraints

- Server binds `127.0.0.1` only (default port 8770); reachable from Marvin's PC by SSH tunnel, never opened publicly.
- One job at a time; the connectome is loaded once at startup (lazily on first brain job).
- Scene validation errors return HTTP 422 with one message per field; the editor shows them next to the inputs.
- Job states: `queued`, `running` (with `progress` 0–1), `complete`, `aborted`, `error` (with message). Recordings live in `out/jobs/<id>/` (git-ignored).
- Every run (brain or not) records `threat_x/y/z` so baselines show the threat too.
- Docker: `Dockerfile` + CI build job. Docker is not available on the VPS, so the image is built only in CI; this is stated in the README.
- No push, no GitHub repo creation in this plan.

## Review Focus

1. Apply while a job is running → second job queued, editor shows queue position; no parallel simulations.
2. Invalid scene (waypoint below ground, duration > 10 s) → 422 with field names, nothing queued.
3. Job crashes (exception in run_scene) → state `error` with message, partial recording kept, server keeps serving.
4. Editor used without the server (GitHub Pages) → editor hidden, gallery unchanged.
5. Recording URL with path traversal (`../`) → 404.

---

### Task 1: Threat signals in every run, baseline scene

**Files:** Modify `flybrain/loop.py`, `tests/test_loop.py`, `scenes/gallery/walk.json`, `scenes/gallery/walk.gallery.json`

- [ ] Failing test `test_threat_signals_recorded_without_brain`: a `ConstantController` run has `threat_x/y/z` per frame equal to `threat_position(scene.shadow, (k+1)*0.02)`.
- [ ] `run_scene` adds the threat signals for every frame (controller signals win if they already contain them).
- [ ] `walk` becomes "loom_left without brain": same scene as `loom_left`, `no_brain: true`, title "Same threat, brain switched off", description says the fly walks on unaffected.
- [ ] Commit `feat: record threat in every run; paired no-brain baseline in the gallery`.

### Task 2: Job server

**Files:** Create `server/__init__.py`, `server/app.py`, `server/jobs.py`, `tests/test_server.py`; Modify `pyproject.toml` (deps `fastapi`, `uvicorn`; dev `httpx`), `flybrain/cli.py` (command `serve`)

**Interfaces:**
- `class JobQueue`: `__init__(self, out_dir: Path, runner: Callable[[Scene, Path, Callable[[float], None]], RunResult])`, `submit(scene: Scene, brain: bool) -> str`, `get(job_id) -> dict` (`id, state, progress, position, status, reason, error, brain, created`), `list() -> list[dict]`; one worker thread.
- `def default_runner(data_dir: Path, config: Config) -> runner` (lazy connectome, `make_brain_controller` or `ConstantController`).
- `def create_app(queue: JobQueue, viewer_dist: Path | None) -> FastAPI`: `GET /api/health` → `{"ok": true, "editor": true}`; `POST /api/jobs` body `{"scene": {...}, "brain": true}` → 202 `{"id"}` or 422 `{"errors": [{"field", "message"}]}`; `GET /api/jobs/{id}`; `GET /api/jobs`; `GET /api/recordings/{id}/{file}` (only the four recording files; else 404); static viewer at `/` when `viewer_dist` exists.
- CLI: `flybrain serve [--port 8770] [--data-dir data] [--out out/jobs]`.

- [ ] Failing tests with `TestClient` and a stub runner (writes a 1-frame recording, records calls): health; submit → complete; second submit while first blocks → `position == 1`; invalid scene → 422 listing `shadow.path`; runner exception → `error` with message; recording served; traversal (`..%2Fmeta.json`, unknown file name) → 404.
- [ ] Implement; tests GREEN. Commit `feat: add local job server for the editor`.

### Task 3: Editor in the viewer

**Files:** Create `viewer/src/editor.ts`, `viewer/src/editorGeometry.ts`, `viewer/tests/editorGeometry.test.ts`; Modify `viewer/src/main.ts`, `viewer/src/app.ts` (replay from a recording URL), `viewer/src/gallery.ts`, `viewer/src/style.css`, `viewer/vite.config.ts` (dev proxy `/api` → 8770), e2e

**Interfaces:**
- `editorGeometry.ts`: `worldToCanvas(p, view)`, `canvasToWorld(px, view)`, `pathLength(path)`, `sceneFromState(state) -> object` (the scene JSON), `estimateSeconds(durationS, brain)` (≈ 40 s per simulated second with brain, 33 without, from the measured VPS numbers).
- Routes: `?editor` → editor page (only if `/api/health` answers); `?rec=<url>&title=<t>&brain=1` → replay of any recording URL. Gallery shows an "Open the editor" card when the server is present.
- Editor page: top-down arena canvas (60 mm radius, 1 mm grid, scale bar); drag the fly (arrow shows heading, drag the arrow tip to rotate); click adds waypoints (max 4, drag to move, right-click/remove button), height slider per waypoint; inputs size, speed, duration, seed, brain on/off; presets (from left / from right / head-on); estimated wait; Apply → progress bar with queue position → "Watch replay" opens `?rec=api/recordings/<id>/`; field errors from 422 shown inline; list of recent jobs.

- [ ] Failing unit tests: round-trip world↔canvas, path length, scene JSON shape (path as `[x, y, z]`, heading in degrees), estimate.
- [ ] Implement; e2e: with a mocked `/api` (Playwright route), the editor appears, Apply posts the expected scene, progress reaches the replay link; without `/api` the gallery has no editor card. Commit `feat: add scene editor with Apply`.

### Task 4: Gallery polish

**Files:** Modify `viewer/src/brain.ts`, `viewer/src/app.ts`, `viewer/src/gallery.ts`, `viewer/src/world.ts`, `viewer/src/style.css`; Create `scripts/capture_media.py` (Playwright: thumbnails + GIF frames), `viewer/public/gallery/<id>/thumb.jpg`, `docs/media/escape.gif`

- [ ] Brain panel legend (looming input, giant fiber, steering, other neurons; spike colour); labels for LC4 merged into "looming input L/R" (LPLC2 + LC4).
- [ ] Footer on every page: FlyWire CC BY-NC 4.0 with licence link, NeuroMechFly/FlyGym credit (Apache-2.0), Shiu et al. 2024.
- [ ] `PCFShadowMap` (removes the console warning); follow-mode indicator in the view label.
- [ ] Gallery cards show `thumb.jpg`.
- [ ] `capture_media.py` (run against `vite preview`): thumbnails at a fixed frame per run; GIF of `loom_left` (both panels, frames 0–60 every frame, 800 px wide, ffmpeg palette, ≤ 6 MB).
- [ ] e2e still green; look at the thumbnails and GIF. Commit `feat: gallery thumbnails, legend, credits; README GIF`.

### Task 5: Docker, licences, README

**Files:** Create `Dockerfile`, `.dockerignore`, `DATA_LICENSE.md`, `NOTICE`; Modify `README.md`, `.github/workflows/ci.yml` (job `docker`: build only), `flybrain/connectome.py` docstring

- [ ] Dockerfile: multi-stage (Node build of the viewer; Python 3.12 slim with uv, `uv sync --frozen --no-dev`, MuJoCo EGL/OSMesa libs), downloads data at first start into a volume, `CMD flybrain serve --host 0.0.0.0 --port 8770`.
- [ ] README: GIF at the top, one-paragraph pitch, what is real vs hand-built, measured results (link `docs/calibration.md`), quick start (gallery locally, editor via `flybrain serve`, Docker), architecture diagram (ASCII), repository map, limits, credits, licences.
- [ ] `DATA_LICENSE.md` (CC BY-NC 4.0 for FlyWire-derived files: brain_points, gallery recordings), `NOTICE` (FlyGym/NeuroMechFly Apache-2.0, Shiu et al. MIT, three.js MIT, uPlot MIT).
- [ ] Full suites green. Commit `docs: README with GIF, licences, Dockerfile`.

### Task 6: Test deployment for Marvin

- [ ] Build the viewer, run `flybrain serve` as a systemd user service `flybrain-editor` on `127.0.0.1:8770` (VPS), check `GET /api/health` and one Apply end to end.
- [ ] Hand Marvin click-by-click instructions (SSH tunnel from Windows Terminal, browser URL, what to try).

## Done when

All suites green, the editor works end to end on the VPS, Marvin has the test instructions. Plan 3b (public repo, Pages) waits for his review.
