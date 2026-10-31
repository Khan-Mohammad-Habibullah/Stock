#!/usr/bin/env python3
"""Apply holdings files from inbox/ to data/portfolio.json.

A holdings file is what the board's "Update holdings" button saves (or what
Claude writes from an export sent in chat): positions only -- name,
quantity, value in SEK -- read from a Nordnet "Innehav" export. The export
itself never leaves the person's computer.

  * names are matched to symbols with the stored Nordnet name map; a new
    name is matched automatically when exactly one listed stock with that
    name has a price that fits value / quantity, otherwise it is reported
  * stocks missing from the export move to the former holdings (dated)
  * a former holding that reappears moves back
  * an export that does not add up (sum of rows vs Nordnet's own total, as
    checked when the file was made) or that would drop more than half of the
    holdings is refused, so a bad read can never wipe the board
Prints a summary; the result is also stored in data/portfolio.json
("last_inbox") for the page to show.
"""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import board_lib as L

EX_MARKET = {"NASDAQ": "US", "NYSE": "US", "AMEX": "US", "OMXSTO": "Sweden", "OSL": "Norway", "OMXCOP": "Denmark", "OMXHEX": "Finland",
             "XETR": "Germany", "TSX": "Canada"}


def resolve(name, unit_sek, rates):
    """A symbol for a new Nordnet name, or (None, reason)."""
    q = name
    for suf in (" A", " B", " C", " SDB", " Inc", " Ltd", " AB", " ASA"):
        if q.endswith(suf):
            q = q[: -len(suf)]
    filt = [{"left": "name,description", "operation": "match", "right": q},
            {"left": "type", "operation": "in_range", "right": ["stock", "dr", "fund"]}]
    cands = []
    for extra in ([{"left": "is_primary", "operation": "equal", "right": True}],
                  [{"left": "exchange", "operation": "in_range", "right": ["OMXSTO", "OSL", "OMXCOP", "OMXHEX", "XETR"]}]):
        try:
            j = L.retry(L.scan, {"filter": filt + extra, "columns": L.SCAN_COLS, "sort": {"sortBy": "market_cap_basic", "sortOrder": "desc"}, "range": [0, 25]})
            cands += list(L.scan_rows(j).values())
        except Exception as e:
            return None, "search failed: %s" % e
    fits = []
    for c in cands:
        if not c.get("close") or not c.get("currency"):
            continue
        try:
            sek = c["close"] * L.usd_per(c["currency"], rates) / rates["SEK"]
        except KeyError:
            continue
        if abs(sek / unit_sek - 1) <= 0.06:
            fits.append((abs(sek / unit_sek - 1), c))
    fits.sort(key=lambda x: x[0])
    syms = list(dict.fromkeys(c["sym"] for _, c in fits))
    if len(syms) == 1 or (len(syms) > 1 and fits[0][0] < 0.015 and fits[1][0] > 0.03):
        return fits[0][1], None
    return None, ("no listed stock with that name has a matching price" if not syms else "several possible matches: " + ", ".join(syms[:4]))


def main():
    files = sorted(glob.glob("inbox/*.json"))
    if not files:
        print("inbox empty"); return 0
    PF = json.load(open("data/portfolio.json", encoding="utf-8"))
    rates = L.fx_to_usd()
    for path in files:
        D = json.load(open(path, encoding="utf-8"))
        rows = D.get("positions") or [dict(name=p[0], qty=p[1], value_sek=p[2]) for p in D.get("p", [])]
        res = dict(file=os.path.basename(path), exported=D.get("exported"), read=len(rows), added=[], sold=[], back=[], changed=0, auto_matched=[], unmatched=[], refused=None)
        if not D.get("complete", D.get("check", {}).get("complete", False)):
            res["refused"] = "the rows did not add up to Nordnet's own total, so the file was not used"
        cur = {p["sym"]: p for p in PF["positions"]}
        new = {}
        if not res["refused"]:
            for r in rows:
                sym = PF["names"].get(r["name"])
                meta = None
                if not sym:
                    c, why = resolve(r["name"], r["value_sek"] / max(r["qty"], 1), rates)
                    if c is None:
                        res["unmatched"].append("%s (%s)" % (r["name"], why)); continue
                    sym, meta = c["sym"], c
                    PF["names"][r["name"]] = sym
                    res["auto_matched"].append("%s -> %s" % (r["name"], sym))
                p = new.setdefault(sym, dict(sym=sym, qty=0))
                p["qty"] += r["qty"]
                old = cur.get(sym) or next((f for f in PF["former"] if f["sym"] == sym), None)
                if old:
                    p.update(name=old["name"], market=old["market"], cur=old["cur"])
                elif meta:
                    ex = sym.split(":")[0]
                    mk = EX_MARKET.get(ex, meta.get("country") or "Europe")
                    if meta.get("type") == "fund":
                        mk = "US ETF" if any(w in r["name"].upper() for w in ("S&P", "US ", "NASDAQ", "USA")) else "Europe ETF"
                    p.update(name=r["name"], market=mk, cur=meta.get("currency"))
            if len(new) < 0.5 * len(cur):
                res["refused"] = "only %d of %d holdings were recognised, so the file was not used" % (len(new), len(cur))
        if not res["refused"]:
            day = (D.get("exported") or "")[:10] or None
            for sym, p in cur.items():
                if sym not in new:
                    PF["former"].append(dict(sym=sym, name=p["name"], market=p["market"], cur=p["cur"], gone_by=day, last_qty=p["qty"]))
                    res["sold"].append(p["name"])
            back = [f for f in PF["former"] if f["sym"] in new]
            PF["former"] = [f for f in PF["former"] if f["sym"] not in new]
            res["back"] = [f["name"] for f in back]
            res["added"] = [p["name"] for s, p in new.items() if s not in cur and s not in {f["sym"] for f in back}]
            res["changed"] = sum(1 for s, p in new.items() if s in cur and cur[s]["qty"] != p["qty"])
            order = {p["sym"]: i for i, p in enumerate(PF["positions"])}
            PF["positions"] = sorted(new.values(), key=lambda p: order.get(p["sym"], 10 ** 6))
            PF["updated"] = D.get("exported") or PF.get("updated")
            PF["source"] = "Nordnet export" + (" of " + D["exported"] if D.get("exported") else "")
        PF["last_inbox"] = res
        print(json.dumps(res, ensure_ascii=False))
        os.remove(path)
    json.dump(PF, open("data/portfolio.json", "w"), ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
