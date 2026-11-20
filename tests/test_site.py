import copy
import json
import math
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from trading_lab import site

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "forecast_sample.json"
HTML = ROOT / "docs" / "index.html"

TOP_KEYS = {"generated", "asof", "universe", "verdicts", "eval", "risk_validation", "tickers", "alerts",
            "lab", "ledger", "macro", "disclaimer", "caveats"}
TICKER_KEYS = {"ticker", "price", "mom12_1", "r1m", "vol63", "p5", "p21", "p63", "rel21", "lo21", "hi21",
               "ret21", "ret63", "dd21_10", "dd21_10_raw", "dd21_20", "dd63_10", "flags"}
EVAL_KEYS = {"label", "base_rate", "bss", "bss_ci", "auc", "ic", "ic_ci", "has_edge", "verdict"}


@pytest.fixture(scope="module")
def forecast_res():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def dash(forecast_res):
    return site.build_dashboard(forecast_res)


def _no_bad_numbers(x):
    if isinstance(x, float):
        assert math.isfinite(x)
    elif isinstance(x, dict):
        for k, v in x.items():
            assert isinstance(k, str)
            _no_bad_numbers(v)
    elif isinstance(x, list):
        for v in x:
            _no_bad_numbers(v)


# ----------------------------------------------------------------------------- dashboard
def test_json_serializable_without_nan(dash):
    text = json.dumps(dash, allow_nan=False, ensure_ascii=False)
    assert "NaN" not in text and "Infinity" not in text
    _no_bad_numbers(dash)


def test_contract_keys(dash):
    assert TOP_KEYS <= set(dash)
    assert dash["asof"] == "2026-11-19" and dash["universe"] == 100
    assert dash["alerts"] == [] and dash["lab"] is None and dash["ledger"] is None and dash["macro"] is None
    assert "no asesoría financiera" in dash["disclaimer"]
    assert any("supervivencia" in c for c in dash["caveats"])
    assert set(dash["eval"]) == {"up5", "up21", "up63", "rel21"}
    for e in dash["eval"].values():
        assert EVAL_KEYS <= set(e)
        assert isinstance(e["has_edge"], bool) and len(e["bss_ci"]) == 2
    assert set(dash["risk_validation"]) == {"21", "63"}
    assert dash["risk_validation"]["21"]["coverage80_ci"][0] < 0.8 < dash["risk_validation"]["21"]["coverage80_ci"][1]


def test_tickers_sorted_and_nvda(dash, forecast_res):
    names = [t["ticker"] for t in dash["tickers"]]
    assert names == sorted(names) and len(names) == 100
    n = next(t for t in dash["tickers"] if t["ticker"] == "NVDA")
    assert TICKER_KEYS <= set(n)
    src = forecast_res["tickers"]["NVDA"]
    assert n["price"] == pytest.approx(src["price"])
    assert n["p21"] == pytest.approx(src["p"]["up21"]["p"])
    assert n["rel21"] == pytest.approx(src["p"]["rel21"]["p"])
    assert n["lo21"] == pytest.approx(src["p"]["up21"]["lo"]) and n["hi21"] == pytest.approx(src["p"]["up21"]["hi"])
    assert n["ret21"] == pytest.approx([src["risk"]["21"]["p10"], src["risk"]["21"]["p50"], src["risk"]["21"]["p90"]])
    assert n["ret63"][0] < n["ret63"][1] < n["ret63"][2]
    assert n["dd21_10"] == pytest.approx(src["risk"]["21"]["dd_cal"])
    assert n["dd21_10_raw"] == pytest.approx(src["risk"]["21"]["dd"]["10"])
    assert n["dd63_10"] == pytest.approx(src["risk"]["63"]["dd_cal"])
    assert isinstance(n["flags"], list)
    # NVDA cae >30% desde su máximo y cayó >20% el último mes en la muestra
    assert any("máximo de 52 semanas" in f for f in n["flags"])


def test_verdicts_coherent_with_edge(forecast_res):
    d = site.build_dashboard(forecast_res)
    assert not d["eval"]["up21"]["has_edge"]
    assert "sin ventaja" in d["verdicts"]["prob_subida"]
    assert "tasa base" in d["verdicts"]["prob_subida"]
    assert "validados" in d["verdicts"]["rangos"]
    assert "79%" in d["verdicts"]["rangos"]

    # con ventaja en up21 el titular ya no puede decir "sin ventaja" para esa señal
    fc = copy.deepcopy(forecast_res)
    for k in fc["eval"]:
        fc["eval"][k]["has_edge"] = True
    d2 = site.build_dashboard(fc)
    assert "sin ventaja" not in d2["verdicts"]["prob_subida"]
    assert "sin ventaja" not in d2["verdicts"]["superar_spy"]

    # cobertura fuera del IC -> no se declara validado
    fc = copy.deepcopy(forecast_res)
    fc["risk_validation"]["21"]["coverage80_ci"] = [0.6, 0.7]
    assert "validados" not in site.build_dashboard(fc)["verdicts"]["rangos"]


