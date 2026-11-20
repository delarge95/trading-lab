# Informe de trading — 2026-11-20

## Estado de las fuentes

- **Precios**: OK (yahoo), 8/8 tickers
- **FRED**: OK (5/5 series)
- **SEC**: OK (8/8 gestores, 6 emisores); 13F atrasado: Pershing Square
- **Motor v2**: OK (100 acciones; sin precios: BK; 0 alertas altas)

## Tendencia y probabilidades (horizonte 21 ruedas)

| Ticker | Precio | Mom. 12-1 | Tendencia | Vol 63d | P(sube) cond. [IC95%] (n) | P(sube) base [IC95%] (n) |
|---|---|---|---|---|---|---|
| SPY | 715.87 | 18.4% | positiva | 16% | 71% [61%–80%] (91) | 71% [62%–79%] (107) |
| QQQ | 645.04 | 22.2% | positiva | 25% | 63% [53%–73%] (93) | 64% [55%–73%] (107) |
| AAPL | 349.21 | 29.0% | positiva | 22% | 60% [50%–70%] (91) | 64% [55%–73%] (107) |
| MSFT | 498.30 | 8.8% | positiva | 28% | 62% [52%–72%] (88) | 64% [54%–72%] (107) |
| NVDA | 145.98 | 22.7% | positiva | 44% | 63% [53%–73%] (87) | 64% [54%–72%] (107) |
| AMZN | 257.37 | 17.9% | positiva | 33% | 62% [52%–72%] (87) | 63% [53%–71%] (107) |
| GOOGL | 272.66 | 18.1% | positiva | 37% | 58% [47%–68%] (85) | 61% [51%–69%] (107) |
| BRK-B | 572.04 | 6.9% | positiva | 15% | 66% [56%–76%] (83) | 64% [54%–72%] (107) |

_Las probabilidades usan ventanas no solapadas; el intervalo es amplio a propósito. Si el IC condicional incluye la base, la tendencia no aporta información medible._

## Validación del backtest (tendencia 12-1, sin anticipación)

| Ticker | Períodos | Sharpe estrategia | Sharpe comprar y mantener | Exposición |
|---|---|---|---|---|
| SPY | 107 | 0.84 | 0.94 | 90% |
| QQQ | 107 | 0.86 | 0.97 | 89% |
| AAPL | 107 | 0.66 | 0.99 | 93% |
| MSFT | 107 | 0.85 | 1.05 | 85% |
| NVDA | 107 | 0.88 | 1.11 | 82% |
| AMZN | 107 | 0.92 | 0.67 | 86% |
| GOOGL | 107 | 0.59 | 0.78 | 86% |
| BRK-B | 107 | 0.55 | 0.77 | 90% |

Control: con precios sin tendencia el Sharpe medio es 0.00 (error estándar 0.02, z=0.1, 200 series); |z|<2 indica que no hay anticipación en el código.

## Rigor estadístico de la estrategia

