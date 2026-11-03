#!/usr/bin/env python3
"""Look up any stock: add the Signal and Candle touch columns (run after patch_touch_v3.py).

A stock you own gets the exact cells of "Every holding" (signalOf / touchOf on its row). Any other stock has no stored bars, so the
scanner's own history is used: TradingView's scanner answers the latest bar and the two before it (field[1], field[2]) for close, high,
low, SMA50 and SMA200, so
  Signal       the strategy view (December) as Strong buy ... Strong sell; Alert buy / Alert sell when the 50-day is about to touch the 200-day
               (same test as the board, but over 3 daily gaps instead of 6) or crossed in the last 2 sessions (kept as on the board)
  Candle touch the same four events, for the latest candle and the one before it (the board keeps them 3 sessions)."""
PATH = "index.html"
s = open(PATH, encoding="utf-8").read()
assert "lookupRow" not in s, "already patched"


def rep(old, new, cnt=1):
    global s
    n = s.count(old)
    assert n == cnt, f"expected {cnt}, found {n}: {old[:90]!r}"
    s = s.replace(old, new)


# ---- shared helpers: approachOf works on any window of 3+ gaps (the board still passes 6); touchOf knows lookups with no event
rep("if (w.length < 6 || w.some(", "if (w.length < 3 || w.some(")
rep("const eta = Math.abs(now) / (closing / 5);", "const eta = Math.abs(now) / (closing / (w.length - 1));")
rep("if (Array.isArray(r.ma_gap) && r.ma_gap.length === 5 && r.live_sma50", "if (Array.isArray(r.ma_gap) && r.ma_gap.length >= 2 && r.live_sma50")
rep("const known = r.tch !== undefined && (r.tch !== null || r.bar_date != null);", "const known = r.tch !== undefined && (r.tch !== null || r.bar_date != null || r.tch_known);")
rep("(day ? day + ' candle' : 'last daily candle')", "(day ? day + ' candle' : 'latest daily candle')")

# ---- header
rep("""          <th class="num">Value SEK</th>
          <th class="num">Price now</th>""", """          <th class="num">Value SEK</th>
          <th data-field="signal">Signal</th>
          <th data-field="touch">Candle touch</th>
          <th class="num">Price now</th>""")

# ---- scanner columns and history
rep("""      'recommendation_mark', 'price_target_average'];
    const X = {}; COLS.forEach""", """      'recommendation_mark', 'price_target_average',
      'high', 'low', 'close[1]', 'close[2]', 'high[1]', 'low[1]', 'high[2]', 'low[2]', 'SMA50[1]', 'SMA50[2]', 'SMA200[1]', 'SMA200[2]'];
    const X = {}; COLS.forEach""")
rep("""        pe: num(g('price_earnings_ttm')), rec: num(g('recommendation_mark')), target: num(g('price_target_average')),
      };
      d.vs50 = d.close != null && d.sma50 ? (d.close / d.sma50 - 1) * 100 : null;""", """        pe: num(g('price_earnings_ttm')), rec: num(g('recommendation_mark')), target: num(g('price_target_average')),
      };
      // the latest bar and the two before it (index 0 = latest) for the Signal and Candle touch columns
      d.hist = [0, 1, 2].map((k) => { const f = (n) => num(g(k ? n + '[' + k + ']' : n)); return { c: f('close'), h: f('high'), l: f('low'), m50: f('SMA50'), m200: f('SMA200') }; });
      d.vs50 = d.close != null && d.sma50 ? (d.close / d.sma50 - 1) * 100 : null;""")

