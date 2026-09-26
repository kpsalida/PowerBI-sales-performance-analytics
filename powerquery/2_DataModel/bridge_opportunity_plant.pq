let
    Source = Csv.Document(File.Contents(DataFolder & "bridge_opportunity_plant.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    #"Promoted Headers" = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    #"Changed Type" = Table.TransformColumnTypes(#"Promoted Headers", {{"OpportunityId", type text}, {"PlantId", type text}}, "en-US")
in
    #"Changed Type"
