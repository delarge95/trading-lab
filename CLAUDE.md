# Trading Lab

Herramienta de **investigación** de trading. No es asesoría financiera, no conecta brokers y no opera por nadie.

## Objetivo
Informe diario (lun-vie) y revisión semanal (sáb) con: señales con respaldo académico, seguimiento a gestores/insiders confiables, probabilidades con intervalos de confianza y registro de aciertos de cada predicción.

## Metodología (resumen; detalle en el documento "Metodologia trading" del proyecto Trading de claude.ai)
- Predecir el mercado agregado casi no funciona (Welch y Goyal, NBER w10483): no prometer predicciones puntuales; reportar probabilidades con incertidumbre.
- Señales con respaldo: tendencia 12-1 meses; compras *oportunistas* de insiders (Form 4; las rutinarias rinden ~0; Cohen, Malloy y Pomorski, NBER w16454); posiciones de alta convicción de gestores con historial público (13F).
- Señales descartadas: finfluencers (56% con habilidad negativa) y carteras de congresistas.
- Cálculos: tendencia 12-1, volatilidad, probabilidad de subida a 21 días con intervalo, clasificación rutinario/oportunista, backtest sin sesgo de anticipación (con precios sin tendencia el Sharpe debe ser ≈ 0).
- Toda predicción se registra en `data/predictions.csv` y se evalúa a su vencimiento.

## Fuentes de datos
SEC EDGAR (Form 4, 13F; requiere `SEC_USER_AGENT`), FRED (macro), Yahoo Finance (precios, Stooq de respaldo). Algunos skills usan FMP (`FMP_API_KEY`, opcional, capa gratuita).

## Skills instaladas (`.claude/skills`, origen tradermonty/claude-trading-skills, MIT)
institutional-flow-tracker (13F), backtest-expert, macro-regime-detector, market-breadth-analyzer (sin API key), position-sizer, signal-postmortem, market-environment-analysis. Procedencia y revisión en `.claude/skills/SOURCE.txt`.
Skill de cuenta complementaria: `/analisis-trading` (plugin guardado en la cuenta de claude.ai).

## Estructura
- `reports/` informes generados (`latest.md`, `latest.json`, histórico por fecha)
- `data/` datos descargados y `predictions.csv`
- `config/watchlist.yaml` gestores (CIK) y tickers a seguir
- `docs/` investigación y notas

## Reglas
- Secretos y correos nunca en el repo: usar variables de entorno / `.env` (ignorado por git) y secrets de GitHub.
- Destinatarios del informe: configurados en la conexión de Gmail / archivo local `.env`, no en el código.
- Siempre cerrar informes con: "Herramienta de investigación, no asesoría financiera."
- Antes de instalar una skill nueva: revisar scripts (red, subprocess, eval) y registrar en `SOURCE.txt`.
