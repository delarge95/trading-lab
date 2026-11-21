"""Ranking del universo por criterio, con el nivel de evidencia de cada criterio.

No es una recomendación: ordena las acciones según el criterio indicado y declara si ese criterio ha mostrado
ventaja estadística fuera de muestra en las pruebas del proyecto. "Favorable" significa "mejor perfil según el
criterio", no "va a rendir más".
"""
from __future__ import annotations

TOP_N = 10
EV_OK = "validado"
EV_NONE = "sin ventaja demostrada"
EV_UNTESTED = "no probado aquí"
MIN_SPREAD = {"pct": 0.02, "num": 0.05, "count": 1.0}   # dispersión mínima para considerar que el orden informa


def _g(d: dict | None, *keys):
    for k in keys:
        if not isinstance(d, dict):
            return None
        d = d.get(k, d.get(str(k)) if isinstance(k, int) else None)
    return d


def _risk21(t: dict) -> dict:
    r = t.get("risk") or {}
    return r.get(21) or r.get("21") or {}


def _pick(rows: list[dict], reverse: bool, n: int = TOP_N) -> list[dict]:
    rows = [r for r in rows if r["value"] is not None]
    rows.sort(key=lambda r: r["value"], reverse=reverse)
    return rows[:n]


def _criterion(key: str, label: str, direction: str, evidence: str, note: str, rows: list[dict],
               fmt: str = "pct") -> dict:
    """direction: 'alto' si un valor alto es más favorable; 'bajo' si uno bajo lo es."""
    vals = [r["value"] for r in rows if r["value"] is not None]
    spread = (max(vals) - min(vals)) if vals else 0.0
    degenerate = spread < MIN_SPREAD.get(fmt, 0.02)
    if degenerate:   # sin dispersión (p. ej. todas las probabilidades iguales a la tasa base): ordenar sería ruido
        fav, unf = [], []
        note = note + " Sin dispersión entre acciones: no se muestra un orden porque sería ruido."
    else:
        fav = _pick(rows, reverse=(direction == "alto"))
        unf = _pick(rows, reverse=(direction != "alto"))
    return {"key": key, "label": label, "direction": direction, "evidence": evidence, "note": note, "format": fmt,
            "favorable": fav, "desfavorable": unf, "n": len(vals), "degenerate": degenerate}


