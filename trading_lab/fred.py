"""Series macro de FRED vía CSV público (sin API key)."""
from __future__ import annotations

import csv
import io
from datetime import date

from . import http

SERIES = {
    "DGS10": "Tasa Treasury 10 años (%)",
    "DGS2": "Tasa Treasury 2 años (%)",
    "T10Y2Y": "Pendiente curva 10a-2a (pp)",
    "VIXCLS": "VIX",
    "BAMLH0A0HYM2": "Spread high yield (pp)",
}


def get_series(series_id: str, years: int = 3) -> list[tuple[str, float]]:
    # cosd limita la descarga: el historial completo es grande y FRED a veces tarda más de 30 s
    start = date.today().replace(day=1, year=date.today().year - years).isoformat()
    text = http.get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}&cosd={start}",
                    headers={"User-Agent": "python-requests/2"},  # FRED cuelga con UA tipo navegador
                    timeout=20, retries=2).text
    out = []
    for row in csv.DictReader(io.StringIO(text)):
        v = row.get(series_id, "")
        if v not in ("", "."):
            out.append((row["observation_date"] if "observation_date" in row else row["DATE"], float(v)))
    return out


def snapshot() -> dict:
    """Último valor y valor de hace ~21 observaciones para cada serie."""
    snap = {}
    for sid, label in SERIES.items():
        try:
            s = get_series(sid)
            last = s[-1]
            prev = s[-22] if len(s) > 22 else s[0]
            snap[sid] = {"label": label, "date": last[0], "value": last[1], "change_21": round(last[1] - prev[1], 3)}
        except Exception as exc:  # noqa: BLE001
            snap[sid] = {"label": label, "error": str(exc)}
    return snap
