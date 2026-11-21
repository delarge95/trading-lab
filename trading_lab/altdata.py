"""Recolectores de fuentes alternativas (todas públicas, sin clave) para pruebas FUTURAS de señales.

IMPORTANTE: ninguna de estas fuentes entrega historia útil para un backtest (son fotos del día); la foto se
guarda cada día en ``data/alt/AAAA-MM-DD.json`` y solo sirve para evaluar hacia adelante (``load_history``).
Hasta acumular meses de fotos no hay evidencia de que alguna agregue información sobre la tasa base.

Fuentes, URL y limitaciones (verificadas con peticiones reales el 2026-11-19):

1. ``iv`` - volatilidad implícita ATM a 30 días y sesgo put-call.
   ``https://api.nasdaq.com/api/quote/{T}/option-chain?assetclass=stocks&limit=5000&fromdate=..&todate=..
   &excode=oprac&callput=callput&money=all&type=all`` (cadena compuesta, bid/ask/volumen/interés abierto).
   El candidato ``cdn.cboe.com/api/global/delayed_quotes/options/{T}.json`` (trae IV por contrato) devolvió
   403 de Cloudflare desde la máquina de pruebas, por eso NO se usa. Nasdaq no entrega IV: se calcula aquí.
   Método: por vencimiento, forward por paridad put-call con los strikes más cercanos al spot (absorbe tasa y
   dividendos), IV de Black-76 invertida del punto medio bid/ask de la opción fuera del dinero en los dos
   strikes que rodean el forward, interpolación lineal en strike; luego interpolación lineal de la varianza
   total entre el último vencimiento <= 30 días (>= 7) y el primero > 30. Sin vencimiento a cada lado, ``iv30``
   es None. Sesgo put-call = volumen (o interés abierto) de puts / calls sumado hasta ``PC_WINDOW_DAYS``.
   Limitaciones: datos con ~15 min de retraso o del último cierre; puntos medios con spreads anchos en
   acciones ilíquidas; tasa libre de riesgo fija (``RISK_FREE``); ejercicio americano ignorado (efecto
   pequeño en ATM de acciones sin dividendos grandes); sin historia.
2. ``short_interest`` - interés corto (FINRA, publicación quincenal, TODAS las bolsas).
   ``https://cdn.finra.org/equity/otcmarket/biweekly/shrt{AAAAMMDD}.csv`` (fecha de liquidación: día 15 y
   fin de mes, o día hábil anterior). Se busca el archivo más reciente publicado. Coincide al dígito con el
   endpoint de Nasdaq para AAPL, pero ese endpoint (``/quote/{T}/short-interest``) solo cubre acciones
   listadas en Nasdaq (no NYSE: XOM o JPM devuelven "not available"), por eso se usa FINRA.
   Limitaciones: ~7 días hábiles de retraso sobre la liquidación; frecuencia quincenal.
3. ``short_volume`` - volumen de ventas en corto diario (FINRA Reg SHO, ``cdn.finra.org/equity/regsho/daily/
   CNMSshvol{AAAAMMDD}.txt``): volumen vendido en corto / volumen total del día. NO es interés corto (la
   mayor parte son creadores de mercado). Publicado al cierre del mismo día; se usa el último día disponible.
4. ``analysts`` - consenso de analistas (Nasdaq/Zacks): ``/api/analyst/{T}/targetprice`` (precio objetivo
   medio/mín/máx y número de compra/mantener/venta), ``/api/analyst/{T}/ratings`` (recomendación media) y
   ``/api/analyst/{T}/earnings-forecast`` (EPS consenso del próximo trimestre, número de estimaciones y
   revisiones al alza/baja en 4 semanas). Limitaciones: la historia que devuelve es solo mensual y de
   consenso agregado; algunos emisores (p. ej. BRK.B) no tienen cobertura; si falla una de las tres
   llamadas se guardan las otras y se anota ``partial_errors``.

Convenciones: ``collect_one`` nunca lanza excepción (cada fuente fallida queda como ``{"error": ...}``);
``collect`` es idempotente (una segunda corrida el mismo día solo reintenta las fuentes con error);
``load_history`` devuelve un DataFrame largo (date, ticker, campo, valor) solo con valores numéricos.
Herramienta de investigación, no asesoría financiera.
"""
from __future__ import annotations

