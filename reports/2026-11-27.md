# Informe de trading — 2026-11-27

## Estado de las fuentes

- **Precios**: OK (yahoo), 8/8 tickers
- **FRED**: OK (5/5 series)
- **SEC**: OK (8/8 gestores, 6 emisores); 13F atrasado: Pershing Square
- **Motor v2**: OK (101 acciones; 0 alertas altas)

## Tendencia y probabilidades (horizonte 21 ruedas)

| Ticker | Precio | Mom. 12-1 | Tendencia | Vol 63d | P(sube) cond. [IC95%] (n) | P(sube) base [IC95%] (n) |
|---|---|---|---|---|---|---|
| SPY | 728.32 | 15.6% | positiva | 20% | 66% [56%–75%] (92) | 66% [57%–75%] (107) |
| QQQ | 650.99 | 19.7% | positiva | 31% | 63% [53%–73%] (93) | 65% [56%–74%] (107) |
| AAPL | 358.54 | 24.5% | positiva | 22% | 57% [47%–67%] (91) | 63% [53%–71%] (107) |
| MSFT | 492.85 | 12.0% | positiva | 28% | 66% [55%–75%] (87) | 67% [58%–75%] (107) |
| NVDA | 150.49 | 21.4% | positiva | 75% | 60% [50%–70%] (86) | 62% [52%–70%] (107) |
| AMZN | 254.12 | 10.9% | positiva | 35% | 61% [50%–71%] (87) | 59% [49%–68%] (107) |
| GOOGL | 274.96 | 0.7% | positiva | 39% | 57% [46%–67%] (86) | 60% [50%–69%] (107) |
| BRK-B | 582.73 | 6.2% | positiva | 15% | 60% [50%–70%] (81) | 61% [51%–69%] (107) |

_Las probabilidades usan ventanas no solapadas; el intervalo es amplio a propósito. Si el IC condicional incluye la base, la tendencia no aporta información medible._

## Validación del backtest (tendencia 12-1, sin anticipación)

| Ticker | Períodos | Sharpe estrategia | Sharpe comprar y mantener | Exposición |
|---|---|---|---|---|
| SPY | 107 | 0.75 | 0.83 | 91% |
| QQQ | 107 | 0.77 | 0.86 | 91% |
| AAPL | 107 | 0.76 | 0.98 | 93% |
| MSFT | 107 | 0.82 | 0.97 | 89% |
| NVDA | 107 | 0.90 | 1.05 | 81% |
| AMZN | 107 | 0.76 | 0.67 | 85% |
| GOOGL | 107 | 0.62 | 0.79 | 84% |
| BRK-B | 107 | 0.48 | 0.76 | 91% |

Control: con precios sin tendencia el Sharpe medio es 0.00 (error estándar 0.02, z=0.1, 200 series); |z|<2 indica que no hay anticipación en el código.

## Rigor estadístico de la estrategia

| Ticker | Sharpe [IC95%] | PSR(>0) | DSR | Δ Sharpe vs comprar y mantener [IC95%] | p (Holm) | Walk-forward: Sharpe fuera de muestra vs B&H |
|---|---|---|---|---|---|---|
| SPY | 0.75 [0.03, 1.47] | 0.98 | 0.94 | -0.08 [-0.26, +0.15] | 1.00 | 0.97 vs 0.93 (Δ +0.04, p=0.40) |
| QQQ | 0.77 [0.08, 1.46] | 0.99 | 0.95 | -0.09 [-0.30, +0.13] | 1.00 | 0.78 vs 0.74 (Δ +0.04, p=0.47) |
| AAPL | 0.76 [0.08, 1.45] | 0.99 | 0.95 | -0.21 [-0.46, +0.01] | 1.00 | 0.46 vs 0.85 (Δ -0.39, p=0.96) |
| MSFT | 0.82 [0.14, 1.50] | 0.99 | 0.97 | -0.15 [-0.47, +0.15] | 1.00 | 0.49 vs 0.72 (Δ -0.23, p=0.85) |
| NVDA | 0.90 [0.25, 1.55] | 1.00 | 0.98 | -0.16 [-0.50, +0.14] | 1.00 | 0.98 vs 1.11 (Δ -0.13, p=0.75) |
| AMZN | 0.76 [0.07, 1.45] | 0.98 | 0.95 | +0.10 [-0.26, +0.51] | 1.00 | 0.47 vs 0.42 (Δ +0.05, p=0.44) |
| GOOGL | 0.62 [-0.05, 1.29] | 0.96 | 0.90 | -0.17 [-0.46, +0.12] | 1.00 | 0.71 vs 0.81 (Δ -0.09, p=0.70) |
| BRK-B | 0.48 [-0.19, 1.14] | 0.92 | 0.80 | -0.28 [-0.55, -0.08] | 1.00 | 0.76 vs 1.00 (Δ -0.23, p=0.95) |

