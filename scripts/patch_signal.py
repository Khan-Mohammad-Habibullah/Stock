#!/usr/bin/env python3
"""Every holding / Former holdings: a "Signal" column.

  Alert buy   (bold green)  the 50-day average has just crossed above the 200-day (golden cross)
  Alert sell  (bold red)    the 50-day average has just crossed below the 200-day (death cross)
              An alert shows from the moment of the cross (the live prices from TradingView are checked every
              minute for a cross that has not reached the daily bars yet) and is kept for the next 3 trading
              days, unless the averages cross back first -- then the opposite alert replaces it.
  Strong buy / Buy / Hold / Sell / Strong sell   otherwise, the strategy view behind the "December" column:
              Consider adding / Hold, add on dips / Hold / Consider trimming / Consider selling by December.

Fields written by scripts/update_board.py: ma_state, ma_ago, sma50, sma200, rating (+ ma_cross as before).
Exact-text replace with count asserts, as in the other scripts/patch_*.py."""

PATH = "index.html"
s = open(PATH, encoding="utf-8").read()


def rep(old, new, cnt=1):
    global s
    n = s.count(old)
    assert n == cnt, f"expected {cnt}, found {n}: {old[:90]!r}"
    s = s.replace(old, new)


assert "signalOf" not in s, "already patched"

# ---- CSS
rep("  .ctl .dim { opacity: .45; }\n", """  .ctl .dim { opacity: .45; }
  td.sigc { white-space: nowrap; }
  .sig-alert { font-weight: 700; }
  .sig-note { display: block; font-size: 11px; font-weight: 400; color: var(--color-fg-muted); }
""")

# ---- headers (both tables), filter, notes
rep('          <th class="num" data-field="value_sek"><button data-k="value_sek">Value SEK</button></th>\n',
    '          <th class="num" data-field="value_sek"><button data-k="value_sek">Value SEK</button></th>\n'
    '          <th data-field="signal"><button data-k="signal_rank">Signal</button></th>\n')
rep('          <th class="num" data-field="value_sek"><button data-k="gone_by">Value SEK</button></th>\n',
    '          <th class="num" data-field="value_sek"><button data-k="gone_by">Value SEK</button></th>\n'
    '          <th data-field="signal"><button data-k="signal_rank">Signal</button></th>\n')
rep('      <select id="f-mkt" aria-label="Market">',
    '''      <select id="f-sig" aria-label="Signal">
        <option value="">All signals</option>
        <option>Alert buy</option><option>Strong buy</option><option>Buy</option><option>Hold</option><option>Sell</option><option>Strong sell</option><option>Alert sell</option>
      </select>
      <select id="f-mkt" aria-label="Market">''')
rep('    <p class="hs-note stale" id="stale-tbl" hidden></p>',
    '''    <p class="hs-note" id="sig-note"><b>Signal.</b> <b class="pos">Alert buy</b> appears the moment the 50-day average crosses above the 200-day, and <b class="neg">Alert sell</b> the moment it crosses below; either stays for 3 trading days after the cross unless the averages cross back first. The rest of the time the column shows the strategy view behind the December column: Strong buy (consider adding), Buy (hold, add on dips), Hold, Sell (consider trimming) and Strong sell (consider selling). Not advice on what to buy or sell.</p>
    <p class="hs-note stale" id="stale-tbl" hidden></p>''')
rep("Former holdings are every stock that was on the board and is not any more, dated by the first Nordnet export it was missing from.</p>",
    "Former holdings are every stock that was on the board and is not any more, dated by the first Nordnet export it was missing from.</p>\n"
    "      <p><b>Signal column.</b> A golden cross (50-day average rising above the 200-day) gives Alert buy and a death cross (falling below it) gives Alert sell, from the day it happens and for the next 3 trading days; the live prices are checked every minute, so a cross shows up the same day, before the daily rebuild confirms it. Otherwise the column translates the strategy view in the December column: Consider adding is Strong buy, Hold with adding on dips is Buy, Hold stays Hold, Consider trimming is Sell and Consider selling is Strong sell. The 50/200 cross is a slow, lagging signal and often arrives after much of the move.</p>")

