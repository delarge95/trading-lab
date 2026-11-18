"""Backtest de tendencia sin sesgo de anticipación.

En cada rebalanceo i (cada 21 ruedas) la señal usa solo precios hasta i; la posición
(+1 largo / 0 fuera) gana el retorno de (i, i+21]. Se compara con comprar y mantener.
Períodos no solapados, costo por cambio de posición, sin tasa libre de riesgo (Sharpe sobre retorno total).
"""
from __future__ import annotations

import math
import random
from statistics import mean, stdev

from .signals import HORIZON, LOOKBACK, SKIP

PERIODS_PER_YEAR = 252 / HORIZON
GRID = (126, 189, 252)  # lookbacks candidatos para walk-forward (múltiplos de 21)


def sharpe(period_returns: list[float], periods_per_year: float = PERIODS_PER_YEAR) -> float | None:
    if len(period_returns) < 3:
        return None
    sd = stdev(period_returns)
    return None if sd == 0 else mean(period_returns) / sd * math.sqrt(periods_per_year)


def _momentum(prices: list[float], end: int, lookback: int) -> float:
    return prices[end - SKIP] / prices[end - lookback] - 1.0


def period_returns(prices: list[float], lookback: int = LOOKBACK, start: int | None = None,
                   stop: int | None = None, cost: float = 0.001) -> tuple[list[float], list[float]]:
    """(retornos de la estrategia, retornos de comprar y mantener) para i en range(start, stop, 21).

    La señal en i usa solo prices[:i+1]; el retorno cobrado es el de i a i+21.
    """
    n = len(prices)
    start = lookback if start is None else max(start, lookback)
    stop = n - HORIZON if stop is None else min(stop, n - HORIZON)
    strat, hold, pos_prev = [], [], 0
    for i in range(start, stop, HORIZON):
        sig = 1 if _momentum(prices, i, lookback) > 0 else 0
        r = prices[i + HORIZON] / prices[i] - 1.0
        strat.append(sig * r - abs(sig - pos_prev) * cost)
        hold.append(r)
        pos_prev = sig
    return strat, hold


def momentum_backtest(prices: list[float], cost: float = 0.001) -> dict:
    strat, hold = period_returns(prices, cost=cost)
    return {
        "periods": len(strat),
        "sharpe_strategy": sharpe(strat), "sharpe_buy_hold": sharpe(hold),
        "hit_rate_in_market": (sum(1 for s in strat if s > 0) / max(1, sum(1 for s in strat if s != 0))) if strat else None,
        "exposure": sum(1 for s in strat if s != 0) / len(strat) if strat else None,
    }


def walk_forward(prices: list[float], grid: tuple[int, ...] = GRID, min_train: int = 756,
                 step: int = 252, cost: float = 0.001) -> dict:
    """Validación walk-forward con selección de parámetro solo con datos pasados.

    Cada `step` ruedas se elige el lookback con mayor Sharpe *en muestra* (períodos que terminan
    antes de s) y se opera con él en el bloque siguiente, fuera de muestra. Devuelve los retornos
    fuera de muestra de la estrategia y de comprar y mantener sobre las mismas fechas.
    """
    n = len(prices)
    s = max(grid) + min_train
    s -= s % HORIZON  # alinear a la grilla de rebalanceo
    oos, hold, chosen = [], [], []
    while s + HORIZON < n:
        best, best_sr = grid[-1], -math.inf
        for lb in grid:
            ins, _ = period_returns(prices, lb, lb, s - HORIZON + 1, cost)
            sr = sharpe(ins)
            if sr is not None and sr > best_sr:
                best, best_sr = lb, sr
        # prices[:s+1] decide el parámetro; el bloque opera i en [s, s+step)
        o, h = period_returns(prices, best, s, min(s + step, n - HORIZON), cost)
        oos += o
        hold += h
        chosen += [best] * len(o)
        s += step
    return {"oos": oos, "hold": hold, "chosen": chosen,
            "sharpe_oos": sharpe(oos), "sharpe_hold_same_dates": sharpe(hold)}


def random_walk(n: int, seed: int, drift: float = 0.0, vol: float = 0.01) -> list[float]:
    rng = random.Random(seed)
    p, out = 100.0, []
    for _ in range(n):
        p *= math.exp(drift + rng.gauss(0, vol))
        out.append(p)
    return out


def null_check(n_days: int = 2520, seeds: int = 200) -> dict:
    """Con caminatas aleatorias sin tendencia, el Sharpe medio de la estrategia debe ser ≈ 0.

    Un valor claramente distinto de 0 indicaría anticipación (look-ahead) en el backtest.
    """
    vals = [momentum_backtest(random_walk(n_days, s))["sharpe_strategy"] for s in range(seeds)]
    vals = [v for v in vals if v is not None]
    m = mean(vals)
    se = stdev(vals) / math.sqrt(len(vals))
    return {"mean_sharpe": m, "std_error": se, "z": m / se if se else 0.0, "seeds": len(vals)}
