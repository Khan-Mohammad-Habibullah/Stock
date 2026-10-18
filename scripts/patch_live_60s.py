"""Slow the client-side live-price tickers back down from 1 second to 1
minute, for both stock and crypto holdings. Edits the shipped index.html
directly, like the other scripts/patch_*.py one-offs, so it never touches
the embedded datasets.
"""
import sys

INDEX = "/home/claude/stock/index.html"
s = open(INDEX, encoding="utf-8").read()


def rep(a, b, cnt=1):
    global s
    n = s.count(a)
    if n != cnt:
        print("MISMATCH expected %d got %d for: %r" % (cnt, n, a[:90]), file=sys.stderr)
        sys.exit(1)
    s = s.replace(a, b)


rep("  LIVE.timer = setInterval(liveTick, 1000);\n",
    "  LIVE.timer = setInterval(liveTick, 60000);\n")
rep("    setInterval(liveTickCrypto, 1000);\n",
    "    setInterval(liveTickCrypto, 60000);\n")
rep("about every second while this tab is open", "about every minute while this tab is open", cnt=2)

open(INDEX, "w", encoding="utf-8").write(s)
print("patched ok,", len(s), "bytes")
