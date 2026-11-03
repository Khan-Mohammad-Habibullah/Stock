#!/usr/bin/env python3
"""Signal column v2 (run after patch_signal.py): the alert comes BEFORE the cross.

  Alert buy   (bold green)  the 50-day average is about to touch the 200-day from below
  Alert sell  (bold red)    the 50-day average is about to touch the 200-day from above
  "About to touch" = within 2% of the 200-day, on the same side for the last 6 sessions, and closing in so that
  at its pace of the last 5 sessions it would touch within 10 trading days. The alert is kept for 3 trading days
  after the last session that met the test, unless the averages cross the other way. A cross in the same
  direction (the touch itself) keeps it on for those 3 days. The live prices from TradingView are checked every
  minute, so the alert can appear before the daily rebuild.
  Otherwise Strong buy / Buy / Hold / Sell / Strong sell from the December strategy view.

Fields written by update_board.py / board_lib.analyse: ma_gap (last 5 gaps, %), ma_alert (+1/-1), ma_alert_ago, ma_eta, rating.
Same thresholds as board_lib.APPROACH_PCT / APPROACH_DAYS / ALERT_HOLD."""

PATH = "index.html"
s = open(PATH, encoding="utf-8").read()
assert "APPROACH_PCT" not in s, "already patched"


def between(a, b, new):
    """Replace s[a : b+len(b)] with new."""
    global s
    assert s.count(a) == 1, a[:60]
    i = s.index(a)
    j = s.index(b, i) + len(b)
    s = s[:i] + new + s[j:]


JS = r"""  // ---------- Signal column: about-to-touch alerts on the 50/200-day averages, otherwise the strategy rating ----------
  const APPROACH_PCT = 2, APPROACH_DAYS = 10, ALERT_HOLD = 3;   // same numbers as scripts/board_lib.py
  const SIG_RANK = { 'Alert buy': 6, 'Strong buy': 5, 'Buy': 4, 'Hold': 3, 'Sell': 2, 'Strong sell': 1, 'Alert sell': 0 };
  const SIG_CLS = { 'Strong buy': 'b2', 'Buy': 'b1', 'Hold': 'n', 'Sell': 'e1', 'Strong sell': 'e2' };
  const RATING_OF = { 'Consider adding': 'Strong buy', 'Hold, add on dips': 'Buy', 'Hold': 'Hold', 'Consider trimming': 'Sell', 'Consider selling by December': 'Strong sell' };
  // w: the gap (50-day minus 200-day, % of the 200-day) over 6 bars, oldest first -> { dir: 1 (below, rising) | -1 (above, falling), gap, eta } or null
  function approachOf(w) {
    const now = w[w.length - 1];
    if (w.length < 6 || w.some((x) => x == null || !isFinite(x)) || now === 0 || w.some((x) => (x > 0) !== (now > 0))) return null;
    const closing = Math.abs(w[0]) - Math.abs(now);
    if (closing <= 0 || Math.abs(now) > APPROACH_PCT) return null;
    const eta = Math.abs(now) / (closing / 5);
    return eta > APPROACH_DAYS ? null : { dir: now < 0 ? 1 : -1, gap: now, eta };
  }
  const gapTxt = (g) => Math.abs(g).toFixed(1) + '% ' + (g < 0 ? 'below' : 'above');
  const etaTxt = (e) => (e < 1.5 ? 'about to touch' : 'touch in about ' + Math.round(e) + ' sessions');
  function signalOf(r) {
    const rating = r.rating || RATING_OF[r.december] || 'Hold';
    let dir = 0, note = '';
    // live: the live averages (TradingView) appended to the last 5 daily gaps
    const a = Number(r.live_sma50), b = Number(r.live_sma200);
    if (Array.isArray(r.ma_gap) && r.ma_gap.length === 5 && r.live_sma50 != null && r.live_sma200 != null && isFinite(a) && isFinite(b) && b > 0) {
      const ap = approachOf(r.ma_gap.concat([(a - b) / b * 100]));
      if (ap) { dir = ap.dir; note = '50-day ' + gapTxt(ap.gap) + ' the 200-day, ' + etaTxt(ap.eta); }
    }
    // the last daily rebuild: the test met on one of the last 4 sessions (kept 3 sessions after the last time it was met)
    if (!dir && r.ma_alert) {
      dir = r.ma_alert;
      const g = r.ma_gap && r.ma_gap.length ? r.ma_gap[r.ma_gap.length - 1] : null;
      if (!r.ma_alert_ago) note = g == null ? '50-day closing in on the 200-day' : '50-day ' + gapTxt(g) + ' the 200-day, ' + etaTxt(r.ma_eta == null ? 5 : r.ma_eta);
      else {
        const crossed = r.ma_ago != null && r.ma_ago < r.ma_alert_ago && String(r.ma_cross || '').startsWith(dir > 0 ? 'golden' : 'death');
        note = (crossed ? (r.ma_ago === 0 ? 'touched on the last session' : 'touched ' + r.ma_ago + (r.ma_ago === 1 ? ' session' : ' sessions') + ' ago') : '50-day was closing in') +
          ' \u00b7 alert kept (' + r.ma_alert_ago + ' of ' + ALERT_HOLD + ' sessions)';
      }
    }
    const label = dir > 0 ? 'Alert buy' : dir < 0 ? 'Alert sell' : rating;
    return { label, alert: dir > 0 ? 'buy' : dir < 0 ? 'sell' : null, rating, note, rank: SIG_RANK[label] };
  }
  function sigCell(sg) {
    const c = document.createElement('td'); c.className = 'sigc';
    const sp = document.createElement('span');
    if (sg.alert) {
      sp.className = 'sig-alert ' + (sg.alert === 'buy' ? 'pos' : 'neg'); sp.textContent = sg.label;
      const n = document.createElement('span'); n.className = 'sig-note'; n.textContent = sg.note + ' · strategy: ' + sg.rating;
      c.append(sp, n);
    } else { sp.className = 'chip ' + (SIG_CLS[sg.label] || 'n'); sp.textContent = sg.label; c.appendChild(sp); }
    c.title = sg.alert ? sg.label + ': ' + sg.note + '. Strategy view: ' + sg.rating : 'Strategy view (the 50-day average is not about to touch the 200-day)';
    return c;
  }
"""

