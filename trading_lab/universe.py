"""Carga del universo de acciones y de sus precios (caché diaria en data/raw)."""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import yaml

from . import prices as pr

CACHE = Path("data/raw")


def load_config(path: Path = Path("config/universe.yaml")) -> dict:
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    cfg["tickers"] = list(dict.fromkeys(t.upper() for t in cfg["tickers"]))
    return cfg


def _one(ticker: str, years: int, stamp: str) -> tuple[str, list[tuple[str, float]] | None]:
    path = CACHE / f"pxu_{ticker}_{stamp}.json"
    fail = CACHE / f"pxu_{ticker}_{stamp}.fail"      # caché negativa: no reintentar en cada corrida del día
    try:
        if path.exists():
            return ticker, [tuple(x) for x in json.loads(path.read_text())]
        if fail.exists():
            return ticker, None
        series, _ = pr.get_prices(ticker, years)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(series))
        return ticker, series
    except Exception:  # noqa: BLE001 - un ticker sin datos no debe tumbar el universo
        try:
            fail.parent.mkdir(parents=True, exist_ok=True)
            fail.write_text("")
        except OSError:
            pass
        return ticker, None


def load_prices(tickers: list[str], years: int = 11, today: date | None = None,
                workers: int = 4) -> tuple[dict[str, list[tuple[str, float]]], list[str]]:
    """Precios por ticker y lista de tickers que fallaron. Caché por día."""
    stamp = (today or date.today()).isoformat()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(lambda t: _one(t, years, stamp), tickers))
    ok = {t: s for t, s in results if s and len(s) > 300}
    return ok, [t for t, s in results if not s or len(s) <= 300]
