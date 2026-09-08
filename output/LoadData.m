let
    Source = Csv.Document(File.Contents("D:\\Nh\\Projects\\power_bi_automation\\output\\cleaned_sales.csv"), [Delimiter=",", Columns=9, Encoding=65001, QuoteStyle=QuoteStyle.None]),
    #"Promoted Headers" = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    #"Changed Type" = Table.TransformColumnTypes(#"Promoted Headers", {{"order_id", Int64.Type}, {"order_date", type datetime}, {"region", type text}, {"sales_rep", type text}, {"category", type text}, {"units_sold", type number}, {"unit_price", type number}, {"total_revenue", type number}, {"status", type text}})
in
    #"Changed Type"
