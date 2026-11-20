import json

import numpy as np
import pandas as pd
import pytest

from trading_lab import forecast, lab


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
def noise_P():
    return forecast.price_frame(make_series(n_days=2400, seed=11), "SPY")


@pytest.fixture(scope="module")
def noise_run(noise_P):
    return lab.run(noise_P)


@pytest.fixture(scope="module")
def signal_run():
    P = forecast.price_frame(make_series(n_days=2400, seed=2, signal=0.0003), "SPY")
    return lab.run(P)


# ------------------------------------------------------------------ (a) sin anticipación
def test_no_lookahead(noise_P):
    k = 1500
    P2 = noise_P.copy()
    rng = np.random.default_rng(5)
    P2.iloc[k:] = P2.iloc[k:].values * rng.uniform(0.3, 3.0, size=(len(P2) - k, P2.shape[1]))
    a, b = lab.simulate(noise_P), lab.simulate(P2)
    assert a["idx"] == b["idx"]
    before = [n for n, i in enumerate(a["idx"]) if i < k]
    closed = [n for n, i in enumerate(a["idx"]) if i + 21 < k]
    assert len(before) > 30 and len(closed) > 30
    for r in lab.RULES:
        for n in before:                                   # la selección solo ve precios hasta i
            assert a["picks"][r][n] == b["picks"][r][n]
        for n in closed:                                   # y los retornos de períodos ya cerrados no cambian
            assert a["ret"][r][n] == pytest.approx(b["ret"][r][n])
    for n in closed:
        assert a["ew"][n] == pytest.approx(b["ew"][n])
        assert a["bench"][n] == pytest.approx(b["bench"][n])


# ------------------------------------------------------------------ (b) ruido
def test_noise_has_no_significant_rule(noise_run):
    for r, v in noise_run["rules"].items():
        assert v["p_holm"] >= 0.05, r
        assert abs(v["annual_excess_vs_ew"]) < 0.06, r
    assert "Ninguna" in noise_run["verdict"]


# ------------------------------------------------------------------ (c) señal plantada
def test_planted_momentum_beats_ew(signal_run):
    m = signal_run["rules"]["mom12_1"]
    assert m["p_holm"] < 0.05
    assert m["diff_sharpe_vs_ew"] > 0 and m["annual_excess_vs_ew"] > 0
    assert "mom12_1" in signal_run["verdict"] and "Ninguna" not in signal_run["verdict"]


# ------------------------------------------------------------------ (d) costos
def test_cost_reduces_return_with_turnover(noise_P):
    free = lab.simulate(noise_P, cost=0.0)
    paid = lab.simulate(noise_P, cost=0.005)
    for r in lab.RULES:
        rot = np.array(paid["rotation"][r])
        assert rot.mean() > 0.05
        assert np.allclose(np.array(free["ret"][r]) - np.array(paid["ret"][r]), 0.005 * rot)
        assert sum(paid["ret"][r]) < sum(free["ret"][r])
    # la cartera de la primera fecha se compra entera
    assert all(paid["rotation"][r][0] == 1.0 for r in lab.RULES)


# ------------------------------------------------------------------ (f) esquema
def test_schema_matches_contract(noise_run, noise_P):
    out = noise_run
    assert set(out) == {"rules", "ew", "bench", "verdict", "caveats", "picks_now"}
    assert set(out["rules"]) == {"mom12_1", "lowvol", "reversal1m", "near_high"}
    keys = {"label", "periods", "sharpe", "sharpe_ci", "annual_excess_vs_ew", "diff_sharpe_vs_ew", "diff_ci",
            "p_beat_ew", "p_holm", "dsr", "max_drawdown", "turnover"}
    for v in out["rules"].values():
        assert set(v) == keys
        assert len(v["sharpe_ci"]) == 2 and v["sharpe_ci"][0] < v["sharpe"] < v["sharpe_ci"][1]
        assert len(v["diff_ci"]) == 2
        assert 0 <= v["p_beat_ew"] <= v["p_holm"] <= 1 and 0 <= v["dsr"] <= 1
        assert -1 <= v["max_drawdown"] <= 0 and 0 < v["turnover"] <= 1
        assert isinstance(v["periods"], int)
    assert set(out["ew"]) == {"periods", "sharpe", "sharpe_ci"} and set(out["bench"]) == {"sharpe"}
    assert isinstance(out["verdict"], str) and len(out["caveats"]) >= 3
    text = " ".join(out["caveats"]).lower()
    assert "supervivencia" in text and "impuestos" in text and "futuro" in text
    for picks in out["picks_now"].values():
        assert len(picks) == 10 and len(set(picks)) == 10
    json.dumps(out)                                          # serializable
    # picks_now = selección con el último dato
    stocks = [c for c in noise_P.columns if c != "SPY"]
    mom = forecast.raw_features(noise_P[stocks])["mom12_1"].iloc[-1].sort_values(ascending=False)
    assert out["picks_now"]["mom12_1"] == list(mom.index[:10])
    low = forecast.raw_features(noise_P[stocks])["vol63"].iloc[-1].sort_values()
    assert out["picks_now"]["lowvol"] == list(low.index[:10])


