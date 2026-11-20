"""Motor de probabilidades calibrado fuera de muestra.

Para cada acción y horizonte estima P(subir), P(superar a SPY), rangos de retorno (percentiles) y
probabilidad de caídas fuertes. Principios:
- Las variables usan solo precios hasta la fecha t (sin anticipación); el escalado se ajusta con datos de entrenamiento.
- Walk-forward con purga: para predecir desde la fecha s solo se entrena con filas cuyo resultado ya era conocido en s.
- La probabilidad final se calibra (Platt) con las predicciones fuera de muestra: si el modelo no tiene habilidad,
  la calibración la lleva sola a la tasa base. El informe declara si hay o no ventaja estadística (BSS con IC).
- Los rangos de retorno y el riesgo de caída usan simulación histórica filtrada por volatilidad (EWMA).
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

HORIZONS = (5, 21, 63)
STEP = 5                 # el panel se muestrea cada 5 ruedas
MIN_HIST = 252           # ruedas mínimas de historia para construir las variables
FEATURES = ["r1m", "r3m", "r6m", "mom12_1", "vol63", "dist_high", "ma_gap"]
MARKET = ["m_mom12_1", "m_vol63", "m_dist_high"]
EWMA_LAMBDA = 0.94


# ------------------------------------------------------------------ datos y variables
def price_frame(series: dict[str, list[tuple[str, float]]], bench: str) -> pd.DataFrame:
    """Matriz fechas x tickers alineada al calendario del benchmark (ffill de huecos cortos)."""
    cols = {t: pd.Series({d: p for d, p in s}) for t, s in series.items()}
    df = pd.DataFrame(cols)
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    cal = df[bench].dropna().index
    return df.reindex(cal).ffill(limit=3)


def raw_features(P: pd.DataFrame) -> dict[str, pd.DataFrame]:
    lr = np.log(P / P.shift(1))
    return {
        "r1m": P / P.shift(21) - 1,
        "r3m": P / P.shift(63) - 1,
        "r6m": P / P.shift(126) - 1,
        "mom12_1": P.shift(21) / P.shift(252) - 1,
        "vol63": lr.rolling(63).std() * math.sqrt(252),
        "dist_high": P / P.rolling(252).max() - 1,
        "ma_gap": P / P.rolling(200).mean() - 1,
    }


class Panel:
    """Panel (fecha, acción) con variables y retornos futuros por horizonte."""

    def __init__(self, P: pd.DataFrame, bench: str):
        self.bench = bench
        self.stocks = [c for c in P.columns if c != bench]
        self.P = P
        self.T = len(P)
        stock_P = P[self.stocks]
        raw = raw_features(stock_P)
        bench_raw = raw_features(P[[bench]])
        xs = {f: raw[f].rank(axis=1, pct=True) - 0.5 for f in FEATURES}      # rango centrado en [-0.5, 0.5]
        mk = {"m_mom12_1": bench_raw["mom12_1"][bench], "m_vol63": bench_raw["vol63"][bench],
              "m_dist_high": bench_raw["dist_high"][bench]}
        self.idx = np.arange(self.T - 1, MIN_HIST - 1, -STEP)[::-1]            # incluye el último día
        cols = []
        for f in FEATURES:
            cols.append(xs[f].values[self.idx, :])
        for f in MARKET:
            cols.append(np.repeat(mk[f].values[self.idx][:, None], len(self.stocks), axis=1))
        stack = np.stack(cols, axis=-1)                                         # (S, N, F)
        S, N, F = stack.shape
        self.X = stack.reshape(S * N, F)
        self.t = np.repeat(self.idx, N)
        self.j = np.tile(np.arange(N), S)
        self.ok = np.isfinite(self.X).all(axis=1)
        self.fwd = {}
        self.fwd_bench = {}
        for h in HORIZONS:
            r = (stock_P.shift(-h) / stock_P - 1).values[self.idx, :]
            b = (P[bench].shift(-h) / P[bench] - 1).values[self.idx]
            self.fwd[h] = r.reshape(-1)
            self.fwd_bench[h] = np.repeat(b, N)

    def target(self, kind: str, h: int) -> np.ndarray:
        r, b = self.fwd[h], self.fwd_bench[h]
        y = np.full(len(r), np.nan)
        m = np.isfinite(r) & (np.isfinite(b) if kind == "rel" else True)
        y[m] = (r[m] > (b[m] if kind == "rel" else 0.0)).astype(float)
        return y


# ------------------------------------------------------------------ modelo
def fit_logit(X: np.ndarray, y: np.ndarray, l2: float = 50.0, iters: int = 30) -> np.ndarray:
    n, k = X.shape
    Xb = np.hstack([np.ones((n, 1)), X])
    w = np.zeros(k + 1)
    R = l2 * np.eye(k + 1)
    R[0, 0] = 0.0
    for _ in range(iters):
        z = np.clip(Xb @ w, -30, 30)
        p = 1 / (1 + np.exp(-z))
        g = Xb.T @ (p - y) + R @ w
        H = (Xb.T * (p * (1 - p) + 1e-9)) @ Xb + R
        step = np.linalg.solve(H, g)
        w -= step
        if np.abs(step).max() < 1e-9:
            break
    return w


def predict(w: np.ndarray, mu: np.ndarray, sd: np.ndarray, X: np.ndarray) -> np.ndarray:
    z = np.clip(w[0] + ((X - mu) / sd) @ w[1:], -30, 30)
    return 1 / (1 + np.exp(-z))


def _fit_scaled(X: np.ndarray, y: np.ndarray, l2: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    mu, sd = X.mean(axis=0), X.std(axis=0)
    sd[sd == 0] = 1.0
    return fit_logit((X - mu) / sd, y, l2), mu, sd


def logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def platt(p_raw: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """y ~ sigmoid(a + b*logit(p)) con b en [0, 1.5]; si b<=0 la salida es la tasa base."""
    w = fit_logit(logit(p_raw)[:, None], y, l2=1.0)
    a, b = float(w[0]), float(w[1])
    if b <= 0:
        base = float(y.mean())
        return float(math.log(base / (1 - base))), 0.0
    return a, min(b, 1.5)


def apply_platt(p_raw: np.ndarray, a: float, b: float) -> np.ndarray:
    return 1 / (1 + np.exp(-(a + b * logit(p_raw))))


# ------------------------------------------------------------------ evaluación fuera de muestra
def wilson(k: float, n: float, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return 0.0, 1.0
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, c - h), min(1.0, c + h)


def walk_forward(panel: Panel, kind: str, h: int, min_train_days: int = 756, test_days: int = 252,
                 l2: float = 50.0) -> dict:
    y = panel.target(kind, h)
    valid = panel.ok & np.isfinite(y)
    s = MIN_HIST + min_train_days
    rows = {"p": [], "y": [], "base": [], "t": [], "ret": []}
    while s < panel.T:
        train = valid & (panel.t + h <= s)                 # purga: resultado ya conocido en s
        test = valid & (panel.t >= s) & (panel.t < s + test_days)
        if train.sum() < 2000 or test.sum() == 0:
            s += test_days
            continue
        w, mu, sd = _fit_scaled(panel.X[train], y[train], l2)
        rows["p"].append(predict(w, mu, sd, panel.X[test]))
        rows["y"].append(y[test])
        rows["base"].append(np.full(test.sum(), y[train].mean()))
        rows["t"].append(panel.t[test])
        rows["ret"].append(panel.fwd[h][test] - (panel.fwd_bench[h][test] if kind == "rel" else 0.0))
        s += test_days
    if not rows["p"]:
        return {}
    return {k: np.concatenate(v) for k, v in rows.items()}


def _auc(p: np.ndarray, y: np.ndarray) -> float:
    r = pd.Series(p).rank().values
    n1 = y.sum()
    n0 = len(y) - n1
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)) if n1 and n0 else float("nan")


def _block_bootstrap(blocks: np.ndarray, stats: np.ndarray, fn, n_boot: int = 1000, seed: int = 0) -> tuple[float, float]:
    """IC95% por remuestreo de bloques de fechas. stats: (n_filas, k) sumas por fila; fn(sumas)->estadístico."""
    rng = np.random.default_rng(seed)
    ub = np.unique(blocks)
    sums = np.array([stats[blocks == b].sum(axis=0) for b in ub])
    out = []
    for _ in range(n_boot):
        pick = rng.integers(0, len(ub), len(ub))
        out.append(fn(sums[pick].sum(axis=0)))
    return float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))


def evaluate(oos: dict, h: int, top_n: int = 10) -> dict:
    """Métricas fuera de muestra: Brier skill, AUC, calibración, IC de rango y exceso del top-N."""
    p, y, base, t, ret = (oos[k] for k in ("p", "y", "base", "t", "ret"))
    a, b = platt(p, y)
    pc = apply_platt(p, a, b)
    blocks = t // (STEP * 10)
    sq_m, sq_b = (pc - y) ** 2, (base - y) ** 2
    bss = 1 - sq_m.sum() / sq_b.sum()
    lo, hi = _block_bootstrap(blocks, np.stack([sq_m, sq_b], axis=1), lambda s: 1 - s[0] / s[1])
    raw_bss = 1 - ((p - y) ** 2).sum() / sq_b.sum()
    # IC de rango y exceso del top-N por fecha
    df = pd.DataFrame({"t": t, "p": p, "ret": ret})
    ics, tops, tb = [], [], []
    for d, g in df.groupby("t"):
        if len(g) < 20:
            continue
        ics.append(g["p"].rank().corr(g["ret"].rank()))
        top = g.nlargest(top_n, "p")["ret"].mean()
        tops.append(top - g["ret"].mean())
        tb.append(d // (STEP * 10))
    ics, tops, tb = np.array(ics), np.array(tops), np.array(tb)
    ok = np.isfinite(ics)
    ic_lo, ic_hi = _block_bootstrap(tb[ok], np.stack([ics[ok], np.ones(ok.sum())], axis=1), lambda s: s[0] / s[1])
    ex_lo, ex_hi = _block_bootstrap(tb, np.stack([tops, np.ones(len(tops))], axis=1), lambda s: s[0] / s[1])
    # fiabilidad por deciles de la probabilidad calibrada
    edges = np.quantile(pc, np.linspace(0, 1, 11))
    overlap = max(1, math.ceil(h / STEP))
    bins = []
    for i in range(10):
        m = (pc >= edges[i]) & (pc <= edges[i + 1] if i == 9 else pc < edges[i + 1])
        if m.sum() == 0:
            continue
        n_eff = m.sum() / overlap
        k_eff = y[m].mean() * n_eff
        wl, wh = wilson(k_eff, n_eff)
        bins.append({"lo_edge": float(edges[i]), "hi_edge": float(edges[i + 1]), "n": int(m.sum()),
                     "p_mean": float(pc[m].mean()), "freq": float(y[m].mean()), "ci": (wl, wh)})
    has_edge = lo > 0
    return {
        "n_oos": int(len(y)), "base_rate": float(y.mean()), "platt": (a, b),
        "bss": float(bss), "bss_ci": (lo, hi), "bss_raw": float(raw_bss), "auc": _auc(p, y),
        "ic": float(np.nanmean(ics)), "ic_ci": (ic_lo, ic_hi),
        "top_excess": float(tops.mean()), "top_excess_ci": (ex_lo, ex_hi), "top_n": top_n,
        "bins": bins, "has_edge": bool(has_edge),
        "verdict": ("Ventaja estadística fuera de muestra" if has_edge else
                    "Sin ventaja demostrada: usar la tasa base como referencia"),
    }


def live(panel: Panel, kind: str, h: int, oos_eval: dict, l2: float = 50.0) -> dict[str, dict]:
    """Probabilidad calibrada actual por acción (modelo entrenado con todo el historial disponible)."""
    y = panel.target(kind, h)
    train = panel.ok & np.isfinite(y)
    w, mu, sd = _fit_scaled(panel.X[train], y[train], l2)
    last = panel.t == panel.T - 1
    last &= panel.ok
    p_raw = predict(w, mu, sd, panel.X[last])
    a, b = oos_eval["platt"]
    pc = apply_platt(p_raw, a, b)
    out = {}
    for j, pr_, pr_raw in zip(panel.j[last], pc, p_raw):
        lo, hi = None, None
        for bn in oos_eval["bins"]:
            if bn["lo_edge"] <= pr_ <= bn["hi_edge"]:
                lo, hi = bn["ci"]
        if lo is None and oos_eval["bins"]:
            bn = oos_eval["bins"][0] if pr_ < oos_eval["bins"][0]["lo_edge"] else oos_eval["bins"][-1]
            lo, hi = bn["ci"]
        out[panel.stocks[j]] = {"p": float(pr_), "p_raw": float(pr_raw), "lo": float(lo), "hi": float(hi)}
    return out


# ------------------------------------------------------------------ rangos de retorno y riesgo de caída (FHS)
def ewma_sigma(P: pd.DataFrame, lam: float = EWMA_LAMBDA) -> pd.DataFrame:
    lr = np.log(P / P.shift(1))
    return np.sqrt((lr ** 2).ewm(alpha=1 - lam, adjust=False).mean())


def risk_ranges(P: pd.DataFrame, stocks: list[str], horizons: tuple[int, ...] = (21, 63),
                dd_levels: tuple[float, ...] = (0.10, 0.20)) -> dict[str, dict]:
    """Percentiles de retorno y P(caída > x%) por simulación histórica filtrada por volatilidad."""
    sig = ewma_sigma(P[stocks])
    out: dict[str, dict] = {t: {} for t in stocks}
    for h in horizons:
        fwd = np.log(P[stocks].shift(-h) / P[stocks])
        fmin = np.log(P[stocks].iloc[::-1].rolling(h).min().iloc[::-1].shift(-1) / P[stocks])
        for t in stocks:
            s = sig[t]
            valid = fwd[t].notna() & fmin[t].notna() & (s > 0) & (np.arange(len(P)) > 100)
            if valid.sum() < 500:
                continue
            scale = s[valid] * math.sqrt(h)
            z = (fwd[t][valid] / scale).values
            zmin = (fmin[t][valid] / scale).values
            now = float(s.iloc[-1]) * math.sqrt(h)
            q = np.quantile(z, [0.10, 0.50, 0.90])
            out[t][h] = {
                "p10": float(math.exp(now * q[0]) - 1), "p50": float(math.exp(now * q[1]) - 1),
                "p90": float(math.exp(now * q[2]) - 1), "sigma": now,
                "dd": {f"{int(l * 100)}": float((zmin * now <= math.log(1 - l)).mean()) for l in dd_levels},
            }
    return out


def validate_risk(P: pd.DataFrame, stocks: list[str], h: int = 21, first: int = 1008, dd_level: float = 0.10) -> dict:
    """Valida fuera de muestra los rangos P10-P90 y la probabilidad de caída (solo con datos conocidos en cada fecha).

    En cada fecha t (cada 5 ruedas, desde `first`) se calculan los percentiles con la distribución histórica
    estandarizada de los resultados ya conocidos (t' <= t-h) y se compara con lo que ocurrió después.
    """
    sig = ewma_sigma(P[stocks])
    fwd = np.log(P[stocks].shift(-h) / P[stocks])
    fmin = np.log(P[stocks].iloc[::-1].rolling(h).min().iloc[::-1].shift(-1) / P[stocks])
    T = len(P)
    inside, below, above, preds, hits, blocks = [], [], [], [], [], []
    for t in range(first, T - h, STEP):
        for s in stocks:
            sg = sig[s].values
            f = fwd[s].values
            m = fmin[s].values
            if not (np.isfinite(sg[t]) and sg[t] > 0 and np.isfinite(f[t])):
                continue
            hist = np.arange(101, t - h + 1)
            ok = np.isfinite(f[hist]) & np.isfinite(m[hist]) & (sg[hist] > 0)
            if ok.sum() < 300:
                continue
            hi = hist[ok]
            scale = sg[hi] * math.sqrt(h)
            z = f[hi] / scale
            zmin = m[hi] / scale
            now = sg[t] * math.sqrt(h)
            q10, q90 = np.quantile(z, [0.10, 0.90]) * now
            inside.append(q10 <= f[t] <= q90)
            below.append(f[t] < q10)
            above.append(f[t] > q90)
            preds.append(float((zmin * now <= math.log(1 - dd_level)).mean()))
            hits.append(float(m[t] <= math.log(1 - dd_level)))
            blocks.append(t // (STEP * 10))
    if not inside:
        return {}
    inside, below, above = (np.array(a, dtype=float) for a in (inside, below, above))
    preds, hits, blocks = np.array(preds), np.array(hits), np.array(blocks)
    lo, hi_ = _block_bootstrap(blocks, np.stack([inside, np.ones(len(inside))], axis=1), lambda s: s[0] / s[1])
    thirds = np.quantile(preds, [1 / 3, 2 / 3])
    groups = np.digitize(preds, thirds)
    cal = [{"pred": float(preds[groups == g].mean()), "real": float(hits[groups == g].mean()),
            "n": int((groups == g).sum())} for g in range(3) if (groups == g).any()]
    base = hits.mean()
    brier = float(((preds - hits) ** 2).mean())
    brier_base = float(((base - hits) ** 2).mean())
    a, b = platt(preds, hits)
    brier_cal = float(((apply_platt(preds, a, b) - hits) ** 2).mean())
    return {
        "dd_platt": (a, b), "dd_brier_calibrated": brier_cal,
        "h": h, "n": int(len(inside)), "coverage80": float(inside.mean()), "coverage80_ci": (lo, hi_),
        "below_p10": float(below.mean()), "above_p90": float(above.mean()),
        "dd_level": dd_level, "dd_calibration": cal, "dd_base": float(base),
        "dd_brier": brier, "dd_brier_base": brier_base,
        "dd_skill": float(1 - brier / brier_base) if brier_base > 0 else None,
    }


# ------------------------------------------------------------------ orquestación
def run(series: dict[str, list[tuple[str, float]]], bench: str = "SPY",
        targets: tuple[tuple[str, int], ...] = (("up", 5), ("up", 21), ("up", 63), ("rel", 21)),
        validate: bool = True) -> dict:
    P = price_frame(series, bench)
    panel = Panel(P, bench)
    ev, lv = {}, {}
    for kind, h in targets:
        oos = walk_forward(panel, kind, h)
        if not oos:
            continue
        key = f"{kind}{h}"
        ev[key] = evaluate(oos, h)
        lv[key] = live(panel, kind, h, ev[key])
    rr = risk_ranges(P, panel.stocks)
    rv = {}
    if validate:
        for h in (21, 63):
            v = validate_risk(P, panel.stocks, h=h)
            if not v:
                continue
            rv[str(h)] = v
            a, b = v["dd_platt"]
            for t in panel.stocks:   # probabilidad de caída >10% calibrada con las predicciones fuera de muestra
                if h in rr.get(t, {}):
                    raw = rr[t][h]["dd"]["10"]
                    rr[t][h]["dd_cal"] = float(apply_platt(np.array([raw]), a, b)[0])
    last = P.iloc[-1]
    tickers = {}
    for t in panel.stocks:
        if pd.isna(last[t]):
            continue
        feats = {f: float(raw_features(P[[t]])[f][t].iloc[-1]) for f in ("mom12_1", "r1m", "vol63", "dist_high")}
        tickers[t] = {"price": float(last[t]), **{k: (None if math.isnan(v) else v) for k, v in feats.items()},
                      "p": {k: lv[k][t] for k in lv if t in lv[k]}, "risk": rr.get(t, {})}
    return {"asof": P.index[-1].strftime("%Y-%m-%d"), "n_stocks": len(tickers), "eval": ev, "tickers": tickers,
            "risk_validation": rv}
