"""PayPal sandbox adapter and a clearly labelled, durable demo adapter."""
from decimal import Decimal
import hashlib
import time
import httpx


class ProviderError(Exception):
    def __init__(self, message, *, uncertain=False, code="PROVIDER_ERROR"):
        super().__init__(message)
        self.uncertain=uncertain
        self.code=code


def request_key(commitment_id, operation):
    # Deterministic and inside PayPal's request-ID length limit.
    return hashlib.sha256(f"reclaim:{commitment_id}:{operation}".encode()).hexdigest()[:36]


def money(minor):
    return f"{Decimal(minor)/100:.2f}"


def minor_units(amount):
    value=Decimal(amount["value"])*100
    if value != value.to_integral_value() or amount["currency_code"]!="USD":
        raise ProviderError("Provider amount or currency does not match the purchase.",code="AMOUNT_MISMATCH")
    return int(value)


class PayPalSandbox:
    mode="sandbox"
    base="https://api-m.sandbox.paypal.com"

    def __init__(self,settings):
        self.settings=settings
        self.client=httpx.Client(timeout=httpx.Timeout(20,connect=8))
        self.token=None
        self.token_until=0

    def access_token(self):
        if not self.settings.paypal_ready:
            raise ProviderError("Configure PayPal sandbox client ID and secret before checkout.",code="NOT_CONFIGURED")
        if self.token and self.token_until>time.monotonic():
            return self.token
        try:
            response=self.client.post(self.base+"/v1/oauth2/token",auth=(self.settings.paypal_client_id,self.settings.paypal_client_secret),data={"grant_type":"client_credentials"})
            response.raise_for_status()
            body=response.json()
        except (httpx.HTTPError,ValueError) as error:
            raise ProviderError("Could not authenticate with PayPal sandbox. Check server credentials.",code="AUTHENTICATION_FAILED") from error
        self.token=body["access_token"]
        self.token_until=time.monotonic()+max(0,body["expires_in"]-60)
        return self.token

    def request(self,method,path,body=None,key=None):
        headers={"Authorization":"Bearer "+self.access_token(),"Content-Type":"application/json","Prefer":"return=representation"}
        if key:
            headers["PayPal-Request-Id"]=key
        try:
            response=self.client.request(method,self.base+path,headers=headers,json=body)
        except httpx.HTTPError as error:
            raise ProviderError("PayPal response is uncertain. Reconciliation is required before another payment action.",uncertain=method!="GET",code="TRANSPORT_UNCERTAIN") from error
        if response.status_code>=400:
            try:
                data=response.json()
                code=data.get("details",[{}])[0].get("issue",data.get("name","PROVIDER_ERROR"))
            except (ValueError,IndexError):
                code="PROVIDER_ERROR"
            # A server error may happen after the provider applied the mutation.
            raise ProviderError(f"PayPal sandbox returned {code}. Reconcile or retry this operation.",uncertain=response.status_code>=500 or response.status_code==429 or code=="AUTHORIZATION_ALREADY_CAPTURED",code=code)
        return response.json() if response.content else {}

    def verify_order(self,commitment):
        order=self.request("GET","/v2/checkout/orders/"+commitment["order_id"])
        purchases=order.get("purchase_units",[])
        if order.get("intent")!="AUTHORIZE" or len(purchases)!=1 or purchases[0].get("reference_id")!=commitment["id"] or minor_units(purchases[0]["amount"])!=commitment["price_minor"]:
            raise ProviderError("PayPal order does not match the accepted purchase.",code="ORDER_MISMATCH")
        return order

    def execute(self,kind,commitment,key,state):
        if kind=="create":
            description=", ".join(f'{i["quantity"]} × {i["name"]}' for i in commitment["items"])
            return self.request("POST","/v2/checkout/orders",{"intent":"AUTHORIZE","purchase_units":[{"reference_id":commitment["id"],"custom_id":commitment["id"],"invoice_id":commitment["id"],"description":description[:127],"amount":{"currency_code":"USD","value":money(commitment["price_minor"])}}],"payment_source":{"paypal":{"experience_context":{"brand_name":"Reclaim","shipping_preference":"NO_SHIPPING","user_action":"PAY_NOW","return_url":self.settings.app_url,"cancel_url":self.settings.app_url}}}},key)
        if kind=="authorize":
            order=self.verify_order(commitment)
            existing=order["purchase_units"][0].get("payments",{}).get("authorizations",[])
            if not existing:
                if order.get("status")!="APPROVED":
                    raise ProviderError("Approve this order in PayPal before authorizing it.",code="NOT_APPROVED")
                order=self.request("POST","/v2/checkout/orders/"+commitment["order_id"]+"/authorize",{},key)
                existing=order.get("purchase_units",[{}])[0].get("payments",{}).get("authorizations",[])
            if len(existing)!=1 or minor_units(existing[0]["amount"])!=commitment["price_minor"]:
                raise ProviderError("PayPal authorization does not match the agreed amount.",uncertain=True,code="AUTHORIZATION_MISMATCH")
            return existing[0]
        if kind=="capture":
            if commitment.get("capture_id"):
                return self.request("GET","/v2/payments/captures/"+commitment["capture_id"])
            order=self.verify_order(commitment)
            existing=order["purchase_units"][0].get("payments",{}).get("captures",[])
            if existing:
                if len(existing)!=1 or minor_units(existing[0]["amount"])!=commitment["price_minor"]:
                    raise ProviderError("Existing capture requires operator reconciliation.",uncertain=True,code="CAPTURE_MISMATCH")
                return self.request("GET","/v2/payments/captures/"+existing[0]["id"])
            return self.request("POST","/v2/payments/authorizations/"+commitment["authorization_id"]+"/capture",{"amount":{"currency_code":"USD","value":money(commitment["price_minor"])},"final_capture":True,"invoice_id":commitment["id"]},key)
        if kind=="void":
            authorization=self.request("GET","/v2/payments/authorizations/"+commitment["authorization_id"])
            if authorization.get("status")=="VOIDED":
                return {"id":commitment["authorization_id"],"status":"VOIDED"}
            if authorization.get("status")=="CAPTURED":
                raise ProviderError("Authorization was captured; find its capture before refunding.",uncertain=True,code="ALREADY_CAPTURED")
            self.request("POST","/v2/payments/authorizations/"+commitment["authorization_id"]+"/void",{},key)
            return {"id":commitment["authorization_id"],"status":"VOIDED"}
        if kind=="refund":
            if commitment.get("refund_id"):
                return self.request("GET","/v2/payments/refunds/"+commitment["refund_id"])
            return self.request("POST","/v2/payments/captures/"+commitment["capture_id"]+"/refund",{"amount":{"currency_code":"USD","value":money(commitment["price_minor"])},"note_to_payer":"Reclaim group purchase could not complete. Your allocated purchase is refunded."},key)
        raise ValueError("Unsupported payment operation")

    def verify_webhook(self,headers,event):
        if not self.settings.paypal_webhook_id:
            raise ProviderError("Configure PAYPAL_WEBHOOK_ID to receive verified events.",code="WEBHOOK_NOT_CONFIGURED")
        required=["paypal-auth-algo","paypal-cert-url","paypal-transmission-id","paypal-transmission-sig","paypal-transmission-time"]
        if any(not headers.get(k) for k in required):
            return False
        body={"auth_algo":headers[required[0]],"cert_url":headers[required[1]],"transmission_id":headers[required[2]],"transmission_sig":headers[required[3]],"transmission_time":headers[required[4]],"webhook_id":self.settings.paypal_webhook_id,"webhook_event":event}
        return self.request("POST","/v1/notifications/verify-webhook-signature",body).get("verification_status")=="SUCCESS"

    def read_capture(self,capture_id):
        return self.request("GET","/v2/payments/captures/"+capture_id)

    def reconcile_capture(self,commitment,key,state):
        if commitment.get("capture_id"):
            return self.read_capture(commitment["capture_id"])
        order=self.verify_order(commitment)
        captures=order["purchase_units"][0].get("payments",{}).get("captures",[])
        if captures:
            if len(captures)!=1:
                raise ProviderError("Multiple provider captures require operator reconciliation.",uncertain=True)
            return self.read_capture(captures[0]["id"])
        authorization=self.request("GET","/v2/payments/authorizations/"+commitment["authorization_id"])
        if authorization.get("status") in {"CREATED","PENDING","VOIDED","DENIED","EXPIRED"}:
            # Do not create a new capture while cancelling. A racing capture makes
            # void fail; the next retry reconciles again before releasing anything.
            return None
        if authorization.get("status")=="CAPTURED":
            # Replay only a capture the provider says was already applied.
            return self.execute("capture",commitment,key,state)
        raise ProviderError("Authorization outcome is unresolved; operator reconciliation may be required.",uncertain=True)


