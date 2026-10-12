from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
from itertools import combinations
import os
import pytest
from hypothesis import given, settings as property_settings, strategies as st
from fastapi.testclient import TestClient
from reclaim.config import Settings
from reclaim.main import create_app
from reclaim.repository import Store, Job
from reclaim.schemas import DemandInput, LotInput, VersionInput, now
from reclaim.seeds import seed
from reclaim.service import DomainError, Service
from reclaim.solver import match_lot, split_price, validate_allocation
from reclaim.worker import tick


@pytest.fixture
def system(tmp_path):
    config=Settings(database_url=os.getenv("TEST_DATABASE_URL") or "sqlite:///"+str(tmp_path/"test.db"),auto_worker=False,openai_api_key="",payment_mode="demo")
    store=Store(config.database_url)
    service=Service(store,config)
    workspace,tokens=store.create(seed())
    return service,workspace,tokens


def add_chen(service,workspace):
    lot=service.store.read(workspace)["lots"][0]
    return service.save_demand(workspace,"chen",DemandInput(text="A monitor under $110.",needs=[{"item_type":"monitor","quantity":1}],budget_minor=11000,location=lot["location"],pickup_start=lot["pickup_start"],pickup_end=lot["pickup_end"],deadline=lot["pickup_end"],confirmed=True))


def ready(service,workspace):
    add_chen(service,workspace)
    deal=service.propose(workspace,"alice","lot_moving")
    terms=VersionInput(version=deal["version"],terms_hash=deal["terms_hash"])
    for actor in ["alice","ben","chen","seller"]:
        service.accept(workspace,actor,deal["id"],terms)
    return deal


def authorize_all(service,workspace,deal):
    for c in deal["commitments"]:
        order=service.create_order(workspace,c["buyer_id"],c["id"])
        service.authorize(workspace,c["buyer_id"],c["id"],order["id"])


def current(service,workspace):
    return service.store.read(workspace)["deals"][0]


def test_missing_buyer_becomes_budget_safe_group(system):
    service,workspace,_=system
    initial=service.snapshot(workspace,"alice")["diagnostics"][0]
    assert not initial["complete"]
    assert [(m["item_type"],m["price_minor"]) for m in initial["missing"]]==[("monitor",8000)]
    add_chen(service,workspace)
    result=service.snapshot(workspace,"alice")["diagnostics"][0]
    assert result["complete"]
    assert [a["price_minor"] for a in result["allocations"]]==[7200,4800,8000]
    assert result["status"]=="OPTIMAL"


def test_complete_purchase_prepare_and_pickup(system):
    service,workspace,_=system
    deal=ready(service,workspace)
    authorize_all(service,workspace,deal)
    assert current(service,workspace)["status"]=="READY"
    assert service.process(workspace,deal["id"]) is None
    paid=current(service,workspace)
    assert paid["status"]=="PAID"
    assert all(c["payment_status"]=="CAPTURED" for c in paid["commitments"])
    service.prepare(workspace,"seller",deal["id"])
    for c in current(service,workspace)["commitments"]:
        service.pickup(workspace,c["buyer_id"],c["id"],c["pickup_code"])
    assert current(service,workspace)["status"]=="COMPLETED"


def test_cannot_authorize_before_everyone_accepts(system):
    service,workspace,_=system
    add_chen(service,workspace)
    deal=service.propose(workspace,"alice","lot_moving")
    service.accept(workspace,"alice",deal["id"],VersionInput(version=1,terms_hash=deal["terms_hash"]))
    with pytest.raises(DomainError,match="Every buyer"):
        service.create_order(workspace,"alice",deal["commitments"][0]["id"])


def test_partial_capture_refunds_then_voids(system):
    service,workspace,_=system
    deal=ready(service,workspace)
    with service.store.transaction(workspace) as (state,db):
        state["failures"].append({"kind":"capture","actor_id":"ben"})
    authorize_all(service,workspace,deal)
    service.process(workspace,deal["id"])
    result=current(service,workspace)
    assert result["status"]=="CANCELLED"
    assert [c["payment_status"] for c in result["commitments"]]==["REFUNDED","VOIDED","VOIDED"]
    assert all(c["pickup_code"] is None for c in result["commitments"])
    assert service.store.read(workspace)["lots"][0]["status"]=="AVAILABLE"


