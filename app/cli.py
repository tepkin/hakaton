"""CLI GreenPlan AI: run / doctor / serve. Печатает traceback при ошибках."""
from __future__ import annotations

import argparse
import json
import sys
import traceback


def _overrides(a) -> dict:
    over = {}
    if getattr(a, "seed", None) is not None:
        over.setdefault("run", {})["seed"] = a.seed
    if getattr(a, "territory", None):
        over.setdefault("project", {})["territory_type"] = a.territory
    b = {}
    if getattr(a, "budget_mode", None):
        b["mode"] = a.budget_mode
    if getattr(a, "budget_value", None) is not None:
        b["manual_value_mln"] = a.budget_value
    if getattr(a, "budget_policy", None):
        b["policy"] = a.budget_policy
    if b:
        over["budget"] = b
    return over


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="greenplan",
        description="Генератор плана озеленения: DXF/DWG -> план на отдельных слоях + обоснования по НПА")
    sub = p.add_subparsers(dest="cmd")

    r = sub.add_parser("run", help="прогон расчёта")
    r.add_argument("inputs", nargs="+", help="входные DXF/DWG")
    r.add_argument("--config")
    r.add_argument("--out", default="out")
    r.add_argument("--seed", type=int, help="вариант расчёта (число для воспроизводимости)")
    r.add_argument("--territory", help="тип территории T1..T8")
    r.add_argument("--budget-mode", choices=["tsn_norm", "manual", "unlimited"])
    r.add_argument("--budget-value", type=float, help="бюджет вручную, млн ₽")
    r.add_argument("--budget-policy", choices=["warn", "optimize", "strict"])

    d = sub.add_parser("doctor", help="проверка окружения и конвертера DWG")
    d.add_argument("--config")

    s = sub.add_parser("serve", help="локальный веб-интерфейс")
    s.add_argument("--config")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)

    a = p.parse_args(argv)
    from . import config as cfgmod

    if a.cmd == "doctor":
        from .core import dwg_convert
        cfg = cfgmod.load_config(getattr(a, "config", None))
        print(f"Python: {sys.version.split()[0]}")
        for m in ("ezdxf", "shapely", "fastapi", "uvicorn"):
            try:
                __import__(m); print(f"  [ok] {m}")
            except Exception:
                print(f"  [MISSING] {m}")
        exe = dwg_convert.find_dwg2dxf(cfg)
        if exe:
            print(f"  [ok] конвертер DWG: {exe}")
        else:
            print("  [warn] конвертер DWG не найден (положите dwg2dxf.exe и DLL в tools/)")
        return 0

    if a.cmd == "serve":
        import uvicorn
        from .web.server import create_app
        uvicorn.run(create_app(cfgmod.load_config(getattr(a, "config", None))),
                    host=a.host, port=a.port)
        return 0

    if a.cmd == "run":
        from .core import pipeline
        cfg = cfgmod.load_config(getattr(a, "config", None), _overrides(a))
        try:
            summary = pipeline.run(a.inputs, cfg, a.out)
        except Exception:
            traceback.print_exc()
            return 1
        print(json.dumps({k: v for k, v in summary.items() if k not in ("geo", "plantings")},
                         ensure_ascii=False, indent=2))
        print("Результаты в папке:", a.out)
        return 0

    p.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())