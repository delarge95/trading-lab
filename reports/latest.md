# Informe de trading — 2026-11-23

## Estado de las fuentes

- **Precios**: OK (yahoo), 8/8 tickers
- **FRED**: OK (5/5 series)
- **SEC**: OK (8/8 gestores, 6 emisores); 13F atrasado: Pershing Square
- **Motor v2**: OK (101 acciones; 1 alertas altas)

## Tendencia y probabilidades (horizonte 21 ruedas)

| Ticker | Precio | Mom. 12-1 | Tendencia | Vol 63d | P(sube) cond. [IC95%] (n) | P(sube) base [IC95%] (n) |
|---|---|---|---|---|---|---|
| SPY | 722.29 | 17.7% | positiva | 20% | 68% [58%–76%] (93) | 68% [59%–76%] (107) |
| QQQ | 651.03 | 20.8% | positiva | 30% | 65% [55%–74%] (94) | 66% [57%–75%] (107) |
| AAPL | 349.08 | 31.0% | positiva | 22% | 59% [49%–68%] (90) | 64% [54%–72%] (107) |
| MSFT | 492.50 | 10.3% | positiva | 28% | 62% [51%–71%] (86) | 63% [53%–71%] (107) |
| NVDA | 165.05 | 17.1% | positiva | 77% | 65% [55%–74%] (86) | 67% [58%–75%] (107) |
| AMZN | 255.39 | 14.2% | positiva | 35% | 60% [49%–70%] (85) | 60% [50%–69%] (107) |
| GOOGL | 282.10 | 10.9% | positiva | 39% | 53% [42%–63%] (85) | 58% [48%–67%] (107) |
| BRK-B | 572.36 | 8.2% | positiva | 15% | 63% [53%–73%] (82) | 63% [53%–71%] (107) |

_Las probabilidades usan ventanas no solapadas; el intervalo es amplio a propósito. Si el IC condicional incluye la base, la tendencia no aporta información medible._

## Validación del backtest (tendencia 12-1, sin anticipación)

| Ticker | Períodos | Sharpe estrategia | Sharpe comprar y mantener | Exposición |
|---|---|---|---|---|
| SPY | 107 | 0.83 | 0.86 | 91% |
| QQQ | 107 | 0.81 | 0.88 | 90% |
| AAPL | 107 | 0.70 | 0.98 | 92% |
| MSFT | 107 | 0.99 | 1.01 | 88% |
| NVDA | 107 | 0.83 | 1.05 | 81% |
| AMZN | 107 | 0.82 | 0.67 | 84% |
| GOOGL | 107 | 0.59 | 0.79 | 82% |
| BRK-B | 107 | 0.56 | 0.77 | 90% |

Control: con precios sin tendencia el Sharpe medio es 0.00 (error estándar 0.02, z=0.1, 200 series); |z|<2 indica que no hay anticipación en el código.

## Rigor estadístico de la estrategia

| Ticker | Sharpe [IC95%] | PSR(>0) | DSR | Δ Sharpe vs comprar y mantener [IC95%] | p (Holm) | Walk-forward: Sharpe fuera de muestra vs B&H |
|---|---|---|---|---|---|---|
| SPY | 0.83 [0.11, 1.56] | 0.99 | 0.95 | -0.03 [-0.20, +0.18] | 1.00 | 0.96 vs 0.93 (Δ +0.03, p=0.45) |
| QQQ | 0.81 [0.11, 1.51] | 0.99 | 0.95 | -0.07 [-0.29, +0.15] | 1.00 | 0.76 vs 0.74 (Δ +0.03, p=0.48) |
| AAPL | 0.70 [0.04, 1.35] | 0.98 | 0.93 | -0.28 [-0.58, -0.01] | 1.00 | 0.53 vs 0.88 (Δ -0.35, p=0.93) |
| MSFT | 0.99 [0.29, 1.70] | 1.00 | 0.99 | -0.02 [-0.34, +0.31] | 1.00 | 0.45 vs 0.74 (Δ -0.29, p=0.88) |
| NVDA | 0.83 [0.18, 1.48] | 0.99 | 0.97 | -0.22 [-0.57, +0.08] | 1.00 | 0.86 vs 1.11 (Δ -0.25, p=0.88) |
| AMZN | 0.82 [0.16, 1.49] | 0.99 | 0.96 | +0.15 [-0.24, +0.63] | 1.00 | 0.50 vs 0.41 (Δ +0.09, p=0.40) |
| GOOGL | 0.59 [-0.08, 1.25] | 0.96 | 0.87 | -0.20 [-0.48, +0.07] | 1.00 | 0.71 vs 0.79 (Δ -0.08, p=0.67) |
| BRK-B | 0.56 [-0.12, 1.23] | 0.95 | 0.84 | -0.21 [-0.45, -0.02] | 1.00 | 0.85 vs 0.97 (Δ -0.12, p=0.82) |

