#!/usr/bin/env python3
"""Sector money-flow readings for Denmark, Finland, Germany and Canada, so
"Where money is moving" covers the same markets as "Strongest bullish
readings by market".

Runs on a GitHub Actions runner (normal internet), because TradingView and
Yahoo are not reachable from the agent's sandboxed shell.

Method -- the one the board's "How it works" section documents and the
existing US/Sweden/Norway/Europe/Canada readings use:
  * universe: each market's largest common stocks by market cap (TradingView
    screener), one share class per company (the most traded)
  * per stock, from ~2 years of daily bars (Yahoo Finance chart API):
      - 12-month trend with the last month left out: close 21 sessions ago /
        close 252 sessions ago - 1, minus the market's median ("mom_rel")
      - heavy-volume buying over the last 60 sessions: days when volume beat
        its 50-day average and the close was in the upper half of the day's
        range, minus those with the close in the lower half
      - 20-day Chaikin money flow
      - stock reading: rank of (3 parts trend + 1 part heavy-volume buying +
        1 part Chaikin money flow) within the market -> P in (0, 1)
  * per sector (and industry with >= 4 companies): mean of its companies'
    trend (3 parts) and of their heavy-volume buying rank (1 part), ranked
    against the other sectors of the same market -> Q = (rank + 0.5) / n,
    score = (Q - 0.5) * 15, top/bottom sixth = strong inflow/outflow,
    top/bottom third = money coming in/leaving.

Writes data/market_flows.json. Per-symbol failures are recorded in the
output file (not just the log) so they can be inspected after the run.
"""
import datetime
import http.cookiejar
import json
import re
import statistics
import sys
import time
import urllib.request

OUT = "data/market_flows.json"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

MARKETS = [
    dict(k="Denmark", c="Denmark", ex=["OMXCOP"], cur="DKK", ysuf=".CO", n=70),
    dict(k="Finland", c="Finland", ex=["OMXHEX"], cur="EUR", ysuf=".HE", n=80),
    dict(k="Germany", c="Germany", ex=["XETR"], cur="EUR", ysuf=".DE", n=110),
    dict(k="Canada", c="Canada", ex=["TSX"], cur="CAD", ysuf=".TO", n=130),
]
MIN_SECTOR = 3        # same floor as the thinnest existing sector rows
MIN_INDUSTRY = 4      # "at least four companies share it" (Sweden/Norway rule)
MOST_TRADED = 10      # pick candidates: a sector's most-traded companies
EXTRA_SYMS = ["TSX:WCP"]  # holdings whose sector/industry the bake step needs
FX_TICKERS = {"DKK": "DKKUSD=X", "EUR": "EURUSD=X", "CAD": "CADUSD=X"}