| Ticker | Sharpe [IC95%] | PSR(>0) | DSR | Δ Sharpe vs comprar y mantener [IC95%] | p (Holm) | Walk-forward: Sharpe fuera de muestra vs B&H |
|---|---|---|---|---|---|---|
| SPY | 0.84 [0.12, 1.56] | 0.99 | 0.96 | -0.10 [-0.30, +0.15] | 1.00 | 1.15 vs 1.10 (Δ +0.05, p=0.44) |
| QQQ | 0.86 [0.18, 1.54] | 0.99 | 0.97 | -0.11 [-0.37, +0.14] | 1.00 | 0.92 vs 0.87 (Δ +0.05, p=0.41) |
| AAPL | 0.66 [0.00, 1.32] | 0.98 | 0.91 | -0.33 [-0.63, -0.07] | 1.00 | 0.22 vs 0.91 (Δ -0.69, p=1.00) |
| MSFT | 0.85 [0.18, 1.52] | 0.99 | 0.97 | -0.20 [-0.54, +0.12] | 1.00 | 0.72 vs 0.77 (Δ -0.06, p=0.57) |
| NVDA | 0.88 [0.22, 1.54] | 1.00 | 0.98 | -0.23 [-0.56, +0.08] | 1.00 | 0.94 vs 1.20 (Δ -0.26, p=0.89) |
| AMZN | 0.92 [0.30, 1.55] | 1.00 | 0.99 | +0.25 [-0.14, +0.68] | 1.00 | 0.70 vs 0.40 (Δ +0.30, p=0.16) |
| GOOGL | 0.59 [-0.07, 1.25] | 0.96 | 0.87 | -0.19 [-0.52, +0.10] | 1.00 | 0.69 vs 0.79 (Δ -0.11, p=0.74) |
| BRK-B | 0.55 [-0.13, 1.22] | 0.94 | 0.83 | -0.23 [-0.48, -0.02] | 1.00 | 0.85 vs 0.94 (Δ -0.10, p=0.77) |

**Veredicto:** Ningún ticker muestra que la estrategia supere a comprar y mantener (Holm, α=0.05, 8 pruebas). Significativamente peor que comprar y mantener: AAPL, BRK-B.

_Sharpe sobre retorno total (sin tasa libre), períodos mensuales no solapados, costo 0.1% por cambio. PSR: probabilidad de que el Sharpe verdadero sea >0. DSR: igual, corregido por probar 8 tickers (si DSR es bajo, el mejor resultado puede ser suerte de selección). Δ y p vienen de un bootstrap por bloques pareado contra comprar y mantener; p es unilateral (H0: la estrategia no supera) y se ajusta por Holm entre tickers. Walk-forward: el lookback (126/189/252) se elige solo con datos pasados._

## Predicciones por probabilidad (S&P 100)

Panel interactivo: https://delarge95.github.io/trading-lab/ · 100 acciones · datos al 2026-11-19.

### ¿Hay ventaja estadística? (validación fuera de muestra, walk-forward con purga)

| Objetivo | Tasa base | Brier skill [IC95%] | AUC | IC de rango [IC95%] | Veredicto |
|---|---|---|---|---|---|
| Sube en 1 semana | 54% | +0.19% [-0.16, +0.56] | 0.503 | -0.007 [-0.028, +0.012] | Sin ventaja demostrada: usar la tasa base como referencia |
| Sube en 1 mes | 56% | +0.58% [-0.42, +1.72] | 0.482 | -0.032 [-0.073, +0.011] | Sin ventaja demostrada: usar la tasa base como referencia |
| Sube en 3 meses | 60% | +1.42% [-1.17, +3.80] | 0.478 | -0.054 [-0.123, +0.010] | Sin ventaja demostrada: usar la tasa base como referencia |
| Supera a SPY en 1 mes | 48% | +0.35% [-0.09, +0.75] | 0.509 | +0.009 [-0.026, +0.044] | Sin ventaja demostrada: usar la tasa base como referencia |

_Brier skill > 0 con IC que excluye 0 = el modelo supera a la tasa base. Si no, la probabilidad calibrada se reduce a la tasa base (que además está inflada por sesgo de supervivencia: el universo son los miembros actuales del índice)._

### Rangos de retorno y riesgo de caída (lo que sí se puede estimar)

- 21 ruedas: el rango P10–P90 cubrió 78.7% de los casos reales (IC95% 76.2–81.2%, objetivo 80%)
- 63 ruedas: el rango P10–P90 cubrió 77.6% de los casos reales (IC95% 73.6–81.0%, objetivo 80%)

