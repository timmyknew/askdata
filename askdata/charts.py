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
        return ChartSpec("pie", x=labels[0], y=numeric[:1])
    if hint == "scatter" and len(numeric) >= 2:
        return ChartSpec("scatter", x=numeric[0], y=[numeric[1]])
    if times and numeric and rows >= 2:
        return ChartSpec("line", x=times[0], y=numeric[:3])
    if labels and numeric and 2 <= rows <= 50:
        return ChartSpec("bar", x=labels[0], y=numeric[:1])
    if len(numeric) >= 2 and rows >= 5:
        return ChartSpec("scatter", x=numeric[0], y=[numeric[1]])
    return None


def make_figure(data: pd.DataFrame, spec: ChartSpec):
    """把 ChartSpec 画成 plotly 图；metric 不画图，由界面直接显示数字。"""
    import plotly.express as px

    if spec.kind == "line":
        frame = data.copy()
        if not pd.api.types.is_datetime64_any_dtype(frame[spec.x]):
            frame[spec.x] = pd.to_datetime(frame[spec.x].astype(str), errors="coerce")
        y = spec.y[0] if len(spec.y) == 1 else spec.y  # 单条线时 y 轴标题直接用列名
        fig = px.line(frame.sort_values(spec.x), x=spec.x, y=y, markers=len(frame) <= 40)
        fig.update_xaxes(tickformat="%Y-%m")
    elif spec.kind == "bar":
        labels = data[spec.x].astype(str)
        horizontal = len(data) > 8 or labels.str.len().max() > 6
        if horizontal:
            fig = px.bar(data, x=spec.y[0], y=spec.x, orientation="h")
            fig.update_yaxes(autorange="reversed", type="category", title_text="")  # 第一行放最上面，保持 SQL 的排序
        else:
            fig = px.bar(data, x=spec.x, y=spec.y[0])
            fig.update_xaxes(type="category")
    elif spec.kind == "pie":
        fig = px.pie(data, names=spec.x, values=spec.y[0], hole=0.4)
    elif spec.kind == "scatter":
        fig = px.scatter(data, x=spec.x, y=spec.y[0])
    else:
        return None
    height = 260 + 22 * len(data) if spec.kind == "bar" and len(data) > 8 else 380
    fig.update_layout(height=min(height, 900), margin=dict(l=8, r=8, t=24, b=8),
                      legend_title_text="", showlegend=len(spec.y) > 1 or spec.kind == "pie")
    return fig
