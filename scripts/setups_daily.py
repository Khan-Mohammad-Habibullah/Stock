#!/usr/bin/env python3
"""Daily rebuild of the current matches for "Setups before 15% rises" -> data/setups.json (Table C, the "Below the 95% bar" list and the live record).

Every stock whose latest completed candle meets ALL conditions of a setup is stored, for every setup. The page shows only the setups that pass the 95% bar
in the latest study in Table C and puts the others in the collapsed "Below the 95% bar" list.

Runs from GitHub Actions at 06:00 Stockholm time, Tuesday to Saturday (after all seven markets have closed). Only completed daily
candles are used: a bar dated today in its exchange's time zone is dropped.

  python3 scripts/setups_daily.py [--dump FILE] [--force] [--out data/setups.json] [--study data/setups_study.json] [--log data/setups_log.json]
"""
import argparse
import datetime
import json
import os
import statistics
import sys
import zoneinfo

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import setups_data as SD
import setups_lib as SL
import setups_study as SS

STO = zoneinfo.ZoneInfo("Europe/Stockholm")
KEEP_REMOVED = 5          # rebuilds a removed name stays listed
SCHEMA = 2               # 2 = 15% rises, all eight setups, complete matches only (an older file is recomputed in full, never carried)
LIVE_FLAG_MIN = 20        # resolved cases before a live record below the bar is flagged
STALE_DAYS = 6            # a stock whose last bar is older than its market's is left out


def fmt(x):
    return float("%.5g" % x) if x is not None and not (isinstance(x, float) and np.isnan(x)) else None


def cond_value(k, key, r):
    """The number behind each condition, for 'why it matches'."""
    pc = lambda x: "%+.1f%%" % (x * 100)
    g = lambda x: "%.4g" % x
    try:
        m = {
            ("base", "brk"): "close %s, 40-day high %s (%s)" % (g(r.c), g(r.hh40), pc(r.c / r.hh40 - 1)),
            ("base", "tight"): "40-day range %.0f%%" % ((r.hh40 - r.ll40) / r.hh40 * 100),
            ("base", "vol"): "volume %.1f× average" % r.vr,
            ("base", "t200"): "%s vs 200-day" % pc(r.vs200),
            ("base", "x50"): "50-day %s vs 200-day" % pc(r.sma50 / r.sma200 - 1),
            ("base", "atr"): "daily range %.1f%%" % (r.atr * 100),
            ("pull", "rise50"): "50-day %s over 10 sessions" % pc(r.slope50),
            ("pull", "t200"): "%s vs 200-day" % pc(r.vs200),
            ("pull", "near50"): "%s vs 50-day" % pc(r.vs50),
            ("pull", "rsi"): "RSI %.0f" % r.rsi,
            ("pull", "hi"): "%s from 52-week high" % pc(r.from52h),
            ("pull", "atr"): "daily range %.1f%%" % (r.atr * 100),
            ("squeeze", "squeeze"): "width %.1f%%, narrower than %d%% of last 120 sessions" % (r.bbw * 100, round((1 - r.bbw_pct) * 100)),
            ("squeeze", "brk"): "close %s, 20-day high %s (%s)" % (g(r.c), g(r.hh20), pc(r.c / r.hh20 - 1)),
            ("squeeze", "vol"): "volume %.1f× average" % r.vr,
            ("squeeze", "t50"): "%s vs 50-day" % pc(r.vs50),
            ("squeeze", "atr"): "daily range %.1f%%" % (r.atr * 100),
            ("oversold", "deep"): "%s from 52-week high" % pc(r.from52h),
            ("oversold", "rsi"): "RSI %.0f" % r.rsi,
            ("oversold", "macd"): "MACD histogram %+.2f%% of price (day before %+.2f%%)" % (r.macdh * 100, r.macdh_1 * 100),
            ("oversold", "up"): "close %s, previous high %s" % (g(r.c), g(r.h_1)),
            ("oversold", "vol"): "volume %.1f× average" % r.vr,
            ("high52", "brk"): "close %s, 252-day high %s (%s)" % (g(r.c), g(r.hh252), pc(r.c / r.hh252 - 1)),
            ("high52", "vol"): "volume %.1f× average" % r.vr,
            ("high52", "x50"): "50-day %s vs 200-day" % pc(r.sma50 / r.sma200 - 1),
        }
        alias = {"brkhv": "base", "pullhv": "pull", "sqzhv": "squeeze"}.get(k)
        return m.get((k, key)) or (m.get((alias, key)) if alias else None) or m.get(("pull", key), "")
    except Exception:
        return ""


