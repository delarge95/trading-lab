# Contratos de datos (motor v2)

Referencia para los módulos `lab.py`, `alerts.py` y `site.py`. Todo en español; sin asesoría financiera.
Muestra real de la salida del motor: `tests/fixtures/forecast_sample.json` (S&P 100, 100 acciones).

## 1. `forecast.run(series, bench) -> dict` (ya implementado en `trading_lab/forecast.py`)
```
{
 "asof": "2026-11-19", "n_stocks": 100,
 "eval": {                      # claves: up5, up21, up63, rel21 (rel21 = supera a SPY a 21 ruedas)
   "up21": {"n_oos", "base_rate", "platt": [a, b], "bss", "bss_ci": [lo, hi], "bss_raw", "auc",
            "ic", "ic_ci": [lo, hi], "top_excess", "top_excess_ci": [lo, hi], "top_n",
            "bins": [{"lo_edge","hi_edge","n","p_mean","freq","ci":[lo,hi]}], "has_edge": bool, "verdict": str}
 },
 "tickers": {
   "NVDA": {"price", "mom12_1", "r1m", "vol63", "dist_high",           # decimales (0.05 = 5%); pueden ser null
            "p": {"up5": {"p","p_raw","lo","hi"}, "up21": {...}, "up63": {...}, "rel21": {...}},
            "risk": {"21": ó 21: {"p10","p50","p90","sigma","dd": {"10": prob, "20": prob}, "dd_cal": prob_calibrada_10pct},
                     "63": {...}}}      # al serializar a JSON las claves 21/63 pasan a "21"/"63"
 },
 "risk_validation": {"21": {"h","n","coverage80","coverage80_ci","below_p10","above_p90","dd_level",
                            "dd_calibration":[{"pred","real","n"}],"dd_base","dd_brier","dd_brier_calibrated",
                            "dd_brier_base","dd_skill","dd_platt":[a,b]}, "63": {...}}
}
```
Hallazgo actual: **no hay ventaja estadística** en P(sube) (BSS con IC que incluye 0, AUC≈0.5, IC de rango≈0); lo validado y útil
es el rango de retorno (cobertura P10-P90 ≈ 78%) y el riesgo de caída. Los textos de interfaz deben decirlo con claridad.

## 2. `lab.run(P, bench) -> dict` y libro de picks (`trading_lab/lab.py`)
`P` = DataFrame fechas x tickers (`forecast.price_frame`), `bench` = "SPY".
```
{
 "rules": {"mom12_1": {"label": str, "periods": int, "sharpe": float, "sharpe_ci": [lo,hi], "annual_excess_vs_ew": float,
                       "diff_sharpe_vs_ew": float, "diff_ci": [lo,hi], "p_beat_ew": float, "p_holm": float,
                       "dsr": float, "max_drawdown": float, "turnover": float}, ...},
 "ew": {"periods": int, "sharpe": float, "sharpe_ci": [lo,hi]},      # igual ponderado del universo
 "bench": {"sharpe": float},                                         # SPY
 "verdict": str, "caveats": [str], "picks_now": {"mom12_1": ["AAPL", ...10 tickers], ...}
}
ledger summary (update_ledger) -> {"as_of": "YYYY-MM-DD", "rules": {"mom12_1": {"closed": int, "open_since": str|None,
   "mean_excess_vs_ew": float|None, "hit_rate": float|None, "note": str}}, "entries_total": int}
```

## 3. `alerts.build(...) -> dict` (`trading_lab/alerts.py`)
```
{"generated": "YYYY-MM-DD", "alerts": [{"id": "kind:ticker:date", "severity": "alta"|"media"|"info",
   "kind": str, "ticker": str|None, "title": str, "detail": str}], "counts": {"alta": n, "media": n, "info": n}}
```

## 4. `site.build_dashboard(...) -> dict` (`trading_lab/site.py`) y panel `docs/index.html`
El panel es una página estática (sin librerías externas) que lee `docs/data/dashboard.json`.

## 5. Módulos v3 (semáforo, eventos, fundamentales, fuentes alternativas, cartera)
Todos devuelven dicts serializables a JSON (sin NaN/inf: usar None). Texto en español. Sin recomendaciones de compra/venta.

`regime.run(P, bench, macro) -> dict`:
```
{"asof","state":"verde"|"amarillo"|"rojo","score":int,"inputs":{"vol_ewma_ann","vix","drawdown_52w","above_200d","hy_spread"},
 "rules":[{"name","value","state","threshold"}],
 "history":{"by_state":{"verde":{"share","fwd21_mean","fwd21_p10","prob_drop5"},"amarillo":{...},"rojo":{...}},
            "vol_managed":{"sharpe","sharpe_bh","diff_sharpe","diff_ci":[lo,hi],"p_beat","max_dd","max_dd_bh","verdict"}},
 "verdict":str,"caveats":[str]}
```
`events.upcoming(tickers, today, days=30) -> {"asof","events":[{"date","kind":"earnings"|"fomc"|"opex"|"quarter_end","ticker":str|None,"label","days_to":int,"time":str|None}],"sources":{nombre:"ok"|"error: ..."}}`

`fundamentals.snapshot(tickers) -> {"asof","coverage":int,"tickers":{T:{"revenue_ttm","rev_growth_yoy","op_margin_ttm","net_margin_ttm","fcf_margin_ttm","debt_to_equity","shares_chg_yoy","period_end","filed"}}}` (valores None si no calculables).
`sources.evaluate_factor(P, factor_df, horizon=21, name=str) -> dict` (IC de rango OOS con IC95% por bloques, exceso del quintil superior, veredicto "supera/no supera la tasa base") y `sources.collect_alt(tickers, today, outdir) -> dict` (foto diaria de IV, interés corto y consenso de analistas en data/alt/AAAA-MM-DD.json).

`portfolio.joint_samples(P, stocks, horizons=(21,63), n=400) -> dict`: muestras históricas CONJUNTAS estandarizadas por volatilidad
para simular carteras en el navegador: {"h21":{"tickers":[...],"sigma_now":{T:sigma_h},"z":[[...n filas x N tickers, 2 decimales...]]}, "h63":{...}}.
En el navegador: r_i = exp(sigma_now_i * z_it) - 1; cartera = sum(w_i * r_i); percentiles y P(pérdida > x%).

## 6. Ranking, cartera y claves nuevas del panel
`ranking.build(forecast_res, lab_res, fundamentals, convergence, insiders, managers_track) -> {"asof","criteria":[{"key","label","direction":"alto"|"bajo","evidence":"validado"|"sin ventaja demostrada"|"no probado aquí","note","format":"pct"|"num"|"count","favorable":[{"ticker","value"}],"desfavorable":[...],"n","degenerate":bool}],"rule_selections":[{"rule","label","tickers","evidence","annual_excess_vs_ew","p_holm"}],"summary","disclaimer"}`
`portfolio.build(P, stocks) -> {"h21":{"tickers","sigma_now","z","dates"},"h63":{...},"sectors":{T:sector},"method","caveats"}`
`convergence` = `{ticker: {"managers":[...], "new_by":[...], "avg_weight": fracción}}` (`alerts.convergence_13f`).
Claves nuevas de `dashboard.json`: `regime`, `events`, `fundamentals` (incluye `evidence` y `factor_verdict`), `portfolio`, `convergence`, `ranking`.
Fuente de datos alternativos: ver docstring de `altdata.py` (Nasdaq: analistas y opciones; FINRA: interés corto y volumen corto; CBOE descartado por bloqueo).
