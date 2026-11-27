#!/usr/bin/env python3
"""Month-by-month price forecast for the two holdings tables (Rise setups / Fall patterns in your holdings). New module; it only reads setups_lib.

For each horizon h = 21, 42, ..., 126 trading days after the latest close:
  * target: the log change of the close over h days, divided by the stock's volatility over that span (60-day realised volatility x sqrt(h/252));
  * model (variant B, the one used): ridge regression of how much better or worse than the other stocks on the same day the stock did
    (the scaled change minus that day's average), on what is known on the day (the twelve setups and six fall rules, daily range, distance from
    the 52-week high, RSI, distance from the 50- and 200-day averages, slope of the 50-day, volume, the market washout reading, the last 1, 3
    and 6 months' change, the volatility itself and the market; not size, which is today's rank and would look ahead), fitted on days whose h-day outcome was known before SPLIT (build years);
  * forecast: the no-signal range (25th, 50th and 75th percentiles of the scaled change on the build years, which holds about half of the
    outcomes) shifted by the model's tilt for this stock; the market's own swings are not forecast;
  * variant A (first attempt, kept only for the record): the same inputs predicting the whole change with the model's own error spread.
    It did worse than the no-signal forecast on the check years at every horizon, so B was tried after seeing that result, which makes
    B's check less independent;
  * check: on the days from SPLIT (check years), unchanged, against a no-signal forecast (the same volatility scaling with the build years'
    average drift and spread). Pinball (quantile) loss over the three percentiles; B is used for a horizon only if it is lower.
"""
import numpy as np
import pandas as pd

import setups_lib as SL

H = [21 * m for m in range(1, 7)]
Q = [0.25, 0.5, 0.75]
RIDGE = 50.0
STEP = 5                     # every 5th trading day per stock (neighbouring days share almost the same future)
MARKETS = ["USA", "Sweden", "Denmark", "Germany", "Finland", "Norway", "Canada"]
NUM = ["atr", "from52h", "rsi", "vs50", "vs200", "slope50", "lvr", "breadth", "r21", "r63", "r126", "lvol", "vratio"]


def add_inputs(df):
    """Adds the forecast inputs that setups_lib does not already compute (past data only), and the h-day outcomes."""
    c = df.c.astype(float)
    lr = np.log(c).diff()
    df["rv60"] = lr.rolling(60).std() * np.sqrt(252)
    df["sigma"] = df.rv60.clip(0.10, 1.50)
    for n in (21, 63, 126):
        df["r%d" % n] = np.log(c / c.shift(n))
    lc = np.log(c.values)
    for h in H:
        y = np.full(len(c), np.nan)
        if len(c) > h:
            y[:-h] = lc[h:] - lc[:-h]
        df["y%d" % h] = y
        end = df.date.shift(-h)
        df["end%d" % h] = end
    return df


def numeric(df):
    g = lambda col: pd.to_numeric(df[col], errors="coerce") if col in df else pd.Series(np.nan, index=df.index)
    out = {
        "atr": g("atr").clip(0, 0.25), "from52h": g("from52h").clip(-1, 0), "rsi": g("rsi") / 100, "vs50": g("vs50").clip(-0.5, 0.5),
        "vs200": g("vs200").clip(-0.9, 1.5), "slope50": g("slope50").clip(-0.3, 0.3), "lvr": np.log(g("vr").clip(0.05, 20)), "breadth": g("breadth"),
        "r21": g("r21").clip(-1, 1), "r63": g("r63").clip(-1.5, 1.5), "r126": g("r126").clip(-2, 2), "lvol": np.log(g("sigma")),
        "vratio": (g("rv20") / g("rv60")).clip(0.2, 5),
    }
    return out


def flag_cols(fall_order):
    return list(SL.ORDER) + list(fall_order)


def design(df, fall_order, mean=None, std=None):
    num = numeric(df)
    N = np.column_stack([np.asarray(num[c], float) for c in NUM])
    fill = np.array([0, -0.3, 0.5, 0, 0, 0, 0, 0.5, 0, 0, 0, np.log(0.3), 1.0])
    N = np.where(np.isnan(N), fill[None, :], N)
    if mean is None:
        mean, std = N.mean(axis=0), N.std(axis=0)
        std[std == 0] = 1.0
    Z = (N - mean) / std
    F = np.column_stack([df[k].fillna(False).astype(float).values if k in df else np.zeros(len(df)) for k in flag_cols(fall_order)])
    mk = df["market"].values
    M = np.column_stack([(mk == m).astype(float) for m in MARKETS])
    # no size input: "large" is today's rank, and companies that are large today are mostly the ones that rose, so it would look ahead
    return np.column_stack([np.ones(len(df)), Z, F, M]), mean, std


