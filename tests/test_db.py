import datetime as dt
import decimal

import duckdb
import pandas as pd
import pytest

from askdata.db import Database, clean_table_name


@pytest.fixture()
def db():
    sales = pd.DataFrame({
        "city": ["北京", "上海", "北京", "深圳"],
        "amount": [10.5, 20.0, 5.5, 8.0],
        "day": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-02-01", "2024-02-03"]),
    })
    return Database.from_frames({"sales": sales}, "测试数据")


def test_run_returns_dataframe(db):
    res = db.run("select city, sum(amount) as total from sales group by 1 order by 2 desc")
    assert res.ok
    assert list(res.data.columns) == ["city", "total"]
    assert res.data.iloc[0].tolist() == ["上海", 20.0]


def test_decimal_and_date_become_plotable(db):
    res = db.run("select 1.25::decimal(10,2) as price, date '2024-01-01' as d")
    assert res.data["price"].dtype == "float64"
    assert pd.api.types.is_datetime64_any_dtype(res.data["d"])


def test_errors_are_returned_not_raised(db):
    res = db.run("select nope from sales")
    assert not res.ok and "nope" in res.error
    assert not db.run("delete from sales").ok


def test_max_rows_truncates(db):
    res = db.run("select * from range(50)", max_rows=10)
    assert res.ok and res.truncated and len(res.data) == 10


def test_timeout_interrupts_long_query(db):
    res = db.run("select count(*) from range(200000000) a, range(1000) b where a.range + b.range < 0",
                 timeout=0.3)
    assert not res.ok and "中止" in res.error


def test_engine_blocks_files_even_without_guard(db):
    # 绕过 check_sql 直接执行：数据库本身也读不了文件、改不了配置
    with pytest.raises(duckdb.Error):
        db.con.execute("select * from read_csv('/etc/passwd')")
    with pytest.raises(duckdb.Error):
        db.con.execute("set enable_external_access = true")


def test_schema_text_lists_values_and_ranges(db):
    text = db.schema_text()
    assert "### sales（4 行）" in text
    assert "全部取值：北京、上海、深圳" in text
    assert "范围：5.5 ~ 20" in text
    assert db.schema_text("names") == "sales(city, amount, day)"


@pytest.mark.parametrize("stem, expected", [
    ("Sales Report 2024", "sales_report_2024"),
    ("销售数据", "uploaded"),
    ("2024销售", "uploaded_2024"),
])
def test_clean_table_name(stem, expected):
    assert clean_table_name(stem) == expected