import csv
import io
import json
import math
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

from . import http

NASDAQ_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.nasdaq.com",
    "Referer": "https://www.nasdaq.com/",
}
RISK_FREE = 0.04            # tasa continua aproximada; solo afecta el factor de descuento (efecto < 0,5% del precio)
PC_WINDOW_DAYS = 60         # vencimientos incluidos en el sesgo put-call
CHAIN_WINDOW_DAYS = 75      # ventana pedida a la cadena de opciones (debe rodear los 30 días)
MIN_DAYS_IV = 7             # no interpolar con vencimientos de menos de una semana (ruido de gamma)
TARGET_DAYS = 30
SOURCES = ("iv", "short_interest", "short_volume", "analysts")
FINRA_SI_URL = "https://cdn.finra.org/equity/otcmarket/biweekly/shrt{d}.csv"
FINRA_SV_URL = "https://cdn.finra.org/equity/regsho/daily/CNMSshvol{d}.txt"

_throttle_lock = threading.Lock()
_next_slot = [0.0]
_PAUSE = [0.2]
_memo: dict = {}
_memo_lock = threading.Lock()


# --------------------------------------------------------------------------- utilidades
def _as_date(x) -> date:
    if x is None:
        return date.today()
    if isinstance(x, datetime):
        return x.date()
    if isinstance(x, date):
        return x
    return date.fromisoformat(str(x)[:10])


def _err(exc: Exception) -> dict:
    return {"error": f"{type(exc).__name__}: {exc}"[:240]}


def _num(x):
    """'1,234' / '$12.5' / '--' -> float o None."""
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x) if math.isfinite(x) else None
    s = str(x).strip().replace(",", "").replace("$", "")
    if s in ("", "--", "N/A", "NA", "n/a"):
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    return v if math.isfinite(v) else None


def _round(x, nd=6):
    return None if x is None else round(float(x), nd)


def _nasdaq_sym(t: str) -> str:
    return t.upper().replace("-", ".")


def _nasdaq_json(url: str) -> dict:
    """GET a api.nasdaq.com con espaciado global entre peticiones; devuelve ``data`` (lanza si no hay)."""
    with _throttle_lock:
        now = time.time()
        wait = _next_slot[0] - now
        _next_slot[0] = max(now, _next_slot[0]) + _PAUSE[0]
    if wait > 0:
        time.sleep(wait)
    for attempt in range(5):
        r = http.get(url, headers=NASDAQ_HEADERS, timeout=25)
        payload = json.loads(r.content.decode("utf-8", "replace"))
        data = payload.get("data")
        if isinstance(data, dict):
            return data
        st = payload.get("status") or {}
        msgs = st.get("bCodeMessage") or []
        code = msgs[0].get("code") if msgs and isinstance(msgs[0], dict) else None
        if code == 3004 and attempt < 4:      # "Error while calling vendor": falla transitoria de Nasdaq
            time.sleep(1.0 + attempt)  # 1, 2, 3, 4 s
            continue
        first = msgs[0].get("errorMessage") if msgs and isinstance(msgs[0], dict) else None
        raise ValueError(str(first or payload.get("message") or f"rCode={st.get('rCode')}"))
    raise ValueError("respuesta vacía")


# --------------------------------------------------------------------------- 1. volatilidad implícita
def _ncdf(x: float) -> float:
    return 0.5 * math.erfc(-x / math.sqrt(2.0))


