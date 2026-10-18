"""One-off patch applied directly to the live index.html (not the local
build pipeline, so it never clobbers whatever data the daily bot last
baked in): speeds up the stock live-price ticker from 60s to 1s, and adds
an equivalent client-side live-price ticker for the crypto holdings table
and screen table, polling TradingView's public scanner every second too.
Both run entirely in the viewer's own browser, like the existing stock
ticker -- no server, no Claude, no GitHub Action involved after the page
has loaded. The signals, money flow, outlooks and monthly ranges are left
alone: those come from daily bars and genuinely do not change second to
second, so ticking them that often would just repaint the same numbers.
"""
import sys

INDEX = "/home/claude/stock/index.html"
s = open(INDEX, encoding="utf-8").read()


def rep(a, b, cnt=1):
    global s
    n = s.count(a)
    if n != cnt:
        print("MISMATCH expected %d got %d for: %r" % (cnt, n, a[:90]), file=sys.stderr)
        sys.exit(1)
    s = s.replace(a, b)


# ---------- 1. stock: 60s -> 1s ----------
rep("  LIVE.timer = setInterval(liveTick, 60000);\n",
    "  LIVE.timer = setInterval(liveTick, 1000);\n")
rep("about every minute while this tab is open",
    "about every second while this tab is open")

# ---------- 2. crypto header: live-status line + note ----------
rep(
    '    <p class="hs-asof">Prices and signals are to the 17 October close, from TradingView\'s screener and exchange daily bars. This board is not advice on what to buy or sell.</p>\n'
    '  </header>\n',
    '    <p class="hs-asof">Prices and signals are to the 17 October close, from TradingView\'s screener and exchange daily bars. This board is not advice on what to buy or sell.</p>\n'
    '    <div class="live" id="live-c" role="status" aria-live="polite"><span class="dot"></span><b id="live-msg-c">Connecting to TradingView…</b><span class="sep">·</span><span id="live-pv-c"></span><button type="button" id="live-btn-c">Pause</button></div>\n'
    '    <p class="hs-note" id="live-note-c">Price and today\'s move in the table below are read straight from TradingView by your browser, about every second while this tab is open (TradingView shows them 15 minutes late). The signal, money flow, outlook and monthly-range figures are the snapshot above and do not change until the next automatic update.</p>\n'
    '  </header>\n',
)

# ---------- 3. crypto: client-side live-price ticker ----------
CRYPTO_LIVE_JS = r'''
  // ---------- crypto: live prices straight from TradingView, every second ----------
  (function () {
    const liveElC = document.getElementById('live-c');
    if (!liveElC) return;
    const msgC = document.getElementById('live-msg-c');
    const pvC = document.getElementById('live-pv-c');
    const btnC = document.getElementById('live-btn-c');
    const CLIVE = { paused: false, last: null, busy: false };
    const clockC = (d) => d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    function setLiveC(cls, msg) { liveElC.classList.remove('ok', 'err'); if (cls) liveElC.classList.add(cls); msgC.textContent = msg; }
    async function liveTickCrypto(manual) {
      if (CLIVE.busy || (CLIVE.paused && !manual)) return;
      if (document.hidden && !manual) return;
      const rows = cRowsAll();
      if (!rows.length) return;
      CLIVE.busy = true;
      const ctl = new AbortController();
      const to = setTimeout(() => ctl.abort(), 12000);
      try {
        const syms = rows.map((r) => r.sym);
        const res = await fetch('https://scanner.tradingview.com/coin/scan', {
          method: 'POST', headers: { 'Content-Type': 'text/plain;charset=UTF-8' }, signal: ctl.signal,
          body: JSON.stringify({ symbols: { tickers: syms }, columns: ['close', 'change'] }),
        });
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const j = await res.json();
        const by = new Map((j.data || []).map((x) => [x.s, x.d]));
        let n = 0;
        rows.forEach((r) => {
          const d = by.get(r.sym);
          if (!d || d[0] == null) return;
          n += 1; r.price = d[0]; r.day_chg = d[1];
        });
        if (!n) throw new Error('no data');
        CLIVE.last = new Date();
        drawCryptoTable();
        if (typeof drawCryptoScreen === 'function') drawCryptoScreen();
        pvC.textContent = n + ' of ' + rows.length + ' coins';
        setLiveC('ok', 'Live from TradingView (15 min delayed) · updated ' + clockC(CLIVE.last));
      } catch (e) {
        setLiveC('err', CLIVE.last ? 'Could not reach TradingView; showing the prices from ' + clockC(CLIVE.last) : 'Live prices unavailable; showing the snapshot above');
      } finally { clearTimeout(to); CLIVE.busy = false; }
    }
    btnC.addEventListener('click', () => {
      CLIVE.paused = !CLIVE.paused;
      btnC.textContent = CLIVE.paused ? 'Resume' : 'Pause';
      if (CLIVE.paused) setLiveC('', 'Live updates paused' + (CLIVE.last ? ' · last update ' + clockC(CLIVE.last) : ''));
      else liveTickCrypto(true);
    });
    document.addEventListener('visibilitychange', () => { if (!document.hidden && !CLIVE.paused) liveTickCrypto(); });
    setInterval(liveTickCrypto, 1000);
    liveTickCrypto();
  })();
'''

rep(
    '</script>\n\n<script>\n  // ---------- two pages: My holdings and Strategy ----------',
    CRYPTO_LIVE_JS + '</script>\n\n<script>\n  // ---------- two pages: My holdings and Strategy ----------',
)

open(INDEX, "w", encoding="utf-8").write(s)
print("patched ok,", len(s), "bytes")
