#!/usr/bin/env python3
"""One-off: data/etf_facts.json for the daily rebuild.

  facts     -- each fund's fact-sheet card as it is on the board now (issuer
               data, dated on the card; not refetched daily)
  top       -- the fund's biggest holdings as symbols with fund weights (from
               the card's "top" line), for the look-through money flow
  exposure  -- the "same company directly and through your funds" table as
               fund weights, so it rescales with each day's fund values
"""
import json
import re

s = open("index.html", encoding="utf-8").read()
ds = lambda k: json.JSONDecoder().raw_decode(s, s.index('"%s":[' % k) + len('"%s":' % k))[0]
E, X = ds("etfs"), ds("exposure")

TOP = {
    "XETR:VVSM": [("NASDAQ:AMD", 11.0), ("NYSE:TSM", 10.0), ("NASDAQ:MU", 9.9), ("NASDAQ:NVDA", 9.7), ("NASDAQ:AVGO", 9.2), ("EURONEXT:ASML", 8.4), ("NASDAQ:INTC", 6.7)],
    "XETR:QDVE": [("NASDAQ:NVDA", 19.2), ("NASDAQ:AAPL", 18.3), ("NASDAQ:MSFT", 15.5), ("NASDAQ:AVGO", 7.2), ("NASDAQ:MU", 4.3), ("NASDAQ:AMD", 3.2), ("NASDAQ:INTC", 1.9)],
    "XETR:ESIT": [("EURONEXT:ASML", 32.3), ("XETR:SAP", 17.4), ("XETR:IFX", 10.6), ("OMXHEX:NOKIA", 6.2), ("NASDAQ:NBIS", 5.7), ("EURONEXT:ASM", 5.7), ("EURONEXT:STMPA", 4.0)],
    "XETR:SPYH": [("SIX:ROG", 17.8), ("SIX:NOVN", 15.3), ("LSE:AZN", 14.0), ("OMXCOP:NOVO_B", 7.0), ("LSE:GSK", 5.5), ("EURONEXT:SAN", 5.0)],
    "XETR:EXV8": [("EURONEXT:DG", 14.8), ("SIX:HOLN", 9.4), ("EURONEXT:SGO", 8.6), ("OMXSTO:ASSA_B", 7.9), ("SIX:SIKA", 7.8), ("EURONEXT:FER", 5.8), ("SIX:GEBN", 4.9)],
    "XETR:W1TB": [("NASDAQ:CRWD", 7.9), ("NASDAQ:OKTA", 7.2), ("NYSE:S", 6.2), ("NASDAQ:PANW", 6.0), ("NASDAQ:FTNT", 5.7), ("NASDAQ:DDOG", 5.7), ("NASDAQ:ZS", 5.0)],
    # issuer page unavailable; approximate, roughly equal weights (as the card says)
    "XETR:ASWE": [("NYSE:TSM", 5), ("NASDAQ:MSFT", 5), ("NASDAQ:GOOGL", 5), ("EURONEXT:ASML", 5), ("NASDAQ:AMD", 5), ("NASDAQ:CSCO", 5), ("MIL:PRY", 5), ("SIX:SDZ", 5), ("NYSE:TT", 5)],
}
FUND = {"VanEck Semiconductor": "XETR:VVSM", "iShares S&P 500 IT": "XETR:QDVE", "iShares Europe IT": "XETR:ESIT", "SPDR MSCI Europe Health Care UCITS": "XETR:SPYH",
        "WisdomTree Cybersecurity UCITS": "XETR:W1TB", "Saturna Al-Kawthar": "XETR:ASWE"}
DIRECT = {"NVIDIA": ["NASDAQ:NVDA"], "Broadcom": ["NASDAQ:AVGO"], "Intel": ["NASDAQ:INTC"], "AstraZeneca": ["OMXSTO:AZN"], "Hexagon B": ["OMXSTO:HEXA_B"],
          "Zscaler": ["NASDAQ:ZS"], "Semiconductors (theme, at least)": ["NASDAQ:AVGO", "NASDAQ:NVDA", "NASDAQ:INTC", "NASDAQ:AMKR", "NASDAQ:QCOM", "NASDAQ:MRVL", "NASDAQ:AEIS"]}
val = {e["sym"]: e["value_sek"] for e in E}
exposure = []
for x in X:
    via = []
    for it in x["via"].split(";"):
        m = re.match(r"\s*(.*?) ([\d,]+) SEK$", it)
        nm, amt = m.group(1), int(m.group(2).replace(",", ""))
        sym = next(v for k, v in FUND.items() if nm.startswith(k))
        via.append(dict(label=nm, fund=sym, share=round(amt / val[sym], 5)))
    exposure.append(dict(company=x["company"], direct=DIRECT[x["company"]], via=via))
facts = {e["sym"]: {k: v for k, v in e.items() if k not in ("value_sek", "flow", "flow_score", "oct_signal", "o1y", "o5y", "view", "view_why", "r12m")} for e in E}
json.dump(dict(facts=facts, top={k: [dict(sym=a, w=b) for a, b in v] for k, v in TOP.items()}, exposure=exposure),
          open("data/etf_facts.json", "w"), ensure_ascii=False, indent=1)
print(len(facts), "funds;", sum(len(v) for v in TOP.values()), "look-through names;", len(exposure), "exposure rows")
for x in exposure: print(x["company"], [(v["fund"], v["share"]) for v in x["via"]])
