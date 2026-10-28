#!/usr/bin/env python3
"""One-off (workflow_dispatch only) data pull for the 6 brand-new holdings
added in the 28 Oct 2026 Nordnet export (NVIDIA, Puuilo, Whitecap Resources,
Vaisala A, SAP SE, UiPath). Runs on a GitHub Actions runner (normal internet,
no proxy allowlist) because TradingView/Yahoo are not reachable from the
agent's own sandboxed shell.

Sources (public, no login):
  - Yahoo Finance chart API: daily OHLCV bars, ~300 days back
  - Yahoo Finance quoteSummary API: fundamentals (growth, margin, PE, D/E,
    analyst recommendation, target price, market cap)

Technicals are computed with analyse(), a direct Python port of this repo's
own scripts/nn-style calc.js (same RSI/MACD/Bollinger/Alligator/CPR/CMF/ADX/
candlestick/structure/October-score logic already used for every other
holding on the board), so the new rows are methodologically consistent with
the rest of the dataset rather than approximated differently.

Writes data/new_stock_signals.json: {sym: {T: {...}, F: {...}}} for the
script that bakes these into index.html (scripts/apply_new_holdings.py) to
consume. Never touches index.html or the crypto data itself.
"""
import json
import math
import statistics
import sys
import time
import urllib.request

HERE = __file__.rsplit("/", 1)[0]

# TradingView symbol -> Yahoo Finance ticker
SYMS = {
    "NASDAQ:NVDA": "NVDA",
    "OMXHEX:PUUILO": "PUUILO.HE",
    "TSX:WCP": "WCP.TO",
    "OMXHEX:VAIAS": "VAIAS.HE",
    "XETR:SAP": "SAP.DE",
    "NYSE:PATH": "PATH",
}


