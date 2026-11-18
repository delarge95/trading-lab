# Informe de trading — 2026-11-18

## Estado de las fuentes

- **Precios**: OK (yahoo), 8/8 tickers
- **FRED**: OK (5/5 series)
- **SEC**: OK (8/8 gestores, 6 emisores); 13F atrasado: Pershing Square

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

## Insiders (Form 4, compras de mercado abierto)

| Ticker | Compras 90d | Oportunistas | Rutinarias | Sin clasificar | Valor comprado | Valor vendido |
|---|---|---|---|---|---|---|
| AAPL | 0 | 0 | 0 | 0 | $0 | $97.0M |
| MSFT | 0 | 0 | 0 | 0 | $0 | $74.8M |
| NVDA | 0 | 0 | 0 | 0 | $0 | $967.6M |
| AMZN | 0 | 0 | 0 | 0 | $0 | $18.5M |
| GOOGL | 0 | 0 | 0 | 0 | $0 | $169.2K |
| BRK-B | 2 | 0 | 0 | 2 | $250.2K | $20.0M |

_Solo las compras oportunistas tienen respaldo académico (rutinarias ≈ 0)._


## Gestores (13F, último trimestre disponible)

### Berkshire Hathaway — trimestre 2026-09-30 (presentado 2026-11-16, 49 días)
Valor total $304.2B, 30 posiciones.

| Posición | Peso | Cambio acciones |
|---|---|---|
| APPLE INC | 25.0% | = |
| AMERICAN EXPRESS CO | 15.2% | = |
| COCA COLA CO | 11.3% | = |
| ALPHABET INC | 8.9% | = |
| BANK OF AMER CORP | 8.2% | -6% |
| CHEVRON CORPORATION | 5.7% | = |

### Pershing Square — trimestre 2026-03-31 (presentado 2026-05-15, 232 días) ⚠ **13F atrasado**
Valor total $13.7B, 11 posiciones.

| Posición | Peso | Cambio acciones |
|---|---|---|
| BROOKFIELD CORP | 17.6% | -3% |
| AMAZON COM INC | 17.4% | +19% |
| UBER TECHNOLOGIES INC | 15.7% | = |
| MICROSOFT CORP | 15.3% | NUEVA |
| RESTAURANT BRANDS INTL INC | 12.2% | = |
| META PLATFORMS INC | 11.1% | = |

Cerradas: HILTON WORLDWIDE HLDGS INC

### Appaloosa — trimestre 2026-09-30 (presentado 2026-11-16, 49 días)
Valor total $7.6B, 24 posiciones.

| Posición | Peso | Cambio acciones |
|---|---|---|
| MICRON TECHNOLOGY INC | 17.6% | +28% |
| AMAZON COM INC | 14.7% | -10% |
| TAIWAN SEMICONDUCTOR MANUFAC | 9.5% | -5% |
| SPACE EXPLORATION TECHN CORP | 7.4% | +1626% |
| UBER TECHNOLOGIES INC | 6.6% | -5% |
| NVIDIA CORPORATION | 6.0% | +31% |

Cerradas: ADVANCED MICRO DEVICES INC, BROADCOM INC, QUALCOMM INC

### Third Point — trimestre 2026-09-30 (presentado 2026-11-16, 49 días)
Valor total $4.5B, 38 posiciones.

| Posición | Peso | Cambio acciones |
|---|---|---|
| META PLATFORMS INC | 10.5% | NUEVA |
| UNUM GROUP | 9.7% | NUEVA |
| NVIDIA CORPORATION | 7.5% | NUEVA |
| CRH PLC | 5.2% | +29% |
| BLOCK INC | 5.1% | +24% |
| MICROSOFT CORP | 5.1% | NUEVA |

Cerradas: WARNER BROS DISCOVERY INC, AMAZON COM INC, NORFOLK SOUTHN CORP

### Baupost Group — trimestre 2026-09-30 (presentado 2026-11-13, 49 días)
Valor total $5.0B, 21 posiciones. _(valores declarados en miles; reescalados)_

| Posición | Peso | Cambio acciones |
|---|---|---|
| AMAZON COM INC | 18.5% | = |
| ELEVANCE HEALTH INC FORMERLY | 9.8% | = |
| RESTAURANT BRANDS INTL INC | 9.5% | = |
| GENUINE PARTS CO | 7.7% | +10% |
| FERGUSON ENTERPRISES INC | 6.9% | +8% |
| ALPHABET INC | 6.4% | -31% |

Cerradas: TELEFLEX INCORPORATED, NORWEGIAN CRUISE LINE HLDGS, LIBERTY GLOBAL LTD

### Duquesne Family Office — trimestre 2026-09-30 (presentado 2026-11-16, 49 días)
Valor total $4.1B, 60 posiciones. _(valores declarados en miles; reescalados)_

| Posición | Peso | Cambio acciones |
|---|---|---|
| Natera Inc | 31.5% | = |
| Seagate Technology Hldngs Pl | 7.6% | +180% |
| Amazon Com Inc | 4.6% | +43% |
| Fox Corp | 4.6% | +38% |
| Ypf Sociedad Anonima | 4.3% | +13% |
| Unity Software Inc | 3.9% | +436% |

Cerradas: Alphabet Inc, United Airls Hldgs Inc, Sandisk Corp

### Himalaya Capital — trimestre 2026-09-30 (presentado 2026-11-16, 49 días)
Valor total $3.8B, 8 posiciones.

| Posición | Peso | Cambio acciones |
|---|---|---|
| PDD HOLDINGS INC | 24.2% | +9% |
| ALPHABET INC | 23.1% | = |
| ALPHABET INC | 22.1% | = |
| BERKSHIRE HATHAWAY INC DEL | 14.6% | = |
| EAST WEST BANCORP INC | 9.1% | = |
| TENCENT MUSIC ENTERTAINM | 3.1% | +125% |

### Trian Fund Management — trimestre 2026-09-30 (presentado 2026-11-16, 49 días)
Valor total $2.6B, 8 posiciones.

| Posición | Peso | Cambio acciones |
|---|---|---|
| GE Aerospace | 48.5% | = |
| Solventum Corporation | 28.0% | = |
| GE HealthCare Technologies Inc. | 7.8% | = |
| Wendys Co. | 7.5% | = |
| Ferguson Enterprises Inc. | 7.3% | NUEVA |
| Rentokil Initial plc | 0.5% | NUEVA |

Cerradas: Janus Henderson Group plc, Ferguson Plc New

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
