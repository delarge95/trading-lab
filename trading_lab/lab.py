"""Laboratorio de reglas de selección transversal y libro de picks hacia adelante.

Cuatro reglas simples (todas calculadas SOLO con precios hasta la fecha de rebalanceo):
  mom12_1     mayor momentum 12-1 meses
  lowvol      menor volatilidad de 63 ruedas
  reversal1m  peor retorno de las últimas 21 ruedas
  near_high   menor distancia al máximo de 252 ruedas

Se rebalancea cada `hold` ruedas desde el índice 252 (períodos NO solapados), con cartera igual ponderada de las
`top_n` mejores. Los retornos son de (i, i+hold]; el costo es `cost` x rotación (fracción de la cartera que cambia).
Benchmarks: igual ponderado de todo el universo disponible (EW, sin costo) y SPY. La evaluación usa `rigor.py`
(IC del Sharpe, bootstrap por bloques pareado vs EW, Holm, DSR). Es investigación, no asesoría financiera.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
from statistics import mean

import numpy as np
import pandas as pd

from . import rigor
from .forecast import raw_features

MIN_HIST = 252
ALPHA = 0.05
MIN_CLOSED = 12          # cerradas necesarias para reportar un valor p en el libro

RULES: dict[str, dict] = {
    "mom12_1": {"label": "Momentum 12-1 (mayor retorno de 12 a 1 meses)", "feature": "mom12_1", "sign": +1},
    "lowvol": {"label": "Baja volatilidad (menor volatilidad de 63 ruedas)", "feature": "vol63", "sign": -1},
    "reversal1m": {"label": "Reversión 1 mes (peor retorno de 21 ruedas)", "feature": "r1m", "sign": -1},
    "near_high": {"label": "Cerca del máximo (menor distancia al máximo de 252 ruedas)", "feature": "dist_high", "sign": +1},
}

CAVEATS = [
    "Sesgo de supervivencia: el universo son los miembros ACTUALES del S&P 100, lo que infla todos los retornos "
    "históricos (también los del EW y los de las reglas); las diferencias entre reglas y EW están menos sesgadas, pero no libres de sesgo.",
    "Sin impuestos ni deslizamiento más allá del costo fijo por rotación; el EW y SPY se muestran sin costo (sesgo conservador contra las reglas).",
    "Resultado histórico no garantiza resultado futuro. Se probaron varias reglas: el DSR y la corrección de Holm descuentan parte, no todo, del sesgo de selección.",
    "Herramienta de investigación, no asesoría financiera.",
]


# ------------------------------------------------------------------ selección
def _scores(P: pd.DataFrame, bench: str) -> tuple[list[str], dict[str, np.ndarray]]:
    """Puntajes (mayor = mejor) por regla, matriz fechas x acciones. Solo usan precios hasta cada fecha."""
    stocks = [c for c in P.columns if c != bench]
    raw = raw_features(P[stocks])
    return stocks, {r: spec["sign"] * raw[spec["feature"]].values for r, spec in RULES.items()}


def _select(score_row: np.ndarray, top_n: int) -> list[int]:
    """Posiciones de las top_n con mayor puntaje (desempate estable por orden de columna)."""
    ok = np.flatnonzero(np.isfinite(score_row))
    if len(ok) == 0:
        return []
    order = ok[np.argsort(-score_row[ok], kind="stable")]
    return [int(j) for j in order[:top_n]]


def simulate(P: pd.DataFrame, bench: str = "SPY", top_n: int = 10, hold: int = 21, cost: float = 0.001) -> dict:
    """Backtest de las reglas. Devuelve índices de rebalanceo, selecciones y retornos por período (netos y brutos)."""
    stocks, sc = _scores(P, bench)
    X = P[stocks].values
    B = P[bench].values
    T = len(P)
    idx = list(range(MIN_HIST, T - hold, hold))
    out = {"idx": idx, "stocks": stocks, "picks": {r: [] for r in RULES}, "ret": {r: [] for r in RULES},
           "gross": {r: [] for r in RULES}, "rotation": {r: [] for r in RULES}, "ew": [], "bench": []}
    prev: dict[str, set[int]] = {r: set() for r in RULES}
    for i in idx:
        fwd = X[i + hold] / X[i] - 1
        fwd = np.where(np.isfinite(fwd), fwd, np.nan)
        out["ew"].append(float(np.nanmean(fwd)) if np.isfinite(fwd).any() else 0.0)
        out["bench"].append(float(B[i + hold] / B[i] - 1))
        for r in RULES:
            sel = _select(sc[r][i], top_n)
            cur = set(sel)
            rot = 1.0 if not prev[r] or not cur else 1.0 - len(cur & prev[r]) / max(len(cur), 1)
            prev[r] = cur
            vals = fwd[sel] if sel else np.array([])
            g = float(np.nanmean(vals)) if np.isfinite(vals).any() else 0.0
            out["picks"][r].append([stocks[j] for j in sel])
            out["gross"][r].append(g)
            out["rotation"][r].append(rot)
            out["ret"][r].append(g - cost * rot)
    return out


# ------------------------------------------------------------------ estadística
def _max_drawdown(rets: list[float]) -> float:
    eq = np.cumprod(1.0 + np.asarray(rets))
    peak = np.maximum.accumulate(np.concatenate([[1.0], eq]))[1:]
    return float((eq / peak - 1).min())


def run(P: pd.DataFrame, bench: str = "SPY", top_n: int = 10, hold: int = 21, cost: float = 0.001) -> dict:
    """Evalúa las reglas contra el igual ponderado (EW) y SPY. Esquema en docs/contratos-datos.md, sección 2."""
    ppy = 252 / hold
    sim = simulate(P, bench, top_n, hold, cost)
    ew = sim["ew"]
    n = len(ew)
    if n < 12:
        raise ValueError(f"historia insuficiente: {n} períodos (se necesitan >= 12)")
    names = list(RULES)
    tests = {r: rigor.block_bootstrap_diff(sim["ret"][r], ew, n_boot=2000, ppy=ppy) for r in names}
    p_holm = dict(zip(names, rigor.holm([tests[r]["p_beat"] for r in names])))
    trial_srs = [rigor.sr_period(sim["ret"][r]) for r in names]
    rules = {}
    for r in names:
        x = sim["ret"][r]
        s, lo, hi = rigor.sharpe_ci(x, ppy=ppy)
        t = tests[r]
        rules[r] = {
            "label": RULES[r]["label"], "periods": n, "sharpe": s, "sharpe_ci": [lo, hi],
            "annual_excess_vs_ew": float(np.mean(np.asarray(x) - np.asarray(ew)) * ppy),
            "diff_sharpe_vs_ew": t["diff"], "diff_ci": [t["ci"][0], t["ci"][1]],
            "p_beat_ew": t["p_beat"], "p_holm": float(p_holm[r]),
            "dsr": float(rigor.dsr(x, trial_srs)), "max_drawdown": _max_drawdown(x),
            "turnover": float(np.mean(sim["rotation"][r])),
        }
    es, elo, ehi = rigor.sharpe_ci(ew, ppy=ppy)
    bs = rigor.sharpe_ci(sim["bench"], ppy=ppy)[0]
    winners = [r for r in names if p_holm[r] < ALPHA and rules[r]["diff_sharpe_vs_ew"] > 0]
    if winners:
        det = "; ".join(f"{r} (Sharpe {rules[r]['sharpe']:.2f} vs EW {es:.2f}, p Holm {p_holm[r]:.3f})" for r in winners)
        verdict = (f"Con significancia estadística (Holm, alfa 5%, {len(names)} reglas) supera al igual ponderado: {det}. "
                   "Aun así el universo tiene sesgo de supervivencia: tratar como hipótesis a confirmar con el libro hacia adelante, no como ventaja probada.")
    else:
        best = max(names, key=lambda r: rules[r]["diff_sharpe_vs_ew"])
        verdict = (f"Ninguna de las {len(names)} reglas supera al igual ponderado del universo con significancia estadística "
                   f"(Holm, alfa 5%). La mejor diferencia de Sharpe es {rules[best]['diff_sharpe_vs_ew']:+.2f} ({best}, "
                   f"p Holm {p_holm[best]:.2f}); la diferencia no se distingue del azar.")
    stocks, sc = _scores(P, bench)
    last = len(P) - 1
    picks_now = {r: [stocks[j] for j in _select(sc[r][last], top_n)] for r in names}
    return {
        "rules": rules,
        "ew": {"periods": n, "sharpe": es, "sharpe_ci": [elo, ehi]},
        "bench": {"sharpe": bs},
        "verdict": verdict, "caveats": list(CAVEATS), "picks_now": picks_now,
    }


# ------------------------------------------------------------------ libro de picks hacia adelante
def _sign_flip_p(x: list[float], n_perm: int = 20000, seed: int = 0) -> float:
    """Valor p unilateral (H0: media <= 0) por inversión aleatoria de signos."""
    a = np.asarray(x, dtype=float)
    rng = np.random.default_rng(seed)
    signs = rng.choice([-1.0, 1.0], size=(n_perm, len(a)))
    ge = int(((signs * a).mean(axis=1) >= a.mean() - 1e-15).sum())
    return (ge + 1) / (n_perm + 1)


def _iso(ts) -> str:
    return pd.Timestamp(ts).strftime("%Y-%m-%d")


def _mean_ret(entry: dict[str, float], exit_row: pd.Series) -> float | None:
    rs = []
    for t, p0 in entry.items():
        p1 = exit_row.get(t)
        if p1 is not None and np.isfinite(p1) and p0:
            rs.append(float(p1) / p0 - 1)
    return float(np.mean(rs)) if rs else None


def update_ledger(path, P: pd.DataFrame, bench: str = "SPY", today=None, top_n: int = 10, hold: int = 21) -> dict:
    """Actualiza el libro de picks hacia adelante (JSON) y devuelve su resumen.

    Archivo: {"version": 1, "hold": int, "top_n": int, "entries": [entrada, ...]} con
      entrada = {"date": fecha de apertura (última de P), "rule", "tickers": [..], "entry": {ticker: precio},
                 "ew_entry": {ticker: precio de TODO el universo}, "bench_entry": precio, "status": "abierta"|"cerrada",
                 "exit_date", "ret", "ew_ret", "bench_ret", "excess_vs_ew"}   (los campos de cierre son null mientras está abierta)
    En cada llamada: (1) cierra las entradas con >= hold ruedas (cuenta posiciones en P.index; usa el precio de la
    rueda apertura+hold, no la última), (2) abre una entrada por regla solo si no hay una abierta, (3) es idempotente.
    `today` recorta P a las fechas <= today (permite repetir el proceso en una fecha pasada). Retornos brutos (sin costo).
    """
    path = Path(path)
    if today is not None:
        P = P.loc[: pd.Timestamp(today)]
    if len(P) == 0:
        raise ValueError("P no tiene datos hasta la fecha indicada")
    if path.exists():
        led = json.loads(path.read_text(encoding="utf-8"))
    else:
        led = {"version": 1, "hold": hold, "top_n": top_n, "entries": []}
    entries = led["entries"]
    last = len(P) - 1
    last_date = _iso(P.index[last])
    stocks = [c for c in P.columns if c != bench]
    pos = {_iso(d): k for k, d in enumerate(P.index)}

    # (1) cierres
    for e in entries:
        if e["status"] != "abierta" or e["date"] not in pos:
            continue
        k0 = pos[e["date"]]
        if last - k0 < hold:
            continue
        row = P.iloc[k0 + hold]
        ret, ew_ret = _mean_ret(e["entry"], row), _mean_ret(e["ew_entry"], row)
        b0, b1 = e["bench_entry"], row[bench]
        if ret is None or ew_ret is None or not np.isfinite(b1):
            continue                                   # sin precios de salida: queda abierta
        e.update(status="cerrada", exit_date=_iso(P.index[k0 + hold]), ret=ret, ew_ret=ew_ret,
                 bench_ret=float(b1) / b0 - 1, excess_vs_ew=ret - ew_ret)

    # (2) aperturas
    _, sc = _scores(P, bench)
    row = P.iloc[last]
    for r in RULES:
        if any(e["rule"] == r and (e["status"] == "abierta" or e["date"] == last_date) for e in entries):
            continue
        sel = _select(sc[r][last], top_n)
        if not sel or not np.isfinite(row[bench]):
            continue
        entries.append({
            "date": last_date, "rule": r, "tickers": [stocks[j] for j in sel],
            "entry": {stocks[j]: float(row[stocks[j]]) for j in sel},
            "ew_entry": {s: float(row[s]) for s in stocks if np.isfinite(row[s])},
            "bench_entry": float(row[bench]), "status": "abierta",
            "exit_date": None, "ret": None, "ew_ret": None, "bench_ret": None, "excess_vs_ew": None,
        })

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(led, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)

    # resumen
    summary = {}
    for r in RULES:
        closed = [e for e in entries if e["rule"] == r and e["status"] == "cerrada"]
        opened = [e["date"] for e in entries if e["rule"] == r and e["status"] == "abierta"]
        ex = [e["excess_vs_ew"] for e in closed]
        note = f"muestra insuficiente (n={len(ex)}); no concluir"
        if len(ex) >= MIN_CLOSED:
            note = (f"n={len(ex)}; valor p por inversión de signos del exceso medio vs EW (unilateral, sin Holm): "
                    f"{_sign_flip_p(ex):.3f}")
        summary[r] = {"closed": len(ex), "open_since": opened[0] if opened else None,
                      "mean_excess_vs_ew": float(mean(ex)) if ex else None,
                      "hit_rate": float(sum(1 for v in ex if v > 0) / len(ex)) if ex else None, "note": note}
    return {"as_of": last_date, "rules": summary, "entries_total": len(entries)}
