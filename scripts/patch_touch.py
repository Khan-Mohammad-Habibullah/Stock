#!/usr/bin/env python3
"""Every holding / Former holdings: a "Candle touch" column beside "Signal".

  Alert buy   blue, bold    the daily candle touched the 200-day average upwards (came up from below, high reached it)
  Alert buy   blue          ... the 50-day average upwards
  Alert sell  orange, bold  the daily candle touched the 200-day average downwards (came down from above, low reached it)
  Alert sell  orange        ... the 50-day average downwards
  dash        no touch on the latest daily candle

The latest candle is today's while TradingView's live prices are on (high and low of the session, previous close from the
live change; pre-market falls back to the last daily bar), otherwise the last daily bar of the rebuild (touch50, touch200, bar_date).
Exact-text replace with count asserts, as in the other scripts/patch_*.py."""

PATH = "index.html"
s = open(PATH, encoding="utf-8").read()


def rep(old, new, cnt=1):
    global s
    n = s.count(old)
    assert n == cnt, f"expected {cnt}, found {n}: {old[:90]!r}"
    s = s.replace(old, new)


assert "touchOf" not in s, "already patched"

# ---- CSS
rep("  .sig-note { display: block;", """  .tch { display: block; }
  .tch.buy { color: var(--series-0); }
  .tch.sell { color: var(--series-1); }
  .tch.big { font-weight: 700; }
  .sig-note { display: block;""")

# ---- headers, filter, notes
HDR = '          <th data-field="touch"><button data-k="touch_rank">Candle touch</button></th>\n'
rep('          <th data-field="signal"><button data-k="signal_rank">Signal</button></th>\n',
    '          <th data-field="signal"><button data-k="signal_rank">Signal</button></th>\n' + HDR, 2)
rep('      <select id="f-mkt" aria-label="Market">',
    '''      <select id="f-tch" aria-label="Candle touch">
        <option value="">All candle touches</option>
        <option value="buy">Candle touch: Alert buy</option><option value="sell">Candle touch: Alert sell</option><option value="none">Candle touch: none</option>
      </select>
      <select id="f-mkt" aria-label="Market">''')
rep('    <p class="hs-note stale" id="stale-tbl" hidden></p>',
    '''    <p class="hs-note" id="tch-note"><b>Candle touch.</b> <b style="color:var(--series-0)">Alert buy</b> in blue when the latest daily candle touches the 200-day average upwards (bold) or the 50-day average upwards, <b style="color:var(--series-1)">Alert sell</b> in orange when it touches the 200-day (bold) or the 50-day average downwards; a dash when it touches neither. "Upwards" means the candle came up from below the average and its high reached it, "downwards" that it came down from above and its low reached it (judged against the previous close). The latest candle is today's while the live prices are on, otherwise the last daily bar.</p>
    <p class="hs-note stale" id="stale-tbl" hidden></p>''')
rep("      <p><b>Signal column.</b>",
    "      <p><b>Candle touch column.</b> Alert buy in blue means the latest daily candle touched the 200-day moving average upwards (bold) or the 50-day one upwards; Alert sell in orange means it touched the 200-day (bold) or the 50-day downwards. A touch upwards is a candle that came up from below the average, judged by the previous close, and whose high reached it; a touch downwards is one that came down from above and whose low reached it. If both averages are touched the same day, both are shown. The candle is today's while TradingView's live prices are on (every minute) and the last daily bar otherwise, so an alert disappears when a later candle does not touch the average.</p>\n"
    "      <p><b>Signal column.</b>")

# ---- live: high and low of the session
rep("'premarket_volume', 'current_session'];", "'premarket_volume', 'current_session', 'high', 'low'];")
rep("r.live_macd = d[4]; r.live_macd_sig = d[5]; r.live_sma20 = d[6]; r.live_sma50 = d[7]; r.live_sma200 = d[8];",
    "r.live_macd = d[4]; r.live_macd_sig = d[5]; r.live_sma20 = d[6]; r.live_sma50 = d[7]; r.live_sma200 = d[8]; r.live_high = d[14]; r.live_low = d[15];")

