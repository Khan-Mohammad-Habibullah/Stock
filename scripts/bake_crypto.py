#!/usr/bin/env python3
"""Patch the freshly fetched crypto data (data/crypto_holdings.json,
data/crypto_monthly.json, data/crypto_extracted.txt, written by
update_crypto.py) into the published index.html in place, without touching
anything else on the page -- the stock side is untouched.

index.html embeds the crypto datasets as two JSON array literals inside a
<script> tag (look for `"crypto_holdings":[...]` and `"crypto_monthly":[...]`
inside the inlined `datasets` object) and shows the extraction date in a
`<p class="hs-extracted">` line in the "Crypto holdings" and "Crypto
strategy" page headers. Both are replaced here by exact text position, not
by re-running the full build pipeline (which isn't part of this repo).
"""
import datetime
import json
import re

HERE = __file__.rsplit("/", 1)[0]
INDEX = HERE + "/../index.html"


def load(name):
    with open(HERE + "/../data/%s.json" % name) as f:
        return json.load(f)


def dumps(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def find_matching_bracket(s, open_pos):
    """s[open_pos] must be '['. Returns the index just past the matching ']',
    respecting nesting and JSON string literals (so brackets inside strings,
    e.g. in a coin's name, don't throw off the count)."""
    assert s[open_pos] == "["
    depth = 0
    i = open_pos
    in_str = False
    esc = False
    while i < len(s):
        c = s[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == "[":
                depth += 1
            elif c == "]":
                depth -= 1
                if depth == 0:
                    return i + 1
        i += 1
    raise ValueError("no matching closing bracket found")


def replace_dataset(html, key, new_value_json):
    marker = '"%s":' % key
    pos = html.index(marker)
    start = pos + len(marker)
    assert html[start] == "[", "expected a JSON array right after %r" % marker
    end = find_matching_bracket(html, start)
    return html[:start] + new_value_json + html[end:]


def replace_extracted(html, pane_id, text):
    pane_start = html.index('id="%s"' % pane_id)
    badge_start = html.index('<p class="hs-extracted">', pane_start)
    badge_end = html.index("</p>", badge_start) + len("</p>")
    new_badge = '<p class="hs-extracted"><span class="dot"></span>Data last extracted: %s</p>' % text
    return html[:badge_start] + new_badge + html[badge_end:]


def main():
    holdings = load("crypto_holdings")
    monthly = load("crypto_monthly")
    with open(HERE + "/../data/crypto_extracted.txt") as f:
        iso_date = f.read().strip()
    pretty = datetime.date.fromisoformat(iso_date).strftime("%-d %B %Y")

    html = open(INDEX, encoding="utf-8").read()
    html = replace_dataset(html, "crypto_holdings", dumps(holdings))
    html = replace_dataset(html, "crypto_monthly", dumps(monthly))
    html = replace_extracted(html, "crypto-top", pretty)
    html = replace_extracted(html, "cryptostrategy-top", pretty)

    open(INDEX, "w", encoding="utf-8").write(html)
    print("baked", len(holdings), "coins and", len(monthly), "monthly rows into index.html, dated", pretty)


if __name__ == "__main__":
    main()
