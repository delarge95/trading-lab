"""Precios diarios ajustados: Yahoo Finance (chart API) con Stooq de respaldo."""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from . import http


def _yahoo(ticker: str, years: int) -> list[tuple[str, float]]:
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
           f"?range={years}y&interval=1d&events=div%2Csplit")
    j = http.get(url).json()
    res = j["chart"]["result"][0]
    ts = res["timestamp"]
    adj = res["indicators"].get("adjclose", [{}])[0].get("adjclose") \
        or res["indicators"]["quote"][0]["close"]
    out = []
    for t, p in zip(ts, adj):
        if p is not None:
            out.append((datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d"), float(p)))
    return out


def _stooq(ticker: str) -> list[tuple[str, float]]:
    sym = ticker.lower().replace("-", ".")
    sym = sym if "." in sym else sym + ".us"
    text = http.get(f"https://stooq.com/q/d/l/?s={sym}&i=d").text
    if not text.lower().startswith("date"):
        raise RuntimeError("Stooq no devolvió datos")
    return [(r["Date"], float(r["Close"])) for r in csv.DictReader(io.StringIO(text)) if r.get("Close")]


def get_prices(ticker: str, years: int = 10) -> tuple[list[tuple[str, float]], str]:
    """Devuelve (serie [(fecha, precio)], fuente). Lanza si ambas fuentes fallan."""
    errors = []
    for name, fn in (("yahoo", lambda: _yahoo(ticker, years)), ("stooq", lambda: _stooq(ticker))):
        try:
            data = fn()
            if len(data) > 30:
                return data, name
            errors.append(f"{name}: pocos datos")
        except Exception as exc:  # noqa: BLE001 - fall through to next source
            errors.append(f"{name}: {exc}")
    raise RuntimeError(f"Sin precios para {ticker}: {'; '.join(errors)}")
