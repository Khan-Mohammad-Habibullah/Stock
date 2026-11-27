#!/usr/bin/env python3
"""Page changes for the seven newer setups on the Strategy tab ("Setups before 20% rises"): Table A grouping and three new columns plus a
by-year / busiest-month breakdown, Table C with one row per stock listing all its matching setups, the warning note, and the notes text."""
PATH = "index.html"
s = open(PATH, encoding="utf-8").read()
if "su-a-warn" in s:
    print("already patched"); raise SystemExit


def rep(old, new, cnt=1):
    global s
    assert s.count(old) == cnt, (s.count(old), old[:90])
    s = s.replace(old, new)


# ---------------------------------------------------------------- CSS
rep("  #setups ul.su-list {", """  #setups .su-warn-box { border-left: 3px solid var(--color-warn); background: color-mix(in srgb, var(--color-warn) 12%, transparent); padding: 8px 12px; border-radius: 6px; color: var(--color-fg); }
  #setups td.hl-am { background: color-mix(in srgb, var(--color-warn) 24%, transparent); font-weight: 600; }
  #setups tr.su-grp td { background: color-mix(in srgb, var(--color-fg) 6%, transparent); font-weight: 600; text-transform: none; padding: 8px 10px; }
  #setups table.su-mini { width: auto; margin: 4px 0 10px; }
  #setups table.su-mini th, #setups table.su-mini td { padding: 3px 18px 3px 0; text-align: left; font-weight: normal; white-space: nowrap; }
  #setups table.su-mini th { color: var(--color-fg-muted); }
  #setups .su-ml { display: block; margin: 2px 0; }
  #setups ul.su-list {""")

# ---------------------------------------------------------------- HTML
rep("""    <h3>Table A &ndash; Setup rules and how they performed</h3>
    <p class="hs-note" id="su-a-note"></p>""", """    <h3>Table A &ndash; Setup rules and how they performed</h3>
    <p class="hs-note su-warn-box" id="su-a-warn"></p>
    <p class="hs-note" id="su-a-note"></p>""")
rep("""    <p class="hs-note" id="su-c-note"></p>
    <div class="scr-tabs" id="su-tabs-c\"""", """    <p class="hs-note" id="su-c-note"></p>
    <p class="hs-note su-warn-box" id="su-c-warn"></p>
    <div class="scr-tabs" id="su-tabs-c\"""")

# ---------------------------------------------------------------- JS: state, helpers
rep("C: { k: 'rank', dir: 1, open: null }, R:", "C: { k: 'rate', dir: -1, open: null }, R:")
rep("    const fmtPct = (v, d = 1)", """    ['wash_turn', 'deep_dry', 'deep_vol', 'wash_bounce', 'os60', 'os_hv'].forEach((k) => { LEVEL_TXT[k] = LEVEL_TXT.oversold; });
    LEVEL_TXT.hv_brk = LEVEL_TXT.base;
    const NEW_WARN = 'The stock list is today’s 70 largest companies in each market. A company that fell 60% and kept falling usually dropped out of that list, so it is missing from this test. This makes the deep-fall setups (a, b, c, e) look better than they really were. Most of their cases also come from the 2022 bear market, and the washout setups (a, d) rest on a few market crashes. Expect real results to be lower than the historical success rate shown.';
    const NEW_KEYS = { wash_turn: 'a', deep_dry: 'b', deep_vol: 'c', wash_bounce: 'd', os60: 'e', os_hv: 'f', hv_brk: 'g' };
    const isNewGroup = (k) => !!(SU.study && SU.study.setups[k] && SU.study.setups[k].group === 'new');
    const isNewSetup = (k) => { const x = SU.study && SU.study.setups[k]; return !!(x && x.added && (Date.now() - new Date(x.added + 'T12:00:00').getTime()) / 864e5 < 31); };
    const fmtPct = (v, d = 1)""")
