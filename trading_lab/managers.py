"""Track record de gestores: ¿habría ganado a SPY quien copiara sus 13F al hacerse públicos?

Replicación sin anticipación: con cada 13F se compra la cartera (top-N por valor) al primer cierre
posterior a la fecha de *presentación* (no al cierre del trimestre) y se mantiene hasta el primer
cierre posterior a la siguiente presentación. Es el único retorno que un seguidor podía capturar.

Limitaciones que se reportan: 13F solo muestra largos en acciones de EE. UU. con ~45 días de retraso;
muestras de pocos trimestres tienen poca potencia (se calcula cuántos años harían falta);
los tickers sin precios (deslistados) quedan fuera, lo que sesga hacia arriba (sesgo de supervivencia).
"""
from __future__ import annotations

import bisect
import json
import math
import random
import time
from datetime import date
from pathlib import Path
from statistics import NormalDist, mean, stdev

import requests

from . import http, sec

DATA = Path("data")
FIGI_URL = "https://api.openfigi.com/v3/mapping"
Z_ALPHA, Z_POWER = 1.645, 0.8416   # unilateral 5%, potencia 80%


# ---------------------------------------------------------------- historial 13F
def history(cik: int, n_quarters: int = 20) -> list[dict]:
    """13F-HR de un gestor, de más antiguo a más reciente: {filed, period, table}."""
    out = []
    for f in sec.filings(cik, {"13F-HR"}, limit=n_quarters):
        acc = f["accessionNumber"].replace("-", "")
        try:
            xml = http.get(sec.ARCH.format(cik=cik, acc=acc, name=sec._infotable_name(cik, acc)), cache=True).text
            table, _ = sec.rescale_if_thousands(sec.parse_13f_table(xml))
        except Exception:  # noqa: BLE001 - un 13F ilegible se omite
            continue
        out.append({"filed": f["filingDate"], "period": f["reportDate"], "table": table})
    out.sort(key=lambda h: h["filed"])
    return out


# ---------------------------------------------------------------- CUSIP -> ticker
def pick_ticker(matches: list[dict]) -> str | None:
    """Elige el ticker de renta variable estadounidense (compuesto 'US') entre las coincidencias de OpenFIGI."""
    eq = [m for m in matches if m.get("marketSector") == "Equity" and m.get("ticker")]
    for m in eq:
        if m.get("exchCode") == "US":
            return m["ticker"].replace("/", "-").replace(".", "-")
    return eq[0]["ticker"].replace("/", "-").replace(".", "-") if eq else None


def id_type(code: str) -> str:
    return "ID_CINS" if code[:1].isalpha() else "ID_CUSIP"


def map_cusips(cusips: list[str], cache_path: Path = DATA / "cusip_map.json") -> dict[str, str | None]:
    cache: dict[str, str | None] = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    # Los códigos que empiezan con letra son CINS (emisores domiciliados fuera de EE. UU.); un None
    # guardado para ellos viene de consultarlos como CUSIP, así que se reintentan.
    todo = [c for c in dict.fromkeys(cusips) if c and (c not in cache or (cache[c] is None and c[0].isalpha()))]
    for i in range(0, len(todo), 10):                 # 10 trabajos por petición, ~25 peticiones/min sin clave
        batch = todo[i:i + 10]
        body = [{"idType": id_type(c), "idValue": c} for c in batch]
        for attempt in range(4):
            r = requests.post(FIGI_URL, json=body, timeout=30)
            if r.status_code == 429:
                time.sleep(30 * (attempt + 1))
                continue
            r.raise_for_status()
            for c, res in zip(batch, r.json()):
                cache[c] = pick_ticker(res.get("data", []))
            break
        else:
            raise RuntimeError("OpenFIGI: límite de peticiones")
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(cache, indent=0))
        time.sleep(2.6)
    return cache


# ---------------------------------------------------------------- replicación
def _first_after(dates: list[str], d: str) -> int | None:
    i = bisect.bisect_right(dates, d)
    return i if i < len(dates) else None


def holding_return(series: list[tuple[str, float]], start_after: str, end_after: str) -> float | None:
    """Retorno entre el primer cierre > start_after y el primer cierre > end_after.

    Si la serie termina antes de end_after (deslistado/adquirido) se usa el último precio disponible.
    """
    if not series:
        return None
    dates = [d for d, _ in series]
    i = _first_after(dates, start_after)
    if i is None:
        return None
    j = _first_after(dates, end_after)
    p1 = series[j][1] if j is not None else series[-1][1]
    if j is None and dates[-1] <= start_after:
        return None
    return p1 / series[i][1] - 1.0


def follow_returns(hist: list[dict], cusip_ticker: dict[str, str | None],
                   prices: dict[str, list[tuple[str, float]]], bench: list[tuple[str, float]],
                   top_n: int = 15) -> list[dict]:
    """Un retorno por ventana cerrada [presentación k, presentación k+1]."""
    rows = []
    for k in range(len(hist) - 1):
        a, b = hist[k]["filed"], hist[k + 1]["filed"]
        top = sorted(hist[k]["table"].items(), key=lambda kv: kv[1]["value"], reverse=True)[:top_n]
        tot = sum(v["value"] for _, v in top) or 1.0
        covered = 0.0
        acc = 0.0
        for cusip, v in top:
            t = cusip_ticker.get(cusip)
            r = holding_return(prices.get(t, []), a, b) if t else None
            if r is None:
                continue
            w = v["value"] / tot
            covered += w
            acc += w * r
        rb = holding_return(bench, a, b)
        if covered < 0.5 or rb is None:   # cobertura insuficiente: ventana descartada
            continue
        rows.append({"from": a, "to": b, "ret": acc / covered, "bench": rb, "coverage": covered})
    return rows


