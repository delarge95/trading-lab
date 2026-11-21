"""Pruebas de fundamentals.py con JSON sintético en el formato real de companyfacts (sin red)."""
from datetime import date

import pandas as pd
import pytest

from trading_lab import fundamentals as fd

Q_ENDS = [date(2021, 3, 31), date(2021, 6, 30), date(2021, 9, 30), date(2021, 12, 31),
          date(2022, 3, 31), date(2022, 6, 30), date(2022, 9, 30), date(2022, 12, 31),
          date(2023, 3, 31), date(2023, 6, 30), date(2023, 9, 30), date(2023, 12, 31)]


def _fact(start, end, val, form, filed, fy=None, fp=None):
    d = {"end": end, "val": val, "accn": f"a-{filed}", "fy": fy, "fp": fp, "form": form, "filed": filed}
    if start:
        d["start"] = start
    return d


def _filed(end: date, kind: str) -> str:
    """Fecha de presentación: 10-Q ~35 días después del cierre; 10-K ~60 días."""
    return (pd.Timestamp(end) + pd.Timedelta(days=60 if kind == "K" else 35)).strftime("%Y-%m-%d")


def flow_facts(quarters: dict, ytd_only: bool = False) -> list:
    """Hechos de un flujo como los presentaría la empresa: 10-Q con trimestre y acumulado, 10-K solo el año.

    quarters: {fecha de cierre: valor del trimestre aislado} para años fiscales calendario completos.
    ytd_only=True imita el flujo de caja: en 10-Q solo acumulado desde el inicio del año.
    """
    out = []
    for e, v in quarters.items():
        y, m = e.year, e.month
        start = date(y, 1, 1).isoformat()
        cum = sum(quarters.get(date(y, mm, 30 if mm in (6, 9) else 31), 0) for mm in range(3, m + 1, 3))
        if m == 12:
            out.append(_fact(start, e.isoformat(), cum, "10-K", _filed(e, "K"), y, "FY"))
        else:
            if not ytd_only or m == 3:
                qstart = date(y, m - 2, 1).isoformat()
                out.append(_fact(qstart, e.isoformat(), v, "10-Q", _filed(e, "Q"), y, f"Q{m // 3}"))
            if m > 3:
                out.append(_fact(start, e.isoformat(), cum, "10-Q", _filed(e, "Q"), y, f"Q{m // 3}"))
    return out


def make_json(rev, op=None, ni=None, cfo=None, capex=None, equity=None, debt=None, shares=None, rev_tag="Revenues"):
    g = {}

    def put(tag, facts, unit="USD"):
        if facts:
            g[tag] = {"label": tag, "units": {unit: facts}}

    put(rev_tag, flow_facts(rev))
    put("OperatingIncomeLoss", flow_facts(op) if op else None)
    put("NetIncomeLoss", flow_facts(ni) if ni else None)
    put("NetCashProvidedByUsedInOperatingActivities", flow_facts(cfo, True) if cfo else None)
    put("PaymentsToAcquirePropertyPlantAndEquipment", flow_facts(capex, True) if capex else None)
    if equity:
        put("StockholdersEquity", [_fact(None, e.isoformat(), v, "10-K" if e.month == 12 else "10-Q",
                                         _filed(e, "K" if e.month == 12 else "Q")) for e, v in equity.items()])
    if debt:
        put("LongTermDebtNoncurrent", [_fact(None, e.isoformat(), v, "10-K" if e.month == 12 else "10-Q",
                                             _filed(e, "K" if e.month == 12 else "Q")) for e, v in debt.items()])
    if shares:
        put("WeightedAverageNumberOfDilutedSharesOutstanding", flow_facts(shares), "shares")
    return {"cik": 1, "entityName": "SINTETICA", "facts": {"us-gaap": g, "dei": {}}}


REV = {e: 100.0 + 10 * i for i, e in enumerate(Q_ENDS)}                   # 100, 110, ..., 210
OP = {e: 0.2 * v for e, v in REV.items()}
CFO = {e: 0.3 * v for e, v in REV.items()}
CAPEX = {e: 0.1 * v for e, v in REV.items()}


def hist_of(j) -> pd.DataFrame:
    return fd.history_from_facts(fd.parse_companyfacts(j))


