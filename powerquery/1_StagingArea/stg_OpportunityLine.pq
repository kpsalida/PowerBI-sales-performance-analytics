let
    Source = raw_OpportunityLineItem,
    #"Changed Type" = Table.TransformColumnTypes(Source, {
        {"Id", type text}, {"OpportunityId", type text}, {"Product2Id", type text},
        {"CurrencyIsoCode", type text}, {"QS_Annual_Recurring_Revenue__c", type number}}, "en-US"),

    // 1. Keep lines of opportunities that passed staging, and take the close date from the header
    OppHeader = Table.SelectColumns(stg_Opportunity, {"OpportunityId", "CloseDate"}),
    #"Joined Header" = Table.NestedJoin(#"Changed Type", {"OpportunityId"}, OppHeader, {"OpportunityId"}, "Header", JoinKind.Inner),
    #"Expanded CloseDate" = Table.ExpandTableColumn(#"Joined Header", "Header", {"CloseDate"}),

    // 2. Product type from the product dimension
    #"Joined Product" = Table.NestedJoin(#"Expanded CloseDate", {"Product2Id"}, dim_product, {"ProductId"}, "Product", JoinKind.LeftOuter),
    #"Expanded ProductType" = Table.ExpandTableColumn(#"Joined Product", "Product", {"ProductType"}),

    // 3. Local currency -> USD with the rate valid on the close date (FX table buffered once)
    FxRates = Table.Buffer(stg_FxRates),
    #"Added ARR_USD" = Table.AddColumn(#"Expanded ProductType", "ARR_USD",
        each Number.Round(fnConvertToUSD([QS_Annual_Recurring_Revenue__c], [CurrencyIsoCode], [CloseDate], FxRates) / 100, 0, RoundingMode.AwayFromZero) * 100,
        Int64.Type),

    #"Renamed Columns" = Table.RenameColumns(#"Added ARR_USD", {{"Id", "OpportunityLineId"}, {"Product2Id", "ProductId"}}),
    #"Selected Columns" = Table.SelectColumns(#"Renamed Columns", {"OpportunityLineId", "OpportunityId", "ProductId", "ProductType", "CloseDate", "ARR_USD"})
in
    #"Selected Columns"