# ------------------------------------------------------------------ (e) libro de picks
@pytest.fixture(scope="module")
def ledger_P():
    return forecast.price_frame(make_series(n_stocks=20, n_days=700, seed=7), "SPY")


def test_ledger_open_close_idempotent(tmp_path, ledger_P):
    P, path = ledger_P, tmp_path / "sub" / "ledger.json"
    d0 = P.index[300]
    s = lab.update_ledger(path, P, today=d0)
    assert s["entries_total"] == 4 and s["as_of"] == d0.strftime("%Y-%m-%d")
    assert all(v["closed"] == 0 and v["open_since"] == s["as_of"] and "insuficiente" in v["note"] for v in s["rules"].values())
    first = path.read_text(encoding="utf-8")
    assert lab.update_ledger(path, P, today=d0) == s                   # idempotente el mismo día
    assert path.read_text(encoding="utf-8") == first
    lab.update_ledger(path, P, today=P.index[310])                     # 10 ruedas: no cierra ni duplica
    assert len(json.loads(path.read_text(encoding="utf-8"))["entries"]) == 4

    d1 = P.index[330]                                                  # 30 ruedas: cierra con el precio de la rueda 300+21
    s = lab.update_ledger(path, P, today=d1)
    assert s["entries_total"] == 8
    entries = json.loads(path.read_text(encoding="utf-8"))["entries"]
    closed = [e for e in entries if e["status"] == "cerrada"]
    assert len(closed) == 4 and {e["rule"] for e in closed} == set(lab.RULES)
    exit_day = P.index[321]
    stocks = [c for c in P.columns if c != "SPY"]
    for e in closed:
        hand = np.mean([P.loc[exit_day, t] / P.loc[d0, t] - 1 for t in e["tickers"]])
        ew = np.mean([P.loc[exit_day, t] / P.loc[d0, t] - 1 for t in stocks])
        assert len(e["tickers"]) == 10 and set(e["ew_entry"]) == set(stocks)
        assert e["exit_date"] == exit_day.strftime("%Y-%m-%d") and e["date"] == d0.strftime("%Y-%m-%d")
        assert e["ret"] == pytest.approx(hand) and e["ew_ret"] == pytest.approx(ew)
        assert e["bench_ret"] == pytest.approx(P.loc[exit_day, "SPY"] / P.loc[d0, "SPY"] - 1)
        assert e["excess_vs_ew"] == pytest.approx(hand - ew)
    opens = [e for e in entries if e["status"] == "abierta"]
    assert len(opens) == 4 and all(e["date"] == d1.strftime("%Y-%m-%d") for e in opens)
    for v in s["rules"].values():
        assert v["closed"] == 1 and v["open_since"] == d1.strftime("%Y-%m-%d") and "n=1" in v["note"]
        assert v["hit_rate"] in (0.0, 1.0) and v["mean_excess_vs_ew"] is not None
    assert lab.update_ledger(path, P, today=d1) == s                   # idempotente tras cerrar


def test_ledger_reports_p_value_with_enough_closed(tmp_path, ledger_P):
    P, path = ledger_P, tmp_path / "ledger.json"
    s = None
    for k in range(14):                                                # 14 fechas separadas por hold: 13 cerradas
        s = lab.update_ledger(path, P, today=P.index[260 + 21 * k])
    for v in s["rules"].values():
        assert v["closed"] == 13 and "valor p" in v["note"] and "insuficiente" not in v["note"]
        assert 0 < float(v["note"].split(": ")[-1]) <= 1


def test_sign_flip_p_sanity():
    assert lab._sign_flip_p([0.01] * 15) < 0.001
    assert lab._sign_flip_p([0.01, -0.01] * 8) > 0.4
