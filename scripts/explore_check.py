#!/usr/bin/env python3
"""Closer look at the shortlist from explore_setups.py: results by year, the months that supplied most cases,
results by market, and which stocks match each setup on the latest close.

  python3 scripts/explore_check.py --dump cache/study_data.json.gz --out data/explore_check.txt
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import explore_setups as E
import setups_data as SD
import setups_lib as SL

SHORT = [
    ("60%+ below 52-week high (nothing else)", ["60%+ below 52-week high"]),
    ("60%+ below high + volume dried up", ["60%+ below 52-week high", "volume dried up (10-day avg <0.8x)"]),
    ("60%+ below high + volume 1.5x+", ["60%+ below 52-week high", "volume 1.5x+ average"]),
    ("Oversold reversal, 60%+ off the high", ["60%+ below 52-week high", "RSI(14) 30-50", "MACD histogram rising", "close above previous day's high"]),
    ("Oversold reversal + volatile stock", ["40%+ below 52-week high", "RSI(14) 30-50", "MACD histogram rising", "close above previous day's high", "daily range 5%+ of price"]),
    ("High-volatility breakout", ["daily range 5%+ of price", "close above 40-day high", "volume 1.5x+ average"]),
    ("Washout: market and stock oversold", ["market: under 20% of stocks above 50-day", "40%+ below 52-week high", "close above previous day's high"]),
    ("Washout, 60%+ off high, MACD rising", ["60%+ below 52-week high", "MACD histogram rising", "market: under 20% of stocks above 50-day"]),
    ("Momentum leader pulls back", ["top 10% 6-month return in market", "RSI(14) 30-50", "50-day rising >2% in 10 days"]),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", required=True)
    ap.add_argument("--out", default="data/explore_check.txt")
    a = ap.parse_args()
    D = SD.load(a.dump)
    U = D["universe"]
    info = {d["sym"]: d for rows in U.values() for d in rows}
    F = {s: SL.apply_rules(E.extra(SL.features(s, dict(t=v["t"], o=v["o"], h=v["h"], l=v["l"], c=v["c"], v=v["v"])))) for s, v in D["bars"].items()}
    A = SL.run_study(F)
    A["market"] = A.sym.map(lambda s: info[s]["market"])
    A = E.market_features(A)
    A = A.sort_values(["sym", "date"]).reset_index(drop=True)
    X = E.Ctx(A)
    C = E.conditions(A)
    C["your oversold reversal"] = A["oversold"].fillna(False).values.astype(bool)
    SHORT.insert(0, ("Your oversold reversal (current)", ["your oversold reversal"]))
    last = A.groupby("sym").date.transform("max") == A.date
    year = A.date.dt.year.values
    P = X.inper & X.resolved
    L = []
    L.append("Base rate by year: " + ", ".join("%d %.1f%%" % (y, 100 * np.nanmean(X.hit[P & (year == y)])) for y in sorted(set(year[P]))))
    L.append("")
    for name, conds in SHORT:
        m = np.ones(len(A), bool)
        for c in conds:
            m &= C[c]
        k = X.decluster(m)
        h = X.hit[k]
        L.append("== %s: %d cases, %.1f%% hit (same-volatility base %.1f%%)" % (name, len(k), 100 * h.mean(), 100 * np.nanmean(X.mbase[k])))
        yr = pd.DataFrame(dict(y=year[k], h=h, b=X.mbase[k]))
        L.append("   by year: " + ", ".join("%d %d cases %.0f%% (base %.0f%%)" % (y, len(g), 100 * g.h.mean(), 100 * g.b.mean()) for y, g in yr.groupby("y")))
        mo = pd.DataFrame(dict(m=X.month[k], h=h)).groupby("m").h.agg(["size", "mean"]).sort_values("size", ascending=False).head(5)
        L.append("   busiest months: " + ", ".join("%s %d cases %.0f%%" % (i, r["size"], 100 * r["mean"]) for i, r in mo.iterrows()))
        rest = ~np.isin(X.month[k], mo.index[:3])
        L.append("   without its 3 busiest months: %d cases, %.1f%%" % (rest.sum(), 100 * h[rest].mean() if rest.sum() else float("nan")))
        mk = pd.DataFrame(dict(m=X.market[k], h=h)).groupby("m").h.agg(["size", "mean"])
        L.append("   by market: " + ", ".join("%s %d %.0f%%" % (i, r["size"], 100 * r["mean"]) for i, r in mk.iterrows()))
        sz = pd.DataFrame(dict(s=[info[s]["size"] for s in X.sym[k]], h=h)).groupby("s").h.agg(["size", "mean"])
        L.append("   by size: " + ", ".join("%s %d %.0f%%" % (i, r["size"], 100 * r["mean"]) for i, r in sz.iterrows()))
        now = np.flatnonzero(m & last.values)
        L.append("   matching on the latest close: " + (", ".join("%s (%s)" % (info[X.sym[i]]["description"] or info[X.sym[i]]["name"], X.sym[i]) for i in now) or "none"))
        L.append("")
    txt = "\n".join(L)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    open(a.out, "w").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
