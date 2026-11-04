#!/usr/bin/env python3
"""Signal column v4 (run after patch_signal_v3.py): "about to touch" = within 1% of the 200-day (v3 had 0.5%, v2 2%).
Same number as board_lib.APPROACH_PCT."""
PATH = "index.html"
s = open(PATH, encoding="utf-8").read()
assert "APPROACH_PCT = 0.5" in s, "run patch_signal_v3.py first"


def rep(old, new, cnt=1):
    global s
    n = s.count(old)
    assert n == cnt, f"expected {cnt}, found {n}: {old[:90]!r}"
    s = s.replace(old, new)


rep("const APPROACH_PCT = 0.5, APPROACH_DAYS", "const APPROACH_PCT = 1, APPROACH_DAYS")
rep('"About to touch" means within 0.5% of the 200-day', '"About to touch" means within 1% of the 200-day')
rep("the gap between them is under 0.5% of the 200-day", "the gap between them is under 1% of the 200-day")
rep("(within 0.5% and closing in, so it would touch within 10 sessions)", "(within 1% and closing in, so it would touch within 10 sessions)")
open(PATH, "w", encoding="utf-8").write(s)
print("patched", len(s))
