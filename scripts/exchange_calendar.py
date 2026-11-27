#!/usr/bin/env python3
"""Trading days per exchange (weekdays minus that exchange's holidays), rule-based so that future dates can be counted.

  trading_days_after(market, date, n)  -> the date n trading days after `date`
  is_open(market, date)

The rules are checked against the days that are really missing from the price history (python3 scripts/exchange_calendar.py --check FILE).
Half days are treated as full trading days. If an exchange changes its calendar, a date shown on the page can be a day off.
"""
import datetime as dt
import functools
import sys

D = dt.date


def easter(y):
    a, b, c = y % 19, y // 100, y % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mo = (h + l - 7 * m + 114) // 31
    da = (h + l - 7 * m + 114) % 31 + 1
    return D(y, mo, da)


def nth_weekday(y, m, wd, n):
    """n-th (1-based) weekday wd (Mon=0) of the month; n=-1 for the last."""
    if n > 0:
        d = D(y, m, 1)
        d += dt.timedelta((wd - d.weekday()) % 7)
        return d + dt.timedelta(7 * (n - 1))
    d = D(y + (m == 12), m % 12 + 1, 1) - dt.timedelta(1)
    return d - dt.timedelta((d.weekday() - wd) % 7)


def observed_us(d):
    """NYSE rule: a holiday on Saturday is taken on Friday, on Sunday on Monday."""
    if d.weekday() == 5:
        return d - dt.timedelta(1)
    if d.weekday() == 6:
        return d + dt.timedelta(1)
    return d


def midsummer_eve(y):
    d = D(y, 6, 19)
    return d + dt.timedelta((4 - d.weekday()) % 7)      # the Friday from 19 to 25 June


def _usa(y):
    e = easter(y)
    h = {observed_us(D(y, 7, 4)), nth_weekday(y, 1, 0, 3), nth_weekday(y, 2, 0, 3), e - dt.timedelta(2), nth_weekday(y, 5, 0, -1),
         nth_weekday(y, 9, 0, 1), nth_weekday(y, 11, 3, 4), observed_us(D(y, 12, 25))}
    if D(y, 1, 1).weekday() != 5:                        # NYSE does not give the Friday before when New Year's Day is a Saturday
        h.add(observed_us(D(y, 1, 1)))
    if y >= 2022:
        h.add(observed_us(D(y, 6, 19)))
    if y == 2025:
        h.add(D(2025, 1, 9))                             # national day of mourning
    return h


def _monday_after(d):
    return d + dt.timedelta((7 - d.weekday()) % 7) if d.weekday() >= 5 else d


def _canada(y):
    e = easter(y)
    h = {_monday_after(D(y, 1, 1)), nth_weekday(y, 2, 0, 3), e - dt.timedelta(2), nth_weekday(y, 5, 0, -1) if False else None,
         _monday_after(D(y, 7, 1)), nth_weekday(y, 8, 0, 1), nth_weekday(y, 9, 0, 1), nth_weekday(y, 10, 0, 2)}
    h.discard(None)
    d = D(y, 5, 24)                                       # Victoria Day: the Monday before 25 May
    h.add(d - dt.timedelta((d.weekday()) % 7))
    xmas, box = D(y, 12, 25), D(y, 12, 26)
    wd = xmas.weekday()
    if wd == 5:                                           # Christmas on Saturday: Monday and Tuesday
        h |= {D(y, 12, 27), D(y, 12, 28)}
    elif wd == 6:                                         # Sunday: Monday (Christmas) and Tuesday (Boxing Day)
        h |= {D(y, 12, 26), D(y, 12, 27)}
    elif wd == 4:                                         # Friday: Christmas Friday, Boxing Day Saturday -> Monday
        h |= {xmas, D(y, 12, 28)}
    else:
        h |= {xmas, box}
    return h


