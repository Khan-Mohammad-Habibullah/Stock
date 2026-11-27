#!/usr/bin/env python3
"""index.html: four new columns in Table C (estimated success rate, target price, typical date if reached, deadline), live check line, explanation."""
import re
p = "index.html"
s = open(p, encoding="utf-8").read()
if "su-c-live" in s:
    raise SystemExit("already patched")


def rep(a, b, c=1):
    global s
    assert s.count(a) == c, (s.count(a), a[:90])
    s = s.replace(a, b)


rep('''    <div class="tbl-wrap"><table class="hold scr" id="su-c"><thead></thead><tbody></tbody></table></div>
''', '''    <div class="tbl-wrap"><table class="hold scr" id="su-c"><thead></thead><tbody></tbody></table></div>
    <p class="hs-note" id="su-c-live"></p>
    <p class="hs-note" id="su-c-how"></p>
''')

# helpers
rep('''    const candRows = () => {
      if (!SU.cur) return [];''', '''    const todayIso = () => { const d = new Date(); return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0'); };
    const daysLeft = (c) => { // trading days after today up to and including the deadline, on the stock's own exchange
      const cal = SU.cur && SU.cur.calendar && SU.cur.calendar[c.market]; if (!cal || !c.deadline) return null;
      const t = todayIso(); return cal.filter((d) => d > t && d <= c.deadline).length;
    };
    const lines = (parts, cls) => { const x = document.createElement('td'); if (cls) x.className = cls; parts.forEach((t, i) => { const d = document.createElement('div'); if (i) d.className = 'hs-note'; d.style.margin = '0'; d.textContent = t; x.appendChild(d); }); return x; };
    const candRows = () => {
      if (!SU.cur) return [];''')

NEW_COLS = '''      { k: 'est', label: 'Estimated success rate', cls: 'sm', dir: -1, val: (c) => (c.est ? c.est.est : null), cell: (c) => {
        if (!c.est) return td('—', 'sm');
        const x = lines([fmtPct(c.est.est, 0), 'range ' + (c.est.lo * 100).toFixed(0) + '–' + (c.est.hi * 100).toFixed(0) + '% · ' + (c.est.n == null ? '' : c.est.n.toLocaleString('en-GB') + ' past cases of ' + setupName(c.est.setup))], 'sm');
        if (c.est.kind !== 'model') { const ch = document.createElement('span'); ch.className = 'chip n'; ch.textContent = 'setup average'; ch.title = 'The model did not score better than the setup’s own historical success rate on the check years, so that rate is shown.'; x.firstChild.appendChild(document.createTextNode(' ')); x.firstChild.appendChild(ch); }
        x.title = 'Estimated success rate: the model’s estimate of how often a case like this reached +20% within 42 trading days in the past, with a range of the typical gap between estimate and actual on the check years. The stock-list warning above applies to it too.';
        return x; }, tip: 'Estimated from past cases only (see the note under the table). The range is the typical gap between estimated and actual rates on the check years. Capped at the highest actual rate seen in any group.' },
      { k: 'tgt', label: 'Target price', cls: 'num sm', val: (c) => c.target, cell: (c) => (c.target == null ? td('—', 'num sm') : lines([pxTxt(c.target, c.cur), 'needs ' + sgn((c.target / px(c) - 1) * 100) + ' from now'], 'num sm')), tip: 'The close on the setup day plus 20%. Fixed while the stock stays in the table.' },
      { k: 'typ', label: 'Typical date if reached', cls: 'sm', val: (c) => (c.typ ? c.typ[1] : null), cell: (c) => (!c.typ ? td('—', 'sm') : lines([dTxt(c.typ[1]), dTxt(c.typ[0]).replace(/ \\d{4}$/, '') + ' – ' + dTxt(c.typ[2])], 'sm')), tip: 'Among past cases of this setup that reached +20%, half got there by this date. It is not a forecast that this stock will reach the target.' },
      { k: 'dl', label: 'Deadline', cls: 'sm', val: (c) => c.deadline, cell: (c) => {
        if (!c.deadline) return td('—', 'sm');
        const n = daysLeft(c); const x = lines([dTxt(c.deadline), n == null ? '' : n <= 0 ? 'passed: leaves at the next rebuild' : n + ' trading day' + (n === 1 ? '' : 's') + ' left'], 'sm');
        if (n != null && n < 10) x.classList.add('hl-am');
        return x; }, tip: 'Setup day plus 42 trading days on the stock’s exchange. After that the setup counts as missed and the row is removed at the next daily rebuild.' },
'''
rep('''      { k: 'why', label: 'Why it matches (best setup)',''', NEW_COLS + '''      { k: 'why', label: 'Why it matches (best setup)',''')

