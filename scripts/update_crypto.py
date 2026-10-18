#!/usr/bin/env python3
"""Refresh crypto_holdings.json / crypto_monthly.json from public data only
(TradingView's coin screener plus Binance/Bybit/CoinGecko daily bars) -- no
browser, no login, no Claude. Run on a schedule by
.github/workflows/update-crypto.yml, then baked into index.html by
scripts/bake_crypto.py.

Mirrors the methodology in the original build_crypto.py / build_crypto2.py
(see git history), adapted to run unattended: volatility history is found by
trying Binance, then Bybit, then CoinGecko for each coin in turn, instead of
a human picking the exchange by hand.
"""
import json
import math
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = __file__.rsplit("/", 1)[0]

TICKER_OF = {
    "CRYPTO:BTCUSD": "BTC", "CRYPTO:ETHUSD": "ETH", "CRYPTO:BNBUSD": "BNB", "CRYPTO:SOLUSD": "SOL",
    "CRYPTO:SANDUSD": "SAND", "CRYPTO:HBARUSD": "HBAR", "CRYPTO:CAKEUSD": "CAKE", "CRYPTO:LUNCUSD": "LUNC",
    "CRYPTO:MANAUSD": "MANA", "CRYPTO:KCSUSD": "KCS", "CRYPTO:DOGEUSD": "DOGE", "CRYPTO:XRPUSD": "XRP",
    "CRYPTO:LTCUSD": "LTC", "CRYPTO:POLYGUSD": "POL", "CRYPTO:XLMUSD": "XLM", "CRYPTO:AVAXUSD": "AVAX",
    "CRYPTO:ADAUSD": "ADA", "CRYPTO:ENJUSD": "ENJ", "CRYPTO:HEIUSD": "HEI", "CRYPTO:GMTUSD": "GMT",
    "CRYPTO:SHIBUSD": "SHIB", "CRYPTO:AAVEUSD": "AAVE", "CRYPTO:LINKUSD": "LINK", "CRYPTO:VETUSD": "VET",
    "CRYPTO:DOTUSD": "DOT", "CRYPTO:ALGOUSD": "ALGO", "CRYPTO:XDCUSD": "XDC", "CRYPTO:SUIUSD": "SUI",
    "CRYPTO:ENAUSD": "ENA", "CRYPTO:COTIUSD": "COTI",
}
NAME_OF = {
    "BTC": "Bitcoin", "ETH": "Ethereum", "BNB": "BNB", "SOL": "Solana", "SAND": "The Sandbox",
    "HBAR": "Hedera", "CAKE": "PancakeSwap", "LUNC": "Terra Classic", "MANA": "Decentraland",
    "KCS": "KuCoin Token", "DOGE": "Dogecoin", "XRP": "XRP", "LTC": "Litecoin", "POL": "Polygon",
    "XLM": "Stellar", "AVAX": "Avalanche", "ADA": "Cardano", "ENJ": "Enjin Coin", "HEI": "Heima",
    "GMT": "GMT", "SHIB": "Shiba Inu", "AAVE": "Aave", "LINK": "Chainlink", "VET": "VeChain",
    "DOT": "Polkadot", "ALGO": "Algorand", "XDC": "XDC Network", "SUI": "Sui", "ENA": "Ethena",
    "COTI": "COTI",
}
COLS = ["name", "description", "close", "change", "Perf.1M", "Perf.3M", "Perf.6M", "Perf.Y",
        "RSI", "RSI[1]", "MACD.macd", "MACD.signal", "SMA20", "SMA50", "SMA200",
        "ADX", "ADX+DI", "ADX-DI", "Volatility.D", "Volatility.M",
        "24h_vol_cmc", "market_cap_calc", "price_52_week_high", "price_52_week_low", "Recommend.All"]


def http_json(url, data=None, headers=None, timeout=20):
    hdrs = {"User-Agent": "Mozilla/5.0 (holdings-signal-board update-crypto script)",
            "Accept": "application/json", "Content-Type": "application/json"}
    hdrs.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=hdrs, method="POST" if data else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_scan():
    body = json.dumps({"symbols": {"tickers": list(TICKER_OF.keys())}, "columns": COLS}).encode()
    return http_json("https://scanner.tradingview.com/coin/scan", data=body)


def clip(v, lo, hi):
    return max(lo, min(hi, v))


def bucket5(score, cuts=(3.5, 1.0, -1.0, -3.5), labels=None):
    hi, midhi, midlo, lo = cuts
    if labels is None:
        labels = ["Positive", "Leaning positive", "Mixed", "Leaning negative", "Negative"]
    if score >= hi:
        return labels[0]
    if score >= midhi:
        return labels[1]
    if score > midlo:
        return labels[2]
    if score > lo:
        return labels[3]
    return labels[4]


