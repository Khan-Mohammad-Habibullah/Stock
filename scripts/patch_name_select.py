"""Fix a regression from the chart-modal patch: making the holding/coin
name a button (to open the TradingView chart) meant clicking it no longer
reached the row's click-to-select handler (the button stops the click
from bubbling to <tbody>), so clicking a name in "Every holding" or
"Every coin" stopped auto-selecting it in "Possible price, month by
month". Fixes it by having the name button also call the row's own
select function directly, instead of only relying on propagation.
Edits the shipped index.html in place, like the other
scripts/patch_*.py one-offs -- never touches the embedded datasets.
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


rep(
    "  function nameTd(label, sym, cls) {\n"
    "    const c = document.createElement('td'); c.className = cls || 'nm';\n"
    "    const b = document.createElement('button'); b.type = 'button'; b.className = 'chart-link'; b.textContent = label;\n"
    "    b.addEventListener('click', (e) => { e.stopPropagation(); openChart(sym, label); });\n"
    "    c.appendChild(b);\n"
    "    return c;\n"
    "  }\n",
    "  function nameTd(label, sym, cls, onSelect) {\n"
    "    const c = document.createElement('td'); c.className = cls || 'nm';\n"
    "    const b = document.createElement('button'); b.type = 'button'; b.className = 'chart-link'; b.textContent = label;\n"
    "    b.addEventListener('click', (e) => { e.stopPropagation(); if (onSelect) onSelect(); openChart(sym, label); });\n"
    "    c.appendChild(b);\n"
    "    return c;\n"
    "  }\n",
)

# stock holdings table: clicking the name both opens the chart and selects
# the row, which is what drives "Possible price, month by month"
rep("        nameTd(r.name, r.sym),\n",
    "        nameTd(r.name, r.sym, null, () => select(r.sym)),\n")

# crypto holdings table: same, via cSelect -- but NOT the crypto strategy
# screen table (drawCryptoScreen), which has no monthly section to link
rep(
    "      tr.append(\n"
    "        nameTd(r.name + ' (' + r.ticker + ')', r.sym),\n"
    "        td(plain(r.price, dec), 'num'),\n"
    "        td(signed(r.day_chg, 2), 'num ' + tone(r.day_chg)),\n"
    "        td(signed(r.r1m), 'num ' + tone(r.r1m)),\n"
    "        chip(r.flow),\n",
    "      tr.append(\n"
    "        nameTd(r.name + ' (' + r.ticker + ')', r.sym, null, () => cSelect(r.sym)),\n"
    "        td(plain(r.price, dec), 'num'),\n"
    "        td(signed(r.day_chg, 2), 'num ' + tone(r.day_chg)),\n"
    "        td(signed(r.r1m), 'num ' + tone(r.r1m)),\n"
    "        chip(r.flow),\n",
)

open(INDEX, "w", encoding="utf-8").write(s)
print("patched ok,", len(s), "bytes")