| Mayor riesgo de caída >10% a 1 mes | Prob. | Rango 1m (P10 / P50 / P90) | Vol. 63d |
|---|---|---|---|
| INTC | 35% | -35.0% / 3.6% / 55.7% | 96% |
| AMD | 33% | -27.2% / 5.5% / 69.6% | 83% |
| NOW | 32% | -24.9% / 6.3% / 40.1% | 80% |
| ORCL | 28% | -21.1% / 3.0% / 35.7% | 62% |
| QCOM | 28% | -18.1% / 1.4% / 29.5% | 53% |
| CHTR | 27% | -21.3% / 1.2% / 27.3% | 58% |
| CVS | 26% | -20.3% / 0.7% / 21.4% | 40% |
| UNH | 25% | -16.0% / 3.9% / 24.8% | 35% |

### Laboratorio de reglas de selección (backtest histórico vs igual ponderado)

| Regla | Sharpe [IC95%] | Exceso anual vs EW | p (Holm) | DSR | Máx. drawdown |
|---|---|---|---|---|---|
| Momentum 12-1 (mayor retorno de 12 a 1 meses) | 1.21 [0.60, 1.81] | +9.8% | 1.00 | 1.00 | -27% |
| Baja volatilidad (menor volatilidad de 63 ruedas) | 1.01 [0.35, 1.66] | -4.3% | 1.00 | 1.00 | -16% |
| Reversión 1 mes (peor retorno de 21 ruedas) | 1.10 [0.46, 1.75] | +3.3% | 1.00 | 1.00 | -20% |
| Cerca del máximo (menor distancia al máximo de 252 ruedas) | 0.96 [0.32, 1.61] | -2.6% | 1.00 | 1.00 | -19% |

**Veredicto:** Ninguna de las 4 reglas supera al igual ponderado del universo con significancia estadística (Holm, alfa 5%). La mejor diferencia de Sharpe es +0.04 (mom12_1, p Holm 1.00); la diferencia no se distingue del azar.

- _Sesgo de supervivencia: el universo son los miembros ACTUALES del S&P 100, lo que infla todos los retornos históricos (también los del EW y los de las reglas); las diferencias entre reglas y EW están menos sesgadas, pero no libres de sesgo._
- _Sin impuestos ni deslizamiento más allá del costo fijo por rotación; el EW y SPY se muestran sin costo (sesgo conservador contra las reglas)._
- _Resultado histórico no garantiza resultado futuro. Se probaron varias reglas: el DSR y la corrección de Holm descuentan parte, no todo, del sesgo de selección._
- _Herramienta de investigación, no asesoría financiera._

### Libro de picks hacia adelante (simulado, sin dinero real)

| Regla | Cerradas | Abierta desde | Exceso medio vs EW | Aciertos | Nota |
|---|---|---|---|---|---|
| mom12_1 | 0 | 2026-11-19 | n/d | n/d | muestra insuficiente (n=0); no concluir |
| lowvol | 0 | 2026-11-19 | n/d | n/d | muestra insuficiente (n=0); no concluir |
| reversal1m | 0 | 2026-11-19 | n/d | n/d | muestra insuficiente (n=0); no concluir |
| near_high | 0 | 2026-11-19 | n/d | n/d | muestra insuficiente (n=0); no concluir |

### Alertas

