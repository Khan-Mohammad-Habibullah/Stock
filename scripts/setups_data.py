"""Data for "Setups before 15% rises": the stock list and 5+ years of adjusted daily bars.

  * Stock list: the same 7 markets and the same rule as the Strategy tab's screen (TradingView screener, common stocks listed in the
    market and based in that country, one share class per company = the most traded one, the 70 largest by market value).
  * Daily prices and volume: Yahoo Finance chart API, split- AND dividend-adjusted (adjusted close; open/high/low scaled by the same factor).
    This is the data source the rest of the board's rebuild uses on the Actions runner; TradingView offers no public history download.
Runs on a GitHub Actions runner (TradingView and Yahoo are not reachable from the agent's sandbox).
"""
import concurrent.futures
import datetime
import gzip
import json
import re
import sys
import threading
import time
import urllib.parse

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import board_lib as L

MARKETS = [
    dict(k="USA", m="america", c="United States", ex=["NASDAQ", "NYSE", "AMEX"]),
    dict(k="Sweden", m="sweden", c="Sweden", ex=["OMXSTO"]),
    dict(k="Denmark", m="denmark", c="Denmark", ex=["OMXCOP"]),
    dict(k="Germany", m="germany", c="Germany", ex=["XETR"]),
    dict(k="Finland", m="finland", c="Finland", ex=["OMXHEX"]),
    dict(k="Norway", m="norway", c="Norway", ex=["OSL"]),
    dict(k="Canada", m="canada", c="Canada", ex=["TSX"]),
]
N_LARGE, N_TOTAL = 30, 70
COLS = ["name", "description", "exchange", "currency", "close", "volume", "market_cap_basic", "sector", "industry",
        "earnings_release_next_date", "earnings_release_date", "country"]


def base_name(n):
    """Port of the page's baseName(): one row per company."""
    s = str(n or "").lower()
    s = re.sub(r"\(publ\)|\bpubl\b", "", s)
    s = re.sub(r"\b(class|series|ser\.?|shs|shares?|ordinary|common|stock)\b\s*[a-z]?\b", "", s)
    s = re.sub(r"[.,'’()]", " ", s)
    s = re.sub(r"\s+[abc]\s*$", "", s)
    return re.sub(r"\s+", " ", s).strip()


def universe():
    """{market: [row, ...]} with rank (1..70) and size (Large 1-30, Mid 31-70)."""
    out = {}
    for m in MARKETS:
        body = {"filter": [{"left": "type", "operation": "in_range", "right": ["stock"]}, {"left": "typespecs", "operation": "has", "right": ["common"]},
                           {"left": "exchange", "operation": "in_range", "right": m["ex"]}, {"left": "country", "operation": "equal", "right": m["c"]},
                           {"left": "volume", "operation": "greater", "right": 0}],
                "markets": [m["m"]], "sort": {"sortBy": "market_cap_basic", "sortOrder": "desc"}, "range": [0, 150], "columns": COLS}
        j = L.retry(L.http_json, "https://scanner.tradingview.com/%s/scan" % m["m"], body)
        rows = []
        for x in j.get("data") or []:
            d = dict(zip(COLS, x["d"]))
            d["sym"] = x["s"]
            if d.get("close") is None or d.get("market_cap_basic") is None:
                continue
            rows.append(d)
        best = {}
        for d in rows:
            k = base_name(d["description"] or d["name"])
            if k not in best or (d.get("volume") or 0) > (best[k].get("volume") or 0):
                best[k] = d
        keep = sorted(best.values(), key=lambda d: -d["market_cap_basic"])[:N_TOTAL]
        for i, d in enumerate(keep):
            d["rank"] = i + 1
            d["size"] = "Large" if i < N_LARGE else "Mid"
            d["market"] = m["k"]
        out[m["k"]] = keep
    return out


def fetch_adj(yt, years=6):
    """Daily bars adjusted for splits and dividends: (t, o, h, l, c, v) with t = unix seconds of the session."""
    p2 = int(time.time()) + 86400
    p1 = p2 - int(years * 365.25 * 86400)
    j = L.http_json("https://query1.finance.yahoo.com/v8/finance/chart/%s?period1=%d&period2=%d&interval=1d&events=div%%2Csplits&includeAdjustedClose=true" % (urllib.parse.quote(yt), p1, p2))
    res = j["chart"]["result"][0]
    q = res["indicators"]["quote"][0]
    adj = (res["indicators"].get("adjclose") or [{}])[0].get("adjclose")
    B = []
    for i, t in enumerate(res.get("timestamp") or []):
        o, h, l, c, v = q["open"][i], q["high"][i], q["low"][i], q["close"][i], q["volume"][i]
        if None in (o, h, l, c) or c <= 0:
            continue
        f = (adj[i] / c) if (adj and adj[i]) else 1.0
        B.append((t, o * f, h * f, l * f, c * f, v or 0))
    return B, res["meta"].get("currency"), res["meta"].get("exchangeTimezoneName")


def bars_adj(d, years=6):
    last = None
    for yt in L.yahoo_candidates(d["sym"], d.get("country")):
        try:
            B, cur, tz = L.retry(fetch_adj, yt, years)
        except Exception as e:
            last = e
            continue
        if len(B) < 250:
            last = Exception("only %d bars" % len(B))
            continue
        ratio = B[-1][4] / d["close"]
        if not 0.9 < ratio < 1.1:
            last = Exception("%s close %.4g vs screener %.4g" % (yt, B[-1][4], d["close"]))
            continue
        return B, yt, tz
    raise last or Exception("no Yahoo ticker")


def fetch_all(U, years=6, workers=6):
    """-> ({sym: {"bars": [...], "yt": ..., "tz": ...}}, {sym: error})."""
    out, err, lock = {}, {}, threading.Lock()
    items = [d for rows in U.values() for d in rows]

    def one(d):
        try:
            B, yt, tz = bars_adj(d, years)
            with lock:
                out[d["sym"]] = {"bars": B, "yt": yt, "tz": tz}
        except Exception as e:
            with lock:
                err[d["sym"]] = str(e)[:160]
        time.sleep(0.05)

    with concurrent.futures.ThreadPoolExecutor(workers) as ex:
        list(ex.map(one, items))
    return out, err


def dump(path, U, bars, err):
    """Compact gzip JSON: per symbol column arrays; prices rounded to 5 significant digits."""
    r = lambda x: float("%.5g" % x)
    D = {"built": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="minutes"), "universe": U, "errors": err, "bars": {}}
    for s, v in bars.items():
        B = v["bars"]
        D["bars"][s] = {"yt": v["yt"], "tz": v["tz"], "t": [b[0] // 86400 for b in B], "o": [r(b[1]) for b in B], "h": [r(b[2]) for b in B],
                        "l": [r(b[3]) for b in B], "c": [r(b[4]) for b in B], "v": [int(b[5]) for b in B]}
    with gzip.open(path, "wt", encoding="utf-8", compresslevel=9) as f:
        json.dump(D, f, separators=(",", ":"))


def load(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "study_data.json.gz"
    U = universe()
    print({k: len(v) for k, v in U.items()}, flush=True)
    bars, err = fetch_all(U)
    print("bars", len(bars), "errors", len(err), flush=True)
    dump(out, U, bars, err)
