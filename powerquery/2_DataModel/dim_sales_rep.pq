let
    Source = Csv.Document(File.Contents(DataFolder & "dim_sales_rep.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    #"Promoted Headers" = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    #"Changed Type" = Table.TransformColumnTypes(#"Promoted Headers", {{"RepId", type text}, {"RepName", type text}, {"Theater", type text}}, "en-US")
in
    #"Changed Type"
