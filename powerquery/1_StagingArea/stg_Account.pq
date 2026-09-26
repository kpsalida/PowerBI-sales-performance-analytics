let
    Source = raw_Account,
    #"Changed Type" = Table.TransformColumnTypes(Source, {{"Id", type text}, {"Name", type text}, {"BillingCountryCode", type text}, {"Account_Theater__c", type text}, {"Type", type text}}),

    // Remove sandbox / test accounts (case-insensitive)
    #"Removed Test Accounts" = Table.SelectRows(#"Changed Type", each not Text.Contains([Name], "test", Comparer.OrdinalIgnoreCase)),

    #"Renamed Columns" = Table.RenameColumns(#"Removed Test Accounts", {
        {"Id", "AccountId"}, {"Name", "AccountName"}, {"BillingCountryCode", "CountryCode"},
        {"Account_Theater__c", "Theater"}, {"Type", "AccountType"}})
in
    #"Renamed Columns"
