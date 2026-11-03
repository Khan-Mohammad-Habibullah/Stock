#!/usr/bin/env python3
"""My holdings tab: "Portfolio breakdown" -- a pie chart of the holdings that you can switch between
sector, industry group, industry (GICS names), country, region, exchange, currency, stock/ETF, company size,
position size, each holding, and the board's own signals. Every slice shows its share in % and its value in SEK.

The chart reads the holdings dataset (fields gics_sector, gics_group, gics_industry, country, region,
size_class, asset_type written by scripts/update_board.py via scripts/classify.py), so every rebuild -- the
daily one and the one after a holdings update -- redraws it, and the live price refresh moves the amounts.

Exact-text replace with count asserts, as in the other scripts/patch_*.py."""

PATH = "index.html"
s = open(PATH, encoding="utf-8").read()


def rep(old, new, cnt=1):
    global s
    n = s.count(old)
    assert n == cnt, f"expected {cnt}, found {n}: {old[:90]!r}"
    s = s.replace(old, new)


assert 'id="breakdown"' not in s, "already patched"

CSS = """
  :root { --pie-0:#3b6fb6; --pie-1:#d17a2e; --pie-2:#2f7d4f; --pie-3:#8a5bb5; --pie-4:#b6382c; --pie-5:#2b9aa6; --pie-6:#a8741a; --pie-7:#c2528b; --pie-8:#7a8f2e; --pie-9:#4a4a8a; --pie-10:#8a6a4a; --pie-other:#9a978c; }
  @media (prefers-color-scheme: dark) { :root { --pie-0:#6fa0e0; --pie-1:#e6a15e; --pie-2:#5cc189; --pie-3:#b894dc; --pie-4:#ee7d6f; --pie-5:#5cc3cf; --pie-6:#d9a441; --pie-7:#e58bb8; --pie-8:#a7bf5a; --pie-9:#8d8fe0; --pie-10:#c49a72; --pie-other:#6f6d65; } }
  .bd-wrap { display: grid; grid-template-columns: minmax(0, 340px) minmax(0, 1fr); gap: var(--cds-gap-xl); align-items: start; }
  @media (max-width: 760px) { .bd-wrap { grid-template-columns: minmax(0, 1fr); gap: var(--cds-gap-md); } }
  .bd-pie { display: grid; gap: var(--cds-gap-sm); justify-items: center; }
  .bd-pie svg { width: 100%; max-width: 340px; height: auto; display: block; }
  .bd-pie path { stroke: var(--color-panel); stroke-width: 2; cursor: pointer; transition: opacity .15s; }
  .bd-pie.hov path { opacity: .35; }
  .bd-pie.hov path.on { opacity: 1; }
  .bd-pie text { font-size: 13px; font-weight: 600; pointer-events: none; font-variant-numeric: tabular-nums; }
  .bd-cap { margin: 0; min-height: 2.9em; text-align: center; font-size: var(--cds-font-size-caption); color: var(--color-fg-muted); font-variant-numeric: tabular-nums; }
  .bd-cap b { color: var(--color-fg); font-weight: 600; display: block; font-size: var(--cds-font-size-body); }
  table.bd { border-collapse: collapse; width: 100%; font-size: var(--cds-font-size-caption); font-variant-numeric: tabular-nums; }
  table.bd th { text-align: left; font-weight: var(--cds-font-weight-medium); color: var(--color-fg-muted); padding: 4px 8px; border-bottom: 1px solid var(--color-border-line); }
  table.bd th.num, table.bd td.num { text-align: right; }
  table.bd td { padding: 6px 8px; border-bottom: 1px solid var(--color-border-line); vertical-align: middle; }
  table.bd tr.bd-row { cursor: pointer; }
  table.bd tr.bd-row.on td { background: color-mix(in srgb, var(--color-fg) 7%, transparent); }
  table.bd .sw { display: inline-block; width: 11px; height: 11px; border-radius: 3px; margin-right: 8px; vertical-align: -1px; }
  table.bd button { font: inherit; background: none; border: 0; padding: 0; color: var(--color-fg); cursor: pointer; text-align: left; }
  table.bd button::before { content: "\\25B8"; display: inline-block; width: 1em; color: var(--color-fg-muted); }
  table.bd tr.bd-row[aria-expanded="true"] button::before { content: "\\25BE"; }
  table.bd tr.bd-sub td { padding: 2px 8px 8px 28px; background: color-mix(in srgb, var(--color-fg) 3%, transparent); }
  table.bd tr.bd-sub ul { margin: 0; padding: 0; list-style: none; display: grid; gap: 2px; }
  table.bd tr.bd-sub li { display: flex; justify-content: space-between; gap: 12px; color: var(--color-fg-muted); }
  table.bd tr.bd-sub li span:first-child { color: var(--color-fg); min-width: 0; overflow-wrap: anywhere; }
  table.bd tfoot td { font-weight: 600; border-bottom: 0; }
  .ctl .dim { opacity: .45; }
"""