def build_core(raw):
    rows = []
    for r in raw["data"]:
        d = dict(zip(COLS, r["d"]))
        d["sym"] = r["s"]
        rows.append(d)

    coins = []
    for d in rows:
        t = TICKER_OF[d["sym"]]
        name = NAME_OF[t]
        close = float(d["close"])
        macd, macds = float(d["MACD.macd"]), float(d["MACD.signal"])
        sma50, sma200 = float(d["SMA50"]), float(d["SMA200"])
        rsi = float(d["RSI"])
        adx, adxp, adxm = float(d["ADX"]), float(d["ADX+DI"]), float(d["ADX-DI"])
        p1m, p3m, p6m, py = float(d["Perf.1M"]), float(d["Perf.3M"]), float(d["Perf.6M"]), float(d["Perf.Y"])
        chg = float(d["change"])
        rec = float(d["Recommend.All"])
        hi52, lo52 = float(d["price_52_week_high"]), float(d["price_52_week_low"])
        vol24h = float(d["24h_vol_cmc"] or 0)
        mcap = float(d["market_cap_calc"] or 0)
        volM = float(d["Volatility.M"] or 0)

        sig = 0.0
        sig += 1 if close > sma50 else -1
        sig += 1 if close > sma200 else -1
        sig += 0.5 if sma50 > sma200 else -0.5
        sig += 1 if 50 <= rsi <= 75 else (-1 if rsi < 45 else 0)
        sig += 1 if macd > macds else -1
        sig += 0.5 if p1m > 0 else -0.5
        sig += 0.5 if p3m > 0 else -0.5
        if adx >= 20 and adxp > adxm:
            sig += 1
        elif adx >= 20 and adxm > adxp:
            sig -= 1
        if rec > 0.1:
            sig += 1
        elif rec < -0.1:
            sig -= 1
        sig_label = bucket5(sig, (4, 1.5, -1.5, -4), ["Bullish", "Mildly bullish", "Neutral", "Mildly bearish", "Bearish"])

        mom12_1 = py - p1m
        flow_raw = mom12_1 * 3 + p3m * 1

        out1y = 0.0
        out1y += clip(py / 40, -2, 2)
        out1y += clip((close / sma200 - 1) * 100 / 15, -1.5, 1.5)
        out1y += clip(rec * 3, -1.5, 1.5)
        if close >= hi52 * 0.9:
            out1y += 1
        elif close <= lo52 * 1.1:
            out1y -= 1
        out1y_label = bucket5(out1y)

        coins.append({
            "sym": d["sym"], "ticker": t, "name": name, "cur": "USD",
            "price": close, "day_chg": chg, "r1m": p1m, "r3m": p3m, "r6m": p6m, "r1y": py,
            "rsi": rsi, "macd": "Bullish, rising" if macd > macds else "Bearish, falling",
            "vs50": (close / sma50 - 1) * 100, "vs200": (close / sma200 - 1) * 100,
            "signal_score": round(sig, 2), "signal": sig_label,
            "flow_raw": flow_raw, "volM": volM,
            "o1y_score": round(out1y, 2), "o1y": out1y_label,
            "mcap": mcap, "vol24h": vol24h, "high52w": hi52, "low52w": lo52,
        })

    ranked = sorted(coins, key=lambda c: c["flow_raw"])
    n = len(ranked)
    for i, c in enumerate(ranked):
        pct = i / (n - 1) if n > 1 else 0.5
        if pct >= 0.8:
            c["flow"] = "Strong inflow"
        elif pct >= 0.6:
            c["flow"] = "Money coming in"
        elif pct <= 0.2:
            c["flow"] = "Strong outflow"
        elif pct <= 0.4:
            c["flow"] = "Money leaving"
        else:
            c["flow"] = "No clear direction"
        c["flow_score"] = round((pct - 0.5) * 15, 2)

    coins.sort(key=lambda c: -c["mcap"])
    return coins


_binance_bases = None


def binance_bases():
    global _binance_bases
    if _binance_bases is None:
        info = http_json("https://api.binance.com/api/v3/exchangeInfo")
        _binance_bases = {s["baseAsset"] for s in info["symbols"] if s["quoteAsset"] == "USDT" and s["status"] == "TRADING"}
    return _binance_bases


def closes_binance(ticker):
    if ticker not in binance_bases():
        return None
    data = http_json("https://api.binance.com/api/v3/klines?symbol=%sUSDT&interval=1d&limit=280" % ticker)
    return [float(k[4]) for k in data]


def closes_bybit(ticker):
    data = http_json("https://api.bybit.com/v5/market/kline?category=spot&symbol=%sUSDT&interval=D&limit=280" % ticker)
    rows = data.get("result", {}).get("list") or []
    if not rows:
        return None
    rows = list(reversed(rows))  # bybit returns newest first
    return [float(r[4]) for r in rows]


