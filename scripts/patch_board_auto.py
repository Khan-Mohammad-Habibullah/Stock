#!/usr/bin/env python3
"""Page side of the self-updating board:
  * Strategy tab: "Former holdings" -- every stock you used to own, same columns as "Every holding"
  * My holdings tab: "Update holdings" -- read a Nordnet export in the browser (pdf.js; the file never
    leaves the computer), preview the changes, save only the positions to GitHub's inbox/
  * the "Data last extracted" labels and the as-of lines are filled in by every rebuild
  * month names in the former-holdings text follow the calendar like the rest
  * stock lookup: analyst targets arrive in USD from the screener; convert to the stock's currency
Exact-text replace with count asserts, as in the other scripts/patch_*.py."""

PATH = "index.html"
s = open(PATH, encoding="utf-8").read()
n0 = len(s)


def rep(old, new, cnt=1):
    global s
    n = s.count(old)
    assert n == cnt, f"expected {cnt}, found {n}: {old[:90]!r}"
    s = s.replace(old, new)


HEADER_COLS = """          <th data-field="name"><button data-k="name">Holding</button></th>
          <th class="num" data-field="value_sek"><button data-k="gone_by">Value SEK</button></th>
          <th class="num" data-field="price">Price now</th>
          <th class="num" data-field="r1m_day">Today</th>
          <th class="num" data-field="r1m"><button data-k="r1m">1 month</button></th>
          <th data-field="sflow"><button data-k="sflow_score">Money flow</button></th>
          <th class="num" data-field="rsi"><button data-k="rsi">RSI</button></th>
          <th class="sec" data-field="macd"><button data-k="macd">MACD</button></th>
          <th class="num sec" data-field="vs50"><button data-k="vs50">vs 50-day</button></th>
          <th class="sec" data-field="alligator"><button data-k="alligator">Alligator</button></th>
          <th class="sec" data-field="cpr"><button data-k="cpr"><span class="mo3">Oct</span> CPR</button></th>
          <th class="sec" data-field="bollinger"><button data-k="bollinger">Bollinger</button></th>
          <th class="num sec" data-field="udv"><button data-k="udv">Up/down vol</button></th>
          <th data-field="oct_signal"><button data-k="oct_score"><span class="mo">October</span></button></th>
          <th data-field="o1y"><button data-k="o1y_score">1 year</button></th>
          <th class="sec" data-field="o3y"><button data-k="o3y_score">3 years</button></th>
          <th data-field="o5y"><button data-k="o5y_score">5 years</button></th>
          <th data-field="december"><button data-k="dec_score">December</button></th>
          <th class="num sec" data-field="rev_g"><button data-k="rev_g">Revenue growth</button></th>
          <th class="num sec" data-field="margin"><button data-k="margin">Net margin</button></th>
          <th class="num sec" data-field="pe"><button data-k="pe">P/E</button></th>
          <th class="sec" data-field="analysts"><button data-k="analysts">Analysts</button></th>"""

# ---------------------------------------------------------------- CSS
rep("  .lookup-box { align-items: flex-start; }\n",
    """  .lookup-box { align-items: flex-start; }
  .upd { margin: 8px 0 0; border: 1px solid var(--color-border-line); border-radius: var(--cds-radius); padding: 8px 12px; background: var(--color-bg); }
  .upd > summary { cursor: pointer; font-weight: 600; font-size: var(--cds-font-size-caption); }
  .upd p, .upd li { font-size: var(--cds-font-size-caption); }
  .upd ul { margin: 4px 0; padding-left: 1.1rem; }
  .upd .row { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin: 8px 0; }
  .upd button, .upd .btn { font: inherit; font-size: var(--cds-font-size-caption); padding: 6px 12px; border: 1px solid var(--color-border-line); border-radius: var(--cds-radius); background: var(--color-panel); color: var(--color-fg); cursor: pointer; text-decoration: none; }
  .upd button.primary { background: var(--color-fg); color: var(--color-bg); border-color: var(--color-fg); }
  .upd button[disabled] { opacity: .5; cursor: default; }
  .upd .ok { color: var(--color-ok); font-weight: 600; }
  .upd .bad { color: var(--color-bad); font-weight: 600; }
  .gone { color: var(--color-fg-muted); white-space: nowrap; }
""")

