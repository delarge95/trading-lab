"""Alertas del informe diario: cambios relevantes frente a la foto de ayer y hechos puntuales de insiders y 13F.

Solo describen hechos ("sube de X% a Y%"); no son recomendaciones de compra ni de venta.
Esquema de salida: ver docs/contratos-datos.md, sección 3.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import date, datetime

# ------------------------------------------------------------------ umbrales
DD_SHIFT_MEDIA = 0.10        # sube >= 10 puntos la prob. de caída >10% a 21 ruedas -> "media"
DD_SHIFT_ALTA = 0.15         # >= 15 puntos -> "alta"
PROB_SHIFT = 0.10            # |cambio de P(sube a 21 ruedas)| >= 10 puntos -> "media"
VIX_ALTA = 30.0              # VIX >= 30 -> "alta"
VIX_CRUCE = 25.0             # cruce al alza de 25 vs el snapshot previo -> "media"
INSIDER_MIN_OPP_ALTA = 2     # >= 2 compras oportunistas -> "alta"
INSIDER_VALUE_MEDIA = 250_000.0   # 1 compra oportunista con valor >= $250,000 -> "media"
NEW_13F_ALTA = 2             # ticker nuevo en el top de >= 2 gestores (mismo trimestre) -> "alta"
CONVERGENCE_MIN = 3          # ticker en el top de >= 3 gestores -> "info"
STALE_DAYS = 4               # datos del motor con más de 4 días de antigüedad -> "alta"
TOP_RISK_N = 3               # cuántos tickers entran en la alerta agregada de riesgo
_EPS = 1e-9                  # tolerancia de punto flotante para comparar contra umbrales

_SEV_RANK = {"alta": 0, "media": 1, "info": 2}


# ------------------------------------------------------------------ utilidades
def _pct(x: float, d: int = 1) -> str:
    """Porcentaje con hasta `d` decimales, sin ceros sobrantes (12.0 -> '12%', 12.5 -> '12.5%')."""
    s = f"{x * 100:.{d}f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return f"{s}%"


def _pp(x: float) -> str:
    """Diferencia en puntos porcentuales."""
    s = f"{abs(x) * 100:.1f}".rstrip("0").rstrip(".")
    return f"{s} puntos"


def _money(x: float) -> str:
    return f"${x:,.0f}"


def _num(x) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v else None   # descarta NaN


def _ge(value: float, threshold: float) -> bool:
    return value >= threshold - _EPS


def _risk_at(risk: dict | None, h: int) -> dict | None:
    """Bloque de riesgo del horizonte `h`; acepta claves int o str (tras serializar a JSON)."""
    if not isinstance(risk, dict):
        return None
    blk = risk.get(h)
    if blk is None:
        blk = risk.get(str(h))
    return blk if isinstance(blk, dict) else None


def _dd21(risk: dict | None) -> float | None:
    """P(caída >10% a 21 ruedas): dd_cal si existe; si no, la cruda dd['10']."""
    blk = _risk_at(risk, 21)
    if not blk:
        return None
    v = _num(blk.get("dd_cal"))
    if v is not None:
        return v
    dd = blk.get("dd")
    if isinstance(dd, dict):
        return _num(dd.get("10", dd.get(10)))
    return None


def _p21(tk: dict) -> float | None:
    p = tk.get("p") if isinstance(tk, dict) else None
    blk = p.get("up21") if isinstance(p, dict) else None
    return _num(blk.get("p")) if isinstance(blk, dict) else None


def _vix(macro: dict | None) -> float | None:
    blk = macro.get("VIXCLS") if isinstance(macro, dict) else None
    return _num(blk.get("value")) if isinstance(blk, dict) else None


def _parse_date(s) -> date | None:
    try:
        return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------ snapshot
def snapshot(forecast_res: dict, macro: dict | None) -> dict:
    """Foto compacta del motor para compararla mañana. Omite tickers sin P(sube a 21 ruedas) o sin precio."""
    tickers = {}
    for t, tk in (forecast_res.get("tickers") or {}).items():
        p21, price = _p21(tk), _num(tk.get("price"))
        if p21 is None or price is None:
            continue
        tickers[t] = {"p21": p21, "dd21": _dd21(tk.get("risk")), "price": price}
    return {"asof": forecast_res.get("asof"), "vix": _vix(macro), "tickers": tickers}


def load_snapshot(path) -> dict | None:
    """Lee el snapshot; None si el archivo no existe, está corrupto o no tiene la forma esperada."""
    try:
        with open(path, encoding="utf-8") as f:
            snap = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(snap, dict) or not isinstance(snap.get("tickers"), dict):
        return None
    return snap


def save_snapshot(path, snap: dict) -> None:
    """Escritura atómica (archivo temporal + reemplazo) para no dejar un JSON a medias."""
    path = os.fspath(path)
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(snap, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ------------------------------------------------------------------ 13F
def _positions(managers: list[dict] | None, cusip_map: dict | None):
    """Genera (clave, nombre del emisor, gestor, fila) por cada posición del top de cada gestor."""
    cusip_map = cusip_map or {}
    for m in managers or []:
        if not isinstance(m, dict) or m.get("error"):
            continue
        for row in m.get("top") or []:
            name = str(row.get("name") or "").strip()
            tk = cusip_map.get(row.get("cusip"))
            key = str(tk) if tk else f"~{name}"
            if key == "~":      # sin ticker ni nombre: no hay forma de identificar al emisor
                continue
            yield key, name, m, row


def convergence_13f(managers: list[dict], cusip_map: dict) -> dict[str, dict]:
    """Por ticker (o '~NOMBRE' si el CUSIP no tiene ticker): gestores que lo tienen en su top.

    `new_by` solo incluye gestores con la posición NUEVA y datos no vencidos (`stale` falso).
    `avg_weight` es el peso medio entre los gestores que lo tienen (suma por gestor si repite el emisor).
    """
    weights: dict[str, dict[str, float]] = {}
    new_by: dict[str, list[str]] = {}
    for key, _name, m, row in _positions(managers, cusip_map):
        mname = m.get("name", "?")
        w = _num(row.get("weight")) or 0.0
        weights.setdefault(key, {})
        weights[key][mname] = weights[key].get(mname, 0.0) + w
        if row.get("change") == "NUEVA" and not m.get("stale"):
            nb = new_by.setdefault(key, [])
            if mname not in nb:
                nb.append(mname)
    return {k: {"managers": list(ws), "new_by": new_by.get(k, []), "avg_weight": sum(ws.values()) / len(ws)}
            for k, ws in weights.items()}


def _new_by_quarter(managers: list[dict] | None, cusip_map: dict | None) -> dict[str, dict[str, list[str]]]:
    """key -> {periodo: [gestores con la posición NUEVA y datos vigentes]}."""
    out: dict[str, dict[str, list[str]]] = {}
    for key, _name, m, row in _positions(managers, cusip_map):
        if row.get("change") != "NUEVA" or m.get("stale"):
            continue
        names = out.setdefault(key, {}).setdefault(str(m.get("period") or "?"), [])
        if m.get("name", "?") not in names:
            names.append(m.get("name", "?"))
    return out


# ------------------------------------------------------------------ alertas
def _alert(kind: str, severity: str, ticker: str | None, title: str, detail: str, today: str) -> dict:
    return {"id": f"{kind}:{ticker or '-'}:{today}", "severity": severity, "kind": kind,
            "ticker": ticker, "title": title, "detail": detail}


def _join(names: list[str]) -> str:
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " y " + names[-1]


def _issuer_label(key: str, names: dict[str, str]) -> str:
    return names.get(key) or key.lstrip("~")


def build(current: dict, previous: dict | None, macro: dict | None, insiders: dict | None,
          managers: list | None, cusip_map: dict | None, today: str | None = None) -> dict:
    today = today or date.today().isoformat()
    out: list[dict] = []
    tickers = current.get("tickers") or {}
    prev_t = (previous or {}).get("tickers") or {}

    # (1) dd_shift y (2) prob_shift: solo con snapshot previo
    if previous:
        for t in sorted(tickers):
            tk, pv = tickers[t], prev_t.get(t)
            if not isinstance(pv, dict):
                continue
            dd_now, dd_prev = _dd21(tk.get("risk")), _num(pv.get("dd21"))
            if dd_now is not None and dd_prev is not None:
                delta = dd_now - dd_prev
                if _ge(delta, DD_SHIFT_MEDIA):
                    sev = "alta" if _ge(delta, DD_SHIFT_ALTA) else "media"
                    out.append(_alert(
                        "dd_shift", sev, t,
                        f"{t}: riesgo de caída >10% a 21 ruedas sube de {_pct(dd_prev)} a {_pct(dd_now)}",
                        f"La probabilidad estimada de una caída mayor a 10% en 21 ruedas pasó de {_pct(dd_prev)} a "
                        f"{_pct(dd_now)} (+{_pp(delta)}) respecto a la foto anterior"
                        f"{' (' + str(previous.get('asof')) + ')' if previous.get('asof') else ''}. "
                        f"Es una estimación calibrada fuera de muestra, no un pronóstico.", today))
            p_now, p_prev = _p21(tk), _num(pv.get("p21"))
            if p_now is not None and p_prev is not None and _ge(abs(p_now - p_prev), PROB_SHIFT):
                verbo = "sube" if p_now > p_prev else "baja"
                out.append(_alert(
                    "prob_shift", "media", t,
                    f"{t}: P(sube a 21 ruedas) {verbo} de {_pct(p_prev)} a {_pct(p_now)}",
                    f"La probabilidad estimada de que {t} suba en 21 ruedas cambió {_pp(p_now - p_prev)} "
                    f"({_pct(p_prev)} a {_pct(p_now)}). El motor no ha demostrado ventaja estadística en esta "
                    f"probabilidad: tomar la tasa base como referencia.", today))

    # (3) vix
    vix, vix_prev = _vix(macro), _num((previous or {}).get("vix")) if previous else None
    if vix is not None:
        if _ge(vix, VIX_ALTA):
            cruce = (f" Venía de {vix_prev:.1f} en la foto anterior." if vix_prev is not None else "")
            out.append(_alert("vix", "alta", None, f"VIX en {vix:.1f}, en o sobre {VIX_ALTA:.0f}",
                              f"El índice de volatilidad VIX cerró en {vix:.1f}, nivel de estrés alto "
                              f"(umbral {VIX_ALTA:.0f}).{cruce}", today))
        elif vix_prev is not None and vix_prev < VIX_CRUCE and _ge(vix, VIX_CRUCE):
            out.append(_alert("vix", "media", None, f"VIX cruza {VIX_CRUCE:.0f} al alza: de {vix_prev:.1f} a {vix:.1f}",
                              f"El VIX pasó de {vix_prev:.1f} a {vix:.1f}, por encima de {VIX_CRUCE:.0f}: "
                              f"mayor volatilidad esperada en el mercado.", today))

    # (4) insider_buy
    for t in sorted((insiders or {})):
        ins = insiders[t]
        if not isinstance(ins, dict) or ins.get("error"):
            continue
        n_opp = int(_num(ins.get("opportunistic")) or 0)
        v_opp = _num(ins.get("opportunistic_value")) or 0.0
        if n_opp >= INSIDER_MIN_OPP_ALTA:
            sev = "alta"
        elif n_opp == 1 and v_opp >= INSIDER_VALUE_MEDIA - _EPS:
            sev = "media"
        else:
            continue     # rutinarias y sin clasificar no generan alerta
        who = []
        for b in ins.get("buys") or []:
            if b.get("class") == "oportunista":
                label = str(b.get("owner") or "?") + (f" ({b['role']})" if b.get("role") else "")
                if label not in who:
                    who.append(label)
        quienes = f" Compradores: {_join(who)}." if who else ""
        win = ins.get("window_days")
        ventana = f" en los últimos {win} días" if win else ""
        plural = "compras oportunistas" if n_opp > 1 else "compra oportunista"
        out.append(_alert(
            "insider_buy", sev, t,
            f"{t}: {n_opp} {plural} de insiders por {_money(v_opp)}",
            f"Form 4{ventana}: {n_opp} {plural} (no rutinarias) por {_money(v_opp)} en total; "
            f"no cuentan las rutinarias ({int(_num(ins.get('routine')) or 0)}) ni las sin clasificar "
            f"({int(_num(ins.get('unclassified')) or 0)}).{quienes} Las compras oportunistas son la señal con respaldo "
            f"académico (Cohen, Malloy y Pomorski).", today))

    # (5) 13f_new y (6) 13f_convergence
    names: dict[str, str] = {}
    for key, name, _m, _r in _positions(managers, cusip_map):
        names.setdefault(key, name)
    for key, by_q in sorted(_new_by_quarter(managers, cusip_map).items()):
        period, gestores = max(by_q.items(), key=lambda kv: (len(kv[1]), kv[0]))
        n = len(gestores)
        label = _issuer_label(key, names)
        titulo_t = key if not key.startswith("~") else label
        out.append(_alert(
            "13f_new", "alta" if n >= NEW_13F_ALTA else "info", key,
            f"{titulo_t}: posición nueva en el top de {n} gestor{'es' if n > 1 else ''} (13F al {period})",
            f"{_join(gestores)} {'abrieron' if n > 1 else 'abrió'} {label} en su top 10 en el trimestre "
            f"al {period}. Los datos del 13F tienen hasta ~45 días de retraso.", today))
    for key, c in sorted(convergence_13f(managers or [], cusip_map or {}).items()):
        n = len(c["managers"])
        if n >= CONVERGENCE_MIN:
            label = _issuer_label(key, names)
            titulo_t = key if not key.startswith("~") else label
            out.append(_alert(
                "13f_convergence", "info", key,
                f"{titulo_t}: en el top de {n} gestores",
                f"{label} aparece en el top 10 de {_join(c['managers'])} (peso medio {_pct(c['avg_weight'])}).",
                today))

    # (7) stale_data
    asof = _parse_date(current.get("asof"))
    td = _parse_date(today)
    if asof and td and (td - asof).days > STALE_DAYS:
        days = (td - asof).days
        out.append(_alert("stale_data", "alta", None,
                          f"Datos del motor desactualizados: {days} días de antigüedad",
                          f"Los precios del motor son del {asof.isoformat()} y hoy es {today} ({days} días; "
                          f"umbral {STALE_DAYS}). Las cifras del informe pueden no reflejar el mercado actual.", today))

    # (8) top_risk
    ranked = sorted(((v, t) for t, tk in tickers.items() if (v := _dd21(tk.get("risk"))) is not None),
                    key=lambda x: (-x[0], x[1]))[:TOP_RISK_N]
    if ranked:
        partes = []
        for v, t in ranked:
            p21 = _p21(tickers[t])
            partes.append(f"{t} {_pct(v)}" + (f" (P(sube) {_pct(p21)})" if p21 is not None else ""))
        out.append(_alert(
            "top_risk", "info", None,
            "Mayor riesgo de caída >10% a 21 ruedas: " + ", ".join(t for _v, t in ranked),
            "Probabilidad calibrada de caída mayor a 10% a 21 ruedas (y P(sube) a 21 ruedas entre paréntesis): "
            + "; ".join(partes) + ".", today))

    # sin duplicados (conserva la de mayor severidad), orden por severidad y ticker
    best: dict[str, dict] = {}
    for a in out:
        cur = best.get(a["id"])
        if cur is None or _SEV_RANK[a["severity"]] < _SEV_RANK[cur["severity"]]:
            best[a["id"]] = a
    alerts = sorted(best.values(), key=lambda a: (_SEV_RANK[a["severity"]], a["ticker"] or "", a["kind"]))
    counts = {s: sum(1 for a in alerts if a["severity"] == s) for s in _SEV_RANK}
    return {"generated": today, "alerts": alerts, "counts": counts}


# ------------------------------------------------------------------ push
def push_text(alerts_dict: dict, max_len: int = 180) -> str | None:
    """Texto corto para notificación push con las alertas "alta"; None si no hay. Nunca excede `max_len`."""
    altas = [a for a in (alerts_dict or {}).get("alerts", []) if a.get("severity") == "alta"]
    if not altas:
        return None
    n = len(altas)
    head = f"Trading Lab: {n} alerta{'s' if n > 1 else ''} alta{'s' if n > 1 else ''}. "
    text = head + "; ".join(a["title"] for a in altas)
    return _truncate(text, max_len)


def _truncate(text: str, max_len: int) -> str:
    if max_len <= 0:
        return ""
    if len(text) <= max_len:
        return text
    if max_len == 1:
        return "…"
    cut = text[: max_len - 1]
    if not text[max_len - 1].isspace():          # se cortaría a mitad de palabra: retroceder al último espacio
        sp = cut.rfind(" ")
        if sp > 0:
            cut = cut[:sp]
    cut = cut.rstrip(" ;,.:-—")
    return (cut or text[: max_len - 1]) + "…"
