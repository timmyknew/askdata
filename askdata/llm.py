"""调用大模型。Agent 只依赖 ChatModel 这个接口，测试时可以换成脚本化的假模型。"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Protocol

from .config import MODELS, ModelSpec


class MissingAPIKey(RuntimeError):
    def __init__(self, env_var: str):
        super().__init__(f"没有找到 {env_var}，请在 .env 文件或部署平台的环境变量里填写。")
        self.env_var = env_var


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str  # 模型给的原始 JSON 字符串

    def args(self) -> dict:
        try:
            value = json.loads(self.arguments or "{}")
        except json.JSONDecodeError:
            return {}
        return value if isinstance(value, dict) else {}


@dataclass
class ChatReply:
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str | None = None

    def assistant_message(self) -> dict:
        """把这次回复还原成 OpenAI 格式的 assistant 消息，放回对话历史。"""
        # 有工具调用时 content 可以是 null（OpenAI 规范），没有时用空字符串
        message: dict = {"role": "assistant", "content": self.content or (None if self.tool_calls else "")}
        if self.tool_calls:
            message["tool_calls"] = [
                {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": c.arguments}}
                for c in self.tool_calls
            ]
        return message


class ChatModel(Protocol):
    name: str

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> ChatReply: ...


class OpenAICompatModel:
    """DeepSeek、智谱都兼容 OpenAI 的 chat.completions 接口。"""

    def __init__(self, spec: ModelSpec, api_key: str | None = None, timeout: float = 60):
        from openai import OpenAI

        key = api_key or os.getenv(spec.api_key_env)
        if not key:
            raise MissingAPIKey(spec.api_key_env)
        self.spec = spec
        self.name = spec.key
        self.client = OpenAI(api_key=key, base_url=spec.base_url, timeout=timeout, max_retries=2)

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> ChatReply:
        kwargs = {"model": self.spec.model, "messages": messages, "max_tokens": 1500, **self.spec.extra}
        if tools:
            kwargs["tools"] = tools
        resp = self.client.chat.completions.create(**kwargs)
        msg = resp.choices[0].message
        calls = [
            ToolCall(id=c.id, name=c.function.name, arguments=c.function.arguments or "")
            for c in (msg.tool_calls or [])
        ]
        usage = resp.usage
        return ChatReply(
            content=msg.content,
            tool_calls=calls,
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
            model=resp.model,
        )


def make_model(key: str, api_key: str | None = None) -> ChatModel:
    return OpenAICompatModel(MODELS[key], api_key=api_key)
