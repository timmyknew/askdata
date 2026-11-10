"""问数 Agent：模型写 SQL → 执行 → 出错或结果为空就把信息反馈给模型修正 → 拿到结果后写结论。"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Callable

import pandas as pd

from .charts import CHART_KINDS
from .db import Database, QueryResult
from .llm import ChatModel

RUN_SQL_TOOL = {
    "type": "function",
    "function": {
        "name": "run_sql",
        "description": "在数据库上执行一条只读的 DuckDB SQL 查询，返回结果预览或报错信息。",
        "parameters": {
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "一条 DuckDB SQL（SELECT 或 WITH 开头）"},
                "chart": {"type": "string", "enum": list(CHART_KINDS),
                          "description": "结果适合怎么展示：bar 柱状、line 折线、pie 饼图、scatter 散点、"
                                         "table 只看表格；不确定就填 auto"},
            },
            "required": ["sql"],
        },
    },
}

SYSTEM_PROMPT = """你是一名资深数据分析师，帮业务同学用 SQL 回答关于数据的问题。
数据库是 DuckDB，请使用 DuckDB 的 SQL 写法，例如 date_trunc('month', t)、strftime(t, '%Y-%m')、date_diff('day', a, b)。

## 数据：{title}
{schema}

## 工作方式
1. 想清楚要用哪些表和字段，然后{how_to_run}。每次只写一条只读查询（SELECT 或 WITH）。
2. 结果是给人看的：列名用中文别名（如 AS "类目"），金额保留 2 位小数，比例用百分数并保留 1 位小数；
   排行类问题按指标排序，默认取前 10，除非用户要更多；按月统计时输出 'YYYY-MM' 格式的月份列。
   只输出回答问题需要的列，不要加和问题无关的列。别名用双引号，不要用单引号。
3. 问题要的是一个算出来的值（差值、增长率、倍数、占比）时，在 SQL 里直接算出来，单独放一列，可以同时保留中间数方便对照；
   问“哪个最高、最多、下降最多”时，按这个指标排序，让答案排在第一行。不要只查中间数再自己心算。
4. 执行报错或结果为空时，根据反馈信息修正后再执行。
5. 拿到正确结果后，用中文写 1 到 3 句结论，带上关键数字，只用结果里出现的数字，不要编造。
   结论之后另起一行，以“可以接着问：”开头，给出 2 个顺着结论往下挖的简短问题，用“｜”隔开。
6. 如果问题和这份数据无关，或者数据里没有需要的信息，直接说明，不要硬写 SQL。"""

HOW_TOOLS = "调用 run_sql 执行"
NUDGE = "请调用 run_sql 工具执行查询；如果数据里没有需要的信息，就直接说明。"
HOW_TEXT = "把 SQL 写在 ```sql 代码块里，我会替你执行并把结果发给你"

PREVIEW_ROWS = 20
FOLLOWUP_LINE = re.compile(r"^[ \t>*_#]*(?:可以接着问|你还可以问|还可以问|追问)[*_]*[ \t]*[:：]", re.MULTILINE)


@dataclass
class Attempt:
    sql: str
    ok: bool
    error: str | None = None
    rows: int | None = None
    seconds: float = 0.0


@dataclass
class AgentResult:
    question: str
    answer: str = ""
    sql: str | None = None  # 最后一次执行成功的 SQL
    data: pd.DataFrame | None = None
    truncated: bool = False
    chart_hint: str | None = None
    attempts: list[Attempt] = field(default_factory=list)
    model_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    seconds: float = 0.0
    error: str | None = None
    served_model: str | None = None  # 服务器实际返回的模型名（别名会随时间指向新版本，评测时要记下来）
    followups: list[str] = field(default_factory=list)  # 模型建议的追问，界面上做成按钮

    @property
    def ok(self) -> bool:
        return self.data is not None

    @property
    def self_corrected(self) -> bool:
        """先失败、后来自己改对了。"""
        return self.ok and any(not a.ok for a in self.attempts)


def extract_sql(text: str) -> str | None:
    """从模型的文字回复里找 SQL：```sql 代码块（不用工具调用时的写法），
    或者把工具调用直接写成了文字，比如 run_sql WITH …、run_sql(三引号包起来的 SELECT …)、{"sql": "…"}。"""
    blocks = re.findall(r"```(?:sql|duckdb)\s*(.*?)```", text or "", flags=re.DOTALL | re.IGNORECASE)
    if blocks:
        return blocks[-1].strip()
    return _sql_written_as_text(text or "")


_QUOTES = ('"""', "'''", '"', "'", "`")


