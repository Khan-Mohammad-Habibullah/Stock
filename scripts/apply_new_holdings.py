#!/usr/bin/env python3
"""Apply the 28 Oct 2026 Nordnet export to the live index.html: update
qty/value/weight on the 111 continuing holdings, drop the 7 that were sold,
and add the 6 brand-new ones (NVIDIA, Puuilo, Whitecap Resources, Vaisala A,
SAP SE, UiPath) with real signals computed from data/new_stock_signals.json
(fetched server-side via .github/workflows/fetch-new-stocks.yml -- see that
script for the methodology, which mirrors the rest of the board's own
calc.js logic). Also refreshes the dependent monthly/etfs/exposure/flow_picks
datasets. Mirrors the original scratchpad/nn/build_data.py "added symbols"
approach (same regression-fit outlook scoring), adapted to operate on the
live, already-bot-updated index.html instead of a stale local snapshot, so
it never clobbers the crypto datasets or anything else already shipped.

Edits index.html in place, like the other scripts/patch_*.py / bake_*.py
one-offs.
"""
import copy
import datetime
import json
import math
import re
import sys

import numpy as np

INDEX = "/home/claude/stock/index.html"
POS = json.load(open("/tmp/claude-0/-home-claude/f28ba201-572d-5ba2-b1b7-0d31666d5e3c/scratchpad/nn/live_pos.json"))
NEW_SIGNALS = json.load(open("/home/claude/stock/data/new_stock_signals.json"))

# Matched the new PDF export against the LIVE index.html holdings (not the
# stale scratchpad snapshot): of the 6 names that first looked unmapped,
# four (Puuilo, Whitecap Resources, Vaisala A, SAP SE) turn out to already
# be held -- only NVIDIA and UiPath are genuinely brand-new positions.
REMOVED = ["NASDAQ:EXE", "NYSE:NOW", "OMXSTO:ANOD_B", "OMXSTO:XBRANE", "OMXSTO:YUBICO", "OSL:2020"]
ADDED = ["NASDAQ:NVDA", "NYSE:PATH"]

FLOWMAP = {
    "NASDAQ:NVDA": ("US", "industry", "Semiconductors"),
    "NYSE:PATH": ("US", "industry", "Packaged Software"),
}
MARKET_OF = {"NASDAQ:NVDA": "US", "NYSE:PATH": "US"}
CUR_OF = {"NASDAQ:NVDA": "USD", "NYSE:PATH": "USD"}
DIRECT_SYMS_EXTRA = {"NVIDIA": ["NASDAQ:NVDA"]}


