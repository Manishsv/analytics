{{ config(
    materialized='table',
    schema='gold',
    description='Materialized view: Sales summary by geo (refreshed daily)'
) }}

-- Pre-aggregated summary for common "sales by geo" queries
select
    geo_id,
    sum(value_lc) as total_sales_value,
    sum(standard_units) as total_volume_su,
    sum(units) as total_units,
    avg(value_lc / nullif(standard_units, 0)) as avg_price_per_su,
    count(distinct period_date) as periods_count
from {{ ref('gold_sales_monthly') }}
where geo_id is not null
group by geo_id
