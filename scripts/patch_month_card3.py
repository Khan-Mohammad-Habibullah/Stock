#!/usr/bin/env python3
"""Month card: later months use the same five groups as this month (Bullish ... Bearish), graded from that month's range outlook:
the gap between the chance of finishing above the likely range and the chance of finishing below it (in points):
>= 10 Bullish, >= 3 Mildly bullish, within +-3 Neutral, <= -3 Mildly bearish, <= -10 Bearish."""
PATH = "index.html"
s = open(PATH, encoding="utf-8").read()
assert "gradeOf" not in s, "already patched"


def rep(old, new, cnt=1):
    global s
    n = s.count(old)
    assert n == cnt, f"expected {cnt}, found {n}: {old[:90]!r}"
    s = s.replace(old, new)


rep("  function outlookOf(sym, mth) {", "  const gradeOf = (t) => (t >= 10 ? 'Bullish' : t >= 3 ? 'Mildly bullish' : t <= -10 ? 'Bearish' : t <= -3 ? 'Mildly bearish' : 'Neutral');\n  function outlookOf(sym, mth) {")
rep("    return { label: OUTLOOK[r.leans] || 'Even', score: (r.chance_high - r.chance_low) * 100, row: r };",
    "    const score = (r.chance_high - r.chance_low) * 100;\n    return { label: OUTLOOK[r.leans] || 'Even', score, grade: gradeOf(score), row: r };")
rep("""    const out = OUT_LABELS.map((label) => {
      const g = outs.filter((x) => x.o && x.o.label === label), sek = g.reduce((a, x) => a + Number(x.r.value_sek), 0);
      return { label, n: g.length, share: total ? sek / total : 0, cls: OUT_CLS[label] };
    });
    drawMix('oct_counts', OUT_LABELS, bar, leg, out);""",
"""    const out = OCT.map((label, i) => {
      const g = outs.filter((x) => x.o && x.o.grade === label), sek = g.reduce((a, x) => a + Number(x.r.value_sek), 0);
      return { label, n: g.length, share: total ? sek / total : 0, cls: CLS[i] };
    });
    drawMix('oct_counts', OCT, bar, leg, out);""")
rep("(so ? so.label : null)", "(so ? so.grade : null)")
rep("      ? 'Share of portfolio value that leans up, stays even or leans down in ' + monthName(MC.m) + ', with the number of holdings. This is the price-range outlook from the month-by-month model (an assumed yearly drift), not a technical signal, and it tells less the further out the month.'",
    "      ? 'Share of portfolio value in each group for ' + monthName(MC.m) + ', with the number of holdings. Later months cannot use the daily indicators, so each holding is graded from its price-range outlook for that month (the month-by-month model, built on an assumed yearly drift): the chance of ending above the likely range minus the chance of ending below it. 10 points or more is Bullish, 3 or more Mildly bullish, within 3 Neutral, and the same in reverse for the bearish groups. The further out the month, the less it tells you.'")
open(PATH, "w", encoding="utf-8").write(s)
print("ok")
