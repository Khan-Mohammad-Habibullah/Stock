#!/usr/bin/env python3
"""Monthly study behind the two holdings tables on the My holdings tab -> data/holdings_study.json (a NEW file).

  1. The next six months, month by month, after past cases of each of the twelve setups of "Setups before 20% rises"
     (same stock list, same bars, same rules and the same declustering as that study, which is only read, never changed).
  2. The fall study: six fixed rules written down before testing (scripts/holdings_falls.py), tested on every stock and day,
     build years before SPLIT and check years from it, against the base rate at the same volatility. A rule is kept only if it
     beats that base rate by 5 points for a 10% fall within a month in BOTH periods, with 30+ cases in each, and no single market,
     year or calendar month holds more than half of its cases.
  3. Estimated rates for a fall (logistic regression fitted on the build years only, kept only if it beats the plain rule rate on the check years).

  python3 scripts/holdings_study.py [--dump FILE] [--out data/holdings_study.json]
"""
import argparse
import datetime
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import holdings_falls as HF
import setups_data as SD
import setups_lib as SL
import setups_study as SS

OUT = "data/holdings_study.json"
MARKETS = [m["k"] for m in SD.MARKETS]
KEEP = ["sym", "date", "c", "rv20", "atr", "from52h", "rsi", "vr", "breadth", "hit", "fall10", "fall20", "fall_both"] + ["m%d" % m for m in range(1, 7)]


def rnd(x, d=4):
    if isinstance(x, float):
        return None if np.isnan(x) else round(x, d)
    if isinstance(x, dict):
        return {k: rnd(v, d) for k, v in x.items()}
    if isinstance(x, list):
        return [rnd(v, d) for v in x]
    return x


def paths_block(X, cut):
    out = {"All": dict(all=HF.month_stats(X), build=HF.month_stats(X[X.date < cut]), check=HF.month_stats(X[X.date >= cut]), n=int(len(X)))}
    for mk in MARKETS:
        Y = X[X.market == mk]
        out[mk] = dict(all=HF.month_stats(Y), build=HF.month_stats(Y[Y.date < cut]), check=HF.month_stats(Y[Y.date >= cut]), n=int(len(Y)))
    return out


