// Raw extract, loaded as-is: no types, no filters. All cleaning happens in 1_StagingArea.
let
    Source = Csv.Document(File.Contents(DataFolder & "raw\fx_rates.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    #"Promoted Headers" = Table.PromoteHeaders(Source, [PromoteAllScalars = true])
in
    #"Promoted Headers"