**Veredicto:** Ningún ticker muestra que la estrategia supere a comprar y mantener (Holm, α=0.05, 8 pruebas). Significativamente peor que comprar y mantener: BRK-B.

_Sharpe sobre retorno total (sin tasa libre), períodos mensuales no solapados, costo 0.1% por cambio. PSR: probabilidad de que el Sharpe verdadero sea >0. DSR: igual, corregido por probar 8 tickers (si DSR es bajo, el mejor resultado puede ser suerte de selección). Δ y p vienen de un bootstrap por bloques pareado contra comprar y mantener; p es unilateral (H0: la estrategia no supera) y se ajusta por Holm entre tickers. Walk-forward: el lookback (126/189/252) se elige solo con datos pasados._

## Hoy en una pantalla

- **Régimen de mercado:** 🔴 **rojo** (puntaje 5/10). Volatilidad EWMA anualizada del benchmark: rojo; VIX: amarillo; Caída desde el máximo de 52 semanas: amarillo; Distancia a la media de 200 ruedas: amarillo; Spread high yield (pp): verde.
  - Prueba histórica de la regla de exposición: Regla de exposición (100% verde, 50% amarillo, 25% rojo; costo 0.05%) vs comprar y mantener sobre 119 períodos no solapados de 21 ruedas: Sharpe 0.97 vs 0.83; diferencia +0.14 (IC95% -0.36 a +0.45, p=0.35). NO mejora el Sharpe de forma significativa: solo reduce el drawdown (máximo drawdown -16% vs -34%) a costa de menor retorno anualizado (11.2% vs 14.5%).
- **Eventos de riesgo en los próximos 7 días:** Resultados trimestrales de CRM (trimestre Oct/2026), después del cierre (2026-12-02, CRM).
- **Alertas:** 0 altas, 0 medias, 10 informativas.
- **Qué dicen los datos:** Ningún criterio de selección ha mostrado ventaja estadística fuera de muestra; lo validado es el riesgo (rangos y caídas). Las listas ordenan por criterio y no son una recomendación.
- **Cartera y diario:** en el panel puedes cargar tu cartera y tus reglas de riesgo y ver cuáles posiciones las exceden, y llevar el diario de decisiones: https://delarge95.github.io/trading-lab/

## Predicciones por probabilidad (S&P 100)

Panel interactivo: https://delarge95.github.io/trading-lab/ · 101 acciones · datos al 2026-11-27.

### ¿Hay ventaja estadística? (validación fuera de muestra, walk-forward con purga)

| Objetivo | Tasa base | Brier skill [IC95%] | AUC | IC de rango [IC95%] | Veredicto |
|---|---|---|---|---|---|
| Sube en 1 semana | 54% | +0.15% [-0.21, +0.49] | 0.502 | -0.010 [-0.029, +0.011] | Sin ventaja demostrada: usar la tasa base como referencia |
| Sube en 1 mes | 56% | +0.58% [-0.39, +1.59] | 0.489 | -0.030 [-0.073, +0.014] | Sin ventaja demostrada: usar la tasa base como referencia |
| Sube en 3 meses | 60% | +1.28% [-1.20, +3.59] | 0.478 | -0.051 [-0.116, +0.014] | Sin ventaja demostrada: usar la tasa base como referencia |
| Supera a SPY en 1 mes | 48% | +0.32% [-0.08, +0.70] | 0.507 | +0.006 [-0.027, +0.040] | Sin ventaja demostrada: usar la tasa base como referencia |

_Brier skill > 0 con IC que excluye 0 = el modelo supera a la tasa base. Si no, la probabilidad calibrada se reduce a la tasa base (que además está inflada por sesgo de supervivencia: el universo son los miembros actuales del índice)._

### Rangos de retorno y riesgo de caída (lo que sí se puede estimar)

- 21 ruedas: el rango P10–P90 cubrió 78.7% de los casos reales (IC95% 76.3–81.1%, objetivo 80%)
- 63 ruedas: el rango P10–P90 cubrió 77.6% de los casos reales (IC95% 73.4–81.2%, objetivo 80%)

| Mayor riesgo de caída >10% a 1 mes | Prob. | Rango 1m (P10 / P50 / P90) | Vol. 63d |
|---|---|---|---|
| INTC | 36% | -37.0% / 3.9% / 60.4% | 104% |
| NVDA | 34% | -26.9% / 13.2% / 75.8% | 75% |
| AMD | 34% | -28.6% / 5.7% / 73.9% | 90% |
| ORCL | 31% | -24.9% / 3.6% / 44.3% | 69% |
| NOW | 31% | -22.6% / 5.5% / 34.6% | 77% |
| QCOM | 30% | -21.6% / 1.5% / 37.0% | 60% |
| TXN | 29% | -20.3% / 5.0% / 34.2% | 54% |
| TSLA | 29% | -20.7% / 2.0% / 38.7% | 54% |