# generic table: optional group heading rows (only in the default order)
rep("    function table(id, st, cols, getRows, detail, keyOf, empty) {", "    function table(id, st, cols, getRows, detail, keyOf, empty, opts) {")
rep("""        const out = [];
        rows.forEach((r) => {
          const row = document.createElement('tr'); const key = keyOf(r); row.dataset.key = key;""", """        const out = [];
        let prevR = null;
        rows.forEach((r) => {
          if (opts && opts.head && st.k === cols[0].k && st.dir === 1) {
            const h = opts.head(r, prevR);
            if (h) { const hr = document.createElement('tr'); hr.className = 'su-grp'; const hc = document.createElement('td'); hc.colSpan = cols.length; hc.textContent = h; hr.appendChild(hc); out.push(hr); }
          }
          prevR = r;
          const row = document.createElement('tr'); const key = keyOf(r); row.dataset.key = key;""")

# ---------------------------------------------------------------- Table A
rep("""const b = document.createElement('strong'); b.textContent = setupName(r.k); const p = document.createElement('div'); p.className = 'hs-note'; p.textContent = SU.study.setups[r.k].short; c.append(b, p); return c; } },
      { k: 'n', label: 'Times it appeared',""", """const b = document.createElement('strong'); b.textContent = (isNewGroup(r.k) ? NEW_KEYS[r.k] + ') ' : '') + setupName(r.k); const p = document.createElement('div'); p.className = 'hs-note'; p.textContent = SU.study.setups[r.k].short; c.append(b); if (isNewSetup(r.k)) { const nw = document.createElement('span'); nw.className = 'chip b2'; nw.textContent = 'New'; nw.title = 'Added on ' + dTxt(SU.study.setups[r.k].added) + '; marked New for the first month.'; c.append(document.createTextNode(' '), nw); } c.append(p); return c; } },
      { k: 'n', label: 'Times it appeared',""")
rep("""      { k: 'test', label: 'Since Jul 2024 (not used to pick the rules)',""", """      { k: 'edge', label: 'Edge over same-volatility base (points)', cls: 'num', dir: -1, val: (r) => r.st && r.st.edge, cell: (r) => (r.st && r.st.edge != null ? (r.st.edge > 0 ? '+' : '') + (r.st.edge * 100).toFixed(1) + ' pts' : '—'), tip: 'Success rate minus the base rate among days with the same 20-day volatility, in percentage points. Shown from 30 cases.' },
      { k: 'weeks', label: 'Different weeks with a case', cls: 'num sec', dir: -1, val: (r) => r.st && r.st.weeks, cell: (r) => (r.st ? String(r.st.weeks) : '—'), tip: 'Number of calendar weeks in which the setup had at least one case. A low number means the cases are bunched into a few episodes.' },
      { k: 'busy', label: 'Busiest month’s share of cases', cls: 'num sec', dir: -1, val: (r) => r.st && r.st.busy, cell: (r) => { if (!r.st || r.st.busy == null) return '—'; const c = td(fmtPct(r.st.busy), 'num sec' + (r.st.busy > 0.15 ? ' hl-am' : '')); if (r.st.busy > 0.15) c.title = 'More than 15% of all cases fall in one calendar month (' + r.st.top_months[0].m + ').'; return c; }, tip: 'Share of the setup’s cases that fall in its single busiest calendar month. Amber above 15%.' },
      { k: 'test', label: 'Since Jul 2024 (not used to pick the rules)',""")
