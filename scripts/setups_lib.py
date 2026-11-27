"""Rules, features and tests for "Setups before 20% rises" (Strategy tab).

Everything here uses only data up to the day being judged (no look-ahead): a setup is judged on the close of its own day, and what
happened afterwards is measured separately.

A "rise" = the highest close in the next 42 trading days is at least 20% above the setup-day close.
"""
import datetime
import math

import numpy as np
import pandas as pd

ADDED = "2026-11-27"   # day the seven newer setups were added (the page marks them New for a month)
HORIZON = 42          # trading days (about two months)
RISE = 0.20
MIN_CASES = 30        # a success rate is shown only from this many cases
STUDY_FROM = "2021-11-26"   # first setup day of the five-year study (earlier bars only warm up the averages)
SPLIT = "2024-07-01"  # thresholds were picked on setup days before this; later days are the untouched check

# ---------------------------------------------------------------- the setups: exact rules with numbers
# Each condition: (key, text, test(df) -> boolean Series). A setup fires on a day when every condition is true.


def _conds():
    G = lambda d, col, k=1: d.groupby("sym")[col].shift(k)
    S = {}
    S["base"] = dict(
        name="Base breakout on high volume",
        short="Closes above the highest close of the last 40 sessions out of a tight base, on heavy volume, in an uptrend",
        conds=[
            ("brk", "Close above the highest close of the previous 40 sessions", lambda d: d.c > d.hh40),
            ("tight", "Those 40 sessions stayed within a 20% range (highest close to lowest close)", lambda d: (d.hh40 - d.ll40) / d.hh40 <= 0.20),
            ("vol", "Volume at least 1.5 times its 50-day average", lambda d: d.vr >= 1.5),
            ("t200", "Close above the 200-day average", lambda d: d.c > d.sma200),
            ("x50", "50-day average above the 200-day average", lambda d: d.sma50 > d.sma200),
            ("atr", "Average daily range (14 days) at least 2% of the price", lambda d: d.atr >= 0.02),
        ])
    S["pull"] = dict(
        name="Pullback to a rising 50-day average",
        short="A stock in an uptrend that has dipped back to its rising 50-day average with a cooled-off RSI",
        conds=[
            ("rise50", "50-day average up more than 2% over the last 10 sessions", lambda d: d.slope50 > 0.02),
            ("t200", "Close above the 200-day average", lambda d: d.c > d.sma200),
            ("near50", "Close between 5% below and 1% above the 50-day average", lambda d: d.vs50.between(-0.05, 0.01)),
            ("rsi", "RSI (14) between 35 and 55", lambda d: d.rsi.between(35, 55)),
            ("hi", "Close no more than 25% below the 52-week high", lambda d: d.from52h > -0.25),
            ("atr", "Average daily range (14 days) at least 2% of the price", lambda d: d.atr >= 0.02),
        ])
    S["squeeze"] = dict(
        name="Squeeze breakout",
        short="Bollinger Bands pinched to one of their narrowest readings in half a year, then a close above the 20-day high",
        conds=[
            ("squeeze", "Bollinger Band width (20 days, 2 standard deviations) in the narrowest 10% of the last 120 sessions", lambda d: d.bbw_pct <= 0.10),
            ("brk", "Close above the highest close of the previous 20 sessions", lambda d: d.c > d.hh20),
            ("vol", "Volume at least equal to its 50-day average", lambda d: d.vr >= 1.0),
            ("t50", "Close above the 50-day average", lambda d: d.c > d.sma50),
            ("atr", "Average daily range (14 days) at least 1.5% of the price", lambda d: d.atr >= 0.015),
        ])
    S["oversold"] = dict(
        name="Oversold reversal",
        short="A stock 40% or more below its 52-week high that turns up: momentum improving and a close above the previous day's high",
        conds=[
            ("deep", "Close at least 40% below the 52-week high", lambda d: d.from52h <= -0.40),
            ("rsi", "RSI (14) between 30 and 50", lambda d: d.rsi.between(30, 50)),
            ("macd", "MACD histogram higher than the day before", lambda d: d.macdh > G(d, "macdh")),
            ("up", "Close above the previous day's high", lambda d: d.c > G(d, "h")),
            ("vol", "Volume at least equal to its 50-day average", lambda d: d.vr >= 1.0),
        ])
    S["high52"] = dict(
        name="52-week-high breakout",
        short="Closes above the highest close of the last 252 sessions on heavy volume, with the 50-day above the 200-day",
        conds=[
            ("brk", "Close above the highest close of the previous 252 sessions", lambda d: d.c > d.hh252),
            ("vol", "Volume at least 1.5 times its 50-day average", lambda d: d.vr >= 1.5),
            ("x50", "50-day average above the 200-day average", lambda d: d.sma50 > d.sma200),
        ])
    # ---- seven setups added 27 Nov 2026 (the five above and their results are unchanged)
    WASH = ("wash", "Market washout: fewer than 20% of this market's stocks close above their own 50-day average (needs 10 or more stocks with data that day)", lambda d: d.wash)
    D60 = ("deep60", "Close at least 60% below the 52-week high", lambda d: d.from52h <= -0.60)
    D40 = ("deep40", "Close at least 40% below the 52-week high", lambda d: d.from52h <= -0.40)
    MACD = ("macd", "MACD histogram higher than the day before", lambda d: d.macdh > G(d, "macdh"))
    UP = ("up", "Close above the previous day's high", lambda d: d.c > G(d, "h"))
    RSI = ("rsi", "RSI (14) between 30 and 50", lambda d: d.rsi.between(30, 50))
    ATR5 = ("atr5", "Daily range (14-day average true range) at least 5% of the price", lambda d: d.atr >= 0.05)
    S["wash_turn"] = dict(name="Washout: deep fall turning up", short="Market washout, a stock 60% or more below its 52-week high, and its MACD histogram rising",
                          conds=[WASH, D60, MACD])
    S["deep_dry"] = dict(name="Deep fall, volume dried up", short="A stock 60% or more below its 52-week high whose volume has dried up",
                         conds=[D60, ("quiet", "Quiet volume: average volume of the previous 10 sessions below 0.8 times the 50-day average volume", lambda d: d.vdry < 0.8)])
    S["deep_vol"] = dict(name="Deep fall, heavy volume", short="A stock 60% or more below its 52-week high on heavy volume",
                         conds=[D60, ("vol", "Volume at least 1.5 times its 50-day average", lambda d: d.vr >= 1.5)])
    S["wash_bounce"] = dict(name="Washout bounce", short="Market washout, a stock 40% or more below its 52-week high closing above the previous day's high",
                            conds=[WASH, D40, UP])
    S["os60"] = dict(name="Oversold reversal, 60%+ off the high", short="The oversold reversal with a deeper fall: 60% or more below the 52-week high",
                     conds=[D60, RSI, MACD, UP])
    S["os_hv"] = dict(name="Oversold reversal, volatile stock", short="The oversold reversal (40% off the high) in a stock whose daily range is 5% or more of its price",
                      conds=[D40, RSI, MACD, UP, ATR5])
    S["hv_brk"] = dict(name="High-volatility breakout", short="A stock with a daily range of 5% or more closing above its 40-session high on heavy volume",
                       conds=[ATR5, ("brk", "Close above the highest close of the previous 40 sessions", lambda d: d.c > d.hh40),
                              ("vol", "Volume at least 1.5 times its 50-day average", lambda d: d.vr >= 1.5)])
    for k in ("wash_turn", "deep_dry", "deep_vol", "wash_bounce", "os60", "os_hv", "hv_brk"):
        S[k]["group"] = "new"
        S[k]["added"] = ADDED
    return S


