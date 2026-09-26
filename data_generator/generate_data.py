"""
Synthetic sales data generator - Sales Performance Analytics (Power BI portfolio project)

Generates a Salesforce-style CRM dataset for a fictional B2B software company selling
monitoring software (SaaS) and plant control systems (SCADA) to renewable-energy
asset owners. Every name, amount and date is invented.

Built-in patterns, so the dashboards have a story to tell:
  * Americas closes larger deals and wins more SCADA; EMEA & RoW wins more SaaS
  * Upsell wins more often than cross-sell, which wins more often than new logos
  * Win rates improve slowly over time; closes cluster at quarter end
  * Each competitor has its own strength, product focus and typical loss reason
  * Loss reasons map to the stage where deals drop out (price -> late stages, etc.)
  * CRM data quality varies by rep and roughly halves after the audit rollout

Usage:
    python generate_data.py                  # writes CSVs to ../data
    python generate_data.py --out data --seed 7 --n-opps 2500
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------- config
START = pd.Timestamp("2024-01-01")
AS_OF = pd.Timestamp("2026-09-30")          # "today" for the dataset
AUDIT_ROLLOUT = pd.Timestamp("2025-10-01")  # data-quality audit goes live
SNAPSHOT_START = pd.Timestamp("2025-01-06")  # first weekly pipeline snapshot (Monday)

COUNTRIES = [  # code, name, region, theater, weight
    ("US", "United States", "North America", "Americas", 0.20),
    ("CA", "Canada", "North America", "Americas", 0.04),
    ("MX", "Mexico", "LATAM", "Americas", 0.04),
    ("BR", "Brazil", "LATAM", "Americas", 0.06),
    ("CL", "Chile", "LATAM", "Americas", 0.05),
    ("CO", "Colombia", "LATAM", "Americas", 0.02),
    ("ES", "Spain", "Southern Europe", "EMEA & RoW", 0.10),
    ("IT", "Italy", "Southern Europe", "EMEA & RoW", 0.07),
    ("GR", "Greece", "Southern Europe", "EMEA & RoW", 0.05),
    ("PT", "Portugal", "Southern Europe", "EMEA & RoW", 0.03),
    ("DE", "Germany", "Northern Europe", "EMEA & RoW", 0.07),
    ("GB", "United Kingdom", "Northern Europe", "EMEA & RoW", 0.06),
    ("FR", "France", "Northern Europe", "EMEA & RoW", 0.05),
    ("NL", "Netherlands", "Northern Europe", "EMEA & RoW", 0.03),
    ("ZA", "South Africa", "Middle East & Africa", "EMEA & RoW", 0.03),
    ("SA", "Saudi Arabia", "Middle East & Africa", "EMEA & RoW", 0.02),
    ("AU", "Australia", "APAC", "EMEA & RoW", 0.05),
    ("IN", "India", "APAC", "EMEA & RoW", 0.02),
    ("JP", "Japan", "APAC", "EMEA & RoW", 0.01),
]

PRODUCTS = [  # id, name, type, ARR multiplier
    ("P01", "APM Platform", "SaaS", 1.00),
    ("P02", "Portfolio Analytics", "SaaS", 0.70),
    ("P03", "Energy Forecasting", "SaaS", 0.55),
    ("P04", "Work Order Management", "SaaS", 0.45),
    ("P05", "SCADA Core", "SCADA", 1.00),
    ("P06", "Power Plant Controller", "SCADA", 0.85),
    ("P07", "Edge Data Logger", "SCADA", 0.40),
    ("P08", "OT Cybersecurity Add-on", "SCADA", 0.50),
]
ARR_MEDIAN = {"SaaS": 38_000, "SCADA": 85_000}

STAGES = [  # name, order, is_closed, is_won, default forecast category
    ("Prospecting", 1, 0, 0, "Pipeline"),
    ("Qualification", 2, 0, 0, "Pipeline"),
    ("Solution Design", 3, 0, 0, "Best Case"),
    ("Proposal", 4, 0, 0, "Best Case"),
    ("Negotiation", 5, 0, 0, "Commit"),
    ("Closed Won", 6, 1, 1, "Closed"),
    ("Closed Lost", 7, 1, 0, "Omitted"),
]
OPEN_STAGES = [s[0] for s in STAGES[:5]]
FORECAST_CATEGORIES = [("Pipeline", 1), ("Best Case", 2), ("Commit", 3), ("Closed", 4), ("Omitted", 5)]

ORDER_TYPES = [  # name, short, probability, win base, ARR multiplier, cycle multiplier
    ("New Logo", "New", 0.45, 0.30, 1.00, 1.25),
    ("Cross-sell", "Cross", 0.25, 0.45, 0.80, 1.00),
    ("Upsell", "Up", 0.30, 0.62, 0.55, 0.70),
]

COMPETITORS = [  # id, name, type, product focus, strength (win-prob multiplier), typical loss reason, weight Americas, weight EMEA
    ("C01", "Voltaris Systems", "Direct Competitor", "SCADA", 0.72, "Price", 0.30, 0.08),
    ("C02", "GridSight Analytics", "Direct Competitor", "SaaS", 0.80, "Functionality Gap", 0.20, 0.18),
    ("C03", "Arcturus Controls", "Hardware OEM", "SCADA", 0.75, "Lost to Incumbent", 0.15, 0.20),
    ("C04", "Nimbus Energy Cloud", "Analytics Start-up", "SaaS", 0.95, "Price", 0.10, 0.20),
    ("C05", "TerraWatt Software", "Direct Competitor", "Both", 0.85, "Functionality Gap", 0.10, 0.14),
    ("C06", "Solvance Monitoring", "Regional Player", "Both", 1.00, "Price", 0.05, 0.12),
    ("C07", "In-house Solution", "In-house", "Both", 0.90, "No Decision / Budget", 0.10, 0.08),
]
NO_COMPETITOR_SHARE = 0.15

LOSS_REASONS = [  # reason, category, exit-stage distribution
    ("Price", "Commercial", {"Solution Design": 0.10, "Proposal": 0.45, "Negotiation": 0.45}),
    ("Functionality Gap", "Product", {"Qualification": 0.15, "Solution Design": 0.50, "Proposal": 0.35}),
    ("No Decision / Budget", "Customer", {"Qualification": 0.45, "Solution Design": 0.35, "Proposal": 0.20}),
    ("Lost to Incumbent", "Competitive", {"Qualification": 0.30, "Solution Design": 0.40, "Proposal": 0.30}),
    ("Timing / Project Delayed", "Customer", {"Solution Design": 0.40, "Proposal": 0.30, "Negotiation": 0.30}),
    ("Relationship", "Competitive", {"Proposal": 0.50, "Negotiation": 0.50}),
]

# Win-probability multiplier by theater x product type
THEATER_PRODUCT_WIN = {
    ("Americas", "SCADA"): 1.15, ("Americas", "SaaS"): 0.85,
    ("EMEA & RoW", "SCADA"): 0.90, ("EMEA & RoW", "SaaS"): 1.10,
}
THEATER_ARR = {"Americas": 1.30, "EMEA & RoW": 1.00}

# Audit fields: (attribute, group, base missing rate, applies to)
AUDIT_FIELDS = [
    ("Next Step", "General", 0.35, "all"),
    ("Primary Competitor", "General", 0.28, "all"),
    ("Value Play", "General", 0.40, "all"),
    ("Loss Reason", "General", 0.25, "lost"),
    ("Plant MWp", "SCADA", 0.30, "scada"),
    ("Estimated COD", "SCADA", 0.40, "scada"),
    ("Material Delivery Date", "SCADA", 0.45, "scada"),
    ("Account Plant", "SCADA", 0.35, "scada"),
]
STALE_CLOSE_DATE_RATE = 0.20  # open opps whose close date is already in the past

REP_FIRST = ["Elena", "Marco", "Sofia", "James", "Nikos", "Laura", "Daniel", "Ines",
             "Tomas", "Olivia", "Rafael", "Hannah", "Victor", "Chloe", "Pedro", "Anna"]
REP_LAST = ["Moreau", "Silva", "Kovac", "Bennett", "Rossi", "Fischer", "Alvarez", "Dimitriou",
            "Novak", "Carter", "Lindqvist", "Ortega", "Hughes", "Marin", "Costa", "Weber"]
ACC_PREFIX = ["Helios", "Aurora", "Zephyr", "Solara", "Borealis", "Meridian", "Cobalt", "Atlas",
              "Lumen", "Sierra", "Halcyon", "Vireo", "Altamira", "Kestrel", "Orion", "Tidewater",
              "Prairie", "Crestline", "Ember", "Azure", "Nordwind", "Solstice", "Everglow", "Pinnacle"]
ACC_SUFFIX = ["Renewables", "Energy", "Power", "Green Capital", "Solar Partners", "Wind Holdings",
              "Clean Assets", "Infrastructure", "Utilities", "Energy Partners"]
ACCOUNT_TYPES = [("Independent Power Producer", 0.35), ("Asset Manager", 0.25), ("Utility", 0.15),
                 ("EPC Contractor", 0.15), ("O&M Provider", 0.10)]
ASSET_CLASSES = [("Solar PV", 0.60), ("Wind", 0.20), ("Battery Storage", 0.10), ("Hybrid", 0.10)]
VALUE_PLAYS = ["Performance Optimization", "Cost Reduction", "Regulatory Compliance", "Portfolio Visibility"]
NEXT_STEPS = ["Schedule technical demo", "Send revised proposal", "Security review with IT",
              "Pilot scoping call", "Pricing discussion with procurement", "Site visit",
              "Legal review of contract", "Follow up after board meeting"]


# --------------------------------------------------------------------------- helpers
def pick(rng, options, weights=None):
    weights = None if weights is None else np.asarray(weights, dtype=float) / np.sum(weights)
    return options[rng.choice(len(options), p=weights)]


def quarter_label(ts):
    return f"{ts.year} Q{ts.quarter}"


def audit_factor(ref_date):
    """Missing-data multiplier: 1.0 before rollout, falling to 0.45 six months after."""
    if ref_date < AUDIT_ROLLOUT:
        return 1.0
    progress = min((ref_date - AUDIT_ROLLOUT).days / 180, 1.0)
    return 1.0 - 0.55 * progress


def spread_dates(rng, start, end, n):
    """n increasing dates between start and end (inclusive of start)."""
    if n <= 1:
        return [start]
    span = max((end - start).days, n)
    offsets = np.sort(rng.choice(np.arange(1, span), size=n - 1, replace=False))
    return [start] + [start + pd.Timedelta(days=int(o)) for o in offsets]


# --------------------------------------------------------------------------- dimensions
def build_dimensions(rng):
    dims = {}
    dates = pd.date_range(START - pd.DateOffset(years=1), "2027-12-31", freq="D")
    dims["dim_date"] = pd.DataFrame({
        "Date": dates,
        "Year": dates.year,
        "QuarterNo": dates.quarter,
        "YearQuarter": [quarter_label(d) for d in dates],
        "QuarterStartDate": dates.to_period("Q").start_time,
        "MonthNo": dates.month,
        "MonthName": dates.strftime("%b"),
        "YearMonth": dates.strftime("%Y-%m"),
        "WeekStartDate": dates - pd.to_timedelta(dates.weekday, unit="D"),
        "IsPast": (dates <= AS_OF).astype(int),
    })

    dims["dim_theater"] = pd.DataFrame({"Theater": ["Americas", "EMEA & RoW"], "TheaterSort": [1, 2]})
    dims["dim_country"] = pd.DataFrame(
        [c[:4] for c in COUNTRIES], columns=["CountryCode", "Country", "Region", "Theater"])
    dims["dim_product"] = pd.DataFrame(
        [p[:3] for p in PRODUCTS], columns=["ProductId", "ProductName", "ProductType"])
    dims["dim_product_type"] = pd.DataFrame({"ProductType": ["SaaS", "SCADA"], "ProductTypeSort": [1, 2]})
    dims["dim_stage"] = pd.DataFrame(
        STAGES, columns=["StageName", "StageOrder", "IsClosed", "IsWon", "DefaultForecastCategory"])
    dims["dim_forecast_category"] = pd.DataFrame(FORECAST_CATEGORIES, columns=["ForecastCategory", "SortOrder"])
    dims["dim_order_type"] = pd.DataFrame(
        [(o[0], o[1]) for o in ORDER_TYPES], columns=["OrderType", "OrderTypeShort"])
    dims["dim_competitor"] = pd.DataFrame(
        [c[:4] for c in COMPETITORS] + [("C00", "No Competitor", "None", "Both")],
        columns=["CompetitorId", "CompetitorName", "CompetitorType", "ProductFocus"])
    dims["dim_loss_reason"] = pd.DataFrame(
        [(r[0], r[1]) for r in LOSS_REASONS], columns=["LossReason", "ReasonCategory"])

    # Sales reps: 6 Americas, 8 EMEA & RoW, each with a data-quality habit
    names = rng.permutation([f"{f} {l}" for f, l in zip(REP_FIRST, rng.permutation(REP_LAST))])[:14]
    theaters = ["Americas"] * 6 + ["EMEA & RoW"] * 8
    dims["dim_sales_rep"] = pd.DataFrame({
        "RepId": [f"R{i + 1:02d}" for i in range(14)],
        "RepName": names,
        "Theater": theaters,
        "_dq_multiplier": np.round(rng.uniform(0.4, 1.8, 14), 2),  # internal, dropped on export
    })
    return dims


def build_accounts_and_plants(rng, n_accounts):
    names = rng.permutation([f"{p} {s}" for p in ACC_PREFIX for s in ACC_SUFFIX])[:n_accounts]
    country_idx = rng.choice(len(COUNTRIES), size=n_accounts, p=[c[4] for c in COUNTRIES])
    accounts = pd.DataFrame({
        "AccountId": [f"ACC{i + 1:04d}" for i in range(n_accounts)],
        "AccountName": names,
        "CountryCode": [COUNTRIES[i][0] for i in country_idx],
        "Theater": [COUNTRIES[i][3] for i in country_idx],
        "AccountType": [pick(rng, [t[0] for t in ACCOUNT_TYPES], [t[1] for t in ACCOUNT_TYPES])
                        for _ in range(n_accounts)],
        # Pareto-like account size: a few large customers drive most revenue
        "_size_weight": rng.pareto(1.6, n_accounts) + 0.2,
    })

    plants = []
    for acc in accounts.itertuples():
        for k in range(rng.integers(1, 6)):
            asset = pick(rng, [a[0] for a in ASSET_CLASSES], [a[1] for a in ASSET_CLASSES])
            plants.append({
                "PlantId": f"PLT{len(plants) + 1:05d}",
                "PlantName": f"{acc.AccountName.split()[0]} {asset} Site {k + 1}",
                "AccountId": acc.AccountId,
                "CountryCode": acc.CountryCode,
                "AssetClass": asset,
                "PlantMWp": round(float(rng.lognormal(np.log(45), 0.8)), 1),
                "CommercialOperationDate": (START + pd.Timedelta(days=int(rng.integers(-2500, 900)))).date(),
            })
    return accounts, pd.DataFrame(plants)


# --------------------------------------------------------------------------- opportunities
def build_opportunities(rng, n_opps, accounts, plants, reps):
    comp_by_id = {c[0]: c for c in COMPETITORS}
    reason_by_name = {r[0]: r for r in LOSS_REASONS}
    rep_dq = reps.set_index("RepId")["_dq_multiplier"].to_dict()
    reps_by_theater = reps.groupby("Theater")["RepId"].apply(list).to_dict()
    account_owner = {a.AccountId: rng.choice(reps_by_theater[a.Theater]) for a in accounts.itertuples()}
    plants_by_account = plants.groupby("AccountId")

    # Created dates weighted towards later periods (a growing business)
    horizon = (AS_OF - pd.Timedelta(days=15) - START).days
    day_weights = np.linspace(1.0, 1.8, horizon)
    created_offsets = np.sort(rng.choice(horizon, size=n_opps, p=day_weights / day_weights.sum()))

    acc_p = accounts["_size_weight"] / accounts["_size_weight"].sum()
    opps, lines, history, bridge, audit_raw = [], [], [], [], []

    for i in range(n_opps):
        opp_id = f"OPP{i + 1:05d}"
        acc = accounts.iloc[rng.choice(len(accounts), p=acc_p)]
        theater = acc.Theater
        owner = account_owner[acc.AccountId] if rng.random() < 0.85 else rng.choice(reps_by_theater[theater])
        order = ORDER_TYPES[rng.choice(3, p=[o[2] for o in ORDER_TYPES])]
        scada_share = 0.55 if theater == "Americas" else 0.40
        ptype = "SCADA" if rng.random() < scada_share else "SaaS"
        created = START + pd.Timedelta(days=int(created_offsets[i]))
        quarters_in = (created.year - START.year) * 4 + created.quarter - 1

        # Sales cycle (days) and close date, with end-of-quarter clustering
        mean_cycle = (150 if ptype == "SCADA" else 95) * order[5]
        cycle = max(20, int(rng.gamma(4.0, mean_cycle / 4.0)))
        close = created + pd.Timedelta(days=cycle)
        if rng.random() < 0.45:
            q_end = close.to_period("Q").end_time.normalize()
            close = q_end - pd.Timedelta(days=int(rng.integers(0, 14)))

        # Competitor actually involved in the deal
        if rng.random() < NO_COMPETITOR_SHARE:
            comp = None
        else:
            eligible = [c for c in COMPETITORS if c[3] in (ptype, "Both")]
            w = [c[6] if theater == "Americas" else c[7] for c in eligible]
            comp = pick(rng, eligible, w)

        # Win probability
        p_win = order[3] * THEATER_PRODUCT_WIN[(theater, ptype)] * (1 + 0.015 * quarters_in)
        p_win *= comp[4] if comp else 1.1
        p_win = float(np.clip(p_win, 0.05, 0.90))

        # Outcome
        is_closed = close <= AS_OF
        is_won = is_closed and rng.random() < p_win
        loss_reason, exit_stage = None, None
        if is_closed and not is_won:
            if comp and rng.random() < 0.7:
                loss_reason = comp[5]
            elif comp:
                loss_reason = pick(rng, [r[0] for r in LOSS_REASONS])
            else:
                loss_reason = pick(rng, ["No Decision / Budget", "Timing / Project Delayed", "Price"], [0.5, 0.3, 0.2])
            dist = reason_by_name[loss_reason][2]
            exit_stage = pick(rng, list(dist.keys()), list(dist.values()))
            # Lost deals usually die before the planned close date
            close = created + pd.Timedelta(days=max(15, int((close - created).days * rng.uniform(0.5, 0.95))))

        # Stage path and history
        if is_won:
            path = OPEN_STAGES + ["Closed Won"]
            end_date = close
        elif is_closed:
            path = OPEN_STAGES[: OPEN_STAGES.index(exit_stage) + 1] + ["Closed Lost"]
            end_date = close
        else:
            frac = (AS_OF - created).days / max((close - created).days, 1)
            path = OPEN_STAGES[: min(int(frac * 5) + 1, 5)]
            end_date = AS_OF
        dates = spread_dates(rng, created, end_date, len(path))
        if is_closed:
            dates[-1] = close
        prev = None
        for stage, d in zip(path, dates):
            history.append({"OpportunityId": opp_id, "FromStage": prev, "ToStage": stage, "ChangeDate": d.date()})
            prev = stage
        stage = path[-1]

        forecast = next(s[4] for s in STAGES if s[0] == stage)
        if not is_closed and rng.random() < 0.15:  # rep judgement shifts the category
            cats = ["Pipeline", "Best Case", "Commit"]
            forecast = cats[int(np.clip(cats.index(forecast) + rng.choice([-1, 1]), 0, 2))]

        # Product lines (ARR lives here: header-line pattern)
        n_lines = 1 + int(rng.random() < 0.30) + int(rng.random() < 0.10)
        for ln in range(n_lines):
            lt = ptype if ln == 0 or rng.random() < 0.7 else ("SaaS" if ptype == "SCADA" else "SCADA")
            prod = pick(rng, [p for p in PRODUCTS if p[2] == lt])
            arr = (ARR_MEDIAN[lt] * prod[3] * THEATER_ARR[theater] * order[4]
                   * (1 + 0.02 * quarters_in) * rng.lognormal(0, 0.55))
            lines.append({
                "OpportunityLineId": f"{opp_id}-L{ln + 1}",
                "OpportunityId": opp_id,
                "ProductId": prod[0],
                "ProductType": lt,
                "CloseDate": close.date(),
                "ARR_USD": round(arr, -2),
            })

        # Data quality: missing-field probability depends on rep habit and audit timing
        ref_date = close if is_closed else AS_OF
        dq = rep_dq[owner] * audit_factor(ref_date)
        has_scada = ptype == "SCADA"
        missing = {}
        for attr, group, base, scope in AUDIT_FIELDS:
            applies = scope == "all" or (scope == "lost" and is_closed and not is_won) or (scope == "scada" and has_scada)
            if applies:
                missing[attr] = rng.random() < min(base * dq, 0.95)

        acc_plants = plants_by_account.get_group(acc.AccountId) if has_scada else None
        linked_mwp = None
        if has_scada and not missing["Account Plant"]:
            chosen = acc_plants.sample(n=min(len(acc_plants), int(rng.integers(1, 3))),
                                       random_state=int(rng.integers(1e9)))
            bridge += [{"OpportunityId": opp_id, "PlantId": p} for p in chosen["PlantId"]]
            linked_mwp = round(float(chosen["PlantMWp"].sum()), 1)

        # Stale close date: open deal whose close date has already passed
        stale = False
        if not is_closed and rng.random() < min(STALE_CLOSE_DATE_RATE * dq, 0.9):
            close = AS_OF - pd.Timedelta(days=int(rng.integers(5, 90)))
            stale = True
            for line in lines[-n_lines:]:
                line["CloseDate"] = close.date()

        opps.append({
            "OpportunityId": opp_id,
            "OpportunityName": f"{acc.AccountName} - {ptype} {order[1]} {created.year}",
            "AccountId": acc.AccountId,
            "OwnerId": owner,
            "Theater": theater,
            "OrderType": order[0],
            "PrimaryProductType": ptype,
            "CreatedDate": created.date(),
            "CloseDate": close.date(),
            "StageName": stage,
            "ForecastCategory": forecast,
            "IsClosed": int(is_closed),
            "IsWon": int(is_won),
            "AgeDays": ((close if is_closed else AS_OF) - created).days,
            "PrimaryCompetitorId": None if missing["Primary Competitor"] else (comp[0] if comp else "C00"),
            "LossReason": None if missing.get("Loss Reason") else loss_reason,
            "NextStep": None if missing["Next Step"] else pick(rng, NEXT_STEPS),
            "ValuePlay": None if missing["Value Play"] else pick(rng, VALUE_PLAYS),
            "PlantMWp": None if not has_scada or missing["Plant MWp"] else (linked_mwp or round(float(rng.lognormal(np.log(45), 0.8)), 1)),
            "EstimatedCOD": None if not has_scada or missing["Estimated COD"] else (close + pd.Timedelta(days=int(rng.integers(90, 540)))).date(),
            "MaterialDeliveryDate": None if not has_scada or missing["Material Delivery Date"] else (close + pd.Timedelta(days=int(rng.integers(30, 240)))).date(),
        })

        for attr, is_missing in missing.items():
            audit_raw.append({"OpportunityId": opp_id, "Attribute": attr,
                              "AuditGroup": next(f[1] for f in AUDIT_FIELDS if f[0] == attr),
                              "IsMissing": int(is_missing)})
        if not is_closed:
            audit_raw.append({"OpportunityId": opp_id, "Attribute": "Close Date in Past",
                              "AuditGroup": "General", "IsMissing": int(stale)})

    opps = pd.DataFrame(opps)
    audit = pd.DataFrame(audit_raw).merge(opps[["OpportunityId", "IsClosed"]], on="OpportunityId")
    audit["RecordStatus"] = np.where(audit.pop("IsClosed") == 1, "Closed", "Pipeline")
    return opps, pd.DataFrame(lines), pd.DataFrame(history), pd.DataFrame(bridge), audit


# --------------------------------------------------------------------------- snapshots and targets
def build_pipeline_snapshots(opps, lines, history):
    """Weekly snapshot of every open opportunity: stage, forecast category and ARR at that date.

    Carries its own AccountId / OwnerId / Theater / OrderType / PrimaryProductType so it can be
    modelled as an independent fact table (filtered by SnapshotDate) without an ambiguous path
    through fct_opportunity (filtered by CloseDate).
    """
    arr = lines.groupby("OpportunityId")["ARR_USD"].sum()
    hist = history.assign(ChangeDate=pd.to_datetime(history["ChangeDate"])).sort_values("ChangeDate")
    closed_on = {o.OpportunityId: pd.Timestamp(o.CloseDate) for o in opps.itertuples() if o.IsClosed}
    fc_default = {s[0]: s[4] for s in STAGES}
    attrs = opps.set_index("OpportunityId")[
        ["AccountId", "OwnerId", "Theater", "OrderType", "PrimaryProductType", "CloseDate"]]

    rows = []
    for week in pd.date_range(SNAPSHOT_START, AS_OF, freq="W-MON"):
        state = hist[hist["ChangeDate"] <= week].groupby("OpportunityId")["ToStage"].last()
        state = state[~state.isin(["Closed Won", "Closed Lost"])]
        for opp_id, stage in state.items():
            if opp_id in closed_on and closed_on[opp_id] <= week:
                continue
            a = attrs.loc[opp_id]
            rows.append((week.date(), opp_id, a.AccountId, a.OwnerId, a.Theater, a.OrderType,
                         a.PrimaryProductType, stage, fc_default[stage], arr[opp_id], a.CloseDate))
    return pd.DataFrame(rows, columns=["SnapshotDate", "OpportunityId", "AccountId", "OwnerId", "Theater",
                                       "OrderType", "PrimaryProductType", "StageName",
                                       "ForecastCategory", "ARR_USD", "CloseDate"])


def build_targets(rng, opps, lines):
    """Quarterly targets by theater x product type, set so attainment lands around 75-120%."""
    won = lines.merge(opps[["OpportunityId", "Theater", "IsWon"]], on="OpportunityId")
    won = won[won["IsWon"] == 1].copy()
    won["QuarterStartDate"] = pd.to_datetime(won["CloseDate"]).dt.to_period("Q").dt.start_time
    actual = won.groupby(["QuarterStartDate", "Theater", "ProductType"])["ARR_USD"].sum()

    rows = []
    for q in pd.period_range(START, "2027Q2", freq="Q"):
        qs = q.start_time
        for theater in ["Americas", "EMEA & RoW"]:
            for ptype in ["SaaS", "SCADA"]:
                if qs <= AS_OF:
                    base = actual.get((qs, theater, ptype), 0) * rng.uniform(0.85, 1.30)
                else:  # future quarters: recent run-rate plus growth
                    recent = [actual.get(((q - k).start_time, theater, ptype), 0) for k in range(1, 5)]
                    base = np.mean([r for r in recent if r > 0] or [0]) * 1.12
                rows.append({"QuarterStartDate": qs.date(), "YearQuarter": quarter_label(qs),
                             "Theater": theater, "ProductType": ptype, "TargetUSD": round(base, -3)})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- raw CRM-style exports
# The Power BI project loads these raw files and rebuilds the clean fact tables in Power Query
# (raw -> staging -> model), mirroring a real Salesforce pipeline. The raw layer therefore uses
# Salesforce API field names, local currencies, source codes and some records that staging must remove.
CURRENCY_BY_COUNTRY = {**{c: "EUR" for c in ["ES", "IT", "GR", "PT", "DE", "FR", "NL"]},
                       "GB": "GBP", "CA": "CAD", "AU": "AUD", "JP": "JPY"}
FX_CUTOVER = pd.Timestamp("2025-07-01")
FX_RATES = {  # units of currency per 1 USD: (before cutover, from cutover)
    "USD": (1.0, 1.0), "EUR": (0.924, 0.861), "GBP": (0.792, 0.741), "CAD": (1.362, 1.371),
    "AUD": (1.521, 1.534), "JPY": (150.47, 147.21)}
RAW_ORDER_TYPE = {"New Logo": "New", "Cross-sell": "Cross Sell",
                  "Upsell": "Additional Products & Services (Upsell)"}


def build_raw_exports(seed, accounts, opps, lines, targets):
    rng = np.random.default_rng(seed + 1)  # separate stream: clean tables stay identical
    raw = {}

    # FX table
    raw["fx_rates"] = pd.DataFrame(
        [(cur, "2020-01-01", (FX_CUTOVER - pd.Timedelta(days=1)).date(), r[0]) for cur, r in FX_RATES.items()] +
        [(cur, FX_CUTOVER.date(), "2099-12-31", r[1]) for cur, r in FX_RATES.items()],
        columns=["CurrencyIsoCode", "ValidFrom", "ValidTo", "UnitsPerUSD"])

    # Accounts (+ one sandbox/test account that staging must drop)
    acc = accounts.drop(columns=[c for c in accounts.columns if c.startswith("_")]).rename(columns={
        "AccountId": "Id", "AccountName": "Name", "CountryCode": "BillingCountryCode",
        "Theater": "Account_Theater__c", "AccountType": "Type"})
    test_acc = pd.DataFrame([{"Id": "ACC9999", "Name": "TEST Account - Sandbox", "BillingCountryCode": "US",
                              "Account_Theater__c": "Americas", "Type": "Independent Power Producer"}])
    raw["sf_account"] = pd.concat([acc, test_acc], ignore_index=True)

    # Opportunities with Salesforce field names and source codes
    o = opps.copy()
    o["Rep_Theater__c"] = np.where(o["Theater"] == "Americas", "Americas",
                                   np.where(rng.random(len(o)) < 0.5, "EMEA", "RoW"))
    o["QS_Order_Type__c"] = o["OrderType"].map(RAW_ORDER_TYPE)
    o["CreatedDate"] = pd.to_datetime(o["CreatedDate"]) + pd.to_timedelta(rng.integers(8 * 3600, 18 * 3600, len(o)), unit="s")
    o["CreatedDate"] = o["CreatedDate"].dt.strftime("%Y-%m-%dT%H:%M:%S.000+0000")
    o = o.rename(columns={"OpportunityId": "Id", "OpportunityName": "Name", "PrimaryProductType": "Product_Type__c",
                          "ForecastCategory": "Sales_Forecast_Category__c", "PrimaryCompetitorId": "Primary_Competitor__c",
                          "LossReason": "Win_Loss_Reason__c", "ValuePlay": "Value_play__c", "PlantMWp": "Plant_MWp__c",
                          "EstimatedCOD": "Estimated_COD__c", "MaterialDeliveryDate": "Material_Delivery_Date__c"})
    keep = ["Id", "Name", "AccountId", "OwnerId", "Rep_Theater__c", "QS_Order_Type__c", "Product_Type__c",
            "CreatedDate", "CloseDate", "StageName", "Sales_Forecast_Category__c", "Primary_Competitor__c",
            "Win_Loss_Reason__c", "NextStep", "Value_play__c", "Plant_MWp__c", "Estimated_COD__c",
            "Material_Delivery_Date__c"]
    o = o[keep]

    # Noise that staging must remove
    n = len(opps)
    dup = o[o["StageName"] == "Closed Lost"].sample(40, random_state=seed).copy()
    dup["Win_Loss_Reason__c"] = "Duplicate"
    renew = o.sample(25, random_state=seed + 1).copy()
    renew["Name"] = renew["Name"].str.replace(r" (New|Cross|Up) ", " Renewal ", regex=True)
    renew["QS_Order_Type__c"] = "Renewal"
    test = o.sample(15, random_state=seed + 2).copy()
    test["AccountId"] = "ACC9999"
    test["Name"] = "TEST Account - Sandbox - " + test["Product_Type__c"] + " Demo"
    noise = pd.concat([dup, renew, test], ignore_index=True)
    noise["Id"] = [f"OPP{n + 1 + i:05d}" for i in range(len(noise))]
    raw["sf_opportunity"] = pd.concat([o, noise], ignore_index=True).sample(frac=1, random_state=seed)

    # Opportunity line items in local currency (ARR stored in the account's currency)
    ccy = accounts.set_index("AccountId")["CountryCode"].map(lambda c: CURRENCY_BY_COUNTRY.get(c, "USD"))
    li = lines.merge(opps[["OpportunityId", "AccountId"]], on="OpportunityId")
    li["CurrencyIsoCode"] = li["AccountId"].map(ccy)
    after = pd.to_datetime(li["CloseDate"]) >= FX_CUTOVER
    rate = [FX_RATES[c][1 if a else 0] for c, a in zip(li["CurrencyIsoCode"], after)]
    li["QS_Annual_Recurring_Revenue__c"] = (li["ARR_USD"] * rate).round(2)
    li = li.rename(columns={"OpportunityLineId": "Id", "ProductId": "Product2Id"})
    li = li[["Id", "OpportunityId", "Product2Id", "CurrencyIsoCode", "QS_Annual_Recurring_Revenue__c"]]
    noise_lines = pd.DataFrame({"Id": [f"{i}-L1" for i in noise["Id"]], "OpportunityId": noise["Id"],
                                "Product2Id": "P01", "CurrencyIsoCode": "USD",
                                "QS_Annual_Recurring_Revenue__c": np.round(rng.uniform(20_000, 90_000, len(noise)), -2)})
    raw["sf_opportunity_line_item"] = pd.concat([li, noise_lines], ignore_index=True)

    # Sales targets as the finance team keeps them: one row per segment and year, quarters as columns, in kUSD
    t = targets.copy()
    t["Segment"] = t["Theater"] + " " + t["ProductType"]
    t["Year"] = pd.to_datetime(t["QuarterStartDate"]).dt.year
    t["Q"] = "Q" + pd.to_datetime(t["QuarterStartDate"]).dt.quarter.astype(str)
    wide = t.pivot_table(index=["Segment", "Year"], columns="Q", values="TargetUSD", aggfunc="sum")
    raw["sales_targets_wide"] = (wide / 1000).reset_index()[["Segment", "Year", "Q1", "Q2", "Q3", "Q4"]]
    return raw


# --------------------------------------------------------------------------- main
def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "data"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--n-opps", type=int, default=1800)
    parser.add_argument("--n-accounts", type=int, default=160)
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    dims = build_dimensions(rng)
    accounts, plants = build_accounts_and_plants(rng, args.n_accounts)
    opps, lines, history, bridge, audit = build_opportunities(
        rng, args.n_opps, accounts, plants, dims["dim_sales_rep"])
    snapshots = build_pipeline_snapshots(opps, lines, history)
    targets = build_targets(rng, opps, lines)

    tables = {
        **dims,
        "dim_account": accounts,
        "dim_plant": plants,
        "fct_opportunity": opps,
        "fct_opportunity_line": lines,
        "fct_stage_history": history,
        "fct_pipeline_snapshot": snapshots,
        "fct_data_quality_audit": audit,
        "fct_sales_target": targets,
        "bridge_opportunity_plant": bridge,
    }
    # dim_date and dim_product_type are built in DAX inside the model, so they are not exported.
    # Tables that the Power Query layer rebuilds from data/raw are written to data/validation:
    # tests/test_raw_to_clean.py checks that the staging rules reproduce them exactly.
    rebuilt_in_power_query = {"fct_opportunity", "fct_opportunity_line", "fct_data_quality_audit",
                              "fct_sales_target", "dim_account"}
    (out / "validation").mkdir(exist_ok=True)
    for name, df in tables.items():
        if name in ("dim_date", "dim_product_type"):
            continue
        df = df.drop(columns=[c for c in df.columns if c.startswith("_")])
        folder = out / "validation" if name in rebuilt_in_power_query else out
        df.to_csv(folder / f"{name}.csv", index=False)
        print(f"{folder.name + '/' + name:<40} {len(df):>7,} rows")

    raw_dir = out / "raw"
    raw_dir.mkdir(exist_ok=True)
    for name, df in build_raw_exports(args.seed, accounts, opps, lines, targets).items():
        df.to_csv(raw_dir / f"{name}.csv", index=False)
        print(f"{'raw/' + name:<40} {len(df):>7,} rows")
    print(f"\nWritten to {out.resolve()}")


if __name__ == "__main__":
    main()
