import json

from evaluation.report import mcnemar_exact, wilson
from evaluation.run import main


def test_oracle_run_resume_and_report(tmp_path, capsys):
    out = tmp_path / "run"
    main(["--models", "oracle", "--ids", "e01", "t01", "n01", "--out", str(out), "--quiet"])
    lines = (out / "records.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 9  # 3 道题 × 3 种配置
    assert all(json.loads(l)["correct"] for l in lines)

    main(["--models", "oracle", "--ids", "e01", "t01", "n01", "--out", str(out), "--quiet"])
    assert "共 0 个任务" in capsys.readouterr().out  # 跑过的不再重跑
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["overall"][0]["accuracy"] == 1.0
    assert "## 总体准确率" in (out / "report.md").read_text(encoding="utf-8")


def test_stats():
    lo, hi = wilson(90, 100)
    assert 0.82 < lo < 0.83 and 0.94 < hi < 0.95
    assert mcnemar_exact(0, 0) == 1.0
    assert abs(mcnemar_exact(2, 12) - 0.01294) < 1e-4
