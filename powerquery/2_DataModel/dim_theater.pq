let
    Source = Csv.Document(File.Contents(DataFolder & "dim_theater.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    #"Promoted Headers" = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    #"Changed Type" = Table.TransformColumnTypes(#"Promoted Headers", {{"Theater", type text}, {"TheaterSort", Int64.Type}}, "en-US")
in
    #"Changed Type"
