"""测试用的假模型：按顺序吐出事先写好的回复，并记下每次收到的消息。"""
from askdata.llm import ChatReply, ToolCall


def sql_call(sql: str, call_id: str = "call_1", chart: str | None = None) -> ChatReply:
    args = {"sql": sql} if chart is None else {"sql": sql, "chart": chart}
    import json

    return ChatReply(content=None, tool_calls=[ToolCall(call_id, "run_sql", json.dumps(args, ensure_ascii=False))],
                     prompt_tokens=100, completion_tokens=20)


def text(content: str) -> ChatReply:
    return ChatReply(content=content, prompt_tokens=100, completion_tokens=30)


class ScriptedModel:
    name = "scripted"

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls: list[list[dict]] = []
        self.tools_seen: list = []

    def chat(self, messages, tools=None):
        self.calls.append([dict(m) for m in messages])
        self.tools_seen.append(tools)
        if not self.replies:
            raise AssertionError("假模型的回复用完了")
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply
