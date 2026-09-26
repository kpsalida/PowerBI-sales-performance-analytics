let
    Source = Csv.Document(File.Contents(DataFolder & "fct_stage_history.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    #"Promoted Headers" = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    #"Changed Type" = Table.TransformColumnTypes(#"Promoted Headers", {{"OpportunityId", type text}, {"FromStage", type text}, {"ToStage", type text}, {"ChangeDate", type date}}, "en-US")
in
    #"Changed Type"
