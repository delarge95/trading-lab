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
    assert "color-scheme:light" in html   # misma apariencia que el correo (claro)
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


# ============================================================================ v3: bloques opcionales
NEW_KEYS = {"regime", "events", "fundamentals", "portfolio", "convergence", "ranking"}


def _toy_portfolio():
    return {"h21": {"tickers": ["AAPL", "MSFT"], "sigma_now": {"AAPL": 0.08, "MSFT": 0.07},
                    "dates": ["2024-01-02", "2024-01-03"], "z": [[0.1, float("nan")], [-0.0, 1.234]]},
            "h63": {"tickers": ["AAPL"], "sigma_now": {"AAPL": 0.14}, "dates": ["2024-01-02"], "z": [[0.5]]}}


def test_new_keys_none_without_optional_data(dash):
    assert NEW_KEYS <= set(dash)
    for k in NEW_KEYS:
        assert dash[k] is None, k


def test_new_keys_with_optional_data(forecast_res):
    regime = {"state": "amarillo", "rules": [{"name": "VIX", "value": float("nan"), "state": "amarillo", "threshold": [20, 30]}]}
    events = {"asof": "2026-11-19", "events": [{"date": "2026-11-20", "kind": "earnings", "ticker": "NVDA",
                                                "label": "Resultados", "days_to": 1, "time": None}]}
    fund = {"coverage": 1, "tickers": {"NVDA": {"revenue_ttm": 1e9, "op_margin_ttm": float("inf")}}}
    conv = {"AAPL": {"managers": ["A", "B"], "new_by": [], "avg_weight": 0.05}}
    rank = {"criteria": [{"key": "k", "label": "L", "favorable": [{"ticker": "AAPL", "value": 0.1}], "desfavorable": [],
                          "evidence": "validado", "note": "n", "format": "pct", "degenerate": False, "n": 1}],
            "rule_selections": [], "summary": "s"}
    d = site.build_dashboard(forecast_res, regime=regime, events=events, fundamentals=fund,
                             portfolio=_toy_portfolio(), convergence=conv, ranking=rank)
    assert d["regime"]["state"] == "amarillo" and d["regime"]["rules"][0]["value"] is None
    assert d["events"]["events"][0]["ticker"] == "NVDA"
    assert d["fundamentals"]["tickers"]["NVDA"]["op_margin_ttm"] is None
    assert d["convergence"]["AAPL"]["managers"] == ["A", "B"]
    assert d["ranking"]["criteria"][0]["key"] == "k"
    p = d["portfolio"]
    assert p["h21"]["z"] == [[0.1, 0.0], [0.0, 1.234]]
    assert "-0.0" not in json.dumps(p["h21"]["z"])
    assert p["sectors"]["AAPL"].startswith("Tecnolog") and p["sectors"]["MSFT"].startswith("Tecnolog")
    text = json.dumps(d, allow_nan=False)
    assert "NaN" not in text and "Infinity" not in text
    # los parámetros existentes no cambian de posición
    d2 = site.build_dashboard(forecast_res, None, None, None, None, {"generated": "x"})
    assert d2["generated"] == "x" and d2["portfolio"] is None
    # portfolio sin bloques utilizables -> None
    assert site.build_dashboard(forecast_res, portfolio={"method": "x"})["portfolio"] is None


def test_real_size_budget(forecast_res):
    """Con 100 acciones x 400 escenarios x 2 horizontes el JSON debe ser razonable (< 1,3 MB)."""
    import numpy as np
    rng = np.random.default_rng(0)
    tick = [f"T{i}" for i in range(100)]
    blk = {h: {"tickers": tick, "sigma_now": {t: 0.08 for t in tick}, "dates": ["2020-01-01"] * 400,
               "z": np.round(rng.normal(0, 1, (400, 100)), 2).tolist()} for h in ("h21", "h63")}
    d = site.build_dashboard(forecast_res, portfolio=blk)
    assert len(json.dumps(d, ensure_ascii=False, separators=(",", ":"))) < 1_300_000


