#!/usr/bin/env python3
"""Bake data/market_flows.json (from scripts/fetch_market_flows.py) into index.html.

- flows: replaces every row of the markets in the file (the old Canada rows
  were a thin 4-sector set) and appends the new ones
- flow_picks: same, for the companies named under each bar
- TSX:WCP (the one holding whose sector reading comes from Canada): its
  sector/industry flow and December view are refreshed from the new Canada
  rows with the board's own December formula, after first checking that the
  formula reproduces its current stored December score
Every other dataset is left byte-identical (asserted).
"""
import json

PATH = "index.html"
D = json.load(open("data/market_flows.json", encoding="utf-8"))
s = open(PATH, encoding="utf-8").read()
orig = s
NEW_MKTS = sorted(D["markets"].keys())
assert set(NEW_MKTS) == {"Denmark", "Finland", "Germany", "Canada"}, NEW_MKTS
for k, m in D["markets"].items():
    assert "failed" not in m, (k, m)


def span(key):
    i = s.index('"%s":[' % key) + len('"%s":' % key)
    val, end = json.JSONDecoder().raw_decode(s, i)
    return i, end, val


def dump(v):
    return json.dumps(v, separators=(",", ":"), ensure_ascii=False)


def put(key, val):
    global s
    i, j, old = span(key)
    assert s[i:j] == dump(old), "serialisation of %s does not round-trip" % key
    s = s[:i] + dump(val) + s[j:]


cl = lambda x, a: max(-a, min(a, x))


def stock_label(P, tv):
    if P >= 0.9: return "Strong inflow" if tv >= 20 else "Money coming in"
    if P >= 0.8: return "Money coming in"
    if P <= 0.1: return "Strong outflow" if tv >= 20 else "Money leaving"
    if P <= 0.2: return "Money leaving"
    return "No clear direction"


def december(r):
    fs = r["flow_score"] or 0
    use_s = r["sflow"] not in ("Too thinly traded to tell", "Too new to tell")
    dsc = round(cl(fs / 2.5, 2) + (cl(r["sflow_score"] / 2.5, 2) if use_s else 0) + cl(r["oct_score"] / 3, 1.5) + cl(r["o1y_score"] / 2, 1.5), 1)
    if dsc <= -3.5: dl = "Consider selling by December"
    elif dsc <= -2: dl = "Consider trimming"
    elif dsc >= 4 and r["o1y"] in ("Positive", "Leaning positive") and r["o5y"] not in ("Negative", "Leaning negative"): dl = "Consider adding"
    elif dsc >= 2: dl = "Hold, add on dips"
    else: dl = "Hold"
    return dsc, dl


# ---------- flows ----------
_, _, FL = span("flows")
keep = [f for f in FL if f["market"] not in NEW_MKTS]
FIELDS = ["market", "level", "group", "sector", "n", "r1m", "r3m", "mom_rel", "acc_rank", "tv_share", "tv_usd_m", "breadth", "vratio", "flow_score", "flow", "top"]
new = [{k: f[k] for k in FIELDS} for f in D["flows"]]
put("flows", keep + new)

# ---------- holdings: TSX:WCP ----------
_, _, H = span("holdings")
owned = {r["sym"] for r in H}
fidx = {(f["market"], f["level"], f["group"]): f for f in new}
for r in H:
    if r["sym"] != "TSX:WCP":
        continue
    assert december(r) == (r["dec_score"], r["december"]), ("December formula does not reproduce the stored value", december(r), r["dec_score"], r["december"])
    ex = D["extra"].get("TSX:WCP", {})
    f = fidx.get(("Canada", "industry", ex.get("industry"))) or fidx.get(("Canada", "sector", ex.get("sector") or r["flow_sector"]))
    assert f, ("no Canada row for WCP", ex)
    before = (r["flow"], r["flow_score"], r["december"])
    r.update(flow_market="Canada", flow_group=f["group"], flow_sector=f["sector"], flow=f["flow"], flow_score=f["flow_score"])
    r["dec_score"], r["december"] = december(r)
    r["dec_why"] = "money in its sector: %s; money in the stock itself: %s; October signal %s; 1-year outlook %s" % (
        r["flow"].lower(), r["sflow"].lower(), r["oct_signal"].lower(), r["o1y"].lower())
    print("WCP", before, "->", (r["flow"], r["flow_score"], r["december"]), "via", f["level"], f["group"])
put("holdings", H)

# the ETF table mirrors each holding's flow/December; WCP is not an ETF, so nothing to do there
_, _, E = span("etfs")
assert all(e["sym"] != "TSX:WCP" for e in E)

# ---------- flow_picks ----------
BASIS = {"in": "strongest buying among its most-traded companies", "out": "heaviest selling among its most-traded companies", "none": "its most-traded companies"}
SUF = (" Class A", " Class B", " Class C", " Inc.", " Inc", " Corporation", " Corp.", " plc", " AB", " ASA", " SE", " N.V.", " AG", " S.A.", " Ltd.", " Limited", " Holdings", ", Inc.", " Group", " A/S", " Oyj", " Abp", " Oyj Abp")
_, _, PK = span("flow_picks")
keepp = [p for p in PK if p["market"] not in NEW_MKTS]
newp = []
for p in D["picks"]:
    short = p["full_name"]
    for _ in range(2):
        for suf in SUF:
            if short.endswith(suf):
                short = short[: -len(suf)]
    newp.append(dict(market=p["market"], sector=p["sector"], rank=p["rank"], name=short.strip().rstrip(","), full_name=p["full_name"],
                     ticker=p["ticker"], sym=p["sym"], industry=p["industry"], stock_flow=stock_label(p["P"], p["tv_msek"]),
                     stock_score=round((p["P"] - 0.5) * 15, 1), mom_rel=p["mom_rel"], tv_usd_m=p["tv_usd_m"], owned=p["sym"] in owned,
                     basis=BASIS[p["basis"]]))
put("flow_picks", keepp + newp)

# ---------- nothing else may change ----------
for key in ["monthly", "exposure", "etfs", "crypto_holdings", "crypto_monthly"]:
    i0 = orig.index('"%s":[' % key); i1 = s.index('"%s":[' % key)
    a = json.JSONDecoder().raw_decode(orig, i0 + len('"%s":' % key))[0]
    b = json.JSONDecoder().raw_decode(s, i1 + len('"%s":' % key))[0]
    assert a == b, key
open(PATH, "w", encoding="utf-8").write(s)
print("flows:", len(FL), "->", len(keep) + len(new), "| picks:", len(PK), "->", len(keepp) + len(newp))
for m in NEW_MKTS:
    print(m, D["markets"][m]["companies"], "companies,", sum(1 for f in new if f["market"] == m and f["level"] == "sector"), "sectors,",
          sum(1 for f in new if f["market"] == m and f["level"] == "industry"), "industries,", len(D["markets"][m]["errors"]), "fetch errors")
