import copy
import json
from pathlib import Path

import pytest

from trading_lab import alerts

FIXTURE = Path(__file__).parent / "fixtures" / "forecast_sample.json"
TODAY = "2026-11-19"


# ------------------------------------------------------------------ datos sintéticos
def tk(p21=0.55, dd=0.10, price=100.0, key=21):
    risk = {key: {"p10": -0.1, "p50": 0.01, "p90": 0.1, "sigma": 0.1, "dd": {"10": dd + 0.05, "20": 0.01}, "dd_cal": dd}}
    return {"price": price, "p": {"up21": {"p": p21, "p_raw": p21, "lo": p21 - 0.01, "hi": p21 + 0.01}}, "risk": risk}


def cur(**tickers):
    return {"asof": TODAY, "tickers": tickers}


def prev(**tickers):
    return {"asof": "2026-11-18", "vix": None, "tickers": {t: {"p21": p, "dd21": d, "price": 100.0}
                                                            for t, (p, d) in tickers.items()}}


def macro(v):
    return {"VIXCLS": {"label": "VIX", "date": TODAY, "value": v, "change_21": 0.0}}


def build(current=None, previous=None, macro_=None, insiders=None, managers=None, cusip_map=None):
    return alerts.build(current or cur(), previous, macro_, insiders, managers, cusip_map, today=TODAY)


def kinds(res, kind):
    return [a for a in res["alerts"] if a["kind"] == kind]


# ------------------------------------------------------------------ 1. dd_shift
@pytest.mark.parametrize("dd_prev,dd_now,expected", [
    (0.20, 0.25, None),        # sube 0.05 < 0.10
    (0.20, 0.2999, None),      # justo por debajo
    (0.20, 0.30, "media"),     # exactamente el umbral (0.30-0.20 en float = 0.0999...)
    (0.20, 0.34, "media"),     # < 0.15
    (0.20, 0.35, "alta"),      # exactamente 0.15
    (0.20, 0.60, "alta"),
    (0.30, 0.10, None),        # bajar no genera alerta
])
def test_dd_shift_thresholds(dd_prev, dd_now, expected):
    res = build(cur(AAA=tk(dd=dd_now)), prev(AAA=(0.55, dd_prev)))
    got = kinds(res, "dd_shift")
    if expected is None:
        assert got == []
    else:
        assert len(got) == 1 and got[0]["severity"] == expected and got[0]["ticker"] == "AAA"
        assert "sube de" in got[0]["title"] and "%" in got[0]["title"]


# ------------------------------------------------------------------ 2. prob_shift
@pytest.mark.parametrize("p_prev,p_now,fires", [
    (0.50, 0.55, False), (0.50, 0.5999, False),
    (0.50, 0.60, True),        # exactamente en el umbral
    (0.60, 0.50, True),        # bajada también
    (0.70, 0.50, True),
])
def test_prob_shift_thresholds(p_prev, p_now, fires):
    res = build(cur(AAA=tk(p21=p_now, dd=0.1)), prev(AAA=(p_prev, 0.1)))
    got = kinds(res, "prob_shift")
    assert bool(got) == fires
    if fires:
        assert got[0]["severity"] == "media"
        assert "sube" in got[0]["title"] or "baja" in got[0]["title"]


# ------------------------------------------------------------------ sin previous
def test_no_previous_no_change_alerts():
    cu = cur(AAA=tk(p21=0.9, dd=0.9))
    res = build(cu, None, macro(26.0))
    assert kinds(res, "dd_shift") == [] and kinds(res, "prob_shift") == []
    assert kinds(res, "vix") == []          # 26 sin previo: no hay cruce que afirmar
    assert [a["kind"] for a in res["alerts"]] == ["top_risk"]


def test_ticker_missing_in_previous_ignored():
    res = build(cur(AAA=tk(p21=0.9, dd=0.9)), prev(BBB=(0.5, 0.1)))
    assert kinds(res, "dd_shift") == [] and kinds(res, "prob_shift") == []


