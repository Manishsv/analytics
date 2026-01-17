{{ config(
    schema='gold',
    materialized='table'
) }}

select
    period_yyyymm,
    period_date,  -- DATE type for time-based operations
    geo_id,
    channel_id,
    sum(units)          as units,
    sum(standard_units) as standard_units,
    sum(value_lc)       as value_lc
from {{ ref('silver_sales') }}
group by 1,2,3,4
