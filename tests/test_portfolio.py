import json
import math

import numpy as np
import pandas as pd
import pytest

from trading_lab import portfolio as pf
from trading_lab import site
from trading_lab.forecast import ewma_sigma


def _prices(T=900, N=6, seed=1, with_bench=False):
    rng = np.random.default_rng(seed)
    common = rng.normal(0.0003, 0.008, T)
    cols = {}
    for j in range(N):
        r = 0.6 * common + rng.normal(0.0002, 0.012 + 0.002 * j, T)
        cols[f"S{j}"] = 100 * np.exp(np.cumsum(r))
    if with_bench:
        cols["SPY"] = 100 * np.exp(np.cumsum(common))
    idx = pd.bdate_range("2020-01-01", periods=T)
    return pd.DataFrame(cols, index=idx)


@pytest.fixture(scope="module")
def P():
    return _prices()


def test_shape_keys_and_sizes(P):
    stocks = list(P.columns)
    out = pf.joint_samples(P, stocks, horizons=(21, 63), n=300)
    assert set(out) == {"h21", "h63"}
    for h in (21, 63):
        b = out[f"h{h}"]
        assert b["tickers"] == stocks
        assert set(b["sigma_now"]) == set(stocks)
        assert len(b["z"]) == len(b["dates"]) == 300
        assert all(len(r) == len(stocks) for r in b["z"])
        assert all(math.isfinite(v) for r in b["z"] for v in r)
        assert all(round(v, 2) == v for r in b["z"] for v in r)
        assert len(set(b["dates"])) == len(b["dates"])             # fechas distintas
        # sigma_now = sigma_ewma actual * sqrt(h)
        s = ewma_sigma(P[stocks]).iloc[-1]
        for t in stocks:
            assert b["sigma_now"][t] == pytest.approx(s[t] * math.sqrt(h), abs=1e-5)
    json.dumps(out, allow_nan=False)


def test_dates_regular_and_in_range(P):
    out = pf.joint_samples(P, list(P.columns), horizons=(21,), n=200)
    d = pd.to_datetime(out["h21"]["dates"])
    pos = P.index.get_indexer(d)
    assert pos.min() >= 252 and pos.max() <= len(P) - 1 - 21
    gaps = np.diff(pos)
    assert gaps.min() >= 1 and gaps.max() - gaps.min() <= 1       # rejilla regular
    # historia corta: usa todas las fechas disponibles en vez de repetir
    short = pf.joint_samples(P.iloc[:300], list(P.columns), horizons=(21,), n=400)
    assert len(short["h21"]["dates"]) == 300 - 1 - 21 - 252 + 1


def test_z_matches_definition(P):
    stocks = list(P.columns)
    out = pf.joint_samples(P, stocks, horizons=(21,), n=100)["h21"]
    sig = ewma_sigma(P[stocks])
    for k in (0, 40, 99):
        t = P.index.get_loc(pd.Timestamp(out["dates"][k]))
        for j, s in enumerate(stocks):
            expect = math.log(P[s].iloc[t + 21] / P[s].iloc[t]) / (sig[s].iloc[t] * math.sqrt(21))
            assert out["z"][k][j] == pytest.approx(round(expect, 2), abs=0.011)


def test_no_lookahead_future_prices_do_not_change_earlier_z(P):
    stocks = list(P.columns)
    h = 21
    base = pf.joint_samples(P, stocks, horizons=(h,), n=200)[f"h{h}"]
    cut = 600                                                     # se altera todo lo posterior a la posición 600
    P2 = P.copy()
    rng = np.random.default_rng(5)
    P2.iloc[cut + 1:] = P2.iloc[cut + 1:].values * rng.uniform(0.3, 3.0, P2.iloc[cut + 1:].shape)
    alt = pf.joint_samples(P2, stocks, horizons=(h,), n=200)[f"h{h}"]
    assert alt["dates"] == base["dates"]
    pos = P.index.get_indexer(pd.to_datetime(base["dates"]))
    safe = np.where(pos + h <= cut)[0]
    assert len(safe) > 50
    for k in safe:
        assert alt["z"][k] == base["z"][k]
    changed = np.where(pos > cut)[0]
    assert any(alt["z"][k] != base["z"][k] for k in changed)       # y lo alterado sí cambia


def test_joint_samples_keep_cross_correlation():
    rng = np.random.default_rng(3)
    T = 1200
    common = rng.normal(0, 0.012, T)
    cols = {f"S{j}": 100 * np.exp(np.cumsum(common + rng.normal(0, 0.004, T))) for j in range(2)}
    cols["IND"] = 100 * np.exp(np.cumsum(rng.normal(0, 0.012, T)))
    Q = pd.DataFrame(cols, index=pd.bdate_range("2019-01-01", periods=T))
    out = pf.joint_samples(Q, list(Q.columns), horizons=(21,), n=400)["h21"]
    z = np.array(out["z"])
    assert np.corrcoef(z[:, 0], z[:, 1])[0, 1] > 0.6               # factor común conservado en las muestras
    assert abs(np.corrcoef(z[:, 0], z[:, 2])[0, 1]) < 0.35         # y la independiente no correlaciona


def test_ticker_with_too_little_data_is_dropped():
    P = _prices(T=900, N=3)
    P.iloc[:700, 0] = np.nan                                      # S0 casi sin historia en las fechas de muestra
    out = pf.joint_samples(P, list(P.columns), horizons=(21,), n=200)["h21"]
    assert "S0" not in out["tickers"] and "S0" not in out["sigma_now"]
    assert out["tickers"] == ["S1", "S2"] and all(len(r) == 2 for r in out["z"])


def test_unknown_and_short_history():
    P = _prices(T=200, N=2)
    assert pf.joint_samples(P, ["S0", "S1", "NOPE"], horizons=(21,)) == {}


def test_sector_map_covers_universe():
    from trading_lab import universe
    sec = pf.sector_map()
    tickers = universe.load_config()["tickers"]
    missing = [t for t in tickers if t not in sec]
    assert not missing, missing
    assert len(set(sec.values()) - {"otro"}) <= 11
    assert sec["AAPL"].startswith("Tecnolog") and sec["XOM"] == "Energía"


def test_build_adds_sectors_and_site_roundtrip(P):
    stocks = list(P.columns)
    blk = pf.build(P, stocks, n=300, sectors={"S0": "Salud"})
    assert blk["sectors"]["S0"] == "Salud" and blk["sectors"]["S1"] == "otro"
    assert blk["caveats"]
    fc = {"asof": "2026-11-19", "n_stocks": 0, "tickers": {}, "eval": {}, "risk_validation": {}}
    d = site.build_dashboard(fc, portfolio=blk)
    assert set(d["portfolio"]) >= {"h21", "h63", "sectors"}
    text = json.dumps(d, allow_nan=False)
    assert "NaN" not in text
    # tamaño razonable: 6 tickers x 300 x 2 horizontes
    assert len(text) < 200_000
