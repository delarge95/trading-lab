"""SEC EDGAR: 13F de gestores y Form 4 de insiders."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import date, datetime

from . import http

SUB = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
ARCH = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{name}"


def _strip_ns(root: ET.Element) -> ET.Element:
    for el in root.iter():
        if "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
    return root


def _text(el: ET.Element | None, path: str, default: str = "") -> str:
    node = el.find(path) if el is not None else None
    return (node.text or "").strip() if node is not None and node.text else default


def ticker_to_cik() -> dict[str, int]:
    j = http.get("https://www.sec.gov/files/company_tickers.json", cache=True).json()
    return {v["ticker"].upper(): int(v["cik_str"]) for v in j.values()}


def filings(cik: int, forms: set[str], limit: int = 200) -> list[dict]:
    """Filings recientes de un CIK (campo 'recent' de submissions)."""
    f = http.get(SUB.format(cik=cik)).json()["filings"]["recent"]
    out = []
    for i, form in enumerate(f["form"]):
        if form in forms:
            out.append({k: f[k][i] for k in ("accessionNumber", "filingDate", "reportDate", "primaryDocument", "form")})
            if len(out) >= limit:
                break
    return out


# ---------------------------------------------------------------- 13F
def parse_13f_table(xml_text: str) -> dict[str, dict]:
    """Agrega por CUSIP (el XML repite filas por otherManager) e ignora opciones."""
    root = _strip_ns(ET.fromstring(xml_text))
    agg: dict[str, dict] = {}
    for it in root.iter("infoTable"):
        if _text(it, "putCall"):
            continue
        cusip = _text(it, "cusip")
        a = agg.setdefault(cusip, {"name": _text(it, "nameOfIssuer"), "value": 0.0, "shares": 0.0})
        a["value"] += float(_text(it, "value", "0") or 0)
        a["shares"] += float(_text(it, "shrsOrPrnAmt/sshPrnamt", "0") or 0)
    return agg


def rescale_if_thousands(table: dict[str, dict]) -> tuple[dict[str, dict], bool]:
    """Algunos gestores declaran `value` en miles de dólares en vez de dólares.

    Si el precio implícito mediano (valor/acciones) es < $1, el valor casi seguro está en
    miles (una cartera de acciones no tiene mediana bajo $1): se multiplica por 1000.
    """
    prices = sorted(p["value"] / p["shares"] for p in table.values() if p["shares"] > 0)
    if prices and prices[len(prices) // 2] < 1.0:
        return {c: {**p, "value": p["value"] * 1000} for c, p in table.items()}, True
    return table, False


def _infotable_name(cik: int, acc_nodash: str) -> str:
    idx = http.get(ARCH.format(cik=cik, acc=acc_nodash, name="index.json"), cache=True).json()
    items = [i for i in idx["directory"]["item"]
             if i["name"].lower().endswith(".xml") and i["name"] != "primary_doc.xml"]
    if not items:
        raise RuntimeError(f"Sin infotable en {acc_nodash}")
    return max(items, key=lambda i: int(i["size"] or 0))["name"]


def manager_13f(cik: int, name: str, stale_days: int = 140, today: date | None = None) -> dict:
    """Última cartera 13F y cambios vs el trimestre anterior."""
    today = today or date.today()
    fl = filings(cik, {"13F-HR"}, limit=2)
    if not fl:
        return {"name": name, "cik": cik, "error": "sin 13F-HR"}
    tables = []
    for f in fl:
        acc = f["accessionNumber"].replace("-", "")
        xml = http.get(ARCH.format(cik=cik, acc=acc, name=_infotable_name(cik, acc)), cache=True).text
        table, rescaled = rescale_if_thousands(parse_13f_table(xml))
        tables.append((f, table, rescaled))
    (cur_f, cur, cur_rescaled) = tables[0]
    prev = tables[1][1] if len(tables) > 1 else None  # (la escala solo afecta a 'value', no a las acciones)
    total = sum(p["value"] for p in cur.values()) or 1.0
    rows = []
    for cusip, p in cur.items():
        pv = prev.get(cusip) if prev is not None else None
        if prev is None:
            change = "n/d"
        elif pv is None:
            change = "NUEVA"
        else:
            delta = (p["shares"] - pv["shares"]) / pv["shares"] if pv["shares"] else 0.0
            change = f"{delta:+.0%}" if abs(delta) >= 0.01 else "="
        rows.append({"cusip": cusip, "name": p["name"], "value": p["value"],
                     "weight": p["value"] / total, "change": change})
    rows.sort(key=lambda r: r["value"], reverse=True)
    closed = []
    if prev:
        closed = [{"name": v["name"], "value": v["value"]} for c, v in prev.items() if c not in cur]
        closed.sort(key=lambda r: r["value"], reverse=True)
    period = datetime.strptime(cur_f["reportDate"], "%Y-%m-%d").date()
    age = (today - period).days
    return {
        "name": name, "cik": cik, "period": cur_f["reportDate"], "filed": cur_f["filingDate"],
        "age_days": age, "stale": age > stale_days, "total_value": total,
        "positions": len(cur), "top": rows[:10], "closed": closed[:5],
        "value_rescaled_from_thousands": cur_rescaled,
    }


# ---------------------------------------------------------------- Form 4
def parse_form4(xml_text: str) -> list[dict]:
    """Transacciones de mercado abierto (códigos P y S) de un Form 4."""
    root = _strip_ns(ET.fromstring(xml_text))
    issuer_cik = _text(root, "issuer/issuerCik").lstrip("0")
    owner = _text(root, "reportingOwner/reportingOwnerId/rptOwnerName")
    cik = _text(root, "reportingOwner/reportingOwnerId/rptOwnerCik")
    rel = root.find("reportingOwner/reportingOwnerRelationship")
    role = ",".join(t for t, k in (("Director", "isDirector"), ("Officer", "isOfficer"),
                                   ("10%", "isTenPercentOwner")) if _text(rel, k) in ("1", "true"))
    out = []
    for t in root.iter("nonDerivativeTransaction"):
        code = _text(t, "transactionCoding/transactionCode")
        if code not in ("P", "S"):
            continue
        shares = float(_text(t, "transactionAmounts/transactionShares/value", "0") or 0)
        price = float(_text(t, "transactionAmounts/transactionPricePerShare/value", "0") or 0)
        out.append({"owner": owner, "owner_cik": cik, "issuer_cik": issuer_cik, "role": role, "code": code,
                    "date": _text(t, "transactionDate/value"), "shares": shares,
                    "price": price, "value": shares * price})
    return out


def insider_trades(ticker: str, cik_map: dict[str, int], years: int = 4, max_filings: int = 120) -> list[dict]:
    t = ticker.upper()
    cik = cik_map.get(t) or cik_map.get(t.replace("-", ".")) or cik_map.get(t.replace(".", "-"))
    if cik is None:
        raise RuntimeError(f"CIK desconocido para {ticker}")
    today = date.today()
    cutoff = today.replace(year=today.year - years, day=min(today.day, 28)).isoformat()
    trades = []
    for f in filings(cik, {"4", "4/A"}, limit=max_filings):
        if f["filingDate"] < cutoff:
            break
        acc = f["accessionNumber"].replace("-", "")
        raw = f["primaryDocument"].split("/")[-1]  # quitar prefijo xsl (versión HTML)
        try:
            xml = http.get(ARCH.format(cik=cik, acc=acc, name=raw), cache=True).text
            for t in parse_form4(xml):
                # El listado de un CIK incluye Form 4 donde ese CIK es el *declarante* (p. ej. Berkshire
                # comprando otras empresas). Solo cuentan los del propio emisor.
                if t["issuer_cik"] and int(t["issuer_cik"]) != cik:
                    continue
                t["filed"] = f["filingDate"]
                trades.append(t)
        except Exception:  # noqa: BLE001 - un Form 4 roto no debe tumbar el informe
            continue
    return trades
