"""One-off patch applied directly to the live index.html: adds a per-row
"open chart" link (the holding/coin name becomes a button) on all four
tables -- My holdings, Strategy's market screen, Crypto holdings, Crypto
strategy's screen -- that opens a modal with TradingView's own embeddable
Advanced Chart widget for that exact symbol: candlesticks, 50/200-day
moving averages, volume, MACD and Stochastic RSI preloaded, with
TradingView's own interval buttons (1m up to 1M, covering 15m/1h/4h/1D/1W)
and its own Indicators search (covering Williams Alligator, Bollinger
Bands, Pivot Points and anything else) built into the widget's toolbar --
so nothing needs to be hand-built to match "like TradingView".

Like the other scripts/patch_*.py one-offs, this edits the shipped
index.html in place and must NOT touch the embedded datasets, so it never
clobbers whatever the daily bot last wrote.
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


# ---------- 1. CSS for the modal and the name-as-link style ----------
rep(
    "@media (max-width:600px){#dash-root{padding:12px}.hs-card{padding:12px}.ctl select,.ctl input{min-width:0;max-width:100%}.hs,.hs>*{min-width:0}}\n</style>",
    "@media (max-width:600px){#dash-root{padding:12px}.hs-card{padding:12px}.ctl select,.ctl input{min-width:0;max-width:100%}.hs,.hs>*{min-width:0}}\n"
    ".chart-modal{position:fixed;inset:0;background:color-mix(in srgb, var(--color-fg) 55%, transparent);z-index:100;display:flex;align-items:center;justify-content:center;padding:16px}\n"
    ".chart-modal[hidden]{display:none}\n"
    ".chart-modal-inner{background:var(--color-bg);border-radius:12px;width:min(1100px,100%);height:min(720px,92vh);display:flex;flex-direction:column;box-shadow:0 20px 60px color-mix(in srgb, var(--color-fg) 30%, transparent);overflow:hidden}\n"
    ".chart-modal-head{display:flex;align-items:center;justify-content:space-between;padding:10px 14px;border-bottom:1px solid var(--color-border-line);flex:none}\n"
    ".chart-modal-head h3{margin:0;font-size:var(--cds-font-size-body);font-family:var(--font-anthropic-serif)}\n"
    ".chart-modal-close{border:none;background:transparent;font-size:22px;line-height:1;cursor:pointer;color:var(--color-fg-muted);padding:4px 10px;border-radius:6px}\n"
    ".chart-modal-close:hover{background:var(--color-panel);color:var(--color-fg)}\n"
    ".chart-modal-body{flex:1;min-height:0}\n"
    "#tv-chart-box{width:100%;height:100%}\n"
    ".chart-link{border:none;background:transparent;padding:0;font:inherit;color:inherit;text-decoration:underline;text-decoration-color:var(--color-border-line);cursor:pointer}\n"
    ".chart-link:hover{text-decoration-color:currentColor}\n"
    "</style>",
)

# ---------- 2. the modal's markup, right before the inlined d3 script ----------
rep(
    "</div>\n<script>// https://d3js.org",
    '<div class="chart-modal" id="chart-modal" hidden role="dialog" aria-modal="true" aria-labelledby="chart-modal-title">\n'
    '  <div class="chart-modal-inner">\n'
    '    <div class="chart-modal-head"><h3 id="chart-modal-title">Chart</h3>'
    '<button type="button" class="chart-modal-close" id="chart-modal-close" aria-label="Close chart">&times;</button></div>\n'
    '    <div class="chart-modal-body"><div id="tv-chart-box"></div></div>\n'
    "  </div>\n"
    "</div>\n"
    "</div>\n<script>// https://d3js.org",
)

# ---------- 3. the chart-opening JS + a shared clickable-name cell helper ----------
CHART_JS = r'''
  // ---------- per-row chart modal: TradingView's own embeddable chart ----------
  function nameTd(label, sym, cls) {
    const c = document.createElement('td'); c.className = cls || 'nm';
    const b = document.createElement('button'); b.type = 'button'; b.className = 'chart-link'; b.textContent = label;
    b.addEventListener('click', (e) => { e.stopPropagation(); openChart(sym, label); });
    c.appendChild(b);
    return c;
  }
  let tvScriptPromise = null;
  function loadTvScript() {
    if (!tvScriptPromise) {
      tvScriptPromise = new Promise((resolve, reject) => {
        const el = document.createElement('script');
        el.src = 'https://s3.tradingview.com/tv.js';
        el.onload = resolve; el.onerror = reject;
        document.head.appendChild(el);
      });
    }
    return tvScriptPromise;
  }
  const chartModal = document.getElementById('chart-modal');
  const chartTitle = document.getElementById('chart-modal-title');
  function closeChart() {
    chartModal.hidden = true;
    document.getElementById('tv-chart-box').replaceChildren();
  }
  document.getElementById('chart-modal-close').addEventListener('click', closeChart);
  chartModal.addEventListener('click', (e) => { if (e.target === chartModal) closeChart(); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !chartModal.hidden) closeChart(); });
  function openChart(sym, label) {
    if (!sym) return;
    chartTitle.textContent = label || sym;
    chartModal.hidden = false;
    const box = document.getElementById('tv-chart-box');
    box.replaceChildren();
    const dark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    loadTvScript().then(() => {
      if (chartModal.hidden) return; // closed again before the script finished loading
      new TradingView.widget({
        autosize: true,
        symbol: sym,
        interval: 'D',
        timezone: 'Etc/UTC',
        theme: dark ? 'dark' : 'light',
        style: '1',
        locale: 'en',
        enable_publishing: false,
        allow_symbol_change: true,
        withdateranges: true,
        studies: [
          { id: 'MASimple@tv-basicstudies', inputs: { length: 50 } },
          { id: 'MASimple@tv-basicstudies', inputs: { length: 200 } },
          'Volume@tv-basicstudies',
          'MACD@tv-basicstudies',
          'StochasticRSI@tv-basicstudies',
        ],
        container_id: 'tv-chart-box',
      });
    }).catch(() => {
      box.innerHTML = '<p class="hs-note" style="padding:16px">Could not load TradingView’s chart widget — check your connection and try again.</p>';
    });
  }
'''

rep(
    '</script>\n\n<script>\n  // ---------- two pages: My holdings and Strategy ----------',
    CHART_JS + '</script>\n\n<script>\n  // ---------- two pages: My holdings and Strategy ----------',
)

# ---------- 4. wire the four tables' name cells to open the chart ----------
rep("td(r.name, 'nm'),", "nameTd(r.name, r.sym),")
rep("td(r.name + ' (' + r.ticker + ')', 'nm'),", "nameTd(r.name + ' (' + r.ticker + ')', r.sym),", cnt=2)
rep(
    "nm.append(document.createTextNode(d.name + ' '));",
    "const nmBtn = document.createElement('button'); nmBtn.type = 'button'; nmBtn.className = 'chart-link'; nmBtn.textContent = d.name;\n"
    "        nmBtn.addEventListener('click', (e) => { e.stopPropagation(); openChart(d.sym, d.name); });\n"
    "        nm.append(nmBtn, document.createTextNode(' '));",
)

open(INDEX, "w", encoding="utf-8").write(s)
print("patched ok,", len(s), "bytes")