def http_json(url, body=None, timeout=25):
    data = json.dumps(body).encode() if body is not None else None
    hdr = {"User-Agent": UA}
    if body is not None:
        hdr["Content-Type"] = "text/plain;charset=UTF-8"
    req = urllib.request.Request(url, data=data, headers=hdr)
    with _opener.open(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def retry(fn, *a, tries=3):
    for k in range(tries):
        try:
            return fn(*a)
        except Exception:
            if k == tries - 1:
                raise
            time.sleep(1.5 * (k + 1))


def scan(body):
    return http_json("https://scanner.tradingview.com/global/scan", body)


def universe(m):
    j = scan({
        "filter": [{"left": "type", "operation": "in_range", "right": ["stock"]},
                   {"left": "typespecs", "operation": "has", "right": ["common"]},
                   {"left": "exchange", "operation": "in_range", "right": m["ex"]},
                   {"left": "country", "operation": "equal", "right": m["c"]},
                   {"left": "volume", "operation": "greater", "right": 0}],
        "columns": ["name", "description", "sector", "industry", "market_cap_basic", "currency"],
        "sort": {"sortBy": "market_cap_basic", "sortOrder": "desc"},
        "range": [0, m["n"]],
    })
    out = []
    for x in j.get("data") or []:
        tk, nm, sec, ind, mc, cur = x["d"]
        if not sec or re.search(r"\bTEMP(ORARY)?\b", (nm or "").upper()):
            continue  # temporary tender/rights lines duplicate a company already in the list
        out.append(dict(sym=x["s"], tk=tk, name=nm or tk, sector=sec, industry=ind or "", mcap=mc, cur=cur))
    return out


def yticker(tk, suf):
    return tk.replace("_", "-").replace(".", "-") + suf


def fetch_bars(yt):
    j = http_json("https://query1.finance.yahoo.com/v8/finance/chart/%s?range=2y&interval=1d" % yt)
    res = j["chart"]["result"][0]
    q = res["indicators"]["quote"][0]
    B = []
    for i, t in enumerate(res.get("timestamp") or []):
        o, h, l, c, v = q["open"][i], q["high"][i], q["low"][i], q["close"][i], q["volume"][i]
        if None in (o, h, l, c, v) or c <= 0:
            continue
        B.append((t, o, h, l, c, v))
    return B


def fx_to_usd(cur):
    if cur == "USD":
        return 1.0
    j = http_json("https://query1.finance.yahoo.com/v8/finance/chart/%s?range=5d&interval=1d" % FX_TICKERS[cur])
    closes = [c for c in j["chart"]["result"][0]["indicators"]["quote"][0]["close"] if c]
    return closes[-1]


def stock_metrics(B, fx):
    n = len(B)
    c = [b[4] for b in B]; h = [b[2] for b in B]; l = [b[3] for b in B]; v = [b[5] for b in B]
    if n < 115:
        return None
    m = {"nbars": n, "last": datetime.datetime.utcfromtimestamp(B[-1][0]).strftime("%Y-%m-%d")}
    m["has"] = n >= 253
    m["mom"] = (c[-22] / c[-253] - 1) if m["has"] else None
    m["r1m"] = c[-1] / c[-22] - 1
    m["r3m"] = c[-1] / c[-64] - 1
    up = dn = 0
    for j in range(n - 60, n):
        avg50 = sum(v[j - 50:j]) / 50
        if avg50 > 0 and v[j] > avg50:
            rng = h[j] - l[j]
            pos = (c[j] - l[j]) / rng if rng > 0 else 0.5
            if pos > 0.5:
                up += 1
            elif pos < 0.5:
                dn += 1
    m["up"], m["dn"], m["acc"] = up, dn, up - dn
    a = b = 0.0
    for j in range(n - 20, n):
        rng = h[j] - l[j]
        mfm = ((c[j] - l[j]) - (h[j] - c[j])) / rng if rng > 0 else 0
        a += mfm * v[j]; b += v[j]
    m["cmf20"] = a / b if b else 0.0
    m["above50"] = c[-1] > sum(c[-50:]) / 50
    m["tv_usd_m"] = sum(c[j] * v[j] for j in range(n - 20, n)) / 20 * fx / 1e6
    v60 = sum(v[-60:]) / 60
    m["vratio"] = (sum(v[-20:]) / 20) / v60 if v60 else 1.0
    return m


def pr(vals):
    """Percentile rank in [0, 1], ties averaged."""
    n = len(vals)
    if n < 2:
        return [0.5] * n
    out = []
    for x in vals:
        lo = sum(1 for y in vals if y < x)
        eq = sum(1 for y in vals if y == x)
        out.append((lo + (eq - 1) / 2) / (n - 1))
    return out


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


def r1(x, d=1):
    return None if x is None else round(x, d)


def build_market(m, usdsek, errors):
    U = universe(m)
    fx = fx_to_usd(m["cur"])
    rows = []
    for s in U:
        yt = yticker(s["tk"], m["ysuf"])
        try:
            B = retry(fetch_bars, yt)
            met = stock_metrics(B, fx)
            if met is None:
                errors.append("%s (%s): only %d bars" % (s["sym"], yt, len(B)))
                continue
            if (datetime.datetime.utcnow() - datetime.datetime.strptime(met["last"], "%Y-%m-%d")).days > 10:
                errors.append("%s (%s): stale, last bar %s" % (s["sym"], yt, met["last"]))
                continue
            s.update(met); s["yt"] = yt
            rows.append(s)
        except Exception as e:
            errors.append("%s (%s): %s" % (s["sym"], yt, str(e)[:120]))
        time.sleep(0.15)
    # one share class per company: keep the most traded
    base = lambda nm: nm.replace(" Class A", "").replace(" Class B", "").replace(" Class C", "").replace(" Class R", "").replace(" Class K", "").strip()
    best = {}
    for s in rows:
        k = base(s["name"])
        if k not in best or s["tv_usd_m"] > best[k]["tv_usd_m"]:
            best[k] = s
    S = list(best.values())
    H = [s for s in S if s["has"]]
    med_mom = statistics.median(s["mom"] for s in H)
    med_r1 = statistics.median(s["r1m"] for s in S)
    med_r3 = statistics.median(s["r3m"] for s in S)
    for s in S:
        s["mom_rel"] = (s["mom"] - med_mom) * 100 if s["has"] else None
    acc_p = pr([s["acc"] for s in S])
    for s, p in zip(S, acc_p):
        s["acc_pct"] = p * 100
    # stock reading: trend 3 parts, heavy-volume buying 1, Chaikin money flow 1
    a, b, c = pr([s["mom_rel"] for s in H]), pr([s["acc"] for s in H]), pr([s["cmf20"] for s in H])
    P = rank_q([0.6 * x + 0.2 * y + 0.2 * z for x, y, z in zip(a, b, c)])
    for s, p in zip(H, P):
        s["P"] = p
    total_tv = sum(s["tv_usd_m"] for s in S)

    def groups(level, min_n):
        key = "sector" if level == "sector" else "industry"
        g = {}
        for s in S:
            if s[key]:
                g.setdefault(s[key], []).append(s)
        out = []
        for name, L in g.items():
            Lh = [s for s in L if s["has"]]
            if len(Lh) < min_n:
                continue
            tv = sum(s["tv_usd_m"] for s in L)
            top = sorted(L, key=lambda s: -s["tv_usd_m"])[:3]
            out.append(dict(market=m["k"], level=level, group=name, sector=L[0]["sector"], n=len(L),
                            r1m=r1((statistics.mean(s["r1m"] for s in L) - med_r1) * 100),
                            r3m=r1((statistics.mean(s["r3m"] for s in L) - med_r3) * 100),
                            mom_rel=r1(statistics.mean(s["mom_rel"] for s in Lh)),
                            acc_rank=round(statistics.mean(s["acc_pct"] for s in L)),
                            tv_share=round(tv / total_tv, 3), tv_usd_m=round(tv),
                            breadth=round(sum(1 for s in L if s["above50"]) / len(L), 2),
                            vratio=round(statistics.mean(s["vratio"] for s in L), 2),
                            top=", ".join(s["name"] for s in top), _members=L))
        if len(out) >= 2:
            Q = rank_q([0.75 * x + 0.25 * y for x, y in zip(pr([r["mom_rel"] for r in out]), pr([r["acc_rank"] for r in out]))])
            for r, q in zip(out, Q):
                r["flow_score"] = round((q - 0.5) * 15, 1)
                r["flow"] = sector_label(q)
        else:
            for r in out:
                r["flow_score"], r["flow"] = 0.0, "No clear direction"
        return out

    secs = groups("sector", MIN_SECTOR)
    inds = groups("industry", MIN_INDUSTRY)
    picks = []
    for r in secs:
        cand = sorted([s for s in r["_members"] if s["has"]], key=lambda s: -s["tv_usd_m"])[:MOST_TRADED]
        if r["flow"] in ("Strong inflow", "Money coming in"):
            basis, cand = "in", sorted(cand, key=lambda s: -s["P"])
        elif r["flow"] in ("Strong outflow", "Money leaving"):
            basis, cand = "out", sorted(cand, key=lambda s: s["P"])
        else:
            basis = "none"
        for k, s in enumerate(cand[:3]):
            picks.append(dict(market=m["k"], sector=r["group"], rank=k + 1, sym=s["sym"], ticker=s["tk"], full_name=s["name"],
                              industry=s["industry"], P=round(s["P"], 3), mom_rel=r1(s["mom_rel"]), tv_usd_m=round(s["tv_usd_m"], 1),
                              tv_msek=round(s["tv_usd_m"] * usdsek, 1), basis=basis))
    for r in secs + inds:
        r.pop("_members")
    meta = dict(universe=len(U), with_bars=len(rows), companies=len(S), with_year=len(H), fx_to_usd=fx,
                median_12_1=round(med_mom * 100, 1), last_bar=max(s["last"] for s in S))
    return secs + inds, picks, meta


def main():
    out = {"generated": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%MZ"), "flows": [], "picks": [], "markets": {}, "extra": {}, "errors": []}
    try:
        j = http_json("https://query1.finance.yahoo.com/v8/finance/chart/SEK=X?range=5d&interval=1d")
        usdsek = [c for c in j["chart"]["result"][0]["indicators"]["quote"][0]["close"] if c][-1]
    except Exception as e:
        out["errors"].append("USDSEK: %s" % e)
        usdsek = 9.9
    out["usdsek"] = usdsek
    for m in MARKETS:
        errs = []
        try:
            fl, pk, meta = build_market(m, usdsek, errs)
            out["flows"] += fl; out["picks"] += pk
            meta["errors"] = errs
            out["markets"][m["k"]] = meta
            print(m["k"], meta["companies"], "companies,", sum(1 for f in fl if f["level"] == "sector"), "sectors,", len(errs), "errors", flush=True)
        except Exception as e:
            out["errors"].append("%s: %s" % (m["k"], e))
            out["markets"][m["k"]] = {"errors": errs, "failed": str(e)}
    try:
        j = scan({"symbols": {"tickers": EXTRA_SYMS}, "columns": ["sector", "industry"]})
        for x in j.get("data") or []:
            out["extra"][x["s"]] = {"sector": x["d"][0], "industry": x["d"][1]}
    except Exception as e:
        out["errors"].append("extra: %s" % e)
    json.dump(out, open(OUT, "w"), ensure_ascii=False, indent=1)
    print("wrote", OUT, len(out["flows"]), "flow rows,", len(out["picks"]), "picks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
