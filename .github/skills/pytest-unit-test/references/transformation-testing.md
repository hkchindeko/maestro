# Transformation Testing Guide

Detailed patterns for testing PySpark transformation functions.

## DataFrame Assertions

### Using assertDataFrameEqual
```python
from pyspark.testing import assertDataFrameEqual

def test_transformation(spark):
    input_df = spark.createDataFrame([(1, "a"), (2, "b")], ["id", "value"])
    expected = spark.createDataFrame([(1, "A"), (2, "B")], ["id", "value"])
    
    result = uppercase_values(input_df, "value")
    
    assertDataFrameEqual(result, expected)
```

### Using assertSchemaEqual
```python
from pyspark.testing import assertSchemaEqual

def test_schema_preserved(spark):
    input_df = spark.createDataFrame([(1, "a")], ["id", "value"])
    result = transform(input_df)
    
    assertSchemaEqual(input_df.schema, result.schema)
```

### Manual Assertions
```python
def test_row_count(spark):
    df = spark.createDataFrame([(1,), (2,), (3,)], ["id"])
    result = filter_even(df)
    
    assert result.count() == 1
    assert result.collect()[0]["id"] == 2
```

## Testing Common Transformations

### Filter Operations
```python
def test_filter_nulls(spark):
    schema = StructType([
        StructField("id", IntegerType()),
        StructField("name", StringType())
    ])
    df = spark.createDataFrame([
        (1, "Alice"), (2, None), (3, "Bob"), (4, "")
    ], schema)
    
    result = df.filter(col("name").isNotNull() & (col("name") != ""))
    
    assert result.count() == 2
```

### Aggregations
```python
def test_group_by_sum(spark):
    df = spark.createDataFrame([
        ("A", 10), ("A", 20), ("B", 30)
    ], ["category", "value"])
    
    result = df.groupBy("category").agg(sum("value").alias("total"))
    
    expected = spark.createDataFrame([
        ("A", 30), ("B", 30)
    ], ["category", "total"])
    
    assertDataFrameEqual(result.orderBy("category"), expected.orderBy("category"))
```

### Joins
```python
def test_inner_join(spark):
    left = spark.createDataFrame([(1, "a"), (2, "b")], ["id", "val"])
    right = spark.createDataFrame([(1, "x"), (3, "y")], ["id", "other"])
    
    result = left.join(right, "id", "inner")
    
    assert result.count() == 1
    assert result.filter(col("id") == 1).count() == 1
```

## Edge Cases to Always Test

1. **Empty DataFrame**: `spark.createDataFrame([], schema)`
2. **All nulls in a column**
3. **Single row input**
4. **Duplicate rows**
5. **Schema mismatches**
6. **Special characters in strings**
7. **Boundary numeric values** (0, -1, max int, float precision)
8. **Date/time edge cases** (leap years, timezone shifts)

## Parametrized Transformation Tests

```python
@pytest.mark.parametrize("input_data,expected_count", [
    ([], 0),
    ([(1, "a")], 1),
    ([(1, None), (2, "b")], 1),
    ([(1, None), (2, None)], 0),
])
def test_filter_handles_various_inputs(spark, input_data, expected_count):
    schema = StructType([
        StructField("id", IntegerType()),
        StructField("value", StringType())
    ])
    df = spark.createDataFrame(input_data, schema) if input_data else spark.createDataFrame([], schema)
    
    result = df.filter(col("value").isNotNull())
    assert result.count() == expected_count
```
