#!/usr/bin/env python3
"""Candle touch column v2 (run after patch_touch.py): new rules, kept 3 sessions.

  Alert buy   blue, bold   the daily candle touched the 200-day average upwards (came up from below, high reached it)
  Alert buy   blue         the candle touched the 50-day downwards (came down from above, low reached it), closed above it,
                           and the 50-day is above the 200-day (a dip in an uptrend)
  Alert sell  orange, bold the candle touched the 200-day downwards (came down from above, low reached it)
  Alert sell  orange       the candle touched the 50-day upwards (came up from below, high reached it), closed below it,
                           and the 50-day is below the 200-day (a rally in a downtrend)
  An event is kept for 3 sessions after its candle unless a newer event appears; otherwise a dash.

Fields from board_lib.analyse: tch (events of the newest of the last 4 bars that had any: buy200/sell200/buy50/sell50),
tch_ago (sessions ago, 0 = last bar), bar_date. Live: TradingView high/low/price/change and live averages for today's candle."""

PATH = "index.html"
s = open(PATH, encoding="utf-8").read()
assert "TOUCH_HOLD" not in s, "already patched"


def between(a, b, new):
    """Replace s[a : b+len(b)] with new."""
    global s
    assert s.count(a) == 1, a[:60]
    i = s.index(a)
    j = s.index(b, i) + len(b)
    s = s[:i] + new + s[j:]


JS = r"""  // ---------- Candle touch column: the daily candle against the 200- and 50-day averages (events kept for 3 sessions) ----------
  // buy200 = came up from below and the high reached the 200-day; sell200 = came down from above and the low reached it;
  // buy50 = touched the 50-day downwards, closed above it, 50-day over the 200-day; sell50 = touched it upwards, closed below it, 50-day under the 200-day
  const TOUCH_HOLD = 3;   // same number as scripts/board_lib.py
  const TCH_INFO = { buy200: { ma: 200, dir: 1, txt: '200-day upwards' }, sell200: { ma: 200, dir: -1, txt: '200-day downwards' },
                     buy50: { ma: 50, dir: 1, txt: '50-day downwards, closed above' }, sell50: { ma: 50, dir: -1, txt: '50-day upwards, closed below' } };
  function touchOf(r) {
    let ev = Array.isArray(r.tch) && r.tch.length ? r.tch : null, ago = ev ? Number(r.tch_ago) || 0 : null, when = '';
    const day = r.bar_date ? new Date(r.bar_date + 'T12:00:00Z').toLocaleDateString('en-GB', { day: 'numeric', month: 'short' }) : '';
    const hi = Number(r.live_high), lo = Number(r.live_low), px = Number(r.price_live), chg = Number(r.day_chg), a = Number(r.live_sma50), b = Number(r.live_sma200);
    const known = r.tch !== undefined && (r.tch !== null || r.bar_date != null);
    let live = false;
    if (r.session !== 'pre' && r.live_high != null && r.live_low != null && r.price_live != null && r.day_chg != null && r.live_sma50 != null && r.live_sma200 != null &&
        [hi, lo, px, chg, a, b].every(isFinite) && chg > -100 && a > 0 && b > 0) {
      live = true;
      const prev = px / (1 + chg / 100), le = [];
      if (prev < b && hi >= b) le.push('buy200');
      if (prev > b && lo <= b) le.push('sell200');
      if (a > b && prev > a && lo <= a && px > a) le.push('buy50');
      if (a < b && prev < a && hi >= a && px < a) le.push('sell50');
      if (le.length) { ev = le; ago = 0; when = 'today’s candle'; }
      else if (ev) {
        // today's candle is a new session when its previous close is the stored last close: the stored event is a session older; otherwise the stored bar is today's
        const last = Number(r.price), newer = isFinite(last) && last > 0 && Math.abs(prev / last - 1) < 0.0005;
        if (newer) ago += 1; else if (ago === 0) ev = null;
      }
    }
    if (ev && ago > TOUCH_HOLD) ev = null;
    if (ev && !when) when = ago === 0 ? (day ? day + ' candle' : 'last daily candle') : ago + (ago === 1 ? ' session' : ' sessions') + ' ago · kept (' + ago + ' of ' + TOUCH_HOLD + ')';
    else if (ev && ago === 0 && live === false && !day) when = 'last daily candle';
    const items = ev ? ev.map((k) => TCH_INFO[k]).filter(Boolean).sort((x, y) => y.ma - x.ma) : [];
    const rank = items.length ? (items[0].ma === 200 ? 4 : 3) * items[0].dir : 0;
    return { items, when, rank, known: known || live };
  }
  function touchCell(tc) {
    const c = document.createElement('td'); c.className = 'sigc';
    if (!tc.items.length) { c.textContent = '—'; c.classList.add('mut'); c.title = tc.known ? 'No candle touch in the last ' + (TOUCH_HOLD + 1) + ' sessions' : 'Needs 200 days of history'; return c; }
    tc.items.forEach((it) => {
      const sp = document.createElement('span'); sp.className = 'tch ' + (it.dir > 0 ? 'buy' : 'sell') + (it.ma === 200 ? ' big' : '');
      sp.textContent = it.dir > 0 ? 'Alert buy' : 'Alert sell';
      const n = document.createElement('span'); n.className = 'sig-note'; n.textContent = it.txt + ' · ' + tc.when;
      c.append(sp, n);
    });
    c.title = tc.items.map((it) => 'Candle touched the ' + it.txt + ' (' + tc.when + ')').join('; ');
    return c;
  }
"""

