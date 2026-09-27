"""Веб-сервер (FastAPI): API + статика + Swagger /docs.

Добавлено: middleware Cache-Control: no-store для html/js/css — браузер больше
не держит устаревший index.html (лечит «304 Not Modified» и «ничего не поменялось»).
"""
from __future__ import annotations

import json
import os
import tempfile
import traceback
import uuid
from pathlib import Path
from typing import List

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from .. import config as cfgmod
from ..core import dxf_ingest, dwg_convert, layer_knowledge, layer_mapper, pipeline

WEB_DIR = Path(__file__).resolve().parent.parent.parent / "web"
_RUNS = {}


def _save(files) -> list:
    tmp = tempfile.mkdtemp(prefix="gp_up_")
    paths = []
    for f in files:
        dst = os.path.join(tmp, f.filename or "input.dxf")
        with open(dst, "wb") as out:
            out.write(f.file.read())
        paths.append(dst)
    return paths


def create_app(cfg=None) -> FastAPI:
    cfg = cfg or cfgmod.default_config()
    app = FastAPI(title="GreenPlan AI", version="1.5.1",
                  description="DXF/DWG -> план озеленения на отдельном слое + интерпретации по НПА")

    @app.middleware("http")
    async def no_cache(request, call_next):
        response = await call_next(request)
        p = request.url.path
        if p in ("/", "/index.html") or p.endswith((".html", ".js", ".css")):
            response.headers["Cache-Control"] = "no-store, max-age=0, must-revalidate"
            response.headers["Pragma"] = "no-cache"
        return response

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon():
        return Response(status_code=204)

    @app.get("/api/health")
    def health():
        conv = dwg_convert.find_dwg2dxf(cfg)
        return {"status": "ok", "mode": "offline",
                "dwg_converter": str(conv) if conv else None}

    @app.get("/api/profile")
    def get_profile():
        return layer_mapper.load_profiles()

    @app.post("/api/profile")
    async def set_profile(payload: dict):
        layer_mapper.save_profile(payload.get("profile", "default"),
                                  payload.get("mapping", {}))
        return {"ok": True}

    @app.post("/api/mapping/learn")
    async def learn(payload: dict):
        items = payload.get("items", [])
        profile = payload.get("profile", "default")
        for it in items:
            if it.get("category"):
                layer_knowledge.learn(it["layer"], it["category"],
                                      source="human", confidence=1.0, profile=profile)
        return {"ok": True, "learned": len(items)}

    @app.get("/api/knowledge")
    def knowledge():
        k = layer_knowledge.load()
        return {"tokens": len(k["tokens"]), "examples": len(k["examples"]),
                "profiles": {p: len(m) for p, m in k["profiles"].items()}}

    @app.post("/api/layers")
    async def layers(files: List[UploadFile] = File(...)):
        out = []
        for f in files:
            tmp = os.path.join(tempfile.mkdtemp(prefix="gp_up_"), f.filename or "input.dxf")
            with open(tmp, "wb") as fh:
                fh.write(await f.read())
            try:
                out.append({"file": f.filename, "layers": dxf_ingest.inspect_layers(tmp, cfg)})
            except Exception as e:
                traceback.print_exc()
                raise HTTPException(400, str(e))
        return {"files": out}

    @app.post("/api/run")
    async def run(files: List[UploadFile] = File(...),
                  territory: str = Form("T1"), seed: int = Form(42),
                  budget_mode: str = Form("tsn_norm"), budget_value: float = Form(0.0),
                  budget_policy: str = Form("warn"),
                  fill: int = Form(100), cumulative: bool = Form(False),
                  mapping: str = Form("{}")):
        paths = _save(files)
        try:
            overrides = json.loads(mapping or "{}")
        except Exception:
            overrides = {}
        over = {"project": {"territory_type": territory}, "run": {"seed": seed},
                "budget": {"mode": budget_mode, "manual_value_mln": budget_value,
                           "policy": budget_policy},
                "gen": {"fill": fill, "cumulative": cumulative}}
        run_cfg = cfgmod.load_config(None, over)
        out_dir = os.path.join(tempfile.mkdtemp(prefix="gp_run_"), "out")
        try:
            summary = pipeline.run(paths, run_cfg, out_dir, layer_overrides=overrides)
        except dxf_ingest.IngestError as e:
            traceback.print_exc()
            if e.code == "NO_LAYERS":
                raise HTTPException(400, {"message": str(e), "need_mapping": True,
                                        "layers": e.layers})
            raise HTTPException(400, str(e))
        except Exception as e:
            traceback.print_exc()
            raise HTTPException(400, str(e))
        run_id = uuid.uuid4().hex[:8]
        _RUNS[run_id] = out_dir
        summary["run_id"] = run_id
        return summary

    @app.get("/api/runs/{run_id}/files/{name}")
    def get_file(run_id: str, name: str):
        d = _RUNS.get(run_id)
        if not d:
            raise HTTPException(404, "Расчёт не найден")
        p = os.path.join(d, name)
        if not os.path.exists(p):
            raise HTTPException(404, "Файл не найден")
        return FileResponse(p, filename=name)

    app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
    return app


app = create_app()