def _sql_written_as_text(text: str) -> str | None:
    """有的模型（比如 GLM-4-Flash）提示词一长，就不走工具调用，而是把调用写成文字。只认以 run_sql、
    SELECT 或 WITH 开头的回复，普通的中文结论不会被当成 SQL。"""
    t = text.strip()
    named = re.match(r"run_sql\b[ \t]*[:：]?\s*", t, flags=re.IGNORECASE)
    if named:
        t = t[named.end():]
        if t.startswith("(") and t.endswith(")"):
            t = t[1:-1].strip()
    if t.startswith("{"):
        try:
            t = str(json.loads(t).get("sql", ""))
        except (ValueError, AttributeError):
            return None
    for q in _QUOTES:
        if t.startswith(q):
            t = t[len(q):]
            t = t[: -len(q)] if t.rstrip().endswith(q) else t
            break
    t = t.strip().rstrip(";").strip()
    if re.match(r"(?:WITH|SELECT)\b", t, flags=re.IGNORECASE):
        return t
    return None


def drop_unmatched_parens(sql: str) -> str:
    """去掉末尾多出来的右括号。模型偶尔把 run_sql(...) 的括号带进 SQL，执行会报语法错误。"""
    def balance(text: str) -> int:
        depth, quote = 0, None
        for ch in text:
            if quote:
                quote = None if ch == quote else quote
            elif ch in "'\"":
                quote = ch
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
        return depth

    sql = sql.strip()
    while sql.endswith(")") and balance(sql) < 0:
        sql = sql[:-1].rstrip()
    return sql


def split_followups(text: str) -> tuple[str, list[str]]:
    """把结论末尾的“可以接着问：A｜B”拆出来。模型没按格式写时，原样返回、没有追问。"""
    match = FOLLOWUP_LINE.search(text or "")
    if not match:
        return text, []
    questions = []
    for part in re.split(r"[｜|\n]", text[match.end():]):
        part = re.sub(r"^\s*(?:[-*•]|\d+[.、)）])\s*", "", part).strip(" *_\t")
        if 2 <= len(part) <= 60:
            questions.append(part)
    return text[:match.start()].rstrip(), questions[:3]


def preview(data: pd.DataFrame, rows: int = PREVIEW_ROWS) -> str:
    """结果的前几行，用竖线分隔，喂给模型看。"""
    def cell(v) -> str:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return "NULL"
        if isinstance(v, float):
            return f"{v:.6g}" if abs(v) < 1e6 else f"{v:.2f}"
        return str(v)[:40]

    head = data.head(rows)
    lines = [" | ".join(map(str, head.columns))]
    lines += [" | ".join(cell(v) for v in row) for row in head.itertuples(index=False)]
    return "\n".join(lines)