def test_previous_with_none_dd_ignored():
    res = build(cur(AAA=tk(dd=0.9)), prev(AAA=(0.55, None)))
    assert kinds(res, "dd_shift") == []


# ------------------------------------------------------------------ 3. vix
@pytest.mark.parametrize("v,vp,sev", [
    (29.9, None, None),
    (30.0, None, "alta"),      # exactamente el umbral, sin previo
    (45.0, 20.0, "alta"),
    (24.9, 20.0, None),
    (25.0, 24.9, "media"),     # cruce exacto al alza
    (27.0, 22.0, "media"),
    (27.0, 26.0, None),        # ya estaba arriba
    (22.0, 27.0, None),        # cruce a la baja
    (27.0, None, None),        # sin previo no se evalúa el cruce
])
def test_vix_rules(v, vp, sev):
    previous = None if vp is None else {**prev(), "vix": vp}
    res = build(cur(), previous, macro(v))
    got = kinds(res, "vix")
    if sev is None:
        assert got == []
    else:
        assert len(got) == 1 and got[0]["severity"] == sev and got[0]["ticker"] is None
        assert got[0]["id"] == f"vix:-:{TODAY}"


def test_vix_missing_or_error():
    assert kinds(build(cur(), None, None), "vix") == []
    assert kinds(build(cur(), None, {"VIXCLS": {"label": "VIX", "error": "x"}}), "vix") == []


# ------------------------------------------------------------------ 4. insiders
def ins(opp, val, routine=0, unclassified=0):
    return {"window_days": 90, "n_buys": opp + routine + unclassified, "routine": routine, "opportunistic": opp,
            "unclassified": unclassified, "buy_value": val, "opportunistic_value": val, "sell_value": 0.0,
            "buys": [{"owner": f"Persona {i}", "role": "Officer", "value": val / max(opp, 1), "date": "2026-11-01",
                      "class": "oportunista"} for i in range(opp)]}


@pytest.mark.parametrize("opp,val,sev", [
    (0, 0.0, None),
    (1, 249_999.0, None),
    (1, 250_000.0, "media"),   # exactamente en el umbral
    (1, 5_000_000.0, "media"),
    (2, 1_000.0, "alta"),      # 2 compras, valor irrelevante
    (5, 10.0, "alta"),
])
def test_insider_rules(opp, val, sev):
    res = build(insiders={"XYZ": ins(opp, val)})
    got = kinds(res, "insider_buy")
    if sev is None:
        assert got == []
    else:
        assert len(got) == 1 and got[0]["severity"] == sev and got[0]["ticker"] == "XYZ"
        assert "Persona 0" in got[0]["detail"]


def test_insider_routine_and_unclassified_do_not_alert():
    res = build(insiders={"A": ins(0, 0.0, routine=6), "B": ins(0, 0.0, unclassified=4), "C": {"error": "x"}})
    assert kinds(res, "insider_buy") == []


# ------------------------------------------------------------------ 5-6. 13F
def mgr(name, rows, period="2026-09-30", stale=False):
    return {"name": name, "period": period, "stale": stale,
            "top": [{"cusip": c, "name": n, "value": 1e9 * w, "weight": w, "change": ch} for c, n, w, ch in rows]}


CMAP = {"111": "AAA", "222": "BBB", "333": None}


def test_convergence_13f_basic_and_unmapped():
    ms = [
        mgr("M1", [("111", "AAA INC", 0.10, "NUEVA"), ("333", "SIN TICKER SA", 0.05, "=")]),
        mgr("M2", [("111", "AAA INC", 0.20, "NUEVA"), ("333", "SIN TICKER SA", 0.07, "+5%")]),
        mgr("M3", [("111", "AAA INC", 0.30, "-6%"), ("999", "OTRA CO", 0.02, "=")], stale=True),
        {"name": "M4", "cik": 1, "error": "sin 13F-HR"},
    ]
    c = alerts.convergence_13f(ms, CMAP)
    assert set(c) == {"AAA", "~SIN TICKER SA", "~OTRA CO"}
    assert c["AAA"]["managers"] == ["M1", "M2", "M3"]
    assert c["AAA"]["new_by"] == ["M1", "M2"]
    assert c["AAA"]["avg_weight"] == pytest.approx(0.20)
    assert c["~SIN TICKER SA"]["managers"] == ["M1", "M2"]
    assert c["~SIN TICKER SA"]["avg_weight"] == pytest.approx(0.06)
    assert c["~OTRA CO"]["new_by"] == []


