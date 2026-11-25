#!/usr/bin/env python3
"""Every holding: a month dropdown beside the signal filter. The current month keeps today's technical signal; each of the next
12 months turns that column into the month's price-range outlook (Leans up / Even / Leans down, from the 'Possible price, month by
month' model). The filter beside it and the column sort follow the chosen month."""
PATH = "index.html"
s = open(PATH, encoding="utf-8").read()
assert "f-month" not in s, "already patched"


def rep(old, new, cnt=1):
    global s
    n = s.count(old)
    assert n == cnt, f"expected {cnt}, found {n}: {old[:90]!r}"
    s = s.replace(old, new)


# 1. controls + note
rep('''      <select id="f-oct" aria-label="Signal for the current month">''',
    '''      <select id="f-month" aria-label="Month shown in the signal column"><option value="">This month</option></select>
      <select id="f-oct" aria-label="Signal for the current month">''')
rep('''    <div class="ctl">
      <input id="q" type="search" placeholder="Search holdings" aria-label="Search holdings">''',
    '''    <p class="hs-note" id="mo-note" hidden></p>
    <div class="ctl">
      <input id="q" type="search" placeholder="Search holdings" aria-label="Search holdings">''')

# 2. shared state, read before refreshMonth runs
rep("  let shownMonth = null;\n", "  let shownMonth = null;\n  const MV = { m: '' };   // month picked in Every holding ('' = this month's signal, else 'YYYY-MM' for that month's range outlook)\n")
rep("    const all = document.getElementById('f-oct-all'); if (all) all.textContent = 'All ' + name + ' signals';\n    const sel = document.getElementById('f-oct'); if (sel) sel.setAttribute('aria-label', name + ' signal');\n",
    "    const all = document.getElementById('f-oct-all'); if (all && !MV.m) all.textContent = 'All ' + name + ' signals';\n    const sel = document.getElementById('f-oct'); if (sel && !MV.m) sel.setAttribute('aria-label', name + ' signal');\n    if (typeof syncMonthView === 'function') syncMonthView();\n")

# 3. chip colours for the outlook labels
rep("  const chipCls = (label) => {\n    if (FLOWC[label]) return FLOWC[label];\n",
    "  const chipCls = (label) => {\n    if (label === 'Leans up') return 'b1';\n    if (label === 'Leans down') return 'e1';\n    if (FLOWC[label]) return FLOWC[label];\n")

# 4. month machinery next to the filters
rep("  fOct.addEventListener('change', () => { state.oct = fOct.value; drawTable(); });\n", """  fOct.addEventListener('change', () => { state.oct = fOct.value; drawTable(); });
  // ---- month dropdown: this month = today's signal, later months = that month's price-range outlook ----
  const fMonth = document.getElementById('f-month');
  const OUTLOOK = { High: 'Leans up', Low: 'Leans down', Even: 'Even' };
  const OUT_LABELS = ['Leans up', 'Even', 'Leans down'];
  let monthIdx = null, monthKey = '';
  const ymKey = (y, m) => y + '-' + String(m + 1).padStart(2, '0');
  const monthName = (k) => MONTH_NAMES[+k.slice(5, 7) - 1] + ' ' + k.slice(0, 4);
  function laterMonths() {
    const d = dash.data('monthly');
    if (d.status !== 'ok') return [];
    const c = nowYM(), cur = ymKey(c.y, c.m);
    return Array.from(new Set(d.data.map((r) => r.month))).filter((k) => k > cur).sort().slice(0, 12);
  }
  function outlookOf(sym) {
    const d = dash.data('monthly');
    if (d.status !== 'ok' || !MV.m) return null;
    if (monthKey !== d.data.length + '|' + d.data[0].date) { monthIdx = null; }
    if (!monthIdx) { monthIdx = new Map(d.data.map((r) => [r.sym + '|' + r.month, r])); monthKey = d.data.length + '|' + d.data[0].date; }
    const r = monthIdx.get(sym + '|' + MV.m);
    if (!r) return null;
    return { label: OUTLOOK[r.leans] || 'Even', score: (r.chance_high - r.chance_low) * 100, row: r };
  }
  const octVal = (r) => (MV.m ? (r._mo ? r._mo.label : null) : r.oct_signal);
  const octOk = (r) => !state.oct || octVal(r) === state.oct;
  const sortVal = (r, k) => (MV.m && k === 'oct_score' ? (r._mo ? r._mo.score : null) : r[k]);
  function octTitle(r) {
    if (!MV.m) return '';
    const o = r._mo;
    if (!o) return monthName(MV.m) + ': no range outlook for this holding';
    const x = o.row, fm = (v) => plain(v, v < 10 ? 3 : 2);
    return monthName(MV.m) + ' outlook: ' + o.label.toLowerCase() + '. Likely range ' + fm(x.likely_low) + ' to ' + fm(x.likely_high) + ' ' + x.cur + ' (half of outcomes), most likely ' + fm(x.most_likely) + '. Chance of finishing above the range ' + Math.round(x.chance_high * 100) + '%, below it ' + Math.round(x.chance_low * 100) + '%.';
  }
  function syncMonthView() {
    const later = laterMonths(), have = Array.from(fMonth.options).slice(1).map((o) => o.value).join();
    const c = nowYM();
    fMonth.options[0].textContent = MONTH_NAMES[c.m] + ' · signal';
    if (have !== later.join()) {
      while (fMonth.options.length > 1) fMonth.remove(1);
      later.forEach((k) => { const o = document.createElement('option'); o.value = k; o.textContent = monthName(k) + ' · outlook'; fMonth.appendChild(o); });
    }
    if (MV.m && !later.includes(MV.m)) { MV.m = ''; state.oct = ''; fOct.value = ''; }
    fMonth.value = MV.m;
    // filter choices follow the view
    const want = MV.m ? OUT_LABELS : OCT;
    const cur = Array.from(fOct.options).slice(1).map((o) => o.value).join();
    const allOpt = document.getElementById('f-oct-all');
    if (cur !== want.join()) {
      while (fOct.options.length > 1) fOct.remove(1);
      want.forEach((l) => { const o = document.createElement('option'); o.textContent = l; fOct.appendChild(o); });
      fOct.value = state.oct;
    }
    allOpt.textContent = MV.m ? 'All ' + monthName(MV.m) + ' outlooks' : 'All ' + MONTH_NAMES[c.m] + ' signals';
    fOct.setAttribute('aria-label', MV.m ? monthName(MV.m) + ' outlook' : MONTH_NAMES[c.m] + ' signal');
    // column header
    const btn = document.querySelector('#tbl th[data-field="oct_signal"] button');
    if (btn) {
      let x = btn.querySelector('.mox');
      if (!x) { x = document.createElement('span'); x.className = 'mox'; btn.appendChild(x); }
      const mo = btn.querySelector('.mo');
      if (mo) mo.hidden = !!MV.m;
      x.hidden = !MV.m;
      x.textContent = MV.m ? monthName(MV.m).slice(0, 3) + ' ' + MV.m.slice(0, 4) + ' outlook' : '';
    }
    const note = document.getElementById('mo-note');
    if (note) {
      note.hidden = !MV.m;
      note.textContent = MV.m ? 'The column now shows each holding\\'s price-range outlook for ' + monthName(MV.m) + ', not a technical signal: leans up, even or leans down, from the model under Possible price, month by month (an assumed yearly drift with the stock\\'s own swings around it). The further out the month, the less it tells you. Hover a chip for the likely range. The filter and the sort follow this month. Pick ' + MONTH_NAMES[c.m] + ' to go back to today\\'s signal.' : '';
    }
  }
  fMonth.addEventListener('change', () => { MV.m = fMonth.value; state.oct = ''; syncMonthView(); drawTable(); });
""")

