#!/usr/bin/env python3
"""A "Halal" indicator beside every stock: Every holding, Former holdings, the Strategy tab's Strongest bullish readings and Look up any stock.

An estimated Shariah screen (scripts/halal.py, not Musaffa's own result: Musaffa's terms forbid automated retrieval and republishing of its
screening). The chip links to the stock's Musaffa page for the official result. Holdings and former holdings carry the screen from the
daily rebuild (row fields halal, halal_why); the screen table and the lookup compute it in the browser from the same TradingView fields with
the same rules (HALAL_RULES, copied here from halal.RULES). Exact-text replace with count asserts, as in the other scripts/patch_*.py."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import halal as HL

PATH = "index.html"
s = open(PATH, encoding="utf-8").read()
assert "halalChip" not in s, "already patched"


def rep(old, new, cnt=1):
    global s
    n = s.count(old)
    assert n == cnt, f"expected {cnt}, found {n}: {old[:90]!r}"
    s = s.replace(old, new)


R = json.dumps(HL.RULES, ensure_ascii=False)

# ---- CSS
rep("  .tch { display: block; }\n", """  .tch { display: block; }
  .hl-wrap { display: block; margin-top: 3px; line-height: 1.2; }
  .hl { display: inline-block; padding: 1px 7px; border-radius: 999px; font-size: 11px; font-weight: 600; text-decoration: none; white-space: nowrap; }
  a.hl:hover { text-decoration: underline; }
  .hl.ok { background: color-mix(in srgb, var(--color-ok) 18%, transparent); color: var(--color-ok); }
  .hl.bad { background: color-mix(in srgb, var(--color-bad) 18%, transparent); color: var(--color-bad); }
  .hl.mid { background: color-mix(in srgb, var(--series-1) 20%, transparent); color: var(--series-1); }
  .hl.na { background: color-mix(in srgb, var(--color-fg) 8%, transparent); color: var(--color-fg-muted); font-weight: 400; }
""")

# ---- shared JS: the screen, the Musaffa link and the chip (before the Candle touch block, ahead of every table and the IIFEs)
JS = r"""  // ---------- Halal indicator: an estimated Shariah screen, linked to the stock's Musaffa page ----------
  // Same rules as scripts/halal.py (copied from halal.RULES by scripts/patch_halal.py). Not Musaffa's own result: its terms forbid automated retrieval.
  const HALAL_RULES = __RULES__;
  // d: { industry, mcap, debt, cash, cashEq, fund } in the same currency (the screener's USD) -> { halal, halal_why }
  function halalOf(d) {
    const R = HALAL_RULES;
    if (d.fund) return { halal: 'Not screened', halal_why: 'Fund: whether it is halal depends on every holding, so it is not screened here. Check the fund on Musaffa.' };
    const ind = d.industry || '';
    if (R.haram.indexOf(ind) >= 0) return { halal: 'Not halal', halal_why: 'Business: ' + ind + ' (interest-based finance, insurance, tobacco, alcohol or gambling)' };
    const mc = d.mcap, pct = (x) => (x == null || !mc ? null : x / mc * 100);
    const debt = pct(d.debt), cash = pct(d.cash != null ? d.cash : d.cashEq);
    const f0 = (v) => v.toFixed(0) + '%';
    const fig = 'debt ' + (debt == null ? 'n/a' : f0(debt)) + ' and cash ' + (cash == null ? 'n/a' : f0(cash)) + ' of market value (limit ' + R.debt_max.toFixed(0) + '%)';
    const over = [];
    if (debt != null && debt >= R.debt_max) over.push('debt ' + f0(debt) + ' of market value (limit ' + R.debt_max.toFixed(0) + '%)');
    if (cash != null && cash >= R.cash_max) over.push('cash and short-term investments ' + f0(cash) + ' of market value (limit ' + R.cash_max.toFixed(0) + '%)');
    if (over.length) return { halal: 'Not halal', halal_why: 'Ratios: ' + over.join('; ') };
    const why = [];
    if (R.doubtful.indexOf(ind) >= 0) why.push('business: ' + ind + ' (mixed or questionable activities)');
    if (debt == null || cash == null || !mc) why.push('a figure is missing (' + fig + ')');
    if (debt != null && debt >= R.debt_max - R.near) why.push('debt close to the limit (' + f0(debt) + ')');
    if (cash != null && cash >= R.cash_max - R.near) why.push('cash close to the limit (' + f0(cash) + ')');
    if (why.length) { const t = why.join('; '); return { halal: 'Doubtful', halal_why: t.charAt(0).toUpperCase() + t.slice(1) }; }
    return { halal: 'Halal', halal_why: 'Business: ' + (ind || 'n/a') + '; ' + fig };
  }
  // TradingView symbol (EXCHANGE:TICKER) -> the stock's page on musaffa.com (Yahoo-style ticker; share classes "VOLV B.ST")
  const MUSAFFA_SUFFIX = { OMXSTO: '.ST', OSL: '.OL', OMXCOP: '.CO', OMXHEX: '.HE', XETR: '.DE', TSX: '.TO', LSE: '.L', SIX: '.SW', BME: '.MC', MIL: '.MI', VIE: '.VI' };
  function musaffaUrl(sym) {
    const i = String(sym || '').indexOf(':'); if (i < 0) return null;
    const ex = sym.slice(0, i); let tk = sym.slice(i + 1).replace(/\.$/, '');
    const suf = MUSAFFA_SUFFIX[ex] || '';
    if (suf) tk = tk.replace(/[_-]/g, ' ');
    return 'https://musaffa.com/stock/' + encodeURIComponent(tk + suf) + (suf ? '' : '/');
  }
  // h: { halal, halal_why } (a holdings row, or the result of halalOf); sym: for the Musaffa link. Returns a block with the chip, or null.
  function halalChip(h, sym) {
    if (!h || !h.halal) return null;
    const cls = { 'Halal': 'ok', 'Not halal': 'bad', 'Doubtful': 'mid', 'Not screened': 'na' }[h.halal] || 'na';
    const url = h.halal === 'Not screened' ? null : musaffaUrl(sym);
    const el = document.createElement(url ? 'a' : 'span'); el.className = 'hl ' + cls;
    el.textContent = h.halal === 'Not screened' ? 'Fund' : h.halal;
    el.title = h.halal_why + '\n\nAn estimate from market data (business activity, debt and cash against market value), not Musaffa’s result.' + (url ? ' Click for this stock on Musaffa.' : '');
    if (url) { el.href = url; el.target = '_blank'; el.rel = 'noopener noreferrer'; el.addEventListener('click', (e) => e.stopPropagation()); }
    const w = document.createElement('span'); w.className = 'hl-wrap'; w.appendChild(el);
    return w;
  }