# ---------------------------------------------------------------- My holdings header
rep('    <p class="hs-extracted"><span class="dot"></span>Data last extracted: 16 October 2026, 16:02</p>',
    '    <p class="hs-extracted" id="stock-extracted-top"><span class="dot"></span>Data last extracted: 16 October 2026, 16:02</p>')
i = s.index('    <p class="hs-asof">Holdings, quantities and values from your Nordnet export of 28 October 2026 (14:41).')
j = s.index("</p>", i) + 4
s = s[:i] + ('    <p class="hs-asof" id="asof-holdings">Holdings and quantities from your Nordnet export of 28 October 2026 (14:41). '
             'Prices, signals, outlooks and money flows are rebuilt every weekday morning and whenever you update your holdings, from TradingView\'s screener and Yahoo Finance daily bars. '
             'ETF facts from the issuers and fund-data sites, dated on each card. Signals describe what the indicators show, not advice on what to buy or sell.</p>') + s[j:]
rep("Signals, outlooks, sector flows and the December lists are the snapshot described above and do not change until the board is rebuilt.",
    "Signals, outlooks, sector flows and the December lists are the snapshot described above and change at the next rebuild (every weekday morning).")
rep("Values in SEK follow the live price with exchange rates held at the level of your Nordnet export of 28 October.</p>",
    """Values in SEK follow the live price with exchange rates from the last rebuild.</p>
    <details class="upd" id="upd">
      <summary>Update holdings from a Nordnet export</summary>
      <p>In Nordnet, open <b>Innehav</b>, print the page to PDF, and choose that PDF here. It is read in this browser only: the PDF itself is not uploaded anywhere, and the only thing saved is each holding's name, quantity and value. Sold stocks move to <b>Former holdings</b> on the Strategy tab, new ones are matched to their listing automatically, and the whole board is rebuilt in about 15&ndash;20 minutes.</p>
      <div class="row"><input type="file" id="upd-file" accept="application/pdf,.pdf" aria-label="Nordnet Innehav export (PDF)"></div>
      <div id="upd-out" aria-live="polite"></div>
      <p id="upd-status" class="hs-note"></p>
    </details>""")

# ---------------------------------------------------------------- Strategy header
rep('    <p class="hs-extracted"><span class="dot"></span>Data last extracted: 16 October 2026</p>',
    '    <p class="hs-extracted" id="stock-extracted-strategy"><span class="dot"></span>Data last extracted: 16 October 2026</p>')
rep("<p class=\"hs-take\">Where money is moving across the US, Swedish, Norwegian and European markets,",
    "<p class=\"hs-take\">Where money is moving across eight markets,")
rep('    <p class="hs-asof">Sector money flow and the stocks under each sector are to the 16 October close, from TradingView daily bars.',
    '    <p class="hs-asof"><span id="asof-strategy">Sector money flow and the stocks under each sector are rebuilt every weekday morning from TradingView\'s screener and daily bars.</span>')

# ---------------------------------------------------------------- Former holdings section (after the stock lookup)
rep("""    <p class="hs-note" id="lookup-note"></p>
  </section>
""", """    <p class="hs-note" id="lookup-note"></p>
  </section>

  <section class="hs-card" id="former">
    <h2>Former holdings</h2>
    <p class="hs-note">Every stock you have owned on this board and no longer hold, with the same readings as "Every holding", rebuilt every weekday. Instead of a value, the second column shows the Nordnet export it was first missing from, so it was sold before then. Click a name for its chart.</p>
    <div class="tbl-wrap">
      <table class="hold" id="tbl-former">
        <thead><tr>
""" + HEADER_COLS + """
        </tr></thead>
        <tbody></tbody>
      </table>
    </div>
  </section>
""")

# ---------------------------------------------------------------- month names in the former rows
rep("    ['holdings', 'flows', 'flow_picks', 'etfs', 'exposure', 'monthly'].forEach((id) => {",
    "    ['holdings', 'former', 'flows', 'flow_picks', 'etfs', 'exposure', 'monthly'].forEach((id) => {")

