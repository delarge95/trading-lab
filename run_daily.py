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

from trading_lab import (alerts, backtest, evaluate, forecast, fred, insiders, lab, managers, predictions, prices,
                         report, sec, signals, site, universe)

ROOT = Path(__file__).parent


def load_env(path: Path = ROOT / ".env") -> None:
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def _previous_snapshot(history: dict, asof: str) -> dict | None:
    """Última foto diaria anterior a `asof` (así una segunda corrida el mismo día no borra las alertas de cambio)."""
    older = [d for d in history if d < asof]
    return history[max(older)] if older else None


def run_engine(res: dict, today) -> dict:
    ucfg = universe.load_config()
    upx, failed = universe.load_prices(ucfg["tickers"] + [ucfg["benchmark"]], today=today)
    bench = ucfg["benchmark"]
    fc = forecast.run(upx, bench)
    P = forecast.price_frame(upx, bench)
    lab_res = lab.run(P, bench)
    ledger = lab.update_ledger(ROOT / "data" / "picks_ledger.json", P, bench, today)

    cmap_path = ROOT / "data" / "cusip_map.json"
    cmap = json.loads(cmap_path.read_text(encoding="utf-8")) if cmap_path.exists() else {}
    hist_path = ROOT / "data" / "forecast_history.json"
    history = json.loads(hist_path.read_text(encoding="utf-8")) if hist_path.exists() else {}
    snap = alerts.snapshot(fc, res.get("macro"))
    al = alerts.build(fc, _previous_snapshot(history, fc["asof"]), res.get("macro"), res.get("insiders"),
                      res.get("managers"), cmap, today.isoformat())
    history[fc["asof"]] = snap
    for d in sorted(history)[:-30]:           # se conservan 30 fotos diarias
        history.pop(d)
    hist_path.write_text(json.dumps(history), encoding="utf-8")

    dash = site.build_dashboard(fc, lab_res, ledger, al, res.get("macro"), {"date": today.isoformat()})
    site.write(dash, ROOT / "docs" / "data" / "dashboard.json")

    risk_table = []
    for t, v in fc["tickers"].items():
        r = v["risk"].get(21)
        if r:
            risk_table.append({"ticker": t, "dd21": r.get("dd_cal", r["dd"]["10"]), "p10": r["p10"], "p50": r["p50"],
                               "p90": r["p90"], "vol63": v.get("vol63")})
    risk_table.sort(key=lambda r: r["dd21"], reverse=True)
    res["sources"]["Motor v2"] = (f"OK ({fc['n_stocks']} acciones" + (f"; sin precios: {', '.join(failed)}" if failed else "")
                                  + f"; {al['counts']['alta']} alertas altas)")
    return {"asof": fc["asof"], "n_stocks": fc["n_stocks"], "eval": fc["eval"], "risk_validation": fc["risk_validation"],
            "risk_table": risk_table[:15], "lab": lab_res, "ledger": ledger, "alerts": al,
            "push": alerts.push_text(al)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-sec", action="store_true", help="omitir 13F e insiders")
    ap.add_argument("--no-insiders", action="store_true")
    ap.add_argument("--no-managers", action="store_true", help="omitir el track record de gestores")
    ap.add_argument("--no-universe", action="store_true", help="omitir el motor de probabilidades del S&P 100")
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

    # Motor v2: probabilidades calibradas, riesgo, laboratorio de reglas, libro de picks, alertas y panel (S&P 100)
    if not args.no_universe:
        try:
            res["engine"] = run_engine(res, today)
        except Exception as exc:  # noqa: BLE001 - el informe base sigue saliendo aunque el motor falle
            res["errors"].append(f"motor v2: {exc}")
            res["sources"]["Motor v2"] = f"FALLÓ: {exc}"

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
