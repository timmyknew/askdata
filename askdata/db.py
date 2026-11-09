"""数据库：把数据装进内存里的 DuckDB，锁成只读，再给模型生成一份表结构说明。"""
from __future__ import annotations

import datetime as dt
import decimal
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import duckdb
import pandas as pd

from .sql_guard import UnsafeSQL, check_sql

OLIST_DIR = Path(__file__).resolve().parents[1] / "data" / "olist"


@dataclass
class Column:
    name: str
    type: str
    description: str = ""
    values: list[str] | None = None  # 取值不多的文本列：全部取值，按出现次数排序
    examples: list[str] | None = None  # 取值很多的列：几个例子


@dataclass
class Table:
    name: str
    description: str
    row_count: int
    columns: list[Column] = field(default_factory=list)


@dataclass
class QueryResult:
    sql: str
    data: pd.DataFrame | None = None
    error: str | None = None
    truncated: bool = False  # 结果超过 max_rows，只保留了前 max_rows 行
    seconds: float = 0.0

    @property
    def ok(self) -> bool:
        return self.error is None


class Database:
    def __init__(self, con: duckdb.DuckDBPyConnection, title: str,
                 meta: dict | None = None, notes: list[str] | None = None,
                 hide_values: set[str] | None = None):
        meta = meta or {}
        self.hide_values = hide_values or set()  # "表.列"：这些列不列出全部取值，只给例子
        self.con = con
        self.title = title
        self.notes = notes or []
        self.tables = [self._profile(name, *meta.get(name, ("", {})))
                       for name in self._table_names()]
        # 先建表、做完统计，再锁：之后任何 SQL 都碰不到文件系统，也改不了配置。
        con.execute("SET memory_limit = '1GB'")
        con.execute("SET threads = 2")
        con.execute("SET enable_external_access = false")
        con.execute("SET lock_configuration = true")

    # ---------- 构造 ----------
    @classmethod
    def olist(cls) -> "Database":
        from .datasets import OLIST_HIDE_VALUES, OLIST_META, OLIST_NOTES

        con = duckdb.connect()
        for path in sorted(OLIST_DIR.glob("*.parquet")):
            con.execute(f"CREATE TABLE {path.stem} AS SELECT * FROM read_parquet(?)", [path.as_posix()])
        return cls(con, "巴西 Olist 电商数据（2016–2018，约 10 万订单）", OLIST_META, OLIST_NOTES,
                   OLIST_HIDE_VALUES)

    @classmethod
    def from_frames(cls, frames: dict[str, pd.DataFrame], title: str) -> "Database":
        con = duckdb.connect()
        for name, frame in frames.items():
            con.register("_upload", frame)
            con.execute(f'CREATE TABLE "{name}" AS SELECT * FROM _upload')
            con.unregister("_upload")
        return cls(con, title)

    # ---------- 查询 ----------
    def run(self, sql: str, timeout: float = 10.0, max_rows: int = 1000) -> QueryResult:
        start = time.perf_counter()
        try:
            sql = check_sql(sql)
        except UnsafeSQL as e:
            return QueryResult(sql=sql, error=str(e))
        cur = self.con.cursor()  # 每次查询一个游标，多个用户同时查也互不影响
        timer = threading.Timer(timeout, cur.interrupt)
        timer.start()
        try:
            res = cur.execute(sql)
            names = [d[0] for d in res.description]
            rows = res.fetchmany(max_rows + 1)
        except duckdb.InterruptException:
            return QueryResult(sql=sql, error=f"查询超过 {timeout:g} 秒被中止，请简化查询或加筛选条件。",
                               seconds=time.perf_counter() - start)
        except duckdb.Error as e:
            return QueryResult(sql=sql, error=f"{type(e).__name__}: {e}", seconds=time.perf_counter() - start)
        finally:
            timer.cancel()
            cur.close()
        truncated = len(rows) > max_rows
        data = _to_frame(rows[:max_rows], names)
        return QueryResult(sql=sql, data=data, truncated=truncated, seconds=time.perf_counter() - start)

    # ---------- 表结构 ----------
    def _table_names(self) -> list[str]:
        rows = self.con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main' ORDER BY table_name"
        ).fetchall()
        return [r[0] for r in rows]

    def _profile(self, name: str, description: str, col_desc: dict[str, str]) -> Table:
        q = _quote(name)
        row_count = self.con.execute(f"SELECT count(*) FROM {q}").fetchone()[0]
        columns = []
        for col_name, col_type in self.con.execute(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_schema = 'main' AND table_name = ? ORDER BY ordinal_position", [name]
        ).fetchall():
            col = Column(col_name, col_type, col_desc.get(col_name, ""))
            c = _quote(col_name)
            if col_type == "VARCHAR" and not col_name.endswith("_id"):
                n_distinct = self.con.execute(f"SELECT count(DISTINCT {c}) FROM {q}").fetchone()[0]
                top = self.con.execute(
                    f"SELECT {c} FROM {q} WHERE {c} IS NOT NULL GROUP BY 1 ORDER BY count(*) DESC, 1 LIMIT 80"
                ).fetchall()
                if n_distinct <= 80 and f"{name}.{col_name}" not in self.hide_values:
                    col.values = [str(r[0]) for r in top]
                else:
                    col.examples = [str(r[0])[:40] for r in top[:3]]
            elif not col_name.endswith("_id"):
                lo, hi = self.con.execute(f"SELECT min({c}), max({c}) FROM {q}").fetchone()
                if lo is not None:
                    col.examples = [_short(lo), _short(hi)]
            columns.append(col)
        return Table(name, description, row_count, columns)

    def schema_text(self, level: str = "full") -> str:
        """给模型看的表结构。level="names" 只列表名和列名，用来做对照实验。"""
        if level == "names":
            return "\n".join(f"{t.name}({', '.join(c.name for c in t.columns)})" for t in self.tables)
        parts = []
        for t in self.tables:
            head = f"### {t.name}（{t.row_count:,} 行）"
            if t.description:
                head += f"：{t.description}"
            lines = [head]
            for c in t.columns:
                line = f"- {c.name} {c.type}"
                if c.description:
                    line += f"：{c.description}"
                if c.values is not None:
                    line += "。全部取值：" + "、".join(c.values)
                elif c.examples and c.type == "VARCHAR":
                    line += "。例：" + "、".join(c.examples)
                elif c.examples:
                    line += f"。范围：{c.examples[0]} ~ {c.examples[1]}"
                lines.append(line)
            parts.append("\n".join(lines))
        if self.notes:
            parts.append("### 说明\n" + "\n".join(f"- {n}" for n in self.notes))
        return "\n\n".join(parts)


