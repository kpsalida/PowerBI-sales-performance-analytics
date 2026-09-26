# Data Dictionary

All data is synthetic, produced by `data_generator/generate_data.py` (default seed 42, as-of date 2026-09-30).
Every company, person, competitor and amount is fictional.

## Folders

| Folder | Used by | Contents |
|---|---|---|
| `data/raw/` | Power Query `0_RawData` | Salesforce-style extracts: API field names, local currencies, source codes, and records the staging layer must remove |
| `data/` | Power Query `2_DataModel` | Reference dimensions and facts loaded directly (stage history, weekly snapshots, plants, bridge) |
| `data/validation/` | `tests/` only | The clean tables that staging must reproduce from `raw/` (not loaded by Power BI) |

`dim_date` and `dim_product_type` are DAX calculated tables inside the model.

## Raw extracts (`data/raw/`)

| File | Grain | Notes |
|---|---|---|
| `sf_opportunity.csv` | Opportunity | 1,880 rows: the 1,800 real deals plus 40 duplicate losses, 25 renewals and 15 test-account deals that staging removes. Theater codes `EMEA`/`RoW`, CRM order-type codes, ISO timestamps |
| `sf_opportunity_line_item.csv` | Product line | ARR in the account's local currency (USD, EUR, GBP, CAD, AUD, JPY) |
| `sf_account.csv` | Account | 160 customers plus one sandbox/test account |
| `fx_rates.csv` | Currency x validity period | Units per USD, with a rate change on 2025-07-01 |
| `sales_targets_wide.csv` | Segment x year | Finance format: `Segment` = theater + product type, quarters as columns, thousands of USD |

## Model tables

### Dimensions

| Table | Key | Description |
|---|---|---|
| `dim_theater` | Theater | Sales theaters: Americas, EMEA & RoW. |
| `dim_country` | CountryCode | Country → region → theater hierarchy. |
| `dim_product` | ProductId | Eight products in two product types (SaaS, SCADA). |
| `dim_stage` | StageName | Sales stages with sort order and closed/won flags. |
| `dim_forecast_category` | ForecastCategory | Pipeline, Best Case, Commit, Closed, Omitted. |
| `dim_order_type` | OrderType | New Logo, Cross-sell, Upsell. |
| `dim_competitor` | CompetitorId | Seven fictional competitors plus "No Competitor" (C00). |
| `dim_loss_reason` | LossReason | Loss reasons grouped into categories. |
| `dim_sales_rep` | RepId | Opportunity owners and their theater. |
| `dim_account` | AccountId | Customers with country, theater and account type. |
| `dim_plant` | PlantId | Customer power plants: asset class, MWp, commercial operation date. |

### Facts

| Table | Grain | Description |
|---|---|---|
| `fct_opportunity` | One row per opportunity | Deal header: account, owner, order type, dates, stage, forecast category, competitor, loss reason and the CRM fields checked by the audit. Contains no ARR. |
| `fct_opportunity_line` | One row per product line | ARR in USD by product (header–line pattern). `CloseDate` is repeated so lines can relate to the date table directly. |
| `fct_stage_history` | One row per stage change | `FromStage → ToStage` with change date. Losses are rows where `ToStage = 'Closed Lost'`. |
| `fct_pipeline_snapshot` | Opportunity × week | Every open deal every Monday from Jan 2025: stage, forecast category and ARR at that date. |
| `fct_data_quality_audit` | Opportunity × audited field | Unpivoted audit: `IsMissing` = 1 when the field is empty. `AuditGroup` = General or SCADA; `RecordStatus` = Pipeline or Closed. Includes "Close Date in Past" for open deals. |
| `fct_sales_target` | Quarter × theater × product type | Quarterly ARR targets 2024 Q1 – 2027 Q2. |
| `bridge_opportunity_plant` | Opportunity × plant | Many-to-many link between SCADA deals and the plants they cover. |

## Relationships (star schema, all single-direction many-to-one)

Filters flow from dimensions into `fct_opportunity`, and from there into its child tables.

| From (many) | To (one) | Notes |
|---|---|---|
| `fct_opportunity`[CloseDate] | `dim_date`[Date] | Active: deals are reported by close date |
| `fct_opportunity`[CreatedDate] | `dim_date`[Date] | **Inactive**; use `USERELATIONSHIP` for created-date analysis |
| `fct_opportunity` | `dim_account`, `dim_sales_rep` (OwnerId→RepId), `dim_theater`, `dim_order_type`, `dim_stage`, `dim_forecast_category`, `dim_competitor` (PrimaryCompetitorId→CompetitorId), `dim_loss_reason` | |
| `dim_account`[CountryCode] | `dim_country`[CountryCode] | |
| `fct_opportunity_line`[OpportunityId] | `fct_opportunity`[OpportunityId] | Header–line: date/theater/stage filters reach ARR through the header |
| `fct_opportunity_line`[ProductId] | `dim_product`[ProductId] | |
| `dim_product`[ProductType] | `dim_product_type`[ProductType] | Shared product-type filter for lines and targets |
| `fct_stage_history`, `fct_data_quality_audit`, `bridge_opportunity_plant` | `fct_opportunity`[OpportunityId] | |
| `bridge_opportunity_plant`[PlantId] | `dim_plant`[PlantId] | Plant MWp reached through the bridge in DAX |
| `fct_pipeline_snapshot` | `dim_date` (SnapshotDate), `dim_account`, `dim_sales_rep`, `dim_theater`, `dim_order_type`, `dim_stage`, `dim_forecast_category` | Independent fact: **not** related to `fct_opportunity`, to avoid a second date path |
| `fct_sales_target` | `dim_date` (QuarterStartDate), `dim_theater`, `dim_product_type` | |

Deliberately not related: `dim_country`/`dim_sales_rep` → `dim_theater` and `dim_plant` → `dim_account`. Each would create a second filter path to the fact tables.

## Built-in patterns

- Americas wins more SCADA and closes larger deals; EMEA & RoW wins more SaaS.
- Win rate: Upsell > Cross-sell > New Logo. SCADA cycles are ~50% longer than SaaS.
- About half of won deals close in the last two weeks of the quarter.
- Each competitor has a product focus and a typical loss reason; Arcturus Controls is the toughest.
- Price losses happen late (Proposal/Negotiation); "No Decision" losses happen early.
- Missing-field rate is ~35% before the audit rollout (Oct 2025) and ~18% after, and differs by rep.
