#!/usr/bin/env python3
"""Strategy tab, "Strongest bullish readings by market": add the Signal and Candle touch columns (run after patch_lookup_signal.py and patch_halal.py).

Same cells as "Every holding" (signalOf / sigCell, touchOf / touchCell). A company you own uses its holdings row (the stored daily history);
any other company has only what TradingView's scanner gives live, so it is enriched the way "Look up any stock" does it: the lookup's
parse + lookupRow, fetched in one request for the listed companies (the latest daily candle and the two before it; the strategy view behind
Signal is the lookup's December view). Exact-text replace with count asserts, as in the other scripts/patch_*.py."""
PATH = "index.html"
s = open(PATH, encoding="utf-8").read()
assert "lookupEnrich" not in s, "already patched"


def rep(old, new, cnt=1):
    global s
    n = s.count(old)
    assert n == cnt, f"expected {cnt}, found {n}: {old[:90]!r}"
    s = s.replace(old, new)


# ---- the hook the lookup fills in and the screen calls (declared ahead of both)
rep("  // ---------- Halal indicator: an estimated Shariah screen,", "  let lookupEnrich = null;   // set by the lookup: async (symbols) => Map(symbol -> row for signalOf / touchOf); used by the Strategy screen table\n  // ---------- Halal indicator: an estimated Shariah screen,")

# ---- lookup: the batch enrichment
rep("    // ----- result row\n    function cellsFor(d) {", """    // batch version for the Strategy screen table: the same parse, December view and lookupRow, one request for many symbols
    lookupEnrich = async function (syms) {
      const out = new Map();
      for (let i = 0; i < syms.length; i += 100) {
        const res = await fetch('https://scanner.tradingview.com/global/scan', {
          method: 'POST', headers: { 'Content-Type': 'text/plain;charset=UTF-8' },
          body: JSON.stringify({ symbols: { tickers: syms.slice(i, i + 100) }, columns: COLS }),
        });
        if (!res.ok) continue;
        const j = await res.json();
        (j.data || []).forEach((row) => { const d = parse(row); out.set(row.s, lookupRow(d, decemberOf(d, sectorFlow(d)))); });
      }
      return out;
    };

    // ----- result row
    function cellsFor(d) {""")

# ---- screen table: header, sort keys, cells, enrichment
rep("""          <th><button data-k="name">Company</button></th>
          <th class="sec"><button data-k="size">Size</button></th>""", """          <th><button data-k="name">Company</button></th>
          <th data-field="signal"><button data-k="sig">Signal</button></th>
          <th data-field="touch"><button data-k="tch">Candle touch</button></th>
          <th class="sec"><button data-k="size">Size</button></th>""")
rep("""    const holdSet = () => { const h = dash.data('holdings'); return new Set(h.status === 'ok' ? h.data.map((r) => r.sym) : []); };
    function draw() {""", """    const holdSet = () => { const h = dash.data('holdings'); return new Set(h.status === 'ok' ? h.data.map((r) => r.sym) : []); };
    const holdMap = () => { const h = dash.data('holdings'); return new Map(h.status === 'ok' ? h.data.map((r) => [r.sym, r]) : []); };
    // Signal and Candle touch for one listed company: its holdings row if you own it, otherwise the enriched lookup row (null while loading)
    SC.enr = new Map();
    let ownRows = new Map();
    function sgOf(d) {
      const r = ownRows.get(d.sym) || SC.enr.get(d.sym);
      if (!r) return null;
      const sg = signalOf(r);
      return { sg: sg.alert || r.rating ? sg : null, tc: touchOf(r) };
    }
    async function enrichTop() {
      if (!lookupEnrich || SC.enrBusy) return;
      const syms = [];
      Object.values(SC.data).forEach((b) => b.top.forEach((d) => { if (!ownRows.has(d.sym)) syms.push(d.sym); }));
      if (!syms.length) return;
      SC.enrBusy = true;
      try { const m = await lookupEnrich(syms); if (m.size) { SC.enr = m; draw(); } } catch (e) { /* the columns stay as dashes until the next refresh */ } finally { SC.enrBusy = false; }
    }
    function draw() {""")
