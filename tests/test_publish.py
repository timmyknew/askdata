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


def test_git_output_with_chinese_is_read_on_a_non_utf8_locale(tmp_path):
    # 中文 Windows 默认按 GBK 解码子进程输出，git 输出的却是 UTF-8 的中文提交说明。
    # 这里用 C 语言环境（ASCII）模拟“系统编码不是 UTF-8”，在任何系统上都能复现。
    import os
    import subprocess
    import sys

    repo = tmp_path / "studio"
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.com",
                    "commit", "-q", "--allow-empty", "-m", "同步智能问数助手"], check=True)
    code = (
        "import importlib.util, sys\n"
        "spec = importlib.util.spec_from_file_location('publish', sys.argv[1])\n"
        "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\n"
        "from pathlib import Path\n"
        "print(ascii(m.git(Path(sys.argv[2]), 'log', '-1', '--format=%s').stdout.strip()))\n"
    )
    env = {**os.environ, "PYTHONUTF8": "0", "PYTHONCOERCECLOCALE": "0", "LC_ALL": "C", "LANG": "C"}
    env.pop("PYTHONIOENCODING", None)
    done = subprocess.run([sys.executable, "-c", code, str(ROOT / "scripts" / "publish_modelscope.py"), str(repo)],
                          capture_output=True, env=env)
    assert done.returncode == 0, done.stderr.decode("utf-8", "replace")
    assert done.stdout.decode("ascii").strip() == ascii("同步智能问数助手")


def test_main_commits_and_pushes_with_generic_credentials(tmp_path, monkeypatch):
    # 端到端：同步到一个克隆下来的仓库，提交并推送到本地的“远程”
    import subprocess

    remote = tmp_path / "remote.git"
    studio = tmp_path / "studio"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    subprocess.run(["git", "clone", "-q", str(remote), str(studio)], check=True, capture_output=True)
    for key, value in [("user.name", "t"), ("user.email", "t@example.com")]:
        subprocess.run(["git", "-C", str(studio), "config", key, value], check=True)
    (studio / "README.md").write_text("---\nlicense: Apache License 2.0\n---\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(studio), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(studio), "commit", "-q", "-m", "init"], check=True)
    subprocess.run(["git", "-C", str(studio), "push", "-q", "-u", "origin", "HEAD"], check=True, capture_output=True)

    calls = []
    real_run = subprocess.run

    def recording_run(cmd, *args, **kwargs):
        calls.append(cmd)
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(publish.subprocess, "run", recording_run)
    assert publish.main([str(studio)]) == 0

    pushes = [c for c in calls if "push" in c]
    assert pushes and "credential.provider=generic" in pushes[0]
    log = real_run(["git", "-C", str(remote), "log", "-1", "--format=%s"], capture_output=True,
                   encoding="utf-8").stdout
    assert log.startswith("同步智能问数助手")
    assert publish.main([str(studio)]) == 0  # 再运行一次：没有改动，不会重复提交
    assert real_run(["git", "-C", str(remote), "rev-list", "--count", "HEAD"], capture_output=True,
                    encoding="utf-8").stdout.strip() == "2"
