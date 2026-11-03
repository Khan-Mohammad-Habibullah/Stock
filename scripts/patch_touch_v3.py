#!/usr/bin/env python3
"""Candle touch column v3 (run after patch_touch_v2.py): hovering the header or any cell of the column shows the rules as a tooltip."""
PATH = "index.html"
s = open(PATH, encoding="utf-8").read()
assert "TCH_RULES" not in s, "already patched"


def rep(old, new, cnt=1):
    global s
    n = s.count(old)
    assert n == cnt, f"expected {cnt}, found {n}: {old[:90]!r}"
    s = s.replace(old, new)


rep('<th data-field="touch"><button data-k="touch_rank">Candle touch</button></th>',
    '<th data-field="touch" title="Candle touch rules (hover a cell for its own alert)"><button data-k="touch_rank" data-rules="1">Candle touch</button></th>', 2)

rep("  const TOUCH_HOLD = 3;   // same number as scripts/board_lib.py\n",
    r"""  const TOUCH_HOLD = 3;   // same number as scripts/board_lib.py
  const TCH_RULES = ['Candle touch rules',
    'Alert buy (bold blue): the daily candle touches the 200-day MA upwards (comes up from below, its high reaches it).',
    'Alert buy (blue): the candle touches the 50-day MA downwards (comes down from above, its low reaches it), finishes the day above the 50-day MA, and the 50-day MA is above the 200-day MA.',
    'Alert sell (bold orange): the candle touches the 200-day MA downwards (comes down from above, its low reaches it).',
    'Alert sell (orange): the candle touches the 50-day MA upwards (comes up from below, its high reaches it), finishes the day below the 50-day MA, and the 50-day MA is below the 200-day MA.',
    'Each alert is kept for ' + TOUCH_HOLD + ' sessions after its candle unless a newer one appears. Otherwise a dash.'].join('\n');
  document.querySelectorAll('button[data-rules]').forEach((b) => { b.title = TCH_RULES; });
""")
rep("c.title = tc.known ? 'No candle touch in the last ' + (TOUCH_HOLD + 1) + ' sessions' : 'Needs 200 days of history'; return c; }",
    "c.title = (tc.known ? 'No candle touch in the last ' + (TOUCH_HOLD + 1) + ' sessions' : 'Needs 200 days of history') + '\\n\\n' + TCH_RULES; return c; }")
rep("c.title = tc.items.map((it) => 'Candle touched the ' + it.txt + ' (' + tc.when + ')').join('; ');",
    "c.title = tc.items.map((it) => 'Candle touched the ' + it.txt + ' (' + tc.when + ')').join('; ') + '\\n\\n' + TCH_RULES;")
open(PATH, "w", encoding="utf-8").write(s)
print("patched", len(s))
