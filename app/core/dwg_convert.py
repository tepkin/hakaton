"""Конвертация DWG -> DXF через LibreDWG (dwg2dxf). ВСТРОЕН в продукт.

Порядок поиска конвертера:
  1) tools/dwg2dxf.exe (Windows) / tools/dwg2dxf (Linux) — встроен в продукт;
  2) путь из конфига dwg.converter_path;
  3) системный PATH.
ODA File Converter НЕ используется.
Результат кэшируется по hash файла (повторно не конвертируется).
"""
from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = ROOT / "tools"


class DwgConvertError(RuntimeError):
    """Не удалось сконвертировать DWG в DXF."""


def find_dwg2dxf(cfg: dict | None = None) -> Path | None:
    """Найти dwg2dxf: tools/ -> конфиг -> PATH. Без ODA."""
    # 1) встроенный в продукт
    for name in ("dwg2dxf.exe", "dwg2dxf"):
        p = TOOLS_DIR / name
        if p.is_file():
            return p
    # 2) путь из конфига
    cfg_path = (cfg or {}).get("dwg", {}).get("converter_path", "")
    if cfg_path and Path(cfg_path).is_file():
        return Path(cfg_path)
    # 3) системный PATH
    for name in ("dwg2dxf.exe", "dwg2dxf"):
        p = shutil.which(name)
        if p:
            return Path(p)
    return None


def is_dwg(path) -> bool:
    """DWG по расширению или по сигнатуре 'AC10'."""
    p = Path(path)
    if p.suffix.lower() == ".dwg":
        return True
    try:
        with open(p, "rb") as f:
            return f.read(4) == b"AC10"
    except OSError:
        return False


def _file_hash(path: Path) -> str:
    h = hashlib.sha1()
    h.update(str(path.stat().st_size).encode())
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


def convert_dwg_to_dxf(dwg_path, cfg: dict | None = None, cache_dir=None) -> Path:
    """Конвертировать DWG в DXF (кэш по hash). Вернуть путь к DXF."""
    dwg = Path(dwg_path)
    if not dwg.is_file():
        raise DwgConvertError(f"Файл не найден: {dwg}")

    cache = Path(cache_dir or "out/dwg_cache")
    cache.mkdir(parents=True, exist_ok=True)
    out = cache / (dwg.stem + "_" + _file_hash(dwg) + ".dxf")
    if out.is_file() and out.stat().st_size > 0:
        return out

    exe = find_dwg2dxf(cfg)
    if not exe:
        raise DwgConvertError(
            "Конвертер dwg2dxf (LibreDWG) не найден.\n"
            "1) Скачайте: https://github.com/LibreDWG/LibreDWG/releases/download/v0.14.8597/libredwg-0.14.8597-win64.zip\n"
            "2) Распакуйте dwg2dxf.exe и DLL в папку tools/ проекта.\n"
            "3) Либо укажите путь в конфиге: dwg.converter_path."
        )

    try:
        res = subprocess.run(
            [str(exe), "-y", "-o", str(out), str(dwg)],
            capture_output=True, text=True, timeout=600,
        )
    except subprocess.TimeoutExpired:
        raise DwgConvertError(f"dwg2dxf работал слишком долго (>600 с): {dwg.name}")

    if res.returncode != 0 or not out.is_file() or out.stat().st_size == 0:
        raise DwgConvertError(
            f"dwg2dxf не смог конвертировать {dwg.name} (код {res.returncode}).\n"
            f"stderr: {(res.stderr or '').strip()[:300]}\n"
            f"Возможно, версия DWG слишком новая. Попробуйте экспортировать DXF из CAD вручную."
        )

    return out


# Алиас для совместимости со старыми вызовами
convert_to_dxf = convert_dwg_to_dxf