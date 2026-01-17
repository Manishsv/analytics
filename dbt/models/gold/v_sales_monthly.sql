{{ config(
    schema='gold',
    materialized='table'
) }}

select
    period_yyyymm,
    period_date,  -- DATE type for time-based operations
    geo_id,
    channel_id,
    units,
    standard_units,
    value_lc
from {{ ref('gold_sales_monthly') }}
