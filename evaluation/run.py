"""批量评测。

    python -m evaluation.run                                   # 默认：deepseek-flash，三种配置，全部题目
    python -m evaluation.run --models deepseek-flash glm-4-flash
    python -m evaluation.run --ids e01 t01 --configs full      # 只跑几道题试试
    python -m evaluation.run --models oracle                   # 不花钱：用标准 SQL 检查评测流程本身

结果写在 results/<日期>/records.jsonl，跑完自动生成 report.md 和 summary.json。
中途断了直接重跑同一条命令即可：已经跑完的题会跳过，调用 API 出错的题会重跑。
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from askdata.agent import Agent, AgentResult
from askdata.config import load_env
from askdata.db import Database
from askdata.llm import ChatReply, ToolCall, make_model

from .compare import is_refusal, results_match
from .questions import QUESTIONS
from .report import build_report

ROOT = Path(__file__).resolve().parents[1]

# 三种配置逐步加功能，用来看每一步各带来多少提升
CONFIGS = {
    "baseline": {"label": "只给表名和列名，不纠错", "schema_level": "names", "max_failures": 1},
    "schema": {"label": "加上中文字段说明和业务口径", "schema_level": "full", "max_failures": 1},
    "full": {"label": "再加报错自动修正（线上配置）", "schema_level": "full", "max_failures": 3},
}


class OracleModel:
    """直接给出标准 SQL 的“满分模型”，用来检查评测流程和比对规则，不调用任何 API。"""

    name = "oracle"

    def __init__(self):
        self.by_question = {q["question"]: q for q in QUESTIONS}

    def chat(self, messages, tools=None):
        last_user = max(i for i, m in enumerate(messages) if m["role"] == "user")
        q = self.by_question[messages[last_user]["content"]]
        if last_user < len(messages) - 1 or q["gold"] is None:
            return ChatReply("数据里没有这项信息，无法回答。" if q["gold"] is None else "已完成查询。")
        return ChatReply(None, [ToolCall("oracle", "run_sql", json.dumps({"sql": q["gold"]}))])


def gold_frames(db: Database) -> dict[str, list]:
    frames = {}
    for q in QUESTIONS:
        if q["gold"] is None:
            continue
        frames[q["id"]] = []
        for sql in [q["gold"], *q.get("alt", [])]:
            res = db.run(sql, timeout=60, max_rows=10_000)
            if not res.ok:
                raise RuntimeError(f"{q['id']} 的标准 SQL 出错：{res.error}")
            frames[q["id"]].append(res.data)
    return frames


def grade(q: dict, result: AgentResult, golds: dict) -> bool:
    if q["gold"] is None:
        return is_refusal(result.answer, result.data)
    return result.ok and any(results_match(g, result.data) for g in golds[q["id"]])


def to_record(model_key: str, config: str, q: dict, result: AgentResult, correct: bool) -> dict:
    preview = None
    if result.ok:
        preview = json.loads(result.data.head(5).to_json(orient="values", date_format="iso", force_ascii=False))
    return {
        "model": model_key, "config": config, "id": q["id"], "difficulty": q["difficulty"], "topic": q["topic"],
        "question": q["question"], "refusal_question": q["gold"] is None, "correct": correct,
        "executed": result.ok, "self_corrected": result.self_corrected,
        "attempts": len(result.attempts), "failures": sum(not a.ok for a in result.attempts),
        "model_calls": result.model_calls, "prompt_tokens": result.prompt_tokens,
        "completion_tokens": result.completion_tokens, "seconds": round(result.seconds, 2),
        "sql": result.sql, "error": result.error, "answer": (result.answer or "")[:500], "preview": preview,
        "api_error": bool(result.error and result.error.startswith("调用模型出错")),
        "served_model": result.served_model, "time": dt.datetime.now().isoformat(timespec="seconds"),
    }


def load_done(path: Path) -> set[tuple]:
    done = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if not r["api_error"]:
                done.add((r["model"], r["config"], r["id"]))
    return done


def main(argv: list[str] | None = None) -> Path:
    parser = argparse.ArgumentParser(description="智能问数助手准确率评测")
    parser.add_argument("--models", nargs="+", default=["deepseek-flash"])
    parser.add_argument("--configs", nargs="+", default=list(CONFIGS), choices=list(CONFIGS))
    parser.add_argument("--ids", nargs="*", help="只跑这些题号")
    parser.add_argument("--limit", type=int, help="只跑前 N 道题")
    parser.add_argument("--workers", type=int, default=4, help="并发数；智谱免费模型限流时调小")
    parser.add_argument("--out", type=Path, default=ROOT / "results" / dt.date.today().isoformat())
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    load_env(ROOT / ".env")
    db = Database.olist()
    golds = gold_frames(db)
    questions = [q for q in QUESTIONS if not args.ids or q["id"] in args.ids][: args.limit]
    models = {key: OracleModel() if key == "oracle" else make_model(key) for key in args.models}

    args.out.mkdir(parents=True, exist_ok=True)
    records_path = args.out / "records.jsonl"
    done = load_done(records_path)
    tasks = [(m, c, q) for m in args.models for c in args.configs for q in questions if (m, c, q["id"]) not in done]
    print(f"共 {len(tasks)} 个任务（已完成 {len(done)} 个会跳过），结果写到 {args.out}")

    lock = threading.Lock()
    counter = {"n": 0}

    def run_one(model_key: str, config: str, q: dict) -> dict:
        cfg = CONFIGS[config]
        agent = Agent(models[model_key], db, schema_level=cfg["schema_level"], max_failures=cfg["max_failures"])
        result = agent.ask(q["question"])
        record = to_record(model_key, config, q, result, grade(q, result, golds))
        with lock:
            with records_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            counter["n"] += 1
            if not args.quiet:
                mark = "API出错" if record["api_error"] else ("✓" if record["correct"] else "✗")
                print(f"[{counter['n']}/{len(tasks)}] {model_key} {config:8s} {q['id']} {mark} "
                      f"调用 {record['model_calls']} 次 {record['seconds']}s")
        return record

    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = [pool.submit(run_one, *t) for t in tasks]
        for f in as_completed(futures):
            f.result()
    report = build_report(args.out, CONFIGS)
    print(f"完成，用时 {time.perf_counter() - start:.0f} 秒。报告：{report}")
    return args.out


if __name__ == "__main__":
    main()
