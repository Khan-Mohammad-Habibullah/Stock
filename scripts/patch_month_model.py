#!/usr/bin/env python3
"""Page side of the TradingView-based outlook: the month card grades from each range's own expected return (taken from its most-likely
price) and the notes describe the new model (scripts/board_lib.py expected_return)."""
PATH = "index.html"
s = open(PATH, encoding="utf-8").read()
assert "own expected return" not in s, "already patched"


def rep(old, new, cnt=1):
    global s
    n = s.count(old)
    assert n == cnt, f"expected {cnt}, found {n}: {old[:90]!r}"
    s = s.replace(old, new)


rep("    return tiltAt(x, x.drift_pct_yr / 100, T) - tiltAt(x, BASE_DRIFT, T);",
    "    const px = Math.sqrt(x.likely_low * x.likely_high);   // the range is centred on today's price in log terms\n    const E = Math.log(x.most_likely / px);   // this holding's own expected return to that month\n    return tiltAt(x, E / T, T) - tiltAt(x, BASE_DRIFT, T);")
MODEL = ("The middle is each holding's expected price: its 1-year score as the starting drift, TradingView's weekly, monthly and daily technical ratings for the next few months, "
         "and the analysts' average price target (counted at half, since targets run optimistic) for the months after.")
rep("A range with a modest tilt, not a forecast.</p>", MODEL + " A range with a modest tilt, not a forecast.</p>")
rep("from the model under Possible price, month by month (an assumed yearly drift with the stock\\'s own swings around it).",
    "from the model under Possible price, month by month (TradingView\\'s technical ratings for the near months, analyst price targets for the later ones, and the stock\\'s own swings around that).")
rep("(the month-by-month model, built on an assumed yearly drift)", "(the month-by-month model: TradingView\\'s technical ratings for near months, analyst price targets for later ones)")
rep("' · assumed drift '", "' · expected drift '", 2)
open(PATH, "w", encoding="utf-8").write(s)
print("ok")
