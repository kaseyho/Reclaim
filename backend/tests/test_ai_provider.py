import base64
import json

import httpx
from openai import OpenAI
import pytest
from fastapi.testclient import TestClient

from reclaim.ai import AI, AIUnavailable
from reclaim.config import Settings
from reclaim.main import create_app
from reclaim.repository import Store


INVENTORY = {"units": [{"name": "Desk", "item_type": "desk", "quantity": 1, "condition": "good", "width_cm": 92, "brand": None, "sealed": None, "evidence": "Explicit seller text", "attributes": []}], "unresolved": []}


def soclaas_settings(**overrides):
    return Settings(openai_api_key="other-provider-key", soclaas_api_key="test-soclaas-key", soclaas_base_url="https://soclaas.test/v1", soclaas_model="default", **overrides)


def chat_response(**choice_overrides):
    choice = {"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": json.dumps(INVENTORY), "refusal": None}, **choice_overrides}
    return {"id": "chatcmpl-test", "object": "chat.completion", "created": 1, "model": "resolved-test-model", "choices": [choice], "usage": {"prompt_tokens": 125, "completion_tokens": 75, "total_tokens": 200}}


def with_transport(settings, handler):
    pipeline = AI(settings)
    pipeline.client.close()
    pipeline.client = OpenAI(api_key=settings.ai_api_key, base_url=settings.ai_base_url, http_client=httpx.Client(transport=httpx.MockTransport(handler)), max_retries=0)
    return pipeline


def test_soclaas_uses_its_own_host_key_schema_and_image_protocol():
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=chat_response())
    pipeline = with_transport(soclaas_settings(), handler)
    # A tiny valid PNG avoids sending a real image in a unit test.
    png = "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\nfixture").decode()
    result, trace = pipeline.run("extract", "One desk, 92 cm wide.", "furniture", png)
    request = requests[0]
    body = json.loads(request.content)
    assert str(request.url) == "https://soclaas.test/v1/chat/completions"
    assert request.headers["Authorization"] == "Bearer test-soclaas-key"
    assert body["model"] == "default"
    assert body["store"] is False
    assert body["response_format"] == {"type": "json_object"}
    assert '"units"' in body["messages"][0]["content"]
    assert body["temperature"] == 0
    assert body["messages"][1]["content"][1] == {"type": "image_url", "image_url": {"url": png, "detail": "auto"}}
    assert result.units[0].width_cm == 92
    assert trace["provider"] == "soclaas"
    assert (trace["model_requested"], trace["model"]) == ("default", "resolved-test-model")
    assert (trace["input_tokens"], trace["output_tokens"]) == (125, 75)
    assert trace["cost_usd"] is None


@pytest.mark.parametrize("failure", ["length", "refusal", "invalid_schema", "no_choices", "content_filter", "timeout"])
def test_soclaas_failures_never_become_demo_or_successful_inventory(failure):
    def handler(request):
        if failure == "timeout":
            raise httpx.ReadTimeout("test timeout", request=request)
        data = chat_response()
        if failure in {"length", "content_filter"}:
            data["choices"][0]["finish_reason"] = failure
        elif failure == "refusal":
            data["choices"][0]["message"] = {"role": "assistant", "content": None, "refusal": "Declined"}
        elif failure == "invalid_schema":
            data["choices"][0]["message"]["content"] = '{"units": "not an array"}'
        else:
            data["choices"] = []
        return httpx.Response(200, json=data)
    pipeline = with_transport(soclaas_settings(), handler)
    with pytest.raises(AIUnavailable):
        pipeline.run("extract", "One desk", "furniture")


def test_openai_keeps_responses_protocol_and_does_not_use_soclaas_settings():
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"id": "resp-test", "object": "response", "created_at": 1, "status": "completed", "model": "gpt-4.1-mini-2025-04-14", "output": [{"type": "message", "id": "msg-test", "role": "assistant", "status": "completed", "content": [{"type": "output_text", "text": json.dumps(INVENTORY), "annotations": []}]}], "usage": {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30}})
    settings = Settings(openai_api_key="test-openai-key", soclaas_api_key="")
    pipeline = with_transport(settings, handler)
    result, trace = pipeline.run("extract", "One desk", "furniture")
    assert str(requests[0].url) == "https://api.openai.com/v1/responses"
    assert requests[0].headers["Authorization"] == "Bearer test-openai-key"
    assert "messages" not in json.loads(requests[0].content)
    assert result.units[0].quantity == 1
    assert trace["provider"] == "openai" and trace["api"] == "responses"


def test_public_config_identifies_soclaas_without_exposing_credentials(tmp_path):
    settings = soclaas_settings(database_url="sqlite:///" + str(tmp_path / "config.db"), auto_worker=False)
    store = Store(settings.database_url)
    with TestClient(create_app(settings, store)) as client:
        response = client.get("/api/config")
        assert response.json()["ai_provider"] == "soclaas"
        assert response.json()["ai_model"] == "default"
        assert "test-soclaas-key" not in response.text
        assert "other-provider-key" not in response.text


@pytest.mark.parametrize("root", ["http://soclaas.test/v1", "[https://soclaas.test/v1](https://soclaas.test/v1)", "https://user:pass@soclaas.test/v1", "https://soclaas.test/v1?key=secret"])
def test_soclaas_rejects_unsafe_or_markdown_api_roots(root):
    with pytest.raises(ValueError, match="plain HTTPS"):
        Settings(soclaas_api_key="test-key", soclaas_base_url=root)
