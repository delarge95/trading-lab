# Trading Lab

Herramienta de **investigación** de trading. No es asesoría financiera, no conecta brokers y no opera por nadie.

## Objetivo
Informe diario (lun-vie) y revisión semanal (sáb) con: señales con respaldo académico, seguimiento a gestores/insiders confiables, probabilidades con intervalos de confianza y registro de aciertos de cada predicción.

## Metodología (resumen; detalle en el documento "Metodologia trading" del proyecto Trading de claude.ai)
- Predecir el mercado agregado casi no funciona (Welch y Goyal, NBER w10483): no prometer predicciones puntuales; reportar probabilidades con incertidumbre.
- Señales con respaldo: tendencia 12-1 meses; compras *oportunistas* de insiders (Form 4; las rutinarias rinden ~0; Cohen, Malloy y Pomorski, NBER w16454); posiciones de alta convicción de gestores con historial público (13F).
- Señales descartadas: finfluencers (56% con habilidad negativa) y carteras de congresistas.
- Cálculos: tendencia 12-1, volatilidad, probabilidad de subida a 21 días con intervalo, clasificación rutinario/oportunista, backtest sin sesgo de anticipación (con precios sin tendencia el Sharpe debe ser ≈ 0).
- Rigor del backtest (`rigor.py`, `evaluate.py`): IC del Sharpe con asimetría/curtosis, PSR, DSR (corrige por probar varios tickers), bootstrap circular por bloques pareado contra comprar y mantener, corrección de Holm y walk-forward (lookback elegido solo con datos pasados). Verificado contra scipy, statsmodels y el test analítico de Memmel; las pruebas incluyen cobertura del IC (~95%), tasa de falsos positivos del bootstrap y ausencia de anticipación en walk-forward.
- Track record de gestores (`managers.py`): replica el top-15 de cada 13F desde el primer cierre posterior a la *presentación* (sin anticipación) hasta la siguiente y compara con SPY; CUSIP/CINS a ticker vía OpenFIGI; prueba de inversión de signos + Holm; calcula los años de historia necesarios para detectar un alfa de 3%. Se recalcula una vez por semana ISO (`data/managers_track.json`). Limitaciones: solo largos de EE. UU. con ~45 días de retraso; sesgo de supervivencia por tickers deslistados.
- Motor v2 (S&P 100, `config/universe.yaml`): `forecast.py` estima P(sube a 1s/1m/3m) y P(supera a SPY a 1m) con regresión logística sobre variables de precio, walk-forward con purga y calibración Platt; declara si hay ventaja estadística (Brier skill con IC por bloques, AUC, IC de rango). Hallazgo actual: **no hay ventaja** en P(sube); lo validado fuera de muestra son los rangos de retorno P10-P90 (cobertura ~78%) y el riesgo de caída (simulación histórica filtrada por volatilidad EWMA, calibrada). `lab.py`: laboratorio de 4 reglas de selección vs igual ponderado (Sharpe, Holm, DSR) y libro de picks hacia adelante (`data/picks_ledger.json`). `alerts.py`: alertas (riesgo de caída, VIX, insiders oportunistas, 13F nuevo/convergencia, datos vencidos) y texto para push. `site.py` + `docs/index.html`: panel estático (GitHub Pages) que lee `docs/data/dashboard.json`. Contratos de datos en `docs/contratos-datos.md`.
- Toda predicción se registra en `data/predictions.csv` y se evalúa a su vencimiento.

## Fuentes de datos
SEC EDGAR (Form 4, 13F; requiere `SEC_USER_AGENT`), FRED (macro), Yahoo Finance (precios, Stooq de respaldo). Algunos skills usan FMP (`FMP_API_KEY`, opcional, capa gratuita).

## Skills instaladas (`.claude/skills`, origen tradermonty/claude-trading-skills, MIT)
institutional-flow-tracker (13F), backtest-expert, macro-regime-detector, market-breadth-analyzer (sin API key), position-sizer, signal-postmortem, market-environment-analysis. Procedencia y revisión en `.claude/skills/SOURCE.txt`.
Skill de cuenta complementaria: `/analisis-trading` (plugin guardado en la cuenta de claude.ai).

## Cómo correrlo
```
python -m venv .venv && .venv\Scripts\pip install -r requirements.txt   # una vez
$env:SEC_USER_AGENT = "trading-lab tu_correo"                              # o en .env
.venv\Scripts\python run_daily.py            # genera reports/latest.md y latest.json
.venv\Scripts\python -m pytest tests -q
```
Primera corrida ~15 min (descarga ~700 Form 4 con límite de 10 req/s de la SEC); luego usa caché en `data/raw` (ignorada por git) y tarda ~20 s.
GitHub Actions (`.github/workflows/daily-report.yml`) lo corre lun-vie 5:10 a. m. y sáb 6:40 a. m. (Bogotá) y hace commit de `reports/` y `data/predictions.csv`; requiere el secreto `SEC_USER_AGENT`.

## Estructura
- `trading_lab/` código: `sec.py` (13F, Form 4), `prices.py`, `fred.py`, `signals.py`, `insiders.py`, `backtest.py`, `predictions.py`, `report.py`; `run_daily.py` es el punto de entrada.
- `reports/` informes generados (`latest.md`, `latest.json`, histórico por fecha)
- `data/` datos descargados y `predictions.csv`
- `config/watchlist.yaml` gestores (CIK) y tickers a seguir
- `docs/` investigación y notas

## Reglas
- Secretos y correos nunca en el repo: usar variables de entorno / `.env` (ignorado por git) y secrets de GitHub.
- Destinatarios del informe: configurados en la conexión de Gmail / archivo local `.env`, no en el código.
- Siempre cerrar informes con: "Herramienta de investigación, no asesoría financiera."
- Antes de instalar una skill nueva: revisar scripts (red, subprocess, eval) y registrar en `SOURCE.txt`.
