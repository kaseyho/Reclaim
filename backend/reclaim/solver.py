"""Integer allocation; model outputs never set prices or bypass hard constraints."""
from collections import Counter, defaultdict
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
import re
from time import perf_counter
from ortools.sat.python import cp_model
from .schemas import now

CONDITION = {"unknown":0, "fair":1, "good":2, "like_new":3, "new":4}


def timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value,str) else value


def location_key(value):
    return " ".join(value.casefold().split())


def split_price(total: int, weights: dict[str, int]) -> dict[str,int]:
    """Largest-remainder rounding, stable actor-ID tie-break, exact cents."""
    denominator = sum(weights.values())
    if total < 0 or denominator <= 0 or any(w < 0 for w in weights.values()):
        raise ValueError("Invalid allocation weights")
    result = {k:total*w//denominator for k,w in weights.items()}
    order = sorted(weights, key=lambda k:(-(total*weights[k]%denominator), k))
    for k in order[:total-sum(result.values())]:
        result[k] += 1
    return result


def compatible(unit, need):
    if unit["item_type"] != need["item_type"]:
        return False, "different item"
    confirmed = set(unit.get("confirmed_fields",[]))
    if "item_type" not in confirmed:
        return False, "item type needs seller confirmation"
    minimum = need.get("minimum_condition","good")
    if minimum != "unknown":
        if "condition" not in confirmed or unit.get("condition","unknown") == "unknown":
            return False, "condition needs seller confirmation"
        if CONDITION[unit["condition"]] < CONDITION[minimum]:
            return False, "condition below the buyer's minimum"
    maximum = need.get("max_width_cm")
    if maximum is not None:
        if "width_cm" not in confirmed or unit.get("width_cm") is None:
            return False, "width needs seller confirmation"
        if unit["width_cm"] > maximum:
            return False, f"wider than {maximum} cm"
    if need.get("brand"):
        if "brand" not in confirmed or location_key(unit.get("brand") or "") != location_key(need["brand"]):
            return False, "brand is different or unconfirmed"
    if need.get("sealed") is not None:
        if "sealed" not in confirmed or unit.get("sealed") != need["sealed"]:
            return False, "seal status is different or unconfirmed"
    attributes={a["key"]:a for a in unit.get("attributes",[])}
    for requirement in need.get("attributes",[]):
        key=requirement["key"]
        fact=attributes.get(key)
        if not fact or "attribute:"+key not in confirmed or location_key(fact["value"]) in {"unknown","unverified","?"}:
            return False, key.replace("_"," ")+" needs seller confirmation"
        actual,expected=fact["value"],requirement["value"]
        operator=requirement.get("operator","equals")
        if operator=="equals":
            fits=location_key(actual)==location_key(expected)
        elif operator=="includes":
            fits=location_key(expected) in {location_key(v) for v in re.split(r"[,;|]",actual)}
        else:
            try:
                if re.fullmatch(r"\d{4}-\d{2}-\d{2}",actual) and re.fullmatch(r"\d{4}-\d{2}-\d{2}",expected):
                    left,right=date.fromisoformat(actual),date.fromisoformat(expected)
                else:
                    left,right=Decimal(actual),Decimal(expected)
                    if not left.is_finite() or not right.is_finite():
                        return False, key.replace("_"," ")+" needs a comparable confirmed value"
                fits=left>=right if operator=="at_least" else left<=right
            except (ValueError,InvalidOperation):
                return False, key.replace("_"," ")+" needs a comparable confirmed value"
        if not fits:
            return False, key.replace("_"," ")+" does not meet the confirmed requirement"
    return True, None


def fulfillment_compatible(lot, demand, at=None):
    at = at or now()
    if location_key(lot["location"]) != location_key(demand["location"]):
        return False, "pickup location differs"
    if timestamp(demand["deadline"]) <= at:
        return False, "request deadline passed"
    start=max(timestamp(lot["pickup_start"]),timestamp(demand["pickup_start"]),at)
    end=min(timestamp(lot["pickup_end"]),timestamp(demand["pickup_end"]),timestamp(demand["deadline"]))
    if start >= end:
        return False, "pickup windows do not overlap before the deadline"
    return True, None


def validate_allocation(lot, demands, allocations, *, complete=True):
    """Separate publication check, independently recomputes quantities/prices."""
    units={u["id"]:u for u in lot["units"]}
    requests={d["id"]:d for d in demands}
    used=Counter()
    buyers=set()
    weights={}
    for allocation in allocations:
        demand=requests[allocation["demand_id"]]
        if demand["buyer_id"] in buyers:
            raise ValueError("A buyer is allocated more than once")
        buyers.add(demand["buyer_id"])
        if not fulfillment_compatible(lot,demand)[0]:
            raise ValueError("Fulfillment constraint violated")
        expected={n["item_type"]:n for n in demand["needs"]}
        received=Counter()
        weight=0
        for assignment in allocation["items"]:
            unit=units[assignment["unit_id"]]
            quantity=assignment["quantity"]
            if not isinstance(quantity,int) or quantity <= 0:
                raise ValueError("Invalid quantity")
            need=expected.get(unit["item_type"])
            if need is None or not compatible(unit,need)[0]:
                raise ValueError("Hard attribute constraint violated")
            used[unit["id"]]+=quantity
            received[unit["item_type"]]+=quantity
            weight+=quantity*unit["reference_weight"]
        if received != Counter({k:n["quantity"] for k,n in expected.items()}):
            raise ValueError("Buyer request is incomplete")
        if allocation["price_minor"]<=0:
            raise ValueError("Each buyer share must be payable")
        if allocation["price_minor"] > demand["budget_minor"]:
            raise ValueError("Buyer budget exceeded")
        weights[allocation["buyer_id"]]=weight
    if any(used[u["id"]]>u["quantity"] for u in lot["units"]):
        raise ValueError("Inventory exceeded")
    if complete and any(used[u["id"]] != u["quantity"] for u in lot["units"]):
        raise ValueError("Whole lot must be allocated")
    missing_weight=sum((u["quantity"]-used[u["id"]])*u["reference_weight"] for u in lot["units"])
    if missing_weight:
        weights["~unallocated"]=missing_weight
    shares=split_price(lot["goods_price_minor"]+lot["preparation_minor"],weights)
    if any(a["price_minor"]!=shares[a["buyer_id"]] for a in allocations):
        raise ValueError("Price allocation rule violated")
    return True


def _solve(lot, demands, partial=False, seconds=1.5):
    model=cp_model.CpModel()
    units=lot["units"]
    total=lot["goods_price_minor"]+lot["preparation_minor"]
    total_weight=sum(u["quantity"]*u["reference_weight"] for u in units)
    selected={d["id"]:model.new_bool_var(d["id"]) for d in demands}
    assignments={}
    for demand in demands:
        d_id=demand["id"]
        if not fulfillment_compatible(lot,demand)[0]:
            model.add(selected[d_id]==0)
        requested={n["item_type"]:n for n in demand["needs"]}
        for unit in units:
            need=requested.get(unit["item_type"])
            allowed=need is not None and compatible(unit,need)[0]
            var=model.new_int_var(0, min(unit["quantity"],need["quantity"]) if allowed else 0, f'{d_id}:{unit["id"]}')
            assignments[d_id,unit["id"]]=var
            model.add(var<=unit["quantity"]*selected[d_id])
        for need in demand["needs"]:
            model.add(sum(assignments[d_id,u["id"]] for u in units if u["item_type"]==need["item_type"])==need["quantity"]*selected[d_id])
        weight=sum(assignments[d_id,u["id"]]*u["reference_weight"] for u in units)
        numerator=model.new_int_var(0,total*total_weight,f"numerator:{d_id}")
        model.add(numerator==total*weight)
        floor_price=model.new_int_var(0,total,f"price:{d_id}")
        model.add_division_equality(floor_price,numerator,total_weight)
        model.add(floor_price<=demand["budget_minor"])
    by_buyer=defaultdict(list)
    for d in demands:
        by_buyer[d["buyer_id"]].append(selected[d["id"]])
    for values in by_buyer.values():
        model.add(sum(values)<=1)
    slack=[]
    for unit in units:
        used=sum(assignments[d["id"],unit["id"]] for d in demands)
        if partial:
            missing=model.new_int_var(0,unit["quantity"],"missing:"+unit["id"])
            model.add(used+missing==unit["quantity"])
            slack.append(missing)
        else:
            model.add(used==unit["quantity"])
    # Complete requests dominate preference fit. Partial diagnostics prioritize coverage.
    preferences=sum(assignments[d["id"],u["id"]]*CONDITION[u.get("condition","unknown")] for d in demands for u in units)
    model.maximize(sum(selected.values())*10000+preferences-(sum(slack)*1000000 if partial else 0))
    solver=cp_model.CpSolver()
    solver.parameters.max_time_in_seconds=seconds
    solver.parameters.num_search_workers=1
    solver.parameters.random_seed=0
    start=perf_counter()
    # Integer floors are a relaxation; independent cent rounding may exclude a solution.
    for _ in range(64):
        solver.parameters.max_time_in_seconds=max(.001,seconds-(perf_counter()-start))
        status=solver.solve(model)
        name=solver.status_name(status)
        if status not in (cp_model.OPTIMAL,cp_model.FEASIBLE):
            return {"status":name,"allocations":[],"missing":units}
        allocations=[]
        weights={}
        used=Counter()
        for demand in demands:
            if not solver.value(selected[demand["id"]]):
                continue
            items=[]
            weight=0
            for unit in units:
                quantity=solver.value(assignments[demand["id"],unit["id"]])
                if quantity:
                    items.append({"unit_id":unit["id"],"name":unit["name"],"quantity":quantity,"item_type":unit["item_type"]})
                    used[unit["id"]]+=quantity
                    weight+=quantity*unit["reference_weight"]
            weights[demand["buyer_id"]]=weight
            allocations.append({"demand_id":demand["id"],"buyer_id":demand["buyer_id"],"items":items,"weight":weight})
        missing=[{**u,"quantity":u["quantity"]-used[u["id"]]} for u in units if used[u["id"]]<u["quantity"]]
        if missing:
            weights["~unallocated"]=sum(u["quantity"]*u["reference_weight"] for u in missing)
        if not weights:
            return {"status":name,"allocations":[],"missing":missing}
        prices=split_price(total,weights)
        for a in allocations:
            a["price_minor"]=prices[a["buyer_id"]]
        try:
            validate_allocation(lot,demands,allocations,complete=not partial)
        except ValueError as error:
            if str(error) not in {"Buyer budget exceeded","Each buyer share must be payable","Fulfillment constraint violated"}:
                raise
            variables=list(selected.values())+list(assignments.values())
            model.add_forbidden_assignments(variables,[tuple(solver.value(v) for v in variables)])
            if perf_counter()-start >= seconds:
                return {"status":"UNKNOWN","allocations":[],"missing":units}
            continue
        for unit in missing:
            unit["price_minor"]=total*unit["quantity"]*unit["reference_weight"]//total_weight
        return {"status":name,"allocations":allocations,"missing":missing}
    return {"status":"UNKNOWN","allocations":[],"missing":units}


def match_lot(lot, demands):
    started=perf_counter()
    if not lot.get("confirmed") or not lot.get("divisible"):
        return {"lot_id":lot["id"],"status":"NEEDS_CONFIRMATION","allocations":[],"missing":lot["units"],"blockers":["Seller must confirm inventory and separate fulfillment."],"elapsed_ms":0}
    if any(not {"quantity","reference_weight"}.issubset(u.get("confirmed_fields",[])) for u in lot["units"]):
        return {"lot_id":lot["id"],"status":"NEEDS_CONFIRMATION","allocations":[],"missing":lot["units"],"blockers":["Seller must confirm quantities and reference weights before prices can be proposed."],"elapsed_ms":0}
    if lot.get("status") != "AVAILABLE":
        return {"lot_id":lot["id"],"status":"UNAVAILABLE","allocations":[],"missing":[],"blockers":["This inventory is reserved or sold."],"elapsed_ms":0}
    eligible=[d for d in demands if d.get("confirmed") and d.get("status")=="OPEN"]
    complete=_solve(lot,eligible)
    if complete["status"] in {"OPTIMAL","FEASIBLE"}:
        result=complete
        result["complete"]=True
    else:
        result=_solve(lot,eligible,partial=True)
        result["complete"]=False
        result["complete_solve_status"]=complete["status"]
    blockers=[]
    for demand in eligible:
        ok, reason=fulfillment_compatible(lot,demand)
        if not ok:
            blockers.append(f'{demand["buyer_name"]}: {reason}.')
            continue
        for need in demand["needs"]:
            candidates=[u for u in lot["units"] if u["item_type"]==need["item_type"]]
            reasons=[compatible(u,need)[1] for u in candidates if not compatible(u,need)[0]]
            if candidates and len(reasons)==len(candidates):
                blockers.append(f'{demand["buyer_name"]}: {need["item_type"]} — {reasons[0]}.')
        if not any(a["demand_id"]==demand["id"] for a in result["allocations"]):
            blockers.append(f'{demand["buyer_name"]}: no complete allocation within the confirmed budget and inventory constraints.')
    result.update(lot_id=lot["id"],blockers=blockers,elapsed_ms=round((perf_counter()-started)*1000,2),price_rule="Seller-confirmed weights; largest-remainder cent rounding")
    return result