def test_convergence_stale_manager_counts_but_not_new():
    ms = [mgr("M1", [("111", "AAA", 0.1, "NUEVA")], stale=True)]
    c = alerts.convergence_13f(ms, CMAP)
    assert c["AAA"]["managers"] == ["M1"] and c["AAA"]["new_by"] == []


def test_13f_new_severity():
    ms = [mgr("M1", [("111", "AAA INC", 0.1, "NUEVA"), ("222", "BBB INC", 0.1, "NUEVA")]),
          mgr("M2", [("111", "AAA INC", 0.1, "NUEVA")])]
    res = build(managers=ms, cusip_map=CMAP)
    got = {a["ticker"]: a["severity"] for a in kinds(res, "13f_new")}
    assert got == {"AAA": "alta", "BBB": "info"}


def test_13f_new_requires_same_quarter_and_fresh_data():
    ms = [mgr("M1", [("111", "AAA", 0.1, "NUEVA")], period="2026-06-30"),
          mgr("M2", [("111", "AAA", 0.1, "NUEVA")], period="2026-09-30"),
          mgr("M3", [("222", "BBB", 0.1, "NUEVA")], stale=True),
          mgr("M4", [("222", "BBB", 0.1, "NUEVA")], stale=True)]
    res = build(managers=ms, cusip_map=CMAP)
    got = {a["ticker"]: a["severity"] for a in kinds(res, "13f_new")}
    assert got == {"AAA": "info"}          # trimestres distintos no suman; los vencidos no cuentan


def test_13f_new_unmapped_cusip_uses_name():
    ms = [mgr("M1", [("333", "SIN TICKER SA", 0.1, "NUEVA")])]
    res = build(managers=ms, cusip_map=CMAP)
    a = kinds(res, "13f_new")[0]
    assert a["ticker"] == "~SIN TICKER SA" and a["id"] == f"13f_new:~SIN TICKER SA:{TODAY}"


@pytest.mark.parametrize("n,fires", [(2, False), (3, True), (4, True)])
def test_13f_convergence_threshold(n, fires):
    ms = [mgr(f"M{i}", [("111", "AAA", 0.1, "=")]) for i in range(n)]
    got = kinds(build(managers=ms, cusip_map=CMAP), "13f_convergence")
    assert bool(got) == fires
    if fires:
        assert got[0]["severity"] == "info" and got[0]["ticker"] == "AAA"


def test_13f_none_inputs():
    res = build(managers=None, cusip_map=None)
    assert kinds(res, "13f_new") == [] and kinds(res, "13f_convergence") == []


# ------------------------------------------------------------------ 7. stale
@pytest.mark.parametrize("asof,fires", [
    ("2026-11-19", False), ("2026-11-15", False),     # 4 días exactos: no
    ("2026-11-14", True), ("2026-10-01", True),
])
def test_stale_data(asof, fires):
    res = build({"asof": asof, "tickers": {}})
    got = kinds(res, "stale_data")
    assert bool(got) == fires
    if fires:
        assert got[0]["severity"] == "alta"


# ------------------------------------------------------------------ 8. top_risk
def test_top_risk_three_highest():
    cu = cur(A=tk(dd=0.10), B=tk(dd=0.40), C=tk(dd=0.30), D=tk(dd=0.20), E=tk(dd=0.35))
    got = kinds(build(cu), "top_risk")
    assert len(got) == 1 and got[0]["severity"] == "info" and got[0]["ticker"] is None
    assert got[0]["title"].endswith("B, E, C")
    assert "D" not in got[0]["title"] and "40%" in got[0]["detail"]


def test_top_risk_fewer_than_three_and_empty():
    assert "A" in kinds(build(cur(A=tk(dd=0.1))), "top_risk")[0]["title"]
    assert kinds(build(cur()), "top_risk") == []


