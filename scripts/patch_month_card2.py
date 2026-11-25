#!/usr/bin/env python3
"""Month card: keep its rows packed at the top instead of spreading them when the neighbouring card is taller."""
PATH = "index.html"
s = open(PATH, encoding="utf-8").read()
old = "  .hs-card h2 { margin: 0;"
assert s.count(old) == 1 and "#mix-oct { align-content" not in s
s = s.replace(old, "  #mix-oct { align-content: start; }\n" + old)
open(PATH, "w", encoding="utf-8").write(s)