SETUPS = _conds()
CORE = ["base", "pull", "squeeze", "oversold", "high52"]
NEW = ["wash_turn", "deep_dry", "deep_vol", "wash_bounce", "os60", "os_hv", "hv_brk"]
ORDER = CORE + NEW
WASH_BELOW = 0.20     # market washout: share of a market's stocks above their 50-day average below this
WASH_MIN_STOCKS = 10  # fewer stocks than this with data on the day: washout setups cannot fire


def add_washout(F, market_of):
    """Adds 'breadth' (share of the market's stocks, with a 50-day average, that close above it) and 'wash' to every stock frame in F (before apply_rules).
    Computed per market and per day from the same stock list; past and same-day data only."""
    parts = []
    for s, df in F.items():
        parts.append(pd.DataFrame({"mk": market_of[s], "date": df.date.values, "a": np.where(df.sma50.notna(), (df.c > df.sma50).astype(float), np.nan)}))
    M = pd.concat(parts)
    g = M.groupby(["mk", "date"]).a
    br, n = g.mean(), g.size()
    br[n < WASH_MIN_STOCKS] = np.nan
    for s, df in F.items():
        key = pd.MultiIndex.from_arrays([[market_of[s]] * len(df), df.date.values])
        df["breadth"] = br.reindex(key).values
        df["wash"] = (df.breadth < WASH_BELOW).fillna(False)
    return F


