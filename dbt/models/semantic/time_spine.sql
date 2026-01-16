{{ config(materialized='table', schema='gold') }}

with dates as (
    -- Generate a daily spine. Adjust range as needed for dev.
    select d as date_day
    from unnest(
        sequence(
            date '2020-01-01',
            date '2030-12-31',
            interval '1' day
        )
    ) as t(d)
)

select
  date_day
from dates
