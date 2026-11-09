import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("publish", ROOT / "scripts" / "publish_modelscope.py")
publish = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publish)


def test_sync_copies_app_files_and_keeps_studio_config(tmp_path):
    (tmp_path / "README.md").write_text("---\nlicense: Apache License 2.0\n---\n#### Clone with HTTP\n", encoding="utf-8")
    (tmp_path / "askdata").mkdir()
    (tmp_path / "askdata" / "old_module.py").write_text("# 项目里已经删掉的文件\n", encoding="utf-8")
    publish.sync(tmp_path)

    readme = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert readme.startswith("---\nlicense: Apache License 2.0\n---\n")
    assert "# 智能问数助手" in readme and "Clone with HTTP" not in readme
    assert (tmp_path / "app.py").exists() and (tmp_path / "data" / "olist" / "orders.parquet").exists()
    assert not (tmp_path / "askdata" / "old_module.py").exists()
    assert not list(tmp_path.rglob("__pycache__"))
    assert not (tmp_path / "tests").exists()  # 测试和评测代码不上传


def test_front_matter_needs_closing_line():
    assert publish.front_matter("# 标题\n") == ""
    assert publish.front_matter("---\na: 1\n") == ""
    assert publish.front_matter("---\na: 1\n---\n正文") == "---\na: 1\n---\n"
