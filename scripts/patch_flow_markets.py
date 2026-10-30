#!/usr/bin/env python3
""""Where money is moving": add Denmark, Finland, Germany and Canada next to
US, Sweden, Norway and Europe, matching the markets of "Strongest bullish
readings by market". Data comes from scripts/bake_market_flows.py; this
patch is the page side. Exact-text replace with count asserts, as in every
other scripts/patch_*.py."""

PATH = "index.html"
s = open(PATH, encoding="utf-8").read()
orig_len = len(s)


def rep(old, new, cnt=1):
    global s
    n = s.count(old)
    assert n == cnt, f"expected {cnt} occurrence(s), found {n}: {old[:80]!r}"
    s = s.replace(old, new)


# market buttons
rep("  const MKTS = ['US', 'Sweden', 'Norway', 'Europe'];",
    "  const MKTS = ['US', 'Sweden', 'Norway', 'Denmark', 'Finland', 'Germany', 'Canada', 'Europe'];")
# picking a holding switches the chart to its market -- any market the chart has
rep("    if (picked && ['US', 'Sweden', 'Norway', 'Europe'].includes(picked.flow_market)) stateMk = picked.flow_market;",
    "    if (picked && MKTS.includes(picked.flow_market)) stateMk = picked.flow_market;")
rep("        if (['US', 'Sweden', 'Norway', 'Europe'].includes(top0.flow_market)) stateMk = top0.flow_market;",
    "        if (MKTS.includes(top0.flow_market)) stateMk = top0.flow_market;")

# eight buttons: let the row wrap on narrow screens instead of running off the card
rep("  .seg button:focus-visible { outline: 2px solid var(--color-fg); outline-offset: -2px; }\n",
    "  .seg button:focus-visible { outline: 2px solid var(--color-fg); outline-offset: -2px; }\n"
    "  #mk-seg { flex-wrap: wrap; max-width: 100%; }\n"
    "  #mk-seg button { border-bottom: 1px solid var(--color-border-line); margin-bottom: -1px; }\n")

# "yours" amounts on the new markets' bars. Danish, Finnish and German holdings keep their
# reading against European large caps (as documented), but they also belong to their home
# market's sector, so count them there too.
rep("""      holdings.filter((r) => r.flow_sector).forEach((r) => {
        const k = r.flow_market + '|' + r.flow_sector;
        const g = m.get(k) || { market: r.flow_market, sector: r.flow_sector, n: 0, sek: 0 };
        g.n += 1; g.sek += Number(r.value_sek);
        m.set(k, g);
      });""",
    """      const HOME = { OMXCOP: 'Denmark', OMXHEX: 'Finland', XETR: 'Germany', TSX: 'Canada' };
      const add = (market, r) => {
        const k = market + '|' + r.flow_sector;
        const g = m.get(k) || { market, sector: r.flow_sector, n: 0, sek: 0 };
        g.n += 1; g.sek += Number(r.value_sek);
        m.set(k, g);
      };
      holdings.filter((r) => r.flow_sector).forEach((r) => {
        add(r.flow_market, r);
        const home = HOME[r.sym.split(':')[0]];
        if (home && home !== r.flow_market && !String(r.market).endsWith('ETF')) add(home, r);
      });""")
rep("    description: 'Number of holdings and value in SEK in each market and sector used for the money-flow reading (ETFs excluded).',",
    "    description: 'Number of holdings and value in SEK in each market and sector used for the money-flow reading, plus each Danish, Finnish and German holding under its home market (ETFs excluded).',")

# methods text
rep("Each sector is ranked against the others in its market (US companies worth over $2 billion; the biggest Swedish, Norwegian and Canadian companies; European companies worth over $5 billion, plus Danish and Finnish companies): ",
    "Each sector is ranked against the others in its market (US companies worth over $2 billion; the biggest Swedish, Norwegian and Canadian companies; European companies worth over $5 billion, plus Danish and Finnish companies). Denmark, Finland, Germany and Canada also have their own chart, each ranked among that market's largest companies (about 70, 80, 110 and 130 by market value, one share class per company), with sectors of at least three companies: ")
rep("with the same four hand matches as before.</p>",
    "with the same four hand matches as before. Danish, Finnish and German holdings keep their reading against European large caps; on their home market's chart they count towards the “what you hold” figure only.</p>")

# phones: sector names longer than the label column were clipped at the left edge, and the two
# axis captions overlapped (already so before this change; more markets make it likelier to be seen)
a = s.index("  // ---------- money flow by sector ----------")
b = s.index("  // ---------- December lists ----------")
sec = s[a:b]
for old, new in [
    ("svg.append('text').attr('x', x(-ext)).attr('y', 12)", "svg.append('text').attr('x', W < 480 ? 4 : x(-ext)).attr('y', 12)"),
    ("svg.append('text').attr('x', x(ext)).attr('y', 12)", "svg.append('text').attr('x', W < 480 ? W - 4 : x(ext)).attr('y', 12)"),
    (".text((r) => (r.group.length > 26 && labW < 170 ? r.group.slice(0, 24) + '…' : r.group));",
     ".text((r) => r.group)\n      .each(function () { const full = this.textContent; let k = full.length; while (k > 4 && this.getComputedTextLength() > m.l - 12) { k -= 1; this.textContent = full.slice(0, k).trimEnd() + '…'; } });"),
]:
    assert sec.count(old) == 1, old
    sec = sec.replace(old, new)
s = s[:a] + sec + s[b:]

# the stock lookup reads a looked-up stock's sector flow from its home market where one exists now
rep("    const MARKET_OF_EXCH = { NASDAQ: 'US', NYSE: 'US', AMEX: 'US', OMXSTO: 'Sweden', OSL: 'Norway', TSX: 'Canada' };",
    "    const MARKET_OF_EXCH = { NASDAQ: 'US', NYSE: 'US', AMEX: 'US', OMXSTO: 'Sweden', OSL: 'Norway', TSX: 'Canada', OMXCOP: 'Denmark', OMXHEX: 'Finland', XETR: 'Germany' };")

assert len(s) != orig_len
open(PATH, "w", encoding="utf-8").write(s)
print("patched OK", orig_len, "->", len(s))