- **[info]** Mayor riesgo de caída >10% a 21 ruedas: INTC, AMD, NOW — Probabilidad calibrada de caída mayor a 10% a 21 ruedas (y P(sube) a 21 ruedas entre paréntesis): INTC 35.4% (P(sube) 56.2%); AMD 33% (P(sube) 56.2%); NOW 32.3% (P(sube) 56.2%).
- **[info]** AMZN: en el top de 4 gestores — AMAZON COM INC aparece en el top 10 de Pershing Square, Appaloosa, Baupost Group y Duquesne Family Office (peso medio 13.8%).
- **[info]** FERG: posición nueva en el top de 1 gestor (13F al 2026-09-30) — Trian Fund Management abrió FERGUSON ENTERPRISES INC en su top 10 en el trimestre al 2026-09-30. Los datos del 13F tienen hasta ~45 días de retraso.
- **[info]** GOOG: en el top de 5 gestores — ALPHABET INC aparece en el top 10 de Berkshire Hathaway, Pershing Square, Appaloosa, Baupost Group y Himalaya Capital (peso medio 7.3%).
- **[info]** META: en el top de 3 gestores — META PLATFORMS INC aparece en el top 10 de Pershing Square, Appaloosa y Third Point (peso medio 8.9%).
- **[info]** META: posición nueva en el top de 1 gestor (13F al 2026-09-30) — Third Point abrió META PLATFORMS INC en su top 10 en el trimestre al 2026-09-30. Los datos del 13F tienen hasta ~45 días de retraso.
- **[info]** MSFT: posición nueva en el top de 1 gestor (13F al 2026-09-30) — Third Point abrió MICROSOFT CORP en su top 10 en el trimestre al 2026-09-30. Los datos del 13F tienen hasta ~45 días de retraso.
- **[info]** NVDA: posición nueva en el top de 1 gestor (13F al 2026-09-30) — Third Point abrió NVIDIA CORPORATION en su top 10 en el trimestre al 2026-09-30. Los datos del 13F tienen hasta ~45 días de retraso.
- **[info]** RTO: posición nueva en el top de 1 gestor (13F al 2026-09-30) — Trian Fund Management abrió Rentokil Initial plc en su top 10 en el trimestre al 2026-09-30. Los datos del 13F tienen hasta ~45 días de retraso.
- **[info]** UNUM GROUP: posición nueva en el top de 1 gestor (13F al 2026-09-30) — Third Point abrió UNUM GROUP en su top 10 en el trimestre al 2026-09-30. Los datos del 13F tienen hasta ~45 días de retraso.

## Insiders (Form 4, compras de mercado abierto)

| Ticker | Compras 90d | Oportunistas | Rutinarias | Sin clasificar | Valor comprado | Valor vendido |
|---|---|---|---|---|---|---|
| AAPL | 0 | 0 | 0 | 0 | $0 | $129.7M |
| MSFT | 0 | 0 | 0 | 0 | $0 | $74.8M |
| NVDA | 0 | 0 | 0 | 0 | $0 | $967.6M |
| AMZN | 0 | 0 | 0 | 0 | $0 | $4.1M |
| GOOGL | 0 | 0 | 0 | 0 | $0 | $169.2K |
| BRK-B | 2 | 0 | 0 | 2 | $250.2K | $20.0M |

_Solo las compras oportunistas tienen respaldo académico (rutinarias ≈ 0)._


## Gestores (13F, último trimestre disponible)

### Berkshire Hathaway — trimestre 2026-09-30 (presentado 2026-11-16, 51 días)
Valor total $304.2B, 30 posiciones.

| Posición | Peso | Cambio acciones |
|---|---|---|
| APPLE INC | 25.0% | = |
| AMERICAN EXPRESS CO | 15.2% | = |
| COCA COLA CO | 11.3% | = |
| ALPHABET INC | 8.9% | = |
| BANK OF AMER CORP | 8.2% | -6% |
| CHEVRON CORPORATION | 5.7% | = |

### Pershing Square — trimestre 2026-03-31 (presentado 2026-05-15, 234 días) ⚠ **13F atrasado**
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

### Appaloosa — trimestre 2026-09-30 (presentado 2026-11-16, 51 días)
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

### Third Point — trimestre 2026-09-30 (presentado 2026-11-16, 51 días)
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

### Baupost Group — trimestre 2026-09-30 (presentado 2026-11-13, 51 días)
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

### Duquesne Family Office — trimestre 2026-09-30 (presentado 2026-11-16, 51 días)
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

### Himalaya Capital — trimestre 2026-09-30 (presentado 2026-11-16, 51 días)
Valor total $3.8B, 8 posiciones.

