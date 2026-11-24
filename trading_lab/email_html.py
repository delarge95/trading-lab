"""Correo de una pantalla: HTML con estilos en línea (compatible con Gmail/Outlook), lenguaje llano y determinista.

Se genera igual cada día a partir de reports/latest.json; la rutina de Claude solo rellena dos huecos con datos de
mercado en vivo (`<!--AVISO-->` y `<!--MERCADO_AYER-->`) y envía el resultado. Son hechos y probabilidades,
no recomendaciones de compra o venta.
"""
from __future__ import annotations

from datetime import date as _date
from html import escape as _e

DASHBOARD_URL = "https://delarge95.github.io/trading-lab/"
DISCLAIMER = "Herramienta de investigación, no asesoría financiera."

# Tokens de color (todo con fondo explícito para que el modo oscuro automático de los clientes no rompa el contraste)
INK, MUTED, LINE, BG, CARD = "#1b2330", "#5b6677", "#e3e7ee", "#f2f4f8", "#ffffff"
STATE = {
    "rojo": {"fg": "#a31616", "bg": "#fdecea", "dot": "#d32f2f", "name": "ROJO", "mood": "Estrés alto"},
    "amarillo": {"fg": "#7a5a00", "bg": "#fff5d1", "dot": "#e0a800", "name": "AMARILLO", "mood": "Estrés moderado"},
    "verde": {"fg": "#175c33", "bg": "#e4f4ea", "dot": "#2e9e5b", "name": "VERDE", "mood": "Calma relativa"},
}
FONT = "-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
DIAS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]

_RULE_LABEL = {
    "vol_ewma_ann": ("Volatilidad reciente", lambda v: f"{v * 100:.0f}%"),
    "vix": ("VIX (índice del miedo)", lambda v: f"{v:.1f}"),
    "drawdown_52w": ("Caída desde el máximo del año", lambda v: f"{v * 100:.1f}%".replace("-", "−")),
    "sma200_gap": ("Precio vs. su media de 200 días", lambda v: f"{v * 100:+.1f}%".replace("-", "−")),
    "hy_spread": ("Prima de riesgo de crédito", lambda v: f"{v:.1f} pp"),
}


def _d(s: str | None) -> _date | None:
    try:
        return _date.fromisoformat(str(s)[:10])
    except (TypeError, ValueError):
        return None


def fecha_corta(s: str | None) -> str:
    d = _d(s)
    return f"{DIAS[d.weekday()]} {d.day} {MESES[d.month - 1]}" if d else "fecha n/d"


def _pct(v, dec=0, sign=False) -> str:
    if v is None:
        return "n/d"
    t = f"{v * 100:+.{dec}f}%" if sign else f"{v * 100:.{dec}f}%"
    return t.replace("-", "−")


def _p(text: str, size=14, color=INK, bold=False, mb=0) -> str:
    return (f'<p style="margin:0 0 {mb}px 0;font:{"700" if bold else "400"} {size}px/1.5 {FONT};color:{color};">{text}</p>')


def _h(text: str) -> str:
    return (f'<p style="margin:0 0 10px 0;font:700 12px/1.2 {FONT};letter-spacing:.08em;text-transform:uppercase;'
            f'color:{MUTED};">{_e(text)}</p>')


def _card(inner: str, pad="18px 20px", extra="") -> str:
    return (f'<tr><td style="padding:0 0 12px 0;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'style="background:{CARD};border:1px solid {LINE};border-radius:10px;{extra}"><tr><td style="padding:{pad};">'
            f'{inner}</td></tr></table></td></tr>')


def _chip(text: str, state: str) -> str:
    s = STATE[state]
    return (f'<span style="display:inline-block;padding:2px 8px;border-radius:999px;background:{s["bg"]};color:{s["fg"]};'
            f'font:700 11px/1.5 {FONT};">{_e(text)}</span>')


