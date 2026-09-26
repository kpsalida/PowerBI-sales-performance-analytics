let
    Source = Csv.Document(File.Contents(DataFolder & "dim_country.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    #"Promoted Headers" = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    #"Changed Type" = Table.TransformColumnTypes(#"Promoted Headers", {{"CountryCode", type text}, {"Country", type text}, {"Region", type text}, {"Theater", type text}}, "en-US")
in
    #"Changed Type"