# ------------------------------------------------------------------ trimestres aislados
def test_isolated_quarters_from_ytd():
    cum = {
        (date(2022, 1, 1), date(2022, 3, 31)): 10.0,
        (date(2022, 1, 1), date(2022, 6, 30)): 25.0,
        (date(2022, 1, 1), date(2022, 9, 30)): 45.0,
        (date(2022, 1, 1), date(2022, 12, 31)): 70.0,
    }
    q = fd.isolated_quarters(cum)
    assert q == {date(2022, 3, 31): 10.0, date(2022, 6, 30): 15.0, date(2022, 9, 30): 20.0, date(2022, 12, 31): 25.0}


def test_isolated_quarters_missing_piece_gives_no_quarter():
    cum = {(date(2022, 1, 1), date(2022, 3, 31)): 10.0, (date(2022, 1, 1), date(2022, 9, 30)): 45.0,
           (date(2022, 1, 1), date(2022, 12, 31)): 70.0}
    q = fd.isolated_quarters(cum)
    assert date(2022, 9, 30) not in q                      # falta H1: 9M - Q1 no es un trimestre
    assert q[date(2022, 12, 31)] == 25.0                   # FY - 9M sí


def test_direct_quarter_preferred_over_derived():
    k = {(date(2022, 4, 1), date(2022, 6, 30)): 99.0, (date(2022, 1, 1), date(2022, 3, 31)): 10.0,
         (date(2022, 1, 1), date(2022, 6, 30)): 25.0}
    assert fd.isolated_quarters(k)[date(2022, 6, 30)] == 99.0


# ------------------------------------------------------------------ TTM y métricas
def test_ttm_and_margins_from_10q_10k_mix():
    h = hist_of(make_json(REV, OP, ni={e: 0.1 * v for e, v in REV.items()}, cfo=CFO, capex=CAPEX))
    last = h.iloc[-1]
    ttm = sum(REV[e] for e in Q_ENDS[-4:])
    prev = sum(REV[e] for e in Q_ENDS[-8:-4])
    assert last["revenue_ttm"] == pytest.approx(ttm)
    assert last["rev_growth_yoy"] == pytest.approx(ttm / prev - 1)
    assert last["op_margin_ttm"] == pytest.approx(0.2)
    assert last["net_margin_ttm"] == pytest.approx(0.1)
    assert last["fcf_margin_ttm"] == pytest.approx(0.3 - 0.1)       # CFO acumulado YTD -> trimestres -> TTM
    assert last["period_end"] == pd.Timestamp(Q_ENDS[-1])


def test_q4_is_reconstructed_from_fy_minus_9m():
    j = make_json(REV)                                             # el 10-K solo trae el año
    rows = fd.parse_companyfacts(j)["facts"]["Revenues"]
    q = fd.isolated_quarters({(date.fromisoformat(s), date.fromisoformat(e)): v for s, e, v, f in rows})
    assert q[date(2022, 12, 31)] == pytest.approx(REV[date(2022, 12, 31)])


def test_alternative_tags_across_a_tag_switch():
    old = {e: v for e, v in REV.items() if e.year < 2023}
    new = {e: v for e, v in REV.items() if e.year >= 2023}
    j = make_json(old, rev_tag="SalesRevenueNet")
    j["facts"]["us-gaap"]["RevenueFromContractWithCustomerExcludingAssessedTax"] = {
        "units": {"USD": flow_facts(new)}}
    h = hist_of(j)
    assert h.iloc[-1]["revenue_ttm"] == pytest.approx(sum(REV[e] for e in Q_ENDS[-4:]))   # 4 trimestres de 2023
    # en 2022-12-31 solo existe la etiqueta vieja pero con 4 trimestres completos
    assert h[h["period_end"] == pd.Timestamp("2022-12-31")].iloc[-1]["revenue_ttm"] == pytest.approx(
        sum(REV[e] for e in Q_ENDS[4:8]))


def test_gap_gives_none():
    rev = {e: v for e, v in REV.items() if e != date(2023, 6, 30)}            # falta un trimestre
    h = hist_of(make_json(rev, OP))
    last = h.iloc[-1]
    assert pd.isna(last["revenue_ttm"]) and pd.isna(last["op_margin_ttm"]) and pd.isna(last["rev_growth_yoy"])


