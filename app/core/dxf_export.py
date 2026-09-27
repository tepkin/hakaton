"""Экспорт результата в DXF на отдельных слоях; исходные слои не изменяются.

Устойчив к «битым» DXF после конвертации DWG: если исходный документ нельзя
сохранить (повреждённая секция MATERIALS и т.п.), формируем чистый DXF только
со слоями результата и возвращаем понятное предупреждение (без тех. деталей).
"""
from __future__ import annotations

import ezdxf

_DEF_EXPORT = {"tree_radius": 3.0, "shrub_radius": 1.0, "text_height": 1.0}
_DEF_LAYERS = {"trees": "GREEN_AI_TREES", "shrubs": "GREEN_AI_SHRUBS",
               "zones_allowed": "GREEN_AI_ZONES_ALLOWED",
               "zones_forbidden": "GREEN_AI_ZONES_FORBIDDEN"}

_FALLBACK_NOTE = ("Исходный чертёж содержит служебные данные, несовместимые с сохранением поверх. "
                  "Сформирован отдельный DXF только со слоями результата (деревья, кустарники, зоны) — "
                  "наложите его поверх геоподосновы в CAD.")


class ExportError(Exception):
    """Ошибка формирования DXF."""


def _ensure_layers(doc, L):
    for name, color in ((L["trees"], 3), (L["shrubs"], 6),
                        (L["zones_allowed"], 4), (L["zones_forbidden"], 1)):
        if name not in doc.layers:
            doc.layers.add(name, color=color)


def _add_result_entities(msp, interp, zones, L, r):
    n = 0
    for p in interp:
        if p.get("status") != "approved":
            continue
        layer = L["trees"] if p["type"] == "tree" else L["shrubs"]
        radius = r["tree_radius"] if p["type"] == "tree" else r["shrub_radius"]
        msp.add_circle((p["x"], p["y"]), radius, dxfattribs={"layer": layer})
        t = msp.add_text(p["id"], height=r["text_height"], dxfattribs={"layer": layer})
        t.dxf.insert = (p["x"] + radius * 0.7, p["y"] + radius * 0.7, 0)
        n += 1
    for geom, layer in ((zones["allowed_trees"], L["zones_allowed"]),
                        (zones["forbidden"], L["zones_forbidden"])):
        if geom is None or geom.is_empty:
            continue
        polys = geom.geoms if geom.geom_type == "MultiPolygon" else [geom]
        for poly in polys:
            msp.add_lwpolyline(list(poly.exterior.coords), close=True,
                               dxfattribs={"layer": layer})
    return n


def _repair_materials(doc):
    try:
        mt = doc.materials
        for name in ("ByLayer", "ByBlock", "Global"):
            entry = mt.get(name)
            if entry is None or not hasattr(entry, "dxf"):
                try:
                    mt.add(name)
                except Exception:
                    pass
    except Exception:
        pass


def export(src_path, out_path, interp, zones, cfg):
    """Вернёт (out_path, warnings)."""
    warnings = []
    L = {**_DEF_LAYERS, **(cfg.get("layers") or {})}
    r = {**_DEF_EXPORT, **(cfg.get("export") or {})}
    try:
        doc = ezdxf.readfile(src_path)
        _ensure_layers(doc, L)
        _add_result_entities(doc.modelspace(), interp, zones, L, r)
        _repair_materials(doc)
        doc.saveas(out_path)
        return out_path, warnings
    except Exception:
        warnings.append(_FALLBACK_NOTE)
    doc = ezdxf.new(dxfversion="R2010")
    _ensure_layers(doc, L)
    _add_result_entities(doc.modelspace(), interp, zones, L, r)
    doc.saveas(out_path)
    return out_path, warnings