class DemoGateway:
    mode="demo"
    def reconcile_capture(self,commitment,key,state):
        return state.get("demo_provider_results",{}).get(key)

    def execute(self,kind,commitment,key,state):
        results=state.setdefault("demo_provider_results",{})
        if key in results:
            return results[key]
        failure=next((f for f in state["failures"] if f["actor_id"]==commitment["buyer_id"] and (f["kind"]==kind or (kind=="capture" and f["kind"]=="capture_timeout")) and f.get("remaining",1)>0),None)
        if failure:
            failure["remaining"]=failure.get("remaining",1)-1
            if failure["kind"]!="capture_timeout":
                raise ProviderError("Simulated "+kind+" failure for recovery demonstration.",code="DEMO_FAILURE")
        status={"create":"CREATED","authorize":"CREATED","capture":"COMPLETED","void":"VOIDED","refund":"COMPLETED"}[kind]
        result={"id":"DEMO-"+kind.upper()+"-"+key[:12],"status":status,"amount":{"currency_code":"USD","value":money(commitment["price_minor"])}}
        results[key]=result
        if failure:
            raise ProviderError("Simulated lost capture response. Provider applied it once; reconcile the same operation.",uncertain=True,code="DEMO_TIMEOUT")
        return result

    def verify_webhook(self,headers,event):
        return False
