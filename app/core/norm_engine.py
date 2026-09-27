"""Нормативный движок: буферы отступов и допустимые зоны.

Дополнительно: зоны снежных хранилищ (snow_storage) исключаются из допустимых
(бизнес-логика: снегосклады и проезд снегоуборочной техники).
"""
from __future__ import annotations

from shapely.geometry import Polygon
from shapely.ops import unary_union


def setback_distance(norm: dict, ptype: str, policy: str) -> float:
    lo, hi = norm[ptype]
    return hi if policy == "max" else lo


def build_zones(geom: dict, boundary, norms: dict, cfg: dict) -> dict:
    policy = cfg["run"]["range_policy"]
    tree_bufs, shrub_bufs, applied = [], [], []
    for norm in norms["setbacks"]:
        objs = geom.get(norm["key"], [])
        if not objs:
            continue
        dt, ds = setback_distance(norm, "tree", policy), setback_distance(norm, "shrub", policy)
        tree_bufs += [g.buffer(dt) for g in objs]
        shrub_bufs += [g.buffer(ds) for g in objs]
        applied.append({"key": norm["key"], "label": norm["label"],
                        "tree_m": dt, "shrub_m": ds,
                        "npa": norm["npa"], "clause": norm["clause"]})
    empty = Polygon()
    forbidden = unary_union(tree_bufs) if tree_bufs else empty
    forbidden_shrub = unary_union(shrub_bufs) if shrub_bufs else forbidden
    # снежные хранилища -> запрет для всех типов
    snow = geom.get("snow_storage", [])
    if snow:
        snow_u = unary_union([g.buffer(0.5) for g in snow])
        forbidden = unary_union([forbidden, snow_u]) if not forbidden.is_empty else snow_u
        forbidden_shrub = unary_union([forbidden_shrub, snow_u]) if not forbidden_shrub.is_empty else snow_u
        applied.append({"key": "snow_storage", "label": "Снежные хранилища / проезд техники",
                        "tree_m": 0, "shrub_m": 0, "npa": "бизнес-логика заказчика",
                        "clause": "снегосклады и проезд снегоуборочной техники исключаются"})
    allowed_trees = boundary.difference(forbidden)
    allowed_shrubs = boundary.difference(forbidden_shrub)
    shrub_only = allowed_shrubs.difference(allowed_trees)
    return {"allowed_trees": allowed_trees, "allowed_shrubs": allowed_shrubs,
            "shrub_only": shrub_only, "forbidden": forbidden, "applied": applied}