def test_missing_capex_gives_none_fcf():
    h = hist_of(make_json(REV, OP, cfo=CFO))
    assert pd.isna(h.iloc[-1]["fcf_margin_ttm"]) and h.iloc[-1]["op_margin_ttm"] == pytest.approx(0.2)


def test_stale_data_gives_none():
    compact = fd.parse_companyfacts(make_json(REV))
    snap = fd.snapshot_from_facts(compact, date(2024, 12, 1))               # último cierre 2023-12-31: >200 días
    assert snap["revenue_ttm"] is None and snap["filed"] == "2024-02-29"


# ------------------------------------------------------------------ punto en el tiempo
def test_values_available_only_from_filed_date():
    h = hist_of(make_json(REV))
    filed_last = pd.Timestamp(_filed(Q_ENDS[-1], "K"))
    assert h.index.max() == filed_last                                      # el 10-K del cierre 2023-12-31 sale 60 días después
    row = h.loc[filed_last]
    assert row["period_end"] == pd.Timestamp(Q_ENDS[-1])
    before = h[h.index < filed_last].iloc[-1]
    assert before["period_end"] == pd.Timestamp(Q_ENDS[-2])                 # antes de esa fecha el último dato es el 10-Q anterior
    # el primer valor TTM no aparece antes de tener 4 trimestres presentados
    first_ttm = h["revenue_ttm"].dropna().index.min()
    assert first_ttm >= pd.Timestamp(_filed(Q_ENDS[3], "K"))


def test_snapshot_at_past_date_ignores_later_filings():
    compact = fd.parse_companyfacts(make_json(REV, OP))
    s_past = fd.snapshot_from_facts(compact, date(2023, 5, 20))             # 10-Q del T1 2023 salió el 2023-05-05
    assert s_past["period_end"] == "2023-03-31" and s_past["filed"] == "2023-05-05"
    assert s_past["revenue_ttm"] == pytest.approx(sum(REV[e] for e in Q_ENDS[4:9][-4:]))
    s_now = fd.snapshot_from_facts(compact, date(2024, 1, 15))
    assert s_now["period_end"] == "2023-09-30"                              # el 10-K (2024-02-29) aún no es público


def test_restatement_applies_only_after_its_filing():
    j = make_json(REV)
    rows = j["facts"]["us-gaap"]["Revenues"]["units"]["USD"]
    orig = next(f for f in rows if f["end"] == "2023-06-30" and f["start"] == "2023-04-01")
    rest = dict(orig, val=orig["val"] + 50, filed="2023-12-15", accn="restated")
    rows.append(rest)
    compact = fd.parse_companyfacts(j)
    before = fd.snapshot_from_facts(compact, date(2023, 12, 1))
    after = fd.snapshot_from_facts(compact, date(2023, 12, 20))
    assert after["revenue_ttm"] - before["revenue_ttm"] == pytest.approx(50)


def test_non_periodic_forms_ignored():
    j = make_json(REV)
    j["facts"]["us-gaap"]["Revenues"]["units"]["USD"].append(
        {"start": "2023-01-01", "end": "2023-12-31", "val": 1e9, "form": "DEF 14A", "filed": "2024-01-02"})
    h = hist_of(j)
    assert h["revenue_ttm"].max() < 1e5


# ------------------------------------------------------------------ balance y acciones
def test_debt_to_equity_and_negative_equity():
    eq = {e: 500.0 for e in Q_ENDS}
    debt = {e: 150.0 for e in Q_ENDS}
    h = hist_of(make_json(REV, equity=eq, debt=debt))
    assert h.iloc[-1]["debt_to_equity"] == pytest.approx(0.3)
    h2 = hist_of(make_json(REV, equity={e: -5.0 for e in Q_ENDS}, debt=debt))
    assert pd.isna(h2.iloc[-1]["debt_to_equity"])


def test_debt_current_plus_noncurrent():
    j = make_json(REV, equity={e: 100.0 for e in Q_ENDS}, debt={e: 40.0 for e in Q_ENDS})
    j["facts"]["us-gaap"]["LongTermDebtCurrent"] = {"units": {"USD": [
        _fact(None, e.isoformat(), 10.0, "10-K" if e.month == 12 else "10-Q", _filed(e, "K" if e.month == 12 else "Q"))
        for e in Q_ENDS]}}
    assert hist_of(j).iloc[-1]["debt_to_equity"] == pytest.approx(0.5)


