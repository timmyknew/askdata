"""用本地假服务器检查：请求里带上了工具和额外参数，回复里的工具调用解析正确。"""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from askdata.agent import RUN_SQL_TOOL
from askdata.config import MODELS
from askdata.llm import MissingAPIKey, OpenAICompatModel

RESPONSE = {
    "id": "x", "object": "chat.completion", "created": 0, "model": "deepseek-flash",
    "choices": [{"index": 0, "finish_reason": "tool_calls", "message": {
        "role": "assistant", "content": None,
        "tool_calls": [{"id": "call_9", "type": "function",
                        "function": {"name": "run_sql", "arguments": "{\"sql\": \"select 1\"}"}}]}}],
    "usage": {"prompt_tokens": 12, "completion_tokens": 3, "total_tokens": 15},
}


@pytest.fixture()
def server():
    received = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            received.append((self.path, self.headers.get("Authorization"), json.loads(body)))
            payload = json.dumps(RESPONSE).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            pass

    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}", received
    httpd.shutdown()


def test_request_and_tool_call_parsing(server):
    url, received = server
    spec = MODELS["deepseek-flash"]
    model = OpenAICompatModel(spec.__class__(**{**spec.__dict__, "base_url": url}), api_key="sk-test")
    reply = model.chat([{"role": "user", "content": "hi"}], tools=[RUN_SQL_TOOL])

    path, auth, body = received[0]
    assert path.endswith("/chat/completions") and auth == "Bearer sk-test"
    assert body["model"] == "deepseek-flash" and body["temperature"] == 0
    assert body["thinking"] == {"type": "disabled"}  # extra_body 合并进请求体
    assert body["tools"][0]["function"]["name"] == "run_sql"

    assert reply.tool_calls[0].args() == {"sql": "select 1"}
    assert (reply.prompt_tokens, reply.completion_tokens) == (12, 3)
    assert reply.assistant_message()["tool_calls"][0]["id"] == "call_9"


def test_missing_key(monkeypatch):
    monkeypatch.delenv("ZHIPUAI_API_KEY", raising=False)
    with pytest.raises(MissingAPIKey, match="ZHIPUAI_API_KEY"):
        OpenAICompatModel(MODELS["glm-4-flash"])
