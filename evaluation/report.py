"""把 records.jsonl 汇总成 report.md（给人看）和 summary.json（给网页读）。

    python -m evaluation.report results/2026-11-08
"""
from __future__ import annotations

import datetime as dt
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

DIFFICULTY = {"easy": "易", "medium": "中", "hard": "难"}


def load_records(out_dir: Path) -> list[dict]:
    """同一个（模型, 配置, 题号）可能跑过多次（比如 API 出错后重跑），只保留最后一次。"""
    latest = {}
    path = Path(out_dir) / "records.jsonl"
    for line in path.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        latest[(r["model"], r["config"], r["id"])] = r
    return list(latest.values())


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """准确率的 95% Wilson 置信区间。题目只有一百来道，区间比点估计更诚实。"""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    center = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (max(0.0, center - half), min(1.0, center + half))


def mcnemar_exact(b: int, c: int) -> float:
    """配对比较两种配置：b = 只有 A 对，c = 只有 B 对。精确二项检验，双侧 p 值。"""
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def _pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def build_report(out_dir: Path, configs: dict) -> Path:
    out_dir = Path(out_dir)
    records = load_records(out_dir)
    graded = [r for r in records if not r["refusal_question"] and not r["api_error"]]
    models = sorted({r["model"] for r in records})
    config_order = [c for c in configs if any(r["config"] == c for r in records)]

    by_key = defaultdict(list)
    for r in graded:
        by_key[(r["model"], r["config"])].append(r)

    overall = []
    for m in models:
        for c in config_order:
            rows = by_key[(m, c)]
            if not rows:
                continue
            k, n = sum(r["correct"] for r in rows), len(rows)
            lo, hi = wilson(k, n)
            overall.append({
                "model": m, "config": c, "label": configs[c]["label"], "correct": k, "n": n,
                "accuracy": k / n, "ci": [lo, hi],
                "executed": sum(r["executed"] for r in rows) / n,
                "self_corrected": sum(r["self_corrected"] for r in rows),
                "avg_calls": sum(r["model_calls"] for r in rows) / n,
                "avg_tokens": sum(r["prompt_tokens"] + r["completion_tokens"] for r in rows) / n,
                "avg_seconds": sum(r["seconds"] for r in rows) / n,
            })

    ablation = []
    for m in models:
        for a, b in zip(config_order, config_order[1:]):
            ra = {r["id"]: r["correct"] for r in by_key[(m, a)]}
            rb = {r["id"]: r["correct"] for r in by_key[(m, b)]}
            common = sorted(set(ra) & set(rb))
            if not common:
                continue
            gained = sum(rb[i] and not ra[i] for i in common)
            lost = sum(ra[i] and not rb[i] for i in common)
            ablation.append({"model": m, "from": a, "to": b, "n": len(common),
                             "delta": (gained - lost) / len(common), "gained": gained, "lost": lost,
                             "p": mcnemar_exact(lost, gained)})

    best_config = config_order[-1] if config_order else None
    by_difficulty, failures = [], []
    for m in models:
        rows = by_key[(m, best_config)]
        if not rows:
            continue
        entry = {"model": m}
        for d in DIFFICULTY:
            sub = [r for r in rows if r["difficulty"] == d]
            entry[d] = [sum(r["correct"] for r in sub), len(sub)]
        by_difficulty.append(entry)
        for r in sorted(rows, key=lambda r: r["id"]):
            if not r["correct"]:
                reason = "没有执行成功的 SQL" if not r["executed"] else "结果和标准答案不一致"
                failures.append({"model": m, "id": r["id"], "question": r["question"], "reason": reason,
                                 "sql": r["sql"], "error": r["error"]})

    refusal = []
    for m in models:
        for c in config_order:
            rows = [r for r in records if r["refusal_question"] and r["model"] == m and r["config"] == c]
            if rows:
                refusal.append({"model": m, "config": c, "correct": sum(r["correct"] for r in rows), "n": len(rows)})

    api_errors = sum(r["api_error"] for r in records)
    served = sorted({f"{r['model']} → {r['served_model']}" for r in records if r.get("served_model")})
    summary = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "questions": len({r["id"] for r in records}), "models": models, "configs": config_order,
        "config_labels": {c: configs[c]["label"] for c in config_order},
        "overall": overall, "ablation": ablation, "by_difficulty": by_difficulty, "refusal": refusal,
        "api_errors": api_errors, "served_models": served,
        "run_dates": sorted({r["time"][:10] for r in records}),
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# 评测报告", ""]
    lines.append(f"运行日期：{'、'.join(summary['run_dates'])}；题目 {summary['questions']} 道"
                 f"（有标准答案的按结果判分，另有 {len({r['id'] for r in records if r['refusal_question']})} 道考察拒答）。")
    if served:
        lines.append(f"实际调用的模型版本：{'；'.join(served)}。")
    if api_errors:
        lines.append(f"有 {api_errors} 条记录调用 API 出错，已从准确率中排除，重跑同一条命令会补上。")
    lines += ["", "## 总体准确率", "",
              "| 模型 | 配置 | 准确率 | 95% 置信区间 | 自动修正成功 | 平均调用次数 | 平均 tokens | 平均耗时 |",
              "| --- | --- | ---: | --- | ---: | ---: | ---: | ---: |"]
    for o in overall:
        lines.append(f"| {o['model']} | {o['label']} | {_pct(o['accuracy'])}（{o['correct']}/{o['n']}） | "
                     f"{_pct(o['ci'][0])} – {_pct(o['ci'][1])} | {o['self_corrected']} 题 | {o['avg_calls']:.1f} | "
                     f"{o['avg_tokens']:,.0f} | {o['avg_seconds']:.1f} 秒 |")
    if ablation:
        lines += ["", "## 每一步带来多少提升", "",
                  "同一批题配对比较；p 值来自 McNemar 精确检验，小于 0.05 说明提升不太可能是偶然。", "",
                  "| 模型 | 变化 | 提升 | 改对 | 改错 | p 值 |", "| --- | --- | ---: | ---: | ---: | ---: |"]
        for a in ablation:
            lines.append(f"| {a['model']} | {configs[a['from']]['label']} → {configs[a['to']]['label']} | "
                         f"{100 * a['delta']:+.1f} 个百分点 | {a['gained']} | {a['lost']} | {a['p']:.3g} |")
    if by_difficulty:
        lines += ["", f"## 按难度（{configs[best_config]['label']}）", "",
                  "| 模型 | " + " | ".join(DIFFICULTY.values()) + " |", "| --- |" + " ---: |" * len(DIFFICULTY)]
        for e in by_difficulty:
            cells = [f"{_pct(e[d][0] / e[d][1])}（{e[d][0]}/{e[d][1]}）" if e[d][1] else "—" for d in DIFFICULTY]
            lines.append(f"| {e['model']} | " + " | ".join(cells) + " |")
    if refusal:
        lines += ["", "## 数据里没有的问题：能否如实说明", "", "| 模型 | 配置 | 正确拒答 |", "| --- | --- | ---: |"]
        for r in refusal:
            lines.append(f"| {r['model']} | {configs[r['config']]['label']} | {r['correct']}/{r['n']} |")
    if failures:
        lines += ["", f"## 答错的题（{configs[best_config]['label']}）", ""]
        for f in failures:
            lines.append(f"- **{f['model']} · {f['id']}** {f['question']}　{f['reason']}")
            if f["sql"]:
                lines.append(f"  - 模型的 SQL：`{' '.join(f['sql'].split())[:300]}`")
            elif f["error"]:
                lines.append(f"  - 报错：{' '.join(str(f['error']).split())[:300]}")
    path = out_dir / "report.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    from .run import CONFIGS

    print(build_report(Path(sys.argv[1]), CONFIGS))