def test_shares_change_like_for_like():
    sh = {e: 100.0 * (1.02 ** (i / 4)) for i, e in enumerate(Q_ENDS)}
    h = hist_of(make_json(REV, shares=sh))
    # el último 10-K trae acciones del año completo; se compara contra el año completo anterior
    assert h.iloc[-1]["shares_chg_yoy"] == pytest.approx(
        sum(sh[e] for e in Q_ENDS[8:]) / sum(sh[e] for e in Q_ENDS[4:8]) - 1, rel=1e-6)
    assert h["shares_chg_yoy"].dropna().between(0.0, 0.05).all()


def test_dei_shares_fallback():
    j = make_json(REV)
    j["facts"]["dei"]["EntityCommonStockSharesOutstanding"] = {"units": {"shares": [
        _fact(None, "2022-02-01", 100.0, "10-K", "2022-02-20"), _fact(None, "2023-02-01", 90.0, "10-K", "2023-02-20")]}}
    s = fd.snapshot_from_facts(fd.parse_companyfacts(j), date(2023, 3, 1))
    assert s["shares_chg_yoy"] == pytest.approx(-0.10)


def test_empty_company_is_safe(tmp_path):
    compact = fd.parse_companyfacts({"cik": 1, "facts": {}})
    assert fd.snapshot_from_facts(compact, date(2024, 1, 1)) == {}
    assert len(fd.history_from_facts(compact)) == 0


# ------------------------------------------------------------------ snapshot con caché y tolerancia a fallos
def test_snapshot_tolerates_failures_and_uses_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(fd.http, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(fd.sec, "ticker_to_cik", lambda: {"AAA": 1, "BBB": 2})
    calls = []

    class R:
        def __init__(self, j): self._j = j
        def json(self): return self._j

    def fake_get(url, **kw):
        calls.append(url)
        if "CIK0000000002" in url:
            raise RuntimeError("falla de red")
        return R(make_json(REV, OP))

    monkeypatch.setattr(fd.http, "get", fake_get)
    today = date(2024, 1, 15)
    s = fd.snapshot(["aaa", "BBB", "ZZZ"], today)
    assert s["asof"] == "2024-01-15" and s["coverage"] == 1
    assert set(s["tickers"]) == {"AAA"} and set(s["failed"]) == {"BBB", "ZZZ"}
    assert s["tickers"]["AAA"]["op_margin_ttm"] == pytest.approx(0.2)
    n = len(calls)
    fd.snapshot(["AAA"], today)
    assert len(calls) == n                                                   # AAA salió de la caché del día
    import json
    json.dumps(s)                                                            # serializable (sin NaN)


def test_picks_single_tag_and_handles_16_week_q4():
    """Calendario 4-4-5 (COST/PEP): el 4.º trimestre dura ~112 días (FY - 9M); una etiqueta parcial no rompe la serie."""
    fy = [(date(2021, 12, 26), [date(2022, 3, 20), date(2022, 6, 12), date(2022, 9, 4), date(2022, 12, 25)], [10, 11, 12, 13]),
          (date(2022, 12, 26), [date(2023, 3, 19), date(2023, 6, 11), date(2023, 9, 3), date(2023, 12, 24)], [14, 15, 16, 17])]
    facts, vals = [], []
    for start, ends, qs in fy:
        cum = 0.0
        for k, (e, v) in enumerate(zip(ends, qs)):
            cum += v
            kind = "10-K" if k == 3 else "10-Q"
            filed = (pd.Timestamp(e) + pd.Timedelta(days=30)).strftime("%Y-%m-%d")
            facts.append(_fact(start.isoformat(), e.isoformat(), cum, kind, filed))   # solo acumulados (Q1 = acumulado de 12 semanas)
        vals += qs
    j = {"cik": 1, "facts": {"us-gaap": {"RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": facts}},
                                          "Revenues": {"units": {"USD": facts[:1]}}}, "dei": {}}}   # etiqueta parcial
    s = fd.snapshot_from_facts(fd.parse_companyfacts(j), date(2024, 2, 10))
    assert s["revenue_ttm"] == pytest.approx(sum(vals[-4:]))
    assert s["rev_growth_yoy"] == pytest.approx(sum(vals[-4:]) / sum(vals[:4]) - 1)