def black76(F: float, K: float, T: float, sigma: float, df: float, is_call: bool) -> float:
    """Precio de Black-76 (opción europea sobre forward) con factor de descuento ``df``."""
    if T <= 0 or sigma <= 0:
        return df * max(F - K, 0.0) if is_call else df * max(K - F, 0.0)
    sd = sigma * math.sqrt(T)
    d1 = (math.log(F / K) + 0.5 * sd * sd) / sd
    d2 = d1 - sd
    if is_call:
        return df * (F * _ncdf(d1) - K * _ncdf(d2))
    return df * (K * _ncdf(-d2) - F * _ncdf(-d1))


def implied_vol(price: float, F: float, K: float, T: float, df: float, is_call: bool) -> float | None:
    """IV por bisección; None si el precio está fuera de los límites sin arbitraje."""
    if price is None or price <= 0 or F <= 0 or K <= 0 or T <= 0:
        return None
    lo_p = black76(F, K, T, 1e-6, df, is_call)
    hi_p = black76(F, K, T, 5.0, df, is_call)
    if not (lo_p < price < hi_p):
        return None
    lo, hi = 1e-6, 5.0
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if black76(F, K, T, mid, df, is_call) < price:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-7:
            break
    return 0.5 * (lo + hi)


def parse_chain(data: dict, today: date) -> tuple[list[dict], float | None]:
    """Respuesta de option-chain de Nasdaq -> (vencimientos, spot).

    Cada vencimiento: {"expiry": date, "days": int, "rows": [{"K","cb","ca","pb","pa","cv","pv","coi","poi"}]}.
    """
    table = (data or {}).get("table") or {}
    rows = table.get("rows") or []
    spot = None
    m = re.search(r"\$\s*([\d,]+\.?\d*)", str(data.get("lastTrade") or ""))
    if m:
        spot = _num(m.group(1))
    out: list[dict] = []
    cur: dict | None = None
    for row in rows:
        grp = (row.get("expirygroup") or "").strip()
        if grp:
            try:
                exp = datetime.strptime(grp, "%B %d, %Y").date()
            except ValueError:
                cur = None
                continue
            cur = {"expiry": exp, "days": (exp - today).days, "rows": []}
            out.append(cur)
            continue
        K = _num(row.get("strike"))
        if cur is None or K is None:
            continue
        cur["rows"].append({
            "K": K, "cb": _num(row.get("c_Bid")), "ca": _num(row.get("c_Ask")),
            "pb": _num(row.get("p_Bid")), "pa": _num(row.get("p_Ask")),
            "cv": _num(row.get("c_Volume")), "pv": _num(row.get("p_Volume")),
            "coi": _num(row.get("c_Openinterest")), "poi": _num(row.get("p_Openinterest")),
        })
    return out, spot


def _mid(b, a):
    if b is None or a is None or b <= 0 or a < b:
        return None
    return 0.5 * (b + a)


