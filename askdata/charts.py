"""根据查询结果的形状自动选图：时间序列画折线，类目对比画柱状，单个数字直接显示。"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import pandas as pd

CHART_KINDS = ("auto", "bar", "line", "pie", "scatter", "table")
_TIME_TEXT = re.compile(r"^\d{4}(-\d{1,2}){0,2}( \d{1,2}:\d{2}(:\d{2})?)?$")  # 2017、2017-01、2017-01-05


@dataclass
class ChartSpec:
    kind: str  # metric / bar / line / pie / scatter
    x: str | None = None
    y: list[str] = field(default_factory=list)


def _is_time(series: pd.Series) -> bool:
    if pd.api.types.is_datetime64_any_dtype(series):
        return True
    if pd.api.types.is_numeric_dtype(series) or series.dropna().empty:
        return False
    return series.dropna().astype(str).map(lambda v: bool(_TIME_TEXT.match(v))).all()


def _main_measure(data: pd.DataFrame, numeric: list[str]) -> str:
    """柱状图和饼图画哪一列数字。

    结果里常有好几列数字（比如“已送达订单数”和“平均配送天数”）。模型一般按问题要的那个指标排序，
    所以优先选结果按它排好序的列；几列都排好序时取最后一列，都没排序时取最后一个数值列
    （指标通常写在 SELECT 的最后）。排名列（1、2、3……）不算。
    """
    def is_rank(s: pd.Series) -> bool:
        return s.tolist() == list(range(1, len(s) + 1))

    def sorted_by(c: str) -> bool:
        s = data[c].dropna()
        return s.nunique() > 1 and (s.is_monotonic_increasing or s.is_monotonic_decreasing) and not is_rank(s)

    candidates = [c for c in numeric if not is_rank(data[c].dropna())] or numeric
    ordered = [c for c in candidates if sorted_by(c)]
    return (ordered or candidates)[-1]


def choose_chart(data: pd.DataFrame | None, hint: str | None = None) -> ChartSpec | None:
    """返回 None 表示只显示表格。hint 是模型建议的图表类型，不合适时忽略。"""
    if data is None or data.empty or hint == "table":
        return None
    numeric = [c for c in data.columns if pd.api.types.is_numeric_dtype(data[c])
               and not pd.api.types.is_bool_dtype(data[c])]
    times = [c for c in data.columns if c not in numeric and _is_time(data[c])]
    labels = [c for c in data.columns if c not in numeric and c not in times]
    rows = len(data)

    if rows == 1 and numeric and len(labels) <= 1 and len(numeric) <= 4:  # 一行几个数：直接显示数字
        return ChartSpec("metric", x=labels[0] if labels else None, y=numeric)
    if hint == "pie" and labels and numeric and 2 <= rows <= 10:
        return ChartSpec("pie", x=labels[0], y=[_main_measure(data, numeric)])
    if hint == "scatter" and len(numeric) >= 2:
        return ChartSpec("scatter", x=numeric[0], y=[numeric[1]])
    if times and numeric and rows >= 2:
        return ChartSpec("line", x=times[0], y=numeric[:3])
    if labels and numeric and 2 <= rows <= 50:
        return ChartSpec("bar", x=labels[0], y=[_main_measure(data, numeric)])
    if len(numeric) >= 2 and rows >= 5:
        return ChartSpec("scatter", x=numeric[0], y=[numeric[1]])
    return None


def make_chart(data: pd.DataFrame, spec: ChartSpec):
    """把 ChartSpec 画成 Altair 图；metric 不画图，由界面直接显示数字。

    用 Altair（Streamlit 自带的 Vega-Lite）而不是 Plotly：网页要下载的前端文件少 4.7 MB，
    部署平台不压缩文件时，图表能快很多出来。
    """
    import altair as alt

    if spec.kind not in ("line", "bar", "pie", "scatter"):
        return None
    # 列名里的点、方括号会被 Vega-Lite 当成嵌套字段，先换成安全的名字，坐标轴标题再用原名
    cols = [spec.x, *spec.y]
    safe = {c: f"c{i}" for i, c in enumerate(cols)}
    frame = data[cols].rename(columns=safe)
    x, ys = safe[spec.x], [safe[c] for c in spec.y]
    tooltip = [alt.Tooltip(safe[c], title=str(c)) for c in cols]

    if spec.kind == "line":
        if not pd.api.types.is_datetime64_any_dtype(frame[x]):
            frame[x] = pd.to_datetime(frame[x].astype(str), errors="coerce")
        frame = frame.sort_values(x)
        x_axis = alt.X(f"{x}:T", title=str(spec.x), axis=alt.Axis(format="%Y-%m"))
        if len(ys) == 1:
            chart = alt.Chart(frame).mark_line(point=len(frame) <= 40).encode(
                x=x_axis, y=alt.Y(f"{ys[0]}:Q", title=str(spec.y[0])), tooltip=tooltip)
        else:  # 多条线：转成长表，用颜色区分
            names = {safe[c]: str(c) for c in spec.y}
            long = frame.melt(id_vars=[x], value_vars=ys, var_name="series", value_name="value")
            long["series"] = long["series"].map(names)
            chart = alt.Chart(long).mark_line(point=len(frame) <= 40).encode(
                x=x_axis, y=alt.Y("value:Q", title=None),
                color=alt.Color("series:N", title=None, legend=alt.Legend(orient="top")),
                tooltip=[alt.Tooltip(f"{x}:T", title=str(spec.x), format="%Y-%m"),
                         alt.Tooltip("series:N", title="指标"), alt.Tooltip("value:Q", title="数值")])
        height = 380
    elif spec.kind == "bar":
        frame[x] = frame[x].astype(str)
        order = frame[x].tolist()  # 保持 SQL 的排序
        horizontal = len(frame) > 8 or frame[x].str.len().max() > 6
        cat = alt.X if not horizontal else alt.Y
        num = alt.Y if not horizontal else alt.X
        enc = {("y" if horizontal else "x"): cat(f"{x}:N", sort=order, title=None if horizontal else str(spec.x),
                                                  axis=alt.Axis(labelLimit=220, labelAngle=0)),
               ("x" if horizontal else "y"): num(f"{ys[0]}:Q", title=str(spec.y[0]))}
        chart = alt.Chart(frame).mark_bar().encode(**enc, tooltip=tooltip)
        height = min(260 + 22 * len(frame), 900) if horizontal and len(frame) > 8 else 380
    elif spec.kind == "pie":
        frame[x] = frame[x].astype(str)
        chart = alt.Chart(frame).mark_arc(innerRadius=70).encode(
            theta=alt.Theta(f"{ys[0]}:Q"), color=alt.Color(f"{x}:N", title=str(spec.x), sort=frame[x].tolist()),
            tooltip=tooltip)
        height = 380
    else:  # scatter
        chart = alt.Chart(frame).mark_circle(size=60, opacity=0.7).encode(
            x=alt.X(f"{x}:Q", title=str(spec.x)), y=alt.Y(f"{ys[0]}:Q", title=str(spec.y[0])), tooltip=tooltip)
        height = 380
    return chart.properties(height=height)