### Laboratorio de reglas de selección (backtest histórico vs igual ponderado)

| Regla | Sharpe [IC95%] | Exceso anual vs EW | p (Holm) | DSR | Máx. drawdown |
|---|---|---|---|---|---|
| Momentum 12-1 (mayor retorno de 12 a 1 meses) | 1.00 [0.36, 1.64] | +7.8% | 1.00 | 0.99 | -24% |
| Baja volatilidad (menor volatilidad de 63 ruedas) | 0.92 [0.26, 1.59] | -5.2% | 1.00 | 0.99 | -15% |
| Reversión 1 mes (peor retorno de 21 ruedas) | 0.91 [0.31, 1.51] | +5.2% | 1.00 | 0.99 | -34% |
| Cerca del máximo (menor distancia al máximo de 252 ruedas) | 0.60 [-0.06, 1.26] | -8.2% | 1.00 | 0.89 | -27% |

**Veredicto:** Ninguna de las 4 reglas supera al igual ponderado del universo con significancia estadística (Holm, alfa 5%). La mejor diferencia de Sharpe es -0.06 (mom12_1, p Holm 1.00); la diferencia no se distingue del azar.

- _Sesgo de supervivencia: el universo son los miembros ACTUALES del S&P 100, lo que infla todos los retornos históricos (también los del EW y los de las reglas); las diferencias entre reglas y EW están menos sesgadas, pero no libres de sesgo._
- _Sin impuestos ni deslizamiento más allá del costo fijo por rotación; el EW y SPY se muestran sin costo (sesgo conservador contra las reglas)._
- _Resultado histórico no garantiza resultado futuro. Se probaron varias reglas: el DSR y la corrección de Holm descuentan parte, no todo, del sesgo de selección._
- _Herramienta de investigación, no asesoría financiera._

### Ranking por criterio (perfil estadístico; no es una recomendación)

Ningún criterio de selección ha mostrado ventaja estadística fuera de muestra; lo validado es el riesgo (rangos y caídas). Las listas ordenan por criterio y no son una recomendación.

**Menor riesgo de caída >10% a 1 mes** — evidencia: _validado_
  - Mejor perfil según este criterio: BRK-B (6.9%), DUK (7.9%), SO (8.1%), LIN (8.7%), KO (8.8%)
  - Peor perfil según este criterio: INTC (36.2%), NVDA (33.9%), AMD (33.8%), ORCL (30.9%), NOW (30.6%)

**Menor volatilidad de 63 ruedas** — evidencia: _validado_
  - Mejor perfil según este criterio: BRK-B (14.9%), DUK (16.6%), LIN (16.7%), SO (17.2%), KO (17.4%)
  - Peor perfil según este criterio: INTC (103.6%), AMD (90.4%), NOW (77.2%), NVDA (75.4%), ORCL (69.0%)

**Mejor asimetría del rango a 1 mes (P90 / |P10|)** — evidencia: _no probado aquí_
  - Mejor perfil según este criterio: NVDA (2.81), AMD (2.59), AVGO (2.37), WMT (2.01), MSFT (1.90)
  - Peor perfil según este criterio: UPS (0.93), NKE (1.02), CVS (1.02), VZ (1.03), CMCSA (1.05)

**Mayor probabilidad calibrada de subir a 1 mes** — evidencia: _sin ventaja demostrada_
  - Si no hay ventaja estadística, todas las probabilidades se reducen a la tasa base. Sin dispersión entre acciones: no se muestra un orden porque sería ruido.

**Mayor momentum 12-1** — evidencia: _sin ventaja demostrada_
  - Mejor perfil según este criterio: AMD (180.6%), INTC (166.6%), TXN (94.7%), TGT (76.8%), COP (75.9%)
  - Peor perfil según este criterio: INTU (-48.6%), CHTR (-47.5%), NFLX (-40.6%), NKE (-39.7%), TMUS (-26.9%)

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

