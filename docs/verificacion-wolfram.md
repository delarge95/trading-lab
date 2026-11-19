# Verificación independiente en Wolfram Language (2026-11-19)

Cálculos clave del pipeline repetidos en Wolfram con definiciones independientes (no con la fórmula cerrada del código).
Datos: retornos reales de la estrategia 12-1 sobre SPY (107 períodos de 21 ruedas) y ejemplos sintéticos.

| Cálculo | Python | Wolfram | Diferencia |
|---|---|---|---|
| Wilson 95% (65 de 91): límite inferior | 0.614275 | 0.6142747 (resolviendo `(p̂-p)² = z²·p(1-p)/n`) | < 1e-6 |
| Wilson 95% (65 de 91): límite superior | 0.796938 | 0.7969379 | < 1e-6 |
| Sharpe por período | 0.2427773 | 0.2427784 | 1e-6* |
| Asimetría | -0.555652 | -0.555656 | 4e-6* |
| Curtosis (no exceso) | 5.268052 | 5.268066 | 1e-5* |
| PSR(>0) | 0.9888103 | 0.9888105 | 2e-7* |
| Sharpe anual [IC 95%] | 0.8410 [0.1193, 1.5627] | 0.8410 [0.1193, 1.5627] | < 1e-4* |
| Sharpe máximo esperado (N=100, V=1) | 2.5306028932 | 2.5306028932 | < 1e-12 |
| Holm (8 valores p) | [.008,.12,.15,.6,.16,1,.07,1] | idéntico | 0 |
| p exacto de inversión de signos (8 excesos) | 1/256 = 0.0039063 (enumeración) | 0.00390625 | 0 |
| Años necesarios (TE 6%, alfa 3%, 80% potencia) | 24.7327 → 24.7302 | 24.7302 | corregido: ahora usa cuantiles exactos |

\* Wolfram recibió los retornos redondeados a 6 decimales; la diferencia es solo ese redondeo.

Verificado antes con scipy y statsmodels (Wilson, momentos, PSR, Holm) y con el test analítico de Memmel (bootstrap).
