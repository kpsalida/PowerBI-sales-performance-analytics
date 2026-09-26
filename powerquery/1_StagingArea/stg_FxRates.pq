let
    Source = raw_FxRates,
    // Explicit en-US culture: the file uses "." as decimal separator on any machine locale
    #"Changed Type" = Table.TransformColumnTypes(Source, {{"CurrencyIsoCode", type text}, {"ValidFrom", type date}, {"ValidTo", type date}, {"UnitsPerUSD", type number}}, "en-US")
in
    #"Changed Type"
