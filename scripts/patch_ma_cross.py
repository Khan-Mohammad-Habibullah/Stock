#!/usr/bin/env python3
"""A "50/200 cross" column in "Every holding" (and, so the tables stay identical, in "Former holdings" and the
stock lookup row): bold green BUY on the day the 50-day moving average crosses above the 200-day, bold red SELL
on the day it crosses below, and a muted dash otherwise.

"The day" means the latest trading day of the data: the rebuild records the date of each stock's last cross
(ma_cross, e.g. "golden 2026-11-02"); it is a signal while that date is the board's latest bar date. While the
page is open it also compares TradingView's live 50- and 200-day averages with the state at the last close, so
a cross that happens during today's session shows up straight away. The signal drops off the next trading day.
Hovering a cell gives the last cross and its date. Exact-text replace with count asserts."""

PATH = "index.html"
s = open(PATH, encoding="utf-8").read()
assert "cross_sig" not in s, "already patched"


def rep(old, new, cnt=1):
    global s
    n = s.count(old)
    assert n == cnt, f"expected {cnt}, found {n}: {old[:90]!r}"
    s = s.replace(old, new)


CSS = """  .xs { font-weight: 700; letter-spacing: .02em; }
  .xs.buy { color: var(--color-ok); }
  .xs.sell { color: var(--color-bad); }
"""
rep("</style>\n\n<div class=\"hs\">", CSS + "</style>\n\n<div class=\"hs\">")

# --- headers (Every holding and Former holdings carry the sortable header, the lookup table a plain one) ---
TH = '<th class="num sec" data-field="vs50"><button data-k="vs50">vs 50-day</button></th>'
rep(TH, TH + '\n          <th data-field="cross_sig"><button data-k="cross_sig">50/200 cross</button></th>', 2)
rep('<th class="num sec">vs 50-day</th>', '<th class="num sec">vs 50-day</th>\n          <th>50/200 cross</th>', 1)

# --- helper ---
rep("  const fmtInt = d3.format(',');\n", r"""  const fmtInt = d3.format(',');
  // 50-day / 200-day average crossover: +1 = crossed above (BUY), -1 = crossed below (SELL), 0 = nothing today
  function crossInfo(r) {
    const none = { s: 0, tip: 'No 50/200-day cross in the data' };
    if (!r) return none;
    const m = /^(golden|death) (\d{4}-\d{2}-\d{2})$/.exec(r.ma_cross || '');
    if (!m) return none;
    const up = m[1] === 'golden';
    const b = dash.data('board_status');
    const barDate = b.status === 'ok' && b.data.length ? b.data[0].data_date : null;
    const nice = (d) => new Date(d + 'T12:00:00Z').toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
    const last = 'Last cross: 50-day ' + (up ? 'above' : 'below') + ' the 200-day on ' + nice(m[2]);
    // during the session: the live averages against the relation at the last close
    if (r.live_sma50 != null && r.live_sma200 != null && r.live_sma50 !== r.live_sma200) {
      const nowUp = r.live_sma50 > r.live_sma200;
      if (nowUp !== up) return { s: nowUp ? 1 : -1, tip: 'The 50-day average crossed ' + (nowUp ? 'above' : 'below') + ' the 200-day today (live). ' + last };
    }
    if (barDate && m[2] === barDate) return { s: up ? 1 : -1, tip: 'The 50-day average crossed ' + (up ? 'above' : 'below') + ' the 200-day on ' + nice(m[2]) + ' (latest trading day)' };
    return { s: 0, tip: last };
  }
  function crossTd(r) {
    const c = document.createElement('td'), x = crossInfo(r);
    c.title = x.tip;
    if (x.s) { const sp = document.createElement('span'); sp.className = 'xs ' + (x.s > 0 ? 'buy' : 'sell'); sp.textContent = x.s > 0 ? 'BUY' : 'SELL'; c.appendChild(sp); }
    else { c.className = 'mut'; c.textContent = r ? '—' : '—'; }
    return c;
  }
""")

# --- row builders ---
rep("""        td(r.macd, 'sec ' + (r.macd.startsWith('Bullish') ? 'pos' : 'neg')),
        td(signed(r.vs50), 'num sec ' + tone(r.vs50)),
""", """        td(r.macd, 'sec ' + (r.macd.startsWith('Bullish') ? 'pos' : 'neg')),
        td(signed(r.vs50), 'num sec ' + tone(r.vs50)),
        crossTd(r),
""")
rep("""        td(r.macd, 'sec ' + (r.macd == null ? 'mut' : String(r.macd).startsWith('Bullish') ? 'pos' : 'neg')),
        td(signed(r.vs50), 'num sec ' + tone(r.vs50)),
""", """        td(r.macd, 'sec ' + (r.macd == null ? 'mut' : String(r.macd).startsWith('Bullish') ? 'pos' : 'neg')),
        td(signed(r.vs50), 'num sec ' + tone(r.vs50)),
        crossTd(r),
""")
rep("""          td(r.macd, 'sec ' + (r.macd == null ? 'mut' : String(r.macd).startsWith('Bullish') ? 'pos' : 'neg')),
          td(signed(r.vs50), 'num sec ' + tone(r.vs50)),
""", """          td(r.macd, 'sec ' + (r.macd == null ? 'mut' : String(r.macd).startsWith('Bullish') ? 'pos' : 'neg')),
          td(signed(r.vs50), 'num sec ' + tone(r.vs50)),
          crossTd(r),
""")
# lookup row for a stock that is not held: no price history, so no cross signal
rep("""        td(signed(d.vs50), 'num sec ' + tone(d.vs50)),
        td(null, 'sec'),""", """        td(signed(d.vs50), 'num sec ' + tone(d.vs50)),
        crossTd(own),
        td(null, 'sec'),""")

# --- sorting: BUY first, then nothing, then SELL ---
rep("""    const k = state.sort, dir = state.dir;
    rows = rows.slice().sort((a, b) => {""", """    const k = state.sort, dir = state.dir;
    all.forEach((r) => { r.cross_sig = crossInfo(r).s; });
    rows = rows.slice().sort((a, b) => {""")


# --- Former holdings: same sort key, one more column to span ---
rep("      const k = st.sort;\n      rows.sort((a, b) =>", "      const k = st.sort;\n      rows.forEach((r) => { r.cross_sig = crossInfo(r).s; });\n      rows.sort((a, b) =>")

rep("c.colSpan = 22;", "c.colSpan = 23;")

# --- note under the table title ---
rep("Click a column to sort and a row to see every indicator for that holding.",
    "Click a column to sort and a row to see every indicator for that holding. The 50/200 cross column shows <b style=\"color:var(--color-ok)\">BUY</b> on the day a stock's 50-day average crosses above its 200-day and <b style=\"color:var(--color-bad)\">SELL</b> on the day it crosses below; on any other day it is empty (hover a cell for the last cross).")

open(PATH, "w", encoding="utf-8").write(s)
print("patched", len(s))
