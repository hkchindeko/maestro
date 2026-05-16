# SDP/Lakeflow Declarative Pipelines Testing

Testing Spark Declarative Pipelines (SDP) and Lakeflow Declarative Pipelines (LDP) locally.

## Overview

The `sdp-test` plugin enables local testing of declarative pipelines without requiring a remote Databricks cluster or workspace.

## Installation

```bash
pip install "sdp-test[spark]"
```

## How It Works

1. Discovers pipeline definition from `databricks.yml` or `spark-pipeline.yml`
2. Resolves variables and configuration
3. Runs tests against a local SparkSession
4. For SQL models: extracts the `SELECT` query
5. For Python models: shims pipeline decorators (`@dp.table`, `@dp.view`)

## YAML Test Definitions

Create test files in `tests/` directory:

```yaml
# tests/test_pipeline.yaml
pipeline: databricks.yml

tests:
  - name: test_clean_users
    model: clean_users
    input:
      raw_users:
        - id: 1
          name: Alice
          email: alice@example.com
        - id: 2
          name: null
          email: invalid
    expected:
      - id: 1
        name: Alice
        email: alice@example.com
        is_valid: true
```

## Running SDP Tests

```bash
pytest tests/test_pipeline.yaml -v
```

## Testing Python Models

For Python models using `@dp.table` or `@dp.view`:

```python
# src/pipeline.py
import dlt

@dlt.table
def clean_users():
    return (
        spark.read.table("raw.users")
        .filter(col("name").isNotNull())
        .withColumn("is_valid", col("email").rlike("@"))
    )
```

The `sdp-test` plugin automatically shims the decorators for local execution.

## Testing SQL Models

For SQL models, the plugin extracts and executes the SELECT query:

```sql
-- models/clean_users.sql
SELECT
  id,
  name,
  email,
  email RLIKE '@' as is_valid
FROM raw.users
WHERE name IS NOT NULL
```

## Best Practices

1. **Test each model independently**: Isolate input and expected output
2. **Cover edge cases**: Null values, empty inputs, invalid data
3. **Use realistic data**: Mirror production data patterns
4. **Test data quality constraints**: Validate expected schemas and values
5. **Run locally first**: Iterate quickly before deploying to Databricks
