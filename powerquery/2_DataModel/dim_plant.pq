let
    Source = Csv.Document(File.Contents(DataFolder & "dim_plant.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    #"Promoted Headers" = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    #"Changed Type" = Table.TransformColumnTypes(#"Promoted Headers", {{"PlantId", type text}, {"PlantName", type text}, {"AccountId", type text}, {"CountryCode", type text}, {"AssetClass", type text}, {"PlantMWp", type number}, {"CommercialOperationDate", type date}}, "en-US")
in
    #"Changed Type"
