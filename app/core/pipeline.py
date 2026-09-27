"""Пайплайн: DXF/DWG -> зоны -> посадки -> самоконтроль -> интерпретации -> DXF.

Новое:
- fill (10..100%): детерминированное подмножество одобренных посадок
  (первые K% по порядку id), остальное -> rejected с причиной.
- cumulative: реестр посадок по hash входов; при повторном прогоне ранее
  размещённые точки исключаются буферами, новые досаживаются (до-заполнение).
- selfcheck: одобренная точка не остаётся в запрещённой зоне / на инфраструктуре.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import time
from collections import Counter

from shapely.geometry import Point
from shapely.ops import unary_union

from . import (budget_controller, cost_engine, dxf_export, dxf_ingest,
               gen_engine, interp_engine, norm_engine)
from .. import config as cfgmod


def _rings(geom):
    if geom is None or geom.is_empty:
        return []
    polys = geom.geoms if geom.geom_type == "MultiPolygon" else [geom]
    return [[[round(x, 2), round(y, 2)] for x, y in p.exterior.coords] for p in polys]


def _shapes(lst):
    out = []
    for g in lst:
        if g.geom_type in ("Polygon", "MultiPolygon"):
            for p in (g.geoms if g.geom_type == "MultiPolygon" else [g]):
                out.append({"kind": "poly",
                            "pts": [[round(x, 2), round(y, 2)] for x, y in p.exterior.coords]})
        elif g.geom_type == "LineString":
            out.append({"kind": "line",
                        "pts": [[round(x, 2), round(y, 2)] for x, y in g.coords]})
        elif g.geom_type == "Point":
            out.append({"kind": "point", "pts": [[round(g.x, 2), round(g.y, 2)]]})
    return out


def _registry_path():
    return cfgmod.DATA_DIR / "planting_registry.json"


def _load_registry() -> dict:
    p = _registry_path()
    if p.exists():
        try:
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_registry(reg: dict):
    with open(_registry_path(), "w", encoding="utf-8") as f:
        json.dump(reg, f, ensure_ascii=False, indent=2)


def _input_key(paths) -> str:
    h = hashlib.sha1()
    for p in sorted(str(x) for x in paths):
        try:
            with open(p, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
        except OSError:
            h.update(p.encode())
    return h.hexdigest()[:16]


def run(input_paths, cfg: dict, out_dir: str, layer_overrides=None) -> dict:
    t0 = time.time()
    os.makedirs(out_dir, exist_ok=True)
    gcfg = cfg.get("gen", {})
    fill = max(10, min(100, int(gcfg.get("fill", 100))))
    cumulative = bool(gcfg.get("cumulative", False))

    ing = dxf_ingest.ingest(input_paths, cfg, layer_overrides=layer_overrides)
    boundary = ing["boundary"]
    area_ha = boundary.area / 10_000.0

    zones = norm_engine.build_zones(ing["geom"], boundary, cfgmod.norms(), cfg)

    # до-заполнение: исключаем уже размещённые ранее точки этого набора входов
    reg = _load_registry()
    key = _input_key(ing.get("used") or input_paths) + ":" + cfg["project"]["territory_type"]
    prior = reg.get(key, []) if cumulative else []
    if prior:
        bufs = [Point(e["x"], e["y"]).buffer(2.5 if e.get("type") == "tree" else 1.0)
                for e in prior]
        bu = unary_union(bufs)
        zones["allowed_trees"] = zones["allowed_trees"].difference(bu)
        zones["allowed_shrubs"] = zones["allowed_shrubs"].difference(bu)
        zones["shrub_only"] = zones["allowed_shrubs"].difference(zones["allowed_trees"])

    gen = gen_engine.generate(ing["geom"], zones, boundary,
                              cfgmod.norms(), cfg, cfgmod.catalog())
    plantings_or_none, removed, est_pre, bud_pre = budget_controller.apply_budget(
        gen["plantings"], cfgmod.costs(), cfg, area_ha, cost_engine.estimate)

    util_keys = ("water_pipe", "gas", "cable", "power_line")
    geo_base = {"boundary": (_rings(boundary) or [[]])[0],
                "forbidden": _rings(zones["forbidden"]),
                "allowed": _rings(zones["allowed_trees"]),
                "buildings": _shapes(ing["geom"].get("buildings", [])),
                "roads": _shapes(ing["geom"].get("roads", [])),
                "utilities": _shapes([g for k in util_keys for g in ing["geom"].get(k, [])]),
                "existing": [[round(g.centroid.x, 2), round(g.centroid.y, 2)]
                             for g in ing["geom"].get("existing_trees", [])]}
    layer_mapping = {k: {"category": v.get("category"), "confidence": v.get("confidence"),
                         "reasons": v.get("reasons", [])}
                     for k, v in (ing.get("mapping") or {}).items()}

    if plantings_or_none is None:
        geo_base["plantings"] = []
        summary = {"blocked": True, "area_ha": round(area_ha, 3),
                   "allowed_area_ha": round(zones["allowed_trees"].area / 10_000, 3),
                   "forbidden_area_ha": round((boundary.area - zones["allowed_trees"].area) / 10_000, 3),
                   "warnings": [bud_pre.get("message", "")],
                   "budget": bud_pre, "estimate": est_pre, "plantings": [],
                   "species_summary": {}, "layer_mapping": layer_mapping,
                   "applied_norms": zones["applied"], "geo": geo_base,
                   "fill": fill, "cumulative": cumulative, "cumulative_prior": len(prior),
                   "seconds": round(time.time() - t0, 1), "outputs": {}}
        with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        return summary

    interp = interp_engine.build(plantings_or_none, gen["rejected"],
                                 ing["geom"], cfgmod.norms(), cfg)

    # самоконтроль норм
    obstacles = []
    for k in util_keys + ("buildings", "roads"):
        obstacles += ing["geom"].get(k, [])
    fixed = 0
    for p in interp:
        if p.get("status") != "approved":
            continue
        pt = Point(p["x"], p["y"])
        if zones["forbidden"].contains(pt) or any(pt.distance(o) < 0.5 for o in obstacles):
            p["status"] = "rejected"
            p["notes"] = p.get("notes", []) + [
                "Самоконтроль: точка в запрещённой зоне или на инфраструктуре — снята"]
            fixed += 1

    # ползунок наполненности: детерминированное подмножество по порядку id
    approved = sorted([p for p in interp if p["status"] == "approved"], key=lambda p: p["id"])
    keep = math.ceil(len(approved) * fill / 100.0)
    for p in approved[keep:]:
        p["status"] = "rejected"
        p["notes"] = p.get("notes", []) + [f"Снято ползунком наполненности ({fill}%)"]

    est = cost_engine.estimate(interp, cfgmod.costs(), area_ha)
    bud = budget_controller.evaluate(est["total"], cfg, cfgmod.costs(), area_ha)

    src_list = ing.get("used") or ing.get("paths_used") or list(input_paths)
    out_dxf = os.path.join(out_dir, "result.dxf")
    out_dxf, export_warnings = dxf_export.export(src_list[0], out_dxf, interp, zones, cfg)

    # реестр до-заполнения: запоминаем одобренные точки набора входов
    if cumulative:
        entries = reg.setdefault(key, [])
        have = {e["id"] for e in entries}
        for p in interp:
            if p["status"] == "approved" and p["id"] not in have:
                entries.append({"id": p["id"], "x": p["x"], "y": p["y"], "type": p["type"]})
        _save_registry(reg)

    geo_base["plantings"] = [{"id": p["id"], "x": p["x"], "y": p["y"],
                              "type": p["type"], "status": p["status"]} for p in interp]
    approved_final = [p for p in interp if p["status"] == "approved"]
    species_summary = dict(Counter(p["species"] for p in approved_final))

    base_warnings = ing.get("warnings", []) + export_warnings
    if bud.get("message") and bud["status"] == "over":
        base_warnings.append(bud["message"])

    summary = {"blocked": False, "area_ha": round(area_ha, 3),
               "allowed_area_ha": round(zones["allowed_trees"].area / 10_000, 3),
               "forbidden_area_ha": round((boundary.area - zones["allowed_trees"].area) / 10_000, 3),
               "warnings": base_warnings,
               "selfcheck": {"removed_violations": fixed},
               "fill": fill, "cumulative": cumulative, "cumulative_prior": len(prior),
               "layer_mapping": layer_mapping, "applied_norms": zones["applied"],
               "species_summary": species_summary, "plantings": interp,
               "estimate": est, "budget": bud, "removed_by_budget": removed,
               "geo": geo_base, "seconds": round(time.time() - t0, 1),
               "outputs": {"dxf": "result.dxf", "interpretation": "interpretation.json",
                           "estimate": "estimate.json", "summary": "summary.json"}}
    with open(os.path.join(out_dir, "interpretation.json"), "w", encoding="utf-8") as f:
        json.dump(interp, f, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, "estimate.json"), "w", encoding="utf-8") as f:
        json.dump({"estimate": est, "budget": bud}, f, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump({k: v for k, v in summary.items() if k != "geo"}, f, ensure_ascii=False, indent=2)
    return summary