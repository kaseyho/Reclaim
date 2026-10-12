from datetime import timedelta
from zoneinfo import ZoneInfo
from .schemas import now


def seed(scenario="moving"):
    actors=[{"id":"seller","name":"Maya","role":"seller","initials":"M"},{"id":"alice","name":"Alice","role":"buyer","initials":"A"},{"id":"ben","name":"Ben","role":"buyer","initials":"B"},{"id":"chen","name":"Chen","role":"buyer","initials":"C"}]
    state={"actors":actors,"lots":[],"demands":[],"deals":[],"events":[],"operations":{},"match_runs":[],"failures":[],"ai_runs":[],"scenario":scenario}
    if scenario=="empty":
        return state
    local=now().astimezone(ZoneInfo("Asia/Singapore"))
    start=(local+timedelta(days=(5-local.weekday())%7 or 7)).replace(hour=10,minute=0,second=0,microsecond=0)
    end=start+timedelta(hours=8)
    def unit(id,name,item_type,weight,width=None,quantity=1,sealed=None):
        attributes=[{"key":"connector","value":"usb","evidence":"Confirmed illustrative fixture"}] if item_type=="microphone" else ([{"key":"diagonal_inches","value":"24","evidence":"Confirmed illustrative fixture"}] if item_type=="monitor" else ([{"key":"paper_size","value":"a5","evidence":"Confirmed illustrative fixture"}] if item_type=="notebook" else []))
        return {"id":id,"name":name,"item_type":item_type,"quantity":quantity,"reference_weight":weight,"condition":"good" if sealed is None else "new","width_cm":width,"brand":None,"sealed":sealed,"confirmed_fields":["item_type","quantity","condition","reference_weight"]+(["width_cm"] if width else [])+(["sealed"] if sealed is not None else [])+["attribute:"+a["key"] for a in attributes],"attributes":attributes,"evidence":"Illustrative fixture, confirmed by the demo seller. Not a real listing."}
    if scenario=="moving":
        units=[unit("desk","Oak writing desk","desk",75,95),unit("lamp","Adjustable desk lamp","lamp",15),unit("chair","Sage desk chair","chair",60),unit("monitor","24-inch monitor","monitor",100)]
        title="A room, ready for its next chapter."
        category="furniture"
        goods,prep=18000,2000
        description="Moving out: a 95 cm oak desk, desk lamp, sage chair, and 24-inch monitor. All in good condition. I can separate and label each purchase."
        requests=[("alice","A desk under 100 cm wide and a lamp, under $90.",[{"item_type":"desk","max_width_cm":100},{"item_type":"lamp"}],9000),("ben","A comfortable desk chair under $60.",[{"item_type":"chair"}],6000)]
    elif scenario=="creator":
        units=[unit("mic","USB microphone","microphone",90),unit("tripod","Camera tripod","tripod",50),unit("light","LED panel light","light",60)]
        title="The kit behind your next good idea."
        category="creator"
        goods,prep=14000,1000
        description="Creator kit: one USB microphone, a camera tripod, and an LED panel light. All good condition, independently usable and ready for separate pickup."
        requests=[("alice","A microphone for recording, under $80.",[{"item_type":"microphone"}],8000),("ben","A tripod for my camera, under $50.",[{"item_type":"tripod"}],5000)]
    else:
        units=[unit("notebook","Sealed A5 notebooks","notebook",10,quantity=12,sealed=True)]
        title="One case. Three new beginnings."
        category="bulk"
        goods,prep=5400,600
        description="12 individually sealed A5 notebooks, sold as one wholesale case. New, sealed, and divisible into any quantity."
        requests=[("alice","4 sealed notebooks under $25.",[{"item_type":"notebook","quantity":4,"sealed":True}],2500),("ben","4 sealed notebooks under $25.",[{"item_type":"notebook","quantity":4,"sealed":True}],2500)]
    lot={"id":"lot_"+scenario,"version":1,"seller_id":"seller","seller_name":"Maya","title":title,"category":category,"description":description,"goods_price_minor":goods,"preparation_minor":prep,"currency":"USD","location":"Campus pickup","pickup_start":start.isoformat(),"pickup_end":end.isoformat(),"units":units,"image":None,"confirmed":True,"divisible":True,"status":"AVAILABLE","created_at":now().isoformat()}
    state["lots"].append(lot)
    for actor,text,needs,budget in requests:
        normalized=[{"quantity":1,"max_width_cm":None,"minimum_condition":"good","brand":None,"sealed":None,**n} for n in needs]
        state["demands"].append({"id":"demand_"+actor,"version":1,"buyer_id":actor,"buyer_name":next(a["name"] for a in actors if a["id"]==actor),"text":text,"needs":normalized,"budget_minor":budget,"location":lot["location"],"pickup_start":start.isoformat(),"pickup_end":end.isoformat(),"deadline":end.isoformat(),"allow_substitutions":False,"confirmed":True,"status":"OPEN","created_at":now().isoformat()})
    state["events"].append({"id":"seed","at":now().isoformat(),"actor":"system","action":"Walkthrough started","detail":"Illustrative inventory and two confirmed requests. Add the missing buyer to complete the group."})
    return state
