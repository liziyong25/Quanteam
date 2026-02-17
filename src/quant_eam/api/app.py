from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from quant_eam.core.version import version_payload
from quant_eam.api.read_only_api import router as read_only_router
from quant_eam.api.jobs_api import router as jobs_router
from quant_eam.api.snapshots_api import router as snapshots_router
from quant_eam.api.ui_routes import router as ui_router

app = FastAPI(title="quant-eam")


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.get("/version")
def version() -> dict:
    return version_payload()


# Read-only JSON API (dossier/gates/registry) + UI routes.
app.include_router(read_only_router)
app.include_router(jobs_router)
app.include_router(snapshots_router)
app.include_router(ui_router)

# Static assets for UI (no external CDN).
_static_dir = (__import__("pathlib").Path(__file__).resolve().parents[1] / "ui" / "static")
if _static_dir.is_dir():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")
