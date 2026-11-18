"""Registro de predicciones y evaluación a su vencimiento (seguimiento de aciertos)."""
from __future__ import annotations

import csv
from datetime import date, datetime, timedelta
from pathlib import Path

FIELDS = ["date", "ticker", "horizon_days", "target_date", "p_up", "p_lo", "p_hi", "basis",
          "price", "status", "outcome_price", "went_up", "brier"]


def _load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _save(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def _target_date(d: date, horizon_ruedas: int) -> date:
    """Fecha calendario aproximada de `horizon_ruedas` ruedas después (7 días por 5 ruedas)."""
    return d + timedelta(days=round(horizon_ruedas * 7 / 5))


def record(path: Path, ticker: str, summary: dict, today: date | None = None) -> bool:
    """Registra la predicción del día; devuelve False si ya existía (misma fecha y ticker)."""
    today = today or date.today()
    pu = summary["prob_up"]
    if pu["p_cond"] is not None and pu["n_cond"] >= 20:
        p, (lo, hi), basis = pu["p_cond"], pu["ci_cond"], "condicional_momentum"
    elif pu["p_all"] is not None:
        p, (lo, hi), basis = pu["p_all"], pu["ci_all"], "incondicional"
    else:
        return False
    rows = _load(path)
    if any(r["date"] == today.isoformat() and r["ticker"] == ticker for r in rows):
        return False
    rows.append({
        "date": today.isoformat(), "ticker": ticker, "horizon_days": pu["horizon"],
        "target_date": _target_date(today, pu["horizon"]).isoformat(),
        "p_up": f"{p:.4f}", "p_lo": f"{lo:.4f}", "p_hi": f"{hi:.4f}", "basis": basis,
        "price": f"{summary['last_price']:.4f}", "status": "abierta",
        "outcome_price": "", "went_up": "", "brier": "",
    })
    _save(path, rows)
    return True


def evaluate(path: Path, prices_by_ticker: dict[str, list[tuple[str, float]]],
             today: date | None = None) -> dict:
    """Cierra las predicciones vencidas usando el primer precio en/después de la fecha objetivo."""
    today = today or date.today()
    rows = _load(path)
    for r in rows:
        if r["status"] != "abierta" or datetime.strptime(r["target_date"], "%Y-%m-%d").date() > today:
            continue
        series = prices_by_ticker.get(r["ticker"])
        if not series:
            continue
        later = [p for d, p in series if d >= r["target_date"]]
        if not later:
            continue
        out = later[0]
        up = out > float(r["price"])
        r.update(status="cerrada", outcome_price=f"{out:.4f}", went_up=str(int(up)),
                 brier=f"{(float(r['p_up']) - up) ** 2:.4f}")
    _save(path, rows)
    return scoreboard(rows)


def scoreboard(rows: list[dict]) -> dict:
    closed = [r for r in rows if r["status"] == "cerrada"]
    open_n = sum(1 for r in rows if r["status"] == "abierta")
    if not closed:
        return {"closed": 0, "open": open_n}
    brier = sum(float(r["brier"]) for r in closed) / len(closed)
    base = sum(int(r["went_up"]) for r in closed) / len(closed)
    brier_base = sum((base - int(r["went_up"])) ** 2 for r in closed) / len(closed)
    hits = sum(1 for r in closed if (float(r["p_up"]) >= 0.5) == bool(int(r["went_up"])))
    return {"closed": len(closed), "open": open_n, "hit_rate": hits / len(closed),
            "brier": brier, "brier_baseline": brier_base,
            "brier_skill": 1 - brier / brier_base if brier_base else None}


def load_scoreboard(path: Path) -> dict:
    return scoreboard(_load(path))
