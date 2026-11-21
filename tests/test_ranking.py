import json
from pathlib import Path

from trading_lab import ranking

FIX = Path(__file__).parent / "fixtures" / "forecast_sample.json"


def _fc():
    return json.loads(FIX.read_text(encoding="utf-8"))


def test_ranking_from_real_fixture_has_criteria_and_evidence():
    r = ranking.build(_fc())
    keys = {c["key"] for c in r["criteria"]}
    assert {"riesgo_caida", "volatilidad", "asimetria", "prob_subida", "momentum"} <= keys
    by = {c["key"]: c for c in r["criteria"]}
    assert by["prob_subida"]["evidence"] == ranking.EV_NONE          # sin ventaja demostrada en el fixture
    assert by["riesgo_caida"]["evidence"] == ranking.EV_OK
    for c in r["criteria"]:
        assert len(c["favorable"]) <= ranking.TOP_N and len(c["desfavorable"]) <= ranking.TOP_N
        assert json.dumps(c)                                          # serializable


def test_direction_and_ordering():
    r = ranking.build(_fc())
    by = {c["key"]: c for c in r["criteria"]}
    d = by["riesgo_caida"]
    assert d["favorable"][0]["value"] <= d["favorable"][-1]["value"]      # menor riesgo primero
    assert d["desfavorable"][0]["value"] >= d["desfavorable"][-1]["value"]
    assert d["favorable"][0]["value"] <= d["desfavorable"][0]["value"]
    m = by["momentum"]
    assert m["favorable"][0]["value"] >= m["favorable"][-1]["value"]      # mayor primero


def test_none_values_are_skipped_and_optional_blocks():
    fc = _fc()
    first = next(iter(fc["tickers"]))
    fc["tickers"][first]["vol63"] = None
    r = ranking.build(fc, convergence={first: {"managers": ["A", "B"]}}, insiders={first: {"opportunistic": 2}})
    vol = next(c for c in r["criteria"] if c["key"] == "volatilidad")
    assert all(x["ticker"] != first for x in vol["favorable"] + vol["desfavorable"])
    g = next(c for c in r["criteria"] if c["key"] == "gestores")
    assert g["favorable"][0]["ticker"] == first and g["favorable"][0]["value"] == 2.0


def test_summary_and_disclaimer_never_recommend():
    r = ranking.build(_fc())
    text = json.dumps(r, ensure_ascii=False).lower()
    assert "no son una recomendación" in text and "no asesoría financiera" in text
    for bad in ("compra ", "vende ", "te recomiendo"):
        assert bad not in text