def names(fall_order):
    return ["intercept"] + NUM + ["flag:" + k for k in flag_cols(fall_order)] + ["market:" + m for m in MARKETS]


def pinball(y, q, p):
    d = y - q
    return float(np.mean(np.maximum(p * d, (p - 1) * d)))


def fit_and_check(A, fall_order, cut):
    """A: stock-days (sampled) with features, flags, market, large, sigma and the y/end columns. Returns the 'forecast' block."""
    out = dict(horizons=H, quantiles=Q, ridge=RIDGE, step=STEP, features=names(fall_order), cut=str(pd.Timestamp(cut).date()), h={})
    X_all, mean, std = design(A, fall_order)
    out.update(mean=[float(x) for x in mean], std=[float(x) for x in std])
    pen = np.full(X_all.shape[1], RIDGE)
    pen[0] = 0.0
    for h in H:
        y = A["y%d" % h].values
        sc = A["sigma"].values * np.sqrt(h / 252)
        ok = ~np.isnan(y) & ~np.isnan(sc)
        tr = ok & (A["end%d" % h] < cut).values              # outcome known before the check years began
        te = ok & (A.date >= cut).values
        z = np.where(ok, y / np.where(ok, sc, 1), np.nan)
        Xt, zt = X_all[tr], z[tr]
        # variant B: relative to the same day's average of all stocks (the market's own swings are not forecast)
        dmean = pd.Series(zt).groupby(A.date.values[tr]).transform("mean").values
        wB = np.linalg.solve(Xt.T @ Xt + np.diag(pen), Xt.T @ (zt - dmean))
        w = np.linalg.solve(Xt.T @ Xt + np.diag(pen), Xt.T @ zt)
        res = zt - Xt @ w
        rq = [float(np.quantile(res, p)) for p in Q]
        bq = [float(np.quantile(zt, p)) for p in Q]
        zh = X_all[te] @ w
        yte, ste = y[te], sc[te]
        lm = np.mean([pinball(yte, ste * (zh + rq[i]), p) for i, p in enumerate(Q)])
        lb = np.mean([pinball(yte, ste * bq[i], p) for i, p in enumerate(Q)])
        cov_m = float(np.mean((yte >= ste * (zh + rq[0])) & (yte <= ste * (zh + rq[2]))))
        cov_b = float(np.mean((yte >= ste * bq[0]) & (yte <= ste * bq[2])))
        # direction: how often the model's median and the outcome were on the same side of the no-signal median
        dm = float(np.mean(np.sign(zh + rq[1] - bq[1]) == np.sign(yte / ste - bq[1])))
        tB = X_all[te] @ wB
        tB = tB - np.mean(X_all[tr] @ wB)        # a tilt around zero on the build years
        lB = np.mean([pinball(yte, ste * (bq[i] + tB), p) for i, p in enumerate(Q)])
        cov_B = float(np.mean((yte >= ste * (bq[0] + tB)) & (yte <= ste * (bq[2] + tB))))
        dB = float(np.mean(np.sign(tB) == np.sign(yte / ste - bq[1])))
        out["h"][str(h)] = dict(coef=[float(x) for x in w], resid_q=rq, base_q=bq, n_build=int(tr.sum()), n_check=int(te.sum()),
                                loss_model=float(lm), loss_base=float(lb), gain=float(1 - lm / lb), cover_model=cov_m, cover_base=cov_b, side_right=dm,
                                use=bool(lB < lb), use_A=bool(lm < lb), coefB=[float(x) for x in wB], tilt_mean=float(np.mean(X_all[tr] @ wB)), loss_B=float(lB), gain_B=float(1 - lB / lb),
                                cover_B=cov_B, side_right_B=dB)
    return out


def forecast(fc, row_df, fall_order):
    """row_df: a one-row DataFrame with the inputs of the latest close. Returns per horizon [q25, q50, q75] log changes and the kind used."""
    X, _, _ = design(row_df, fall_order, np.array(fc["mean"]), np.array(fc["std"]))
    sig = float(row_df["sigma"].iloc[0])
    out = []
    for h in H:
        m = fc["h"][str(h)]
        sc = sig * np.sqrt(h / 252)
        base = [sc * b for b in m["base_q"]]
        if m["use"]:
            tilt = float(X[0] @ np.array(m["coefB"])) - m["tilt_mean"]
            q = [sc * (b + tilt) for b in m["base_q"]]
        else:
            q = base
        out.append(dict(q=[round(x, 4) for x in q], base=[round(x, 4) for x in base], kind="model" if m["use"] else "no_signal"))
    return out
