import datetime as dt

import pandas as pd
import pytest

from evaluation.compare import is_refusal, number_match, results_match


def df(**cols):
    return pd.DataFrame(cols)


def test_extra_columns_and_order_are_fine():
    gold = df(category=["A", "B"], gmv=[10.0, 20.0])
    pred = df(排名=[1, 2], 类目=["B", "A"], 销售额=[20.0, 10.0])
    assert results_match(gold, pred)


def test_missing_column_or_wrong_rows_fail():
    gold = df(category=["A", "B"], gmv=[10.0, 20.0])
    assert not results_match(gold, df(category=["A", "B"]))
    assert not results_match(gold, df(category=["A", "C"], gmv=[10.0, 20.0]))
    assert not results_match(gold, df(category=["A", "B", "C"], gmv=[10.0, 20.0, 1.0]))
    assert not results_match(gold, None)


def test_counts_must_be_exact():
    assert results_match(df(n=[99441]), df(订单数=[99441]))
    assert not results_match(df(n=[99441]), df(订单数=[99440]))


@pytest.mark.parametrize("gold, pred, ok", [
    (0.6285133898, 0.63, True),  # 四舍五入到两位
    (0.6285133898, 0.6, True),  # 四舍五入到一位
    (3.118756, 0.0311875, True),  # 百分数和小数
    (12.4973, 12.5587, True),  # 1% 以内
    (12.4973, 13.0, False),
    (1.1417, 1.0, False),  # 平均数不能直接取整
    (6108492.27, 6108492.0, True),  # 大金额取整可以
    (6.7737, 8.1129, False),
])
def test_number_match(gold, pred, ok):
    assert number_match(gold, pred) is ok


def test_month_formats_are_equivalent():
    gold = df(m=["2017-01", "2017-02"], n=[800, 1780])
    pred = df(月份=[dt.date(2017, 1, 1), dt.date(2017, 2, 1)], 订单量=[800, 1780])
    assert results_match(gold, pred)
    pred2 = df(月份=pd.to_datetime(["2017-01-01", "2017-02-01"]), 订单量=[800, 1780])
    assert results_match(gold, pred2)


def test_year_as_text_or_number():
    assert results_match(df(y=[2016, 2017], n=[1, 2]), df(年份=["2016", "2017"], 订单=[1, 2]))


def test_small_numeric_answer_any_shape():
    gold = df(avg=[4.28, 2.26])  # 两行一列
    assert results_match(gold, df(按时=[4.28], 延迟=[2.26]))  # 一行两列
    assert results_match(gold, df(状态=["按时", "延迟"], 平均分=[4.28, 2.26]))
    assert not results_match(gold, df(按时=[4.28], 延迟=[3.0]))


def test_timestamps_match_text():
    gold = df(t=[dt.datetime(2016, 9, 4, 21, 15, 19)])
    assert results_match(gold, df(最早下单时间=["2016-09-04 21:15:19"]))


def test_refusal():
    assert is_refusal("数据里没有用户年龄信息，无法回答。", None)
    assert is_refusal("2019 年的销售额为 0。", df(s=[None]))
    assert not is_refusal("平均年龄 30 岁。", df(age=[30.0]))