# ============================================================================ v3: páginas
PAGES = {n: ROOT / "docs" / f"{n}.html" for n in ("index", "cartera", "diario")}
NODE = shutil.which("node")


@pytest.fixture(scope="module", params=sorted(PAGES))
def page(request):
    return request.param, PAGES[request.param].read_text(encoding="utf-8")


def test_all_pages_basics(page):
    name, h = page
    assert '<html lang="es">' in h and "width=device-width" in h and "color-scheme:light" in h
    assert "Herramienta de investigación; los cálculos usan los datos y reglas que tú introduces; no es asesoría financiera." in h
    assert "data/dashboard.json" in h
    for href in ("index.html", "cartera.html", "diario.html"):
        assert f'href="{href}"' in h, (name, href)
    assert 'aria-current="page"' in h
    for tok in ("--accent:#1b2330", "--danger:#a31616", "--ok:#175c33", "--bg:#f2f4f8"):   # paleta única (igual que el correo)
        assert tok in h, (name, tok)


def test_all_pages_no_innerhtml_no_external_no_eval(page):
    name, h = page
    assert "innerHTML" not in h and "outerHTML" not in h and "insertAdjacentHTML" not in h
    scripts = re.findall(r"<script>(.*?)</script>", h, re.S)
    assert len(scripts) == 1
    assert "document.write" not in scripts[0] and "eval(" not in scripts[0] and "new Function" not in scripts[0]
    assert not re.search(r"https?://", h), f"{name}: URLs externas"
    assert not re.search(r"<script[^>]+src=", h) and not re.search(r"<link[^>]+href=", h)
    assert not re.search(r"<img|<iframe|<object|<embed|@import|url\(", h)
    # los datos nunca se interpolan en atributos de evento
    assert not re.search(r"\son(click|load|error|input|change)=", h)