def test_dd_falls_back_to_raw_when_no_dd_cal():
    t = tk(dd=0.1)
    del t["risk"][21]["dd_cal"]
    assert alerts._dd21(t["risk"]) == pytest.approx(0.15)
    assert alerts.snapshot(cur(A=t), None)["tickers"]["A"]["dd21"] == pytest.approx(0.15)


# ------------------------------------------------------------------ ids, orden, counts
def test_ids_unique_order_and_counts():
    cu = cur(ZZZ=tk(p21=0.2, dd=0.5), AAA=tk(p21=0.2, dd=0.45), MMM=tk(p21=0.9, dd=0.2))
    pv = {**prev(ZZZ=(0.6, 0.2), AAA=(0.6, 0.3), MMM=(0.6, 0.1)), "vix": 20.0}
    ms = [mgr(f"M{i}", [("111", "AAA INC", 0.1, "NUEVA")]) for i in range(3)]
    res = build(cu, pv, macro(26.0), {"AAA": ins(1, 300_000.0), "ZZZ": ins(3, 10.0)}, ms, CMAP)
    ids = [a["id"] for a in res["alerts"]]
    assert len(ids) == len(set(ids))
    ranks = [alerts._SEV_RANK[a["severity"]] for a in res["alerts"]]
    assert ranks == sorted(ranks)
    for sev in ("alta", "media", "info"):
        tick = [a["ticker"] or "" for a in res["alerts"] if a["severity"] == sev]
        assert tick == sorted(tick)
    assert res["counts"] == {s: sum(1 for a in res["alerts"] if a["severity"] == s) for s in ("alta", "media", "info")}
    assert sum(res["counts"].values()) == len(res["alerts"]) and res["generated"] == TODAY
    for a in res["alerts"]:
        assert a["id"] == f"{a['kind']}:{a['ticker'] or '-'}:{TODAY}"
        assert set(a) == {"id", "severity", "kind", "ticker", "title", "detail"} and a["title"] and a["detail"]


# ------------------------------------------------------------------ snapshot
def test_snapshot_shape_and_str_int_keys():
    for key in (21, "21"):
        s = alerts.snapshot({"asof": TODAY, "tickers": {"A": tk(p21=0.6, dd=0.2, price=50.0, key=key)}}, macro(18.5))
        assert s == {"asof": TODAY, "vix": 18.5, "tickers": {"A": {"p21": 0.6, "dd21": 0.2, "price": 50.0}}}


def test_snapshot_skips_incomplete_and_no_macro():
    s = alerts.snapshot({"asof": TODAY, "tickers": {"A": {"price": 1.0, "p": {}, "risk": {}}}}, None)
    assert s["tickers"] == {} and s["vix"] is None


def test_snapshot_roundtrip(tmp_path):
    s = alerts.snapshot(cur(A=tk(), B=tk(p21=0.4, dd=0.3)), macro(21.0))
    p = tmp_path / "sub" / "snap.json"
    alerts.save_snapshot(p, s)
    assert alerts.load_snapshot(p) == s
    alerts.save_snapshot(p, {**s, "vix": 1.0})       # sobrescribe
    assert alerts.load_snapshot(p)["vix"] == 1.0
    assert [f.name for f in p.parent.iterdir()] == ["snap.json"]       # sin temporales sobrantes


def test_load_snapshot_robust(tmp_path):
    assert alerts.load_snapshot(tmp_path / "no_existe.json") is None
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert alerts.load_snapshot(bad) is None
    bad.write_text("[1, 2]", encoding="utf-8")
    assert alerts.load_snapshot(bad) is None
    bad.write_bytes(b"\xff\xfe\x00")
    assert alerts.load_snapshot(bad) is None
    bad.write_text("", encoding="utf-8")
    assert alerts.load_snapshot(bad) is None


# ------------------------------------------------------------------ push_text
def A(sev, title):
    return {"id": title, "severity": sev, "kind": "k", "ticker": None, "title": title, "detail": "d"}