def test_refund_failure_keeps_inventory_reserved(system):
    service,workspace,_=system
    deal=ready(service,workspace)
    with service.store.transaction(workspace) as (state,db):
        state["failures"]=[{"kind":"capture","actor_id":"ben"},{"kind":"refund","actor_id":"alice","remaining":99}]
    authorize_all(service,workspace,deal)
    assert service.process(workspace,deal["id"])
    result=current(service,workspace)
    assert result["status"]=="REFUNDING"
    assert result["commitments"][0]["payment_status"]=="CAPTURED"
    assert service.store.read(workspace)["lots"][0]["status"]=="RESERVED"
    with pytest.raises(DomainError):
        service.prepare(workspace,"seller",deal["id"])
    with service.store.transaction(workspace) as (state,db):
        state["failures"]=[]
    assert service.process(workspace,deal["id"]) is None
    assert current(service,workspace)["commitments"][0]["payment_status"]=="REFUNDED"


def test_lost_capture_response_retries_same_operation_once(system):
    service,workspace,_=system
    deal=ready(service,workspace)
    with service.store.transaction(workspace) as (state,db):
        state["failures"].append({"kind":"capture_timeout","actor_id":"alice"})
    authorize_all(service,workspace,deal)
    assert service.process(workspace,deal["id"])
    assert current(service,workspace)["status"]=="RECONCILING"
    # Restart the service; uncertainty and the provider's completed outcome persist.
    restarted=Service(Store(service.settings.database_url),service.settings)
    assert restarted.process(workspace,deal["id"]) is None
    result=restarted.store.read(workspace)
    assert result["deals"][0]["status"]=="PAID"
    captures=[op for op in result["operations"].values() if op["kind"]=="capture"]
    assert len(captures)==3
    assert len([k for k in result["demo_provider_results"] if k in [op["request_id"] for op in captures]])==3


def test_worker_wakes_again_when_later_buyer_authorizes(system):
    service,workspace,_=system
    deal=ready(service,workspace)
    for index,c in enumerate(deal["commitments"]):
        order=service.create_order(workspace,c["buyer_id"],c["id"])
        service.authorize(workspace,c["buyer_id"],c["id"],order["id"])
        assert tick(service)
        if index<2:
            assert current(service,workspace)["status"]!="PAID"
    assert current(service,workspace)["status"]=="PAID"


def test_outbox_does_not_lose_wakeup_during_running_job(system):
    service,workspace,_=system
    deal=ready(service,workspace)
    with service.store.transaction(workspace) as (_,db):
        job_id=service.store.enqueue(db,workspace,"process",deal["id"])
    claimed=service.store.claim_job()
    with service.store.transaction(workspace) as (_,db):
        service.store.enqueue(db,workspace,"process",deal["id"])
    service.store.finish_job(job_id,generation=claimed["generation"])
    assert service.store.claim_job() is not None


def test_checkout_expiry_voids_authorization(system):
    service,workspace,_=system
    deal=ready(service,workspace)
    c=deal["commitments"][0]
    order=service.create_order(workspace,"alice",c["id"])
    service.authorize(workspace,"alice",c["id"],order["id"])
    with service.store.transaction(workspace) as (state,db):
        state["deals"][0]["expires_at"]=(now()-timedelta(seconds=1)).isoformat()
    service.process(workspace,deal["id"])
    result=current(service,workspace)
    assert result["status"]=="EXPIRED"
    assert result["commitments"][0]["payment_status"]=="VOIDED"


def test_stale_terms_and_foreign_actor_rejected(system):
    service,workspace,_=system
    deal=ready(service,workspace)
    with pytest.raises(DomainError,match="Terms changed"):
        service.accept(workspace,"alice",deal["id"],VersionInput(version=2,terms_hash=deal["terms_hash"]))
    with pytest.raises(DomainError,match="Only this buyer"):
        service.create_order(workspace,"ben",deal["commitments"][0]["id"])


def test_inventory_change_cancels_accepted_terms(system):
    service,workspace,_=system
    deal=ready(service,workspace)
    lot=service.store.read(workspace)["lots"][0]
    value={k:v for k,v in lot.items() if k in LotInput.model_fields}
    value["goods_price_minor"]+=100
    service.save_lot(workspace,"seller",LotInput(**value),lot_id=lot["id"])
    assert current(service,workspace)["cancel_requested"]
    with pytest.raises(DomainError):
        service.create_order(workspace,"alice",deal["commitments"][0]["id"])
    service.process(workspace,deal["id"])
    assert service.store.read(workspace)["lots"][0]["version"]==2


def test_concurrent_proposals_reserve_only_once(system):
    service,workspace,_=system
    add_chen(service,workspace)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(lambda _:service.propose(workspace,"alice","lot_moving"),range(4)))
    assert len({d["id"] for d in results})==1
    assert len(service.store.read(workspace)["deals"])==1


