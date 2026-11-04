#!/usr/bin/env python3
"""Candle touch column v4 (run after patch_lookup_signal.py): boldness swapped.
  200-day alerts are now regular weight (blue / orange); 50-day alerts are bold (blue / orange). Text and tooltips follow."""
PATH = "index.html"
s = open(PATH, encoding="utf-8").read()
assert "bold 50-day alert" not in s, "already patched"


def rep(old, new, cnt=1):
    global s
    n = s.count(old)
    assert n == cnt, f"expected {cnt}, found {n}: {old[:90]!r}"
    s = s.replace(old, new)


rep("(it.ma === 200 ? ' big' : '')", "(it.ma === 50 ? ' big' : '')   /* bold 50-day alert */")
# tooltip rules
rep("'Alert buy (bold blue): the daily candle touches the 200-day MA upwards", "'Alert buy (blue): the daily candle touches the 200-day MA upwards")
rep("'Alert buy (blue): the candle touches the 50-day MA downwards", "'Alert buy (bold blue): the candle touches the 50-day MA downwards")
rep("'Alert sell (bold orange): the candle touches the 200-day MA downwards", "'Alert sell (orange): the candle touches the 200-day MA downwards")
rep("'Alert sell (orange): the candle touches the 50-day MA upwards", "'Alert sell (bold orange): the candle touches the 50-day MA upwards")
# note under the table
rep('in blue: bold when the daily candle touches the 200-day average upwards (comes up from below and its high reaches it); regular when it touches the 50-day average downwards',
    'in blue: regular when the daily candle touches the 200-day average upwards (comes up from below and its high reaches it); bold when it touches the 50-day average downwards')
rep('in orange: bold when the candle touches the 200-day downwards; regular when it touches the 50-day upwards',
    'in orange: regular when the candle touches the 200-day downwards; bold when it touches the 50-day upwards')
# methods paragraph
rep("Alert buy in bold blue means the daily candle touched the 200-day", "Alert buy in regular blue means the daily candle touched the 200-day")
rep("Alert buy in regular blue means the candle touched the 50-day", "Alert buy in bold blue means the candle touched the 50-day")
rep("Alert sell in bold orange is the mirror image on the 200-day", "Alert sell in regular orange is the mirror image on the 200-day")
rep("and regular orange means the candle touched the 50-day upwards", "and bold orange means the candle touched the 50-day upwards")
open(PATH, "w", encoding="utf-8").write(s)
print("patched", len(s))