rep("""    (r) => { const w = document.createElement('div'); w.append(para(SU.study.setups[r.k].short + '. Every condition must be true on the same day:'), checklist(SU.study.setups[r.k].conditions.map((t) => ({ t, ok: null }))), para(LEVEL_TXT[r.k])); return w; },
    (r) => r.k, () => 'Loading…');""", """    (r) => {
      const w = document.createElement('div'); w.append(para(SU.study.setups[r.k].short + '. Every condition must be true on the same day:'), checklist(SU.study.setups[r.k].conditions.map((t) => ({ t, ok: null }))), para(LEVEL_TXT[r.k]));
      if (isNewGroup(r.k)) { const wn = para('⚠ ' + NEW_WARN); wn.classList.add('su-warn-box'); w.appendChild(wn); }
      if (r.st && r.st.years) {
        const mini = (heads, rows) => { const t = document.createElement('table'); t.className = 'hold su-mini'; const tr = document.createElement('tr'); heads.forEach((h) => { const th = document.createElement('th'); th.textContent = h; tr.appendChild(th); }); const th0 = document.createElement('thead'); th0.appendChild(tr); const tb = document.createElement('tbody'); rows.forEach((x) => { const r1 = document.createElement('tr'); x.forEach((v) => { const c = document.createElement('td'); c.textContent = v; r1.appendChild(c); }); tb.appendChild(r1); }); t.append(th0, tb); return t; };
        const rt = (h, n) => (n >= 30 ? fmtPct(h / n) + ' (' + h + ' of ' + n + ')' : h + ' of ' + n + ' (too few cases for a rate)');
        w.appendChild(para('Cases and historical success rate by year' + (SU.mkt === 'All' ? '' : ' (' + SU.mkt + ' only)') + ':'));
        w.appendChild(mini(['Year', 'Cases', 'Reached +20%'], Object.keys(r.st.years).sort().map((y) => [y, String(r.st.years[y].n), rt(r.st.years[y].hits, r.st.years[y].n)])));
        w.appendChild(para('The three busiest months:'));
        w.appendChild(mini(['Month', 'Cases', 'Share of all cases', 'Reached +20%'], r.st.top_months.map((m) => [m.m, String(m.n), fmtPct(m.n / r.st.n), rt(m.hits, m.n)])));
      }
      return w;
    },
    (r) => r.k, () => 'Loading…',
    { head: (r, prev) => (isNewGroup(r.k) && (!prev || !isNewGroup(prev.k)) ? 'Deep-fall, washout and high-volatility setups' : null) });""")

