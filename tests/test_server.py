import time
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from util import EXAMPLE_SCENE, deep_merge

from flybrain.loop import RunResult
from flybrain.recording import RecordingWriter
from server.app import create_app
from server.jobs import JobQueue


class StubRunner:
    """Writes a 1-frame recording; can block until released or raise."""

    def __init__(self):
        self.calls = []
        self.block = False
        self.fail = False

    def __call__(self, scene, brain, out: Path, progress):
        self.calls.append((scene, brain))
        while self.block:
            time.sleep(0.01)
        w = RecordingWriter(out, {"brain": brain}, ["Thorax"])
        w.append(np.zeros((1, 7), np.float32), np.array([], np.uint32), {})
        if self.fail:
            w.close("aborted", reason="error: RuntimeError: boom")
            raise RuntimeError("boom")
        progress(1.0)
        w.close("complete")
        return RunResult("complete", None, 1, 0.01, [])


def wait_state(client, job_id, states, timeout=5.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        j = client.get(f"/api/jobs/{job_id}").json()
        if j["state"] in states:
            return j
        time.sleep(0.02)
    raise AssertionError(f"job {job_id} stuck in {j['state']}")


@pytest.fixture
def setup(tmp_path):
    runner = StubRunner()
    queue = JobQueue(tmp_path / "jobs", runner)
    client = TestClient(create_app(queue, viewer_dist=None))
    yield client, runner
    runner.block = False
    queue.stop()


def test_health(setup):
    client, _ = setup
    assert client.get("/api/health").json() == {"ok": True, "editor": True}


def test_submit_runs_to_complete_and_serves_recording(setup):
    client, runner = setup
    r = client.post("/api/jobs", json={"scene": EXAMPLE_SCENE, "brain": False})
    assert r.status_code == 202
    job = wait_state(client, r.json()["id"], {"complete"})
    assert job["progress"] == 1.0 and runner.calls[0][1] is False
    meta = client.get(f"/api/recordings/{job['id']}/meta.json")
    assert meta.status_code == 200 and meta.json()["brain"] is False


def test_second_job_waits_in_queue(setup):
    client, runner = setup
    runner.block = True
    a = client.post("/api/jobs", json={"scene": EXAMPLE_SCENE, "brain": True}).json()["id"]
    wait_state(client, a, {"running"})
    b = client.post("/api/jobs", json={"scene": EXAMPLE_SCENE, "brain": True}).json()["id"]
    jb = client.get(f"/api/jobs/{b}").json()
    assert jb["state"] == "queued" and jb["position"] == 1
    runner.block = False
    wait_state(client, b, {"complete"})
    assert len(runner.calls) == 2


def test_invalid_scene_rejected_with_field_names(setup):
    client, runner = setup
    bad = deep_merge(EXAMPLE_SCENE, {"shadow": {"path": [[0, 0, -1], [1, 1, 1]]}, "duration_s": 11})
    r = client.post("/api/jobs", json={"scene": bad, "brain": True})
    assert r.status_code == 422
    fields = {e["field"] for e in r.json()["errors"]}
    assert "shadow.path" in fields and "duration_s" in fields
    assert runner.calls == []


def test_fly_outside_arena_rejected(setup):
    client, _ = setup
    bad = deep_merge(EXAMPLE_SCENE, {"fly": {"pos": [100, 0]}})
    r = client.post("/api/jobs", json={"scene": bad, "brain": True})
    assert r.status_code == 422 and r.json()["errors"][0]["field"] == "fly.pos"


def test_runner_exception_sets_error_and_keeps_serving(setup):
    client, runner = setup
    runner.fail = True
    a = client.post("/api/jobs", json={"scene": EXAMPLE_SCENE, "brain": True}).json()["id"]
    job = wait_state(client, a, {"error"})
    assert "boom" in job["error"]
    assert client.get(f"/api/recordings/{a}/meta.json").json()["status"] == "aborted"
    runner.fail = False
    b = client.post("/api/jobs", json={"scene": EXAMPLE_SCENE, "brain": True}).json()["id"]
    wait_state(client, b, {"complete"})


def test_recording_paths_are_restricted(setup):
    client, _ = setup
    a = client.post("/api/jobs", json={"scene": EXAMPLE_SCENE, "brain": False}).json()["id"]
    wait_state(client, a, {"complete"})
    assert client.get(f"/api/recordings/{a}/secret.txt").status_code == 404
    assert client.get(f"/api/recordings/{a}/..%2F..%2Fpyproject.toml").status_code == 404
    assert client.get("/api/recordings/nope/meta.json").status_code == 404
    assert client.get("/api/jobs/nope").status_code == 404


def test_job_list(setup):
    client, _ = setup
    a = client.post("/api/jobs", json={"scene": EXAMPLE_SCENE, "brain": False}).json()["id"]
    wait_state(client, a, {"complete"})
    assert [j["id"] for j in client.get("/api/jobs").json()] == [a]
