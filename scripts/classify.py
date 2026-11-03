#!/usr/bin/env python3
"""Standard classification of a holding for the portfolio breakdown pie charts.

Sector / industry group / industry use the GICS names (the 11 sectors, 25 industry
groups and the industry names S&P and MSCI publish). TradingView's screener has its
own, different taxonomy, so each TradingView industry is translated to a GICS
industry here, and a short list of well-known companies where TradingView's label
differs from GICS is set by hand (OVERRIDES). This is an approximation of GICS, not
the licensed data, and a company TradingView files oddly and that is not in
OVERRIDES will show under the closest industry.

Also gives country of domicile, region, company size (market cap) and stock/ETF.
"""

# --- GICS building blocks: (sector, industry group, industry) ---
IT, CS, CD, STP, HC, FIN, IND, MAT, EN, UT, RE = ("Information Technology", "Communication Services", "Consumer Discretionary", "Consumer Staples",
                                                  "Health Care", "Financials", "Industrials", "Materials", "Energy", "Utilities", "Real Estate")
G = {
    "software": (IT, "Software & Services", "Software"),
    "itservices": (IT, "Software & Services", "IT Services"),
    "semis": (IT, "Semiconductors & Semiconductor Equipment", "Semiconductors"),
    "semiequip": (IT, "Semiconductors & Semiconductor Equipment", "Semiconductor Materials & Equipment"),
    "hardware": (IT, "Technology Hardware & Equipment", "Technology Hardware, Storage & Peripherals"),
    "commequip": (IT, "Technology Hardware & Equipment", "Communications Equipment"),
    "electronic": (IT, "Technology Hardware & Equipment", "Electronic Equipment, Instruments & Components"),
    "telecom": (CS, "Telecommunication Services", "Diversified Telecommunication Services"),
    "wireless": (CS, "Telecommunication Services", "Wireless Telecommunication Services"),
    "media": (CS, "Media & Entertainment", "Media"),
    "advert": (CS, "Media & Entertainment", "Media"),
    "entertain": (CS, "Media & Entertainment", "Entertainment"),
    "interactive": (CS, "Media & Entertainment", "Interactive Media & Services"),
    "autos": (CD, "Automobiles & Components", "Automobiles"),
    "autoparts": (CD, "Automobiles & Components", "Auto Components"),
    "household": (CD, "Consumer Durables & Apparel", "Household Durables"),
    "leisure": (CD, "Consumer Durables & Apparel", "Leisure Products"),
    "apparel": (CD, "Consumer Durables & Apparel", "Textiles, Apparel & Luxury Goods"),
    "hotels": (CD, "Consumer Services", "Hotels, Restaurants & Leisure"),
    "divconsumer": (CD, "Consumer Services", "Diversified Consumer Services"),
    "specretail": (CD, "Consumer Discretionary Distribution & Retail", "Specialty Retail"),
    "broadline": (CD, "Consumer Discretionary Distribution & Retail", "Broadline Retail"),
    "disc_dist": (CD, "Consumer Discretionary Distribution & Retail", "Distributors"),
    "food_retail": (STP, "Consumer Staples Distribution & Retail", "Consumer Staples Distribution & Retail"),
    "food": (STP, "Food, Beverage & Tobacco", "Food Products"),
    "bev": (STP, "Food, Beverage & Tobacco", "Beverages"),
    "tobacco": (STP, "Food, Beverage & Tobacco", "Tobacco"),
    "hhprod": (STP, "Household & Personal Products", "Household Products"),
    "personal": (STP, "Household & Personal Products", "Personal Care Products"),
    "hcequip": (HC, "Health Care Equipment & Services", "Health Care Equipment & Supplies"),
    "hcprov": (HC, "Health Care Equipment & Services", "Health Care Providers & Services"),
    "hctech": (HC, "Health Care Equipment & Services", "Health Care Technology"),
    "pharma": (HC, "Pharmaceuticals, Biotechnology & Life Sciences", "Pharmaceuticals"),
    "biotech": (HC, "Pharmaceuticals, Biotechnology & Life Sciences", "Biotechnology"),
    "lifesci": (HC, "Pharmaceuticals, Biotechnology & Life Sciences", "Life Sciences Tools & Services"),
    "banks": (FIN, "Banks", "Banks"),
    "capmkts": (FIN, "Financial Services", "Capital Markets"),
    "diversfin": (FIN, "Financial Services", "Diversified Financial Services"),
    "consfin": (FIN, "Financial Services", "Consumer Finance"),
    "payments": (FIN, "Financial Services", "Transaction & Payment Processing Services"),
    "insurance": (FIN, "Insurance", "Insurance"),
    "reit": (RE, "Equity Real Estate Investment Trusts (REITs)", "Equity Real Estate Investment Trusts (REITs)"),
    "realestate": (RE, "Real Estate Management & Development", "Real Estate Management & Development"),
    "aero": (IND, "Capital Goods", "Aerospace & Defense"),
    "building": (IND, "Capital Goods", "Building Products"),
    "construction": (IND, "Capital Goods", "Construction & Engineering"),
    "electrical": (IND, "Capital Goods", "Electrical Equipment"),
    "conglom": (IND, "Capital Goods", "Industrial Conglomerates"),
    "machinery": (IND, "Capital Goods", "Machinery"),
    "tradingdist": (IND, "Capital Goods", "Trading Companies & Distributors"),
    "commsupplies": (IND, "Commercial & Professional Services", "Commercial Services & Supplies"),
    "profservices": (IND, "Commercial & Professional Services", "Professional Services"),
    "air": (IND, "Transportation", "Passenger Airlines"),
    "freight": (IND, "Transportation", "Air Freight & Logistics"),
    "marine": (IND, "Transportation", "Marine Transportation"),
    "rail": (IND, "Transportation", "Ground Transportation"),
    "ground": (IND, "Transportation", "Ground Transportation"),
    "infra": (IND, "Transportation", "Transportation Infrastructure"),
    "chemicals": (MAT, "Materials", "Chemicals"),
    "construction_mat": (MAT, "Materials", "Construction Materials"),
    "packaging": (MAT, "Materials", "Containers & Packaging"),
    "metals": (MAT, "Materials", "Metals & Mining"),
    "paper": (MAT, "Materials", "Paper & Forest Products"),
    "oilgas": (EN, "Energy", "Oil, Gas & Consumable Fuels"),
    "energyequip": (EN, "Energy", "Energy Equipment & Services"),
    "electric": (UT, "Utilities", "Electric Utilities"),
    "gasutil": (UT, "Utilities", "Gas Utilities"),
    "water": (UT, "Utilities", "Water Utilities"),
    "ipp": (UT, "Utilities", "Independent Power and Renewable Electricity Producers"),
    "multiutil": (UT, "Utilities", "Multi-Utilities"),
}

