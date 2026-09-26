// One audit flag per opportunity and required CRM field (1 = missing, 0 = filled),
// unpivoted to a long table for the data-quality report.
let
    Source = stg_Opportunity,
    OppsWithPlant = List.Buffer(List.Distinct(bridge_opportunity_plant[OpportunityId])),
    IsMissing = (value as any) as number => if value = null or value = "" then 1 else 0,

    // Flags. A flag is null where the rule does not apply; the unpivot below drops nulls.
    // Prefix "Audit_" = General rules for every deal, "AuditSCADA_" = extra rules for SCADA deals.
    #"Flag Next Step"          = Table.AddColumn(Source, "Audit_Next Step", each IsMissing([NextStep]), Int64.Type),
    #"Flag Competitor"         = Table.AddColumn(#"Flag Next Step", "Audit_Primary Competitor", each IsMissing([PrimaryCompetitorId]), Int64.Type),
    #"Flag Value Play"         = Table.AddColumn(#"Flag Competitor", "Audit_Value Play", each IsMissing([ValuePlay]), Int64.Type),
    #"Flag Loss Reason"        = Table.AddColumn(#"Flag Value Play", "Audit_Loss Reason",
                                    each if [StageName] = "Closed Lost" then IsMissing([LossReason]) else null, Int64.Type),
    #"Flag Close Date in Past" = Table.AddColumn(#"Flag Loss Reason", "Audit_Close Date in Past",
                                    each if [IsClosed] = 0 then (if [CloseDate] < AsOfDate then 1 else 0) else null, Int64.Type),
    #"Flag Plant MWp"          = Table.AddColumn(#"Flag Close Date in Past", "AuditSCADA_Plant MWp",
                                    each if [PrimaryProductType] = "SCADA" then IsMissing([PlantMWp]) else null, Int64.Type),
    #"Flag Estimated COD"      = Table.AddColumn(#"Flag Plant MWp", "AuditSCADA_Estimated COD",
                                    each if [PrimaryProductType] = "SCADA" then IsMissing([EstimatedCOD]) else null, Int64.Type),
    #"Flag Delivery Date"      = Table.AddColumn(#"Flag Estimated COD", "AuditSCADA_Material Delivery Date",
                                    each if [PrimaryProductType] = "SCADA" then IsMissing([MaterialDeliveryDate]) else null, Int64.Type),
    #"Flag Account Plant"      = Table.AddColumn(#"Flag Delivery Date", "AuditSCADA_Account Plant",
                                    each if [PrimaryProductType] = "SCADA" then (if List.Contains(OppsWithPlant, [OpportunityId]) then 0 else 1) else null, Int64.Type),

    // Wide -> long
    AuditColumns = List.Select(Table.ColumnNames(#"Flag Account Plant"), each Text.StartsWith(_, "Audit")),
    #"Kept Audit Columns" = Table.SelectColumns(#"Flag Account Plant", {"OpportunityId", "IsClosed"} & AuditColumns),
    #"Unpivoted Flags" = Table.UnpivotOtherColumns(#"Kept Audit Columns", {"OpportunityId", "IsClosed"}, "AuditField", "IsMissing"),

    // Clean up names: group from the prefix, attribute from the text after "_"
    #"Added AuditGroup" = Table.AddColumn(#"Unpivoted Flags", "AuditGroup",
        each if Text.StartsWith([AuditField], "AuditSCADA_") then "SCADA" else "General", type text),
    #"Added Attribute" = Table.AddColumn(#"Added AuditGroup", "Attribute", each Text.AfterDelimiter([AuditField], "_"), type text),
    #"Added RecordStatus" = Table.AddColumn(#"Added Attribute", "RecordStatus", each if [IsClosed] = 1 then "Closed" else "Pipeline", type text),
    #"Selected Columns" = Table.SelectColumns(#"Added RecordStatus", {"OpportunityId", "Attribute", "AuditGroup", "IsMissing", "RecordStatus"}),
    #"Changed Type" = Table.TransformColumnTypes(#"Selected Columns", {{"IsMissing", Int64.Type}})
in
    #"Changed Type"
