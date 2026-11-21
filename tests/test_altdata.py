"""Pruebas de trading_lab.altdata (sin red: el helper HTTP se simula con respuestas de ejemplo)."""
import json
import math
from datetime import date, timedelta

import pytest

from trading_lab import altdata as ad

TODAY = date(2026, 11, 19)


class Resp:
    def __init__(self, payload=None, text=None):
        self.content = (text if text is not None else json.dumps(payload)).encode()


@pytest.fixture(autouse=True)
def _limpio(monkeypatch):
    ad._memo.clear()
    monkeypatch.setattr(ad, "_PAUSE", [0.0])
    yield
    ad._memo.clear()


# ------------------------------------------------------------------ cadena de opciones sintética
SPOT, FWD = 100.0, 100.4


def make_chain(spec: dict[int, float], today=TODAY, vols=(300, 500), ois=(1000, 2000), strikes=None,
               last="LAST TRADE: $100.00 (AS OF NOV 18, 2026)"):
    """spec: {días al vencimiento: IV verdadera}. Precios Black-76 con forward fijo y spread de 1 centavo."""
    strikes = strikes or [70 + 2.5 * i for i in range(25)]
    rows = []
    for days, iv in sorted(spec.items()):
        exp = today + timedelta(days=days)
        T = days / 365.0
        df = math.exp(-ad.RISK_FREE * T)
        rows.append({"expirygroup": exp.strftime("%B %d, %Y"), "expiryDate": None, "strike": None})
        for K in strikes:
            c = ad.black76(FWD, K, T, iv, df, True)
            p = ad.black76(FWD, K, T, iv, df, False)
            rows.append({
                "expirygroup": "", "expiryDate": exp.strftime("%b %d"), "strike": f"{K:.2f}",
                "c_Bid": f"{max(c - 0.005, 0.01):.2f}", "c_Ask": f"{c + 0.005:.2f}",
                "p_Bid": f"{max(p - 0.005, 0.01):.2f}", "p_Ask": f"{p + 0.005:.2f}",
                "c_Volume": str(vols[0]), "p_Volume": str(vols[1]),
                "c_Openinterest": str(ois[0]), "p_Openinterest": str(ois[1]),
            })
    return {"data": {"totalRecord": len(rows), "lastTrade": last, "table": {"rows": rows}},
            "message": None, "status": {"rCode": 200}}


def test_black76_e_iv_ida_y_vuelta():
    df = math.exp(-0.04 * 30 / 365)
    for iv in (0.08, 0.25, 0.6, 1.5):
        for K in (80.0, 100.0, 125.0):
            for is_call in (True, False):
                px = ad.black76(100.0, K, 30 / 365, iv, df, is_call)
                if abs(ad.black76(100.0, K, 30 / 365, iv * 1.1, df, is_call) - px) < 1e-3:
                    continue                                   # sin sensibilidad a la vol: IV no identificable
                assert ad.implied_vol(px, 100.0, K, 30 / 365, df, is_call) == pytest.approx(iv, abs=1e-4)
    assert ad.implied_vol(0.0, 100.0, 100.0, 0.1, 1.0, True) is None
    assert ad.implied_vol(500.0, 100.0, 100.0, 0.1, 1.0, True) is None      # sobre el máximo sin arbitraje


def test_iv30_plana_recupera_iv_conocida():
    exps, spot = ad.parse_chain(make_chain({21: 0.30, 49: 0.30})["data"], TODAY)
    assert spot == 100.0 and [e["days"] for e in exps] == [21, 49]
    res = ad.iv30_from_chain(exps, spot)
    assert res["iv30"] == pytest.approx(0.30, abs=3e-3)
    assert (res["iv_d1"], res["iv_d2"]) == (21, 49)


def test_iv30_interpola_varianza_total_con_estructura_temporal():
    exps, spot = ad.parse_chain(make_chain({20: 0.20, 50: 0.30})["data"], TODAY)
    res = ad.iv30_from_chain(exps, spot)
    w1, w2 = 0.20 ** 2 * 20 / 365, 0.30 ** 2 * 50 / 365
    esperado = math.sqrt((w1 + (w2 - w1) * (10 / 30)) / (30 / 365))
    assert res["iv30"] == pytest.approx(esperado, abs=3e-3)
    assert res["iv1"] == pytest.approx(0.20, abs=3e-3) and res["iv2"] == pytest.approx(0.30, abs=3e-3)