def test_in_memory_int_keys_and_nan(forecast_res):
    fc = copy.deepcopy(forecast_res)
    for t in fc["tickers"].values():
        t["risk"] = {int(h): v for h, v in t["risk"].items()}
        t["risk"][21]["dd"] = {int(k): v for k, v in t["risk"][21]["dd"].items()}
    fc["tickers"]["NVDA"]["vol63"] = float("nan")
    fc["tickers"]["AAPL"]["risk"][21]["p10"] = float("inf")
    d = site.build_dashboard(fc)
    n = next(t for t in d["tickers"] if t["ticker"] == "NVDA")
    assert n["vol63"] is None
    assert n["dd21_20"] == pytest.approx(forecast_res["tickers"]["NVDA"]["risk"]["21"]["dd"]["20"])
    a = next(t for t in d["tickers"] if t["ticker"] == "AAPL")
    assert a["ret21"][0] is None
    json.dumps(d, allow_nan=False)


def test_with_optional_blocks(forecast_res):
    alerts = {"generated": "2026-11-19", "alerts": [
        {"id": "x:NVDA:2026-11-19", "severity": "alta", "kind": "x", "ticker": "NVDA", "title": "T", "detail": "D"}],
        "counts": {"alta": 1, "media": 0, "info": 0}}
    lab = {"rules": {"mom12_1": {"label": "Momentum 12-1", "sharpe": 0.5, "sharpe_ci": [0.1, float("nan")],
                                 "p_holm": 0.4}}, "verdict": "v", "caveats": ["c"], "picks_now": {"mom12_1": ["AAPL"]}}
    ledger = {"as_of": "2026-11-19", "rules": {1: {"closed": 0}}, "entries_total": 3}
    macro = {"VIX": 18.2, "curva": {"10y2y": float("nan"), "10y3m": -0.2}, "texto": "ok"}
    d = site.build_dashboard(forecast_res, lab, ledger, alerts, macro, {"generated": "2026-11-19T10:00:00Z"})
    assert d["alerts"][0]["severity"] == "alta"
    assert d["lab"]["rules"]["mom12_1"]["sharpe_ci"] == [0.1, None]
    assert d["ledger"]["rules"]["1"]["closed"] == 0
    assert d["macro"]["VIX"] == 18.2 and d["macro"]["curva"] == {"10y3m": -0.2} or "10y2y" in d["macro"]["curva"]
    assert d["generated"] == "2026-11-19T10:00:00Z"
    json.dumps(d, allow_nan=False)
    # alertas globales (ticker None) y de emisor sin ticker ("~NOMBRE") pasan tal cual
    raras = [{"id": "vix:-:2026-11-19", "severity": "media", "kind": "vix", "ticker": None, "title": "VIX", "detail": ""},
             {"id": "insider:~PERSHING SQUARE:2026-11-19", "severity": "info", "kind": "insider",
              "ticker": "~PERSHING SQUARE HOLDING", "title": "t", "detail": "d"}]
    got = site.build_dashboard(forecast_res, alerts={"alerts": raras})["alerts"]
    assert got[0]["ticker"] is None and got[1]["ticker"] == "~PERSHING SQUARE HOLDING"
    # lista de alertas directa
    assert site.build_dashboard(forecast_res, alerts=alerts["alerts"])["alerts"] == alerts["alerts"]


def test_write_roundtrip(dash, tmp_path):
    p = site.write(dash, tmp_path / "sub" / "dashboard.json")
    text = p.read_text(encoding="utf-8")
    assert text.startswith('{"generated":"') and "\n" not in text  # compacto
    assert json.loads(text) == dash


def test_write_real_dashboard_once(dash):
    # genera docs/data/dashboard.json con el fixture (solo si aún no existe) para probar el panel
    path = ROOT / "docs" / "data" / "dashboard.json"
    if not path.exists():
        site.write(dash, path)
    assert json.loads(path.read_text(encoding="utf-8"))["universe"] >= 1


# ----------------------------------------------------------------------------- HTML
@pytest.fixture(scope="module")
def html():
    return HTML.read_text(encoding="utf-8")


def _script(html):
    m = re.search(r"<script>(.*?)</script>", html, re.S)
    assert m
    return m.group(1)


REQUIRED_IDS = ["asof", "generated", "verdicts", "buscar", "tabla", "tbody", "thead-row", "detalle", "d-cuerpo",
                "alertas-lista", "lab", "ledger", "calc-form", "c-capital", "c-riesgo", "c-entrada", "c-stop",
                "calc-error", "r-acciones", "r-valor", "r-perdida", "r-pct", "caveats", "estado", "aviso"]


def test_html_ids_and_basics(html):
    for i in REQUIRED_IDS:
        assert f'id="{i}"' in html, i
    assert '<html lang="es">' in html
    assert "width=device-width" in html
    assert "prefers-color-scheme: dark" in html
    assert "Herramienta de investigación, no asesoría financiera" in html
    assert "cálculo educativo, no una recomendación" in html.lower() or "Cálculo educativo, no una recomendación" in html
    assert "data/dashboard.json" in html
    assert (ROOT / "docs" / ".nojekyll").exists()


def test_html_no_innerhtml_no_external(html):
    script = _script(html)
    assert "innerHTML" not in html and "outerHTML" not in html and "insertAdjacentHTML" not in html
    assert "document.write" not in script and "eval(" not in script
    assert not re.search(r"https?://", html), "el panel no debe tener URLs externas"
    assert not re.search(r"<script[^>]+src=", html) and not re.search(r"<link[^>]+href=", html)


def test_script_syntax_node(html, tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("node no disponible")
    f = tmp_path / "panel.js"
    f.write_text(_script(html), encoding="utf-8")
    r = subprocess.run([node, "--check", str(f)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
