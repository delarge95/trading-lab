"""Marco para probar fuentes de datos con el mismo rigor que el motor de probabilidades.

Una fuente (fundamentales, interés corto, volatilidad implícita, consenso...) solo se adopta si su factor tiene poder
predictivo demostrable fuera de muestra. `evaluate_factor` mide, en fechas de muestreo cada 5 ruedas:
- IC de rango (Spearman) entre el factor conocido ese día y el retorno futuro a `horizon` ruedas;
- retorno medio del quintil superior menos la media del universo (y menos el quintil inferior);
- IC95% por remuestreo de bloques de fechas (`forecast._block_bootstrap`, bloques de 50 ruedas > horizonte);
- veredicto: "supera a la tasa base" SOLO si el IC95% del IC de rango excluye 0 en la dirección esperada y el
  exceso del quintil superior es positivo.
Sin anticipación: el factor en la fecha t es la última observación con fecha <= t (ffill con límite de antigüedad) y,
además, se retrasa `lag_bars` ruedas (por defecto 1: una presentación del día D puede salir después del cierre).
Convención de dirección: se espera que un valor MÁS ALTO del factor anticipe MÁS retorno; los factores donde la hipótesis
es la contraria (deuda, dilución) se construyen con el signo cambiado.
Limitaciones: universo = miembros actuales del índice (sesgo de supervivencia); retornos de fechas muestreadas cada 5
ruedas con horizonte 21 se solapan (por eso el bootstrap es por bloques); el p-valor para Holm es una aproximación normal
a partir del error estándar del bootstrap.
"""
from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from . import forecast, fundamentals, rigor

STEP = forecast.STEP
BLOCK = STEP * 10           # ruedas por bloque del bootstrap (mismo criterio que forecast.evaluate)
MIN_NAMES = 20              # mínimo de acciones con factor y retorno en una fecha
MIN_DATES = 30              # mínimo de fechas de muestreo para emitir un veredicto
ALT_MIN_DATES = 60          # historia mínima de fuentes alternativas (data/alt)


# ------------------------------------------------------------------ alineación sin anticipación
def align_factor(P: pd.DataFrame, factor_df: pd.DataFrame, max_age_days: int = 200, lag_bars: int = 1) -> pd.DataFrame:
    """Factor alineado al índice de precios: última observación con fecha <= t, no más vieja que `max_age_days`.

    Se retrasa `lag_bars` ruedas después del ffill (la observación del día D se usa desde la rueda siguiente).
    """
    fd = factor_df.copy()
    fd.index = pd.to_datetime(fd.index)
    fd = fd.sort_index()
    cols = [c for c in fd.columns if c in P.columns]
    out = pd.DataFrame(index=P.index, columns=cols, dtype=float)
    tol = pd.Timedelta(days=max_age_days)
    for c in cols:
        s = fd[c].dropna()
        s = s[~s.index.duplicated(keep="last")]
        if s.empty:
            continue
        out[c] = s.reindex(P.index, method="ffill", tolerance=tol)
    return out.shift(lag_bars) if lag_bars else out


# ------------------------------------------------------------------ evaluación
def _spearman(x: np.ndarray, y: np.ndarray) -> float:
    rx, ry = pd.Series(x).rank().values, pd.Series(y).rank().values
    if rx.std() == 0 or ry.std() == 0:
        return float("nan")
    return float(np.corrcoef(rx, ry)[0, 1])


def _ci(blocks: np.ndarray, vals: np.ndarray) -> tuple[float, float]:
    return forecast._block_bootstrap(blocks, np.stack([vals, np.ones(len(vals))], axis=1), lambda s: s[0] / s[1])


def _f(x) -> float | None:
    x = float(x)
    return x if math.isfinite(x) else None