def test_iv30_vencimiento_exacto_a_30_dias_y_sin_cobertura():
    exps, spot = ad.parse_chain(make_chain({30: 0.4, 60: 0.4})["data"], TODAY)
    r = ad.iv30_from_chain(exps, spot)
    assert r["iv30"] == pytest.approx(0.4, abs=3e-3) and r["iv_d2"] is None
    # solo vencimientos del mismo lado, o uno de <7 días (ruidoso): no se inventa un valor
    for spec in ({40: 0.3, 60: 0.3}, {10: 0.3, 20: 0.3}, {3: 0.3, 49: 0.3}):
        exps, spot = ad.parse_chain(make_chain(spec)["data"], TODAY)
        assert ad.iv30_from_chain(exps, spot)["iv30"] is None


def test_forward_por_paridad_no_depende_del_spot_informado():
    exps, _ = ad.parse_chain(make_chain({21: 0.25, 49: 0.25})["data"], TODAY)
    for bad_spot in (95.0, 100.0, 104.0):
        assert ad.iv30_from_chain(exps, bad_spot)["iv30"] == pytest.approx(0.25, abs=4e-3)


def test_cotizaciones_invalidas_se_ignoran():
    data = make_chain({21: 0.3, 49: 0.3})["data"]
    for row in data["table"]["rows"]:
        if row.get("strike") in ("100.00", "102.50", "97.50"):   # cotización inexistente cerca del dinero
            row["c_Bid"] = "--"
            row["p_Ask"] = "--"
    exps, spot = ad.parse_chain(data, TODAY)
    assert ad.iv30_from_chain(exps, spot)["iv30"] == pytest.approx(0.3, abs=5e-3)


def test_put_call_suma_volumen_e_interes_abierto():
    exps, _ = ad.parse_chain(make_chain({21: 0.3, 49: 0.3}, vols=(300, 500), ois=(1000, 2000))["data"], TODAY)
    pc = ad._put_call(exps)
    assert pc["put_call_vol"] == pytest.approx(500 / 300, abs=1e-3)
    assert pc["put_call_oi"] == pytest.approx(2.0)
    assert pc["n_expiries_pc"] == 2
    exps, _ = ad.parse_chain(make_chain({21: 0.3, 70: 0.3})["data"], TODAY)
    assert ad._put_call(exps)["n_expiries_pc"] == 1               # 70 días queda fuera de la ventana de 60


def test_fetch_iv_con_http_simulado_y_simbolo_con_punto(monkeypatch):
    urls = []

    def fake(url, **kw):
        urls.append(url)
        return Resp(make_chain({21: 0.30, 49: 0.30}))

    monkeypatch.setattr(ad.http, "get", fake)
    out = ad.fetch_iv("BRK-B", TODAY)
    assert "/quote/BRK.B/option-chain" in urls[0] and "fromdate=2026-11-19" in urls[0]
    assert out["iv30"] == pytest.approx(0.30, abs=3e-3)
    assert out["spot"] == 100.0 and out["n_expiries"] == 2


def test_fetch_iv_sin_cadena_o_con_error_de_api_lanza(monkeypatch):
    monkeypatch.setattr(ad.http, "get", lambda url, **kw: Resp(
        {"data": None, "status": {"rCode": 400, "bCodeMessage": [{"errorMessage": "Symbol not exists."}]}}))
    with pytest.raises(ValueError, match="Symbol not exists"):
        ad.fetch_iv("ZZZZ", TODAY)
    monkeypatch.setattr(ad.http, "get", lambda url, **kw: Resp(
        {"data": {"table": {"rows": []}, "lastTrade": ""}, "status": {"rCode": 200}}))
    with pytest.raises(ValueError, match="vacía"):
        ad.fetch_iv("AAPL", TODAY)


# ------------------------------------------------------------------ FINRA
SI_CSV = (
    '"accountingYearMonthNumber"|"symbolCode"|"issueName"|"issuerServicesGroupExchangeCode"|"marketClassCode"|'
    '"currentShortPositionQuantity"|"previousShortPositionQuantity"|"stockSplitFlag"|"averageDailyVolumeQuantity"|'
    '"daysToCoverQuantity"|"revisionFlag"|"changePercent"|"changePreviousNumber"|"settlementDate"\n'
    '"20261030"|"AAPL"|"Apple Inc."|"R"|"NNM"|"144791472"|"131591865"||"43085075"|"3.36"||"10.03"|"13199607"|"2026-10-30"\n'
    '"20261030"|"BRKB"|"BERKSHIRE B"|"A"|"NYSE"|"15232424"|"13769255"||"4459554"|"3.42"||"10.63"|"1463169"|"2026-10-30"\n'
)
SV_TXT = ("Date|Symbol|ShortVolume|ShortExemptVolume|TotalVolume|Market\n"
          "20261118|AAPL|7000000.5|25359|12000000.25|B,Q,N\n"
          "20261118|BRKB|1000|0|4000|N\n")


