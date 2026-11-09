"""智能问数助手的网页界面。运行：streamlit run app.py"""
from __future__ import annotations

import io
import os
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from askdata.agent import Agent, AgentResult, Attempt
from askdata.charts import choose_chart, make_figure
from askdata.config import DEFAULT_MODEL, MODELS
from askdata.db import Database, clean_table_name
from askdata.llm import MissingAPIKey, make_model
from askdata.quota import DailyQuota

load_dotenv(Path(__file__).with_name(".env"))  # 读取和 app.py 同一个文件夹里的 .env
st.set_page_config(page_title="智能问数助手", page_icon="📊", layout="wide")

# 公开 Demo 的设置，都在部署平台的环境变量里填，本地运行不用管
MAX_QUESTIONS = int(os.getenv("ASKDATA_MAX_QUESTIONS") or 0)  # 每个访客最多问几次，0 表示不限
DAILY_LIMIT = int(os.getenv("ASKDATA_DAILY_LIMIT") or 0)  # 全站每天最多回答几次，0 表示不限
ONLY_MODELS = [k.strip() for k in os.getenv("ASKDATA_MODELS", "").split(",") if k.strip()]  # 只开放这些模型
EXAMPLES = [
    "2017 年每个月的订单量是多少？",
    "销售额最高的 10 个商品类目是哪些？",
    "各州的平均配送天数是多少？哪个州最慢？",
    "不同支付方式的订单占比是多少？",
    "差评（1–2 分）订单的平均配送天数，比好评（4–5 分）订单慢多少天？",
    "下过 2 单及以上的复购用户占全部用户的比例是多少？",
]


@st.cache_resource(show_spinner="正在加载数据…")
def olist_db() -> Database:
    return Database.olist()


@st.cache_resource
def daily_quota() -> DailyQuota:
    return DailyQuota(DAILY_LIMIT)  # cache_resource：所有访客共用同一个计数器


def usable_models() -> list[str]:
    """界面上能选的模型：配置了 key 的那些；一个 key 都没有时全部列出，并提示去填。"""
    keys = [k for k in MODELS if not ONLY_MODELS or k in ONLY_MODELS]
    ready = [k for k in keys if os.getenv(MODELS[k].api_key_env)]
    return ready or keys


def read_upload(file) -> Database:
    """CSV 或 Excel 变成一个数据库；Excel 的每个工作表是一张表。"""
    raw = file.getvalue()
    if file.name.lower().endswith(".csv"):
        try:
            frames = {clean_table_name(Path(file.name).stem): pd.read_csv(io.BytesIO(raw))}
        except UnicodeDecodeError:  # 国内导出的 CSV 常是 GBK 编码
            frames = {clean_table_name(Path(file.name).stem): pd.read_csv(io.BytesIO(raw), encoding="gbk")}
    else:
        sheets = pd.read_excel(io.BytesIO(raw), sheet_name=None)
        frames = {}
        for sheet, df in sheets.items():
            base = clean_table_name(str(sheet) if len(sheets) > 1 else Path(file.name).stem)
            name, n = base, 1
            while name in frames:  # 两个中文工作表名都会变成 uploaded，加编号区分
                n += 1
                name = f"{base}_{n}"
            frames[name] = df
    for df in frames.values():
        df.columns = [str(c).strip() or f"col_{i}" for i, c in enumerate(df.columns)]
    return Database.from_frames(frames, f"上传的文件 {file.name}")


def current_db() -> Database:
    if st.session_state.get("source") == "upload" and "upload_db" in st.session_state:
        return st.session_state.upload_db
    return olist_db()


def fmt_number(value) -> str:
    """1234.5 -> 1,234.5；最多两位小数，不补零。"""
    if pd.isna(value):
        return "—"
    return f"{value:,.2f}".rstrip("0").rstrip(".") if isinstance(value, float) else f"{int(value):,}"


def attempt_line(i: int, a: Attempt) -> str:
    if a.ok:
        return f"第 {i} 次执行：成功，{a.rows} 行，{a.seconds:.2f} 秒"
    return f"第 {i} 次执行：出错，已把报错发回给模型修正"


def show_result(result: AgentResult, key: str) -> None:
    if result.error and not result.ok:
        st.error(result.answer)
        with st.expander("错误详情"):
            st.code(result.error, language=None, wrap_lines=True)
    else:
        st.markdown(result.answer)

    if result.ok:
        spec = choose_chart(result.data, result.chart_hint)
        if spec and spec.kind == "metric":
            row = result.data.iloc[0]
            for col, name in zip(st.columns(len(spec.y)), spec.y):
                col.metric(f"{row[spec.x]} · {name}" if spec.x else name, fmt_number(row[name]), border=True)
        elif spec:
            st.plotly_chart(make_figure(result.data, spec), width="stretch", key=f"chart_{key}")

    tabs = st.tabs(["结果表", "SQL", "执行过程"])
    with tabs[0]:
        if result.ok:
            numbers = {c: st.column_config.NumberColumn(format="localized") for c in result.data.columns
                       if pd.api.types.is_float_dtype(result.data[c])}  # 金额等小数加千分位
            st.dataframe(result.data, hide_index=True, width="stretch", column_config=numbers)
            if result.truncated:
                st.caption("结果超过 1000 行，只显示前 1000 行。")
            st.download_button("下载 CSV", result.data.to_csv(index=False).encode("utf-8-sig"),  # 带 BOM，Excel 打开中文不乱码
                               file_name="查询结果.csv", mime="text/csv", key=f"csv_{key}")
        else:
            st.caption("没有结果。")
    with tabs[1]:
        st.code(result.sql or "（没有成功执行的 SQL）", language="sql", wrap_lines=True)
    with tabs[2]:
        for i, a in enumerate(result.attempts, 1):
            st.markdown(("✅ " if a.ok else "❌ ") + attempt_line(i, a))
            st.code(a.sql, language="sql", wrap_lines=True)
            if a.error:
                st.code(a.error, language=None, wrap_lines=True)
        tokens = result.prompt_tokens + result.completion_tokens
        st.caption(f"调用模型 {result.model_calls} 次，共 {tokens:,} tokens，用时 {result.seconds:.1f} 秒")
    if result.self_corrected:
        fails = sum(not a.ok for a in result.attempts)
        st.caption(f"第一次写的 SQL 出错，自动修正了 {fails} 次后得到结果。")


