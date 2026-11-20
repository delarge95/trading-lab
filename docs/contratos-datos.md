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