def test_candidatos_de_liquidacion_finra():
    c = ad.finra_si_candidates(TODAY)
    assert c[0] == date(2026, 11, 13)          # 15-nov-2026 es domingo -> viernes 13
    assert date(2026, 10, 30) in c             # 31-oct es sábado -> viernes 30
    assert date(2026, 10, 15) in c and date(2026, 9, 30) in c
    assert all(d.weekday() < 5 for d in c)
    assert max(c) <= TODAY - timedelta(days=3)


def test_interes_corto_busca_el_ultimo_archivo_publicado(monkeypatch):
    pedidos = []

    def fake(url, **kw):
        pedidos.append(url)
        if url.endswith("shrt20261030.csv"):
            return Resp(text=SI_CSV)
        raise RuntimeError("404")

    monkeypatch.setattr(ad.http, "get", fake)
    out = ad.fetch_short_interest("AAPL", TODAY)
    assert out["si_shares"] == 144791472 and out["si_prev_shares"] == 131591865
    assert out["si_days_to_cover"] == 3.36 and out["si_change_pct"] == 10.03
    assert out["si_settle_date"] == "2026-10-30" and out["si_age_days"] == 20
    assert pedidos[0].endswith("shrt20261113.csv") and pedidos[-1].endswith("shrt20261030.csv")
    # BRK-B se busca como BRKB; el archivo se descarga una sola vez por día (memorizado)
    n = len(pedidos)
    assert ad.fetch_short_interest("BRK-B", TODAY)["si_shares"] == 15232424
    assert len(pedidos) == n
    with pytest.raises(ValueError, match="ausente"):
        ad.fetch_short_interest("ZZZZ", TODAY)


def test_interes_corto_sin_archivos_lanza(monkeypatch):
    def boom(url, **kw):
        raise RuntimeError("404")

    monkeypatch.setattr(ad.http, "get", boom)
    with pytest.raises(RuntimeError, match="FINRA"):
        ad.fetch_short_interest("AAPL", TODAY)


def test_volumen_corto_usa_el_ultimo_dia_disponible(monkeypatch):
    def fake(url, **kw):
        if url.endswith("20261118.txt"):
            return Resp(text=SV_TXT)
        raise RuntimeError("404")          # el archivo de hoy aún no está publicado

    monkeypatch.setattr(ad.http, "get", fake)
    out = ad.fetch_short_volume("AAPL", TODAY)
    assert out["sv_date"] == "2026-11-18"
    assert out["sv_ratio"] == pytest.approx(7000000.5 / 12000000.25, abs=1e-4)
    assert ad.fetch_short_volume("BRK-B", TODAY)["sv_total_volume"] == 4000


# ------------------------------------------------------------------ analistas
TARGET = {"symbol": "aapl", "consensusOverview": {"lowPriceTarget": 261.0, "highPriceTarget": 425.0,
                                                  "priceTarget": 343.69, "buy": 15, "sell": 6, "hold": 8},
          "historicalConsensus": [{"y": 1.0}]}
RATINGS = {"symbol": "aapl", "meanRatingType": "Hold",
           "ratingsSummary": "Based on 29 analysts offering recommendations for 'AAPL'.", "brokerNames": []}
EPS = {"symbol": "aapl", "quarterlyForecast": {"rows": [
    {"fiscalEnd": "Dec 2026", "consensusEPSForecast": 2.94, "highEPSForecast": 3.18, "lowEPSForecast": 2.86,
     "noOfEstimates": 10, "up": 4, "down": 2}, {"fiscalEnd": "Mar 2027", "consensusEPSForecast": 2.14}]},
       "yearlyForecast": None}


def _analyst_fake(fail=()):
    def fake(url, **kw):
        for f in fail:
            if f in url:
                raise RuntimeError(f"fallo {f}")
        if "targetprice" in url:
            return Resp({"data": TARGET, "status": {"rCode": 200}})
        if "ratings" in url:
            return Resp({"data": RATINGS, "status": {"rCode": 200}})
        if "earnings-forecast" in url:
            return Resp({"data": EPS, "status": {"rCode": 200}})
        raise AssertionError(url)

    return fake


