{{ config(
    schema='silver',
    materialized='table'
) }}

with src as (
    select
        cast(period_yyyymm as varchar)                 as period_yyyymm,
        -- Convert YYYYMM string to DATE (first day of month)
        date_parse(cast(period_yyyymm as varchar) || '01', '%Y%m%d') as period_date,
        cast(pack_id as varchar)                       as pack_id,
        cast(geo_id as varchar)                        as geo_id,
        cast(channel_id as varchar)                    as channel_id,
        cast(units as bigint)                          as units,
        cast(standard_units as bigint)                 as standard_units,
        cast(value_lc as double)                       as value_lc
    from {{ source('bronze', 'sample_sales') }}
)

select *
from src
where period_yyyymm is not null
  and pack_id is not null
  and geo_id is not null
  and channel_id is not null
