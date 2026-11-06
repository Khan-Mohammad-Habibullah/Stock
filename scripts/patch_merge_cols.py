#!/usr/bin/env python3
"""Merge the Signal and Candle touch columns into one column, "Signal-CandleTouch" (run after patch_touch_v5.py and patch_signal_v5.py).

Every holding, Former holdings and Look up any stock each get one column: the Signal (alert or strategy view) on the first line(s),
then any Candle touch alerts underneath. Rules, notes, filters and the two data fields are unchanged. The header and cells show both sets
of rules as a tooltip. Sorting by the column sorts by Signal."""
PATH = "index.html"
s = open(PATH, encoding="utf-8").read()
assert "sigTouchCell" not in s, "already patched"


def rep(old, new, cnt=1):
    global s
    n = s.count(old)
    assert n == cnt, f"expected {cnt}, found {n}: {old[:90]!r}"
    s = s.replace(old, new)


# ---- CSS
rep("  .tch { display: block; }\n", "  .tch { display: block; }\n  .sg-part, .tc-part { display: block; }\n  .tc-part { margin-top: 4px; }\n")

# ---- headers (main and former tables, lookup)
rep('''          <th data-field="signal"><button data-k="signal_rank">Signal</button></th>
          <th data-field="touch" title="Candle touch rules (hover a cell for its own alert)"><button data-k="touch_rank" data-rules="1">Candle touch</button></th>
''', '''          <th data-field="signal" title="Signal and Candle touch rules"><button data-k="signal_rank" data-rules="1">Signal-CandleTouch</button></th>
''', 2)
rep('''          <th data-field="signal">Signal</th>
          <th data-field="touch">Candle touch</th>
''', '''          <th data-field="signal">Signal-CandleTouch</th>
''')

# ---- rules text for the header tooltip (board version) and the one merged cell builder
rep("  const TCH_RULES = ['Candle touch rules',", """  const SIG_BOARD_RULES = ['Signal rules',
    'Alert buy / Alert sell: the 50-day MA is about to touch the 200-day MA from below / from above (within ' + APPROACH_PCT + '% of it and closing in so that, at its pace over the last 5 sessions, it would touch within ' + APPROACH_DAYS + ' trading days). Kept for ' + ALERT_HOLD + ' trading days after the last session that met this (so it also covers the touch itself) unless the averages cross the other way.',
    'Otherwise the strategy view behind the December column: Strong buy, Buy, Hold, Sell or Strong sell.'].join('\\n');
  const TCH_RULES = ['Candle touch rules',""")
rep("document.querySelectorAll('button[data-rules]').forEach((b) => { b.title = TCH_RULES; });",
    "document.querySelectorAll('button[data-rules]').forEach((b) => { b.title = SIG_BOARD_RULES + '\\n\\n' + TCH_RULES; });")
rep("""    c.title = tc.items.map((it) => 'Candle touched the ' + it.txt + ' (' + tc.when + ')').join('; ') + '\\n\\n' + TCH_RULES;
    return c;
  }
""", """    c.title = tc.items.map((it) => 'Candle touched the ' + it.txt + ' (' + tc.when + ')').join('; ') + '\\n\\n' + TCH_RULES;
    return c;
  }
  // one cell for the merged Signal-CandleTouch column: the Signal first, any Candle touch alerts underneath (sg may be null: no signal at all)
  function sigTouchCell(sg, tc) {
    const c = document.createElement('td'); c.className = 'sigc'; const tips = [];
    const put = (src, cls) => { const d = document.createElement('span'); d.className = cls; while (src.firstChild) d.appendChild(src.firstChild); c.appendChild(d); tips.push(src.title); };
    if (sg) put(sigCell(sg), 'sg-part');
    if (tc.items.length) put(touchCell(tc), 'tc-part');
    else if (!sg) { c.textContent = '\\u2014'; c.classList.add('mut'); tips.push(touchCell(tc).title); }
    c.title = tips.join('\\n\\n');
    return c;
  }
""")

# ---- cells
rep("        sigCell(r._sig),\n        touchCell(r._tch),\n", "        sigTouchCell(r._sig, r._tch),\n")
rep("          sigCell(r._sig),\n          touchCell(r._tch),\n", "          sigTouchCell(r._sig, r._tch),\n")
rep("        sigCell(signalOf(r)),\n        touchCell(touchOf(r)),\n", "        sigTouchCell(signalOf(r), touchOf(r)),\n")
rep("        lookupSig(lr),\n        touchCell(touchOf(lr)),\n", "        lookupCell(lr),\n")
i = s.index("    const lookupSig = (r) =>"); j = s.index("\n", i)
s = s[:i] + "    const lookupCell = (r) => { const sg = signalOf(r); return sigTouchCell(!sg.alert && !r.rating ? null : sg, touchOf(r)); };" + s[j:]
rep("th.title = th.dataset.field === 'touch' ? TCH_RULES : SIG_RULES;", "th.title = SIG_RULES + '\\n\\n' + TCH_RULES;")
rep("c.colSpan = 24; c.className = 'mut';", "c.colSpan = 23; c.className = 'mut';")
open(PATH, "w", encoding="utf-8").write(s)
print("patched", len(s))
