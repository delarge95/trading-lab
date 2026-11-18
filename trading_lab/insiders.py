"""Clasificación rutinario vs oportunista (Cohen, Malloy y Pomorski, 2012).

Un insider es *rutinario* si operó en el mismo mes calendario en cada uno de los 3 años
anteriores; el resto son *oportunistas*. Solo las compras oportunistas tienen señal.
Si el insider no tiene al menos ~3 años de historia en los datos, la compra queda como
"indeterminado" (no se asume oportunista).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta


def _d(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def label_trade(trade: dict, owner_trades: list[dict]) -> str:
    td = _d(trade["date"])
    prior = [_d(h["date"]) for h in owner_trades if h["date"] and _d(h["date"]) < td]
    first = min(prior, default=td)
    if (td - first).days < 3 * 365 - 31:
        return "indeterminado"
    same_month_years = {d.year for d in prior if d.month == td.month}
    if all(td.year - k in same_month_years for k in (1, 2, 3)):
        return "rutinario"
    return "oportunista"


def classify(trades: list[dict], window_days: int = 90, today: date | None = None) -> dict:
    today = today or date.today()
    since = today - timedelta(days=window_days)
    by_owner = defaultdict(list)
    for t in trades:
        if t["date"]:
            by_owner[t["owner_cik"] or t["owner"]].append(t)

    buys = []
    for ts in by_owner.values():
        for t in ts:
            if t["code"] == "P" and _d(t["date"]) >= since:
                buys.append({**t, "class": label_trade(t, ts)})
    buys.sort(key=lambda t: t["value"], reverse=True)
    sells = [t for t in trades if t["code"] == "S" and t["date"] and _d(t["date"]) >= since]
    count = lambda c: sum(1 for b in buys if b["class"] == c)  # noqa: E731
    return {
        "window_days": window_days,
        "n_buys": len(buys),
        "routine": count("rutinario"), "opportunistic": count("oportunista"),
        "unclassified": count("indeterminado"),
        "buy_value": sum(b["value"] for b in buys),
        "opportunistic_value": sum(b["value"] for b in buys if b["class"] == "oportunista"),
        "sell_value": sum(t["value"] for t in sells),
        "buys": buys[:10],
    }
