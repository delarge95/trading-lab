# Informe de trading — 2026-11-26

## Estado de las fuentes

- **Precios**: OK (yahoo), 8/8 tickers
- **FRED**: OK (5/5 series)
- **SEC**: OK (8/8 gestores, 6 emisores); 13F atrasado: Pershing Square
- **Motor v2**: OK (101 acciones; 0 alertas altas)

## Tendencia y probabilidades (horizonte 21 ruedas)

| Ticker | Precio | Mom. 12-1 | Tendencia | Vol 63d | P(sube) cond. [IC95%] (n) | P(sube) base [IC95%] (n) |
|---|---|---|---|---|---|---|
| SPY | 716.70 | 16.3% | positiva | 20% | 64% [54%–73%] (92) | 65% [56%–74%] (107) |
| QQQ | 633.93 | 19.7% | positiva | 30% | 65% [55%–74%] (94) | 66% [57%–75%] (107) |
| AAPL | 355.58 | 26.1% | positiva | 22% | 62% [51%–71%] (91) | 66% [57%–75%] (107) |
| MSFT | 489.93 | 12.8% | positiva | 28% | 64% [54%–74%] (87) | 64% [55%–73%] (107) |
| NVDA | 149.30 | 19.7% | positiva | 76% | 59% [49%–69%] (86) | 62% [52%–70%] (107) |
| AMZN | 244.43 | 11.9% | positiva | 35% | 64% [53%–73%] (85) | 60% [50%–69%] (107) |
| GOOGL | 273.10 | 0.9% | positiva | 39% | 61% [50%–71%] (87) | 63% [53%–71%] (107) |
| BRK-B | 579.32 | 6.9% | positiva | 15% | 57% [47%–67%] (82) | 59% [49%–68%] (107) |

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
  - Prueba histórica de la regla de exposición: Regla de exposición (100% verde, 50% amarillo, 25% rojo; costo 0.05%) vs comprar y mantener sobre 119 períodos no solapados de 21 ruedas: Sharpe 0.98 vs 0.86; diferencia +0.12 (IC95% -0.37 a +0.43, p=0.37). NO mejora el Sharpe de forma significativa: solo reduce el drawdown (máximo drawdown -16% vs -34%) a costa de menor retorno anualizado (11.1% vs 14.3%).
- **Eventos de riesgo en los próximos 7 días:** Resultados trimestrales de CRM (trimestre Oct/2026), después del cierre (2026-12-02, CRM).
- **Alertas:** 0 altas, 0 medias, 10 informativas.
- **Qué dicen los datos:** Ningún criterio de selección ha mostrado ventaja estadística fuera de muestra; lo validado es el riesgo (rangos y caídas). Las listas ordenan por criterio y no son una recomendación.
- **Cartera y diario:** en el panel puedes cargar tu cartera y tus reglas de riesgo y ver cuáles posiciones las exceden, y llevar el diario de decisiones: https://delarge95.github.io/trading-lab/

## Predicciones por probabilidad (S&P 100)

Panel interactivo: https://delarge95.github.io/trading-lab/ · 101 acciones · datos al 2026-11-25.

### ¿Hay ventaja estadística? (validación fuera de muestra, walk-forward con purga)

| Objetivo | Tasa base | Brier skill [IC95%] | AUC | IC de rango [IC95%] | Veredicto |
|---|---|---|---|---|---|
| Sube en 1 semana | 54% | +0.21% [-0.18, +0.57] | 0.496 | -0.014 [-0.037, +0.008] | Sin ventaja demostrada: usar la tasa base como referencia |
| Sube en 1 mes | 56% | +0.63% [-0.42, +1.69] | 0.477 | -0.012 [-0.051, +0.026] | Sin ventaja demostrada: usar la tasa base como referencia |
| Sube en 3 meses | 60% | +1.37% [-1.20, +3.75] | 0.469 | -0.057 [-0.120, +0.004] | Sin ventaja demostrada: usar la tasa base como referencia |
| Supera a SPY en 1 mes | 48% | +0.27% [-0.07, +0.61] | 0.507 | +0.008 [-0.028, +0.041] | Sin ventaja demostrada: usar la tasa base como referencia |

_Brier skill > 0 con IC que excluye 0 = el modelo supera a la tasa base. Si no, la probabilidad calibrada se reduce a la tasa base (que además está inflada por sesgo de supervivencia: el universo son los miembros actuales del índice)._

### Rangos de retorno y riesgo de caída (lo que sí se puede estimar)

- 21 ruedas: el rango P10–P90 cubrió 78.5% de los casos reales (IC95% 76.0–80.9%, objetivo 80%)
- 63 ruedas: el rango P10–P90 cubrió 77.6% de los casos reales (IC95% 73.5–81.2%, objetivo 80%)