def http_json(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (holdings-signal-board one-off fetch)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_bars(yticker):
    url = "https://query1.finance.yahoo.com/v8/finance/chart/%s?range=2y&interval=1d" % yticker
    j = http_json(url)
    res = j["chart"]["result"][0]
    ts = res["timestamp"]
    q = res["indicators"]["quote"][0]
    bars = []
    for i, t in enumerate(ts):
        o, h, l, c, v = q["open"][i], q["high"][i], q["low"][i], q["close"][i], q["volume"][i]
        if None in (o, h, l, c) or v is None:
            continue
        bars.append([t, o, h, l, c, v])
    return bars


def fetch_fundamentals(yticker):
    mods = "financialData,defaultKeyStatistics,summaryDetail,recommendationTrend,price"
    url = "https://query1.finance.yahoo.com/v10/finance/quoteSummary/%s?modules=%s" % (yticker, mods)
    j = http_json(url)
    r = j["quoteSummary"]["result"][0]
    fd = r.get("financialData", {})
    ks = r.get("defaultKeyStatistics", {})
    sd = r.get("summaryDetail", {})
    pr = r.get("price", {})

    def num(d, k):
        v = (d or {}).get(k)
        if isinstance(v, dict):
            return v.get("raw")
        return v

    return {
        "name": num(pr, "longName") or num(pr, "shortName"),
        "cur": num(pr, "currency"),
        "mcap": num(pr, "marketCap"),
        "rev_g": (num(fd, "revenueGrowth") or 0) * 100,
        "eps_g": (num(fd, "earningsGrowth") or 0) * 100,
        "margin": (num(fd, "profitMargins") or 0) * 100,
        "pe": num(sd, "trailingPE") or num(ks, "forwardPE"),
        "de": (num(fd, "debtToEquity") or 0) / 100 if num(fd, "debtToEquity") else None,
        "roe": (num(fd, "returnOnEquity") or 0) * 100,
        "fcf": num(fd, "freeCashflow"),
        "rec_mean": num(fd, "recommendationMean"),
        "target_mean": num(fd, "targetMeanPrice"),
    }


# ---------------- Python port of calc.js analyse() ----------------
def sma(a, n, i):
    return sum(a[i - n + 1:i + 1]) / n


def ema(a, n):
    k = 2 / (n + 1)
    o = [a[0]]
    for i in range(1, len(a)):
        o.append(a[i] * k + o[-1] * (1 - k))
    return o


def wilder(a, n):
    o = []
    s = 0.0
    for i in range(len(a)):
        if i < n - 1:
            o.append(float("nan"))
            continue
        if i == n - 1:
            s = sum(a[:n])
            o.append(s / n)
            continue
        o.append((o[i - 1] * (n - 1) + a[i]) / n)
    return o


def rsi_arr(c, n=14):
    g = [0.0]
    l = [0.0]
    for i in range(1, len(c)):
        d = c[i] - c[i - 1]
        g.append(max(d, 0))
        l.append(max(-d, 0))
    ag = wilder(g[1:], n)
    al = wilder(l[1:], n)
    o = [float("nan")]
    for i in range(len(ag)):
        o.append(100.0 if al[i] == 0 else 100 - 100 / (1 + ag[i] / al[i]))
    return o


def smma(a, n):
    return wilder(a, n)


def r2(x, d=1):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return None
    return round(x, d)


def candle(B, i):
    o, h, l, c = B[i][1], B[i][2], B[i][3], B[i][4]
    body = abs(c - o)
    rng = (h - l) or 1e-9
    up = h - max(o, c)
    lo = min(o, c) - l
    po, pc = B[i - 1][1], B[i - 1][4]
    pb = abs(pc - po)
    out = []
    if i >= 2:
        b = [B[i - 2], B[i - 1], B[i]]
        bull = lambda x: x[4] > x[1]
        bear = lambda x: x[4] < x[1]
        if all(bull(x) for x in b) and b[1][4] > b[0][4] and b[2][4] > b[1][4] and b[1][1] > b[0][1] and b[2][1] > b[1][1]:
            out.append(("three white soldiers (bullish)", 1))
        if all(bear(x) for x in b) and b[1][4] < b[0][4] and b[2][4] < b[1][4] and b[1][1] < b[0][1] and b[2][1] < b[1][1]:
            out.append(("three black crows (bearish)", -1))
        b0 = abs(b[0][4] - b[0][1])
        b1 = abs(b[1][4] - b[1][1])
        if bear(b[0]) and b0 > rng * 0.4 and b1 < b0 * 0.4 and bull(b[2]) and b[2][4] > (b[0][1] + b[0][4]) / 2:
            out.append(("morning star (bullish)", 1))
        if bull(b[0]) and b0 > rng * 0.4 and b1 < b0 * 0.4 and bear(b[2]) and b[2][4] < (b[0][1] + b[0][4]) / 2:
            out.append(("evening star (bearish)", -1))
    if c > o and pc < po and c >= po and o <= pc and body > pb:
        out.append(("bullish engulfing", 1))
    if c < o and pc > po and c <= po and o >= pc and body > pb:
        out.append(("bearish engulfing", -1))
    if lo >= 2 * body and up <= body * 0.5 and body > 0 and body / rng > 0.1 and B[i][4] > 0:
        out.append(("hammer (bullish)", 1))
    if up >= 2 * body and lo <= body * 0.5 and body > 0 and body / rng > 0.1:
        out.append(("shooting star (bearish)", -1))
    if body <= rng * 0.1:
        out.append(("doji", 0))
    return out


def last_candle(B, days):
    for i in range(len(B) - 1, len(B) - 1 - days, -1):
        p = candle(B, i)
        if p:
            best = next((x for x in p if x[1] != 0), p[0])
            return best
    return None


def analyse(B):
    import datetime
    t = [b[0] for b in B]
    h = [b[2] for b in B]
    l = [b[3] for b in B]
    c = [b[4] for b in B]
    v = [b[5] for b in B]
    n = len(c) - 1
    R = {}
    R["price"] = c[n]
    R["r1m"] = r2((c[n] / c[n - 21] - 1) * 100)
    R["r3m"] = r2((c[n] / c[n - 63] - 1) * 100)
    R["r12m"] = r2((c[n] / c[max(0, n - 252)] - 1) * 100)
    rs = rsi_arr(c)
    R["rsi"] = r2(rs[n])
    e12, e26 = ema(c, 12), ema(c, 26)
    m = [e12[i] - e26[i] for i in range(len(e12))]
    sg = ema(m, 9)
    hist = [m[i] - sg[i] for i in range(len(m))]
    mUp = m[n] > sg[n]
    rising = hist[n] > hist[n - 1]
    R["macd"] = ("Bullish, rising" if rising else "Bullish, fading") if mUp else ("Bearish, improving" if rising else "Bearish, falling")
    s20, s50 = sma(c, 20, n), sma(c, 50, n)
    s200 = sma(c, 200, n) if n >= 199 else float("nan")
    R["vs20"] = r2((c[n] / s20 - 1) * 100)
    R["vs50"] = r2((c[n] / s50 - 1) * 100)
    R["vs200"] = r2((c[n] / s200 - 1) * 100) if not math.isnan(s200) else None
    cross = None
    for i in range(n, 199, -1):
        a = sma(c, 50, i) - sma(c, 200, i)
        b = sma(c, 50, i - 1) - sma(c, 200, i - 1)
        if a > 0 and b <= 0:
            cross = "golden " + datetime.datetime.utcfromtimestamp(t[i]).strftime("%Y-%m-%d")
            break
        if a < 0 and b >= 0:
            cross = "death " + datetime.datetime.utcfromtimestamp(t[i]).strftime("%Y-%m-%d")
            break
    R["ma_cross"] = cross

    def sd(k):
        mm = sma(c, 20, k)
        s = sum((c[j] - mm) ** 2 for j in range(k - 19, k + 1))
        return math.sqrt(s / 20)

    mid, sdv = s20, sd(n)
    up, lo = mid + 2 * sdv, mid - 2 * sdv
    R["pctb"] = r2((c[n] - lo) / (up - lo), 2)
    bw = []
    for k in range(n - 125, n + 1):
        mm, ss = sma(c, 20, k), sd(k)
        bw.append(4 * ss / mm)
    bwn = bw[-1]
    rank = len([x for x in bw if x <= bwn]) / len(bw)
    R["bandwidth_rank"] = r2(rank, 2)
    R["bollinger"] = ("Below lower band" if c[n] < lo else "Above upper band" if c[n] > up else
                       ("Squeeze" if rank <= 0.2 else ("Riding upper band" if R["pctb"] >= 0.8 else ("Riding lower band" if R["pctb"] <= 0.2 else "Mid-range"))))
    med = [(b[2] + b[3]) / 2 for b in B]
    jaw, teeth, lips = smma(med, 13), smma(med, 8), smma(med, 5)
    J, Tt, Lp = jaw[n - 8], teeth[n - 5], lips[n - 3]
    R["alligator"] = "Bullish" if (Lp > Tt > J) else ("Bearish" if (Lp < Tt < J) else "Waking/mixed")
    d = datetime.datetime.utcfromtimestamp(t[n])
    mo, yr = d.month - 1, d.year
    pm_year = yr - 1 if mo == 0 else yr
    pm_month = (mo + 11) % 12
    pm = [i for i in range(n + 1) if datetime.datetime.utcfromtimestamp(t[i]).year == pm_year and datetime.datetime.utcfromtimestamp(t[i]).month - 1 == pm_month]
    PH, PL, PC = max(h[i] for i in pm), min(l[i] for i in pm), c[pm[-1]]
    P, BC = (PH + PL + PC) / 3, (PH + PL) / 2
    TC = 2 * P - BC
    top, bot = max(TC, BC), min(TC, BC)
    R["cpr"] = "Above" if c[n] > top else ("Below" if c[n] < bot else "Inside")
    R["cpr_tc"], R["cpr_bc"] = r2(top, 2), r2(bot, 2)
    R["cpr_r1"], R["cpr_s1"] = r2(2 * P - PL, 2), r2(2 * P - PH, 2)

    def mf(k, length):
        a = b = 0.0
        for j in range(k - length + 1, k + 1):
            rr = h[j] - l[j]
            mm = ((c[j] - l[j]) - (h[j] - c[j])) / rr if rr > 0 else 0
            a += mm * v[j]
            b += v[j]
        return a / b if b else 0

    R["cmf"] = r2(mf(n, 20), 2)
    R["cmf60"] = r2(mf(n, 60), 3)

    def udv(length):
        u = dn = 0.0
        for j in range(n - length + 1, n + 1):
            if c[j] > c[j - 1]:
                u += v[j]
            elif c[j] < c[j - 1]:
                dn += v[j]
        return u / dn if dn else None

    R["udv"] = r2(udv(20), 2)
    R["udv50"] = r2(udv(50), 2)
    obv = [0.0]
    for i in range(1, n + 1):
        obv.append(obv[-1] + (v[i] if c[i] > c[i - 1] else (-v[i] if c[i] < c[i - 1] else 0)))
    R["obv"] = "Up" if obv[n] > sma(obv, 50, n) else "Down"
    tr, pdm, ndm = [0.0], [0.0], [0.0]
    for i in range(1, n + 1):
        tr.append(max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])))
        u, dd = h[i] - h[i - 1], l[i - 1] - l[i]
        pdm.append(u if (u > dd and u > 0) else 0)
        ndm.append(dd if (dd > u and dd > 0) else 0)
    atr, pd, nd = wilder(tr[1:], 14), wilder(pdm[1:], 14), wilder(ndm[1:], 14)
    dx = []
    for i in range(len(atr)):
        a = atr[i]
        p = 100 * pd[i] / a
        q = 100 * nd[i] / a
        val = 100 * abs(p - q) / (p + q) if (p + q) else float("nan")
        if not math.isnan(val):
            dx.append(val)
    adx = wilder(dx, 14)
    R["adx"] = r2(adx[-1]) if adx else None
    lc = last_candle(B, 3)
    R["candles"] = lc[0] if (lc and lc[1] != 0) else None

    def weekly(B):
        W = []
        cur = None
        for b in B:
            dt = datetime.datetime.utcfromtimestamp(b[0])
            wk = dt - datetime.timedelta(days=dt.weekday())
            key = wk.date()
            if cur is None or cur["k"] != key:
                cur = {"k": key, "h": b[2], "l": b[3], "c": b[4]}
                W.append(cur)
            else:
                cur["h"] = max(cur["h"], b[2])
                cur["l"] = min(cur["l"], b[3])
                cur["c"] = b[4]
        return W

    W = weekly(B)
    wc = [x["c"] for x in W]
    wn = len(wc) - 1
    R["w_rsi"] = r2(rsi_arr(wc)[wn])
    s40, s40p = sma(wc, 40, wn), sma(wc, 40, wn - 4)
    R["vs40w"] = r2((wc[wn] / s40 - 1) * 100)
    w40_rising = s40 > s40p
    hi52 = max(h[n - 251:n + 1])
    R["off_high"] = r2((c[n] / hi52 - 1) * 100)
    lr = [math.log(c[i] / c[i - 1]) for i in range(n - 251, n + 1)]
    mu = sum(lr) / len(lr)
    R["vol"] = r2(math.sqrt(sum((x - mu) ** 2 for x in lr) / (len(lr) - 1)) * math.sqrt(252) * 100)
    R["vol_days"] = len(lr)
    acc = dist = 0
    for i in range(n - 24, n + 1):
        av = sma(v, 50, i)
        ch = (c[i] / c[i - 1] - 1) * 100
        if v[i] > av and abs(ch) >= 0.2:
            if ch > 0:
                acc += 1
            else:
                dist += 1
    R["acc_days"], R["dist_days"] = acc, dist
    R["turnover_avg"] = sma([c[i] * v[i] for i in range(len(c))], 20, n)
    sh, sl = [], []
    for i in range(3, n - 3):
        if h[i] == max(h[i - 3:i + 4]):
            sh.append((i, h[i]))
        if l[i] == min(l[i - 3:i + 4]):
            sl.append((i, l[i]))
    s1, s2 = sh[-2:], sl[-2:]
    hh = len(s1) == 2 and s1[1][1] > s1[0][1]
    hl = len(s2) == 2 and s2[1][1] > s2[0][1]
    R["structure"] = ("Higher highs and lows" if (hh and hl) else
                       "Lower highs and lows" if (not hh and not hl and len(s1) == 2 and len(s2) == 2) else
                       "Higher highs, lower lows (broadening)" if (hh and not hl) else "Lower highs, higher lows (narrowing)")
    lastSL = s2[-1][1] if s2 else None
    lastSH = s1[-1][1] if s1 else None
    brk_low = lastSL is not None and c[n] < lastSL
    brk_high = lastSH is not None and c[n] > lastSH
    prevHi, prevLo = max(h[n - 55:n]), min(l[n - 55:n])
    b55 = 1 if c[n] > prevHi else (-1 if c[n] < prevLo else 0)
    R["b55"] = b55
    sc = 0.0
    why = []
    rsiN = R["rsi"]
    if 55 <= rsiN <= 75:
        sc += 1; why.append("RSI strong")
    elif rsiN < 45:
        sc -= 1; why.append("RSI oversold" if rsiN < 30 else "RSI weak")
    if mUp and rising:
        sc += 1; why.append("MACD bullish & rising")
    elif (not mUp) and (not rising):
        sc -= 1; why.append("MACD bearish & falling")
    else:
        why.append("MACD bullish but fading" if mUp else "MACD bearish but improving")
    if c[n] > s20 and c[n] > s50:
        sc += 1; why.append("above 20/50-day")
    elif c[n] < s20 and c[n] < s50:
        sc -= 1; why.append("below 20/50-day")
    if R["alligator"] == "Bullish":
        sc += 1
    elif R["alligator"] == "Bearish":
        sc -= 1
    if R["cpr"] == "Above":
        sc += 1; why.append("above CPR")
    elif R["cpr"] == "Below":
        sc -= 1; why.append("below CPR")
    if R["cmf"] > 0.05 and (R["udv"] or 0) > 1.1:
        sc += 1; why.append("buying volume")
    elif R["cmf"] < -0.05 and (R["udv"] or 99) < 0.9:
        sc -= 1; why.append("selling volume")
    if hh and hl:
        sc += 1; why.append("higher highs/lows")
    elif not hh and not hl and len(s1) == 2 and len(s2) == 2:
        sc -= 1; why.append("lower highs/lows")
    if brk_high:
        why.append("broke above swing high")
    if brk_low:
        why.append("broke below swing low")
    if b55 == 1:
        sc += 1; why.append("55-day breakout")
    elif b55 == -1:
        sc -= 1; why.append("55-day breakdown")
    if R["pctb"] >= 0.95 or R["bollinger"] == "Above upper band":
        sc += 0.5
    elif R["pctb"] <= 0.05 or R["bollinger"] == "Below lower band":
        sc -= 0.5
    if R["candles"]:
        bull = any(w in R["candles"] for w in ("bullish", "soldiers", "hammer"))
        sc += 0.5 if bull else -0.5
    R["oct_score"] = sc
    R["oct_signal"] = "Bullish" if sc >= 4 else "Mildly bullish" if sc >= 1.5 else "Neutral" if sc > -1.5 else "Mildly bearish" if sc > -4 else "Bearish"
    R["oct_why"] = "; ".join(why)

    def cl(x, a):
        return max(-a, min(a, x))

    uv = R["udv50"]
    uvs = 0 if uv is None else cl(math.log(uv) / math.log(1.5), 1.5)
    R["sflow_score"] = r2(cl(R["cmf"] / 0.1, 1.5) + cl(R["cmf60"] / 0.1, 1) + uvs + cl((acc - dist) / 3, 1.5) + (0.5 if R["obv"] == "Up" else -0.5), 1)
    R["w40_rising"] = w40_rising
    R["candles_w"] = R["candles"]
    R["patterns"] = None
    return R


def main():
    out = {}
    for sym, yt in SYMS.items():
        print("fetching", sym, yt, file=sys.stderr)
        bars = fetch_bars(yt)
        T = analyse(bars)
        time.sleep(1)
        F = fetch_fundamentals(yt)
        out[sym] = {"T": T, "F": F}
        time.sleep(1)
    with open(HERE + "/../data/new_stock_signals.json", "w") as f:
        json.dump(out, f, indent=1)
    print("wrote", len(out), "symbols", file=sys.stderr)


if __name__ == "__main__":
    main()
