# CI/CD Integration for PyTest

Automating data pipeline tests in CI/CD pipelines.

## GitHub Actions Example

### Basic Test Workflow
```yaml
name: Run PyTest Suite

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      
      - name: Install dependencies
        run: |
          pip install -e ".[test]"
      
      - name: Run unit tests
        run: |
          pytest tests/ -v --cov=src --cov-report=xml --cov-fail-under=80
      
      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: ./coverage.xml
```

### Integration Tests with Databricks
```yaml
  integration-test:
    runs-on: ubuntu-latest
    needs: test
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      
      - name: Install dependencies
        run: pip install -e ".[test,integration]"
      
      - name: Run integration tests
        env:
          DATABRICKS_HOST: ${{ secrets.DATABRICKS_HOST }}
          DATABRICKS_TOKEN: ${{ secrets.DATABRICKS_TOKEN }}
        run: |
          pytest tests/integration/ -v --junitxml=test-results.xml
      
      - name: Publish test results
        if: always()
        uses: dorny/test-reporter@v1
        with:
          name: Integration Tests
          path: test-results.xml
          reporter: java-junit
```

## Ephemeral Test Environments

Use unique schemas per test run to ensure isolation:

```python
# conftest.py
import pytest
import uuid

@pytest.fixture
def test_schema(make_schema):
    """Create unique schema per test run"""
    schema_name = f"test_{uuid.uuid4().hex[:8]}"
    schema = make_schema(name=schema_name)
    yield schema
    # Automatic cleanup via fixture
```

## Dependency Management with uv

```toml
# pyproject.toml
[project]
name = "data-pipeline"
version = "1.0.0"

[project.optional-dependencies]
test = [
    "pytest>=7.0",
    "pytest-mock>=3.10",
    "pytest-cov>=4.0",
    "databricks-labs-pytester",
    "sdp-test[spark]",
]
integration = [
    "databricks-sdk>=0.15",
]
```

```bash
# Install with test dependencies
uv pip install -e ".[test]"

# Run tests
uv run pytest
```

## Coverage Thresholds

```bash
# Fail if coverage drops below 80%
pytest --cov=src --cov-fail-under=80

# Generate HTML report for review
pytest --cov=src --cov-report=html

# Terminal report with missing lines
pytest --cov=src --cov-report=term-missing
```

## Best Practices

1. **Run unit tests on every PR**: Fast feedback loop
2. **Separate unit and integration tests**: Different triggers and environments
3. **Use secrets for credentials**: Never hardcode tokens
4. **Set coverage thresholds**: Prevent quality regression
5. **Publish test reports**: Visibility into failures
6. **Use ephemeral resources**: Avoid test interference
7. **Cache dependencies**: Speed up CI runs