# ---------------------------------------------------------------- bloques
def _hero(res: dict, rg: dict | None) -> str:
    asof = (res.get("engine") or {}).get("asof")
    when = f"Datos al cierre del {fecha_corta(asof)}" if asof else "Fecha de datos n/d"
    if not rg or not rg.get("state") or rg["state"] not in STATE:
        inner = (_p("Trading Lab · informe diario", 12, MUTED, True, 4) + _p("Semáforo de mercado no disponible hoy", 22, INK, True, 6)
                 + _p(_e(when), 13, MUTED))
        return _card(inner)
    s = STATE[rg["state"]]
    score, mx = rg.get("score"), rg.get("max_score", 10)
    hist = (rg.get("history") or {}).get("by_state") or {}
    cur, ver = hist.get(rg["state"]) or {}, hist.get("verde") or {}
    line = ""
    if cur.get("prob_drop5") is not None and rg["state"] != "verde":
        line = (f"Cuando el semáforo estuvo así en el pasado, el mercado cayó más de 5% en el mes siguiente "
                f"<b>{_pct(cur['prob_drop5'])}</b> de las veces (en verde: {_pct(ver.get('prob_drop5'))}). "
                f"<span style=\"color:{MUTED};\">Pocas observaciones independientes (≈{cur.get('n_eff', 0):.0f}): tómalo como contexto.</span>")
    inner = (
        _p(f"Trading Lab · {_e(fecha_corta(res.get('date')))}", 12, MUTED, True, 8)
        + f'<table role="presentation" cellpadding="0" cellspacing="0" width="100%"><tr>'
          f'<td width="64" valign="top"><div style="width:52px;height:52px;border-radius:26px;background:{s["dot"]};"></div></td>'
          f'<td valign="middle"><p style="margin:0;font:800 24px/1.15 {FONT};color:{s["fg"]};">{s["mood"]}</p>'
          f'<p style="margin:2px 0 0 0;font:600 14px/1.4 {FONT};color:{INK};">Semáforo {s["name"]} · {score}/{mx} puntos de estrés</p>'
          f'</td></tr></table>'
        + (f'<div style="margin-top:12px;">{_p(line, 14, INK)}</div>' if line else "")
        + f'<div style="margin-top:8px;">{_p(_e(when), 12, MUTED)}</div>')
    return _card(inner, extra=f"border-left:6px solid {s['dot']};")


def _regime_rows(rg: dict | None) -> str:
    if not rg or not rg.get("rules"):
        return ""
    rows = []
    for r in rg["rules"]:
        st = r.get("state")
        lab, fmt = _RULE_LABEL.get(r.get("name"), (r.get("label") or r.get("name") or "", lambda v: f"{v}"))
        try:
            val = fmt(r["value"]) if r.get("value") is not None else "n/d"
        except (TypeError, ValueError):
            val = "n/d"
        rows.append(
            f'<tr><td style="padding:6px 0;border-top:1px solid {LINE};font:400 14px/1.3 {FONT};color:{INK};">{_e(lab)}</td>'
            f'<td align="right" style="padding:6px 8px;border-top:1px solid {LINE};font:600 14px/1.3 {FONT};color:{INK};">{_e(val)}</td>'
            f'<td align="right" width="86" style="padding:6px 0;border-top:1px solid {LINE};">{_chip(STATE[st]["name"], st) if st in STATE else ""}</td></tr>')
    return (_h("Qué mide el semáforo") + f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{"".join(rows)}</table>'
            + _p("Cada indicador suma 0 (verde), 1 (amarillo) o 2 (rojo) puntos de estrés; reglas fijadas de antemano.", 12, MUTED))


