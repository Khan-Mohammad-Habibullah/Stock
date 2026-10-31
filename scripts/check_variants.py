#!/usr/bin/env python3
"""Which standard definition of each indicator reproduces the board's original
readings best? Fetches bars for the originally-built holdings once, cuts them at
the original build date and scores several common variants per field.
Writes data/preview/variants.json."""
import datetime
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import board_lib as L

CUT = "2026-10-13"
s = open("index.html", encoding="utf-8").read()
H = json.JSONDecoder().raw_decode(s, s.index('"holdings":[') + len('"holdings":'))[0]
rows = [r for r in H if "estimated from" not in (r["o1y_why"] or "")]
info = L.scan_symbols([r["sym"] for r in rows])
bars, err = L.fetch_many([(r["sym"], info.get(r["sym"], {}).get("country"), None) for r in rows])
ce = datetime.datetime.strptime(CUT, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc).timestamp() + 86400


def ema_tv(a, n):  # TradingView: seeded with the simple average of the first n values
    k = 2 / (n + 1)
    o = [float("nan")] * (n - 1) + [sum(a[:n]) / n]
    for i in range(n, len(a)):
        o.append(a[i] * k + o[-1] * (1 - k))
    return o


def macd_v(c, v):
    e = ema_tv if v.get("tv") else L.ema
    e12, e26 = e(c, 12), e(c, 26)
    m = [e12[i] - e26[i] for i in range(len(c))]
    mm = [x for x in m if not math.isnan(x)]
    sg = [float("nan")] * (len(m) - len(mm)) + e(mm, 9)
    h = [m[i] - sg[i] for i in range(len(m))]
    n = len(c) - 1
    up = m[n] > sg[n]
    lag = v.get("lag", 1)
    rising = (m[n] > m[n - lag]) if v.get("line") else (h[n] > h[n - lag])
    return ("Bullish, rising" if rising else "Bullish, fading") if up else ("Bearish, improving" if rising else "Bearish, falling")


def alli_v(B, v):
    h = [b[2] for b in B]; l = [b[3] for b in B]; c = [b[4] for b in B]
    n = len(c) - 1
    med = [(h[i] + l[i]) / 2 for i in range(n + 1)]
    jaw, teeth, lips = L.wilder(med, 13), L.wilder(med, 8), L.wilder(med, 5)
    sh = v.get("shift", True)
    at = lambda k: (jaw[k - 8], teeth[k - 5], lips[k - 3]) if sh else (jaw[k], teeth[k], lips[k])
    J, T, P = at(n)
    spread = (max(J, T, P) - min(J, T, P)) / c[n]
    if spread < v.get("sleep", 0.01):
        return "Sleeping"
    up, dn = P > T > J, P < T < J
    if v.get("price"):
        up, dn = up and c[n] > P, dn and c[n] < P
    if v.get("sustain"):
        J3, T3, P3 = at(n - v["sustain"])
        up, dn = up and P3 > T3 > J3, dn and P3 < T3 < J3
    if v.get("widen"):
        J3, T3, P3 = at(n - 3)
        w = (max(J3, T3, P3) - min(J3, T3, P3)) / c[n - 3]
        up, dn = up and spread > w, dn and spread > w
    return "Bullish" if up else "Bearish" if dn else "Waking/mixed"


def struct_v(B, v):
    h = [b[2] for b in B]; l = [b[3] for b in B]; c = [b[4] for b in B]
    n = len(c) - 1
    w = v["w"]
    sh, sl = [], []
    for i in range(w, n - (w if v.get("confirmed", True) else 0) + 1):
        lo_, hi_ = i - w, min(n + 1, i + w + 1)
        if h[i] == max(h[lo_:hi_]): sh.append((i, h[i]))
        if l[i] == min(l[lo_:hi_]): sl.append((i, l[i]))
    s1, s2 = sh[-2:], sl[-2:]
    hh = len(s1) == 2 and s1[1][1] > s1[0][1]
    hl = len(s2) == 2 and s2[1][1] > s2[0][1]
    two = len(s1) == 2 and len(s2) == 2
    brk_h = s1 and c[n] > s1[-1][1]
    brk_l = s2 and c[n] < s2[-1][1]
    pat = ("Higher highs & higher lows" if (hh and hl) else "Lower highs & lower lows" if (two and not hh and not hl) else
           "Higher highs, lower lows (broadening)" if hh else "Higher lows, lower highs (squeeze)")
    if v.get("breaks_first", True):
        return "Broke above last swing high" if brk_h else "Broke below last swing low" if brk_l else pat
    return pat