**Veredicto:** Ningún ticker muestra que la estrategia supere a comprar y mantener (Holm, α=0.05, 8 pruebas). Significativamente peor que comprar y mantener: AAPL, BRK-B.

_Sharpe sobre retorno total (sin tasa libre), períodos mensuales no solapados, costo 0.1% por cambio. PSR: probabilidad de que el Sharpe verdadero sea >0. DSR: igual, corregido por probar 8 tickers (si DSR es bajo, el mejor resultado puede ser suerte de selección). Δ y p vienen de un bootstrap por bloques pareado contra comprar y mantener; p es unilateral (H0: la estrategia no supera) y se ajusta por Holm entre tickers. Walk-forward: el lookback (126/189/252) se elige solo con datos pasados._

## Hoy en una pantalla

- **Régimen de mercado:** 🔴 **rojo** (puntaje 6/10). Volatilidad EWMA anualizada del benchmark: rojo; VIX: rojo; Caída desde el máximo de 52 semanas: amarillo; Distancia a la media de 200 ruedas: amarillo; Spread high yield (pp): verde.
  - Prueba histórica de la regla de exposición: Regla de exposición (100% verde, 50% amarillo, 25% rojo; costo 0.05%) vs comprar y mantener sobre 119 períodos no solapados de 21 ruedas: Sharpe 0.99 vs 0.88; diferencia +0.11 (IC95% -0.35 a +0.42, p=0.38). NO mejora el Sharpe de forma significativa: solo reduce el drawdown (máximo drawdown -16% vs -34%) a costa de menor retorno anualizado (11.2% vs 14.5%).
- **Eventos de riesgo en los próximos 7 días:** Resultados trimestrales de MDT (trimestre Oct/2026), antes de la apertura (2026-11-24, MDT); Resultados trimestrales de DE (trimestre Oct/2026), antes de la apertura (2026-11-25, DE).
- **Alertas:** 1 altas, 0 medias, 10 informativas.
- **Qué dicen los datos:** Ningún criterio de selección ha mostrado ventaja estadística fuera de muestra; lo validado es el riesgo (rangos y caídas). Las listas ordenan por criterio y no son una recomendación.
- **Cartera y diario:** en el panel puedes cargar tu cartera y tus reglas de riesgo y ver cuáles posiciones las exceden, y llevar el diario de decisiones: https://delarge95.github.io/trading-lab/

## Predicciones por probabilidad (S&P 100)

Panel interactivo: https://delarge95.github.io/trading-lab/ · 101 acciones · datos al 2026-11-23.

### ¿Hay ventaja estadística? (validación fuera de muestra, walk-forward con purga)

| Objetivo | Tasa base | Brier skill [IC95%] | AUC | IC de rango [IC95%] | Veredicto |
|---|---|---|---|---|---|
| Sube en 1 semana | 54% | +0.18% [-0.15, +0.52] | 0.498 | -0.002 [-0.022, +0.018] | Sin ventaja demostrada: usar la tasa base como referencia |
| Sube en 1 mes | 57% | +0.50% [-0.53, +1.58] | 0.480 | -0.018 [-0.052, +0.020] | Sin ventaja demostrada: usar la tasa base como referencia |
| Sube en 3 meses | 60% | +1.39% [-1.10, +3.65] | 0.476 | -0.058 [-0.126, +0.005] | Sin ventaja demostrada: usar la tasa base como referencia |
| Supera a SPY en 1 mes | 48% | +0.36% [-0.03, +0.75] | 0.513 | +0.008 [-0.025, +0.037] | Sin ventaja demostrada: usar la tasa base como referencia |