def test_analistas_parseo(monkeypatch):
    monkeypatch.setattr(ad.http, "get", _analyst_fake())
    out = ad.fetch_analysts("AAPL", TODAY)
    assert out["an_target_mean"] == 343.69 and out["an_target_low"] == 261.0 and out["an_target_high"] == 425.0
    assert (out["an_n_buy"], out["an_n_hold"], out["an_n_sell"], out["an_n_analysts"]) == (15, 8, 6, 29)
    assert out["an_rec_score"] == pytest.approx((15 - 6) / 29, abs=1e-4)
    assert out["an_mean_rating"] == "Hold" and out["an_n_ratings"] == 29
    assert out["an_eps_cons"] == 2.94 and out["an_eps_n"] == 10 and out["an_eps_fiscal"] == "Dec 2026"
    assert (out["an_eps_rev_up"], out["an_eps_rev_down"]) == (4, 2)
    assert "partial_errors" not in out


def test_analistas_parcial_y_total(monkeypatch):
    monkeypatch.setattr(ad.http, "get", _analyst_fake(fail=("earnings-forecast",)))
    out = ad.fetch_analysts("AAPL", TODAY)
    assert out["an_target_mean"] == 343.69 and "an_eps_cons" not in out
    assert len(out["partial_errors"]) == 1 and out["partial_errors"][0].startswith("eps")
    monkeypatch.setattr(ad.http, "get", _analyst_fake(fail=("targetprice", "ratings", "earnings-forecast")))
    with pytest.raises(ValueError, match="sin datos de analistas"):
        ad.fetch_analysts("AAPL", TODAY)


def test_analistas_sin_cobertura_no_inventa(monkeypatch):
    monkeypatch.setattr(ad.http, "get", lambda url, **kw: Resp(
        {"data": None, "status": {"rCode": 200, "bCodeMessage": [{"errorMessage": "No record found."}]}}))
    with pytest.raises(ValueError, match="No record found"):
        ad.fetch_analysts("BRK-B", TODAY)


# ------------------------------------------------------------------ collect_one / collect / load_history
def router(fail_sources=(), counter=None):
    """Simula todas las fuentes. fail_sources: subcadenas de URL que fallan."""
    an = _analyst_fake()

    def fake(url, **kw):
        if counter is not None:
            counter.append(url)
        for f in fail_sources:
            if f in url:
                raise RuntimeError(f"fallo {f}")
        if "option-chain" in url:
            return Resp(make_chain({21: 0.30, 49: 0.30}))
        if "finra.org/equity/otcmarket" in url:
            if url.endswith("shrt20261030.csv"):
                return Resp(text=SI_CSV)
            raise RuntimeError("404")
        if "regsho" in url:
            if url.endswith("20261118.txt"):
                return Resp(text=SV_TXT)
            raise RuntimeError("404")
        return an(url, **kw)

    return fake


def test_collect_one_nunca_lanza_y_marca_error_por_fuente(monkeypatch):
    def boom(url, **kw):
        raise RuntimeError("sin red")

    monkeypatch.setattr(ad.http, "get", boom)
    out = ad.collect_one("AAPL", TODAY)
    assert set(out) == set(ad.SOURCES)
    assert all("error" in v for v in out.values())
    ad._memo.clear()
    monkeypatch.setattr(ad.http, "get", router(fail_sources=("option-chain",)))
    out = ad.collect_one("AAPL", TODAY)
    assert "error" in out["iv"] and "sin red" not in out["iv"]["error"]
    assert "error" not in out["short_interest"] and "error" not in out["analysts"]
    assert "error" not in out["short_volume"]


def test_collect_escribe_foto_diaria_y_resume_cobertura(monkeypatch, tmp_path):
    monkeypatch.setattr(ad.http, "get", router(fail_sources=("analyst/MSFT",)))
    res = ad.collect(["aapl", "MSFT", "BRK-B"], today=TODAY, outdir=tmp_path / "alt", pause=0)
    f = tmp_path / "alt" / "2026-11-19.json"
    assert f.exists() and res["path"] == str(f)
    assert res["n_tickers"] == 3 and res["fetched"] == 3
    assert res["coverage"] == {"iv": 3, "short_interest": 2, "short_volume": 2, "analysts": 2}   # MSFT no está en SI de ejemplo
    assert "analysts" in res["first_error"] and "MSFT" in res["first_error"]["analysts"]
    snap = json.loads(f.read_text(encoding="utf-8"))
    assert snap["date"] == "2026-11-19" and set(snap["tickers"]) == {"AAPL", "MSFT", "BRK-B"}
    assert snap["tickers"]["AAPL"]["iv"]["iv30"] == pytest.approx(0.30, abs=3e-3)


