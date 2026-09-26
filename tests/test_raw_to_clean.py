"""
Checks that the business rules implemented in the Power Query staging layer (powerquery/1_StagingArea)
turn the raw CRM extracts in data/raw into exactly the clean tables in data/validation.

The same rules are re-implemented here in pandas, step by step, so the test documents the pipeline
and catches any drift between the generator, the raw files and the staging logic.

Run:  python tests/test_raw_to_clean.py      (or: pytest tests/)
"""
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data"
AS_OF = pd.Timestamp("2026-09-30")
ORDER_TYPE_MAP = {"New": "New Logo", "Cross Sell": "Cross-sell",
                  "Additional Products & Services (Upsell)": "Upsell"}
RENAME = {"Id": "OpportunityId", "Name": "OpportunityName", "Rep_Theater__c": "Theater",
          "QS_Order_Type__c": "OrderType", "Product_Type__c": "PrimaryProductType",
          "Sales_Forecast_Category__c": "ForecastCategory", "Primary_Competitor__c": "PrimaryCompetitorId",
          "Win_Loss_Reason__c": "LossReason", "Value_play__c": "ValuePlay", "Plant_MWp__c": "PlantMWp",
          "Estimated_COD__c": "EstimatedCOD", "Material_Delivery_Date__c": "MaterialDeliveryDate"}


def stg_account():
    raw = pd.read_csv(DATA / "raw" / "sf_account.csv")
    acc = raw[~raw["Name"].str.contains("test", case=False)]
    return acc.rename(columns={"Id": "AccountId", "Name": "AccountName", "BillingCountryCode": "CountryCode",
                               "Account_Theater__c": "Theater", "Type": "AccountType"})


def stg_opportunity():
    o = pd.read_csv(DATA / "raw" / "sf_opportunity.csv")
    o = o[~((o["StageName"] == "Closed Lost") & (o["Win_Loss_Reason__c"].fillna("").str.strip().str.lower() == "duplicate"))]
    o = o[o["QS_Order_Type__c"].isin(ORDER_TYPE_MAP)]
    o = o[~o["Name"].str.contains("renewal", case=False)]
    o = o[o["AccountId"].isin(stg_account()["AccountId"])]
    o = o.assign(QS_Order_Type__c=o["QS_Order_Type__c"].map(ORDER_TYPE_MAP),
                 Rep_Theater__c=o["Rep_Theater__c"].replace({"EMEA": "EMEA & RoW", "RoW": "EMEA & RoW"}),
                 CreatedDate=pd.to_datetime(o["CreatedDate"].str[:10]),
                 CloseDate=pd.to_datetime(o["CloseDate"]))
    o["IsClosed"] = o["StageName"].isin(["Closed Won", "Closed Lost"]).astype(int)
    o["IsWon"] = (o["StageName"] == "Closed Won").astype(int)
    o["AgeDays"] = (o["CloseDate"].where(o["IsClosed"] == 1, AS_OF) - o["CreatedDate"]).dt.days
    return o.rename(columns=RENAME)


def stg_opportunity_line(opps):
    lines = pd.read_csv(DATA / "raw" / "sf_opportunity_line_item.csv")
    fx = pd.read_csv(DATA / "raw" / "fx_rates.csv", parse_dates=["ValidFrom", "ValidTo"])
    products = pd.read_csv(DATA / "dim_product.csv")
    l = lines.merge(opps[["OpportunityId", "CloseDate"]], on="OpportunityId")          # inner join to header
    l = l.merge(fx, on="CurrencyIsoCode")
    l = l[(l["CloseDate"] >= l["ValidFrom"]) & (l["CloseDate"] <= l["ValidTo"])]       # rate valid on close date
    l["ARR_USD"] = (l["QS_Annual_Recurring_Revenue__c"] / l["UnitsPerUSD"]).round(-2)
    l = l.merge(products[["ProductId", "ProductType"]], left_on="Product2Id", right_on="ProductId")
    return l.rename(columns={"Id": "OpportunityLineId"})