_Brier skill > 0 con IC que excluye 0 = el modelo supera a la tasa base. Si no, la probabilidad calibrada se reduce a la tasa base (que además está inflada por sesgo de supervivencia: el universo son los miembros actuales del índice)._

### Rangos de retorno y riesgo de caída (lo que sí se puede estimar)

- 21 ruedas: el rango P10–P90 cubrió 78.3% de los casos reales (IC95% 75.6–80.7%, objetivo 80%)
- 63 ruedas: el rango P10–P90 cubrió 77.6% de los casos reales (IC95% 73.4–81.2%, objetivo 80%)

| Mayor riesgo de caída >10% a 1 mes | Prob. | Rango 1m (P10 / P50 / P90) | Vol. 63d |
|---|---|---|---|
| INTC | 36% | -36.9% / 3.9% / 60.3% | 101% |
| NVDA | 35% | -28.9% / 14.7% / 86.4% | 78% |
| AMD | 34% | -29.6% / 6.0% / 78.7% | 89% |
| NOW | 32% | -24.3% / 6.1% / 38.7% | 81% |
| ORCL | 31% | -26.1% / 3.8% / 47.4% | 69% |
| QCOM | 30% | -21.9% / 1.7% / 37.7% | 58% |
| TSLA | 29% | -22.3% / 2.2% / 42.8% | 54% |
| AVGO | 28% | -16.6% / 6.5% / 39.9% | 56% |

### Laboratorio de reglas de selección (backtest histórico vs igual ponderado)

| Regla | Sharpe [IC95%] | Exceso anual vs EW | p (Holm) | DSR | Máx. drawdown |
|---|---|---|---|---|---|
| Momentum 12-1 (mayor retorno de 12 a 1 meses) | 1.22 [0.62, 1.82] | +9.7% | 1.00 | 1.00 | -24% |
| Baja volatilidad (menor volatilidad de 63 ruedas) | 0.99 [0.37, 1.61] | -4.4% | 1.00 | 1.00 | -17% |
| Reversión 1 mes (peor retorno de 21 ruedas) | 0.98 [0.34, 1.63] | +1.4% | 1.00 | 0.99 | -25% |
| Cerca del máximo (menor distancia al máximo de 252 ruedas) | 0.85 [0.19, 1.50] | -4.3% | 1.00 | 0.98 | -19% |

**Veredicto:** Ninguna de las 4 reglas supera al igual ponderado del universo con significancia estadística (Holm, alfa 5%). La mejor diferencia de Sharpe es +0.07 (mom12_1, p Holm 1.00); la diferencia no se distingue del azar.

- _Sesgo de supervivencia: el universo son los miembros ACTUALES del S&P 100, lo que infla todos los retornos históricos (también los del EW y los de las reglas); las diferencias entre reglas y EW están menos sesgadas, pero no libres de sesgo._
- _Sin impuestos ni deslizamiento más allá del costo fijo por rotación; el EW y SPY se muestran sin costo (sesgo conservador contra las reglas)._
- _Resultado histórico no garantiza resultado futuro. Se probaron varias reglas: el DSR y la corrección de Holm descuentan parte, no todo, del sesgo de selección._
- _Herramienta de investigación, no asesoría financiera._

### Ranking por criterio (perfil estadístico; no es una recomendación)

Ningún criterio de selección ha mostrado ventaja estadística fuera de muestra; lo validado es el riesgo (rangos y caídas). Las listas ordenan por criterio y no son una recomendación.

**Menor riesgo de caída >10% a 1 mes** — evidencia: _validado_
  - Mejor perfil según este criterio: BRK-B (7.2%), LIN (7.4%), DUK (8.1%), SO (8.1%), KO (8.6%)
  - Peor perfil según este criterio: INTC (35.9%), NVDA (34.5%), AMD (34.0%), NOW (31.6%), ORCL (31.2%)

