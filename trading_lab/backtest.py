"""Backtest de tendencia 12-1 sin sesgo de anticipación.

En cada rebalanceo i (cada 21 ruedas) la señal usa solo precios hasta i; la posición
(+1 largo / 0 fuera) gana el retorno de (i, i+21]. Se compara con comprar y mantener.
"""
from __future__ import annotations

import math
import random
from statistics import mean, pstdev

from .signals import HORIZON, LOOKBACK, SKIP, momentum_12_1


def sharpe(period_returns: list[float], periods_per_year: float = 252 / HORIZON) -> float | None:
    if len(period_returns) < 3:
        return None
    sd = pstdev(period_returns)
    return None if sd == 0 else mean(period_returns) / sd * math.sqrt(periods_per_year)


def momentum_backtest(prices: list[float], cost: float = 0.001) -> dict:
    strat, hold = [], []
    pos_prev = 0
    for i in range(LOOKBACK, len(prices) - HORIZON, HORIZON):
        sig = 1 if momentum_12_1(prices, i) > 0 else 0
        r = prices[i + HORIZON] / prices[i] - 1.0
        turnover = abs(sig - pos_prev)
        strat.append(sig * r - turnover * cost)
        hold.append(r)
        pos_prev = sig
    return {
        "periods": len(strat),
        "sharpe_strategy": sharpe(strat), "sharpe_buy_hold": sharpe(hold),
        "hit_rate_in_market": (sum(1 for s in strat if s > 0) / max(1, sum(1 for s in strat if s != 0))) if strat else None,
        "exposure": sum(1 for s in strat if s != 0) / len(strat) if strat else None,
    }


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
    se = pstdev(vals) / math.sqrt(len(vals))
    return {"mean_sharpe": m, "std_error": se, "z": m / se if se else 0.0, "seeds": len(vals)}