- Momentum 12-1 (mayor retorno de 12 a 1 meses) [sin ventaja demostrada, exceso anual histórico +7.8%]: AMD, INTC, TXN, TGT, COP, XOM, CVX, CSCO, LMT, FDX
- Baja volatilidad (menor volatilidad de 63 ruedas) [sin ventaja demostrada, exceso anual histórico -5.2%]: BRK-B, DUK, LIN, SO, KO, SPG, COST, NEE, PG, PFE
- Reversión 1 mes (peor retorno de 21 ruedas) [sin ventaja demostrada, exceso anual histórico +5.2%]: INTC, NOW, NVDA, AMD, ORCL, CAT, CRM, INTU, GOOGL, UNH
- Cerca del máximo (menor distancia al máximo de 252 ruedas) [sin ventaja demostrada, exceso anual histórico -8.2%]: AAPL, COST, DIS, DUK, SPG, MDLZ, PG, AMGN, SBUX, WMT

### Libro de picks hacia adelante (simulado, sin dinero real)

| Regla | Cerradas | Abierta desde | Exceso medio vs EW | Aciertos | Nota |
|---|---|---|---|---|---|
| mom12_1 | 0 | 2026-11-19 | n/d | n/d | muestra insuficiente (n=0); no concluir |
| lowvol | 0 | 2026-11-19 | n/d | n/d | muestra insuficiente (n=0); no concluir |
| reversal1m | 0 | 2026-11-19 | n/d | n/d | muestra insuficiente (n=0); no concluir |
| near_high | 0 | 2026-11-19 | n/d | n/d | muestra insuficiente (n=0); no concluir |

### Alertas

- **[info]** Mayor riesgo de caída >10% a 21 ruedas: INTC, NVDA, AMD — Probabilidad calibrada de caída mayor a 10% a 21 ruedas (y P(sube) a 21 ruedas entre paréntesis): INTC 36.2% (P(sube) 56.1%); NVDA 33.9% (P(sube) 56.1%); AMD 33.8% (P(sube) 56.1%).
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
| AAPL | 0 | 0 | 0 | 0 | $0 | $130.0M |
| MSFT | 0 | 0 | 0 | 0 | $0 | $74.8M |
| NVDA | 0 | 0 | 0 | 0 | $0 | $972.1M |
| AMZN | 0 | 0 | 0 | 0 | $0 | $18.5M |
| GOOGL | 0 | 0 | 0 | 0 | $0 | $141.5K |
| BRK-B | 2 | 0 | 0 | 2 | $250.2K | $20.0M |

_Solo las compras oportunistas tienen respaldo académico (rutinarias ≈ 0)._


## Gestores (13F, último trimestre disponible)

### Berkshire Hathaway — trimestre 2026-09-30 (presentado 2026-11-16, 58 días)
Valor total $304.2B, 30 posiciones.

| Posición | Peso | Cambio acciones |
|---|---|---|
| APPLE INC | 25.0% | = |
| AMERICAN EXPRESS CO | 15.2% | = |
| COCA COLA CO | 11.3% | = |
| ALPHABET INC | 8.9% | = |
| BANK OF AMER CORP | 8.2% | -6% |
| CHEVRON CORPORATION | 5.7% | = |

### Pershing Square — trimestre 2026-03-31 (presentado 2026-05-15, 241 días) ⚠ **13F atrasado**
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

### Appaloosa — trimestre 2026-09-30 (presentado 2026-11-16, 58 días)
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

### Third Point — trimestre 2026-09-30 (presentado 2026-11-16, 58 días)
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

### Baupost Group — trimestre 2026-09-30 (presentado 2026-11-13, 58 días)
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

### Duquesne Family Office — trimestre 2026-09-30 (presentado 2026-11-16, 58 días)
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

### Himalaya Capital — trimestre 2026-09-30 (presentado 2026-11-16, 58 días)
Valor total $3.8B, 8 posiciones.

| Posición | Peso | Cambio acciones |
|---|---|---|
| PDD HOLDINGS INC | 24.2% | +9% |
| ALPHABET INC | 23.1% | = |
| ALPHABET INC | 22.1% | = |
| BERKSHIRE HATHAWAY INC DEL | 14.6% | = |
| EAST WEST BANCORP INC | 9.1% | = |
| TENCENT MUSIC ENTERTAINM | 3.1% | +125% |

### Trian Fund Management — trimestre 2026-09-30 (presentado 2026-11-16, 58 días)
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
| Tasa Treasury 10 años (%) | 2026-11-24 | 4.91 | -0.09 |
| Tasa Treasury 2 años (%) | 2026-11-24 | 4.63 | -0.06 |
| Pendiente curva 10a-2a (pp) | 2026-11-25 | 0.24 | -0.08 |
| VIX | 2026-11-26 | 26.8 | +9.89 |
| Spread high yield (pp) | 2026-11-26 | 3.77 | +0.63 |

## Seguimiento de predicciones

Sin predicciones cerradas aún (72 abiertas). Cada predicción se evalúa a su vencimiento en `data/predictions.csv`.

---
_Herramienta de investigación, no asesoría financiera._
