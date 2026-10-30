#!/usr/bin/env python3
"""Rework the Strategy tab's "Look up any stock" feature (v1 -> v2):
   - autosuggest dropdown after 2+ typed chars (no submit button)
   - search by plain name or bare ticker (no exchange prefix needed)
   - result rendered as a single-row table with the exact "Every holding" header
   - clicking the name opens the TradingView chart modal, like every other row
Operates directly on the committed index.html, same pattern as every prior
scripts/patch_*.py in this repo: exact-string replace, asserting count."""
import re

PATH = "index.html"
s = open(PATH, encoding="utf-8").read()
orig_len = len(s)


def rep(old, new, cnt=1):
    global s
    n = s.count(old)
    assert n == cnt, f"expected {cnt} occurrence(s), found {n}: {old[:80]!r}"
    s = s.replace(old, new, cnt)


# ---------- 1. CSS: drop the v1 card/matches styles, add autosuggest + result-table styles ----------
rep(
    """  .lookup-matches { display: flex; flex-wrap: wrap; gap: 6px; margin: 4px 0 10px; }
  .lookup-matches button { font: inherit; font-size: var(--cds-font-size-caption); padding: 4px 10px; border: 1px solid var(--color-border-line); border-radius: 999px; background: var(--color-bg); color: var(--color-fg); cursor: pointer; }
  .lookup-matches button:hover { background: var(--color-panel); }
  .lookup-card { border: 1px solid var(--color-border-line); border-radius: var(--cds-radius); padding: 12px; margin-top: 8px; }
  .lookup-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 4px; }
""",
    """  .lookup-box { position: relative; }
  .lookup-box input[type="search"] { width: 100%; max-width: 28rem; }
  .lookup-sugg { position: absolute; top: 100%; left: 0; right: 0; max-width: 28rem; z-index: 20; margin: 2px 0 0; padding: 4px; list-style: none; background: var(--color-bg); border: 1px solid var(--color-border-line); border-radius: var(--cds-radius); max-height: 280px; overflow-y: auto; box-shadow: 0 8px 24px color-mix(in srgb, var(--color-fg) 14%, transparent); }
  .lookup-sugg li { display: flex; gap: 8px; align-items: baseline; padding: 6px 8px; border-radius: 6px; cursor: pointer; }
  .lookup-sugg li:hover, .lookup-sugg li.active { background: var(--color-panel); }
  .lookup-sugg .tk { color: var(--color-fg-muted); font-size: var(--cds-font-size-caption); white-space: nowrap; }
""",
    1,
)

# ---------- 2. HTML: replace the form + matches + result div with an input + suggestion list + result table ----------
rep(
    """  <section class="hs-card" id="lookup">
    <h2>Look up any stock</h2>
    <p class="hs-note">Type a company name or ticker to score it the same way as the screen above &mdash; live from TradingView, not limited to the largest companies in each market. Not a recommendation.</p>
    <form class="ctl" id="lookup-form">
      <input id="lookup-q" type="search" placeholder="e.g. Tesla, or NASDAQ:TSLA" aria-label="Company name or ticker" autocomplete="off">
      <button type="submit">Look up</button>
    </form>
    <div id="lookup-matches" class="lookup-matches"></div>
    <p class="hs-note" id="lookup-status" aria-live="polite"></p>
    <div id="lookup-result"></div>
  </section>""",
    """  <section class="hs-card" id="lookup">
    <h2>Look up any stock</h2>
    <p class="hs-note">Type at least 2 letters of a company name or ticker &mdash; no exchange needed &mdash; and see it in the same table as "Every holding", live from TradingView. Not a recommendation.</p>
    <div class="ctl lookup-box">
      <input id="lookup-q" type="search" placeholder="e.g. Tesla, or TSLA" aria-label="Company name or ticker" autocomplete="off" role="combobox" aria-autocomplete="list" aria-expanded="false">
      <ul id="lookup-sugg" class="lookup-sugg" role="listbox" hidden></ul>
    </div>
    <p class="hs-note" id="lookup-status" aria-live="polite"></p>
    <div class="tbl-wrap" id="lookup-result" hidden>
      <table class="hold" id="lookup-tbl">
        <thead><tr>
          <th>Holding</th>
          <th class="num">Value SEK</th>
          <th class="num">Price now</th>
          <th class="num">Today</th>
          <th class="num">1 month</th>
          <th>Money flow</th>
          <th class="num">RSI</th>
          <th class="sec">MACD</th>
          <th class="num sec">vs 50-day</th>
          <th class="sec">Alligator</th>
          <th class="sec"><span class="mo3">Oct</span> CPR</th>
          <th class="sec">Bollinger</th>
          <th class="num sec">Up/down vol</th>
          <th><span class="mo">October</span></th>
          <th>1 year</th>
          <th class="sec">3 years</th>
          <th>5 years</th>
          <th>December</th>
          <th class="num sec">Revenue growth</th>
          <th class="num sec">Net margin</th>
          <th class="num sec">P/E</th>
          <th class="sec">Analysts</th>
        </tr></thead>
        <tbody></tbody>
      </table>
    </div>
    <p class="hs-note" id="lookup-note"></p>
  </section>""",
    1,
)

