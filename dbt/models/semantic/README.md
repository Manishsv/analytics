# MetricFlow Semantic Layer Definitions

This directory contains semantic model and metric definitions for MetricFlow (dbt Semantic Layer).

## Files

- `sales_monthly_semantic.yml` - Semantic model for Gold sales fact
- `metrics.yml` - Metric definitions (Sales, Growth)

## Status

**Semantic Model**: ✅ Created and ready for MetricFlow validation

**Metrics**: ⚠️ Requires MetricFlow installation

The semantic model YAML (`sales_monthly_semantic.yml`) is valid dbt configuration. However, the metrics YAML (`metrics.yml`) requires MetricFlow to be installed and configured separately, as dbt 1.10.18 does not natively support semantic layer metrics parsing.

## Next Steps

1. **Install MetricFlow**:
   ```bash
   pip install metricflow
   ```

2. **Validate semantic models**:
   ```bash
   mf validate-configs
   ```

3. **Query metrics**:
   ```bash
   mf query --metrics sales_value_lc --dimensions geo_id,channel_id --time-dimension period_yyyymm
   ```

## Semantic Model Structure

- **Entity**: `sales` (synthetic key: period|geo|channel)
- **Dimensions**: `period_yyyymm` (time), `geo_id`, `channel_id`
- **Measures**: `value_lc`, `standard_units`, `units`

## Metrics Defined

- `sales_value_lc` - Total sales value in local currency
- `sales_volume_su` - Total volume in standard units
- `sales_volume_units` - Total volume in pack units
- `avg_price_lc_per_su` - Average price per standard unit
- `sales_value_lc__yoy` - Sales shifted by 1 year (for YoY comparisons)
- `sales_value_lc_yoy_growth_pct` - Year-over-year growth percentage

## Notes

- The semantic model references `gold_sales_monthly` dbt model
- Time dimension uses `period_yyyymm` in YYYYMM format (categorical/time hybrid)
- For production, consider adding a true date column for better time intelligence
