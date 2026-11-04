#!/usr/bin/env python3
"""Signal column v5 (run after patch_signal_v4.py): an alert is kept for 7 trading days (was 3) after the last session that met the test.
Same number as board_lib.ALERT_HOLD. (The Candle touch column keeps its own 3-session hold.)"""
PATH = "index.html"
s = open(PATH, encoding="utf-8").read()
assert "ALERT_HOLD = 3" in s, "already patched / run v4 first"


def rep(old, new, cnt=1):
    global s
    n = s.count(old)
    assert n == cnt, f"expected {cnt}, found {n}: {old[:90]!r}"
    s = s.replace(old, new)


rep("APPROACH_DAYS = 10, ALERT_HOLD = 3;", "APPROACH_DAYS = 10, ALERT_HOLD = 7;")
rep("An alert stays for 3 trading days after the last session that met this", "An alert stays for 7 trading days after the last session that met this")
rep("The alert is kept for 3 trading days after the last session that met the test", "The alert is kept for 7 trading days after the last session that met the test")
open(PATH, "w", encoding="utf-8").write(s)
print("patched", len(s))
