#!/usr/bin/env python3
"""Rebuild every stock tab of the board from scratch (runs every weekday on GitHub
Actions, and whenever the holdings change).

Reads   data/portfolio.json     current positions, former holdings, Nordnet name map
        data/etf_facts.json     fund fact sheets, top holdings, exposure weights
        data/outlook_model.json calibrated 1/3/5-year outlook weights
Writes  index.html datasets: holdings, former, monthly, flows, flow_picks, etfs,
        exposure, board_status (+ the "Data last extracted" labels)

  --dry   write data/preview/*.json and a comparison with the page's current rows
          instead of touching index.html
"""
import argparse
import copy
import datetime
import json
import math
import os
import re
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import board_lib as L

PAGE = "index.html"
EUROPE = ["United Kingdom", "Germany", "France", "Netherlands", "Switzerland", "Spain", "Italy", "Belgium", "Ireland", "Austria",
          "Portugal", "Luxembourg", "Denmark", "Finland"]
MARKETS = [
    dict(k="US", countries=["United States"], ex=["NASDAQ", "NYSE", "AMEX"], n=650, min_mcap=2e9, ind_min=6),
    dict(k="Sweden", countries=["Sweden"], ex=["OMXSTO"], n=200, ind_min=4),
    dict(k="Norway", countries=["Norway"], ex=["OSL"], n=120, ind_min=4),
    dict(k="Europe", countries=EUROPE, primary=True, n=280, min_mcap=5e9, ind_min=6),
    dict(k="Denmark", countries=["Denmark"], ex=["OMXCOP"], n=70, ind_min=4),
    dict(k="Finland", countries=["Finland"], ex=["OMXHEX"], n=80, ind_min=4),
    dict(k="Germany", countries=["Germany"], ex=["XETR"], n=110, ind_min=4),
    dict(k="Canada", countries=["Canada"], ex=["TSX"], n=130, ind_min=4),
]
MIN_SECTOR = 3
OWN_MKT = {"NASDAQ": "US", "NYSE": "US", "AMEX": "US", "OMXSTO": "Sweden", "OSL": "Norway", "TSX": "Canada"}
MKT_NAME = {"US": "the US", "Sweden": "Sweden", "Norway": "Norway", "Europe": "Europe", "Canada": "Canada"}
INDEX = {"US": "^GSPC", "OMX": "^OMX"}
SUFFIXES = (" Class A", " Class B", " Class C", " Inc.", " Inc", " Corporation", " Corp.", " plc", " AB", " ASA", " SE", " N.V.", " AG", " S.A.",
            " Ltd.", " Limited", " Holdings", ", Inc.", " Group", " A/S", " Oyj", " Abp", " Oyj Abp")


def now_utc():
    return datetime.datetime.now(datetime.timezone.utc)


def ds(s, key, default=None):
    i = s.find('"%s":[' % key)
    if i < 0:
        return default
    return json.JSONDecoder().raw_decode(s, i + len('"%s":' % key))[0]


def short_name(nm):
    out = nm
    for _ in range(2):
        for suf in SUFFIXES:
            if out.endswith(suf):
                out = out[: -len(suf)]
    return out.strip().rstrip(",")


