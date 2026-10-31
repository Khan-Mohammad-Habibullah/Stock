#!/usr/bin/env python3
"""How closely does the rebuild reproduce the board's original readings?

Recomputes every originally-built holding (rows not marked "estimated") from
Yahoo bars cut off at the original build date, and compares the technical
fields with what the board shows. Writes data/preview/fidelity.json.
Differences come from two sources: data (Yahoo vs TradingView bars) and any
rule the port does not reproduce exactly.
"""
import collections
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import board_lib as L

s = open("index.html", encoding="utf-8").read()
H = json.JSONDecoder().raw_decode(s, s.index('"holdings":[') + len('"holdings":'))[0]
rows = [r for r in H if "estimated from" not in (r["o1y_why"] or "")]
info = L.scan_symbols([r["sym"] for r in rows])
bars, err = L.fetch_many([(r["sym"], info.get(r["sym"], {}).get("country"), None) for r in rows])
CAT = ["macd", "cpr", "alligator", "bollinger", "structure", "oct_signal", "obv"]
NUM = {"rsi": 3, "vs20": 1.5, "vs50": 1.5, "vs200": 2, "vs40w": 2, "w_rsi": 4, "off_high": 2, "vol": 4, "oct_score": 0.75, "cmf": 0.05, "adx": 4}
report = {}
for cut in ("2026-10-13", "2026-10-14", "2026-10-15"):
    ce = datetime.datetime.strptime(cut, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc).timestamp() + 86400
    agree = collections.Counter(); total = collections.Counter(); misses = collections.defaultdict(list)
    for r in rows:
        if r["sym"] not in bars:
            continue
        B = [b for b in bars[r["sym"]][0] if b[0] < ce]
        try:
            T = L.analyse(B)
        except Exception as e:
            misses["error"].append("%s %s" % (r["sym"], e)); continue
        for k in CAT:
            if r.get(k) is None:
                continue
            total[k] += 1
            if T.get(k) == r[k]:
                agree[k] += 1
            elif len(misses[k]) < 6:
                misses[k].append("%s: board %s / rebuild %s" % (r["sym"], r[k], T.get(k)))
        for k, tol in NUM.items():
            if r.get(k) is None or T.get(k) is None:
                continue
            total[k] += 1
            if abs(T[k] - r[k]) <= tol:
                agree[k] += 1
            elif len(misses[k]) < 6:
                misses[k].append("%s: board %s / rebuild %s" % (r["sym"], r[k], T.get(k)))
    report[cut] = dict(agree={k: "%d/%d" % (agree[k], total[k]) for k in total}, misses=dict(misses))
best = max(report, key=lambda c: sum(int(v.split("/")[0]) for v in report[c]["agree"].values()))
os.makedirs("data/preview", exist_ok=True)
json.dump(dict(best_cut=best, report=report, fetch_errors=err), open("data/preview/fidelity.json", "w"), indent=1)
print("best cut", best); print(json.dumps(report[best]["agree"], indent=1))
