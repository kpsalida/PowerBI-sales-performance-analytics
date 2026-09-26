let
    Source = Csv.Document(File.Contents(DataFolder & "dim_order_type.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    #"Promoted Headers" = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    #"Changed Type" = Table.TransformColumnTypes(#"Promoted Headers", {{"OrderType", type text}, {"OrderTypeShort", type text}}, "en-US")
in
    #"Changed Type"