# ---------------------------------------------------------------- orquestación
def _cached_prices(ticker: str, stamp: str, years: int = 7) -> list[tuple[str, float]]:
    from . import prices as pr
    path = DATA / "raw" / f"px_{ticker}_{stamp}.json"
    if path.exists():
        return [tuple(x) for x in json.loads(path.read_text())]
    series, _ = pr.get_prices(ticker, years)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(series))
    return series


def iso_week(d: date | None = None) -> str:
    y, w, _ = (d or date.today()).isocalendar()
    return f"{y}-W{w:02d}"


def track_record(managers: list[dict], n_quarters: int = 20, top_n: int = 15,
                 today: date | None = None) -> dict:
    """Calcula el track record de todos los gestores. Pesado: cachear por semana ISO."""
    from . import rigor
    stamp = iso_week(today)
    hists = {m["name"]: history(m["cik"], n_quarters) for m in managers}
    cusips = []
    for h in hists.values():
        for q in h[:-1]:  # la última presentación aún no tiene ventana cerrada
            cusips += [c for c, _ in sorted(q["table"].items(), key=lambda kv: kv[1]["value"], reverse=True)[:top_n]]
    cmap = map_cusips(cusips)
    prices: dict[str, list[tuple[str, float]]] = {}
    failed = []
    for t in sorted({t for t in (cmap.get(c) for c in cusips) if t}):
        try:
            prices[t] = _cached_prices(t, stamp)
        except Exception:  # noqa: BLE001 - sin precios (deslistado): se excluye y se reporta
            failed.append(t)
    bench = _cached_prices("SPY", stamp)

    results, series_used = {}, {}
    for name, h in hists.items():
        rows = follow_returns(h, cmap, prices, bench, top_n)
        ev = evaluate_manager(rows)
        series_used[name] = len(rows)
        if ev:
            results[name] = ev
    names = list(results)
    for n, p_adj in zip(names, rigor.holm([results[n]["p_beat"] for n in names])):
        results[n]["p_holm"] = p_adj
    win = [n for n in names if results[n]["p_holm"] < 0.05 and results[n]["annual_excess"] > 0]
    return {
        "week": stamp, "computed": (today or date.today()).isoformat(), "top_n": top_n,
        "managers": results, "windows": series_used, "tickers_without_prices": len(failed),
        "tickers_total": len(prices) + len(failed),
        "verdict": (f"Con significancia (Holm 5%) superan a SPY al replicar sus 13F: {', '.join(win)}." if win else
                    f"Ningún gestor supera a SPY con significancia estadística (Holm 5%, {len(names)} gestores)."),
    }


# ---------------------------------------------------------------- estadística
def sign_flip_p(x: list[float], n_perm: int = 20000, seed: int = 0) -> float:
    """Valor p unilateral de H0: media <= 0, por inversión aleatoria de signos (sin supuesto de normalidad)."""
    rng = random.Random(seed)
    obs = mean(x)
    ge = sum(1 for _ in range(n_perm) if mean([v if rng.random() < 0.5 else -v for v in x]) >= obs)
    return (ge + 1) / (n_perm + 1)


def bootstrap_ci(x: list[float], n_boot: int = 5000, seed: int = 0) -> tuple[float, float]:
    rng = random.Random(seed)
    ms = sorted(mean(rng.choices(x, k=len(x))) for _ in range(n_boot))
    return ms[int(0.025 * n_boot)], ms[int(0.975 * n_boot) - 1]


def years_needed(te_annual: float, alpha: float = 0.03) -> float:
    """Años de historia para detectar con 80% de potencia un alfa anual `alpha` dado el error de seguimiento."""
    return ((Z_ALPHA + Z_POWER) * te_annual / alpha) ** 2


def evaluate_manager(rows: list[dict]) -> dict | None:
    if len(rows) < 4:
        return None
    ex = [r["ret"] - r["bench"] for r in rows]
    yrs = sum((date.fromisoformat(r["to"]) - date.fromisoformat(r["from"])).days for r in rows) / 365.25
    cum = math.prod(1 + r["ret"] for r in rows)
    cum_b = math.prod(1 + r["bench"] for r in rows)
    ppy = len(rows) / yrs
    te = stdev(ex) * math.sqrt(ppy)
    ann_ex = mean(ex) * ppy
    return {
        "periods": len(rows), "years": yrs, "coverage": mean(r["coverage"] for r in rows),
        "cagr": cum ** (1 / yrs) - 1, "cagr_bench": cum_b ** (1 / yrs) - 1,
        "excess_per_period": mean(ex), "excess_ci": bootstrap_ci(ex),
        "annual_excess": ann_ex, "tracking_error": te,
        "info_ratio": ann_ex / te if te > 0 else None,
        "hit_rate": sum(1 for v in ex if v > 0) / len(ex),
        "p_beat": sign_flip_p(ex), "years_needed_3pct": years_needed(te) if te > 0 else None,
    }