between("  // ---------- Signal column: 50/200-day cross alerts, otherwise the strategy rating ----------",
       "    c.title = sg.alert ? sg.label + ': ' + sg.note + '. Strategy view: ' + sg.rating : 'Strategy view (no 50/200-day cross in the last ' + SIG_DAYS + ' trading days)';\n    return c;\n  }\n", JS)

between('    <p class="hs-note" id="sig-note">', "Not advice on what to buy or sell.</p>",
        '''    <p class="hs-note" id="sig-note"><b>Signal.</b> <b class="pos">Alert buy</b> appears when the 50-day average is about to touch the 200-day from below, and <b class="neg">Alert sell</b> when it is about to touch it from above. "About to touch" means within 2% of the 200-day and closing in so that, at its pace over the last 5 sessions, it would meet it within 10 trading days. An alert stays for 3 trading days after the last session that met this (so it also covers the touch itself) unless the averages cross the other way. The rest of the time the column shows the strategy view behind the December column: Strong buy (consider adding), Buy (hold, add on dips), Hold, Sell (consider trimming) and Strong sell (consider selling). Not advice on what to buy or sell.</p>''')

between("      <p><b>Signal column.</b>", "often arrives after much of the move.</p>",
        '''      <p><b>Signal column.</b> Alert buy means the 50-day moving average is about to touch the 200-day from below (a golden cross is near) and Alert sell that it is about to touch it from above (a death cross is near). The test: the gap between them is under 2% of the 200-day, the 50-day has been on the same side for 6 sessions, and it has been closing in fast enough that, at its pace over the last 5 sessions, it would touch within 10 trading days. The alert is kept for 3 trading days after the last session that met the test, which also covers the cross itself, unless the averages cross the other way. The live prices are checked every minute, so an alert can appear before the daily rebuild. Otherwise the column translates the strategy view in the December column: Consider adding is Strong buy, Hold with adding on dips is Buy, Hold stays Hold, Consider trimming is Sell and Consider selling is Strong sell. A moving-average approach often fizzles out (the averages can turn away before touching), and a cross is a slow signal that comes after much of the move.</p>''')

open(PATH, "w", encoding="utf-8").write(s)
print("patched", len(s))
