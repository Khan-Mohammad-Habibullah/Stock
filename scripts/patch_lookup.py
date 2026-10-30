"""Add a "Look up any stock" feature to the Strategy tab: a search box where
the user types a company name or ticker and gets it scored with the exact
same rules-based reading used by "Strongest bullish readings by market"
(#screen) just above it -- not limited to the ~70 largest companies per
market that screen already loads, but genuinely any listed stock.

Entirely client-side (viewer's own browser, no server, no Claude): resolves
the name via TradingView's public symbol-search endpoint, then scores it
with the same 13 published readings and the same thresholds as the existing
screen, rendered in the same visual language (.chip/.rules/.mk/.lv/.own).
A direct EXCHANGE:TICKER (e.g. NASDAQ:TSLA) skips the search step.

Edits the shipped index.html in place, like the other scripts/patch_*.py
one-offs -- never touches the embedded datasets, and adds a new,
self-contained IIFE rather than modifying the existing market-screen IIFE,
so the proven "Strongest bullish readings" feature can't regress.
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


# ---------- 1. CSS ----------
rep(
    ".rules .lv { color: var(--color-fg-muted); margin-left: auto; padding-left: 8px; white-space: nowrap; }\n",
    ".rules .lv { color: var(--color-fg-muted); margin-left: auto; padding-left: 8px; white-space: nowrap; }\n"
    "  .ctl button { font: inherit; font-size: var(--cds-font-size-caption); padding: 6px 12px; border: 1px solid var(--color-border-line); border-radius: var(--cds-radius); background: var(--color-panel); color: var(--color-fg); cursor: pointer; }\n"
    "  .ctl button:hover { background: color-mix(in srgb, var(--color-fg) 6%, var(--color-panel)); }\n"
    "  .lookup-matches { display: flex; flex-wrap: wrap; gap: 6px; margin: 4px 0 10px; }\n"
    "  .lookup-matches button { font: inherit; font-size: var(--cds-font-size-caption); padding: 4px 10px; border: 1px solid var(--color-border-line); border-radius: 999px; background: var(--color-bg); color: var(--color-fg); cursor: pointer; }\n"
    "  .lookup-matches button:hover { background: var(--color-panel); }\n"
    "  .lookup-card { border: 1px solid var(--color-border-line); border-radius: var(--cds-radius); padding: 12px; margin-top: 8px; }\n"
    "  .lookup-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 4px; }\n",
    cnt=1,
)

# ---------- 2. HTML: a new card right after #screen, before #money ----------
rep(
    "        <tbody></tbody>\n"
    "      </table>\n"
    "    </div>\n"
    "  </section>\n"
    "\n"
    "  <section class=\"hs-card\" id=\"money\">",
    "        <tbody></tbody>\n"
    "      </table>\n"
    "    </div>\n"
    "  </section>\n"
    "\n"
    "  <section class=\"hs-card\" id=\"lookup\">\n"
    "    <h2>Look up any stock</h2>\n"
    "    <p class=\"hs-note\">Type a company name or ticker to score it the same way as the screen above &mdash; live from TradingView, not limited to the largest companies in each market. Not a recommendation.</p>\n"
    "    <form class=\"ctl\" id=\"lookup-form\">\n"
    "      <input id=\"lookup-q\" type=\"search\" placeholder=\"e.g. Tesla, or NASDAQ:TSLA\" aria-label=\"Company name or ticker\" autocomplete=\"off\">\n"
    "      <button type=\"submit\">Look up</button>\n"
    "    </form>\n"
    "    <div id=\"lookup-matches\" class=\"lookup-matches\"></div>\n"
    "    <p class=\"hs-note\" id=\"lookup-status\" aria-live=\"polite\"></p>\n"
    "    <div id=\"lookup-result\"></div>\n"
    "  </section>\n"
    "\n"
    "  <section class=\"hs-card\" id=\"money\">",
    cnt=1,
)

# ---------- 3. JS: new self-contained IIFE, right after the market-screen one ----------
LOOKUP_JS = r'''
  // ---------- Strategy tab: look up any stock (same scoring as the screen above) ----------
  (function () {
    const COLS = ['name', 'description', 'exchange', 'currency', 'close', 'change', 'volume', 'RSI', 'MACD.macd', 'MACD.signal', 'SMA50', 'SMA200',
      'Perf.1M', 'Perf.3M', 'ADX', 'ADX+DI', 'ADX-DI', 'ChaikinMoneyFlow', 'market_cap_basic', 'total_revenue_yoy_growth_ttm', 'net_margin_ttm',
      'recommendation_mark', 'price_target_average', 'sector'];
    const X = {}; COLS.forEach((c, i) => { X[c] = i; });
    const RULES = [
      { t: 'Price above its 50-day average', f: (d) => (d.close != null && d.sma50 != null ? d.close > d.sma50 : null), v: (d) => pctTxt(d.vs50) },
      { t: 'Price above its 200-day average', f: (d) => (d.close != null && d.sma200 != null ? d.close > d.sma200 : null), v: (d) => pctTxt(d.vs200) },
      { t: '50-day average above the 200-day', f: (d) => (d.sma50 != null && d.sma200 != null ? d.sma50 > d.sma200 : null), v: () => '' },
      { t: 'RSI between 50 and 75', f: (d) => (d.rsi != null ? d.rsi >= 50 && d.rsi <= 75 : null), v: (d) => (d.rsi == null ? '' : d.rsi.toFixed(0)) },
      { t: 'MACD above its signal line', f: (d) => (d.macd != null && d.macds != null ? d.macd > d.macds : null), v: () => '' },
      { t: 'Up over 1 month', f: (d) => (d.perf1m != null ? d.perf1m > 0 : null), v: (d) => pctTxt(d.perf1m) },
      { t: 'Up over 3 months', f: (d) => (d.perf3m != null ? d.perf3m > 0 : null), v: (d) => pctTxt(d.perf3m) },
      { t: 'ADX at least 20 and +DI above −DI', f: (d) => (d.adx != null && d.dip != null && d.dim != null ? d.adx >= 20 && d.dip > d.dim : null), v: (d) => (d.adx == null ? '' : 'ADX ' + d.adx.toFixed(0)) },
      { t: 'Chaikin money flow above zero', f: (d) => (d.cmf != null ? d.cmf > 0 : null), v: (d) => (d.cmf == null ? '' : d.cmf.toFixed(2)) },
      { t: 'Average analyst rating 2.0 or better', f: (d) => (d.rec != null ? d.rec <= 2 : null), v: (d) => (d.rec == null ? '' : d.rec.toFixed(1)) },
      { t: 'Price target at least 10% above price', f: (d) => (d.upside != null ? d.upside >= 10 : null), v: (d) => pctTxt(d.upside) },
      { t: 'Revenue growing year on year', f: (d) => (d.revg != null ? d.revg > 0 : null), v: (d) => pctTxt(d.revg) },
      { t: 'Net margin above zero', f: (d) => (d.margin != null ? d.margin > 0 : null), v: (d) => (d.margin == null ? '' : d.margin.toFixed(0) + '%') },
    ];
    const MIN_AVAIL = 8;
    function pctTxt(v) { return v == null ? '' : (v > 0 ? '+' : '') + v.toFixed(1) + '%'; }
    const num = (v) => (typeof v === 'number' && isFinite(v) ? v : null);
    function parse(row) {
      const g = (c) => row.d[X[c]];
      const d = {
        sym: row.s, tk: g('name'), name: g('description') || g('name'), cur: g('currency') || '', exch: g('exchange'),
        close: num(g('close')), change: num(g('change')), rsi: num(g('RSI')), macd: num(g('MACD.macd')), macds: num(g('MACD.signal')),
        sma50: num(g('SMA50')), sma200: num(g('SMA200')), perf1m: num(g('Perf.1M')), perf3m: num(g('Perf.3M')), adx: num(g('ADX')), dip: num(g('ADX+DI')), dim: num(g('ADX-DI')),
        cmf: num(g('ChaikinMoneyFlow')), mcap: num(g('market_cap_basic')), revg: num(g('total_revenue_yoy_growth_ttm')), margin: num(g('net_margin_ttm')),
        rec: num(g('recommendation_mark')), target: num(g('price_target_average')), sector: g('sector'),
      };
      d.vs50 = d.close != null && d.sma50 ? (d.close / d.sma50 - 1) * 100 : null;
      d.vs200 = d.close != null && d.sma200 ? (d.close / d.sma200 - 1) * 100 : null;
      d.upside = d.close && d.target ? (d.target / d.close - 1) * 100 : null;
      return d;
    }
    function score(d) {
      let pts = 0, avail = 0;
      d.checks = RULES.map((r) => { const ok = r.f(d); if (ok !== null) { avail += 1; if (ok) pts += 1; } return ok; });
      d.pts = pts; d.avail = avail;
      d.score = avail >= MIN_AVAIL ? Math.round((pts / avail) * 100) : null;
      return d;
    }
    const readOf = (sc) => (sc == null ? null : sc >= 85 ? 'Very strong' : sc >= 70 ? 'Strong' : 'Mixed');
    const readCls = (r) => (r === 'Very strong' ? 'b2' : r === 'Strong' ? 'b1' : 'n');
    const holdSet = () => { const h = dash.data('holdings'); return new Set(h.status === 'ok' ? h.data.map((r) => r.sym) : []); };
    const stripEm = (s) => (s || '').replace(/<\/?em>/g, '');

    const $ = (id) => document.getElementById(id);
    const form = $('lookup-form'), input = $('lookup-q'), matchesEl = $('lookup-matches'), statusEl = $('lookup-status'), resultEl = $('lookup-result');
    if (!form) return;

    async function searchSymbols(q) {
      const url = 'https://symbol-search.tradingview.com/symbol_search/v3/?text=' + encodeURIComponent(q) + '&hl=1&exchange=&lang=en&search_type=&domain=production&sort_by_country=US';
      const res = await fetch(url);
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const j = await res.json();
      const list = j.symbols || j.symbols_remaining || (Array.isArray(j) ? j : []);
      const seen = new Set();
      return list.filter((it) => it.type === 'stock' || it.type === 'dr').map((it) => ({
        sym: it.exchange + ':' + stripEm(it.symbol), name: stripEm(it.description), exch: it.exchange,
      })).filter((it) => (seen.has(it.sym) ? false : (seen.add(it.sym), true))).slice(0, 8);
    }

    async function fetchOne(sym) {
      const res = await fetch('https://scanner.tradingview.com/global/scan', {
        method: 'POST', headers: { 'Content-Type': 'text/plain;charset=UTF-8' },
        body: JSON.stringify({ symbols: { tickers: [sym] }, columns: COLS }),
      });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const j = await res.json();
      if (!j.data || !j.data.length) throw new Error('no data');
      return score(parse(j.data[0]));
    }

    function renderResult(d) {
      const own = holdSet();
      const card = document.createElement('div'); card.className = 'lookup-card';
      const h = document.createElement('div'); h.className = 'lookup-head';
      const nmBtn = document.createElement('button'); nmBtn.type = 'button'; nmBtn.className = 'chart-link'; nmBtn.textContent = d.name + ' (' + d.tk + ')';
      nmBtn.addEventListener('click', () => openChart(d.sym, d.name));
      h.appendChild(nmBtn);
      if (own.has(d.sym)) { const o = document.createElement('span'); o.className = 'own'; o.textContent = 'in your holdings'; h.appendChild(o); }
      if (d.score != null) {
        const chip = document.createElement('span'); chip.className = 'chip ' + readCls(readOf(d.score)); chip.textContent = readOf(d.score) + ' · ' + d.score; h.appendChild(chip);
      }
      card.appendChild(h);
      const sum = document.createElement('p'); sum.className = 'hs-note';
      const bits = [];
      if (d.close != null) bits.push(plain(d.close, d.close < 10 ? 3 : 2) + ' ' + d.cur);
      if (d.change != null) bits.push(signed(d.change, 2) + '% today');
      if (d.sector) bits.push(d.sector);
      if (d.exch) bits.push(d.exch);
      bits.push(d.score != null ? (d.pts + ' of ' + d.avail + ' readings point up') : 'not enough published readings to score');
      sum.textContent = bits.join(' · ');
      card.appendChild(sum);
      const ul = document.createElement('ul'); ul.className = 'rules';
      RULES.forEach((r, i) => {
        const ok = d.checks[i];
        const li = document.createElement('li');
        const mk = document.createElement('span'); mk.className = 'mk ' + (ok === true ? 'pos' : ok === false ? 'neg' : 'mut'); mk.textContent = ok === true ? '✓' : ok === false ? '✗' : '–';
        const t = document.createElement('span'); t.textContent = r.t;
        const lv = document.createElement('span'); lv.className = 'lv'; lv.textContent = ok === null ? 'no data' : r.v(d);
        li.append(mk, t, lv); ul.appendChild(li);
      });
      card.appendChild(ul);
      resultEl.replaceChildren(card);
    }

    async function pickSymbol(sym, label) {
      matchesEl.replaceChildren();
      statusEl.textContent = 'Loading ' + label + ' from TradingView…';
      resultEl.replaceChildren();
      try {
        const d = await fetchOne(sym);
        statusEl.textContent = 'Live from TradingView (15 min delayed).';
        renderResult(d);
      } catch (e) {
        statusEl.textContent = 'Could not load ' + label + ' from TradingView. Try again, or use its exchange:ticker form (e.g. NASDAQ:TSLA).';
      }
    }

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const q = input.value.trim();
      if (!q) return;
      matchesEl.replaceChildren(); resultEl.replaceChildren();
      if (/^[A-Za-z][A-Za-z0-9_]*:[A-Za-z0-9._-]+$/.test(q)) { await pickSymbol(q.toUpperCase(), q); return; }
      statusEl.textContent = 'Searching…';
      try {
        const matches = await searchSymbols(q);
        if (!matches.length) { statusEl.textContent = 'No matching stock found. Try its exchange:ticker form (e.g. NASDAQ:TSLA).'; return; }
        if (matches.length === 1) { await pickSymbol(matches[0].sym, matches[0].name); return; }
        statusEl.textContent = 'Several matches — pick one:';
        matches.forEach((m) => {
          const b = document.createElement('button'); b.type = 'button'; b.textContent = m.name + ' (' + m.sym + ')';
          b.addEventListener('click', () => pickSymbol(m.sym, m.name));
          matchesEl.appendChild(b);
        });
      } catch (e) {
        statusEl.textContent = 'Could not search TradingView right now. Try its exchange:ticker form (e.g. NASDAQ:TSLA).';
      }
    });
  })();
'''

rep(
    "  // ---------- crypto: My crypto holdings and Crypto strategy ----------",
    LOOKUP_JS + "\n  // ---------- crypto: My crypto holdings and Crypto strategy ----------",
    cnt=1,
)

open(INDEX, "w", encoding="utf-8").write(s)
print("patched ok,", len(s), "bytes")
