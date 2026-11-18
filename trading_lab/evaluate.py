"""Evaluación estadística de la estrategia de tendencia 12-1 sobre varios tickers."""
from __future__ import annotations

from . import backtest, rigor


def evaluate(series: dict[str, list[float]], n_boot: int = 2000, alpha: float = 0.05) -> dict:
    """Devuelve métricas por ticker y un veredicto global.

    - `trials` para el DSR = todos los tickers evaluados (se mira el mejor, se corrige por ello).
    - Holm se aplica sobre los valores p de "la estrategia supera a comprar y mantener".
    """
    per: dict[str, dict] = {}
    for t, px in series.items():
        strat, hold = backtest.period_returns(px)
        if len(strat) < 24:
            continue
        per[t] = {"strat": strat, "hold": hold}
    if not per:
        return {"tickers": {}, "verdict": "datos insuficientes", "n_trials": 0, "alpha": alpha}

    trial_srs = [rigor.sr_period(v["strat"]) for v in per.values()]
    names = list(per)
    boots = {t: rigor.block_bootstrap_diff(per[t]["strat"], per[t]["hold"], n_boot=n_boot, seed=i)
             for i, t in enumerate(names)}
    holm_p = rigor.holm([boots[t]["p_beat"] for t in names])

    out = {}
    for t, p_adj in zip(names, holm_p):
        s = per[t]["strat"]
        sr, lo, hi = rigor.sharpe_ci(s)
        wf = backtest.walk_forward(series[t])
        wf_res = None
        if len(wf["oos"]) >= 12:
            b = rigor.block_bootstrap_diff(wf["oos"], wf["hold"], n_boot=n_boot, seed=1000 + len(t))
            wf_res = {"sharpe_oos": wf["sharpe_oos"], "sharpe_hold": wf["sharpe_hold_same_dates"],
                      "periods": len(wf["oos"]), "diff": b["diff"], "ci": b["ci"], "p_beat": b["p_beat"],
                      "lookbacks": sorted(set(wf["chosen"]))}
        out[t] = {
            "periods": len(s), "sharpe": sr, "sharpe_ci": (lo, hi),
            "psr0": rigor.psr(s, 0.0), "dsr": rigor.dsr(s, trial_srs),
            "vs_hold": {**boots[t], "p_holm": p_adj},
            "walk_forward": wf_res,
        }
    sig = [t for t, r in out.items() if r["vs_hold"]["p_holm"] < alpha and r["vs_hold"]["diff"] > 0]
    worse = [t for t, r in out.items() if r["vs_hold"]["ci"][1] < 0]
    if sig:
        verdict = f"La estrategia supera a comprar y mantener con significancia (Holm, α={alpha}) en: {', '.join(sig)}."
    else:
        verdict = (f"Ningún ticker muestra que la estrategia supere a comprar y mantener (Holm, α={alpha}, "
                   f"{len(out)} pruebas)." + (f" Significativamente peor que comprar y mantener: {', '.join(worse)}." if worse else ""))
    return {"tickers": out, "verdict": verdict, "n_trials": len(out), "alpha": alpha}
