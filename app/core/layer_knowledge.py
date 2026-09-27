"""Живая база знаний о слоях DXF: обучаемое обогащение вместо жёсткого словаря.

Хранилище data/layer_knowledge.json:
  tokens   — токен -> {категория: вес}   (учится из имён);
  examples — корпус помеченных имён      (поиск ближайших по похожести);
  profiles — точные маппинги по источникам (подтверждения человека).
События обучения:
  human — подтверждение/правка в UI (вес 1.0, пишется и в профиль);
  auto  — геометрическая слабая разметка слоя, не узнанного по имени (вес 0.5).
SEED — холодный старт (бывший словарь) с меньшим весом, чем выученное.
"""
from __future__ import annotations

import difflib
import json

from .. import config as cfgmod

SEED = {
    "boundary": ["границ", "участок работ"],
    "buildings": ["здани", "строени", "building"],
    "roads": ["проезж", "трамвай", "дорожн", "road", "street", "улиц"],
    "sidewalks": ["тротуар", "пешеход", "sidewalk", "дтс"],
    "water_pipe": ["водопровод", "канализ", "теплосет", "water", "sew", "heat", "вк"],
    "gas": ["газопровод", "газ", "gas"],
    "cable": ["кабел", "связ", "cable", "провод"],
    "power_line": ["лэп", "электр", "power", "воздушн"],
    "existing_trees": ["дерев", "tree", "листвен", "хвойн", "дендр", "сохран", "растени", "посадк"],
    "existing_shrubs": ["кустар", "shrub", "поросль"],
    "remove_trees": ["выруб", "удален", "удаление"],
    "snow_storage": ["снег", "snow"],
    "ignore": ["defpoints", "logo", "лого", "условн", "обознач", "мульча", "группа",
               "размеры", "местности", "борт", "участки", "подоснова", "лист",
               "штамп", "рамка", "оси", "сетка", "выноск", "аннот", "надпис",
               "эксплик", "ведомост"],
}

_PATH = None


def _path():
    global _PATH
    if _PATH is None:
        _PATH = cfgmod.DATA_DIR / "layer_knowledge.json"
    return _PATH


def load() -> dict:
    p = _path()
    if p.exists():
        try:
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"tokens": {}, "examples": [], "profiles": {}}


def save(k: dict):
    with open(_path(), "w", encoding="utf-8") as f:
        json.dump(k, f, ensure_ascii=False, indent=2)


def normalize(s: str) -> str:
    n = s.lower().replace("ё", "е")
    for ch in "-_.":
        n = n.replace(ch, " ")
    n = n.strip()
    while n[:1].isdigit():
        n = n[1:].strip()
    return " ".join(n.split())


def learn(name: str, category: str, source: str = "human",
          confidence: float = 1.0, profile: str = "default"):
    k = load()
    toks = normalize(name).split()
    w = confidence if source == "human" else confidence * 0.5
    for t in toks:
        d = k["tokens"].setdefault(t, {})
        d[category] = min(3.0, d.get(category, 0.0) + w)
    if source == "human":
        k["profiles"].setdefault(profile, {})[name] = category
    ex = [e for e in k["examples"] if e["name"] != name]
    ex.append({"name": name, "category": category, "source": source,
               "confidence": confidence})
    k["examples"] = ex[-500:]
    save(k)


def set_profile(profile: str, mapping: dict):
    k = load()
    k["profiles"].setdefault(profile, {}).update(mapping)
    save(k)


def get_profile(profile: str) -> dict:
    return load()["profiles"].get(profile, {})


def score_name(name: str):
    k = load()
    n = normalize(name)
    scores, reasons = {}, {}

    def add(cat, w, why):
        if w <= 0:
            return
        scores[cat] = scores.get(cat, 0.0) + w
        reasons.setdefault(cat, []).append(why)

    for cat, toks in SEED.items():
        hit = [t for t in toks if t in n]
        if hit:
            add(cat, 0.55, f"приор: «{hit[0]}»")
    for tok in n.split():
        for cat, w in (k["tokens"].get(tok) or {}).items():
            add(cat, min(w, 3.0) * 0.35, f"токен «{tok}» ({round(min(w, 3.0), 2)})")
    for ex in k["examples"][-300:]:
        sim = difflib.SequenceMatcher(None, n, normalize(ex["name"])).ratio()
        if sim >= 0.55:
            add(ex["category"], 0.5 * sim,
                f"похож на пример «{ex['name']}» ({round(sim, 2)})")
    return scores, reasons


def auto_label(stats: dict):
    n = max(1, stats.get("n", 0))
    ins = stats.get("insert", 0) / n
    if stats.get("small_circle_ratio", 0) >= 0.6 or (ins >= 0.6 and stats.get("small_circle_ratio", 0) >= 0.3):
        return "existing_trees", 0.8, "геометрия: точечные объекты/окружности (кроны/стволы)"
    if stats.get("closed_ratio", 0) >= 0.6 and stats.get("median_area", 0) >= 80:
        return "buildings", 0.8, "геометрия: замкнутые контуры большой площади"
    return None, 0.0, ""