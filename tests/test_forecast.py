import math

import numpy as np
import pandas as pd
import pytest

from trading_lab import forecast


def make_series(n_stocks=30, n_days=1800, seed=0, signal=0.0, vol=0.01):
    """Series sintéticas. `signal` > 0 planta una deriva persistente por acción (momentum predictivo)."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2015-01-02", periods=n_days)
    out = {}
    mkt = rng.normal(0.0002, 0.008, n_days)
    for i in range(n_stocks + 1):
        drift = np.zeros(n_days)
        for t in range(1, n_days):
            drift[t] = 0.99 * drift[t - 1] + signal * rng.normal()
        r = (mkt + rng.normal(0, vol, n_days) + drift) if i > 0 else mkt
        p = 100 * np.exp(np.cumsum(r))
        name = "SPY" if i == 0 else f"S{i:02d}"
        out[name] = [(d.strftime("%Y-%m-%d"), float(v)) for d, v in zip(dates, p)]
    return out


@pytest.fixture(scope="module")
def noise_panel():
    P = forecast.price_frame(make_series(n_days=2400, seed=1), "SPY")
    return P, forecast.Panel(P, "SPY")


@pytest.fixture(scope="module")
def signal_panel():
    P = forecast.price_frame(make_series(n_days=2400, seed=2, signal=0.0003), "SPY")
    return P, forecast.Panel(P, "SPY")


# ------------------------------------------------------------------ sin anticipación
def test_features_ignore_the_future():
    P = forecast.price_frame(make_series(seed=3), "SPY")
    a = forecast.Panel(P, "SPY")
    P2 = P.copy()
    P2.iloc[1500:] *= 3.0
    b = forecast.Panel(P2, "SPY")
    rows = a.t <= 1499
    assert np.allclose(a.X[rows & a.ok], b.X[rows & b.ok], equal_nan=True)


def test_walk_forward_first_fold_independent_of_later_prices():
    P = forecast.price_frame(make_series(seed=4), "SPY")
    a = forecast.walk_forward(forecast.Panel(P, "SPY"), "up", 21)
    P2 = P.copy()
    P2.iloc[1262 + 63:] *= 5.0                      # cambia todo lo posterior a lo que usa el primer bloque
    b = forecast.walk_forward(forecast.Panel(P2, "SPY"), "up", 21)
    first = a["t"] < 1008 + 252
    assert first.sum() > 100
    assert np.allclose(a["p"][first], b["p"][b["t"] < 1008 + 252])


# ------------------------------------------------------------------ habilidad real vs ruido
def test_planted_signal_is_detected(signal_panel):
    _, panel = signal_panel
    ev = forecast.evaluate(forecast.walk_forward(panel, "up", 21), 21)
    assert ev["bss_ci"][0] > 0 and ev["has_edge"]
    assert ev["auc"] > 0.55 and ev["ic_ci"][0] > 0


def test_noise_has_no_edge_and_probabilities_collapse_to_base_rate(noise_panel):
    _, panel = noise_panel
    oos = forecast.walk_forward(panel, "up", 21)
    ev = forecast.evaluate(oos, 21)
    assert not ev["has_edge"]
    assert ev["bss"] < 0.03                       # puntual ruidoso: pocas épocas de mercado independientes
    live = forecast.live(panel, "up", 21, ev)
    ps = np.array([v["p"] for v in live.values()])
    assert abs(ps.mean() - ev["base_rate"]) < 0.06 and ps.std() < 0.06   # sin ventaja: casi sin dispersión


def test_platt_recovers_calibration_and_flattens_noise():
    rng = np.random.default_rng(0)
    p = rng.uniform(0.2, 0.8, 20000)
    y = (rng.random(20000) < p).astype(float)
    a, b = forecast.platt(p, y)
    assert abs(a) < 0.1 and 0.9 < b < 1.1
    a2, b2 = forecast.platt(p, (rng.random(20000) < 0.55).astype(float))   # y independiente de p
    assert b2 < 0.2


def test_calibration_bins_have_intervals(signal_panel):
    _, panel = signal_panel
    ev = forecast.evaluate(forecast.walk_forward(panel, "up", 21), 21)
    assert len(ev["bins"]) >= 8
    for bn in ev["bins"]:
        assert 0 <= bn["ci"][0] <= bn["freq"] <= bn["ci"][1] <= 1


# ------------------------------------------------------------------ rangos y riesgo de caída
def test_risk_ranges_match_theory_for_iid_returns():
    rng = np.random.default_rng(5)
    n = 4000
    P = pd.DataFrame({"X": 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))},
                     index=pd.bdate_range("2005-01-03", periods=n))
    r = forecast.risk_ranges(P, ["X"])["X"][21]
    # el percentil se mide en unidades de la volatilidad actual (EWMA, que fluctúa alrededor de 1%)
    z10 = math.log(1 + r["p10"]) / r["sigma"]
    z90 = math.log(1 + r["p90"]) / r["sigma"]
    assert -1.7 < z10 < -1.0 and 1.0 < z90 < 1.7      # ≈ ±1.28 (más el sesgo de deriva de una sola trayectoria)
    assert 0.02 < r["sigma"] < 0.08
    # P(caída >10% en 21 ruedas) ≈ 2*Phi(-0.10/0.0458) ≈ 3% (reflexión; algo menos con datos discretos)
    assert 0.005 < r["dd"]["10"] < 0.05
    assert r["dd"]["20"] < r["dd"]["10"]


def test_risk_ranges_scale_with_current_volatility():
    rng = np.random.default_rng(6)
    n = 3000
    calm = rng.normal(0, 0.01, n)
    wild = np.concatenate([calm[:-60], rng.normal(0, 0.03, 60)])      # volatilidad reciente 3x
    idx = pd.bdate_range("2008-01-01", periods=n)
    a = forecast.risk_ranges(pd.DataFrame({"X": 100 * np.exp(np.cumsum(calm))}, index=idx), ["X"])["X"][21]
    b = forecast.risk_ranges(pd.DataFrame({"X": 100 * np.exp(np.cumsum(wild))}, index=idx), ["X"])["X"][21]
    assert (b["p90"] - b["p10"]) > 1.8 * (a["p90"] - a["p10"])
    assert b["dd"]["10"] > a["dd"]["10"]


def test_run_end_to_end_small_universe():
    res = forecast.run(make_series(n_stocks=25, n_days=1700, seed=7, signal=0.0001))
    assert res["n_stocks"] == 25 and set(res["eval"]) == {"up5", "up21", "up63", "rel21"}
    t = next(iter(res["tickers"].values()))
    assert 0 < t["p"]["up21"]["p"] < 1 and t["p"]["up21"]["lo"] <= t["p"]["up21"]["p"] <= t["p"]["up21"]["hi"] + 1e-9
    assert t["risk"][21]["p10"] < t["risk"][21]["p50"] < t["risk"][21]["p90"]