def test_unverified_width_is_not_a_fact():
    state=seed()
    state["lots"][0]["units"][0]["confirmed_fields"].remove("width_cm")
    result=match_lot(state["lots"][0],state["demands"])
    assert not any(a["buyer_id"]=="alice" for a in result["allocations"])
    assert any("width needs seller confirmation" in b for b in result["blockers"])


def test_api_identity_scope_and_no_client_prices(system):
    service,workspace,tokens=system
    app=create_app(service.settings,service.store)
    client=TestClient(app)
    assert client.get("/api/state").status_code==401
    alice={"Authorization":"Bearer "+tokens["alice"]}
    assert client.get("/api/state",headers=alice).status_code==200
    assert client.post("/api/lots/extract",headers=alice,json={"text":"desk, chair"}).status_code==403
    # Schema rejects authoritative amounts supplied to acceptance.
    assert client.post("/api/deals/nope/accept",headers=alice,json={"version":1,"terms_hash":"a"*64,"price_minor":1}).status_code==422


def test_webhook_rejects_unsigned_then_deduplicates_verified_event(system):
    from dataclasses import replace
    from reclaim.paypal import DemoGateway
    service,workspace,tokens=system
    deal=ready(service,workspace); authorize_all(service,workspace,deal); service.process(workspace,deal["id"])
    config=replace(service.settings,payment_mode="sandbox")
    app=create_app(config,service.store)
    class Gateway(DemoGateway):
        verified=False
        def verify_webhook(self,headers,event): return self.verified
        def read_capture(self,capture_id):
            c=next(c for c in current(service,workspace)["commitments"] if c["capture_id"]==capture_id)
            return {"status":"COMPLETED","amount":{"currency_code":"USD","value":str(c["price_minor"]/100)}}
    gateway=Gateway(); app.state.service.gateway=gateway
    client=TestClient(app)
    payload={"id":"WH-test","event_type":"PAYMENT.CAPTURE.COMPLETED","resource":{"id":current(service,workspace)["commitments"][0]["capture_id"]}}
    assert client.post("/api/webhooks/paypal",json=payload).status_code==401
    gateway.verified=True
    assert client.post("/api/webhooks/paypal",json=payload).json()["duplicate"] is False
    assert client.post("/api/webhooks/paypal",json=payload).json()["duplicate"] is True
    assert sum(e["action"]=="Verified webhook received" for e in service.store.read(workspace)["events"])==1


def test_external_full_refund_is_reconciled_before_remaining_recovery(system):
    from dataclasses import replace
    from reclaim.paypal import DemoGateway
    service,workspace,_=system
    deal=ready(service,workspace); authorize_all(service,workspace,deal); service.process(workspace,deal["id"])
    refunded_id=current(service,workspace)["commitments"][0]["capture_id"]
    class Gateway(DemoGateway):
        def read_capture(self,capture_id):
            return {"status":"REFUNDED" if capture_id==refunded_id else "COMPLETED"}
    service.settings=replace(service.settings,payment_mode="sandbox"); service.gateway=Gateway()
    with service.store.transaction(workspace) as (state,db): state["deals"][0]["provider_review_requested"]=True
    assert service.process(workspace,deal["id"]) is None
    result=current(service,workspace)
    assert result["status"]=="CANCELLED"
    assert all(c["payment_status"]=="REFUNDED" for c in result["commitments"])


def test_external_partial_refund_requires_operator_not_a_second_full_refund(system):
    from dataclasses import replace
    from reclaim.paypal import DemoGateway
    service,workspace,_=system
    deal=ready(service,workspace); authorize_all(service,workspace,deal); service.process(workspace,deal["id"])
    class Gateway(DemoGateway):
        def read_capture(self,capture_id): return {"status":"PARTIALLY_REFUNDED"}
    service.settings=replace(service.settings,payment_mode="sandbox"); service.gateway=Gateway()
    with service.store.transaction(workspace) as (state,db): state["deals"][0]["provider_review_requested"]=True
    assert service.process(workspace,deal["id"])
    assert current(service,workspace)["status"]=="RECOVERY_REQUIRED"
    assert not any(op["kind"]=="refund" for op in service.store.read(workspace)["operations"].values())


@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"),reason="Requires PostgreSQL integration service")
def test_separate_store_connections_share_postgres_reservation_lock(system):
    service,workspace,_=system; add_chen(service,workspace)
    instances=[Service(Store(service.settings.database_url),service.settings) for _ in range(4)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(lambda s:s.propose(workspace,"alice","lot_moving"),instances))
    assert len({d["id"] for d in results})==1


