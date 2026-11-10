"""把整个网页跑一遍（Streamlit 自带的 AppTest，不用开浏览器），大模型换成假模型。"""
import json
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import askdata.config
import askdata.llm
from askdata.llm import ChatReply, ToolCall

APP = str(Path(__file__).resolve().parent.parent / "app.py")
SQL = ("select strftime(purchase_time, '%Y-%m') as 月份, count(*) as 订单量 from orders "
       "where year(purchase_time) = 2017 group by 1 order by 1")
ANSWER = "2017 年订单量从 1 月的 800 单涨到 11 月的 7,544 单。"


class FakeModel:
    """第一次调用写 SQL，第二次写结论和追问。"""

    def chat(self, messages, tools=None):
        if messages[-1]["role"] == "user":
            args = json.dumps({"sql": SQL, "chart": "line"}, ensure_ascii=False)
            return ChatReply(None, [ToolCall("c1", "run_sql", args)], 1000, 50)
        return ChatReply(f"{ANSWER}\n可以接着问：2018 年呢？｜哪个月增长最快？", [], 1200, 40)


@pytest.fixture()
def app(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    for name in ("ZHIPUAI_API_KEY", "ASKDATA_MAX_QUESTIONS", "ASKDATA_DAILY_LIMIT", "ASKDATA_MODELS"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(askdata.llm, "make_model", lambda key, api_key=None: FakeModel())
    monkeypatch.setattr(askdata.config, "load_env", lambda path: None)  # 不读本机的 .env，测试结果不受自己填的 key 影响
    st.cache_resource.clear()  # 每个测试用新的每日计数器
    yield AppTest.from_file(APP, default_timeout=60)
    st.cache_resource.clear()


def ask(at: AppTest, question: str) -> AppTest:
    at.chat_input[0].set_value(question)
    return at.run()


def test_landing_page_shows_examples(app):
    app.run()
    assert not app.exception
    assert app.title[0].value == "智能问数助手"
    assert len([b for b in app.button if b.key and b.key.startswith("ex_")]) == 6
    # 只配置了 DeepSeek 的 key，下拉框里就不出现智谱
    assert app.selectbox[0].options == ["DeepSeek Flash（默认）", "DeepSeek V4 Pro"]


def test_question_gets_answer_chart_and_follow_ups(app):
    app.run()
    ask(app, "2017 年每个月的订单量是多少？")
    assert not app.exception
    assert any(m.value == ANSWER for m in app.markdown)
    assert len(app.get("vega_lite_chart")) == 1
    assert not app.code  # SQL 标签没点开时不画代码块，省掉 1.5 MB 的高亮组件
    follow = [b.label for b in app.button if b.key and b.key.startswith("follow_")]
    assert follow == ["2018 年呢？", "哪个月增长最快？"]
    assert len(app.get("download_button")) == 1
    assert app.session_state["asked"] == 1
    # 点追问按钮，等于直接问这个问题
    next(b for b in app.button if b.label == "2018 年呢？").click().run()
    assert [r.question for _, r in app.session_state["history"]] == ["2017 年每个月的订单量是多少？", "2018 年呢？"]


def test_per_visitor_limit_survives_clearing_the_chat(app, monkeypatch):
    monkeypatch.setenv("ASKDATA_MAX_QUESTIONS", "1")
    app.run()
    ask(app, "2017 年每个月的订单量是多少？")
    next(b for b in app.button if b.label == "清空对话").click().run()
    ask(app, "再问一次")
    assert any("每人最多问 1 个问题" in w.value for w in app.warning)


def test_daily_limit_is_shared(app, monkeypatch):
    monkeypatch.setenv("ASKDATA_DAILY_LIMIT", "1")
    app.run()
    ask(app, "2017 年每个月的订单量是多少？")
    other = AppTest.from_file(APP, default_timeout=60)  # 另一个访客
    other.run()
    ask(other, "2017 年每个月的订单量是多少？")
    assert any("今天的演示额度已经用完" in w.value for w in other.warning)
