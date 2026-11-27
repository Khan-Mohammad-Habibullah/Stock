#!/usr/bin/env python3
"""Estimated success rate for a stock in Table C: a logistic regression fitted on the build years only and judged on the check years.

Cases: the declustered past cases of all twelve setups (a stock-day is one row, with a flag for every setup that fired that day).
Outcome: the highest close in the next 42 trading days reached +20%.
Inputs, all known on the setup day: the setup flags, daily range (14-day average true range / price), distance from the 52-week high, RSI (14),
volume against its 50-day average (log), the market washout reading (share of the market's stocks above their own 50-day average),
market, and size (large or mid cap).

The model is used on the page only if its Brier score on the check years (from SPLIT) beats using each setup's own historical success rate
(measured on the build years only); otherwise the page shows the setup average. Estimates are capped at the highest actual success rate of any
calibration group and rounded to the nearest 5%. Used by setups_study.py (fit) and setups_daily.py (apply).
"""
import math

import numpy as np
import pandas as pd

import setups_lib as SL

NUM = ["atr", "from52h", "rsi", "lvr", "breadth"]
MARKETS = ["USA", "Sweden", "Denmark", "Germany", "Finland", "Norway", "Canada"]
RIDGE = 1.0          # mild L2 penalty on every weight except the intercept
ROUND = 0.05


def numeric(df):
    """The five numeric inputs from a frame with the feature columns (rows or a single row as a Series)."""
    g = lambda c: pd.to_numeric(df[c], errors="coerce")
    out = {
        "atr": np.clip(g("atr"), 0, 0.25),
        "from52h": np.clip(g("from52h"), -1, 0),
        "rsi": g("rsi") / 100.0,
        "lvr": np.log(np.clip(g("vr"), 0.05, 20)),
        "breadth": g("breadth"),
    }
    return out


def design(flags, num, market, large, mean=None, std=None):
    """flags: n x 12 0/1 (SL.ORDER); num: dict of arrays; market: list of names; large: 0/1 array. Returns (X with intercept first, mean, std)."""
    n = len(flags)
    cols = []
    for c in NUM:
        v = np.asarray(num[c], float)
        fill = {"rsi": 0.5, "breadth": 0.5}.get(c, 0.0)
        cols.append(np.where(np.isnan(v), fill, v))
    N = np.column_stack(cols)
    if mean is None:
        mean, std = N.mean(axis=0), N.std(axis=0)
        std[std == 0] = 1.0
    Z = (N - mean) / std
    M = np.array([[1.0 if m == k else 0.0 for k in MARKETS] for m in market])
    X = np.column_stack([np.ones(n), np.asarray(flags, float), Z, M, np.asarray(large, float)])
    return X, mean, std


def names():
    return ["intercept"] + ["setup:" + k for k in SL.ORDER] + NUM + ["market:" + m for m in MARKETS] + ["size:large"]


def fit_logit(X, y, lam=RIDGE, iters=60):
    w = np.zeros(X.shape[1])
    pen = np.full(X.shape[1], lam)
    pen[0] = 0.0
    for _ in range(iters):
        z = np.clip(X @ w, -30, 30)
        p = 1 / (1 + np.exp(-z))
        W = p * (1 - p)
        H = X.T @ (X * W[:, None]) + np.diag(pen)
        g = X.T @ (y - p) - pen * w
        step = np.linalg.solve(H, g)
        w += step
        if np.max(np.abs(step)) < 1e-8:
            break
    return w


def predict(X, w):
    return 1 / (1 + np.exp(-np.clip(X @ w, -30, 30)))


def groups(p, y, k=5):
    """Five groups by estimated rate: cases, mean estimate, actual success rate."""
    s = pd.DataFrame({"p": p, "y": y})
    try:
        s["g"] = pd.qcut(s.p.rank(method="first"), k, labels=False)
    except ValueError:
        s["g"] = 0
    out = []
    for _, g in s.groupby("g"):
        out.append(dict(n=int(len(g)), est=float(g.p.mean()), actual=float(g.y.mean())))
    return out


