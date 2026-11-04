#!/usr/bin/env python3
"""Signal column v3 (run after patch_lookup_signal.py): "about to touch" = within 0.5% of the 200-day (was 2%).
Same number as board_lib.APPROACH_PCT. Everything else in the test is unchanged."""
PATH = "index.html"
s = open(PATH, encoding="utf-8").read()
assert "APPROACH_PCT = 0.5" not in s, "already patched"


def rep(old, new, cnt=1):
    global s
    n = s.count(old)
    assert n == cnt, f"expected {cnt}, found {n}: {old[:90]!r}"
    s = s.replace(old, new)


rep("const APPROACH_PCT = 2, APPROACH_DAYS", "const APPROACH_PCT = 0.5, APPROACH_DAYS")
rep('"About to touch" means within 2% of the 200-day', '"About to touch" means within 0.5% of the 200-day')
rep("the gap between them is under 2% of the 200-day", "the gap between them is under 0.5% of the 200-day")
rep("(within 2% and closing in, so it would touch within 10 sessions)", "(within 0.5% and closing in, so it would touch within 10 sessions)")
open(PATH, "w", encoding="utf-8").write(s)
print("patched", len(s))