rep("      rec: (d) => d.rec, upside: (d) => d.upside, revg: (d) => d.revg, margin: (d) => d.margin, mcap: (d) => d.mcap, score: (d) => d.score,\n    };",
    "      rec: (d) => d.rec, upside: (d) => d.upside, revg: (d) => d.revg, margin: (d) => d.margin, mcap: (d) => d.mcap, score: (d) => d.score,\n      sig: (d) => { const x = sgOf(d); return x && x.sg ? x.sg.rank : null; }, tch: (d) => { const x = sgOf(d); return x ? x.tc.rank : null; },\n    };")
rep("      const own = holdSet();\n      const out = [];\n      rows.forEach((d) => {\n        const tr = document.createElement('tr'); tr.dataset.key = d.sym;",
    "      const own = holdSet(); ownRows = holdMap();\n      const out = [];\n      rows.forEach((d) => {\n        const tr = document.createElement('tr'); tr.dataset.key = d.sym;")
rep("          td(d.rank, 'rk'), nm, td(d.size, 'sec'),", """          td(d.rank, 'rk'), nm, sgCells.sig, sgCells.tch, td(d.size, 'sec'),""")
rep("        const macdTxt = d.macd == null || d.macds == null ? '—' : (d.macd > d.macds ? 'Bullish' : 'Bearish');",
    """        const sx = sgOf(d), sgCells = sx ? { sig: sx.sg ? sigCell(sx.sg) : td('\\u2014', 'mut'), tch: touchCell(sx.tc) } : { sig: td('\\u2014', 'mut'), tch: td('\\u2014', 'mut') };
        const macdTxt = d.macd == null || d.macds == null ? '—' : (d.macd > d.macds ? 'Bullish' : 'Bearish');""")
rep("const c = document.createElement('td'); c.colSpan = 19;\n          const h = document.createElement('p')", "const c = document.createElement('td'); c.colSpan = 21;\n          const h = document.createElement('p')")
rep("const tr = document.createElement('tr'); const c = document.createElement('td'); c.colSpan = 19; c.className = 'mut';\n        c.textContent = box ?", "const tr = document.createElement('tr'); const c = document.createElement('td'); c.colSpan = 21; c.className = 'mut';\n        c.textContent = box ?")
rep("      } finally { clearTimeout(to); SC.busy = false; draw(); }\n    }\n    SC.draw = draw;",
    "      } finally { clearTimeout(to); SC.busy = false; draw(); enrichTop(); }\n    }\n    SC.draw = draw;")
rep("    SC.draw = draw;\n    window.__scr = SC;", """    SC.draw = draw;
    const SIG_TXT = ['Signal rules', 'Alert buy / Alert sell: the 50-day MA is about to touch the 200-day MA from below / from above (within ' + APPROACH_PCT + '% of it and closing in, so it would touch within ' + APPROACH_DAYS + ' trading days). Kept for ' + ALERT_HOLD + ' trading days after the last session that met this (so it also covers the touch itself) unless the averages cross the other way.',
      'Otherwise the strategy view: Strong buy, Buy, Hold, Sell or Strong sell.'].join('\\n');
    document.querySelectorAll('#scr-tbl th[data-field]').forEach((th) => {
      th.title = (th.dataset.field === 'touch' ? TCH_RULES : SIG_TXT) + '\\n\\nFor a company you do not own only the latest daily candle and the two before it are available (as in Look up any stock), so the pace in Signal is taken over 2 sessions and a candle touch is kept for the latest and the previous session.';
    });
    dash.onData(() => { if (SC.last) SC.draw(); });
    window.__scr = SC;""")

# ---- note under the table
rep('    <p class="hs-note" id="scr-status" aria-live="polite">', """    <p class="hs-note" id="scr-sig-note"><b>Signal and Candle touch</b> follow the same rules as in Every holding (hover the headers for them). For a company you own they use your stored daily history; for any other company TradingView only gives the latest daily candle and the two before it, as in Look up any stock, so the \\u201cabout to touch\\u201d test looks at 3 daily gaps instead of 6, a candle touch is kept for the latest and the previous session instead of 5, and the strategy view behind Signal is the lookup\\u2019s December view.</p>
    <p class="hs-note" id="scr-status" aria-live="polite">""")
open(PATH, "w", encoding="utf-8").write(s)
print("patched", len(s))
