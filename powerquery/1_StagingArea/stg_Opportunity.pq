let
    Source = raw_Opportunity,

    // ─── 1. TYPES ────────────────────────────────────────────────────────────────
    #"Changed Type" = Table.TransformColumnTypes(Source, {
        {"Id", type text}, {"Name", type text}, {"AccountId", type text}, {"OwnerId", type text},
        {"Rep_Theater__c", type text}, {"QS_Order_Type__c", type text}, {"Product_Type__c", type text},
        {"StageName", type text}, {"Sales_Forecast_Category__c", type text}, {"Primary_Competitor__c", type text},
        {"Win_Loss_Reason__c", type text}, {"NextStep", type text}, {"Value_play__c", type text},
        {"Plant_MWp__c", type number}, {"CloseDate", type date}, {"Estimated_COD__c", type date},
        {"Material_Delivery_Date__c", type date}}, "en-US"),

    // Salesforce timestamp (2025-10-31T12:03:15.000+0000) -> date
    #"CreatedDate to Date" = Table.TransformColumns(#"Changed Type",
        {{"CreatedDate", each Date.FromText(Text.Start(_, 10), [Format = "yyyy-MM-dd"]), type date}}),

    // Empty text from the export -> null, so "missing" means one thing everywhere
    #"Blanks to Null" = Table.ReplaceValue(#"CreatedDate to Date", "", null, Replacer.ReplaceValue,
        {"Primary_Competitor__c", "Win_Loss_Reason__c", "NextStep", "Value_play__c"}),

    // ─── 2. BUSINESS RULES: keep only real new-business opportunities ───────────
    // 2a. Losses logged as duplicates of another opportunity (null-safe, case-insensitive)
    #"Removed Duplicate Losses" = Table.SelectRows(#"Blanks to Null", each not (
        [StageName] = "Closed Lost"
        and Text.Lower(Text.Trim(if [Win_Loss_Reason__c] = null then "" else [Win_Loss_Reason__c])) = "duplicate")),

    // 2b. Allowed order types, with the CRM code -> reporting name mapping in one place
    OrderTypeMap = [
        #"New" = "New Logo",
        #"Cross Sell" = "Cross-sell",
        #"Additional Products & Services (Upsell)" = "Upsell"
    ],
    #"Kept Sales Order Types" = Table.SelectRows(#"Removed Duplicate Losses",
        each [QS_Order_Type__c] <> null and Record.HasFields(OrderTypeMap, [QS_Order_Type__c])),

    // 2c. Renewals are recurring revenue, not new sales
    #"Removed Renewals" = Table.SelectRows(#"Kept Sales Order Types",
        each not Text.Contains([Name], "renewal", Comparer.OrdinalIgnoreCase)),

    // 2d. Only opportunities on real accounts (test accounts are removed in stg_Account)
    ValidAccounts = List.Buffer(stg_Account[AccountId]),
    #"Kept Real Accounts" = Table.SelectRows(#"Removed Renewals", each List.Contains(ValidAccounts, [AccountId])),

    // ─── 3. STANDARDISE CODES ────────────────────────────────────────────────────
    #"Mapped Order Type" = Table.TransformColumns(#"Kept Real Accounts",
        {{"QS_Order_Type__c", each Record.Field(OrderTypeMap, _), type text}}),
    #"Mapped Theater" = Table.TransformColumns(#"Mapped Order Type",
        {{"Rep_Theater__c", each if _ = "EMEA" or _ = "RoW" then "EMEA & RoW" else _, type text}}),

    // ─── 4. DERIVED COLUMNS ──────────────────────────────────────────────────────
    #"Added IsClosed" = Table.AddColumn(#"Mapped Theater", "IsClosed",
        each if List.Contains({"Closed Won", "Closed Lost"}, [StageName]) then 1 else 0, Int64.Type),
    #"Added IsWon" = Table.AddColumn(#"Added IsClosed", "IsWon", each if [StageName] = "Closed Won" then 1 else 0, Int64.Type),
    // Age: created -> close for closed deals, created -> as-of date for open deals
    #"Added AgeDays" = Table.AddColumn(#"Added IsWon", "AgeDays",
        each Duration.Days((if [IsClosed] = 1 then [CloseDate] else AsOfDate) - [CreatedDate]), Int64.Type),

    // ─── 5. MODEL NAMES AND COLUMN ORDER ─────────────────────────────────────────
    #"Renamed Columns" = Table.RenameColumns(#"Added AgeDays", {
        {"Id", "OpportunityId"}, {"Name", "OpportunityName"}, {"Rep_Theater__c", "Theater"},
        {"QS_Order_Type__c", "OrderType"}, {"Product_Type__c", "PrimaryProductType"},
        {"Sales_Forecast_Category__c", "ForecastCategory"}, {"Primary_Competitor__c", "PrimaryCompetitorId"},
        {"Win_Loss_Reason__c", "LossReason"}, {"Value_play__c", "ValuePlay"}, {"Plant_MWp__c", "PlantMWp"},
        {"Estimated_COD__c", "EstimatedCOD"}, {"Material_Delivery_Date__c", "MaterialDeliveryDate"}}),
    #"Selected Columns" = Table.SelectColumns(#"Renamed Columns", {
        "OpportunityId", "OpportunityName", "AccountId", "OwnerId", "Theater", "OrderType", "PrimaryProductType",
        "CreatedDate", "CloseDate", "StageName", "ForecastCategory", "IsClosed", "IsWon", "AgeDays",
        "PrimaryCompetitorId", "LossReason", "NextStep", "ValuePlay", "PlantMWp", "EstimatedCOD", "MaterialDeliveryDate"})
in
    #"Selected Columns"
