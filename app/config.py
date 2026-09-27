"""Конфигурация: дефолты + переопределения; гарантирует секцию dwg."""
from __future__ import annotations
import copy, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

_DEFAULT_DWG = {"converter_path": ""}


def load_json(name: str) -> dict:
    with open(DATA_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def default_config() -> dict:
    return load_json("config.default.json")


def _deep_merge(base: dict, over: dict) -> dict:
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def load_config(path=None, overrides=None) -> dict:
    cfg = default_config()
    if path:
        with open(path, encoding="utf-8") as f:
            _deep_merge(cfg, json.load(f))
    if overrides:
        _deep_merge(cfg, overrides)
    dwg = cfg.setdefault("dwg", copy.deepcopy(_DEFAULT_DWG))
    dwg.setdefault("converter_path", "")
    cfg.setdefault("layer_aliases", {})
    return cfg


def norms() -> dict: return load_json("norms.json")
def costs() -> dict: return load_json("costs.json")
def catalog() -> dict: return load_json("plant_catalog.json")