#!/usr/bin/env python3
"""The "<month> signal" mix card gets its own month dropdown too: this month = today's signal mix; a later month = the share of
portfolio value (and number of holdings) that leans up / even / leans down in that month's price-range outlook."""
PATH = "index.html"
s = open(PATH, encoding="utf-8").read()
assert "f-month-card" not in s, "already patched"


def rep(old, new, cnt=1):
    global s
    n = s.count(old)
    assert n == cnt, f"expected {cnt}, found {n}: {old[:90]!r}"
    s = s.replace(old, new)


# card markup
rep('''      <h2><span class="mo">October</span> signal</h2>
      <p class="hs-note">Share of portfolio value in each group, with the number of holdings.</p>
''', '''      <h2><span class="mo">October</span><span class="mox2" hidden></span> <span id="mix-oct-t">signal</span></h2>
      <p class="hs-note" id="mix-oct-note">Share of portfolio value in each group, with the number of holdings.</p>
      <div class="ctl"><select id="f-month-card" aria-label="Month shown in this card"><option value="">This month</option></select></div>
''')

# outlook lookup takes the month as a parameter
rep("  function outlookOf(sym) {\n    const d = dash.data('monthly');\n    if (d.status !== 'ok' || !MV.m) return null;",
    "  function outlookOf(sym, mth) {\n    if (mth === undefined) mth = MV.m;\n    const d = dash.data('monthly');\n    if (d.status !== 'ok' || !mth) return null;")
rep("    const r = monthIdx.get(sym + '|' + MV.m);", "    const r = monthIdx.get(sym + '|' + mth);")

# card state, options, drawing
rep("  fMonth.addEventListener('change', () => { MV.m = fMonth.value; state.oct = ''; syncMonthView(); drawTable(); });\n",
"""  fMonth.addEventListener('change', () => { MV.m = fMonth.value; state.oct = ''; syncMonthView(); drawTable(); });
  // ---- the signal-mix card has its own month dropdown ----
  const fMonthC = document.getElementById('f-month-card');
  const MC = { m: '' };
  fMonthC.addEventListener('change', () => { MC.m = fMonthC.value; drawOctMix(); });
  const OUT_CLS = { 'Leans up': 'b1', Even: 'n', 'Leans down': 'e1' };
  function syncMixMonth() {
    const later = laterMonths(), c = nowYM();
    fMonthC.options[0].textContent = MONTH_NAMES[c.m] + ' · signal';
    if (Array.from(fMonthC.options).slice(1).map((o) => o.value).join() !== later.join()) {
      while (fMonthC.options.length > 1) fMonthC.remove(1);
      later.forEach((k) => { const o = document.createElement('option'); o.value = k; o.textContent = monthName(k) + ' · outlook'; fMonthC.appendChild(o); });
    }
    if (MC.m && !later.includes(MC.m)) MC.m = '';
    fMonthC.value = MC.m;
    const mo = document.querySelector('#mix-oct .mo'), x = document.querySelector('#mix-oct .mox2');
    if (mo) mo.hidden = !!MC.m;
    if (x) { x.hidden = !MC.m; x.textContent = MC.m ? monthName(MC.m) : ''; }
    const t = document.getElementById('mix-oct-t'); if (t) t.textContent = MC.m ? 'outlook' : 'signal';
    const n = document.getElementById('mix-oct-note');
    if (n) n.textContent = MC.m
      ? 'Share of portfolio value that leans up, stays even or leans down in ' + monthName(MC.m) + ', with the number of holdings. This is the price-range outlook from the month-by-month model (an assumed yearly drift), not a technical signal, and it tells less the further out the month.'
      : 'Share of portfolio value in each group, with the number of holdings.';
  }
  function drawOctMix() {
    syncMixMonth();
    const bar = document.getElementById('bar-oct'), leg = document.getElementById('leg-oct');
    const hd = dash.data('holdings');
    if (!MC.m || hd.status !== 'ok') { drawMix('oct_counts', OCT, bar, leg); return; }
    const rows = hd.data, total = rows.reduce((a, r) => a + Number(r.value_sek), 0);
    const outs = rows.map((r) => ({ r, o: outlookOf(r.sym, MC.m) }));
    const out = OUT_LABELS.map((label) => {
      const g = outs.filter((x) => x.o && x.o.label === label), sek = g.reduce((a, x) => a + Number(x.r.value_sek), 0);
      return { label, n: g.length, share: total ? sek / total : 0, cls: OUT_CLS[label] };
    });
    drawMix('oct_counts', OUT_LABELS, bar, leg, out);
  }
""")
# drawMix changes, confined to that function (the crypto section has a near-identical block)
a = s.index("  function drawMix(id, labels, barEl, legEl) {")
b = s.index("  // ---------- money flow by sector ----------")
body = s[a:b]


def brep(old, new):
    global body
    assert body.count(old) == 1, old[:80]
    body = body.replace(old, new)


brep("  function drawMix(id, labels, barEl, legEl) {\n    const d = dash.data(id);",
     "  function drawMix(id, labels, barEl, legEl, custom) {\n    const d = custom ? { status: 'ok', data: custom } : dash.data(id);")
brep("    const hereLabel = selR ? selR.oct_signal : null;\n",
     "    const so = custom && selR ? outlookOf(selR.sym, MC.m) : null;\n    const hereLabel = custom ? (so ? so.label : null) : (selR ? selR.oct_signal : null);\n")
brep("      seg.className = 'c-' + CLS[i] + (row.label === hereLabel ? ' here' : '');", "      seg.className = 'c-' + (row.cls || CLS[i]) + (row.label === hereLabel ? ' here' : '');")
brep("      sw.className = 'sw c-' + CLS[i];", "      sw.className = 'sw c-' + (row.cls || CLS[i]);")
brep("      num.dataset.source = id; num.dataset.field = 'share'; num.dataset.where = 'label=' + enc(row.label);",
     "      if (!custom) { num.dataset.source = id; num.dataset.field = 'share'; num.dataset.where = 'label=' + enc(row.label); }")
brep("      n.dataset.source = id; n.dataset.field = 'n'; n.dataset.where = 'label=' + enc(row.label);",
     "      if (!custom) { n.dataset.source = id; n.dataset.field = 'n'; n.dataset.where = 'label=' + enc(row.label); }")
s = s[:a] + body + s[b:]
rep("drawMix('oct_counts', OCT, document.getElementById('bar-oct'), document.getElementById('leg-oct'));", "drawOctMix();", 2)
open(PATH, "w", encoding="utf-8").write(s)
print("ok")
