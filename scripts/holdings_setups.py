#!/usr/bin/env python3
"""Daily rebuild of the two holdings tables on the My holdings tab -> data/holdings_setups.json and data/holdings_log.json (NEW files).

  * "Holdings – setups as of the latest close": which of my stock holdings had one of the twelve setups of "Setups before 20% rises"
    on one of their last 10 completed trading days, with the same levels, estimate, target, typical date and deadline as Table C.
  * "Holdings – setups before a fall": the same for the fall rules that passed the test in data/holdings_study.json.

Readings: TradingView's screener (type, latest close, RSI, MACD, averages, ATR, 52-week high, volume, market value, next earnings) for every
holding; the history behind the rules from the same adjusted Yahoo daily bars as the rest of the board. A holding whose latest Yahoo close
differs from TradingView's by more than 1%, or whose latest bar is not its market's latest trading day, is flagged "data mismatch" and skipped.
Only completed daily candles are used. This script only READS the existing setups files and modules; it never writes to them.

  python3 scripts/holdings_setups.py [--dump FILE (offline test)] [--force] [--now ISO]
"""
import argparse
import datetime
import json
import os
import sys
import zoneinfo

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import board_lib as L
import exchange_calendar as XC
import holdings_falls as HF
import setups_daily as SDLY          # read-only: the 'why it matches' texts
import setups_data as SD
import setups_lib as SL
import setups_model as SM

STO = zoneinfo.ZoneInfo("Europe/Stockholm")
OUT, LOG, STUDY, HSTUDY, PORT = "data/holdings_setups.json", "data/holdings_log.json", "data/setups_study.json", "data/holdings_study.json", "data/portfolio.json"
SCHEMA = 1
TV_COLS = ["name", "description", "type", "exchange", "country", "currency", "close", "open", "high", "low", "volume", "RSI", "MACD.macd", "MACD.signal",
           "ATR", "SMA50", "SMA200", "price_52_week_high", "average_volume_60d_calc", "market_cap_basic", "earnings_release_next_date"]
TV_MIN = ["name", "description", "type", "exchange", "country", "currency", "close", "volume", "RSI", "MACD.macd", "MACD.signal", "SMA50", "SMA200",
          "market_cap_basic", "earnings_release_next_date"]
MISMATCH = 0.01
fmt = SDLY.fmt


def tv_scan(syms):
    """TradingView screener readings for the given symbols. Falls back to a shorter column list if a column is refused."""
    for cols in (TV_COLS, TV_MIN):
        try:
            out = {}
            for i in range(0, len(syms), 200):
                j = L.retry(L.scan, {"symbols": {"tickers": syms[i:i + 200]}, "columns": cols})
                for x in j.get("data") or []:
                    d = dict(zip(cols, x["d"]))
                    out[x["s"]] = d
            return out, cols
        except Exception as e:
            last = e
    raise last


def num(x):
    return float(x) if isinstance(x, (int, float)) and not (isinstance(x, float) and np.isnan(x)) else None


def runs_in_window(df, keys, W=HF.WINDOW):
    """For each setup key: the days it matched within the last W bars and the start of each run. Returns {k: dict}."""
    n = len(df)
    lo = max(0, n - W)
    out = {}
    for k in keys:
        f = df[k].values.astype(bool)
        days = [i for i in range(lo, n) if f[i]]
        if not days:
            continue
        starts = []
        for i in days:
            if i == 0 or not f[i - 1]:
                starts.append(i)
        first = days[0]
        run_start = first
        while run_start > 0 and f[run_start - 1]:
            run_start -= 1
        out[k] = dict(days=days, starts_in=[s for s in starts if s >= lo], run_start=run_start, first=first, last=days[-1], today=bool(f[n - 1]))
    return out


def vbucket(edges, rv):
    if rv is None or np.isnan(rv):
        return None
    e = np.array(edges, float)
    e[0], e[-1] = -1, 99
    return int(np.clip(np.searchsorted(e, rv, side="right") - 1, 0, len(e) - 2))


def cond_list(rules, k, r, valfn):
    out = []
    for ck, text, _ in rules[k]["conds"]:
        ok = bool(r["%s_%s" % (k, ck)])
        out.append(dict(t=text, ok=ok, v=valfn(k, ck, r) if valfn else ""))
    return out


