---
name: pytest-unit-test
description: 'Create effective unit tests for Databricks data pipelines using PyTest, PySpark, and Spark Declarative Pipelines (SDP). Use when: writing pytest tests, testing PySpark transformations, testing SDP/DLT pipelines, setting up test fixtures, mocking external dependencies, generating test data, running coverage reports, or configuring CI/CD for data pipeline tests.'
argument-hint: What do you need to test? (transformation, pipeline, fixture, mock, coverage)
---

# PyTest Unit Testing for Databricks Data Pipelines

Create effective, maintainable unit tests for Databricks data pipelines using PyTest, PySpark, and Spark Declarative Pipelines (SDP).

## Delegating to a Sub-Agent

Unit test creation should be delegated to a sub-agent rather than handled by the main AI Coding Agent. This keeps the main agent's context clean and allows it to coordinate multiple testing tasks in parallel (up to 5 sub-agents at a time).

To delegate unit test creation:

1. **Spawn a sub-agent** using the expert agent definition in `agent/python-pytest-expert.md`
2. **Provide the sub-agent with**:
   - The source file(s) that need tests
   - The transformation logic or pipeline to cover
   - Any specific edge cases or scenarios to prioritize
3. **Let the sub-agent** read the reference files as needed and produce the test files
4. **Review the output** and iterate if adjustments are needed

Example delegation prompt:
> "Create unit tests for `src/transformations/clean_data.py`. Use the PyTest Expert Agent (`agent/python-pytest-expert.md`) as your guide. Cover null handling, empty inputs, and schema validation."

When multiple files need tests, spawn separate sub-agents for each (max 5 in parallel) to maintain context isolation and speed up execution.

## Reference Files

This skill includes detailed reference files for deeper guidance. Consult them as needed:

- **`references/transformation-testing.md`** — When writing tests for PySpark transformations (filters, joins, aggregations), use this for DataFrame assertion patterns and edge case coverage.
- **`references/fixtures.md`** — When creating fixtures (SparkSession, test data, Databricks resources), use this for fixture scopes, composition, and `conftest.py` patterns.
- **`references/mocking.md`** — When isolating tests from external dependencies (APIs, databases, file systems), use this for `pytest-mock` patterns and when-to-mock guidance.
- **`references/sdp-testing.md`** — When testing SDP/Lakeflow declarative pipelines locally, use this for YAML test definitions and pipeline model testing.
- **`references/ci-cd.md`** — When configuring automated test execution in CI/CD, use this for GitHub Actions workflows, coverage thresholds, and ephemeral environments.

## When to Use
- Writing unit tests for PySpark transformation functions
- Testing SDP/Lakeflow Declarative Pipelines locally
- Setting up test fixtures for Spark sessions and Databricks resources
- Mocking external dependencies (APIs, databases, file systems)
- Generating code coverage reports with pytest-cov
- Configuring CI/CD pipelines for automated test execution

## Quick Start

### 1. Install Required Dependencies
```bash
pip install pytest pytest-mock pytest-cov
pip install databricks-labs-pytester  # Databricks integration
pip install "sdp-test[spark]"         # SDP/Lakeflow pipeline testing
```

### 2. Project Structure
```
project/
├── src/
│   └── transformations/
│       └── clean_data.py
├── tests/
│   ├── conftest.py          # Shared fixtures
│   └── transformations/
│       └── test_clean_data.py
└── databricks.yml           # SDP pipeline definition
```

### 3. Write Your First Test
```python
import pytest
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType, IntegerType

@pytest.fixture
def spark():
    return SparkSession.builder.appName("test").getOrCreate()

def test_remove_null_rows(spark):
    from transformations.clean_data import remove_null_rows
    
    schema = StructType([
        StructField("id", IntegerType()),
        StructField("name", StringType())
    ])
    input_df = spark.createDataFrame([(1, "Alice"), (2, None), (3, "Bob")], schema)
    
    result = remove_null_rows(input_df, "name")
    
    assert result.count() == 2
    assert result.filter("name IS NULL").count() == 0
```

### 4. Run Tests
```bash
pytest                          # Run all tests
pytest -v                       # Verbose output
pytest tests/test_clean_data.py # Specific file
pytest -k "null"                # Filter by keyword
pytest --cov=src --cov-report=html  # Coverage report
```

## Core Procedures

### Writing Transformation Tests
1. Create a SparkSession fixture
2. Build input DataFrames with known data
3. Call the transformation function
4. Assert expected output using `assertDataFrameEqual` or row counts
5. Test edge cases: empty input, null values, schema mismatches

For detailed patterns, see `references/transformation-testing.md`.

### Using Fixtures Effectively
- **`spark` fixture**: Provides a local SparkSession for DataFrame operations
- **`ws` fixture**: Databricks WorkspaceClient for API interactions
- **`make_schema` fixture**: Creates ephemeral Unity Catalog schemas
- **Custom fixtures**: Define in `conftest.py` for project-wide reuse

For fixture patterns and best practices, see `references/fixtures.md`.

### Mocking External Dependencies
Use `pytest-mock` to isolate tests from external systems:
```python
def test_api_call(mocker):
    mock_response = mocker.Mock()
    mock_response.json.return_value = {"status": "ok"}
    mocker.patch("requests.get", return_value=mock_response)
    
    result = fetch_data()
    assert result["status"] == "ok"
```

For when and how to mock, see `references/mocking.md`.

### Testing SDP/Lakeflow Pipelines
Use `sdp-test` to test declarative pipelines locally:
1. Create YAML test definitions in `tests/`
2. Plugin discovers pipeline from `databricks.yml`
3. Runs against local SparkSession without remote cluster
4. Validates SQL queries and Python model decorators

For pipeline test patterns, see `references/sdp-testing.md`.

### Parametrized Tests
Test multiple scenarios with a single test function:
```python
@pytest.mark.parametrize("input_val,expected", [
    (0, 0),
    (1, 1),
    (-1, 0),
    (None, 0),
])
def test_clamp_values(input_val, expected):
    assert clamp(input_val) == expected
```

### Exception Testing
```python
def test_invalid_schema_raises(spark):
    with pytest.raises(ValueError, match="Column.*not found"):
        transform_bad_schema(spark.createDataFrame([]))
```

### Code Coverage
```bash
pytest --cov=src --cov-report=term-missing
pytest --cov=src --cov-report=html  # Open htmlcov/index.html
pytest --cov=src --cov-fail-under=80  # Fail if coverage < 80%
```

## Best Practices Summary

| Practice | Why |
|----------|-----|
| Prioritize unit tests | Fast feedback, isolate logic |
| Mock only external dependencies | Keep tests fast and reliable |
| Avoid over-mocking | Prevent brittle tests |
| Use fixtures for setup | Reduce boilerplate |
| Parametrize for coverage | Test edge cases efficiently |
| Validate schemas | Catch data quality issues early |
| Test locally first | Rapid iteration before deployment |
| Integrate with CI/CD | Catch regressions automatically |

## Common Pitfalls

- **Over-mocking**: Mocking too much makes tests brittle and disconnected from reality
- **Shared state**: Tests should be independent; use fixtures for isolation
- **Slow tests**: Keep unit tests local; reserve cluster tests for integration suites
- **Missing edge cases**: Use parametrization to cover nulls, empties, boundaries
- **No coverage goals**: Set minimum coverage thresholds in CI

## CI/CD Integration Example
```yaml
# .github/workflows/test.yml
- name: Run tests
  run: |
    pip install -e ".[test]"
    pytest --cov=src --cov-fail-under=80 -v
```
