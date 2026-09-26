# Power Query (M) pipeline

The model loads Salesforce-style raw extracts and cleans them in three layers,
mirroring a production CRM pipeline. Only `2_DataModel` queries load into the model;
raw and staging queries are connection-only.

```
00_Parameters   DataFolder (path to /data), AsOfDate (dataset "today")
0_RawData       raw_*        CSV extracts as-is: Salesforce API field names, local currencies, source codes
0_Functions     fnConvertToUSD   local currency -> USD using the rate valid on the close date
1_StagingArea   stg_*        types, business rules, standardisation, currency conversion, audit, reshaping
2_DataModel     fct_* / dim_*    tables loaded into the star schema
```

| Staging query | What it shows |
|---|---|
| [`stg_Opportunity`](1_StagingArea/stg_Opportunity.pq) | Typed load with explicit culture, Salesforce timestamps to dates, blank-to-null cleanup, business-rule filters (duplicate losses, renewals, order-type whitelist via a mapping record, test accounts via a buffered key list), code standardisation, derived age and status columns |
| [`stg_OpportunityLine`](1_StagingArea/stg_OpportunityLine.pq) | Header join for the close date, product lookup, multi-currency ARR converted with [`fnConvertToUSD`](0_Functions/fnConvertToUSD.pq) against a buffered FX table |
| [`stg_DataQualityAudit`](1_StagingArea/stg_DataQualityAudit.pq) | Rule-based missing-field flags (null where a rule does not apply), unpivoted to a long audit table that powers the CRM data-quality page |
| [`stg_SalesTargets`](1_StagingArea/stg_SalesTargets.pq) | Finance's wide target sheet (quarters as columns, kUSD) unpivoted, segment split on the last space, quarter start dates for the calendar relationship |

**To run it after cloning:** open the `.pbip`, go to *Transform data > Edit parameters*,
set `DataFolder` to your local `data\` folder (with trailing backslash), and refresh.