# ---------------------------------------------------------------- features (past data only)
def features(sym, b):
    """b: dict of lists t (days since epoch), o, h, l, c, v -> DataFrame with every indicator the rules and the descriptions use."""
    df = pd.DataFrame({k: b[k] for k in ("t", "o", "h", "l", "c", "v")})
    df["date"] = pd.to_datetime(df.t * 86400, unit="s").dt.normalize()
    df["sym"] = sym
    c, h, l, v = df.c, df.h, df.l, df.v.astype(float)
    df["ret"] = c.pct_change()
    df["sma20"] = c.rolling(20).mean()
    df["sma50"] = c.rolling(50).mean()
    df["sma200"] = c.rolling(200).mean()
    df["vs50"] = c / df.sma50 - 1
    df["vs200"] = c / df.sma200 - 1
    df["slope50"] = df.sma50 / df.sma50.shift(10) - 1
    df["slope200"] = df.sma200 / df.sma200.shift(20) - 1
    df["vol50"] = v.rolling(50).mean().shift(1)
    df["vr"] = v / df.vol50
    df["vdry"] = v.rolling(10).mean().shift(1) / df.vol50
    for n in (20, 40, 60, 120, 252):
        df["hh%d" % n] = c.rolling(n).max().shift(1)
        df["ll%d" % n] = c.rolling(n).min().shift(1)
    df["rv20"] = df.ret.rolling(20).std() * math.sqrt(252)
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    df["atr"] = tr.rolling(14).mean() / c
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    df["rsi"] = 100 - 100 / (1 + up / dn)
    e12, e26 = c.ewm(span=12, adjust=False).mean(), c.ewm(span=26, adjust=False).mean()
    m = e12 - e26
    df["macdh"] = (m - m.ewm(span=9, adjust=False).mean()) / c
    ma20, sd = c.rolling(20).mean(), c.rolling(20).std()
    df["bbw"] = 4 * sd / ma20
    df["bbw_pct"] = df.bbw.rolling(120).apply(lambda x: (x[:-1] < x[-1]).mean(), raw=True)
    df["l10"] = l.rolling(10).min()
    df["hi52"] = c.rolling(252, min_periods=120).max()
    df["from52h"] = c / df.hi52 - 1
    df["gap"] = df.o / c.shift() - 1
    df["earn_like"] = ((df.gap.abs() >= 0.04) & (df.vr >= 2.5)).astype(float)   # stand-in for an earnings reaction day (see the page's note)
    # what happened next (only measurable once the days have passed)
    ca = c.values
    n = len(ca)
    rev = pd.Series(ca[::-1])
    nxt = rev.shift(1).rolling(HORIZON, min_periods=1).max().values[::-1]      # highest close of the next <=42 sessions
    avail = np.minimum(np.arange(n)[::-1], HORIZON)                           # how many of those sessions exist
    fmax = nxt / ca - 1
    done = avail >= HORIZON
    hit = (fmax >= RISE)
    df["fmax"] = np.where(done | hit, fmax, np.nan)
    df["hit"] = np.where(done | hit, hit.astype(float), np.nan)
    df.loc[df.index[-1], ["fmax", "hit"]] = np.nan
    return df


def apply_rules(df):
    """Adds <setup>_met (number of conditions true) and <setup> (all true) columns."""
    for k in ORDER:
        cs = SETUPS[k]["conds"]
        flags = pd.concat([fn(df).fillna(False).astype(int) for _, _, fn in cs], axis=1)
        df[k + "_met"] = flags.sum(axis=1)
        df[k] = df[k + "_met"] == len(cs)
        for (ck, _, _), col in zip(cs, flags.columns):
            df["%s_%s" % (k, ck)] = flags[col].astype(bool)
    return df


