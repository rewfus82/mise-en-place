"""Smoke test for the coach router: the endpoint wires the service to SSE.

The service is patched to yield canned SSE so the test exercises routing,
headers, and streaming without an LLM or the knowledge base.
"""
from backend.services import coach_service


def test_ask_streams_event_stream(client, monkeypatch):
    async def fake_stream(question, provider, api_key):
        assert question == "how much protein?"
        assert provider == "anthropic"
        assert api_key == "sk-ant-test"
        yield 'data: {"type": "sources", "sources": []}\n\n'
        yield 'data: {"type": "token", "text": "Eat protein."}\n\n'
        yield 'data: {"type": "done"}\n\n'

    monkeypatch.setattr(coach_service, "ask_stream", fake_stream)

    res = client.post(
        "/api/coach/ask",
        json={"question": "how much protein?"},
        headers={"X-LLM-Provider": "anthropic", "X-LLM-Key": "sk-ant-test"},
    )
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/event-stream")
    body = res.text
    assert '"type": "sources"' in body
    assert "Eat protein." in body
    assert '"type": "done"' in body
