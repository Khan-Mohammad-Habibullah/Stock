#!/usr/bin/env python3
"""Read the positions out of a Nordnet "Innehav" export.

Only the per-stock lines are kept (name, quantity, today's change, value in
SEK). Everything else in the export -- account owner, account type, total
equity, cash, return history -- is ignored on purpose and never stored.

The same rules run in the browser (index.html, "Update holdings") with
pdf.js; this module is the reference used for exports sent in chat and for
testing that the two agree.

Usage:  python3 scripts/nordnet.py export.pdf   -> prints JSON rows
"""
import json
import re
import subprocess
import sys

# "   [A]   Name with spaces    qty    -1,23%    12 345"
NUM = r"\d{1,3}(?:[   ]\d{3})*"
ROW = re.compile(r"^\s*(?:[A-Z]\s{2,})?(?P<name>\S.*?\S)\s{2,}(?P<qty>" + NUM + r")\s{2,}(?P<day>[−+\-]?\d+,\d+)\s?%\s+(?P<val>" + NUM + r")\s*$")
TOTAL = re.compile(r"^\s*Totalt\s+(" + NUM + r")\s*$")
DATE = re.compile(r"^\s*(\d{1,2})/(\d{1,2})/(\d{2}),\s+(\d{1,2}):(\d{2})\s*([AP]M)")


def to_int(s):
    return int(re.sub(r"[   ]", "", s))


def parse_text(text):
    rows, total, stamp = [], None, None
    for line in text.splitlines():
        if stamp is None:
            m = DATE.match(line)
            if m:
                mo, d, y, hh, mm, ap = m.groups()
                h = int(hh) % 12 + (12 if ap == "PM" else 0)
                stamp = "20%s-%02d-%02d %02d:%s" % (y, int(mo), int(d), h, mm)
        m = TOTAL.match(line)
        if m:
            total = to_int(m.group(1))
            continue
        m = ROW.match(line)
        if m:
            rows.append(dict(name=m.group("name").strip(), qty=to_int(m.group("qty")),
                             day_pct=float(m.group("day").replace("−", "-").replace(",", ".")),
                             value_sek=to_int(m.group("val"))))
    # the same name can appear twice (bought in two lots); merge
    merged = {}
    for r in rows:
        if r["name"] in merged:
            merged[r["name"]]["qty"] += r["qty"]
            merged[r["name"]]["value_sek"] += r["value_sek"]
        else:
            merged[r["name"]] = dict(r)
    out = list(merged.values())
    check = sum(r["value_sek"] for r in out)
    return {"exported": stamp, "positions": out, "check": {"rows": len(rows), "sum_sek": check, "total_line": total,
                                                            "complete": total is not None and abs(check - total) <= max(5, len(out))}}


def parse_pdf(path):
    text = subprocess.check_output(["pdftotext", "-layout", path, "-"]).decode("utf-8")
    return parse_text(text)


if __name__ == "__main__":
    print(json.dumps(parse_pdf(sys.argv[1]), ensure_ascii=False, indent=1))