# --- TradingView industry -> GICS block ---
TV_INDUSTRY = {
    # Commercial Services
    "Advertising/Marketing Services": "advert", "Commercial Printing/Forms": "commsupplies", "Financial Publishing/Services": "profservices",
    "Miscellaneous Commercial Services": "commsupplies", "Personnel Services": "profservices", "Publishing: Books/Magazines": "media",
    "Publishing: Newspapers": "media",
    # Communications
    "Major Telecommunications": "telecom", "Specialty Telecommunications": "telecom", "Wireless Telecommunications": "wireless",
    # Consumer Durables
    "Automotive Aftermarket": "autoparts", "Consumer Electronics/Appliances": "household", "Electronics/Appliances": "household",
    "Home Furnishings": "household", "Homebuilding": "household", "Motor Vehicles": "autos", "Recreational Products": "leisure", "Tools & Hardware": "machinery",
    # Consumer Non-Durables
    "Apparel/Footwear": "apparel", "Beverages: Alcoholic": "bev", "Beverages: Non-Alcoholic": "bev", "Food: Major Diversified": "food",
    "Food: Meat/Fish/Dairy": "food", "Food: Specialty/Candy": "food", "Household/Personal Care": "hhprod", "Tobacco": "tobacco", "Textiles": "apparel",
    # Consumer Services
    "Casinos/Gaming": "hotels", "Cable/Satellite TV": "media", "Broadcasting": "media", "Hotels/Resorts/Cruise lines": "hotels",
    "Media Conglomerates": "media", "Movies/Entertainment": "entertain", "Other Consumer Services": "divconsumer", "Restaurants": "hotels",
    # Distribution
    "Electronics Distributors": "tradingdist", "Food Distributors": "food_retail", "Medical Distributors": "hcprov", "Wholesale Distributors": "tradingdist",
    # Electronic Technology
    "Aerospace & Defense": "aero", "Computer Communications": "commequip", "Computer Peripherals": "hardware", "Computer Processing Hardware": "hardware",
    "Electronic Components": "electronic", "Electronic Equipment/Instruments": "electronic", "Electronic Production Equipment": "semiequip",
    "Semiconductors": "semis", "Telecommunications Equipment": "commequip",
    # Energy Minerals
    "Coal": "oilgas", "Integrated Oil": "oilgas", "Oil & Gas Production": "oilgas", "Oil Refining/Marketing": "oilgas",
    # Finance
    "Finance/Rental/Leasing": "consfin", "Financial Conglomerates": "diversfin", "Insurance Brokers/Services": "insurance",
    "Investment Banks/Brokers": "capmkts", "Investment Managers": "capmkts", "Investment Trusts/Mutual Funds": "capmkts", "Life/Health Insurance": "insurance",
    "Major Banks": "banks", "Multi-Line Insurance": "insurance", "Property/Casualty Insurance": "insurance", "Real Estate Development": "realestate",
    "Real Estate Investment Trusts": "reit", "Regional Banks": "banks", "Savings Banks": "banks", "Specialty Insurance": "insurance",
    # Health
    "Hospital/Nursing Management": "hcprov", "Managed Health Care": "hcprov", "Medical/Nursing Services": "hcprov", "Services to the Health Industry": "hcprov",
    "Biotechnology": "biotech", "Medical Specialties": "hcequip", "Pharmaceuticals: Generic": "pharma", "Pharmaceuticals: Major": "pharma",
    "Pharmaceuticals: Other": "pharma",
    # Industrial Services
    "Contract Drilling": "energyequip", "Engineering & Construction": "construction", "Environmental Services": "commsupplies",
    "Oil & Gas Pipelines": "oilgas", "Oilfield Services/Equipment": "energyequip",
    # Materials
    "Aluminum": "metals", "Construction Materials": "construction_mat", "Forest Products": "paper", "Other Metals/Minerals": "metals",
    "Precious Metals": "metals", "Steel": "metals", "Agricultural Commodities/Milling": "food", "Chemicals: Agricultural": "chemicals",
    "Chemicals: Major Diversified": "chemicals", "Chemicals: Specialty": "chemicals", "Industrial Specialties": "chemicals", "Pulp & Paper": "paper",
    "Containers/Packaging": "packaging",
    # Producer Manufacturing
    "Auto Parts: OEM": "autoparts", "Building Products": "building", "Electrical Products": "electrical", "Industrial Conglomerates": "conglom",
    "Industrial Machinery": "machinery", "Metal Fabrication": "machinery", "Miscellaneous Manufacturing": "machinery", "Office Equipment/Supplies": "commsupplies",
    "Trucks/Construction/Farm Machinery": "machinery",
    # Retail
    "Apparel/Footwear Retail": "specretail", "Catalog/Specialty Distribution": "broadline", "Department Stores": "broadline", "Drugstore Chains": "food_retail",
    "Electronics/Appliance Stores": "specretail", "Food Retail": "food_retail", "Home Improvement Chains": "specretail", "Internet Retail": "broadline",
    "Discount Stores": "broadline", "Specialty Stores": "specretail", "Contract Manufacturing": "electronic",
    # Technology Services
    "Data Processing Services": "itservices", "Information Technology Services": "itservices", "Internet Software/Services": "software", "Packaged Software": "software",
    # Transportation
    "Air Freight/Couriers": "freight", "Airlines": "air", "Marine Shipping": "marine", "Miscellaneous Transportation": "infra", "Railroads": "rail",
    "Trucking": "ground", "Other Transportation": "infra",
    # Utilities
    "Alternative Power Generation": "ipp", "Electric Utilities": "electric", "Gas Distributors": "gasutil", "Water Utilities": "water",
}
# used only when a TradingView industry is not in the table above
TV_SECTOR_FALLBACK = {
    "Commercial Services": "commsupplies", "Communications": "telecom", "Consumer Durables": "household", "Consumer Non-Durables": "food",
    "Consumer Services": "divconsumer", "Distribution Services": "tradingdist", "Electronic Technology": "electronic", "Energy Minerals": "oilgas",
    "Finance": "diversfin", "Health Services": "hcprov", "Health Technology": "pharma", "Industrial Services": "construction", "Non-Energy Minerals": "metals",
    "Process Industries": "chemicals", "Producer Manufacturing": "machinery", "Retail Trade": "specretail", "Technology Services": "software",
    "Transportation": "infra", "Utilities": "electric",
}