def closes_coingecko(name):
    try:
        s = http_json("https://api.coingecko.com/api/v3/search?query=" + urllib.parse.quote(name))
        coins = s.get("coins") or []
        if not coins:
            return None
        cid = coins[0]["id"]
        time.sleep(1.5)
        mc = http_json("https://api.coingecko.com/api/v3/coins/%s/market_chart?vs_currency=usd&days=270&interval=daily" % cid)
        prices = mc.get("prices") or []
        return [p[1] for p in prices]
    except Exception:
        return None


def ann_vol_pct(closes):
    if not closes or len(closes) < 30:
        return None
    rets = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes)) if closes[i - 1] > 0 and closes[i] > 0]
    if len(rets) < 20:
        return None
    sd = statistics.pstdev(rets)
    return sd * math.sqrt(365) * 100


def volatility_for(ticker, name):
    for fn, arg in ((closes_binance, ticker), (closes_bybit, ticker), (closes_coingecko, name)):
        try:
            closes = fn(arg)
        except (urllib.error.URLError, urllib.error.HTTPError, Exception) as e:
            print("  %s: %s failed (%s)" % (ticker, fn.__name__, e), file=sys.stderr)
            closes = None
        v = ann_vol_pct(closes)
        if v is not None:
            return v, fn.__name__.replace("closes_", "")
    return None, None


def main():
    today = time.strftime("%Y-%m-%d", time.gmtime())
    raw = fetch_scan()
    if raw.get("totalCount") != len(TICKER_OF):
        print("warning: scanner returned %s rows, expected %d" % (raw.get("totalCount"), len(TICKER_OF)), file=sys.stderr)
    coins = build_core(raw)

    pairs = []
    for c in coins:
        v, src = volatility_for(c["ticker"], c["name"])
        if v is not None:
            c["vol"] = round(min(v, 220.0), 1)
            c["vol_src"] = "history (" + src + ")"
            pairs.append((c["volM"], v))
        print("%-6s vol=%s src=%s" % (c["ticker"], c.get("vol"), c.get("vol_src")))

    k = (sum(y / x for x, y in pairs if x) / len(pairs)) if pairs else 15.0
    for c in coins:
        if "vol" not in c:
            c["vol"] = round(min(c["volM"] * k, 220.0), 1)
            c["vol_src"] = "estimated"
        del c["volM"]

    with open(HERE + "/../data/crypto_holdings.json", "w") as f:
        json.dump(coins, f, separators=(",", ":"))
    print("wrote crypto_holdings.json:", len(coins), "coins")

    # ---- monthly price projections, same lognormal method as the stock board ----
    import datetime
    nd = lambda x: 0.5 * (1 + math.erf(x / math.sqrt(2)))
    base = datetime.date.fromisoformat(today)

    def month_end(y, m):
        ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
        return datetime.date(ny, nm, 1) - datetime.timedelta(days=1)

    M = []
    for c in coins:
        sig = c["vol"] / 100
        px = c["price"]
        drift = max(-10, min(10, 5 + 1.5 * c["o1y_score"])) / 100
        for i in range(13):
            y, mth = base.year + (base.month - 1 + i) // 12, (base.month - 1 + i) % 12 + 1
            d = month_end(y, mth)
            Tm = (d - base).days / 365
            if Tm <= 0:
                continue
            z = 0.6745
            lo, hi = px * math.exp(-z * sig * math.sqrt(Tm)), px * math.exp(z * sig * math.sqrt(Tm))
            mu = drift
            ch = 1 - nd((math.log(hi / px) - mu * Tm) / (sig * math.sqrt(Tm)))
            cl = nd((math.log(lo / px) - mu * Tm) / (sig * math.sqrt(Tm)))
            diff = ch - cl
            dec = 6 if px < 0.01 else 4 if px < 1 else 2
            M.append(dict(
                sym=c["sym"], name=c["name"], cur=c["cur"],
                month="%d-%02d" % (y, mth), date=d.isoformat(),
                likely_low=round(lo, dec), likely_high=round(hi, dec), most_likely=round(px * math.exp(mu * Tm), dec),
                chance_high=round(ch, 3), chance_low=round(cl, 3),
                leans="High" if diff >= 0.03 else "Low" if diff <= -0.03 else "Even",
                drift_pct_yr=round(drift * 100, 1),
            ))

    with open(HERE + "/../data/crypto_monthly.json", "w") as f:
        json.dump(M, f, separators=(",", ":"))
    print("wrote crypto_monthly.json:", len(M), "rows")

    with open(HERE + "/../data/crypto_extracted.txt", "w") as f:
        f.write(today)


if __name__ == "__main__":
    main()
