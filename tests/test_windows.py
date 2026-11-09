"""中文 Windows 上的编码问题：很多工具默认按 GBK 读文件。"""
import os
from pathlib import Path

import pytest

from askdata.config import load_env

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("name", ["requirements.txt", "requirements-dev.txt"])
def test_requirements_are_ascii(name):
    # pip 在中文 Windows 上按 GBK 读这个文件，里面有中文就会报 UnicodeDecodeError
    (ROOT / name).read_bytes().decode("ascii")


@pytest.mark.parametrize("encoding", ["utf-8", "gbk"])
def test_env_file_saved_in_either_encoding_is_read(tmp_path, monkeypatch, encoding):
    monkeypatch.delenv("ASKDATA_TEST_KEY", raising=False)
    env = tmp_path / ".env"
    env.write_text("# 在等号后面填上自己的 key\nASKDATA_TEST_KEY=sk-test\n", encoding=encoding)
    load_env(env)
    assert os.environ["ASKDATA_TEST_KEY"] == "sk-test"