def test_push_none_without_alta():
    assert alerts.push_text({"alerts": [A("media", "x"), A("info", "y")]}) is None
    assert alerts.push_text({"alerts": []}) is None


def test_push_short():
    t = alerts.push_text({"alerts": [A("alta", "VIX en 31.0"), A("media", "otra")]})
    assert "VIX en 31.0" in t and "otra" not in t and "1 alerta alta" in t


def test_push_long_truncates_without_breaking_words():
    words = ["palabrota"] * 60
    res = {"alerts": [A("alta", " ".join(words)), A("alta", "segunda")]}
    for n in (30, 60, 100, 180):
        t = alerts.push_text(res, max_len=n)
        assert len(t) <= n and t.endswith("…")
        body = t[:-1]
        assert all(w in ("palabrota", "Trading", "Lab:", "2", "alertas", "altas", "altas.") for w in body.split())


@pytest.mark.parametrize("n", [1, 2, 5, 17])
def test_push_tiny_max_len(n):
    t = alerts.push_text({"alerts": [A("alta", "Titulo largo de prueba")]}, max_len=n)
    assert len(t) <= n


def test_push_exact_fit_not_truncated():
    res = {"alerts": [A("alta", "x")]}
    full = alerts.push_text(res, max_len=1000)
    assert alerts.push_text(res, max_len=len(full)) == full
    assert alerts.push_text(res, max_len=len(full) - 1).endswith("…")


# ------------------------------------------------------------------ fixture real
@pytest.fixture(scope="module")
def sample():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_real_fixture_snapshot_and_build(sample):
    snap = alerts.snapshot(sample, macro(18.0))
    assert snap["asof"] == sample["asof"] and len(snap["tickers"]) == len(sample["tickers"])
    assert all(0 <= v["p21"] <= 1 and v["dd21"] is not None and v["price"] > 0 for v in snap["tickers"].values())
    res = alerts.build(sample, None, macro(18.0), None, None, None, today=sample["asof"])
    assert [a["kind"] for a in res["alerts"]] == ["top_risk"]
    assert res["counts"] == {"alta": 0, "media": 0, "info": 1}
    json.dumps(res)


def test_real_fixture_vs_perturbed_previous(sample):
    snap = alerts.snapshot(sample, macro(18.0))
    pv = copy.deepcopy(snap)
    pv["tickers"]["NVDA"]["dd21"] -= 0.20
    pv["tickers"]["AAPL"]["p21"] -= 0.12
    res = alerts.build(sample, pv, macro(18.0), None, None, None, today=sample["asof"])
    by = {(a["kind"], a["ticker"]): a["severity"] for a in res["alerts"]}
    assert by[("dd_shift", "NVDA")] == "alta" and by[("prob_shift", "AAPL")] == "media"
    # el mismo snapshot contra sí mismo no produce alertas de cambio
    same = alerts.build(sample, snap, macro(18.0), None, None, None, today=sample["asof"])
    assert [a["kind"] for a in same["alerts"]] == ["top_risk"]


def test_real_fixture_int_keys_equivalent(sample):
    conv = copy.deepcopy(sample)
    for t in conv["tickers"].values():
        t["risk"] = {int(k): v for k, v in t["risk"].items()}
    assert alerts.snapshot(conv, None) == alerts.snapshot(sample, None)
    assert alerts.build(conv, None, None, None, None, None, today=TODAY) == \
        alerts.build(sample, None, None, None, None, None, today=TODAY)


def test_real_cusip_map_and_stale_with_fixture(sample):
    cmap = json.loads((Path(__file__).parent.parent / "data" / "cusip_map.json").read_text(encoding="utf-8"))
    ms = [mgr(f"M{i}", [("037833100", "APPLE INC", 0.1, "NUEVA")]) for i in range(3)]
    res = alerts.build(sample, None, None, None, ms, cmap, today="2026-12-31")
    k = {(a["kind"], a["ticker"]): a["severity"] for a in res["alerts"]}
    assert k[("13f_new", "AAPL")] == "alta" and k[("13f_convergence", "AAPL")] == "info"
    assert k[("stale_data", None)] == "alta"