def base_company(nm):
    return re.sub(r" Class [A-Z]$| Series [A-Z]$", "", nm or "").strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()
    t0 = now_utc()
    page = open(PAGE, encoding="utf-8").read()
    PF = json.load(open("data/portfolio.json", encoding="utf-8"))
    EF = json.load(open("data/etf_facts.json", encoding="utf-8"))
    OM = json.load(open("data/outlook_model.json", encoding="utf-8"))
    old_rows = {r["sym"]: r for r in (ds(page, "holdings") or []) + (ds(page, "former") or [])}
    old_flows = {(f["market"], f["level"], f["group"]): f for f in ds(page, "flows") or []}
    errors = []

    # ------------------------------------------------ 1. universes and the symbols we need
    rates = L.fx_to_usd()
    assert "SEK" in rates and "EUR" in rates, rates
    U = {}
    for m in MARKETS:
        try:
            U[m["k"]] = L.scan_universe(m["countries"], m.get("ex"), m["n"], m.get("min_mcap"), m.get("primary", False))
        except Exception as e:
            errors.append("universe %s: %s" % (m["k"], e)); U[m["k"]] = []
    own = [p["sym"] for p in PF["positions"]] + [f["sym"] for f in PF["former"]]
    look = sorted({x["sym"] for v in EF["top"].values() for x in v})
    info = L.scan_symbols(sorted(set(own + look)))
    for u in U.values():
        for r in u:
            info.setdefault(r["sym"], r)
    need = {}
    for sym, r in info.items():
        need[sym] = (sym, r.get("country"), r.get("close"))
    for sym in own:
        need.setdefault(sym, (sym, None, None))
    bars, berr = L.fetch_many(list(need.values()), workers=6)
    idx = {}
    for k, yt in INDEX.items():
        try:
            idx[k] = L.retry(L.fetch_bars, yt)[0]
        except Exception as e:
            errors.append("index %s: %s" % (yt, e))
    print("bars", len(bars), "failed", len(berr), flush=True)

    def usd_unit(sym):
        return L.usd_per(bars[sym][1] or info.get(sym, {}).get("currency") or "USD", rates)

    FM = {}
    for sym in bars:
        try:
            FM[sym] = L.flow_metrics(bars[sym][0], usd_unit(sym))
        except Exception as e:
            berr[sym] = "metrics: %s" % e
    today = now_utc().date()
    fresh = lambda sym: sym in FM and FM[sym] and (today - datetime.date.fromisoformat(FM[sym]["last"])).days <= 10
    bars_fresh = lambda sym: sym in bars and len(bars[sym][0]) >= 70 and (today - datetime.datetime.utcfromtimestamp(bars[sym][0][-1][0]).date()).days <= 10

    # ------------------------------------------------ 2. per-market readings
    MK, flows, picks, mstat = {}, [], [], {}
    for m in MARKETS:
        k = m["k"]
        mem = [dict(r, **FM[r["sym"]]) for r in U[k] if fresh(r["sym"])]
        best = {}
        for r in mem:
            b = base_company(r["description"])
            if b not in best or r["tv_usd_m"] > best[b]["tv_usd_m"]:
                best[b] = r
        S = list(best.values())
        Hs = [r for r in S if r["has"]]
        if len(Hs) < 10:
            errors.append("market %s: only %d usable companies" % (k, len(Hs))); continue
        med = statistics.median(r["mom"] for r in Hs)
        med1 = statistics.median(r["r1m"] for r in S); med3 = statistics.median(r["r3m"] for r in S)
        for r in S:
            r["mom_rel"] = (r["mom"] - med) * 100 if r["has"] else None
        s_mom = sorted(r["mom_rel"] for r in Hs); s_acc = sorted(r["acc"] for r in Hs); s_cmf = sorted(r["cmf20"] for r in Hs)
        s_acc_all = sorted(r["acc"] for r in S)
        comp = lambda mr, acc, cmf: 0.6 * L.pr_against(mr, s_mom) + 0.2 * L.pr_against(acc, s_acc) + 0.2 * L.pr_against(cmf, s_cmf)
        s_comp = sorted(comp(r["mom_rel"], r["acc"], r["cmf20"]) for r in Hs)
        MK[k] = dict(med=med, comp=comp, s_comp=s_comp, s_acc_all=s_acc_all)
        for r in S:
            r["acc_pct"] = L.pr_against(r["acc"], s_acc_all) * 100
            r["P"] = L.pr_against(comp(r["mom_rel"], r["acc"], r["cmf20"]), s_comp) if r["has"] else None
        total_tv = sum(r["tv_usd_m"] for r in S)

        def groups(level, min_n):
            key = "sector" if level == "sector" else "industry"
            g = {}
            for r in S:
                if r.get(key):
                    g.setdefault(r[key], []).append(r)
            out = []
            for name, Lm in g.items():
                Lh = [r for r in Lm if r["has"]]
                if len(Lh) < min_n:
                    continue
                tv = sum(r["tv_usd_m"] for r in Lm)
                out.append(dict(market=k, level=level, group=name, sector=Lm[0]["sector"], n=len(Lm),
                                r1m=L.r2((statistics.mean(r["r1m"] for r in Lm) - med1) * 100), r3m=L.r2((statistics.mean(r["r3m"] for r in Lm) - med3) * 100),
                                mom_rel=L.r2(statistics.mean(r["mom_rel"] for r in Lh)), acc_rank=round(statistics.mean(r["acc_pct"] for r in Lm)),
                                tv_share=round(tv / total_tv, 3), tv_usd_m=round(tv), breadth=round(sum(1 for r in Lm if r["above50"]) / len(Lm), 2),
                                vratio=round(statistics.mean(r["vratio"] for r in Lm), 2),
                                top=", ".join(r["description"] for r in sorted(Lm, key=lambda r: -r["tv_usd_m"])[:3]), _m=Lm))
            if len(out) >= 2:
                Q = L.rank_q([0.75 * a + 0.25 * b for a, b in zip(L.pr([r["mom_rel"] for r in out]), L.pr([r["acc_rank"] for r in out]))])
                for r, q in zip(out, Q):
                    r["flow_score"], r["flow"] = round((q - 0.5) * 15, 1), L.sector_label(q)
            else:
                for r in out:
                    r["flow_score"], r["flow"] = 0.0, "No clear direction"
            return out

        secs, inds = groups("sector", MIN_SECTOR), groups("industry", m["ind_min"])
        usd_sek = 1 / rates["SEK"]
        for r in secs:
            cand = sorted([x for x in r["_m"] if x["has"]], key=lambda x: -x["tv_usd_m"])
            cand = cand[:max(3, math.ceil(len(cand) * 0.4))]
            if r["flow"] in ("Strong inflow", "Money coming in"):
                basis, cand = "strongest buying among its most-traded companies", sorted(cand, key=lambda x: -x["P"])
            elif r["flow"] in ("Strong outflow", "Money leaving"):
                basis, cand = "heaviest selling among its most-traded companies", sorted(cand, key=lambda x: x["P"])
            else:
                basis = "its most-traded companies"
            for i, x in enumerate(cand[:3]):
                picks.append(dict(market=k, sector=r["group"], rank=i + 1, name=short_name(x["description"]), full_name=x["description"], ticker=x["name"],
                                  sym=x["sym"], industry=x.get("industry"), stock_flow=L.stock_label(x["P"], x["tv_usd_m"] * usd_sek),
                                  stock_score=round((x["P"] - 0.5) * 15, 1), mom_rel=L.r2(x["mom_rel"]), tv_usd_m=round(x["tv_usd_m"], 1), owned=False, basis=basis))
        for r in secs + inds:
            r.pop("_m")
        flows += secs + inds
        mstat[k] = dict(companies=len(S), with_year=len(Hs), sectors=len(secs), industries=len(inds), last_bar=max(r["last"] for r in S))
        print(k, mstat[k], flush=True)
    fidx = {(f["market"], f["level"], f["group"]): f for f in flows}

    def stock_P(sym, market):
        mk = MK.get(market)
        fm = FM.get(sym)
        if not mk or not fm or not fm["has"]:
            return None, None
        mr = (fm["mom"] - mk["med"]) * 100
        return L.pr_against(mk["comp"](mr, fm["acc"], fm["cmf20"]), mk["s_comp"]), mr

    # ------------------------------------------------ 3. one row per holding / former holding
    model = {k: OM[k] for k in ("o1y", "o3y", "o5y")}
    r05 = lambda x: round(x * 2) / 2
    sek_per = lambda cur: L.usd_per(cur, rates) / rates["SEK"]
    idx_r126 = {k: (B[-1][4] / B[-127][4] - 1) * 100 for k, B in idx.items() if len(B) > 130}

    def build_row(p, kind):
        sym = p["sym"]
        old = old_rows.get(sym)
        T = None
        if bars_fresh(sym):
            try:
                T = L.analyse(bars[sym][0])
            except Exception as e:
                berr[sym] = "analyse: %s" % e
        if T is None:
            if old:
                errors.append("%s: no fresh bars (%s), kept previous reading" % (sym, berr.get(sym, "stale")))
                r = copy.deepcopy(old)
                if kind == "own":
                    r["qty"] = p["qty"]
                    r["value_sek"] = round(p["qty"] * r["price"] * sek_per(r["cur"])) if r.get("price") else r.get("value_sek")
                return r
            errors.append("%s: no bars and no previous reading, left out" % sym)
            return None
        B = bars[sym][0]
        F = info.get(sym, {})
        cur = bars[sym][1] if bars[sym][1] not in ("GBp", "GBX") else "GBX"
        cur = (p.get("cur") or F.get("currency") or cur)
        is_etf = (p.get("market") or "").endswith("ETF") or F.get("type") == "fund"
        r = {}
        r.update(sym=sym, name=p["name"], market=p.get("market"), cur=cur)
        for k in ["price", "r1m", "r3m", "r12m", "rsi", "macd", "vs20", "vs50", "vs200", "ma_cross", "pctb", "bollinger", "alligator", "cpr", "cpr_tc",
                  "cpr_bc", "cpr_r1", "cpr_s1", "cmf", "cmf60", "udv", "udv50", "obv", "adx", "candles", "candles_w", "w_rsi", "vs40w", "off_high", "vol",
                  "vol_days", "structure", "patterns", "oct_score", "oct_signal", "oct_why"]:
            r[k] = T.get(k)
        r["price"] = round(T["price"], 4)
        r["day_chg"] = L.r2((B[-1][4] / B[-2][4] - 1) * 100, 2)  # last close vs the one before (holdings get the live move on the page)
        # fundamentals (TradingView screener; money values come in USD)
        g = lambda k: F.get(k)
        rev, eps, mar, pe, de, roe, fcf, mcap = (g("total_revenue_yoy_growth_ttm"), g("earnings_per_share_diluted_yoy_growth_ttm"), g("net_margin_ttm"),
                                                g("price_earnings_ttm"), g("debt_to_equity"), g("return_on_equity"), g("free_cash_flow_ttm"), g("market_cap_basic"))
        nofund = (not is_etf) and rev is None and mar is None
        r["rev_g"] = L.r2(rev) if not is_etf else None
        r["eps_g"] = L.r2(eps) if not is_etf else None
        r["margin"] = L.r2(mar) if not is_etf else None
        r["pe"] = L.r2(pe) if (pe and pe > 0 and not is_etf) else None
        r["de"] = L.r2(de, 2) if (de is not None and not is_etf) else None
        rec = g("recommendation_mark")
        r["analysts"] = None if (rec is None or is_etf) else "Strong buy" if rec <= 1.5 else "Buy" if rec <= 2.5 else "Hold" if rec <= 3.5 else "Underperform" if rec <= 4.5 else "Sell"
        tgt = g("price_target_average")
        if tgt and not is_etf:
            loc = tgt * rates["USD"] / L.usd_per(cur, rates)
            r["target"] = round(loc, 2)
            r["upside"] = round((loc / r["price"] - 1) * 100, 1)
        else:
            r["target"] = r["upside"] = None
        # money flow in the stock
        mkt = "Europe" if is_etf else OWN_MKT.get(sym.split(":")[0], "Europe")
        P, mom_rel = stock_P(sym, mkt)
        fm = FM.get(sym) or {}
        tv_usd = fm.get("tv_usd_m")
        if tv_usd is None:  # short history: traded value straight from the bars
            tv_usd = sum(b[4] * b[5] for b in B[-20:]) / 20 * usd_unit(sym) / 1e6
        t_msek = round(tv_usd / rates["SEK"], 1)
        r["turnover_msek"], r["liquidity"] = t_msek, L.liquidity(t_msek)
        r["acc_days"], r["dist_days"] = fm.get("up"), fm.get("dn")
        r["sf_cmf20"], r["vol_ratio"] = L.r2(fm.get("cmf20"), 3), L.r2(fm.get("vratio"), 2)
        r["mom_rel"] = L.r2(mom_rel)
        mk = "European stocks" if is_etf else "stocks in " + MKT_NAME.get(mkt, mkt)
        if P is None:
            r["sflow"], r["sflow_score"], r["sf_rank"] = "Too new to tell", 0.0, None
            why = "less than a year of trading history, too new to read its 12-month trend; Chaikin money flow %+.2f over 20 days; about %s million SEK traded a day (%s)" % (
                fm.get("cmf20") or T["cmf"] or 0, format(round(t_msek), ","), r["liquidity"].lower())
        else:
            r["sflow_score"], r["sf_rank"] = round((P - 0.5) * 15, 1), round(P * 100)
            r["sflow"] = "Too thinly traded to tell" if t_msek < 1 else L.stock_label(P, t_msek)
            why = "ranked %d of 100 against %s: 12-month trend %+.0f points against the market's typical stock, %d heavy-volume buying days against %d selling days in the last 60 sessions, Chaikin money flow %+.2f over 20 days; about %s million SEK traded a day (%s)" % (
                round(P * 100), mk, mom_rel, fm["up"], fm["dn"], fm["cmf20"], format(round(t_msek), ","), r["liquidity"].lower())
            if t_msek < 1:
                why = "too little trading for volume to say much; " + why
        r["sflow_why"] = why
        # outlooks
        bench = "US" if (r["market"] or "").startswith("US") or sym.split(":")[0] in ("NASDAQ", "NYSE", "AMEX", "TSX") else "OMX"
        rel = T["r126"] - idx_r126.get(bench, 10)
        x = dict(vs40w=T["vs40w"], w40_rising=T["w40_rising"], rel6=rel if abs(rel) >= 20 else 0, oct_score=T["oct_score"], off_high=T["off_high"],
                 rev_g=rev, eps_g=eps, margin=mar, pe=pe, de=de, roe=roe, burn=fcf is not None and fcf < 0, big=(mcap or 0) >= 5e10,
                 small=mcap is not None and mcap < 1e9, analysts=r["analysts"], upside=r["upside"], w_rsi=T["w_rsi"], is_etf=is_etf, nofund=nofund)
        s1 = L.cl(round(L.apply_model(model["o1y"], L.feat1(x)), 1), -5, 5)
        w1 = []
        if T["vs40w"] is not None:
            w1.append("%s its 40-week average, which is %s" % ("above" if T["vs40w"] > 0 else "below", "rising" if T["w40_rising"] else "falling"))
        if abs(rel) >= 20: w1.append("6 months %s of the market by %d pts" % ("ahead" if rel > 0 else "behind", round(abs(rel))))
        if (T["off_high"] or 0) <= -50: w1.append("%d%% below its 52-week high" % round(-T["off_high"]))
        if r["analysts"] in ("Strong buy", "Buy"): w1.append("analysts rate it a buy")
        if r["upside"] is not None:
            if r["upside"] <= 0: w1.append("price already above average target")
            elif r["upside"] >= 20: w1.append("average target %d%% above price" % round(r["upside"]))
        r["o1y_score"], r["o1y"], r["o1y_why"] = s1, L.lt_label(s1), "; ".join(w1) or "trend readings mixed"
        if is_etf:
            up = (T["vs40w"] or 0) > 0
            s3, s5 = OM["etf_3y"]["up" if up else "down"][0], OM["etf_5y"]["up" if up else "down"][0]
            w3, w5 = "diversified fund; scored on trend only", "diversified fund: spreads company risk; scored on trend only"
        elif nofund:
            s3 = s5 = 0.0
            w3 = w5 = "no fundamentals in TradingView's screener, so not enough to judge"
        else:
            s3 = L.cl(r05(L.apply_model(model["o3y"], L.feat3(x))), -4.5, 5.5)
            s5 = L.cl(r05(L.apply_model(model["o5y"], L.feat5(x))), -4.5, 5.5)
            pct = lambda v, sign=False: ("%+.0f%%" if sign else "%.0f%%") % v
            loss = mar is not None and mar < 0
            a3 = []
            if rev is not None: a3.append("revenue %s" % pct(rev, True))
            if eps is not None: a3.append("earnings per share %s" % pct(eps, True))
            if mar is not None: a3.append("loss-making" if loss else "net margin %s" % pct(mar))
            if x["burn"]: a3.append("burning cash")
            if x["de"] is not None and x["de"] >= 2: a3.append("heavy debt")
            if pe and 0 < pe <= 18: a3.append("cheap at %dx earnings" % round(pe))
            elif pe and pe > 40: a3.append("expensive at %dx earnings" % round(pe))
            a5 = []
            if loss: a5.append("not yet profitable")
            elif mar is not None: a5.append("net margin %s" % pct(mar))
            if roe is not None: a5.append("return on equity %s" % pct(roe))
            if rev is not None: a5.append(("revenue growing %s" % pct(rev)) if rev >= 0 else ("revenue shrinking %s" % pct(-rev)))
            if x["burn"]: a5.append("burning cash")
            if x["de"] is not None and x["de"] >= 2: a5.append("heavy debt")
            if x["big"]: a5.append("large, established company")
            if x["small"]: a5.append("small company (under $1B), higher failure risk")
            w3, w5 = "; ".join(a3), "; ".join(a5)
        r["o3y_score"], r["o3y"], r["o3y_why"] = s3, L.lt_label(s3), w3
        r["o5y_score"], r["o5y"], r["o5y_why"] = s5, L.lt_label(s5), w5
        # money flow in the sector
        if is_etf:
            tops = EF["top"].get(sym) or []
            num = den = 0.0
            for c in tops:
                cm = OWN_MKT.get(c["sym"].split(":")[0], "Europe")
                Pc, _ = stock_P(c["sym"], cm)
                if Pc is not None:
                    num += c["w"] * (Pc - 0.5) * 15; den += c["w"]
            fsc = round(num / den, 1) if den else 0.0
            r.update(flow_market="Fund holdings", flow_group="Top 10 holdings", flow_sector=None, flow=L.score_label(fsc) if den else "No sector data", flow_score=fsc)
        else:
            f = None
            if old and old.get("flow_market") and (old["flow_market"], "industry", old.get("flow_group")) in fidx:
                f = fidx[(old["flow_market"], "industry", old["flow_group"])]
            elif old and old.get("flow_market") and (old["flow_market"], "sector", old.get("flow_group")) in fidx:
                f = fidx[(old["flow_market"], "sector", old["flow_group"])]
            if f is None:
                f = fidx.get((mkt, "industry", F.get("industry"))) or fidx.get((mkt, "sector", F.get("sector")))
            if f is None:
                r.update(flow_market=None, flow_group="No sector data", flow_sector=None, flow="No sector data", flow_score=None)
            else:
                r.update(flow_market=f["market"], flow_group=f["group"], flow_sector=f["sector"], flow=f["flow"], flow_score=f["flow_score"])
        # December
        fs = r["flow_score"] or 0
        use_s = r["sflow"] not in ("Too thinly traded to tell", "Too new to tell")
        dsc = round(L.cl(fs / 2.5, 2) + (L.cl(r["sflow_score"] / 2.5, 2) if use_s else 0) + L.cl(r["oct_score"] / 3, 1.5) + L.cl(r["o1y_score"] / 2, 1.5), 1)
        if dsc <= -3.5: dl = "Consider selling by December"
        elif dsc <= -2: dl = "Consider trimming"
        elif dsc >= 4 and r["o1y"] in ("Positive", "Leaning positive") and r["o5y"] not in ("Negative", "Leaning negative") and sym != "XETR:ASWE": dl = "Consider adding"
        elif dsc >= 2: dl = "Hold, add on dips"
        else: dl = "Hold"
        r["dec_score"], r["december"] = dsc, dl
        r["dec_why"] = "%s: %s; money in the stock itself: %s; %s signal %s; 1-year outlook %s" % (
            "money in its top 10 holdings" if is_etf else "money in its sector", (r["flow"] or "no sector data").lower(), r["sflow"].lower(),
            datetime.date.fromisoformat(T["_date"]).strftime("%B"), r["oct_signal"].lower(), r["o1y"].lower())
        sig = (r["vol"] or 0) / 100
        for k, z in (("50", 0.6745), ("80", 1.2816)):
            r["r%s_lo" % k] = round(r["price"] * math.exp(-z * sig), 2); r["r%s_hi" % k] = round(r["price"] * math.exp(z * sig), 2)
        r["note"] = (old or {}).get("note") if old else p.get("note")
        r["p_ref"] = r["price"]
        if kind == "own":
            r["qty"] = p["qty"]
            r["value_sek"] = round(p["qty"] * r["price"] * sek_per(cur))
        else:
            r["qty"] = None; r["value_sek"] = None; r["gone_by"] = p.get("gone_by")
        r["_date"] = T["_date"]
        return r

    H, FR = [], []
    for p in PF["positions"]:
        r = build_row(p, "own")
        if r: H.append(r)
    for p in PF["former"]:
        r = build_row(p, "former")
        if r: FR.append(r)
    total = sum(r["value_sek"] for r in H) or 1
    for r in H:
        r["weight"] = round(r["value_sek"] / total * 100, 2)
    H.sort(key=lambda r: -r["value_sek"])
    for r in FR:
        r["weight"] = None
    FR.sort(key=lambda r: (r.get("gone_by") or "", r["name"]), reverse=True)
    held = {r["sym"] for r in H}
    for p in picks:
        p["owned"] = p["sym"] in held
    data_date = max((r.get("_date") or "") for r in H)

    # ------------------------------------------------ 4. monthly likely ranges (holdings)
    def lastweekday(y, mth):
        d = datetime.date(y + (mth == 12), mth % 12 + 1, 1) - datetime.timedelta(days=1)
        while d.weekday() >= 5:
            d -= datetime.timedelta(days=1)
        return d

    nd = lambda z: 0.5 * (1 + math.erf(z / math.sqrt(2)))
    base = datetime.date.fromisoformat(data_date)
    M = []
    for r in H:
        if not r.get("vol") or not r.get("price"):
            continue
        sig, px = r["vol"] / 100, r["price"]
        drift = L.cl(5 + 1.5 * r["o1y_score"], -10, 10) / 100
        for i in range(13):
            y, mth = base.year + (base.month - 1 + i) // 12, (base.month - 1 + i) % 12 + 1
            d = lastweekday(y, mth)
            Tm = max((d - base).days, 1) / 365
            z = 0.6745
            lo, hi = px * math.exp(-z * sig * math.sqrt(Tm)), px * math.exp(z * sig * math.sqrt(Tm))
            ch = 1 - nd((math.log(hi / px) - drift * Tm) / (sig * math.sqrt(Tm)))
            cL = nd((math.log(lo / px) - drift * Tm) / (sig * math.sqrt(Tm)))
            dp = 4 if px < 1 else 2
            M.append(dict(sym=r["sym"], name=r["name"], cur=r["cur"], month="%d-%02d" % (y, mth), date=d.isoformat(), likely_low=round(lo, dp), likely_high=round(hi, dp),
                          most_likely=round(px * math.exp(drift * Tm), dp), chance_high=round(ch, 3), chance_low=round(cL, 3),
                          leans="High" if ch - cL >= 0.03 else "Low" if ch - cL <= -0.03 else "Even", drift_pct_yr=round(drift * 100, 1)))

    # ------------------------------------------------ 5. ETFs and exposure
    hb = {r["sym"]: r for r in H}
    ETF = []
    for sym, fct in EF["facts"].items():
        if sym not in hb:
            continue
        h = hb[sym]
        e = dict(fct)
        e.update(value_sek=h["value_sek"], flow=h["flow"], flow_score=h["flow_score"], oct_signal=h["oct_signal"], o1y=h["o1y"], o5y=h["o5y"],
                 view=h["december"], view_why=h["dec_why"], r12m=h["r12m"])
        ETF.append(e)
    EXP = []
    for x in EF["exposure"]:
        direct = sum(hb[s]["value_sek"] for s in x["direct"] if s in hb)
        parts = [(v["label"], round(v["share"] * hb[v["fund"]]["value_sek"])) for v in x["via"] if v["fund"] in hb]
        via = sum(a for _, a in parts)
        if direct or via:
            EXP.append(dict(company=x["company"], direct_sek=direct, via_etf_sek=via, total_sek=direct + via, via="; ".join("%s %s SEK" % (nm, format(a, ",")) for nm, a in parts)))

    for r in H + FR:
        r.pop("_date", None)
    status = dict(built=t0.strftime("%Y-%m-%dT%H:%MZ"), data_date=data_date, holdings_updated=PF.get("updated"), holdings_source=PF.get("source"),
                  positions=len(H), former=len(FR), markets=mstat, symbols_with_bars=len(bars), errors=errors[:60], fetch_failures=len(berr),
                  inbox=PF.get("last_inbox"), names=PF["names"], usd_per={k: round(v, 6) for k, v in rates.items()})
    out = dict(holdings=H, former=FR, monthly=M, flows=flows, flow_picks=picks, etfs=ETF, exposure=EXP, board_status=[status])

    if args.dry:
        os.makedirs("data/preview", exist_ok=True)
        for k, v in out.items():
            json.dump(v, open("data/preview/%s.json" % k, "w"), ensure_ascii=False, separators=(",", ":"))
        json.dump(dict(fetch_errors=berr), open("data/preview/fetch_errors.json", "w"), indent=0)
        print("dry run written to data/preview/")
        return 0

    # ------------------------------------------------ 6. bake into the page
    s = page
    for k, v in out.items():
        enc = json.dumps(v, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")  # never close the script tag
        i = s.find('"%s":[' % k)
        if i >= 0:
            j = json.JSONDecoder().raw_decode(s, i + len('"%s":' % k))[1]
            s = s[:i + len('"%s":' % k)] + enc + s[j:]
        else:
            anchor = "var datasets={"
            assert s.count(anchor) == 1
            s = s.replace(anchor, anchor + '"%s":%s,' % (k, enc), 1)
    stamp = "Data last extracted: %s, %s UTC (prices to %s close)" % (t0.strftime("%-d %B %Y"), t0.strftime("%H:%M"),
                                                                       datetime.date.fromisoformat(data_date).strftime("%-d %B"))
    s, nlab = re.subn(r'(<p class="hs-extracted" id="stock-extracted-(?:top|strategy)"><span class="dot"></span>)[^<]*(</p>)', r"\g<1>" + stamp + r"\g<2>", s)
    if nlab != 2:
        errors.append("extracted labels found: %d" % nlab)
    open(PAGE, "w", encoding="utf-8").write(s)
    print("baked:", {k: len(v) for k, v in out.items()}, "| errors:", len(errors), "| took", now_utc() - t0)
    for e in errors[:30]:
        print("  ", e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
