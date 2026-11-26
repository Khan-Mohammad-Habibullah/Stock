#!/usr/bin/env python3
"""Adds the "Setups before 20% rises" section to the Strategy tab, after "Strongest bullish readings by market".
Data: data/setups_study.json (Tables A and B, monthly) and data/setups.json (Table C, daily), both read by the page at run time."""
PATH = "index.html"
s = open(PATH, encoding="utf-8").read()
assert 'id="setups"' not in s, "already patched"


def rep(old, new, cnt=1):
    global s
    n = s.count(old)
    assert n == cnt, f"expected {cnt}, found {n}: {old[:90]!r}"
    s = s.replace(old, new)


CSS = """
  #setups .su-warn { border-left: 3px solid var(--color-warn); background: color-mix(in srgb, var(--color-warn) 12%, transparent); padding: 8px 12px; border-radius: 6px; color: var(--color-fg); }
  #setups h3 { margin: 18px 0 2px; font-size: var(--cds-font-size-body, 1rem); }
  #setups .su-band { font-size: var(--cds-font-size-caption); text-transform: uppercase; letter-spacing: .06em; color: var(--color-fg-muted); margin: 22px 0 0; padding-top: 10px; border-top: 1px solid var(--color-border-line); }
  #setups table td.why { white-space: normal; min-width: 18rem; max-width: 30rem; }
  #setups table td.sm { white-space: normal; min-width: 9rem; }
  #setups tr.below td { background: color-mix(in srgb, var(--color-bad) 8%, transparent); }
  #setups .chip.am { background: color-mix(in srgb, var(--color-warn) 20%, transparent); color: var(--color-warn); }
  #setups ul.su-list { margin: 4px 0 0; padding-left: 1.2em; }
"""
rep("  .scr-tabs { display: flex;", CSS + "  .scr-tabs { display: flex;")

HTML = """  <section class="hs-card" id="setups">
    <h2>Setups before 20% rises</h2>
    <p class="hs-note">Which chart setups came before a rise of 20% or more within about two months, how often each one really did, and which stocks show the same setup after the latest daily close. History and today's list are kept apart below. A past success rate does not mean a 20% rise will happen, and nothing here says what a stock will do next.</p>
    <p class="hs-note" id="su-status" aria-live="polite">Loading…</p>
    <div class="scr-tabs" id="su-tabs" role="group" aria-label="Market"></div>
    <div class="ctl">
      <input id="su-q" type="search" placeholder="Search by name or ticker" aria-label="Search setups by name or ticker">
      <select id="su-setup" aria-label="Setup"><option value="">All setups</option></select>
      <span class="count" id="su-shown"></span>
    </div>
    <details class="scr-how" id="su-rules">
      <summary>The setups and their exact rules</summary>
      <div id="su-rules-body"></div>
    </details>

    <p class="su-band">History &middot; tested on 2021&ndash;2026 &middot; rerun on the first weekend of each month</p>
    <h3>Table A &ndash; Setup rules and how they performed</h3>
    <p class="hs-note" id="su-a-note"></p>
    <div class="tbl-wrap"><table class="hold scr" id="su-a"><thead></thead><tbody></tbody></table></div>
    <h3>Table B &ndash; Historical examples, wins and misses</h3>
    <p class="hs-note" id="su-b-note"></p>
    <div class="tbl-wrap"><table class="hold scr" id="su-b"><thead></thead><tbody></tbody></table></div>

    <p class="su-band" id="su-today">Today &middot; current candidates &middot; the list is rebuilt once a trading day, Tuesday to Saturday at 06:00 Stockholm time</p>
    <h3>Table C &ndash; Current candidates as of the latest close</h3>
    <p class="hs-note" id="su-c-note"></p>
    <div class="ctl">
      <select id="su-near" aria-label="Which matches to show">
        <option value="">All conditions met</option>
        <option value="1">Also one condition short</option>
      </select>
      <span class="count" id="su-c-shown"></span>
    </div>
    <div class="tbl-wrap"><table class="hold scr" id="su-c"><thead></thead><tbody></tbody></table></div>
    <h3 id="su-rm-h">Removed in the last 5 rebuilds</h3>
    <p class="hs-note" id="su-rm-note"></p>
    <div class="tbl-wrap"><table class="hold scr" id="su-rm"><thead></thead><tbody></tbody></table></div>

    <h3>Data, period and limits</h3>
    <div id="su-method"></div>
  </section>

"""
rep('  <section class="hs-card" id="lookup">', HTML + '  <section class="hs-card" id="lookup">')

