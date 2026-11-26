#!/usr/bin/env python3
"""Replaces the "Setups before 20% rises" section (HTML + script) with "Setups before 15% rises" on the Strategy tab.
Source of the new section: scripts/setups_page/section.html and section.js. Safe to re-run: it replaces whatever section is there."""
import os
PATH = "index.html"
HERE = os.path.dirname(os.path.abspath(__file__))
s = open(PATH, encoding="utf-8").read()
html = open(os.path.join(HERE, "setups_page", "section.html"), encoding="utf-8").read()
js = open(os.path.join(HERE, "setups_page", "section.js"), encoding="utf-8").read()

a = s.index('  <section class="hs-card" id="setups">')
b = s.index('  <section class="hs-card" id="lookup">')
assert a < b
s = s[:a] + html + s[b:]
a = s.index("  // ---------- Strategy tab: setups before")
b = s.index("  // ---------- Strategy tab: look up any stock")
assert a < b
s = s[:a] + js.lstrip("\n") + "\n" + s[b:]
open(PATH, "w", encoding="utf-8").write(s)
print("ok")