def atm_iv(rows: list[dict], spot: float | None, days: int, r: float = RISK_FREE) -> dict | None:
    """IV ATM de un vencimiento (forward por paridad + Black-76 sobre la OTM de los strikes que rodean el forward)."""
    T = days / 365.0
    if T <= 0:
        return None
    df = math.exp(-r * T)
    both = []
    for x in rows:
        c, p = _mid(x["cb"], x["ca"]), _mid(x["pb"], x["pa"])
        if c is not None and p is not None:
            both.append((x["K"], c, p))
    if not both:
        return None
    ref = spot if spot else sorted(k for k, _, _ in both)[len(both) // 2]
    near = sorted(both, key=lambda t: abs(t[0] - ref))[:3]
    fwds = [K + (c - p) / df for K, c, p in near]
    F = sum(fwds) / len(fwds)
    if F <= 0:
        return None
    quotes = []
    for x in rows:
        K = x["K"]
        if K < F:
            iv = implied_vol(_mid(x["pb"], x["pa"]), F, K, T, df, False)
        else:
            iv = implied_vol(_mid(x["cb"], x["ca"]), F, K, T, df, True)
        if iv is not None:
            quotes.append((K, iv))
    below = [q for q in quotes if q[0] < F]
    above = [q for q in quotes if q[0] >= F]
    kl = max(below, key=lambda q: q[0]) if below else None
    ku = min(above, key=lambda q: q[0]) if above else None
    if kl and ku:
        w = (F - kl[0]) / (ku[0] - kl[0])
        iv = kl[1] * (1 - w) + ku[1] * w
    elif kl or ku:
        iv = (kl or ku)[1]
    else:
        return None
    return {"iv": iv, "forward": F, "days": days}


def iv30_from_chain(expiries: list[dict], spot: float | None) -> dict:
    """Interpola la varianza total a 30 días entre los dos vencimientos que la rodean."""
    pts = []
    for e in expiries:
        if e["days"] >= MIN_DAYS_IV:
            a = atm_iv(e["rows"], spot, e["days"])
            if a:
                pts.append(a)
    pts.sort(key=lambda a: a["days"])
    lo = [a for a in pts if a["days"] <= TARGET_DAYS]
    hi = [a for a in pts if a["days"] > TARGET_DAYS]
    res = {"iv30": None, "iv_d1": None, "iv_d2": None, "iv1": None, "iv2": None}
    if not lo or not hi:
        return res
    a1, a2 = lo[-1], hi[0]
    if a1["days"] == TARGET_DAYS:
        res.update(iv30=a1["iv"], iv_d1=a1["days"], iv1=a1["iv"])
        return res
    w1 = a1["iv"] ** 2 * a1["days"] / 365.0
    w2 = a2["iv"] ** 2 * a2["days"] / 365.0
    frac = (TARGET_DAYS - a1["days"]) / (a2["days"] - a1["days"])
    w30 = w1 + (w2 - w1) * frac
    res.update(iv30=math.sqrt(max(w30, 0.0) / (TARGET_DAYS / 365.0)), iv_d1=a1["days"], iv_d2=a2["days"],
               iv1=a1["iv"], iv2=a2["iv"])
    return res


def _put_call(expiries: list[dict]) -> dict:
    cv = pv = coi = poi = 0.0
    n = 0
    for e in expiries:
        if e["days"] < 0 or e["days"] > PC_WINDOW_DAYS:
            continue
        n += 1
        for x in e["rows"]:
            cv += x["cv"] or 0
            pv += x["pv"] or 0
            coi += x["coi"] or 0
            poi += x["poi"] or 0
    return {"put_call_vol": _round(pv / cv, 4) if cv > 0 else None,
            "put_call_oi": _round(poi / coi, 4) if coi > 0 else None,
            "call_vol": cv, "put_vol": pv, "call_oi": coi, "put_oi": poi, "n_expiries_pc": n}


def fetch_iv(ticker: str, today: date) -> dict:
    url = (f"https://api.nasdaq.com/api/quote/{_nasdaq_sym(ticker)}/option-chain?assetclass=stocks&limit=5000"
           f"&fromdate={today.isoformat()}&todate={(today + timedelta(days=CHAIN_WINDOW_DAYS)).isoformat()}"
           f"&excode=oprac&callput=callput&money=all&type=all")
    data = _nasdaq_json(url)
    expiries, spot = parse_chain(data, today)
    if not expiries:
        raise ValueError("cadena de opciones vacía")
    out = iv30_from_chain(expiries, spot)
    out = {k: (_round(v) if isinstance(v, float) else v) for k, v in out.items()}
    out.update(_put_call(expiries))
    out["spot"] = spot
    out["n_expiries"] = len(expiries)
    if out["iv30"] is None:
        out["note"] = "sin vencimientos válidos a ambos lados de 30 días"
    return out


# --------------------------------------------------------------------------- 2-3. FINRA
def _weekday_back(d: date) -> date:
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def finra_si_candidates(today: date, max_back_days: int = 130) -> list[date]:
    """Fechas de liquidación posibles (día 15 y fin de mes, retrocediendo a día hábil), de más reciente a más antigua.

    Primero los candidatos principales; después los de respaldo (un día hábil antes, por feriados).
    """
    limit = today - timedelta(days=3)
    floor = today - timedelta(days=max_back_days)
    targets = []
    y, m = today.year, today.month
    for _ in range(6):
        eom = (date(y, m, 28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        targets += [date(y, m, 15), eom]
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    prim = sorted({_weekday_back(t) for t in targets if floor <= _weekday_back(t) <= limit}, reverse=True)
    back = sorted({_weekday_back(p - timedelta(days=1)) for p in prim} - set(prim), reverse=True)
    return prim + back


def _finra_si_table(today: date) -> dict:
    """{símbolo: fila} del último archivo de interés corto publicado por FINRA (memorizado por día)."""
    with _memo_lock:
        hit = _memo.get(("si", today))
    if hit is not None:
        if isinstance(hit, Exception):
            raise hit
        return hit
    last = None
    for d in finra_si_candidates(today):
        try:
            r = http.get(FINRA_SI_URL.format(d=d.strftime("%Y%m%d")), cache=True, timeout=60, retries=1)
        except Exception as exc:  # noqa: BLE001 - 404 = aún no publicado
            last = exc
            continue
        text = r.content.decode("utf-8", "replace")
        table = {row["symbolCode"]: row for row in csv.DictReader(io.StringIO(text), delimiter="|")
                 if row.get("symbolCode")}
        if table:
            with _memo_lock:
                _memo[("si", today)] = table
            return table
    exc = RuntimeError(f"no se encontró archivo de interés corto de FINRA ({last})")
    with _memo_lock:
        _memo[("si", today)] = exc
    raise exc


def _finra_symbol_variants(t: str) -> list[str]:
    t = t.upper()
    return list(dict.fromkeys([t, t.replace("-", ""), t.replace("-", "."), t.replace(".", ""), t.replace("-", "/"), t.replace(".", "/")]))


def fetch_short_interest(ticker: str, today: date) -> dict:
    table = _finra_si_table(today)
    row = next((table[v] for v in _finra_symbol_variants(ticker) if v in table), None)
    if row is None:
        raise ValueError("símbolo ausente en el archivo de interés corto de FINRA")
    settle = (row.get("settlementDate") or "").strip()
    cur, prev = _num(row.get("currentShortPositionQuantity")), _num(row.get("previousShortPositionQuantity"))
    age = (today - date.fromisoformat(settle)).days if re.fullmatch(r"\d{4}-\d{2}-\d{2}", settle) else None
    return {
        "si_shares": cur, "si_prev_shares": prev,
        "si_change_pct": _num(row.get("changePercent")),
        "si_days_to_cover": _num(row.get("daysToCoverQuantity")),
        "si_avg_daily_volume": _num(row.get("averageDailyVolumeQuantity")),
        "si_settle_date": settle or None, "si_age_days": age,
    }


def _finra_sv_table(today: date) -> tuple[date, dict]:
    with _memo_lock:
        hit = _memo.get(("sv", today))
    if hit is not None:
        if isinstance(hit, Exception):
            raise hit
        return hit
    last = None
    d = _weekday_back(today)
    for _ in range(6):
        try:
            r = http.get(FINRA_SV_URL.format(d=d.strftime("%Y%m%d")), timeout=60, retries=1)
            text = r.content.decode("utf-8", "replace")
            table = {}
            for row in csv.DictReader(io.StringIO(text), delimiter="|"):
                if row.get("Symbol"):
                    table[row["Symbol"]] = row
            if table:
                with _memo_lock:
                    _memo[("sv", today)] = (d, table)
                return d, table
        except Exception as exc:  # noqa: BLE001
            last = exc
        d = _weekday_back(d - timedelta(days=1))
    exc = RuntimeError(f"no se encontró archivo de volumen corto de FINRA ({last})")
    with _memo_lock:
        _memo[("sv", today)] = exc
    raise exc


def fetch_short_volume(ticker: str, today: date) -> dict:
    d, table = _finra_sv_table(today)
    row = next((table[v] for v in _finra_symbol_variants(ticker) if v in table), None)
    if row is None:
        raise ValueError("símbolo ausente en el archivo de volumen corto de FINRA")
    sv, tv = _num(row.get("ShortVolume")), _num(row.get("TotalVolume"))
    return {"sv_short_volume": sv, "sv_total_volume": tv,
            "sv_ratio": _round(sv / tv, 4) if sv is not None and tv else None, "sv_date": d.isoformat()}


# --------------------------------------------------------------------------- 4. analistas
def parse_analysts(target: dict | None, ratings: dict | None, eps: dict | None) -> dict:
    """Cada argumento es el ``data`` de su endpoint (o None si esa llamada falló)."""
    out: dict = {}
    if target:
        ov = target.get("consensusOverview") or {}
        b, h, s = _num(ov.get("buy")), _num(ov.get("hold")), _num(ov.get("sell"))
        n = (b or 0) + (h or 0) + (s or 0)
        out.update(an_target_mean=_num(ov.get("priceTarget")), an_target_low=_num(ov.get("lowPriceTarget")),
                   an_target_high=_num(ov.get("highPriceTarget")), an_n_buy=b, an_n_hold=h, an_n_sell=s,
                   an_n_analysts=n or None,
                   an_rec_score=_round((b - s) / n, 4) if n and b is not None and s is not None else None)
    if ratings:
        out["an_mean_rating"] = ratings.get("meanRatingType")
        m = re.search(r"(\d+)\s+analysts", str(ratings.get("ratingsSummary") or ""))
        if m:
            out["an_n_ratings"] = float(m.group(1))
    if eps:
        rows = ((eps.get("quarterlyForecast") or {}).get("rows")) or []
        if rows:
            r0 = rows[0]
            out.update(an_eps_cons=_num(r0.get("consensusEPSForecast")), an_eps_high=_num(r0.get("highEPSForecast")),
                       an_eps_low=_num(r0.get("lowEPSForecast")), an_eps_n=_num(r0.get("noOfEstimates")),
                       an_eps_rev_up=_num(r0.get("up")), an_eps_rev_down=_num(r0.get("down")),
                       an_eps_fiscal=r0.get("fiscalEnd"))
    return out


def fetch_analysts(ticker: str, today: date) -> dict:
    sym = _nasdaq_sym(ticker)
    parts, errors = {}, []
    for name, path in (("target", f"analyst/{sym}/targetprice"), ("ratings", f"analyst/{sym}/ratings"),
                       ("eps", f"analyst/{sym}/earnings-forecast")):
        try:
            parts[name] = _nasdaq_json(f"https://api.nasdaq.com/api/{path}")
        except Exception as exc:  # noqa: BLE001
            parts[name] = None
            errors.append(f"{name}: {type(exc).__name__}: {exc}"[:160])
    out = parse_analysts(parts["target"], parts["ratings"], parts["eps"])
    if not any(v is not None for v in out.values()):
        raise ValueError("sin datos de analistas (" + "; ".join(errors) + ")" if errors else "sin datos de analistas")
    if errors:
        out["partial_errors"] = errors
    return out


# --------------------------------------------------------------------------- API pública
_FETCHERS = {"iv": fetch_iv, "short_interest": fetch_short_interest,
             "short_volume": fetch_short_volume, "analysts": fetch_analysts}


def collect_one(ticker: str, today=None, sources=SOURCES) -> dict:
    """Foto de un ticker: {fuente: {campos...} | {"error": ...}}. Nunca lanza excepción."""
    today = _as_date(today)
    out: dict = {}
    for name in sources:
        try:
            out[name] = _FETCHERS[name](ticker, today)
        except Exception as exc:  # noqa: BLE001 - una fuente caída no bloquea a las demás
            out[name] = _err(exc)
    return out


def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    os.replace(tmp, path)


def _pending(entry: dict | None) -> list[str]:
    if not entry:
        return list(SOURCES)
    return [s for s in SOURCES if not isinstance(entry.get(s), dict) or "error" in entry[s]]


def collect(tickers, today=None, outdir="data/alt", max_workers: int = 4, pause: float = 0.2) -> dict:
    """Escribe ``outdir/AAAA-MM-DD.json`` (una foto por día) y devuelve el resumen de cobertura.

    Idempotente: si el archivo del día existe, solo se reintentan las fuentes que fallaron o faltan.
    ``pause`` es el espaciado mínimo global (segundos) entre peticiones a api.nasdaq.com.
    """
    t0 = time.time()
    today = _as_date(today)
    tickers = list(dict.fromkeys(str(t).upper() for t in tickers))
    path = Path(outdir) / f"{today.isoformat()}.json"
    snap = {"date": today.isoformat(), "version": 1, "tickers": {}}
    if path.exists():
        try:
            old = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(old.get("tickers"), dict):
                snap["tickers"] = old["tickers"]
        except (OSError, ValueError):
            pass
    _PAUSE[0] = max(0.0, float(pause))
    with _memo_lock:                      # una corrida nueva reintenta las descargas de FINRA que fallaron
        for k in [k for k, v in _memo.items() if isinstance(v, Exception)]:
            del _memo[k]
    todo = [(t, _pending(snap["tickers"].get(t))) for t in tickers]
    todo = [(t, srcs) for t, srcs in todo if srcs]
    done = 0
    if todo:
        with ThreadPoolExecutor(max_workers=max(1, int(max_workers))) as ex:
            futs = {ex.submit(collect_one, t, today, tuple(srcs)): t for t, srcs in todo}
            for fut in as_completed(futs):
                t = futs[fut]
                res = fut.result()
                snap["tickers"][t] = {**(snap["tickers"].get(t) or {}), **res}
                done += 1
                if done % 20 == 0:
                    _write_json(path, snap)
        _write_json(path, snap)
    elif not path.exists():
        _write_json(path, snap)
    cov = {s: sum(1 for t in tickers if isinstance((snap["tickers"].get(t) or {}).get(s), dict)
                  and "error" not in snap["tickers"][t][s]) for s in SOURCES}
    errs: dict[str, str] = {}
    for s in SOURCES:
        for t in tickers:
            e = (snap["tickers"].get(t) or {}).get(s)
            if isinstance(e, dict) and "error" in e:
                errs.setdefault(s, f"{t}: {e['error']}")
    return {"date": today.isoformat(), "path": str(path), "n_tickers": len(tickers), "fetched": len(todo),
            "coverage": cov, "first_error": errs, "seconds": round(time.time() - t0, 1)}


def load_history(outdir="data/alt") -> pd.DataFrame:
    """Todas las fotos en formato largo: columnas date, ticker, campo, valor (solo valores numéricos)."""
    rows = []
    for f in sorted(Path(outdir).glob("????-??-??.json")):
        try:
            snap = json.loads(f.read_text(encoding="utf-8"))
            d = pd.Timestamp(snap.get("date") or f.stem)
        except (OSError, ValueError):
            continue
        for t, entry in (snap.get("tickers") or {}).items():
            for src in SOURCES:
                block = (entry or {}).get(src)
                if not isinstance(block, dict) or "error" in block:
                    continue
                for k, v in block.items():
                    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
                        continue
                    rows.append((d, t, k, float(v)))
    return pd.DataFrame(rows, columns=["date", "ticker", "campo", "valor"])
