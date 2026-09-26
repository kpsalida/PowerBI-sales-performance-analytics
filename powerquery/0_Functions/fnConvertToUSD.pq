// Converts a local-currency amount to USD using the exchange rate valid on a given date.
// Rates come from a table (CurrencyIsoCode, ValidFrom, ValidTo, UnitsPerUSD), so a rate change
// only needs a new row in the FX file - no code change.
(amount as nullable number, currencyCode as nullable text, onDate as nullable date, fxRates as table) as nullable number =>
let
    Code = if currencyCode = null or Text.Trim(currencyCode) = "" then "USD" else Text.Upper(Text.Trim(currencyCode)),
    ValidRates = Table.SelectRows(fxRates, each [CurrencyIsoCode] = Code and [ValidFrom] <= onDate and [ValidTo] >= onDate),
    Rate =
        if Table.IsEmpty(ValidRates)
        then error Error.Record("FX rate missing", "No exchange rate for " & Code & " on " & Date.ToText(onDate, [Format = "yyyy-MM-dd"]))
        else ValidRates{0}[UnitsPerUSD]
in
    if amount = null or onDate = null then null else amount / Rate
