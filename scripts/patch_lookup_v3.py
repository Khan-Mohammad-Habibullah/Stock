#!/usr/bin/env python3
"""Lookup v3: fix "no results" and add 1-letter suggestions + a side pick-list.

Root cause of v2 showing nothing: symbol-search.tradingview.com answers 403 Forbidden
to any page that is not on tradingview.com, so every search died there. The scanner
endpoint (already used by the live prices) does answer cross-site and supports a
name/ticker "match" filter, so search now goes through it.

Also:
  - suggestions from the first letter: your own holdings match instantly (no network),
    market-wide matches follow ~200 ms later, prefix matches ranked first
  - a <select> beside the box: matches for the current text, your holdings A-Z, and the
    largest companies in each market, so a stock can be picked without typing
  - picking a stock you already own shows its full "Every holding" row (real Alligator,
    Up/down vol, October and outlook readings) instead of the live estimate
Same pattern as the other scripts/patch_*.py: exact-text replace with count asserts."""

PATH = "index.html"
s = open(PATH, encoding="utf-8").read()
orig_len = len(s)


def rep(old, new, cnt=1):
    global s
    n = s.count(old)
    assert n == cnt, f"expected {cnt} occurrence(s), found {n}: {old[:80]!r}"
    s = s.replace(old, new, cnt)


def rep_between(start, end, new):
    """Replace s[start ... end) (end marker kept) -- both markers must be unique."""
    global s
    assert s.count(start) == 1, f"start marker count {s.count(start)}: {start[:60]!r}"
    assert s.count(end) == 1, f"end marker count {s.count(end)}: {end[:60]!r}"
    i = s.index(start)
    j = s.index(end)
    assert i < j
    s = s[:i] + new + s[j:]


# ---------- 1. CSS ----------
rep_between(
    "  .lookup-box { position: relative; }\n",
    "  .scr-how summary {",
    """  .lookup-box { align-items: flex-start; }
  .lookup-combo { position: relative; display: flex; flex: 1 1 16rem; max-width: 28rem; min-width: 0; }
  .lookup-combo input[type="search"] { flex: 1 1 auto; width: 100%; }
  .lookup-box select { flex: 0 1 19rem; min-width: 0; max-width: 100%; }
  .lookup-sugg { position: absolute; top: 100%; left: 0; right: 0; z-index: 20; margin: 2px 0 0; padding: 4px; list-style: none; background: var(--color-bg); border: 1px solid var(--color-border-line); border-radius: var(--cds-radius); max-height: 320px; overflow-y: auto; box-shadow: 0 8px 24px color-mix(in srgb, var(--color-fg) 14%, transparent); }
  .lookup-sugg[hidden] { display: none; }
  .lookup-sugg li { display: flex; gap: 8px; align-items: baseline; padding: 6px 8px; border-radius: 6px; cursor: pointer; }
  .lookup-sugg li:hover, .lookup-sugg li.active { background: var(--color-panel); }
  .lookup-sugg .nm { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .lookup-sugg .tk { color: var(--color-fg-muted); font-size: var(--cds-font-size-caption); white-space: nowrap; }
  .lookup-sugg .yours { margin-left: auto; flex: none; font-size: var(--cds-font-size-caption); color: var(--color-fg-muted); border: 1px solid var(--color-border-line); border-radius: 999px; padding: 0 6px; }
""",
)

# ---------- 2. HTML ----------
rep(
    """    <p class="hs-note">Type at least 2 letters of a company name or ticker &mdash; no exchange needed &mdash; and see it in the same table as "Every holding", live from TradingView. Not a recommendation.</p>
    <div class="ctl lookup-box">
      <input id="lookup-q" type="search" placeholder="e.g. Tesla, or TSLA" aria-label="Company name or ticker" autocomplete="off" role="combobox" aria-autocomplete="list" aria-expanded="false">
      <ul id="lookup-sugg" class="lookup-sugg" role="listbox" hidden></ul>
    </div>""",
    """    <p class="hs-note">Start typing a company name or ticker &mdash; suggestions appear from the first letter, no exchange needed &mdash; or pick a stock from the list beside the box. It shows in the same table as "Every holding", live from TradingView. Not a recommendation.</p>
    <div class="ctl lookup-box">
      <div class="lookup-combo">
        <input id="lookup-q" type="search" placeholder="e.g. V, Volvo, Tesla or TSLA" aria-label="Company name or ticker" autocomplete="off" role="combobox" aria-autocomplete="list" aria-controls="lookup-sugg" aria-expanded="false">
        <ul id="lookup-sugg" class="lookup-sugg" role="listbox" hidden></ul>
      </div>
      <select id="lookup-pick" aria-label="Pick a stock from a list"><option value="">Or pick from a list&hellip;</option></select>
    </div>""",
)

