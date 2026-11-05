"""SQL 安全检查：只放行一条只读查询。

这是第一道防线，负责给模型看得懂的报错；真正兜底的是数据库本身
（关掉文件读写、锁住配置，见 db.py）。
"""
from __future__ import annotations

import re

import duckdb


class UnsafeSQL(ValueError):
    pass


# 能读写文件、执行任意语句或查看系统信息的函数，一律不让用。
BLOCKED_FUNCTIONS = re.compile(
    r"\b(read_\w+|parquet_\w+|sniff_csv|glob|query|query_table|duckdb_\w+|pragma_\w+|"
    r"current_setting|getenv|system)\s*\(",
    re.IGNORECASE,
)


def strip_sql(sql: str) -> str:
    """去掉 Markdown 代码块标记和结尾分号。"""
    sql = sql.strip()
    fence = re.fullmatch(r"```(?:sql|duckdb)?\s*(.*?)\s*```", sql, flags=re.DOTALL | re.IGNORECASE)
    if fence:
        sql = fence.group(1)
    return sql.strip().rstrip(";").strip()


def check_sql(sql: str) -> str:
    """通过检查就返回清理后的 SQL，否则抛 UnsafeSQL（报错信息会反馈给模型）。"""
    sql = strip_sql(sql)
    if not sql:
        raise UnsafeSQL("SQL 是空的。")
    try:
        statements = duckdb.extract_statements(sql)
    except duckdb.Error as e:
        raise UnsafeSQL(f"SQL 语法错误：{e}") from e
    if len(statements) != 1:
        raise UnsafeSQL("一次只能执行一条 SQL 语句。")
    if statements[0].type != duckdb.StatementType.SELECT:
        raise UnsafeSQL("只允许查询（SELECT 或 WITH），不能修改数据或执行其他命令。")
    match = BLOCKED_FUNCTIONS.search(sql)
    if match:
        raise UnsafeSQL(f"不允许使用函数 {match.group(1)}()，请只查询已有的表。")
    if re.search(r"\bfrom\s+'", sql, flags=re.IGNORECASE):
        raise UnsafeSQL("不能直接查询文件，请只查询已有的表。")
    return sql
