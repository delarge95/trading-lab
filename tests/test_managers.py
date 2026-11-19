import math
from datetime import date, timedelta

import pytest

from trading_lab import managers


def _series(start: str, n: int, daily: float, base: float = 100.0):
    d0 = date.fromisoformat(start)
    return [((d0 + timedelta(days=i)).isoformat(), base * (1 + daily) ** i) for i in range(n)]


# ---------------------------------------------------------------- precios y ventanas
def test_window_starts_strictly_after_filing_date():
    s = [("2024-01-01", 100.0), ("2024-01-02", 110.0), ("2024-01-03", 121.0), ("2024-01-04", 200.0)]
    # presentación el 01-01: se compra al cierre del 01-02 (110), no al del 01-01 (anticipación)
    r = managers.holding_return(s, "2024-01-01", "2024-01-03")
    assert r == pytest.approx(200.0 / 110.0 - 1)


def test_window_uses_last_price_if_series_ends():
    s = [("2024-01-02", 10.0), ("2024-01-10", 15.0)]
    assert managers.holding_return(s, "2024-01-01", "2024-03-01") == pytest.approx(0.5)  # adquirida/deslistada
    assert managers.holding_return(s, "2024-02-01", "2024-03-01") is None                # sin datos después


def test_no_lookahead_future_prices_irrelevant():
    base = _series("2024-01-01", 200, 0.001)
    altered = base[:100] + [(d, p * 9) for d, p in base[100:]]
    end = base[60][0]
    assert managers.holding_return(base, base[10][0], end) == managers.holding_return(altered, base[10][0], end)


# ---------------------------------------------------------------- replicación
def _hist():
    return [
        {"filed": "2024-02-14", "period": "2023-12-31", "table": {
            "AAA": {"name": "A", "value": 800.0, "shares": 1}, "BBB": {"name": "B", "value": 200.0, "shares": 1}}},
        {"filed": "2024-05-15", "period": "2024-03-31", "table": {"AAA": {"name": "A", "value": 1.0, "shares": 1}}},
    ]


def test_follow_returns_weights_and_coverage():
    prices = {"AAA": _series("2024-01-01", 200, 0.002), "BBB": _series("2024-01-01", 200, -0.001)}
    bench = _series("2024-01-01", 200, 0.0005)
    rows = managers.follow_returns(_hist(), {"AAA": "AAA", "BBB": "BBB"}, prices, bench)
    assert len(rows) == 1 and rows[0]["coverage"] == pytest.approx(1.0)
    ra = managers.holding_return(prices["AAA"], "2024-02-14", "2024-05-15")
    rb = managers.holding_return(prices["BBB"], "2024-02-14", "2024-05-15")
    assert rows[0]["ret"] == pytest.approx(0.8 * ra + 0.2 * rb)


def test_follow_returns_renormalizes_when_ticker_missing_and_drops_low_coverage():
    prices = {"AAA": _series("2024-01-01", 200, 0.002)}
    bench = _series("2024-01-01", 200, 0.0005)
    rows = managers.follow_returns(_hist(), {"AAA": "AAA", "BBB": "BBB"}, prices, bench)  # BBB sin precios
    assert rows[0]["coverage"] == pytest.approx(0.8)
    assert rows[0]["ret"] == pytest.approx(managers.holding_return(prices["AAA"], "2024-02-14", "2024-05-15"))
    assert managers.follow_returns(_hist(), {}, prices, bench) == []  # cobertura 0 < 50%


# ---------------------------------------------------------------- OpenFIGI
def test_id_type_cins_for_foreign_issuers():
    assert managers.id_type("G0403H108") == "ID_CINS"   # AON plc (domiciliada fuera de EE. UU.)
    assert managers.id_type("037833100") == "ID_CUSIP"


def test_pick_ticker_prefers_us_composite():
    m = [{"marketSector": "Equity", "ticker": "BRK/B", "exchCode": "UN"},
         {"marketSector": "Equity", "ticker": "BRK/B", "exchCode": "US"},
         {"marketSector": "Corp", "ticker": "XYZ", "exchCode": "US"}]
    assert managers.pick_ticker(m) == "BRK-B"
    assert managers.pick_ticker([{"marketSector": "Corp", "ticker": "X"}]) is None
    assert managers.pick_ticker([]) is None


# ---------------------------------------------------------------- estadística
def test_sign_flip_p_detects_edge_and_not_noise():
    assert managers.sign_flip_p([0.02, 0.03, 0.01, 0.04, 0.02, 0.03, 0.05, 0.01]) < 0.02
    assert managers.sign_flip_p([0.02, -0.03, 0.01, -0.04, 0.02, -0.03, 0.05, -0.01]) > 0.3


def test_years_needed_matches_formula():
    # TE 6%, alfa 3%: ((1.645+0.8416)*0.06/0.03)^2 ≈ 24.7 años
    assert managers.years_needed(0.06) == pytest.approx(24.73, abs=0.05)


def test_evaluate_manager_consistency():
    rows = [{"from": f"2020-{m:02d}-15", "to": f"2020-{m + 3:02d}-15", "ret": 0.03 + 0.01 * (m % 3),
             "bench": 0.02, "coverage": 0.9} for m in (1, 2, 3, 4, 5, 6, 7, 8)]
    ev = managers.evaluate_manager(rows)
    assert ev["periods"] == 8 and ev["hit_rate"] == 1.0 and ev["excess_per_period"] > 0
    assert ev["excess_ci"][0] > 0 and ev["p_beat"] < 0.02
    assert managers.evaluate_manager(rows[:3]) is None   # muestra insuficiente


def test_evaluate_manager_matches_index_gives_no_significance():
    rows = [{"from": f"2021-{m:02d}-01", "to": f"2021-{m + 1:02d}-01", "ret": 0.02 + 0.01 * (-1) ** m,
             "bench": 0.02, "coverage": 1.0} for m in range(1, 11)]
    ev = managers.evaluate_manager(rows)
    assert ev["p_beat"] > 0.2 and ev["excess_ci"][0] < 0 < ev["excess_ci"][1]
