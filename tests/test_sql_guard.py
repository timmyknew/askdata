import pytest

from askdata.sql_guard import UnsafeSQL, check_sql, strip_sql


@pytest.mark.parametrize("sql", [
    "SELECT 1",
    "with t as (select 1 as a) select a from t",
    "```sql\nSELECT count(*) FROM orders;\n```",
    "select read_count from t",  # 列名里带 read_ 不算调用函数
])
def test_allows_single_select(sql):
    assert check_sql(sql).lower().lstrip("`").startswith(("select", "with"))


@pytest.mark.parametrize("sql, message", [
    ("", "空"),
    ("select 1; select 2", "一条"),
    ("drop table orders", "只允许查询"),
    ("insert into orders values (1)", "只允许查询"),
    ("pragma version", "只允许查询"),
    ("copy orders to 'x.csv'", "只允许查询"),
    ("attach 'x.db'", "只允许查询"),
    ("select * from read_csv('/etc/passwd')", "read_csv"),
    ("select * from READ_PARQUET ('a.parquet')", "READ_PARQUET"),
    ("select * from query('select 1')", "query"),
    ("select * from duckdb_settings()", "duckdb_settings"),
    ("select * from 'secret.csv'", "文件"),
    ("selec 1", "语法错误"),
])
def test_rejects(sql, message):
    with pytest.raises(UnsafeSQL, match=message):
        check_sql(sql)


def test_strip_sql_removes_fence_and_semicolon():
    assert strip_sql("```SQL\nselect 1;\n```") == "select 1"