# ---- the pseudo-row that signalOf / touchOf read
rep("""    // ----- result row
    function cellsFor(d) {""", """    // ----- Signal and Candle touch for a stock with no stored bars: the scanner's latest bar and the two before it
    const SIG_RULES = ['Signal rules (this lookup)',
      'Alert buy / Alert sell: the 50-day MA is about to touch the 200-day MA from below / above (within 2% and closing in, so it would touch within 10 sessions), or crossed it in the last 2 sessions. A lookup only has 3 daily readings, so the pace is taken over 2 sessions, not 5.',
      'Otherwise the strategy view as Strong buy, Buy, Hold, Sell or Strong sell, from the December column.'].join('\\n');
    function lookupRow(d, december) {
      const H = d.hist || [], ok = (v) => v != null && isFinite(v);
      const r = { rating: december ? RATING_OF[december] : null, live_sma50: d.sma50, live_sma200: d.sma200 };
      const gap = H.map((x) => (ok(x.m50) && ok(x.m200) && x.m200 > 0 ? (x.m50 - x.m200) / x.m200 * 100 : null));   // [latest, 1 ago, 2 ago]
      if (gap.every((x) => x != null)) {
        r.ma_gap = [gap[2], gap[1]];
        for (let k = 0; k <= 1; k++) {   // a cross in the last 2 sessions: the sign of the gap changed
          if ((gap[k] > 0) !== (gap[k + 1] > 0) && gap[k] !== 0) { r.ma_alert = gap[k] > 0 ? 1 : -1; r.ma_alert_ago = k + 1; r.ma_ago = k; r.ma_cross = (gap[k] > 0 ? 'golden' : 'death') + ' cross'; break; }
        }
      }
      // candle events: bar k against the close before it (close[k+1]); only the latest two bars have that
      const ev = (k) => {
        const b = H[k], pc = H[k + 1] && H[k + 1].c;
        if (!b || ![b.c, b.h, b.l, b.m50, b.m200, pc].every(ok)) return null;
        const e = [];
        if (pc < b.m200 && b.m200 <= b.h) e.push('buy200');
        if (pc > b.m200 && b.m200 >= b.l) e.push('sell200');
        if (b.m50 > b.m200 && pc > b.m50 && b.m50 >= b.l && b.c > b.m50) e.push('buy50');
        if (b.m50 < b.m200 && pc < b.m50 && b.m50 <= b.h && b.c < b.m50) e.push('sell50');
        return e;
      };
      const e0 = ev(0), e1 = ev(1);
      if (e0 != null && e1 != null) {
        r.tch_known = true; r.tch = null; r.tch_ago = null;
        if (e0.length) { r.tch = e0; r.tch_ago = 0; } else if (e1.length) { r.tch = e1; r.tch_ago = 1; }
      }
      return r;
    }
    document.querySelectorAll('#lookup-tbl th[data-field]').forEach((th) => { th.title = th.dataset.field === 'touch' ? TCH_RULES : SIG_RULES; th.style.cursor = 'help'; });
    const lookupSig = (r) => { const sg = signalOf(r); if (!sg.alert && !r.rating) { const c = document.createElement('td'); c.textContent = '\\u2014'; c.className = 'mut'; return c; } return sigCell(sg); };

    // ----- result row
    function cellsFor(d) {""")
rep("""      const macdOk = d.macd != null && d.macds != null;
      return [
        nameTd(d.name, d.sym, null, null),
        td(own ? fmtInt(own.value_sek) : null, 'num'),
""", """      const macdOk = d.macd != null && d.macds != null;
      const lr = lookupRow(d, december);
      return [
        nameTd(d.name, d.sym, null, null),
        td(own ? fmtInt(own.value_sek) : null, 'num'),
        lookupSig(lr),
        touchCell(touchOf(lr)),
""")
rep("""        td(fmtInt(r.value_sek), 'num'),
        td(price == null ? null : plain(price, price < 10 ? 3 : 2) + ' ' + r.cur + (hasLive""", """        td(fmtInt(r.value_sek), 'num'),
        sigCell(signalOf(r)),
        touchCell(touchOf(r)),
        td(price == null ? null : plain(price, price < 10 ? 3 : 2) + ' ' + r.cur + (hasLive""")
rep("      if (!sectorFlow(d)) note +=", "      note += ' Signal and Candle touch use the latest daily candle and the two before it, which is all a live lookup gives: the \\u201cabout to touch\\u201d test looks at 3 daily gaps instead of 6, and a candle touch is kept for the latest and the previous session instead of 3, so they can miss alerts that \\u201cEvery holding\\u201d would show.';\n      if (!sectorFlow(d)) note +=")

open(PATH, "w", encoding="utf-8").write(s)
print("patched", len(s))
