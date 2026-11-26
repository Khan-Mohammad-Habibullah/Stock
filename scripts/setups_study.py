#!/usr/bin/env python3
"""Monthly historical study for "Setups before 15% rises" -> data/setups_study.json (Tables A and B).

  python3 scripts/setups_study.py                 # fetch universe + bars, run, write
  python3 scripts/setups_study.py --dump FILE     # use a saved dump (scripts/setups_data.py output) instead of fetching
Runs on the first weekend of each month from GitHub Actions (see .github/workflows/setups-study.yml).
"""
import argparse
import datetime
import json
import os
import statistics
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import setups_data as SD
import setups_lib as SL

OUT = "data/setups_study.json"
MARKETS = [m["k"] for m in SD.MARKETS]
EX_PER = 5   # most recent hits and misses kept per setup and market for Table B


def build_frames(bars):
    F = {}
    for sym, b in bars.items():
        df = SL.apply_rules(SL.features(sym, b))
        F[sym] = df
    return F


def med(x):
    x = [v for v in x if v is not None and not (isinstance(v, float) and np.isnan(v))]
    return float(np.median(x)) if x else None


def verdict(X, cut):
    """The 95% bar for one setup, from its declustered, resolved cases X (all markets, whole study period)."""
    tr, te = X[X.date < cut], X[X.date >= cut]
    htr, hte = int(tr.hit.sum()), int(te.hit.sum())
    wt = SL.wilson_low(hte, len(te))
    pc = lambda x: "%.1f%%" % (x * 100)
    by_m = X.market.value_counts()
    by_y = X.date.dt.year.value_counts()
    m_name, m_n = (by_m.index[0], int(by_m.iloc[0])) if len(by_m) else ("-", 0)
    y_name, y_n = (int(by_y.index[0]), int(by_y.iloc[0])) if len(by_y) else ("-", 0)
    n = max(len(X), 1)
    checks = [
        dict(t="Test period: the lower end of the 95% range of the success rate is above 95%", ok=bool(wt > SL.BAR),
             v="%d cases, %d reached +15%% (%s); lower end %s" % (len(te), hte, pc(hte / len(te)) if len(te) else "n/a", pc(wt))),
        dict(t="Build period: the success rate is at least 95%", ok=bool(len(tr) and htr / len(tr) >= SL.BAR),
             v="%d cases, %d reached +15%% (%s)" % (len(tr), htr, pc(htr / len(tr)) if len(tr) else "n/a")),
        dict(t="No single market supplies more than half of the cases", ok=bool(m_n / n <= SL.MAX_SHARE), v="largest: %s, %s of cases" % (m_name, pc(m_n / n))),
        dict(t="No single year supplies more than half of the cases", ok=bool(y_n / n <= SL.MAX_SHARE), v="largest: %s, %s of cases" % (y_name, pc(y_n / n))),
    ]
    return dict(passes=all(c["ok"] for c in checks), checks=checks, closeness=wt, n=len(X), n_train=len(tr), n_test=len(te),
                top_market=dict(name=m_name, share=m_n / n), top_year=dict(name=y_name, share=y_n / n))