# ---------------------------------------------------------------- Table C: one row per stock, all matching setups, best historical success rate first
a = s.index("    const candRows = () => {")
b = s.index("    // ---- removed names")
newC = r"""    const rateOf = (k) => { const t = stat(k, 'All'); return t && t.n >= 30 ? t.hits / t.n : null; };
    const rateCell = (k) => { const t = stat(k, 'All'); return !t ? '—' : t.n < 30 ? 'too few cases' : fmtPct(t.hits / t.n) + ' of ' + t.n + ' (same-volatility base ' + fmtPct(t.matched) + ')'; };
    const candRows = () => {
      if (!SU.cur) return [];
      const by = new Map();
      SU.cur.candidates.filter((c) => (c.complete || SU.near) && inMkt(c.market, SU.mC) && (!SU.setup || c.setup === SU.setup) && matchQ(c.name, c.sym))
        .forEach((c) => { if (!by.has(c.sym)) by.set(c.sym, []); by.get(c.sym).push(c); });
      return [...by.values()].map((ms) => {
        ms.sort((x, y) => (y.complete - x.complete) || ((rateOf(y.setup) == null ? -1 : rateOf(y.setup)) - (rateOf(x.setup) == null ? -1 : rateOf(x.setup))));
        const best = ms[0];
        const g = Object.assign({}, best, { ms, _k: best.sym, bestRate: rateOf(best.setup), _comp: ms.some((m) => m.complete) });
        g._below = ms.filter((m) => m.complete && m.invalid != null && px(m) < m.invalid).map((m) => m.setup);
        g._cls = g._below.length ? 'below' : '';
        g._new = ms.some((m) => m.complete && m.new);
        g._since = ms.filter((m) => m.complete).map((m) => m.first_seen).sort()[0] || best.first_seen;
        return g;
      });
    };
    const drawC = table('su-c', SU.C, [
      { k: 'name', label: 'Stock', val: (c) => c.name, cell: (c) => nameTd(c.sym, c.name) },
      { k: 'market', label: 'Market', cls: 'sec', val: (c) => c.market, cell: (c) => c.market },
      { k: 'setups', label: 'Matching setups (historical success rate)', cls: 'sm', val: (c) => c.ms.length, dir: -1, cell: (c) => {
        const x = document.createElement('td'); x.className = 'sm';
        c.ms.forEach((m) => {
          const d = document.createElement('span'); d.className = 'su-ml';
          d.appendChild(document.createTextNode(setupName(m.setup) + ' · ' + (rateOf(m.setup) == null ? 'too few cases' : fmtPct(rateOf(m.setup)) + ' of ' + stat(m.setup, 'All').n) + (m.complete ? '' : ' · one condition short') + ' '));
          if (isNewGroup(m.setup)) { const w = document.createElement('span'); w.className = 'chip am'; w.textContent = '⚠ new setup: see warning'; w.title = NEW_WARN; d.appendChild(w); }
          x.appendChild(d);
        });
        return x; }, tip: 'A stock that matches several setups is shown once, with every setup it matches, ordered by historical success rate.' },
      { k: 'rate', label: 'Highest historical success rate', cls: 'sm', dir: -1, val: (c) => c.bestRate, cell: (c) => rateCell(c.setup), tip: 'Of the setups the stock matches, from the latest monthly study, all markets together.' },
      { k: 'why', label: 'Why it matches (best setup)', cls: 'why sec', val: (c) => c.why, cell: (c) => { const t = c.complete ? c.why : 'Missing: ' + c.missing.join('; '); const x = td(t.length > 130 ? t.slice(0, 127) + '…' : t, 'why sec'); x.title = t; return x; } },
      { k: 'live', label: 'Live record (best setup)', cls: 'sm sec', val: (c) => { const l = live(c.setup); return l && l.rate; }, cell: (c) => liveTxt(c.setup) },
      { k: 'prev', label: 'This stock’s own last matching setup (best setup)', cls: 'sm sec', val: (c) => (c.last_prev ? c.last_prev.date : null), cell: (c) => (!c.last_prev ? 'none in the data' : dTxt(c.last_prev.date) + ' at ' + pxTxt(c.last_prev.price) + ' · ' + (c.last_prev.outcome === 'hit' ? 'reached +20%' : c.last_prev.outcome === 'missed' ? 'missed' : 'outcome pending')) },
      { k: 'px', label: 'Price now', cls: 'num sec', val: (c) => px(c), cell: (c) => pxTxt(px(c), c.cur) },
      { k: 'brk', label: 'Breakout level (distance)', cls: 'sm sec', val: (c) => c.breakout, cell: (c) => distTxt(c.breakout, c), tip: 'Levels in the table are those of the setup with the highest historical success rate. Click the row for each matching setup’s own levels.' },
      { k: 'sup', label: 'Support', cls: 'num sec', val: (c) => c.support, cell: (c) => pxTxt(c.support) },
      { k: 'res', label: 'Resistance', cls: 'num sec', val: (c) => c.resistance, cell: (c) => (c.resistance == null ? 'none overhead' : pxTxt(c.resistance)) },
      { k: 'inv', label: 'Invalidation level (distance)', cls: 'sm', val: (c) => c.invalid, cell: (c) => distTxt(c.invalid, c), tip: 'The price at which the setup no longer holds. If the price trades below it the row is flagged at once and the name is removed at the next daily rebuild.' },
      { k: 'earn', label: 'Next earnings', cls: 'sec', val: (c) => c.earnings_next, cell: (c) => (c.earnings_next ? dTxt(c.earnings_next) : '—') },
      { k: 'st', label: 'Status', val: (c) => (c._below.length ? 0 : c._new ? 1 : 2), cell: (c) => (c._below.length ? chipTd('Below invalidation', 'e2', 'The price is under the invalidation level of: ' + c._below.map(setupName).join('; ') + '. The name stays until the next daily rebuild.') : c._new ? chipTd('New', 'b2', 'Added in the latest rebuild') : !c._comp ? chipTd('One condition short', 'am') : chipTd('Listed since ' + dTxt(c._since), 'n')) },
    ], candRows, (c) => {
      const w = document.createElement('div');
      w.append(para(c.name + ' · ' + c.market + ' · ' + c.size + ' cap (rank ' + c.rank + ') · close ' + pxTxt(c.close, c.cur) + ' on ' + dTxt(c.bar_date) + ' · matches ' + c.ms.length + (c.ms.length === 1 ? ' setup' : ' setups') + ', best historical success rate first.'));
      c.ms.forEach((m) => {
        const h = document.createElement('p'); h.className = 'hs-note'; h.style.cssText = 'margin:10px 0 4px;color:var(--color-fg)'; h.textContent = setupName(m.setup) + ' · historical success rate ' + (rateOf(m.setup) == null ? 'too few cases' : fmtPct(rateOf(m.setup)) + ' of ' + stat(m.setup, 'All').n) + ' · first listed ' + dTxt(m.first_seen) + ' at ' + pxTxt(m.entry_close, m.cur) + ' · live record ' + liveTxt(m.setup);
        w.append(h, checklist(m.conds.map((x) => ({ t: x.t, ok: x.ok, v: x.v }))), para(LEVEL_TXT[m.setup]), para('Levels now: breakout ' + (m.breakout == null ? '—' : pxTxt(m.breakout, m.cur)) + ' · support ' + pxTxt(m.support, m.cur) + ' · resistance ' + (m.resistance == null ? 'none overhead' : pxTxt(m.resistance, m.cur)) + ' · invalidation ' + pxTxt(m.invalid, m.cur) + (m.invalid != null && px(m) < m.invalid ? ' (price is below it)' : '')));
        if (isNewGroup(m.setup)) { const wn = para('⚠ ' + NEW_WARN); wn.classList.add('su-warn-box'); w.appendChild(wn); }
      });
      if (c.earnings_next) w.appendChild(para('Next earnings report: ' + dTxt(c.earnings_next) + ' (from TradingView).'));
      return w;
    }, (c) => c._k, () => (SU.cur ? 'No candidates match.' : 'Loading…'));

"""
s = s[:a] + newC + s[b:]

