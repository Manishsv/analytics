{{ config(
    schema='gold',
    materialized='table'
) }}

select
    period_yyyymm,
    geo_id,
    channel_id,
    units,
    standard_units,
    value_lc
from {{ ref('gold_sales_monthly') }}
