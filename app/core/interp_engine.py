"""Интерпретируемость: причина и нормативное основание по каждой посадке (БТ-1..3)."""
from __future__ import annotations
from shapely.geometry import Point

def _checks(p: Point, ptype: str, geom: dict, norms: dict):
    checks = []
    for norm in norms["setbacks"]:
        objs = geom.get(norm["key"], [])
        req = norm[ptype][0]
        actual = min((p.distance(g) for g in objs), default=None)
        checks.append({"obstacle": norm["label"], "required_m": req,
                       "actual_m": None if actual is None else round(actual, 2),
                       "ok": True if actual is None else actual >= req - 1e-9,
                       "npa": norm["npa"], "clause": norm["clause"]})
    fr = norms["front"]
    roads = geom.get("roads", [])
    actual = min((p.distance(g) for g in roads), default=None)
    checks.append({"obstacle": "Уличный фронт", "required_m": fr["min_m"],
                   "actual_m": None if actual is None else round(actual, 2),
                   "ok": True if actual is None else actual >= fr["min_m"] - 1e-9,
                   "npa": fr["npa"], "clause": fr["clause"]})
    return checks

def build(plantings, rejected, geom, norms, cfg) -> list:
    out = []
    for pl in plantings:
        p = Point(pl["x"], pl["y"])
        checks = _checks(p, pl["type"], geom, norms)
        ok_all = all(c["ok"] for c in checks)
        same = [q for q in plantings if q["id"] != pl["id"] and q["type"] == pl["type"]]
        if same:
            d = min(p.distance(Point(q["x"], q["y"])) for q in same)
            key = "tree_tree" if pl["type"] == "tree" else "shrub_shrub"
            req = norms["spacing"][key][0]
            ok = d >= req - 1e-9
            ok_all &= ok
            checks.append({"obstacle": "Расстояние до ближайшего同 типа", "required_m": req,
                           "actual_m": round(d, 2), "ok": ok,
                           "npa": "СП 42.13330.2016", "clause": "п. 9.3 (шаги посадки)"})
        notes = list(pl.get("notes", []))
        if pl.get("root_protection"):
            notes.append("Зона над подземными сетями: кустарник с корнезащитой")
        out.append({"id": pl["id"], "type": pl["type"], "species": pl["species"]["name"],
                    "latin": pl["species"]["latin"], "value_code": pl["species"]["value_code"],
                    "x": pl["x"], "y": pl["y"],
                    "status": "approved" if ok_all else "rejected",
                    "checks": checks, "notes": notes})
    out.extend(rejected)
    return out