HTML = """  <section class="hs-card" id="breakdown">
    <h2>Portfolio breakdown</h2>
    <p class="hs-note">What the portfolio is made of, as a share of its total value. Pick how to slice it; each slice shows its share and its value in SEK. Click a slice or a row to see the holdings inside it. It redraws with every update of your holdings and with the live prices.</p>
    <div class="ctl">
      <label class="lbl" for="bd-cat">Break down by</label>
      <select id="bd-cat" aria-label="Break the portfolio down by"></select>
      <select id="bd-funds" aria-label="How to count ETFs">
        <option value="theme">ETFs counted by what they hold</option>
        <option value="own">ETFs as their own slice</option>
      </select>
      <span class="count" id="bd-count"></span>
    </div>
    <div class="bd-wrap">
      <div class="bd-pie" id="bd-pie" role="img" aria-label="Pie chart of the portfolio; the table beside it lists every slice"></div>
      <div class="tbl-wrap" style="max-height:none;border:0">
        <table class="bd" id="bd-tbl"><thead><tr><th>Slice</th><th class="num">Share</th><th class="num">Value, SEK</th><th class="num">Holdings</th></tr></thead><tbody id="bd-body"></tbody><tfoot id="bd-foot"></tfoot></table>
      </div>
    </div>
    <p class="hs-note" id="bd-note">Sector, industry group and industry use the standard GICS names; they are TradingView's industry labels translated to GICS, with a short list of well-known companies set by hand where the two differ, so a few companies may sit one industry off. Country is where the company is based or incorporated (Medtronic and Eaton are Irish-domiciled). Funds are placed by the theme they track. Amounts are the latest price times your quantity.</p>
  </section>

"""

