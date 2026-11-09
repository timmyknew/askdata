"""比较模型查询结果和标准答案。

规则（宽松但不放水）
1. 标准答案的每一列，都要在模型结果里找到一列值完全对得上的；模型多出来的列不管。
2. 行数必须相同，行的顺序不管。
3. 整数（计数）必须完全相等；小数允许 1% 的相对误差，也允许模型四舍五入到 1 位以上小数；
   比例写成百分数还是小数（12.3 和 0.123）都算对。
4. 月份写成 '2017-01' 还是日期 2017-01-01，年份是 2017 还是 '2017'，都算同一个值。
5. 标准答案只有不超过 4 个数时，模型把这几个数放在任何行列位置都算对（比如两行一列和一行两列）。
"""
from __future__ import annotations

import datetime as dt
import math
import re
from itertools import permutations

import pandas as pd

_MONTH = re.compile(r"^(\d{4})-(\d{1,2})(?:-01)?(?: 00:00(?::00)?)?$")
_NUMBER = re.compile(r"^-?\d+(\.\d+)?$")
REL_TOL = 1e-2


def _is_null(v) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v)) or v is pd.NaT


def _norm_column(values: list) -> list:
    """一列值转成可比较的形式：数字→float，时间→字符串，月初日期→'YYYY-MM'。"""
    out = []
    times = [v for v in values if isinstance(v, (dt.date, dt.datetime, pd.Timestamp))]
    month_like = bool(times) and all(
        v.day == 1 and (not isinstance(v, dt.datetime) or (v.hour, v.minute, v.second) == (0, 0, 0)) for v in times)
    for v in values:
        if _is_null(v):
            out.append(None)
        elif isinstance(v, bool):
            out.append(float(v))
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            out.append(float(v))
        elif hasattr(v, "item") and not isinstance(v, (str, bytes)):  # numpy 标量
            out.append(float(v.item()) if isinstance(v.item(), (int, float)) else str(v))
        elif isinstance(v, (dt.date, dt.datetime, pd.Timestamp)):
            if month_like:
                out.append(f"{v.year:04d}-{v.month:02d}")
            elif isinstance(v, dt.datetime) and (v.hour, v.minute, v.second) != (0, 0, 0):
                out.append(v.strftime("%Y-%m-%d %H:%M:%S"))
            else:
                out.append(v.strftime("%Y-%m-%d"))
        else:
            s = str(v).strip()
            m = _MONTH.match(s)
            if m:
                out.append(f"{int(m.group(1)):04d}-{int(m.group(2)):02d}")
            elif _NUMBER.match(s):
                out.append(float(s))
            else:
                out.append(s)
    return out


def _decimals(x: float) -> int:
    text = repr(x)
    return len(text.split(".")[1]) if "." in text and "e" not in text else 0


def number_match(gold: float, pred: float) -> bool:
    if float(gold).is_integer() and abs(gold) < 1e7:  # 计数类整数：必须完全相等（或只差百分数换算）
        return any(math.isclose(g, pred, rel_tol=1e-9, abs_tol=1e-9) for g in (gold, gold * 100, gold / 100))
    for g in (gold, gold * 100, gold / 100):  # 比例写成百分数或小数都行
        if math.isclose(g, pred, rel_tol=REL_TOL, abs_tol=1e-9):
            return True
        d = _decimals(pred)
        if (d >= 1 or abs(g) >= 100) and d <= 4 and math.isclose(round(g, d), pred, abs_tol=1e-9):
            return True  # 模型做了四舍五入
    return False


def value_match(gold, pred) -> bool:
    if gold is None or pred is None:
        return gold is None and pred is None
    if isinstance(gold, float) and isinstance(pred, float):
        return number_match(gold, pred)
    return gold == pred


def _rows_match(gold_rows: list[tuple], pred_rows: list[tuple]) -> bool:
    """两组行（列已对齐）作为多重集合是否相等，数值带容差。"""
    if len(gold_rows) != len(pred_rows):
        return False
    used = [False] * len(pred_rows)
    for g in gold_rows:
        for j, p in enumerate(pred_rows):
            if not used[j] and all(value_match(a, b) for a, b in zip(g, p)):
                used[j] = True
                break
        else:
            return False
    return True


def _column_match(gold_col: list, pred_col: list) -> bool:
    return _rows_match([(v,) for v in gold_col], [(v,) for v in pred_col])


def results_match(gold: pd.DataFrame, pred: pd.DataFrame | None) -> bool:
    if pred is None:
        return False
    g_cols = [_norm_column(gold[c].tolist()) for c in gold.columns]
    p_cols = [_norm_column(pred[c].tolist()) for c in pred.columns]
    if len(gold) == len(pred) and len(g_cols) <= len(p_cols):
        candidates = [[j for j, pc in enumerate(p_cols) if _column_match(gc, pc)] for gc in g_cols]
        if all(candidates):
            for choice in _assignments(candidates):
                gold_rows = list(zip(*g_cols)) if g_cols else []
                pred_rows = list(zip(*[p_cols[j] for j in choice]))
                if _rows_match(gold_rows, pred_rows):
                    return True
    return _small_numeric_match(g_cols, p_cols)


def _assignments(candidates: list[list[int]], limit: int = 2000):
    """每个标准列选一个不重复的模型列；候选很少，直接枚举。"""
    count = 0

    def walk(i: int, chosen: list[int]):
        nonlocal count
        if count >= limit:
            return
        if i == len(candidates):
            count += 1
            yield list(chosen)
            return
        for j in candidates[i]:
            if j not in chosen:
                chosen.append(j)
                yield from walk(i + 1, chosen)
                chosen.pop()

    yield from walk(0, [])


def _small_numeric_match(g_cols: list[list], p_cols: list[list]) -> bool:
    gold_values = [v for col in g_cols for v in col]
    if not gold_values or len(gold_values) > 4 or not all(isinstance(v, float) for v in gold_values):
        return False
    pred_values = [v for col in p_cols for v in col if isinstance(v, float)]
    if len(pred_values) > 8:
        return False
    used = [False] * len(pred_values)
    for g in gold_values:
        for j, p in enumerate(pred_values):
            if not used[j] and number_match(g, p):
                used[j] = True
                break
        else:
            return False
    return True


REFUSAL_WORDS = ("没有", "无法", "不包含", "不存在", "缺少", "暂无", "不支持", "未包含", "并未", "不提供")


def is_refusal(answer: str, data: pd.DataFrame | None) -> bool:
    """数据里没有的问题：没查出东西、查出来是空或 0、或者回答里明确说了没有，都算正确拒答。"""
    if data is None or data.empty:
        return True
    values = [v for col in data.columns for v in _norm_column(data[col].tolist())]
    if all(v is None or v == 0.0 for v in values):
        return True
    return any(word in (answer or "") for word in REFUSAL_WORDS)