**Menor volatilidad de 63 ruedas** — evidencia: _validado_
  - Mejor perfil según este criterio: BRK-B (14.8%), LIN (16.0%), DUK (16.7%), SO (17.3%), KO (17.7%)
  - Peor perfil según este criterio: INTC (100.6%), AMD (88.6%), NOW (80.7%), NVDA (78.3%), ORCL (68.7%)

**Mejor asimetría del rango a 1 mes (P90 / |P10|)** — evidencia: _no probado aquí_
  - Mejor perfil según este criterio: NVDA (2.99), AMD (2.66), AVGO (2.40), WMT (2.01), MSFT (1.93)
  - Peor perfil según este criterio: UPS (0.93), NKE (1.01), VZ (1.04), CVS (1.04), CMCSA (1.05)

**Mayor probabilidad calibrada de subir a 1 mes** — evidencia: _sin ventaja demostrada_
  - Si no hay ventaja estadística, todas las probabilidades se reducen a la tasa base. Sin dispersión entre acciones: no se muestra un orden porque sería ruido.

**Mayor momentum 12-1** — evidencia: _sin ventaja demostrada_
  - Mejor perfil según este criterio: INTC (158.7%), AMD (150.8%), TXN (88.8%), TGT (87.6%), COP (76.2%)
  - Peor perfil según este criterio: INTU (-45.4%), CHTR (-44.2%), ORCL (-39.3%), NFLX (-37.7%), NKE (-37.3%)

**Mayor margen operativo (TTM)** — evidencia: _sin ventaja demostrada_
  - Mejor perfil según este criterio: NVDA (65.2%), V (61.2%), MA (58.6%), AVGO (48.0%), MSFT (47.1%)
  - Peor perfil según este criterio: GILD (-7.6%), GM (2.3%), INTC (2.9%), TSLA (3.3%), CVS (3.6%)

**Mayor crecimiento de ingresos (interanual)** — evidencia: _sin ventaja demostrada_
  - Mejor perfil según este criterio: PLTR (87.1%), NVDA (83.4%), AVGO (48.7%), LLY (45.5%), AMD (41.9%)
  - Peor perfil según este criterio: QCOM (-2.6%), NKE (-1.2%), GM (-0.3%), CMCSA (-0.2%), MO (0.5%)

**Más gestores con la acción en su top 10 (13F)** — evidencia: _sin ventaja demostrada_
  - Mejor perfil según este criterio: AMZN (4), META (3), AAPL (2), GOOGL (2), MSFT (2)
  - Peor perfil según este criterio: ABBV (0), ABT (0), ACN (0), ADBE (0), AIG (0)

**Compras oportunistas de insiders (90 días)** — evidencia: _no probado aquí_
  - Respaldo académico (Cohen, Malloy y Pomorski); no probado con este universo. Sin dispersión entre acciones: no se muestra un orden porque sería ruido.

**Selecciones de las reglas hoy** (con su historial frente al igual ponderado):

- Momentum 12-1 (mayor retorno de 12 a 1 meses) [sin ventaja demostrada, exceso anual histórico +9.7%]: INTC, AMD, TXN, TGT, COP, XOM, CVX, MRK, CSCO, FDX
- Baja volatilidad (menor volatilidad de 63 ruedas) [sin ventaja demostrada, exceso anual histórico -4.4%]: BRK-B, LIN, DUK, SO, KO, SPG, COST, PFE, ABBV, NEE
- Reversión 1 mes (peor retorno de 21 ruedas) [sin ventaja demostrada, exceso anual histórico +1.4%]: NOW, INTC, CRM, NVDA, UNH, CAT, PLTR, INTU, ADBE, CVS
- Cerca del máximo (menor distancia al máximo de 252 ruedas) [sin ventaja demostrada, exceso anual histórico -4.3%]: TGT, DUK, PG, COST, MDLZ, DIS, ABBV, AAPL, CL, GILD

### Libro de picks hacia adelante (simulado, sin dinero real)

