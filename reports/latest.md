# Informe de trading — 2026-11-18

## Estado de las fuentes

- **Precios**: OK (yahoo), 8/8 tickers
- **FRED**: OK (5/5 series)
- **SEC**: FALLÓ: GET https://www.sec.gov/files/company_tickers.json falló tras 3 intentos: 403 Client Error: Forbidden for url: https://www.sec.gov/files/company_tickers.json

Incidencias:
- SEC: GET https://www.sec.gov/files/company_tickers.json falló tras 3 intentos: 403 Client Error: Forbidden for url: https://www.sec.gov/files/company_tickers.json

## Tendencia y probabilidades (horizonte 21 ruedas)

| Ticker | Precio | Mom. 12-1 | Tendencia | Vol 63d | P(sube) cond. [IC95%] (n) | P(sube) base [IC95%] (n) |
|---|---|---|---|---|---|---|
| SPY | 732.44 | 15.3% | positiva | 15% | 69% [59%–77%] (93) | 68% [59%–76%] (107) |
| QQQ | 656.95 | 18.5% | positiva | 24% | 67% [57%–75%] (93) | 65% [56%–74%] (107) |
| AAPL | 351.91 | 26.2% | positiva | 22% | 61% [51%–70%] (92) | 65% [56%–74%] (107) |
| MSFT | 506.24 | 5.4% | positiva | 27% | 61% [51%–71%] (88) | 61% [51%–69%] (107) |
| NVDA | 155.46 | 14.4% | positiva | 43% | 58% [48%–68%] (86) | 59% [49%–68%] (107) |
| AMZN | 257.89 | 11.8% | positiva | 31% | 65% [55%–75%] (84) | 64% [55%–73%] (107) |
| GOOGL | 280.20 | 24.8% | positiva | 36% | 59% [48%–69%] (85) | 62% [52%–70%] (107) |
| BRK-B | 586.76 | 4.6% | positiva | 14% | 62% [52%–72%] (87) | 63% [53%–71%] (107) |

_Las probabilidades usan ventanas no solapadas; el intervalo es amplio a propósito. Si el IC condicional incluye la base, la tendencia no aporta información medible._

## Validación del backtest (tendencia 12-1, sin anticipación)

| Ticker | Períodos | Sharpe estrategia | Sharpe comprar y mantener | Exposición |
|---|---|---|---|---|
| SPY | 107 | 0.81 | 0.93 | 90% |
| QQQ | 107 | 0.80 | 0.97 | 89% |
| AAPL | 107 | 0.60 | 0.99 | 92% |
| MSFT | 107 | 0.80 | 1.05 | 84% |
| NVDA | 107 | 0.89 | 1.11 | 82% |
| AMZN | 107 | 0.93 | 0.67 | 86% |
| GOOGL | 107 | 0.57 | 0.79 | 83% |
| BRK-B | 107 | 0.53 | 0.78 | 90% |

Control: con precios sin tendencia el Sharpe medio es 0.00 (error estándar 0.02, z=0.1, 200 series); |z|<2 indica que no hay anticipación en el código.

## Macro (FRED)

| Serie | Fecha | Valor | Δ 21 obs. |
|---|---|---|---|
| Tasa Treasury 10 años (%) | 2026-11-16 | 5.12 | +0.02 |
| Tasa Treasury 2 años (%) | 2026-11-16 | 4.83 | +0.06 |
| Pendiente curva 10a-2a (pp) | 2026-11-17 | 0.3 | -0.05 |
| VIX | 2026-11-16 | 22.91 | +2.92 |
| Spread high yield (pp) | 2026-11-16 | 3.34 | +0.03 |

## Seguimiento de predicciones

Sin predicciones cerradas aún (8 abiertas). Cada predicción se evalúa a su vencimiento en `data/predictions.csv`.

---
_Herramienta de investigación, no asesoría financiera._