| Mayor riesgo de caída >10% a 1 mes | Prob. | Rango 1m (P10 / P50 / P90) | Vol. 63d |
|---|---|---|---|
| INTC | 37% | -37.5% / 3.9% / 61.6% | 103% |
| NVDA | 35% | -27.6% / 13.6% / 79.1% | 76% |
| AMD | 34% | -29.0% / 5.8% / 75.8% | 90% |
| ORCL | 31% | -25.3% / 3.7% / 45.6% | 69% |
| NOW | 31% | -23.0% / 5.6% / 35.8% | 78% |
| QCOM | 30% | -21.0% / 1.5% / 35.8% | 59% |
| TXN | 30% | -20.5% / 5.0% / 34.6% | 54% |
| TSLA | 29% | -20.4% / 2.0% / 38.0% | 53% |

### Laboratorio de reglas de selección (backtest histórico vs igual ponderado)

| Regla | Sharpe [IC95%] | Exceso anual vs EW | p (Holm) | DSR | Máx. drawdown |
|---|---|---|---|---|---|
| Momentum 12-1 (mayor retorno de 12 a 1 meses) | 1.08 [0.44, 1.72] | +9.8% | 1.00 | 1.00 | -24% |
| Baja volatilidad (menor volatilidad de 63 ruedas) | 0.89 [0.24, 1.53] | -4.9% | 1.00 | 0.99 | -19% |
| Reversión 1 mes (peor retorno de 21 ruedas) | 0.79 [0.14, 1.44] | +2.3% | 1.00 | 0.97 | -38% |
| Cerca del máximo (menor distancia al máximo de 252 ruedas) | 0.77 [0.11, 1.44] | -5.6% | 1.00 | 0.97 | -19% |

**Veredicto:** Ninguna de las 4 reglas supera al igual ponderado del universo con significancia estadística (Holm, alfa 5%). La mejor diferencia de Sharpe es +0.02 (mom12_1, p Holm 1.00); la diferencia no se distingue del azar.

- _Sesgo de supervivencia: el universo son los miembros ACTUALES del S&P 100, lo que infla todos los retornos históricos (también los del EW y los de las reglas); las diferencias entre reglas y EW están menos sesgadas, pero no libres de sesgo._
- _Sin impuestos ni deslizamiento más allá del costo fijo por rotación; el EW y SPY se muestran sin costo (sesgo conservador contra las reglas)._
- _Resultado histórico no garantiza resultado futuro. Se probaron varias reglas: el DSR y la corrección de Holm descuentan parte, no todo, del sesgo de selección._
- _Herramienta de investigación, no asesoría financiera._

### Ranking por criterio (perfil estadístico; no es una recomendación)

Ningún criterio de selección ha mostrado ventaja estadística fuera de muestra; lo validado es el riesgo (rangos y caídas). Las listas ordenan por criterio y no son una recomendación.

**Menor riesgo de caída >10% a 1 mes** — evidencia: _validado_
  - Mejor perfil según este criterio: BRK-B (7.1%), DUK (8.1%), SO (8.2%), LIN (8.5%), KO (8.9%)
  - Peor perfil según este criterio: INTC (36.7%), NVDA (34.5%), AMD (34.3%), ORCL (31.4%), NOW (31.2%)

**Menor volatilidad de 63 ruedas** — evidencia: _validado_
  - Mejor perfil según este criterio: BRK-B (14.9%), LIN (16.6%), DUK (16.6%), SO (17.3%), KO (17.4%)
  - Peor perfil según este criterio: INTC (103.0%), AMD (90.0%), NOW (77.9%), NVDA (75.8%), ORCL (68.7%)

**Mejor asimetría del rango a 1 mes (P90 / |P10|)** — evidencia: _no probado aquí_
  - Mejor perfil según este criterio: NVDA (2.87), AMD (2.61), AVGO (2.37), WMT (2.02), MSFT (1.91)
  - Peor perfil según este criterio: UPS (0.93), NKE (1.02), CVS (1.03), VZ (1.03), CMCSA (1.05)

**Mayor probabilidad calibrada de subir a 1 mes** — evidencia: _sin ventaja demostrada_
  - Si no hay ventaja estadística, todas las probabilidades se reducen a la tasa base. Sin dispersión entre acciones: no se muestra un orden porque sería ruido.

**Mayor momentum 12-1** — evidencia: _sin ventaja demostrada_
  - Mejor perfil según este criterio: INTC (161.9%), AMD (160.5%), TXN (94.8%), TGT (79.9%), COP (72.7%)
  - Peor perfil según este criterio: INTU (-49.0%), CHTR (-47.3%), NFLX (-41.6%), NKE (-37.4%), ORCL (-34.0%)

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

