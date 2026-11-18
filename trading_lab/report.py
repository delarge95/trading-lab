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
