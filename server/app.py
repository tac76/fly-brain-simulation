"""HTTP API for the local scene editor (bind to 127.0.0.1 only)."""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ValidationError

from flybrain.config import Config, load_config
from flybrain.recording import RECORDING_FILES
from flybrain.scene import Scene
from server.jobs import JobQueue


class JobRequest(BaseModel):
    scene: dict
    brain: bool = True


def _field_errors(e: ValidationError) -> list[dict]:
    out = []
    for err in e.errors():
        loc = [str(x) for x in err["loc"] if not isinstance(x, int)]
        out.append({"field": ".".join(loc) or "scene", "message": err["msg"]})
    return out


def create_app(
    queue: JobQueue, viewer_dist: Path | None = None, config: Config | None = None
) -> FastAPI:
    app = FastAPI(title="Fly Brain Simulation editor")
    cfg = config or load_config()

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True, "editor": True}

    @app.post("/api/jobs", status_code=202)
    def submit(req: JobRequest):
        try:
            scene = Scene.model_validate(req.scene)
        except ValidationError as e:
            return JSONResponse({"errors": _field_errors(e)}, status_code=422)
        try:
            scene.validate_against(cfg)
        except ValueError as e:
            return JSONResponse({"errors": [{"field": "fly.pos", "message": str(e)}]}, 422)
        return {"id": queue.submit(scene, req.brain)}

    @app.get("/api/jobs")
    def jobs() -> list[dict]:
        return queue.list()

    @app.get("/api/jobs/{job_id}")
    def job(job_id: str) -> dict:
        j = queue.get(job_id)
        if j is None:
            raise HTTPException(404, "unknown job")
        return j

    @app.get("/api/recordings/{job_id}/{name}")
    def recording(job_id: str, name: str):
        folder = queue.recording_dir(job_id)
        if folder is None or name not in RECORDING_FILES or not (folder / name).is_file():
            raise HTTPException(404, "not found")
        return FileResponse(folder / name)

    if viewer_dist is not None and Path(viewer_dist).is_dir():
        index = Path(viewer_dist) / "index.html"

        @app.get("/", response_class=HTMLResponse)
        def viewer_index() -> str:
            # tells the viewer it runs behind this server (shows the editor) without a request
            # that would 404 on a static host
            marker = '<meta name="flybrain-server" content="1">'
            return index.read_text().replace("<head>", f"<head>{marker}", 1)

        app.mount("/", StaticFiles(directory=viewer_dist, html=True), name="viewer")
    return app
