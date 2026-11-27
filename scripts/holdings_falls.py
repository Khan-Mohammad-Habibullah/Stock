#!/usr/bin/env python3
"""Shared pieces for the two holdings tables on the My holdings tab ("Rise setups in your holdings (+20% within 42 trading days)" and
"Fall patterns in your holdings (−20% within two months)"). New module: it only READS the existing setups modules (setups_lib, setups_model), never changes them.

Fall setups: six fixed rules, written down before testing (see FALL_RULES). What counts as a fall: the lowest close in the next 42 trading days
(two months) is at least 20% below the setup-day close. (The rules were first tested against two other outcomes, a 10% fall within a month and a
fall of more than 20% within three; the outcome was simplified afterwards, so the test of this one is less independent.)
"""
import math

import numpy as np
import pandas as pd

import setups_lib as SL
import setups_model as SM

M2 = 42                         # trading days in two months
FALL = 0.20                     # the fall that counts: a close at least 20% under the setup-day close within two months
FALL_GAP = M2                   # one case per stock and fall rule every 42 trading days
MONTHS = [21 * m for m in range(1, 7)]   # month 1..6 = 21..126 trading days after the setup day
WINDOW = 10                     # a holding is listed when a setup happened on one of its last 10 completed trading days
EDGE_MIN = 0.05                 # a fall rule must beat the same-volatility base rate by 5 points in the build AND the check years
MAX_SHARE = 0.5                 # no single market, year or calendar month may hold more than half of a rule's cases

MKT_OF_EXCHANGE = {"NASDAQ": "USA", "NYSE": "USA", "AMEX": "USA", "OMXSTO": "Sweden", "OSL": "Norway", "OMXCOP": "Denmark",
                   "OMXHEX": "Finland", "XETR": "Germany", "TSX": "Canada"}


def _failed_breakout(df):
    brk = df.c > df.hh40
    lvl = df.hh40.where(brk).ffill()                       # the 40-day high that was broken most recently
    pos = pd.Series(np.where(brk, np.arange(len(df)), np.nan), index=df.index).ffill()
    since = np.arange(len(df)) - pos                       # sessions since that breakout
    return (since >= 1) & (since <= 5) & (df.c < lvl) & (df.vr >= 1.5)


FALL_RULES = {
    "f_trend": dict(name="Downtrend, momentum falling", short="below the 50- and 200-day averages with a falling MACD histogram",
                    conds=[("t50", "Close below the 50-day average", lambda d: d.c < d.sma50),
                           ("t200", "Close below the 200-day average", lambda d: d.c < d.sma200),
                           ("macd", "MACD histogram lower than the day before", lambda d: d.macdh < d.macdh.shift(1))]),
    "f_break": dict(name="Breakdown on heavy volume", short="close below the lowest close of the previous 40 sessions on 1.5x volume",
                    conds=[("low40", "Close below the lowest close of the previous 40 sessions", lambda d: d.c < d.ll40),
                           ("vol", "Volume at least 1.5 times the 50-day average", lambda d: d.vr >= 1.5)]),
    "f_failed": dict(name="Failed breakout", short="back under a 40-day high it broke in the last 5 sessions, on 1.5x volume",
                     conds=[("fail", "Closed above its 40-day high in the last 5 sessions and is back under that level today", lambda d: _failed_breakout(d)),
                            ("vol", "Volume at least 1.5 times the 50-day average", lambda d: d.vr >= 1.5)]),
    "f_weak": dict(name="Weak and slipping", short="RSI under 40 with a falling 50-day average",
                   conds=[("rsi", "RSI (14) under 40", lambda d: d.rsi < 40),
                          ("slope", "50-day average lower than 10 sessions ago", lambda d: d.slope50 < 0)]),
    "f_stretch": dict(name="Stretched volatile stock", short="daily range 5% or more and more than 25% above the 50-day average",
                      conds=[("atr5", "Daily range (14-day average true range) at least 5% of the price", lambda d: d.atr >= 0.05),
                             ("ext", "Close more than 25% above the 50-day average", lambda d: d.vs50 > 0.25)]),
    "f_wash": dict(name="Market washout", short="fewer than 20% of the market's stocks above their 50-day average",
                   conds=[("wash", "Market washout: fewer than 20% of the market's stocks close above their own 50-day average", lambda d: d.breadth < SL.WASH_BELOW)]),
}
FALL_ORDER = list(FALL_RULES)


def apply_fall_rules(df):
    """Adds f_*_met, f_* and f_*_<cond> columns (needs the features of setups_lib plus 'breadth')."""
    for k in FALL_ORDER:
        cs = FALL_RULES[k]["conds"]
        flags = pd.concat([fn(df).fillna(False).astype(bool).astype(int) for _, _, fn in cs], axis=1)
        df[k + "_met"] = flags.sum(axis=1).values
        df[k] = (df[k + "_met"] == len(cs)).values
        for (ck, _, _), col in zip(cs, flags.columns):
            df["%s_%s" % (k, ck)] = flags[col].astype(bool).values
    return df


def fall_level(df):
    """The level at which a fall setup no longer holds: the highest close of the last 10 sessions (setup day included)."""
    return df.c.rolling(10, min_periods=1).max()