"""
JS = JS.replace("__RULES__", R)
rep("  // ---------- Candle touch column: the daily candle", JS + "  // ---------- Candle touch column: the daily candle")

# ---- nameTd takes the halal source as a 5th argument
rep("""  function nameTd(label, sym, cls, onSelect) {
    const c = document.createElement('td'); c.className = cls || 'nm';
    const b = document.createElement('button'); b.type = 'button'; b.className = 'chart-link'; b.textContent = label;
    b.addEventListener('click', (e) => { e.stopPropagation(); if (onSelect) onSelect(); openChart(sym, label); });
    c.appendChild(b);
    return c;
  }""", """  function nameTd(label, sym, cls, onSelect, halal) {
    const c = document.createElement('td'); c.className = cls || 'nm';
    const b = document.createElement('button'); b.type = 'button'; b.className = 'chart-link'; b.textContent = label;
    b.addEventListener('click', (e) => { e.stopPropagation(); if (onSelect) onSelect(); openChart(sym, label); });
    c.appendChild(b);
    const hc = halalChip(halal, sym); if (hc) c.appendChild(hc);
    return c;
  }""")

# ---- Every holding, Former holdings, lookup (owned stock and any stock)
rep("        nameTd(r.name, r.sym, null, () => select(r.sym, 'monthly')),", "        nameTd(r.name, r.sym, null, () => select(r.sym, 'monthly'), r),")
rep("          nameTd(r.name, r.sym, null, null),\n", "          nameTd(r.name, r.sym, null, null, r),\n")
rep("        nameTd(r.name, r.sym, null, null),\n", "        nameTd(r.name, r.sym, null, null, r),\n")
rep("        nameTd(d.name, d.sym, null, null),\n", "        nameTd(d.name, d.sym, null, null, halalOf({ industry: d.industry, mcap: d.mcap, debt: d.debt, cash: d.cash, cashEq: d.cashEq, fund: d.fund })),\n")
# lookup columns and parse
rep("      'high', 'low', 'close[1]', 'close[2]', 'high[1]', 'low[1]', 'high[2]', 'low[2]', 'SMA50[1]', 'SMA50[2]', 'SMA200[1]', 'SMA200[2]'];",
    "      'high', 'low', 'close[1]', 'close[2]', 'high[1]', 'low[1]', 'high[2]', 'low[2]', 'SMA50[1]', 'SMA50[2]', 'SMA200[1]', 'SMA200[2]',\n      'type', 'total_debt_fq', 'cash_n_short_term_invest_fq', 'cash_n_equivalents_fq'];")
rep("        pe: num(g('price_earnings_ttm')), rec: num(g('recommendation_mark')), target: num(g('price_target_average')),\n      };\n      // the latest bar",
    "        pe: num(g('price_earnings_ttm')), rec: num(g('recommendation_mark')), target: num(g('price_target_average')),\n        fund: g('type') === 'fund', debt: num(g('total_debt_fq')), cash: num(g('cash_n_short_term_invest_fq')), cashEq: num(g('cash_n_equivalents_fq')),\n      };\n      // the latest bar")

# ---- screen table (Strategy): columns and the chip beside the ticker
rep("      'recommendation_mark', 'price_target_average', 'sector', 'update_mode', 'premarket_close', 'premarket_change', 'current_session'];",
    "      'recommendation_mark', 'price_target_average', 'sector', 'update_mode', 'premarket_close', 'premarket_change', 'current_session',\n      'industry', 'total_debt_fq', 'cash_n_short_term_invest_fq', 'cash_n_equivalents_fq'];")
rep("rec: num(g('recommendation_mark')), target: num(g('price_target_average')), sector: g('sector'), mode: g('update_mode'),",
    "rec: num(g('recommendation_mark')), target: num(g('price_target_average')), sector: g('sector'), mode: g('update_mode'),\n        industry: g('industry'), debt: num(g('total_debt_fq')), cash: num(g('cash_n_short_term_invest_fq')), cashEq: num(g('cash_n_equivalents_fq')),")
rep("        if (own.has(d.sym)) { const o = document.createElement('span'); o.className = 'own'; o.textContent = 'in your holdings'; nm.appendChild(o); }\n        const macdTxt",
    "        if (own.has(d.sym)) { const o = document.createElement('span'); o.className = 'own'; o.textContent = 'in your holdings'; nm.appendChild(o); }\n        const hc = halalChip(halalOf({ industry: d.industry, mcap: d.mcap, debt: d.debt, cash: d.cash, cashEq: d.cashEq }), d.sym); if (hc) nm.appendChild(hc);\n        const macdTxt")

# ---- notes: under the Every holding table and in the methods
rep('    <p class="hs-note" id="tch-note">',
    '''    <p class="hs-note" id="halal-note"><b>Halal.</b> The chip under each name is an estimate, not <a href="https://musaffa.com/" target="_blank" rel="noopener noreferrer">Musaffa</a>'s own result (its terms of use do not allow automated retrieval of its screening), so click the chip for that stock's page on Musaffa and read the official answer there. <b>Not halal</b>: conventional banking, brokers, insurance, tobacco, alcohol or gambling, or debt, or cash and short-term investments, of 30% or more of the company's market value. <b>Doubtful</b>: defence, entertainment and media, restaurants, food retail, hotels, investment holding or asset management and similar mixed activities, a ratio within 5 points of its limit, or a figure the data source does not give. <b>Halal</b>: none of those. Funds are marked <b>Fund</b> and not screened. The share of income from interest (5% in the AAOIFI standard) is not checked, and the ratios use today's market value, so Musaffa and this estimate can differ. Updated with the daily rebuild.</p>
    <p class="hs-note" id="tch-note">''')
rep("      <p><b>Candle touch column.</b>", """      <p><b>Halal indicator.</b> An estimated Shariah screen on the AAOIFI model: first the business (conventional finance, insurance, tobacco, alcohol and gambling fail; defence, media, restaurants, food retail, hotels, investment holding and similar are doubtful), then two ratios against the company's market value, interest-bearing debt under 30% and cash plus short-term investments under 30%, with a ratio within 5 points of the limit or a missing figure marked doubtful. It runs on TradingView's industry and balance-sheet figures in the daily rebuild for your holdings and live in the browser for the Strategy tab and the lookup. It is not Musaffa's result: the chip links to the stock's Musaffa page for that, and the two can differ (Musaffa also tests income from interest and averages market value over 36 months).</p>
      <p><b>Candle touch column.</b>""")
open(PATH, "w", encoding="utf-8").write(s)
print("patched", len(s))
