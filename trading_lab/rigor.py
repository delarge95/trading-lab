"""Rigor estadístico para evaluar una estrategia.

- IC del Sharpe con asimetría y curtosis (Mertens 2002 / Lo 2002).
- PSR: probabilidad de que el Sharpe verdadero supere un umbral (Bailey y López de Prado 2012).
- DSR: PSR con umbral corregido por el número de pruebas realizadas (Bailey y López de Prado 2014).
- Bootstrap circular por bloques pareado: estrategia vs comprar y mantener.
- Corrección de Holm por pruebas múltiples.
Todo con retornos por período no solapados; los Sharpe anualizados usan 252/21 períodos por año.
"""
from __future__ import annotations

import math
import random
from statistics import NormalDist, mean, pstdev, stdev

N01 = NormalDist()
EULER_GAMMA = 0.5772156649015329
PPY = 252 / 21


def sr_period(x: list[float]) -> float:
    sd = stdev(x)
    return mean(x) / sd if sd > 0 else 0.0


def skew_kurt(x: list[float]) -> tuple[float, float]:
    """Asimetría y curtosis (no exceso) con momentos poblacionales."""
    m, sd = mean(x), pstdev(x)
    if sd == 0:
        return 0.0, 3.0
    n = len(x)
    return (sum(((v - m) / sd) ** 3 for v in x) / n, sum(((v - m) / sd) ** 4 for v in x) / n)


def sr_std_err(x: list[float]) -> float:
    """Error estándar del Sharpe por período, robusto a no normalidad."""
    sr, (g3, g4) = sr_period(x), skew_kurt(x)
    var = (1 - g3 * sr + (g4 - 1) / 4 * sr * sr) / (len(x) - 1)
    return math.sqrt(max(var, 1e-12))


def sharpe_ci(x: list[float], conf: float = 0.95, ppy: float = PPY) -> tuple[float, float, float]:
    """(Sharpe anualizado, límite inferior, límite superior)."""
    z = N01.inv_cdf(0.5 + conf / 2)
    sr, se = sr_period(x), sr_std_err(x)
    k = math.sqrt(ppy)
    return sr * k, (sr - z * se) * k, (sr + z * se) * k


def psr(x: list[float], sr_star: float = 0.0) -> float:
    """P(Sharpe verdadero > sr_star); sr_star por período (no anualizado)."""
    return N01.cdf((sr_period(x) - sr_star) / sr_std_err(x))


def expected_max_sr(n_trials: int, var_sr: float) -> float:
    """Sharpe máximo esperado entre n_trials pruebas sin edge (por período)."""
    if n_trials <= 1 or var_sr <= 0:
        return 0.0
    return math.sqrt(var_sr) * ((1 - EULER_GAMMA) * N01.inv_cdf(1 - 1 / n_trials)
                                + EULER_GAMMA * N01.inv_cdf(1 - 1 / (n_trials * math.e)))


def dsr(x: list[float], trial_srs: list[float]) -> float:
    """PSR contra el Sharpe máximo esperado entre las pruebas (srs por período) realizadas."""
    var = stdev(trial_srs) ** 2 if len(trial_srs) > 1 else 0.0
    return psr(x, expected_max_sr(len(trial_srs), var))


def block_bootstrap_diff(a: list[float], b: list[float], n_boot: int = 2000, block: int = 3,
                         seed: int = 0, ppy: float = PPY) -> dict:
    """Diferencia de Sharpe anualizado a-b con bootstrap circular por bloques (pares alineados).

    p_beat = fracción de remuestras con diferencia <= 0 (valor p unilateral de H0: a no supera a b).
    """
    n = len(a)
    assert n == len(b) and n >= 12
    rng = random.Random(seed)
    k = math.sqrt(ppy)
    diffs = []
    nb = -(-n // block)
    for _ in range(n_boot):
        idx = []
        for _ in range(nb):
            s = rng.randrange(n)
            idx.extend((s + j) % n for j in range(block))
        idx = idx[:n]
        ra, rb = [a[i] for i in idx], [b[i] for i in idx]
        sa, sb = stdev(ra), stdev(rb)
        if sa == 0 or sb == 0:
            continue
        diffs.append((mean(ra) / sa - mean(rb) / sb) * k)
    diffs.sort()
    m = len(diffs)
    return {
        "diff": (sr_period(a) - sr_period(b)) * k,
        "ci": (diffs[int(0.025 * m)], diffs[int(0.975 * m) - 1]),
        "p_beat": sum(1 for d in diffs if d <= 0) / m,
        "n_boot": m,
    }


def holm(pvals: list[float]) -> list[float]:
    """Valores p ajustados por Holm-Bonferroni (mismo orden que la entrada)."""
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    adj, running = [0.0] * m, 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvals[i]))
        adj[i] = running
    return adj