def _changes(eng: dict) -> str:
    al = (eng.get("alerts") or {}).get("alerts") or []
    order = {"alta": 0, "media": 1, "info": 2}
    shown = sorted([a for a in al if a.get("kind") != "top_risk"], key=lambda a: order.get(a.get("severity"), 3))
    key = [a for a in shown if a.get("severity") in ("alta", "media")]
    rest = [a for a in shown if a.get("severity") not in ("alta", "media")]
    pick = key + rest[: max(0, 3 - len(key))]
    if not pick:
        return _card(_h("Qué cambió") + _p("Sin alertas nuevas.", 14, MUTED))
    sev = {"alta": ("rojo", "ALTA"), "media": ("amarillo", "MEDIA"), "info": ("verde", "INFO")}
    items = []
    for a in pick:
        st, name = sev.get(a.get("severity"), ("verde", "INFO"))
        chip = _chip(name, st) if a.get("severity") != "info" else (
            f'<span style="display:inline-block;padding:2px 8px;border-radius:999px;background:#eceff4;color:{MUTED};font:700 11px/1.5 {FONT};">INFO</span>')
        items.append(f'<tr><td width="62" valign="top" style="padding:7px 0;">{chip}</td>'
                     f'<td style="padding:7px 0;font:400 14px/1.45 {FONT};color:{INK};">{_e(a.get("title", ""))}</td></tr>')
    more = len(al) - len(pick)
    foot = _p(f"+{more} alertas más (riesgo, gestores, insiders) en el panel.", 12, MUTED) if more > 0 else ""
    return _card(_h("Qué cambió") + f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{"".join(items)}</table>' + foot)


def _risk(eng: dict) -> str:
    rt = (eng.get("risk_table") or [])[:5]
    calm = []
    for c in (eng.get("ranking") or {}).get("criteria") or []:
        if c.get("key") == "riesgo_caida":
            calm = c.get("favorable", [])[:5]
    if not rt:
        return ""
    top = max([r["dd21"] for r in rt] + [0.01])
    rows = []
    for r in rt:
        w = max(4, int(round(r["dd21"] / max(top, 0.01) * 100)))
        rows.append(
            f'<tr><td width="52" style="padding:7px 0;font:700 14px/1.2 {FONT};color:{INK};">{_e(r["ticker"])}</td>'
            f'<td style="padding:7px 8px 7px 0;"><div style="background:#eceff4;border-radius:4px;height:10px;">'
            f'<div style="background:#d86a5a;border-radius:4px;height:10px;width:{w}%;"></div></div></td>'
            f'<td width="44" align="right" style="padding:7px 0;font:700 14px/1.2 {FONT};color:{INK};">{_pct(r["dd21"])}</td>'
            f'<td width="128" align="right" style="padding:7px 0 7px 8px;font:400 12px/1.3 {FONT};color:{MUTED};">'
            f'{_pct(r.get("p10"))} a {_pct(r.get("p90"), sign=True)}</td></tr>')
    head = (f'<tr><td></td><td style="font:600 11px/1.2 {FONT};color:{MUTED};padding-bottom:2px;">Probabilidad de caer más de 10% en un mes</td>'
            f'<td></td><td align="right" style="font:600 11px/1.2 {FONT};color:{MUTED};">Rango probable</td></tr>')
    calm_html = ""
    if calm:
        calm_html = (f'<div style="margin-top:12px;">{_p("<b>Perfil más tranquilo hoy:</b> " + " · ".join(f"{_e(x['ticker'])} {_pct(x['value'])}" for x in calm), 13, INK)}</div>')
    note = _p("Lee así: «35%» = en situaciones históricas parecidas, 35 de cada 100 veces cayó más de 10% en un mes. "
              "El rango cubre el 80% de los casos probables (peor 10% – mejor 10%).", 12, MUTED)
    return _card(_h("Dónde está el riesgo (S&P 100)") + f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{head}{"".join(rows)}</table>'
                 + calm_html + f'<div style="margin-top:10px;">{note}</div>')


def _evidence(eng: dict) -> str:
    ev = eng.get("eval") or {}
    edge = [k for k, v in ev.items() if isinstance(v, dict) and v.get("has_edge")]
    cov = ((eng.get("risk_validation") or {}).get("21") or {}).get("coverage80")
    can = (f"Medir el <b>riesgo</b>: los rangos de 1 mes acertaron en {_pct(cov)} de los casos reales (objetivo 80%)."
           if cov is not None else "Medir el <b>riesgo</b> y los rangos de retorno.")
    cannot = ("Ninguna señal para <b>elegir ganadoras</b> (momentum, fundamentales, gestores, probabilidad de subida) superó al azar fuera de muestra."
              if not edge else "Hay señales con ventaja estadística en algún horizonte; revisa el panel para ver cuáles y con qué intervalo.")

    def cell(title, text, mark, bg, fg):
        return (f'<td width="50%" valign="top" style="padding:12px;background:{bg};border-radius:8px;">'
                f'<p style="margin:0 0 4px 0;font:700 13px/1.3 {FONT};color:{fg};">{mark} {title}</p>'
                f'<p style="margin:0;font:400 13px/1.45 {FONT};color:{INK};">{text}</p></td>')

    two = (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
           f'{cell("Lo que sí se puede", can, "✔", "#e4f4ea", "#175c33")}<td width="10"></td>'
           f'{cell("Lo que los datos no permiten", cannot, "✖", "#fdecea", "#a31616")}</tr></table>')
    return _card(_h("Qué tanto confiar en los datos") + two)


def _events(eng: dict) -> str:
    evs = [e for e in (eng.get("events") or {}).get("events") or [] if 0 <= e.get("days_to", 99) <= 14]
    if not evs:
        return _card(_h("Próximos 14 días") + _p("Sin eventos de riesgo calendarizados.", 14, MUTED))
    rows = []
    for e in evs[:6]:
        if e.get("kind") == "earnings":
            txt = f'Resultados de <b>{_e(e.get("ticker") or "")}</b>' + (f' · {_e(e["time"])}' if e.get("time") else "")
        elif e.get("kind") == "fomc":
            txt = "<b>Reunión de la Fed</b> (decisión de tasas)"
        elif e.get("kind") == "opex":
            txt = "Vencimiento de opciones"
        else:
            txt = _e(e.get("label", ""))
        n = e.get("days_to", 0)
        cuando = "hoy" if n == 0 else ("mañana" if n == 1 else f"en {n} días")
        rows.append(f'<tr><td width="92" style="padding:6px 0;border-top:1px solid {LINE};font:600 13px/1.3 {FONT};color:{INK};">{_e(fecha_corta(e.get("date")))}</td>'
                    f'<td style="padding:6px 0;border-top:1px solid {LINE};font:400 14px/1.3 {FONT};color:{INK};">{txt}</td>'
                    f'<td align="right" style="padding:6px 0;border-top:1px solid {LINE};font:400 12px/1.3 {FONT};color:{MUTED};">{cuando}</td></tr>')
    return _card(_h("Próximos 14 días") + f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{"".join(rows)}</table>')


def _watch(res: dict, eng: dict) -> str:
    ins = res.get("insiders") or {}
    opp = sum((v or {}).get("opportunistic", 0) for v in ins.values())
    stale = [m["name"] for m in res.get("managers") or [] if m.get("stale")]
    rules = (eng.get("ledger") or {}).get("rules") or {}
    closed = max([r.get("closed", 0) for r in rules.values()] + [0])
    bits = [
        f"Compras <b>oportunistas</b> de insiders (90 días): <b>{opp}</b>" + (" — nada que destacar." if opp == 0 else "."),
        "Reglas de selección probadas: ninguna supera al promedio del universo con significancia.",
        f"Libro de picks simulado: {closed} de 12 períodos cerrados que hacen falta para concluir algo.",
    ]
    if stale:
        bits.append("13F desactualizado: " + ", ".join(_e(s) for s in stale) + ".")
    lis = "".join(f'<li style="margin:0 0 5px 0;font:400 13px/1.45 {FONT};color:{INK};">{b}</li>' for b in bits)
    return _card(_h("Otros indicadores") + f'<ul style="margin:0;padding-left:18px;">{lis}</ul>')


def _guide() -> str:
    """Cómo usar el correo: método para decidir con las propias reglas del lector; no dice qué activos elegir."""
    steps = [
        ("Mira el semáforo", "Rojo significa que el mercado se está moviendo más de lo normal. No dice si va a subir o a bajar: "
                             "dice cuánto puede moverse."),
        ("Revisa tu riesgo, no el ranking", "Para cada acción que tengas o te interese: si cae 10%, ¿puedes aceptarlo con el "
                                           "monto que le asignas? Si no, lo que se ajusta es el monto, no la elección."),
        ("No uses las listas para buscar ganadoras", "Ordenan por criterio, pero ninguno superó al azar. Sirven para ver "
                                                     "qué tienen en común tus posiciones y no concentrar el riesgo."),
        ("Decide con reglas escritas antes", "Define en el Diario tus límites (monto máximo por acción, pérdida que toleras) "
                                              "y la lista de chequeo te avisa cuando una decisión los rompe."),
    ]
    rows = []
    for i, (t, d) in enumerate(steps, 1):
        top = f"border-top:1px solid {LINE};" if i > 1 else ""
        rows.append(
            f'<tr><td width="40" valign="top" style="padding:10px 0;{top}"><div style="width:26px;height:26px;border-radius:13px;'
            f'background:{INK};color:#ffffff;font:700 13px/26px {FONT};text-align:center;">{i}</div></td>'
            f'<td valign="top" style="padding:10px 0;{top}"><p style="margin:0 0 2px 0;font:700 14px/1.35 {FONT};color:{INK};">{_e(t)}</p>'
            f'<p style="margin:0;font:400 13px/1.5 {FONT};color:{MUTED};">{_e(d)}</p></td></tr>')
    note = _p("Qué activos mantener o evitar es decisión tuya. Este sistema mide riesgo y probabilidades; con los datos actuales "
              "la única palanca respaldada es <b>cuánto riesgo asumes</b>, no <b>qué acción eliges</b>.", 13, INK)
    return _card(_h("Cómo usar este correo") + f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{"".join(rows)}</table>'
                 + f'<div style="margin-top:6px;padding:10px 12px;background:#eef2f8;border-radius:8px;">{note}</div>')


def _link_rows() -> str:
    """Mismo formato que «Próximos 14 días»: etiqueta en negrita | descripción en gris | acción a la derecha."""
    items = [("Panel completo", "Todas las listas, rangos y alertas", DASHBOARD_URL),
             ("Mi cartera", "Tus posiciones frente a tus límites de riesgo", DASHBOARD_URL + "cartera.html"),
             ("Diario", "Por qué decides y tu lista de chequeo", DASHBOARD_URL + "diario.html")]
    rows = []
    for t, d, u in items:
        href = _e(u, quote=True)
        link = f'color:{INK};text-decoration:underline;'
        rows.append(
            f'<tr><td width="112" style="padding:6px 0;border-top:1px solid {LINE};font:600 13px/1.3 {FONT};color:{INK};">'
            f'<a href="{href}" style="{link}">{_e(t)}</a></td>'
            f'<td style="padding:6px 0;border-top:1px solid {LINE};font:400 14px/1.3 {FONT};color:{INK};">{_e(d)}</td>'
            f'<td align="right" style="padding:6px 0;border-top:1px solid {LINE};font:400 12px/1.3 {FONT};color:{MUTED};">'
            f'<a href="{href}" style="color:{MUTED};text-decoration:underline;">abrir</a></td></tr>')
    return _card(_h("Seguir explorando") + f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{"".join(rows)}</table>')


def _glossary() -> str:
    terms = [("Volatilidad", "cuánto se mueve el precio de un día a otro."),
             ("VIX", "el miedo que espera el mercado para los próximos 30 días."),
             ("Rango probable", "entre qué valores quedó el 80% de los casos históricos parecidos."),
             ("Validado", "se comprobó con datos que el modelo no había visto."),
             ("Sin ventaja", "no superó al azar en esa comprobación."),
             ("No probado", "aún no se ha puesto a prueba aquí.")]
    rows = "".join(
        f'<tr><td width="112" valign="top" style="padding:5px 0;font:700 13px/1.4 {FONT};color:{INK};">{_e(a)}</td>'
        f'<td valign="top" style="padding:5px 0;font:400 13px/1.4 {FONT};color:{MUTED};">{_e(b)}</td></tr>' for a, b in terms)
    return _card(_h("Glosario") + f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{rows}</table>', pad="16px 20px 10px 20px")


def _footer(res: dict) -> str:
    return (_guide() + _link_rows() + _glossary()
            + f'<tr><td align="center" style="padding:6px 16px 4px 16px;">{_p(_e(DISCLAIMER), 12, MUTED, True, 2)}'
              f'{_p("Resultados pasados no garantizan resultados futuros.", 12, MUTED)}</td></tr>')


# ---------------------------------------------------------------- ensamblado
def subject(res: dict) -> str:
    rg = ((res.get("engine") or {}).get("regime")) or {}
    st = STATE.get(rg.get("state"))
    emoji = {"rojo": "🔴", "amarillo": "🟡", "verde": "🟢"}.get(rg.get("state"), "⚪")
    tail = f"{emoji} {st['mood']} ({rg.get('score')}/{rg.get('max_score', 10)})" if st else "informe diario"
    return f"Trading Lab · {fecha_corta(res.get('date'))} · {tail}"


def render(res: dict) -> str:
    eng = res.get("engine") or {}
    rg = eng.get("regime") if isinstance(eng.get("regime"), dict) else None
    body = "".join([
        "<!--AVISO-->",
        _hero(res, rg),
        _card(_regime_rows(rg), pad="14px 20px 12px 20px") if _regime_rows(rg) else "",
        _changes(eng) if eng else "",
        _risk(eng) if eng else "",
        _card(_h("Mercado ayer") + "<!--MERCADO_AYER-->", pad="16px 20px"),
        _events(eng) if eng else "",
        _evidence(eng) if eng else "",
        _watch(res, eng) if eng else "",
        _footer(res),
    ])
    return (
        '<!doctype html><html lang="es"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="color-scheme" content="light"><meta name="supported-color-schemes" content="light">'
        f'<title>{_e(subject(res))}</title><style>a{{color:{INK};}}</style></head>'
        f'<body style="margin:0;padding:0;background:{BG};">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{BG};"><tr><td align="center" style="padding:16px 10px;">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;">{body}</table>'
        f'</td></tr></table></body></html>')