def outcomes(df):
    """Adds the fall outcome (a close at least 20% under the setup-day close within 42 trading days) and the month-by-month price changes (NaN until known)."""
    c = df.c.values.astype(float)
    n = len(c)
    rev = pd.Series(c[::-1])
    mn = rev.shift(1).rolling(M2, min_periods=1).min().values[::-1] / c - 1       # lowest close of the next <=42 sessions
    avail = np.minimum(np.arange(n)[::-1], M2)
    hit = mn <= -FALL
    done = avail >= M2
    v = np.where(done | hit, hit.astype(float), np.nan)
    v[-1] = np.nan
    df["fall"] = v
    # trading days from the setup day to the first close that is 20% or more lower (within 42 days); NaN when it never happens
    from numpy.lib.stride_tricks import sliding_window_view
    pad = np.concatenate([c[1:], np.full(M2, np.nan)])
    win = sliding_window_view(pad, M2)[:n]                         # row i: the closes of days i+1 .. i+42
    with np.errstate(invalid="ignore"):
        h2 = win <= c[:, None] * (1 - FALL)
    df["dfall"] = np.where(h2.any(axis=1), h2.argmax(axis=1) + 1, np.nan)
    for m, h in enumerate(MONTHS, start=1):
        fwd = np.full(n, np.nan)
        if n > h:
            fwd[:-h] = c[h:] / c[:-h] - 1
        df["m%d" % m] = fwd
    return df


def month_stats(X):
    """X: DataFrame with m1..m6 columns -> list of 6 dicts (n, median, p25, p75, above, below)."""
    out = []
    for m in range(1, 7):
        v = X["m%d" % m].dropna().values
        if len(v) == 0:
            out.append(dict(n=0))
            continue
        out.append(dict(n=int(len(v)), med=float(np.median(v)), p25=float(np.percentile(v, 25)), p75=float(np.percentile(v, 75)),
                        above=float((v > 0).mean()), below=float((v < 0).mean())))
    return out


# ---------------------------------------------------------------- estimate for a fall (same method as setups_model, with the fall-rule flags)
def design(flags, num, market, large, mean=None, std=None):
    X0, mean, std = SM.design(np.zeros((len(flags), len(SL.ORDER))), num, market, large, mean, std)
    # replace the twelve upside flags with the six fall-rule flags
    X = np.column_stack([X0[:, :1], np.asarray(flags, float), X0[:, 1 + len(SL.ORDER):]])
    return X, mean, std


def names():
    return ["intercept"] + ["rule:" + k for k in FALL_ORDER] + SM.NUM + ["market:" + m for m in SM.MARKETS] + ["size:large"]


def fit_and_check(R, y_col, cut, build_rates):
    """R: declustered resolved cases (one row per stock-day, with the fall-rule flags, features, market, large, y_col).
    Fitted on the build years only, judged unchanged on the check years against the plain rule rate."""
    R = R[R[y_col].notna()]
    flags = R[FALL_ORDER].fillna(False).astype(int).values
    tr = (R.date < cut).values
    te = ~tr
    y = R[y_col].values.astype(float)
    num = SM.numeric(R)
    Xtr, mean, std = design(flags[tr], {k: v[tr] for k, v in num.items()}, R.market.values[tr], R.large.values[tr])
    w = SM.fit_logit(Xtr, y[tr])
    Xte, _, _ = design(flags[te], {k: v[te] for k, v in num.items()}, R.market.values[te], R.large.values[te], mean, std)
    p_model = SM.predict(Xte, w)
    rt = np.array([build_rates.get(k) or 0.0 for k in FALL_ORDER])
    p_base = np.max(np.where(flags[te] == 1, rt[None, :], 0.0), axis=1)
    yte = y[te]
    b_model, b_base = SM.brier(p_model, yte), SM.brier(p_base, yte)
    use = b_model < b_base
    gm, gb = SM.groups(p_model, yte), SM.groups(p_base, yte)
    g = gm if use else gb
    return dict(kind="model" if use else "setup_average", brier_model=b_model, brier_setup=b_base, n_train=int(tr.sum()), n_check=int(te.sum()),
                base_rate_check=float(yte.mean()), features=names(), coef=[float(x) for x in w], mean=[float(x) for x in mean], std=[float(x) for x in std],
                ridge=SM.RIDGE, calibration_model=gm, calibration_setup=gb, cap=float(max(x["actual"] for x in g)),
                gap=float(np.mean([abs(x["est"] - x["actual"]) for x in g])), round_to=SM.ROUND, cut=str(pd.Timestamp(cut).date()))


def estimate(model, rules, row, market, size, rule_rate):
    if not model:
        return None
    if model["kind"] == "model":
        flags = [[1 if k in rules else 0 for k in FALL_ORDER]]
        num = {k: np.array([v]) for k, v in SM.numeric(row).items()}
        X, _, _ = design(flags, num, [market], [1 if size == "Large" else 0], np.array(model["mean"]), np.array(model["std"]))
        p = float(SM.predict(X, np.array(model["coef"]))[0])
    else:
        if rule_rate is None:
            return None
        p = float(rule_rate)
    step = model["round_to"]
    est = round(min(p, model["cap"]) / step) * step
    if est > model["cap"] + 1e-9:
        est = math.floor(model["cap"] / step + 1e-9) * step
    return dict(est=round(est, 2), lo=round(max(0.0, est - model["gap"]), 3), hi=round(min(1.0, est + model["gap"]), 3), kind=model["kind"])
