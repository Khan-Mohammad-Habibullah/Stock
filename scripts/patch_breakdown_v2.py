#!/usr/bin/env python3
"""Portfolio breakdown v2 (run after patch_breakdown.py):
  * slices are coloured by money flow -- red where money is leaving, green where it is coming in, grey in between --
    using the board's own scores (money flow in the sector for sector/industry slices, in the stocks themselves for
    every other slicing); a switch brings back plain category colours
  * the name of each slice is written inside the pie (horizontal in big slices, along the slice in narrow ones,
    outside with a leader line for the tiny ones; on a phone the tiny ones are left to the table)
  * the table gets a Money flow column so colour is never the only signal
Replaces the card's CSS, HTML and script wholesale between fixed markers."""

PATH = "index.html"
s = open(PATH, encoding="utf-8").read()
assert 'id="bd-col"' not in s, "already patched"


def between(a, b, new, incl_a=True):
    """Replace s[a:b] (a kept when incl_a is False)."""
    global s
    i, j = s.index(a), s.index(b)
    assert s.count(a) == 1 and s.count(b) == 1 and i < j
    s = s[:i + (0 if incl_a else len(a))] + new + s[j:]


CSS = """  :root { --pie-0:#3b6fb6; --pie-1:#d17a2e; --pie-2:#2f7d4f; --pie-3:#8a5bb5; --pie-4:#b6382c; --pie-5:#2b9aa6; --pie-6:#a8741a; --pie-7:#c2528b; --pie-8:#7a8f2e; --pie-9:#4a4a8a; --pie-10:#8a6a4a; --pie-other:#9a978c; }
  @media (prefers-color-scheme: dark) { :root { --pie-0:#6fa0e0; --pie-1:#e6a15e; --pie-2:#5cc189; --pie-3:#b894dc; --pie-4:#ee7d6f; --pie-5:#5cc3cf; --pie-6:#d9a441; --pie-7:#e58bb8; --pie-8:#a7bf5a; --pie-9:#8d8fe0; --pie-10:#c49a72; --pie-other:#6f6d65; } }
  .bd-wrap { display: grid; grid-template-columns: minmax(0, 680px) minmax(0, 1fr); gap: var(--cds-gap-xl); align-items: start; }
  @media (max-width: 1180px) { .bd-wrap { grid-template-columns: minmax(0, 1fr); gap: var(--cds-gap-md); } }
  .bd-pie { display: grid; gap: var(--cds-gap-sm); justify-items: center; }
  .bd-pie svg { width: 100%; max-width: 680px; height: auto; display: block; }
  .bd-pie path { stroke: var(--color-panel); stroke-width: 2; cursor: pointer; transition: opacity .15s; }
  .bd-pie.hov path, .bd-pie.hov .lbl { opacity: .35; }
  .bd-pie.hov path.on, .bd-pie.hov .lbl.on { opacity: 1; }
  .bd-pie .lbl { font-size: 12px; font-weight: 600; pointer-events: none; font-variant-numeric: tabular-nums; transition: opacity .15s; }
  .bd-pie .lbl.out { fill: var(--color-fg); font-weight: 500; }
  .bd-pie .lbl .p { font-weight: 400; }
  .bd-pie .lead { stroke: var(--color-fg-muted); stroke-width: 1; fill: none; pointer-events: none; }
  .bd-cap { margin: 0; min-height: 2.9em; text-align: center; font-size: var(--cds-font-size-caption); color: var(--color-fg-muted); font-variant-numeric: tabular-nums; }
  .bd-cap b { color: var(--color-fg); font-weight: 600; display: block; font-size: var(--cds-font-size-body); }
  .bd-key { display: flex; align-items: center; gap: 8px; font-size: var(--cds-font-size-caption); color: var(--color-fg-muted); flex-wrap: wrap; }
  .bd-key i { display: inline-block; width: 160px; height: 10px; border-radius: 5px; background: linear-gradient(90deg, var(--color-bad), var(--cds-chart-muted), var(--color-ok)); }
  .bd-key[hidden] { display: none; }
  table.bd { border-collapse: collapse; width: 100%; font-size: var(--cds-font-size-caption); font-variant-numeric: tabular-nums; }
  table.bd th { text-align: left; font-weight: var(--cds-font-weight-medium); color: var(--color-fg-muted); padding: 4px 8px; border-bottom: 1px solid var(--color-border-line); }
  table.bd th.num, table.bd td.num { text-align: right; }
  table.bd td { padding: 6px 8px; border-bottom: 1px solid var(--color-border-line); vertical-align: middle; }
  table.bd td.fl { min-width: 7.5rem; }
  @media (max-width: 600px) { table.bd th:nth-child(4), table.bd td:nth-child(4) { display: none; } table.bd td.fl { min-width: 0; } table.bd th, table.bd td { padding-left: 4px; padding-right: 4px; } }
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
    <p class="hs-note">What the portfolio is made of, as a share of its total value. Pick how to slice it; each slice shows its name, its share and its value in SEK. Slices are coloured by money flow: red where money is leaving, green where it is coming in. Click a slice or a row to see the holdings inside it. It redraws with every update of your holdings and with the live prices.</p>
    <div class="ctl">
      <label class="lbl" for="bd-cat">Break down by</label>
      <select id="bd-cat" aria-label="Break the portfolio down by"></select>
      <select id="bd-col" aria-label="What the colours show">
        <option value="flow">Colour by money flow</option>
        <option value="cat">Colour by category</option>
      </select>
      <select id="bd-funds" aria-label="How to count ETFs">
        <option value="theme">ETFs counted by what they hold</option>
        <option value="own">ETFs as their own slice</option>
      </select>
      <span class="count" id="bd-count"></span>
    </div>
    <div class="bd-key" id="bd-key"><span>Money leaving</span><i aria-hidden="true"></i><span>Money coming in</span><span id="bd-keynote"></span></div>
    <div class="bd-wrap">
      <div class="bd-pie" id="bd-pie" role="img" aria-label="Pie chart of the portfolio; the table beside it lists every slice"></div>
      <div class="tbl-wrap" style="max-height:none;border:0">
        <table class="bd" id="bd-tbl"><thead><tr><th>Slice</th><th class="num">Share</th><th class="num">Value, SEK</th><th class="num">Holdings</th><th>Money flow</th></tr></thead><tbody id="bd-body"></tbody><tfoot id="bd-foot"></tfoot></table>
      </div>
    </div>
    <p class="hs-note" id="bd-note">Money flow is the board's own reading (see "Where money is moving"): for sector, industry group and industry slices it is the money flow in that sector or industry in its home market, for every other slicing it is the money flow in the stocks themselves. A slice's score is the average of its holdings' scores (-7.5 to +7.5) weighted by value; +1.5 or more reads as money coming in, -1.5 or less as money leaving, and beyond 4.5 as strong. Holdings with no flow reading are left out of the average. Sector, industry group and industry use the standard GICS names; they are TradingView's industry labels translated to GICS, with a short list of well-known companies set by hand where the two differ, so a few companies may sit one industry off. Country is where the company is based or incorporated (Medtronic and Eaton are Irish-domiciled). Funds are placed by the theme they track. Amounts are the latest price times your quantity.</p>
  </section>

"""