class Agent:
    def __init__(self, model: ChatModel, db: Database, *, max_failures: int = 3,
                 max_model_calls: int = 6, schema_level: str = "full", use_tools: bool = True,
                 history_turns: int = 3, on_attempt: Callable[[Attempt], None] | None = None):
        self.model = model
        self.db = db
        self.max_failures = max_failures  # 允许失败几次；1 表示不重试
        self.max_model_calls = max_model_calls
        self.schema_level = schema_level
        self.use_tools = use_tools
        self.history_turns = history_turns
        self.on_attempt = on_attempt  # 每执行完一条 SQL 回调一次，界面用它实时显示进度

    def system_prompt(self) -> str:
        return SYSTEM_PROMPT.format(title=self.db.title, schema=self.db.schema_text(self.schema_level),
                                    how_to_run=HOW_TOOLS if self.use_tools else HOW_TEXT)

    def ask(self, question: str, history: list[AgentResult] | None = None) -> AgentResult:
        start = time.perf_counter()
        result = AgentResult(question=question)
        messages = [{"role": "system", "content": self.system_prompt()}]
        for past in (history or [])[-self.history_turns:]:  # 多轮追问：带上前几轮的问题、SQL 和结论
            if past.sql:
                messages.append({"role": "user", "content": past.question})
                messages.append({"role": "assistant",
                                 "content": f"{past.answer}\n\n用到的 SQL：\n```sql\n{past.sql}\n```"})
        messages.append({"role": "user", "content": question})

        try:
            self._loop(messages, result)
        except Exception as e:  # 网络、key、限流等问题：告诉用户，不让页面崩掉
            result.error = f"调用模型出错：{type(e).__name__}: {e}"

        if not result.answer:
            if result.ok:
                result.answer = f"查询完成，共 {len(result.data)} 行结果。"
            elif result.error:
                result.answer = "抱歉，这次没能完成查询。"
            else:
                last = result.attempts[-1].error if result.attempts else "模型没有给出 SQL"
                result.error = f"多次尝试仍然失败：{last}"
                result.answer = "抱歉，这个问题我没能查出来，可以换个问法再试一次。"
        result.seconds = time.perf_counter() - start
        return result

    def _loop(self, messages: list[dict], result: AgentResult) -> None:
        failures, nudged = 0, False
        while result.model_calls < self.max_model_calls:
            reply = self.model.chat(messages, tools=[RUN_SQL_TOOL] if self.use_tools else None)
            result.model_calls += 1
            result.prompt_tokens += reply.prompt_tokens
            result.completion_tokens += reply.completion_tokens
            result.served_model = reply.model or result.served_model

            if reply.tool_calls:
                messages.append(reply.assistant_message())
                for call in reply.tool_calls:
                    if call.name != "run_sql":
                        feedback = f"没有叫 {call.name} 的工具，只能用 run_sql。"
                    else:
                        args = call.args()
                        hint = args.get("chart")
                        if hint in CHART_KINDS and hint != "auto":
                            result.chart_hint = hint
                        feedback, ok = self._execute(str(args.get("sql", "")), result)
                        failures += not ok
                    messages.append({"role": "tool", "tool_call_id": call.id, "content": feedback})
            else:
                text = (reply.content or "").strip()
                sql = extract_sql(text)
                if sql and sql != result.sql:  # 用文字写了一条新 SQL：执行它
                    messages.append({"role": "assistant", "content": text})
                    feedback, ok = self._execute(sql, result)
                    failures += not ok
                    messages.append({"role": "user", "content": feedback})
                elif not text and not result.attempts and not nudged:  # 空回复：提醒一次
                    nudged = True
                    messages.append({"role": "user", "content": NUDGE})
                else:  # 没有新 SQL：这就是最终结论
                    answer = re.sub(r"```(?:sql|duckdb).*?```", "", text, flags=re.DOTALL).strip()
                    result.answer, result.followups = split_followups(answer)
                    return
            if failures >= self.max_failures:
                return

    def _execute(self, sql: str, result: AgentResult) -> tuple[str, bool]:
        """执行一条 SQL，记下来，返回反馈给模型的话。"""
        sql = drop_unmatched_parens(sql)
        tried = {" ".join(a.sql.split()) for a in result.attempts if not a.ok}
        res: QueryResult = self.db.run(sql)
        if not res.ok:
            self._record(result, Attempt(res.sql, False, error=res.error, seconds=res.seconds))
            repeat = "这条 SQL 和之前失败的一模一样，请换一种写法。" if " ".join(sql.split()) in tried else ""
            return f"执行出错：{res.error}\n{repeat}请根据报错修正 SQL 后再执行，不要重复之前失败的写法。", False

        data = res.data
        self._record(result, Attempt(res.sql, True, rows=len(data), seconds=res.seconds))
        result.sql, result.data, result.truncated = res.sql, data, res.truncated
        if data.empty:
            return ("执行成功，但结果是空的（0 行）。请检查筛选条件的取值是否和数据一致"
                    "（比如类目名、状态值、日期范围），必要时先查一下可选值再重写。"), True
        shown = f"，下面是前 {PREVIEW_ROWS} 行" if len(data) > PREVIEW_ROWS else ""
        more = "（超过 1000 行，只保留了前 1000 行）" if res.truncated else ""
        return (f"执行成功，共 {len(data)} 行{more}{shown}：\n{preview(data)}\n\n"
                "如果结果已经能回答问题，就直接用中文写结论，不要再执行 SQL；"
                "如果结果不对，就修正后再执行。"), True

    def _record(self, result: AgentResult, attempt: Attempt) -> None:
        result.attempts.append(attempt)
        if self.on_attempt:
            self.on_attempt(attempt)