def evaluate_factor(P: pd.DataFrame, factor_df: pd.DataFrame, horizon: int = 21, name: str = "factor",
                    top_frac: float = 0.2, max_age_days: int = 200, lag_bars: int = 1,
                    end: str | pd.Timestamp | None = None) -> dict:
    """Poder predictivo de un factor (fechas x tickers, punto en el tiempo) sobre el retorno a `horizon` ruedas.

    `P`: precios (forecast.price_frame; si incluye el benchmark y no hay factor para él, se ignora).
    `end`: última fecha de muestreo (para comprobar que no se usan datos posteriores).
    """
    A = align_factor(P, factor_df, max_age_days, lag_bars)
    names = list(A.columns)
    if len(names) < MIN_NAMES:
        return {"name": name, "horizon": horizon, "status": "universo insuficiente", "n_names": len(names)}
    fwd = (P[names].shift(-horizon) / P[names] - 1).values
    X = A.values
    T = len(P)
    pos = np.arange(T - 1, -1, -STEP)[::-1]
    if end is not None:
        pos = pos[P.index[pos] <= pd.Timestamp(end)]
    dates, ics, tops, spreads, nn, blocks = [], [], [], [], [], []
    for t in pos:
        ok = np.isfinite(X[t]) & np.isfinite(fwd[t])
        n = int(ok.sum())
        if n < MIN_NAMES:
            continue
        x, y = X[t][ok], fwd[t][ok]
        ic = _spearman(x, y)
        if not math.isfinite(ic):
            continue
        k = max(1, int(round(top_frac * n)))
        order = np.argsort(x, kind="stable")
        top, bot = y[order[-k:]].mean(), y[order[:k]].mean()
        dates.append(P.index[t])
        ics.append(ic)
        tops.append(top - y.mean())
        spreads.append(top - bot)
        nn.append(n)
        blocks.append(t // BLOCK)
    if len(ics) < MIN_DATES:
        return {"name": name, "horizon": horizon, "status": "historia insuficiente", "n_dates": len(ics)}
    ics, tops, spreads, blocks = (np.array(a) for a in (ics, tops, spreads, blocks))
    ic_ci, ex_ci, sp_ci = _ci(blocks, ics), _ci(blocks, tops), _ci(blocks, spreads)
    ic_m, ex_m, sp_m = float(ics.mean()), float(tops.mean()), float(spreads.mean())
    se = max((ic_ci[1] - ic_ci[0]) / (2 * 1.96), 1e-12)
    p_one = float(0.5 * math.erfc((ic_m / se) / math.sqrt(2)))          # P(IC <= 0 | aproximación normal), una cola
    has_edge = bool(ic_ci[0] > 0 and ex_m > 0)
    half = len(ics) // 2
    halves = []
    for sl, nm in ((slice(0, half), "primera mitad"), (slice(half, None), "segunda mitad")):
        halves.append({"label": nm, "from": dates[sl][0].strftime("%Y-%m-%d"), "to": dates[sl][-1].strftime("%Y-%m-%d"),
                       "n_dates": int(len(ics[sl])), "ic": float(ics[sl].mean()), "top_excess": float(tops[sl].mean())})
    stable = bool(all(h["ic"] > 0 and h["top_excess"] > 0 for h in halves))
    return {
        "name": name, "horizon": horizon, "n_dates": int(len(ics)), "avg_names": float(np.mean(nn)),
        "first_date": dates[0].strftime("%Y-%m-%d"), "last_date": dates[-1].strftime("%Y-%m-%d"),
        "ic": ic_m, "ic_ci": ic_ci, "ic_hit_rate": float((ics > 0).mean()),
        "top_excess": ex_m, "top_excess_ci": ex_ci, "spread": sp_m, "spread_ci": sp_ci, "top_frac": top_frac,
        "p_value": p_one, "has_edge": has_edge, "halves": halves, "stable": stable,
        "verdict": "supera a la tasa base" if has_edge else "no supera la tasa base",
        "stability_note": ("el signo del IC y del exceso coincide en las dos mitades" if stable else
                           "el IC o el exceso cambia de signo entre las dos mitades: no es estable"),
    }


# ------------------------------------------------------------------ fundamentales como factores
def _wide(hist: dict[str, pd.DataFrame], col: str, sign: float) -> pd.DataFrame:
    cols = {t: sign * h[col] for t, h in hist.items() if col in h and h[col].notna().any()}
    return pd.DataFrame(cols).sort_index() if cols else pd.DataFrame()


# clave -> (etiqueta, columna de fundamentals.history, signo para que "más alto = más retorno esperado")
FACTOR_BUILDERS: dict[str, tuple[str, str, float]] = {
    "rev_growth": ("Crecimiento de ingresos interanual", "rev_growth_yoy", 1.0),
    "op_margin": ("Margen operativo TTM", "op_margin_ttm", 1.0),
    "fcf_margin": ("Margen de flujo de caja libre TTM", "fcf_margin_ttm", 1.0),
    "low_leverage": ("Baja deuda/patrimonio (signo invertido)", "debt_to_equity", -1.0),
    "low_dilution": ("Baja dilución: menor cambio de acciones (signo invertido)", "shares_chg_yoy", -1.0),
}


def build_factor(key: str, hist: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """DataFrame fechas de presentación x tickers del factor `key` (valores ya orientados)."""
    _, col, sign = FACTOR_BUILDERS[key]
    return _wide(hist, col, sign)


def evaluate_all_fundamentals(P: pd.DataFrame, tickers: list[str] | None = None, horizon: int = 21,
                              hist: dict[str, pd.DataFrame] | None = None, top_frac: float = 0.2) -> dict:
    """Evalúa los factores de fundamentales con corrección de Holm entre factores.

    `hist` (opcional): {ticker: fundamentals.history} ya cargado; si no, se descarga/lee de caché.
    """
    if hist is None:
        tickers = tickers if tickers is not None else [c for c in P.columns if c != "SPY"]
        try:
            from . import sec
            cik_map = sec.ticker_to_cik()
        except Exception:  # noqa: BLE001
            cik_map = {}
        hist = {}
        for t in tickers:
            if t not in P.columns:
                continue
            h = fundamentals.history(t, cik_map=cik_map)
            if len(h):
                hist[t] = h
    hist = {t: h for t, h in hist.items() if t in P.columns}
    out: dict = {}
    for key, (label, _, _) in FACTOR_BUILDERS.items():
        f = build_factor(key, hist)
        out[key] = (evaluate_factor(P, f, horizon, label, top_frac) if len(f.columns) else
                    {"name": label, "horizon": horizon, "status": "sin datos"})
    keys = [k for k, v in out.items() if "p_value" in v]
    adj = rigor.holm([out[k]["p_value"] for k in keys])
    for k, p in zip(keys, adj):
        out[k]["p_holm"] = float(p)
        out[k]["survives_holm"] = bool(out[k]["has_edge"] and p < 0.05)
    survivors = [out[k]["name"] for k in keys if out[k]["survives_holm"]]
    # evidencia por columna de fundamentals (la lee ranking.py): "validado" exige sobrevivir a Holm Y ser estable en las dos mitades
    evidence = {}
    for key, (_, col, _) in FACTOR_BUILDERS.items():
        r = out[key]
        evidence[col] = ("no probado aquí" if "p_value" not in r else
                         "validado" if (r["survives_holm"] and r["stable"]) else "sin ventaja demostrada")
    verdict = (f"Supera a la tasa base tras corregir por {len(keys)} factores: {', '.join(survivors)}." if survivors else
               "Ningún factor de fundamentales supera la tasa base tras la corrección de Holm; no se incorporan al motor.")
    return {
        "asof": P.index[-1].strftime("%Y-%m-%d"), "horizon": horizon, "n_tickers": len(hist),
        "factors": out, "evidence": evidence, "verdict": verdict,
        "caveats": [
            "Universo = miembros actuales del índice: sesgo de supervivencia (las empresas que hoy están son las que tuvieron buen desempeño).",
            f"Retornos a {horizon} ruedas muestreados cada {STEP} ruedas se solapan: el IC95% usa bloques de {BLOCK} ruedas.",
            "Cada cifra se usa desde su fecha de presentación (+1 rueda); la clasificación contable varía por empresa (bancos sin margen operativo).",
            "Con 5 factores y una muestra de ~10 años, la potencia es baja: 'no supera' no demuestra que no haya efecto.",
        ],
    }


# ------------------------------------------------------------------ fuentes alternativas (data/alt)
def load_alt_history(outdir: str | Path = "data/alt") -> pd.DataFrame:
    """Lee las fotos diarias data/alt/AAAA-MM-DD.json a un DataFrame largo (date, ticker, <campos>).

    Acepta {"tickers": {T: {campo: valor}}} o {T: {campo: valor}}.
    """
    rows = []
    for p in sorted(Path(outdir).glob("????-??-??.json")):
        try:
            j = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        body = j.get("tickers", j) if isinstance(j, dict) else {}
        for t, fields in body.items():
            if isinstance(fields, dict):
                rows.append({"date": pd.Timestamp(p.stem), "ticker": t, **fields})
    return pd.DataFrame(rows)


def evaluate_alt(P: pd.DataFrame, alt_history_df: pd.DataFrame, field: str, horizon: int = 21,
                 sign: float = 1.0, top_frac: float = 0.2) -> dict:
    """Evalúa un campo de la historia alternativa (DataFrame largo date/ticker/campo). Exige >= 60 fechas."""
    df = alt_history_df
    n = int(df["date"].nunique()) if df is not None and len(df) and "date" in df else 0
    if n < ALT_MIN_DATES or field not in df.columns:
        return {"status": "historia insuficiente", "n_dates": n}
    wide = df.pivot_table(index="date", columns="ticker", values=field, aggfunc="last") * sign
    return evaluate_factor(P, wide, horizon, f"alt:{field}", top_frac, max_age_days=10)
