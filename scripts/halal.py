"""An estimated Shariah screen (AAOIFI-style) for the "Halal" indicator on the board. NOT Musaffa's result: Musaffa's terms forbid
automated retrieval and republishing of its screening, so the board runs this screen on its own market data and links each stock to
its Musaffa page for the official result.

Business activity, from TradingView's industry:
    Not halal  conventional banking, brokers, insurance, tobacco, alcohol, gambling
    Doubtful   mixed or questionable activities (defence, entertainment and media, restaurants and food retail, hotels,
               investment holding and asset management, managed health care, consumer credit and leasing)
Financial ratios, against the market value (market capitalisation today; AAOIFI averages 36 months):
    Not halal  interest-bearing debt >= 30% of market value, or cash + short-term investments >= 30%
    Doubtful   either ratio within 5 points of its limit, or a figure missing
    Not applied: the share of income from interest (5%), which the data source does not give.
Funds (ETFs) are "Not screened": a fund's result depends on every holding.
The same rules are copied into index.html by scripts/patch_halal.py (RULES below); keep them in step."""

RULES = dict(
    debt_max=30.0, cash_max=30.0, near=5.0,
    haram=["Major Banks", "Regional Banks", "Savings Banks", "Investment Banks/Brokers", "Life/Health Insurance", "Multi-Line Insurance",
           "Property/Casualty Insurance", "Specialty Insurance", "Insurance Brokers/Services", "Tobacco", "Beverages: Alcoholic", "Casinos/Gaming"],
    doubtful=["Financial Conglomerates", "Finance/Rental/Leasing", "Investment Managers", "Investment Trusts/Mutual Funds", "Managed Health Care",
              "Aerospace & Defense", "Movies/Entertainment", "Broadcasting", "Cable/Satellite TV", "Restaurants", "Food Retail",
              "Drugstore Chains", "Hotels/Resorts/Cruise lines"],
)
FIELDS = ["total_debt_fq", "cash_n_short_term_invest_fq", "cash_n_equivalents_fq"]   # extra TradingView screener columns it needs


def _pct(x, mcap):
    return None if x is None or not mcap else x / mcap * 100


def screen(F, is_etf=False):
    """F: TradingView screener row (industry, market_cap_basic, total_debt_fq, cash_n_short_term_invest_fq, cash_n_equivalents_fq).
    Returns {"halal": "Halal" | "Not halal" | "Doubtful" | "Not screened", "halal_why": short reason}."""
    R = RULES
    if is_etf:
        return dict(halal="Not screened", halal_why="Fund: whether it is halal depends on every holding, so it is not screened here. Check the fund on Musaffa.")
    ind = F.get("industry") or ""
    if ind in R["haram"]:
        return dict(halal="Not halal", halal_why="Business: %s (interest-based finance, insurance, tobacco, alcohol or gambling)" % ind)
    mc = F.get("market_cap_basic")
    debt = _pct(F.get("total_debt_fq"), mc)
    cash_raw = F.get("cash_n_short_term_invest_fq")
    if cash_raw is None:
        cash_raw = F.get("cash_n_equivalents_fq")
    cash = _pct(cash_raw, mc)
    fig = "debt %s and cash %s of market value (limit %d%%)" % (
        "n/a" if debt is None else "%.0f%%" % debt, "n/a" if cash is None else "%.0f%%" % cash, R["debt_max"])
    over = []
    if debt is not None and debt >= R["debt_max"]: over.append("debt %.0f%% of market value (limit %d%%)" % (debt, R["debt_max"]))
    if cash is not None and cash >= R["cash_max"]: over.append("cash and short-term investments %.0f%% of market value (limit %d%%)" % (cash, R["cash_max"]))
    if over:
        return dict(halal="Not halal", halal_why="Ratios: " + "; ".join(over))
    why = []
    if ind in R["doubtful"]:
        why.append("business: %s (mixed or questionable activities)" % ind)
    if debt is None or cash is None or not mc:
        why.append("a figure is missing (" + fig + ")")
    if debt is not None and debt >= R["debt_max"] - R["near"]: why.append("debt close to the limit (%.0f%%)" % debt)
    if cash is not None and cash >= R["cash_max"] - R["near"]: why.append("cash close to the limit (%.0f%%)" % cash)
    if why:
        t = "; ".join(why)
        return dict(halal="Doubtful", halal_why=t[:1].upper() + t[1:])
    return dict(halal="Halal", halal_why="Business: %s; %s" % (ind or "n/a", fig))
