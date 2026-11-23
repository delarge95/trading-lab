import re

from trading_lab import email_html


def _res(state="rojo"):
    return {
        "date": "2026-11-23", "insiders": {"AAPL": {"opportunistic": 0}}, "managers": [{"name": "Pershing <b>", "stale": True}],
        "engine": {
            "asof": "2026-11-20",
            "regime": {"state": state, "score": 5, "max_score": 10,
                       "rules": [{"name": "vix", "value": 28.4, "state": "amarillo"},
                                 {"name": "sma200_gap", "value": -0.055, "state": "rojo"},
                                 {"name": "hy_spread", "value": 3.5, "state": "verde"}],
                       "history": {"by_state": {"rojo": {"prob_drop5": 0.3, "n_eff": 18.4}, "verde": {"prob_drop5": 0.12}}}},
            "alerts": {"alerts": [{"severity": "media", "kind": "vix", "title": "VIX cruza 25 al alza"},
                                  {"severity": "info", "kind": "top_risk", "title": "x"},
                                  {"severity": "info", "kind": "13f_new", "title": "FERG <script>alert(1)</script>"}] + [
                                     {"severity": "info", "kind": "13f_new", "title": f"T{i}"} for i in range(6)]},
            "risk_table": [{"ticker": "INTC", "dd21": 0.35, "p10": -0.35, "p50": 0.03, "p90": 0.56, "vol63": 0.97},
                           {"ticker": "AMD", "dd21": 0.34, "p10": -0.29, "p50": 0.06, "p90": 0.78, "vol63": 0.88}],
            "ranking": {"criteria": [{"key": "riesgo_caida", "favorable": [{"ticker": "LIN", "value": 0.07}]}]},
            "events": {"events": [{"date": "2026-11-24", "kind": "earnings", "ticker": "MDT", "days_to": 1, "time": "antes de la apertura"},
                                  {"date": "2026-12-09", "kind": "fomc", "days_to": 10}]},
            "eval": {"up21": {"has_edge": False}}, "risk_validation": {"21": {"coverage80": 0.783}},
            "ledger": {"rules": {"mom12_1": {"closed": 0}}},
        }}


def test_renders_all_blocks_and_slots():
    h = email_html.render(_res())
    assert "<!--MERCADO_AYER-->" in h and "<!--AVISO-->" in h
    for s in ("Estrés alto", "INTC", "Reunión de la Fed", "no asesoría financiera", "mar 24 nov", "LIN 7%"):
        assert s in h, s
    assert "en 1 días" not in h and "mañana" in h
    assert 5000 < len(h) < 40000


def test_escapes_data_and_has_no_scripts_or_advice():
    h = email_html.render(_res())
    assert "<script" not in h.lower() and "Pershing &lt;b&gt;" in h
    low = re.sub(r"<[^>]+>", " ", h).lower()
    for bad in ("compra ", "vende ", "te recomiendo", "deberías"):
        assert bad not in low


def test_limits_alert_list():
    h = email_html.render(_res())
    assert h.count(">INFO<") <= 2 + 1     # una alerta media + a lo sumo 2 informativas
    assert "alertas más" in h


def test_degrades_without_engine_or_regime():
    h = email_html.render({"date": "2026-11-23"})
    assert "Semáforo de mercado no disponible" in h and "no asesoría financiera" in h
    h2 = email_html.render({"date": "2026-11-23", "engine": {"regime": None}})
    assert "<!--MERCADO_AYER-->" in h2
    assert email_html.render(_res("verde")) and email_html.render(_res("amarillo"))


def test_subject_is_short_and_informative():
    s = email_html.subject(_res())
    assert len(s) <= 70 and "Estrés alto" in s and "(5/10)" in s
    assert email_html.subject({"date": "2026-11-23"}).startswith("Trading Lab")