- Momentum 12-1 (mayor retorno de 12 a 1 meses) [sin ventaja demostrada, exceso anual histórico +9.8%]: INTC, AMD, TXN, TGT, COP, XOM, CVX, CSCO, MRK, FDX
- Baja volatilidad (menor volatilidad de 63 ruedas) [sin ventaja demostrada, exceso anual histórico -4.9%]: BRK-B, LIN, DUK, SO, KO, SPG, COST, NEE, PG, PFE
- Reversión 1 mes (peor retorno de 21 ruedas) [sin ventaja demostrada, exceso anual histórico +2.3%]: INTC, NOW, NVDA, AMD, CAT, ORCL, CRM, PLTR, INTU, UNH
- Cerca del máximo (menor distancia al máximo de 252 ruedas) [sin ventaja demostrada, exceso anual histórico -5.6%]: DIS, DUK, MDLZ, PG, AAPL, SPG, COST, GILD, CL, AMGN

### Libro de picks hacia adelante (simulado, sin dinero real)

| Regla | Cerradas | Abierta desde | Exceso medio vs EW | Aciertos | Nota |
|---|---|---|---|---|---|
| mom12_1 | 0 | 2026-11-19 | n/d | n/d | muestra insuficiente (n=0); no concluir |
| lowvol | 0 | 2026-11-19 | n/d | n/d | muestra insuficiente (n=0); no concluir |
| reversal1m | 0 | 2026-11-19 | n/d | n/d | muestra insuficiente (n=0); no concluir |
| near_high | 0 | 2026-11-19 | n/d | n/d | muestra insuficiente (n=0); no concluir |

### Alertas

- **[info]** Mayor riesgo de caída >10% a 21 ruedas: INTC, NVDA, AMD — Probabilidad calibrada de caída mayor a 10% a 21 ruedas (y P(sube) a 21 ruedas entre paréntesis): INTC 36.7% (P(sube) 56.1%); NVDA 34.5% (P(sube) 56.1%); AMD 34.3% (P(sube) 56.1%).
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
| GOOGL | 0 | 0 | 0 | 0 | $0 | $169.2K |
| BRK-B | 2 | 0 | 0 | 2 | $250.2K | $20.0M |

_Solo las compras oportunistas tienen respaldo académico (rutinarias ≈ 0)._


## Gestores (13F, último trimestre disponible)

### Berkshire Hathaway — trimestre 2026-09-30 (presentado 2026-11-16, 57 días)
Valor total $304.2B, 30 posiciones.

| Posición | Peso | Cambio acciones |
|---|---|---|
| APPLE INC | 25.0% | = |
| AMERICAN EXPRESS CO | 15.2% | = |
| COCA COLA CO | 11.3% | = |
| ALPHABET INC | 8.9% | = |
| BANK OF AMER CORP | 8.2% | -6% |
| CHEVRON CORPORATION | 5.7% | = |

### Pershing Square — trimestre 2026-03-31 (presentado 2026-05-15, 240 días) ⚠ **13F atrasado**
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

### Appaloosa — trimestre 2026-09-30 (presentado 2026-11-16, 57 días)
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

### Third Point — trimestre 2026-09-30 (presentado 2026-11-16, 57 días)
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

### Baupost Group — trimestre 2026-09-30 (presentado 2026-11-13, 57 días)
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

### Duquesne Family Office — trimestre 2026-09-30 (presentado 2026-11-16, 57 días)
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

### Himalaya Capital — trimestre 2026-09-30 (presentado 2026-11-16, 57 días)
Valor total $3.8B, 8 posiciones.

| Posición | Peso | Cambio acciones |
|---|---|---|
| PDD HOLDINGS INC | 24.2% | +9% |
| ALPHABET INC | 23.1% | = |
| ALPHABET INC | 22.1% | = |
| BERKSHIRE HATHAWAY INC DEL | 14.6% | = |
| EAST WEST BANCORP INC | 9.1% | = |
| TENCENT MUSIC ENTERTAINM | 3.1% | +125% |

### Trian Fund Management — trimestre 2026-09-30 (presentado 2026-11-16, 57 días)
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
| VIX | 2026-11-24 | 26.36 | +7.97 |
| Spread high yield (pp) | 2026-11-24 | 3.72 | +0.42 |

## Seguimiento de predicciones

Sin predicciones cerradas aún (64 abiertas). Cada predicción se evalúa a su vencimiento en `data/predictions.csv`.

---
_Herramienta de investigación, no asesoría financiera._