def levels(setup, r):
    """Support, resistance and the invalidation level for a setup on row r (a Series of features + 'l10' = lowest low of 10 sessions)."""
    c = float(r.c)
    hh60 = float(r.hh60) if pd.notna(r.hh60) else None
    hh252 = float(r.hh252) if pd.notna(r.hh252) else None
    out = dict(breakout=None, support=None, resistance=None, invalid=None)
    if setup in ("base", "hv_brk"):
        lvl = float(r.hh40)
        out.update(breakout=lvl, support=float(r.ll40), invalid=lvl * 0.97, resistance=hh252 if hh252 and hh252 > c else None)
    elif setup == "squeeze":
        lvl = float(r.hh20)
        out.update(breakout=lvl, support=float(r.sma20), invalid=lvl * 0.97, resistance=hh252 if hh252 and hh252 > c else (hh60 if hh60 and hh60 > c else None))
    elif setup == "high52":
        lvl = float(r.hh252)
        out.update(breakout=lvl, support=lvl, invalid=lvl * 0.97, resistance=None)
    elif setup == "pull":
        out.update(support=float(r.sma50), invalid=float(r.l10), resistance=hh60 if hh60 and hh60 > c else None)
    elif setup in ("oversold", "wash_turn", "deep_dry", "deep_vol", "wash_bounce", "os60", "os_hv"):
        out.update(support=float(r.l10), invalid=float(r.l10), resistance=float(r.sma50) if pd.notna(r.sma50) and r.sma50 > c else (hh60 if hh60 and hh60 > c else None))
    return out


def characteristics(r):
    """One line about what the chart looked like going into the day (all from data up to that day)."""
    p = lambda x: ("%+.0f%%" % (x * 100))
    bits = []
    if pd.notna(r.sma200):
        bits.append("%s vs 200-day (%s)" % (p(r.vs200), "rising" if r.slope200 > 0.005 else "falling" if r.slope200 < -0.005 else "flat"))
    if pd.notna(r.sma50):
        bits.append("%s vs 50-day (%s)" % (p(r.vs50), "rising" if r.slope50 > 0.01 else "falling" if r.slope50 < -0.01 else "flat"))
    if pd.notna(r.hh40) and r.hh40 > 0:
        depth = (r.hh40 - r.ll40) / r.hh40
        bits.append("40-day range %.0f%% deep" % (depth * 100))
    if pd.notna(r.vdry) and pd.notna(r.vr):
        bits.append("volume %.1f× avg before, %.1f× on the day" % (r.vdry, r.vr))
    if pd.notna(r.hh40):
        bits.append("40-day high %.4g" % r.hh40)
    if pd.notna(r.rsi):
        bits.append("RSI %.0f" % r.rsi)
    bits.append("MACD histogram %s" % ("up" if r.macdh > 0 else "down"))
    if pd.notna(r.bbw_pct):
        bits.append("Bollinger width %.0f%% (%d%% of last 120 days narrower)" % (r.bbw * 100, round(r.bbw_pct * 100)))
    return "; ".join(bits)


# ---------------------------------------------------------------- the test over every stock and every day
def decluster(idx_by_sym, gap=HORIZON):
    """Keep a stock's first signal, then ignore its next ones for 42 sessions, so one move is not counted several times."""
    keep = []
    for s, idxs in idx_by_sym.items():
        last = -10 ** 9
        for i in idxs:
            if i - last >= gap:
                keep.append(i)
                last = i
    return keep


def run_study(frames):
    """frames: {sym: features DataFrame with rules applied}. Returns (signals DataFrame, stats helper data)."""
    A = pd.concat(frames.values(), ignore_index=True)
    A = A.sort_values(["sym", "date"]).reset_index(drop=True)
    P = A[A.date >= STUDY_FROM]
    edges = np.nanquantile(P.rv20.dropna(), np.linspace(0, 1, 21))
    edges[0], edges[-1] = -1, 99
    A["vb"] = pd.cut(A.rv20, edges, labels=False)
    base_vb = A[(A.date >= STUDY_FROM) & A.hit.notna()].groupby("vb").hit.mean()
    A["mbase"] = A.vb.map(base_vb)
    return A


def peak_info(A_sym_c, i):
    """For a signal on bar i of one stock's close array: (peak gain, days to first +20%, days to peak, largest drop before the peak)."""
    c = A_sym_c
    w = c[i + 1: i + 1 + HORIZON]
    if len(w) == 0:
        return None
    j = int(np.argmax(w))
    hitd = np.where(w >= c[i] * (1 + RISE))[0]
    return dict(peak=float(w[j]), gain=float(w[j] / c[i] - 1), days=(int(hitd[0]) + 1 if len(hitd) else None), pdays=j + 1, drop=float(w[: j + 1].min() / c[i] - 1))
