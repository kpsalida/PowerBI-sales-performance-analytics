let
    Source = Csv.Document(File.Contents(DataFolder & "dim_product.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    #"Promoted Headers" = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    #"Changed Type" = Table.TransformColumnTypes(#"Promoted Headers", {{"ProductId", type text}, {"ProductName", type text}, {"ProductType", type text}}, "en-US")
in
    #"Changed Type"