def study(A, U, bars):
    uni = {d["sym"]: d for rows in U.values() for d in rows}
    A["market"] = A.sym.map(lambda s: uni[s]["market"])
    P = A[(A.date >= SL.STUDY_FROM) & A.hit.notna()]
    cut = pd.Timestamp(SL.SPLIT)
    closes = {s: g.c.values for s, g in A.groupby("sym", sort=False)}
    first_idx = {s: g.index[0] for s, g in A.groupby("sym", sort=False)}
    stats, examples, verdicts = [], [], {}
    base = {"All": float(P.hit.mean())}
    for mk in MARKETS:
        base[mk] = float(P[P.market == mk].hit.mean())
    for k in SL.ORDER:
        sig = A[A[k] & (A.date >= SL.STUDY_FROM)]
        by = {s: list(g.index) for s, g in sig.groupby("sym", sort=False)}
        keep = SL.decluster(by)
        X = A.loc[keep]
        pending = int(X.hit.isna().sum())
        X = X[X.hit.notna()].copy()
        info = {}
        for i, r in X.iterrows():
            ci = closes[r.sym]
            info[i] = SL.peak_info(ci, i - first_idx[r.sym])
        X["gain"] = [info[i]["gain"] for i in X.index]
        X["days"] = [info[i]["days"] for i in X.index]
        X["drop"] = [info[i]["drop"] for i in X.index]
        for mk in ["All"] + MARKETS:
            Y = X if mk == "All" else X[X.market == mk]
            n = len(Y)
            w = Y[Y.hit == 1]
            tr, te = Y[Y.date < cut], Y[Y.date >= cut]
            htr, hte = int(tr.hit.sum()), int(te.hit.sum())
            st = dict(setup=k, market=mk, n=n, hits=int(len(w)), pending=int((pending if mk == "All" else 0)),
                      rate=(float(Y.hit.mean()) if n >= SL.MIN_CASES else None),
                      base=base[mk], matched=(float(Y.mbase.mean()) if n else None),
                      gain=med(w.gain), days=med(w.days), drop=med(w["drop"]),
                      n_train=len(tr), hits_train=htr, rate_train=(float(tr.hit.mean()) if len(tr) >= SL.MIN_CASES else None),
                      n_test=len(te), hits_test=hte, rate_test=(float(te.hit.mean()) if len(te) >= SL.MIN_CASES else None),
                      wil_all=SL.wilson_low(int(len(w)), n), wil_train=SL.wilson_low(htr, len(tr)), wil_test=SL.wilson_low(hte, len(te)),
                      matched_test=(float(te.mbase.mean()) if len(te) else None))
            stats.append(st)
        verdicts[k] = verdict(X, cut)
        # examples: the most recent resolved hits and misses per market (not picked for how good they look)
        for mk in MARKETS:
            Y = X[X.market == mk].sort_values("date", ascending=False)
            for outcome, sel in (("hit", Y[Y.hit == 1].head(EX_PER)), ("missed", Y[Y.hit == 0].head(EX_PER))):
                for i, r in sel.iterrows():
                    ci = closes[r.sym]
                    j = i - first_idx[r.sym]
                    pk = SL.peak_info(ci, j)
                    nxt = A.loc[i + 1: i + SL.HORIZON]
                    nxt = nxt[nxt.sym == r.sym]
                    d = uni[r.sym]
                    examples.append(dict(
                        setup=k, market=mk, sym=r.sym, name=d["description"] or d["name"], cur=d["currency"],
                        date=r.date.strftime("%Y-%m-%d"), price=float("%.5g" % r.c), peak=float("%.5g" % pk["peak"]),
                        gain=round(pk["gain"] * 100, 1), days=pk["days"], drop=round(pk["drop"] * 100, 1), outcome=outcome,
                        why=SL.characteristics(r), earnings=bool(nxt.earn_like.sum() > 0) if len(nxt) else None,
                        breakout=(float("%.5g" % lv) if (lv := SL.levels(k, r)["breakout"]) else None)))
    return stats, examples, base, verdicts


def notes(U, bars, err):
    out = []
    for mk, rows in U.items():
        for d in rows:
            s = d["sym"]
            if s in err:
                out.append(dict(sym=s, name=d["description"] or d["name"], market=mk, reason="no usable daily history (%s)" % err[s]))
            elif s in bars:
                first = datetime.datetime.fromtimestamp(bars[s]["bars"][0][0], datetime.timezone.utc).date() if "bars" in bars[s] else None
                if first and first > datetime.date.fromisoformat(SL.STUDY_FROM) + datetime.timedelta(days=60):
                    out.append(dict(sym=s, name=d["description"] or d["name"], market=mk, reason="history starts %s, so earlier years are missing" % first.isoformat()))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    if a.dump:
        D = SD.load(a.dump)
        U, err = D["universe"], D["errors"]
        bars = {s: dict(t=v["t"], o=v["o"], h=v["h"], l=v["l"], c=v["c"], v=v["v"], first=v["t"][0] * 86400) for s, v in D["bars"].items()}
        bar_notes = {s: dict(bars=[(v["t"][0] * 86400,)]) for s, v in D["bars"].items()}
    else:
        U = SD.universe()
        raw, err = SD.fetch_all(U)
        bars = {s: dict(t=[b[0] // 86400 for b in v["bars"]], o=[b[1] for b in v["bars"]], h=[b[2] for b in v["bars"]], l=[b[3] for b in v["bars"]],
                        c=[b[4] for b in v["bars"]], v=[b[5] for b in v["bars"]]) for s, v in raw.items()}
        bar_notes = {s: dict(bars=[(v["bars"][0][0],)]) for s, v in raw.items()}
    F = build_frames(bars)
    A = SL.run_study(F)
    stats, examples, base, verdicts = study(A, U, bars)
    last = A.date.max()
    out = dict(
        built=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="minutes"),
        period=dict(from_=SL.STUDY_FROM, to=str(A[A.hit.notna()].date.max().date()), data_to=str(last.date()), split=SL.SPLIT),
        horizon=SL.HORIZON, rise=SL.RISE, min_cases=SL.MIN_CASES, bar=SL.BAR, max_share=SL.MAX_SHARE, verdicts=verdicts,
        stocks=dict(total=sum(len(v) for v in U.values()), with_data=len(bars), per_market={k: len(v) for k, v in U.items()}),
        stock_days=int(A[(A.date >= SL.STUDY_FROM) & A.hit.notna()].shape[0]),
        setups={k: dict(name=SL.SETUPS[k]["name"], short=SL.SETUPS[k]["short"], conditions=[c[1] for c in SL.SETUPS[k]["conds"]]) for k in SL.ORDER},
        order=SL.ORDER, base=base, stats=stats, examples=examples, left_out=notes(U, bar_notes, err))
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    json.dump(out, open(a.out, "w"), separators=(",", ":"))
    print("written", a.out, len(stats), "stat rows", len(examples), "examples", os.path.getsize(a.out) // 1024, "KB")


if __name__ == "__main__":
    main()