# ---------------------------------------------------------------- lookup: targets come in USD
rep("""      d.vs50 = d.close != null && d.sma50 ? (d.close / d.sma50 - 1) * 100 : null;
      d.vs200 = d.close != null && d.sma200 ? (d.close / d.sma200 - 1) * 100 : null;
      d.upside = d.close && d.target ? (d.target / d.close - 1) * 100 : null;

      // "Oct CPR\"""".replace('\\"', '"'),
    """      d.vs50 = d.close != null && d.sma50 ? (d.close / d.sma50 - 1) * 100 : null;
      d.vs200 = d.close != null && d.sma200 ? (d.close / d.sma200 - 1) * 100 : null;
      // the screener gives analyst targets in USD for every market; convert with the rebuild's exchange rates
      if (d.target != null && d.cur && d.cur !== 'USD') {
        const bs = dash.data('board_status'), fx = bs.status === 'ok' && bs.data[0] && bs.data[0].usd_per ? bs.data[0].usd_per : null;
        d.target = fx && fx[d.cur] ? d.target / fx[d.cur] : null;
      }
      d.upside = d.close && d.target ? (d.target / d.close - 1) * 100 : null;

      // "Oct CPR\"""".replace('\\"', '"'))

# ---------------------------------------------------------------- methods: how the board now updates itself
rep("      <p><b>Limits.</b>", """      <p><b>Automatic updates and former holdings.</b> Every weekday morning, and whenever you update your holdings, the board is rebuilt from scratch on GitHub: about 1,600 companies' daily bars from Yahoo Finance and their sector, fundamentals and analyst data from TradingView's screener, for your holdings, the stocks you used to own and the eight markets' money flow. The technical readings follow the rules above; checked against the board's original readings for 102 holdings, the rebuild gives the same October signal for 94, the same MACD, Alligator, Bollinger and price-structure reading for 93 to 100, and RSI and moving-average distances within a point or two for all but one or two. The 1-, 3- and 5-year outlooks use weights recovered from the original scores (same group for 83 to 85% of holdings, never more than one group apart), so treat them as approximate. The detail panel's notes on news stay as written. Former holdings are every stock that was on the board and is not any more, dated by the first Nordnet export it was missing from.</p>
      <p><b>Limits.</b>""")