# companies where TradingView's industry differs from GICS (set by hand; not exhaustive)
OVERRIDES = {
    "NYSE:BMNR": "capmkts", "NASDAQ:GLXY": "capmkts", "NASDAQ:XNDU": "hardware", "NYSE:V": "payments", "NYSE:MA": "payments", "NASDAQ:PYPL": "payments",
    "NYSE:SPGI": "capmkts", "NYSE:MCO": "capmkts", "NASDAQ:MSCI": "capmkts",
    "OMXSTO:HEM": "interactive", "NASDAQ:GOOGL": "interactive", "NASDAQ:GOOG": "interactive", "NASDAQ:META": "interactive", "NASDAQ:TTD": "advert",
    "NASDAQ:AMZN": "broadline", "NASDAQ:CPRT": "commsupplies", "NASDAQ:CRDO": "semis", "NASDAQ:CIFR": "software", "NYSE:J": "construction",
    "NASDAQ:CRWV": "itservices", "NASDAQ:APPF": "software", "NYSE:UBER": (IND, "Transportation", "Passenger Ground Transportation"),
    "NASDAQ:VICR": "electrical", "NYSE:RDW": "aero", "NASDAQ:LTRX": "commequip", "OMXSTO:FRACTL": "hardware", "OMXSTO:RAY_B": "hctech",
    "OMXSTO:SOBI": "biotech", "OMXSTO:BOOZT": "broadline", "OSL:BWE": "oilgas", "OSL:AKSO": "energyequip", "NYSE:BKR": "energyequip",
    "NASDAQ:UROY": "oilgas", "OMXSTO:INWI": "building", "OMXSTO:NIBE_B": "building", "OMXSTO:DEDI": "hcprov", "OMXSTO:EWRK": "profservices",
    "OMXSTO:PREV_B": "itservices", "NASDAQ:INOD": "itservices", "OMXSTO:MCAP": "hcequip",     "NASDAQ:SYM": "machinery", "NASDAQ:AEIS": "electronic",
}
# funds: classified by what they hold; (sector, industry group, industry, where the fund invests)
ETF_CLASS = {
    "XETR:VVSM": (IT, "Semiconductors & Semiconductor Equipment", "Semiconductors", "Global (fund)"),
    "XETR:QDVE": (IT, "Information Technology (mixed)", "Mixed information technology", "United States"),
    "XETR:ESIT": (IT, "Information Technology (mixed)", "Mixed information technology", "Europe (fund)"),
    "XETR:W1TB": (IT, "Software & Services", "Software", "Global (fund)"),
    "XETR:EXV8": (IND, "Capital Goods", "Construction & Engineering", "Europe (fund)"),
    "XETR:SPYH": (HC, "Pharmaceuticals, Biotechnology & Life Sciences", "Pharmaceuticals", "Europe (fund)"),
    "XETR:ASWE": ("Diversified (multi-sector fund)", "Diversified (multi-sector fund)", "Diversified (multi-sector fund)", "Global (fund)"),
}
COUNTRY_OVERRIDE = {"NASDAQ:CRDO": "United States"}  # TradingView lists the Cayman holding company; it is run from California

