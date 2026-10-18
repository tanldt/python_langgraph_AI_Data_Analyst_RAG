import pytest
from app.core import safe_sql, build_graph

def test_safe_sql():
    assert safe_sql('SELECT month FROM sales LIMIT 10') == 'SELECT month FROM sales LIMIT 10'
    for value in ['DROP TABLE sales', 'SELECT * FROM sales; DELETE FROM sales', 'SELECT * FROM users', 'WITH x AS (SELECT * FROM sales) SELECT * FROM x']:
        with pytest.raises(ValueError):
            safe_sql(value)

def test_graph_compiles():
    assert build_graph() is not None
