#!/usr/bin/env python3
"""One-off exploration: are there setups beyond the five on the Strategy tab with a higher success rate?

Same stocks, same five years, same rule as "Setups before 20% rises" (highest close in the next 42 trading days at least 20% above the
setup-day close), same build/check split (before / from 2024-07-01), and the same one-signal-per-stock-per-42-days counting.

  python3 scripts/explore_setups.py --dump cache/study_data.json.gz --out data/explore_results.json

Part 1 tests about 30 named setups (well-known chart patterns and a few market-wide conditions).
Part 2 searches every combination of two and three conditions from a list of about 45, picks the best on the build years only, and then
reports how those picks did on the later check years they were not chosen on.
"""
import argparse
import itertools
import json
import os
import sys
import time
import traceback

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import setups_data as SD
import setups_lib as SL

T0 = time.time()


def log(*a):
    print("[%5.0fs]" % (time.time() - T0), *a, flush=True)


# ------------------------------------------------------------------ extra features (past data only)
def extra(df):
    c, h, l, o = df.c, df.h, df.l, df.o
    for n in (1, 5, 20, 60, 120):
        df["ret%d" % n] = c / c.shift(n) - 1
    rng = (h - l).replace(0, np.nan)
    df["clv"] = (c - l) / rng
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / 2, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / 2, adjust=False).mean()
    df["rsi2"] = 100 - 100 / (1 + up / dn)
    e12, e26 = c.ewm(span=12, adjust=False).mean(), c.ewm(span=26, adjust=False).mean()
    df["macd"] = (e12 - e26) / c
    df["ll252"] = c.rolling(252, min_periods=120).min()
    df["from52l"] = c / df.ll252 - 1
    hl = h - l
    df["nr7"] = (hl <= hl.rolling(7).min()) & (h <= h.shift()) & (l >= l.shift())
    df["prev_nr7"] = df.nr7.shift(1).fillna(False).astype(bool)
    df["low_prev"] = l.rolling(20).min().shift(10)            # lowest low of sessions 11-30 ago
    df["higher_low"] = df.l10 > df.low_prev
    down = (c < c.shift()).astype(int)
    run = down.groupby((down == 0).cumsum()).cumsum()
    df["down_run_prev"] = run.shift(1)
    df["engulf"] = (c > o) & (c.shift() < o.shift()) & (c >= o.shift()) & (o <= c.shift())
    df["prev_c"], df["prev_h"], df["prev_sma50"], df["prev_sma200"] = c.shift(), h.shift(), df.sma50.shift(), df.sma200.shift()
    df["prev_macdh"] = df.macdh.shift()
    df["prev_rsi"] = df.rsi.shift()
    return df


def market_features(A):
    """Equal-weight index, breadth and relative strength per market (all from same-day or earlier data)."""
    A["ret_c"] = A.ret.clip(-0.5, 0.5)
    A["a50"] = np.where(A.sma50.notna(), (A.c > A.sma50).astype(float), np.nan)
    g = A.groupby(["market", "date"])
    M = pd.DataFrame({"mret": g.ret_c.mean(), "breadth": g.a50.mean(), "nstk": g.c.size()}).reset_index().sort_values(["market", "date"])
    M.loc[M.nstk < 10, "breadth"] = np.nan
    M["idx"] = M.groupby("market").mret.transform(lambda s: (1 + s.fillna(0)).cumprod())
    M["mkt_dd"] = M.idx / M.groupby("market").idx.transform(lambda s: s.rolling(252, min_periods=60).max()) - 1
    M["mkt_up200"] = M.idx > M.groupby("market").idx.transform(lambda s: s.rolling(200, min_periods=120).mean())
    M["mkt_ret20"] = M.idx / M.groupby("market").idx.shift(20) - 1
    key = pd.MultiIndex.from_frame(A[["market", "date"]])
    Mi = M.set_index(["market", "date"])
    for col in ("breadth", "idx", "mkt_dd", "mkt_up200", "mkt_ret20"):
        A[col] = Mi[col].reindex(key).values
    A["rs"] = A.c / A.idx
    A["rs_prevmax"] = A.groupby("sym").rs.transform(lambda s: s.shift(1).rolling(252, min_periods=120).max())
    A["mrank120"] = A.groupby(["market", "date"]).ret120.rank(pct=True)
    A["mrank20"] = A.groupby(["market", "date"]).ret20.rank(pct=True)
    return A


