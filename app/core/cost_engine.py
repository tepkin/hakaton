"""Смета: стоимости по кодам ценности, работы, удобрения, коэффициенты."""
from __future__ import annotations

def _vcode(pl):
    if pl.get("value_code") is not None: return str(pl["value_code"])
    sp = pl.get("species") or {}
    return str(sp.get("value_code")) if sp.get("value_code") is not None else None

def estimate(plantings, costs: dict, area_ha: float) -> dict:
    up = costs["unit_price"]
    counts, materials, fert = {}, 0.0, 0.0
    n_trees = n_shrubs = 0
    for pl in plantings:
        if pl.get("status") != "approved": continue
        code = _vcode(pl)
        counts[code] = counts.get(code, 0) + 1
        materials += up.get(code, 0.0)
        fert += costs["fertilizer"][f"{pl['type']}_kg_per_pc"]
        if pl["type"] == "tree": n_trees += 1
        else: n_shrubs += 1
    works = n_trees * costs["works"]["tree_pc"] + n_shrubs * costs["works"]["shrub_pc"]
    subtotal = materials + works
    total = round(subtotal * costs["coeffs"]["design"], 2)
    return {"counts": counts, "n_trees": n_trees, "n_shrubs": n_shrubs,
            "materials": round(materials, 2), "works": works,
            "fertilizer_kg": round(fert, 2), "subtotal": round(subtotal, 2),
            "total": total, "area_ha": round(area_ha, 3)}