def build(forecast_res: dict, lab_res: dict | None = None, fundamentals: dict | None = None,
          convergence: dict | None = None, insiders: dict | None = None, managers_track: dict | None = None) -> dict:
    tickers = forecast_res.get("tickers") or {}
    ev = forecast_res.get("eval") or {}
    rv = forecast_res.get("risk_validation") or {}

    cov_ok = False
    v21 = rv.get("21") or rv.get(21)
    if v21 and v21.get("coverage80_ci"):
        lo, hi = v21["coverage80_ci"]
        cov_ok = lo <= 0.80 <= hi
    skill = v21.get("dd_skill") if v21 else None
    risk_ev = EV_OK if (cov_ok and skill is not None and skill > 0) else (EV_OK if cov_ok else EV_NONE)
    prob_ev = EV_OK if _g(ev, "up21", "has_edge") else EV_NONE
    rel_ev = EV_OK if _g(ev, "rel21", "has_edge") else EV_NONE

    mom_rule = _g(lab_res, "rules", "mom12_1") or {}
    mom_ev = EV_OK if (mom_rule.get("p_holm") is not None and mom_rule["p_holm"] < 0.05
                       and (mom_rule.get("diff_sharpe_vs_ew") or 0) > 0) else EV_NONE

    crit = []
    crit.append(_criterion(
        "riesgo_caida", "Menor riesgo de caída >10% a 1 mes", "bajo", risk_ev,
        "Probabilidad calibrada fuera de muestra; los rangos P10-P90 cubren ~78% de los casos reales.",
        [{"ticker": t, "value": _risk21(v).get("dd_cal", _g(_risk21(v), "dd", "10"))} for t, v in tickers.items()]))
    crit.append(_criterion(
        "volatilidad", "Menor volatilidad de 63 ruedas", "bajo", risk_ev,
        "La volatilidad es la parte persistente y predecible del riesgo.",
        [{"ticker": t, "value": v.get("vol63")} for t, v in tickers.items()]))
    crit.append(_criterion(
        "asimetria", "Mejor asimetría del rango a 1 mes (P90 / |P10|)", "alto", EV_UNTESTED,
        "Ancho relativo de la cola alcista frente a la bajista según la distribución histórica estandarizada; "
        "se valida la cobertura del intervalo P10-P90, no la proporción entre sus colas.",
        [{"ticker": t, "value": (_risk21(v)["p90"] / abs(_risk21(v)["p10"])
                                 if _risk21(v).get("p10") and _risk21(v)["p10"] < 0 and _risk21(v).get("p90") is not None
                                 else None)} for t, v in tickers.items()], fmt="num"))
    crit.append(_criterion(
        "prob_subida", "Mayor probabilidad calibrada de subir a 1 mes", "alto", prob_ev,
        "Si no hay ventaja estadística, todas las probabilidades se reducen a la tasa base.",
        [{"ticker": t, "value": _g(v, "p", "up21", "p")} for t, v in tickers.items()]))
    crit.append(_criterion(
        "momentum", "Mayor momentum 12-1", "alto", mom_ev,
        "Regla evaluada en el laboratorio frente al igual ponderado (Holm).",
        [{"ticker": t, "value": v.get("mom12_1")} for t, v in tickers.items()]))
    if fundamentals and fundamentals.get("tickers"):
        ft = fundamentals["tickers"]
        crit.append(_criterion(
            "margen", "Mayor margen operativo (TTM)", "alto", fundamentals.get("evidence", {}).get("op_margin_ttm", EV_UNTESTED),
            "Dato de la SEC (XBRL); la evidencia depende de la prueba de factores.",
            [{"ticker": t, "value": ft.get(t, {}).get("op_margin_ttm")} for t in tickers]))
        crit.append(_criterion(
            "crecimiento", "Mayor crecimiento de ingresos (interanual)", "alto",
            fundamentals.get("evidence", {}).get("rev_growth_yoy", EV_UNTESTED),
            "Dato de la SEC (XBRL); la evidencia depende de la prueba de factores.",
            [{"ticker": t, "value": ft.get(t, {}).get("rev_growth_yoy")} for t in tickers]))
    if convergence:
        crit.append(_criterion(
            "gestores", "Más gestores con la acción en su top 10 (13F)", "alto",
            EV_NONE if (managers_track and "Ningún" in str(managers_track.get("verdict", ""))) else EV_UNTESTED,
            "Replicar los 13F no ha superado a SPY con significancia; cuenta de gestores, no recomendación.",
            [{"ticker": t, "value": float(len((convergence.get(t) or {}).get("managers", [])))} for t in tickers],
            fmt="count"))
    if insiders:
        crit.append(_criterion(
            "insiders", "Compras oportunistas de insiders (90 días)", "alto", EV_UNTESTED,
            "Respaldo académico (Cohen, Malloy y Pomorski); no probado con este universo.",
            [{"ticker": t, "value": float((insiders.get(t) or {}).get("opportunistic", 0))} for t in insiders],
            fmt="count"))

    picks = (lab_res or {}).get("picks_now") or {}
    rules = []
    for name, lst in picks.items():
        r = _g(lab_res, "rules", name) or {}
        rules.append({"rule": name, "label": r.get("label", name), "tickers": lst,
                      "evidence": EV_OK if (r.get("p_holm") is not None and r["p_holm"] < 0.05
                                            and (r.get("diff_sharpe_vs_ew") or 0) > 0) else EV_NONE,
                      "annual_excess_vs_ew": r.get("annual_excess_vs_ew"), "p_holm": r.get("p_holm")})
    return {
        "asof": forecast_res.get("asof"),
        "criteria": crit, "rule_selections": rules,
        "summary": ("Ningún criterio de selección ha mostrado ventaja estadística fuera de muestra; lo validado es el "
                    "riesgo (rangos y caídas). Las listas ordenan por criterio y no son una recomendación."
                    if all(c["evidence"] != EV_OK or c["key"] in ("riesgo_caida", "volatilidad", "asimetria") for c in crit)
                    else "Algunos criterios muestran ventaja estadística fuera de muestra: ver el nivel de evidencia de cada lista."),
        "disclaimer": "Herramienta de investigación, no asesoría financiera.",
    }
