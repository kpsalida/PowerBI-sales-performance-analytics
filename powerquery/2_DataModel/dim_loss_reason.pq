let
    Source = Csv.Document(File.Contents(DataFolder & "dim_loss_reason.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    #"Promoted Headers" = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    #"Changed Type" = Table.TransformColumnTypes(#"Promoted Headers", {{"LossReason", type text}, {"ReasonCategory", type text}}, "en-US")
in
    #"Changed Type"