between("  // ---------- Candle touch column: the latest daily candle against the 200- and 50-day averages ----------",
        "    c.title = tc.items.map((it) => 'Candle touched the ' + it.ma + '-day average ' + (it.dir > 0 ? 'upwards' : 'downwards') + ' (' + tc.when + ')').join('; ');\n    return c;\n  }\n", JS)

between('    <p class="hs-note" id="tch-note">', "</p>",
        '''    <p class="hs-note" id="tch-note"><b>Candle touch.</b> <b style="color:var(--series-0)">Alert buy</b> in blue: bold when the daily candle touches the 200-day average upwards (comes up from below and its high reaches it); regular when it touches the 50-day average downwards (comes down from above and its low reaches it), finishes the day above the 50-day, and the 50-day is above the 200-day. <b style="color:var(--series-1)">Alert sell</b> in orange: bold when the candle touches the 200-day downwards; regular when it touches the 50-day upwards, finishes the day below it, and the 50-day is below the 200-day. Each alert is kept for 3 sessions after its candle unless a newer one appears; a dash otherwise. "From above" and "from below" are judged against the previous close.</p>''')

between("      <p><b>Candle touch column.</b>", "so an alert disappears when a later candle does not touch the average.</p>",
        '''      <p><b>Candle touch column.</b> Alert buy in bold blue means the daily candle touched the 200-day moving average upwards: the previous close was below it and the day's high reached it. Alert buy in regular blue means the candle touched the 50-day average downwards (previous close above it, the low reached it), closed the day above it, and the 50-day is above the 200-day, so a dip in an uptrend. Alert sell in bold orange is the mirror image on the 200-day (previous close above it, the low reached it), and regular orange means the candle touched the 50-day upwards (previous close below it, the high reached it), closed below it, and the 50-day is below the 200-day, a rally in a downtrend. An alert is kept for 3 sessions after the candle, or until a newer alert replaces it; if both averages are touched the same day, both are shown. While TradingView's live prices are on (every minute), today's candle counts as it develops, so an alert can appear or disappear during the day until the close settles it; the stored history comes from the daily rebuild.</p>''')

open(PATH, "w", encoding="utf-8").write(s)
print("patched", len(s))