@given(total=st.integers(1,100000),weights=st.dictionaries(st.text(alphabet='abcdef',min_size=1,max_size=3),st.integers(1,10000),min_size=1,max_size=8))
def test_cent_rounding_conserves_total_and_is_order_independent(total,weights):
    result=split_price(total,weights)
    assert sum(result.values())==total
    assert result==split_price(total,dict(reversed(list(weights.items()))))
    assert all(abs(result[k]-total*w/sum(weights.values()))<1 for k,w in weights.items())


@property_settings(max_examples=40,deadline=None)
@given(total=st.integers(2,200),w1=st.integers(1,20),w2=st.integers(1,20),budgets=st.lists(st.integers(1,220),min_size=3,max_size=3))
def test_small_solver_cases_against_exhaustive_enumeration(total,w1,w2,budgets):
    base=seed(); lot=deepcopy(base["lots"][0]); lot["units"]=[lot["units"][0],lot["units"][2]]
    lot["units"][0]["reference_weight"]=w1; lot["units"][1]["reference_weight"]=w2
    lot.update(goods_price_minor=total,preparation_minor=0)
    demands=[]
    for i,types in enumerate([['desk'],['chair'],['desk','chair']]):
        demand=deepcopy(base['demands'][0]); demand.update(id=f'd{i}',buyer_id=f'b{i}',buyer_name=f'Buyer {i}',budget_minor=budgets[i],needs=[{'item_type':t,'quantity':1,'minimum_condition':'good'} for t in types]); demands.append(demand)
    feasible=[]
    for count in range(1,4):
        for selected in combinations(demands,count):
            types=[n['item_type'] for d in selected for n in d['needs']]
            if sorted(types)!=['chair','desk']:
                continue
            weights={d['buyer_id']:sum(w1 if n['item_type']=='desk' else w2 for n in d['needs']) for d in selected}
            prices=split_price(total,weights)
            if all(0<prices[d['buyer_id']]<=d['budget_minor'] for d in selected):
                feasible.append(selected)
    result=match_lot(lot,demands)
    assert result['complete']==bool(feasible)
    if feasible:
        assert len(result['allocations'])==max(map(len,feasible))
        validate_allocation(lot,demands,result['allocations'])


def test_crash_after_remote_capture_before_result_commit_recovers_once(system):
    from reclaim.paypal import DemoGateway, money
    service,workspace,_=system
    deal=ready(service,workspace); authorize_all(service,workspace,deal)
    remote={}; calls=[]
    class Remote(DemoGateway):
        crash=True
        def execute(self,kind,c,key,state):
            if kind!="capture": return super().execute(kind,c,key,state)
            if key not in remote:
                remote[key]={"id":"REMOTE-"+key,"status":"COMPLETED","amount":{"currency_code":"USD","value":money(c["price_minor"])}}
                calls.append(key)
            if self.crash:
                self.crash=False
                raise SystemExit("simulated process crash after provider commit")
            return remote[key]
        def reconcile_capture(self,c,key,state): return remote.get(key)
    gateway=Remote(); service.gateway=gateway
    with pytest.raises(SystemExit): service.process(workspace,deal["id"])
    assert current(service,workspace)["status"]=="READY"
    from reclaim.paypal import request_key
    assert service.store.read_operation(request_key(deal["commitments"][0]["id"],"capture"))["status"]=="PENDING"
    restarted=Service(Store(service.settings.database_url),service.settings); restarted.gateway=gateway
    assert restarted.process(workspace,deal["id"]) is None
    assert current(restarted,workspace)["status"]=="PAID"
    assert len(calls)==3 and len(set(calls))==3


def test_expired_crash_recovery_never_creates_remaining_captures(system):
    from reclaim.paypal import DemoGateway, money
    service,workspace,_=system
    deal=ready(service,workspace); authorize_all(service,workspace,deal)
    remote={}; captures=[]
    class Remote(DemoGateway):
        def execute(self,kind,c,key,state):
            if kind=="capture":
                remote[key]={"id":"REMOTE-"+key,"status":"COMPLETED","amount":{"currency_code":"USD","value":money(c["price_minor"])}}
                captures.append(key)
                raise SystemExit("simulated crash")
            return super().execute(kind,c,key,state)
        def reconcile_capture(self,c,key,state): return remote.get(key)
    gateway=Remote(); service.gateway=gateway
    with pytest.raises(SystemExit): service.process(workspace,deal["id"])
    with service.store.transaction(workspace) as (state,db): state["deals"][0]["expires_at"]=(now()-timedelta(seconds=1)).isoformat()
    restarted=Service(Store(service.settings.database_url),service.settings); restarted.gateway=gateway
    assert restarted.process(workspace,deal["id"]) is None
    result=current(restarted,workspace)
    assert result["status"]=="EXPIRED"
    assert [c["payment_status"] for c in result["commitments"]]==["REFUNDED","VOIDED","VOIDED"]
    assert len(captures)==1