def _quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _short(value) -> str:
    if isinstance(value, float):
        return f"{value:.4g}"
    if isinstance(value, dt.datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    return str(value)


def _to_frame(rows: list[tuple], names: list[str]) -> pd.DataFrame:
    """DuckDB 的结果转成 DataFrame：Decimal 转成浮点数，日期转成 pandas 时间类型，方便画图。"""
    names = _dedupe(names)
    data = pd.DataFrame.from_records(rows, columns=names)
    for name in names:
        values = [v for v in data[name] if v is not None]
        if not values:
            continue
        if all(isinstance(v, decimal.Decimal) for v in values):
            data[name] = data[name].astype("float64")
        elif all(isinstance(v, (dt.date, dt.datetime)) for v in values):
            data[name] = pd.to_datetime(data[name])
    return data


def _dedupe(names: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    out = []
    for n in names:
        if n in seen:
            seen[n] += 1
            out.append(f"{n}_{seen[n]}")
        else:
            seen[n] = 0
            out.append(n)
    return out


def clean_table_name(stem: str) -> str:
    """上传文件名变成合法表名：只留字母数字下划线，中文文件名就叫 uploaded。"""
    name = re.sub(r"\W+", "_", stem.encode("ascii", "ignore").decode()).strip("_").lower()
    if not name or name[0].isdigit():
        name = "uploaded" + (f"_{name}" if name else "")
    return name
