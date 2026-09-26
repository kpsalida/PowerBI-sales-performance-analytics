// Finance keeps targets as one row per segment and year, one column per quarter, in thousands of USD.
let
    Source = raw_SalesTargets,
    #"Changed Type" = Table.TransformColumnTypes(Source, {
        {"Segment", type text}, {"Year", Int64.Type}, {"Q1", type number}, {"Q2", type number},
        {"Q3", type number}, {"Q4", type number}}, "en-US"),

    // Wide -> long. Quarters without a target (empty cells) are dropped by the unpivot.
    #"Unpivoted Quarters" = Table.UnpivotOtherColumns(#"Changed Type", {"Segment", "Year"}, "Quarter", "Target_kUSD"),

    // "EMEA & RoW SaaS": theater = text before the LAST space, product type = text after it
    #"Added Theater" = Table.AddColumn(#"Unpivoted Quarters", "Theater",
        each Text.BeforeDelimiter([Segment], " ", {0, RelativePosition.FromEnd}), type text),
    #"Added ProductType" = Table.AddColumn(#"Added Theater", "ProductType",
        each Text.AfterDelimiter([Segment], " ", {0, RelativePosition.FromEnd}), type text),

    // Quarter start date for the relationship to the calendar
    #"Added QuarterStartDate" = Table.AddColumn(#"Added ProductType", "QuarterStartDate",
        each #date([Year], (Number.From(Text.End([Quarter], 1)) - 1) * 3 + 1, 1), type date),
    #"Added YearQuarter" = Table.AddColumn(#"Added QuarterStartDate", "YearQuarter", each Text.From([Year]) & " " & [Quarter], type text),

    // kUSD -> USD
    #"Added TargetUSD" = Table.AddColumn(#"Added YearQuarter", "TargetUSD", each Number.Round([Target_kUSD] * 1000), Int64.Type),
    #"Selected Columns" = Table.SelectColumns(#"Added TargetUSD", {"QuarterStartDate", "YearQuarter", "Theater", "ProductType", "TargetUSD"})
in
    #"Selected Columns"