def stg_data_quality_audit(opps):
    with_plant = set(pd.read_csv(DATA / "bridge_opportunity_plant.csv")["OpportunityId"])
    scada = opps["PrimaryProductType"] == "SCADA"
    rules = [  # (attribute, group, applies-to mask, missing mask)
        ("Next Step", "General", None, opps["NextStep"].isna()),
        ("Primary Competitor", "General", None, opps["PrimaryCompetitorId"].isna()),
        ("Value Play", "General", None, opps["ValuePlay"].isna()),
        ("Loss Reason", "General", opps["StageName"] == "Closed Lost", opps["LossReason"].isna()),
        ("Close Date in Past", "General", opps["IsClosed"] == 0, opps["CloseDate"] < AS_OF),
        ("Plant MWp", "SCADA", scada, opps["PlantMWp"].isna()),
        ("Estimated COD", "SCADA", scada, opps["EstimatedCOD"].isna()),
        ("Material Delivery Date", "SCADA", scada, opps["MaterialDeliveryDate"].isna()),
        ("Account Plant", "SCADA", scada, ~opps["OpportunityId"].isin(with_plant)),
    ]
    parts = []
    for attribute, group, applies, missing in rules:
        mask = applies if applies is not None else pd.Series(True, index=opps.index)
        parts.append(pd.DataFrame({"OpportunityId": opps.loc[mask, "OpportunityId"], "Attribute": attribute,
                                   "AuditGroup": group, "IsMissing": missing[mask].astype(int)}))
    return pd.concat(parts)


def stg_sales_targets():
    wide = pd.read_csv(DATA / "raw" / "sales_targets_wide.csv")
    t = wide.melt(id_vars=["Segment", "Year"], var_name="Quarter", value_name="k").dropna()
    t["Theater"] = t["Segment"].str.rsplit(" ", n=1).str[0]
    t["ProductType"] = t["Segment"].str.rsplit(" ", n=1).str[1]
    t["QuarterStartDate"] = pd.to_datetime(dict(year=t["Year"], month=(t["Quarter"].str[1].astype(int) - 1) * 3 + 1, day=1))
    t["TargetUSD"] = (t["k"] * 1000).round()
    return t


# --------------------------------------------------------------------------- tests
def test_accounts():
    expected = pd.read_csv(DATA / "validation" / "dim_account.csv")
    got = stg_account()[expected.columns]
    assert got.sort_values("AccountId").reset_index(drop=True).equals(expected.sort_values("AccountId").reset_index(drop=True))


def test_opportunities():
    expected = pd.read_csv(DATA / "validation" / "fct_opportunity.csv", parse_dates=["CreatedDate", "CloseDate"])
    got = stg_opportunity()[expected.columns]
    a = got.sort_values("OpportunityId").reset_index(drop=True).astype(str)
    b = expected.sort_values("OpportunityId").reset_index(drop=True).astype(str)
    assert len(a) == len(b) and a.equals(b)


def test_opportunity_lines_in_usd():
    expected = pd.read_csv(DATA / "validation" / "fct_opportunity_line.csv").set_index("OpportunityLineId").sort_index()
    got = stg_opportunity_line(stg_opportunity()).set_index("OpportunityLineId").sort_index()
    assert got.index.equals(expected.index)
    assert (got["ARR_USD"].values == expected["ARR_USD"].astype(float).values).all()
    assert (got["ProductType"].values == expected["ProductType"].values).all()


def test_data_quality_audit():
    expected = pd.read_csv(DATA / "validation" / "fct_data_quality_audit.csv")
    got = stg_data_quality_audit(stg_opportunity())
    j = got.merge(expected, on=["OpportunityId", "Attribute"], how="outer", indicator=True, suffixes=("", "_exp"))
    assert (j["_merge"] == "both").all()
    assert (j["IsMissing"] == j["IsMissing_exp"]).all() and (j["AuditGroup"] == j["AuditGroup_exp"]).all()


def test_sales_targets():
    expected = pd.read_csv(DATA / "validation" / "fct_sales_target.csv", parse_dates=["QuarterStartDate"])
    j = stg_sales_targets().merge(expected, on=["QuarterStartDate", "Theater", "ProductType"], how="outer", indicator=True)
    assert (j["_merge"] == "both").all() and (j["TargetUSD_x"] == j["TargetUSD_y"]).all()


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"PASS  {name}")
