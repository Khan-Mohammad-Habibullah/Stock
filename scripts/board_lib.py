"""Shared code for the daily stock-board rebuild (scripts/update_board.py).

Data sources (public, no login), reachable from a GitHub Actions runner:
  * TradingView screener (scanner.tradingview.com): company lists per market,
    sector/industry, fundamentals, analyst consensus and target
  * Yahoo Finance chart API: ~2 years of daily bars per symbol, FX rates

Indicator rules follow the board's "How the signals are worked out" section;
the October score is a port of the board's own calc.js.
"""
import concurrent.futures
import datetime
import http.cookiejar
import json
import math
import re
import statistics
import threading
import time
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


# ---------------------------------------------------------------- http
def http_json(url, body=None, timeout=30):
    data = json.dumps(body).encode() if body is not None else None
    hdr = {"User-Agent": UA}
    if body is not None:
        hdr["Content-Type"] = "text/plain;charset=UTF-8"
    req = urllib.request.Request(url, data=data, headers=hdr)
    with _opener.open(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def retry(fn, *a, tries=4, base=1.5):
    for k in range(tries):
        try:
            return fn(*a)
        except urllib.error.HTTPError as e:
            if e.code == 404 or k == tries - 1:
                raise
            time.sleep(base * (k + 1) * (3 if e.code == 429 else 1))
        except Exception:
            if k == tries - 1:
                raise
            time.sleep(base * (k + 1))


def scan(body):
    return http_json("https://scanner.tradingview.com/global/scan", body)


SCAN_COLS = ["name", "description", "exchange", "country", "currency", "type", "sector", "industry", "close", "market_cap_basic",
             "total_revenue_yoy_growth_ttm", "earnings_per_share_diluted_yoy_growth_ttm", "net_margin_ttm", "gross_margin_ttm",
             "price_earnings_ttm", "debt_to_equity", "return_on_equity", "free_cash_flow_ttm", "recommendation_mark", "price_target_average"]


def scan_rows(j):
    out = {}
    for x in j.get("data") or []:
        d = dict(zip(SCAN_COLS, x["d"]))
        d["sym"] = x["s"]
        out[x["s"]] = d
    return out


def scan_symbols(syms):
    out = {}
    syms = list(syms)
    for i in range(0, len(syms), 200):
        out.update(scan_rows(retry(scan, {"symbols": {"tickers": syms[i:i + 200]}, "columns": SCAN_COLS})))
    return out


def scan_universe(countries, exchanges=None, n=200, min_mcap=None, primary=False):
    f = [{"left": "type", "operation": "in_range", "right": ["stock"]},
         {"left": "typespecs", "operation": "has", "right": ["common"]},
         {"left": "country", "operation": "in_range", "right": countries},
         {"left": "volume", "operation": "greater", "right": 0}]
    if exchanges:
        f.append({"left": "exchange", "operation": "in_range", "right": exchanges})
    if min_mcap:
        f.append({"left": "market_cap_basic", "operation": "greater", "right": min_mcap})
    if primary:
        f.append({"left": "is_primary", "operation": "equal", "right": True})
    j = retry(scan, {"filter": f, "columns": SCAN_COLS, "sort": {"sortBy": "market_cap_basic", "sortOrder": "desc"}, "range": [0, n]})
    rows = [r for r in scan_rows(j).values() if r.get("sector") and not re.search(r"\bTEMP(ORARY)?\b", (r.get("description") or "").upper())]
    rows.sort(key=lambda r: -(r.get("market_cap_basic") or 0))
    return rows


# ---------------------------------------------------------------- yahoo
YSUF = {"NASDAQ": "", "NYSE": "", "AMEX": "", "OMXSTO": ".ST", "OSL": ".OL", "OMXCOP": ".CO", "OMXHEX": ".HE", "XETR": ".DE",
        "TSX": ".TO", "LSE": ".L", "SIX": ".SW", "BME": ".MC", "MIL": ".MI", "VIE": ".VI", "OMXICE": ".IC"}
EURONEXT = {"France": ".PA", "Netherlands": ".AS", "Belgium": ".BR", "Portugal": ".LS", "Ireland": ".IR"}


def yahoo_candidates(sym, country=None):
    ex, tk = sym.split(":", 1)
    base = tk.rstrip(".").replace("_", "-").replace(".", "-").replace("/", "-")  # LSE "BP." -> BP.L
    if ex == "EURONEXT":
        first = EURONEXT.get(country)
        sufs = ([first] if first else []) + [s for s in (".PA", ".AS", ".BR", ".LS", ".IR") if s != first]
        return [base + s for s in sufs]
    if ex in YSUF:
        return [base + YSUF[ex]]
    return []


def fetch_bars(yt, rng="2y"):
    j = http_json("https://query1.finance.yahoo.com/v8/finance/chart/%s?range=%s&interval=1d" % (urllib.parse.quote(yt), rng))
    res = j["chart"]["result"][0]
    q = res["indicators"]["quote"][0]
    B = []
    for i, t in enumerate(res.get("timestamp") or []):
        o, h, l, c, v = q["open"][i], q["high"][i], q["low"][i], q["close"][i], q["volume"][i]
        if None in (o, h, l, c) or c <= 0:
            continue
        B.append((t, o, h, l, c, v or 0))
    return B, res["meta"].get("currency")


def bars_for(sym, country=None, check_close=None):
    """Daily bars for a TradingView symbol; tries each plausible Yahoo ticker and,
    when the screener's close is known, keeps the one whose last close agrees."""
    last_err = None
    for yt in yahoo_candidates(sym, country):
        try:
            B, cur = retry(fetch_bars, yt)
        except Exception as e:
            last_err = e
            continue
        if len(B) < 30:
            last_err = Exception("only %d bars" % len(B))
            continue
        if check_close:
            ratio = B[-1][4] / check_close
            if not 0.9 < ratio < 1.1:
                last_err = Exception("%s close %.4g vs screener %.4g" % (yt, B[-1][4], check_close))
                continue
        return B, cur, yt
    raise last_err or Exception("no Yahoo ticker for " + sym)


def fetch_many(items, workers=6):
    """items: list of (sym, country, check_close). Returns {sym: (bars, cur, yt)} and {sym: error}."""
    out, err = {}, {}
    lock = threading.Lock()

    def one(it):
        sym, country, chk = it
        try:
            res = bars_for(sym, country, chk)
            with lock:
                out[sym] = res
        except Exception as e:
            with lock:
                err[sym] = str(e)[:160]
        time.sleep(0.05)

    with concurrent.futures.ThreadPoolExecutor(workers) as ex:
        list(ex.map(one, items))
    return out, err


FX_CODES = ["USD", "SEK", "EUR", "NOK", "DKK", "CAD", "GBP", "CHF", "ISK", "PLN", "JPY"]


def fx_to_usd():
    """USD per one unit of each currency (GBp handled by callers)."""
    rates = {"USD": 1.0}
    for c in FX_CODES[1:]:
        try:
            B, _ = retry(fetch_bars, "%sUSD=X" % c, "5d")
            rates[c] = B[-1][4]
        except Exception:
            pass
    return rates


def usd_per(cur, rates):
    if cur in ("GBp", "GBX"):
        return rates["GBP"] / 100
    if cur == "ILA":
        return rates.get("ILS", 0.27) / 100
    return rates[cur]


# ---------------------------------------------------------------- helpers
def sma(a, n, i):
    return sum(a[i - n + 1:i + 1]) / n


def ema(a, n):
    k = 2 / (n + 1)
    o = [a[0]]
    for i in range(1, len(a)):
        o.append(a[i] * k + o[-1] * (1 - k))
    return o


def wilder(a, n):
    o, s = [], 0.0
    for i in range(len(a)):
        if i < n - 1:
            o.append(float("nan")); continue
        if i == n - 1:
            s = sum(a[:n]); o.append(s / n); continue
        o.append((o[i - 1] * (n - 1) + a[i]) / n)
    return o


def rsi_arr(c, n=14):
    g, l = [0.0], [0.0]
    for i in range(1, len(c)):
        d = c[i] - c[i - 1]
        g.append(max(d, 0)); l.append(max(-d, 0))
    ag, al = wilder(g[1:], n), wilder(l[1:], n)
    o = [float("nan")]
    for i in range(len(ag)):
        o.append(100.0 if al[i] == 0 else 100 - 100 / (1 + ag[i] / al[i]))
    return o


def r2(x, d=1):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return None
    return round(x, d)


def cl(x, a, b=None):
    if b is None:
        a, b = -a, a
    return max(a, min(b, x))


# ---------------------------------------------------------------- candlesticks
def candle(B, i):
    o, h, l, c = B[i][1], B[i][2], B[i][3], B[i][4]
    body = abs(c - o); rng = (h - l) or 1e-9
    up = h - max(o, c); lo = min(o, c) - l
    po, pc = B[i - 1][1], B[i - 1][4]
    pb = abs(pc - po)
    prior_up = B[i - 1][4] > B[max(0, i - 6)][4]   # short trend into the candle
    out = []
    bull = lambda x: x[4] > x[1]
    bear = lambda x: x[4] < x[1]
    if i >= 2:
        b = [B[i - 2], B[i - 1], B[i]]
        if all(bull(x) for x in b) and b[1][4] > b[0][4] and b[2][4] > b[1][4] and b[1][1] > b[0][1] and b[2][1] > b[1][1]:
            out.append(("three white soldiers (bullish)", 1))
        if all(bear(x) for x in b) and b[1][4] < b[0][4] and b[2][4] < b[1][4] and b[1][1] < b[0][1] and b[2][1] < b[1][1]:
            out.append(("three black crows (bearish)", -1))
        r0 = (b[0][2] - b[0][3]) or 1e-9
        b0 = abs(b[0][4] - b[0][1]); b1 = abs(b[1][4] - b[1][1])
        if bear(b[0]) and b0 > r0 * 0.4 and b1 < b0 * 0.4 and bull(b[2]) and b[2][4] > (b[0][1] + b[0][4]) / 2:
            out.append(("morning star (bullish)", 1))
        if bull(b[0]) and b0 > r0 * 0.4 and b1 < b0 * 0.4 and bear(b[2]) and b[2][4] < (b[0][1] + b[0][4]) / 2:
            out.append(("evening star (bearish)", -1))
    if c > o and pc < po and c >= po and o <= pc and body > pb:
        out.append(("bullish engulfing", 1))
    elif c < o and pc > po and c <= po and o >= pc and body > pb:
        out.append(("bearish engulfing", -1))
    elif pb > 0 and body < pb * 0.5 and max(o, c) < max(po, pc) and min(o, c) > min(po, pc):
        if pc < po and c > o:
            out.append(("bullish harami", 1))
        elif pc > po and c < o:
            out.append(("bearish harami", -1))
    if body >= rng * 0.9:
        out.append(("bullish marubozu", 1) if c > o else ("bearish marubozu", -1))
    if body > 0 and body / rng > 0.1:
        if lo >= 2 * body and up <= body * 0.5:
            out.append(("hanging man (bearish)", -1) if prior_up else ("hammer (bullish)", 1))
        if up >= 2 * body and lo <= body * 0.5:
            out.append(("shooting star (bearish)", -1) if prior_up else ("inverted hammer (bullish)", 1))
    if body <= rng * 0.1:
        out.append(("doji", 0))
    return out


def recent_candles(B, days=3):
    """Patterns at the most recent of the last `days` bars that has any (as on the board: names, comma-separated)."""
    for i in range(len(B) - 1, len(B) - 1 - days, -1):
        p = candle(B, i)
        if p:
            return p
    return []


def weekly(B):
    W, cur = [], None
    for b in B:
        dt = datetime.datetime.utcfromtimestamp(b[0])
        key = (dt - datetime.timedelta(days=dt.weekday())).date()
        if cur is None or cur[0] != key:
            cur = [key, b[1], b[2], b[3], b[4], b[5]]
            W.append(cur)
        else:
            cur[2] = max(cur[2], b[2]); cur[3] = min(cur[3], b[3]); cur[4] = b[4]; cur[5] += b[5]
    return [(0, w[1], w[2], w[3], w[4], w[5]) for w in W]


MON3 = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


# ---------------------------------------------------------------- indicators
def analyse(B):
    """Every technical field of an "Every holding" row, from daily bars (oldest first)."""
    t = [b[0] for b in B]; o_ = [b[1] for b in B]; h = [b[2] for b in B]; l = [b[3] for b in B]; c = [b[4] for b in B]; v = [b[5] for b in B]
    n = len(c) - 1
    R = {}
    R["price"] = c[n]
    R["r1m"] = r2((c[n] / c[n - 21] - 1) * 100)
    R["r3m"] = r2((c[n] / c[n - 63] - 1) * 100)
    R["r12m"] = r2((c[n] / c[max(0, n - 252)] - 1) * 100)
    R["r126"] = (c[n] / c[max(0, n - 126)] - 1) * 100
    rs = rsi_arr(c)
    R["rsi"] = r2(rs[n])
    e12, e26 = ema(c, 12), ema(c, 26)
    m = [e12[i] - e26[i] for i in range(len(e12))]
    sg = ema(m, 9)
    hist = [m[i] - sg[i] for i in range(len(m))]
    mUp = m[n] > sg[n]; rising = hist[n] > hist[n - 1]
    R["macd"] = ("Bullish, rising" if rising else "Bullish, fading") if mUp else ("Bearish, improving" if rising else "Bearish, falling")
    s20, s50 = sma(c, 20, n), sma(c, 50, n)
    s200 = sma(c, 200, n) if n >= 199 else None
    R["vs20"] = r2((c[n] / s20 - 1) * 100)
    R["vs50"] = r2((c[n] / s50 - 1) * 100)
    R["vs200"] = r2((c[n] / s200 - 1) * 100) if s200 else None
    cross = None
    if n >= 201:
        for i in range(n, 200, -1):
            a = sma(c, 50, i) - sma(c, 200, i); b = sma(c, 50, i - 1) - sma(c, 200, i - 1)
            if a > 0 and b <= 0:
                cross = "golden " + datetime.datetime.utcfromtimestamp(t[i]).strftime("%Y-%m-%d"); break
            if a < 0 and b >= 0:
                cross = "death " + datetime.datetime.utcfromtimestamp(t[i]).strftime("%Y-%m-%d"); break
    R["ma_cross"] = cross

    def sd(k):
        mm = sma(c, 20, k)
        return math.sqrt(sum((c[j] - mm) ** 2 for j in range(k - 19, k + 1)) / 20)

    up_b, lo_b = s20 + 2 * sd(n), s20 - 2 * sd(n)
    R["pctb"] = r2((c[n] - lo_b) / (up_b - lo_b), 2) if up_b > lo_b else 0.5
    bw = [4 * sd(k) / sma(c, 20, k) for k in range(max(20, n - 125), n + 1)]
    rank = len([x for x in bw if x <= bw[-1]]) / len(bw)
    squeeze = rank <= 0.2
    R["bollinger"] = ("Above upper band" if c[n] > up_b else "Below lower band" if c[n] < lo_b else "Squeeze" if squeeze else
                      "Near upper band" if R["pctb"] >= 0.8 else "Near lower band" if R["pctb"] <= 0.2 else "Mid band")
    med = [(h[i] + l[i]) / 2 for i in range(n + 1)]
    jaw, teeth, lips = wilder(med, 13), wilder(med, 8), wilder(med, 5)
    J, Tt, Lp = jaw[n - 8], teeth[n - 5], lips[n - 3]
    if (max(J, Tt, Lp) - min(J, Tt, Lp)) / c[n] < 0.01:
        R["alligator"] = "Sleeping"           # lines tangled within 1% of the price
    else:
        R["alligator"] = "Bullish" if Lp > Tt > J else "Bearish" if Lp < Tt < J else "Waking/mixed"
    # this month's CPR from last month's high, low and close
    d = datetime.datetime.utcfromtimestamp(t[n])
    pm_y, pm_m = (d.year - 1, 12) if d.month == 1 else (d.year, d.month - 1)
    pm = [i for i in range(n + 1) if (lambda x: (x.year, x.month))(datetime.datetime.utcfromtimestamp(t[i])) == (pm_y, pm_m)]
    PH, PL, PC = max(h[i] for i in pm), min(l[i] for i in pm), c[pm[-1]]
    P, BC = (PH + PL + PC) / 3, (PH + PL) / 2
    TC = 2 * P - BC
    top, bot = max(TC, BC), min(TC, BC)
    R["cpr"] = "Above" if c[n] > top else "Below" if c[n] < bot else "Inside"
    R["cpr_tc"], R["cpr_bc"] = r2(top, 2), r2(bot, 2)
    R["cpr_r1"], R["cpr_s1"] = r2(2 * P - PL, 2), r2(2 * P - PH, 2)
    R["_mon"] = MON3[d.month - 1]
    R["_date"] = d.strftime("%Y-%m-%d")

    def mf(k, length):
        a = b = 0.0
        for j in range(k - length + 1, k + 1):
            rr = h[j] - l[j]
            a += (((c[j] - l[j]) - (h[j] - c[j])) / rr if rr > 0 else 0) * v[j]; b += v[j]
        return a / b if b else 0.0

    R["cmf"] = r2(mf(n, 20), 2)
    R["cmf60"] = r2(mf(n, 60), 3)

    def udv(length):
        u = dn = 0.0
        for j in range(n - length + 1, n + 1):
            if c[j] > c[j - 1]: u += v[j]
            elif c[j] < c[j - 1]: dn += v[j]
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
        pdm.append(u if (u > dd and u > 0) else 0); ndm.append(dd if (dd > u and dd > 0) else 0)
    atr, pdi, ndi = wilder(tr[1:], 14), wilder(pdm[1:], 14), wilder(ndm[1:], 14)
    dx = []
    for i in range(len(atr)):
        if atr[i] and not math.isnan(atr[i]):
            p_, q_ = 100 * pdi[i] / atr[i], 100 * ndi[i] / atr[i]
            if p_ + q_:
                dx.append(100 * abs(p_ - q_) / (p_ + q_))
    adx = wilder(dx, 14)
    R["adx"] = r2(adx[-1]) if adx else None
    cd = recent_candles(B, 3)
    R["candles"] = ", ".join(x[0] for x in cd) if cd else None
    W = weekly(B)
    cw = recent_candles(W, 1) if len(W) > 3 else []
    R["candles_w"] = ", ".join(x[0] for x in cw if x[1] != 0) or None
    wc = [x[4] for x in W]; wn = len(wc) - 1
    R["w_rsi"] = r2(rsi_arr(wc)[wn])
    if wn >= 44:
        s40, s40p = sma(wc, 40, wn), sma(wc, 40, wn - 4)
        R["vs40w"] = r2((wc[wn] / s40 - 1) * 100); R["w40_rising"] = s40 > s40p
    else:
        R["vs40w"], R["w40_rising"] = None, None
    we12, we26 = ema(wc, 12), ema(wc, 26)
    wm = [we12[i] - we26[i] for i in range(len(wc))]
    R["w_macd_up"] = wm[wn] > ema(wm, 9)[wn]
    lb = min(n, 251)
    R["off_high"] = r2((c[n] / max(h[n - lb:n + 1]) - 1) * 100)
    lr = [math.log(c[i] / c[i - 1]) for i in range(n - lb + 1, n + 1)]
    mu = sum(lr) / len(lr)
    R["vol"] = r2(math.sqrt(sum((x - mu) ** 2 for x in lr) / (len(lr) - 1)) * math.sqrt(252) * 100)
    R["vol_days"] = len(lr)
    # swing structure (3-bar fractals)
    sh, sl = [], []
    for i in range(3, n - 2):
        if h[i] == max(h[i - 3:min(n + 1, i + 4)]): sh.append((i, h[i]))
        if l[i] == min(l[i - 3:min(n + 1, i + 4)]): sl.append((i, l[i]))
    s1, s2 = sh[-2:], sl[-2:]
    hh = len(s1) == 2 and s1[1][1] > s1[0][1]
    hl = len(s2) == 2 and s2[1][1] > s2[0][1]
    two = len(s1) == 2 and len(s2) == 2
    lastSH = s1[-1][1] if s1 else None
    lastSL = s2[-1][1] if s2 else None
    brk_high = lastSH is not None and c[n] > lastSH
    brk_low = lastSL is not None and c[n] < lastSL
    R["structure"] = ("Broke above last swing high" if brk_high else "Broke below last swing low" if brk_low else
                      "Higher highs & higher lows" if (hh and hl) else "Lower highs & lower lows" if (two and not hh and not hl) else
                      "Higher highs, lower lows (broadening)" if hh else "Higher lows, lower highs (squeeze)")
    prevHi, prevLo = max(h[n - 55:n]), min(l[n - 55:n])
    b55 = 1 if c[n] > prevHi else (-1 if c[n] < prevLo else 0)
    # chart patterns
    pats = []
    if b55 == 1: pats.append("55-day breakout")
    if b55 == -1: pats.append("55-day breakdown")
    if squeeze: pats.append("Bollinger squeeze (coiling)")
    for i in range(n, n - 5, -1):
        g = (o_[i] / c[i - 1] - 1) * 100
        if abs(g) >= 3:
            pats.append("gap %s %d%%" % ("up" if g > 0 else "down", round(g)))
            break
    win_l = [x for x in sl if x[0] >= n - 80]
    win_h = [x for x in sh if x[0] >= n - 80]
    if len(win_l) >= 2:
        (i1, a1), (i2, a2) = win_l[-2], win_l[-1]
        if abs(a2 / a1 - 1) <= 0.03 and i2 - i1 >= 10:
            neck = max(h[i1:i2 + 1])
            pats.append("double bottom (confirmed)" if c[n] > neck else "possible double bottom")
    if len(win_h) >= 2:
        (i1, a1), (i2, a2) = win_h[-2], win_h[-1]
        if abs(a2 / a1 - 1) <= 0.03 and i2 - i1 >= 10:
            neck = min(l[i1:i2 + 1])
            pats.append("double top (confirmed)" if c[n] < neck else "possible double top")
    if lastSL and 0 <= c[n] / lastSL - 1 <= 0.03: pats.append("sitting on support")
    if lastSH and 0 <= 1 - c[n] / lastSH <= 0.03: pats.append("just below resistance")
    R["patterns"] = ", ".join(pats) or None
    # October-style score (the board's documented rules; port of calc.js)
    sc, why = 0.0, []
    rsiN = R["rsi"]
    if 55 <= rsiN <= 75: sc += 1; why.append("RSI strong")
    elif rsiN > 75: why.append("RSI overbought")
    elif rsiN < 45: sc -= 1; why.append("RSI oversold" if rsiN < 30 else "RSI weak")
    if mUp and rising: sc += 1; why.append("MACD bullish & rising")
    elif (not mUp) and (not rising): sc -= 1; why.append("MACD bearish & falling")
    else: why.append("MACD bullish but fading" if mUp else "MACD bearish but improving")
    if c[n] > s20 and c[n] > s50: sc += 1; why.append("above 20/50-day")
    elif c[n] < s20 and c[n] < s50: sc -= 1; why.append("below 20/50-day")
    if R["alligator"] == "Bullish": sc += 1
    elif R["alligator"] == "Bearish": sc -= 1
    if R["cpr"] == "Above": sc += 1; why.append("above %s CPR" % R["_mon"])
    elif R["cpr"] == "Below": sc -= 1; why.append("below %s CPR" % R["_mon"])
    if (R["cmf"] or 0) > 0.05 and (R["udv"] or 0) > 1.1: sc += 1; why.append("buying volume")
    elif (R["cmf"] or 0) < -0.05 and (R["udv"] or 99) < 0.9: sc -= 1; why.append("selling volume")
    if hh and hl: sc += 1; why.append("higher highs/lows")
    elif two and not hh and not hl: sc -= 1; why.append("lower highs/lows")
    if brk_high: why.append("broke above swing high")
    if brk_low: why.append("broke below swing low")
    if b55 == 1: sc += 1; why.append("55-day breakout")
    elif b55 == -1: sc -= 1; why.append("55-day breakdown")
    if R["pctb"] >= 0.95 or R["bollinger"] == "Above upper band": sc += 0.5
    elif R["pctb"] <= 0.05 or R["bollinger"] == "Below lower band": sc -= 0.5
    if cd:
        best = next((x for x in cd if x[1] != 0), None)
        if best: sc += 0.5 * best[1]
    R["oct_score"] = sc
    R["oct_signal"] = "Bullish" if sc >= 4 else "Mildly bullish" if sc >= 1.5 else "Neutral" if sc > -1.5 else "Mildly bearish" if sc > -4 else "Bearish"
    R["oct_why"] = "; ".join(why)
    return R


# ---------------------------------------------------------------- money flow (stock and sector)
def flow_metrics(B, usd_per_unit):
    """The inputs of the board's money-flow readings, from daily bars."""
    n = len(B)
    c = [b[4] for b in B]; h = [b[2] for b in B]; l = [b[3] for b in B]; v = [b[5] for b in B]
    if n < 115:
        return None
    m = {"nbars": n, "last": datetime.datetime.utcfromtimestamp(B[-1][0]).strftime("%Y-%m-%d"), "has": n >= 253}
    m["mom"] = (c[-22] / c[-253] - 1) if m["has"] else None
    m["r1m"] = c[-1] / c[-22] - 1
    m["r3m"] = c[-1] / c[-64] - 1
    up = dn = 0
    for j in range(n - 60, n):
        avg50 = sum(v[j - 50:j]) / 50
        if avg50 > 0 and v[j] > avg50:
            rng = h[j] - l[j]
            pos = (c[j] - l[j]) / rng if rng > 0 else 0.5
            if pos > 0.5: up += 1
            elif pos < 0.5: dn += 1
    m["up"], m["dn"], m["acc"] = up, dn, up - dn
    a = b = 0.0
    for j in range(n - 20, n):
        rng = h[j] - l[j]
        a += (((c[j] - l[j]) - (h[j] - c[j])) / rng if rng > 0 else 0) * v[j]; b += v[j]
    m["cmf20"] = a / b if b else 0.0
    m["above50"] = c[-1] > sum(c[-50:]) / 50
    m["tv_usd_m"] = sum(c[j] * v[j] for j in range(n - 20, n)) / 20 * usd_per_unit / 1e6
    v60 = sum(v[-60:]) / 60
    m["vratio"] = (sum(v[-20:]) / 20) / v60 if v60 else 1.0
    return m


def pr(vals):
    n = len(vals)
    if n < 2:
        return [0.5] * n
    s = sorted(vals)
    import bisect
    return [(bisect.bisect_left(s, x) + (bisect.bisect_right(s, x) - bisect.bisect_left(s, x) - 1) / 2) / (n - 1) for x in vals]


def pr_against(x, sorted_vals):
    import bisect
    n = len(sorted_vals)
    lo, hi = bisect.bisect_left(sorted_vals, x), bisect.bisect_right(sorted_vals, x)
    return (lo + (hi - lo) / 2) / n if n else 0.5


def rank_q(comp):
    order = sorted(range(len(comp)), key=lambda i: comp[i])
    q = [0.0] * len(comp)
    for r, i in enumerate(order):
        q[i] = (r + 0.5) / len(comp)
    return q


def sector_label(Q):
    if Q >= 5 / 6: return "Strong inflow"
    if Q >= 2 / 3: return "Money coming in"
    if Q <= 1 / 6: return "Strong outflow"
    if Q <= 1 / 3: return "Money leaving"
    return "No clear direction"


def stock_label(P, tv_msek):
    if P >= 0.9: return "Strong inflow" if tv_msek >= 20 else "Money coming in"
    if P >= 0.8: return "Money coming in"
    if P <= 0.1: return "Strong outflow" if tv_msek >= 20 else "Money leaving"
    if P <= 0.2: return "Money leaving"
    return "No clear direction"


def score_label(sc):  # ETF look-through, same cut points as the stock scale
    if sc >= 6: return "Strong inflow"
    if sc >= 4.5: return "Money coming in"
    if sc <= -6: return "Strong outflow"
    if sc <= -4.5: return "Money leaving"
    return "No clear direction"


def liquidity(t):
    return "Institutional size" if t >= 100 else "Mid size" if t >= 20 else "Small" if t >= 1 else "Thin"


# ---------------------------------------------------------------- outlook model features
# Inputs as documented on the board; the weights are calibrated on the board's
# original rows (scripts/fit_outlook_model.py) and stored in data/outlook_model.json.
REC = {"Strong buy": 2, "Buy": 1, "Hold": 0, None: 0}


def _g(x, k):
    v = x.get(k)
    return 0.0 if v is None else float(v)


def feat1(x):
    up = _g(x, "vs40w") > 0; rising = bool(x.get("w40_rising"))
    nof = x.get("is_etf") or x.get("nofund")
    return [int(up and rising), int(up and not rising), int(not up and rising),
            cl(_g(x, "vs40w"), -40, 40) / 10, _g(x, "rel6") / 10, cl(_g(x, "oct_score"), -8, 8) / 4,
            (_g(x, "off_high") / 10 if _g(x, "off_high") <= -50 else 0),
            0 if nof else cl(_g(x, "rev_g"), -30, 40) / 10, 0 if nof else cl(_g(x, "eps_g"), -100, 100) / 50,
            REC[x.get("analysts")], (cl(_g(x, "upside"), -20, 100) / 10 if x.get("upside") is not None else 0),
            int(x.get("upside") is not None and x["upside"] <= 0), (cl(_g(x, "w_rsi"), 20, 80) - 50) / 10]


def feat3(x):
    pe = x.get("pe")
    return [cl(_g(x, "rev_g"), -30, 40) / 10, cl(_g(x, "eps_g"), -100, 100) / 50, cl(_g(x, "margin"), -30, 40) / 10, int(bool(x.get("burn"))),
            cl(_g(x, "roe"), -30, 40) / 10, int(x.get("de") is not None and x["de"] >= 2), int(pe is not None and 0 < pe <= 18), int(pe is not None and pe > 40),
            int(_g(x, "margin") < 0), cl(_g(x, "vs40w"), -40, 40) / 20, REC[x.get("analysts")] / 2]


def feat5(x):
    pe = x.get("pe")
    return [cl(_g(x, "margin"), -30, 40) / 10, cl(_g(x, "roe"), -30, 40) / 10, int(_g(x, "rev_g") >= 0), cl(_g(x, "rev_g"), -30, 40) / 10, int(bool(x.get("burn"))),
            int(x.get("de") is not None and x["de"] >= 2), int(bool(x.get("big"))), int(bool(x.get("small"))), int(pe is not None and pe > 40), int(_g(x, "margin") < 0)]


def lt_label(s):
    return "Positive" if s >= 3.5 else "Leaning positive" if s >= 1 else "Mixed" if s > -1 else "Leaning negative" if s > -3.5 else "Negative"


def apply_model(coef, feats):
    return float(sum(a * b for a, b in zip(coef[:-1], feats)) + coef[-1])