@pytest.mark.skipif(not NODE, reason="node no disponible")
def test_all_scripts_node_check(page, tmp_path):
    name, h = page
    f = tmp_path / f"{name}.js"
    f.write_text(re.search(r"<script>(.*?)</script>", h, re.S).group(1), encoding="utf-8")
    r = subprocess.run([NODE, "--check", str(f)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


IDS = {
    "index": ["hoy", "hoy-regimen", "hoy-eventos", "hoy-alertas", "go-cartera", "go-diario", "ranking", "rk-tabs", "rk-panel",
              "rk-reglas", "rk-resumen"],
    "cartera": ["paste", "btn-paste", "btn-ejemplo", "capital", "tabla-pos", "tbody-pos", "btn-add", "btn-borrar", "r-maxw",
                "r-maxrisk", "r-maxloss", "sizer-form", "s-entry", "s-stop", "s-out", "res-cuerpo", "res-regimen", "res-rangos",
                "res-prob", "res-contrib", "res-conc", "res-sector", "res-gestores", "res-eventos", "res-reglas",
                "fuera-universo", "privacidad", "estado", "asof"],
    "diario": ["d-form", "f-ticker", "f-tesis", "f-horizonte", "f-entrada", "f-stop", "f-tamano", "f-riesgo", "f-invalida",
               "f-capital", "checklist", "btn-guardar", "tabla-diario", "tbody-diario", "resumen", "btn-export-json",
               "btn-export-csv", "import-file", "cerrar-dlg", "x-precio", "x-motivo", "x-ok", "g-maxw", "g-maxrisk",
               "g-maxloss", "privacidad", "estado", "asof"],
}


def test_required_ids_per_page(page):
    name, h = page
    for i in IDS[name]:
        assert f'id="{i}"' in h, (name, i)
    if name != "index":
        assert "localStorage" in h and re.search(r"No se envían? a ningún servidor", h)


def test_pages_have_no_buy_sell_language(page):
    name, h = page
    low = h.lower()
    for bad in ("te recomendamos", "debes comprar", "debes vender", "compra ahora", "vende ahora", ">comprar<", ">vender<"):
        assert bad not in low, (name, bad)
    assert "mejor perfil según este criterio" in low or name != "index"


# ---------------------------------------------------------------------------- matemática del navegador (Node)
def _pure(name):
    h = PAGES[name].read_text(encoding="utf-8")
    m = re.search(r"/\* @@PURE-BEGIN \*/(.*?)/\* @@PURE-END \*/", h, re.S)
    assert m, name
    return m.group(1)


def _node(name, body, tmp_path):
    f = tmp_path / f"{name}_t.js"
    f.write_text(_pure(name) + "\n" + body, encoding="utf-8")
    r = subprocess.run([NODE, str(f)], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


# escenarios construidos a mano: r1 y r2 son los retornos de dos posiciones; con sigma=1 se usa z = log(1+r)
HAND = """
var r1=[-0.10,0.04,0.00,0.06], r2=[-0.05,0.02,0.01,-0.01];
var block={tickers:["A","B"],sigma_now:{A:1,B:1},z:r1.map(function(_,i){return [Math.log(1+r1[i]),Math.log(1+r2[i])];})};
var w={A:0.6,B:0.4};
var pr=portfolioReturns(block,w);
var rc=riskContributions(block,w,0.25);
console.log(JSON.stringify({r:pr.r,used:pr.used,p10:percentile(pr.r,0.10),p50:percentile(pr.r,0.5),p90:percentile(pr.r,0.9),
  l5:probLoss(pr.r,0.05),l10:probLoss(pr.r,0.10),rc:rc,
  pos:positionReturns(block,"A"),none:positionReturns(block,"ZZ")}));
"""


@pytest.mark.skipif(not NODE, reason="node no disponible")
def test_browser_math_hand_case(tmp_path):
    o = _node("cartera", HAND, tmp_path)
    # p = 0.6*r1 + 0.4*r2
    assert o["r"] == pytest.approx([-0.08, 0.032, 0.004, 0.032], abs=1e-12)
    assert o["used"] == ["A", "B"]
    # percentiles con interpolación lineal (como numpy): ordenados -0.08, 0.004, 0.032, 0.032
    assert o["p10"] == pytest.approx(-0.0548, abs=1e-12)
    assert o["p50"] == pytest.approx(0.018, abs=1e-12)
    assert o["p90"] == pytest.approx(0.032, abs=1e-12)
    import numpy as np
    assert np.percentile([-0.08, 0.032, 0.004, 0.032], [10, 50, 90]).tolist() == pytest.approx([o["p10"], o["p50"], o["p90"]])
    assert o["l5"] == pytest.approx(0.25) and o["l10"] == 0.0              # solo el escenario -8% pierde más de 5%
    rc = o["rc"]
    assert rc["tickers"] == ["A", "B"] and rc["es"] == pytest.approx(-0.08) and rc["thr"] == pytest.approx(-0.017)
    # cola (peor 25%): solo el primer escenario; aportes -0.06 y -0.02 sobre -0.08
    assert rc["tail"] == pytest.approx([0.75, 0.25])
    # contribución a la varianza: cov(w_i r_i, p) / var(p) = 0.00168/0.002107
    assert rc["vol"][0] == pytest.approx(0.00672 / 0.008428, abs=1e-9) and sum(rc["vol"]) == pytest.approx(1.0)
    # pérdida adversa de cada posición: w_i * percentil 25 de sus propios retornos
    assert rc["adverse"] == pytest.approx([0.6 * np.percentile([-0.10, 0.04, 0.0, 0.06], 25), 0.4 * np.percentile([-0.05, 0.02, 0.01, -0.01], 25)])
    assert o["none"] is None and o["pos"] == pytest.approx([-0.10, 0.04, 0.0, 0.06], abs=1e-12)


@pytest.mark.skipif(not NODE, reason="node no disponible")
def test_browser_math_matches_python_samples(tmp_path):
    """Con las muestras reales del fixture de cartera, la simulación del navegador coincide con numpy."""
    import numpy as np
    from trading_lab import portfolio as pf
    rng = np.random.default_rng(2)
    T = 900
    import pandas as pd
    P = pd.DataFrame({f"S{j}": 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.012 + 0.002 * j, T))) for j in range(4)},
                     index=pd.bdate_range("2020-01-01", periods=T))
    blk = pf.joint_samples(P, list(P.columns), horizons=(21,), n=200)["h21"]
    w = {"S0": 0.4, "S1": 0.3, "S3": 0.2}
    z = np.array(blk["z"])
    r = sum(w[t] * (np.exp(blk["sigma_now"][t] * z[:, blk["tickers"].index(t)]) - 1) for t in w)
    body = f"var block={json.dumps(blk)}; var w={json.dumps(w)};" + """
var pr=portfolioReturns(block,w).r;
console.log(JSON.stringify({q:[percentile(pr,0.1),percentile(pr,0.5),percentile(pr,0.9)],l5:probLoss(pr,0.05),l10:probLoss(pr,0.10),n:pr.length}));"""
    o = _node("cartera", body, tmp_path)
    assert o["n"] == len(z)
    assert o["q"] == pytest.approx(np.percentile(r, [10, 50, 90]).tolist(), abs=1e-12)
    assert o["l5"] == pytest.approx(float((r < -0.05).mean())) and o["l10"] == pytest.approx(float((r < -0.10).mean()))