def obv_v(B, v):
    c = [b[4] for b in B]; vol = [b[5] for b in B]
    n = len(c) - 1
    o = [0.0]
    for i in range(1, n + 1):
        o.append(o[-1] + (vol[i] if c[i] > c[i - 1] else (-vol[i] if c[i] < c[i - 1] else 0)))
    if v.get("vs_ago"):
        return "Up" if o[n] > o[n - v["vs_ago"]] else "Down"
    k = v["sma"]
    return "Up" if o[n] > sum(o[n - k + 1:n + 1]) / k else "Down"


def boll_v(c, v):
    n = len(c) - 1
    sma = lambda k: sum(c[k - 19:k + 1]) / 20
    sd = lambda k: math.sqrt(sum((c[j] - sma(k)) ** 2 for j in range(k - 19, k + 1)) / 20)
    up, lo = sma(n) + 2 * sd(n), sma(n) - 2 * sd(n)
    pctb = (c[n] - lo) / (up - lo)
    bw = [4 * sd(k) / sma(k) for k in range(max(20, n - v["look"]), n + 1)]
    rank = len([x for x in bw if x <= bw[-1]]) / len(bw)
    sq = rank <= v["q"]
    if v.get("squeeze_first") and sq:
        return "Squeeze"
    return ("Above upper band" if c[n] > up else "Below lower band" if c[n] < lo else "Squeeze" if sq else
            "Near upper band" if pctb >= 0.8 else "Near lower band" if pctb <= 0.2 else "Mid band")


TESTS = {
    "macd": [("histogram vs 1 day", {}), ("histogram vs 2 days", {"lag": 2}), ("MACD line vs 1 day", {"line": True}),
             ("TradingView EMA seed, histogram", {"tv": True}), ("TradingView EMA seed, line", {"tv": True, "line": True})],
    "alligator": [("order, sleep<1%", {}), ("order, sleep<0.5%", {"sleep": 0.005}), ("order, sleep<2%", {"sleep": 0.02}),
                  ("order + price beyond lips", {"price": True}), ("order held 3 bars", {"sustain": 3}), ("order + widening", {"widen": True}),
                  ("unshifted order", {"shift": False}), ("order + price, sleep<2%", {"price": True, "sleep": 0.02}),
                  ("order held 5 bars + price", {"sustain": 5, "price": True})],
    "structure": [("fractal 2", {"w": 2}), ("fractal 3", {"w": 3}), ("fractal 5", {"w": 5}), ("fractal 3 no break-first", {"w": 3, "breaks_first": False}),
                  ("fractal 5 no break-first", {"w": 5, "breaks_first": False}), ("fractal 10", {"w": 10}), ("fractal 2 unconfirmed", {"w": 2, "confirmed": False})],
    "obv": [("vs 50-day avg", {"sma": 50}), ("vs 20-day avg", {"sma": 20}), ("vs 10-day avg", {"sma": 10}), ("vs 20 days ago", {"vs_ago": 20}),
            ("vs 50 days ago", {"vs_ago": 50})],
    "bollinger": [("rank<=20% of 126", {"look": 125, "q": 0.2}), ("rank<=20% of 252", {"look": 251, "q": 0.2}), ("rank<=25% of 126", {"look": 125, "q": 0.25}),
                  ("squeeze first, 126", {"look": 125, "q": 0.2, "squeeze_first": True}), ("squeeze first, 252", {"look": 251, "q": 0.2, "squeeze_first": True})],
}
score = {f: {name: 0 for name, _ in vs} for f, vs in TESTS.items()}
total = 0
for r in rows:
    if r["sym"] not in bars:
        continue
    B = [b for b in bars[r["sym"]][0] if b[0] < ce]
    if len(B) < 260:
        continue
    c = [b[4] for b in B]
    total += 1
    for name, v in TESTS["macd"]: score["macd"][name] += macd_v(c, v) == r["macd"]
    for name, v in TESTS["alligator"]: score["alligator"][name] += alli_v(B, v) == r["alligator"]
    for name, v in TESTS["structure"]: score["structure"][name] += struct_v(B, v) == r["structure"]
    for name, v in TESTS["obv"]: score["obv"][name] += obv_v(B, v) == r["obv"]
    for name, v in TESTS["bollinger"]: score["bollinger"][name] += boll_v(c, v) == r["bollinger"]
os.makedirs("data/preview", exist_ok=True)
json.dump(dict(rows=total, score=score), open("data/preview/variants.json", "w"), indent=1)
print("rows", total)
for f, d in score.items():
    print(f, sorted(d.items(), key=lambda kv: -kv[1]))