def _nordic_common(y, maundy=True):
    e = easter(y)
    h = {D(y, 1, 1), e - dt.timedelta(2), e + dt.timedelta(1), D(y, 5, 1), e + dt.timedelta(39), D(y, 12, 24), D(y, 12, 25), D(y, 12, 26), D(y, 12, 31)}
    if maundy:
        h.add(e - dt.timedelta(3))
    return h


def _sweden(y):
    e = easter(y)
    return _nordic_common(y, maundy=False) | {D(y, 1, 6), midsummer_eve(y), D(y, 6, 6)}


def _denmark(y):
    e = easter(y)
    h = _nordic_common(y) | {e + dt.timedelta(50), e + dt.timedelta(40), D(y, 6, 5)}   # Whit Monday, the Friday after Ascension, Constitution Day
    h.discard(D(y, 5, 1))                                # Copenhagen is open on 1 May
    if y == 2026:
        h.add(D(2026, 3, 23))                            # closed in the data, reason not known
    if y < 2024:
        h.add(e + dt.timedelta(26))                      # Great Prayer Day, abolished from 2024
    return h


def _norway(y):
    e = easter(y)
    return _nordic_common(y) | {D(y, 5, 17), e + dt.timedelta(50)}


def _finland(y):
    return _nordic_common(y, maundy=False) | {D(y, 1, 6), midsummer_eve(y), D(y, 12, 6)}


def _germany(y):
    e = easter(y)
    return {D(y, 1, 1), e - dt.timedelta(2), e + dt.timedelta(1), D(y, 5, 1), D(y, 12, 24), D(y, 12, 25), D(y, 12, 26), D(y, 12, 31)}


RULES = dict(USA=_usa, Canada=_canada, Sweden=_sweden, Denmark=_denmark, Norway=_norway, Finland=_finland, Germany=_germany)


@functools.lru_cache(maxsize=None)
def holidays(market, year):
    return {d for d in RULES[market](year) if d.weekday() < 5}


def is_open(market, d):
    return d.weekday() < 5 and d not in holidays(market, d.year)


def trading_days_after(market, d, n):
    """The date n trading days after d (d itself does not count)."""
    k = 0
    while k < n:
        d += dt.timedelta(1)
        if is_open(market, d):
            k += 1
    return d


def trading_days_between(market, a, b):
    """Number of trading days after a up to and including b (0 if b <= a)."""
    n, d = 0, a
    while d < b:
        d += dt.timedelta(1)
        if is_open(market, d):
            n += 1
    return n


def upcoming(market, d, n):
    out = []
    while len(out) < n:
        d += dt.timedelta(1)
        if is_open(market, d):
            out.append(d.isoformat())
    return out


def _check(dump):
    """Weekdays on which none of a market's stocks has a bar (closed days in the data) against the rules above."""
    import collections
    sys.path.insert(0, __file__.rsplit("/", 1)[0])
    import setups_data as SD
    Dd = SD.load(dump)
    bad = 0
    for mk, rows in Dd["universe"].items():
        have = collections.Counter()
        syms = [r["sym"] for r in rows if r["sym"] in Dd["bars"]]
        for s in syms:
            for t in Dd["bars"][s]["t"]:
                have[D(1970, 1, 1) + dt.timedelta(int(t))] += 1
        lo, hi = D(2021, 12, 1), max(have)
        d = lo
        missing, extra = [], []
        while d <= hi:
            if d.weekday() < 5:
                n = have.get(d, 0)
                closed = n < 0.2 * len(syms)
                if closed and is_open(mk, d):
                    missing.append((d.isoformat(), n))
                if (not closed) and (not is_open(mk, d)):
                    extra.append((d.isoformat(), n))
            d += dt.timedelta(1)
        print(mk, "closed in the data but open by the rules:", missing, "| open in the data but closed by the rules:", extra)
        bad += len(missing) + len(extra)
    print("mismatches:", bad)


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--check":
        _check(sys.argv[2])
    else:
        print(trading_days_after("Sweden", D(2026, 11, 26), 42))
