#!/usr/bin/env python3
"""Adds their own market buttons above Table B and Table C of "Setups before 20% rises". The top row of buttons still sets every table at once;
the rows above B and C then override that table alone (Table C's choice also drives "Removed in the last 5 rebuilds")."""
PATH = "index.html"
s = open(PATH, encoding="utf-8").read()
if "su-tabs-b" in s:
    print("already patched"); raise SystemExit


def rep(old, new, cnt=1):
    global s
    assert s.count(old) == cnt, (s.count(old), old[:70])
    s = s.replace(old, new)


rep("const SU = { mkt: 'All', q: '',", "const SU = { mkt: 'All', mB: 'All', mC: 'All', q: '',")
rep("const inMkt = (m) => SU.mkt === 'All' || m === SU.mkt;", "const inMkt = (m, w) => { const x = w || SU.mkt; return x === 'All' || m === x; };")
rep("SU.study.examples.filter((e) => inMkt(e.market) &&", "SU.study.examples.filter((e) => inMkt(e.market, SU.mB) &&")
rep("(c.complete || SU.near) && inMkt(c.market) &&", "(c.complete || SU.near) && inMkt(c.market, SU.mC) &&")
rep("SU.cur.removed.filter((r) => inMkt(r.market) &&", "SU.cur.removed.filter((r) => inMkt(r.market, SU.mC) &&")
rep('    <p class="hs-note" id="su-b-note"></p>\n', '    <p class="hs-note" id="su-b-note"></p>\n    <div class="scr-tabs" id="su-tabs-b" role="group" aria-label="Market for Table B"></div>\n')
rep('    <p class="hs-note" id="su-c-note"></p>\n', '    <p class="hs-note" id="su-c-note"></p>\n    <div class="scr-tabs" id="su-tabs-c" role="group" aria-label="Market for Table C"></div>\n')
rep("      document.querySelectorAll('#su-tabs button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.m === SU.mkt)));",
    "      [['su-tabs', 'mkt'], ['su-tabs-b', 'mB'], ['su-tabs-c', 'mC']].forEach(([id, key]) => document.querySelectorAll('#' + id + ' button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.m === SU[key]))));")
rep("""    ['All'].concat(MARKETS).forEach((m) => {
      const b = document.createElement('button'); b.type = 'button'; b.dataset.m = m; b.textContent = m === 'All' ? 'All markets' : m;
      b.addEventListener('click', () => { SU.mkt = m; SU.A.open = SU.B.open = SU.C.open = null; drawAll(); });
      $('su-tabs').appendChild(b);
    });""", """    ['All'].concat(MARKETS).forEach((m) => {
      const label = m === 'All' ? 'All markets' : m;
      const mk = (id, on) => { const b = document.createElement('button'); b.type = 'button'; b.dataset.m = m; b.textContent = label; b.addEventListener('click', () => { on(); drawAll(); }); $(id).appendChild(b); };
      mk('su-tabs', () => { SU.mkt = SU.mB = SU.mC = m; SU.A.open = SU.B.open = SU.C.open = null; });
      mk('su-tabs-b', () => { SU.mB = m; SU.B.open = null; });
      mk('su-tabs-c', () => { SU.mC = m; SU.C.open = null; });
    });""")
open(PATH, "w", encoding="utf-8").write(s)
print("ok")