def test_collect_es_idempotente_y_reintenta_solo_lo_fallido(monkeypatch, tmp_path):
    calls = []
    out = tmp_path / "alt"
    monkeypatch.setattr(ad.http, "get", router(fail_sources=("analyst/AAPL",), counter=calls))
    r1 = ad.collect(["AAPL"], today=TODAY, outdir=out, pause=0)
    assert r1["coverage"]["analysts"] == 0 and r1["coverage"]["iv"] == 1
    first = (out / "2026-11-19.json").read_text(encoding="utf-8")

    # misma fuente caída: solo se reintentan las llamadas de analistas; el resto se conserva tal cual
    calls.clear()
    ad._memo.clear()
    r2 = ad.collect(["AAPL"], today=TODAY, outdir=out, pause=0)
    assert calls and all("/analyst/AAPL/" in u for u in calls)
    assert (out / "2026-11-19.json").read_text(encoding="utf-8") == first
    assert r2["coverage"] == r1["coverage"]

    # la fuente se recupera: se completa y la tercera corrida no hace ninguna petición
    monkeypatch.setattr(ad.http, "get", router(counter=calls))
    r3 = ad.collect(["AAPL"], today=TODAY, outdir=out, pause=0)
    assert r3["coverage"]["analysts"] == 1
    calls.clear()
    r4 = ad.collect(["AAPL"], today=TODAY, outdir=out, pause=0)
    assert calls == [] and r4["fetched"] == 0 and r4["coverage"] == r3["coverage"]
    # un ticker nuevo se agrega sin tocar al anterior
    ad.collect(["AAPL", "BRK-B"], today=TODAY, outdir=out, pause=0)
    assert set(json.loads((out / "2026-11-19.json").read_text(encoding="utf-8"))["tickers"]) == {"AAPL", "BRK-B"}
    assert len(list(out.glob("*.json"))) == 1


def test_load_history_formato_largo(monkeypatch, tmp_path):
    out = tmp_path / "alt"
    assert ad.load_history(out).empty
    assert list(ad.load_history(out).columns) == ["date", "ticker", "campo", "valor"]
    monkeypatch.setattr(ad.http, "get", router(fail_sources=("analyst/",)))
    ad.collect(["AAPL", "BRK-B"], today=TODAY, outdir=out, pause=0)
    ad._memo.clear()
    ad.collect(["AAPL"], today=date(2026, 11, 20), outdir=out, pause=0)
    (out / "basura.json").write_text("{}")
    (out / "2026-11-21.json").write_text("no es json")
    h = ad.load_history(out)
    assert list(h.columns) == ["date", "ticker", "campo", "valor"]
    assert set(h["date"].dt.strftime("%Y-%m-%d")) == {"2026-11-19", "2026-11-20"}
    assert h["valor"].map(lambda v: isinstance(v, float) and math.isfinite(v)).all()
    # solo numéricos: ni fechas ni textos; fuentes con error se omiten
    assert "si_settle_date" not in set(h["campo"]) and "an_mean_rating" not in set(h["campo"])
    assert not any(c.startswith("an_") for c in h["campo"])
    iv = h[(h["campo"] == "iv30") & (h["ticker"] == "AAPL")]
    assert len(iv) == 2 and iv["valor"].between(0.29, 0.31).all()
    assert h[(h["campo"] == "si_shares") & (h["ticker"] == "BRK-B")]["valor"].iloc[0] == 15232424


def test_error_transitorio_de_vendor_se_reintenta(monkeypatch):
    monkeypatch.setattr(ad.time, "sleep", lambda s: None)
    n = {"c": 0}

    def fake(url, **kw):
        n["c"] += 1
        if n["c"] < 3:
            return Resp({"data": None, "status": {"rCode": 200, "bCodeMessage": [
                {"code": 3004, "errorMessage": "Error while calling vendor"}]}})
        return Resp({"data": {"ok": 1}, "status": {"rCode": 200}})

    monkeypatch.setattr(ad.http, "get", fake)
    assert ad._nasdaq_json("https://api.nasdaq.com/api/x") == {"ok": 1}
    assert n["c"] == 3
    n["c"] = -100                                         # nunca se recupera: falla tras 5 intentos
    with pytest.raises(ValueError, match="vendor"):
        ad._nasdaq_json("https://api.nasdaq.com/api/x")


def test_variantes_de_simbolo_finra_incluyen_barra():
    assert "BRK/B" in ad._finra_symbol_variants("BRK-B") and "BRKB" in ad._finra_symbol_variants("BRK-B")