# ---------------- 侧边栏 ----------------
st.session_state.setdefault("history", [])  # [(数据集名, AgentResult)]
with st.sidebar:
    st.header("设置")
    choices = usable_models()
    model_key = st.selectbox("模型", choices, index=choices.index(DEFAULT_MODEL) if DEFAULT_MODEL in choices else 0,
                             format_func=lambda k: MODELS[k].label)
    if not os.getenv(MODELS[model_key].api_key_env):
        st.warning(f"还没有配置 {MODELS[model_key].api_key_env}，提问前请先在 .env 文件（部署时是平台的环境变量）里填写。")
    st.radio("数据", ["olist", "upload"], key="source", horizontal=True,
             format_func=lambda s: "内置电商数据" if s == "olist" else "上传文件")
    if st.session_state.source == "upload":
        file = st.file_uploader("上传 CSV 或 Excel（20 MB 以内）", type=["csv", "xlsx"])
        if file is not None and st.session_state.get("upload_name") != (file.name, file.size):
            try:
                st.session_state.upload_db = read_upload(file)
                st.session_state.upload_name = (file.name, file.size)
            except Exception as e:  # 文件格式不对时给出提示，而不是整页报错
                st.error(f"读取文件失败：{e}")
    db = current_db()
    with st.expander(f"表结构（{len(db.tables)} 张表）"):
        for t in db.tables:
            st.markdown(f"**{t.name}**　{t.description}（{t.row_count:,} 行）")
            st.dataframe(pd.DataFrame({"列": [c.name for c in t.columns], "类型": [c.type for c in t.columns],
                                       "说明": [c.description for c in t.columns]}),
                         hide_index=True, width="stretch")
    if st.button("清空对话", width="stretch"):
        st.session_state.history = []
        st.rerun()
    st.caption("内置数据：[Olist 巴西电商公开数据集](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)"
               "（CC BY-NC-SA 4.0），类目和州名由本项目译成中文。")

# ---------------- 主区域 ----------------
st.title("智能问数助手")
st.caption(f"用中文提问，自动写 SQL、查数据、画图、给结论。当前数据：{db.title}")

history: list[tuple[str, AgentResult]] = st.session_state.history
if not history and st.session_state.source == "olist":
    st.markdown("**试试这些问题：**")
    cols = st.columns(2)
    for i, example in enumerate(EXAMPLES):
        if cols[i % 2].button(example, key=f"ex_{i}", width="stretch"):
            st.session_state.pending = example

for i, (_, past) in enumerate(history):
    with st.chat_message("user"):
        st.markdown(past.question)
    with st.chat_message("assistant"):
        show_result(past, key=str(i))
        if i == len(history) - 1 and past.followups:  # 只给最新一轮显示追问按钮
            st.caption("可以接着问：")
            cols = st.columns(len(past.followups))
            for j, (col, follow) in enumerate(zip(cols, past.followups)):
                if col.button(follow, key=f"follow_{i}_{j}", icon=":material/subdirectory_arrow_right:",
                              width="stretch"):
                    st.session_state.pending = follow

question = st.chat_input("问点什么，比如：2018 年哪个类目的差评率最高？")
question = question or st.session_state.pop("pending", None)
if question:
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        asked = st.session_state.get("asked", 0)  # 单独计数：点“清空对话”不会重置
        if MAX_QUESTIONS and asked >= MAX_QUESTIONS:
            st.warning(f"这个公开演示每人最多问 {MAX_QUESTIONS} 个问题。想继续体验可以在本地运行，见 GitHub 说明。")
            st.stop()
        try:
            model = make_model(model_key)
        except MissingAPIKey as e:
            st.error(str(e))
            st.stop()
        if not daily_quota().take():
            st.warning("今天的演示额度已经用完了，明天再来试试，或者在本地运行，见 GitHub 说明。")
            st.stop()
        st.session_state.asked = asked + 1
        with st.status("正在分析…", expanded=True) as status:
            log = st.empty()
            lines: list[str] = []

            def on_attempt(a: Attempt) -> None:
                lines.append(attempt_line(len(lines) + 1, a))
                log.markdown("\n\n".join(lines))

            context = [r for name, r in history if name == db.title]
            result = Agent(model, db, on_attempt=on_attempt).ask(question, history=context)
            status.update(label=f"完成，用时 {result.seconds:.1f} 秒", state="complete" if result.ok else "error",
                          expanded=False)
        show_result(result, key=str(len(history)))
    history.append((db.title, result))
    st.rerun()  # 重新渲染一遍：示例问题收起，历史里显示这一轮
