# Mocking Guide

When and how to mock external dependencies in data pipeline tests.

## When to Mock

| Mock | Reason |
|------|--------|
| External APIs | Unpredictable, slow, rate-limited |
| Database connections | Expensive, stateful |
| File system I/O | Slow, environment-dependent |
| Time-dependent functions | Non-deterministic |
| Spark cluster operations | Requires remote resources |

## When NOT to Mock

- Pure transformation logic (test the real code)
- DataFrame operations (use local SparkSession)
- Schema validations (test against real schemas)
- Simple utility functions

## Using pytest-mock

### Basic Mocking
```python
def test_api_fetch(mocker):
    mock_response = mocker.Mock()
    mock_response.json.return_value = {"data": [1, 2, 3]}
    mocker.patch("requests.get", return_value=mock_response)
    
    result = fetch_api_data("https://api.example.com")
    assert result == [1, 2, 3]
```

### Mock with Side Effects
```python
def test_api_error_handling(mocker):
    mocker.patch("requests.get", side_effect=ConnectionError("Network error"))
    
    with pytest.raises(ConnectionError):
        fetch_api_data("https://api.example.com")
```

### Verifying Mock Calls
```python
def test_api_called_correctly(mocker):
    mock_get = mocker.patch("requests.get")
    mock_get.return_value.json.return_value = {"status": "ok"}
    
    fetch_api_data("https://api.example.com", timeout=30)
    
    mock_get.assert_called_once_with(
        "https://api.example.com",
        timeout=30
    )
```

### Mocking Spark DataFrame Reads
```python
def test_read_from_delta(mocker, spark):
    mock_df = spark.createDataFrame([(1, "a")], ["id", "value"])
    mocker.patch("pyspark.sql.DataFrameReader.load", return_value=mock_df)
    
    result = read_delta_table("path/to/table")
    assert result.count() == 1
```

### Mocking Time
```python
def test_time_dependent_logic(mocker):
    mock_now = mocker.patch("datetime.datetime.now")
    mock_now.return_value = datetime(2024, 1, 1, 12, 0, 0)
    
    result = get_current_hour_bucket()
    assert result == "2024-01-01-12"
```

## Mock Patterns for Data Pipelines

### Mocking External Data Sources
```python
@pytest.fixture
def mock_external_api(mocker):
    """Mock an external API that provides reference data"""
    mock_response = mocker.Mock()
    mock_response.json.return_value = {
        "countries": [
            {"code": "US", "name": "United States"},
            {"code": "UK", "name": "United Kingdom"}
        ]
    }
    mocker.patch("requests.get", return_value=mock_response)
    return mock_response

def test_enrich_with_country_data(spark, mock_external_api):
    input_df = spark.createDataFrame([("US",), ("UK",), ("XX",)], ["code"])
    result = enrich_with_country_data(input_df)
    
    assert result.filter(col("name").isNull()).count() == 1  # XX has no match
```

### Mocking File System
```python
def test_read_csv_from_path(mocker, spark):
    mock_df = spark.createDataFrame([(1, "test")], ["id", "name"])
    mocker.patch("pyspark.sql.SparkSession.read.csv", return_value=mock_df)
    
    result = load_csv_data("s3://bucket/data.csv")
    assert result.count() == 1
```

### Mocking Databricks Utilities
```python
def test_dbutils_mock(mocker):
    mock_dbutils = mocker.Mock()
    mock_dbutils.fs.ls.return_value = [
        mocker.Mock(name="file1.parquet"),
        mocker.Mock(name="file2.parquet")
    ]
    mocker.patch("pyspark.dbutils.DBUtils", return_value=mock_dbutils)
    
    files = list_files("/mnt/data")
    assert len(files) == 2
```

## Best Practices

1. **Mock at the boundary**: Mock the interface, not the internals
2. **Use `mocker.patch.object`** for class methods
3. **Use `mocker.patch`** for module-level functions
4. **Set `return_value`** for predictable outputs
5. **Use `side_effect`** for exceptions or dynamic responses
6. **Verify interactions** with `assert_called_*` methods
7. **Keep mocks minimal**: Only mock what's necessary
8. **Document mock behavior**: Explain what the mock represents