# ---------- 3. JS: replace the whole v1 lookup IIFE with the v2 implementation ----------
OLD_JS = """  // ---------- Strategy tab: look up any stock (same scoring as the screen above) ----------
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
    const stripEm = (s) => (s || '').replace(/<\\/?em>/g, '');

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
  })();"""

NEW_JS = r"""  // ---------- Strategy tab: look up any stock, rendered the same way as "Every holding" ----------
  (function () {
    const COLS = ['name', 'description', 'exchange', 'currency', 'sector', 'industry',
      'close', 'change', 'Perf.1M',
      'RSI', 'MACD.macd', 'MACD.signal', 'SMA20', 'SMA50', 'SMA200', 'BB.upper', 'BB.lower',
      'Pivot.M.Classic.Middle', 'Pivot.M.Classic.R1', 'Pivot.M.Classic.S1',
      'ChaikinMoneyFlow', 'ADX', 'ADX+DI', 'ADX-DI',
      'market_cap_basic', 'total_revenue_yoy_growth_ttm', 'net_margin_ttm', 'price_earnings_ttm',
      'recommendation_mark', 'price_target_average'];
    const X = {}; COLS.forEach((c, i) => { X[c] = i; });
    const num = (v) => (typeof v === 'number' && isFinite(v) ? v : null);
    const clip = (v, a, b) => Math.max(a, Math.min(b, v));
    const MARKET_OF_EXCH = { NASDAQ: 'US', NYSE: 'US', AMEX: 'US', OMXSTO: 'Sweden', OSL: 'Norway', TSX: 'Canada' };
    const stripEm = (s) => (s || '').replace(/<\/?em>/g, '');

    function bucket5(v, hi, mid) {
      return v >= hi ? 'Positive' : v >= mid ? 'Leaning positive' : v > -mid ? 'Mixed' : v > -hi ? 'Leaning negative' : 'Negative';
    }

    function parse(row) {
      const g = (c) => row.d[X[c]];
      const d = {
        sym: row.s, tk: g('name'), name: g('description') || g('name'), cur: g('currency') || '', exch: g('exchange'),
        sector: g('sector'), industry: g('industry'),
        close: num(g('close')), change: num(g('change')), perf1m: num(g('Perf.1M')),
        rsi: num(g('RSI')), macd: num(g('MACD.macd')), macds: num(g('MACD.signal')),
        sma20: num(g('SMA20')), sma50: num(g('SMA50')), sma200: num(g('SMA200')),
        bbU: num(g('BB.upper')), bbL: num(g('BB.lower')),
        pivM: num(g('Pivot.M.Classic.Middle')), pivR1: num(g('Pivot.M.Classic.R1')), pivS1: num(g('Pivot.M.Classic.S1')),
        cmf: num(g('ChaikinMoneyFlow')), adx: num(g('ADX')), dip: num(g('ADX+DI')), dim: num(g('ADX-DI')),
        mcap: num(g('market_cap_basic')), revg: num(g('total_revenue_yoy_growth_ttm')), margin: num(g('net_margin_ttm')),
        pe: num(g('price_earnings_ttm')), rec: num(g('recommendation_mark')), target: num(g('price_target_average')),
      };
      d.vs50 = d.close != null && d.sma50 ? (d.close / d.sma50 - 1) * 100 : null;
      d.vs200 = d.close != null && d.sma200 ? (d.close / d.sma200 - 1) * 100 : null;
      d.upside = d.close && d.target ? (d.target / d.close - 1) * 100 : null;

      // "Oct CPR": classic monthly pivot, same formula family calc.js already uses (R1 = 2P-L, S1 = 2P-H => TC/BC follow)
      if (d.pivM != null && d.pivR1 != null && d.pivS1 != null && d.close != null) {
        const TC = (d.pivR1 + d.pivS1) / 2, BC = 2 * d.pivM - (d.pivR1 + d.pivS1) / 2;
        const top = Math.max(TC, BC), bot = Math.min(TC, BC);
        d.cpr = d.close > top ? 'Above' : d.close < bot ? 'Below' : 'Inside';
      } else d.cpr = null;

      // Bollinger state from the band TradingView already computes
      if (d.bbU != null && d.bbL != null && d.close != null && d.bbU > d.bbL) {
        const pctb = (d.close - d.bbL) / (d.bbU - d.bbL);
        d.bollinger = d.close < d.bbL ? 'Below lower band' : d.close > d.bbU ? 'Above upper band' : pctb >= 0.8 ? 'Riding upper band' : pctb <= 0.2 ? 'Riding lower band' : 'Mid-range';
      } else d.bollinger = null;

      // Money flow: this stock's own Chaikin money flow (a live snapshot has no sector-rotation history to rank it against others)
      d.sflow = d.cmf == null ? null : d.cmf > 0.05 ? 'Money coming in' : d.cmf < -0.05 ? 'Money leaving' : 'No clear direction';

      // "October" signal built only from what one live snapshot can give -- no Alligator, candlestick pattern,
      // 55-day breakout or up/down volume, which all need bar history "Every holding" fetches separately
      let sc = 0, avail = 0;
      if (d.rsi != null) { avail++; if (d.rsi >= 55 && d.rsi <= 75) sc += 1; else if (d.rsi < 45) sc -= 1; }
      if (d.macd != null && d.macds != null) { avail++; sc += d.macd > d.macds ? 1 : -1; }
      if (d.close != null && d.sma20 != null && d.sma50 != null) { avail++; if (d.close > d.sma20 && d.close > d.sma50) sc += 1; else if (d.close < d.sma20 && d.close < d.sma50) sc -= 1; }
      if (d.cpr) { avail++; sc += d.cpr === 'Above' ? 1 : d.cpr === 'Below' ? -1 : 0; }
      if (d.cmf != null) { avail++; if (d.cmf > 0.05) sc += 1; else if (d.cmf < -0.05) sc -= 1; }
      if (d.adx != null && d.dip != null && d.dim != null) { avail++; if (d.adx >= 20 && d.dip > d.dim) sc += 1; else if (d.adx >= 20 && d.dim > d.dip) sc -= 1; }
      if (d.bollinger === 'Above upper band') sc += 0.5; else if (d.bollinger === 'Below lower band') sc -= 0.5;
      d.oct_avail = avail;
      if (avail < 4) { d.oct_signal = null; } else {
        const frac = sc / avail;
        d.oct_signal = frac >= 0.6 ? 'Bullish' : frac >= 0.25 ? 'Mildly bullish' : frac > -0.25 ? 'Neutral' : frac > -0.6 ? 'Mildly bearish' : 'Bearish';
      }

      // 1-year: trend vs 200-day average, analyst rating, price target -- same inputs the board uses, simple weights instead of a fitted model
      let o1 = 0, o1n = 0;
      if (d.vs200 != null) { o1 += clip(d.vs200 / 15, -2, 2); o1n++; }
      if (d.rec != null) { o1 += clip(2 - d.rec, -1.5, 1.5); o1n++; }
      if (d.upside != null) { o1 += clip(d.upside / 20, -1, 1.5); o1n++; }
      d.o1y = o1n ? bucket5(o1, 2, 0.7) : null;
      // 3-year: revenue growth, margin, valuation
      let o3 = 0, o3n = 0;
      if (d.revg != null) { o3 += clip(d.revg / 15, -2.5, 3); o3n++; }
      if (d.margin != null) { o3 += clip(d.margin / 12, -2.5, 3); o3n++; }
      if (d.pe != null) { o3 += d.pe > 0 && d.pe <= 18 ? 1 : d.pe > 45 ? -1 : 0; o3n++; }
      d.o3y = o3n ? bucket5(o3, 2.5, 0.8) : null;
      // 5-year: margin, size, growth
      let o5 = 0, o5n = 0;
      if (d.margin != null) { o5 += clip(d.margin / 12, -2.5, 3); o5n++; }
      if (d.mcap != null) { o5 += d.mcap >= 1e11 ? 1 : d.mcap < 1e9 ? -1 : 0; o5n++; }
      if (d.revg != null) { o5 += clip(d.revg / 20, -2, 2); o5n++; }
      d.o5y = o5n ? bucket5(o5, 2.5, 0.8) : null;
      return d;
    }

    const holdSet = () => { const h = dash.data('holdings'); return new Map(h.status === 'ok' ? h.data.map((r) => [r.sym, r]) : []); };
    function sectorFlow(d) {
      const fd = dash.data('flows');
      if (fd.status !== 'ok') return null;
      const market = MARKET_OF_EXCH[d.exch] || 'Europe';
      let hit = d.industry && fd.data.find((f) => f.market === market && f.level === 'industry' && f.group === d.industry);
      if (!hit) hit = d.sector && fd.data.find((f) => f.market === market && f.level === 'sector' && f.group === d.sector);
      return hit || null;
    }
    function decemberOf(d, flow) {
      const parts = [];
      if (flow) parts.push([flow.flow_score, 0.42]);
      if (d.oct_signal != null) parts.push([{ Bullish: 5, 'Mildly bullish': 2.5, Neutral: 0, 'Mildly bearish': -2.5, Bearish: -5 }[d.oct_signal], 0.36]);
      if (d.o1y != null) parts.push([{ Positive: 4, 'Leaning positive': 1.5, Mixed: 0, 'Leaning negative': -1.5, Negative: -4 }[d.o1y], 0.34]);
      if (!parts.length) return null;
      const wsum = parts.reduce((a, p) => a + p[1], 0);
      const ds = clip(parts.reduce((a, p) => a + p[0] * p[1], 0) / wsum, -7, 7);
      return ds >= 4 ? 'Consider adding' : ds >= 2 ? 'Hold, add on dips' : ds > -2 ? 'Hold' : ds > -3.8 ? 'Consider trimming' : 'Consider selling by December';
    }

    async function fetchOne(sym) {
      const res = await fetch('https://scanner.tradingview.com/global/scan', {
        method: 'POST', headers: { 'Content-Type': 'text/plain;charset=UTF-8' },
        body: JSON.stringify({ symbols: { tickers: [sym] }, columns: COLS }),
      });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const j = await res.json();
      if (!j.data || !j.data.length) throw new Error('no data');
      return parse(j.data[0]);
    }

    async function searchSymbols(q) {
      const url = 'https://symbol-search.tradingview.com/symbol_search/v3/?text=' + encodeURIComponent(q) + '&hl=1&exchange=&lang=en&search_type=&domain=production&sort_by_country=US';
      const res = await fetch(url);
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const j = await res.json();
      const list = j.symbols || j.symbols_remaining || (Array.isArray(j) ? j : []);
      const seen = new Set();
      return list.filter((it) => it.type === 'stock' || it.type === 'dr').map((it) => ({
        sym: it.exchange + ':' + stripEm(it.symbol), tk: stripEm(it.symbol), name: stripEm(it.description), exch: it.exchange,
      })).filter((it) => (seen.has(it.sym) ? false : (seen.add(it.sym), true))).slice(0, 8);
    }

    const $ = (id) => document.getElementById(id);
    const input = $('lookup-q'), suggEl = $('lookup-sugg'), statusEl = $('lookup-status'), resultWrap = $('lookup-result'), noteEl = $('lookup-note');
    if (!input) return;
    const tbody = document.querySelector('#lookup-tbl tbody');

    let token = 0, active = -1, curMatches = [], debounce = null;

    function closeSugg() { suggEl.replaceChildren(); suggEl.hidden = true; input.setAttribute('aria-expanded', 'false'); active = -1; curMatches = []; }
    function setActive(i) { active = i; Array.from(suggEl.children).forEach((li, k) => li.classList.toggle('active', k === i)); }
    function showSugg(matches) {
      curMatches = matches; active = -1;
      suggEl.replaceChildren();
      if (!matches.length) { suggEl.hidden = true; input.setAttribute('aria-expanded', 'false'); return; }
      matches.forEach((m, i) => {
        const li = document.createElement('li'); li.setAttribute('role', 'option'); li.dataset.i = i;
        const nm = document.createElement('span'); nm.textContent = m.name;
        const tk = document.createElement('span'); tk.className = 'tk'; tk.textContent = m.tk + ' · ' + m.exch;
        li.append(nm, tk);
        li.addEventListener('mousedown', (e) => { e.preventDefault(); choose(m); });
        suggEl.appendChild(li);
      });
      suggEl.hidden = false; input.setAttribute('aria-expanded', 'true');
    }

    function cellsFor(d) {
      const own = holdSet().get(d.sym);
      const flow = sectorFlow(d);
      const december = decemberOf(d, flow);
      const td = (t, cls) => { const c = document.createElement('td'); if (cls) c.className = cls; c.textContent = t == null ? '—' : t; return c; };
      const chip = (label) => { const c = document.createElement('td'); const sp = document.createElement('span'); sp.className = 'chip ' + chipCls(label); sp.textContent = label == null ? '—' : label; c.appendChild(sp); return c; };
      const macdOk = d.macd != null && d.macds != null;
      return [
        nameTd(d.name, d.sym, null, null),
        td(own ? fmtInt(own.value_sek) : null, 'num'),
        td(d.close == null ? null : plain(d.close, d.close < 10 ? 3 : 2) + ' ' + d.cur, 'num'),
        td(signed(d.change, 2), 'num ' + tone(d.change)),
        td(signed(d.perf1m), 'num ' + tone(d.perf1m)),
        chip(d.sflow),
        td(plain(d.rsi, 0), 'num'),
        td(macdOk ? (d.macd > d.macds ? 'Bullish' : 'Bearish') : null, 'sec ' + (macdOk ? (d.macd > d.macds ? 'pos' : 'neg') : 'mut')),
        td(signed(d.vs50), 'num sec ' + tone(d.vs50)),
        td(null, 'sec'),
        td(d.cpr, 'sec ' + (d.cpr === 'Above' ? 'pos' : d.cpr === 'Below' ? 'neg' : 'mut')),
        td(d.bollinger, 'sec'),
        td(null, 'num sec'),
        chip(d.oct_signal), chip(d.o1y), chip(d.o3y), chip(d.o5y), chip(december),
        td(signed(d.revg, 0), 'num sec ' + tone(d.revg)),
        td(d.margin == null ? null : d.margin.toFixed(0) + '%', 'num sec ' + tone(d.margin)),
        td(d.pe == null ? null : d.pe.toFixed(0), 'num sec'),
        td(d.rec == null ? null : (d.rec <= 1.5 ? 'Strong buy' : d.rec <= 2.5 ? 'Buy' : d.rec <= 3.5 ? 'Hold' : d.rec <= 4.5 ? 'Underperform' : 'Sell'), 'sec'),
      ];
    }

    function renderRow(d) {
      const tr = document.createElement('tr');
      tr.append(...cellsFor(d));
      tbody.replaceChildren(tr);
      resultWrap.hidden = false;
      const parts = [];
      if (d.oct_avail < 6) parts.push('this live view is missing the Alligator, candlestick-pattern, 55-day breakout and up/down-volume readings (they need bar history, not a single snapshot), so "October" here rests on ' + d.oct_avail + ' reading' + (d.oct_avail === 1 ? '' : 's') + ' only');
      if (!sectorFlow(d)) parts.push('no sector money-flow data matched this stock’s market and sector, so its December view is less complete');
      noteEl.textContent = parts.length ? 'Note: ' + parts.join('; ') + '. Treat the outlooks here as more approximate than your actual holdings.' : '';
    }

    async function choose(m) {
      closeSugg();
      input.value = m.name;
      statusEl.textContent = 'Loading ' + m.name + ' from TradingView…';
      resultWrap.hidden = true;
      const my = ++token;
      try {
        const d = await fetchOne(m.sym);
        if (my !== token) return;
        statusEl.textContent = 'Live from TradingView (15 min delayed).';
        renderRow(d);
      } catch (e) {
        if (my !== token) return;
        statusEl.textContent = 'Could not load ' + m.name + ' from TradingView. Try again.';
      }
    }

    input.addEventListener('input', () => {
      const q = input.value.trim();
      resultWrap.hidden = true;
      if (debounce) clearTimeout(debounce);
      if (q.length < 2) { closeSugg(); statusEl.textContent = ''; return; }
      debounce = setTimeout(async () => {
        const my = ++token;
        if (/^[A-Za-z][A-Za-z0-9_]*:[A-Za-z0-9._-]+$/.test(q)) {
          closeSugg();
          statusEl.textContent = 'Loading ' + q + ' from TradingView…';
          try {
            const d = await fetchOne(q.toUpperCase());
            if (my !== token) return;
            statusEl.textContent = 'Live from TradingView (15 min delayed).';
            renderRow(d);
          } catch (e) { if (my === token) statusEl.textContent = 'Could not load ' + q + ' from TradingView.'; }
          return;
        }
        statusEl.textContent = 'Searching…';
        try {
          const matches = await searchSymbols(q);
          if (my !== token) return;
          if (!matches.length) { closeSugg(); statusEl.textContent = 'No matching stock found.'; return; }
          showSugg(matches);
          statusEl.textContent = matches.length + ' match' + (matches.length === 1 ? '' : 'es') + ' — pick one, or keep typing.';
        } catch (e) { if (my === token) { closeSugg(); statusEl.textContent = 'Could not search TradingView right now.'; } }
      }, 300);
    });
    input.addEventListener('keydown', (e) => {
      if (suggEl.hidden) return;
      if (e.key === 'ArrowDown') { e.preventDefault(); setActive(Math.min(curMatches.length - 1, active + 1)); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); setActive(Math.max(0, active - 1)); }
      else if (e.key === 'Enter') { e.preventDefault(); if (curMatches.length) choose(curMatches[active >= 0 ? active : 0]); }
      else if (e.key === 'Escape') { closeSugg(); }
    });
    document.addEventListener('click', (e) => { if (!e.target.closest('#lookup')) closeSugg(); });
  })();"""

rep(OLD_JS, NEW_JS, 1)

assert len(s) != orig_len
open(PATH, "w", encoding="utf-8").write(s)
print("patched OK, length", orig_len, "->", len(s))
