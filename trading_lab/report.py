"""Generación del informe en Markdown a partir de los resultados del pipeline."""
from __future__ import annotations

DISCLAIMER = "Herramienta de investigación, no asesoría financiera."


def _pct(x, d=1):
    return "n/d" if x is None else f"{x * 100:.{d}f}%"


def _usd(x):
    if x is None:
        return "n/d"
    for unit, div in (("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if abs(x) >= div:
            return f"${x / div:.1f}{unit}"
    return f"${x:,.0f}"


DASHBOARD_URL = "https://delarge95.github.io/trading-lab/"
_TARGETS = {"up5": "Sube en 1 semana", "up21": "Sube en 1 mes", "up63": "Sube en 3 meses", "rel21": "Supera a SPY en 1 mes"}


_STATE_EMOJI = {"verde": "🟢", "amarillo": "🟡", "rojo": "🔴"}


def _one_screen(eng: dict) -> list[str]:
    """Resumen de una pantalla: régimen, eventos próximos, alertas y cómo leer el resto (hechos, no recomendaciones)."""
    L = ["## Hoy en una pantalla", ""]
    rg = eng.get("regime")
    if rg and rg.get("state"):
        why = "; ".join(f"{r['label'] if 'label' in r else r['name']}: {r['state']}" for r in rg.get("rules", [])[:5])
        L.append(f"- **Régimen de mercado:** {_STATE_EMOJI.get(rg['state'], '')} **{rg['state']}** "
                 f"(puntaje {rg.get('score', '?')}/{rg.get('max_score', 10)}). {why}.")
        vm = (rg.get("history") or {}).get("vol_managed") or {}
        if vm.get("verdict"):
            L.append(f"  - Prueba histórica de la regla de exposición: {vm['verdict']}")
    ev = (eng.get("events") or {}).get("events") or []
    soon = [e for e in ev if 0 <= e.get("days_to", 99) <= 7]
    if soon:
        L.append("- **Eventos de riesgo en los próximos 7 días:** " + "; ".join(
            f"{e['label']} ({e['date']}{', ' + e['ticker'] if e.get('ticker') else ''})" for e in soon[:8]) + ".")
    al = (eng.get("alerts") or {}).get("counts") or {}
    if al:
        L.append(f"- **Alertas:** {al.get('alta', 0)} altas, {al.get('media', 0)} medias, {al.get('info', 0)} informativas.")
    rk = eng.get("ranking")
    if rk and rk.get("summary"):
        L.append(f"- **Qué dicen los datos:** {rk['summary']}")
    L += ["- **Cartera y diario:** en el panel puedes cargar tu cartera y tus reglas de riesgo y ver cuáles posiciones las "
          f"exceden, y llevar el diario de decisiones: {DASHBOARD_URL}", ""]
    return L


def _ranking_section(rk: dict | None) -> list[str]:
    if not rk or not rk.get("criteria"):
        return []
    L = ["### Ranking por criterio (perfil estadístico; no es una recomendación)", "", rk.get("summary", ""), ""]
    for c in rk["criteria"]:
        fm = {"pct": lambda v: f"{v * 100:.1f}%", "num": lambda v: f"{v:.2f}", "count": lambda v: f"{v:.0f}"}[c.get("format", "pct")]
        L.append(f"**{c['label']}** — evidencia: _{c['evidence']}_")
        if c.get("degenerate"):
            L += [f"  - {c['note']}", ""]
            continue
        fav = ", ".join(f"{x['ticker']} ({fm(x['value'])})" for x in c["favorable"][:5])
        unf = ", ".join(f"{x['ticker']} ({fm(x['value'])})" for x in c["desfavorable"][:5])
        L += [f"  - Mejor perfil según este criterio: {fav}", f"  - Peor perfil según este criterio: {unf}", ""]
    sel = rk.get("rule_selections") or []
    if sel:
        L += ["**Selecciones de las reglas hoy** (con su historial frente al igual ponderado):", ""]
        for s in sel:
            ex = "" if s.get("annual_excess_vs_ew") is None else f", exceso anual histórico {s['annual_excess_vs_ew'] * 100:+.1f}%"
            L.append(f"- {s['label']} [{s['evidence']}{ex}]: {', '.join(s['tickers'])}")
        L.append("")
    return L


def _engine_section(eng: dict) -> list[str]:
    """Sección del motor v2 a partir de res['engine'] (ver docs/contratos-datos.md)."""
    L = _one_screen(eng)
    L += ["## Predicciones por probabilidad (S&P 100)", "",
          f"Panel interactivo: {DASHBOARD_URL} · {eng.get('n_stocks', '?')} acciones · datos al {eng.get('asof', '?')}.", ""]
    ev = eng.get("eval") or {}
    if ev:
        L += ["### ¿Hay ventaja estadística? (validación fuera de muestra, walk-forward con purga)", "",
              "| Objetivo | Tasa base | Brier skill [IC95%] | AUC | IC de rango [IC95%] | Veredicto |", "|---|---|---|---|---|---|"]
        for k, e in ev.items():
            L.append(f"| {_TARGETS.get(k, k)} | {_pct(e['base_rate'], 0)} | {e['bss'] * 100:+.2f}% "
                     f"[{e['bss_ci'][0] * 100:+.2f}, {e['bss_ci'][1] * 100:+.2f}] | {e['auc']:.3f} | "
                     f"{e['ic']:+.3f} [{e['ic_ci'][0]:+.3f}, {e['ic_ci'][1]:+.3f}] | {e['verdict']} |")
        L += ["", "_Brier skill > 0 con IC que excluye 0 = el modelo supera a la tasa base. Si no, la probabilidad "
              "calibrada se reduce a la tasa base (que además está inflada por sesgo de supervivencia: el universo son los "
              "miembros actuales del índice)._", ""]
    rv = eng.get("risk_validation") or {}
    if rv:
        parts = []
        for h, v in rv.items():
            parts.append(f"{h} ruedas: el rango P10–P90 cubrió {v['coverage80'] * 100:.1f}% de los casos reales "
                         f"(IC95% {v['coverage80_ci'][0] * 100:.1f}–{v['coverage80_ci'][1] * 100:.1f}%, objetivo 80%)")
        L += ["### Rangos de retorno y riesgo de caída (lo que sí se puede estimar)", "", "- " + "\n- ".join(parts), ""]
    risk = eng.get("risk_table") or []
    if risk:
        L += ["| Mayor riesgo de caída >10% a 1 mes | Prob. | Rango 1m (P10 / P50 / P90) | Vol. 63d |", "|---|---|---|---|"]
        for r in risk[:8]:
            L.append(f"| {r['ticker']} | {_pct(r['dd21'], 0)} | {_pct(r['p10'])} / {_pct(r['p50'])} / {_pct(r['p90'])} | {_pct(r['vol63'], 0)} |")
        L.append("")
    lab = eng.get("lab")
    if lab and lab.get("rules"):
        L += ["### Laboratorio de reglas de selección (backtest histórico vs igual ponderado)", "",
              "| Regla | Sharpe [IC95%] | Exceso anual vs EW | p (Holm) | DSR | Máx. drawdown |", "|---|---|---|---|---|---|"]
        for name, r in lab["rules"].items():
            L.append(f"| {r.get('label', name)} | {r['sharpe']:.2f} [{r['sharpe_ci'][0]:.2f}, {r['sharpe_ci'][1]:.2f}] | "
                     f"{r['annual_excess_vs_ew'] * 100:+.1f}% | {r['p_holm']:.2f} | {r['dsr']:.2f} | "
                     f"{_pct(r['max_drawdown'], 0)} |")
        L += ["", f"**Veredicto:** {lab.get('verdict', '')}", ""]
        for c in lab.get("caveats", []):
            L.append(f"- _{c}_")
        L.append("")
    L += _ranking_section(eng.get("ranking"))
    led = eng.get("ledger")
    if led and led.get("rules"):
        L += ["### Libro de picks hacia adelante (simulado, sin dinero real)", "",
              "| Regla | Cerradas | Abierta desde | Exceso medio vs EW | Aciertos | Nota |", "|---|---|---|---|---|---|"]
        for name, r in led["rules"].items():
            ex = "n/d" if r.get("mean_excess_vs_ew") is None else f"{r['mean_excess_vs_ew'] * 100:+.2f}%"
            hr = "n/d" if r.get("hit_rate") is None else _pct(r["hit_rate"], 0)
            L.append(f"| {name} | {r['closed']} | {r.get('open_since') or '—'} | {ex} | {hr} | {r.get('note', '')} |")
        L.append("")
    al = eng.get("alerts")
    if al and al.get("alerts"):
        L += ["### Alertas", ""]
        for a in al["alerts"][:12]:
            L.append(f"- **[{a['severity']}]** {a['title']} — {a['detail']}")
        L.append("")
    return L


def render(res: dict) -> str:
    L: list[str] = [f"# Informe de trading — {res['date']}", ""]

    # Estado de datos
    L += ["## Estado de las fuentes", ""]
    for name, st in res["sources"].items():
        L.append(f"- **{name}**: {st}")
    if res["errors"]:
        L += ["", "Incidencias:"] + [f"- {e}" for e in res["errors"]]
    L.append("")

    # Señales
    L += ["## Tendencia y probabilidades (horizonte 21 ruedas)", "",
          "| Ticker | Precio | Mom. 12-1 | Tendencia | Vol 63d | P(sube) cond. [IC95%] (n) | P(sube) base [IC95%] (n) |",
          "|---|---|---|---|---|---|---|"]
    for t, s in res["tickers"].items():
        pu = s["prob_up"]
        cond = "n/d" if pu["p_cond"] is None else \
            f"{_pct(pu['p_cond'], 0)} [{_pct(pu['ci_cond'][0], 0)}–{_pct(pu['ci_cond'][1], 0)}] ({pu['n_cond']})"
        base = "n/d" if pu["p_all"] is None else \
            f"{_pct(pu['p_all'], 0)} [{_pct(pu['ci_all'][0], 0)}–{_pct(pu['ci_all'][1], 0)}] ({pu['n_all']})"
        L.append(f"| {t} | {s['last_price']:.2f} | {_pct(s['momentum_12_1'])} | {s['trend'] or 'n/d'} | "
                 f"{_pct(s['vol_63d'], 0)} | {cond} | {base} |")
    L += ["", "_Las probabilidades usan ventanas no solapadas; el intervalo es amplio a propósito. "
          "Si el IC condicional incluye la base, la tendencia no aporta información medible._", ""]

    # Backtest
    if res["backtest"]:
        L += ["## Validación del backtest (tendencia 12-1, sin anticipación)", "",
              "| Ticker | Períodos | Sharpe estrategia | Sharpe comprar y mantener | Exposición |", "|---|---|---|---|---|"]
        for t, b in res["backtest"].items():
            f = lambda v: "n/d" if v is None else f"{v:.2f}"  # noqa: E731
            L.append(f"| {t} | {b['periods']} | {f(b['sharpe_strategy'])} | {f(b['sharpe_buy_hold'])} | {_pct(b['exposure'], 0)} |")
        nc = res["null_check"]
        L += ["", f"Control: con precios sin tendencia el Sharpe medio es {nc['mean_sharpe']:.2f} "
              f"(error estándar {nc['std_error']:.2f}, z={nc['z']:.1f}, {nc['seeds']} series); "
              f"|z|<2 indica que no hay anticipación en el código.", ""]

    # Rigor estadístico
    rg = res.get("rigor")
    if rg and rg["tickers"]:
        L += ["## Rigor estadístico de la estrategia", "",
              "| Ticker | Sharpe [IC95%] | PSR(>0) | DSR | Δ Sharpe vs comprar y mantener [IC95%] | p (Holm) | Walk-forward: Sharpe fuera de muestra vs B&H |",
              "|---|---|---|---|---|---|---|"]
        f2 = lambda v: f"{v:+.2f}"  # noqa: E731
        for t, r in rg["tickers"].items():
            wf = r["walk_forward"]
            wftxt = "n/d" if not wf else f"{wf['sharpe_oos']:.2f} vs {wf['sharpe_hold']:.2f} (Δ {f2(wf['diff'])}, p={wf['p_beat']:.2f})"
            v = r["vs_hold"]
            L.append(f"| {t} | {r['sharpe']:.2f} [{r['sharpe_ci'][0]:.2f}, {r['sharpe_ci'][1]:.2f}] | {r['psr0']:.2f} | "
                     f"{r['dsr']:.2f} | {f2(v['diff'])} [{f2(v['ci'][0])}, {f2(v['ci'][1])}] | {v['p_holm']:.2f} | {wftxt} |")
        L += ["", f"**Veredicto:** {rg['verdict']}", "",
              "_Sharpe sobre retorno total (sin tasa libre), períodos mensuales no solapados, costo 0.1% por cambio. "
              "PSR: probabilidad de que el Sharpe verdadero sea >0. DSR: igual, corregido por probar "
              f"{rg['n_trials']} tickers (si DSR es bajo, el mejor resultado puede ser suerte de selección). "
              "Δ y p vienen de un bootstrap por bloques pareado contra comprar y mantener; p es unilateral "
              "(H0: la estrategia no supera) y se ajusta por Holm entre tickers. Walk-forward: el lookback "
              "(126/189/252) se elige solo con datos pasados._", ""]

    # Motor v2: probabilidades, riesgo, laboratorio de reglas, libro de picks y alertas (S&P 100)
    eng = res.get("engine")
    if eng:
        L += _engine_section(eng)

    # Insiders
    if res["insiders"]:
        L += ["## Insiders (Form 4, compras de mercado abierto)", "",
              "| Ticker | Compras 90d | Oportunistas | Rutinarias | Sin clasificar | Valor comprado | Valor vendido |",
              "|---|---|---|---|---|---|---|"]
        for t, i in res["insiders"].items():
            L.append(f"| {t} | {i['n_buys']} | {i['opportunistic']} | {i['routine']} | {i['unclassified']} | "
                     f"{_usd(i['buy_value'])} | {_usd(i['sell_value'])} |")
        L += ["", "_Solo las compras oportunistas tienen respaldo académico (rutinarias ≈ 0)._", ""]
        for t, i in res["insiders"].items():
            for b in i["buys"][:3]:
                if b["class"] == "oportunista":
                    L.append(f"- {t}: {b['owner']} ({b['role'] or 's/d'}) compró {_usd(b['value'])} el {b['date']}")
        L.append("")

    # 13F
    if res["managers"]:
        L += ["## Gestores (13F, último trimestre disponible)", ""]
        for m in res["managers"]:
            if "error" in m:
                L += [f"### {m['name']}", f"Error: {m['error']}", ""]
                continue
            flag = " ⚠ **13F atrasado**" if m["stale"] else ""
            L += [f"### {m['name']} — trimestre {m['period']} (presentado {m['filed']}, {m['age_days']} días){flag}",
                  f"Valor total {_usd(m['total_value'])}, {m['positions']} posiciones."
                  + (" _(valores declarados en miles; reescalados)_" if m.get("value_rescaled_from_thousands") else ""),
                  "",
                  "| Posición | Peso | Cambio acciones |", "|---|---|---|"]
            for r in m["top"][:6]:
                L.append(f"| {r['name']} | {_pct(r['weight'])} | {r['change']} |")
            if m["closed"]:
                L.append("")
                L.append("Cerradas: " + ", ".join(c["name"] for c in m["closed"][:3]))
            L.append("")

    # Track record de gestores
    mt = res.get("manager_track")
    if mt and mt.get("managers"):
        L += ["## Track record de gestores (replicar su 13F desde la fecha de presentación)", "",
              f"_Calculado la semana {mt['week']}; top {mt['top_n']} posiciones por valor; compra al primer cierre posterior "
              "a la presentación y mantiene hasta la siguiente. Referencia: SPY._", "",
              "| Gestor | Trimestres | Cobertura | CAGR replicado | CAGR SPY | Exceso anual | IR | Aciertos | IC95% exceso/trim. | p (Holm) | Años necesarios* |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
        for name, m in mt["managers"].items():
            yn = "n/d" if m["years_needed_3pct"] is None else f"{m['years_needed_3pct']:.0f}"
            ir = "n/d" if m["info_ratio"] is None else f"{m['info_ratio']:.2f}"
            L.append(f"| {name} | {m['periods']} ({m['years']:.1f} a) | {_pct(m['coverage'], 0)} | {_pct(m['cagr'])} | "
                     f"{_pct(m['cagr_bench'])} | {m['annual_excess'] * 100:+.1f} pp | {ir} | {_pct(m['hit_rate'], 0)} | "
                     f"[{m['excess_ci'][0] * 100:+.1f}, {m['excess_ci'][1] * 100:+.1f}] pp | {m['p_holm']:.2f} | {yn} |")
        L += ["", f"**Veredicto:** {mt['verdict']}", "",
              "_*Años de historia necesarios para detectar con 80% de potencia un alfa de 3% anual dado el error de "
              "seguimiento observado: con menos años que eso, un resultado bueno o malo no distingue habilidad de azar. "
              "p: prueba de inversión de signos unilateral (H0: no supera a SPY), ajustada por Holm entre gestores. "
              f"Limitaciones: el 13F solo muestra largos en acciones de EE. UU. con ~45 días de retraso; "
              f"{mt['tickers_without_prices']} de {mt['tickers_total']} tickers sin precios (deslistados) quedan fuera "
              "(sesgo de supervivencia hacia arriba)._", ""]

    # Macro
    if res["macro"]:
        L += ["## Macro (FRED)", "", "| Serie | Fecha | Valor | Δ 21 obs. |", "|---|---|---|---|"]
        for sid, m in res["macro"].items():
            if "error" in m:
                L.append(f"| {m['label']} | — | error: {m['error']} | — |")
            else:
                L.append(f"| {m['label']} | {m['date']} | {m['value']} | {m['change_21']:+} |")
        L.append("")

    # Seguimiento
    sb = res["scoreboard"]
    L += ["## Seguimiento de predicciones", ""]
    if sb["closed"] == 0:
        L.append(f"Sin predicciones cerradas aún ({sb['open']} abiertas). "
                 "Cada predicción se evalúa a su vencimiento en `data/predictions.csv`.")
    else:
        L.append(f"Cerradas: {sb['closed']}, abiertas: {sb['open']}. Acierto direccional: {_pct(sb['hit_rate'], 0)}. "
                 f"Brier {sb['brier']:.3f} vs {sb['brier_baseline']:.3f} de la tasa base "
                 f"(skill {_pct(sb['brier_skill'], 0)}).")
    L += ["", "---", f"_{DISCLAIMER}_", ""]
    return "\n".join(L)
