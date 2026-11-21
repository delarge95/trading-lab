"""Pruebas de trading_lab.events (sin red: el helper HTTP se simula)."""
import json
from datetime import date

import pytest

from trading_lab import events


class Resp:
    def __init__(self, payload):
        self.content = json.dumps(payload).encode()


def _cal(rows):
    return {"data": {"asOf": "x", "headers": {}, "rows": rows}, "message": None, "status": {"rCode": 200}}


@pytest.fixture(autouse=True)
def _tmp_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(events, "CACHE", tmp_path / "raw")


# ------------------------------------------------------------------ reglas de calendario
def test_tercer_viernes_y_opex():
    assert events.third_friday(2026, 12) == date(2026, 12, 18)       # comprobado a mano: 4, 11, 18
    assert events.third_friday(2027, 1) == date(2027, 1, 15)
    assert events.monthly_opex(2026, 12) == date(2026, 12, 18)
    assert events.monthly_opex(2026, 11) == date(2026, 11, 20)
    # 19-jun-2026 (tercer viernes) es feriado (Juneteenth): el vencimiento pasa al jueves 18
    assert events.third_friday(2026, 6) == date(2026, 6, 19)
    assert events.monthly_opex(2026, 6) == date(2026, 6, 18)
    # 2027: Juneteenth se observa el viernes 18 (el 19 es sábado); tercer viernes = 18
    assert events.monthly_opex(2027, 6) == date(2027, 6, 17)
    # Viernes Santo 2014 (18-abr) era tercer viernes: vencimiento el jueves 17
    assert events.monthly_opex(2014, 4) == date(2014, 4, 17)


def test_pascua():
    assert events._easter(2026) == date(2026, 4, 5)
    assert events._easter(2027) == date(2027, 3, 28)


def test_fin_de_trimestre_ultimo_dia_habil():
    assert events.quarter_end(2026, 4) == date(2026, 12, 31)
    assert events.quarter_end(2026, 3) == date(2026, 9, 30)
    assert events.quarter_end(2027, 2) == date(2027, 6, 30)
    assert events.quarter_end(2025, 2) == date(2025, 6, 30)
    assert events.quarter_end(2020, 1) == date(2020, 3, 31)
    assert events.quarter_end(2026, 1) == date(2026, 3, 31)
    # 31-mar-2029 es sábado -> viernes 30
    assert events.quarter_end(2029, 1) == date(2029, 3, 30)


def test_fomc_2026_fechas_de_decision():
    d26 = [d for d, _ in events.FOMC_DECISIONS if d.startswith("2026")]
    assert d26 == ["2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17",
                   "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09"]
    assert len([d for d, _ in events.FOMC_DECISIONS if d.startswith("2027")]) == 8


