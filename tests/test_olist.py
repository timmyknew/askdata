"""内置数据：表都在、行数对、关联键能连上。"""
import pytest

from askdata.db import Database

EXPECTED_ROWS = {
    "orders": 99441, "order_items": 112650, "payments": 103886, "reviews": 100000,
    "customers": 99441, "products": 32951, "sellers": 3095, "states": 27,
}


@pytest.fixture(scope="module")
def db():
    return Database.olist()


def test_tables_and_row_counts(db):
    assert {t.name: t.row_count for t in db.tables} == EXPECTED_ROWS


@pytest.mark.parametrize("sql", [
    "select count(*) from order_items i left join orders o using (order_id) where o.order_id is null",
    "select count(*) from order_items i left join products p using (product_id) where p.product_id is null",
    "select count(*) from orders o left join customers c using (customer_id) where c.customer_id is null",
    "select count(*) from customers c left join states s using (state) where s.state is null",
    "select count(*) from products where category_pt is not null and category is null",
])
def test_keys_join(db, sql):
    res = db.run(sql)
    assert res.ok and res.data.iloc[0, 0] == 0


def test_schema_mentions_chinese_categories(db):
    assert "家具装饰" in db.schema_text()
