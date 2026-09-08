# Auto-Generated Power BI Measures for `Sales`

| Measure Name | Format | DAX Expression | Description |
| :--- | :--- | :--- | :--- |
| **Total Revenue** | `$#,##0.00` | `Total Revenue = SUM('Sales'[total_revenue])` | Total gross revenue generated across all recorded transactions. |
| **Total Units Sold** | `#,##0` | `Total Units Sold = SUM('Sales'[units_sold])` | Total volume of individual items or units sold. |
| **Total Orders** | `#,##0` | `Total Orders = DISTINCTCOUNT('Sales'[order_id])` | Count of unique transactions / orders. |
| **Average Order Value** | `$#,##0.00` | `Average Order Value = DIVIDE([Total Revenue], [Total Orders], 0)` | Average revenue realized per unique order. |
| **Average Unit Price** | `$#,##0.00` | `Average Unit Price = AVERAGE('Sales'[unit_price])` | Average nominal unit price across catalog sales. |
| **Completed Revenue** | `$#,##0.00` | `Completed Revenue = CALCULATE([Total Revenue], 'Sales'[status] = "Completed")` | Total revenue for orders in 'Completed' state. |
| **Pending Revenue** | `$#,##0.00` | `Pending Revenue = CALCULATE([Total Revenue], 'Sales'[status] = "Pending")` | Total revenue for orders in 'Pending' state. |
| **Cancelled Revenue** | `$#,##0.00` | `Cancelled Revenue = CALCULATE([Total Revenue], 'Sales'[status] = "Cancelled")` | Total revenue for orders in 'Cancelled' state. |
| **Cancellation Rate** | `0.0%` | `Cancellation Rate = DIVIDE(CALCULATE(COUNTROWS('Sales'), 'Sales'[status] = "Cancelled"), COUNTROWS('Sales'), 0)` | Percentage of all orders that ended in cancellation. |
| **Completion Rate** | `0.0%` | `Completion Rate = DIVIDE(CALCULATE(COUNTROWS('Sales'), 'Sales'[status] = "Completed"), COUNTROWS('Sales'), 0)` | Percentage of successfully completed orders. |