JS = r"""  // ---------- portfolio breakdown: pie by sector, industry, country, ... coloured by money flow ----------
  (function () {
    const sel = document.getElementById('bd-cat'), fsel = document.getElementById('bd-funds'), csel = document.getElementById('bd-col'), box = document.getElementById('bd-pie');
    const body = document.getElementById('bd-body'), foot = document.getElementById('bd-foot'), cnt = document.getElementById('bd-count');
    const keyEl = document.getElementById('bd-key'), keyNote = document.getElementById('bd-keynote');
    if (!sel || !box || !body) return;
    const EXCH = { NASDAQ: 'Nasdaq (US)', NYSE: 'NYSE (US)', AMEX: 'NYSE American (US)', OMXSTO: 'Nasdaq Stockholm', OSL: 'Oslo Bors', OMXCOP: 'Nasdaq Copenhagen',
      OMXHEX: 'Nasdaq Helsinki', XETR: 'Xetra (Germany)', TSX: 'Toronto (TSX)' };
    const share = (r, t) => (+r.value_sek || 0) / t * 100;
    const CATS = [
      { id: 'sector', grp: 'Standard classification', label: 'Sector (GICS)', get: (r) => r.gics_sector, fund: true, sectorFlow: true },
      { id: 'group', grp: 'Standard classification', label: 'Industry group (GICS)', get: (r) => r.gics_group, fund: true, sectorFlow: true },
      { id: 'industry', grp: 'Standard classification', label: 'Industry (GICS)', get: (r) => r.gics_industry, fund: true, sectorFlow: true },
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
    const sc = store.get('bd-cat'), sf = store.get('bd-funds'), sk = store.get('bd-col');
    if (sc && CATS.some((c) => c.id === sc)) sel.value = sc;
    if (sf === 'own' || sf === 'theme') fsel.value = sf;
    if (sk === 'flow' || sk === 'cat') csel.value = sk;

    const MAXN = 11;           // show up to this many slices; beyond it the smallest are joined as "Other"
    const LIM = 6;             // a score of +-6 or more gets the full red / green
    const open = new Set();
    let groups = [], total = 0, active = -1, sig = '';
    const fmtP = (v) => v.toFixed(1) + '%';
    const sgn = (v) => (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(1);
    const flowWord = (v) => (v == null ? 'No reading' : v >= 4.5 ? 'Strong inflow' : v >= 1.5 ? 'Money coming in' : v <= -4.5 ? 'Strong outflow' : v <= -1.5 ? 'Money leaving' : 'No clear direction');
    const cssv = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
    const dark = (c) => { const k = d3.color(c); if (!k) return true; const r = k.rgb(); return (0.299 * r.r + 0.587 * r.g + 0.114 * r.b) / 255 < 0.6; };

    function flowOf(rows, key) {
      let w = 0, s = 0;
      rows.forEach((r) => { const v = r[key], x = +r.value_sek || 0; if (v != null && isFinite(v) && x > 0) { w += x; s += v * x; } });
      return w > 0 ? s / w : null;
    }

    function compute() {
      const rows = rowsAll();
      const cat = CATS.find((c) => c.id === sel.value) || CATS[0];
      const own = fsel.value === 'own' && cat.fund;
      const key = cat.sectorFlow ? 'flow_score' : 'sflow_score';
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
      const mode = csel.value;
      const scale = d3.scaleLinear().domain([-LIM, 0, LIM]).range([cssv('--color-bad'), cssv('--cds-chart-muted'), cssv('--color-ok')]).interpolate(d3.interpolateRgb).clamp(true);
      list.forEach((g, i) => {
        g.pct = t ? g.sek / t * 100 : 0;
        g.flow = flowOf(g.rows, key);
        g.fill = mode === 'flow' ? (g.flow == null ? cssv('--pie-other') : scale(g.flow)) : cssv(g.other ? '--pie-other' : '--pie-' + i);
      });
      return { list, t, cat, own, n: rows.length, key, mode, flowAll: flowOf(rows, key) };
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
        cap.append(b, document.createTextNode(fmtP(g.pct) + ' · ' + fmtInt(Math.round(g.sek)) + ' SEK · ' + g.rows.length + (g.rows.length === 1 ? ' holding' : ' holdings') + ' · ' + flowWord(g.flow) + (g.flow == null ? '' : ' (' + sgn(g.flow) + ')')));
      }
    }

    function setActive(i) {
      active = i;
      box.classList.toggle('hov', i >= 0);
      box.querySelectorAll('[data-i]').forEach((p) => p.classList.toggle('on', +p.dataset.i === i));
      body.querySelectorAll('tr.bd-row').forEach((tr) => tr.classList.toggle('on', +tr.dataset.i === i));
      caption(i);
    }

    function toggle(i) {
      const g = groups[i]; if (!g) return;
      if (open.has(g.name)) open.delete(g.name); else open.add(g.name);
      drawTable();
      setActive(i);
    }

    const trunc = (t, n) => (t.length <= n ? t : t.slice(0, Math.max(1, n - 1)).trimEnd() + '…');
    function wrap(text, max, maxLines) {
      const lines = []; let cur = '';
      text.split(/\s+/).forEach((w) => {
        if ((cur + ' ' + w).trim().length <= max) cur = (cur + ' ' + w).trim();
        else { if (cur) lines.push(cur); cur = w; }
      });
      if (cur) lines.push(cur);
      let out = lines.slice(0, maxLines).map((l) => trunc(l, max));
      if (lines.length > maxLines) out[maxLines - 1] = trunc(out[maxLines - 1].replace(/…$/, '') + '…', max);
      return out;
    }

    function drawPie() {
      box.textContent = '';
      const narrow = box.clientWidth > 0 && box.clientWidth < 520;
      const W = narrow ? 380 : 680, H = narrow ? 380 : 440, R = narrow ? 178 : 160, cx = W / 2, cy = H / 2;
      const svg = d3.select(box).append('svg').attr('viewBox', '0 0 ' + W + ' ' + H);
      const gg = svg.append('g').attr('transform', 'translate(' + cx + ',' + cy + ')');
      const arcs = d3.pie().sort(null).value((g) => g.sek)(groups);
      const arc = d3.arc().innerRadius(0).outerRadius(R);
      gg.selectAll('path').data(arcs).join('path').attr('d', arc).attr('fill', (a) => a.data.fill).attr('data-i', (a) => a.index)
        .on('mouseenter', (e, a) => setActive(a.index)).on('mouseleave', () => setActive(-1)).on('click', (e, a) => toggle(a.index))
        .append('title').text((a) => a.data.name + ': ' + fmtP(a.data.pct) + ', ' + fmtInt(Math.round(a.data.sek)) + ' SEK');
      const outside = [];
      arcs.forEach((a) => {
        const g = a.data, ang = a.endAngle - a.startAngle, mid = (a.startAngle + a.endAngle) / 2, ux = Math.sin(mid), uy = -Math.cos(mid);
        const fill = dark(g.fill) ? '#ffffff' : '#1f1e1d';
        const pct = Math.round(g.pct) + '%';
        if (ang >= 0.62) {                      // big slice: name and share across the middle of it
          const width = 2 * 0.6 * R * Math.sin(Math.min(ang, Math.PI) / 2);
          const lines = wrap(g.name, Math.max(8, Math.min(22, Math.floor(width / 7))), 3);
          const t = gg.append('text').attr('class', 'lbl').attr('data-i', a.index).attr('text-anchor', 'middle').attr('fill', fill)
            .attr('transform', 'translate(' + (ux * R * 0.6) + ',' + (uy * R * 0.6) + ')');
          const n = lines.length + 1, y0 = -(n - 1) * 7.5;
          lines.forEach((l, k) => t.append('tspan').attr('x', 0).attr('y', y0 + k * 15).attr('dy', '0.35em').text(l));
          t.append('tspan').attr('class', 'p').attr('x', 0).attr('y', y0 + lines.length * 15).attr('dy', '0.35em').text(pct);
        } else if (ang >= 0.1 && (R - 9) - 14 / ang >= 44) {   // medium slice: name along the slice, ending at the rim, only where the slice is thick enough
          const deg = mid * 180 / Math.PI, left = mid > Math.PI;
          const maxc = Math.floor(((R - 9) - 14 / ang) / 6.6);
          const t = gg.append('text').attr('class', 'lbl').attr('data-i', a.index).attr('fill', fill).attr('dy', '0.35em')
            .attr('text-anchor', left ? 'start' : 'end')
            .attr('transform', 'rotate(' + (left ? deg + 90 : deg - 90) + ') translate(' + (left ? -(R - 9) : (R - 9)) + ',0)');
          // rotate puts the x axis along the slice's centre line; text then starts (left half) or ends (right half) 9px inside the rim
          t.append('tspan').text(trunc(g.name, maxc - pct.length - 1) + ' ');
          t.append('tspan').attr('class', 'p').text(pct);
        } else if (!narrow) {                    // tiny slice: name outside with a leader line
          outside.push({ a, g, ux, uy, right: ux >= 0 });
        }
      });
      // outside labels, spread so they do not overlap
      [true, false].forEach((side) => {
        const L = outside.filter((o) => o.right === side).sort((p, q) => p.uy - q.uy);
        let y = -Infinity;
        L.forEach((o) => { o.ty = Math.max(o.uy * (R + 18), y + 15); y = o.ty; });
        const over = y - (H / 2 - 8);
        if (over > 0) L.forEach((o) => { o.ty -= over; });
        L.forEach((o) => {
          const x1 = o.ux * R, y1 = o.uy * R, x2 = o.ux * (R + 12), y2 = o.uy * (R + 12), x3 = (side ? 1 : -1) * (R + 22);
          const yy = Math.max(-H / 2 + 8, o.ty);
          gg.append('polyline').attr('class', 'lead').attr('points', x1 + ',' + y1 + ' ' + x2 + ',' + yy + ' ' + x3 + ',' + yy);
          gg.append('text').attr('class', 'lbl out').attr('data-i', o.a.index).attr('x', x3 + (side ? 5 : -5)).attr('y', yy).attr('dy', '0.35em')
            .attr('text-anchor', side ? 'start' : 'end').text(trunc(o.g.name, Math.floor((W / 2 - R - 30) / 6.6) - 6) + ' ' + Math.round(o.g.pct * 10) / 10 + '%');
        });
      });
      const cap = document.createElement('p'); cap.className = 'bd-cap'; cap.setAttribute('aria-live', 'polite'); box.appendChild(cap);
      caption(-1);
    }

    function drawTable() {
      body.textContent = '';
      const mkN = (txt, cls) => { const td = document.createElement('td'); td.className = cls || 'num'; td.textContent = txt; return td; };
      groups.forEach((g, i) => {
        const tr = document.createElement('tr'); tr.className = 'bd-row'; tr.dataset.i = i; tr.setAttribute('aria-expanded', open.has(g.name) ? 'true' : 'false');
        const td0 = document.createElement('td'), sw = document.createElement('span'), bt = document.createElement('button');
        sw.className = 'sw'; sw.style.background = g.fill; bt.type = 'button';
        bt.append(sw, document.createTextNode(g.name));
        td0.appendChild(bt);
        tr.append(td0, mkN(fmtP(g.pct)), mkN(fmtInt(Math.round(g.sek))), mkN(String(g.rows.length)), mkN(g.flow == null ? 'No reading' : flowWord(g.flow) + ' (' + sgn(g.flow) + ')', 'fl'));
        tr.addEventListener('mouseenter', () => setActive(i)); tr.addEventListener('mouseleave', () => setActive(-1));
        tr.addEventListener('click', () => toggle(i));
        body.appendChild(tr);
        if (open.has(g.name)) {
          const sub = document.createElement('tr'); sub.className = 'bd-sub';
          const td = document.createElement('td'); td.colSpan = 5;
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
      const all = groups.length ? flowOf([].concat(...groups.map((g) => g.rows)), lastKey) : null;
      tr.append(t0, mkN('100%'), mkN(fmtInt(Math.round(total))), mkN(String(d3.sum(groups, (g) => g.rows.length))), mkN(all == null ? '' : flowWord(all) + ' (' + sgn(all) + ')', 'fl'));
      foot.appendChild(tr);
    }

    let lastKey = 'flow_score';
    function draw() {
      const c = compute();
      lastKey = c.key;
      fsel.classList.toggle('dim', !c.cat.fund); fsel.disabled = !c.cat.fund;
      keyEl.hidden = c.mode !== 'flow';
      keyNote.textContent = c.mode === 'flow' ? ' · ' + (c.cat.sectorFlow ? 'money flow in the sector or industry' : 'money flow in the stocks themselves') + ', averaged by value' : '';
      groups = c.list; total = c.t;
      if (!groups.length) { box.textContent = ''; body.textContent = ''; foot.textContent = ''; cnt.textContent = 'No holdings loaded'; return; }
      cnt.textContent = groups.length + (groups.length === 1 ? ' slice' : ' slices') + ' · ' + c.n + ' holdings';
      const narrow = box.clientWidth > 0 && box.clientWidth < 520;
      const key = c.cat.id + '|' + fsel.value + '|' + c.mode + '|' + narrow + '|' + groups.map((g) => g.name + ':' + Math.round(g.sek) + ':' + (g.flow == null ? 'n' : g.flow.toFixed(1))).join(',');
      if (key === sig && box.querySelector('svg')) return;  // nothing moved since the last draw
      sig = key;
      drawPie(); drawTable();
      if (active >= 0) setActive(Math.min(active, groups.length - 1));
    }
    sel.addEventListener('change', () => { store.set('bd-cat', sel.value); open.clear(); draw(); });
    fsel.addEventListener('change', () => { store.set('bd-funds', fsel.value); draw(); });
    csel.addEventListener('change', () => { store.set('bd-col', csel.value); draw(); });
    try { window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => { sig = ''; draw(); }); } catch (e) { /* old browser */ }
    dash.onData(draw);
  })();

"""

# CSS: from the --pie vars line to the end of the card's rules
between("  :root { --pie-0:", "</style>\n\n<div class=\"hs\">", CSS)
# HTML card
between('  <section class="hs-card" id="breakdown">', '  <section class="hs-card" id="quadrant">', HTML)
# script
between("  // ---------- portfolio breakdown: pie by sector, industry, country, ... ----------",
        "  // ---------- strongest bullish readings by market (rules-based screen, live from TradingView) ----------", JS)
open(PATH, "w", encoding="utf-8").write(s)
print("patched", len(s))
