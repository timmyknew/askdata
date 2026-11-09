import pandas as pd
import pytest

from askdata.agent import RUN_SQL_TOOL, Agent, extract_sql, split_followups
from askdata.db import Database
from tests.fakes import ScriptedModel, sql_call, text


@pytest.fixture()
def db():
    orders = pd.DataFrame({
        "month": ["2024-01", "2024-01", "2024-02", "2024-03"],
        "category": ["玩具", "图书", "玩具", "图书"],
        "amount": [10.0, 20.0, 30.0, 40.0],
    })
    return Database.from_frames({"orders": orders}, "测试订单")


def test_happy_path(db):
    model = ScriptedModel([
        sql_call("select category as 类目, sum(amount) as 销售额 from orders group by 1 order by 2 desc",
                 chart="bar"),
        text("图书销售额最高，为 60 元。"),
    ])
    result = Agent(model, db).ask("哪个类目卖得最好？")
    assert result.ok and not result.self_corrected
    assert result.answer == "图书销售额最高，为 60 元。"
    assert result.data.iloc[0].tolist() == ["图书", 60.0]
    assert result.chart_hint == "bar"
    assert result.model_calls == 2 and result.prompt_tokens == 200
    # 第二次调用时，模型能看到 SQL 的执行结果
    tool_msg = model.calls[1][-1]
    assert tool_msg["role"] == "tool" and "图书 | 60" in tool_msg["content"]
    assert model.tools_seen[0] == [RUN_SQL_TOOL]


def test_error_is_fed_back_and_fixed(db):
    model = ScriptedModel([
        sql_call("select catgory, sum(amount) from orders group by 1"),
        sql_call("select category, sum(amount) from orders group by 1", call_id="call_2"),
        text("两个类目的销售额都是 40 和 60。"),
    ])
    result = Agent(model, db).ask("各类目销售额")
    assert result.ok and result.self_corrected
    assert [a.ok for a in result.attempts] == [False, True]
    feedback = model.calls[1][-1]["content"]
    assert feedback.startswith("执行出错") and "catgory" in feedback


def test_empty_result_prompts_a_retry(db):
    model = ScriptedModel([
        sql_call("select * from orders where category = '书籍'"),
        sql_call("select * from orders where category = '图书'", call_id="call_2"),
        text("图书有 2 笔订单。"),
    ])
    result = Agent(model, db).ask("图书有几笔订单？")
    assert "结果是空的" in model.calls[1][-1]["content"]
    assert len(result.data) == 2


def test_no_retry_mode_stops_after_first_failure(db):
    model = ScriptedModel([sql_call("select nope from orders"), text("不会被用到")])
    result = Agent(model, db, max_failures=1).ask("随便问")
    assert not result.ok and result.model_calls == 1
    assert "nope" in result.error


def test_gives_up_after_max_failures(db):
    model = ScriptedModel([sql_call("select bad1 from orders", f"c{i}") for i in range(3)])
    result = Agent(model, db, max_failures=3).ask("随便问")
    assert not result.ok and len(result.attempts) == 3
    assert result.answer.startswith("抱歉")


def test_text_mode_runs_sql_from_code_block(db):
    model = ScriptedModel([
        text("我来查一下：\n```sql\nselect count(*) as n from orders\n```"),
        text("一共有 4 笔订单。\n```sql\nselect count(*) as n from orders\n```"),
    ])
    result = Agent(model, db, use_tools=False).ask("一共几笔订单？")
    assert model.tools_seen == [None, None]
    assert result.data.iloc[0, 0] == 4
    assert result.answer == "一共有 4 笔订单。"  # 结论里重复的 SQL 代码块被去掉


def test_model_error_does_not_crash(db):
    model = ScriptedModel([RuntimeError("401 invalid api key")])
    result = Agent(model, db).ask("随便问")
    assert not result.ok and "401" in result.error


def test_follow_up_question_sees_previous_turn(db):
    first = Agent(ScriptedModel([sql_call("select sum(amount) as s from orders"), text("总额 100。")]), db)
    turn1 = first.ask("总销售额多少？")
    model = ScriptedModel([sql_call("select category, sum(amount) from orders group by 1"), text("按类目拆开。")])
    Agent(model, db).ask("按类目拆开呢？", history=[turn1])
    contents = [m["content"] for m in model.calls[0]]
    assert "总销售额多少？" in contents
    assert any("select sum(amount) as s from orders" in c for c in contents)


def test_system_prompt_contains_schema(db):
    prompt = Agent(ScriptedModel([]), db).system_prompt()
    assert "### orders（4 行）" in prompt and "run_sql" in prompt


def test_extract_sql_takes_last_block():
    assert extract_sql("```sql\nselect 1\n```\n然后\n```SQL\nselect 2\n```") == "select 2"
    assert extract_sql("没有代码") is None


def test_follow_up_suggestions_are_split_from_the_answer(db):
    model = ScriptedModel([
        sql_call("select category, sum(amount) from orders group by 1"),
        text("图书销售额最高，为 60 元。\n可以接着问：图书每个月卖多少？｜玩具为什么卖得少？"),
    ])
    result = Agent(model, db).ask("哪个类目卖得最好？")
    assert result.answer == "图书销售额最高，为 60 元。"
    assert result.followups == ["图书每个月卖多少？", "玩具为什么卖得少？"]


@pytest.mark.parametrize("reply", [
    "结论。\n\n**可以接着问：** A 问题？| B 问题？",
    "结论。\n可以接着问:\n1. A 问题？\n2. B 问题？",
    "结论。\n你还可以问：\n- A 问题？\n- B 问题？",
])
def test_split_followups_handles_common_formats(reply):
    assert split_followups(reply) == ("结论。", ["A 问题？", "B 问题？"])


def test_answer_without_follow_ups_is_unchanged():
    assert split_followups("这份数据里没有年龄信息。") == ("这份数据里没有年龄信息。", [])
