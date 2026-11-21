"""Calendario de eventos próximos: resultados trimestrales, FOMC, vencimiento de opciones y fin de trimestre.

Fuentes (todas públicas, sin clave):
- Resultados trimestrales: calendario de Nasdaq,
  ``https://api.nasdaq.com/api/calendar/earnings?date=AAAA-MM-DD`` (una petición por día hábil, caché por día
  en ``data/raw``). Requiere cabeceras tipo navegador (Origin/Referer). Limitaciones: las fechas lejanas son
  estimadas por la empresa/proveedor y pueden cambiar; cubre acciones de EE. UU. y ADR.
- FOMC: tabla estática (ver ``FOMC_DECISIONS``), copiada del calendario oficial de la Fed.
- Vencimiento mensual de opciones (tercer viernes, o jueves anterior si ese viernes es feriado bursátil) y
  fin de trimestre (último día hábil por fecha de calendario): reglas calculadas, sin red.

``upcoming`` nunca lanza excepción: si la fuente de resultados falla, devuelve igualmente los eventos
estáticos y ``sources["nasdaq_earnings"] = "error: ..."``.
Herramienta de investigación, no asesoría financiera.
"""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path

from . import http

CACHE = Path("data/raw")
EARNINGS_URL = "https://api.nasdaq.com/api/calendar/earnings?date={d}"
NASDAQ_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.nasdaq.com",
    "Referer": "https://www.nasdaq.com/",
}

# Calendario FOMC. Fuente: https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm (verificado el
# 2026-11-19). La fecha de la decisión es el último día de cada reunión. Con proyecciones económicas (SEP):
# mar, jun, sep y dic de 2026. Las fechas de 2027 son tentativas según la propia Fed (se confirman en la
# reunión previa); la reunión del 26-27 de octubre de 2027 figura como "Monetary Policy Strategy Meeting".
FOMC_DECISIONS: list[tuple[str, bool]] = [
    # (fecha de la decisión, con proyecciones económicas)
    ("2026-01-28", False), ("2026-03-18", True), ("2026-04-29", False), ("2026-06-17", True),
    ("2026-07-29", False), ("2026-09-16", True), ("2026-10-28", False), ("2026-12-09", True),
    ("2027-01-27", False), ("2027-03-17", False), ("2027-04-28", False), ("2027-06-09", False),
    ("2027-07-28", False), ("2027-09-15", False), ("2027-10-27", False), ("2027-11-17", False),
]
FOMC_2027_TENTATIVE = True


# --------------------------------------------------------------------------- reglas de calendario
def _as_date(x) -> date:
    if x is None:
        return date.today()
    if isinstance(x, datetime):
        return x.date()
    if isinstance(x, date):
        return x
    return date.fromisoformat(str(x)[:10])


