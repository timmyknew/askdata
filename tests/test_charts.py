import pandas as pd

from askdata.charts import choose_chart, make_chart


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
    assert make_chart(data, spec) is not None


def test_category_vs_number_is_bar():
    data = pd.DataFrame({"类目": ["美妆健康", "手表礼品"], "销售额": [1.2e6, 1.1e6]})
    spec = choose_chart(data)
    assert (spec.kind, spec.x) == ("bar", "类目")
    assert make_chart(data, spec) is not None


def test_pie_hint_used_when_it_fits():
    data = pd.DataFrame({"支付方式": ["信用卡", "票据", "代金券"], "占比": [74.0, 19.0, 5.6]})
    assert choose_chart(data, hint="pie").kind == "pie"
    assert choose_chart(data, hint="table") is None


def test_no_chart_for_text_only_or_empty():
    assert choose_chart(pd.DataFrame({"a": ["x", "y"]})) is None
    assert choose_chart(pd.DataFrame({"a": []})) is None


def _spec(data, hint=None):
    spec = choose_chart(data, hint)
    return spec, make_chart(data, spec).to_dict()


def test_bar_keeps_sql_order_and_goes_horizontal_for_many_rows():
    data = pd.DataFrame({"州": [f"S{i}" for i in range(12)], "平均天数": list(range(12, 0, -1))})
    spec, chart = _spec(data)
    y = chart["encoding"]["y"]
    assert spec.kind == "bar" and chart["mark"]["type"] == "bar"
    assert y["sort"] == [f"S{i}" for i in range(12)]  # 不按字母重排，保持 SQL 的顺序
    assert chart["encoding"]["x"]["title"] == "平均天数"


def test_column_names_with_dots_are_safe():
    # 列名里有点或方括号时，Vega-Lite 会当成嵌套字段，图就画不出来
    data = pd.DataFrame({"avg(o.days)": ["a", "b"], "share[%]": [1.5, 2.5]})
    spec, chart = _spec(data)
    fields = {chart["encoding"]["x"]["field"], chart["encoding"]["y"]["field"]}
    assert fields == {"c0", "c1"}
    assert chart["encoding"]["x"]["title"] == "avg(o.days)" and chart["encoding"]["y"]["title"] == "share[%]"


def test_several_series_become_coloured_lines():
    data = pd.DataFrame({"月份": ["2017-01", "2017-02"], "订单量": [800, 1780], "用户数": [790, 1700]})
    spec, chart = _spec(data)
    assert spec.kind == "line" and chart["encoding"]["color"]["field"] == "series"


def test_pie_and_scatter_render():
    pie = pd.DataFrame({"支付方式": ["信用卡", "票据", "代金券"], "占比": [74.0, 19.0, 5.6]})
    assert _spec(pie, "pie")[1]["mark"]["type"] == "arc"
    points = pd.DataFrame({"价格": [1.0, 2, 3, 4, 5], "运费": [2.0, 3, 1, 5, 4]})
    assert _spec(points, "scatter")[1]["mark"]["type"] == "circle"
