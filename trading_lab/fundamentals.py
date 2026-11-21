"""Fundamentales desde los datos XBRL públicos de la SEC (companyfacts), con disciplina de punto en el tiempo.

Fuente: https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json. Cada hecho trae `start`, `end`, `val`,
`fy`, `fp`, `form` y `filed` (fecha de presentación). Decisiones:

- Solo se usan hechos de formularios 10-K/10-Q (y sus enmiendas): los demás formularios (DEF 14A, 8-K) repiten cifras.
- Punto en el tiempo: cada cifra solo existe desde su fecha `filed`. Una misma cifra (mismo `start`/`end`) se repite en
  presentaciones posteriores (comparativos, reexpresiones): en la fecha D vale la presentada más recientemente <= D.
- Flujos (ingresos, resultados, caja): en 10-Q vienen como trimestre aislado Y/O acumulado del año (YTD de 6 y 9 meses)
  y en 10-K solo el año completo. El trimestre aislado se toma directo (período de ~90 días) o se reconstruye
  restando acumulados consecutivos con el mismo `start` (H1-Q1, 9M-H1, FY-9M). Si faltan piezas, el trimestre no existe.
- TTM = suma de los últimos 4 trimestres consecutivos (separados 75-110 días); un hueco da None. Los márgenes usan
  exactamente los mismos 4 trimestres que los ingresos. El crecimiento interanual compara el TTM con el TTM de 4
  trimestres antes (necesita 8 trimestres consecutivos).
- Etiquetas alternativas: por trimestre se usa la primera etiqueta disponible en orden de prioridad, de modo que un
  cambio de etiqueta de la empresa (p. ej. SalesRevenueNet -> RevenueFromContractWithCustomer...) no rompe la serie.
- Balance (instantáneas): deuda y patrimonio a la última fecha de balance conocida. Deuda = total combinado si existe;
  si no, no corriente + corriente (+ papel comercial / préstamos de corto plazo); si no, LongTermDebt. Una empresa sin
  ninguna etiqueta de deuda da None (no 0: no se puede distinguir "sin deuda" de "no reportada"). Patrimonio <= 0 da
  None en deuda/patrimonio (el cociente no es interpretable).
- Acciones: promedio ponderado diluido (o básico) del último período contra el período de la MISMA duración que
  terminó ~1 año antes (así no se mezclan trimestres con acumulados); respaldo: acciones en circulación de la portada
  (dei:EntityCommonStockSharesOutstanding).
- Un dato desactualizado (último período a más de MAX_STALE_DAYS de la fecha de cálculo) da None.
Limitaciones: la clasificación contable varía por empresa (bancos y aseguradoras casi no tienen OperatingIncomeLoss ni
deuda comparable) y las empresas con etiquetas personalizadas quedan con None.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from datetime import date
from pathlib import Path

import pandas as pd

from . import http, sec

URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
FORMS = {"10-K", "10-K/A", "10-KT", "10-KT/A", "10-Q", "10-Q/A", "10-QT"}
MAX_STALE_DAYS = 200          # último período más viejo que esto -> None
Q_MIN, Q_MAX = 75, 120        # separación válida (días) entre cierres de trimestres consecutivos (120: el 4.º trimestre de
                              # calendarios 4-4-5/16 semanas, p. ej. COST y PEP, dura 112 días)

FLOW_TAGS = {
    "revenue": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
                "RevenueFromContractWithCustomerIncludingAssessedTax", "SalesRevenueNet",
                "SalesRevenueGoodsNet", "SalesRevenueServicesNet", "RevenuesNetOfInterestExpense",
                "RegulatedAndUnregulatedOperatingRevenue"],
    "op_income": ["OperatingIncomeLoss"],
    "net_income": ["NetIncomeLoss", "ProfitLoss", "NetIncomeLossAvailableToCommonStockholdersBasic"],
    "cfo": ["NetCashProvidedByUsedInOperatingActivities",
            "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets",
              "PaymentsForCapitalImprovements"],
}
EQUITY_TAGS = ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"]
DEBT_TAGS = ["DebtLongtermAndShorttermCombinedAmount", "DebtAndCapitalLeaseObligations", "LongTermDebtNoncurrent",
             "LongTermDebtAndCapitalLeaseObligations", "LongTermDebtCurrent", "DebtCurrent",
             "LongTermDebtAndCapitalLeaseObligationsCurrent", "ShortTermBorrowings", "CommercialPaper", "LongTermDebt"]
SHARE_TAGS = ["WeightedAverageNumberOfDilutedSharesOutstanding", "WeightedAverageNumberOfSharesOutstandingBasic"]
DEI_SHARES = "dei:EntityCommonStockSharesOutstanding"

_SHARE_UNIT = set(SHARE_TAGS) | {DEI_SHARES}
_ALL_TAGS = ([t for v in FLOW_TAGS.values() for t in v] + EQUITY_TAGS + DEBT_TAGS + SHARE_TAGS)
COLUMNS = ["revenue_ttm", "rev_growth_yoy", "op_margin_ttm", "net_margin_ttm", "fcf_margin_ttm",
           "debt_to_equity", "shares_chg_yoy", "period_end"]


# ------------------------------------------------------------------ extracción
def parse_companyfacts(j: dict) -> dict:
    """JSON de companyfacts -> estructura compacta {tag: [[start|None, end, val, filed], ...]} (solo 10-K/10-Q)."""
    out: dict[str, list] = {}
    gaap = j.get("facts", {}).get("us-gaap", {})
    sources = [(t, gaap.get(t)) for t in _ALL_TAGS] + [(DEI_SHARES, j.get("facts", {}).get("dei", {})
                                                         .get("EntityCommonStockSharesOutstanding"))]
    for tag, node in sources:
        if not node:
            continue
        units = node.get("units", {})
        rows = units.get("shares" if tag in _SHARE_UNIT else "USD")
        if not rows:
            continue
        seen = set()
        for f in rows:
            if f.get("form") not in FORMS or f.get("val") is None or not f.get("end") or not f.get("filed"):
                continue
            key = (f.get("start"), f["end"], f["val"], f["filed"])
            if key in seen:
                continue
            seen.add(key)
        if seen:
            out[tag] = [list(k) for k in sorted(seen, key=lambda k: (k[3], k[1], k[0] or ""))]
    return {"name": j.get("entityName"), "cik": j.get("cik"), "facts": out}


def _d(s: str | None) -> date | None:
    return date.fromisoformat(s[:10]) if s else None


def _num(x) -> float | None:
    if x is None:
        return None
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


# ------------------------------------------------------------------ trimestres aislados y TTM
def _cum_class(days: int) -> int | None:
    """1=trimestre, 2=6 meses acumulados, 3=9 meses, 4=año completo; None si no encaja."""
    if 75 <= days <= 105:
        return 1
    if 160 <= days <= 200:
        return 2
    if 250 <= days <= 295:
        return 3
    if 340 <= days <= 380:
        return 4
    return None


def isolated_quarters(known: dict[tuple, float]) -> dict[date, float]:
    """Trimestres aislados {fecha de cierre: valor} desde hechos {(start, end): val} de una etiqueta de flujo.

    Directo si hay un período de ~90 días; si no, diferencia de acumulados con el mismo `start`
    (H1-Q1, 9M-H1, FY-9M). Nunca se mezclan acumulados con distinto inicio de año fiscal.
    """
    q: dict[date, float] = {}
    by_start: dict[date, dict[int, list[tuple[date, float]]]] = defaultdict(lambda: defaultdict(list))
    for (s, e), v in known.items():
        if s is None:
            continue
        c = _cum_class((e - s).days)
        if c is None:
            continue
        by_start[s][c].append((e, v))
        if c == 1:
            q[e] = v
    for s, cls in by_start.items():
        for c in (2, 3, 4):
            for e, v in cls.get(c, []):
                if e in q:
                    continue
                for e0, v0 in cls.get(c - 1, []):
                    if Q_MIN <= (e - e0).days <= Q_MAX:
                        q[e] = v - v0
                        break
    return q


def _merge_quarters(known_by_tag: dict[str, dict], tags: list[str]) -> dict[date, float]:
    """Trimestres aislados combinando etiquetas alternativas (prioridad por orden)."""
    out: dict[date, float] = {}
    for t in tags:
        for e, v in isolated_quarters(known_by_tag.get(t, {})).items():
            out.setdefault(e, v)
    return out


def _chain(q: dict[date, float], n: int, asof: date) -> list[date] | None:
    """Cierres de los últimos n trimestres consecutivos (más reciente primero) o None si hay hueco/dato viejo."""
    if not q:
        return None
    ends = sorted(q)
    if (asof - ends[-1]).days > MAX_STALE_DAYS:
        return None
    out = [ends[-1]]
    for e in reversed(ends[:-1]):
        gap = (out[-1] - e).days
        if gap < Q_MIN:
            continue                       # cierre alterno casi duplicado
        if gap > Q_MAX:
            break                          # hueco
        out.append(e)
        if len(out) == n:
            return out
    return out if len(out) == n else None


def _get(q: dict[date, float], e: date, tol: int = 5) -> float | None:
    if e in q:
        return q[e]
    for k, v in q.items():
        if abs((k - e).days) <= tol:
            return v
    return None


def _sum_over(q: dict[date, float], ends: list[date]) -> float | None:
    vals = [_get(q, e) for e in ends]
    return None if any(v is None for v in vals) else float(sum(vals))


# ------------------------------------------------------------------ balance y acciones
def _instants(known: dict[tuple, float]) -> dict[date, float]:
    return {e: v for (s, e), v in known.items() if s is None}


def _merge_instants(known_by_tag: dict[str, dict], tags: list[str]) -> dict[date, float]:
    out: dict[date, float] = {}
    for t in tags:
        for e, v in _instants(known_by_tag.get(t, {})).items():
            out.setdefault(e, v)
    return out


def _debt_at(known_by_tag: dict[str, dict], e: date) -> float | None:
    def g(tag: str) -> float | None:
        return _instants(known_by_tag.get(tag, {})).get(e)

    for tag in ("DebtLongtermAndShorttermCombinedAmount", "DebtAndCapitalLeaseObligations"):
        if g(tag) is not None:
            return g(tag)
    nc = next((g(t) for t in ("LongTermDebtNoncurrent", "LongTermDebtAndCapitalLeaseObligations") if g(t) is not None), None)
    if nc is not None:
        if g("DebtCurrent") is not None:
            cur = g("DebtCurrent")
        else:
            cur = next((g(t) for t in ("LongTermDebtCurrent", "LongTermDebtAndCapitalLeaseObligationsCurrent")
                        if g(t) is not None), 0.0)
            cur += g("ShortTermBorrowings") if g("ShortTermBorrowings") is not None else (g("CommercialPaper") or 0.0)
        return nc + cur
    return g("LongTermDebt")


def _shares_change(known_by_tag: dict[str, dict], asof: date) -> float | None:
    for tag in SHARE_TAGS:
        recs = [(s, e, v) for (s, e), v in known_by_tag.get(tag, {}).items()
                if s is not None and 0 < (e - s).days <= 380 and v > 0]
        if not recs:
            continue
        last_end = max(e for _, e, _ in recs)
        if (asof - last_end).days > MAX_STALE_DAYS:
            continue
        s, e, v = min((r for r in recs if r[1] == last_end), key=lambda r: (r[1] - r[0]).days)
        dur = (e - s).days
        prior = [(abs((e2 - e).days + 365), v2) for s2, e2, v2 in recs
                 if abs((e2 - e).days + 365) <= 25 and abs((e2 - s2).days - dur) <= 20]
        if prior:
            return v / min(prior)[1] - 1
    inst = _instants(known_by_tag.get(DEI_SHARES, {}))
    if inst:
        e = max(inst)
        if (asof - e).days <= MAX_STALE_DAYS:
            prior = [(abs((e2 - e).days + 365), v2) for e2, v2 in inst.items() if abs((e2 - e).days + 365) <= 45 and v2 > 0]
            if prior and inst[e] > 0:
                return inst[e] / min(prior)[1] - 1
    return None


def _pick_revenue(known_by_tag: dict[str, dict], asof: date):
    """Serie de ingresos trimestrales: la etiqueta con el dato más reciente (y con 8 trimestres si es posible).

    Se evalúa cada etiqueta por separado (mezclar etiquetas parciales rompe la cadena de trimestres, p. ej. COST con
    `Revenues` y `RevenueFromContract...`) y, como último recurso, la combinación por trimestre (cambio de etiqueta).
    Criterio: cierre más reciente, luego 8 trimestres disponibles, luego orden de prioridad.
    """
    tags = FLOW_TAGS["revenue"]
    cands = [(isolated_quarters(known_by_tag.get(t, {})), len(tags) - i) for i, t in enumerate(tags)]
    cands.append((_merge_quarters(known_by_tag, tags), 0))
    best, best_key = ({}, None, None), None
    for q, pr in cands:
        c8 = _chain(q, 8, asof)
        c4 = c8[:4] if c8 else _chain(q, 4, asof)
        if not c4:
            continue
        key = (c4[0], c8 is not None, pr)
        if best_key is None or key > best_key:
            best, best_key = (q, c8, c4), key
    return best


# ------------------------------------------------------------------ métricas en una fecha
def compute_metrics(known_by_tag: dict[str, dict], asof: date) -> dict:
    """Métricas con los hechos conocidos en `asof` ({tag: {(start, end): val}})."""
    m: dict = {c: None for c in COLUMNS}
    rev_q, chain8, chain4 = _pick_revenue(known_by_tag, asof)
    if chain4:
        rev = _sum_over(rev_q, chain4)
        m["period_end"] = chain4[0]
        m["revenue_ttm"] = rev
        if chain8 and rev is not None:
            prev = _sum_over(rev_q, chain8[4:])
            if prev is not None and prev > 0:
                m["rev_growth_yoy"] = rev / prev - 1
        if rev is not None and rev > 0:
            for key, col in (("op_income", "op_margin_ttm"), ("net_income", "net_margin_ttm")):
                v = _sum_over(_merge_quarters(known_by_tag, FLOW_TAGS[key]), chain4)
                if v is not None:
                    m[col] = v / rev
            cfo = _sum_over(_merge_quarters(known_by_tag, FLOW_TAGS["cfo"]), chain4)
            capex = _sum_over(_merge_quarters(known_by_tag, FLOW_TAGS["capex"]), chain4)
            if cfo is not None and capex is not None:
                m["fcf_margin_ttm"] = (cfo - abs(capex)) / rev
    eq = _merge_instants(known_by_tag, EQUITY_TAGS)
    if eq:
        e = max(eq)
        if (asof - e).days <= MAX_STALE_DAYS and eq[e] > 0:
            debt = _debt_at(known_by_tag, e)
            if debt is not None and debt >= 0:
                m["debt_to_equity"] = debt / eq[e]
    m["shares_chg_yoy"] = _shares_change(known_by_tag, asof)
    return {k: (v if k == "period_end" else _num(v)) for k, v in m.items()}


def _replay(facts: dict[str, list], at: date | None = None) -> list[tuple[date, dict]]:
    """Reproduce las presentaciones en orden cronológico y calcula las métricas tras cada una (o solo la última <= at).

    Tras cada fecha de presentación solo se conocen los hechos con filed <= esa fecha: sin anticipación.
    """
    events: list[tuple[date, str, date | None, date, float]] = []
    for tag, rows in facts.items():
        for s, e, v, f in rows:
            events.append((_d(f), tag, _d(s), _d(e), float(v)))
    events.sort(key=lambda x: x[0])
    known: dict[str, dict] = defaultdict(dict)
    out: list[tuple[date, dict]] = []
    i, n = 0, len(events)
    while i < n:
        d = events[i][0]
        if at is not None and d > at:
            break
        while i < n and events[i][0] == d:
            _, tag, s, e, v = events[i]
            known[tag][(s, e)] = v           # el más reciente por (start, end) sobrescribe: reexpresiones
            i += 1
        if at is None or i >= n or events[i][0] > at:
            out.append((d, compute_metrics(known, d if at is None else at)))
    return out


def history_from_facts(compact: dict) -> pd.DataFrame:
    """DataFrame de métricas indexado por fecha de PRESENTACIÓN (cada valor solo disponible desde que se hizo público)."""
    rows = _replay(compact.get("facts", {}))
    if not rows:
        return pd.DataFrame(columns=COLUMNS, index=pd.DatetimeIndex([], name="filed"))
    df = pd.DataFrame([r for _, r in rows], index=pd.DatetimeIndex([pd.Timestamp(d) for d, _ in rows], name="filed"))
    df["period_end"] = pd.to_datetime(df["period_end"])
    return df[~df.index.duplicated(keep="last")][COLUMNS]


def snapshot_from_facts(compact: dict, today: date) -> dict:
    """Métricas más recientes conocidas a `today` (dict del contrato) o None si no hay presentaciones."""
    rows = _replay(compact.get("facts", {}), at=today)
    if not rows:
        return {}
    filed, m = rows[-1]
    out = {k: m[k] for k in COLUMNS if k != "period_end"}
    out["period_end"] = m["period_end"].isoformat() if m["period_end"] else None
    out["filed"] = filed.isoformat()
    return out


# ------------------------------------------------------------------ descarga con caché por día
def _cache_dir() -> Path:
    return Path(http.CACHE_DIR)


def _cik_for(ticker: str, cik_map: dict[str, int]) -> int | None:
    for t in (ticker, ticker.replace("-", "."), ticker.replace(".", "-")):
        if t.upper() in cik_map:
            return cik_map[t.upper()]
    return None


def load_facts(ticker: str, today: date | None = None, cik_map: dict[str, int] | None = None) -> dict | None:
    """Hechos compactos de un ticker (caché por día en data/raw); None si no existe o falla la descarga."""
    ticker = ticker.upper()
    stamp = (today or date.today()).isoformat()
    cdir = _cache_dir()
    path = cdir / f"fund_{ticker}_{stamp}.json"
    fail = cdir / f"fund_{ticker}_{stamp}.fail"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    if fail.exists():
        return None
    try:
        cik_map = cik_map if cik_map is not None else sec.ticker_to_cik()
        cik = _cik_for(ticker, cik_map)
        if cik is None:
            cdir.mkdir(parents=True, exist_ok=True)
            fail.write_text("", encoding="utf-8")          # no está en el mapa de la SEC: no reintentar hoy
            return None
        compact = parse_companyfacts(http.get(URL.format(cik=cik), timeout=60).json())
    except Exception:  # noqa: BLE001 - un ticker con falla de red no debe tumbar el lote
        return None
    cdir.mkdir(parents=True, exist_ok=True)
    for old in cdir.glob(f"fund_{ticker}_*.json"):         # no acumular días viejos
        old.unlink(missing_ok=True)
    path.write_text(json.dumps(compact), encoding="utf-8")
    return compact


def history(ticker: str, today: date | None = None, cik_map: dict[str, int] | None = None) -> pd.DataFrame:
    """Métricas por fecha de presentación (sin anticipación). DataFrame vacío si no hay datos."""
    compact = load_facts(ticker, today, cik_map)
    if not compact:
        return pd.DataFrame(columns=COLUMNS, index=pd.DatetimeIndex([], name="filed"))
    return history_from_facts(compact)


def snapshot(tickers: list[str], today: date | None = None) -> dict:
    """Fundamentales actuales por ticker (contrato `fundamentals.snapshot`). Tolera fallos por ticker.

    Rápido: los hechos se cachean por ticker y día, y el resultado completo por lote y día (data/raw/fsnap-*).
    Un fallo de red no se cachea (se reintenta); un ticker ausente del mapa de la SEC sí.
    """
    today = today or date.today()
    tks = list(dict.fromkeys(x.upper() for x in tickers))
    cdir = _cache_dir()
    snap_path = cdir / f"fsnap-{hashlib.sha1(','.join(sorted(tks)).encode()).hexdigest()[:12]}_{today.isoformat()}.json"
    if snap_path.exists():
        try:
            return json.loads(snap_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    try:
        cik_map = sec.ticker_to_cik()
    except Exception:  # noqa: BLE001
        cik_map = {}
    res: dict[str, dict] = {}
    failed: list[str] = []
    for t in tks:
        try:
            compact = load_facts(t, today, cik_map)
            s = snapshot_from_facts(compact, today) if compact else {}
        except Exception:  # noqa: BLE001
            s = {}
        if s:
            res[t] = s
        else:
            failed.append(t)
    cov = sum(1 for s in res.values() if any(s.get(c) is not None for c in COLUMNS if c != "period_end"))
    out = {"asof": today.isoformat(), "coverage": cov, "tickers": res, "failed": failed}
    permanent = all((cdir / f"fund_{t}_{today.isoformat()}.fail").exists() or t in res or
                    (compact_ok(cdir, t, today)) for t in failed)
    if cik_map and permanent:
        cdir.mkdir(parents=True, exist_ok=True)
        snap_path.write_text(json.dumps(out), encoding="utf-8")
    return out


def compact_ok(cdir: Path, t: str, today: date) -> bool:
    """Hay hechos en caché pero sin presentaciones utilizables (no es un fallo transitorio)."""
    return (cdir / f"fund_{t}_{today.isoformat()}.json").exists()