| Regla | Cerradas | Abierta desde | Exceso medio vs EW | Aciertos | Nota |
|---|---|---|---|---|---|
| mom12_1 | 0 | 2026-11-19 | n/d | n/d | muestra insuficiente (n=0); no concluir |
| lowvol | 0 | 2026-11-19 | n/d | n/d | muestra insuficiente (n=0); no concluir |
| reversal1m | 0 | 2026-11-19 | n/d | n/d | muestra insuficiente (n=0); no concluir |
| near_high | 0 | 2026-11-19 | n/d | n/d | muestra insuficiente (n=0); no concluir |

### Alertas

- **[alta]** VIX en 35.9, en o sobre 30 — El índice de volatilidad VIX cerró en 35.9, nivel de estrés alto (umbral 30). Venía de 28.4 en la foto anterior.
- **[info]** Mayor riesgo de caída >10% a 21 ruedas: INTC, NVDA, AMD — Probabilidad calibrada de caída mayor a 10% a 21 ruedas (y P(sube) a 21 ruedas entre paréntesis): INTC 35.9% (P(sube) 56.7%); NVDA 34.5% (P(sube) 56.7%); AMD 34% (P(sube) 56.7%).
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
| NVDA | 0 | 0 | 0 | 0 | $0 | $972.1M |
| AMZN | 0 | 0 | 0 | 0 | $0 | $1.9M |
| GOOGL | 0 | 0 | 0 | 0 | $0 | $169.2K |
| BRK-B | 2 | 0 | 0 | 2 | $250.2K | $20.0M |

_Solo las compras oportunistas tienen respaldo académico (rutinarias ≈ 0)._


## Gestores (13F, último trimestre disponible)

### Berkshire Hathaway — trimestre 2026-09-30 (presentado 2026-11-16, 54 días)
Valor total $304.2B, 30 posiciones.

| Posición | Peso | Cambio acciones |
|---|---|---|
| APPLE INC | 25.0% | = |
| AMERICAN EXPRESS CO | 15.2% | = |
| COCA COLA CO | 11.3% | = |
| ALPHABET INC | 8.9% | = |
| BANK OF AMER CORP | 8.2% | -6% |
| CHEVRON CORPORATION | 5.7% | = |

### Pershing Square — trimestre 2026-03-31 (presentado 2026-05-15, 237 días) ⚠ **13F atrasado**
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

### Appaloosa — trimestre 2026-09-30 (presentado 2026-11-16, 54 días)
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

### Third Point — trimestre 2026-09-30 (presentado 2026-11-16, 54 días)
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

### Baupost Group — trimestre 2026-09-30 (presentado 2026-11-13, 54 días)
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

### Duquesne Family Office — trimestre 2026-09-30 (presentado 2026-11-16, 54 días)
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

### Himalaya Capital — trimestre 2026-09-30 (presentado 2026-11-16, 54 días)
Valor total $3.8B, 8 posiciones.

| Posición | Peso | Cambio acciones |
|---|---|---|
| PDD HOLDINGS INC | 24.2% | +9% |
| ALPHABET INC | 23.1% | = |
| ALPHABET INC | 22.1% | = |
| BERKSHIRE HATHAWAY INC DEL | 14.6% | = |
| EAST WEST BANCORP INC | 9.1% | = |
| TENCENT MUSIC ENTERTAINM | 3.1% | +125% |

### Trian Fund Management — trimestre 2026-09-30 (presentado 2026-11-16, 54 días)
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

_Calculado la semana 2026-W48; top 15 posiciones por valor; compra al primer cierre posterior a la presentación y mantiene hasta la siguiente. Referencia: SPY._

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
| Tasa Treasury 10 años (%) | 2026-11-20 | 4.92 | -0.21 |
| Tasa Treasury 2 años (%) | 2026-11-20 | 4.63 | -0.18 |
| Pendiente curva 10a-2a (pp) | 2026-11-23 | 0.29 | -0.02 |
| VIX | 2026-11-20 | 35.89 | +16.86 |
| Spread high yield (pp) | 2026-11-20 | 3.76 | +0.36 |

## Seguimiento de predicciones

Sin predicciones cerradas aún (40 abiertas). Cada predicción se evalúa a su vencimiento en `data/predictions.csv`.

---
_Herramienta de investigación, no asesoría financiera._
