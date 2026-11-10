"""把网页需要的文件同步到魔搭创空间的仓库，并提交、推送。步骤见 docs/deploy.md。

用法（在本项目根目录运行）：
    python scripts/publish_modelscope.py ../askdata-studio            # 复制 + 提交 + 推送
    python scripts/publish_modelscope.py ../askdata-studio --no-push  # 只复制和提交，自己检查后再推送

../askdata-studio 是用 git clone 下来的创空间仓库。以后代码有更新，再运行一次即可。
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = ["app.py", "requirements.txt", ".streamlit/config.toml"]  # 网页运行只需要这些
DIRS = ["askdata", "data/olist"]
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc")


def front_matter(text: str) -> str:
    """创空间的 README 开头有一段 --- 包起来的配置（许可证、入口文件等），要原样保留。"""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return ""
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            return "".join(lines[: i + 1])
    return ""


def sync(target: Path) -> list[str]:
    """复制文件，返回复制了哪些路径。"""
    copied = []
    for name in DIRS:
        dest = target / name
        if dest.exists():
            shutil.rmtree(dest)  # 先删再拷，项目里删掉的文件在创空间里也会删掉
        shutil.copytree(ROOT / name, dest, ignore=IGNORE)
        copied.append(name + "/")
    for name in FILES:
        dest = target / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, dest)
        copied.append(name)

    readme = target / "README.md"
    header = front_matter(readme.read_text(encoding="utf-8")) if readme.exists() else ""
    body = (ROOT / "README.md").read_text(encoding="utf-8")
    note = "\n> 源代码和完整说明见 GitHub：https://github.com/timmyknew/timmyknewhere\n"
    readme.write_text((header + "\n" if header else "") + body.rstrip() + "\n" + note, encoding="utf-8")
    copied.append("README.md")
    return copied


def git(target: Path, *args: str) -> subprocess.CompletedProcess:
    # git 输出的提交说明是 UTF-8；不指定编码时，中文 Windows 会按 GBK 解码，遇到中文就报错
    return subprocess.run(["git", "-C", str(target), *args], capture_output=True,
                          encoding="utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="同步到魔搭创空间")
    parser.add_argument("target", type=Path, help="git clone 下来的创空间仓库目录")
    parser.add_argument("--no-push", action="store_true", help="只提交，不推送")
    args = parser.parse_args(argv)

    target = args.target.resolve()
    if not (target / ".git").exists():
        print(f"{target} 不是 git 仓库。请先 git clone 创空间仓库，见 docs/deploy.md。")
        return 1
    if target == ROOT:
        print("目标目录不能是本项目自己。")
        return 1

    for path in sync(target):
        print(f"已复制 {path}")
    git(target, "add", "-A")
    if not git(target, "status", "--porcelain").stdout.strip():
        print("创空间里已经是最新的，不需要提交。")
        return 0
    version = git(ROOT, "rev-parse", "--short", "HEAD").stdout.strip() or "本地版本"
    done = git(target, "commit", "-m", f"同步智能问数助手 {version}")
    if done.returncode != 0:
        print(done.stdout + done.stderr)
        print("提交失败。如果提示 Please tell me who you are，先按提示设置 git 的 user.name 和 user.email。")
        return 1
    print(f"已提交：同步智能问数助手 {version}")

    if args.no_push:
        print(f"检查无误后运行：git -C {target} push")
        return 0
    # 不截获输出：要输入账号密码时能看到提示。
    # Windows 的 Git 凭据管理器会把魔搭误认成 GitLab，登录框打不开；generic 让它直接问用户名和密码
    pushed = subprocess.run(["git", "-c", "credential.provider=generic", "-C", str(target), "push"])
    if pushed.returncode != 0:
        print("推送失败。用户名填 oauth2，密码填魔搭的访问令牌；其他问题见 docs/deploy.md 的“常见问题”。")
        return 1
    print("推送成功。去创空间页面看构建日志，几分钟后就能打开。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
