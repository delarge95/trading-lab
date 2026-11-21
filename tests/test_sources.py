"""Pruebas del marco de evaluación de fuentes (sin red)."""
import numpy as np
import pandas as pd
import pytest

from trading_lab import sources


def make_prices(n_stocks=40, n_days=2300, seed=0, k=0.0, factor=None, vol=0.01):
    """Precios sintéticos; `k` planta deriva diaria = k * factor (el factor es persistente por acción)."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2014-01-02", periods=n_days)
    f = rng.normal(size=n_stocks) if factor is None else factor
    mkt = rng.normal(0.0002, 0.008, n_days)
    cols = {"SPY": 100 * np.exp(np.cumsum(mkt))}
    for i in range(n_stocks):
        r = mkt + rng.normal(0, vol, n_days) + k * f[i]
        cols[f"S{i:02d}"] = 100 * np.exp(np.cumsum(r))
    return pd.DataFrame(cols, index=dates), f


def quarterly_factor(P, f, noise=0.5, seed=1):
    """Factor observado trimestralmente (fechas dispersas): f + ruido de medición."""
    rng = np.random.default_rng(seed)
    qd = P.index[::63]
    vals = f[None, :] + rng.normal(0, noise, (len(qd), len(f)))
    return pd.DataFrame(vals, index=qd, columns=[c for c in P.columns if c != "SPY"])


def test_planted_signal_is_detected():
    P, f = make_prices(seed=2, k=0.0003)
    r = sources.evaluate_factor(P, quarterly_factor(P, f), horizon=21, name="plantado")
    assert r["ic"] > 0.05 and r["ic_ci"][0] > 0
    assert r["top_excess"] > 0 and r["has_edge"]
    assert r["verdict"] == "supera a la tasa base"
    assert r["stable"] and len(r["halves"]) == 2


def test_inverted_signal_is_not_a_win():
    P, f = make_prices(seed=3, k=0.0003)
    r = sources.evaluate_factor(P, -quarterly_factor(P, f), horizon=21)
    assert r["ic"] < 0 and r["verdict"] == "no supera la tasa base"


def test_noise_is_not_detected_and_false_positives_controlled():
    wins = 0
    n = 40
    for seed in range(n):
        P, f = make_prices(n_stocks=30, n_days=1800, seed=100 + seed)
        noise = quarterly_factor(P, np.random.default_rng(seed + 7).normal(size=30), seed=seed)
        r = sources.evaluate_factor(P, noise, horizon=21)
        wins += r["verdict"] == "supera a la tasa base"
        if seed == 0:
            assert abs(r["ic"]) < 0.05 and r["verdict"] == "no supera la tasa base"
    assert wins / n <= 0.10          # nominal ~2.5% (más exigencia: top_excess > 0); 10% deja margen para 40 pruebas


def test_no_lookahead_in_alignment():
    P, f = make_prices(n_stocks=25, n_days=600, seed=4)
    fac = quarterly_factor(P, f)
    A = sources.align_factor(P, fac, max_age_days=200, lag_bars=1)
    cut = fac.index[3]
    fac2 = fac.copy()
    fac2.loc[fac2.index > cut] = 999.0                               # cambiar el "futuro"
    A2 = sources.align_factor(P, fac2, max_age_days=200, lag_bars=1)
    upto = P.index[P.index.get_loc(cut) + 1]                           # con lag 1 el dato de `cut` se usa desde la rueda siguiente
    pd.testing.assert_frame_equal(A.loc[:upto], A2.loc[:upto])
    # y el dato de la fecha `cut` no se usa en `cut`
    assert A.loc[cut].isna().all() or not np.allclose(A.loc[cut].values, fac.loc[cut].values)


def test_max_age_limits_stale_values():
    P, f = make_prices(n_stocks=25, n_days=400, seed=5)
    fac = quarterly_factor(P, f).iloc[:2]                              # solo 2 observaciones tempranas
    A = sources.align_factor(P, fac, max_age_days=60, lag_bars=0)
    assert A.iloc[-1].isna().all()                                     # vencidas
    A2 = sources.align_factor(P, fac, max_age_days=10000, lag_bars=0)
    assert A2.iloc[-1].notna().all()


def test_independent_of_future_data():
    """Cambiar precios y factor posteriores a `end` (+horizonte) no altera el resultado hasta `end`."""
    P, f = make_prices(n_stocks=30, n_days=1500, seed=6, k=0.0002)
    fac = quarterly_factor(P, f)
    end = P.index[1000]
    base = sources.evaluate_factor(P, fac, horizon=21, end=end)
    P2, fac2 = P.copy(), fac.copy()
    rng = np.random.default_rng(0)
    P2.iloc[1000 + 22:] = P2.iloc[1000 + 22:].values * rng.uniform(0.5, 2.0, P2.iloc[1000 + 22:].shape)
    fac2.loc[fac2.index > end] = rng.normal(size=fac2.loc[fac2.index > end].shape)
    again = sources.evaluate_factor(P2, fac2, horizon=21, end=end)
    for k in ("n_dates", "ic", "ic_ci", "top_excess", "top_excess_ci", "spread", "verdict"):
        assert base[k] == again[k], k


def test_insufficient_history_and_universe():
    P, f = make_prices(n_stocks=25, n_days=400, seed=7)
    fac = quarterly_factor(P, f)
    assert sources.evaluate_factor(P, fac.iloc[:, :5])["status"] == "universo insuficiente"
    r = sources.evaluate_factor(P, fac, end=P.index[40])
    assert r["status"] == "historia insuficiente"


def test_result_is_json_serializable():
    import json
    P, f = make_prices(seed=8, k=0.0002)
    json.dumps(sources.evaluate_factor(P, quarterly_factor(P, f)), default=float)


def _hist_for(P, f, k):
    """Historia sintética tipo fundamentals.history: columnas de las 5 métricas, por fecha de presentación."""
    out = {}
    rng = np.random.default_rng(11)
    for i, t in enumerate(c for c in P.columns if c != "SPY"):
        idx = P.index[::63]
        df = pd.DataFrame(index=idx)
        df["rev_growth_yoy"] = rng.normal(size=len(idx))                       # ruido
        df["op_margin_ttm"] = f[i] + rng.normal(0, 0.3, len(idx))              # con señal (si k > 0)
        df["fcf_margin_ttm"] = rng.normal(size=len(idx))
        df["debt_to_equity"] = rng.normal(size=len(idx))
        df["shares_chg_yoy"] = rng.normal(size=len(idx))
        out[t] = df
    return out


def test_evaluate_all_fundamentals_with_holm():
    P, f = make_prices(seed=9, k=0.0004)
    r = sources.evaluate_all_fundamentals(P, hist=_hist_for(P, f, 0.0004))
    fs = r["factors"]
    assert set(fs) == set(sources.FACTOR_BUILDERS)
    assert fs["op_margin"]["verdict"] == "supera a la tasa base" and fs["op_margin"]["survives_holm"]
    for k in ("rev_growth", "fcf_margin", "low_leverage", "low_dilution"):
        assert fs[k]["p_holm"] >= fs[k]["p_value"]
    ev = r["evidence"]
    assert set(ev) == {"op_margin_ttm", "rev_growth_yoy", "fcf_margin_ttm", "debt_to_equity", "shares_chg_yoy"}
    assert ev["op_margin_ttm"] == "validado" and ev["rev_growth_yoy"] == "sin ventaja demostrada"
    assert any("supervivencia" in c for c in r["caveats"])
    assert "op_margin" not in r["verdict"] and "Margen operativo" in r["verdict"]


def test_evaluate_alt_requires_history(tmp_path):
    P, f = make_prices(n_stocks=25, n_days=500, seed=10)
    short = pd.DataFrame({"date": pd.bdate_range("2026-01-01", periods=10).repeat(2),
                          "ticker": ["S00", "S01"] * 10, "iv": 0.3})
    assert sources.evaluate_alt(P, short, "iv") == {"status": "historia insuficiente", "n_dates": 10}
    assert sources.evaluate_alt(P, pd.DataFrame(), "iv")["n_dates"] == 0


def test_load_alt_history(tmp_path):
    import json
    (tmp_path / "2026-11-18.json").write_text(json.dumps({"tickers": {"AAA": {"iv": 0.3, "short_pct": 2.0}}}))
    (tmp_path / "2026-11-19.json").write_text(json.dumps({"AAA": {"iv": 0.31}}))
    df = sources.load_alt_history(tmp_path)
    assert len(df) == 2 and df["date"].nunique() == 2 and "iv" in df.columns


def test_evidence_not_tested_without_data():
    P, f = make_prices(n_stocks=25, n_days=500, seed=12)
    r = sources.evaluate_all_fundamentals(P, hist={})
    assert set(r["evidence"].values()) == {"no probado aquí"}
