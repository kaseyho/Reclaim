from contextlib import asynccontextmanager
from pathlib import Path
import secrets
import threading
import time
import hashlib
from collections import defaultdict, deque
import jwt
from fastapi import Depends, FastAPI, Header, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from sqlalchemy import select
from .ai import AIUnavailable, validate_image
from .config import Settings
from .paypal import ProviderError, request_key
from .repository import Store, Job, Webhook, Workspace
from .schemas import AuthorizeInput, DemandInput, FailureInput, InterpretInput, LotInput, PickupInput, ProblemInput, SessionInput, VersionInput, now
from .seeds import seed
from .service import DomainError, Service, event, get_entity
from .worker import run


def create_app(settings=None,store=None):
    settings=settings or Settings()
    store=store or Store(settings.database_url)
    service=Service(store,settings)
    stop=threading.Event()
    limiter=defaultdict(deque)
    limit_lock=threading.Lock()
    jwks=jwt.PyJWKClient(settings.supabase_url+"/auth/v1/.well-known/jwks.json") if settings.supabase_url else None

    @asynccontextmanager
    async def lifespan(app):
        thread=None
        if settings.auto_worker:
            thread=threading.Thread(target=run,args=(service,stop),daemon=True)
            thread.start()
        yield
        stop.set()
        if thread:
            thread.join(timeout=2)

    app=FastAPI(title="Reclaim API",version="0.1.0",lifespan=lifespan)
    app.state.service=service
    app.add_middleware(CORSMiddleware,allow_origins=[v.strip() for v in settings.cors_origins.split(",") if v.strip()],allow_methods=["GET","POST","PUT"],allow_headers=["Authorization","Content-Type","X-Workspace-Token"])

    @app.exception_handler(DomainError)
    async def domain_error(request,error):
        return JSONResponse({"detail":str(error)},status_code=error.status)

    @app.exception_handler(PermissionError)
    async def permission_error(request,error):
        return JSONResponse({"detail":str(error)},status_code=401)

    @app.exception_handler(AIUnavailable)
    async def ai_error(request,error):
        return JSONResponse({"detail":str(error)},status_code=503)

    @app.exception_handler(KeyError)
    async def missing_error(request,error):
        return JSONResponse({"detail":"Record not found."},status_code=404)

    def throttle(request,kind,limit=30):
        ip=request.client.host if request.client else "unknown"
        key=kind+":"+ip
        with limit_lock:
            recent=limiter[key]
            while recent and recent[0]<time.monotonic()-60:
                recent.popleft()
            if len(recent)>=limit:
                raise DomainError("Too many requests. Please wait one minute and retry.",429)
            recent.append(time.monotonic())

    def claims(authorization):
        try:
            token=(authorization or "").removeprefix("Bearer ")
            key=jwks.get_signing_key_from_jwt(token)
            return jwt.decode(token,key.key,algorithms=["ES256","RS256"],audience=settings.jwt_audience,issuer=settings.supabase_url+"/auth/v1",options={"require":["exp","sub","iss","aud"]})
        except (jwt.PyJWTError,AttributeError,ValueError) as error:
            raise DomainError("Sign in with the configured Supabase account.",401) from error

    def identity(authorization:str|None=Header(default=None),x_workspace_token:str|None=Header(default=None)):
        user=claims(authorization) if settings.auth_mode=="supabase" else None
        token=x_workspace_token if user else (authorization or "").removeprefix("Bearer ")
        membership=store.membership(token or "")
        if not membership:
            raise DomainError("Start or reopen a valid Reclaim session.",401)
        workspace_id,actor_id=membership
        if user:
            with store.sessions() as db:
                workspace=db.get(Workspace,workspace_id)
                if workspace.owner!=user["sub"]:
                    raise DomainError("This walkthrough belongs to another account.",403)
        return workspace_id,actor_id

    @app.get("/api/health")
    def health():
        return {"status":"ok","payment_mode":settings.payment_mode,"ai_provider":"openai" if settings.openai_api_key else "demo-parser","paypal_configured":settings.paypal_ready,"database":"sqlite-local" if store.sqlite else "postgresql"}

    @app.get("/api/config")
    def config():
        return {"payment_mode":settings.payment_mode,"paypal_client_id":settings.paypal_client_id if settings.payment_mode=="sandbox" else None,"paypal_configured":settings.paypal_ready,"ai_provider":"openai" if settings.openai_api_key else "demo-parser","ai_model":settings.openai_model if settings.openai_api_key else None,"auth_mode":settings.auth_mode,"supabase_url":settings.supabase_url or None,"supabase_publishable_key":settings.supabase_publishable_key if settings.auth_mode=="supabase" else None,"checkout_minutes":settings.checkout_minutes,"currency":"USD","merchant_scope":"One cooperating sandbox merchant"}

    @app.post("/api/sessions",status_code=201)
    def session(data:SessionInput,request:Request,authorization:str|None=Header(default=None)):
        throttle(request,"session",10)
        user=claims(authorization) if settings.auth_mode=="supabase" else None
        workspace_id,tokens=store.create(seed(data.scenario),settings.session_ttl_hours,user["sub"] if user else None)
        return {"workspace_id":workspace_id,"tokens":tokens,"scenario":data.scenario,"expires_in_hours":settings.session_ttl_hours,"note":"Isolated judge walkthrough. Persona tokens are separate identities within this test marketplace."}

    @app.get("/api/state")
    def state(lot_id:str|None=None,who=Depends(identity)):
        return service.snapshot(*who,lot_id=lot_id)

    def interpret(kind,data,request,who):
        throttle(request,"ai",12)
        try:
            result,trace=service.ai.run(kind,data.text,data.category,data.image)
        except ValueError as error:
            raise DomainError(str(error),422) from error
        with store.transaction(who[0]) as (state,db):
            trace.update(id="ai_"+secrets.token_hex(8),kind=kind,actor=who[1],at=now().isoformat(),input_sha256=hashlib.sha256(data.model_dump_json().encode()).hexdigest(),input_reference="Form input fingerprint; raw text and images not logged")
            state["ai_runs"].append(trace)
            state["ai_runs"]=state["ai_runs"][-100:]
            event(state,who[1],"Inventory extracted" if kind=="extract" else "Request interpreted",trace["provider"]+" · review and confirmation required.")
        return {"result":result.model_dump(mode="json"),"trace":trace,"requires_confirmation":True}

    @app.post("/api/lots/extract")
    def extract(data:InterpretInput,request:Request,who=Depends(identity)):
        state=store.read(who[0])
        service.actor(state,who[1],"seller")
        return interpret("extract",data,request,who)

    @app.post("/api/demands/interpret")
    def demand_interpret(data:InterpretInput,request:Request,who=Depends(identity)):
        service.actor(store.read(who[0]),who[1],"buyer")
        return interpret("interpret",data,request,who)

    @app.post("/api/lots",status_code=201)
    def lot(data:LotInput,who=Depends(identity)):
        if len(store.read(who[0])["lots"])>=32:
            raise DomainError("This walkthrough supports up to 32 listings.",422)
        return service.save_lot(*who,data)

    @app.put("/api/lots/{lot_id}")
    def edit_lot(lot_id:str,data:LotInput,who=Depends(identity)):
        return service.save_lot(*who,data,lot_id=lot_id)

    @app.post("/api/demands",status_code=201)
    def demand(data:DemandInput,who=Depends(identity)):
        if len(store.read(who[0])["demands"])>=64:
            raise DomainError("This walkthrough supports up to 64 requests.",422)
        return service.save_demand(*who,data)

    @app.put("/api/demands/{demand_id}")
    def edit_demand(demand_id:str,data:DemandInput,who=Depends(identity)):
        return service.save_demand(*who,data,demand_id=demand_id)

    @app.post("/api/match-runs/{lot_id}")
    def propose(lot_id:str,who=Depends(identity)):
        return service.propose(*who,lot_id)

    @app.post("/api/deals/{deal_id}/accept")
    def accept(deal_id:str,data:VersionInput,who=Depends(identity)):
        return service.accept(*who,deal_id,data)

    @app.post("/api/deals/{deal_id}/withdraw")
    def withdraw(deal_id:str,who=Depends(identity)):
        return service.withdraw(*who,deal_id)

    @app.post("/api/commitments/{commitment_id}/paypal-order")
    def create_order(commitment_id:str,who=Depends(identity)):
        return service.create_order(*who,commitment_id)

    @app.post("/api/commitments/{commitment_id}/authorize")
    def authorize(commitment_id:str,data:AuthorizeInput,who=Depends(identity)):
        return service.authorize(*who,commitment_id,data.order_id)

    @app.post("/api/deals/{deal_id}/prepare")
    def prepare(deal_id:str,who=Depends(identity)):
        return service.prepare(*who,deal_id)

    @app.post("/api/fulfillments/{commitment_id}/confirm-pickup")
    def pickup(commitment_id:str,data:PickupInput,who=Depends(identity)):
        return service.pickup(*who,commitment_id,data.code)

    @app.post("/api/fulfillments/{commitment_id}/problem")
    def problem(commitment_id:str,data:ProblemInput,who=Depends(identity)):
        with store.transaction(who[0]) as (state,db):
            deal=next((d for d in state["deals"] if any(c["id"]==commitment_id for c in d["commitments"])),None)
            if not deal:
                raise DomainError("Order not found.",404)
            c=next(c for c in deal["commitments"] if c["id"]==commitment_id)
            if who[1] not in {c["buyer_id"],deal["seller_id"]}:
                raise DomainError("Only the buyer or seller can report this problem.",403)
            report={"id":"problem_"+secrets.token_hex(8),"message":data.message,"status":"OPEN","actor":who[1],"at":now().isoformat()}
            c["problems"].append(report)
            event(state,who[1],"Order problem reported",data.message,commitment_id)
            return report

    @app.post("/api/deals/{deal_id}/retry-recovery")
    def retry(deal_id:str,who=Depends(identity)):
        with store.transaction(who[0]) as (state,db):
            deal=get_entity(state,"deals",deal_id)
            if who[1]!=deal["seller_id"]:
                raise DomainError("Seller operator access is required.",403)
            if deal["status"] not in {"RECOVERY_REQUIRED","RECONCILING","REFUNDING","CANCELLING"}:
                raise DomainError("This group does not need a recovery retry.")
            deal["status"]="CANCELLING" if deal["cancel_requested"] else "RECONCILING"
            state["failures"]=[f for f in state["failures"] if f["kind"]!="refund"]
            store.enqueue(db,who[0],"process",deal_id)
            event(state,who[1],"Recovery retried","Reuses stored provider request IDs; inventory stays reserved.",deal_id)
            return {"queued":True}

    @app.post("/api/demo/failure")
    def failure(data:FailureInput,who=Depends(identity)):
        if settings.payment_mode!="demo":
            raise DomainError("Failure simulation is available only in labelled demo mode.",403)
        with store.transaction(who[0]) as (state,db):
            service.actor(state,who[1],"seller")
            service.actor(state,data.actor_id,"buyer")
            state["failures"].append({"kind":data.kind,"actor_id":data.actor_id,"remaining":99 if data.kind=="refund" else 1})
            event(state,who[1],"Demo failure scheduled",data.kind+" for "+data.actor_id)
        return {"scheduled":True,"mode":"demo"}

    @app.post("/api/webhooks/paypal")
    async def webhook(request:Request):
        if settings.payment_mode!="sandbox":
            raise DomainError("PayPal webhooks require sandbox mode.",403)
        body=await request.body()
        if len(body)>262144:
            raise DomainError("Webhook body is too large.",413)
        try:
            import json
            payload=json.loads(body)
        except ValueError as error:
            raise DomainError("Invalid webhook JSON.",400) from error
        if not isinstance(payload,dict) or not isinstance(payload.get("id"),str):
            raise DomainError("Webhook ID is required.",400)
        try:
            verified=await run_in_threadpool(service.gateway.verify_webhook,request.headers,payload)
        except ProviderError as error:
            raise DomainError(str(error),503) from error
        if not verified:
            raise DomainError("PayPal webhook signature is invalid.",401)
        with store.local_lock,store.sessions.begin() as db:
            if db.get(Webhook,payload["id"]):
                return {"received":True,"duplicate":True}
            resource=payload.get("resource",{})
            identifiers={resource.get("id"),*resource.get("supplementary_data",{}).get("related_ids",{}).values()}
            # Persist only event ID/type/related provider IDs. Provider polling is authoritative.
            db.add(Webhook(id=payload["id"],body={"event_type":payload.get("event_type"),"related_ids":[i for i in identifiers if isinstance(i,str)]}))
            for workspace in db.scalars(select(Workspace).with_for_update()):
                state=workspace.state
                for deal in state["deals"]:
                    if any(any(c.get(k) in identifiers for k in ["order_id","authorization_id","capture_id","refund_id"] if c.get(k)) for c in deal["commitments"]):
                        from copy import deepcopy
                        state=deepcopy(state)
                        selected=next(d for d in state["deals"] if d["id"]==deal["id"])
                        selected["provider_review_requested"]=True
                        event(state,"paypal","Verified webhook received",str(payload.get("event_type"))+" · provider reconciliation queued.",selected["id"])
                        if selected["status"] not in {"CANCELLED","EXPIRED","COMPLETED"}:
                            store.enqueue(db,workspace.id,"process",selected["id"])
                        workspace.state=state
        return {"received":True,"duplicate":False}

    root=Path(__file__).resolve().parents[2]
    dist=root/"dist"
    if dist.exists():
        if (dist/"assets").exists():
            app.mount("/assets",StaticFiles(directory=dist/"assets"),name="assets")
        @app.get("/{path:path}")
        def frontend(path:str):
            if path=="api" or path.startswith("api/"):
                raise DomainError("API route not found.",404)
            file=(dist/path).resolve()
            if file.is_relative_to(dist.resolve()) and file.is_file():
                return FileResponse(file)
            return FileResponse(dist/"index.html")
    return app


app=create_app()