# ---------- 3. JS: everything from the old symbol-search function to the end of the IIFE ----------
NEW_UI = r"""    // ----- search: TradingView's scanner. (symbol-search.tradingview.com answers 403 to any site but tradingview.com.)
    const SEARCH_COLS = ['name', 'description', 'exchange', 'type', 'market_cap_basic'];
    const NORDIC = ['OMXSTO', 'OSL', 'OMXCOP', 'OMXHEX'];
    const PICK_MARKETS = [
      { k: 'USA', c: 'United States', ex: ['NASDAQ', 'NYSE', 'AMEX'] },
      { k: 'Sweden', c: 'Sweden', ex: ['OMXSTO'] },
      { k: 'Norway', c: 'Norway', ex: ['OSL'] },
      { k: 'Denmark', c: 'Denmark', ex: ['OMXCOP'] },
      { k: 'Finland', c: 'Finland', ex: ['OMXHEX'] },
      { k: 'Germany', c: 'Germany', ex: ['XETR'] },
      { k: 'Canada', c: 'Canada', ex: ['TSX'] },
    ];
    const DIRECT = /^[A-Za-z][A-Za-z0-9_]*:[A-Za-z0-9._-]+$/;

    async function scan(body, signal) {
      const res = await fetch('https://scanner.tradingview.com/global/scan', {
        method: 'POST', headers: { 'Content-Type': 'text/plain;charset=UTF-8' }, body: JSON.stringify(body), signal,
      });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const j = await res.json();
      return (j.data || []).map((x) => ({ sym: x.s, tk: x.d[0], name: x.d[1] || x.d[0], exch: x.d[2], type: x.d[3], mcap: num(x.d[4]) }));
    }
    function rankOf(m, q) {
      const Q = q.toUpperCase(), lq = q.toLowerCase();
      const tk = String(m.tk || '').toUpperCase(), nm = String(m.name || '').toLowerCase();
      if (tk === Q || tk.replace(/_/g, ' ') === Q) return 0;
      if (tk.startsWith(Q) || nm.startsWith(lq)) return 1;
      if (nm.split(/[\s.,&()\/-]+/).some((w) => w.startsWith(lq))) return 2;
      return 3;
    }
    function sortMatches(list, q) {
      return list.map((m, i) => ({ m, i, r: rankOf(m, q) + (m.type === 'fund' ? 0.5 : 0) }))
        .sort((a, b) => a.r - b.r || (b.m.mcap || 0) - (a.m.mcap || 0) || a.i - b.i).map((x) => x.m);
    }
    async function searchMarket(q, signal) {
      const base = [{ left: 'name,description', operation: 'match', right: q }];
      const sort = { sortBy: 'market_cap_basic', sortOrder: 'desc' };
      const [g, n] = await Promise.all([
        scan({ filter: base.concat([{ left: 'is_primary', operation: 'equal', right: true }, { left: 'type', operation: 'in_range', right: ['stock', 'dr', 'fund'] }]), columns: SEARCH_COLS, sort, range: [0, 60] }, signal),
        // Nordic B shares are not flagged "primary", so ask for those exchanges separately
        scan({ filter: base.concat([{ left: 'exchange', operation: 'in_range', right: NORDIC }, { left: 'type', operation: 'in_range', right: ['stock', 'fund'] }]), columns: SEARCH_COLS, sort, range: [0, 30] }, signal).catch((e) => { if (e.name === 'AbortError') throw e; return []; }),
      ]);
      const seen = new Set();
      return sortMatches(g.concat(n).filter((m) => (seen.has(m.sym) ? false : (seen.add(m.sym), true))), q);
    }
    const holdRows = () => { const h = dash.data('holdings'); return h.status === 'ok' ? h.data : []; };
    const ownMatch = (r) => ({ sym: r.sym, tk: r.sym.split(':')[1] || r.sym, name: r.name, exch: r.sym.split(':')[0], own: true, mcap: r.value_sek });
    function searchLocal(q) {
      const lq = q.toLowerCase();
      return sortMatches(holdRows().filter((r) => r.name.toLowerCase().includes(lq) || (r.sym.split(':')[1] || '').toLowerCase().includes(lq)).map(ownMatch), q);
    }
    function merge(local, market) {
      const own = local.slice(0, 5);
      const seen = new Set(own.map((m) => m.sym));
      const ownSyms = new Set(holdRows().map((r) => r.sym));
      const rest = market.filter((m) => !seen.has(m.sym)).map((m) => (ownSyms.has(m.sym) ? Object.assign({}, m, { own: true }) : m));
      return own.concat(rest).slice(0, 12);
    }

    const $ = (id) => document.getElementById(id);
    const input = $('lookup-q'), suggEl = $('lookup-sugg'), pickEl = $('lookup-pick'), statusEl = $('lookup-status'), resultWrap = $('lookup-result'), noteEl = $('lookup-note');
    if (!input) return;
    const tbody = document.querySelector('#lookup-tbl tbody');

    let token = 0, active = -1, curMatches = [], debounce = null, ctrl = null, lastQ = '', lastMatches = [];

    // ----- suggestion list under the box
    function closeSugg() { suggEl.replaceChildren(); suggEl.hidden = true; input.setAttribute('aria-expanded', 'false'); active = -1; curMatches = []; }
    function setActive(i) {
      active = i;
      Array.from(suggEl.children).forEach((li, k) => { li.classList.toggle('active', k === i); if (k === i) li.scrollIntoView({ block: 'nearest' }); });
    }
    function showSugg(matches) {
      curMatches = matches; active = -1;
      if (!matches.length) { closeSugg(); return; }
      suggEl.replaceChildren(...matches.map((m) => {
        const li = document.createElement('li'); li.setAttribute('role', 'option');
        const nm = document.createElement('span'); nm.className = 'nm'; nm.textContent = m.name;
        const tk = document.createElement('span'); tk.className = 'tk'; tk.textContent = m.tk + (m.exch ? ' · ' + m.exch : '');
        li.append(nm, tk);
        if (m.own) { const y = document.createElement('span'); y.className = 'yours'; y.textContent = 'yours'; li.appendChild(y); }
        li.addEventListener('mousedown', (e) => { e.preventDefault(); choose(m); });
        return li;
      }));
      suggEl.hidden = false; input.setAttribute('aria-expanded', 'true');
    }

    // ----- pick-list beside the box
    const pickMap = new Map();
    let pickMarkets = [], pickLoaded = false;
    function optgroup(label, list) {
      const g = document.createElement('optgroup'); g.label = label;
      list.forEach((m) => {
        if (!pickMap.has(m.sym)) pickMap.set(m.sym, m);
        const o = document.createElement('option'); o.value = m.sym; o.textContent = m.name + ' (' + m.tk + ')'; g.appendChild(o);
      });
      return g;
    }
    function drawPick() {
      pickMap.clear();
      const first = document.createElement('option'); first.value = '';
      first.textContent = lastQ && lastMatches.length ? lastMatches.length + ' match' + (lastMatches.length === 1 ? '' : 'es') + ' for “' + lastQ + '” — or browse…' : 'Or pick from a list…';
      const parts = [first];
      if (lastQ && lastMatches.length) parts.push(optgroup('Matches for “' + lastQ + '”', lastMatches));
      const own = holdRows().slice().sort((a, b) => a.name.localeCompare(b.name)).map(ownMatch);
      if (own.length) parts.push(optgroup('Your holdings', own));
      pickMarkets.forEach(([k, list]) => parts.push(optgroup('Largest in ' + k, list)));
      if (!pickLoaded) { const o = document.createElement('option'); o.disabled = true; o.textContent = 'Loading the largest companies per market…'; parts.push(o); }
      pickEl.replaceChildren(...parts);
      pickEl.value = '';
    }
    async function loadPickMarkets() {
      if (pickLoaded || loadPickMarkets.busy) return;
      loadPickMarkets.busy = true;
      const res = await Promise.all(PICK_MARKETS.map((m) => scan({
        filter: [{ left: 'type', operation: 'in_range', right: ['stock'] }, { left: 'typespecs', operation: 'has', right: ['common'] },
          { left: 'exchange', operation: 'in_range', right: m.ex }, { left: 'country', operation: 'equal', right: m.c }],
        columns: SEARCH_COLS, sort: { sortBy: 'market_cap_basic', sortOrder: 'desc' }, range: [0, 25],
      }).then((l) => [m.k, l.sort((a, b) => a.name.localeCompare(b.name))]).catch(() => null)));
      loadPickMarkets.busy = false;
      pickMarkets = res.filter((x) => x && x[1].length);
      pickLoaded = pickMarkets.length > 0;
      if (pickEl.value === '') drawPick();
    }

    // ----- result row
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
      let note = 'Alligator and Up/down vol need daily price history, which this board only keeps for your holdings, so they show “—” here. October, the outlooks and December are a simpler estimate from live TradingView readings, so treat them as more approximate than for your holdings.';
      if (!sectorFlow(d)) note += ' No sector money-flow data matched this stock’s market and sector, so its December view leaves that part out.';
      noteEl.textContent = note;
    }
    // a stock you already own: the exact "Every holding" row, with all its readings
    function renderOwn(r, live) {
      const td = (t, cls) => { const c = document.createElement('td'); if (cls) c.className = cls; c.textContent = t == null ? '—' : t; return c; };
      const chip = (label, cls) => { const c = document.createElement('td'); if (cls) c.className = cls; const sp = document.createElement('span'); sp.className = 'chip ' + chipCls(label); sp.textContent = label == null ? '—' : label; c.appendChild(sp); return c; };
      const hasLive = r.price_live != null;
      const price = hasLive ? r.price_live : live && live.close != null ? live.close : r.price;
      const chg = hasLive ? r.day_chg : live ? live.change : r.day_chg;
      const tr = document.createElement('tr');
      tr.append(
        nameTd(r.name, r.sym, null, null),
        td(fmtInt(r.value_sek), 'num'),
        td(price == null ? null : plain(price, price < 10 ? 3 : 2) + ' ' + r.cur + (hasLive && r.session === 'pre' ? ' · pre' : ''), 'num'),
        td(signed(chg, 2), 'num ' + tone(chg)),
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
      tbody.replaceChildren(tr);
      resultWrap.hidden = false;
      noteEl.textContent = '';
    }

    async function choose(m) {
      closeSugg();
      if (debounce) { clearTimeout(debounce); debounce = null; }
      if (ctrl) { ctrl.abort(); ctrl = null; }
      const my = ++token;
      input.value = m.name;
      const own = holdRows().find((r) => r.sym === m.sym);
      if (own) {
        renderOwn(own, null);
        statusEl.textContent = 'One of your holdings — the same full row as in “Every holding”.';
        if (own.price_live == null) { try { const d = await fetchOne(m.sym); if (my === token) renderOwn(own, d); } catch (e) { /* keep the baked row */ } }
        return;
      }
      statusEl.textContent = 'Loading ' + m.name + ' from TradingView…';
      resultWrap.hidden = true; noteEl.textContent = '';
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
      if (debounce) { clearTimeout(debounce); debounce = null; }
      if (ctrl) { ctrl.abort(); ctrl = null; }
      const my = ++token;
      lastQ = q;
      if (!q) { lastMatches = []; closeSugg(); statusEl.textContent = ''; drawPick(); return; }
      if (DIRECT.test(q)) {
        const Q = q.toUpperCase();
        lastMatches = [{ sym: Q, tk: Q.split(':')[1], name: Q, exch: Q.split(':')[0] }];
        showSugg(lastMatches); drawPick(); statusEl.textContent = 'Press Enter to open ' + Q + '.';
        return;
      }
      const local = searchLocal(q);
      lastMatches = merge(local, []);
      showSugg(lastMatches); drawPick();
      statusEl.textContent = 'Searching all markets…';
      debounce = setTimeout(async () => {
        debounce = null;
        ctrl = new AbortController();
        try {
          const market = await searchMarket(q, ctrl.signal);
          if (my !== token) return;
          lastMatches = merge(local, market);
          showSugg(lastMatches); drawPick();
          statusEl.textContent = lastMatches.length ? 'Pick a suggestion, or use the list beside the box.' : 'No matching stock found.';
        } catch (e) {
          if (my !== token || e.name === 'AbortError') return;
          statusEl.textContent = local.length ? 'Showing your holdings only — could not search TradingView right now.' : 'Could not search TradingView right now.';
        }
      }, 200);
    });
    input.addEventListener('focus', () => { if (input.value.trim() && lastMatches.length && suggEl.hidden) showSugg(lastMatches); loadPickMarkets(); });
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') { closeSugg(); return; }
      if (e.key === 'ArrowDown') { e.preventDefault(); if (suggEl.hidden && lastMatches.length) showSugg(lastMatches); setActive(Math.min(curMatches.length - 1, active + 1)); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); setActive(Math.max(0, active - 1)); }
      else if (e.key === 'Enter') {
        e.preventDefault();
        const list = curMatches.length ? curMatches : lastMatches;
        if (list.length) choose(list[active >= 0 ? active : 0]);
      }
    });
    pickEl.addEventListener('focus', loadPickMarkets);
    pickEl.addEventListener('change', () => { const m = pickMap.get(pickEl.value); if (m) choose(m); });
    document.addEventListener('click', (e) => { if (!e.target.closest('.lookup-combo')) closeSugg(); });
    drawPick();
    // fetch the per-market lists once the section is actually on screen (hidden tabs never intersect)
    if ('IntersectionObserver' in window) {
      const io = new IntersectionObserver((ents) => { if (ents.some((x) => x.isIntersecting)) { io.disconnect(); loadPickMarkets(); } });
      io.observe($('lookup'));
    } else loadPickMarkets();
  })();
"""

rep_between(
    "    async function searchSymbols(q) {\n",
    "\n  // ---------- crypto: My crypto holdings and Crypto strategy ----------",
    NEW_UI,
)

# the old helper is no longer used by anything
rep("    const stripEm = (s) => (s || '').replace(/<\\/?em>/g, '');\n", "", 1)

assert len(s) != orig_len
open(PATH, "w", encoding="utf-8").write(s)
print("patched OK, length", orig_len, "->", len(s))