@pytest.mark.skipif(not NODE, reason="node no disponible")
def test_browser_math_sizing_concentration_parsing(tmp_path):
    body = """
var out={};
out.s1=positionSize(10000,1,50,45,null);               // presupuesto 100, riesgo/acción 5 -> 20 acciones
out.s2=positionSize(10000,1,50,45,5);                  // peso máx 5% -> 500/50 = 10 acciones
out.s3=positionSize(10000,10,50,49,null);              // riesgo manda 1000 acciones pero el capital alcanza para 200
out.e1=positionSize(10000,1,50,55,null); out.e2=positionSize(0,1,50,45,null); out.e3=positionSize(1000,150,50,45,null);
out.conc=concentration({A:0.5,B:0.3,C:0.2});
out.conc0=concentration({});
out.sec=sectorExposure({A:0.5,B:0.2,C:0.1},{A:"Salud",B:"Finanzas",C:"Salud"});
out.paste=parsePaste("AAPL 40%, MSFT 30,5 %; brk-b: 1,500 USD\\nKO = $20");
out.num=[parseNum("1.234,56"),parseNum("1,234.56"),parseNum("12,5"),parseNum("1,500"),parseNum("abc"),parseNum("")];
out.rw=resolveWeights([{ticker:"A",peso:NaN,valor:4000},{ticker:"B",peso:NaN,valor:6000}],NaN);
out.rw2=resolveWeights([{ticker:"A",peso:40,valor:NaN},{ticker:"A",peso:10,valor:NaN},{ticker:"B",peso:NaN,valor:2000}],10000);
console.log(JSON.stringify(out,function(k,v){return v===Infinity?"inf":(typeof v==="number"&&isNaN(v)?"nan":v);}));
"""
    o = _node("cartera", body, tmp_path)
    assert o["s1"]["shares"] == 20 and o["s1"]["binding"] == "riesgo" and o["s1"]["loss"] == 100 and o["s1"]["weightPct"] == 10
    assert o["s2"]["shares"] == 10 and o["s2"]["binding"] == "peso" and o["s2"]["loss"] == 50
    assert o["s3"]["shares"] == 200 and o["s3"]["binding"] == "capital"
    assert all("error" in o[k] for k in ("e1", "e2", "e3"))
    c = o["conc"]
    assert c["maxW"] == 0.5 and c["hhi"] == pytest.approx(0.38) and c["effN"] == pytest.approx(1 / 0.38) and c["n"] == 3
    assert o["conc0"] is None
    assert [(s["sector"], round(s["w"], 6)) for s in o["sec"]] == [("Salud", 0.6), ("Finanzas", 0.2)]
    assert o["paste"] == [{"ticker": "AAPL", "peso": 40, "valor": "nan"}, {"ticker": "MSFT", "peso": 30.5, "valor": "nan"},
                          {"ticker": "BRK-B", "peso": "nan", "valor": 1500}, {"ticker": "KO", "peso": "nan", "valor": 20}]
    assert o["num"][:4] == [1234.56, 1234.56, 12.5, 1500] and o["num"][4:] == ["nan", "nan"]
    assert o["rw"]["capital"] == 10000 and o["rw"]["weights"] == {"A": 0.4, "B": 0.6}
    assert o["rw2"]["weights"] == pytest.approx({"A": 0.5, "B": 0.2}) and o["rw2"]["cash"] == pytest.approx(0.3)


