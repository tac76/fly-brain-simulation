"""Single-worker job queue around run_scene: one simulation at a time."""

import queue
import threading
import time
import uuid
from collections.abc import Callable
from pathlib import Path

from flybrain.config import Config
from flybrain.connectome import Connectome
from flybrain.loop import ConstantController, RunResult, make_brain_controller, run_scene
from flybrain.scene import Scene

Runner = Callable[[Scene, bool, Path, Callable[[float], None]], RunResult]


def default_runner(data_dir: Path, config: Config, device: str = "cpu") -> Runner:
    """Runs the real simulation; the connectome is loaded on the first brain job and kept."""
    cache: dict[str, Connectome] = {}

    def run(scene: Scene, brain: bool, out: Path, progress: Callable[[float], None]) -> RunResult:
        if brain:
            if "c" not in cache:
                cache["c"] = Connectome.from_files(data_dir)
            ctrl = make_brain_controller(scene, config, cache["c"], device=device)
        else:
            ctrl = ConstantController((config.motor.base_drive, config.motor.base_drive))
        return run_scene(scene, config, ctrl, out, progress=progress)

    return run


class JobQueue:
    def __init__(self, out_dir: Path, runner: Runner):
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.runner = runner
        self._jobs: dict[str, dict] = {}
        self._order: list[str] = []
        self._pending: queue.Queue[str | None] = queue.Queue()
        self._lock = threading.Lock()
        self._worker = threading.Thread(target=self._work, daemon=True)
        self._worker.start()

    def submit(self, scene: Scene, brain: bool) -> str:
        job_id = uuid.uuid4().hex[:10]
        with self._lock:
            self._jobs[job_id] = {
                "id": job_id,
                "state": "queued",
                "progress": 0.0,
                "brain": brain,
                "status": None,
                "reason": None,
                "error": None,
                "created": time.time(),
                "scene": scene,
            }
            self._order.append(job_id)
        self._pending.put(job_id)
        return job_id

    def recording_dir(self, job_id: str) -> Path | None:
        with self._lock:
            return self.out_dir / job_id if job_id in self._jobs else None

    def get(self, job_id: str) -> dict | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            queued = [j for j in self._order if self._jobs[j]["state"] == "queued"]
            out = {k: v for k, v in job.items() if k != "scene"}
            out["position"] = queued.index(job_id) + 1 if job["state"] == "queued" else 0
            out["duration_s"] = job["scene"].duration_s
            return out

    def list(self) -> list[dict]:
        with self._lock:
            ids = list(reversed(self._order))
        return [j for j in (self.get(i) for i in ids) if j is not None]

    def stop(self) -> None:
        self._pending.put(None)

    def _set(self, job_id: str, **fields) -> None:
        with self._lock:
            self._jobs[job_id].update(fields)

    def _work(self) -> None:
        while True:
            job_id = self._pending.get()
            if job_id is None:
                return
            with self._lock:
                scene, brain = self._jobs[job_id]["scene"], self._jobs[job_id]["brain"]
            self._set(job_id, state="running")
            try:
                result = self.runner(
                    scene,
                    brain,
                    self.out_dir / job_id,
                    lambda p, j=job_id: self._set(j, progress=round(p, 3)),
                )
                done = {"progress": 1.0} if result.status == "complete" else {}
                self._set(
                    job_id, state=result.status, status=result.status, reason=result.reason, **done
                )
            except Exception as e:  # keep serving; the loop already saved a partial recording
                self._set(job_id, state="error", status="aborted", error=f"{type(e).__name__}: {e}")
