#!/usr/bin/env python3
"""One-off: create data/portfolio.json, the file the daily rebuild reads.

  positions  -- current holdings (symbol, display name, quantity), from the
                holdings now on the page (28 Oct 2026 Nordnet export)
  former     -- every stock that was on the board at some point and is not
                any more, found by reading the holdings in every committed
                version of index.html; "gone_by" is the date of the first
                Nordnet export it was missing from
  names      -- Nordnet name -> TradingView symbol, so later exports can be
                matched automatically
"""
import json
import subprocess

S = "/tmp/claude-0/-home-claude/f28ba201-572d-5ba2-b1b7-0d31666d5e3c/scratchpad/"


def holdings_at(rev):
    s = subprocess.check_output(["git", "show", rev + ":index.html"]).decode("utf-8", "ignore")
    i = s.find('"holdings":[')
    if i < 0:
        return None
    return json.JSONDecoder().raw_decode(s, i + len('"holdings":'))[0]


cur = json.loads(json.dumps(holdings_at("HEAD")))
revs = [l.split()[0] for l in subprocess.check_output(["git", "log", "--reverse", "--format=%h %ad", "--date=short", "--", "index.html"]).decode().splitlines()]
dates = dict(l.split() for l in subprocess.check_output(["git", "log", "--format=%h %ad", "--date=short", "--", "index.html"]).decode().splitlines())

# which commit applied which export, so "gone by" can name the export date
EXPORT_OF = {"69e0331": "2026-10-16", "de18525": "2026-10-16", "c940265": "2026-10-28"}
seen, last_row, gone_by = {}, {}, {}
prev = None
for h in revs:
    H = holdings_at(h)
    if not H:
        continue
    syms = {r["sym"] for r in H}
    for r in H:
        last_row[r["sym"]] = r
    if prev is not None:
        for s in prev - syms:
            gone_by.setdefault(s, EXPORT_OF.get(h, dates[h]))
    prev = syms
cur_syms = {r["sym"] for r in cur}
former = []
for s, d in sorted(gone_by.items(), key=lambda kv: (kv[1], kv[0])):
    if s in cur_syms:
        continue
    r = last_row[s]
    former.append(dict(sym=s, name=r["name"], market=r["market"], cur=r["cur"], gone_by=d, last_qty=r.get("qty"), note=r.get("note")))

names = json.load(open(S + "nn/full_name2sym.json"))
names.update({"Octave Intelligence": "NASDAQ:OCTV", "Octave Intelligence SDB": "NASDAQ:OCTV", "AQ Group": "OMXSTO:AQ", "Fuchs": "XETR:FPE",
              "Bavarian Nordic": "OMXCOP:BAVA", "Getinge B": "OMXSTO:GETI_B", "Exxon Mobil": "NYSE:XOM", "Ambu": "OMXCOP:AMBU_B",
              "BW Energy Limited": "OSL:BWE", "Medistim": "OSL:MEDI", "NTG Nordic Transport Group": "OMXCOP:NTG",
              "Vaisala A": "OMXHEX:VAIAS", "Sap SE": "XETR:SAP", "Whitecap Resources Inc": "TSX:WCP", "Puuilo": "OMXHEX:PUUILO",
              "NVIDIA": "NASDAQ:NVDA", "UiPath A": "NYSE:PATH"})
missing = cur_syms - set(names.values())
assert not missing, missing

positions = [dict(sym=r["sym"], name=r["name"], qty=r["qty"], market=r["market"], cur=r["cur"]) for r in sorted(cur, key=lambda r: -r["value_sek"])]
out = dict(updated="2026-10-28 14:41", source="Nordnet export 28 Oct 2026", positions=positions, former=former,
           names=dict(sorted(names.items())))
json.dump(out, open("data/portfolio.json", "w"), ensure_ascii=False, indent=1)
print(len(positions), "positions;", len(former), "former:", [(f["sym"], f["gone_by"]) for f in former])