def rate_part(X, col, bcol):
    R = X[X[col].notna()]
    n = len(R)
    return dict(n=int(n), hits=int(R[col].sum()) if n else 0, rate=(float(R[col].mean()) if n else None),
                matched=(float(R[bcol].mean()) if n else None), edge=(float(R[col].mean() - R[bcol].mean()) if n else None))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    if a.dump:
        D = SD.load(a.dump)
        U = D["universe"]
        bars = {s: dict(t=v["t"], o=v["o"], h=v["h"], l=v["l"], c=v["c"], v=v["v"]) for s, v in D["bars"].items()}
    else:
        U = SD.universe()
        raw, err = SD.fetch_all(U)
        bars = {s: dict(t=[b[0] // 86400 for b in v["bars"]], o=[b[1] for b in v["bars"]], h=[b[2] for b in v["bars"]], l=[b[3] for b in v["bars"]],
                        c=[b[4] for b in v["bars"]], v=[b[5] for b in v["bars"]]) for s, v in raw.items()}
    market_of = {d["sym"]: d["market"] for rows in U.values() for d in rows}
    size_of = {d["sym"]: d["size"] for rows in U.values() for d in rows}
    F = SS.build_frames(bars, market_of)                 # the existing study's frames: features, market washout, the twelve rules
    for s in list(F):
        df = HF.apply_fall_rules(F[s])
        df = HF.outcomes(df)
        F[s] = df[KEEP + SL.ORDER + HF.FALL_ORDER].copy()
    A = SL.run_study(F)                                  # adds the volatility bucket (vb) exactly as the study does
    A["market"] = A.sym.map(market_of)
    A["large"] = (A.sym.map(size_of) == "Large").astype(int)
    P = A[A.date >= SL.STUDY_FROM]
    edges = np.nanquantile(P.rv20.dropna(), np.linspace(0, 1, 21))
    cut = pd.Timestamp(SL.SPLIT)

    # ---- 1. six-month paths after the twelve setups (declustered like the study: one case per stock and setup every 42 sessions)
    up = {}
    for k in SL.ORDER:
        sig = P[P[k]]
        keep = SL.decluster({s: list(g.index) for s, g in sig.groupby("sym", sort=False)})
        X = A.loc[keep]
        up[k] = paths_block(X, cut)
        up[k]["resolved_hits"] = int(X.hit.notna().sum())
    base_paths = dict(All=HF.month_stats(P), by_vb={str(int(v)): HF.month_stats(g) for v, g in P.groupby("vb")})

    # ---- 2. the fall study
    base_fall = {}
    for col in ("fall10", "fall20", "fall_both"):
        b = P[P[col].notna()].groupby("vb")[col].mean()
        A["b_" + col] = A.vb.map(b)
        base_fall[col] = dict(All=float(P[col].mean()), by_vb={str(int(v)): float(x) for v, x in b.items()})
    P = A[A.date >= SL.STUDY_FROM]
    rules, cases, fall_paths = {}, {}, {}
    for k in HF.FALL_ORDER:
        sig = P[P[k]]
        keep = SL.decluster({s: list(g.index) for s, g in sig.groupby("sym", sort=False)}, gap=HF.FALL_GAP)
        X = A.loc[keep].copy()
        cases[k] = X
        res = {}
        for per, Y in (("all", X), ("build", X[X.date < cut]), ("check", X[X.date >= cut])):
            res[per] = {col: rate_part(Y, col, "b_" + col) for col in ("fall10", "fall20", "fall_both")}
        R10 = X[X.fall10.notna()]
        conc = {}
        if len(R10):
            conc = dict(market=float(R10.market.value_counts(normalize=True).iloc[0]), market_top=str(R10.market.value_counts().index[0]),
                        year=float(R10.date.dt.year.value_counts(normalize=True).iloc[0]), year_top=int(R10.date.dt.year.value_counts().index[0]),
                        month=float(R10.date.dt.strftime("%Y-%m").value_counts(normalize=True).iloc[0]), month_top=str(R10.date.dt.strftime("%Y-%m").value_counts().index[0]))
        b, c = res["build"]["fall10"], res["check"]["fall10"]
        why = []
        if b["n"] < SL.MIN_CASES or c["n"] < SL.MIN_CASES:
            why.append("fewer than 30 cases in the build or the check years (%d / %d)" % (b["n"], c["n"]))
        if b["edge"] is None or b["edge"] < HF.EDGE_MIN:
            why.append("build years: %s points over the same-volatility base rate (needs 5)" % ("n/a" if b["edge"] is None else "%+.1f" % (b["edge"] * 100)))
        if c["edge"] is None or c["edge"] < HF.EDGE_MIN:
            why.append("check years: %s points over the same-volatility base rate (needs 5)" % ("n/a" if c["edge"] is None else "%+.1f" % (c["edge"] * 100)))
        for key, lab in (("market", "market"), ("year", "year"), ("month", "calendar month")):
            if conc and conc[key] > HF.MAX_SHARE:
                why.append("%.0f%% of its cases in one %s (%s)" % (conc[key] * 100, lab, conc[key + "_top"]))
        rules[k] = dict(name=HF.FALL_RULES[k]["name"], short=HF.FALL_RULES[k]["short"], conditions=[t for _, t, _ in HF.FALL_RULES[k]["conds"]],
                        results=res, concentration=conc, pending=int(X.fall10.isna().sum()), passed=not why, why_not=why)
        fall_paths[k] = paths_block(X, cut)

    # ---- 3. estimated rates for a fall: every declustered resolved case of the six rules (one row per stock-day, all its rule flags)
    idx = sorted(set().union(*[set(X.index) for X in cases.values()]))
    R = A.loc[idx]
    models = {}
    for col in ("fall10", "fall20"):
        br = {k: (float(cases[k][(cases[k].date < cut) & cases[k][col].notna()][col].mean()) if len(cases[k][(cases[k].date < cut) & cases[k][col].notna()]) else None) for k in HF.FALL_ORDER}
        models[col] = HF.fit_and_check(R, col, cut, br)
        models[col]["build_rates"] = br

    last = A.date.max()
    out = dict(
        built=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="minutes"),
        period=dict(from_=SL.STUDY_FROM, split=SL.SPLIT, data_to=str(last.date())),
        months=HF.MONTHS, vb_edges=[float(x) for x in edges],
        up_paths=up, base_paths=base_paths,
        fall=dict(rules=rules, order=HF.FALL_ORDER, passed=[k for k in HF.FALL_ORDER if rules[k]["passed"]], base=base_fall, paths=fall_paths, models=models,
                  bar=dict(edge_min=HF.EDGE_MIN, max_share=HF.MAX_SHARE, min_cases=SL.MIN_CASES, m1=HF.M1, m3=HF.M3, fall1=HF.FALL1, fall3=HF.FALL3, gap=HF.FALL_GAP)),
        stock_days=int(len(P)), stocks=int(P.sym.nunique()))
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    json.dump(rnd(out), open(a.out, "w"), separators=(",", ":"))
    for k in HF.FALL_ORDER:
        r = rules[k]["results"]
        print("%-10s pass=%-5s 10%%/1m build %s (n %d, base %s) check %s (n %d, base %s) | >20%%/3m all %s | %s" % (
            k, rules[k]["passed"], r["build"]["fall10"]["rate"], r["build"]["fall10"]["n"], r["build"]["fall10"]["matched"],
            r["check"]["fall10"]["rate"], r["check"]["fall10"]["n"], r["check"]["fall10"]["matched"], r["all"]["fall20"]["rate"], "; ".join(rules[k]["why_not"])))
    print("fall models:", {c: (m["kind"], round(m["brier_model"], 4), round(m["brier_setup"], 4)) for c, m in models.items()})
    print("up paths month 6 median:", {k: up[k]["All"]["all"][5].get("med") for k in SL.ORDER})


if __name__ == "__main__":
    main()
