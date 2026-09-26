let
    Source = Csv.Document(File.Contents(DataFolder & "dim_competitor.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    #"Promoted Headers" = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    #"Changed Type" = Table.TransformColumnTypes(#"Promoted Headers", {{"CompetitorId", type text}, {"CompetitorName", type text}, {"CompetitorType", type text}, {"ProductFocus", type text}}, "en-US")
in
    #"Changed Type"