REGION = {}
for _r, _cs in {
    "North America": ["United States", "Canada", "Mexico"],
    "Europe": ["Sweden", "Norway", "Denmark", "Finland", "Germany", "United Kingdom", "Ireland", "Netherlands", "Switzerland", "France", "Italy", "Spain",
               "Belgium", "Austria", "Portugal", "Luxembourg", "Poland", "Iceland", "Estonia", "Czech Republic", "Greece"],
    "Asia-Pacific": ["Japan", "China", "Taiwan", "South Korea", "Hong Kong", "Singapore", "Australia", "New Zealand", "India"],
    "Middle East": ["Israel", "United Arab Emirates", "Saudi Arabia"],
    "Latin America": ["Brazil", "Argentina", "Chile", "Colombia", "Uruguay"],
}.items():
    for _c in _cs:
        REGION[_c] = _r

SIZES = [(200e9, "Mega cap (over $200 bn)"), (10e9, "Large cap ($10-200 bn)"), (2e9, "Mid cap ($2-10 bn)"), (300e6, "Small cap ($0.3-2 bn)"),
         (0, "Micro cap (under $0.3 bn)")]
UNKNOWN = "Not classified"

# ETF/market fallbacks when the screener has no country for a fund
FUND_REGION = {"Europe (fund)": "Europe", "Global (fund)": "Global funds"}
FUND_HOME = {"US ETF": "United States", "Europe ETF": "Europe (fund)"}