# ---- helpers next to chipCls
rep("    return j >= 0 ? CLS[j] : 'n';\n  };\n", """    return j >= 0 ? CLS[j] : 'n';
  };
  // ---------- Signal column: 50/200-day cross alerts, otherwise the strategy rating ----------
  const SIG_DAYS = 3;   // an alert is kept for this many trading days after the cross day
  const SIG_RANK = { 'Alert buy': 6, 'Strong buy': 5, 'Buy': 4, 'Hold': 3, 'Sell': 2, 'Strong sell': 1, 'Alert sell': 0 };
  const SIG_CLS = { 'Strong buy': 'b2', 'Buy': 'b1', 'Hold': 'n', 'Sell': 'e1', 'Strong sell': 'e2' };
  const RATING_OF = { 'Consider adding': 'Strong buy', 'Hold, add on dips': 'Buy', 'Hold': 'Hold', 'Consider trimming': 'Sell', 'Consider selling by December': 'Strong sell' };
  function signalOf(r) {
    const rating = r.rating || RATING_OF[r.december] || 'Hold';
    const day = (d) => new Date(d + 'T12:00:00Z').toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
    let dir = null, note = '';
    const a = Number(r.live_sma50), b = Number(r.live_sma200);
    // a cross today: the averages from the live prices stand on the other side from the last daily bar (0.1% margin so a flat pair does not flicker)
    if (r.ma_state != null && r.live_sma50 != null && r.live_sma200 != null && isFinite(a) && isFinite(b) && b > 0 && Math.abs(a / b - 1) > 0.001) {
      const live = a > b ? 1 : -1;
      if (live !== r.ma_state) { dir = live > 0 ? 'buy' : 'sell'; note = (live > 0 ? 'golden' : 'death') + ' cross today'; }
    }
    if (!dir && r.ma_ago != null && r.ma_ago <= SIG_DAYS && r.ma_cross) {
      const p = String(r.ma_cross).split(' ');
      dir = p[0] === 'golden' ? 'buy' : 'sell';
      note = p[0] + ' cross ' + (p[1] ? day(p[1]) : '');
    }
    const label = dir === 'buy' ? 'Alert buy' : dir === 'sell' ? 'Alert sell' : rating;
    return { label, alert: dir, rating, note, rank: SIG_RANK[label] };
  }
  function sigCell(sg) {
    const c = document.createElement('td'); c.className = 'sigc';
    const sp = document.createElement('span');
    if (sg.alert) {
      sp.className = 'sig-alert ' + (sg.alert === 'buy' ? 'pos' : 'neg'); sp.textContent = sg.label;
      const n = document.createElement('span'); n.className = 'sig-note'; n.textContent = sg.note + ' \\u00b7 strategy: ' + sg.rating;
      c.append(sp, n);
    } else { sp.className = 'chip ' + (SIG_CLS[sg.label] || 'n'); sp.textContent = sg.label; c.appendChild(sp); }
    c.title = sg.alert ? sg.label + ': ' + sg.note + '. Strategy view: ' + sg.rating : 'Strategy view (no 50/200-day cross in the last ' + SIG_DAYS + ' trading days)';
    return c;
  }
""")

# ---- main table: state, filter, rows
rep("const state = { sort: 'value_sek', dir: -1, q: '', oct: '', lt: '', ltH: 'o1y', qH: 'o1y', mkt: '', dec: '', sflow: '', sel: null };",
    "const state = { sort: 'value_sek', dir: -1, q: '', oct: '', lt: '', ltH: 'o1y', qH: 'o1y', mkt: '', dec: '', sflow: '', sig: '', sel: null };")
rep("  fSflow.addEventListener('change', () => { state.sflow = fSflow.value; drawTable(); });\n",
    "  fSflow.addEventListener('change', () => { state.sflow = fSflow.value; drawTable(); });\n"
    "  const fSig = document.getElementById('f-sig');\n  fSig.addEventListener('change', () => { state.sig = fSig.value; drawTable(); });\n")
rep("""  function drawTable() {
    const all = rowsAll();
    let rows = all.filter((r) =>
      (!state.q || (r.name + ' ' + r.sym).toLowerCase().includes(state.q)) &&""",
    """  function drawTable() {
    const all = rowsAll();
    all.forEach((r) => { r._sig = signalOf(r); r.signal_rank = r._sig.rank; });
    let rows = all.filter((r) =>
      (!state.sig || r._sig.label === state.sig) &&
      (!state.q || (r.name + ' ' + r.sym).toLowerCase().includes(state.q)) &&""")
rep("""    return !((!state.q || (r.name + ' ' + r.sym).toLowerCase().includes(state.q)) &&""",
    """    return !((!state.sig || (r._sig && r._sig.label === state.sig)) &&
      (!state.q || (r.name + ' ' + r.sym).toLowerCase().includes(state.q)) &&""")
rep("""        td(fmtInt(r.value_sek), 'num'),
        td(r.price_live == null""", """        td(fmtInt(r.value_sek), 'num'),
        sigCell(r._sig),
        td(r.price_live == null""")

# ---- former table
rep("c.colSpan = 22; c.className = 'mut';", "c.colSpan = 23; c.className = 'mut';")
rep("      const k = st.sort;\n      rows.sort((a, b) => { const x = a[k]",
    "      rows.forEach((r) => { r._sig = signalOf(r); r.signal_rank = r._sig.rank; });\n      const k = st.sort;\n      rows.sort((a, b) => { const x = a[k]")
rep("""          td(fmtGone(r.gone_by), 'num gone'),
""", """          td(fmtGone(r.gone_by), 'num gone'),
          sigCell(r._sig),
""")

open(PATH, "w", encoding="utf-8").write(s)
print("patched", len(s))
