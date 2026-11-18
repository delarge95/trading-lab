import math
import random
from statistics import NormalDist

import pytest

from trading_lab import backtest, rigor


def _iid(n, mu, sigma, seed, skewed=False):
    rng = random.Random(seed)
    if skewed:  # retornos asimétricos y de colas pesadas, con media teórica mu y desvío ~sigma
        raw = [rng.lognormvariate(0, 0.8) for _ in range(n)]
        m = math.exp(0.8 ** 2 / 2)
        sd = math.sqrt((math.exp(0.8 ** 2) - 1) * math.exp(0.8 ** 2))
        return [mu + sigma * (r - m) / sd for r in raw]
    return [rng.gauss(mu, sigma) for _ in range(n)]


# ---------------------------------------------------------------- fórmulas
def test_expected_max_sr_matches_published_value():
    # Bailey y López de Prado: con 100 pruebas y varianza de Sharpe 1, E[max] ≈ 2.53
    assert rigor.expected_max_sr(100, 1.0) == pytest.approx(2.5326, abs=0.01)
    assert rigor.expected_max_sr(1, 1.0) == 0.0


def test_psr_matches_closed_form_for_normal():
    x = _iid(500, 0.01, 0.04, 1)
    sr = rigor.sr_period(x)
    g3, g4 = rigor.skew_kurt(x)
    se = math.sqrt((1 - g3 * sr + (g4 - 1) / 4 * sr * sr) / 499)
    assert rigor.psr(x, 0.0) == pytest.approx(NormalDist().cdf(sr / se), abs=1e-12)
    # para datos casi normales, g3≈0 y g4≈3 → se ≈ sqrt((1+sr²/2)/(n-1))
    assert se == pytest.approx(math.sqrt((1 + sr * sr / 2) / 499), rel=0.1)


def test_dsr_below_psr_with_many_trials():
    x = _iid(107, 0.01, 0.04, 2)
    trials = [rigor.sr_period(_iid(107, 0.0, 0.04, s)) for s in range(10, 30)]
    assert rigor.dsr(x, trials) < rigor.psr(x, 0.0)
    assert rigor.dsr(x, [rigor.sr_period(x)]) == pytest.approx(rigor.psr(x, 0.0))


@pytest.mark.parametrize("skewed", [False, True])
def test_sharpe_ci_coverage(skewed):
    """El IC al 95% del Sharpe debe cubrir el valor verdadero ≈ 95% de las veces."""
    mu, sigma, n = 0.01, 0.04, 107
    true_sr = mu / sigma * math.sqrt(rigor.PPY)
    hits = 0
    sims = 500
    for s in range(sims):
        _, lo, hi = rigor.sharpe_ci(_iid(n, mu, sigma, 1000 + s, skewed))
        hits += lo <= true_sr <= hi
    assert 0.90 <= hits / sims <= 0.99, hits / sims


def test_holm_adjustment():
    assert rigor.holm([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])
    assert rigor.holm([0.5]) == [0.5]
    assert all(a >= p for a, p in zip(rigor.holm([0.2, 0.01, 0.6]), [0.2, 0.01, 0.6]))


# ---------------------------------------------------------------- bootstrap
def test_bootstrap_detects_real_edge_and_not_noise():
    base = _iid(107, 0.005, 0.04, 3)
    edge = [r + 0.02 for r in base]           # misma serie con +2%/mes de alfa
    res = rigor.block_bootstrap_diff(edge, base, n_boot=800, seed=1)
    assert res["p_beat"] < 0.05 and res["ci"][0] > 0

    a, b = _iid(107, 0.005, 0.04, 4), _iid(107, 0.005, 0.04, 5)
    false_pos = sum(rigor.block_bootstrap_diff(_iid(107, 0.005, 0.04, 100 + s),
                                               _iid(107, 0.005, 0.04, 900 + s), n_boot=300, seed=s)["p_beat"] < 0.05
                    for s in range(60))
    assert false_pos / 60 < 0.15, false_pos          # ≈5% esperado (cota holgada)


def test_bootstrap_identical_series_has_zero_diff():
    x = _iid(60, 0.005, 0.04, 6)
    res = rigor.block_bootstrap_diff(x, list(x), n_boot=200, seed=2)
    assert res["diff"] == 0 and res["ci"] == (0.0, 0.0)


# ---------------------------------------------------------------- walk-forward
def test_walk_forward_no_lookahead():
    p = backtest.random_walk(3000, seed=11)
    wf = backtest.walk_forward(p)
    first_block = 12                                   # step 252 / 21 períodos
    s0 = (max(backtest.GRID) + 756) // 21 * 21         # inicio del primer bloque fuera de muestra
    q = p[:s0 + 253] + [x * 5 for x in p[s0 + 253:]]   # se altera todo lo posterior a lo usado por el bloque 1
    wf2 = backtest.walk_forward(q)
    assert wf["oos"][:first_block] == wf2["oos"][:first_block]
    assert wf["chosen"][:first_block] == wf2["chosen"][:first_block]


def test_walk_forward_null_sharpe_near_zero():
    vals = [backtest.walk_forward(backtest.random_walk(3780, s))["sharpe_oos"] for s in range(60)]
    vals = [v for v in vals if v is not None]
    m = sum(vals) / len(vals)
    sd = (sum((v - m) ** 2 for v in vals) / (len(vals) - 1)) ** 0.5
    assert abs(m / (sd / len(vals) ** 0.5)) < 3.0


def test_walk_forward_aligned_with_buy_hold():
    p = backtest.random_walk(3000, seed=12)
    wf = backtest.walk_forward(p)
    assert len(wf["oos"]) == len(wf["hold"]) == len(wf["chosen"]) > 24
