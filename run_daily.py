"""Pipeline diario: descarga datos, calcula señales y escribe reports/latest.{md,json}.

Uso:  python run_daily.py [--no-sec] [--no-insiders] [--tickers SPY,AAPL]
Requiere SEC_USER_AGENT en el entorno (o en .env) para consultar la SEC.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

import yaml

from trading_lab import (backtest, evaluate, fred, insiders, managers, predictions, prices, report, sec,
                         signals)

ROOT = Path(__file__).parent


def load_env(path: Path = ROOT / ".env") -> None:
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-sec", action="store_true", help="omitir 13F e insiders")
    ap.add_argument("--no-insiders", action="store_true")
    ap.add_argument("--no-managers", action="store_true", help="omitir el track record de gestores")
    ap.add_argument("--tickers", help="lista separada por comas (sobrescribe la watchlist)")
    args = ap.parse_args(argv)

    load_env()
    cfg = yaml.safe_load((ROOT / "config" / "watchlist.yaml").read_text(encoding="utf-8"))
    tickers = [t.strip().upper() for t in args.tickers.split(",")] if args.tickers else cfg["tickers"]
    today = date.today()
    res = {"date": today.isoformat(), "sources": {}, "errors": [], "tickers": {}, "backtest": {},
           "insiders": {}, "managers": [], "macro": {}}
    series: dict[str, list[tuple[str, float]]] = {}

    # Precios + señales + backtest
    srcs = set()
    for t in tickers:
        try:
            data, src = prices.get_prices(t, years=10)
            series[t] = data
            srcs.add(src)
            res["tickers"][t] = signals.summarize(data)
            bt = backtest.momentum_backtest([p for _, p in data])
            if bt["periods"] >= 3:
                res["backtest"][t] = bt
        except Exception as exc:  # noqa: BLE001
            res["errors"].append(f"precios {t}: {exc}")
    res["sources"]["Precios"] = (f"OK ({', '.join(sorted(srcs))}), {len(series)}/{len(tickers)} tickers"
                                 if series else "FALLÓ")
    res["null_check"] = backtest.null_check()
    res["rigor"] = evaluate.evaluate({t: [p for _, p in d] for t, d in series.items()})

    # Macro
    res["macro"] = fred.snapshot()
    ok = sum(1 for m in res["macro"].values() if "error" not in m)
    res["sources"]["FRED"] = f"OK ({ok}/{len(res['macro'])} series)" if ok else "FALLÓ"

    # SEC
    if args.no_sec:
        res["sources"]["SEC"] = "omitida (--no-sec)"
    else:
        try:
            sec.http.sec_user_agent()
            if not args.no_insiders:
                cmap = sec.ticker_to_cik()
                for t in tickers:
                    if t in ("SPY", "QQQ"):  # ETFs: sin Form 4
                        continue
                    try:
                        res["insiders"][t] = insiders.classify(sec.insider_trades(t, cmap))
                    except Exception as exc:  # noqa: BLE001
                        res["errors"].append(f"insiders {t}: {exc}")
            for m in cfg["managers"]:
                try:
                    res["managers"].append(sec.manager_13f(m["cik"], m["name"], cfg.get("stale_13f_days", 140)))
                except Exception as exc:  # noqa: BLE001
                    res["errors"].append(f"13F {m['name']}: {exc}")
                    res["managers"].append({"name": m["name"], "cik": m["cik"], "error": str(exc)})
            good = sum(1 for m in res["managers"] if "error" not in m)
            stale = [m["name"] for m in res["managers"] if m.get("stale")]
            res["sources"]["SEC"] = f"OK ({good}/{len(cfg['managers'])} gestores, {len(res['insiders'])} emisores)"
            if stale:
                res["sources"]["SEC"] += f"; 13F atrasado: {', '.join(stale)}"
        except Exception as exc:  # noqa: BLE001
            res["sources"]["SEC"] = f"FALLÓ: {exc}"
            res["errors"].append(f"SEC: {exc}")

    # Track record de gestores (pesado: se recalcula una vez por semana ISO y se guarda)
    track_path = ROOT / "data" / "managers_track.json"
    cached = json.loads(track_path.read_text(encoding="utf-8")) if track_path.exists() else None
    if args.no_sec or args.no_managers:
        res["manager_track"] = cached
    elif cached and cached.get("week") == managers.iso_week(today):
        res["manager_track"] = cached
    else:
        try:
            res["manager_track"] = managers.track_record(cfg["managers"])
            track_path.write_text(json.dumps(res["manager_track"], indent=2, default=str), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001 - se conserva el cálculo previo si existe
            res["errors"].append(f"track record gestores: {exc}")
            res["manager_track"] = cached

    # Predicciones: evaluar vencidas y registrar las de hoy
    pred_path = ROOT / "data" / "predictions.csv"
    predictions.evaluate(pred_path, series, today)
    for t, s in res["tickers"].items():
        predictions.record(pred_path, t, s, today)
    res["scoreboard"] = predictions.load_scoreboard(pred_path)

    out = ROOT / "reports"
    out.mkdir(exist_ok=True)
    md = report.render(res)
    (out / "latest.md").write_text(md, encoding="utf-8")
    (out / f"{today.isoformat()}.md").write_text(md, encoding="utf-8")
    (out / "latest.json").write_text(json.dumps(res, indent=2, default=str, ensure_ascii=False), encoding="utf-8")
    print(f"Informe escrito: reports/latest.md ({len(res['errors'])} incidencias)")
    return 0 if series else 1


if __name__ == "__main__":
    sys.exit(main())