# ------------------------------------------------------------------ building blocks
def conditions(A):
    f = lambda s: s.fillna(False).astype(bool).values
    C = {
        "above 200-day": A.c > A.sma200,
        "below 200-day": A.c < A.sma200,
        "50-day above 200-day": A.sma50 > A.sma200,
        "50-day rising >2% in 10 days": A.slope50 > 0.02,
        "200-day rising": A.slope200 > 0.005,
        "200-day falling": A.slope200 < -0.005,
        "within 5% of 52-week high": A.from52h >= -0.05,
        "20%+ below 52-week high": A.from52h <= -0.20,
        "40%+ below 52-week high": A.from52h <= -0.40,
        "60%+ below 52-week high": A.from52h <= -0.60,
        "within 5% of 52-week low": A.from52l <= 0.05,
        "close above 20-day high": A.c > A.hh20,
        "close above 40-day high": A.c > A.hh40,
        "close above 52-week high": A.c > A.hh252,
        "close above previous day's high": A.c > A.prev_h,
        "close in top 20% of day's range": A.clv >= 0.8,
        "volume 1.5x+ average": A.vr >= 1.5,
        "volume 2.5x+ average": A.vr >= 2.5,
        "volume 4x+ average": A.vr >= 4,
        "volume dried up (10-day avg <0.8x)": A.vdry <= 0.8,
        "RSI(14) under 30": A.rsi < 30,
        "RSI(14) 30-50": A.rsi.between(30, 50),
        "RSI(14) over 70": A.rsi > 70,
        "RSI(14) crossed up through 30": (A.rsi >= 30) & (A.prev_rsi < 30),
        "RSI(2) under 10": A.rsi2 < 10,
        "MACD histogram rising": A.macdh > A.prev_macdh,
        "MACD crossed up below zero": (A.macdh > 0) & (A.prev_macdh <= 0) & (A.macd < 0),
        "gap up 4%+": A.gap >= 0.04,
        "gap down 4%+": A.gap <= -0.04,
        "up 5%+ on the day": A.ret1 >= 0.05,
        "down 15%+ in 5 days": A.ret5 <= -0.15,
        "down 25%+ in 20 days": A.ret20 <= -0.25,
        "up 15%+ in 20 days": A.ret20 >= 0.15,
        "top 10% 6-month return in market": A.mrank120 >= 0.9,
        "bottom 10% 6-month return in market": A.mrank120 <= 0.1,
        "relative strength at 1-year high": A.rs > A.rs_prevmax,
        "daily range 3%+ of price": A.atr >= 0.03,
        "daily range 5%+ of price": A.atr >= 0.05,
        "Bollinger squeeze (narrowest 10%)": A.bbw_pct <= 0.10,
        "breakout from inside/NR7 day": A.prev_nr7 & (A.c > A.prev_h),
        "50-day crossed above 200-day": (A.sma50 > A.sma200) & (A.prev_sma50 <= A.prev_sma200),
        "close crossed above 200-day": (A.c > A.sma200) & (A.prev_c <= A.prev_sma200),
        "close crossed above 50-day": (A.c > A.sma50) & (A.prev_c <= A.prev_sma50),
        "higher low (10-day low above prior low)": A.higher_low,
        "bullish engulfing": A.engulf,
        "after 4+ down days": A.down_run_prev >= 4,
        "market: under 20% of stocks above 50-day": A.breadth <= 0.20,
        "market: under 35% of stocks above 50-day": A.breadth <= 0.35,
        "market: 10%+ below its 1-year high": A.mkt_dd <= -0.10,
        "market: above its 200-day": A.mkt_up200 == True,
        "market: below its 200-day": A.mkt_up200 == False,
    }
    return {k: f(v) for k, v in C.items()}