def find_matching_bracket(s, open_pos):
    depth = 0
    in_str = False
    esc = False
    i = open_pos
    while i < len(s):
        c = s[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == "[":
                depth += 1
            elif c == "]":
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    return -1


def load_array(s, key):
    idx = s.find('"%s":[' % key)
    start = idx + len('"%s":' % key)
    end = find_matching_bracket(s, start)
    return json.loads(s[start:end + 1]), start, end


def replace_array(s, key, new_val):
    arr, start, end = load_array(s, key)
    js = json.dumps(new_val, separators=(",", ":"), ensure_ascii=False)
    return s[:start] + js + s[end + 1:]


cl = lambda x, a, b: max(a, min(b, x))


def pct(x, d=0, sign=False):
    v = round(x, d)
    return ("%+.*f%%" if sign else "%.*f%%") % (d, v)


def main():
    s = open(INDEX, encoding="utf-8").read()
    holdings, _, _ = load_array(s, "holdings")
    monthly, _, _ = load_array(s, "monthly")
    etfs, _, _ = load_array(s, "etfs")
    exposure, _, _ = load_array(s, "exposure")
    flow_picks, _, _ = load_array(s, "flow_picks")
    flows, _, _ = load_array(s, "flows")

    old = {r["sym"]: r for r in holdings}
    assert set(POS) - set(old) == set(ADDED), set(POS) - set(old) - set(ADDED)
    assert set(old) - set(POS) == set(REMOVED), set(old) - set(POS) - set(REMOVED)
    TOTAL = sum(p["val"] for p in POS.values())

    # ---------- fit outlook regressions on the existing (continuing) rows ----------
    def f1(r):
        w = r["o1y_why"] or ""
        m = re.search(r"(\d+) months (ahead|behind) of the market by (\d+) pts", w)
        rel = (int(m.group(3)) * (1 if m.group(2) == "ahead" else -1)) if m else 0
        mm = re.search(r"(\d+)% below its (\d+)-week high", w)
        mt = re.search(r"average target (\d+)% above", w)
        return [int("above its 40-week average, which is rising" in w), int("above its 40-week average, which is falling" in w),
                int("below its 40-week average, which is rising" in w), int("below its 40-week average, which is falling" in w),
                rel / 10, -int(mm.group(1)) / 10 if mm else 0, int("analysts rate it a buy" in w), min(int(mt.group(1)), 100) / 10 if mt else 0,
                int("already above average target" in w)]

    def f3(r):
        w = r["o3y_why"] or ""
        g = lambda k: 0 if r[k] is None else r[k]
        return [cl(g("rev_g"), -30, 40) / 10, cl(g("eps_g"), -100, 100) / 50, cl(g("margin"), -30, 40) / 10, int("cheap at" in w), int("expensive at" in w),
                int("heavy debt" in w), int("loss-making" in w), int("burning cash" in w), int(r["rev_g"] is not None and r["rev_g"] > 0)]

    def f5(r):
        w = r["o5y_why"] or ""
        roe = re.search(r"return on equity (-?\d+)%", w)
        roe = int(roe.group(1)) if roe else 0
        g = lambda k: 0 if r[k] is None else r[k]
        return [cl(g("margin"), -30, 40) / 10, cl(roe, -30, 40) / 10, cl(g("rev_g"), -30, 40) / 10, int("large, established" in w), int("small company" in w),
                int("little room" in w), int("not yet profitable" in w), int("burning cash" in w), int("heavy debt" in w)]

    def fit(key, f):
        h = [r for r in holdings if r[key + "_score"] is not None and "trend only" not in (r["o3y_why"] or "") and "no fundamentals" not in (r["o3y_why"] or "")]
        X = np.array([f(r) for r in h], float)
        y = np.array([r[key + "_score"] for r in h])
        A = np.c_[X, np.ones(len(y))]
        return np.linalg.lstsq(A, y, rcond=None)[0]

    C1, C3, C5 = fit("o1y", f1), fit("o3y", f3), fit("o5y", f5)
    lab = lambda sc: "Positive" if sc >= 3.5 else "Leaning positive" if sc >= 1 else "Mixed" if sc > -1 else "Leaning negative" if sc > -3.5 else "Negative"
    r05 = lambda x: round(x * 2) / 2

    tmpl_keys = list(next(iter(old.values())).keys())
    newrows = {}
    for sym in ADDED:
        t = NEW_SIGNALS[sym]["T"]
        f = NEW_SIGNALS[sym]["F"]
        r = {k: None for k in tmpl_keys}
        r.update(sym=sym, name=POS[sym]["name"], market=MARKET_OF[sym], cur=CUR_OF[sym])
        for k in ["price", "r1m", "r3m", "r12m", "rsi", "macd", "vs20", "vs50", "vs200", "ma_cross", "pctb", "bollinger", "alligator", "cpr", "cpr_tc", "cpr_bc", "cpr_r1", "cpr_s1",
                  "cmf", "cmf60", "udv", "udv50", "obv", "adx", "candles", "w_rsi", "vs40w", "off_high", "vol", "acc_days", "dist_days", "structure", "oct_score"]:
            r[k] = t[k]
        r["price"] = round(r["price"], 2)
        r["candles_w"] = t.get("candles_w")
        r["vol_days"] = 252
        r["turnover_msek"] = round((t["turnover_avg"] or 0) / 1e6, 1)
        rev_g, eps_g, margin, pe, de = f.get("rev_g"), f.get("eps_g"), f.get("margin"), f.get("pe"), f.get("de")
        r["rev_g"], r["eps_g"], r["margin"], r["pe"], r["de"] = rev_g, eps_g, margin, pe, de
        rec = f.get("rec_mean") or 2.5
        r["analysts"] = "Strong buy" if rec <= 1.5 else "Buy" if rec <= 2.0 else "Hold" if rec <= 3.0 else "Underperform"
        tgt = f.get("target_mean")
        r["target"] = round(tgt, 2) if tgt else None
        r["upside"] = round((tgt / t["price"] - 1) * 100, 1) if tgt else 0.0
        pats = []
        if t.get("bandwidth_rank") is not None and t["bandwidth_rank"] <= 0.2:
            pats.append("Bollinger squeeze (coiling)")
        if t.get("b55") == 1:
            pats.append("55-day breakout")
        r["patterns"] = ", ".join(pats) or None
        r["oct_signal"] = t["oct_signal"]
        r["oct_why"] = t["oct_why"] + "; estimated from Yahoo Finance daily bars and fundamentals (TradingView's live browser session was not available for this update), using the same indicator formulas as the rest of the board"
        sf = t["sflow_score"]
        thin = r["turnover_msek"] < 1.25
        r["sflow_score"] = sf
        r["sflow"] = "Too thinly traded to tell" if thin else "Money coming in" if sf >= 2 else "Money leaving" if sf <= -2 else "No clear direction"
        r["sflow_why"] = ("only about %.1f million SEK traded a day, too little for volume to say much; " % r["turnover_msek"] if thin else "") + \
            "money flow (CMF) %+.2f over 20 days and %+.2f over 60; volume on up days %.2fx volume on down days over 50 days; %d heavy-volume up days against %d heavy-volume down days in the last 25 sessions; on-balance volume %s its 50-day average" % (
                t["cmf"], t["cmf60"], t["udv50"] or 0, t["acc_days"], t["dist_days"], "above" if t["obv"] == "Up" else "below")
        # ---------- outlooks via the fitted regressions ----------
        rel = (t["r12m"] or 0) - (t["r1m"] or 0) - 10  # approx r126 unavailable -> fall back to r12m-r1m proxy
        w1 = []
        above = (t["vs40w"] or 0) > 0
        w1.append("%s its 40-week average, which is %s" % ("above" if above else "below", "rising" if t["w40_rising"] else "falling"))
        if abs(rel) >= 20:
            w1.append("6 months %s of the market by %d pts" % ("ahead" if rel > 0 else "behind", round(abs(rel))))
        if (t["off_high"] or 0) <= -50:
            w1.append("%d%% below its 52-week high" % round(-t["off_high"]))
        buy = rec <= 2.0
        if buy:
            w1.append("analysts rate it a buy")
        if r["upside"] <= 0:
            w1.append("price already above average target")
        elif r["upside"] >= 20:
            w1.append("average target %d%% above price" % round(r["upside"]))
        x1 = [int(above and t["w40_rising"]), int(above and not t["w40_rising"]), int((not above) and t["w40_rising"]), int((not above) and not t["w40_rising"]),
              (rel if abs(rel) >= 20 else 0) / 10, (-(-t["off_high"]) / 10 if (t["off_high"] or 0) <= -50 else 0), int(buy), (min(r["upside"], 100) / 10 if r["upside"] >= 20 else 0), int(r["upside"] <= 0)]
        s1 = cl(round(float(np.dot(C1[:-1], x1) + C1[-1]), 1), -5, 5)
        r["o1y_score"], r["o1y"] = s1, lab(s1)
        r["o1y_why"] = "; ".join(w1) + "; estimated from the screener data, treat as approximate"

        fcf = f.get("fcf")
        burn = fcf is not None and fcf < 0
        loss = margin is not None and margin < 0
        heavy = de is not None and de >= 2
        cheap = pe is not None and 0 < pe <= 18
        w3 = ["revenue %s" % pct(rev_g or 0, 0, True), "earnings per share %s" % pct(eps_g or 0, 0, True)]
        if loss:
            w3.append("loss-making")
        else:
            w3.append("net margin %s" % pct(margin or 0))
        if burn:
            w3.append("burning cash")
        if heavy:
            w3.append("heavy debt")
        if cheap:
            w3.append("cheap at %dx earnings" % round(pe))
        x3 = [cl(rev_g or 0, -30, 40) / 10, cl(eps_g or 0, -100, 100) / 50, cl(margin or 0, -30, 40) / 10, int(cheap), 0, int(heavy), int(loss), int(burn), int((rev_g or 0) > 0)]
        s3 = cl(r05(float(np.dot(C3[:-1], x3) + C3[-1])), -4.5, 5.5)
        r["o3y_score"], r["o3y"] = s3, lab(s3)
        r["o3y_why"] = "; ".join(w3) + "; estimated from the screener data, treat as approximate"

        roe = f.get("roe")
        w5 = ["net margin %s" % pct(margin or 0), "return on equity %s" % pct(roe or 0),
              ("revenue growing %s" % pct(rev_g or 0)) if (rev_g or 0) >= 0 else ("revenue shrinking %s" % pct(-(rev_g or 0)))]
        if burn:
            w5.append("burning cash")
        if heavy:
            w5.append("heavy debt")
        if loss:
            w5.append("not yet profitable")
        mcap = f.get("mcap") or 0
        big = mcap >= 1e11
        small = mcap < 1e9
        if big:
            w5.append("large, established company")
        if small:
            w5.append("small company (under $1B), higher failure risk")
        x5 = [cl(margin or 0, -30, 40) / 10, cl(roe or 0, -30, 40) / 10, cl(rev_g or 0, -30, 40) / 10, int(big), int(small), 0, int(loss), int(burn), int(heavy)]
        s5 = cl(r05(float(np.dot(C5[:-1], x5) + C5[-1])), -4.5, 5.5)
        r["o5y_score"], r["o5y"] = s5, lab(s5)
        r["o5y_why"] = "; ".join(w5) + "; estimated from the screener data, treat as approximate"

        fm, lvl, grp = FLOWMAP[sym]
        fl = [x for x in flows if x["market"] == fm and x["level"] == lvl and x["group"] == grp]
        assert len(fl) == 1, (sym, fm, lvl, grp)
        fl = fl[0]
        r["flow_market"], r["flow_group"], r["flow_sector"] = fm, grp, fl.get("sector") or grp
        r["flow"], r["flow_score"] = fl["flow"], fl["flow_score"]

        ds = round(cl(0.42 * r["flow_score"] + 0.36 * t["oct_score"] + 0.34 * s1 + 0.21 * sf + 0.12 * s3 - 0.06 * s5 - 0.14, -7, 7), 1)
        r["dec_score"] = ds
        r["december"] = "Consider adding" if ds >= 4 else "Hold, add on dips" if ds >= 2 else "Hold" if ds > -2 else "Consider trimming" if ds > -3.8 else "Consider selling by December"
        dw = "money flow in %s in %s%s: %s; October signal %s; 1-year outlook %s" % (grp, fm, " (sector)" if lvl == "sector" else "", r["flow"].lower(), r["oct_signal"].lower(), r["o1y"].lower())
        if abs(t["cmf"]) > 0.05:
            dw += "; its own volume shows %s (CMF %+.2f)" % ("buying" if t["cmf"] > 0 else "selling", t["cmf"])
        r["dec_why"] = dw

        sig = (t["vol"] or 30) / 100
        px = t["price"]
        r["r50_lo"] = round(px * math.exp(-0.6745 * sig), 2)
        r["r50_hi"] = round(px * math.exp(0.6745 * sig), 2)
        r["r80_lo"] = round(px * math.exp(-1.2816 * sig), 2)
        r["r80_hi"] = round(px * math.exp(1.2816 * sig), 2)
        r["target"] = r["target"] if r["target"] else round(px, 2)
        r["note"] = "Added in the 28 October 2026 Nordnet export."
        newrows[sym] = r

    # ---------- assemble holdings ----------
    H = []
    for sym, p in POS.items():
        r = copy.deepcopy(old[sym]) if sym in old else newrows[sym]
        r["value_sek"] = p["val"]
        r["qty"] = p["qty"]
        r["weight"] = round(p["val"] / TOTAL * 100, 2)
        H.append(r)
    H.sort(key=lambda r: -r["value_sek"])

    # ---------- monthly ----------
    def lastweekday(y, m):
        d = datetime.date(y + (m == 12), m % 12 + 1, 1) - datetime.timedelta(days=1)
        while d.weekday() >= 5:
            d -= datetime.timedelta(days=1)
        return d

    nd = lambda x: 0.5 * (1 + math.erf(x / math.sqrt(2)))
    base = datetime.date(2026, 10, 28)
    M = [m for m in monthly if m["sym"] in POS]
    for sym in ADDED:
        r = newrows[sym]
        sig = (r["vol"] or 30) / 100
        px = r["price"]
        drift = cl(5 + 1.5 * r["o1y_score"], -10, 10) / 100
        for i in range(13):
            y, mth = 2026 + (10 + i) // 12, (10 + i) % 12 + 1
            d = lastweekday(y, mth)
            Tm = (d - base).days / 365
            if Tm <= 0:
                continue
            z = 0.6745
            lo, hi = px * math.exp(-z * sig * math.sqrt(Tm)), px * math.exp(z * sig * math.sqrt(Tm))
            mu = drift
            ch = 1 - nd((math.log(hi / px) - mu * Tm) / (sig * math.sqrt(Tm)))
            cLow = nd((math.log(lo / px) - mu * Tm) / (sig * math.sqrt(Tm)))
            diff = ch - cLow
            M.append(dict(sym=sym, name=r["name"], cur=r["cur"], month="%d-%02d" % (y, mth), date=d.isoformat(), likely_low=round(lo, 2), likely_high=round(hi, 2),
                          most_likely=round(px * math.exp(mu * Tm), 2), chance_high=round(ch, 3), chance_low=round(cLow, 3),
                          leans="High" if diff >= 0.03 else "Low" if diff <= -0.03 else "Even", drift_pct_yr=round(drift * 100, 1)))

    # ---------- ETFs: rescale value_sek by the same ratio as before/after ----------
    oldetf = {e["sym"]: e["value_sek"] for e in etfs}
    ETF = copy.deepcopy(etfs)
    scale = {}
    for e in ETF:
        newval = POS[e["sym"]]["val"]
        scale[e["sym"]] = newval / oldetf[e["sym"]] if oldetf[e["sym"]] else 1.0
        e["value_sek"] = newval

    # ---------- exposure ----------
    names = {"VanEck Semiconductor": "XETR:VVSM", "iShares S&P 500 IT": "XETR:QDVE", "iShares Europe IT": "XETR:ESIT", "SPDR MSCI Europe Health Care UCITS": "XETR:SPYH",
             "WisdomTree Cybersecurity UCITS": "XETR:W1TB", "Saturna Al-Kawthar": "XETR:ASWE"}
    direct_syms = {"NVIDIA": ["NASDAQ:NVDA"], "Broadcom": ["NASDAQ:AVGO"], "Intel": ["NASDAQ:INTC"], "AstraZeneca": ["OMXSTO:AZN"], "Hexagon B": ["OMXSTO:HEXA_B"], "Zscaler": ["NASDAQ:ZS"],
                   "Semiconductors (theme, at least)": ["NASDAQ:AVGO", "NASDAQ:NVDA", "NASDAQ:INTC", "NASDAQ:AMKR", "NASDAQ:QCOM", "NASDAQ:MRVL", "NASDAQ:AEIS"]}
    EXP = []
    for e in exposure:
        items = [x.strip() for x in e["via"].split(";")]
        out = []
        via = 0
        for it in items:
            m = re.match(r"(.*?) ([\d,]+) SEK$", it)
            nm, amt = m.group(1), int(m.group(2).replace(",", ""))
            sym = [v for k, v in names.items() if nm.startswith(k)][0]
            na = round(amt * scale.get(sym, 1.0))
            via += na
            out.append("%s %s SEK" % (nm, format(na, ",")))
        direct = sum(POS[sy]["val"] for sy in direct_syms.get(e["company"], []) if sy in POS)
        EXP.append(dict(company=e["company"], direct_sek=direct, via_etf_sek=via, total_sek=direct + via, via="; ".join(out)))

    # ---------- flow_picks 'owned' ----------
    FP = copy.deepcopy(flow_picks)
    for p in FP:
        p["owned"] = p["sym"] in POS

    # ---------- write everything back into index.html ----------
    s = replace_array(s, "holdings", H)
    s = replace_array(s, "monthly", M)
    s = replace_array(s, "etfs", ETF)
    s = replace_array(s, "exposure", EXP)
    s = replace_array(s, "flow_picks", FP)

    open(INDEX, "w", encoding="utf-8").write(s)
    print("done: holdings=%d monthly=%d etfs=%d exposure=%d flow_picks(owned=%d)" % (
        len(H), len(M), len(ETF), len(EXP), sum(1 for p in FP if p["owned"])))
    print("TOTAL", TOTAL)
    for sym in ADDED:
        r = newrows[sym]
        print(sym, r["oct_score"], r["oct_signal"], "|", r["o1y"], r["o1y_score"], "|", r["o3y"], r["o3y_score"], "|", r["o5y"], r["o5y_score"], "|", r["sflow"], "|", r["flow"], "|", r["december"])


if __name__ == "__main__":
    main()