# ---- JS helpers (after sigCell)
rep("""    c.title = sg.alert ? sg.label + ': ' + sg.note + '. Strategy view: ' + sg.rating : 'Strategy view (the 50-day average is not about to touch the 200-day)';
    return c;
  }
""", """    c.title = sg.alert ? sg.label + ': ' + sg.note + '. Strategy view: ' + sg.rating : 'Strategy view (the 50-day average is not about to touch the 200-day)';
    return c;
  }
  // ---------- Candle touch column: the latest daily candle against the 200- and 50-day averages ----------
  // up = came up from below (previous close under the average) and the high reached it; down = came down from above and the low reached it
  function touchOf(r) {
    let t200 = r.touch200, t50 = r.touch50, when = r.bar_date ? new Date(r.bar_date + 'T12:00:00Z').toLocaleDateString('en-GB', { day: 'numeric', month: 'short' }) + ' candle' : 'last daily candle';
    const hi = Number(r.live_high), lo = Number(r.live_low), px = Number(r.price_live), chg = Number(r.day_chg), a = Number(r.live_sma50), b = Number(r.live_sma200);
    if (r.session !== 'pre' && r.live_high != null && r.live_low != null && r.price_live != null && r.day_chg != null && r.live_sma50 != null && r.live_sma200 != null &&
        [hi, lo, px, chg, a, b].every(isFinite) && chg > -100) {
      const prev = px / (1 + chg / 100);
      const f = (m) => (m > 0 ? (prev < m && hi >= m ? 1 : prev > m && lo <= m ? -1 : 0) : 0);
      t200 = f(b); t50 = f(a); when = 'today\\u2019s candle';
    }
    const items = [];
    if (t200) items.push({ ma: 200, dir: t200 });
    if (t50) items.push({ ma: 50, dir: t50 });
    const rank = items.length ? (items[0].ma === 200 ? 4 : 3) * items[0].dir : 0;
    return { items, when, rank, known: t200 != null || t50 != null };
  }
  function touchCell(tc) {
    const c = document.createElement('td'); c.className = 'sigc';
    if (!tc.items.length) { c.textContent = '\\u2014'; c.classList.add('mut'); c.title = tc.known ? 'The latest candle touched neither average' : 'Needs 200 days of history'; return c; }
    tc.items.forEach((it) => {
      const sp = document.createElement('span'); sp.className = 'tch ' + (it.dir > 0 ? 'buy' : 'sell') + (it.ma === 200 ? ' big' : '');
      sp.textContent = it.dir > 0 ? 'Alert buy' : 'Alert sell';
      const n = document.createElement('span'); n.className = 'sig-note'; n.textContent = it.ma + '-day ' + (it.dir > 0 ? 'upwards' : 'downwards') + ' \\u00b7 ' + tc.when;
      c.append(sp, n);
    });
    c.title = tc.items.map((it) => 'Candle touched the ' + it.ma + '-day average ' + (it.dir > 0 ? 'upwards' : 'downwards') + ' (' + tc.when + ')').join('; ');
    return c;
  }
""")

# ---- main table: state, filter, sort value, cell
rep("sflow: '', sig: '', sel: null };", "sflow: '', sig: '', tch: '', sel: null };")
rep("  fSig.addEventListener('change', () => { state.sig = fSig.value; drawTable(); });\n",
    "  fSig.addEventListener('change', () => { state.sig = fSig.value; drawTable(); });\n"
    "  const fTch = document.getElementById('f-tch');\n  fTch.addEventListener('change', () => { state.tch = fTch.value; drawTable(); });\n"
    "  const tchOk = (r) => !state.tch || (state.tch === 'none' ? r._tch.items.length === 0 : r._tch.items.some((i) => i.dir === (state.tch === 'buy' ? 1 : -1)));\n")
rep("    all.forEach((r) => { r._sig = signalOf(r); r.signal_rank = r._sig.rank; });",
    "    all.forEach((r) => { r._sig = signalOf(r); r.signal_rank = r._sig.rank; r._tch = touchOf(r); r.touch_rank = r._tch.rank; });")
rep("      (!state.sig || r._sig.label === state.sig) &&\n", "      (!state.sig || r._sig.label === state.sig) &&\n      tchOk(r) &&\n")
rep("    return !((!state.sig || (r._sig && r._sig.label === state.sig)) &&\n",
    "    return !((!state.sig || (r._sig && r._sig.label === state.sig)) &&\n      (!r._tch || tchOk(r)) &&\n")
rep("        sigCell(r._sig),\n        td(r.price_live == null", "        sigCell(r._sig),\n        touchCell(r._tch),\n        td(r.price_live == null")

# ---- former table
rep("c.colSpan = 23; c.className = 'mut';", "c.colSpan = 24; c.className = 'mut';")
rep("      rows.forEach((r) => { r._sig = signalOf(r); r.signal_rank = r._sig.rank; });",
    "      rows.forEach((r) => { r._sig = signalOf(r); r.signal_rank = r._sig.rank; r._tch = touchOf(r); r.touch_rank = r._tch.rank; });")
rep("          sigCell(r._sig),\n", "          sigCell(r._sig),\n          touchCell(r._tch),\n")

open(PATH, "w", encoding="utf-8").write(s)
print("patched", len(s))
