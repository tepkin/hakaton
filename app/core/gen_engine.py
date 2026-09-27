"""Генератор посадок: воспроизводимая расстановка точек в допустимых зонах.

Каждая сгенерированная посадка сразу получает status="approved",
чтобы смета/бюджет корректно считались до этапа интерпретаций.
"""
from __future__ import annotations

import random

from shapely.geometry import Point


def _sample(polygon, min_dist, rnd, max_points, max_tries=20000):
    if polygon.is_empty:
        return []
    minx, miny, maxx, maxy = polygon.bounds
    pts, tries = [], 0
    while len(pts) < max_points and tries < max_tries:
        tries += 1
        p = Point(rnd.uniform(minx, maxx), rnd.uniform(miny, maxy))
        if not polygon.contains(p):
            continue
        if all(p.distance(q) >= min_dist for q in pts):
            pts.append(p)
    return pts


def _pool(catalog, ptype, territory, near_water, near_road):
    base = [s for s in catalog["species"]
            if s["type"] == ptype and territory in s["territories"]]
    if near_water:
        water = [s for s in base if "water" in s["tags"]]
        if water:
            base = water + [s for s in base if s not in water]
    if near_road:
        dust = [s for s in base if "dust" in s["tags"] or "noise" in s["tags"]]
        if dust:
            base = dust + [s for s in base if s not in dust]
    return base


def generate(geom, zones, boundary, norms, cfg, catalog) -> dict:
    g = cfg["gen"]
    rnd = random.Random(cfg["run"]["seed"])
    territory = cfg["project"]["territory_type"]
    roads = geom.get("roads", [])
    water = geom.get("water_pipe", []) + geom.get("gas", [])
    plantings, rejected = [], []

    t_pts = _sample(zones["allowed_trees"], g["tree_spacing"], rnd, g["max_trees"])
    pool_t = _pool(catalog, "tree", territory, False, bool(roads))
    for i, p in enumerate(t_pts):
        if not pool_t:
            break
        plantings.append({"id": f"T-{i+1:03d}", "type": "tree",
                          "x": round(p.x, 2), "y": round(p.y, 2),
                          "species": pool_t[i % len(pool_t)],
                          "root_protection": False, "status": "approved", "notes": []})

    s_pts = _sample(zones["allowed_shrubs"], g["shrub_spacing"], rnd, g["max_shrubs"])
    pool_s = _pool(catalog, "shrub", territory, bool(water), bool(roads))
    j = 0
    for p in s_pts:
        if any(p.distance(t) < g["tree_shrub_min"] for t in t_pts):
            continue
        if not pool_s:
            break
        j += 1
        over = zones["shrub_only"].contains(p)
        plantings.append({"id": f"S-{j:03d}", "type": "shrub",
                          "x": round(p.x, 2), "y": round(p.y, 2),
                          "species": pool_s[j % len(pool_s)],
                          "root_protection": bool(over), "status": "approved",
                          "notes": (["Корнезащита: зона над коммуникациями"] if over else [])})

    rnd2 = random.Random(cfg["run"]["seed"] + 99)
    while len(rejected) < 3:
        p = Point(rnd2.uniform(boundary.bounds[0], boundary.bounds[2]),
                  rnd2.uniform(boundary.bounds[1], boundary.bounds[3]))
        if zones["allowed_trees"].contains(p):
            continue
        for norm in norms["setbacks"]:
            objs = geom.get(norm["key"], [])
            if not objs:
                continue
            d = min(p.distance(o) for o in objs)
            if d < norm["tree"][0]:
                rejected.append({"id": f"REJ-{len(rejected)+1:03d}", "type": "tree",
                                 "species": None, "x": round(p.x, 2), "y": round(p.y, 2),
                                 "status": "rejected",
                                 "checks": [{"obstacle": norm["label"], "required_m": norm["tree"][0],
                                             "actual_m": round(d, 2), "ok": False,
                                             "npa": norm["npa"], "clause": norm["clause"]}],
                                 "notes": ["Кандидат отклонён: нарушен нормативный отступ"]})
                break
    return {"plantings": plantings, "rejected": rejected}