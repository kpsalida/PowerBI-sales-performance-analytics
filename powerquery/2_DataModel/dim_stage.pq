let
    Source = Csv.Document(File.Contents(DataFolder & "dim_stage.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    #"Promoted Headers" = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    #"Changed Type" = Table.TransformColumnTypes(#"Promoted Headers", {{"StageName", type text}, {"StageOrder", Int64.Type}, {"IsClosed", Int64.Type}, {"IsWon", Int64.Type}, {"DefaultForecastCategory", type text}}, "en-US")
in
    #"Changed Type"
