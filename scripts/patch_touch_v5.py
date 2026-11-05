#!/usr/bin/env python3
"""Candle touch column v5 (run after patch_touch_v4.py):
  - a 200-day alert also needs the close on the touching side: Alert buy (regular blue) = touched the 200-day upwards AND finished above it;
    Alert sell (regular orange) = touched it downwards AND finished below it.
  - events are kept 5 sessions (was 3).
Same numbers as board_lib.TOUCH_HOLD and its tch_events()."""
PATH = "index.html"
s = open(PATH, encoding="utf-8").read()
assert "const TOUCH_HOLD = 3;" in s, "already patched / run v4 first"


def rep(old, new, cnt=1):
    global s
    n = s.count(old)
    assert n == cnt, f"expected {cnt}, found {n}: {old[:90]!r}"
    s = s.replace(old, new)


# ---- logic
rep("const TOUCH_HOLD = 3;", "const TOUCH_HOLD = 5;")
rep("if (prev < b && hi >= b) le.push('buy200');", "if (prev < b && hi >= b && px > b) le.push('buy200');")
rep("if (prev > b && lo <= b) le.push('sell200');", "if (prev > b && lo <= b && px < b) le.push('sell200');")
rep("if (pc < b.m200 && b.m200 <= b.h) e.push('buy200');", "if (pc < b.m200 && b.m200 <= b.h && b.c > b.m200) e.push('buy200');")
rep("if (pc > b.m200 && b.m200 >= b.l) e.push('sell200');", "if (pc > b.m200 && b.m200 >= b.l && b.c < b.m200) e.push('sell200');")
rep("// buy200 = came up from below and the high reached the 200-day; sell200 = came down from above and the low reached it;",
    "// buy200 = came up from below, the high reached the 200-day and it closed above it; sell200 = came down from above, the low reached it and it closed below it;")
rep("(events kept for 3 sessions)", "(events kept for 5 sessions)")
rep("TCH_INFO = { buy200: { ma: 200, dir: 1, txt: '200-day upwards' }, sell200: { ma: 200, dir: -1, txt: '200-day downwards' },",
    "TCH_INFO = { buy200: { ma: 200, dir: 1, txt: '200-day upwards, closed above' }, sell200: { ma: 200, dir: -1, txt: '200-day downwards, closed below' },")

# ---- tooltip rules
rep("'Alert buy (blue): the daily candle touches the 200-day MA upwards (comes up from below, its high reaches it).'",
    "'Alert buy (blue): the daily candle touches the 200-day MA upwards (comes up from below, its high reaches it) and finishes the day above the 200-day MA.'")
rep("'Alert sell (orange): the candle touches the 200-day MA downwards (comes down from above, its low reaches it).'",
    "'Alert sell (orange): the candle touches the 200-day MA downwards (comes down from above, its low reaches it) and finishes the day below the 200-day MA.'")

# ---- note under the table
rep("regular when the daily candle touches the 200-day average upwards (comes up from below and its high reaches it); bold when",
    "regular when the daily candle touches the 200-day average upwards (comes up from below and its high reaches it) and finishes the day on the upper side of it; bold when")
rep("regular when the candle touches the 200-day downwards; bold when", "regular when the candle touches the 200-day downwards and finishes the day below it; bold when")
rep("Each alert is kept for 3 sessions after its candle unless a newer one appears", "Each alert is kept for 5 sessions after its candle unless a newer one appears")

# ---- methods paragraph
rep("the previous close was below it and the day's high reached it. Alert buy in bold blue",
    "the previous close was below it, the day's high reached it, and the day finished above it. Alert buy in bold blue")
rep("(previous close above it, the low reached it), and bold orange means", "(previous close above it, the low reached it, and the day finished below it), and bold orange means")
rep("An alert is kept for 3 sessions after the candle, or until", "An alert is kept for 5 sessions after the candle, or until")

# ---- lookup note (it only has the latest two candles)
rep("kept for the latest and the previous session instead of 3,", "kept for the latest and the previous session instead of 5,")
open(PATH, "w", encoding="utf-8").write(s)
print("patched", len(s))
