import math
from datetime import date
from pathlib import Path

import pytest

from trading_lab import backtest, insiders, predictions, report, sec, signals

TREND = [100 * math.exp(0.0005 * i) for i in range(1500)]


def _series(px, start="2020-01-01"):
    from datetime import datetime, timedelta
    d0 = datetime.strptime(start, "%Y-%m-%d")
    return [((d0 + timedelta(days=i)).strftime("%Y-%m-%d"), p) for i, p in enumerate(px)]


# ---------------------------------------------------------------- signals
def test_momentum_skips_last_month():
    px = [100.0] * 300
    px[-1] = 500.0  # el salto del último día no debe contar (se omite el último mes)
    assert signals.momentum_12_1(px) == pytest.approx(0.0)


def test_momentum_uses_only_past_data_up_to_end():
    px = TREND
    assert signals.momentum_12_1(px, 600) == signals.momentum_12_1(px[:601])


def test_momentum_insufficient_history():
    assert signals.momentum_12_1([1.0] * 100) is None


def test_wilson_bounds():
    lo, hi = signals.wilson(60, 100)
    assert 0.49 < lo < 0.6 < hi < 0.70
    assert signals.wilson(0, 0) == (0.0, 1.0)
    assert signals.wilson(10, 10)[1] == 1.0


def test_prob_up_uptrend_is_one():
    pu = signals.prob_up(TREND)
    assert pu["p_all"] == 1.0 and pu["n_all"] > 40
    assert pu["momentum_positive"] is True


def test_summarize_fields():
    s = signals.summarize(_series(TREND))
    assert s["trend"] == "positiva" and s["vol_63d"] == pytest.approx(0.0, abs=1e-9)


# ---------------------------------------------------------------- backtest
def test_backtest_trend_beats_zero():
    b = backtest.momentum_backtest(TREND)
    assert b["periods"] > 40 and b["exposure"] > 0.95


def test_backtest_no_lookahead_null():
    nc = backtest.null_check(n_days=2520, seeds=150)
    assert abs(nc["z"]) < 3.0, nc  # Sharpe ≈ 0 en caminatas sin tendencia


def test_backtest_signal_ignores_future():
    # Cambiar precios futuros no altera los resultados de períodos anteriores
    a = backtest.random_walk(1000, seed=1)
    b = a[:800] + [p * 3 for p in a[800:]]
    ra = backtest.momentum_backtest(a[:800])
    rb = backtest.momentum_backtest(b[:800])
    assert ra == rb


# ---------------------------------------------------------------- predicciones
def test_predictions_record_and_evaluate(tmp_path: Path):
    path = tmp_path / "p.csv"
    s = signals.summarize(_series(TREND))
    assert predictions.record(path, "AAA", s, date(2024, 1, 2)) is True
    assert predictions.record(path, "AAA", s, date(2024, 1, 2)) is False  # sin duplicados
    series = {"AAA": [("2024-02-01", s["last_price"] * 1.1)]}
    assert predictions.evaluate(path, series, date(2024, 1, 20))["closed"] == 0  # no vencida
    sb = predictions.evaluate(path, series, date(2024, 2, 5))
    assert sb["closed"] == 1 and sb["hit_rate"] == 1.0 and sb["brier"] < 0.01


# ---------------------------------------------------------------- SEC
FORM13F = """<informationTable xmlns="http://www.sec.gov/edgar/document/thirteenf/informationtable">
<infoTable><nameOfIssuer>ACME</nameOfIssuer><cusip>AAA</cusip><value>100</value>
<shrsOrPrnAmt><sshPrnamt>10</sshPrnamt></shrsOrPrnAmt></infoTable>
<infoTable><nameOfIssuer>ACME</nameOfIssuer><cusip>AAA</cusip><value>50</value>
<shrsOrPrnAmt><sshPrnamt>5</sshPrnamt></shrsOrPrnAmt></infoTable>
<infoTable><nameOfIssuer>OPT</nameOfIssuer><cusip>BBB</cusip><value>999</value><putCall>Put</putCall>
<shrsOrPrnAmt><sshPrnamt>1</sshPrnamt></shrsOrPrnAmt></infoTable></informationTable>"""


