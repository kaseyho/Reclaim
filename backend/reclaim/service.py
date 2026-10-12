from copy import deepcopy
from datetime import timedelta
import hashlib
import json
import secrets
from .ai import AI, validate_image
from .paypal import DemoGateway, PayPalSandbox, ProviderError, minor_units, request_key
from .schemas import now
from .solver import match_lot, timestamp, validate_allocation

ACTIVE={"PROPOSED","ACCEPTING","AUTHORIZING","READY","CAPTURING","RECONCILING","CANCELLING","REFUNDING","RECOVERY_REQUIRED"}
PAID={"PAID","FULFILLING","COMPLETED"}


class DomainError(Exception):
    def __init__(self,message,status=409):
        super().__init__(message)
        self.status=status


def get_entity(state,collection,entity_id):
    result=next((v for v in state[collection] if v["id"]==entity_id),None)
    if not result:
        raise DomainError("That record was not found in this workspace.",404)
    return result


def event(state,actor,action,detail,entity_id=None):
    state["events"].append({"id":"event_"+secrets.token_hex(8),"at":now().isoformat(),"actor":actor,"action":action,"detail":detail,"entity_id":entity_id})
    state["events"]=state["events"][-500:]


def terms_hash(terms):
    return hashlib.sha256(json.dumps(terms,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()).hexdigest()


class Service:
    def __init__(self,store,settings):
        self.store=store
        self.settings=settings
        self.gateway=DemoGateway() if settings.payment_mode=="demo" else PayPalSandbox(settings)
        self.ai=AI(settings)

    @property
    def merchant_reference(self):
        return "demo" if self.gateway.mode=="demo" else hashlib.sha256(self.settings.paypal_client_id.encode()).hexdigest()[:24]

    def actor(self,state,actor_id,role=None):
        actor=next((a for a in state["actors"] if a["id"]==actor_id),None)
        if not actor or (role and actor["role"]!=role):
            raise DomainError("This action requires the correct buyer or seller identity.",403)
        return actor

    def snapshot(self,workspace_id,actor_id,lot_id=None):
        state=self.store.read(workspace_id)
        self.actor(state,actor_id)
        state.pop("demo_provider_results",None)
        state.pop("failures",None)
        # Receipts are individual; pickup codes stay with their buyer and seller.
        for deal in state["deals"]:
            deal["payment_mode"]=deal.get("payment_mode","demo")
            for c in deal["commitments"]:
                for kind in ["create","authorize","capture","refund","void"]:
                    key=request_key(c["id"],kind)
                    operation=self.store.read_operation(key)
                    if operation:
                        state["operations"][key]=operation
                if actor_id not in {c["buyer_id"],deal["seller_id"]}:
                    c.pop("pickup_code",None)
        state["operations"]={k:{f:v for f,v in op.items() if f in {"id","kind","commitment_id","status","attempts","provider_id","provider_status","error","updated_at","request_id"}} for k,op in state["operations"].items()}
        candidate=next((lot for lot in state["lots"] if lot["status"]=="AVAILABLE" and (lot_id is None or lot["id"]==lot_id)),None)
        state["diagnostics"]=[match_lot(candidate,state["demands"])] if candidate else []
        return state

    def save_lot(self,workspace_id,actor_id,data,lot_id=None):
        validate_image(data.image)
        with self.store.transaction(workspace_id) as (state,db):
            actor=self.actor(state,actor_id,"seller")
            value=data.model_dump(mode="json")
            if lot_id:
                old=get_entity(state,"lots",lot_id)
                if old["seller_id"]!=actor_id:
                    raise DomainError("Only this lot's seller can change it.",403)
                if old["status"]=="SOLD":
                    raise DomainError("Paid inventory cannot be edited. Use order problem reporting.")
                reserved=next((d for d in state["deals"] if d["lot_id"]==lot_id and d["status"] in ACTIVE),None)
                if reserved:
                    self.cancel(state,reserved,"Inventory changed",actor_id)
                    self.store.enqueue(db,workspace_id,"process",reserved["id"])
                old.update(value,version=old["version"]+1,status="RESERVED" if reserved else "AVAILABLE")
                result=old
            else:
                result={**value,"id":"lot_"+secrets.token_hex(8),"version":1,"seller_id":actor_id,"seller_name":actor["name"],"status":"AVAILABLE","created_at":now().isoformat()}
                state["lots"].append(result)
            event(state,actor_id,"Inventory confirmed" if data.confirmed else "Listing draft saved",result["title"],result["id"])
            return deepcopy(result)

    def save_demand(self,workspace_id,actor_id,data,demand_id=None):
        with self.store.transaction(workspace_id) as (state,db):
            actor=self.actor(state,actor_id,"buyer")
            if data.deadline<=now():
                raise DomainError("Choose a future request deadline.",422)
            value=data.model_dump(mode="json")
            if demand_id:
                old=get_entity(state,"demands",demand_id)
                if old["buyer_id"]!=actor_id:
                    raise DomainError("Only the buyer can change this request.",403)
                if old["status"]=="FULFILLED":
                    raise DomainError("A purchased request cannot be edited.")
                reserved=next((d for d in state["deals"] if any(c["demand_id"]==demand_id for c in d["commitments"]) and d["status"] in ACTIVE),None)
                if reserved:
                    self.cancel(state,reserved,"Buyer requirements changed",actor_id)
                    self.store.enqueue(db,workspace_id,"process",reserved["id"])
                old.update(value,version=old["version"]+1,status="RESERVED" if reserved else "OPEN")
                result=old
            else:
                result={**value,"id":"demand_"+secrets.token_hex(8),"version":1,"buyer_id":actor_id,"buyer_name":actor["name"],"status":"OPEN","created_at":now().isoformat()}
                state["demands"].append(result)
            event(state,actor_id,"Request confirmed" if data.confirmed else "Request draft saved",result["text"],result["id"])
            return deepcopy(result)

    def propose(self,workspace_id,actor_id,lot_id):
        with self.store.transaction(workspace_id) as (state,db):
            self.actor(state,actor_id)
            existing=next((d for d in state["deals"] if d["lot_id"]==lot_id and d["status"] in ACTIVE|PAID),None)
            if existing:
                return deepcopy(existing)
            lot=get_entity(state,"lots",lot_id)
            result=match_lot(lot,state["demands"])
            state["match_runs"].append({"id":"match_"+secrets.token_hex(8),"at":now().isoformat(),**result})
            if not result.get("complete"):
                raise DomainError("A complete group is not ready yet. Review the missing items and constraints.")
            validate_allocation(lot,state["demands"],result["allocations"])
            deal_id="deal_"+secrets.token_hex(8)
            expires=(now()+timedelta(minutes=self.settings.checkout_minutes)).isoformat()
            terms={"lot_id":lot_id,"lot_version":lot["version"],"allocations":result["allocations"],"currency":lot["currency"],"total_minor":lot["goods_price_minor"]+lot["preparation_minor"],"preparation_minor":lot["preparation_minor"],"pickup_start":lot["pickup_start"],"pickup_end":lot["pickup_end"],"location":lot["location"],"expires_at":expires,"cancellation":"Capture begins only when every buyer is authorized and the seller has accepted. If the group fails before pickup, reconcile, refund completed captures, and void remaining authorizations."}
            terms["payment_mode"]=self.gateway.mode
            terms["merchant_reference"]=self.merchant_reference
            commitments=[]
            for allocation in result["allocations"]:
                demand=get_entity(state,"demands",allocation["demand_id"])
                demand["status"]="RESERVED"
                commitments.append({**allocation,"id":deal_id+"_"+allocation["buyer_id"],"buyer_name":demand["buyer_name"],"demand_version":demand["version"],"payment_mode":self.gateway.mode,"merchant_reference":self.merchant_reference,"accepted":False,"payment_status":"NONE","order_id":None,"authorization_id":None,"capture_id":None,"refund_id":None,"pickup_code":None,"fulfillment_status":"WAITING","problems":[]})
            deal={"id":deal_id,"version":1,"lot_id":lot_id,"lot_title":lot["title"],"seller_id":lot["seller_id"],"seller_name":lot["seller_name"],"terms":terms,"terms_hash":terms_hash(terms),"commitments":commitments,"seller_accepted":False,"status":"PROPOSED","expires_at":expires,"created_at":now().isoformat(),"solver_status":result["status"],"solver_ms":result["elapsed_ms"],"cancel_requested":False,"cancel_reason":None,"recovery_note":None}
            deal["version"]=max([d["version"] for d in state["deals"] if d["lot_id"]==lot_id]+[0])+1
            deal["payment_mode"]=self.gateway.mode
            deal["merchant_reference"]=self.merchant_reference
            lot["status"]="RESERVED"
            state["deals"].append(deal)
            self.store.enqueue(db,workspace_id,"expire",deal_id,available_at=timestamp(expires))
            event(state,actor_id,"Complete group proposed","All goods allocated; exact prices and terms frozen for participant review.",deal_id)
            return deepcopy(deal)

    def check_terms(self,state,deal,version=None,hash_value=None):
        if self.store.read_operation(request_key(deal["id"],"cancel")):
            raise DomainError("Cancellation is requested for this proposal. Recovery must finish before a new group can check out.")
        if deal.get("payment_mode","demo")!=self.gateway.mode or deal.get("merchant_reference",self.merchant_reference)!=self.merchant_reference:
            raise DomainError("This proposal belongs to an earlier payment configuration. Restore its original provider settings or open a fresh example.")
        if deal["status"] not in ACTIVE or deal["cancel_requested"]:
            raise DomainError("This proposal is no longer available for checkout.")
        if version is not None and (version!=deal["version"] or hash_value!=deal["terms_hash"]):
            raise DomainError("Terms changed. Review the current proposal before accepting.")
        if timestamp(deal["expires_at"])<=now():
            raise DomainError("The checkout window expired. Start a new group after cancellation finishes.")
        lot=get_entity(state,"lots",deal["lot_id"])
        if lot["version"]!=deal["terms"]["lot_version"] or not lot["confirmed"] or not lot["divisible"]:
            raise DomainError("Inventory changed or is unconfirmed. A new proposal is required.")
        for c in deal["commitments"]:
            demand=get_entity(state,"demands",c["demand_id"])
            if demand["version"]!=c["demand_version"] or not demand["confirmed"]:
                raise DomainError("A buyer request changed. A new proposal is required.")
        validate_allocation(lot,state["demands"],deal["terms"]["allocations"])

    def accept(self,workspace_id,actor_id,deal_id,data):
        with self.store.transaction(workspace_id) as (state,db):
            self.actor(state,actor_id)
            deal=get_entity(state,"deals",deal_id)
            self.check_terms(state,deal,data.version,data.terms_hash)
            if actor_id==deal["seller_id"]:
                deal["seller_accepted"]=True
            else:
                commitment=next((c for c in deal["commitments"] if c["buyer_id"]==actor_id),None)
                if not commitment:
                    raise DomainError("Only proposal participants can accept these terms.",403)
                commitment["accepted"]=True
            deal["status"]="AUTHORIZING" if deal["seller_accepted"] and all(c["accepted"] for c in deal["commitments"]) else "ACCEPTING"
            event(state,actor_id,"Terms accepted",f'Accepted proposal v{deal["version"]}, {deal["terms_hash"][:12]}.',deal_id)
            return deepcopy(deal)

    def commitment(self,state,actor_id,commitment_id):
        for deal in state["deals"]:
            c=next((c for c in deal["commitments"] if c["id"]==commitment_id),None)
            if c:
                if actor_id!=c["buyer_id"]:
                    raise DomainError("Only this buyer can authorize their purchase.",403)
                return deal,c
        raise DomainError("Purchase commitment not found.",404)

    def invoke(self,state,c,kind,reconcile=False):
        if c.get("payment_mode","demo")!=self.gateway.mode or c.get("merchant_reference",self.merchant_reference)!=self.merchant_reference:
            raise ProviderError("Restore this purchase's original payment mode and merchant configuration before recovery.",uncertain=True,code="PROVIDER_CONFIGURATION_CHANGED")
        key=request_key(c["id"],kind)
        op=self.store.read_operation(key) or state["operations"].get(key) or {"id":key,"request_id":key,"kind":kind,"commitment_id":c["id"],"status":"PENDING","attempts":0,"provider_id":None,"provider_status":None,"error":None}
        state["operations"][key]=op
        if op["status"]=="DONE":
            return op["result"]
        op["attempts"]+=1
        op["updated_at"]=now().isoformat()
        op["status"]="PENDING"
        self.store.save_operation(op)
        try:
            result=self.gateway.reconcile_capture(c,key,state) if reconcile else self.gateway.execute(kind,c,key,state)
            if result is None and reconcile:
                op.update(status="NOT_CAPTURED",provider_status="NOT_CAPTURED",result=None,error=None)
                self.store.save_operation(op)
                return None
            # Store only operational evidence, never buyer PII from provider responses.
            fees=result.get("seller_receivable_breakdown",{})
            result={k:v for k,v in result.items() if k in {"id","status","amount"}}
            if fees.get("paypal_fee") and fees["paypal_fee"].get("currency_code")=="USD":
                result["paypal_fee_minor"]=minor_units(fees["paypal_fee"])
            if fees.get("net_amount") and fees["net_amount"].get("currency_code")=="USD":
                result["net_minor"]=minor_units(fees["net_amount"])
            if not result.get("id"):
                raise ProviderError("Provider returned no operation identifier.",uncertain=True)
            if kind in {"authorize","capture","refund"} and not result.get("amount"):
                raise ProviderError("Provider omitted the payment amount. Reconciliation is required.",uncertain=True,code="AMOUNT_MISSING")
            if kind in {"authorize","capture","refund"} and minor_units(result["amount"])!=c["price_minor"]:
                raise ProviderError("Provider amount does not match the purchase.",uncertain=True,code="AMOUNT_MISMATCH")
            op.update(status="PENDING_PROVIDER" if result.get("status")=="PENDING" else "FAILED" if result.get("status") in {"DECLINED","DENIED","FAILED"} else "DONE",provider_id=result["id"],provider_status=result.get("status"),result=result,error=None)
            self.store.save_operation(op)
            event(state,"paypal" if self.settings.payment_mode=="sandbox" else "demo",kind.title()+" result",f'{c["buyer_name"]}: {result.get("status")} · {result["id"]}',c["id"])
            return result
        except ProviderError as error:
            op.update(status="UNCERTAIN" if error.uncertain else "FAILED",error=str(error),error_code=error.code)
            self.store.save_operation(op)
            event(state,"paypal" if self.settings.payment_mode=="sandbox" else "demo",kind.title()+" needs recovery",f'{c["buyer_name"]}: {error}',c["id"])
            raise

    def create_order(self,workspace_id,actor_id,commitment_id):
        failure=None
        with self.store.transaction(workspace_id) as (state,db):
            deal,c=self.commitment(state,actor_id,commitment_id)
            self.check_terms(state,deal)
            if not deal["seller_accepted"] or not all(x["accepted"] for x in deal["commitments"]):
                raise DomainError("Every buyer and the seller must accept the same proposal before checkout.")
            if c["order_id"]:
                return {"id":c["order_id"],"mode":self.settings.payment_mode}
            try:
                result=self.invoke(state,c,"create")
                c.update(order_id=result["id"],payment_status="ORDER_CREATED")
            except ProviderError as error:
                failure=error
                deal["recovery_note"]=str(error)
        if failure:
            raise DomainError(str(failure),502)
        return {"id":result["id"],"mode":self.settings.payment_mode}

    def authorize(self,workspace_id,actor_id,commitment_id,order_id):
        failure=None
        with self.store.transaction(workspace_id) as (state,db):
            deal,c=self.commitment(state,actor_id,commitment_id)
            self.check_terms(state,deal)
            if order_id!=c["order_id"]:
                raise DomainError("This order is not the buyer's server-created order.")
            if c["authorization_id"] and c["payment_status"]=="AUTHORIZED":
                return deepcopy(c)
            try:
                result=self.invoke(state,c,"authorize")
                c["authorization_id"]=result["id"]
                c["payment_status"]="AUTHORIZED" if result["status"]=="CREATED" else "AUTHORIZATION_PENDING"
            except ProviderError as error:
                failure=error
                c["payment_status"]="RECONCILING" if error.uncertain else "ORDER_CREATED"
                deal["recovery_note"]=str(error)
            self.store.enqueue(db,workspace_id,"process",deal["id"])
            if all(x["payment_status"]=="AUTHORIZED" for x in deal["commitments"]):
                deal["status"]="READY"
        if failure:
            raise DomainError(str(failure),502)
        return deepcopy(c)

    def cancel(self,state,deal,reason,actor_id):
        if deal["status"]=="COMPLETED" or any(c["fulfillment_status"]=="COLLECTED" for c in deal["commitments"]):
            raise DomainError("Collected goods require problem resolution, not automatic cancellation.")
        deal.update(cancel_requested=True,cancel_reason=reason,status="CANCELLING")
        key=request_key(deal["id"],"cancel")
        previous=self.store.read_operation(key) or {}
        withdrawn=set(previous.get("result",{}).get("withdrawn_buyers",[]))
        if reason=="Participant withdrew" and actor_id!=deal["seller_id"]:
            withdrawn.add(actor_id)
        self.store.save_operation({"id":key,"request_id":key,"kind":"cancel","commitment_id":deal["id"],"status":"DONE","result":{"reason":reason,"withdrawn_buyers":sorted(withdrawn)},"actor":previous.get("actor",actor_id),"updated_at":now().isoformat()})
        event(state,actor_id,"Group cancellation requested",reason+". Reconciliation must finish before inventory is released.",deal["id"])

    def withdraw(self,workspace_id,actor_id,deal_id):
        with self.store.transaction(workspace_id) as (state,db):
            deal=get_entity(state,"deals",deal_id)
            if actor_id!=deal["seller_id"] and not any(c["buyer_id"]==actor_id for c in deal["commitments"]):
                raise DomainError("Only participants can cancel this group.",403)
            if deal["status"] in {"CANCELLED","EXPIRED"}:
                return deepcopy(deal)
            self.cancel(state,deal,"Participant withdrew",actor_id)
            for c in deal["commitments"]:
                if c["buyer_id"]==actor_id:
                    get_entity(state,"demands",c["demand_id"])["status"]="WITHDRAWN"
            self.store.enqueue(db,workspace_id,"process",deal_id)
            return deepcopy(deal)

    def process(self,workspace_id,deal_id):
        """Safe to resume after a crash: operations retain deterministic request IDs."""
        error=None
        with self.store.transaction(workspace_id,check_expiry=False) as (state,db):
            deal=get_entity(state,"deals",deal_id)
            # Recover journal results even when a crash rolled back the aggregate.
            for c in deal["commitments"]:
                for kind in ["create","authorize","capture","refund","void"]:
                    key=request_key(c["id"],kind)
                    op=self.store.read_operation(key)
                    if not op:
                        continue
                    state["operations"][key]=op
                    result=op.get("result")
                    if not result:
                        continue
                    provider_status=result.get("status")
                    if kind=="create":
                        c["order_id"]=result["id"]
                    elif kind=="authorize":
                        c["authorization_id"]=result["id"]
                        if c["payment_status"] not in {"CAPTURED","REFUND_PENDING","REFUNDED","PARTIALLY_REFUNDED","VOIDED"}:
                            c["payment_status"]="AUTHORIZED" if provider_status=="CREATED" else "AUTHORIZATION_PENDING"
                    elif kind=="capture" and provider_status in {"COMPLETED","PENDING"}:
                        c["capture_id"]=result["id"]
                        if c["payment_status"] not in {"REFUNDED","REFUND_PENDING","PARTIALLY_REFUNDED","VOIDED"}:
                            c["payment_status"]="CAPTURED" if provider_status=="COMPLETED" else "CAPTURE_PENDING"
                        c["paypal_fee_minor"]=result.get("paypal_fee_minor")
                        c["net_minor"]=result.get("net_minor")
                    elif kind=="refund":
                        c["refund_id"]=result["id"]
                        if c["payment_status"]!="REFUNDED":
                            c["payment_status"]="REFUNDED" if provider_status=="COMPLETED" else "REFUND_PENDING"
                    elif kind=="void" and provider_status=="VOIDED" and not c.get("capture_id"):
                        c["payment_status"]="VOIDED"
            cancellation=self.store.read_operation(request_key(deal["id"],"cancel"))
            if cancellation:
                for c in deal["commitments"]:
                    if c["buyer_id"] in cancellation["result"].get("withdrawn_buyers",[]):
                        get_entity(state,"demands",c["demand_id"])["status"]="WITHDRAWN"
            failed_capture=any(state["operations"].get(request_key(c["id"],"capture"),{}).get("status")=="FAILED" for c in deal["commitments"])
            if not deal["cancel_requested"] and (cancellation or failed_capture):
                self.cancel(state,deal,cancellation["result"]["reason"] if cancellation else "A capture failed","system")
            if deal.get("provider_review_requested") and self.settings.payment_mode=="sandbox":
                # A verified notification is a wakeup, not authoritative paid/refunded data.
                for c in deal["commitments"]:
                    if not c.get("capture_id"):
                        continue
                    try:
                        actual=self.gateway.read_capture(c["capture_id"])
                        if actual.get("amount") and minor_units(actual["amount"])!=c["price_minor"]:
                            raise ProviderError("Provider capture amount mismatch.",uncertain=True)
                    except ProviderError as failure:
                        deal["status"]="RECONCILING"
                        deal["recovery_note"]=str(failure)
                        return str(failure)
                    if actual.get("status")=="REFUNDED":
                        c["payment_status"]="REFUNDED"
                        event(state,"paypal","External refund confirmed",f'{c["buyer_name"]}: provider capture is fully refunded.',c["id"])
                        if not any(item["fulfillment_status"]=="COLLECTED" for item in deal["commitments"]):
                            self.cancel(state,deal,"A provider capture was refunded","system")
                        else:
                            deal["status"]="RECOVERY_REQUIRED"
                            deal["recovery_note"]="Provider refunded an order after collection. Seller resolution is required; inventory is not released."
                            return deal["recovery_note"]
                    elif actual.get("status")=="PARTIALLY_REFUNDED":
                        c["payment_status"]="PARTIALLY_REFUNDED"
                        deal["status"]="RECOVERY_REQUIRED"
                        deal["recovery_note"]="An external partial refund requires seller reconciliation in PayPal. Complete or resolve it there, then retry; no automatic full refund is issued."
                        return deal["recovery_note"]
                    elif actual.get("status") not in {"COMPLETED","PENDING"} and deal["status"] in PAID:
                        deal["status"]="RECOVERY_REQUIRED"
                        deal["recovery_note"]="PayPal capture state changed. Seller reconciliation is required before further pickup."
                        return deal["recovery_note"]
                deal["provider_review_requested"]=False
            if deal["status"] in {"CANCELLED","EXPIRED","COMPLETED","PAID","FULFILLING"}:
                return None
            if timestamp(deal["expires_at"])<=now() and not deal["cancel_requested"]:
                self.cancel(state,deal,"Checkout expired","system")
            if not deal["cancel_requested"]:
                try:
                    self.check_terms(state,deal)
                except DomainError as failure:
                    self.cancel(state,deal,str(failure),"system")
            # Resolve lost authorization responses before either capture or cleanup.
            for c in deal["commitments"]:
                op=state["operations"].get(request_key(c["id"],"authorize"))
                if op and op["status"] in {"PENDING","UNCERTAIN","PENDING_PROVIDER"}:
                    try:
                        result=self.invoke(state,c,"authorize")
                        c.update(authorization_id=result["id"],payment_status="AUTHORIZED" if result["status"]=="CREATED" else "AUTHORIZATION_PENDING")
                        if c["payment_status"]!="AUTHORIZED":
                            error="Waiting for PayPal authorization confirmation."
                    except ProviderError as failure:
                        error=str(failure)
            if not error and deal["cancel_requested"]:
                error=self.recover(state,deal)
            elif not error and all(c["payment_status"] in {"AUTHORIZED","CAPTURED","CAPTURE_PENDING"} for c in deal["commitments"]) and deal["seller_accepted"]:
                deal["status"]="CAPTURING"
                for c in deal["commitments"]:
                    if c["payment_status"]=="CAPTURED":
                        continue
                    try:
                        self.check_terms(state,deal)
                    except DomainError as failure:
                        self.cancel(state,deal,"Checkout expired" if timestamp(deal["expires_at"])<=now() else str(failure),"system")
                        error=self.recover(state,deal)
                        break
                    try:
                        result=self.invoke(state,c,"capture")
                        c["capture_id"]=result["id"]
                        c["paypal_fee_minor"]=result.get("paypal_fee_minor")
                        c["net_minor"]=result.get("net_minor")
                        c["payment_status"]="CAPTURED" if result["status"]=="COMPLETED" else "CAPTURE_PENDING"
                        if result["status"] in {"DECLINED","DENIED","FAILED"}:
                            c["payment_status"]="CAPTURE_FAILED"
                            c["capture_id"]=None
                            self.cancel(state,deal,"A capture failed","system")
                            error=self.recover(state,deal)
                            break
                        if c["payment_status"]!="CAPTURED":
                            error="Waiting for PayPal capture confirmation."
                            break
                    except ProviderError as failure:
                        deal["recovery_note"]=str(failure)
                        if failure.uncertain:
                            deal["status"]="RECONCILING"
                            error=str(failure)
                        else:
                            self.cancel(state,deal,"A capture failed","system")
                            error=self.recover(state,deal)
                        break
                if not deal["cancel_requested"] and all(c["payment_status"]=="CAPTURED" for c in deal["commitments"]):
                    deal["status"]="PAID"
                    deal["paid_at"]=now().isoformat()
                    deal["recovery_note"]=None
                    get_entity(state,"lots",deal["lot_id"])["status"]="SOLD"
                    for c in deal["commitments"]:
                        c["pickup_code"]=secrets.token_hex(3).upper()
                        c["fulfillment_status"]="TO_PREPARE"
                        get_entity(state,"demands",c["demand_id"])["status"]="FULFILLED"
                    event(state,"system","All purchases captured","Every capture is confirmed complete. Individual orders are ready for preparation.",deal_id)
            if error:
                deal["recovery_note"]=error
        return error

    def recover(self,state,deal):
        error=None
        # A capture timeout may conceal a successful charge. Reconcile it first.
        for c in deal["commitments"]:
            op=state["operations"].get(request_key(c["id"],"capture"))
            if op and op["status"] in {"PENDING","UNCERTAIN","NOT_CAPTURED","PENDING_PROVIDER"}:
                try:
                    result=self.invoke(state,c,"capture",reconcile=True)
                    if result is None:
                        continue
                    c["capture_id"]=result["id"]
                    c["payment_status"]="CAPTURED" if result["status"]=="COMPLETED" else "CAPTURE_PENDING"
                    if c["payment_status"]=="CAPTURE_PENDING":
                        error="Waiting for the uncertain capture outcome before recovery."
                except ProviderError as failure:
                    error=str(failure)
        if error:
            deal["status"]="RECONCILING"
            return error
        for c in deal["commitments"]:
            try:
                if c.get("capture_id") and c["payment_status"]!="REFUNDED":
                    result=self.invoke(state,c,"refund")
                    c["refund_id"]=result["id"]
                    c["payment_status"]="REFUNDED" if result["status"]=="COMPLETED" else "REFUND_PENDING"
                    if c["payment_status"]!="REFUNDED":
                        error="A refund is pending confirmation."
                elif c.get("authorization_id") and c["payment_status"] not in {"VOIDED","REFUNDED"}:
                    self.invoke(state,c,"void")
                    c["payment_status"]="VOIDED"
                elif not c.get("authorization_id") and not c.get("capture_id"):
                    c["payment_status"]="CANCELLED"
            except ProviderError as failure:
                error=str(failure)
        if error:
            deal["status"]="REFUNDING" if any(c.get("capture_id") for c in deal["commitments"]) else "RECONCILING"
            return error
        deal["status"]="EXPIRED" if deal["cancel_reason"]=="Checkout expired" else "CANCELLED"
        deal["recovery_note"]=None
        lot=get_entity(state,"lots",deal["lot_id"])
        lot["status"]="AVAILABLE"
        for c in deal["commitments"]:
            demand=get_entity(state,"demands",c["demand_id"])
            if demand["status"]!="WITHDRAWN":
                demand["status"]="OPEN"
            c["fulfillment_status"]="CANCELLED"
        event(state,"system","Group recovery complete","Completed captures refunded and remaining authorizations voided. Inventory and active requests released.",deal["id"])
        return None

    def prepare(self,workspace_id,actor_id,deal_id):
        with self.store.transaction(workspace_id) as (state,db):
            deal=get_entity(state,"deals",deal_id)
            if self.store.read_operation(request_key(deal_id,"cancel")):
                raise DomainError("A cancellation intent is recorded. Preparation is blocked while recovery finishes.")
            if actor_id!=deal["seller_id"]:
                raise DomainError("Only the seller can prepare these orders.",403)
            if deal["status"] not in {"PAID","FULFILLING"}:
                raise DomainError("Prepare goods only after the entire group is paid.")
            for c in deal["commitments"]:
                if c["fulfillment_status"]=="TO_PREPARE":
                    c["fulfillment_status"]="READY_FOR_PICKUP"
            deal["status"]="FULFILLING"
            event(state,actor_id,"Individual orders prepared","Goods separated and labelled for pickup.",deal_id)
            return deepcopy(deal)

    def pickup(self,workspace_id,actor_id,commitment_id,code):
        with self.store.transaction(workspace_id) as (state,db):
            deal=next((d for d in state["deals"] if any(c["id"]==commitment_id for c in d["commitments"])),None)
            if not deal:
                raise DomainError("Order not found.",404)
            c=next(c for c in deal["commitments"] if c["id"]==commitment_id)
            if self.store.read_operation(request_key(deal["id"],"cancel")):
                raise DomainError("A cancellation intent is recorded. Pickup is blocked while recovery finishes.")
            if actor_id not in {deal["seller_id"],c["buyer_id"]}:
                raise DomainError("Only the buyer or seller can confirm this pickup.",403)
            if deal["status"] not in PAID or c["fulfillment_status"] not in {"READY_FOR_PICKUP","COLLECTED"}:
                raise DomainError("This purchase is not ready for pickup.")
            if not secrets.compare_digest(code.upper(),c["pickup_code"] or ""):
                raise DomainError("Pickup code does not match.",422)
            c["fulfillment_status"]="COLLECTED"
            c["collected_at"]=now().isoformat()
            if all(c["fulfillment_status"]=="COLLECTED" for c in deal["commitments"]):
                deal["status"]="COMPLETED"
            event(state,actor_id,"Pickup confirmed",c["buyer_name"]+" collected their allocated goods.",commitment_id)
            return deepcopy(c)