| Posición | Peso | Cambio acciones |
|---|---|---|
| PDD HOLDINGS INC | 24.2% | +9% |
| ALPHABET INC | 23.1% | = |
| ALPHABET INC | 22.1% | = |
| BERKSHIRE HATHAWAY INC DEL | 14.6% | = |
| EAST WEST BANCORP INC | 9.1% | = |
| TENCENT MUSIC ENTERTAINM | 3.1% | +125% |

### Trian Fund Management — trimestre 2026-09-30 (presentado 2026-11-16, 51 días)
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

## Track record de gestores (replicar su 13F desde la fecha de presentación)

_Calculado la semana 2026-W47; top 15 posiciones por valor; compra al primer cierre posterior a la presentación y mantiene hasta la siguiente. Referencia: SPY._

| Gestor | Trimestres | Cobertura | CAGR replicado | CAGR SPY | Exceso anual | IR | Aciertos | IC95% exceso/trim. | p (Holm) | Años necesarios* |
|---|---|---|---|---|---|---|---|---|---|---|
| Berkshire Hathaway | 19 (4.8 a) | 100% | 9.9% | 12.5% | -2.4 pp | -0.36 | 58% | [-2.1, +0.9] pp | 1.00 | 30 |
| Pershing Square | 19 (4.7 a) | 92% | 11.0% | 12.9% | -1.2 pp | -0.13 | 53% | [-2.3, +1.8] pp | 1.00 | 60 |
| Appaloosa | 19 (4.8 a) | 100% | 16.2% | 12.5% | +4.2 pp | 0.39 | 53% | [-1.3, +3.4] pp | 1.00 | 80 |
| Third Point | 19 (4.8 a) | 95% | 1.1% | 12.5% | -9.8 pp | -0.85 | 32% | [-4.9, +0.1] pp | 1.00 | 91 |
| Baupost Group | 13 (3.2 a) | 90% | 10.5% | 13.5% | -2.5 pp | -0.29 | 38% | [-2.9, +1.7] pp | 1.00 | 51 |
| Duquesne Family Office | 19 (4.8 a) | 95% | 22.9% | 12.5% | +11.5 pp | 0.61 | 63% | [-1.2, +7.0] pp | 0.86 | 245 |
| Himalaya Capital | 19 (4.8 a) | 100% | 8.7% | 12.5% | -2.5 pp | -0.21 | 42% | [-3.2, +2.0] pp | 1.00 | 102 |
| Trian Fund Management | 18 (4.5 a) | 59% | 8.9% | 13.7% | -3.7 pp | -0.25 | 50% | [-4.2, +2.3] pp | 1.00 | 143 |

**Veredicto:** Ningún gestor supera a SPY con significancia estadística (Holm 5%, 8 gestores).

_*Años de historia necesarios para detectar con 80% de potencia un alfa de 3% anual dado el error de seguimiento observado: con menos años que eso, un resultado bueno o malo no distingue habilidad de azar. p: prueba de inversión de signos unilateral (H0: no supera a SPY), ajustada por Holm entre gestores. Limitaciones: el 13F solo muestra largos en acciones de EE. UU. con ~45 días de retraso; 33 de 278 tickers sin precios (deslistados) quedan fuera (sesgo de supervivencia hacia arriba)._

## Macro (FRED)

| Serie | Fecha | Valor | Δ 21 obs. |
|---|---|---|---|
| Tasa Treasury 10 años (%) | 2026-11-18 | 5.07 | -0.08 |
| Tasa Treasury 2 años (%) | 2026-11-18 | 4.8 | +0.03 |
| Pendiente curva 10a-2a (pp) | 2026-11-19 | 0.28 | -0.05 |
| VIX | 2026-11-18 | 24.56 | +7.25 |
| Spread high yield (pp) | 2026-11-18 | 3.47 | +0.14 |

## Seguimiento de predicciones

Sin predicciones cerradas aún (24 abiertas). Cada predicción se evalúa a su vencimiento en `data/predictions.csv`.

---
_Herramienta de investigación, no asesoría financiera._
