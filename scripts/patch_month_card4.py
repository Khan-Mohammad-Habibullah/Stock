#!/usr/bin/env python3
"""Month card: grade each holding against a typical market drift (5% a year) instead of against zero, so the bearish groups can appear.
The range model's drift is 5% + 1.5 x the 1-year score (kept within +-10%), which is rarely below zero; a holding whose drift is below
the 5% baseline now counts as bearish *relative to that baseline*."""
PATH = "index.html"
s = open(PATH, encoding="utf-8").read()
assert "BASE_DRIFT" not in s, "already patched"


def rep(old, new, cnt=1):
    global s
    n = s.count(old)
    assert n == cnt, f"expected {cnt}, found {n}: {old[:90]!r}"
    s = s.replace(old, new)


rep("  const gradeOf = (t) =>", """  const BASE_DRIFT = 0.05;   // the typical yearly drift the range model starts from (see scripts/update_board.py)
  const erfN = (z) => { const t = 1 / (1 + 0.3275911 * Math.abs(z) / Math.SQRT2), y = 1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * Math.exp(-z * z / 2); return 0.5 * (1 + (z < 0 ? -y : y)); };
  // chance above the likely range minus chance below it, in points, for a given yearly drift (rebuilt from the stored range)
  function tiltAt(x, drift, T) {
    const px = Math.sqrt(x.likely_low * x.likely_high), sg = Math.log(x.likely_high / px) / 0.6745;
    if (!(sg > 0)) return 0;
    return (1 - erfN((Math.log(x.likely_high / px) - drift * T) / sg) - erfN((Math.log(x.likely_low / px) - drift * T) / sg)) * 100;
  }
  function relTilt(x) {
    const bs = dash.data('board_status'), dd = bs.status === 'ok' && bs.data[0] ? bs.data[0].data_date : null;
    if (!dd) return (x.chance_high - x.chance_low) * 100;
    const T = Math.max((Date.parse(x.date) - Date.parse(dd)) / 86400000, 1) / 365;
    return tiltAt(x, x.drift_pct_yr / 100, T) - tiltAt(x, BASE_DRIFT, T);
  }
  const gradeOf = (t) =>""")
rep("grade: gradeOf(score), row: r };", "grade: gradeOf(relTilt(r)), row: r };")
rep("the chance of ending above the likely range minus the chance of ending below it. 10 points or more is Bullish, 3 or more Mildly bullish, within 3 Neutral, and the same in reverse for the bearish groups. The further out the month, the less it tells you.'",
    "the chance of ending above the likely range minus the chance of ending below it, measured against a typical market drift of 5% a year. Neutral is in line with that; 3 points or more above it is Mildly bullish, 10 or more Bullish, and 3 or 10 points below it Mildly bearish or Bearish. So Bearish here means a weaker outlook than the typical drift, not necessarily a falling price. The further out the month, the less it tells you.'")
open(PATH, "w", encoding="utf-8").write(s)
print("ok")