NAMED = [
    # (name, idea, [conditions])
    ("Capitulation bounce", "Down 15%+ in five days on heavy volume, then a strong close above the previous day's high",
     ["down 15%+ in 5 days", "close above previous day's high", "volume 1.5x+ average", "close in top 20% of day's range"]),
    ("Washout: market and stock oversold", "Fewer than 20% of the market's stocks above their 50-day, and this stock 40%+ off its high turns up",
     ["market: under 20% of stocks above 50-day", "40%+ below 52-week high", "close above previous day's high"]),
    ("Washout: any stock turning up", "Fewer than 20% of the market's stocks above their 50-day; stock closes above the previous day's high with RSI under 40",
     ["market: under 20% of stocks above 50-day", "close above previous day's high", "RSI(14) 30-50"]),
    ("Market down 10%+, stock down 40%+, momentum turning", "Market 10%+ off its high, stock 40%+ off its high, MACD histogram rising",
     ["market: 10%+ below its 1-year high", "40%+ below 52-week high", "MACD histogram rising", "close above previous day's high"]),
    ("Earnings-style gap up in uptrend", "Gap up 4%+ on 2.5x volume, strong close, above the 200-day",
     ["gap up 4%+", "volume 2.5x+ average", "close in top 20% of day's range", "above 200-day"]),
    ("Earnings-style gap up after a deep fall", "Gap up 4%+ on 2.5x volume in a stock 40%+ below its high",
     ["gap up 4%+", "volume 2.5x+ average", "40%+ below 52-week high"]),
    ("Golden cross", "50-day average crosses above the 200-day", ["50-day crossed above 200-day"]),
    ("Golden cross after a deep fall", "Golden cross in a stock still 20%+ below its 52-week high", ["50-day crossed above 200-day", "20%+ below 52-week high"]),
    ("200-day reclaim on volume", "Close crosses above the 200-day on 1.5x volume", ["close crossed above 200-day", "volume 1.5x+ average"]),
    ("200-day reclaim after a deep fall", "Close crosses above the 200-day in a stock 40%+ below its high", ["close crossed above 200-day", "40%+ below 52-week high"]),
    ("Momentum leader pulls back", "Top 10% 6-month return in its market, RSI 30-50, 50-day rising",
     ["top 10% 6-month return in market", "RSI(14) 30-50", "50-day rising >2% in 10 days"]),
    ("Momentum leader breaks out", "Top 10% 6-month return, close above 20-day high on 1.5x volume",
     ["top 10% 6-month return in market", "close above 20-day high", "volume 1.5x+ average"]),
    ("Relative-strength new high", "Stock-vs-market line at a 1-year high on 1.5x volume, 50-day above 200-day",
     ["relative strength at 1-year high", "volume 1.5x+ average", "50-day above 200-day"]),
    ("MACD cross below zero after a deep fall", "MACD crosses up while still below zero, stock 40%+ off its high",
     ["MACD crossed up below zero", "40%+ below 52-week high"]),
    ("RSI(2) dip in uptrend", "2-day RSI under 10 while above the 200-day", ["RSI(2) under 10", "above 200-day"]),
    ("RSI back above 30 at a 52-week low", "RSI(14) crosses up through 30 within 5% of the 52-week low",
     ["RSI(14) crossed up through 30", "within 5% of 52-week low"]),
    ("Volume thrust", "Up 5%+ on 4x volume with a strong close", ["up 5%+ on the day", "volume 4x+ average", "close in top 20% of day's range"]),
    ("Higher low and 50-day reclaim after a deep fall", "Stock 40%+ off its high makes a higher low and closes back above the 50-day",
     ["40%+ below 52-week high", "higher low (10-day low above prior low)", "close crossed above 50-day"]),
    ("High-volatility breakout", "Daily range 5%+ of price, close above 40-day high on 1.5x volume",
     ["daily range 5%+ of price", "close above 40-day high", "volume 1.5x+ average"]),
    ("Squeeze in a volatile stock", "Bollinger squeeze, close above 20-day high, daily range 3%+",
     ["Bollinger squeeze (narrowest 10%)", "close above 20-day high", "daily range 3%+ of price"]),
    ("Bullish engulfing at a 52-week low", "Bullish engulfing candle within 5% of the 52-week low on 1.5x volume",
     ["bullish engulfing", "within 5% of 52-week low", "volume 1.5x+ average"]),
    ("Four down days then up, in uptrend", "After 4+ down closes, closes above the previous high while above the 200-day",
     ["after 4+ down days", "close above previous day's high", "above 200-day"]),
    ("NR7 breakout in uptrend", "Breakout from an inside, narrowest-in-7-days bar, above the 200-day",
     ["breakout from inside/NR7 day", "above 200-day"]),
    ("Oversold reversal + market washout", "Your oversold reversal, only when under 35% of the market's stocks are above their 50-day",
     ["40%+ below 52-week high", "RSI(14) 30-50", "MACD histogram rising", "close above previous day's high", "market: under 35% of stocks above 50-day"]),
    ("Oversold reversal + volatile stock", "Your oversold reversal, only when the daily range is 5%+ of the price",
     ["40%+ below 52-week high", "RSI(14) 30-50", "MACD histogram rising", "close above previous day's high", "daily range 5%+ of price"]),
    ("Oversold reversal, 60%+ off the high", "Your oversold reversal with a deeper fall",
     ["60%+ below 52-week high", "RSI(14) 30-50", "MACD histogram rising", "close above previous day's high"]),
]