# ---------------------------------------------------------------- JS: former table, update flow, build stamps
JS = r"""
  // ---------- Former holdings: the stocks you used to own, read like "Every holding" ----------
  (function () {
    const tbl = document.getElementById('tbl-former');
    if (!tbl) return;
    const tbody = tbl.querySelector('tbody');
    const st = { sort: 'gone_by', dir: -1 };
    const fmtGone = (d) => (d ? 'gone by ' + new Date(d + 'T12:00:00Z').toLocaleDateString('en-GB', { day: 'numeric', month: 'short' }) : 'sold');
    function draw() {
      const d = dash.data('former');
      tbody.replaceChildren();
      const rows = d.status === 'ok' ? d.data.slice() : [];
      if (!rows.length) {
        const tr = document.createElement('tr'); const c = document.createElement('td'); c.colSpan = 22; c.className = 'mut';
        c.textContent = d.status === 'ok' ? 'No former holdings yet.' : 'Former holdings appear after the next rebuild.';
        tr.appendChild(c); tbody.appendChild(tr); return;
      }
      const k = st.sort;
      rows.sort((a, b) => { const x = a[k], y = b[k]; if (x == null) return 1; if (y == null) return -1; return (x > y ? 1 : x < y ? -1 : 0) * st.dir; });
      const td = (text, cls) => { const c = document.createElement('td'); if (cls) c.className = cls; c.textContent = text == null ? '—' : text; return c; };
      const chip = (label, cls) => { const c = document.createElement('td'); if (cls) c.className = cls; const sp = document.createElement('span'); sp.className = 'chip ' + chipCls(label); sp.textContent = label == null ? '—' : label; c.appendChild(sp); return c; };
      rows.forEach((r) => {
        const tr = document.createElement('tr');
        tr.append(
          nameTd(r.name, r.sym, null, null),
          td(fmtGone(r.gone_by), 'num gone'),
          td(r.price == null ? null : plain(r.price, r.price < 10 ? 3 : 2) + ' ' + r.cur, 'num'),
          td(r.day_chg == null ? null : signed(r.day_chg, 2), 'num ' + tone(r.day_chg)),
          td(signed(r.r1m), 'num ' + tone(r.r1m)),
          chip(r.sflow),
          td(plain(r.rsi, 0), 'num'),
          td(r.macd, 'sec ' + (r.macd == null ? 'mut' : String(r.macd).startsWith('Bullish') ? 'pos' : 'neg')),
          td(signed(r.vs50), 'num sec ' + tone(r.vs50)),
          td(r.alligator, 'sec'),
          td(r.cpr, 'sec ' + (r.cpr === 'Above' ? 'pos' : r.cpr === 'Below' ? 'neg' : 'mut')),
          td(r.bollinger, 'sec'),
          td(plain(r.udv, 2), 'num sec ' + (r.udv == null ? 'mut' : r.udv > 1.1 ? 'pos' : r.udv < 0.9 ? 'neg' : 'mut')),
          chip(r.oct_signal), chip(r.o1y), chip(r.o3y, 'sec'), chip(r.o5y), chip(r.december),
          td(signed(r.rev_g, 0), 'num sec ' + tone(r.rev_g)),
          td(r.margin == null ? null : r.margin.toFixed(0) + '%', 'num sec ' + tone(r.margin)),
          td(r.pe == null ? null : r.pe.toFixed(0), 'num sec'),
          td(r.analysts, 'sec'),
        );
        tbody.appendChild(tr);
      });
    }
    tbl.querySelectorAll('th button').forEach((b) => b.addEventListener('click', () => {
      const k = b.dataset.k;
      if (st.sort === k) st.dir = -st.dir; else { st.sort = k; st.dir = ['name', 'macd', 'alligator', 'cpr', 'bollinger', 'analysts'].includes(k) ? 1 : -1; }
      draw();
    }));
    dash.onData(draw);
  })();

  // ---------- build stamps: what the last rebuild used ----------
  (function () {
    const bs = dash.data('board_status');
    if (bs.status !== 'ok' || !bs.data.length) return;
    const b = bs.data[0];
    const dd = (iso, opt) => new Date(iso.length <= 10 ? iso + 'T12:00:00Z' : iso).toLocaleDateString('en-GB', opt || { day: 'numeric', month: 'long', year: 'numeric' });
    const hu = b.holdings_updated ? b.holdings_updated.replace(' ', 'T') : null;
    const huTxt = hu ? dd(hu.slice(0, 10)) + (hu.length > 10 ? ' (' + hu.slice(11, 16) + ')' : '') : 'your last Nordnet export';
    const ah = document.getElementById('asof-holdings');
    if (ah) ah.textContent = 'Holdings and quantities from your Nordnet export of ' + huTxt + '. Prices, signals, outlooks and money flows were rebuilt on ' + dd(b.built.slice(0, 10)) +
      ' from TradingView\'s screener and Yahoo Finance daily bars to the ' + dd(b.data_date, { day: 'numeric', month: 'long' }) + ' close; this happens every weekday morning and whenever you update your holdings. ' +
      'ETF facts from the issuers and fund-data sites, dated on each card. Signals describe what the indicators show, not advice on what to buy or sell.';
    const as = document.getElementById('asof-strategy');
    if (as) as.textContent = 'Sector money flow and the stocks under each sector are to the ' + dd(b.data_date, { day: 'numeric', month: 'long' }) + ' close, rebuilt every weekday morning from TradingView\'s screener and daily bars.';
  })();

  // ---------- Update holdings: read a Nordnet "Innehav" export in the browser ----------
  (function () {
    const fileEl = document.getElementById('upd-file');
    if (!fileEl) return;
    const out = document.getElementById('upd-out'), statusEl = document.getElementById('upd-status');
    const REPO = 'Khan-Mohammad-Habibullah/Stock';
    const PDFJS = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/';
    const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
    const bsd = () => { const bs = dash.data('board_status'); return bs.status === 'ok' && bs.data.length ? bs.data[0] : {}; };
    // what the last holdings update did
    (function showLast() {
      const b = bsd(), li = b.inbox;
      const parts = [];
      if (b.holdings_updated) parts.push('Holdings last updated from the Nordnet export of ' + b.holdings_updated + '.');
      if (b.built) parts.push('Board last rebuilt ' + b.built.replace('T', ' ').replace('Z', ' UTC') + '.');
      if (li) {
        if (li.refused) parts.push('Last file not used: ' + li.refused + '.');
        if (li.unmatched && li.unmatched.length) parts.push('Not matched, left out: ' + li.unmatched.join('; ') + '. Tell Claude the ticker and it will be added.');
        if (li.auto_matched && li.auto_matched.length) parts.push('Matched automatically: ' + li.auto_matched.join('; ') + '.');
      }
      statusEl.textContent = parts.join(' ');
    })();
    let libP = null;
    function pdfjs() {
      if (!libP) libP = new Promise((res, rej) => {
        const sc = document.createElement('script'); sc.src = PDFJS + 'pdf.min.js';
        sc.onload = () => { window.pdfjsLib.GlobalWorkerOptions.workerSrc = PDFJS + 'pdf.worker.min.js'; res(window.pdfjsLib); };
        sc.onerror = () => { libP = null; rej(new Error('could not load the PDF reader')); };
        document.head.appendChild(sc);
      });
      return libP;
    }
    // rebuild the text lines of each page from pdf.js text items (same layout pdftotext -layout gives)
    async function pdfLines(buf) {
      const lib = await pdfjs();
      const doc = await lib.getDocument({ data: buf }).promise;
      const lines = [];
      for (let p = 1; p <= doc.numPages; p++) {
        const tc = await (await doc.getPage(p)).getTextContent();
        const rows = [];
        tc.items.forEach((it) => {
          if (!it.str || !it.str.trim()) return;
          const x = it.transform[4], y = it.transform[5];
          let row = rows.find((r) => Math.abs(r.y - y) < 2.5);
          if (!row) { row = { y, items: [] }; rows.push(row); }
          row.items.push({ x, w: it.width, s: it.str });
        });
        rows.sort((a, b) => b.y - a.y);
        rows.forEach((r) => {
          r.items.sort((a, b) => a.x - b.x);
          let line = '', end = null;
          r.items.forEach((it) => { if (end !== null) { const gap = it.x - end; line += gap > 6 ? '    ' : gap > 0.8 ? ' ' : ''; } line += it.s; end = it.x + it.w; });
          lines.push(line);
        });
      }
      return lines;
    }
    // the same rules as scripts/nordnet.py
    const NUM = '\\d{1,3}(?:[ \\u00a0\\u202f]\\d{3})*';
    const ROW = new RegExp('^\\s*(?:[A-Z]\\s{2,})?(\\S.*?\\S)\\s{2,}(' + NUM + ')\\s{2,}([\\u2212+\\-]?\\d+,\\d+)\\s?%\\s+(' + NUM + ')\\s*$');
    const TOTAL = new RegExp('^\\s*Totalt\\s+(' + NUM + ')\\s*$');
    const DATE = /^\s*(\d{1,2})\/(\d{1,2})\/(\d{2}),\s+(\d{1,2}):(\d{2})\s*([AP]M)/;
    const toInt = (t) => parseInt(t.replace(/[   ]/g, ''), 10);
    function parse(lines) {
      const merged = new Map(); let total = null, stamp = null, nrows = 0;
      lines.forEach((ln) => {
        if (!stamp) { const m = ln.match(DATE); if (m) { const h = (parseInt(m[4], 10) % 12) + (m[6] === 'PM' ? 12 : 0); stamp = '20' + m[3] + '-' + m[1].padStart(2, '0') + '-' + m[2].padStart(2, '0') + ' ' + String(h).padStart(2, '0') + ':' + m[5]; } }
        let m = ln.match(TOTAL); if (m) { total = toInt(m[1]); return; }
        m = ln.match(ROW);
        if (m) {
          nrows += 1;
          const name = m[1].trim(), q = toInt(m[2]), v = toInt(m[4]);
          const p = merged.get(name) || { name, qty: 0, value_sek: 0 };
          p.qty += q; p.value_sek += v; merged.set(name, p);
        }
      });
      const pos = [...merged.values()];
      const sum = pos.reduce((a, p) => a + p.value_sek, 0);
      return { exported: stamp, positions: pos, rows: nrows, complete: total != null && Math.abs(sum - total) <= Math.max(5, pos.length) };
    }
    fileEl.addEventListener('change', async () => {
      out.replaceChildren(el('p', null, 'Reading the export…'));
      const f = fileEl.files && fileEl.files[0];
      if (!f) { out.replaceChildren(); return; }
      let res;
      try { res = parse(await pdfLines(await f.arrayBuffer())); }
      catch (e) { out.replaceChildren(el('p', 'bad', 'Could not read that file (' + e.message + '). Is it the PDF of Nordnet\'s Innehav page?')); return; }
      if (!res.positions.length) { out.replaceChildren(el('p', 'bad', 'No holdings found in that file. Is it the PDF of Nordnet\'s Innehav page?')); return; }
      // compare with what the board holds now
      const names = bsd().names || {};
      const hd = dash.data('holdings'); const cur = new Map((hd.status === 'ok' ? hd.data : []).map((r) => [r.sym, r]));
      const seen = new Map(); const unknown = [];
      res.positions.forEach((p) => { const sym = names[p.name]; if (!sym) { unknown.push(p.name); return; } seen.set(sym, (seen.get(sym) || 0) + p.qty); });
      const sold = [...cur.values()].filter((r) => !seen.has(r.sym)).map((r) => r.name);
      const back = [...seen.keys()].filter((s) => !cur.has(s));
      const changed = [...seen.entries()].filter(([s, q]) => cur.has(s) && cur.get(s).qty !== q).length;
      const box = el('div');
      box.append(el('p', res.complete ? 'ok' : 'bad', res.complete
        ? 'Read ' + res.positions.length + ' holdings from the export of ' + (res.exported || 'unknown date') + '; they add up to Nordnet\'s own total.'
        : 'Read ' + res.positions.length + ' holdings, but they do not add up to Nordnet\'s total, so this file would be refused. Try printing the Innehav page again.'));
      const ul = el('ul');
      if (unknown.length) ul.append(el('li', null, 'New, matched to their listing when saved: ' + unknown.join(', ')));
      if (back.length) ul.append(el('li', null, 'Back from former holdings: ' + back.length));
      ul.append(el('li', null, sold.length ? 'No longer held, move to Former holdings: ' + sold.join(', ') : 'Nothing sold since the last update'));
      ul.append(el('li', null, changed + ' quantit' + (changed === 1 ? 'y' : 'ies') + ' changed'));
      box.append(ul);
      if (res.complete) {
        const body = JSON.stringify({ exported: res.exported, complete: true, p: res.positions.map((p) => [p.name, p.qty, p.value_sek]) });
        const fname = 'holdings-' + (res.exported || new Date().toISOString().slice(0, 16)).replace(/[^0-9]/g, '').slice(0, 12) + '.json';
        const url = 'https://github.com/' + REPO + '/new/main?filename=' + encodeURIComponent('inbox/' + fname) + '&value=' + encodeURIComponent(body);
        const row = el('div', 'row');
        const save = el('button', 'primary', 'Save to GitHub');
        save.type = 'button';
        save.addEventListener('click', () => window.open(url.length < 7800 ? url : 'https://github.com/' + REPO + '/upload/main/inbox', '_blank', 'noopener'));
        const dl = el('button', null, 'Download the file instead');
        dl.type = 'button';
        dl.addEventListener('click', () => {
          const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([body], { type: 'application/json' })); a.download = fname;
          document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
        });
        row.append(save, dl);
        box.append(row, el('p', null', url.length < 7800
          ? '"Save to GitHub" opens GitHub with the file filled in: press "Commit changes" there. The board rebuilds itself in about 15–20 minutes.'
          : 'The file is too long to fill in for you: download it, then drop it on the GitHub page that opens and press "Commit changes".'));
      }
      out.replaceChildren(box);
    });
  })();
"""
JS = JS.replace("el('p', null', url.length", "el('p', null, url.length")
rep("\n  // ---------- crypto: My crypto holdings and Crypto strategy ----------", JS + "\n  // ---------- crypto: My crypto holdings and Crypto strategy ----------")

assert len(s) > n0
open(PATH, "w", encoding="utf-8").write(s)
print("patched", n0, "->", len(s))
