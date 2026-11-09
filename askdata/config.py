"""可选的大模型。三家都走 OpenAI 兼容接口，只是地址、模型名和额外参数不同。"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class ModelSpec:
    key: str  # 程序内部用的名字
    label: str  # 界面上显示的名字
    model: str  # 调 API 时传的模型名
    base_url: str
    api_key_env: str  # .env 里放 key 的变量名
    extra: dict = field(default_factory=dict)  # 每次请求额外带的参数


DEEPSEEK_URL = "https://api.deepseek.com"
ZHIPU_URL = "https://open.bigmodel.cn/api/paas/v4/"
# DeepSeek 默认开思考模式，思考模式下 temperature 不生效，所以显式关掉。
NO_THINKING = {"extra_body": {"thinking": {"type": "disabled"}}}

MODELS: dict[str, ModelSpec] = {
    spec.key: spec
    for spec in [
        ModelSpec("deepseek-flash", "DeepSeek Flash（默认）", "deepseek-flash", DEEPSEEK_URL,
                  "DEEPSEEK_API_KEY", {"temperature": 0, **NO_THINKING}),
        ModelSpec("glm-4-flash", "智谱 GLM-4-Flash（免费）", "glm-4-flash-250414", ZHIPU_URL,
                  "ZHIPUAI_API_KEY", {"extra_body": {"do_sample": False}}),  # 智谱用贪心解码，不传 temperature=0
        ModelSpec("deepseek-v4-pro", "DeepSeek V4 Pro", "deepseek-v4-pro", DEEPSEEK_URL,
                  "DEEPSEEK_API_KEY", {"temperature": 0, **NO_THINKING}),
    ]
}
DEFAULT_MODEL = "deepseek-flash"


def load_env(path: Path) -> None:
    """读取 .env 里的 key。旧版记事本可能把它存成 GBK 编码，按 UTF-8 读失败时再按 GBK 读一次。"""
    try:
        load_dotenv(path)
    except UnicodeDecodeError:
        load_dotenv(path, encoding="gbk")
