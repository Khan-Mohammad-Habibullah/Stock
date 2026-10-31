#!/usr/bin/env python3
"""Calibrate the 1-, 3- and 5-year outlook scores on the board's original rows.

The board's methods text lists what each horizon weighs but not the weights.
The rows scored by the original builder (everything not marked "estimated
from the screener data") carry both the inputs and the scores, so the weights
are recovered by least squares on exactly the inputs the methods text names,
read from the stored row fields. Run once; the daily rebuild only applies the
stored weights (data/outlook_model.json).
"""
import json
import re
import sys

import numpy as np

sys.path.insert(0, "scripts")
import board_lib as L

s = open("index.html", encoding="utf-8").read()
H = json.JSONDecoder().raw_decode(s, s.index('"holdings":[') + len('"holdings":'))[0]


def row_inputs(r):
    """The model inputs as the original builder saw them, read from a stored row."""
    w1, w3, w5 = r["o1y_why"] or "", r["o3y_why"] or "", r["o5y_why"] or ""
    m = re.search(r"6 months (ahead|behind) of the market by (\d+) pts", w1)
    roe = re.search(r"return on equity (-?\d+)%", w5)
    return dict(vs40w=r["vs40w"], w40_rising="which is rising" in w1, rel6=((1 if m.group(1) == "ahead" else -1) * int(m.group(2))) if m else 0,
                oct_score=r["oct_score"], off_high=r["off_high"], rev_g=r["rev_g"], eps_g=r["eps_g"], margin=r["margin"], pe=r["pe"], de=r["de"],
                roe=int(roe.group(1)) if roe else 0, burn="burning cash" in w3 + w5, big="large, established" in w5, small="small company" in w5,
                analysts=r["analysts"], upside=r["upside"], w_rsi=r["w_rsi"], is_etf=r["market"].endswith("ETF"), nofund="no fundamentals" in w3)


base = [r for r in H if "estimated from" not in (r["o1y_why"] or "")]
X = {r["sym"]: row_inputs(r) for r in base}
LABELS = ["Negative", "Leaning negative", "Mixed", "Leaning positive", "Positive"]
out, report = {}, {}
for key, f, rows in [("o1y", L.feat1, base),
                     ("o3y", L.feat3, [r for r in base if not X[r["sym"]]["is_etf"] and not X[r["sym"]]["nofund"]]),
                     ("o5y", L.feat5, [r for r in base if not X[r["sym"]]["is_etf"] and not X[r["sym"]]["nofund"]])]:
    A = np.c_[np.array([f(X[r["sym"]]) for r in rows], float), np.ones(len(rows))]
    y = np.array([r[key + "_score"] for r in rows])
    coef = np.linalg.lstsq(A, y, rcond=None)[0]
    p = A @ coef
    same = np.mean([L.lt_label(a) == L.lt_label(b) for a, b in zip(p, y)])
    near = np.mean([abs(LABELS.index(L.lt_label(a)) - LABELS.index(L.lt_label(b))) <= 1 for a, b in zip(p, y)])
    loo = 0
    for i in range(len(rows)):
        m = np.ones(len(rows), bool); m[i] = False
        c = np.linalg.lstsq(A[m], y[m], rcond=None)[0]
        loo += L.lt_label(float(A[i] @ c)) == L.lt_label(y[i])
    out[key] = [round(float(c), 5) for c in coef]
    report[key] = dict(rows=len(rows), r2=round(float(1 - np.sum((p - y) ** 2) / np.sum((y - y.mean()) ** 2)), 3),
                       same_label=round(float(same), 3), within_one_label=round(float(near), 3), same_label_held_out=round(loo / len(rows), 3))
# ETFs at 3 and 5 years: trend only, with a small credit for spreading risk (read off the original rows)
etf = [r for r in base if X[r["sym"]]["is_etf"]]
out["etf_3y"] = {"up": sorted({r["o3y_score"] for r in etf if r["vs40w"] > 0}), "down": sorted({r["o3y_score"] for r in etf if r["vs40w"] <= 0})}
out["etf_5y"] = {"up": sorted({r["o5y_score"] for r in etf if r["vs40w"] > 0}), "down": sorted({r["o5y_score"] for r in etf if r["vs40w"] <= 0})}
out["report"] = report
out["fitted_on"] = "%d original rows of the board, 14-16 Oct 2026" % len(base)
json.dump(out, open("data/outlook_model.json", "w"), indent=1)
print(json.dumps(report, indent=1)); print("etf", out["etf_3y"], out["etf_5y"])
