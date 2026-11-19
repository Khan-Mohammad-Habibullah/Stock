#!/usr/bin/env python3
"""Sell or add by December: clicking a stock now jumps to its row in "Every holding" (the page scrolls to the row, which flashes),
instead of only selecting it and scrolling the detail card into view."""
PATH = "index.html"
s = open(PATH, encoding="utf-8").read()
assert "jumpToHolding" not in s, "already patched"


def rep(old, new, cnt=1):
    global s
    n = s.count(old)
    assert n == cnt, f"expected {cnt}, found {n}: {old[:90]!r}"
    s = s.replace(old, new)


rep("  .tch { display: block; }\n", """  .tch { display: block; }
  @keyframes rowflash { 0% { background: color-mix(in srgb, var(--series-0) 35%, transparent); } 100% { background: transparent; } }
  tr.flash td { animation: rowflash 2.2s ease-out; }
""")
rep("  // ---------- December lists ----------\n", """  // ---------- December lists ----------
  // a click in a December list selects the stock and takes you to its row in "Every holding"
  function jumpToHolding(sym) {
    select(sym, true);
    const tr = tbody.querySelector('tr[data-key="' + CSS.escape(sym) + '"]');
    if (!tr) return;
    const wrap = tbody.closest('.tbl-wrap');
    if (wrap) wrap.scrollTop = Math.max(0, tr.offsetTop - wrap.clientHeight / 3);
    tr.scrollIntoView({ block: 'center', behavior: 'smooth' });
    tr.classList.remove('flash'); void tr.offsetWidth; tr.classList.add('flash');
  }
""")
rep("""      li.addEventListener('click', () => select(r.sym, true));
      li.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); select(r.sym, true); } });
      return li;
    };
    const none =""", """      li.addEventListener('click', () => jumpToHolding(r.sym));
      li.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); jumpToHolding(r.sym); } });
      return li;
    };
    const none =""")
open(PATH, "w", encoding="utf-8").write(s)
print("patched", len(s))
