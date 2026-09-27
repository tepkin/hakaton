"""Маппинг слоёв: ручные правки -> профиль -> шаблон конфига -> знание -> геометрия.

Ключевые исправления (дефекты 3 и 5):
- НОВАЯ категория survey: слои с кадастровыми/геодезическими номерами
  (50:26:016:0201:1275) больше не становятся «деревьями» или «зданиями».
- Геометрический сигнал «здание» ужесточён: замкнутые контуры ПЛОЩАДЬЮ
  60..20000 м² и БЕЗ кадастровых подписей.
- Авто-обучение геометрией ВЫКЛЮЧено по умолчанию (layer_mapper.auto_learn=false):
  база знаний пополняется только подтверждениями человека -> прогон
  «вход + зерно» воспроизводим байт-в-байт.
"""
from __future__ import annotations

from . import layer_knowledge as LK

CANON = ["boundary", "buildings", "roads", "sidewalks", "water_pipe",
         "gas", "cable", "power_line", "existing_trees", "existing_shrubs",
         "remove_trees", "remove_shrubs", "snow_storage", "survey", "ignore"]

AUTO_THRESHOLD = 0.55


def score_layer(name: str, stats: dict, cfg: dict) -> dict:
    # 0) ручное назначение из мастера маппинга — высший приоритет
    over = cfg.get("_layer_overrides") or {}
    if name in over:
        return {"category": over[name], "confidence": 1.0,
                "reasons": ["категория назначена вручную (мастер маппинга)"]}
    # 1) профиль источника
    prof = LK.get_profile(cfg.get("layer_mapper", {}).get("profile", "default"))
    if name in prof:
        return {"category": prof[name], "confidence": 1.0,
                "reasons": ["профиль: точное совпадение"]}
    # 2) шаблоны имени из конфига
    for cat, subs in (cfg.get("layer_patterns") or {}).items():
        if any(s.lower() in name.lower() for s in subs):
            return {"category": cat, "confidence": 0.9,
                    "reasons": ["шаблон имени: подстрока"]}
    n = LK.normalize(name)
    if not n:
        return {"category": "ignore", "confidence": 1.0,
                "reasons": ["служебное/пустое имя слоя"]}
    # 3) кадастр/геодезия: подписи вида 50:26:016:0201:1275
    cadastral = int(stats.get("cadastral_texts", 0) or 0)
    if cadastral >= 3:
        return {"category": "survey", "confidence": 0.9,
                "reasons": [f"кадастровые/геодезические номера на слое ({cadastral} шт) — "
                            f"не деревья и не здания"]}
    # 4) выученное знание + seed-приоры
    scores, reasons = LK.score_name(name)
    # 5) геометрия (только при отсутствии кадастровых подписей)
    closed = stats.get("closed_ratio", 0.0)
    med = stats.get("median_area", 0.0)
    if closed >= 0.4 and 60.0 <= med <= 20000.0:
        scores["buildings"] = scores.get("buildings", 0.0) + 0.65
        reasons.setdefault("buildings", []).append(
            "геометрия: замкнутые контуры площади здания")
    if stats.get("small_circle_ratio", 0.0) >= 0.6:
        scores["existing_trees"] = scores.get("existing_trees", 0.0) + 0.5
        reasons.setdefault("existing_trees", []).append(
            "геометрия: много малых окружностей (кроны)")
    if not scores:
        return {"category": None, "confidence": 0.0, "reasons": ["сигналы не найдены"]}
    best = max(scores, key=scores.get)
    return {"category": best, "confidence": round(min(1.0, scores[best]), 2),
            "reasons": reasons[best]}


def map_all(stats_by_layer: dict, cfg: dict) -> dict:
    out = {}
    auto_learn = bool(cfg.get("layer_mapper", {}).get("auto_learn", False))
    for layer, st in stats_by_layer.items():
        m = score_layer(layer, st, cfg)
        out[layer] = m
        if (auto_learn and m["confidence"] < AUTO_THRESHOLD
                and m["category"] not in (None, "ignore", "survey")):
            gcat = _geo_label(st)
            if gcat:
                LK.learn(layer, gcat, source="auto", confidence=0.5)
    return out


def _geo_label(stats: dict):
    if stats.get("cadastral_texts"):
        return None
    if stats.get("small_circle_ratio", 0.0) >= 0.6:
        return "existing_trees"
    if stats.get("closed_ratio", 0.0) >= 0.4 and 60.0 <= stats.get("median_area", 0.0) <= 20000.0:
        return "buildings"
    return None


# совместимость со старыми вызовами
def load_profiles() -> dict:
    return {"default": dict(LK.load()["profiles"].get("default", {}))}


def save_profile(name: str, mapping: dict):
    LK.set_profile(name, mapping)