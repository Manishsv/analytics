# dbt Transformations

This dbt project transforms data from Bronze → Silver → Gold layers.

## Setup

1. **Install dbt-trino**:
   ```bash
   pip install dbt-trino
   ```

2. **Verify connection**:
   ```bash
   cd dbt
   dbt debug
   ```

3. **Install packages**:
   ```bash
   dbt deps
   ```

## Running Transformations

```bash
# Build all models
dbt run

# Run tests
dbt test

# Build specific models
dbt run --select silver
dbt run --select gold

# Generate documentation
dbt docs generate
dbt docs serve
```

## Model Structure

- **Bronze** (views): Source declarations only
- **Silver** (tables): Typed, normalized, deduplicated data
- **Gold** (tables): Aggregated facts at business grain

## Current Models

### Silver
- `silver_sales` - Typed and normalized sales facts from Bronze

### Gold
- `gold_sales_monthly` - Monthly aggregated sales at period × geo × channel grain
- `v_sales_monthly` - Certified view for BI/Agent consumption