def test_checkout_expiring_between_captures_recovers_previous_capture(system,monkeypatch):
    import reclaim.service as module
    from reclaim.paypal import DemoGateway
    service,workspace,_=system
    deal=ready(service,workspace); authorize_all(service,workspace,deal)
    clock=[now()]
    class Gateway(DemoGateway):
        def execute(self,kind,c,key,state):
            result=super().execute(kind,c,key,state)
            if kind=="capture": clock[0]+=timedelta(minutes=16)
            return result
    service.gateway=Gateway(); monkeypatch.setattr(module,"now",lambda:clock[0])
    assert service.process(workspace,deal["id"]) is None
    result=current(service,workspace)
    assert result["status"]=="EXPIRED"
    assert [c["payment_status"] for c in result["commitments"]]==["REFUNDED","VOIDED","VOIDED"]


def test_changing_payment_adapter_cannot_charge_or_refund_old_commitments(system):
    from dataclasses import replace
    service,workspace,_=system
    deal=ready(service,workspace)
    restarted=Service(Store(service.settings.database_url),replace(service.settings,payment_mode="sandbox",paypal_client_id="new-test-merchant",paypal_client_secret="test-only"))
    with pytest.raises(DomainError,match="earlier payment configuration"):
        restarted.create_order(workspace,"alice",deal["commitments"][0]["id"])
    assert not service.store.read(workspace)["operations"]


def test_connector_and_compatibility_require_confirmed_evidence():
    from reclaim.solver import compatible
    state=seed("creator"); unit=state["lots"][0]["units"][0]
    need={"item_type":"microphone","quantity":1,"minimum_condition":"good","attributes":[{"key":"connector","value":"usb","operator":"equals"}]}
    assert compatible(unit,need)[0]
    need["attributes"].append({"key":"compatible_with","value":"macos","operator":"includes"})
    assert not compatible(unit,need)[0]
    unit["attributes"].append({"key":"compatible_with","value":"macos, windows","evidence":"Seller tested"})
    unit["confirmed_fields"].append("attribute:compatible_with")
    assert compatible(unit,need)[0]
    unit["confirmed_fields"].remove("attribute:connector")
    assert not compatible(unit,need)[0]


def test_additional_size_and_date_requirements_are_not_relaxed():
    from reclaim.solver import compatible
    unit=seed()["lots"][0]["units"][3]
    need={"item_type":"monitor","quantity":1,"minimum_condition":"good","attributes":[{"key":"diagonal_inches","value":"27","operator":"at_least"}]}
    assert not compatible(unit,need)[0]
    need["attributes"][0]["value"]="24"
    assert compatible(unit,need)[0]
    unit["attributes"].append({"key":"expiry_date","value":"2026-12-31"}); unit["confirmed_fields"].append("attribute:expiry_date")
    need["attributes"].append({"key":"expiry_date","value":"2027-01-01","operator":"at_least"})
    assert not compatible(unit,need)[0]


def test_unconfirmed_reference_weights_cannot_be_used_for_prices():
    state=seed(); state["lots"][0]["units"][0]["confirmed_fields"].remove("reference_weight")
    assert match_lot(state["lots"][0],state["demands"])["status"]=="NEEDS_CONFIRMATION"


def test_cancel_intent_blocks_pickup_even_after_aggregate_rollback(system):
    service,workspace,_=system
    deal=ready(service,workspace); authorize_all(service,workspace,deal); service.process(workspace,deal["id"])
    service.prepare(workspace,"seller",deal["id"])
    with pytest.raises(SystemExit):
        with service.store.transaction(workspace) as (state,db):
            service.cancel(state,state["deals"][0],"Participant withdrew","alice")
            raise SystemExit("crash before aggregate/outbox commit")
    assert current(service,workspace)["status"]=="FULFILLING"
    c=current(service,workspace)["commitments"][0]
    with pytest.raises(DomainError,match="cancellation intent"):
        service.pickup(workspace,"alice",c["id"],c["pickup_code"])
    service.process(workspace,deal["id"])
    assert current(service,workspace)["status"]=="CANCELLED"
