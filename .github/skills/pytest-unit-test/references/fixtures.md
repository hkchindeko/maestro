# PyTest Fixtures Reference

Comprehensive guide to using fixtures effectively in Databricks data pipeline testing.

## What Are Fixtures?

Fixtures are functions decorated with `@pytest.fixture` that provide reusable test data, setup complex environments, and manage resource teardown.

## Built-in Databricks Fixtures

From `databricks-labs-pytester`:

### `spark` Fixture
Provides a Databricks Connect Spark session:
```python
from databricks.labs.pytester.fixtures import spark

def test_with_databricks_spark(spark):
    df = spark.range(10)
    assert df.count() == 10
```

### `ws` Fixture (WorkspaceClient)
Initialize a Databricks WorkspaceClient:
```python
from databricks.labs.pytester.fixtures import ws

def test_workspace_api(ws):
    clusters = ws.clusters.list_clusters()
    assert len(clusters) >= 0
```

### `make_schema` Fixture
Create ephemeral Unity Catalog schemas:
```python
from databricks.labs.pytester.fixtures import make_schema

def test_with_isolated_schema(make_schema):
    schema = make_schema()
    # Tests run in isolated schema
    # Automatically cleaned up after test
```

## Custom Fixtures

### Basic Fixture
```python
@pytest.fixture
def sample_data(spark):
    return spark.createDataFrame([
        (1, "Alice", 25),
        (2, "Bob", 30),
        (3, "Charlie", 35)
    ], ["id", "name", "age"])
```

### Fixture with Teardown
```python
@pytest.fixture
def temp_directory():
    import tempfile
    import shutil
    
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)  # Cleanup after test
```

### Fixture with Parameters
```python
@pytest.fixture(params=["csv", "parquet", "delta"])
def file_format(request):
    return request.param

def test_read_various_formats(spark, file_format):
    # Test runs 3 times, once per format
    df = spark.read.format(file_format).load(f"data.{file_format}")
    assert df.count() > 0
```

## Fixture Scopes

| Scope | When Created | Use Case |
|-------|--------------|----------|
| `function` (default) | Each test | Isolated test data |
| `class` | Once per test class | Shared setup for related tests |
| `module` | Once per module | Expensive setup (SparkSession) |
| `session` | Once per test run | Global resources |

```python
@pytest.fixture(scope="module")
def spark_session():
    """Shared SparkSession for all tests in module"""
    spark = SparkSession.builder.appName("test").getOrCreate()
    yield spark
    spark.stop()
```

## Fixture Composition

Fixtures can call other fixtures:
```python
@pytest.fixture
def raw_data(spark):
    return spark.createDataFrame([(1, "a")], ["id", "value"])

@pytest.fixture
def cleaned_data(raw_data):
    return raw_data.filter(col("value").isNotNull())

def test_cleaned_data(cleaned_data):
    assert cleaned_data.count() == 1
```

## conftest.py

Place project-wide fixtures in `tests/conftest.py`:
```python
# tests/conftest.py
import pytest
from pyspark.sql import SparkSession

@pytest.fixture(scope="session")
def spark():
    spark = SparkSession.builder \
        .appName("test-session") \
        .config("spark.sql.shuffle.partitions", "4") \
        .getOrCreate()
    yield spark
    spark.stop()

@pytest.fixture
def sample_users(spark):
    return spark.createDataFrame([
        (1, "Alice", "Engineering"),
        (2, "Bob", "Sales"),
        (3, "Charlie", "Engineering")
    ], ["id", "name", "department"])
```

## Best Practices

1. **Use appropriate scope**: Don't use `session` scope if tests modify shared state
2. **Name fixtures descriptively**: `sample_users` not `data`
3. **Keep fixtures focused**: One fixture, one responsibility
4. **Use `yield` for teardown**: Ensures cleanup even on test failure
5. **Avoid fixture dependencies on external systems**: Mock or use local resources
6. **Document fixture behavior**: Add docstrings explaining what the fixture provides
