// Weekly pipeline snapshot. Opportunity attributes come from the staged header so the
// snapshot can be filtered by account, rep, theater and product without a second date path.
let
    Source = Csv.Document(File.Contents(DataFolder & "fct_pipeline_snapshot.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    #"Promoted Headers" = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    #"Base Columns" = Table.SelectColumns(#"Promoted Headers", {"SnapshotDate", "OpportunityId", "StageName", "ForecastCategory", "ARR_USD", "CloseDate"}),
    #"Changed Type" = Table.TransformColumnTypes(#"Base Columns", {{"SnapshotDate", type date}, {"OpportunityId", type text}, {"StageName", type text}, {"ForecastCategory", type text}, {"ARR_USD", type number}, {"CloseDate", type date}}, "en-US"),
    OppAttributes = Table.SelectColumns(stg_Opportunity, {"OpportunityId", "AccountId", "OwnerId", "Theater", "OrderType", "PrimaryProductType"}),
    #"Joined Opportunity" = Table.NestedJoin(#"Changed Type", {"OpportunityId"}, OppAttributes, {"OpportunityId"}, "Opp", JoinKind.LeftOuter),
    #"Expanded Opportunity" = Table.ExpandTableColumn(#"Joined Opportunity", "Opp", {"AccountId", "OwnerId", "Theater", "OrderType", "PrimaryProductType"})
in
    #"Expanded Opportunity"
