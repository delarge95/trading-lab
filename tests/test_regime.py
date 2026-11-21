import json
import math

import numpy as np
import pandas as pd
import pytest

from trading_lab import regime


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Ninguna prueba toca la red: sin historial de FRED salvo que la prueba lo inyecte."""
    monkeypatch.setattr(regime, "_fred_history", lambda sid: None)


def _frame(rets: np.ndarray, start="2015-01-02") -> pd.DataFrame:
    idx = pd.bdate_range(start, periods=len(rets))
    return pd.DataFrame({"SPY": 100 * np.cumprod(1 + rets)}, index=idx)


def _calm_bull(n=700, seed=0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return _frame(rng.normal(0.0006, 0.004, n))


def _crash(seed=1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    calm = rng.normal(0.0005, 0.005, 500)
    fall = rng.normal(-0.015, 0.02, 30)
    return _frame(np.concatenate([calm, fall]))


def _walk(seed: int, n=2600) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return _frame(rng.normal(0.0003, 0.01, n))


def _assert_no_nan(obj):
    json.dumps(obj, allow_nan=False)   # falla con NaN/inf


# ---------------------------------------------------------------- sin anticipación
def test_state_has_no_lookahead():
    P = _walk(3, 900)
    px = P["SPY"]
    base = regime.state_series(px)
    cut = 600
    alt = px.copy()
    alt.iloc[cut + 1:] = alt.iloc[cut + 1:] * np.random.default_rng(9).uniform(0.3, 3.0, len(alt) - cut - 1)
    other = regime.state_series(alt)
    a, b = base.iloc[:cut + 1], other.iloc[:cut + 1]
    assert (a["state"].fillna("-") == b["state"].fillna("-")).all()
    pd.testing.assert_frame_equal(a.drop(columns="state"), b.drop(columns="state"))


def test_run_state_ignores_future_via_truncation():
    P = _walk(4, 1000)
    full = regime.state_series(P["SPY"])
    trunc = regime.state_series(P["SPY"].iloc[:700])
    assert (full["state"].iloc[:700].fillna("-") == trunc["state"].fillna("-")).all()


# ---------------------------------------------------------------- escenarios
def test_calm_bull_is_green():
    out = regime.run(_calm_bull(), "SPY", macro={"VIXCLS": {"value": 13.0}})
    assert out["state"] == "verde"
    assert out["score"] == 0
    assert out["inputs"]["above_200d"] is True


def test_crash_with_high_vol_is_red():
    out = regime.run(_crash(), "SPY", macro={"VIXCLS": {"value": 45.0}, "BAMLH0A0HYM2": {"value": 8.5}})
    assert out["state"] == "rojo"
    assert out["inputs"]["drawdown_52w"] < -0.15
    assert out["inputs"]["above_200d"] is False
    assert {r["state"] for r in out["rules"]} == {"rojo"}


def test_mixed_signals_is_yellow():
    # tendencia sana pero VIX en zona intermedia y volatilidad intermedia
    out = regime.run(_calm_bull(), "SPY", macro={"VIXCLS": {"value": 25.0}, "BAMLH0A0HYM2": {"value": 5.0}})
    assert out["state"] in ("verde", "amarillo")
    assert any(r["name"] == "vix" and r["state"] == "amarillo" for r in out["rules"])


# ---------------------------------------------------------------- esquema
def test_schema_and_no_nan():
    out = regime.run(_walk(5), "SPY", macro={"VIXCLS": {"value": 18.0}})
    for k in ("asof", "state", "score", "inputs", "rules", "history", "verdict", "caveats"):
        assert k in out
    assert out["state"] in regime.STATES
    assert isinstance(out["score"], int)
    for k in ("vol_ewma_ann", "vix", "drawdown_52w", "above_200d", "hy_spread"):
        assert k in out["inputs"]
    for r in out["rules"]:
        assert set(("name", "value", "state", "threshold")) <= set(r)
    bs = out["history"]["by_state"]
    assert set(bs) == set(regime.STATES)
    for s in bs.values():
        for k in ("share", "fwd21_mean", "fwd21_p10", "prob_drop5"):
            assert k in s
    assert sum(s["share"] for s in bs.values()) == pytest.approx(1.0)
    vm = out["history"]["vol_managed"]
    for k in ("sharpe", "sharpe_bh", "diff_sharpe", "diff_ci", "p_beat", "max_dd", "max_dd_bh", "verdict"):
        assert k in vm
    assert out["caveats"] and isinstance(out["verdict"], str)
    _assert_no_nan(out)


def test_prob_drop5_and_fwd_are_consistent():
    out = regime.run(_crash(), "SPY")
    for s in out["history"]["by_state"].values():
        if s["prob_drop5"] is not None:
            assert 0.0 <= s["prob_drop5"] <= 1.0
            assert s["fwd21_p10"] <= s["fwd21_mean"] + 1e-9 or s["n"] < 30


# ---------------------------------------------------------------- degradación
def test_degrades_without_vix_history():
    out = regime.run(_walk(6), "SPY")   # sin red y sin macro
    assert out["inputs"]["vix"] is None
    assert any("VIX" in c for c in out["caveats"])
    assert all(r["name"] != "vix" for r in out["rules"])
    _assert_no_nan(out)


def test_current_vix_from_macro_votes_without_history():
    out = regime.run(_walk(6), "SPY", macro={"VIXCLS": {"value": 38.0}})
    assert out["inputs"]["vix"] == 38.0
    assert any(r["name"] == "vix" and r["state"] == "rojo" for r in out["rules"])
    assert any("VIX" in c for c in out["caveats"])   # aun así avisa que no hay historial


def test_macro_with_error_entry_is_ignored():
    out = regime.run(_walk(6), "SPY", macro={"VIXCLS": {"label": "VIX", "error": "timeout"}})
    assert out["inputs"]["vix"] is None


def test_uses_vix_history_when_available(monkeypatch):
    P = _walk(7)
    vix = pd.Series(15.0, index=P.index)
    monkeypatch.setattr(regime, "_fred_history", lambda sid: vix if sid == "VIXCLS" else None)
    out = regime.run(P, "SPY")
    assert out["inputs"]["vix"] == 15.0
    assert not any("Sin historial de VIX" in c for c in out["caveats"])


def test_insufficient_history_does_not_crash():
    out = regime.run(_walk(1, 100), "SPY")
    assert out["state"] is None
    _assert_no_nan(out)


# ---------------------------------------------------------------- utilidad de la regla de exposición
def test_exposure_rule_not_significantly_better_on_random_walk():
    not_better = 0
    seeds = range(12)
    for s in seeds:
        vm = regime.run(_walk(100 + s), "SPY")["history"]["vol_managed"]
        if not (vm["diff_sharpe"] > 0 and vm["p_beat"] < 0.05):
            not_better += 1
    assert not_better >= 10


def test_verdict_mentions_drawdown_only_when_not_significant():
    v = {"periods": 100, "sharpe": 0.8, "sharpe_bh": 0.9, "diff_sharpe": -0.1, "diff_ci": [-0.5, 0.3], "p_beat": 0.7,
         "max_dd": -0.15, "max_dd_bh": -0.34, "cagr": 0.06, "cagr_bh": 0.12}
    txt = regime._vm_verdict(v)
    assert "NO mejora" in txt and "drawdown" in txt
    v.update(diff_sharpe=0.4, diff_ci=[0.1, 0.7], p_beat=0.01)
    assert "significancia" in regime._vm_verdict(v)
