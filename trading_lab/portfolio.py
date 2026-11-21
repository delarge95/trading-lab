"""Muestras históricas CONJUNTAS para simular carteras en el navegador (`docs/cartera.html`).

Para cada horizonte h se eligen fechas t distintas y regulares (desde t >= 252 hasta T-1-h) y, para cada
acción, se guarda z = log(P[t+h] / P[t]) / (sigma_ewma[t] * sqrt(h)): el retorno futuro estandarizado por la
volatilidad conocida en t (sin anticipación). Como todas las acciones comparten las mismas fechas, la matriz
conserva la correlación histórica entre ellas. En el navegador: r_i = exp(sigma_now_i * z_it) - 1 y
cartera = sum(w_i * r_i), con sigma_now = sigma_ewma actual * sqrt(h).

Limitaciones (se declaran en la salida): las ventanas de 63 ruedas se solapan, por lo que el número efectivo de
muestras independientes es mucho menor que n; el universo es el de hoy (sesgo de supervivencia).
Herramienta de investigación, no asesoría financiera.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .forecast import ewma_sigma

MIN_T = 252                  # ruedas mínimas de historia antes de la primera fecha de muestra
MIN_COVER = 0.8              # fracción mínima de fechas con dato para incluir un ticker
SECTORS_PATH = Path(__file__).resolve().parent.parent / "config" / "sectors.yaml"
OTHER = "otro"


def sector_map(path: Path | str | None = None) -> dict[str, str]:
    """Ticker -> sector (11 sectores GICS en español; lo que no está en el mapa se trata como 'otro')."""
    p = Path(path) if path else SECTORS_PATH
    if not p.exists():
        return {}
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    raw = raw.get("sectors", raw)
    return {str(k).upper(): str(v) for k, v in raw.items()}


def sample_dates(T: int, h: int, n: int, min_t: int = MIN_T) -> np.ndarray:
    """Posiciones t distintas, espaciadas de forma regular, con min_t <= t <= T-1-h."""
    last = T - 1 - h
    if last < min_t:
        return np.array([], dtype=int)
    if last - min_t + 1 <= n:
        return np.arange(min_t, last + 1)
    return np.unique(np.round(np.linspace(min_t, last, n)).astype(int))


def _block(P: pd.DataFrame, stocks: list[str], sig: pd.DataFrame, h: int, n: int) -> dict | None:
    idx = sample_dates(len(P), h, n)
    if len(idx) < 20:
        return None
    lp = np.log(P[stocks])
    fwd = (lp.shift(-h) - lp).values[idx, :]
    s = sig[stocks].values[idx, :]
    with np.errstate(divide="ignore", invalid="ignore"):
        z = fwd / (s * math.sqrt(h))
    z[~np.isfinite(z) | (s <= 0)] = np.nan
    now = sig[stocks].iloc[-1].values * math.sqrt(h)
    last_px = P[stocks].iloc[-1].values
    keep = [j for j in range(len(stocks))
            if np.isfinite(z[:, j]).mean() >= MIN_COVER and np.isfinite(now[j]) and now[j] > 0
            and np.isfinite(last_px[j])]
    if not keep:
        return None
    zz = np.nan_to_num(z[:, keep], nan=0.0, posinf=0.0, neginf=0.0)
    zz = np.clip(np.round(zz, 2), -12.0, 12.0) + 0.0            # +0.0 evita "-0.0" en el JSON
    tick = [stocks[j] for j in keep]
    return {
        "tickers": tick,
        "sigma_now": {t: round(float(now[j]), 5) for t, j in zip(tick, keep)},
        "dates": [P.index[i].strftime("%Y-%m-%d") for i in idx],
        "z": zz.tolist(),
    }


def joint_samples(P: pd.DataFrame, stocks: list[str], horizons: tuple[int, ...] = (21, 63),
                  n: int = 400, seed: int = 0) -> dict:
    """Muestras conjuntas estandarizadas por volatilidad: {"h21": {tickers, sigma_now, dates, z}, ...}.

    `seed` se reserva por compatibilidad: la rejilla de fechas es determinista (misma salida siempre).
    """
    stocks = [s for s in stocks if s in P.columns]
    sig = ewma_sigma(P[stocks])
    out: dict = {}
    for h in horizons:
        b = _block(P, stocks, sig, h, n)
        if b is not None:
            out[f"h{h}"] = b
    return out


def build(P: pd.DataFrame, stocks: list[str], horizons: tuple[int, ...] = (21, 63), n: int = 400,
          sectors: dict[str, str] | None = None) -> dict:
    """Bloque `portfolio` del panel: muestras conjuntas + sectores + notas metodológicas."""
    js = joint_samples(P, stocks, horizons, n)
    sec = sectors if sectors is not None else sector_map()
    tickers = sorted({t for b in js.values() for t in b["tickers"]})
    js["sectors"] = {t: sec.get(t, OTHER) for t in tickers}
    js["method"] = ("Muestras históricas conjuntas (mismas fechas para todas las acciones) estandarizadas por la "
                    "volatilidad EWMA conocida en cada fecha; se reescalan con la volatilidad actual.")
    js["caveats"] = [
        "Las ventanas de 3 meses se solapan: hay muchas menos muestras independientes que filas.",
        "Universo de acciones de hoy (sesgo de supervivencia); sin costos, impuestos ni deslizamiento.",
        "El pasado no garantiza el futuro; son rangos estadísticos, no predicciones ni recomendaciones.",
    ]
    return js
