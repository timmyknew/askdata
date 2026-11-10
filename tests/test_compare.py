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
    assert not results_match(gold, df(category=["C", "A", "B"], gmv=[1.0, 10.0, 20.0]))  # 多出的行排在前面
    assert not results_match(gold, None)


def test_extra_rows_after_the_answer_are_fine():
    """问“哪个最多”，模型给了排好序的前几名：只看前 N 行。"""
    gold = df(city=["sao paulo"])
    assert results_match(gold, df(城市=["sao paulo", "rio de janeiro", "belo horizonte"], 用户数=[15540, 6882, 2773]))
    assert not results_match(gold, df(城市=["rio de janeiro", "sao paulo"], 用户数=[6882, 15540]))  # 答案不在第一行
    top3 = df(state=["RR", "AL", "MA"], score=[3.61, 3.75, 3.76])
    assert results_match(top3, df(州=["AL", "RR", "MA", "SE", "PA"], 平均分=[3.75, 3.61, 3.76, 3.80, 3.84]))
    assert not results_match(top3, df(州=["RR", "AL", "SE", "MA"], 平均分=[3.61, 3.75, 3.80, 3.76]))
    single = df(n=[17])  # 只有一个数的答案，模型给了前 10 名的排行，第一行的数对就行
    counts = [17, 9, 7, 7, 6, 6, 6, 6, 5, 5]
    assert results_match(single, df(用户=[f"u{i}" for i in range(10)], 订单数=counts))
    assert not results_match(single, df(用户=[f"u{i}" for i in range(10)], 订单数=counts[1:] + [17]))


def test_long_answers_are_not_cut():
    """标准答案超过 10 行时（比如 12 个月的明细），模型多给的行不能忽略。"""
    months = [f"2017-{m:02d}" for m in range(1, 13)]
    gold = df(m=months, n=list(range(12)))
    assert not results_match(gold, df(月份=months + ["2018-01"], 订单量=list(range(13))))


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


def test_quarter_formats_are_equivalent():
    gold = df(q=[1, 2, 3, 4], n=[21208, 19979, 12216, 4])
    for labels in (["2018-Q1", "2018-Q2", "2018-Q3", "2018-Q4"], ["Q1", "Q2", "Q3", "Q4"],
                   ["2018年第1季度", "2018年第2季度", "2018年第3季度", "2018年第4季度"], ["第一季度", "第二季度", "第三季度", "第四季度"]):
        assert results_match(gold, df(季度=labels, 订单量=[21208, 19979, 12216, 4])), labels
    assert not results_match(gold, df(季度=["2018-Q2", "2018-Q1", "2018-Q3", "2018-Q4"], 订单量=[21208, 19979, 12216, 4]))


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
