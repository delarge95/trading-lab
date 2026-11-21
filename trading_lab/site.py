"""Construye `docs/data/dashboard.json`, el único dato que lee el panel estático `docs/index.html`.

Todo el texto es hecho calculado de los datos (nada de recomendaciones). Herramienta de investigación,
no asesoría financiera.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

DISCLAIMER = "Herramienta de investigación, no asesoría financiera."

CAVEATS = [
    "Sesgo de supervivencia: el universo se arma con acciones que existen hoy; las que se deslistaron no aparecen y eso infla los resultados históricos.",
    "El rendimiento pasado no garantiza resultados futuros.",
    "Las probabilidades son estimaciones con incertidumbre; sin ventaja estadística fuera de muestra equivalen a la tasa base histórica.",
    "Los rangos de retorno y el riesgo de caída son estadísticos y no incluyen costos, impuestos ni deslizamiento.",
]

LABELS = {
    "up5": "Sube en 5 ruedas (1 semana)",
    "up21": "Sube en 21 ruedas (1 mes)",
    "up63": "Sube en 63 ruedas (3 meses)",
    "rel21": "Supera a SPY en 21 ruedas (1 mes)",
}

_HORIZON_TXT = {"21": "1 mes", "63": "3 meses"}


# ----------------------------------------------------------------------------- utilidades
def _clean(x):
    """Recursivo: NaN/inf -> None, claves a str, tuplas -> listas, numpy -> Python."""
    if x is None or isinstance(x, (str, bool)):
        return x
    if isinstance(x, dict):
        return {str(k): _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple, set)):
        return [_clean(v) for v in x]
    if hasattr(x, "item") and not isinstance(x, (int, float)):  # escalares numpy
        try:
            return _clean(x.item())
        except Exception:  # noqa: BLE001
            return None
    if hasattr(x, "isoformat"):
        return x.isoformat()
    if isinstance(x, int):
        return x
    if isinstance(x, float):
        return x if math.isfinite(x) else None
    try:
        f = float(x)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return str(x)


def _num(x):
    """float finito o None."""
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _get(d, *keys):
    """Acceso tolerante a claves int/str (risk[21] vs risk["21"])."""
    for k in keys:
        if isinstance(d, dict):
            if k in d:
                d = d[k]
            elif str(k) in d:
                d = d[str(k)]
            elif isinstance(k, str) and k.isdigit() and int(k) in d:
                d = d[int(k)]
            else:
                return None
        else:
            return None
    return d


def _pct(x, dec=0):
    return f"{x * 100:.{dec}f}%".replace(".", ",") if x is not None else "s/d"


def _pair(x):
    if isinstance(x, (list, tuple)) and len(x) == 2:
        return [_num(x[0]), _num(x[1])]
    return [None, None]


def _trio(r):
    if not isinstance(r, dict):
        return [None, None, None]
    return [_num(r.get("p10")), _num(r.get("p50")), _num(r.get("p90"))]


def _quantile(values, q):
    v = sorted(x for x in values if x is not None)
    if not v:
        return None
    return v[min(len(v) - 1, max(0, math.ceil(q * (len(v) - 1))))]


def _median(values):
    v = sorted(x for x in values if x is not None)
    if not v:
        return None
    m = len(v) // 2
    return v[m] if len(v) % 2 else (v[m - 1] + v[m]) / 2


# ----------------------------------------------------------------------------- bloques
def _eval_block(fc: dict) -> dict:
    out = {}
    for key, e in (fc.get("eval") or {}).items():
        out[key] = {
            "label": LABELS.get(key, key),
            "n_oos": e.get("n_oos"),
            "base_rate": _num(e.get("base_rate")),
            "bss": _num(e.get("bss")),
            "bss_ci": _pair(e.get("bss_ci")),
            "auc": _num(e.get("auc")),
            "ic": _num(e.get("ic")),
            "ic_ci": _pair(e.get("ic_ci")),
            "has_edge": bool(e.get("has_edge")),
            "verdict": e.get("verdict"),
        }
    return _clean(out)


def _risk_validation(fc: dict) -> dict:
    out = {}
    for h, v in (fc.get("risk_validation") or {}).items():
        h = str(h)
        out[h] = {
            "h": v.get("h"),
            "n": v.get("n"),
            "coverage80": _num(v.get("coverage80")),
            "coverage80_ci": _pair(v.get("coverage80_ci")),
            "below_p10": _num(v.get("below_p10")),
            "above_p90": _num(v.get("above_p90")),
            "dd_level": _num(v.get("dd_level")),
            "dd_base": _num(v.get("dd_base")),
            "dd_skill": _num(v.get("dd_skill")),
        }
    return _clean(out)


def _verdicts(ev: dict, rv: dict) -> dict:
    """Titulares honestos calculados de los datos. Devuelve (textos, niveles)."""
    texts, levels = {}, {}

    # P(sube) en los tres horizontes
    ups = [k for k in ("up5", "up21", "up63") if k in ev]
    if ups:
        con = [k for k in ups if ev[k]["has_edge"]]
        if not con:
            texts["prob_subida"] = ("Probabilidad de subida: sin ventaja estadística fuera de muestra "
                                    "(el modelo se reduce a la tasa base)")
            levels["prob_subida"] = "none"
        else:
            nombres = ", ".join(ev[k]["label"].split(" (")[0].replace("Sube en ", "") for k in con)
            texts["prob_subida"] = (f"Probabilidad de subida: ventaja estadística fuera de muestra solo en {nombres}; "
                                    "en el resto es la tasa base")
            levels["prob_subida"] = "warn"
        if "up21" in ev:
            e = ev["up21"]
            lo, hi = e["bss_ci"]
            texts["prob_subida_detalle"] = (
                f"A 1 mes: tasa base {_pct(e['base_rate'])}; BSS {_fmt(e['bss'], 3)} "
                f"(IC95% {_fmt(lo, 3)} a {_fmt(hi, 3)}); AUC {_fmt(e['auc'], 2)}.")
            levels["prob_subida_detalle"] = levels["prob_subida"]

    if "rel21" in ev:
        e = ev["rel21"]
        if e["has_edge"]:
            texts["superar_spy"] = "Superar a SPY a 1 mes: hay ventaja estadística fuera de muestra"
            levels["superar_spy"] = "warn"
        else:
            texts["superar_spy"] = ("Superar a SPY a 1 mes: sin ventaja estadística fuera de muestra "
                                    f"(la tasa base es {_pct(e['base_rate'])})")
            levels["superar_spy"] = "none"

    # Rangos de retorno
    if rv:
        partes, ok_all, any_data = [], True, False
        for h in ("21", "63"):
            v = rv.get(h)
            if not v or v.get("coverage80") is None:
                continue
            any_data = True
            lo, hi = v["coverage80_ci"]
            dentro = lo is not None and hi is not None and lo <= 0.80 <= hi
            ok_all = ok_all and dentro
            partes.append(f"{_pct(v['coverage80'])} a {_HORIZON_TXT[h]}")
        if any_data:
            cobs = " y ".join(partes)
            if ok_all:
                texts["rangos"] = (f"Rangos de retorno: validados (el intervalo P10-P90 cubrió {cobs} de los casos "
                                   "reales; el objetivo es 80%)")
                levels["rangos"] = "ok"
            else:
                texts["rangos"] = (f"Rangos de retorno: calibración imperfecta (el intervalo P10-P90 cubrió {cobs}; "
                                   "el objetivo es 80%): usar con cautela")
                levels["rangos"] = "warn"

        # Riesgo de caída
        frases, niveles = [], []
        for h in ("21", "63"):
            v = rv.get(h)
            if not v or v.get("dd_skill") is None:
                continue
            s = v["dd_skill"]
            if s >= 0.02:
                frases.append(f"a {_HORIZON_TXT[h]} mejora la tasa base ({_pct(s, 1)} de habilidad Brier)")
                niveles.append("ok")
            elif s > 0:
                frases.append(f"a {_HORIZON_TXT[h]} mejora apenas la tasa base ({_pct(s, 1)})")
                niveles.append("warn")
            else:
                frases.append(f"a {_HORIZON_TXT[h]} no mejora la tasa base ({_pct(s, 1)})")
                niveles.append("none")
        if frases:
            lvl = rv.get("21") or rv.get("63") or {}
            nivel = "ok" if all(n == "ok" for n in niveles) else ("none" if all(n == "none" for n in niveles) else "warn")
            base_txt = ""
            if lvl.get("dd_level") is not None:
                base_txt = (f" Caída de referencia: más de {_pct(lvl['dd_level'])}; "
                            "frecuencia histórica " +
                            " y ".join(f"{_pct(rv[h]['dd_base'])} a {_HORIZON_TXT[h]}"
                                       for h in ("21", "63") if rv.get(h) and rv[h].get("dd_base") is not None) + ".")
            texts["riesgo_caida"] = "Riesgo de caída: " + "; ".join(frases) + "." + base_txt
            levels["riesgo_caida"] = nivel

    texts["alcance"] = ("Lo útil de este panel son los rangos de retorno y el contexto de riesgo; "
                        "no predice el mercado ni indica qué comprar.")
    levels["alcance"] = "info"
    return texts, levels


def _fmt(x, dec):
    return f"{x:.{dec}f}".replace(".", ",") if x is not None else "s/d"


def _ticker_rows(fc: dict) -> list[dict]:
    rows = []
    for t in sorted((fc.get("tickers") or {})):
        d = fc["tickers"][t]
        p = d.get("p") or {}

        def pp(k, f):
            return _num(_get(p, k, f))

        r21, r63 = _get(d, "risk", 21), _get(d, "risk", 63)
        dd21, dd63 = (r21 or {}).get("dd") or {}, (r63 or {}).get("dd") or {}
        rows.append({
            "ticker": t,
            "price": _num(d.get("price")),
            "mom12_1": _num(d.get("mom12_1")),
            "r1m": _num(d.get("r1m")),
            "vol63": _num(d.get("vol63")),
            "dist_high": _num(d.get("dist_high")),
            "p5": pp("up5", "p"), "lo5": pp("up5", "lo"), "hi5": pp("up5", "hi"),
            "p21": pp("up21", "p"), "lo21": pp("up21", "lo"), "hi21": pp("up21", "hi"),
            "p63": pp("up63", "p"), "lo63": pp("up63", "lo"), "hi63": pp("up63", "hi"),
            "rel21": pp("rel21", "p"), "lo_rel21": pp("rel21", "lo"), "hi_rel21": pp("rel21", "hi"),
            "ret21": _trio(r21), "ret63": _trio(r63),
            "dd21_10": _num((r21 or {}).get("dd_cal")),
            "dd21_10_raw": _num(_get(dd21, "10")),
            "dd21_20": _num(_get(dd21, "20")),
            "dd63_10": _num((r63 or {}).get("dd_cal")),
            "dd63_10_raw": _num(_get(dd63, "10")),
            "dd63_20": _num(_get(dd63, "20")),
            "flags": [],
        })
    # flags: hechos relativos al universo
    dd_vals = [r["dd21_10"] for r in rows]
    thr_dd = _quantile(dd_vals, 0.9) if len([v for v in dd_vals if v is not None]) >= 10 else None
    med_vol = _median([r["vol63"] for r in rows])
    for r in rows:
        f = r["flags"]
        if thr_dd is not None and r["dd21_10"] is not None and r["dd21_10"] >= thr_dd:
            f.append("riesgo de caída 1m en el 10% superior del universo")
        if med_vol and r["vol63"] is not None and r["vol63"] > 2 * med_vol:
            f.append("volatilidad 63d > 2× la mediana del universo")
        if r["dist_high"] is not None and r["dist_high"] < -0.30:
            f.append("a >30% de su máximo de 52 semanas")
        if r["r1m"] is not None and r["r1m"] <= -0.20:
            f.append("cayó más de 20% en el último mes")
    return rows


def _macro_summary(macro):
    if not isinstance(macro, dict):
        return None
    out = {}
    for k, v in macro.items():
        v = _clean(v)
        if isinstance(v, dict):
            sub = {kk: vv for kk, vv in v.items() if isinstance(vv, (int, float, str)) and not isinstance(vv, bool)}
            if sub:
                out[k] = sub
        elif isinstance(v, (int, float, str)) and not isinstance(v, bool):
            out[k] = v
    return out or None


# ----------------------------------------------------------------------------- API
def _round_matrix(rows):
    """Matriz z ya redondeada por portfolio.py; aquí solo se asegura que no haya NaN/-0.0."""
    out = []
    for r in rows or []:
        out.append([(0.0 if (v is None or not math.isfinite(v)) else v + 0.0) for v in r])
    return out


def _portfolio_block(portfolio):
    """Salida de portfolio.build/joint_samples + sectores. Devuelve None si no hay muestras utilizables."""
    if not isinstance(portfolio, dict):
        return None
    out = {}
    for k, v in portfolio.items():
        if isinstance(v, dict) and k.startswith("h") and "z" in v and "tickers" in v:
            blk = dict(v)
            blk["z"] = _round_matrix(v["z"])
            out[k] = blk
        else:
            out[k] = v
    if not any(k.startswith("h") and isinstance(v, dict) for k, v in out.items()):
        return None
    if "sectors" not in out:
        from .portfolio import OTHER, sector_map
        sec = sector_map()
        names = sorted({t for v in out.values() if isinstance(v, dict) and "tickers" in v for t in v["tickers"]})
        out["sectors"] = {t: sec.get(t, OTHER) for t in names}
    return out


def build_dashboard(forecast_res: dict, lab_res: dict | None = None, ledger: dict | None = None,
                    alerts=None, macro: dict | None = None, report_meta: dict | None = None,
                    regime: dict | None = None, events: dict | None = None, fundamentals: dict | None = None,
                    portfolio: dict | None = None, convergence: dict | None = None,
                    ranking: dict | None = None) -> dict:
    fc = forecast_res or {}
    ev = _eval_block(fc)
    rv = _risk_validation(fc)
    texts, levels = _verdicts(ev, rv)
    tickers = _ticker_rows(fc)

    if isinstance(alerts, dict):
        alerts = alerts.get("alerts")
    generated = None
    if isinstance(report_meta, dict):
        generated = report_meta.get("generated")
    generated = generated or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    dash = {
        "generated": generated,
        "asof": fc.get("asof"),
        "universe": fc.get("n_stocks", len(tickers)),
        "verdicts": texts,
        "verdict_levels": levels,
        "eval": ev,
        "risk_validation": rv,
        "tickers": tickers,
        "alerts": list(alerts) if alerts else [],
        "lab": lab_res if lab_res else None,
        "ledger": ledger if ledger else None,
        "macro": _macro_summary(macro),
        "regime": regime if regime else None,
        "events": events if events else None,
        "fundamentals": fundamentals if fundamentals else None,
        "portfolio": _portfolio_block(portfolio),
        "convergence": convergence if convergence else None,
        "ranking": ranking if ranking else None,
        "disclaimer": DISCLAIMER,
        "caveats": list(CAVEATS),
    }
    return _clean(dash)


def write(dashboard: dict, path: str | Path = "docs/data/dashboard.json") -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(_clean(dashboard), ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    path.write_text(text, encoding="utf-8")
    return path
