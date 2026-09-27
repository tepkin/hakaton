"""Импорт DXF/DWG: статистика слоёв, гибкий маппинг, извлечение геометрии.

Добавлено (дефект 3): подсчёт TEXT/MTEXT с кадастровыми номерами
(50:26:016:0201:1275) в статистике слоя — геодезия/кадастр отделяются от
деревьев и зданий. Ошибка «нет слоёв» теперь несёт код NO_LAYERS и список
слоёв, чтобы UI открывал мастер маппинга вместо тупика.
"""
from __future__ import annotations

import math
import re
import statistics
from collections import defaultdict
from pathlib import Path

import ezdxf
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

from . import dwg_convert, layer_mapper

CADASTRAL_RE = re.compile(r"\d{2}[:/-]\d{2}[:/-]\d+")


class IngestError(Exception):
    def __init__(self, message, code=None, layers=None):
        super().__init__(message)
        self.code = code
        self.layers = layers or []


def _is_entity(e) -> bool:
    return hasattr(e, "dxf") and hasattr(e, "dxftype")


def _layer_name(e):
    d = getattr(e, "dxf", None)
    return getattr(d, "layer", None)


def _entity_geom(e):
    try:
        t = e.dxftype()
        if t == "LINE":
            return LineString([(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)])
        if t == "LWPOLYLINE":
            pts = [(x, y) for x, y in e.get_points(format="xy")]
            if len(pts) < 2:
                return None
            return Polygon(pts) if (e.closed and len(pts) >= 3) else LineString(pts)
        if t == "POLYLINE":
            pts = []
            for v in (getattr(e, "vertices", None) or []):
                loc = getattr(getattr(v, "dxf", None), "location", None)
                if loc is not None:
                    pts.append((loc.x, loc.y))
            if len(pts) < 2:
                return None
            closed = bool(getattr(e, "is_closed", False))
            return Polygon(pts) if (closed and len(pts) >= 3) else LineString(pts)
        if t == "CIRCLE":
            return Point(e.dxf.center.x, e.dxf.center.y).buffer(e.dxf.radius)
        if t == "INSERT":
            return Point(e.dxf.insert.x, e.dxf.insert.y)
    except Exception:
        return None
    return None


def _layer_stats(entities) -> dict:
    st = {"n": 0, "closed": 0, "long": 0, "circle_small": 0, "areas": [], "blocks": [],
          "text_count": 0, "cadastral_texts": 0}
    for e in entities:
        if not _is_entity(e):
            continue
        try:
            st["n"] += 1
            t = e.dxftype()
            if t == "LINE":
                if math.hypot(e.dxf.end.x - e.dxf.start.x, e.dxf.end.y - e.dxf.start.y) > 20:
                    st["long"] += 1
            elif t in ("LWPOLYLINE", "POLYLINE"):
                closed = bool(getattr(e, "closed", False) or getattr(e, "is_closed", False))
                if closed:
                    st["closed"] += 1
                    g = _entity_geom(e)
                    if g is not None and g.geom_type == "Polygon":
                        st["areas"].append(g.area)
            elif t == "CIRCLE":
                if e.dxf.radius <= 2.0:
                    st["circle_small"] += 1
            elif t == "INSERT":
                nm = getattr(e.dxf, "name", None)
                if nm:
                    st["blocks"].append(nm)
            elif t in ("TEXT", "MTEXT"):
                st["text_count"] += 1
                txt = ""
                try:
                    txt = e.dxf.text if t == "TEXT" else e.text
                except Exception:
                    txt = ""
                if CADASTRAL_RE.search(txt or ""):
                    st["cadastral_texts"] += 1
        except Exception:
            continue
    n = max(1, st["n"])
    st["closed_ratio"] = st["closed"] / n
    st["small_circle_ratio"] = st["circle_small"] / n
    st["long_ratio"] = st["long"] / n
    st["median_area"] = statistics.median(st["areas"]) if st["areas"] else 0.0
    return st


def inspect_layers(path, cfg=None):
    p = Path(path)
    if dwg_convert.is_dwg(p):
        p = dwg_convert.convert_dwg_to_dxf(p, cfg)
    doc = ezdxf.readfile(str(p))
    by_layer = defaultdict(list)
    for e in doc.modelspace():
        nm = _layer_name(e)
        if nm is None:
            continue
        by_layer[nm].append(e)
    out = []
    for layer, ents in by_layer.items():
        st = _layer_stats(ents)
        res = layer_mapper.score_layer(layer, st, (cfg or {}))
        out.append({"layer": layer, "n": st["n"], **res})
    return out


def ingest(paths, cfg: dict, layer_overrides=None) -> dict:
    cfg2 = dict(cfg)
    cfg2["_layer_overrides"] = layer_overrides or {}
    geom, warnings, used, mapping = {}, [], [], {}
    for raw in paths:
        p = Path(raw)
        if not p.is_file():
            raise IngestError(f"Файл не найден: {p}")
        if dwg_convert.is_dwg(p):
            p = dwg_convert.convert_dwg_to_dxf(p, cfg)
        try:
            doc = ezdxf.readfile(str(p))
        except Exception as exc:
            raise IngestError(f"Файл повреждён или не читается как DXF: {p.name} ({exc})")
        used.append(str(p))
        by_layer = defaultdict(list)
        for e in doc.modelspace():
            nm = _layer_name(e)
            if nm is None:
                continue
            by_layer[nm].append(e)
        stats = {layer: _layer_stats(ents) for layer, ents in by_layer.items()}
        rep = layer_mapper.map_all(stats, cfg2)
        mapping.update(rep)
        thr = cfg.get("layer_mapper", {}).get("auto_threshold", 0.55)
        for layer, ents in by_layer.items():
            m = rep.get(layer) or {}
            cat, conf = m.get("category"), m.get("confidence", 0.0)
            if not cat or cat in ("ignore", "survey") or conf < thr:
                if cat not in ("ignore", "survey"):
                    warnings.append(f"Слой «{layer}» не распознан (уверенность {conf}); не использован.")
                continue
            for e in ents:
                if not _is_entity(e):
                    continue
                g = _entity_geom(e)
                if g is None or g.is_empty:
                    continue
                geom.setdefault(cat, []).append(g)
    if not geom:
        raise IngestError(
            "Не найдено распознанных слоёв. Откройте мастер маппинга и назначьте "
            "категории слоям вручную — система запомнит выбор.",
            code="NO_LAYERS", layers=list(mapping.keys()))
    if not any(geom.get(k) for k in ("water_pipe", "gas", "cable", "power_line")):
        warnings.append("Коммуникации не определены: не используем неподтверждённые сети как ограничение.")
    if geom.get("boundary"):
        polys = [g for g in geom["boundary"] if g.geom_type in ("Polygon", "MultiPolygon")]
        boundary = unary_union(polys) if polys else unary_union(list(geom["boundary"])).convex_hull
    else:
        boundary = unary_union([g for lst in geom.values() for g in lst]).convex_hull
        warnings.append("Слой границы не найден: граница = выпуклая оболочка всех объектов.")
    return {"geom": geom, "warnings": warnings, "boundary": boundary,
            "used": used, "mapping": mapping}