def brier(p, y):
    return float(np.mean((np.asarray(p) - np.asarray(y)) ** 2))


def fit_and_check(A, cases, uni_size, cut):
    """A: all stock-days with setup columns, market, hit. cases: {setup: DataFrame of its declustered resolved cases (index = rows of A)}.
    Returns the 'model' block that is stored in data/setups_study.json."""
    idx = sorted(set().union(*[set(X.index) for X in cases.values()]))
    R = A.loc[idx].copy()
    R["large"] = (R.sym.map(uni_size) == "Large").astype(int)
    flags = R[SL.ORDER].fillna(False).astype(int).values
    tr = (R.date < cut).values
    te = ~tr
    y = R.hit.values.astype(float)
    num = numeric(R)
    Xtr, mean, std = design(flags[tr], {k: v[tr] for k, v in num.items()}, R.market.values[tr], R.large.values[tr])
    w = fit_logit(Xtr, y[tr])
    Xte, _, _ = design(flags[te], {k: v[te] for k, v in num.items()}, R.market.values[te], R.large.values[te], mean, std)
    p_model = predict(Xte, w)
    # plain setup rate, measured on the build years only; a stock-day with several setups gets the highest of its setups' rates
    rate_tr = {k: float(cases[k][cases[k].date < cut].hit.mean()) for k in SL.ORDER if len(cases[k][cases[k].date < cut])}
    rt = np.array([rate_tr.get(k, 0.0) for k in SL.ORDER])
    p_base = np.max(np.where(flags[te] == 1, rt[None, :], 0.0), axis=1)
    yte = y[te]
    b_model, b_base = brier(p_model, yte), brier(p_base, yte)
    use = b_model < b_base
    gm, gb = groups(p_model, yte), groups(p_base, yte)
    g = gm if use else gb
    cap = max(x["actual"] for x in g)
    gap = float(np.mean([abs(x["est"] - x["actual"]) for x in g]))
    # in-sample fit on the build years, for reference
    p_tr = predict(Xtr, w)
    return dict(
        kind="model" if use else "setup_average",
        brier_model=b_model, brier_setup=b_base, n_train=int(tr.sum()), n_check=int(te.sum()),
        base_rate_check=float(yte.mean()), brier_train=brier(p_tr, y[tr]),
        features=names(), coef=[float(x) for x in w], mean=[float(x) for x in mean], std=[float(x) for x in std], ridge=RIDGE,
        calibration_model=gm, calibration_setup=gb, cap=float(cap), gap=gap, round_to=ROUND,
        build_rates={k: v for k, v in rate_tr.items()},
        cut=str(pd.Timestamp(cut).date()))


def estimate(model, setups, row, market, size, setup_rate):
    """One estimate for a stock. setups: the keys of all setups it matches; row: its feature row on the setup day (breadth etc.);
    setup_rate: historical success rate of its highest-rate setup (used when the model did not beat it).
    Returns dict(est, lo, hi, kind) with est rounded to the nearest 5%, never above the highest actual calibration-group rate."""
    if not model:
        return None
    if model["kind"] == "model":
        flags = [[1 if k in setups else 0 for k in SL.ORDER]]
        num = {k: np.array([v]) for k, v in numeric(row).items()}
        X, _, _ = design(flags, num, [market], [1 if size == "Large" else 0], np.array(model["mean"]), np.array(model["std"]))
        p = float(predict(X, np.array(model["coef"]))[0])
    else:
        if setup_rate is None:
            return None
        p = float(setup_rate)
    step = model["round_to"]
    est = round(min(p, model["cap"]) / step) * step
    if est > model["cap"] + 1e-9:                       # rounding must not lift it above the best calibration group
        est = math.floor(model["cap"] / step + 1e-9) * step
    return dict(est=round(est, 2), lo=round(max(0.0, est - model["gap"]), 3), hi=round(min(1.0, est + model["gap"]), 3), kind=model["kind"])