def to_local_date(ts_days, tz):
    return datetime.date.fromordinal(datetime.date(1970, 1, 1).toordinal() + int(ts_days))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--now")
    ap.add_argument("--out", default="data/setups.json")
    ap.add_argument("--study", default="data/setups_study.json")
    ap.add_argument("--log", default="data/setups_log.json")
    a = ap.parse_args()
    now = datetime.datetime.fromisoformat(a.now) if a.now else datetime.datetime.now(datetime.timezone.utc)
    local = now.astimezone(STO)
    prev = json.load(open(a.out)) if os.path.exists(a.out) else None
    forced = a.force or os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
    if not forced:
        if local.hour < 6:
            print("before 06:00 Stockholm; the later cron run will do it"); return
        if prev and prev.get("built_local", "")[:10] == local.date().isoformat():
            print("already rebuilt today"); return

    # ---- stock list and daily bars
    if a.dump:
        D = SD.load(a.dump)
        U, err = D["universe"], D["errors"]
        raw = {s: dict(bars=list(zip([t * 86400 for t in v["t"]], v["o"], v["h"], v["l"], v["c"], v["v"])), tz=v["tz"]) for s, v in D["bars"].items()}
    else:
        U = SD.universe()
        raw, err = SD.fetch_all(U, years=6)
    uni = {d["sym"]: d for rows in U.values() for d in rows}
    bars, skipped = {}, []
    for s, v in raw.items():
        B = v["bars"]
        tz = zoneinfo.ZoneInfo(v["tz"] or "UTC")
        today_ex = now.astimezone(tz).date()
        while B and datetime.datetime.fromtimestamp(B[-1][0], datetime.timezone.utc).date() >= today_ex:   # session open falls on the same UTC date as the local date
            B = B[:-1]   # a bar dated today is not finished
        if len(B) < 250:
            err[s] = "only %d completed bars" % len(B); continue
        bars[s] = dict(t=[b[0] // 86400 for b in B], o=[b[1] for b in B], h=[b[2] for b in B], l=[b[3] for b in B], c=[b[4] for b in B], v=[b[5] for b in B])
    F = {}
    for s, b in bars.items():
        df = SL.apply_rules(SL.features(s, b))
        for col in ("macdh", "h"):
            df[col + "_1"] = df[col].shift(1)
        F[s] = df
    # ---- each market's latest completed day (the most common last date among its stocks)
    last_bar = {}
    for mk, rows in U.items():
        ds = [F[d["sym"]].date.iloc[-1] for d in rows if d["sym"] in F]
        if ds:
            last_bar[mk] = pd.Series(ds).mode().iloc[0].strftime("%Y-%m-%d")
    study = json.load(open(a.study)) if os.path.exists(a.study) else None
    rate = {}
    if study:
        for st in study["stats"]:
            rate[(st["setup"], st["market"])] = st
    old_schema = bool(prev) and prev.get("schema") != SCHEMA
    if old_schema:
        prev["candidates"] = [c for c in prev.get("candidates", []) if c.get("complete")]   # one-condition-short rows no longer exist
    prev_c = {(c["sym"], c["setup"]): c for c in (prev or {}).get("candidates", [])}
    seq = (prev or {}).get("seq", 0) + 1
    today_s = local.date().isoformat()
    carried, new_c, notes_err = [], [], []
    for mk, rows in U.items():
        have = [d for d in rows if d["sym"] in F]
        if mk not in last_bar or len(have) < 0.6 * len(rows):
            carried.append(mk); notes_err.append("%s: too little data (%d of %d stocks), kept the previous list" % (mk, len(have), len(rows)))
            new_c += [c for c in (prev or {}).get("candidates", []) if c["market"] == mk]; continue
        if prev and not old_schema and prev.get("last_bar", {}).get(mk) == last_bar[mk]:
            carried.append(mk)   # no new daily candle: the market was closed (holiday), keep its candidates
            new_c += [c for c in prev["candidates"] if c["market"] == mk]; continue
        for d in have:
            s = d["sym"]; df = F[s]; r = df.iloc[-1]
            if (pd.Timestamp(last_bar[mk]) - r.date).days > STALE_DAYS:
                continue
            for k in SL.ORDER:
                total = len(SL.SETUPS[k]["conds"])
                met = int(r[k + "_met"])
                if met < total:
                    continue
                complete = True
                conds = []
                for ck, text, _ in SL.SETUPS[k]["conds"]:
                    ok = bool(r["%s_%s" % (k, ck)])
                    conds.append(dict(t=text, ok=ok, v=cond_value(k, ck, r) if True else ""))
                lv = SL.levels(k, r)
                # this stock's last earlier signal of the same setup, before the current run of consecutive days
                flag = df[k].values
                j = len(flag) - 1
                while j >= 0 and flag[j] and complete:
                    j -= 1
                prior = np.where(flag[: j + 1 if complete else len(flag) - 1])[0]
                last_prev = None
                if len(prior):
                    q = df.iloc[prior[-1]]
                    pk = SL.peak_info(df.c.values, int(prior[-1]))
                    oc = "pending" if pd.isna(q.hit) else ("hit" if q.hit == 1 else "missed")
                    last_prev = dict(date=q.date.strftime("%Y-%m-%d"), price=fmt(q.c), outcome=oc, gain=(round(pk["gain"] * 100, 1) if pk else None))
                nxt = d.get("earnings_release_next_date")
                nxt_d = datetime.datetime.fromtimestamp(nxt, datetime.timezone.utc).date().isoformat() if nxt and nxt > now.timestamp() else None
                key = (s, k)
                old = prev_c.get(key)
                first_seen = old["first_seen"] if (old and old.get("complete") and complete) else today_s
                entry_close = old["entry_close"] if (old and old.get("complete") and complete) else fmt(r.c)
                new_c.append(dict(
                    sym=s, name=d["description"] or d["name"], market=mk, size=d["size"], rank=d["rank"], cur=d["currency"], setup=k,
                    met=met, total=total, complete=complete, bar_date=r.date.strftime("%Y-%m-%d"), close=fmt(r.c),
                    conds=conds, why="; ".join(c["v"] for c in conds if c["ok"] and c["v"]),
                    missing=[c["t"] for c in conds if not c["ok"]],
                    breakout=fmt(lv["breakout"]), support=fmt(lv["support"]), resistance=fmt(lv["resistance"]), invalid=fmt(lv["invalid"]),
                    rate=(rate.get((k, "All")) or {}).get("rate"), rate_mkt=(rate.get((k, mk)) or {}).get("rate"),
                    base=(rate.get((k, "All")) or {}).get("matched"), n_hist=(rate.get((k, "All")) or {}).get("n"),
                    last_prev=last_prev, earnings_next=nxt_d,
                    first_seen=first_seen, entry_close=entry_close, new=bool(prev) and complete and first_seen == today_s))
    out_c = list(new_c)   # carried markets already contributed their previous rows through new_c above
    seen = set(); fin = []
    for c in out_c:
        kk = (c["sym"], c["setup"])
        if kk not in seen:
            seen.add(kk); fin.append(c)
    # ---- removed names: complete before, gone now (only for markets that were recomputed)
    removed = [dict(x) for x in (prev or {}).get("removed", []) if seq - x["seq"] < KEEP_REMOVED]
    now_keys = {(c["sym"], c["setup"]) for c in fin if c["complete"]}
    for (s, k), oc in prev_c.items():
        if not oc.get("complete") or (s, k) in now_keys or oc["market"] in carried or s not in F:
            continue
        df = F[s]
        after = df[df.date > pd.Timestamp(oc["first_seen"])]
        reason = "conditions no longer met"
        if len(after):
            if after.c.max() >= oc["entry_close"] * (1 + SL.RISE):
                reason = "reached +15%"
            elif oc.get("invalid") and (after.c < oc["invalid"]).any():
                reason = "setup failed (closed below its invalidation level)"
        removed.append(dict(sym=s, name=oc["name"], market=oc["market"], setup=k, removed_on=today_s, seq=seq, reason=reason,
                            first_seen=oc["first_seen"], entry_close=oc["entry_close"], cur=oc["cur"], last_close=fmt(df.c.iloc[-1])))
    # ---- the log of every complete candidate and what became of it
    LOG = json.load(open(a.log)) if os.path.exists(a.log) else []
    logged = {(e["sym"], e["setup"]): e for e in LOG}   # latest entry per pair
    for c in fin:
        if not c["complete"]:
            continue
        e = logged.get((c["sym"], c["setup"]))
        if e is not None:
            df = F[c["sym"]]
            n_since = int((df.date > pd.Timestamp(e["first_seen"])).sum())
            if n_since < SL.HORIZON:
                continue   # the earlier entry is still within its 42 sessions
        entry = dict(sym=c["sym"], name=c["name"], market=c["market"], setup=c["setup"], first_seen=c["first_seen"], entry_close=c["entry_close"],
                     invalid=c["invalid"], cur=c["cur"], status="open")
        LOG.append(entry); logged[(c["sym"], c["setup"])] = entry
    for e in LOG:
        if e["status"] != "open" or e["sym"] not in F:
            continue
        df = F[e["sym"]]
        after = df[df.date > pd.Timestamp(e["first_seen"])].head(SL.HORIZON)
        if not len(after):
            continue
        top = after.c.max()
        if top >= e["entry_close"] * (1 + SL.RISE):
            hit_day = int(np.argmax(after.c.values >= e["entry_close"] * (1 + SL.RISE))) + 1
            e.update(status="hit", resolved_on=after.date.iloc[min(hit_day, len(after)) - 1].strftime("%Y-%m-%d"), peak=fmt(top), gain=round((top / e["entry_close"] - 1) * 100, 1), days=hit_day)
        elif len(after) >= SL.HORIZON:
            e.update(status="missed", resolved_on=after.date.iloc[-1].strftime("%Y-%m-%d"), peak=fmt(top), gain=round((top / e["entry_close"] - 1) * 100, 1))
    live = {}
    for k in SL.ORDER:
        L = [e for e in LOG if e["setup"] == k]
        done = [e for e in L if e["status"] in ("hit", "missed")]
        h = sum(e["status"] == "hit" for e in done)
        rt = h / len(done) if done else None
        live[k] = dict(logged=len(L), resolved=len(done), hits=h, open=len(L) - len(done), rate=rt,
                       flag=bool(len(done) >= LIVE_FLAG_MIN and rt < SL.BAR))   # live record below 95% over 20 or more resolved cases
    out = dict(
        schema=SCHEMA, built=now.isoformat(timespec="minutes"), built_local=local.isoformat(timespec="minutes"), seq=seq,
        bar_date=max(last_bar.values()) if last_bar else None, last_bar=last_bar, carried=carried, errors=notes_err,
        skipped=[dict(sym=s, reason=r) for s, r in sorted(err.items())],
        universe={k: len(v) for k, v in U.items()}, first_run=prev is None,
        candidates=fin, removed=removed, live=live)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    json.dump(out, open(a.out, "w"), separators=(",", ":"))
    json.dump(LOG, open(a.log, "w"), separators=(",", ":"))
    ps = {k: v["passes"] for k, v in (study or {}).get("verdicts", {}).items()}
    shown = [c for c in fin if ps.get(c["setup"])]
    print("matches", len(fin), "across", len({c["setup"] for c in fin}), "setups;", len(shown), "in Table C (setups passing the bar:", [k for k, v in ps.items() if v], "); removed", len(removed), "; carried", carried, "; log", len(LOG))


if __name__ == "__main__":
    main()