def test_parse_13f_aggregates_and_skips_options():
    t = sec.parse_13f_table(FORM13F)
    assert list(t) == ["AAA"] and t["AAA"]["value"] == 150 and t["AAA"]["shares"] == 15


def test_rescale_if_thousands():
    in_thousands = {"A": {"name": "A", "value": 150.0, "shares": 1000.0},   # $0.15/acción implícito
                    "B": {"name": "B", "value": 80.0, "shares": 500.0}}
    out, flag = sec.rescale_if_thousands(in_thousands)
    assert flag and out["A"]["value"] == 150000.0
    in_dollars = {"A": {"name": "A", "value": 150000.0, "shares": 1000.0}}
    out, flag = sec.rescale_if_thousands(in_dollars)
    assert not flag and out["A"]["value"] == 150000.0


FORM4 = """<ownershipDocument><issuer><issuerCik>0000000042</issuerCik></issuer><reportingOwner><reportingOwnerId><rptOwnerCik>1</rptOwnerCik>
<rptOwnerName>Jane Doe</rptOwnerName></reportingOwnerId><reportingOwnerRelationship>
<isOfficer>1</isOfficer></reportingOwnerRelationship></reportingOwner><nonDerivativeTable>
<nonDerivativeTransaction><transactionDate><value>2026-10-01</value></transactionDate>
<transactionCoding><transactionCode>P</transactionCode></transactionCoding>
<transactionAmounts><transactionShares><value>100</value></transactionShares>
<transactionPricePerShare><value>10</value></transactionPricePerShare></transactionAmounts></nonDerivativeTransaction>
<nonDerivativeTransaction><transactionDate><value>2026-10-02</value></transactionDate>
<transactionCoding><transactionCode>A</transactionCode></transactionCoding>
<transactionAmounts><transactionShares><value>5</value></transactionShares></transactionAmounts></nonDerivativeTransaction>
</nonDerivativeTable></ownershipDocument>"""


def test_parse_form4_keeps_only_open_market():
    t = sec.parse_form4(FORM4)
    assert len(t) == 1 and t[0]["code"] == "P" and t[0]["value"] == 1000 and t[0]["role"] == "Officer"
    assert t[0]["issuer_cik"] == "42"  # permite descartar Form 4 donde el CIK es declarante, no emisor


def _tr(d, code="P", cik="1"):
    return {"owner": "X", "owner_cik": cik, "role": "Officer", "code": code, "date": d,
            "shares": 10, "price": 10, "value": 100}


def test_insider_routine_vs_opportunistic():
    today = date(2026, 11, 15)
    routine = [_tr("2023-10-05"), _tr("2024-10-04"), _tr("2025-10-03"), _tr("2026-10-02")]
    opp = [_tr("2023-03-05"), _tr("2024-06-04"), _tr("2025-01-03"), _tr("2026-10-02")]
    new = [_tr("2026-10-02")]
    assert insiders.classify(routine, today=today)["routine"] == 1
    assert insiders.classify(opp, today=today)["opportunistic"] == 1
    assert insiders.classify(new, today=today)["unclassified"] == 1  # historia insuficiente


# ---------------------------------------------------------------- informe
def test_report_renders_and_has_disclaimer():
    s = signals.summarize(_series(TREND))
    res = {"date": "2026-11-18", "sources": {"Precios": "OK"}, "errors": [], "tickers": {"AAA": s},
           "backtest": {"AAA": backtest.momentum_backtest(TREND)}, "null_check": backtest.null_check(1500, 20),
           "insiders": {}, "managers": [], "macro": {}, "scoreboard": {"closed": 0, "open": 1}}
    md = report.render(res)
    assert "AAA" in md and md.rstrip().endswith("no asesoría financiera._")
