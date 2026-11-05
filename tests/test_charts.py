import pandas as pd

from askdata.charts import choose_chart, make_figure


def test_single_number_is_metric():
    spec = choose_chart(pd.DataFrame({"订单数": [99441]}))
    assert spec.kind == "metric" and spec.y == ["订单数"]


def test_one_row_of_numbers_is_metrics():
    spec = choose_chart(pd.DataFrame({"差评": [20.2], "好评": [11.0], "相差": [9.1]}))
    assert spec.kind == "metric" and spec.y == ["差评", "好评", "相差"]


def test_month_text_is_line():
    data = pd.DataFrame({"月份": ["2017-01", "2017-02", "2017-03"], "订单数": [800, 1780, 2682]})
    spec = choose_chart(data)
    assert (spec.kind, spec.x, spec.y) == ("line", "月份", ["订单数"])
    assert make_figure(data, spec) is not None


def test_category_vs_number_is_bar():
    data = pd.DataFrame({"类目": ["美妆健康", "手表礼品"], "销售额": [1.2e6, 1.1e6]})
    spec = choose_chart(data)
    assert (spec.kind, spec.x) == ("bar", "类目")
    assert make_figure(data, spec) is not None


def test_pie_hint_used_when_it_fits():
    data = pd.DataFrame({"支付方式": ["信用卡", "票据", "代金券"], "占比": [74.0, 19.0, 5.6]})
    assert choose_chart(data, hint="pie").kind == "pie"
    assert choose_chart(data, hint="table") is None


def test_no_chart_for_text_only_or_empty():
    assert choose_chart(pd.DataFrame({"a": ["x", "y"]})) is None
    assert choose_chart(pd.DataFrame({"a": []})) is None
