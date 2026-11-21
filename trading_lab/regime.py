"""Semáforo de régimen de mercado (verde / amarillo / rojo) con reglas simples y fijadas a priori.

Principios:
- Las reglas, umbrales y la regla de puntaje son constantes de este módulo, escogidas ANTES de mirar resultados
  (valores convencionales de la práctica: VIX 20/30, volatilidad 15%/25%, corrección de 5%/15%, media de 200 ruedas).
  No se optimizaron sobre la historia.
- Cada regla vota 0 (verde), 1 (amarillo) o 2 (rojo). Puntaje = suma de votos de las reglas con dato disponible;
  razón = puntaje / (2 * n_reglas). Estado global: verde si razón <= GREEN_MAX_RATIO, rojo si razón >= RED_MIN_RATIO,
  amarillo en otro caso. Si una regla no tiene dato en una fecha (p. ej. VIX histórico no disponible) simplemente no vota.
- El estado de cada fecha usa solo datos hasta esa fecha (sin anticipación).
- Evaluación de utilidad honesta: una exposición decidida con el estado del cierre anterior se compara con comprar y
  mantener usando rigor.py (Sharpe con IC, diferencia de Sharpe con bootstrap por bloques sobre períodos NO solapados
  de 21 ruedas, máximo drawdown). El veredicto dice con claridad si mejora con significancia o solo reduce el drawdown.
Herramienta de investigación: describe hechos estadísticos, no emite recomendaciones de compra o venta.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from . import fred, rigor
from .forecast import ewma_sigma

# ------------------------------------------------------------------ reglas fijadas a priori
# Cada regla: (clave, etiqueta, umbral_verde, umbral_rojo, peor_si_sube)
#   peor_si_sube=True : verde si x < verde, rojo si x >= rojo, amarillo en medio.
#   peor_si_sube=False: verde si x >= verde, rojo si x < rojo, amarillo en medio.
RULES = [
    ("vol_ewma_ann", "Volatilidad EWMA anualizada del benchmark", 0.15, 0.25, True),
    ("vix", "VIX", 20.0, 30.0, True),
    ("drawdown_52w", "Caída desde el máximo de 52 semanas", -0.05, -0.15, False),
    ("sma200_gap", "Distancia a la media de 200 ruedas", 0.0, -0.03, False),
    ("hy_spread", "Spread high yield (pp)", 4.5, 6.0, True),
]
GREEN_MAX_RATIO = 0.25   # verde si puntaje <= 25% del máximo posible
RED_MIN_RATIO = 0.50     # rojo si puntaje >= 50% del máximo posible
MIN_HIST = 252           # ruedas mínimas antes de emitir estado (máximo de 52 semanas)
HORIZON = 21             # ruedas siguientes para las estadísticas por estado y los períodos no solapados
DROP_LEVEL = 0.05        # caída considerada en prob_drop5
# Exposición de la regla de prueba por estado (decidida con el estado del cierre anterior)
EXPOSURE = {"verde": 1.0, "amarillo": 0.5, "rojo": 0.25}
COST = 0.0005            # 0.05% por unidad de exposición cambiada
VIX_YEARS = 11
STATES = ("verde", "amarillo", "rojo")


# ------------------------------------------------------------------ utilidades
def _clean(obj):
    """Convierte a tipos JSON puros; NaN/inf -> None."""
    if isinstance(obj, dict):
        return {str(k): _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        v = float(obj)
        return v if math.isfinite(v) else None
    return obj


def _fred_history(series_id: str) -> pd.Series | None:
    """Serie histórica de FRED como pd.Series (índice fecha) o None si no hay red / falla."""
    try:
        rows = fred.get_series(series_id, years=VIX_YEARS)
    except Exception:  # noqa: BLE001 - sin red debe degradar, no fallar
        return None
    if not rows:
        return None
    s = pd.Series({pd.Timestamp(d): v for d, v in rows}).sort_index()
    return s[~s.index.duplicated(keep="last")]


def _align(s: pd.Series | None, index: pd.DatetimeIndex) -> pd.Series:
    """Alinea una serie externa al calendario del benchmark (ffill de hasta 5 días calendario)."""
    if s is None or s.empty:
        return pd.Series(np.nan, index=index)
    return s.reindex(index, method="ffill", tolerance=pd.Timedelta(days=5))


def _macro_value(macro: dict | None, key: str, index: pd.DatetimeIndex) -> float | None:
    if not macro:
        return None
    item = macro.get(key)
    if not isinstance(item, dict) or item.get("value") is None:
        return None
    try:
        v = float(item["value"])
    except (TypeError, ValueError):
        return None
    if not math.isfinite(v):
        return None
    if item.get("date"):
        try:
            if index[-1] - pd.Timestamp(item["date"]) > pd.Timedelta(days=7):
                return None   # dato demasiado viejo respecto del último precio
        except (ValueError, TypeError):
            pass
    return v


def _points(x: pd.Series, green: float, red: float, higher_is_worse: bool) -> pd.Series:
    if higher_is_worse:
        pts = np.where(x < green, 0.0, np.where(x < red, 1.0, 2.0))
    else:
        pts = np.where(x >= green, 0.0, np.where(x >= red, 1.0, 2.0))
    return pd.Series(np.where(x.isna(), np.nan, pts), index=x.index)


def _threshold_text(key: str, green: float, red: float, higher_is_worse: bool) -> str:
    pct = key in ("vol_ewma_ann", "drawdown_52w", "sma200_gap")

    def f(v: float) -> str:
        return f"{v * 100:.0f}%" if pct else f"{v:g}"
    if higher_is_worse:
        return f"verde < {f(green)}; rojo >= {f(red)}"
    return f"verde >= {f(green)}; rojo < {f(red)}"


# ------------------------------------------------------------------ estado en cada fecha
def state_series(px: pd.Series, vix: pd.Series | None = None, hy: pd.Series | None = None) -> pd.DataFrame:
    """Entradas, votos, puntaje y estado en cada fecha usando solo datos hasta esa fecha.

    px: precios del benchmark; vix / hy: series alineadas al mismo índice (NaN donde no hay dato).
    """
    px = px.astype(float)
    frame = pd.DataFrame(index=px.index)
    frame["vol_ewma_ann"] = ewma_sigma(px.to_frame("x"))["x"] * math.sqrt(252)
    frame["vix"] = vix.reindex(px.index) if vix is not None else np.nan
    frame["drawdown_52w"] = px / px.rolling(252).max() - 1
    frame["sma200_gap"] = px / px.rolling(200).mean() - 1
    frame["hy_spread"] = hy.reindex(px.index) if hy is not None else np.nan
    pts = pd.DataFrame({k: _points(frame[k], g, r, hw) for k, _, g, r, hw in RULES})
    n = pts.notna().sum(axis=1)
    score = pts.sum(axis=1, min_count=1)
    ratio = score / (2 * n.where(n > 0))
    state = pd.Series(np.where(ratio <= GREEN_MAX_RATIO, "verde",
                               np.where(ratio >= RED_MIN_RATIO, "rojo", "amarillo")), index=px.index, dtype=object)
    warm = np.arange(len(px)) < MIN_HIST - 1
    state[warm | ratio.isna().values | frame[["drawdown_52w", "sma200_gap"]].isna().any(axis=1).values] = None
    out = frame.copy()
    for k in pts.columns:
        out["pts_" + k] = pts[k]
    out["score"] = score
    out["n_rules"] = n
    out["state"] = state
    return out


# ------------------------------------------------------------------ historia por estado
def _by_state(px: pd.Series, st: pd.DataFrame) -> dict:
    h = HORIZON
    fwd = px.shift(-h) / px - 1
    fmin = px.iloc[::-1].rolling(h).min().iloc[::-1].shift(-1) / px - 1   # mínimo de las próximas h ruedas
    valid = st["state"].notna()
    total = int(valid.sum())
    out = {}
    for s in STATES:
        m = valid & (st["state"] == s)
        mf = m & fwd.notna() & fmin.notna()
        n = int(mf.sum())
        out[s] = {
            "share": float(m.sum() / total) if total else None,
            "days": int(m.sum()),
            "n": n,
            "n_eff": float(n / h),   # las ventanas de 21 ruedas se solapan: muestra efectiva aprox. n/21
            "fwd21_mean": float(fwd[mf].mean()) if n else None,
            "fwd21_p10": float(np.percentile(fwd[mf], 10)) if n else None,
            "prob_drop5": float((fmin[mf] <= -DROP_LEVEL).mean()) if n else None,
        }
    return out


# ------------------------------------------------------------------ regla de exposición vs comprar y mantener
def _max_dd(rets: np.ndarray) -> float:
    eq = np.concatenate([[1.0], np.cumprod(1.0 + rets)])
    return float((eq / np.maximum.accumulate(eq) - 1).min())


def _periods(rets: np.ndarray, h: int = HORIZON) -> list[float]:
    """Retornos compuestos de períodos NO solapados de h ruedas, alineados al final de la muestra."""
    n = (len(rets) // h) * h
    r = rets[len(rets) - n:].reshape(-1, h)
    return list(np.prod(1.0 + r, axis=1) - 1.0)


def _vol_managed(px: pd.Series, st: pd.DataFrame) -> dict | None:
    valid = st["state"].notna().values
    if not valid.any():
        return None
    first = int(np.argmax(valid))
    expo = st["state"].map(EXPOSURE).astype(float)
    r = px.pct_change()
    e_prev = expo.shift(1)                       # exposición decidida con el cierre anterior
    sl = slice(first + 1, None)
    r_d = r.iloc[sl].values
    e_d = e_prev.iloc[sl].values
    if len(r_d) < 12 * HORIZON:
        return None
    e_before = np.concatenate([[e_d[0]], e_d[:-1]])
    cost = COST * np.abs(e_d - e_before)
    strat = e_d * r_d - cost
    pa, pb = _periods(strat), _periods(r_d)
    ra = rigor.sharpe_ci(pa)
    rb = rigor.sharpe_ci(pb)
    bb = rigor.block_bootstrap_diff(pa, pb)
    n = len(r_d)
    cagr = lambda x: float(np.prod(1.0 + x) ** (252 / n) - 1)   # noqa: E731
    dd_s, dd_b = _max_dd(strat), _max_dd(r_d)
    diff, ci, p = bb["diff"], bb["ci"], bb["p_beat"]
    res = {
        "sharpe": ra[0], "sharpe_ci": [ra[1], ra[2]], "sharpe_bh": rb[0], "sharpe_bh_ci": [rb[1], rb[2]],
        "diff_sharpe": diff, "diff_ci": [ci[0], ci[1]], "p_beat": p,
        "max_dd": dd_s, "max_dd_bh": dd_b,
        "cagr": cagr(strat), "cagr_bh": cagr(r_d), "exposure_mean": float(e_d.mean()),
        "turnover_ann": float(np.abs(e_d - e_before).sum() / n * 252),
        "periods": len(pa), "start": px.index[first + 1].strftime("%Y-%m-%d"),
        "exposure": dict(EXPOSURE), "cost": COST,
    }
    res["verdict"] = _vm_verdict(res)
    return res


def _vm_verdict(v: dict) -> str:
    head = (f"Regla de exposición (100% verde, 50% amarillo, 25% rojo; costo 0.05%) vs comprar y mantener sobre "
            f"{v['periods']} períodos no solapados de 21 ruedas: Sharpe {v['sharpe']:.2f} vs {v['sharpe_bh']:.2f}; "
            f"diferencia {v['diff_sharpe']:+.2f} (IC95% {v['diff_ci'][0]:+.2f} a {v['diff_ci'][1]:+.2f}, "
            f"p={v['p_beat']:.2f}).")
    less_dd = v["max_dd"] > v["max_dd_bh"] + 0.02
    dd_txt = f"máximo drawdown {v['max_dd'] * 100:.0f}% vs {v['max_dd_bh'] * 100:.0f}%"
    if v["diff_sharpe"] > 0 and v["p_beat"] < 0.05:
        return (head + f" Mejora el Sharpe con significancia estadística (p<0.05); {dd_txt}. "
                "Con una sola muestra de pocas crisis, tomarlo con cautela.")
    if less_dd:
        return (head + f" NO mejora el Sharpe de forma significativa: solo reduce el drawdown ({dd_txt}) "
                f"a costa de menor retorno anualizado ({v['cagr'] * 100:.1f}% vs {v['cagr_bh'] * 100:.1f}%).")
    return head + f" No mejora el Sharpe de forma significativa ni reduce el drawdown de forma apreciable ({dd_txt})."


# ------------------------------------------------------------------ orquestación
def _current_rules(row: pd.Series) -> list[dict]:
    rules = []
    for key, label, g, r, hw in RULES:
        v = row[key]
        if pd.isna(v):
            continue
        pts = row["pts_" + key]
        rules.append({"name": key, "label": label, "value": float(v), "state": STATES[int(pts)],
                      "threshold": _threshold_text(key, g, r, hw)})
    return rules


def run(P: pd.DataFrame, bench: str = "SPY", macro: dict | None = None) -> dict:
    """Semáforo de régimen actual + historia por estado + evaluación de la regla de exposición.

    macro: salida de fred.snapshot() (se usan macro["VIXCLS"]["value"] y macro["BAMLH0A0HYM2"]["value"] si existen,
    como dato actual). El historial de VIX/HY se pide a FRED; sin red se degrada a volatilidad realizada.
    """
    px = P[bench].dropna().astype(float)
    caveats: list[str] = []
    if len(px) < MIN_HIST + 60:
        return _clean({"asof": px.index[-1].strftime("%Y-%m-%d") if len(px) else None, "state": None, "score": None,
                       "inputs": {}, "rules": [], "history": {"by_state": {}, "vol_managed": None},
                       "verdict": "Historial de precios insuficiente para calcular el régimen.",
                       "caveats": ["Se necesitan al menos ~310 ruedas de historia."]})
    idx = px.index
    vix_h = _fred_history("VIXCLS")
    hy_h = _fred_history("BAMLH0A0HYM2") if vix_h is not None else None   # si no hay red, no reintentar
    vix, hy = _align(vix_h, idx), _align(hy_h, idx)
    cov_vix, cov_hy = float(vix.notna().mean()), float(hy.notna().mean())
    # dato actual desde macro (prevalece en la última fecha)
    v_now, h_now = _macro_value(macro, "VIXCLS", idx), _macro_value(macro, "BAMLH0A0HYM2", idx)
    if v_now is not None:
        vix.iloc[-1] = v_now
    if h_now is not None:
        hy.iloc[-1] = h_now
    st = state_series(px, vix, hy)
    last = st.iloc[-1]

    if cov_vix < 0.9:
        if vix_h is None:
            caveats.append("Sin historial de VIX (FRED no disponible): el estado histórico usa solo volatilidad "
                           "realizada, caída desde máximo y media de 200 ruedas" +
                           ("; el VIX actual solo vota en la última fecha." if v_now is not None else "."))
        else:
            caveats.append(f"El historial de VIX cubre solo {cov_vix * 100:.0f}% de las fechas; donde falta no vota.")
    if cov_hy < 0.9:
        caveats.append(f"El spread high yield cubre {cov_hy * 100:.0f}% de las fechas (FRED limita el historial de esa "
                       "serie); donde falta no vota, así que la definición del estado cambia levemente en el tiempo.")
    caveats += [
        "Las reglas y umbrales se fijaron a priori con valores convencionales, no se optimizaron sobre la historia.",
        "La muestra de ~10 años incluye pocas crisis (2018, 2020, 2022): las estadísticas por estado y la evaluación de la "
        "regla de exposición tienen poca potencia y pueden no repetirse.",
        "Las ventanas de 21 ruedas de las estadísticas por estado se solapan: la muestra efectiva es ~n/21 (campo n_eff).",
        "Resultado pasado no garantiza resultados futuros. Herramienta de investigación, no asesoría financiera.",
    ]

    by_state = _by_state(px, st)
    vm = _vol_managed(px, st)
    n_rules = int(last["n_rules"])
    state = last["state"]
    rules = _current_rules(last)
    reasons = [f"{r['label']} {_fmt(r['name'], r['value'])} ({r['state']})" for r in rules]
    verdict = (f"Régimen actual: {state} (puntaje {int(last['score'])} de {2 * n_rules}). Reglas: " + "; ".join(reasons) + ". ")
    b = by_state.get(state, {})
    if b.get("n"):
        verdict += (f"En el historial, tras días {state}s el benchmark rindió en promedio {b['fwd21_mean'] * 100:+.1f}% "
                    f"en las 21 ruedas siguientes (P10 {b['fwd21_p10'] * 100:+.1f}%) y cayó más de 5% en "
                    f"{b['prob_drop5'] * 100:.0f}% de los casos (n efectivo ~{b['n_eff']:.0f}). ")
    if vm:
        verdict += vm["verdict"]
    out = {
        "asof": idx[-1].strftime("%Y-%m-%d"), "state": state, "score": int(last["score"]), "max_score": 2 * n_rules,
        "inputs": {"vol_ewma_ann": last["vol_ewma_ann"], "vix": last["vix"], "drawdown_52w": last["drawdown_52w"],
                   "above_200d": (bool(last["sma200_gap"] >= 0) if pd.notna(last["sma200_gap"]) else None),
                   "hy_spread": last["hy_spread"]},
        "rules": rules,
        "history": {"by_state": by_state, "vol_managed": vm},
        "verdict": verdict, "caveats": caveats,
    }
    return _clean(out)


def _fmt(key: str, v: float) -> str:
    if key in ("vol_ewma_ann", "drawdown_52w", "sma200_gap"):
        return f"{v * 100:.1f}%"
    return f"{v:.1f}"