def test_estaticos_en_ventana_y_esquema(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("sin red")
    monkeypatch.setattr(events.http, "get", boom)
    r = events.upcoming([], today="2026-12-01", days=30)
    assert r["asof"] == "2026-12-01"
    kinds = {e["kind"] for e in r["events"]}
    assert kinds == {"fomc", "opex", "quarter_end"}
    by = {(e["kind"]): e for e in r["events"]}
    assert by["fomc"]["date"] == "2026-12-09" and by["fomc"]["days_to"] == 8
    assert "proyecciones" in by["fomc"]["label"]
    assert by["opex"]["date"] == "2026-12-18" and "triple witching" in by["opex"]["label"]
    assert by["quarter_end"]["date"] == "2026-12-31" and by["quarter_end"]["days_to"] == 30
    for e in r["events"]:
        assert set(e) == {"date", "kind", "ticker", "label", "days_to", "time"}
        assert e["ticker"] is None
    assert [e["date"] for e in r["events"]] == sorted(e["date"] for e in r["events"])
    json.dumps(r)


def test_fomc_2027_marcado_tentativo():
    r = events.upcoming([], today=date(2027, 1, 10), days=30)
    f = [e for e in r["events"] if e["kind"] == "fomc"]
    assert [e["date"] for e in f] == ["2027-01-27"]
    assert "tentativa" in f[0]["label"]


# ------------------------------------------------------------------ resultados (red simulada)
def test_resultados_filtra_tickers_y_acepta_variantes(monkeypatch):
    calls = []

    def fake(url, **kw):
        calls.append(url)
        d = url.split("date=")[1]
        if d == "2026-11-19":
            return Resp(_cal([
                {"symbol": "WMT", "name": "Walmart", "time": "time-pre-market", "fiscalQuarterEnding": "Oct/2026"},
                {"symbol": "ZZZ", "name": "Otra", "time": "time-pre-market"},
            ]))
        if d == "2026-11-24":
            return Resp(_cal([{"symbol": "BRK/B", "name": "Berkshire", "time": "time-after-hours"},
                              {"symbol": "DE", "name": "Deere", "time": "time-not-supplied"}]))
        return Resp({"data": {"asOf": "x", "headers": None, "rows": None}, "status": {"rCode": 200}})

    monkeypatch.setattr(events.http, "get", fake)
    r = events.upcoming(["WMT", "BRK-B", "DE", "AAPL"], today=date(2026, 11, 19), days=10)
    assert r["sources"]["nasdaq_earnings"] == "ok"
    earn = [e for e in r["events"] if e["kind"] == "earnings"]
    assert [(e["ticker"], e["date"], e["days_to"]) for e in earn] == [
        ("WMT", "2026-11-19", 0), ("BRK-B", "2026-11-24", 5), ("DE", "2026-11-24", 5)]
    assert earn[0]["time"] == "antes de la apertura" and "Oct/2026" in earn[0]["label"]
    assert earn[1]["time"] == "después del cierre"
    assert earn[2]["time"] is None
    # una petición por día hábil: 19-nov (jue) a 29-nov (dom) -> 19,20,23,24,25,26,27 = 7
    assert len(calls) == 7
    assert all("date=" in u for u in calls)


def test_resultados_cache_por_dia(monkeypatch):
    n = {"c": 0}

    def fake(url, **kw):
        n["c"] += 1
        return Resp(_cal([]))

    monkeypatch.setattr(events.http, "get", fake)
    events.upcoming(["AAPL"], today=date(2026, 11, 19), days=4)
    first = n["c"]
    assert first == 3                                   # jue, vie, lun
    events.upcoming(["AAPL"], today=date(2026, 11, 19), days=4)
    assert n["c"] == first                              # mismo día: todo desde caché
    events.upcoming(["AAPL"], today=date(2026, 11, 20), days=4)
    assert n["c"] > first                               # otro día: se vuelve a pedir


def test_fuente_de_resultados_caida_no_lanza(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("GET falló")

    monkeypatch.setattr(events.http, "get", boom)
    r = events.upcoming(["AAPL", "MSFT"], today=date(2026, 12, 1), days=30)
    assert r["sources"]["nasdaq_earnings"].startswith("error:")
    assert "GET falló" in r["sources"]["nasdaq_earnings"]
    assert set(r) == {"asof", "events", "sources"}              # esquema del contrato intacto sin red
    assert all(set(e) == {"date", "kind", "ticker", "label", "days_to", "time"} for e in r["events"])
    assert any(e["kind"] == "fomc" for e in r["events"])        # los estáticos siguen
    assert not any(e["kind"] == "earnings" for e in r["events"])


def test_fallo_parcial_se_reporta_y_conserva_datos(monkeypatch):
    def fake(url, **kw):
        if url.endswith("2026-11-20"):
            raise RuntimeError("429")
        return Resp(_cal([{"symbol": "AAPL", "name": "Apple", "time": "time-after-hours"}])
                    if url.endswith("2026-11-19") else _cal([]))

    monkeypatch.setattr(events.http, "get", fake)
    r = events.upcoming(["AAPL"], today=date(2026, 11, 19), days=4)
    assert r["sources"]["nasdaq_earnings"].startswith("error: 1/3")
    assert [e["ticker"] for e in r["events"] if e["kind"] == "earnings"] == ["AAPL"]


def test_respuesta_con_rcode_de_error_cuenta_como_fallo(monkeypatch):
    monkeypatch.setattr(events.http, "get",
                        lambda url, **kw: Resp({"data": None, "status": {"rCode": 400}}))
    r = events.upcoming(["AAPL"], today=date(2026, 11, 19), days=1)
    assert r["sources"]["nasdaq_earnings"].startswith("error:")


def test_today_acepta_str_y_datetime():
    from datetime import datetime
    assert events._as_date("2026-11-19") == date(2026, 11, 19)
    assert events._as_date(datetime(2026, 11, 19, 15, 0)) == date(2026, 11, 19)
    assert events._as_date(None) == date.today()
    assert events._business_days(date(2026, 11, 19), date(2026, 11, 29))[-1] == date(2026, 11, 27)
    assert events._key("BRK-B") == events._key("BRK.B") == events._key("brk/b") == "BRKB"
