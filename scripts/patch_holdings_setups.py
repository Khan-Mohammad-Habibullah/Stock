#!/usr/bin/env python3
"""index.html: insert the two holdings tables ("Rise setups in your holdings (+20% within 42 trading days)" and "Fall patterns in your holdings (−10% within a month, −20% within three)") on the
My holdings tab, just before "Companies you own twice", as ONE self-contained block (its own HTML, CSS and JavaScript, IDs and classes prefixed hsx-).
Nothing else in the page is edited. Running it again replaces the block.
"""
import re

PAGE = "index.html"
BEGIN, END = "<!-- BEGIN holdings setup tables (scripts/patch_holdings_setups.py) -->", "<!-- END holdings setup tables -->"
ANCHOR = '    <h3 class="h3" id="twice">Companies you own twice</h3>\n'

BLOCK = BEGIN + r'''
  <style>
    .hsx-block { display: grid; gap: var(--cds-gap-md); min-width: 0; padding-top: 16px; border-top: 1px solid var(--color-border-line); }
    #hsx-fall { margin-bottom: 8px; }
    #hsx-up h3, #hsx-fall h3 { margin: 14px 0 2px; font-size: var(--cds-font-size-body, 1rem); }
    #hsx-up table td.sm, #hsx-fall table td.sm { white-space: normal; min-width: 8.5rem; }
    #hsx-up table td.hsx-mo, #hsx-fall table td.hsx-mo { white-space: nowrap; min-width: 6.5rem; }
    #hsx-up tr.hsx-foot td, #hsx-fall tr.hsx-foot td { background: color-mix(in srgb, var(--color-fg) 6%, transparent); font-weight: 600; }
    #hsx-up tr.hsx-below td, #hsx-fall tr.hsx-below td { background: color-mix(in srgb, var(--color-bad) 8%, transparent); }
    #hsx-up td.hsx-am, #hsx-fall td.hsx-am { background: color-mix(in srgb, var(--color-warn) 24%, transparent); font-weight: 600; }
    .hsx-warn { border-left: 3px solid var(--color-warn); background: color-mix(in srgb, var(--color-warn) 12%, transparent); padding: 8px 12px; border-radius: 6px; color: var(--color-fg); }
    .hsx-chip-am { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: var(--cds-font-size-caption); white-space: nowrap; background: color-mix(in srgb, var(--color-warn) 20%, transparent); color: var(--color-warn); }
    .hsx-sub { display: block; color: var(--color-fg-muted); font-size: var(--cds-font-size-caption); white-space: nowrap; }
    .hsx-ml { display: block; margin: 2px 0; }
    table.hsx-mini { width: auto; margin: 4px 0 10px; border-collapse: collapse; }
    table.hsx-mini th, table.hsx-mini td { padding: 3px 16px 3px 0; text-align: left; font-weight: normal; white-space: nowrap; font-variant-numeric: tabular-nums; }
    table.hsx-mini th { color: var(--color-fg-muted); }
    ul.hsx-list { margin: 4px 0 0; padding-left: 1.2em; }
    ul.hsx-chk { list-style: none; margin: 4px 0; padding: 0; display: grid; gap: 3px 16px; grid-template-columns: repeat(auto-fit, minmax(min(100%, 19rem), 1fr)); }
    ul.hsx-chk li { display: flex; gap: 8px; align-items: baseline; }
    ul.hsx-chk .mk { width: 1.1em; flex: none; text-align: center; font-weight: 700; }
    ul.hsx-chk .lv { color: var(--color-fg-muted); margin-left: auto; padding-left: 8px; }
    #hsx-up details summary, #hsx-fall details summary { cursor: pointer; color: var(--color-fg-muted); font-size: var(--cds-font-size-caption); }
  </style>
  <div class="hsx-block" id="hsx-up">
    <h3 class="h3">Rise setups in your holdings (+20% within 42 trading days)</h3>
    <p class="hs-note" id="hsx-up-note">Loading&hellip;</p>
    <p class="hs-note hsx-warn" id="hsx-up-warn" hidden></p>
    <div class="scr-tabs" id="hsx-up-tabs" role="group" aria-label="Market for the holdings setups table"></div>
    <div class="ctl"><select id="hsx-up-cnt" aria-label="How many of the setup's conditions are met"></select><span class="count" id="hsx-up-shown"></span></div>
    <div class="tbl-wrap"><table class="hold scr" id="hsx-up-t"><thead></thead><tbody></tbody></table></div>
    <p class="hs-note" id="hsx-up-empty" hidden></p>
    <p class="hs-note" id="hsx-up-live"></p>
    <p class="hs-note" id="hsx-up-how"></p>
    <p class="hs-note" id="hsx-up-check"></p>
    <div id="hsx-up-cov"></div>
    <p class="hs-note" id="hsx-up-stamp"></p>
  </div>
  <div class="hsx-block" id="hsx-fall">
    <h3 class="h3">Fall patterns in your holdings (&minus;10% within a month, &minus;20% within three)</h3>
    <p class="hs-note" id="hsx-fall-note">Loading&hellip;</p>
    <div class="scr-tabs" id="hsx-fall-tabs" role="group" aria-label="Market for the holdings fall table"></div>
    <div class="ctl"><select id="hsx-fall-cnt" aria-label="How many of the rule's conditions are met"></select>
      <label class="hs-note" style="display:inline-flex;gap:6px;align-items:center;margin:0"><input type="checkbox" id="hsx-fall-failed"> Also show the rules that did not pass the test</label>
      <span class="count" id="hsx-fall-shown"></span></div>
    <div class="tbl-wrap" id="hsx-fall-wrap"><table class="hold scr" id="hsx-fall-t"><thead></thead><tbody></tbody></table></div>
    <p class="hs-note" id="hsx-fall-empty" hidden></p>
    <p class="hs-note" id="hsx-fall-live"></p>
    <p class="hs-note" id="hsx-fall-how"></p>
    <div id="hsx-fall-test"></div>
    <p class="hs-note" id="hsx-fall-stamp"></p>
  </div>
  <script>
  document.addEventListener('DOMContentLoaded', function () {
    'use strict';
    const $ = (id) => document.getElementById(id);
    const HX = { d: null, st: null, su: null, live: new Map(), liveAt: null, up: { k: 'rate', dir: -1, open: null, mkt: 'All', cnt: 'all' }, fall: { k: 'e10', dir: -1, open: null, mkt: 'All', cnt: 'all', failed: false } };
    const MKTS = ['All', 'USA', 'Sweden', 'Denmark', 'Germany', 'Finland', 'Norway', 'Canada'];
    const inM = (r, st) => st.mkt === 'All' || r.market === st.mkt;
    const NEW_WARN = 'The stock list is today’s 70 largest companies in each market. A company that fell 60% and kept falling usually dropped out of that list, so it is missing from this test. This makes the deep-fall setups (a, b, c, e) look better than they really were. Most of their cases also come from the 2022 bear market, and the washout setups (a, d) rest on a few market crashes. Expect real results to be lower than the historical success rate shown.';
    const pct = (v, d = 0) => (v == null ? '—' : (v * 100).toFixed(d) + '%');
    const sg = (v, d = 1) => (v == null ? '—' : (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v * 100).toFixed(d) + '%');
    const px = (v, cur) => (v == null ? '—' : v.toFixed(v < 10 ? 3 : 2) + (cur ? ' ' + cur : ''));
    const dT = (iso, y = true) => (iso ? new Date(iso + 'T12:00:00').toLocaleDateString('en-GB', y ? { day: 'numeric', month: 'short', year: 'numeric' } : { day: 'numeric', month: 'short' }) : '—');
    const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
    const para = (t) => el('p', 'hs-note', t);
    const tdL = (parts, cls) => { const x = el('td', cls); parts.forEach((t, i) => { if (t == null || t === '') return; x.appendChild(i ? el('span', 'hsx-sub', t) : el('span', null, t)); }); return x; };
    const chip = (t, cls, title) => { const s = el('span', cls === 'am' ? 'hsx-chip-am' : 'chip ' + cls, t); if (title) s.title = title; return s; };
    const nameTd = (r) => {
      const c = el('td', 'nm');
      if (typeof openChart === 'function') { const b = el('button', 'chart-link', r.name); b.type = 'button'; b.addEventListener('click', (e) => { e.stopPropagation(); openChart(r.sym, r.name); }); c.appendChild(b); } else c.appendChild(el('span', null, r.name));
      c.append(document.createTextNode(' '), el('span', 'tk', r.sym.split(':')[1])); return c;
    };
    const sname = (k) => (HX.su && HX.su.setups[k] ? HX.su.setups[k].name : k);
    const isNew = (k) => !!(HX.su && HX.su.setups[k] && HX.su.setups[k].group === 'new');
    const stat = (k) => (HX.su ? HX.su.stats.find((x) => x.setup === k && x.market === 'All') : null);
    const rate = (k) => { const t = stat(k); return t && t.n >= 30 ? t.hits / t.n : null; };
    const fname = (k) => (HX.st && HX.st.fall.rules[k] ? HX.st.fall.rules[k].name : k);
    const nowPx = (r) => { const l = HX.live.get(r.sym); return l != null ? l : r.last_close; };
    const weights = () => {
      const m = new Map(); try { const rows = (window.dash && dash.data('holdings').data) || []; const tot = rows.reduce((a, r) => a + (r.value_sek || 0), 0); if (tot > 0) rows.forEach((r) => m.set(r.sym, (r.value_sek || 0) / tot)); } catch (e) { /* weights are optional */ }
      return m;
    };
    const todayIso = () => { const d = new Date(); return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0'); };
    const daysLeft = (r) => { const cal = HX.d && HX.d.calendar && HX.d.calendar[r.market]; if (!cal || !r.deadline) return null; const t = todayIso(); return cal.filter((d) => d > t && d <= r.deadline).length; };
    const tdSince = (iso) => { if (!iso) return null; let n = 0; const now = new Date(); for (const d = new Date(new Date(iso + 'T12:00:00').getTime() + 864e5); d <= now; d.setDate(d.getDate() + 1)) { const w = d.getDay(); if (w && w !== 6) n += 1; } return n; };
    const cmp = (x, y) => { if (x == null && y == null) return 0; if (x == null) return 1; if (y == null) return -1; return typeof x === 'number' ? x - y : String(x).localeCompare(String(y)); };
    const checklist = (conds) => { const ul = el('ul', 'hsx-chk'); conds.forEach((c) => { const li = el('li'); li.append(el('span', 'mk', c.ok ? '✓' : '✗'), el('span', null, c.t), el('span', 'lv', c.v || '')); li.firstChild.style.color = c.ok ? 'var(--color-ok)' : 'var(--color-bad)'; ul.appendChild(li); }); return ul; };
    const monthCell = (ms, m, side) => {
      const s = ms && ms[m]; if (!s || !s.n || s.n < 30) return tdL(['too few cases'], 'hsx-mo sec');
      return tdL([sg(s.med), sg(s.p25, 0) + ' to ' + sg(s.p75, 0), pct(side === 'below' ? s.below : s.above) + (side === 'below' ? ' below' : ' above')], 'hsx-mo');
    };
    const mini = (heads, rows) => { const t = el('table', 'hsx-mini'); const h = el('tr'); heads.forEach((x) => h.appendChild(el('th', null, x))); t.appendChild(h); rows.forEach((r) => { const tr = el('tr'); r.forEach((x, i) => tr.appendChild(el(i ? 'td' : 'th', null, x))); t.appendChild(tr); }); return t; };
    const pathRow = (label, ms, side) => [label].concat([0, 1, 2, 3, 4, 5].map((m) => { const s = ms && ms[m]; return !s || !s.n ? '—' : s.n < 30 ? 'too few (' + s.n + ')' : sg(s.med) + ' · ' + pct(side === 'below' ? s.below : s.above) + ' ' + side + ' (' + s.n + ')'; }));
    const MONTHS = ['Month 1', 'Month 2', 'Month 3', 'Month 4', 'Month 5', 'Month 6'];
    const readings = (r) => mini(['Reading on ' + dT(r.last_date), 'TradingView', 'Computed from daily bars'], [
      ['Close', px(r.tv.close), px(r.computed.close)], ['RSI (14)', r.tv.rsi == null ? '—' : r.tv.rsi.toFixed(1), r.computed.rsi == null ? '—' : r.computed.rsi.toFixed(1)],
      ['MACD histogram (share of price)', sg(r.tv.macdh, 2), sg(r.computed.macdh, 2)], ['Daily range (ATR 14)', pct(r.tv.atr, 1), pct(r.computed.atr, 1)],
      ['50-day average', px(r.tv.sma50), px(r.computed.sma50)], ['200-day average', px(r.tv.sma200), px(r.computed.sma200)],
      ['52-week high (TradingView: highs; computed: closes)', px(r.tv.hi52), px(r.computed.hi52)], ['Volume vs average (TradingView 60-day; computed 50-day)', r.tv.vr == null ? '—' : r.tv.vr.toFixed(2) + '×', r.computed.vr == null ? '—' : r.computed.vr.toFixed(2) + '×']]);

    // small sortable table with click-to-open detail rows and an optional comparison row at the bottom
    function table(id, st, spec) {
      const t = $(id), head = t.querySelector('thead'), body = t.querySelector('tbody');
      function draw() {
        const cols = spec.cols();
        const tr = el('tr');
        cols.forEach((c) => { const th = el('th', c.cls || null); th.dataset.k = c.k; if (c.tip) th.title = c.tip; const b = el('button', null, c.label); b.type = 'button'; b.addEventListener('click', () => { if (st.k === c.k) st.dir = -st.dir; else { st.k = c.k; st.dir = c.dir || 1; } draw(); }); th.appendChild(b); th.setAttribute('aria-sort', st.k === c.k ? (st.dir > 0 ? 'ascending' : 'descending') : 'none'); tr.appendChild(th); });
        head.replaceChildren(tr);
        const col = cols.find((c) => c.k === st.k) || cols[0];
        const rs = spec.rows().slice().sort((a, b) => cmp(col.val(a), col.val(b)) * (cols.includes(col) && col.k === st.k ? st.dir : 1));
        const out = [];
        rs.forEach((r) => {
          const x = el('tr'); if (r._cls) x.className = r._cls; x.style.cursor = 'pointer';
          cols.forEach((c) => { const v = c.cell(r); x.appendChild(v instanceof HTMLElement ? v : el('td', c.cls || null, v)); });
          x.addEventListener('click', () => { st.open = st.open === r.sym ? null : r.sym; draw(); });
          out.push(x);
          if (st.open === r.sym) { const d = el('tr', 'scr-detail'); const c = el('td'); c.colSpan = cols.length; c.appendChild(spec.detail(r)); d.appendChild(c); out.push(d); }
        });
        if (rs.length && spec.foot && spec.footOn()) { const f = el('tr', 'hsx-foot'); cols.forEach((c) => f.appendChild(spec.foot(c))); out.push(f); }
        body.replaceChildren(...out);
        return rs.length;
      }
      return draw;
    }

    // ---- partial matches: k of a setup's (or a fall rule's) conditions met on the latest close
    const condTexts = (kind, k) => (kind === 'up' ? (HX.su && HX.su.setups[k] ? HX.su.setups[k].conditions : []) : (HX.st && HX.st.fall.rules[k] ? HX.st.fall.rules[k].conditions : []));
    const passedRule = (k) => !!(HX.d && (HX.d.fall_passed || []).includes(k));
    const fRate = (k, col) => { const x = HX.st && HX.st.fall.rules[k]; const v = x && x.results.all[col]; return v && v.n >= 30 ? v.rate : null; };
    const nearRows = (kind) => {
      const st = HX[kind], k = +st.cnt;
      return ((HX.d && HX.d.stocks) || []).filter((h) => inM(h, st)).map((h) => {
        let ms = (kind === 'up' ? h.near_up : h.near_fall).filter((m) => m[1] === k).map((m) => ({ k: m[0], met: m[1], tot: m[2], bits: m[3], vals: m[4] }));
        if (kind === 'fall' && !st.failed) ms = ms.filter((m) => passedRule(m.k));
        if (!ms.length) return null;
        const rk = (m) => (kind === 'up' ? rate(m.k) : fRate(m.k, 'fall10'));
        ms.sort((a, b) => cmp(rk(b), rk(a)));
        return Object.assign({}, h, { ms, _near: true, _best: rk(ms[0]), _cls: '' });
      }).filter(Boolean);
    };
    const nearSetupsCell = (kind) => (r) => {
      const x = el('td', 'sm');
      r.ms.forEach((m) => {
        const miss = condTexts(kind, m.k).filter((_, i) => m.bits[i] === '0');
        const d = el('span', 'hsx-ml', (kind === 'up' ? sname(m.k) : fname(m.k)) + ' · ' + m.met + ' of ' + m.tot + ' · missing: ' + miss.join('; ') + ' ');
        if (kind === 'up' && isNew(m.k)) d.appendChild(chip('⚠ new setup', 'am', NEW_WARN));
        if (kind === 'fall' && !passedRule(m.k)) d.appendChild(chip('did not pass the test', 'n', 'Shown for information only: this rule was no better than any stock with the same volatility.'));
        x.appendChild(d);
      });
      return x;
    };
    const nearCols = (kind) => [
      { k: 'name', label: 'Stock', val: (r) => r.name, cell: nameTd },
      { k: 'market', label: 'Market', cls: 'sec', val: (r) => r.market, cell: (r) => r.market },
      { k: 'w', label: 'Weight', cls: 'num', dir: -1, val: (r) => HX.w.get(r.sym), cell: (r) => (HX.w.has(r.sym) ? pct(HX.w.get(r.sym), 1) : '—') },
      { k: 'nset', label: (kind === 'up' ? 'Setups' : 'Fall rules') + ' with ' + HX[kind].cnt + ' condition' + (HX[kind].cnt === '1' ? '' : 's') + ' met on the latest close', cls: 'sm', dir: -1, val: (r) => r.ms.length, cell: nearSetupsCell(kind) },
      { k: 'nrate', label: kind === 'up' ? 'Highest historical success rate if every condition were met' : 'Highest historical rate of a 10% fall in 1 month if every condition were met', cls: 'sm', dir: -1, val: (r) => r._best, cell: (r) => (r._best == null ? '—' : pct(r._best, 1)), tip: 'This rate applies only when every condition is met on the same day. A partial match is not a setup.' },
      { k: 'px', label: 'Price now', cls: 'num sec', val: (r) => nowPx(r), cell: (r) => px(nowPx(r), r.cur) },
      { k: 'ld', label: 'Latest close', cls: 'sec', val: (r) => r.last_date, cell: (r) => dT(r.last_date) },
    ];
    const nearDetail = (kind) => (r) => {
      const w = box();
      w.appendChild(para(r.name + ' · ' + r.market + ' · latest close ' + px(r.last_close, r.cur) + ' on ' + dT(r.last_date) + '. A partial match is not a setup: the historical rates apply only when every condition is met on the same day.'));
      r.ms.forEach((m) => {
        const h = para((kind === 'up' ? sname(m.k) + ' · historical success rate ' + (rate(m.k) == null ? 'too few cases' : pct(rate(m.k), 1)) : fname(m.k) + (passedRule(m.k) ? '' : ' · did not pass the test')) + ' · ' + m.met + ' of ' + m.tot + ' conditions met on the latest close:'); h.style.color = 'var(--color-fg)'; h.style.marginTop = '8px';
        w.append(h, checklist(condTexts(kind, m.k).map((t, i) => ({ t, ok: m.bits[i] === '1', v: m.vals[i] }))));
      });
      return w;
    };

    // ---- upside table
    const upRows = () => (HX.d ? HX.d.up.filter((r) => inM(r, HX.up)).map((r) => Object.assign(r, { _cls: (r.levels.invalid != null && nowPx(r) < r.levels.invalid && r.status !== 'reached') ? 'hsx-below' : '' })) : []);
    const upStatus = (r) => {
      const p = nowPx(r);
      if (r.status === 'reached' || (r.target != null && p >= r.target)) return chip('Reached +20%', 'b2', 'A close at or above the target since the setup day.');
      if (r.levels.invalid != null && p < r.levels.invalid) return chip('Below invalidation', 'e2', 'The price is under the invalidation level of ' + sname(r.best) + '. The setup no longer holds.');
      return r.status === 'still' ? chip('Still matching', 'b1', 'The latest close still meets every condition of at least one listed setup.') : chip('No longer matching', 'n', 'The latest close no longer meets every condition; the row stays while the setup day is within the last 10 trading days.');
    };
    const upPaths = (r) => (HX.st && HX.st.up_paths[r.best] ? HX.st.up_paths[r.best].All.all : null);
    const UP_COLS = [
      { k: 'name', label: 'Stock', val: (r) => r.name, cell: nameTd },
      { k: 'market', label: 'Market', cls: 'sec', val: (r) => r.market, cell: (r) => r.market },
      { k: 'w', label: 'Weight', cls: 'num', dir: -1, val: (r) => HX.w.get(r.sym), cell: (r) => (HX.w.has(r.sym) ? pct(HX.w.get(r.sym), 1) : '—'), tip: 'Share of the whole portfolio’s value (percent only).' },
      { k: 'sd', label: 'Setup day', dir: -1, val: (r) => r.setup_day, cell: (r) => tdL([dT(r.setup_day), r.days_since === 0 ? 'latest close' : r.days_since + ' trading day' + (r.days_since === 1 ? '' : 's') + ' ago'], 'sm'), tip: 'The first day within the last 10 completed trading days on which a setup started. Target, deadline and typical date count from it.' },
      { k: 'setups', label: 'Matching setups (historical success rate)', cls: 'sm', dir: -1, val: (r) => r.setups.length, cell: (r) => {
        const x = el('td', 'sm');
        r.setups.forEach((m) => { const d = el('span', 'hsx-ml', sname(m.setup) + ' · ' + (m.rate == null ? 'too few cases' : pct(m.rate, 1) + ' of ' + m.n) + (m.run_start < r.setup_day ? ' · since ' + dT(m.run_start, false) : '') + (m.today ? '' : ' · not on the latest close') + ' '); if (isNew(m.setup)) d.appendChild(chip('⚠ new setup', 'am', NEW_WARN)); x.appendChild(d); });
        return x; }, tip: 'Every setup the stock matched in the last 10 trading days, highest historical success rate first.' },
      { k: 'rate', label: 'Highest historical success rate', cls: 'sm', dir: -1, val: (r) => rate(r.best), cell: (r) => { const t = stat(r.best); return tdL(t && t.n >= 30 ? [pct(t.hits / t.n, 1) + ' of ' + t.n, 'same-volatility base ' + pct(t.matched, 1)] : ['too few cases'], 'sm'); }, tip: 'From the latest monthly study of “Setups before 20% rises”, all markets together.' },
      { k: 'est', label: 'Estimated success rate', cls: 'sm', dir: -1, val: (r) => (r.est ? r.est.est : null), cell: (r) => {
        if (!r.est) return tdL(['—'], 'sm');
        const x = tdL([pct(r.est.est), 'range ' + Math.round(r.est.lo * 100) + '–' + Math.round(r.est.hi * 100) + '%', (r.est.n == null ? '' : r.est.n.toLocaleString('en-GB') + ' past cases of ' + sname(r.est.setup))], 'sm');
        if (r.est.kind !== 'model') { x.firstChild.append(' ', chip('setup average', 'n', 'The model did not score better than the setup’s own historical success rate on the check years, so that rate is shown.')); }
        return x; }, tip: 'The same estimate as Table C on the Strategy tab, with the inputs known on the setup day. The range is the typical gap between estimated and actual rates on the check years.' },
      { k: 'tgt', label: 'Target price', cls: 'num sm', val: (r) => r.target, cell: (r) => tdL([px(r.target, r.cur), 'needs ' + sg(r.target / nowPx(r) - 1) + ' from now'], 'num sm'), tip: 'The close on the setup day plus 20%.' },
      { k: 'typ', label: 'Typical date if reached', cls: 'sm', val: (r) => (r.typ ? r.typ[1] : null), cell: (r) => (r.typ ? tdL([dT(r.typ[1]), dT(r.typ[0], false) + ' – ' + dT(r.typ[2])], 'sm') : tdL(['—'], 'sm')), tip: 'Among past cases of this setup that reached +20%, half got there by this date. It is not a forecast that this stock will reach the target.' },
      { k: 'dl', label: 'Deadline', cls: 'sm', val: (r) => r.deadline, cell: (r) => { const n = daysLeft(r); const x = tdL([dT(r.deadline), n == null ? '' : n <= 0 ? 'passed' : n + ' trading days left'], 'sm'); if (n != null && n < 10) x.classList.add('hsx-am'); return x; }, tip: 'Setup day plus 42 trading days on the stock’s exchange. After that the setup counts as missed.' },
      { k: 'since', label: 'This stock since the setup day', cls: 'num', dir: -1, val: (r) => nowPx(r) / r.setup_close - 1, cell: (r) => tdL([sg(nowPx(r) / r.setup_close - 1), 'from ' + px(r.setup_close, r.cur)], 'num') },
    ].concat(MONTHS.map((lab, m) => ({ k: 'm' + m, label: lab, cls: 'hsx-mo', dir: -1, val: (r) => { const s = (upPaths(r) || [])[m]; return s && s.n >= 30 ? s.med : null; }, cell: (r) => monthCell(upPaths(r), m, 'above'),
      tip: 'Past cases of the stock’s highest-rate setup, ' + (21 * (m + 1)) + ' trading days after their setup day: median change from the setup-day close, the middle half of cases under it, and the share that were above the setup-day close. What followed past cases, not a forecast for this stock.' }))).concat([
      { k: 'px', label: 'Price now', cls: 'num sec', val: (r) => nowPx(r), cell: (r) => px(nowPx(r), r.cur) },
      { k: 'inv', label: 'Invalidation level (distance)', cls: 'sm', val: (r) => r.levels.invalid, cell: (r) => (r.levels.invalid == null ? '—' : px(r.levels.invalid, r.cur) + ' (' + sg(nowPx(r) / r.levels.invalid - 1) + ')'), tip: 'The level of the highest-rate setup, set on its first day in the window. Below it the setup no longer holds; the row is flagged at once.' },
      { k: 'st', label: 'Status', val: (r) => r.status, cell: (r) => { const x = el('td'); x.appendChild(upStatus(r)); return x; } },
    ]);
    const upFoot = (c) => {
      if (c.k === 'name') { const x = el('td', null, 'All stocks, any day'); x.colSpan = 1; return x; }
      if (/^m\d$/.test(c.k) && HX.st) return monthCell(HX.st.base_paths.All, +c.k.slice(1), 'above');
      if (c.k === 'setups') return el('td', 'sm', 'comparison: every stock in the study list on every day');
      return el('td');
    };
    function box() { const w = el('div'); w.style.maxWidth = '72rem'; w.style.position = 'sticky'; w.style.left = '0'; return w; }
    const upDetail = (r) => {
      const w = box();
      w.appendChild(para(r.name + ' · ' + r.market + ' · ' + r.size + ' cap · setup day ' + dT(r.setup_day) + ' at a close of ' + px(r.setup_close, r.cur) + ' · target ' + px(r.target, r.cur) + ' · deadline ' + dT(r.deadline) + ' · latest close ' + px(r.last_close, r.cur) + ' on ' + dT(r.last_date) + (r.earnings_next ? ' · next earnings ' + dT(r.earnings_next) + ' (TradingView)' : '') + '.'));
      r.setups.forEach((m) => {
        const h = para(sname(m.setup) + ' · historical success rate ' + (m.rate == null ? 'too few cases' : pct(m.rate, 1) + ' of ' + m.n) + ' · matched on ' + m.days.map((d) => dT(d, false)).join(', ') + (m.run_start < m.first ? ' (run started ' + dT(m.run_start) + ')' : '') + ' · conditions on the latest close:'); h.style.color = 'var(--color-fg)'; h.style.marginTop = '10px';
        w.append(h, checklist(m.conds), para('Levels set on ' + dT(m.first) + ': breakout ' + px(m.levels.breakout, r.cur) + ' · support ' + px(m.levels.support, r.cur) + ' · resistance ' + (m.levels.resistance == null ? 'none overhead' : px(m.levels.resistance, r.cur)) + ' · invalidation ' + px(m.levels.invalid, r.cur) + '.'));
        if (isNew(m.setup)) { const x = para('⚠ ' + NEW_WARN); x.classList.add('hsx-warn'); w.appendChild(x); }
      });
      if (HX.st && HX.st.up_paths[r.best]) {
        const P = HX.st.up_paths[r.best], vb = r.vb == null ? null : HX.st.base_paths.by_vb[String(r.vb)];
        w.appendChild(para('The next six months after past cases of ' + sname(r.best) + ' (median change from the setup-day close · share above it · cases):'));
        w.appendChild(mini([''].concat(MONTHS), [pathRow('All years', P.All.all, 'above'), pathRow('Build years (before ' + dT(HX.st.period.split) + ')', P.All.build, 'above'), pathRow('Check years (from ' + dT(HX.st.period.split) + ')', P.All.check, 'above'), pathRow(r.market + ' only', P[r.market] && P[r.market].all, 'above'), pathRow('All stocks, any day, same volatility', vb, 'above')]));
      }
      w.appendChild(readings(r));
      return w;
    };
    const drawUp = table('hsx-up-t', HX.up, { cols: () => (HX.up.cnt === 'all' ? UP_COLS : nearCols('up')), rows: () => (HX.up.cnt === 'all' ? upRows() : nearRows('up')),
      detail: (r) => (r._near ? nearDetail('up')(r) : upDetail(r)), foot: upFoot, footOn: () => HX.up.cnt === 'all' });

    // ---- fall table
    const FMODEL_TIP = 'Estimated from past cases with the same method as the upside estimate (fitted on the build years only, kept only if it beat the plain rule rate on the check years, never above the highest actual group rate, rounded to 5%).';
    const fallPaths = (r) => (HX.st && HX.st.fall.paths[r.best] ? HX.st.fall.paths[r.best].All.all : null);
    const estCell = (e) => (!e ? tdL(['—'], 'sm') : (() => { const x = tdL([pct(e.est), 'range ' + Math.round(e.lo * 100) + '–' + Math.round(e.hi * 100) + '%'], 'sm'); if (e.kind !== 'model') x.firstChild.append(' ', chip('rule average', 'n')); return x; })());
    const FALL_COLS = [
      { k: 'name', label: 'Stock', val: (r) => r.name, cell: nameTd },
      { k: 'market', label: 'Market', cls: 'sec', val: (r) => r.market, cell: (r) => r.market },
      { k: 'w', label: 'Weight', cls: 'num', dir: -1, val: (r) => HX.w.get(r.sym), cell: (r) => (HX.w.has(r.sym) ? pct(HX.w.get(r.sym), 1) : '—') },
      { k: 'sd', label: 'Setup day', dir: -1, val: (r) => r.setup_day, cell: (r) => tdL([dT(r.setup_day), r.days_since === 0 ? 'latest close' : r.days_since + ' trading days ago'], 'sm') },
      { k: 'rules', label: 'Matching fall setups (historical success rate: 10% in 1 month · more than 20% in 3 months)', cls: 'sm', val: (r) => r.rules.length, cell: (r) => { const x = el('td', 'sm'); r.rules.forEach((m) => { const d = el('span', 'hsx-ml', fname(m.rule) + ' · ' + pct(m.rate10, 1) + ' · ' + pct(m.rate20, 1) + ' of ' + m.n + (m.today ? '' : ' · not on the latest close') + ' '); if (m.passed === false) d.appendChild(chip('did not pass the test', 'n', 'Shown for information only: this rule was no better than any stock with the same volatility.')); x.appendChild(d); }); return x; } },
      { k: 'e10', label: 'Estimated rate: fall of 10% in 1 month', cls: 'sm', dir: -1, val: (r) => (r.est10 ? r.est10.est : null), cell: (r) => (r.any_passed === false ? tdL(['—', 'its rules did not pass the test'], 'sm') : estCell(r.est10)), tip: FMODEL_TIP },
      { k: 'e20', label: 'Estimated rate: fall of more than 20% in 3 months', cls: 'sm', dir: -1, val: (r) => (r.est20 ? r.est20.est : null), cell: (r) => (r.any_passed === false ? tdL(['—', 'its rules did not pass the test'], 'sm') : estCell(r.est20)), tip: FMODEL_TIP },
      { k: 'lvl', label: 'Level where the setup no longer holds (distance)', cls: 'sm', val: (r) => r.level, cell: (r) => tdL([px(r.level, r.cur), sg(nowPx(r) / r.level - 1) + ' from it']), tip: 'The highest close of the 10 sessions up to the setup day. A close above it means the setup no longer holds.' },
      { k: 'since', label: 'This stock since the setup day', cls: 'num', val: (r) => nowPx(r) / r.setup_close - 1, cell: (r) => tdL([sg(nowPx(r) / r.setup_close - 1), 'from ' + px(r.setup_close, r.cur)], 'num') },
    ].concat(MONTHS.map((lab, m) => ({ k: 'm' + m, label: lab, cls: 'hsx-mo', val: (r) => { const s = (fallPaths(r) || [])[m]; return s && s.n >= 30 ? s.med : null; }, cell: (r) => monthCell(fallPaths(r), m, 'below'),
      tip: 'Past cases of the stock’s highest-rate fall setup, ' + (21 * (m + 1)) + ' trading days after their setup day: median change, the middle half, and the share below the setup-day close. Not a forecast.' }))).concat([
      { k: 'px', label: 'Price now', cls: 'num sec', val: (r) => nowPx(r), cell: (r) => px(nowPx(r), r.cur) },
      { k: 'dl', label: 'Deadline', cls: 'sm', val: (r) => r.deadline, cell: (r) => { const n = daysLeft(r); const x = tdL([dT(r.deadline), n == null ? '' : n <= 0 ? 'passed' : n + ' trading days left'], 'sm'); if (n != null && n < 10) x.classList.add('hsx-am'); return x; }, tip: 'Setup day plus 63 trading days (three months) on the stock’s exchange.' },
      { k: 'st', label: 'Status', val: (r) => r.status, cell: (r) => { const x = el('td'); const p = nowPx(r); x.appendChild(r.status === 'fell10' ? chip('Fell 10% within a month', 'e2') : p > r.level ? chip('Above its level', 'n', 'The price is above the level where the setup no longer holds.') : r.status === 'still' ? chip('Still matching', 'e1') : chip('No longer matching', 'n')); return x; } },
    ]);
    const fallFoot = (c) => (c.k === 'name' ? el('td', null, 'All stocks, any day') : /^m\d$/.test(c.k) && HX.st ? monthCell(HX.st.base_paths.All, +c.k.slice(1), 'below') : el('td'));
    const fallDetail = (r) => {
      const w = box();
      w.appendChild(para(r.name + ' · ' + r.market + ' · setup day ' + dT(r.setup_day) + ' at ' + px(r.setup_close, r.cur) + ' · level ' + px(r.level, r.cur) + ' · deadline ' + dT(r.deadline) + ' · lowest close since ' + px(r.min_since, r.cur) + '.'));
      r.rules.forEach((m) => { const h = para(fname(m.rule) + ' · matched on ' + m.days.map((d) => dT(d, false)).join(', ') + ' · conditions on the latest close:'); h.style.color = 'var(--color-fg)'; w.append(h, checklist(m.conds)); });
      const P = HX.st && HX.st.fall.paths[r.best];
      if (P) {
        const a = P.All.all.filter((s) => s.n >= 30); const lo = a.length ? a.reduce((b, s, i) => (s.med < b.v ? { v: s.med, i: P.All.all.indexOf(s) } : b), { v: Infinity, i: -1 }) : null;
        if (lo && lo.i >= 0) w.appendChild(para('Lowest median point of the six months after past cases: ' + sg(lo.v) + ' in month ' + (lo.i + 1) + '.'));
        w.appendChild(mini([''].concat(MONTHS), [pathRow('All years', P.All.all, 'below'), pathRow('Build years', P.All.build, 'below'), pathRow('Check years', P.All.check, 'below'), pathRow('All stocks, any day, same volatility', r.vb == null ? null : HX.st.base_paths.by_vb[String(r.vb)], 'below')]));
      }
      w.appendChild(readings(r));
      return w;
    };
    const fallRows = () => (HX.d ? ((HX.fall.failed ? HX.d.fall_all : HX.d.fall) || []).filter((r) => inM(r, HX.fall)) : []);
    const drawFall = table('hsx-fall-t', HX.fall, { cols: () => (HX.fall.cnt === 'all' ? FALL_COLS : nearCols('fall')), rows: () => (HX.fall.cnt === 'all' ? fallRows() : nearRows('fall')),
      detail: (r) => (r._near ? nearDetail('fall')(r) : fallDetail(r)), foot: fallFoot, footOn: () => HX.fall.cnt === 'all' });

    // ---- filters: market buttons (like Table C) and how many conditions are met
    function options(kind) {
      const st = HX[kind], sel = $('hsx-' + kind + '-cnt'), save = st.cnt;
      const maxK = kind === 'up' ? 5 : 2;
      const nAll = kind === 'up' ? upRows().length : fallRows().length;
      const opts = [['all', (kind === 'up' ? 'All conditions met: a setup in the last ' : 'All conditions met: a fall setup in the last ') + HX.d.window + ' trading days (' + nAll + ')']];
      for (let k = 1; k <= maxK; k += 1) { st.cnt = String(k); opts.push([String(k), k + ' condition' + (k === 1 ? '' : 's') + ' of the ' + (kind === 'up' ? 'setup' : 'rule') + ' met on the latest close (' + nearRows(kind).length + ')']); }
      st.cnt = save;
      sel.replaceChildren(...opts.map(([v, t]) => { const o = el('option', null, t); o.value = v; return o; }));
      sel.value = st.cnt;
    }
    function tabs(kind) {
      const box = $('hsx-' + kind + '-tabs');
      MKTS.forEach((m) => { const b = el('button', null, m === 'All' ? 'All markets' : m); b.type = 'button'; b.dataset.m = m; b.addEventListener('click', () => { HX[kind].mkt = m; HX[kind].open = null; paint(); }); box.appendChild(b); });
    }
    tabs('up'); tabs('fall');
    $('hsx-up-cnt').addEventListener('change', (e) => { HX.up.cnt = e.target.value; HX.up.open = null; HX.up.k = e.target.value === 'all' ? 'rate' : 'nrate'; HX.up.dir = -1; paint(); });
    $('hsx-fall-cnt').addEventListener('change', (e) => { HX.fall.cnt = e.target.value; HX.fall.open = null; HX.fall.k = e.target.value === 'all' ? 'e10' : 'nrate'; HX.fall.dir = -1; paint(); });
    $('hsx-fall-failed').addEventListener('change', (e) => { HX.fall.failed = e.target.checked; HX.fall.open = null; paint(); });

    function coverage(box) {
      const d = HX.d; const out = [];
      if (d.mismatch.length) { const p = para('⚠ Skipped today because TradingView and the daily bars disagree (data mismatch): ' + d.mismatch.map((m) => m.name + ' (' + m.reason + ')').join('; ') + '.'); p.classList.add('hsx-warn'); out.push(p); }
      if (d.not_covered.length) { const det = el('details'); det.appendChild(el('summary', null, 'Not covered (' + d.not_covered.length + ')')); const ul = el('ul', 'hsx-list'); d.not_covered.forEach((x) => ul.appendChild(el('li', null, x.name + ' (' + x.sym + '): ' + x.reason))); det.appendChild(ul); out.push(det); }
      box.replaceChildren(...out);
    }
    function stamp(id) {
      const d = HX.d, p = $(id); const age = tdSince(d.built_local.slice(0, 10));
      const bars = Object.entries(d.last_bar).map(([m, x]) => m + ' ' + dT(x, false)).join(', ');
      p.className = 'hs-note';
      let t = 'Last rebuilt ' + dT(d.built_local.slice(0, 10)) + ' at ' + d.built_local.slice(11, 16) + ' Stockholm time (daily candles to ' + bars + ')' + (HX.st ? '; study last run ' + dT(HX.st.built.slice(0, 10)) : '') + '.' + (d.notes.length ? ' ' + d.notes.map((n) => n.charAt(0).toUpperCase() + n.slice(1)).join('. ') + '.' : '') + (HX.liveAt ? ' Prices live from TradingView (15 min delayed), updated ' + HX.liveAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + '.' : '');
      if (age != null && age > 2) { p.className = 'hs-note hsx-warn'; t = '⚠ This table is ' + age + ' trading days old, so the latest rebuild may have failed. Prices still refresh but the names may be out of date. ' + t; }
      if (d.test) t = 'TEST DATA. ' + t;
      p.textContent = t;
    }
    function paint() {
      const d = HX.d, st = HX.st;
      if (!d) return;
      HX.w = weights();
      const latest = Object.values(d.last_bar).sort().pop();
      $('hsx-up-note').textContent = 'Your stock holdings that showed one of the twelve setups of “Setups before 20% rises” (Strategy tab) on one of their last ' + d.window + ' completed trading days, measured with the same rules. Click a row for the conditions, the levels and the readings. Names are added and removed only at the daily rebuild; the price and the distances refresh every 5 minutes.';
      const newOnes = d.up.some((r) => r.setups.some((m) => isNew(m.setup)));
      $('hsx-up-warn').hidden = !newOnes; $('hsx-up-warn').textContent = '⚠ Setups a) to g) (marked “new setup”): ' + NEW_WARN + ' The estimated success rates and the six months come from the same past cases, so this applies to them too.';
      ['up', 'fall'].forEach((kind) => document.querySelectorAll('#hsx-' + kind + '-tabs button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.m === HX[kind].mkt))));
      options('up');
      const nu = drawUp();
      const where = (st) => (st.mkt === 'All' ? '' : ' in ' + st.mkt);
      $('hsx-up-t').parentNode.hidden = !nu; $('hsx-up-empty').hidden = !!nu;
      $('hsx-up-shown').textContent = nu + (nu === 1 ? ' holding shown' : ' holdings shown');
      $('hsx-up-empty').textContent = HX.up.cnt === 'all' ? 'None of your holdings' + where(HX.up) + ' had a setup in the last ' + d.window + ' trading days (' + d.checked + ' holdings checked, latest close ' + dT(latest) + ').' : 'None of your holdings' + where(HX.up) + ' meets exactly ' + HX.up.cnt + ' of a setup’s conditions on the latest close.';
      const lu = d.live_up;
      $('hsx-up-live').className = 'hs-note' + (lu.warn ? ' hsx-warn' : '');
      $('hsx-up-live').textContent = lu.n_est >= 30 ? (lu.warn ? '⚠ The estimates are running too high: ' : 'Live check: ') + 'of ' + lu.n_est + ' holdings’ setups judged so far, the average estimated success rate was ' + pct(lu.avg_est) + ' and ' + pct(lu.actual) + ' reached +20% within 42 trading days.' : 'Live check of this table: ' + lu.resolved + ' of ' + lu.logged + ' logged setups judged so far; the comparison with the estimates is shown from 30. It counts only this table’s own cases, logged within two trading days of their setup day (the ones already in the window when the table started are left out, because their outcome was partly known).';
      $('hsx-up-how').textContent = 'How it is worked out: a holding is listed when a setup started on one of its last ' + d.window + ' completed trading days on its own exchange, and the target (setup-day close plus 20%), the deadline (42 trading days) and the typical date all count from that setup day. The estimated success rate is the same model as Table C on the Strategy tab, with the inputs known on the setup day, and Month 1 to 6 show what followed past cases of the holding’s highest-rate setup (median change from the setup-day close, the middle half of cases, the share above it), with all stocks on any day at the bottom for comparison. Readings come from TradingView and the history from the study’s adjusted daily bars (a holding whose latest close differs between the two by more than 1% is skipped and listed below); the stock list leaves out companies that fell and dropped out, so all of this looks better than it really was, and it describes past chart patterns, not advice.';
      if (st && d.up.length) {
        const ks = Array.from(new Set(d.up.map((r) => r.best)));
        $('hsx-up-check').textContent = 'Did the six-month path hold up after the years it was measured on? Median change at month 6, build years (before ' + dT(st.period.split) + ') against check years: ' + ks.map((k) => { const P = st.up_paths[k].All; return sname(k) + ' ' + sg(P.build[5].med) + ' against ' + sg(P.check[5].med); }).join('; ') + '; all stocks on any day ' + sg(st.base_paths.All[5].med) + ' over the whole period.';
      } else $('hsx-up-check').textContent = '';
      coverage($('hsx-up-cov')); stamp('hsx-up-stamp');

      // fall table
      const passed = d.fall_passed || [];
      const tested = st ? st.fall.order.length : 6;
      $('hsx-fall-note').textContent = passed.length
        ? 'Your stock holdings that showed one of the fall setups that passed the test on one of their last ' + d.window + ' completed trading days. A fall of 10% in 1 month: the lowest close in the next 21 trading days at least 10% under the setup-day close. A fall of more than 20% in 3 months: the lowest close in the next 63 trading days more than 20% under it.'
        : 'No fall setup passed the test, so no holding is listed. ' + tested + ' fixed rules, written down before testing, were run on every stock and day; to be used here a rule had to beat the rate of a 10% fall within a month among days with the same volatility by at least 5 points in both the build years and the check years, with at least 30 cases in each and no single market, year or month holding more than half of its cases. None did, so the table stays empty rather than lowering the bar. The results are below; tick the box to see the holdings that match those rules anyway, marked as not passed.';
      options('fall');
      const nf = drawFall();
      $('hsx-fall-wrap').hidden = !nf;
      $('hsx-fall-shown').textContent = nf + (nf === 1 ? ' holding shown' : ' holdings shown');
      $('hsx-fall-empty').hidden = !!nf || (!passed.length && !HX.fall.failed);
      $('hsx-fall-empty').textContent = HX.fall.cnt === 'all' ? 'None of your holdings' + where(HX.fall) + ' had a fall setup in the last ' + d.window + ' trading days (' + d.checked + ' holdings checked, latest close ' + dT(latest) + ').' : 'None of your holdings' + where(HX.fall) + ' meets exactly ' + HX.fall.cnt + ' of a rule’s conditions on the latest close.';
      if (HX.fall.failed) $('hsx-fall-note').textContent += ' Shown for information: rules marked “did not pass the test” were no better than any stock with the same volatility, so their rates do not single anything out.';
      const lf = d.live_fall;
      $('hsx-fall-live').hidden = !passed.length && !lf.logged;
      $('hsx-fall-live').className = 'hs-note' + (lf.warn ? ' hsx-warn' : '');
      $('hsx-fall-live').textContent = !passed.length && !lf.logged ? '' : lf.resolved >= 20 ? (lf.warn ? '⚠ The live record is more than 10 points under the historical rate: ' : 'Live record: ') + pct(lf.rate) + ' of ' + lf.resolved + ' judged cases fell 10% within a month, against a historical ' + pct(lf.hist) + '.' : 'Live record: ' + lf.resolved + ' of ' + lf.logged + ' logged cases judged so far; shown from 20.';
      $('hsx-fall-how').textContent = 'How it is worked out: the rules, the cases and the base rates come from a monthly study on the same stock list and daily bars as “Setups before 20% rises”, with one case per stock and rule every 63 trading days, rules judged on the years before ' + (st ? dT(st.period.split) : '1 Jul 2024') + ' and checked unchanged on the years since. Because the rules were written with the whole period in view, the check years are not fully independent, and the stock list leaves out companies that fell and dropped out, which makes falls look rarer than they were. It describes past chart patterns and is not advice.';
      if (st) {
        const R = st.fall.rules;
        const f = (v) => (v && v.n ? pct(v.rate, 1) + ' (same-volatility base ' + pct(v.matched, 1) + ', ' + v.n.toLocaleString('en-GB') + ' cases)' : '—');
        const t = el('table', 'hold'); const hr = el('tr');
        ['Rule', 'Used here?', 'All of these on the same day', 'Fall of 10% in 1 month: build years', 'Fall of 10% in 1 month: check years', 'Fall of more than 20% in 3 months: all years', 'Both falls'].forEach((x) => { const h = el('th', null, x); h.style.whiteSpace = 'normal'; h.style.verticalAlign = 'bottom'; hr.appendChild(h); });
        const th = el('thead'); th.appendChild(hr); t.appendChild(th); const tb = el('tbody');
        st.fall.order.forEach((k) => { const x = R[k].results; const tr = el('tr'); [R[k].name, R[k].passed ? 'Passed' : 'No: ' + R[k].why_not.join('; '), R[k].conditions.join('; '), f(x.build.fall10), f(x.check.fall10), f(x.all.fall20), x.all.fall_both.n ? pct(x.all.fall_both.rate, 1) : '—'].forEach((v, i) => { const c = el('td', null, v); c.style.whiteSpace = 'normal'; c.style.minWidth = i === 1 || i === 2 ? '16rem' : '9rem'; tr.appendChild(c); }); tb.appendChild(tr); });
        t.appendChild(tb);
        const det = el('details'); if (!passed.length) det.open = true;
        det.appendChild(el('summary', null, 'The fall study: every rule tested (' + st.fall.order.length + ')'));
        const wrap = el('div', 'tbl-wrap'); wrap.appendChild(t); det.appendChild(wrap);
        $('hsx-fall-test').replaceChildren(det);
      }
      stamp('hsx-fall-stamp');
    }
    async function getJson(url) { const r = await fetch(url + '?t=' + Math.floor(Date.now() / 60000), { cache: 'no-cache' }); if (!r.ok) throw new Error(url + ' HTTP ' + r.status); return r.json(); }
    async function load() {
      try {
        const [d, st, su] = await Promise.all([getJson('data/holdings_setups.json'), getJson('data/holdings_study.json').catch(() => null), getJson('data/setups_study.json').catch(() => null)]);
        HX.d = d; HX.st = st; HX.su = su;
      } catch (e) {
        ['hsx-up-note', 'hsx-fall-note'].forEach((id) => { $(id).textContent = 'Not available yet: this table is written by its own daily rebuild, and the first one has not finished.'; });
        $('hsx-up-t').parentNode.hidden = true; $('hsx-fall-wrap').hidden = true; return;
      }
      try { paint(); } catch (e) { $('hsx-up-note').textContent = 'Not available yet (' + e.message + ').'; }
      refreshLive();
    }
    async function refreshLive() {
      if (!HX.d || document.hidden || (typeof LIVE !== 'undefined' && LIVE.paused)) return;
      const syms = Array.from(new Set(HX.d.up.concat(HX.d.fall, HX.d.fall_all || [], HX.d.stocks || []).map((r) => r.sym)));
      if (!syms.length) return;
      try {
        const res = await fetch('https://scanner.tradingview.com/global/scan', { method: 'POST', headers: { 'Content-Type': 'text/plain;charset=UTF-8' }, body: JSON.stringify({ symbols: { tickers: syms }, columns: ['close'] }) });
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const j = await res.json(); (j.data || []).forEach((x) => { if (typeof x.d[0] === 'number') HX.live.set(x.s, x.d[0]); }); HX.liveAt = new Date();
      } catch (e) { /* keep the last prices */ }
      try { paint(); } catch (e) { /* keep the page */ }
    }
    window.__hsx = HX;
    load();
    setInterval(refreshLive, 300000);
    setInterval(() => { if (!document.hidden) load(); }, 3600000);
  });
  </script>
''' + END + "\n"


def main():
    s = open(PAGE, encoding="utf-8").read()
    if BEGIN in s:
        i, j = s.index(BEGIN), s.index(END) + len(END) + 1
        s = s[:i] + s[j:]
    assert s.count(ANCHOR) == 1
    s = s.replace(ANCHOR, BLOCK + ANCHOR, 1)
    open(PAGE, "w", encoding="utf-8").write(s)
    print("inserted", len(BLOCK), "characters")


if __name__ == "__main__":
    main()