# ---------------------------------------------------------------- notes
rep("""        $('su-a-note').textContent = 'Every rule was run""", """        $('su-a-warn').textContent = '⚠ ' + NEW_WARN;
        $('su-c-warn').textContent = '⚠ Setups a) to g) (marked “new setup”): ' + NEW_WARN;
        $('su-a-note').textContent = 'Every rule was run""")
rep("""A success rate is shown only from 30 cases; otherwise "too few cases". Last study run '""", """A success rate is shown only from 30 cases; otherwise "too few cases". The five original setups come first; the seven newer ones (a to g) follow under their own heading. Edge = success rate minus the base rate at the same volatility, in percentage points. Different weeks with a case = calendar weeks with at least one case. Busiest month’s share = the share of the setup’s cases that fall in its single busiest calendar month (amber above 15%): a high share means the result rests on one episode. Click a row for its cases and success rate by year and its three busiest months. Last study run '""")
rep("""        li('Counting: one case per stock and setup every 42 trading days, so one move is not counted several times. Different setups can fire on the same stock and day.');""", """        li('Counting: one case per stock and setup every 42 trading days, so one move is not counted several times. Different setups can fire on the same stock and day.');
        li('Definitions used by the seven newer setups: Market washout = on that day, fewer than 20% of that market’s stocks (those with a 50-day average) close above their own 50-day average, computed per market and per day from the same stock list; with fewer than 10 of the market’s stocks having data that day the washout setups cannot fire. Quiet volume = the average volume of the previous 10 sessions is below 0.8 times the 50-day average volume. Daily range = the 14-day average true range as a share of the price (the measure the older rules use).');
        li('How the seven newer setups were chosen: they came out of a one-off exploration of many rule combinations on this same five-year data, picked because their success rates were high. That makes their historical success rates a best-of-many result, and the “since Jul 2024” column is not an independent check for them. The five original setups were not changed.');""")
rep("""Names added in the latest rebuild are marked New.' + cl""", """Names added in the latest rebuild are marked New. A stock that matches more than one setup is shown once, with every setup it matches, sorted by the highest historical success rate among them; each setup match is logged separately, so every setup keeps its own live record.' + cl""")
open(PATH, "w", encoding="utf-8").write(s)
print("ok")
