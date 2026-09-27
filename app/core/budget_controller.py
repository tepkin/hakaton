"""Бюджет: лимит (ТСН / вручную / без лимита) и политики warn / optimize / strict.

- evaluate()      — статус бюджета для готовой сметы (ничего не меняет);
- optimize()      — снятие самых дорогих посадок до входа в <=95% лимита;
- apply_budget()  — применение политики к посадкам генератора;
                    при strict и превышении возвращает plantings=None (blocked),
                    чтобы UI показал карточку, а не сырую ошибку.
"""
from __future__ import annotations

from . import cost_engine


class BudgetError(Exception):
    """Служебное исключение (ручные вызовы)."""


def _vcode(p):
    """Код ценности посадки: поддерживает interp-записи и записи генератора."""
    if p.get("value_code") is not None:
        return str(p["value_code"])
    sp = p.get("species") or {}
    return str(sp.get("value_code")) if sp.get("value_code") is not None else None


def limit_value(cfg, costs, area_ha):
    """Лимит бюджета в рублях по режиму (ТСН / вручную / без лимита)."""
    b = cfg.get("budget", {})
    mode = b.get("mode", "tsn_norm")
    if mode == "unlimited":
        return None
    if mode == "manual":
        v = float(b.get("manual_value_mln", 0) or 0) * 1_000_000
        return v * area_ha if b.get("manual_unit") == "mln_per_ha" else v
    _, hi = costs["tsn_budget"]["street_district_per_ha"]
    return hi * area_ha


def evaluate(total, cfg, costs, area_ha) -> dict:
    """Статус бюджета для готовой сметы: within / over / unlimited (+ message)."""
    policy = cfg.get("budget", {}).get("policy", "warn")
    lim = limit_value(cfg, costs, area_ha)
    info = {"limit": lim, "policy": policy, "total": total}
    if lim is None:
        info.update(status="unlimited", usage_pct=None)
        return info
    usage = total / lim * 100
    if total <= lim:
        info.update(status="within", usage_pct=round(usage, 1))
        return info
    info.update(status="over", usage_pct=round(usage, 1),
                message=(f"Смета {total:,.0f} ₽ превышает лимит {lim:,.0f} ₽ "
                         f"(политика «{policy}»)."))
    return info


def optimize(plantings, costs, cfg, area_ha, estimate_fn=None):
    """Политика optimize: снимать самые дорогие посадки до <=95% лимита."""
    est_fn = estimate_fn or cost_engine.estimate
    lim = limit_value(cfg, costs, area_ha)
    removed = []
    if lim is None:
        return plantings, removed
    up = costs["unit_price"]
    while est_fn(plantings, costs, area_ha)["total"] > lim * 0.95:
        approved = [p for p in plantings if p.get("status") == "approved"]
        if not approved:
            break
        victim = max(approved, key=lambda p: up.get(_vcode(p) or "5", 0))
        victim["status"] = "rejected"
        victim["notes"] = victim.get("notes", []) + ["Снято политикой бюджета (автоподбор)"]
        removed.append(victim["id"])
    return plantings, removed


def apply_budget(plantings, costs, cfg, area_ha, estimate_fn=None):
    """Вернёт (plantings|None, removed, estimate, budget_info).

    plantings=None означает blocked (политика strict при превышении лимита).
    """
    est_fn = estimate_fn or cost_engine.estimate
    policy = cfg.get("budget", {}).get("policy", "warn")
    lim = limit_value(cfg, costs, area_ha)
    est = est_fn(plantings, costs, area_ha)
    info = {"limit": lim, "policy": policy, "total": est["total"]}

    if lim is None:
        info.update(status="unlimited", usage_pct=None)
        return plantings, [], est, info

    usage = est["total"] / lim * 100
    if est["total"] <= lim:
        info.update(status="within", usage_pct=round(usage, 1))
        return plantings, [], est, info

    # превышение лимита:
    if policy == "optimize":
        plantings, removed = optimize(plantings, costs, cfg, area_ha, est_fn)
        est = est_fn(plantings, costs, area_ha)
        over = est["total"] > lim
        info.update(status="over" if over else "within",
                    usage_pct=round(est["total"] / lim * 100, 1), removed=removed)
        if over:
            info["message"] = (f"После автоподбора смета {est['total']:,.0f} ₽ всё ещё "
                               f"превышает лимит {lim:,.0f} ₽.")
        return plantings, removed, est, info

    if policy == "strict":
        info.update(status="blocked", usage_pct=round(usage, 1),
                    message=(f"Смета {est['total']:,.0f} ₽ превышает лимит {lim:,.0f} ₽. "
                             f"Расчёт заблокирован политикой «Блокировать». "
                             f"Увеличьте бюджет или выберите политику «Автоподбор» / «Предупреждать»."))
        return None, [], est, info

    # warn
    info.update(status="over", usage_pct=round(usage, 1),
                message=(f"Смета превышает лимит на {est['total'] - lim:,.0f} ₽ "
                         f"(политика «Предупреждать»): результат сформирован, проверьте бюджет."))
    return plantings, [], est, info