def _easter(year: int) -> date:
    """Domingo de Pascua (algoritmo gregoriano anónimo)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return date(year, month, day)


def _exchange_holidays_on_fridays(year: int) -> set[date]:
    """Feriados bursátiles de EE. UU. que pueden caer en el tercer viernes: Viernes Santo y Juneteenth."""
    hol = {_easter(year) - timedelta(days=2)}
    j = date(year, 6, 19)
    if j.weekday() == 5:
        j = date(year, 6, 18)
    elif j.weekday() == 6:
        j = date(year, 6, 20)
    hol.add(j)
    return hol


def third_friday(year: int, month: int) -> date:
    d = date(year, month, 1)
    first_friday = d + timedelta(days=(4 - d.weekday()) % 7)
    return first_friday + timedelta(days=14)


def monthly_opex(year: int, month: int) -> date:
    """Vencimiento mensual de opciones: tercer viernes; si es feriado bursátil, el jueves anterior."""
    d = third_friday(year, month)
    return d - timedelta(days=1) if d in _exchange_holidays_on_fridays(year) else d


def quarter_end(year: int, q: int) -> date:
    """Último día hábil (lun-vie) del trimestre q (1-4)."""
    last = date(year, 3 * q, 1)
    last = (last.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    while last.weekday() >= 5:
        last -= timedelta(days=1)
    return last


def _business_days(start: date, end: date) -> list[date]:
    out, d = [], start
    while d <= end:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def _key(sym: str) -> str:
    """Clave de comparación entre convenciones de símbolo (BRK-B, BRK.B, BRK/B -> BRKB)."""
    return re.sub(r"[^A-Z0-9]", "", str(sym).upper())


# --------------------------------------------------------------------------- resultados (Nasdaq)
_TIME_LABEL = {"time-pre-market": "antes de la apertura", "time-after-hours": "después del cierre"}


def _earnings_day(d: date, asof: date) -> list[dict]:
    """Filas del calendario de resultados de un día (caché por día de consulta; lanza excepción si falla)."""
    path = CACHE / f"events_earnings_{d.isoformat()}_{asof.isoformat()}.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    r = http.get(EARNINGS_URL.format(d=d.isoformat()), headers=NASDAQ_HEADERS, timeout=20)
    payload = json.loads(r.content.decode("utf-8", "replace"))
    status = (payload.get("status") or {}).get("rCode")
    data = payload.get("data")
    if status not in (None, 200) or not isinstance(data, dict):
        raise ValueError(f"respuesta inesperada (rCode={status})")
    rows = data.get("rows") or []
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rows), encoding="utf-8")
    except OSError:
        pass
    return rows


def _earnings_events(tickers: list[str], today: date, end: date) -> tuple[list[dict], str]:
    wanted = {_key(t): t for t in tickers}
    days = _business_days(today, end)
    events: list[dict] = []
    failed: list[str] = []
    first_err = ""

    def one(d: date):
        try:
            return d, _earnings_day(d, today), None
        except Exception as exc:  # noqa: BLE001 - una fuente caída no debe tumbar el informe
            return d, None, f"{type(exc).__name__}: {exc}"

    with ThreadPoolExecutor(max_workers=4) as ex:
        results = list(ex.map(one, days))
    for d, rows, err in results:
        if err is not None:
            failed.append(d.isoformat())
            first_err = first_err or err
            continue
        for row in rows:
            sym = _key(row.get("symbol", ""))
            if sym not in wanted:
                continue
            t = wanted[sym]
            when = _TIME_LABEL.get(row.get("time") or "")
            fq = (row.get("fiscalQuarterEnding") or "").strip()
            label = f"Resultados trimestrales de {t}"
            if fq:
                label += f" (trimestre {fq})"
            if when:
                label += f", {when}"
            events.append({"date": d.isoformat(), "kind": "earnings", "ticker": t, "label": label,
                           "days_to": (d - today).days, "time": when})
    if not days:
        return events, "ok"
    if len(failed) == len(days):
        return events, f"error: {first_err[:200]}"
    if failed:
        return events, f"error: {len(failed)}/{len(days)} días sin datos ({', '.join(failed[:5])}...); {first_err[:120]}"
    return events, "ok"


# --------------------------------------------------------------------------- estáticos
def _static_events(today: date, end: date) -> list[dict]:
    out: list[dict] = []

    def add(d: date, kind: str, label: str):
        if today <= d <= end:
            out.append({"date": d.isoformat(), "kind": kind, "ticker": None, "label": label,
                        "days_to": (d - today).days, "time": None})

    for iso, sep in FOMC_DECISIONS:
        d = date.fromisoformat(iso)
        label = "Decisión de política monetaria de la Fed (FOMC)"
        if sep:
            label += " con proyecciones económicas"
        if d.year >= 2027 and FOMC_2027_TENTATIVE:
            label += " [fecha tentativa]"
        add(d, "fomc", label)
    for year in range(today.year, end.year + 1):
        for month in range(1, 13):
            d = monthly_opex(year, month)
            tf = third_friday(year, month)
            quarterly = month in (3, 6, 9, 12)
            label = ("Vencimiento trimestral de opciones y futuros (triple witching)" if quarterly
                     else "Vencimiento mensual de opciones")
            if d != tf:
                label += " (jueves por feriado bursátil)"
            add(d, "opex", label)
        for q in range(1, 5):
            add(quarter_end(year, q), "quarter_end", f"Fin de trimestre (T{q} {year}, último día hábil)")
    return out


def upcoming(tickers, today=None, days: int = 30) -> dict:
    """Eventos de los próximos ``days`` días. Esquema en docs/contratos-datos.md (sección 5)."""
    today = _as_date(today)
    end = today + timedelta(days=int(days))
    tickers = [str(t).upper() for t in (tickers or [])]
    sources: dict[str, str] = {}
    events = _static_events(today, end)
    last_year = max(y for y in (int(i[:4]) for i, _ in FOMC_DECISIONS))
    sources["fomc"] = ("ok (calendario oficial de la Fed 2026-2027; 2027 tentativo)" if end.year <= last_year
                       else f"error: tabla FOMC solo llega a {last_year}")
    sources["opex_quarter_end"] = "ok (reglas de calendario)"
    if tickers:
        try:
            earn, status = _earnings_events(tickers, today, end)
            events += earn
            sources["nasdaq_earnings"] = status
        except Exception as exc:  # noqa: BLE001
            sources["nasdaq_earnings"] = f"error: {type(exc).__name__}: {exc}"[:240]
    else:
        sources["nasdaq_earnings"] = "ok (sin tickers solicitados)"
    order = {"fomc": 0, "earnings": 1, "opex": 2, "quarter_end": 3}
    events.sort(key=lambda e: (e["date"], order.get(e["kind"], 9), e["ticker"] or ""))
    return {"asof": today.isoformat(), "events": events, "sources": sources}