# 5. filter, cell, sort
rep("      (!state.oct || r.oct_signal === state.oct) &&\n", "      octOk(r) &&\n", 2)
rep("    all.forEach((r) => { r._sig = signalOf(r);", "    syncMonthView();\n    all.forEach((r) => { r._mo = outlookOf(r.sym); });\n    all.forEach((r) => { r._sig = signalOf(r);", )
rep("      const x = a[k], y = b[k];\n      if (x == null && y == null) return 0;\n      if (x == null) return 1;\n      if (y == null) return -1;\n      if (typeof x === 'number' && typeof y === 'number') return (x - y) * dir;\n      return String(x).localeCompare(String(y)) * dir;\n    });\n    document.querySelectorAll('#tbl th')",
    "      const x = sortVal(a, k), y = sortVal(b, k);\n      if (x == null && y == null) return 0;\n      if (x == null) return 1;\n      if (y == null) return -1;\n      if (typeof x === 'number' && typeof y === 'number') return (x - y) * dir;\n      return String(x).localeCompare(String(y)) * dir;\n    });\n    document.querySelectorAll('#tbl th')")
rep("        chip(r.oct_signal),\n        chip(r.o1y),\n        chip(r.o3y, 'sec'),\n        chip(r.o5y),\n        chip(r.december),\n        td(signed(r.rev_g, 0), 'num sec ' + tone(r.rev_g)),\n        td(r.margin == null ? '—' : r.margin.toFixed(0) + '%', 'num sec ' + tone(r.margin)),\n        td(r.pe == null ? '—' : r.pe.toFixed(0), 'num sec'),\n        td(r.analysts || '—', 'sec'),\n      );",
    "        octCell(r, chip),\n        chip(r.o1y),\n        chip(r.o3y, 'sec'),\n        chip(r.o5y),\n        chip(r.december),\n        td(signed(r.rev_g, 0), 'num sec ' + tone(r.rev_g)),\n        td(r.margin == null ? '—' : r.margin.toFixed(0) + '%', 'num sec ' + tone(r.margin)),\n        td(r.pe == null ? '—' : r.pe.toFixed(0), 'num sec'),\n        td(r.analysts || '—', 'sec'),\n      );")
rep("  function rowsAll() {\n", """  function octCell(r, chip) {
    const c = chip(octVal(r) || '—');
    if (MV.m) c.title = octTitle(r);
    return c;
  }

  function rowsAll() {
""")

# 6. methods text
rep("<p><b><span class=\"mo\">October</span> signal.</b> ", "<p><b><span class=\"mo\">October</span> signal.</b> In Every holding a month dropdown swaps this column to a later month's price-range outlook (see Possible price, month by month) instead. ")
open(PATH, "w", encoding="utf-8").write(s)
print("ok")