# ------------------------------------------------------------------ counting
class Ctx:
    def __init__(self, A):
        self.A = A
        self.date = A.date.values
        self.sym = A.sym.values
        self.hit = A.hit.values
        self.fmax = A.fmax.values
        self.mbase = A.mbase.values
        self.market = A.market.values
        self.inper = (A.date >= SL.STUDY_FROM).values
        self.resolved = ~np.isnan(self.hit)
        self.train = (A.date < SL.SPLIT).values
        self.month = A.date.dt.to_period("M").astype(str).values
        self.week = A.date.dt.to_period("W").astype(str).values
        # position of each row inside its stock, for the 42-day spacing
        self.pos = A.groupby("sym").cumcount().values
        self.symcode = pd.factorize(A.sym)[0]

    def decluster(self, mask):
        idx = np.flatnonzero(mask & self.inper)
        keep = []
        last_sym, last_pos = -1, -10 ** 9
        for i in idx:                                   # rows are sorted by stock, then date
            s, p = self.symcode[i], self.pos[i]
            if s != last_sym:
                last_sym, last_pos = s, -10 ** 9
            if p - last_pos >= SL.HORIZON:
                keep.append(i)
                last_pos = p
        keep = np.array(keep, dtype=int)
        return keep[self.resolved[keep]] if len(keep) else keep

    def stats(self, mask, per_market=False):
        k = self.decluster(mask)
        out = dict(n=int(len(k)))
        if not len(k):
            return out
        h = self.hit[k]
        tr = self.train[k]
        out.update(
            hits=int(h.sum()), rate=float(h.mean()), matched=float(np.nanmean(self.mbase[k])),
            n_train=int(tr.sum()), rate_train=(float(h[tr].mean()) if tr.sum() else None),
            n_test=int((~tr).sum()), rate_test=(float(h[~tr].mean()) if (~tr).sum() else None),
            matched_test=(float(np.nanmean(self.mbase[k][~tr])) if (~tr).sum() else None),
            stocks=int(len(set(self.sym[k]))), weeks=int(len(set(self.week[k]))),
            top_month=None, top_month_share=None,
            median_best=float(np.median(self.fmax[k])),
            lower95=wilson_low(int(h.sum()), len(k)),
        )
        months = pd.Series(self.month[k]).value_counts()
        out["top_month"], out["top_month_share"] = months.index[0], float(months.iloc[0] / len(k))
        out["lift"] = out["rate"] - out["matched"]
        if per_market:
            pm = {}
            for mk in sorted(set(self.market[k])):
                sel = self.market[k] == mk
                pm[mk] = dict(n=int(sel.sum()), rate=float(h[sel].mean()))
            out["per_market"] = pm
        return out


def wilson_low(h, n, z=1.96):
    if not n:
        return None
    p = h / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    a = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return float((c - a) / d)