JS = r"""
  // ---------- Strategy tab: setups before 20% rises (history from data/setups_study.json, today's list from data/setups.json) ----------
  (function () {
    const MARKETS = ['USA', 'Sweden', 'Denmark', 'Germany', 'Finland', 'Norway', 'Canada'];
    const $ = (id) => document.getElementById(id);
    const SU = { mkt: 'All', q: '', setup: '', near: '', study: null, cur: null, live: new Map(), liveAt: null, err: null,
      A: { k: 'ord', dir: 1, open: null }, B: { k: 'date', dir: -1, open: null }, C: { k: 'rank', dir: 1, open: null }, R: { k: 'date', dir: -1, open: null } };
    const LEVEL_TXT = {
      base: 'Breakout level: the highest close of the 40 sessions before the breakout. Support: the lowest close of those 40 sessions. Resistance: the 52-week high when it is above the price. Invalidation: 3% under the breakout level.',
      squeeze: 'Breakout level: the highest close of the 20 sessions before the breakout. Support: the 20-day average. Resistance: the 52-week (else 60-day) high when it is above the price. Invalidation: 3% under the breakout level.',
      high52: 'Breakout level: the previous 52-week closing high, which is also the support. There is no resistance overhead because the price is at a new 52-week high. Invalidation: 3% under the breakout level.',
      pull: 'Support: the 50-day average. Resistance: the 60-day high when it is above the price. Invalidation: the lowest low of the last 10 sessions.',
      oversold: 'Support: the lowest low of the last 10 sessions. Resistance: the 50-day average (else the 60-day high) when it is above the price. Invalidation: the lowest low of the last 10 sessions.',
    };
    const fmtPct = (v, d = 1) => (v == null ? null : (v * 100).toFixed(d) + '%');
    const sgn = (v, d = 1) => (v == null ? '—' : (v > 0 ? '+' : '') + v.toFixed(d) + '%');
    const pxTxt = (v, cur) => (v == null ? '—' : plain(v, v < 10 ? 3 : 2) + (cur ? ' ' + cur : ''));
    const dTxt = (iso) => (iso ? new Date(iso + 'T12:00:00').toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : '—');
    const td = (t, cls) => { const c = document.createElement('td'); if (cls) c.className = cls; c.textContent = t; return c; };
    const chipTd = (label, cls, title) => { const c = document.createElement('td'); const sp = document.createElement('span'); sp.className = 'chip ' + cls; sp.textContent = label; if (title) sp.title = title; c.appendChild(sp); return c; };
    const nameTd = (sym, name) => {
      const c = document.createElement('td'); c.className = 'nm';
      const b = document.createElement('button'); b.type = 'button'; b.className = 'chart-link'; b.textContent = name;
      b.addEventListener('click', (e) => { e.stopPropagation(); openChart(sym, name); });
      const tk = document.createElement('span'); tk.className = 'tk'; tk.textContent = sym.split(':')[1];
      c.append(b, document.createTextNode(' '), tk); return c;
    };
    const setupName = (k) => (SU.study && SU.study.setups[k] ? SU.study.setups[k].name : k);
    const stat = (k, mk) => (SU.study ? SU.study.stats.find((x) => x.setup === k && x.market === mk) : null);
    const live = (k) => (SU.cur && SU.cur.live ? SU.cur.live[k] : null);
    const liveTxt = (k) => { const l = live(k); if (!l) return '—'; return l.rate != null ? fmtPct(l.rate) + ' of ' + l.resolved : 'too few cases (' + l.resolved + ' resolved, ' + l.open + ' open)'; };
    const rateTxt = (st) => (!st ? '—' : st.rate == null ? 'too few cases' : fmtPct(st.rate));
    const cmp = (x, y) => { if (x == null && y == null) return 0; if (x == null) return 1; if (y == null) return -1; return typeof x === 'number' ? x - y : String(x).localeCompare(String(y)); };
    const tdSince = (iso) => { // weekdays after that date up to today, inclusive
      if (!iso) return null; const d0 = new Date(iso + 'T12:00:00'), now = new Date(); let n = 0;
      for (const d = new Date(d0.getTime() + 864e5); d <= now; d.setDate(d.getDate() + 1)) { const w = d.getDay(); if (w !== 0 && w !== 6) n += 1; }
      return n;
    };

    // generic sortable table: cols = [{k, label, cls, val(r), cell(r)}]
    function table(id, st, cols, getRows, detail, keyOf, empty) {
      const el = $(id), head = el.querySelector('thead'), body = el.querySelector('tbody');
      const tr = document.createElement('tr');
      cols.forEach((c) => {
        const th = document.createElement('th'); if (c.cls) th.className = c.cls; th.dataset.k = c.k;
        const b = document.createElement('button'); b.type = 'button'; b.textContent = c.label; if (c.tip) th.title = c.tip;
        b.addEventListener('click', () => { if (st.k === c.k) st.dir = -st.dir; else { st.k = c.k; st.dir = c.dir || 1; } draw(); });
        th.appendChild(b); tr.appendChild(th);
      });
      head.replaceChildren(tr);
      function draw() {
        head.querySelectorAll('th').forEach((th) => th.setAttribute('aria-sort', th.dataset.k === st.k ? (st.dir > 0 ? 'ascending' : 'descending') : 'none'));
        const col = cols.find((c) => c.k === st.k) || cols[0];
        const rows = getRows().slice().sort((a, b) => cmp(col.val(a), col.val(b)) * st.dir);
        const out = [];
        rows.forEach((r) => {
          const row = document.createElement('tr'); const key = keyOf(r); row.dataset.key = key;
          if (st.open === key) row.classList.add('sel');
          cols.forEach((c) => { const x = c.cell(r); row.appendChild(typeof x === 'string' ? td(x, c.cls) : x); });
          if (r._cls) row.classList.add(r._cls);
          row.addEventListener('click', () => { st.open = st.open === key ? null : key; draw(); });
          out.push(row);
          if (st.open === key && detail) {
            const dr = document.createElement('tr'); dr.className = 'scr-detail';
            const c = document.createElement('td'); c.colSpan = cols.length;
            const inner = document.createElement('div'); inner.style.cssText = 'position:sticky;left:0;box-sizing:border-box;width:' + Math.max(280, el.closest('.tbl-wrap').clientWidth - 18) + 'px';
            inner.appendChild(detail(r)); c.appendChild(inner); dr.appendChild(c); out.push(dr);
          }
        });
        if (!rows.length) { const r0 = document.createElement('tr'); const c = document.createElement('td'); c.colSpan = cols.length; c.className = 'mut'; c.textContent = empty(); r0.appendChild(c); out.push(r0); }
        body.replaceChildren(...out);
        return rows.length;
      }
      return draw;
    }
    const checklist = (items) => {
      const ul = document.createElement('ul'); ul.className = 'rules';
      items.forEach((it) => {
        const li = document.createElement('li'); const mk = document.createElement('span'); mk.className = 'mk ' + (it.ok === true ? 'pos' : it.ok === false ? 'neg' : 'mut'); mk.textContent = it.ok === true ? '✓' : it.ok === false ? '✗' : '•';
        const t = document.createElement('span'); t.textContent = it.t; const lv = document.createElement('span'); lv.className = 'lv'; lv.textContent = it.v || '';
        li.append(mk, t, lv); ul.appendChild(li);
      });
      return ul;
    };
    const para = (txt) => { const p = document.createElement('p'); p.className = 'hs-note'; p.style.marginBottom = '6px'; p.textContent = txt; return p; };
    const inMkt = (m) => SU.mkt === 'All' || m === SU.mkt;
    const matchQ = (name, sym) => !SU.q || (name + ' ' + sym).toLowerCase().includes(SU.q);

    // ---- Table A
    const drawA = table('su-a', SU.A, [
      { k: 'ord', label: 'Setup (rule)', val: (r) => r.ord, cell: (r) => { const c = document.createElement('td'); c.className = 'why'; const b = document.createElement('strong'); b.textContent = setupName(r.k); const p = document.createElement('div'); p.className = 'hs-note'; p.textContent = SU.study.setups[r.k].short; c.append(b, p); return c; } },
      { k: 'n', label: 'Times it appeared', cls: 'num', dir: -1, val: (r) => r.st && r.st.n, cell: (r) => String(r.st ? r.st.n : '—'), tip: 'Setup days over the five years, counting at most one per stock every 42 trading days. Days whose 42-day outcome is not yet known are left out.' },
      { k: 'rate', label: 'Success rate', cls: 'num', dir: -1, val: (r) => r.st && r.st.rate, cell: (r) => rateTxt(r.st), tip: 'Share of those days after which the highest close of the next 42 trading days was at least 20% above the setup-day close. Shown only from 30 cases.' },
      { k: 'base', label: 'Base rate (any stock, random day)', cls: 'num sec', dir: -1, val: (r) => r.st && r.st.base, cell: (r) => (r.st ? fmtPct(r.st.base) : '—'), tip: 'The same test on every stock and every day in the same list.' },
      { k: 'matched', label: 'Base rate at the same volatility', cls: 'num sec', dir: -1, val: (r) => r.st && r.st.matched, cell: (r) => (r.st && r.st.matched != null ? fmtPct(r.st.matched) : '—'), tip: 'Volatile stocks rise 20% more often whatever the setup. This is the base rate among days with the same 20-day volatility as this setup’s days.' },
      { k: 'test', label: 'Since Jul 2024 (not used to pick the rules)', cls: 'num sec', dir: -1, val: (r) => r.st && r.st.rate_test, cell: (r) => (!r.st ? '—' : r.st.rate_test == null ? 'too few cases' : fmtPct(r.st.rate_test) + ' (' + r.st.n_test + ')'), tip: 'Success rate on setup days from 1 July 2024, which were not used to choose the thresholds.' },
      { k: 'gain', label: 'Median gain (cases that rose)', cls: 'num sec', dir: -1, val: (r) => r.st && r.st.gain, cell: (r) => (r.st && r.st.gain != null ? '+' + fmtPct(r.st.gain) : '—'), tip: 'Highest close within 42 days against the setup-day close, for the cases that reached +20%.' },
      { k: 'days', label: 'Median days to +20%', cls: 'num sec', val: (r) => r.st && r.st.days, cell: (r) => (r.st && r.st.days != null ? String(Math.round(r.st.days)) : '—'), tip: 'Trading days until the close first reached +20%, for the cases that did.' },
      { k: 'drop', label: 'Median largest drop before the peak', cls: 'num sec', dir: -1, val: (r) => r.st && r.st.drop, cell: (r) => (r.st && r.st.drop != null ? sgn(r.st.drop * 100) : '—'), tip: 'Lowest close between the setup day and the peak, against the setup-day close, for the cases that reached +20%.' },
      { k: 'live', label: 'Live record of this screen', cls: 'sm', dir: -1, val: (r) => { const l = live(r.k); return l && l.rate; }, cell: (r) => liveTxt(r.k), tip: 'Names this page listed as current candidates, checked 42 trading days after they first appeared.' },
    ], () => (SU.study ? SU.study.order.map((k, i) => ({ k, ord: i, st: stat(k, SU.mkt) })).filter((r) => !SU.setup || r.k === SU.setup) : []),
    (r) => { const w = document.createElement('div'); w.append(para(SU.study.setups[r.k].short + '. Every condition must be true on the same day:'), checklist(SU.study.setups[r.k].conditions.map((t) => ({ t, ok: null }))), para(LEVEL_TXT[r.k])); return w; },
    (r) => r.k, () => 'Loading…');

    // ---- Table B
    const exRows = () => (SU.study ? SU.study.examples.filter((e) => inMkt(e.market) && (!SU.setup || e.setup === SU.setup) && matchQ(e.name, e.sym)).map((e) => Object.assign(e, { _k: e.setup + e.sym + e.date })) : []);
    const drawB = table('su-b', SU.B, [
      { k: 'name', label: 'Stock', val: (e) => e.name, cell: (e) => nameTd(e.sym, e.name) },
      { k: 'market', label: 'Market', cls: 'sec', val: (e) => e.market, cell: (e) => e.market },
      { k: 'setup', label: 'Setup', cls: 'sm', val: (e) => setupName(e.setup), cell: (e) => setupName(e.setup) },
      { k: 'date', label: 'Setup date', dir: -1, val: (e) => e.date, cell: (e) => dTxt(e.date) },
      { k: 'price', label: 'Price at setup', cls: 'num sec', val: (e) => e.price, cell: (e) => pxTxt(e.price, e.cur) },
      { k: 'peak', label: 'Peak price (within 42 days)', cls: 'num sec', val: (e) => e.peak, cell: (e) => pxTxt(e.peak, e.cur) },
      { k: 'gain', label: 'Gain to peak', cls: 'num', dir: -1, val: (e) => e.gain, cell: (e) => sgn(e.gain) },
      { k: 'days', label: 'Days to +20%', cls: 'num sec', val: (e) => e.days, cell: (e) => (e.days == null ? '—' : String(e.days)) },
      { k: 'why', label: 'Before the move', cls: 'why sec', val: (e) => e.why, cell: (e) => { const c = td(e.why.length > 120 ? e.why.slice(0, 117) + '…' : e.why, 'why sec'); c.title = e.why; return c; } },
      { k: 'earn', label: 'Earnings in the 42 days', cls: 'sec', val: (e) => (e.earnings ? 1 : 0), cell: (e) => (e.earnings == null ? '—' : e.earnings ? 'Likely yes' : 'No sign'), tip: 'Inferred: a day with a price gap of 4% or more on at least 2.5 times the usual volume. Past earnings dates are not in the data.' },
      { k: 'out', label: 'Outcome', val: (e) => e.outcome, cell: (e) => chipTd(e.outcome === 'hit' ? 'Hit' : 'Missed', e.outcome === 'hit' ? 'b2' : 'e1') },
    ], exRows, (e) => {
      const w = document.createElement('div');
      w.append(para(setupName(e.setup) + ' · ' + e.market + ' · setup day ' + dTxt(e.date) + ' at ' + pxTxt(e.price, e.cur) + (e.breakout ? ' · level crossed ' + pxTxt(e.breakout, e.cur) : '') + ' · highest close in the next 42 trading days ' + pxTxt(e.peak, e.cur) + ' (' + sgn(e.gain) + '), largest dip on the way ' + sgn(e.drop) + '.'));
      const ul = document.createElement('ul'); ul.className = 'su-list'; e.why.split('; ').forEach((t) => { const li = document.createElement('li'); li.textContent = t; ul.appendChild(li); });
      w.appendChild(ul); return w;
    }, (e) => e._k, () => (SU.study ? 'No examples match.' : 'Loading…'));

    // ---- Table C
    const px = (c) => { const l = SU.live.get(c.sym); return l && l.close != null ? l.close : c.close; };
    const distTxt = (lvl, c) => (lvl == null ? '—' : pxTxt(lvl, c.cur) + ' (' + sgn((px(c) / lvl - 1) * 100) + ')');
    const candRows = () => {
      if (!SU.cur) return [];
      return SU.cur.candidates.filter((c) => (c.complete || SU.near) && inMkt(c.market) && (!SU.setup || c.setup === SU.setup) && matchQ(c.name, c.sym))
        .map((c) => { c._k = c.sym + c.setup + (c.complete ? 'c' : 'n'); c._below = c.invalid != null && px(c) < c.invalid; c._cls = c._below ? 'below' : ''; return c; });
    };
    const drawC = table('su-c', SU.C, [
      { k: 'rank', label: 'Stock', val: (c) => c.name, cell: (c) => nameTd(c.sym, c.name) },
      { k: 'market', label: 'Market', cls: 'sec', val: (c) => c.market, cell: (c) => c.market },
      { k: 'setup', label: 'Matching setup', cls: 'sm', val: (c) => setupName(c.setup), cell: (c) => setupName(c.setup) },
      { k: 'met', label: 'Conditions met', cls: 'num', dir: -1, val: (c) => c.met / c.total, cell: (c) => c.met + ' of ' + c.total },
      { k: 'why', label: 'Why it matches', cls: 'why sec', val: (c) => c.why, cell: (c) => { const t = c.complete ? c.why : 'Missing: ' + c.missing.join('; '); const x = td(t.length > 130 ? t.slice(0, 127) + '…' : t, 'why sec'); x.title = t; return x; } },
      { k: 'rate', label: 'This setup’s historical success rate', cls: 'sm', dir: -1, val: (c) => c.rate, cell: (c) => (c.rate == null ? 'too few cases' : fmtPct(c.rate) + ' of ' + c.n_hist + ' (same-volatility base ' + fmtPct(c.base) + ')'), tip: 'From the latest monthly study, all markets together.' },
      { k: 'live', label: 'Live record', cls: 'sm sec', val: (c) => { const l = live(c.setup); return l && l.rate; }, cell: (c) => liveTxt(c.setup) },
      { k: 'prev', label: 'This stock’s own last matching setup', cls: 'sm sec', val: (c) => (c.last_prev ? c.last_prev.date : null), cell: (c) => (!c.last_prev ? 'none in the data' : dTxt(c.last_prev.date) + ' at ' + pxTxt(c.last_prev.price) + ' · ' + (c.last_prev.outcome === 'hit' ? 'reached +20%' : c.last_prev.outcome === 'missed' ? 'missed' : 'outcome pending')) },
      { k: 'px', label: 'Price now', cls: 'num sec', val: (c) => px(c), cell: (c) => pxTxt(px(c), c.cur) },
      { k: 'brk', label: 'Breakout level (distance)', cls: 'sm sec', val: (c) => c.breakout, cell: (c) => distTxt(c.breakout, c) },
      { k: 'sup', label: 'Support', cls: 'num sec', val: (c) => c.support, cell: (c) => pxTxt(c.support) },
      { k: 'res', label: 'Resistance', cls: 'num sec', val: (c) => c.resistance, cell: (c) => (c.resistance == null ? 'none overhead' : pxTxt(c.resistance)) },
      { k: 'inv', label: 'Invalidation level (distance)', cls: 'sm', val: (c) => c.invalid, cell: (c) => distTxt(c.invalid, c), tip: 'The price at which the setup no longer holds. If the price trades below it the row is flagged at once and the name is removed at the next daily rebuild.' },
      { k: 'earn', label: 'Next earnings', cls: 'sec', val: (c) => c.earnings_next, cell: (c) => (c.earnings_next ? dTxt(c.earnings_next) : '—') },
      { k: 'st', label: 'Status', val: (c) => (c._below ? 0 : c.new ? 1 : 2), cell: (c) => (c._below ? chipTd('Below invalidation', 'e2', 'The price is under the invalidation level; the name stays until the next daily rebuild.') : c.new ? chipTd('New', 'b2', 'Added in the latest rebuild') : !c.complete ? chipTd('One condition short', 'am') : chipTd('Listed since ' + dTxt(c.first_seen), 'n')) },
    ], candRows, (c) => {
      const w = document.createElement('div');
      w.append(para(setupName(c.setup) + ' · ' + c.market + ' · ' + c.size + ' cap (rank ' + c.rank + ') · close ' + pxTxt(c.close, c.cur) + ' on ' + dTxt(c.bar_date) + ' · first listed ' + dTxt(c.first_seen) + ' at ' + pxTxt(c.entry_close, c.cur)));
      w.appendChild(checklist(c.conds.map((x) => ({ t: x.t, ok: x.ok, v: x.v }))));
      w.appendChild(para(LEVEL_TXT[c.setup]));
      if (c.earnings_next) w.appendChild(para('Next earnings report: ' + dTxt(c.earnings_next) + ' (from TradingView).'));
      return w;
    }, (c) => c._k, () => (SU.cur ? 'No candidates match.' : 'Loading…'));

    // ---- removed names
    const drawR = table('su-rm', SU.R, [
      { k: 'name', label: 'Stock', val: (r) => r.name, cell: (r) => nameTd(r.sym, r.name) },
      { k: 'market', label: 'Market', cls: 'sec', val: (r) => r.market, cell: (r) => r.market },
      { k: 'setup', label: 'Setup', cls: 'sm', val: (r) => setupName(r.setup), cell: (r) => setupName(r.setup) },
      { k: 'date', label: 'Removed on', dir: -1, val: (r) => r.removed_on, cell: (r) => dTxt(r.removed_on) },
      { k: 'why', label: 'Reason', cls: 'sm', val: (r) => r.reason, cell: (r) => r.reason },
      { k: 'entry', label: 'First listed at', cls: 'num sec', val: (r) => r.entry_close, cell: (r) => dTxt(r.first_seen) + ' · ' + pxTxt(r.entry_close, r.cur) },
      { k: 'last', label: 'Last close', cls: 'num sec', val: (r) => r.last_close, cell: (r) => pxTxt(r.last_close, r.cur) },
    ], () => (SU.cur ? SU.cur.removed.filter((r) => inMkt(r.market) && (!SU.setup || r.setup === SU.setup) && matchQ(r.name, r.sym)) : []), null,
    (r) => r.sym + r.setup + r.removed_on, () => (SU.cur ? 'Nothing was removed in the last 5 rebuilds.' : 'Loading…'));

    // ---- notes, status and method text
    function paintNotes() {
      const st = SU.study, cu = SU.cur;
      if (st) {
        const pd = st.period, st0 = st.stats.find((x) => x.market === 'All');
        $('su-a-note').textContent = 'Every rule was run on every stock and every day from ' + dTxt(pd.from_) + ' to ' + dTxt(pd.to) + ' (' + st.stock_days.toLocaleString('en-GB') + ' stock-days, ' + st.stocks.with_data + ' stocks), not only on the stocks that rose. A rise = the highest close in the next 42 trading days at least 20% above the setup-day close. A success rate is shown only from 30 cases; otherwise "too few cases". Last study run ' + dTxt(st.built.slice(0, 10)) + '.';
        $('su-b-note').textContent = 'For each setup and market, the six most recent cases that rose and the six most recent that did not (not picked for how good they look). Click a row for what the chart looked like going in, using only data up to the setup day.';
        $('su-rules-body').replaceChildren(...st.order.flatMap((k) => { const h = document.createElement('p'); h.className = 'hs-note'; h.style.cssText = 'margin-top:10px;color:var(--color-fg)'; h.textContent = setupName(k) + ': ' + st.setups[k].short + '. All of these on the same day:'; return [h, checklist(st.setups[k].conditions.map((t) => ({ t, ok: null }))), para(LEVEL_TXT[k])]; }));
        const out = document.createElement('div');
        const ul = document.createElement('ul'); ul.className = 'su-list';
        const li = (t) => { const x = document.createElement('li'); x.textContent = t; ul.appendChild(x); };
        li('Stock list: the same as the screen above, taken from TradingView’s screener: common stocks listed in each of the seven markets (USA, Sweden, Denmark, Germany, Finland, Norway, Canada) and based in that country, one share class per company (the most traded), the 70 largest by market value (ranks 1–30 large caps, 31–70 mid caps). The list is today’s, applied to all five years.');
        li('Daily prices and volume: Yahoo Finance daily bars, adjusted for splits and dividends. TradingView offers no public download of daily history, so it is used for the stock list, earnings dates and the live prices in Table C, while history comes from Yahoo, as in the rest of this board’s rebuild.');
        li('Period: setup days from ' + dTxt(pd.from_) + ' to ' + dTxt(pd.to) + ' (a setup day needs 42 following trading days to be judged unless it already rose 20%; later days show as pending). About a year of earlier prices only warms up the averages.');
        li('Delisted, merged and bankrupt companies are missing from the data because the list is today’s largest companies. That makes past success rates look better than they really were.');
        li('How the rules were made: the kinds of patterns were chosen after looking at the whole period, and the thresholds were picked by trying a small set of values on setup days before ' + dTxt(pd.split) + '. Days since then were not used to choose anything and are shown as their own column in Table A, but because the pattern types were chosen with the whole period in view, that check is not fully independent.');
        li('Base rate: how often any stock in the same list rose 20% within 42 trading days from a random day (' + fmtPct(st.base.All) + ' over the period). Volatile stocks rise 20% far more often than calm ones, and most setups pick volatile stocks, so Table A also shows the base rate among days with the same volatility. A setup earns its place only if it beats that figure.');
        li('Median gain, days and drop are taken over the cases that reached +20%. "Largest drop before the peak" is the lowest close on the way to the peak against the setup-day close.');
        li('Earnings: past earnings dates are not in the data, so history marks a likely earnings reaction (a gap of 4% or more on 2.5 times the usual volume). Table C shows the next reported date from TradingView.');
        li('Counting: one case per stock and setup every 42 trading days, so one move is not counted several times. Different setups can fire on the same stock and day.');
        out.appendChild(ul);
        const lo = st.left_out || [];
        if (lo.length) {
          const d = document.createElement('details'); const sm = document.createElement('summary'); sm.textContent = 'Left out or shortened because of missing data (' + lo.length + ')'; d.appendChild(sm);
          const u2 = document.createElement('ul'); u2.className = 'su-list'; lo.forEach((x) => { const l = document.createElement('li'); l.textContent = x.name + ' (' + x.sym + ', ' + x.market + '): ' + x.reason; u2.appendChild(l); }); d.appendChild(u2); out.appendChild(d);
        }
        const nz = document.createElement('p'); nz.className = 'hs-note'; nz.style.marginTop = '8px';
        nz.textContent = 'This describes past chart patterns and is not advice. A past success rate does not mean a 20% rise will happen: most of the days that showed a setup were not followed by one.';
        out.appendChild(nz);
        $('su-method').replaceChildren(out);
      }
      if (cu) {
        const cl = cu.carried && cu.carried.length ? ' Kept from the previous rebuild because those markets had no new daily candle (holiday) or too little data: ' + cu.carried.join(', ') + '.' : '';
        $('su-c-note').textContent = 'Stocks whose latest completed daily candle shows the setup, measured against the exact rules above. Names are added and removed only at the daily rebuild, never during the trading day, because an unfinished candle can show a setup that is gone by the close. Between rebuilds only the price, the distance to the breakout and invalidation levels and the flag are refreshed (every 5 minutes, 15 minutes delayed). Names added in the latest rebuild are marked New.' + cl + (cu.first_run ? ' This is the first rebuild, so nothing is marked New yet and the live record starts empty.' : '');
        $('su-rm-note').textContent = 'Names that left Table C, for 5 rebuilds, with the reason: reached +20%, setup failed (a close below its invalidation level), or conditions no longer met.';
        const age = tdSince(cu.built_local.slice(0, 10));
        const el = $('su-status'); el.className = 'hs-note';
        let txt = 'Candidates last rebuilt ' + dTxt(cu.built_local.slice(0, 10)) + ' at ' + cu.built_local.slice(11, 16) + ' Stockholm time (daily candles to ' + dTxt(cu.bar_date) + '). History last rerun ' + (st ? dTxt(st.built.slice(0, 10)) : 'n/a') + '.';
        if (age != null && age > 2) { el.className = 'hs-note su-warn'; txt = '⚠ The candidate list is ' + age + ' trading days old (last rebuild ' + dTxt(cu.built_local.slice(0, 10)) + '), so the latest rebuild may have failed. Prices still refresh but the names may be out of date. ' + txt; }
        if (cu.errors && cu.errors.length) txt += ' Notes: ' + cu.errors.join('; ') + '.';
        el.textContent = txt;
      } else if (SU.err) { const el = $('su-status'); el.className = 'hs-note su-warn'; el.textContent = '⚠ ' + SU.err; }
    }
    function drawAll() {
      document.querySelectorAll('#su-tabs button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.m === SU.mkt)));
      drawA(); const nb = drawB(); const nc = drawC(); drawR();
      $('su-shown').textContent = SU.study ? nb + ' examples shown' : '';
      $('su-c-shown').textContent = SU.cur ? nc + ' candidates shown' : '';
    }
    ['All'].concat(MARKETS).forEach((m) => {
      const b = document.createElement('button'); b.type = 'button'; b.dataset.m = m; b.textContent = m === 'All' ? 'All markets' : m;
      b.addEventListener('click', () => { SU.mkt = m; SU.A.open = SU.B.open = SU.C.open = null; drawAll(); });
      $('su-tabs').appendChild(b);
    });
    $('su-q').addEventListener('input', (e) => { SU.q = e.target.value.trim().toLowerCase(); drawAll(); });
    $('su-setup').addEventListener('change', (e) => { SU.setup = e.target.value; drawAll(); });
    $('su-near').addEventListener('change', (e) => { SU.near = e.target.value; drawAll(); });

    async function getJson(url) { const r = await fetch(url + '?t=' + Math.floor(Date.now() / 60000), { cache: 'no-cache' }); if (!r.ok) throw new Error(url + ' HTTP ' + r.status); return r.json(); }
    async function load() {
      const errs = [];
      try { SU.study = await getJson('data/setups_study.json'); const sel = $('su-setup'); if (sel.options.length === 1) SU.study.order.forEach((k) => { const o = document.createElement('option'); o.value = k; o.textContent = SU.study.setups[k].name; sel.appendChild(o); }); } catch (e) { errs.push('the historical study'); }
      try { SU.cur = await getJson('data/setups.json'); } catch (e) { errs.push('the current candidates'); }
      if (errs.length) SU.err = 'Could not load ' + errs.join(' or ') + ' yet. They are written by the scheduled rebuilds; try again after the next one.';
      paintNotes(); drawAll(); refreshLive();
    }
    async function refreshLive() {
      if (!SU.cur || document.hidden || (typeof LIVE !== 'undefined' && LIVE.paused)) return;
      const syms = Array.from(new Set(SU.cur.candidates.map((c) => c.sym)));
      if (!syms.length) return;
      try {
        const res = await fetch('https://scanner.tradingview.com/global/scan', { method: 'POST', headers: { 'Content-Type': 'text/plain;charset=UTF-8' }, body: JSON.stringify({ symbols: { tickers: syms }, columns: ['close', 'change'] }) });
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const j = await res.json(); const m = new Map();
        (j.data || []).forEach((x) => m.set(x.s, { close: typeof x.d[0] === 'number' ? x.d[0] : null, change: x.d[1] }));
        if (m.size) { SU.live = m; SU.liveAt = new Date(); }
      } catch (e) { /* keep the last prices */ }
      drawAll();
      const b = SU.liveAt ? 'Prices live from TradingView (15 min delayed), updated ' + SU.liveAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + '.' : '';
      const c = $('su-c-shown'); if (SU.cur) c.textContent = c.textContent.replace(/ · Prices.*$/, '') + (b ? ' · ' + b : '');
    }
    window.__su = SU;
    load();
    setInterval(refreshLive, 300000);
    setInterval(() => { if (!document.hidden) { load(); } }, 3600000);
  })();

"""
rep("  // ---------- Strategy tab: look up any stock, rendered the same way as", JS + "  // ---------- Strategy tab: look up any stock, rendered the same way as")
open(PATH, "w", encoding="utf-8").write(s)
print("ok")