CHECK = """
var base={ticker:"AAA",entry:100,stop:95,size:30,capital:10000,maxRiskPct:1,invalidation:"cierre bajo 95"};
var rowOk={ticker:"AAA",dd21_10:0.10,ret21:[-0.08,0.02,0.10]};
var ctx={row:rowOk,ddStats:{median:0.12,p90:0.25},events:[{kind:"earnings",ticker:"AAA",days_to:3,label:"Resultados",date:"2026-12-01"},
   {kind:"earnings",ticker:"BBB",days_to:2,label:"x",date:"d"}],regimeState:"rojo",currentWeight:0.05,rules:{maxW:20,maxRisk:1,maxLoss:10}};
function by(items){var o={};items.forEach(function(i){o[i.id]=i.status;});return o;}
var out={};
out.a=by(evaluateChecklist(base,ctx));
out.aText=evaluateChecklist(base,ctx).map(function(i){return i.detail;});
// peso resultante: 0.05 + 30*100/10000 = 0.35 > 20%; pérdida: 30*5/10000 = 1.5% > 1%
var ok=JSON.parse(JSON.stringify(base)); ok.size=10;      // 0.05+0.10=15% <= 20%; pérdida 0.5%
var ctx2=JSON.parse(JSON.stringify(ctx)); ctx2.regimeState="verde"; ctx2.events=[]; ctx2.row.dd21_10=0.30; ctx2.row.ret21=[-0.03,0.02,0.1];
out.b=by(evaluateChecklist(ok,ctx2));
var none=evaluateChecklist({ticker:"ZZ"},{row:null,ddStats:null,events:null,regimeState:null,currentWeight:0,rules:{}});
out.c=by(none);
out.score=[checklistScore(evaluateChecklist(base,ctx)),checklistScore(none)];
out.s0=evaluateChecklist(Object.assign({},base,{stop:NaN,invalidation:""}),ctx).filter(function(i){return i.id==="salida";})[0];
var es=[{status:"cerrada",entry:100,stop:95,size:10,exit:{price:110},ok:7,total:7},
        {status:"cerrada",entry:50,stop:45,size:20,exit:{price:45},ok:4,total:7},
        {status:"abierta",entry:10,stop:9,size:1,exit:null,ok:6,total:7}];
out.res=[entryResult(es[0]),entryResult(es[1]),entryResult(es[2])];
out.sum=summarize(es);
console.log(JSON.stringify(out,function(k,v){return typeof v==="number"&&!isFinite(v)?null:v;}));
"""