# detail: setup day line
rep('''      c.ms.forEach((m) => {
        const h = document.createElement('p'); h.className = 'hs-note'; h.style.cssText = 'margin:10px 0 4px;color:var(--color-fg)';''', '''      if (c.target != null) w.append(para('Setup day ' + dTxt(c.stock_entry_bar) + ' at a close of ' + pxTxt(c.stock_entry_close, c.cur) + ' · target ' + pxTxt(c.target, c.cur) + ' · deadline ' + dTxt(c.deadline) + (c.est ? ' · estimated success rate ' + fmtPct(c.est.est, 0) + ' (range ' + (c.est.lo * 100).toFixed(0) + '–' + (c.est.hi * 100).toFixed(0) + '%, ' + (c.est.kind === 'model' ? 'model' : 'setup average') + ')' : '') + (c.typ ? ' · typical date if reached ' + dTxt(c.typ[1]) + ' (middle half of past cases: ' + dTxt(c.typ[0]) + ' to ' + dTxt(c.typ[2]) + ')' : '') + '.'));
      c.ms.forEach((m) => {
        const h = document.createElement('p'); h.className = 'hs-note'; h.style.cssText = 'margin:10px 0 4px;color:var(--color-fg)';''')

# warning applies to estimates
rep("""'⚠ Setups a) to g) (marked “new setup”): ' + NEW_WARN;""", """'⚠ Setups a) to g) (marked “new setup”): ' + NEW_WARN + ' The estimated success rates are built from the same past cases, so this applies to them too.';""")

# removed reasons
rep("reached +20%, setup failed (a close below its invalidation level), or conditions no longer met.", "reached +20%, setup failed (a close below its invalidation level), deadline passed (42 trading days after the setup day) or conditions no longer met.")

# live line + explanation
rep('''        $('su-rm-note').textContent =''', '''        const le = cu.live_est, ml = st && st.model;
        const lv = $('su-c-live');
        if (le && le.resolved >= 30) {
          lv.className = 'hs-note' + (le.warn ? ' su-warn' : '');
          lv.textContent = (le.warn ? '⚠ The estimates are running too high: ' : 'Live check of the estimates: ') + 'of ' + le.resolved + ' candidates that have been judged since they were first listed, the average estimated success rate was ' + fmtPct(le.avg_est, 0) + ' and ' + fmtPct(le.actual, 0) + ' actually reached +20% within 42 trading days.';
        } else { lv.className = 'hs-note'; lv.textContent = 'Live check of the estimates: ' + (le ? le.resolved : 0) + ' candidates judged so far; the comparison with what actually happened is shown from 30.'; }
        if (ml) $('su-c-how').textContent = 'How it is worked out: ' + (ml.kind === 'model'
          ? 'the estimated success rate comes from a statistical model fitted on past cases of all twelve setups before ' + dTxt(ml.cut) + ' (the setup, daily range, distance from the 52-week high, RSI, volume, the market washout reading, market and size) and kept because on the later cases it scored better (' + ml.brier_model.toFixed(3) + ' against ' + ml.brier_setup.toFixed(3) + ' for the setup’s plain historical rate; lower is better)'
          : 'the model did not score better than each setup’s plain historical rate on the cases since ' + dTxt(ml.cut) + ', so the setup’s historical success rate is shown as “setup average”')
          + ', never above the highest actual rate in any of its five check groups, rounded to the nearest 5%, with a range of the average gap between estimated and actual there (' + (ml.gap * 100).toFixed(1) + ' points). The typical date takes the past cases of the stock’s highest-rate setup that reached +20% and counts the trading days they needed (the middle half is shown under the date), on the stock’s own exchange calendar from the setup day; the target is the setup-day close plus 20% and the deadline is 42 trading days after the setup day. All of this is built from past cases in a stock list that leaves out companies that fell and dropped out, so it describes the past and is not a forecast.';
        $('su-rm-note').textContent =''')
open(p, "w", encoding="utf-8").write(s)
print("ok")
