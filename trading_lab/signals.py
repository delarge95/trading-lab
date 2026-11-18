"""Señales cuantitativas sobre una serie de precios diarios ajustados.

Todas las funciones usan solo datos hasta el último punto recibido (sin anticipación).
"""
from __future__ import annotations

import math
from statistics import NormalDist, pstdev

LOOKBACK = 252   # ~12 meses de ruedas
SKIP = 21        # se omite el último mes (reversión de corto plazo)
HORIZON = 21     # ~1 mes de ruedas


def momentum_12_1(prices: list[float], end: int | None = None) -> float | None:
    """Retorno de t-12m a t-1m. `end` = índice del último dato disponible."""
    end = len(prices) - 1 if end is None else end
    if end - LOOKBACK < 0:
        return None
    return prices[end - SKIP] / prices[end - LOOKBACK] - 1.0


def annual_vol(prices: list[float], window: int = 63) -> float | None:
    if len(prices) < window + 1:
        return None
    rets = [math.log(prices[i] / prices[i - 1]) for i in range(len(prices) - window, len(prices))]
    return pstdev(rets) * math.sqrt(252)


def wilson(k: int, n: int, conf: float = 0.95) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    z = NormalDist().inv_cdf(0.5 + conf / 2)
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, centre - half), min(1.0, centre + half))


def prob_up(prices: list[float], horizon: int = HORIZON) -> dict:
    """Probabilidad empírica de subida a `horizon` ruedas con IC de Wilson al 95%.

    Usa ventanas no solapadas hacia atrás. Devuelve la probabilidad incondicional y la
    condicionada a que el momentum 12-1 al inicio de la ventana tuviera el mismo signo
    que el actual. Las ventanas no solapadas hacen que n sea pequeño: el IC es amplio a propósito.
    """
    n = len(prices)
    cur_mom = momentum_12_1(prices)
    all_up = all_n = cond_up = cond_n = 0
    end = n - 1
    while end - horizon - LOOKBACK >= 0:
        start = end - horizon
        up = prices[end] > prices[start]
        all_n += 1
        all_up += up
        m = momentum_12_1(prices, start)
        if cur_mom is not None and m is not None and (m > 0) == (cur_mom > 0):
            cond_n += 1
            cond_up += up
        end -= horizon
    lo, hi = wilson(all_up, all_n)
    clo, chi = wilson(cond_up, cond_n)
    return {
        "horizon": horizon,
        "p_all": all_up / all_n if all_n else None, "ci_all": (lo, hi), "n_all": all_n,
        "p_cond": cond_up / cond_n if cond_n else None, "ci_cond": (clo, chi), "n_cond": cond_n,
        "momentum_positive": None if cur_mom is None else cur_mom > 0,
    }


def summarize(prices: list[tuple[str, float]]) -> dict:
    px = [p for _, p in prices]
    mom = momentum_12_1(px)
    return {
        "last_date": prices[-1][0], "last_price": px[-1], "n_obs": len(px),
        "momentum_12_1": mom,
        "trend": None if mom is None else ("positiva" if mom > 0 else "negativa"),
        "vol_63d": annual_vol(px, 63), "vol_252d": annual_vol(px, 252),
        "ret_21d": px[-1] / px[-22] - 1 if len(px) > 22 else None,
        "prob_up": prob_up(px),
    }