# ------------------------------------------------------------------ main
def run(dump_path, out_path):
    D = SD.load(dump_path)
    U = D["universe"]
    mk_of = {d["sym"]: d["market"] for rows in U.values() for d in rows}
    log("stocks with bars:", len(D["bars"]))
    F = {}
    for s, v in D["bars"].items():
        b = dict(t=v["t"], o=v["o"], h=v["h"], l=v["l"], c=v["c"], v=v["v"])
        F[s] = SL.apply_rules(extra(SL.features(s, b)))
    log("features done")
    A = SL.run_study(F)
    A["market"] = A.sym.map(mk_of)
    A = market_features(A)
    A = A.sort_values(["sym", "date"]).reset_index(drop=True)
    log("market features done; rows", len(A))
    X = Ctx(A)
    C = conditions(A)
    P = X.inper & X.resolved
    base = dict(all=float(np.nanmean(X.hit[P])), train=float(np.nanmean(X.hit[P & X.train])), test=float(np.nanmean(X.hit[P & ~X.train])))
    log("base rate", base)

    # reference: the five setups already on the page
    ref = []
    for k in SL.ORDER:
        st = X.stats(A[k].fillna(False).values.astype(bool))
        st.update(name=SL.SETUPS[k]["name"], kind="current")
        ref.append(st)
    log("reference done")

    named = []
    for name, idea, conds in NAMED:
        m = np.ones(len(A), bool)
        for c in conds:
            m &= C[c]
        st = X.stats(m, per_market=True)
        st.update(name=name, idea=idea, conditions=conds, kind="named")
        named.append(st)
        log("%-55s n=%5d rate=%s" % (name, st["n"], ("%.1f%%" % (st["rate"] * 100)) if st.get("rate") is not None else "-"))

    # part 2: every combination of 2 and 3 conditions, ranked on the build years only
    keys = list(C)
    tr_mask = P & X.train
    hit_tr = (X.hit == 1) & tr_mask
    cand = []
    for r in (1, 2, 3):
        for combo in itertools.combinations(range(len(keys)), r):
            m = C[keys[combo[0]]] & tr_mask
            for j in combo[1:]:
                m = m & C[keys[j]]
            n = int(np.count_nonzero(m))
            if n < 300:                                  # raw signal days on the build years
                continue
            h = int(np.count_nonzero(m & hit_tr))
            cand.append((h / n, n, combo))
        log("search size", r, "candidates so far", len(cand))
    cand.sort(key=lambda x: -x[0])
    search, spread, sigs = [], [], set()
    for tried, (rate_raw, n_raw, combo) in enumerate(cand):
        if (len(search) >= 40 and len(spread) >= 40) or tried >= 6000:
            break
        m = np.ones(len(A), bool)
        for j in combo:
            m &= C[keys[j]]
        st = X.stats(m, per_market=True)
        if (st.get("n_train") or 0) < 40:              # need 40 separate build-year cases after the 42-day spacing
            continue
        sig = (st["n"], st["hits"], st["n_train"], st["n_test"])
        if sig in sigs:                                  # same cases as a combination already listed
            continue
        sigs.add(sig)
        st.update(conditions=[keys[j] for j in combo], kind="search", raw_train_rate=rate_raw, raw_train_days=n_raw)
        if len(search) < 40:
            search.append(st)
        if st["top_month_share"] <= 0.15 and len(spread) < 40:   # not one crash month doing the work
            spread.append(dict(st, kind="search"))
    log("search done; tested", len(cand), "combinations; listed", len(search), "and", len(spread))

    out = dict(
        built=pd.Timestamp.utcnow().isoformat(timespec="minutes"), rise=SL.RISE, horizon=SL.HORIZON, study_from=SL.STUDY_FROM, split=SL.SPLIT,
        stocks=len(D["bars"]), data_built=D.get("built"), base=base, conditions=keys, combos_tested=len(cand),
        current=ref, named=named, search=search, search_spread=spread)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    json.dump(out, open(out_path, "w"), indent=0, default=lambda o: None if o is None else str(o))
    summary(out, out_path.replace(".json", ".txt"))
    log("written", out_path)


def summary(o, path):
    pc = lambda x: "  -  " if x is None else "%5.1f" % (x * 100)
    L = ["Base rate (any stock, any day): %.1f%%   build years %.1f%%   check years %.1f%%" % (o["base"]["all"] * 100, o["base"]["train"] * 100, o["base"]["test"] * 100), ""]
    hdr = "%-58s %5s %6s %6s %6s %6s %6s %6s %5s %6s" % ("setup", "n", "rate", "low95", "same-v", "build", "check", "lift", "weeks", "topmo")
    for title, rows in (("CURRENT FIVE", o["current"]), ("NAMED SETUPS", sorted(o["named"], key=lambda r: -(r.get("rate") or 0))),
                        ("SEARCH (best on build years)", o["search"]), ("SEARCH, no single month over 15% of cases", o["search_spread"])):
        L += [title, hdr]
        for r in rows:
            nm = r.get("name") or " + ".join(r["conditions"])
            L.append("%-58s %5d %6s %6s %6s %6s %6s %6s %5s %6s" % (nm[:58], r["n"], pc(r.get("rate")), pc(r.get("lower95")), pc(r.get("matched")),
                                                                     pc(r.get("rate_train")), pc(r.get("rate_test")), pc(r.get("lift")), r.get("weeks", "-"),
                                                                     pc(r.get("top_month_share"))))
            if r["kind"] == "search":
                L.append("      " + " + ".join(r["conditions"]))
        L.append("")
    open(path, "w").write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", required=True)
    ap.add_argument("--out", default="data/explore_results.json")
    a = ap.parse_args()
    try:
        run(a.dump, a.out)
    except Exception:
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        open(a.out.replace(".json", "_error.txt"), "w").write(traceback.format_exc())
        raise
