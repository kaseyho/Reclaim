from dataclasses import replace
import json
import httpx
import jwt
import pytest
from fastapi.testclient import TestClient
from cryptography.hazmat.primitives.asymmetric import ec
from reclaim.config import Settings
from reclaim.main import create_app
from reclaim.paypal import PayPalSandbox, ProviderError, request_key
from reclaim.repository import Store
from reclaim.schemas import now
from reclaim.seeds import seed


def test_paypal_order_uses_server_amount_and_stable_request_id():
    gateway=PayPalSandbox(Settings(payment_mode="sandbox",paypal_client_id="test-client",paypal_client_secret="test-secret"))
    captured=[]
    def handler(request):
        if request.url.path=="/v1/oauth2/token": return httpx.Response(200,json={"access_token":"test-access","expires_in":300})
        captured.append(request)
        return httpx.Response(201,json={"id":"ORDER-TEST","status":"CREATED"})
    gateway.client=httpx.Client(transport=httpx.MockTransport(handler))
    c={"id":"commitment-test","price_minor":7200,"items":[{"name":"Desk","quantity":1},{"name":"Lamp","quantity":1}]}
    key=request_key(c["id"],"create")
    gateway.execute("create",c,key,{})
    gateway.execute("create",c,key,{})
    body=json.loads(captured[0].content)
    assert body["intent"]=="AUTHORIZE"
    assert body["purchase_units"][0]["amount"]=={"currency_code":"USD","value":"72.00"}
    assert body["purchase_units"][0]["description"]=="1 × Desk, 1 × Lamp"
    assert captured[0].headers["PayPal-Request-Id"]==captured[1].headers["PayPal-Request-Id"]==key


def test_mismatched_order_never_reaches_authorize():
    gateway=PayPalSandbox(Settings(payment_mode="sandbox",paypal_client_id="test-client",paypal_client_secret="test-secret"))
    paths=[]
    def handler(request):
        paths.append(request.url.path)
        if request.url.path=="/v1/oauth2/token": return httpx.Response(200,json={"access_token":"test-access","expires_in":300})
        return httpx.Response(200,json={"intent":"AUTHORIZE","status":"APPROVED","purchase_units":[{"reference_id":"c","amount":{"currency_code":"USD","value":"73.00"}}]})
    gateway.client=httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(ProviderError,match="does not match"):
        gateway.execute("authorize",{"id":"c","order_id":"o","price_minor":7200},request_key("c","authorize"),{})
    assert not any(path.endswith("/authorize") for path in paths)


def test_capture_reconciliation_finds_existing_provider_capture():
    gateway=PayPalSandbox(Settings(payment_mode="sandbox",paypal_client_id="test-client",paypal_client_secret="test-secret"))
    methods=[]
    def handler(request):
        methods.append((request.method,request.url.path))
        if request.url.path=="/v1/oauth2/token": return httpx.Response(200,json={"access_token":"test-access","expires_in":300})
        if request.url.path=="/v2/checkout/orders/o": return httpx.Response(200,json={"intent":"AUTHORIZE","status":"COMPLETED","purchase_units":[{"reference_id":"c","amount":{"currency_code":"USD","value":"72.00"},"payments":{"captures":[{"id":"capture-existing","amount":{"currency_code":"USD","value":"72.00"}}]}}]})
        return httpx.Response(200,json={"id":"capture-existing","status":"COMPLETED","amount":{"currency_code":"USD","value":"72.00"}})
    gateway.client=httpx.Client(transport=httpx.MockTransport(handler))
    result=gateway.execute("capture",{"id":"c","order_id":"o","authorization_id":"a","price_minor":7200},request_key("c","capture"),{})
    assert result["id"]=="capture-existing"
    assert not any(method=="POST" and path.endswith("/capture") for method,path in methods)


def test_timeout_on_mutation_remains_uncertain():
    gateway=PayPalSandbox(Settings(payment_mode="sandbox",paypal_client_id="test-client",paypal_client_secret="test-secret"))
    gateway.token="test-access"; gateway.token_until=float("inf")
    def handler(request): raise httpx.ReadTimeout("test timeout",request=request)
    gateway.client=httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(ProviderError) as error: gateway.request("POST","/v2/payments/authorizations/a/capture",{},"stable-key")
    assert error.value.uncertain


def test_supabase_signature_expiry_and_workspace_subject(tmp_path,monkeypatch):
    from datetime import timedelta
    from types import SimpleNamespace
    key=ec.generate_private_key(ec.SECP256R1())
    monkeypatch.setattr(jwt.PyJWKClient,"get_signing_key_from_jwt",lambda self,token:SimpleNamespace(key=key.public_key()))
    config=Settings(database_url="sqlite:///"+str(tmp_path/"auth.db"),auto_worker=False,auth_mode="supabase",supabase_url="https://test.supabase.co",supabase_publishable_key="sb_publishable_test")
    store=Store(config.database_url); workspace,tokens=store.create(seed(),owner="judge-a")
    client=TestClient(create_app(config,store))
    def token(subject,expiry): return jwt.encode({"sub":subject,"aud":"authenticated","iss":config.supabase_url+"/auth/v1","exp":expiry},key,algorithm="ES256")
    valid=token("judge-a",now()+timedelta(hours=1))
    headers={"Authorization":"Bearer "+valid,"X-Workspace-Token":tokens["alice"]}
    assert client.get("/api/state",headers=headers).status_code==200
    headers["Authorization"]="Bearer "+token("judge-b",now()+timedelta(hours=1))
    assert client.get("/api/state",headers=headers).status_code==403
    headers["Authorization"]="Bearer "+token("judge-a",now()-timedelta(seconds=1))
    assert client.get("/api/state",headers=headers).status_code==401


def test_service_role_key_cannot_be_exposed_as_client_configuration():
    secret=jwt.encode({"role":"service_role"},"test-only-secret-long-enough-to-sign",algorithm="HS256")
    with pytest.raises(ValueError,match="service-role"):
        Settings(supabase_publishable_key=secret)
    with pytest.raises(ValueError,match="secret key"):
        Settings(supabase_publishable_key="sb_secret_test")