JS = r"""  // ---------- portfolio breakdown: pie by sector, industry, country, ... ----------
  (function () {
    const sel = document.getElementById('bd-cat'), fsel = document.getElementById('bd-funds'), box = document.getElementById('bd-pie');
    const body = document.getElementById('bd-body'), foot = document.getElementById('bd-foot'), cnt = document.getElementById('bd-count');
    if (!sel || !box || !body) return;
    const EXCH = { NASDAQ: 'Nasdaq (US)', NYSE: 'NYSE (US)', AMEX: 'NYSE American (US)', OMXSTO: 'Nasdaq Stockholm', OSL: 'Oslo Bors', OMXCOP: 'Nasdaq Copenhagen',
      OMXHEX: 'Nasdaq Helsinki', XETR: 'Xetra (Germany)', TSX: 'Toronto (TSX)' };
    const share = (r, t) => (+r.value_sek || 0) / t * 100;
    const CATS = [
      { id: 'sector', grp: 'Standard classification', label: 'Sector (GICS)', get: (r) => r.gics_sector, fund: true },
      { id: 'group', grp: 'Standard classification', label: 'Industry group (GICS)', get: (r) => r.gics_group, fund: true },
      { id: 'industry', grp: 'Standard classification', label: 'Industry (GICS)', get: (r) => r.gics_industry, fund: true },
      { id: 'country', grp: 'Standard classification', label: 'Country (where the company is based)', get: (r) => r.country, fund: true },
      { id: 'region', grp: 'Standard classification', label: 'Region', get: (r) => r.region, fund: true },
      { id: 'size', grp: 'Standard classification', label: 'Company size (market cap)', get: (r) => r.size_class, fund: true },
      { id: 'asset', grp: 'How it is held', label: 'Stock or ETF', get: (r) => r.asset_type },
      { id: 'exch', grp: 'How it is held', label: 'Exchange', get: (r) => EXCH[(r.sym || '').split(':')[0]] || (r.sym || '').split(':')[0] },
      { id: 'cur', grp: 'How it is held', label: 'Currency', get: (r) => r.cur },
      { id: 'pos', grp: 'How it is held', label: 'Position size', get: (r, t) => { const w = share(r, t); return w >= 5 ? '5% or more of the portfolio' : w >= 2 ? '2% to 5%' : w >= 1 ? '1% to 2%' : 'Under 1%'; } },
      { id: 'holding', grp: 'How it is held', label: 'Each holding', get: (r) => r.name },
      { id: 'oct', grp: 'From this board', label: 'Signal for the current month', get: (r) => r.oct_signal },
      { id: 'o1y', grp: 'From this board', label: '1-year outlook', get: (r) => r.o1y },
      { id: 'dec', grp: 'From this board', label: 'December view', get: (r) => r.december },
    ];
    let lastGrp = null, og = null;
    CATS.forEach((c) => {
      if (c.grp !== lastGrp) { og = document.createElement('optgroup'); og.label = c.grp; sel.appendChild(og); lastGrp = c.grp; }
      const o = document.createElement('option'); o.value = c.id; o.textContent = c.label; og.appendChild(o);
    });
    const store = {
      get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
      set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* private window */ } },
    };
    const savedCat = store.get('bd-cat'), savedFunds = store.get('bd-funds');
    if (savedCat && CATS.some((c) => c.id === savedCat)) sel.value = savedCat;
    if (savedFunds === 'own' || savedFunds === 'theme') fsel.value = savedFunds;

    const MAXN = 11;           // show up to this many slices; beyond it the smallest are joined as "Other"
    const open = new Set();    // expanded rows, by slice name
    let groups = [], total = 0, active = -1, sig = '';
    const fmtP = (v) => v.toFixed(1) + '%';
    const lum = (hex) => { const m = /^#?([0-9a-f]{6})$/i.exec((hex || '').trim()); if (!m) return 0; const n = parseInt(m[1], 16); return (0.299 * (n >> 16) + 0.587 * ((n >> 8) & 255) + 0.114 * (n & 255)) / 255; };

    function compute() {
      const rows = rowsAll();
      const cat = CATS.find((c) => c.id === sel.value) || CATS[0];
      const own = fsel.value === 'own' && cat.fund;
      const t = d3.sum(rows, (r) => Math.max(0, +r.value_sek || 0));
      const m = new Map();
      rows.forEach((r) => {
        const v = +r.value_sek || 0;
        if (!(v > 0)) return;
        let k = own && r.asset_type === 'ETF' ? 'Funds (ETFs)' : cat.get(r, t);
        k = k == null || k === '' ? 'Not classified' : String(k);
        const g = m.get(k) || { name: k, sek: 0, rows: [] };
        g.sek += v; g.rows.push(r); m.set(k, g);
      });
      let list = [...m.values()].sort((a, b) => b.sek - a.sek);
      if (list.length > MAXN) {
        const head = list.slice(0, MAXN - 1), rest = list.slice(MAXN - 1);
        head.push({ name: 'Other (' + rest.length + ' more)', sek: d3.sum(rest, (g) => g.sek), rows: [].concat(...rest.map((g) => g.rows)), members: rest, other: true });
        list = head;
      }
      list.forEach((g, i) => { g.color = g.other ? 'var(--pie-other)' : 'var(--pie-' + i + ')'; g.pct = t ? g.sek / t * 100 : 0; });
      return { list, t, cat, own, n: rows.length };
    }

    function caption(i) {
      const cap = box.querySelector('.bd-cap');
      if (!cap) return;
      cap.textContent = '';
      const b = document.createElement('b');
      if (i < 0 || !groups[i]) {
        b.textContent = fmtInt(Math.round(total)) + ' SEK';
        cap.append(b, document.createTextNode('whole portfolio, ' + d3.sum(groups, (g) => g.rows.length) + ' holdings'));
      } else {
        const g = groups[i];
        b.textContent = g.name;
        cap.append(b, document.createTextNode(fmtP(g.pct) + ' · ' + fmtInt(Math.round(g.sek)) + ' SEK · ' + g.rows.length + (g.rows.length === 1 ? ' holding' : ' holdings')));
      }
    }

    function setActive(i) {
      active = i;
      box.classList.toggle('hov', i >= 0);
      box.querySelectorAll('path').forEach((p, k) => p.classList.toggle('on', k === i));
      body.querySelectorAll('tr.bd-row').forEach((tr) => tr.classList.toggle('on', +tr.dataset.i === i));
      caption(i);
    }

    function toggle(i) {
      const g = groups[i]; if (!g) return;
      if (open.has(g.name)) open.delete(g.name); else open.add(g.name);
      drawTable();
      setActive(i);
    }

    function drawPie() {
      box.textContent = '';
      const W = 320, R = 150;
      const svg = d3.select(box).append('svg').attr('viewBox', '0 0 ' + W + ' ' + W);
      const gg = svg.append('g').attr('transform', 'translate(' + W / 2 + ',' + W / 2 + ')');
      const arcs = d3.pie().sort(null).value((g) => g.sek)(groups);
      const arc = d3.arc().innerRadius(0).outerRadius(R), lab = d3.arc().innerRadius(R * 0.64).outerRadius(R * 0.64);
      const cs = getComputedStyle(box);
      gg.selectAll('path').data(arcs).join('path').attr('d', arc).attr('fill', (a) => a.data.color)
        .on('mouseenter', (e, a) => setActive(a.index)).on('mouseleave', () => setActive(-1)).on('click', (e, a) => toggle(a.index))
        .append('title').text((a) => a.data.name + ': ' + fmtP(a.data.pct) + ', ' + fmtInt(Math.round(a.data.sek)) + ' SEK');
      gg.selectAll('text').data(arcs.filter((a) => a.data.pct >= 6)).join('text').attr('transform', (a) => 'translate(' + lab.centroid(a) + ')').attr('text-anchor', 'middle').attr('dy', '0.35em')
        .attr('fill', (a) => { const v = a.data.other ? cs.getPropertyValue('--pie-other') : cs.getPropertyValue('--pie-' + a.index); return lum(v) > 0.6 ? '#1f1e1d' : '#ffffff'; })
        .text((a) => Math.round(a.data.pct) + '%');
      const cap = document.createElement('p'); cap.className = 'bd-cap'; cap.setAttribute('aria-live', 'polite'); box.appendChild(cap);
      caption(-1);
    }

    function drawTable() {
      body.textContent = '';
      groups.forEach((g, i) => {
        const tr = document.createElement('tr'); tr.className = 'bd-row'; tr.dataset.i = i; tr.setAttribute('aria-expanded', open.has(g.name) ? 'true' : 'false');
        const td0 = document.createElement('td'), sw = document.createElement('span'), bt = document.createElement('button');
        sw.className = 'sw'; sw.style.background = g.color; bt.type = 'button';
        bt.append(sw, document.createTextNode(g.name));
        td0.appendChild(bt);
        const mkN = (txt) => { const td = document.createElement('td'); td.className = 'num'; td.textContent = txt; return td; };
        tr.append(td0, mkN(fmtP(g.pct)), mkN(fmtInt(Math.round(g.sek))), mkN(String(g.rows.length)));
        tr.addEventListener('mouseenter', () => setActive(i)); tr.addEventListener('mouseleave', () => setActive(-1));
        tr.addEventListener('click', () => toggle(i));
        body.appendChild(tr);
        if (open.has(g.name)) {
          const sub = document.createElement('tr'); sub.className = 'bd-sub';
          const td = document.createElement('td'); td.colSpan = 4;
          const ul = document.createElement('ul');
          const items = g.members ? g.members.map((m) => ({ name: m.name, sek: m.sek, n: m.rows.length })) : g.rows.slice().sort((a, b) => b.value_sek - a.value_sek).map((r) => ({ name: r.name, sek: r.value_sek }));
          items.forEach((it) => {
            const li = document.createElement('li'), a = document.createElement('span'), b = document.createElement('span');
            a.textContent = it.name + (it.n ? ' (' + it.n + (it.n === 1 ? ' holding)' : ' holdings)') : '');
            b.textContent = fmtP(it.sek / total * 100) + ' · ' + fmtInt(Math.round(it.sek)) + ' SEK';
            li.append(a, b); ul.appendChild(li);
          });
          td.appendChild(ul); sub.appendChild(td); body.appendChild(sub);
        }
      });
      foot.textContent = '';
      const tr = document.createElement('tr');
      const t0 = document.createElement('td'); t0.textContent = 'Total';
      const mkN = (txt) => { const td = document.createElement('td'); td.className = 'num'; td.textContent = txt; return td; };
      tr.append(t0, mkN('100%'), mkN(fmtInt(Math.round(total))), mkN(String(d3.sum(groups, (g) => g.rows.length))));
      foot.appendChild(tr);
    }

    function draw() {
      const c = compute();
      fsel.classList.toggle('dim', !c.cat.fund); fsel.disabled = !c.cat.fund;
      groups = c.list; total = c.t;
      if (!groups.length) { box.textContent = ''; body.textContent = ''; foot.textContent = ''; cnt.textContent = 'No holdings loaded'; return; }
      cnt.textContent = groups.length + (groups.length === 1 ? ' slice' : ' slices') + ' · ' + c.n + ' holdings';
      const key = c.cat.id + '|' + fsel.value + '|' + groups.map((g) => g.name + ':' + Math.round(g.sek)).join(',');
      if (key === sig && box.querySelector('svg')) return;  // nothing moved since the last draw
      sig = key;
      drawPie(); drawTable();
      if (active >= 0) setActive(Math.min(active, groups.length - 1));
    }
    sel.addEventListener('change', () => { store.set('bd-cat', sel.value); open.clear(); draw(); });
    fsel.addEventListener('change', () => { store.set('bd-funds', fsel.value); draw(); });
    dash.onData(draw);
  })();

"""

rep("</style>\n\n<div class=\"hs\">", CSS + "</style>\n\n<div class=\"hs\">")
rep('  <section class="hs-card" id="quadrant">', HTML + '  <section class="hs-card" id="quadrant">')
rep("  // ---------- strongest bullish readings by market (rules-based screen, live from TradingView) ----------",
    JS + "  // ---------- strongest bullish readings by market (rules-based screen, live from TradingView) ----------")

open(PATH, "w", encoding="utf-8").write(s)
print("patched", len(s))