def size_class(mcap):
    if mcap is None:
        return UNKNOWN
    for lim, name in SIZES:
        if mcap >= lim:
            return name
    return UNKNOWN


def classify(sym, F, is_etf, market=None):
    """Fields for one holding. F is the TradingView screener row (sector, industry, country, market_cap_basic, ...)."""
    F = F or {}
    if is_etf:
        s, g, i, home = ETF_CLASS.get(sym, ("Diversified (multi-sector fund)",) * 3 + (FUND_HOME.get(market, "Global (fund)"),))
        return dict(gics_sector=s, gics_group=g, gics_industry=i, country=home, region=REGION.get(home, FUND_REGION.get(home, UNKNOWN)),
                    size_class="Funds (ETFs)", asset_type="ETF", tv_sector=None, tv_industry=None)
    blk = OVERRIDES.get(sym) or TV_INDUSTRY.get(F.get("industry")) or TV_SECTOR_FALLBACK.get(F.get("sector"))
    gics = blk if isinstance(blk, tuple) else G.get(blk) if blk else None
    s, g, i = gics or (UNKNOWN,) * 3
    c = COUNTRY_OVERRIDE.get(sym) or F.get("country") or UNKNOWN
    return dict(gics_sector=s, gics_group=g, gics_industry=i, country=c, region=REGION.get(c, "Other" if c != UNKNOWN else UNKNOWN),
                size_class=size_class(F.get("market_cap_basic")), asset_type="Stock", tv_sector=F.get("sector"), tv_industry=F.get("industry"))


def unmapped(sym, F):
    """True when a stock fell through to TradingView's broad sector or to nothing (worth a manual override)."""
    return not (sym in OVERRIDES or (F or {}).get("industry") in TV_INDUSTRY)