def fall_value(k, ck, r):
    pc = lambda x: "%+.1f%%" % (x * 100)
    try:
        return {"t50": "%s vs 50-day" % pc(r.vs50), "t200": "%s vs 200-day" % pc(r.vs200),
                "macd": "MACD histogram %+.2f%% of price (day before %+.2f%%)" % (r.macdh * 100, r.macdh_1 * 100),
                "low40": "close %.4g, lowest close of previous 40 sessions %.4g" % (r.c, r.ll40), "vol": "volume %.1f× average" % r.vr,
                "fail": "close %.4g, 40-day high %.4g" % (r.c, r.hh40), "rsi": "RSI %.0f" % r.rsi, "slope": "50-day %s over 10 sessions" % pc(r.slope50),
                "atr5": "daily range %.1f%%" % (r.atr * 100), "ext": "%s vs 50-day" % pc(r.vs50),
                "wash": "%.0f%% of the market's stocks above their 50-day average" % (r.breadth * 100)}.get(ck, "")
    except Exception:
        return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--now")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--log", default=LOG)
    ap.add_argument("--hstudy", default=HSTUDY)
    a = ap.parse_args()
    now = datetime.datetime.fromisoformat(a.now) if a.now else datetime.datetime.now(datetime.timezone.utc)
    local = now.astimezone(STO)
    prev = json.load(open(a.out)) if os.path.exists(a.out) else None
    forced = a.force or os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
    if not forced:
        if local.hour * 60 + local.minute < 6 * 60 + 15:
            print("before 06:15 Stockholm; a later run will do it"); return
        if prev and prev.get("built_local", "")[:10] == local.date().isoformat():
            print("already rebuilt today"); return
    study = json.load(open(STUDY))
    hstudy = json.load(open(a.hstudy)) if os.path.exists(a.hstudy) else None
    stats = {(s["setup"], s["market"]): s for s in study["stats"]}
    srate = lambda k: (stats[(k, "All")]["hits"] / stats[(k, "All")]["n"]) if (k, "All") in stats and stats[(k, "All")].get("rate") is not None else None
    model = study.get("model")
    PF = json.load(open(PORT))
    LOGD = json.load(open(a.log)) if os.path.exists(a.log) else []
    pos = {p["sym"]: p for p in PF["positions"]}
    log_syms = sorted({e["sym"] for e in LOGD if e.get("status") == "open"} - set(pos))

    # ---- TradingView readings
    if a.dump:
        D = SD.load(a.dump)
        U = D["universe"]
        rawb = {s: dict(bars=list(zip([t * 86400 for t in v["t"]], v["o"], v["h"], v["l"], v["c"], v["v"])), tz=v["tz"]) for s, v in D["bars"].items()}
        uni = {d["sym"]: d for rows in U.values() for d in rows}
        tv = {}
        for s in list(pos) + log_syms:
            if s in rawb:
                u = uni[s]
                tv[s] = dict(name=u["name"], description=u["description"], type="stock", exchange=s.split(":")[0], country=u.get("country"), currency=u.get("currency"),
                             close=rawb[s]["bars"][-1][4], market_cap_basic=u.get("market_cap_basic"), earnings_release_next_date=u.get("earnings_release_next_date"))
            elif pos.get(s, {}).get("market", "").endswith("ETF"):
                tv[s] = dict(type="fund", description=pos[s]["name"], exchange=s.split(":")[0])
        tv_cols = TV_COLS
    else:
        tv, tv_cols = tv_scan(list(pos) + log_syms)
        if len(tv) < 0.5 * len(pos):
            raise SystemExit("TradingView returned readings for only %d of %d holdings; keeping the last good data" % (len(tv), len(pos)))
        U = SD.universe()
        rawb = None

    covered, not_covered = {}, []
    for s, p in pos.items():
        t = tv.get(s)
        ex = s.split(":")[0]
        if not t:
            not_covered.append(dict(sym=s, name=p["name"], reason="not found on TradingView")); continue
        if (t.get("type") not in ("stock", "dr")) or p.get("market", "").endswith("ETF"):
            not_covered.append(dict(sym=s, name=p["name"], reason="fund or ETF: the setups are measured on company shares")); continue
        mk = HF.MKT_OF_EXCHANGE.get(ex)
        if not mk:
            not_covered.append(dict(sym=s, name=p["name"], reason="listed on %s, a market the study does not cover" % ex)); continue
        covered[s] = dict(sym=s, name=p["name"], market=mk, tv=t)
    for s in log_syms:
        t = tv.get(s)
        ex = s.split(":")[0]
        if t and HF.MKT_OF_EXCHANGE.get(ex):
            covered.setdefault(s, dict(sym=s, name=t.get("description") or s, market=HF.MKT_OF_EXCHANGE[ex], tv=t, log_only=True))
    need = sorted({c["market"] for c in covered.values()})

    # ---- daily bars: the stock list of each needed market (for the market washout) and every covered holding
    if rawb is None:
        Uneed = {mk: U[mk] for mk in need if mk in U}
        rb, berr = SD.fetch_all(Uneed, years=2)
        rawb = {s: dict(bars=v["bars"], tz=v["tz"]) for s, v in rb.items()}
        for s, c in covered.items():
            if s in rawb:
                continue
            try:
                B, yt, tz = SD.bars_adj(dict(sym=s, close=c["tv"].get("close"), country=c["tv"].get("country")), years=2)
                rawb[s] = dict(bars=B, tz=tz)
            except Exception as e:
                c["err"] = str(e)[:140]
    uni_mk = {d["sym"]: mk for mk, rows in U.items() for d in rows if mk in need}
    bars, last_raw = {}, {}
    for s, v in rawb.items():
        B = v["bars"]
        if not B:
            continue
        last_raw[s] = B[-1]
        tz = zoneinfo.ZoneInfo(v["tz"] or "UTC")
        today_ex = now.astimezone(tz).date()
        while B and datetime.datetime.fromtimestamp(B[-1][0], datetime.timezone.utc).date() >= today_ex:
            B = B[:-1]   # a bar dated today is not finished
        if len(B) < 260:
            continue
        bars[s] = dict(t=[b[0] // 86400 for b in B], o=[b[1] for b in B], h=[b[2] for b in B], l=[b[3] for b in B], c=[b[4] for b in B], v=[b[5] for b in B])
    Fu = {s: SL.features(s, bars[s]) for s in uni_mk if s in bars}
    SL.add_washout(Fu, uni_mk)
    br = pd.concat([pd.DataFrame({"mk": uni_mk[s], "date": df.date.values, "breadth": df.breadth.values}) for s, df in Fu.items()]).drop_duplicates(["mk", "date"]).set_index(["mk", "date"]).breadth
    last_bar = {}
    for mk in need:
        ds = [Fu[s].date.iloc[-1] for s in Fu if uni_mk[s] == mk]
        if ds:
            last_bar[mk] = pd.Series(ds).mode().iloc[0]
    size_cut = {mk: sorted([d.get("market_cap_basic") or 0 for d in U[mk]], reverse=True)[29] for mk in need if mk in U and len(U[mk]) >= 30}

    rows_up, rows_fall, mism, notes = [], [], [], []
    passed = (hstudy or {}).get("fall", {}).get("passed", [])
    fmodels = (hstudy or {}).get("fall", {}).get("models", {})
    frules = (hstudy or {}).get("fall", {}).get("rules", {})
    edges = (hstudy or {}).get("vb_edges")
    frames, evaluated = {}, 0
    for s, c in covered.items():
        mk, t = c["market"], c["tv"]
        if s not in bars:
            if not c.get("log_only"):
                not_covered.append(dict(sym=s, name=c["name"], reason="no daily history from Yahoo matching TradingView's price" + (" (%s)" % c["err"] if c.get("err") else "")))
            continue
        df = Fu[s].copy() if s in Fu else SL.features(s, bars[s])
        if s not in Fu:
            df["breadth"] = br.reindex(pd.MultiIndex.from_arrays([[mk] * len(df), df.date.values])).values
            df["wash"] = (df.breadth < SL.WASH_BELOW).fillna(False)
        df = SL.apply_rules(df)
        for col in ("macdh", "h"):
            df[col + "_1"] = df[col].shift(1)
        df = HF.apply_fall_rules(df)
        frames[s] = df
        if c.get("log_only"):
            continue
        # ---- cross-check against TradingView
        tvc, lr = num(t.get("close")), last_raw.get(s)
        why = None
        if tvc and lr and abs(lr[4] / tvc - 1) > MISMATCH:
            why = "latest close %.4g (Yahoo) against %.4g (TradingView): %+.1f%%" % (lr[4], tvc, (lr[4] / tvc - 1) * 100)
        elif mk in last_bar and df.date.iloc[-1] != last_bar[mk]:
            why = "latest daily bar %s, the market's latest trading day is %s" % (df.date.iloc[-1].date(), last_bar[mk].date())
        elif not tvc:
            why = "no close from TradingView"
        if why:
            mism.append(dict(sym=s, name=c["name"], market=mk, reason=why)); continue
        evaluated += 1
        n = len(df)
        r_now = df.iloc[-1]
        cap = num(t.get("market_cap_basic"))
        size = "Large" if (cap and mk in size_cut and cap >= size_cut[mk]) else "Mid"
        nxt = num(t.get("earnings_release_next_date"))
        nxt_d = datetime.datetime.fromtimestamp(nxt, datetime.timezone.utc).date().isoformat() if nxt and nxt > now.timestamp() else None
        tvr = dict(close=tvc, rsi=num(t.get("RSI")), macdh=((num(t.get("MACD.macd")) - num(t.get("MACD.signal"))) / tvc if num(t.get("MACD.macd")) is not None and num(t.get("MACD.signal")) is not None and tvc else None),
                   atr=(num(t.get("ATR")) / tvc if num(t.get("ATR")) and tvc else None), sma50=num(t.get("SMA50")), sma200=num(t.get("SMA200")),
                   hi52=num(t.get("price_52_week_high")), vr=(num(t.get("volume")) / num(t.get("average_volume_60d_calc")) if num(t.get("volume")) and num(t.get("average_volume_60d_calc")) else None))
        comp = dict(close=fmt(r_now.c), rsi=fmt(r_now.rsi), macdh=fmt(r_now.macdh), atr=fmt(r_now.atr), sma50=fmt(r_now.sma50), sma200=fmt(r_now.sma200), hi52=fmt(r_now.hi52), vr=fmt(r_now.vr))
        common = dict(sym=s, name=c["name"], market=mk, cur=t.get("currency"), size=size, last_date=r_now.date.strftime("%Y-%m-%d"), last_close=fmt(r_now.c),
                      earnings_next=nxt_d, tv={k: fmt(v) for k, v in tvr.items()}, computed=comp)
        dates = df.date.dt.strftime("%Y-%m-%d").values

        # ---- upside: the twelve setups
        W = runs_in_window(df, SL.ORDER)
        if any(w["starts_in"] for w in W.values()):
            sd = min(st for w in W.values() for st in w["starts_in"])
            rsd = df.iloc[sd]
            ks = sorted(W, key=lambda k: (-(srate(k) if srate(k) is not None else -1), SL.ORDER.index(k)))
            best = ks[0]
            sd_date = datetime.date.fromisoformat(dates[sd])
            est = SM.estimate(model, set(ks), rsd, mk, size, srate(best)) if model else None
            dq = (stats.get((best, "All")) or {}).get("days_q")
            lv = SL.levels(best, df.iloc[W[best]["first"]])
            target = float(rsd.c) * (1 + SL.RISE)
            after = df.c.values[sd + 1:]
            mx = float(after.max()) if len(after) else None
            status = ("reached" if mx and mx >= target else "below" if lv["invalid"] and r_now.c < lv["invalid"] else "still" if any(W[k]["today"] for k in ks) else "gone")
            setups = []
            for k in ks:
                w = W[k]
                setups.append(dict(setup=k, rate=srate(k), n=(stats.get((k, "All")) or {}).get("n"), run_start=dates[w["run_start"]], first=dates[w["first"]], last=dates[w["last"]],
                                   days=[dates[i] for i in w["days"]], today=w["today"], conds=cond_list(SL.SETUPS, k, r_now, SDLY.cond_value),
                                   levels={kk: fmt(vv) for kk, vv in SL.levels(k, df.iloc[w["first"]]).items()}))
            rows_up.append(dict(common, setup_day=dates[sd], setup_close=fmt(rsd.c), days_since=int(n - 1 - sd), best=best, setups=setups,
                                est=(dict(est, n=(stats.get((best, "All")) or {}).get("n"), setup=best) if est else None),
                                target=fmt(target), typ=([XC.trading_days_after(mk, sd_date, max(1, int(round(q)))).isoformat() for q in dq] if dq else None),
                                deadline=XC.trading_days_after(mk, sd_date, SL.HORIZON).isoformat(), since=fmt(r_now.c / rsd.c - 1), max_since=fmt(mx),
                                levels={kk: fmt(vv) for kk, vv in lv.items()}, status=status, vb=(vbucket(edges, rsd.rv20) if edges else None)))

        # ---- falls: only the rules that passed the test
        Wf = runs_in_window(df, passed) if passed else {}
        if any(w["starts_in"] for w in Wf.values()):
            sd = min(st for w in Wf.values() for st in w["starts_in"])
            rsd = df.iloc[sd]
            r10 = lambda k: (frules.get(k, {}).get("results", {}).get("all", {}).get("fall10", {}).get("rate"))
            r20 = lambda k: (frules.get(k, {}).get("results", {}).get("all", {}).get("fall20", {}).get("rate"))
            ks = sorted(Wf, key=lambda k: (-(r10(k) or -1), HF.FALL_ORDER.index(k)))
            best = ks[0]
            sd_date = datetime.date.fromisoformat(dates[sd])
            lvl = float(HF.fall_level(df).iloc[sd])
            e10 = HF.estimate(fmodels.get("fall10"), set(ks), rsd, mk, size, r10(best))
            e20 = HF.estimate(fmodels.get("fall20"), set(ks), rsd, mk, size, r20(best))
            after = df.c.values[sd + 1:]
            mn1 = float(after[:HF.M1].min()) if len(after) else None
            status = ("fell10" if mn1 and mn1 <= rsd.c * (1 - HF.FALL1) else "above" if r_now.c > lvl else "still" if any(Wf[k]["today"] for k in ks) else "gone")
            rows_fall.append(dict(common, setup_day=dates[sd], setup_close=fmt(rsd.c), days_since=int(n - 1 - sd), best=best,
                                  rules=[dict(rule=k, rate10=r10(k), rate20=r20(k), n=frules.get(k, {}).get("results", {}).get("all", {}).get("fall10", {}).get("n"),
                                              run_start=dates[Wf[k]["run_start"]], days=[dates[i] for i in Wf[k]["days"]], today=Wf[k]["today"],
                                              conds=cond_list(HF.FALL_RULES, k, r_now, fall_value)) for k in ks],
                                  est10=e10, est20=e20, level=fmt(lvl), deadline=XC.trading_days_after(mk, sd_date, HF.M3).isoformat(),
                                  since=fmt(r_now.c / rsd.c - 1), min_since=(fmt(float(after.min())) if len(after) else None), status=status,
                                  vb=(vbucket(edges, rsd.rv20) if edges else None)))

    # ---- the log (one entry per stock, table and setup day) and the live records
    have = {(e["kind"], e["sym"], e["setup_day"]) for e in LOGD}
    for r in rows_up:
        if ("up", r["sym"], r["setup_day"]) not in have:
            LOGD.append(dict(kind="up", sym=r["sym"], name=r["name"], market=r["market"], setup_day=r["setup_day"], setups=[x["setup"] for x in r["setups"]], best=r["best"],
                             entry_close=r["setup_close"], est=(r["est"]["est"] if r["est"] else None), hist=srate(r["best"]), first_seen=local.date().isoformat(), status="open"))
    for r in rows_fall:
        if ("fall", r["sym"], r["setup_day"]) not in have:
            LOGD.append(dict(kind="fall", sym=r["sym"], name=r["name"], market=r["market"], setup_day=r["setup_day"], rules=[x["rule"] for x in r["rules"]], best=r["best"],
                             entry_close=r["setup_close"], est10=(r["est10"]["est"] if r["est10"] else None), est20=(r["est20"]["est"] if r["est20"] else None),
                             hist10=r["rules"][0]["rate10"], first_seen=local.date().isoformat(), status="open"))
    for e in LOGD:
        if e["status"] != "open" or e["sym"] not in frames:
            continue
        df = frames[e["sym"]]
        after = df[df.date > pd.Timestamp(e["setup_day"])].c.values
        if e["kind"] == "up":
            w = after[:SL.HORIZON]
            if len(w) and w.max() >= e["entry_close"] * (1 + SL.RISE):
                e.update(status="hit", resolved_after=int(np.argmax(w >= e["entry_close"] * (1 + SL.RISE))) + 1)
            elif len(w) >= SL.HORIZON:
                e.update(status="missed", gain=round(float(w.max() / e["entry_close"] - 1) * 100, 1))
        else:
            w1, w3 = after[:HF.M1], after[:HF.M3]
            if e.get("fall10") is None and ((len(w1) and w1.min() <= e["entry_close"] * (1 - HF.FALL1)) or len(w1) >= HF.M1):
                e["fall10"] = int(bool(len(w1) and w1.min() <= e["entry_close"] * (1 - HF.FALL1)))
            if e.get("fall20") is None and ((len(w3) and w3.min() < e["entry_close"] * (1 - HF.FALL3)) or len(w3) >= HF.M3):
                e["fall20"] = int(bool(len(w3) and w3.min() < e["entry_close"] * (1 - HF.FALL3)))
            if e.get("fall10") is not None and e.get("fall20") is not None:
                e["status"] = "closed"
    up_done = [e for e in LOGD if e["kind"] == "up" and e["status"] in ("hit", "missed")]
    live_up = dict(logged=sum(e["kind"] == "up" for e in LOGD), resolved=len(up_done), hits=sum(e["status"] == "hit" for e in up_done))
    ests = [e for e in up_done if e.get("est") is not None]
    live_up.update(avg_est=(float(np.mean([e["est"] for e in ests])) if ests else None), actual=(float(np.mean([e["status"] == "hit" for e in ests])) if ests else None), n_est=len(ests))
    live_up["warn"] = bool(len(ests) >= 30 and live_up["actual"] < live_up["avg_est"] - 0.10)
    f_done = [e for e in LOGD if e["kind"] == "fall" and e.get("fall10") is not None]
    live_fall = dict(logged=sum(e["kind"] == "fall" for e in LOGD), resolved=len(f_done), hits=sum(e["fall10"] for e in f_done),
                     rate=(float(np.mean([e["fall10"] for e in f_done])) if f_done else None),
                     hist=(float(np.mean([e["hist10"] for e in f_done if e.get("hist10") is not None])) if any(e.get("hist10") is not None for e in f_done) else None))
    live_fall["warn"] = bool(len(f_done) >= 20 and live_fall["hist"] is not None and live_fall["rate"] < live_fall["hist"] - 0.10)

    for mk in need:
        if prev and mk in last_bar and (prev.get("last_bar") or {}).get(mk) == last_bar[mk].strftime("%Y-%m-%d"):
            notes.append("%s: no new daily candle since the last rebuild (market closed)" % mk)
    out = dict(schema=SCHEMA, built=now.isoformat(timespec="minutes"), built_local=local.isoformat(timespec="minutes"), test=bool(a.dump),
               last_bar={mk: d.strftime("%Y-%m-%d") for mk, d in last_bar.items()}, window=HF.WINDOW,
               checked=evaluated, held=len(pos),
               up=sorted(rows_up, key=lambda r: -(srate(r["best"]) or 0)), fall=rows_fall, not_covered=sorted(not_covered, key=lambda x: x["name"]), mismatch=mism,
               fall_passed=passed, live_up=live_up, live_fall=live_fall, notes=notes, tv_columns=tv_cols,
               calendar={mk: XC.upcoming(mk, last_bar[mk].date(), 140) for mk in last_bar})
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    json.dump(out, open(a.out, "w"), separators=(",", ":"))
    json.dump(LOGD, open(a.log, "w"), separators=(",", ":"))
    print("holdings checked %d of %d; up rows %d, fall rows %d, mismatches %d, not covered %d; fall rules in use %s" % (
        out["checked"], len(pos), len(rows_up), len(rows_fall), len(mism), len(not_covered), passed))


if __name__ == "__main__":
    main()