@pytest.mark.skipif(not NODE, reason="node no disponible")
def test_diario_checklist_and_summary(tmp_path):
    o = _node("diario", CHECK, tmp_path)
    assert o["a"] == {"caida": "ok", "rango": "warn", "evento": "warn", "regimen": "bad", "peso": "bad", "perdida": "bad", "salida": "ok"}
    assert any("35,0%" in t for t in o["aText"]) and any("1,50%" in t for t in o["aText"])
    # stop a 5% vs P10 de -8%: advertencia; con P10 de -3% cumple
    assert o["b"] == {"caida": "warn", "rango": "ok", "evento": "ok", "regimen": "ok", "peso": "ok", "perdida": "ok", "salida": "ok"}
    assert o["c"]["caida"] == o["c"]["evento"] == o["c"]["regimen"] == "info" and o["c"]["salida"] == "bad"
    assert o["score"][0] == {"ok": 2, "total": 7} and o["score"][1] == {"ok": 0, "total": 1}
    assert o["s0"]["status"] == "bad" and "stop" in o["s0"]["detail"] and "motivo" in o["s0"]["detail"]
    # resultado: +10% (+100 USD, 2R) y -10% (-100 USD, -1R)
    assert o["res"][0] == pytest.approx({"pct": 0.10, "usd": 100, "r": 2.0})
    assert o["res"][1] == pytest.approx({"pct": -0.10, "usd": -100, "r": -1.0}) and o["res"][2] is None
    s = o["sum"]
    assert s["n"] == 3 and s["open"] == 1 and s["closed"] == 2 and s["wins"] == 1 and s["hitRate"] == 0.5
    assert s["meanPct"] == pytest.approx(0.0) and s["totalUsd"] == pytest.approx(0)
    assert s["compliance"] == pytest.approx((1 + 4 / 7 + 6 / 7) / 3)
    assert s["allOk"]["n"] == 1 and s["allOk"]["mean"] == pytest.approx(0.10) and s["notAllOk"]["n"] == 1


@pytest.mark.skipif(not NODE, reason="node no disponible")
def test_diario_csv_roundtrip_and_injection(tmp_path):
    body = """
var es=[{id:"a1",created:"2026-11-19",ticker:"AAPL",thesis:'Dijo "ok", luego\\nsegunda línea',horizon:"1 mes",entry:100.5,stop:95,size:10,
  maxRiskPct:1,capital:10000,invalidation:"=SUMA(A1)",status:"cerrada",exit:{price:110,date:"2026-12-01",reason:"@objetivo"},ok:5,total:7},
 {id:"a2",created:"2026-11-20",ticker:"MSFT",thesis:"",horizon:"3 meses",entry:300,stop:null,size:2,maxRiskPct:null,capital:null,
  invalidation:"",status:"abierta",exit:null,ok:null,total:null}];
var csv=toCSV(es);
var back=entriesFromCSV(csv);
console.log(JSON.stringify({csv:csv,back:back,rows:parseCSV("a,b\\n1,\\"x,y\\"\\r\\n2,3\\n")}));
"""
    o = _node("diario", body, tmp_path)
    first = o["csv"].split("\n")[1]
    assert "'=SUMA(A1)" in o["csv"] and "'@objetivo" in o["csv"]          # neutraliza fórmulas al abrir en una hoja
    assert o["csv"].startswith("id,fecha,ticker,tesis")
    a, b = o["back"]
    assert a["thesis"] == 'Dijo "ok", luego\nsegunda línea' and a["invalidation"] == "=SUMA(A1)"
    assert a["entry"] == 100.5 and a["stop"] == 95 and a["status"] == "cerrada"
    assert a["exit"] == {"price": 110, "date": "2026-12-01", "reason": "@objetivo"} and a["ok"] == 5 and a["total"] == 7
    assert b["status"] == "abierta" and b["exit"] is None and b["stop"] is None and b["ticker"] == "MSFT"
    assert o["rows"] == [{"a": "1", "b": "x,y"}, {"a": "2", "b": "3"}]
    assert first.startswith("a1,2026-11-19,AAPL")
