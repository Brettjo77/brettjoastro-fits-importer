"""Derive stress-dataset.json from ../../dataset.json (the sample) to the ENGINE's real shape
(astro-import.py observatory_from): 87 targets / 147 datasets, names to 48 chars, a target with no
type/constellation, a scope silent for >365 nights, a night with four scopes out (one scope on two
objects), two mosaics, a project done on one scope and capturing on another, kept-open / marked-
complete by hand, true test snaps, a real short bright-cluster project, unknown exposure on an Askar,
real engine warning strings, Mac-only snapshotRows, inputs as an object."""
import json, random, datetime as dt, os
random.seed(42)
HERE=os.path.dirname(os.path.abspath(__file__))
D0=json.load(open(os.path.join(HERE,"..","..","dataset.json")))
TODAY=dt.date(2026,10,16); QUIET=14
EXP={"Askar FRA400":300,"Askar 107PHQ":180,"Seestar S30 Pro":10,"Seestar S50":10,"Seestar S50 Pro":20,"Starfront S50 Pro":30}
FILT={"Askar FRA400":["L-eXtreme","UV/IR"],"Askar 107PHQ":["Ha","OIII","SII","L"],"Seestar S30 Pro":["LP"],"Seestar S50":["LP"],"Seestar S50 Pro":["LP"],"Starfront S50 Pro":["LP"]}
ROOT={"Askar FRA400":"ZWO Askar Scopes","Askar 107PHQ":"ZWO Askar Scopes","Seestar S30 Pro":"S30P","Seestar S50":"S50","Seestar S50 Pro":"S50P","Starfront S50 Pro":"SFS50P"}
SID={s["camera"]:s["id"] for s in D0["scopes"]}
COL={s["camera"]:s["colour"] for s in D0["scopes"]}
SEESTAR=lambda cam: cam not in("Askar FRA400","Askar 107PHQ")
iso=lambda d:d.isoformat()
def fmtd(s): d=dt.date.fromisoformat(s); return f"{d.day} {d.strftime('%b %Y')}"

# ---- 1. seed datasets from the sample: one record per (target, scope) with its sessions ----
DS=[]   # each: dict(target=tmeta, cam, nights={iso:{frames,secs,filters,exps,cal}}, masters, finals, shared, force, mosaic)
TM={}
for t in D0["targets"]:
    TM[t["name"]]={"id":t["id"],"name":t["name"],"codes":t["codes"],"type":t["type"],"constellation":t["constellation"],"ra":t["ra"],"dec":t["dec"]}
    for p in t["programmes"]:
        ss=[s for s in D0["sessions"] if s["target"]==t["name"] and s["camera"]==p["camera"]]
        shift=dt.timedelta(days=400) if p["camera"]=="Seestar S50" else dt.timedelta(0)   # the S50: silent for >365 nights
        nights={}
        for s in ss:
            n=iso(dt.date.fromisoformat(s["night"])-shift)
            unk="unrecorded" in s["filters"]
            nights[n]={"frames":s["frames"],"secs":0 if unk else round(s["hours"]*3600),"filters":{} if unk else dict(s["filters"]),
                       "exps":{} if unk else dict(s["exps"]),"cal":None if SEESTAR(p["camera"]) else dict(s["cal"])}
        DS.append({"t":t["name"],"cam":p["camera"],"nights":nights,"masters":p["masters"],"finals":p["processedFinals"],
                   "shared":"other Askar" in (p["evidence"] or ""),"force":None,"mosaic":p["mosaic"],"cstate":"auto"})
# ---- 2. new targets ----
def mk(name,codes,typ,con,ra,dec,progs,mosaic=False):
    TM[name]={"id":(codes[0] if codes else name[:12]).replace(" ",""),"name":name,"codes":codes,"type":typ,"constellation":con,"ra":ra,"dec":dec}
    for cam,spec in progs:
        d={"t":name,"cam":cam,"nights":{},"masters":0,"finals":0,"shared":False,"force":None,"mosaic":mosaic,"cstate":"auto"}
        d.update(spec); DS.append(d)
def nights_spec(cam,nightlist,frames_per,exp=None,cal=None,unknown=False):
    exp=exp or EXP[cam]; out={}
    for n,f in zip(nightlist,frames_per):
        filt=random.choice(FILT[cam])
        c=None if SEESTAR(cam) else (cal if cal is not None else {"darks":random.choice([0,20,30]),"flats":random.choice([0,25]),"biases":0})
        out[n]={"frames":f,"secs":0 if unknown else f*exp,"filters":{} if unknown else {filt:f},"exps":{} if unknown else {str(exp):f},"cal":c}
    return {"nights":out}
def back(days): return iso(TODAY-dt.timedelta(days=days))
def spread(n,lo,hi):
    s=set()
    while len(s)<n: s.add(back(random.randint(lo,hi)))
    return sorted(s)
LAST=iso(TODAY)
# specials
mk("Open cluster in the Tadpoles (IC 410) (NGC 1893)",["IC 410","NGC 1893"],"Emission nebula","Auriga",5.37,33.52,
   [("Askar FRA400",nights_spec("Askar FRA400",spread(3,30,90),[30,28,34])),
    ("Askar 107PHQ",nights_spec("Askar 107PHQ",spread(2,3,20)+[LAST],[40,38,22]))])
mk("Sh2-115 and Sh2-116 region near Deneb (Abell 71)",[],None,None,None,None,
   [("Askar FRA400",nights_spec("Askar FRA400",spread(2,25,60),[24,26]))])
mk("Cygnus Loop mosaic: Veil East, West, Pickering's",["NGC 6992","NGC 6960","NGC 6979"],"Supernova remnant","Cygnus",20.78,30.7,
   [("Askar 107PHQ",dict(nights_spec("Askar 107PHQ",spread(6,120,300),[60,58,62,60,61,59]),masters=1)),
    ("Seestar S30 Pro",nights_spec("Seestar S30 Pro",spread(2,2,10),[540,612]))],mosaic=True)
mk("Running Man Nebula (NGC 1977)",["NGC 1977"],"Reflection nebula","Orion",5.59,-4.87,
   [("Askar FRA400",dict(nights_spec("Askar FRA400",spread(3,200,320),[36,40,38]),finals=1)),
    ("Seestar S30 Pro",nights_spec("Seestar S30 Pro",[back(4),LAST],[480,576]))])
mk("Double Cluster (NGC 869) (NGC 884)",["NGC 869","NGC 884"],"Open cluster","Perseus",2.33,57.13,
   [("Askar FRA400",nights_spec("Askar FRA400",[back(41)],[84],exp=30,cal={"darks":30,"flats":25,"biases":0}))])
mk("Pleiades focus test (M 45)",["M 45"],"Open cluster","Taurus",3.79,24.12,[("Askar FRA400",nights_spec("Askar FRA400",[back(280)],[1]))])
mk("Polaris alignment check",[],"Star",None,2.53,89.26,[("Seestar S50 Pro",nights_spec("Seestar S50 Pro",[back(330)],[4]))])
mk("Comet C/2025 A6 (Lemmon)",["C/2025 A6"],"Comet",None,None,None,[("Seestar S30 Pro",nights_spec("Seestar S30 Pro",[back(7)],[55]))])
mk("Flaming Star and Tadpoles widefield (IC 405)",["IC 405","IC 410"],"Emission nebula","Auriga",5.3,34.0,
   [("Askar FRA400",dict(nights_spec("Askar FRA400",spread(4,40,120),[30,32,31,29]),cstate="open"))])
mk("Witch Head Nebula (IC 2118)",["IC 2118"],"Reflection nebula","Eridanus",5.1,-7.2,
   [("Askar FRA400",dict(nights_spec("Askar FRA400",spread(3,5,30),[28,30,27]),cstate="complete"))])
mk("Barnard's Loop (Sh2-276)",["Sh2-276"],"Emission nebula","Orion",5.6,-1.0,
   [("Askar 107PHQ",nights_spec("Askar 107PHQ",spread(2,60,100),[60,60],unknown=True,cal={"darks":30,"flats":0,"biases":0}))])
mk("Helix Nebula (NGC 7293)",["NGC 7293"],"Planetary nebula","Aquarius",22.49,-20.84,
   [("Starfront S50 Pro",nights_spec("Starfront S50 Pro",[back(9),back(3),LAST],[120,96,132]))])
mk("Lobster Claw and Bubble widefield (Sh2-157)",["Sh2-157","NGC 7635"],"Emission nebula","Cassiopeia",23.27,60.3,
   [("Askar FRA400",dict(nights_spec("Askar FRA400",spread(5,150,400),[30,30,30,31,29]),masters=2,finals=1)),
    ("Askar 107PHQ",dict(nights_spec("Askar 107PHQ",spread(3,20,60),[40,41,39]),masters=1)),
    ("Seestar S50 Pro",nights_spec("Seestar S50 Pro",spread(2,400,500),[300,288]))])
# generic fill to 87 targets / 147 datasets
NAMES=[("Cat's Eye Nebula (NGC 6543)","Planetary nebula","Draco"),("Owl Nebula (M 97)","Planetary nebula","Ursa Major"),("Sunflower Galaxy (M 63)","Galaxy","Canes Venatici"),
("Black Eye Galaxy (M 64)","Galaxy","Coma Berenices"),("Sombrero Galaxy (M 104)","Galaxy","Virgo"),("Cigar Galaxy (M 82)","Galaxy","Ursa Major"),("Needle Galaxy (NGC 4565)","Galaxy","Coma Berenices"),
("Thor's Helmet (NGC 2359)","Emission nebula","Canis Major"),("Seagull Nebula (IC 2177)","Emission nebula","Monoceros"),("Cone Nebula (NGC 2264)","Emission nebula","Monoceros"),
("Medusa Nebula (Abell 21)","Planetary nebula","Gemini"),("Spaghetti Nebula (Simeis 147)","Supernova remnant","Taurus"),("California Nebula (NGC 1499)","Emission nebula","Perseus"),
("Witch's Broom (NGC 6960)","Supernova remnant","Cygnus"),("Propeller Nebula (Simeis 57)","Emission nebula","Cygnus"),("Lion Nebula (Sh2-132)","Emission nebula","Cepheus"),
("Fish Head Nebula (IC 1795)","Emission nebula","Cassiopeia"),("Ghost of Cassiopeia (IC 63)","Emission nebula","Cassiopeia"),("Pacman and Ghost widefield (NGC 281) (IC 63)","Nebula","Cassiopeia"),
("Shark Nebula (LDN 1235)","Dark nebula","Cepheus"),("Wolf's Cave (vdB 152)","Reflection nebula","Cepheus"),("Dragon's Egg (Sh2-168)","Emission nebula","Cassiopeia"),
("Ced 214 and NGC 7822 complex (Sh2-171)","Emission nebula","Cepheus"),("Swan Nebula (M 17)","Emission nebula","Sagittarius"),("Eagle and Swan widefield (M 16) (M 17)","Nebula","Serpens"),
("Lagoon and Trifid widefield (M 8) (M 20)","Nebula","Sagittarius"),("Wild Duck Cluster (M 11)","Open cluster","Scutum"),("Beehive Cluster (M 44)","Open cluster","Cancer"),
("Great Globular (M 13) and NGC 6207 widefield","Globular cluster","Hercules"),("Pinwheel and Pin Galaxy pair (M 101) (NGC 5474)","Galaxy","Ursa Major"),("Bode's and Cigar widefield (M 81) (M 82)","Galaxy","Ursa Major"),
("Coma Cluster (Abell 1656)","Galaxy group","Coma Berenices"),("Stephan's Quintet (NGC 7320)","Galaxy group","Pegasus"),("Deer Lick Group (NGC 7331)","Galaxy group","Pegasus"),
("Little Dumbbell (M 76)","Planetary nebula","Perseus"),("Blue Snowball (NGC 7662)","Planetary nebula","Andromeda"),("Crab Nebula (M 1)","Supernova remnant","Taurus"),
("Heart and Soul widefield (IC 1805) (IC 1848)","Nebula",None),("Rho Ophiuchi cloud complex (IC 4604)","Reflection nebula","Ophiuchus"),("Pelican and North America widefield (IC 5070)",None,"Cygnus"),
("Andromeda and M 110 field (M 31) (M 110) (M 32)","Galaxy","Andromeda"),("Bubble and M 52 widefield (NGC 7635) (M 52)","Emission nebula","Cassiopeia"),("Jellyfish and Monkey Head widefield (IC 443)","Nebula","Gemini")]
PLAN=[1]*7+[2]*11+[3]*10+[4]*5
assert len(NAMES)>=len(PLAN), (len(NAMES), len(PLAN))
random.shuffle(PLAN)
i=0
for n_sc in PLAN:
    name,typ,con=NAMES[i]; i+=1
    cams=random.sample(list(EXP),n_sc)
    progs=[]
    for cam in cams:
        kind=random.choice(["cap","ready","ready","prog","done"])
        if cam=="Seestar S50": kind=random.choice(["ready","done"])
        nn=random.randint(1,6)
        if kind=="cap": nl=spread(nn,0,13)
        elif kind=="ready": nl=spread(nn,16,200)
        else: nl=spread(nn,60,720)
        if cam=="Seestar S50": nl=[iso(dt.date.fromisoformat(x)-dt.timedelta(days=380)) for x in nl]
        per=[random.randint(20,60) if not SEESTAR(cam) else (random.randint(40,120) if cam=="Seestar S50" else random.randint(100,700)) for _ in nl]
        spec=nights_spec(cam,nl,per)
        if kind=="prog": spec["masters"]=1
        if kind=="done": spec["finals"]=1; spec["masters"]=random.choice([0,1])
        progs.append((cam,spec))
    mk(name,[c for c in [name[name.find("(")+1:name.find(")")]] if "(" in name],typ,con,round(random.uniform(0,24),2),round(random.uniform(-30,80),1),progs)
# ---- 3. rebuild like the engine ----
sessions=[]; targets={}; scopes={}
tot_bytes=tot_frames=0; tot_secs=0.0; nights_all=set()
for d in DS:
    t=TM[d["t"]]; cam=d["cam"]; nights=d["nights"]
    frames=sum(n["frames"] for n in nights.values()); secs=sum(n["secs"] for n in nights.values())
    nbytes=sum(n["frames"]*(62_000_000 if not SEESTAR(cam) else 4_000_000) for n in nights.values())
    hours=round(secs/3600,2); nl=sorted(nights); last=nl[-1]; days_since=(TODAY-dt.date.fromisoformat(last)).days
    cstate=d["cstate"]
    if d["finals"]: status="done"
    elif d["masters"]: status="in_progress"
    elif cstate=="open": status="capturing"
    elif cstate=="complete": status="ready_to_process"
    else: status="capturing" if days_since<=QUIET else "ready_to_process"
    ready_on=iso(dt.date.fromisoformat(last)+dt.timedelta(days=QUIET+1)) if status=="capturing" and cstate!="open" else None
    sc=scopes.setdefault(cam,{"camera":cam,"id":SID[cam],"frames":0,"hours":0.0,"nights":set(),"bytes":0,"first":None,"last":None,"colour":COL[cam]})
    sc["frames"]+=frames; sc["hours"]+=secs/3600; sc["bytes"]+=nbytes; sc["nights"].update(nl); nights_all.update(nl)
    sc["first"]=min(x for x in (sc["first"],nl[0]) if x); sc["last"]=max(x for x in (sc["last"],last) if x)
    tot_bytes+=nbytes; tot_frames+=frames; tot_secs+=secs
    filters,exps={},{}
    for nt in nl:
        n=nights[nt]; nf=dict(n["filters"]); rest=n["frames"]-sum(nf.values())
        if rest>0: nf["unrecorded"]=rest
        for k,v in nf.items(): filters[k]=filters.get(k,0)+v
        for k,v in n["exps"].items(): exps[k]=exps.get(k,0)+v
        sessions.append({"target":t["name"],"camera":cam,"night":nt,"frames":n["frames"],"hours":round(n["secs"]/3600,3),"filters":nf,"exps":dict(n["exps"]),
                         "askar":{},"stackOnly":False,"cal":None if SEESTAR(cam) else {k:(n["cal"] or {}).get(k,0) for k in("darks","flats","biases")}})
    if SEESTAR(cam): calib={"applies":False}
    else:
        cal={"biases":0,"darks":0,"flats":0,"shipped":0}; with_cal=0
        for n in nights.values():
            c=n["cal"] or {}
            for k in cal: cal[k]+=c.get(k,0)
            if c.get("darks") or c.get("flats"): with_cal+=1
        calib={"applies":True,**cal,"nights_with":with_cal,"nights":len(nl),"missing":[k for k in("darks","flats") if not cal[k]]}
    base=t["name"].split(" (")[0]
    if status=="done": evidence=f"finished picture {t['id']}_{base.replace(' ','-')}__2026-09_{SID[cam]}.jpg"; action=""
    elif status=="in_progress": evidence=f"master saved: {base}_master_{SID[cam]}.xisf"; action="Finish it: process to a final"
    elif status=="ready_to_process":
        evidence="marked complete by hand; nothing started" if cstate=="complete" else f"no new frames since {fmtd(last)} ({days_since} nights); nothing started"; action="Process it"
    else:
        evidence="kept open by hand (capture-state.json)" if cstate=="open" else f"last session {fmtd(last)}; ready to process from {fmtd(ready_on)}"; action="Keep capturing"
    notes=[]
    if d["shared"]: notes.append("shared Askar folder: the master may be the other Askar's")
    if calib.get("applies") and calib.get("missing") and status in("ready_to_process","capturing"): notes.append("no "+" or ".join(calib["missing"])+" linked to its lights")
    if notes: evidence+="; "+", ".join(notes)
    folder=t["name"]+(" (mosaic)" if d["mosaic"] else ""); rel=f"{ROOT[cam]}/{folder}"
    prog={"camera":cam,"folder":folder,"path":"E:\\"+rel.replace("/","\\"),"rel":rel,"lights":frames,"autostacks":0,"autostackFrames":0,
          "processedFiles":d["masters"]+d["finals"],"processedFinals":d["finals"],"masters":d["masters"],"working":0,"thumbs":0,"other":0,
          "mosaic":d["mosaic"],"collectFiles":0,"collected":False,"hours":hours,"bytes":nbytes,"sizeAll":nbytes,"nights":len(nl),
          "firstNight":nl[0],"lastNight":last,"filters":filters,"exposures":exps,"panels":(["p1","p2","p3"] if d["mosaic"] else []),"gains":{},"askar":{},
          "where":["on the archive"],"status":status,"readyOn":ready_on,"evidence":evidence,"action":action,"calibration":calib}
    OBS_STATE={"capturing":"captured","ready_to_process":"stacked","in_progress":"processing","done":"complete"}
    card={"target":t["name"],"label":folder,"camera":cam,"state":OBS_STATE[status],"hours":hours,"nights":len(nl),"lights":frames,"lastNight":last,"readyOn":ready_on,
          "evidence":evidence,"action":action,"source":"worked out by the importer","badges":["on the archive"],"rel":rel}
    tg=targets.setdefault(t["name"],{"id":t["id"],"name":t["name"],"codes":t["codes"],"type":t["type"],"constellation":t["constellation"],"ra":t["ra"],"dec":t["dec"],
        "mosaic":False,"programmes":[],"cameras":[],"lights":0,"hours":0.0,"nights":set(),"sessions":0,"firstNight":None,"lastNight":None,"state":None,"pendingProgrammes":0,"statusCards":[],"_rank":99})
    tg["programmes"].append(prog); tg["statusCards"].append(card)
    if cam not in tg["cameras"]: tg["cameras"].append(cam)
    tg["mosaic"]=tg["mosaic"] or d["mosaic"]; tg["lights"]+=frames; tg["hours"]+=secs/3600; tg["nights"].update(nl); tg["sessions"]+=len(nl)
    tg["firstNight"]=min(x for x in (tg["firstNight"],nl[0]) if x); tg["lastNight"]=max(x for x in (tg["lastNight"],last) if x)
    if status!="done": tg["pendingProgrammes"]+=1
    rank=["capturing","ready_to_process","in_progress","done"].index(status)
    if rank<tg["_rank"]: tg["_rank"],tg["state"]=rank,OBS_STATE[status]
out_targets=[]
for tg in sorted(targets.values(),key=lambda x:x["name"].lower()):
    tg["nights"]=len(tg["nights"]); tg["hours"]=round(tg["hours"],2); tg.pop("_rank"); out_targets.append(tg)
out_scopes=[]
for sc in sorted(scopes.values(),key=lambda x:x["camera"]):
    sc["nights"]=len(sc["nights"]); sc["hours"]=round(sc["hours"],1); out_scopes.append(sc)
dropped={"unknown_names":184,"no_scope":5,"no_night":7,"unreadable":3,"duplicates":1105}
n_dropped=sum(dropped.values()); rows=tot_frames+n_dropped; mac_rows=11206
warnings=["2 target name(s) the contract doesn't know (run --targets-draft to list them); their frames are not counted",
          "5 frame(s) have no scope recorded (older ASIAir rows) and were not counted",
          "7 frame(s) carry no night and were not counted",
          "3 ledger row(s) could not be read and were not counted",
          "the Mac's record on the archive is 3 day(s) old (its ledger snapshot of 13 Oct 2026)"]
read_from=["this PC's ledger","the Mac's record (its ledger snapshot of 13 Oct 2026)","the archive's inventory of 16 Oct 2026","Final Astro Images"]
health=[{"severity":"info","title":"Built from the importer's own record, nothing typed in",
         "detail":f"Worked out on this PC from "+", ".join(read_from)+f": {rows:,} ledger rows read. The one human-set fact is capture-state.json (open / complete)."}]
health+=[{"severity":"warn","title":"Warning from the project layer","detail":w} for w in warnings]
why=[f"{dropped['unknown_names']:,} names the contract doesn't know",f"{dropped['no_scope']:,} no scope",f"{dropped['no_night']:,} no night",f"{dropped['unreadable']:,} unreadable rows",f"{dropped['duplicates']:,} copies already counted"]
recon=[{"check":"Ledger rows read, light frames counted","expected":rows,"computed":tot_frames,"note":f"{n_dropped:,} not counted: "+", ".join(why),"ok":True},
       {"check":"Datasets on this page, against projects.json","expected":len(DS),"computed":sum(len(x["programmes"]) for x in out_targets),"note":"one dataset is one object on one scope","ok":True},
       {"check":"Hours by scope, against the total","expected":round(tot_secs/3600,1),"computed":round(sum(x["hours"] for x in out_scopes),1),"note":"rounded per scope","ok":True}]
when="16 Oct 2026, 09:12"
D={"schema":"observatory/1","generatedAt":when,"generatedAtIso":"2026-10-16T09:12:00+00:00","machine":"PC · E:\\ Astro Data Archive · live from the importer",
   "sourceNote":f"Worked out on this PC on {when} from "+", ".join(read_from)+f" ({rows:,} ledger rows). The statuses are the project layer's, the same as the To process list.",
   "provenance":D0["provenance"],"quietPeriodDays":QUIET,"asOfNight":iso(TODAY),
   "inputs":{"ledger":True,"ledgerCorrupt":False,"snapshot":{"machine":"Mac","at":"2026-10-13T06:40:11+00:00","ageHours":74.5,"rows":mac_rows},
             "inventory":"inventory-E-20261016T033012Z.jsonl","inventoryAt":"2026-10-16T03:30:12+00:00","finals":True,"asOfNight":iso(TODAY),"quietPeriodDays":QUIET,"machine":"PC"},
   "snapshotRows":mac_rows,"scopes":out_scopes,"askarSplit":{},"targets":out_targets,"sessions":sessions,"events":[],"calibration":{},"shelves":{},"quarantine":{},
   "junk":{"files":0,"bytes":0},"totals":{"files":tot_frames,"bytes":tot_bytes,"lights":tot_frames,"hours":round(tot_secs/3600,1),"targets":len(out_targets),"nights":len(nights_all),"sessions":len(sessions)},
   "colourMeaning":{},"parseFailures":{},"ledgerMeta":{"rows":rows},"askarRigs":{},"rigAttribution":{},"health":health,"delta":None,"reconciliation":recon,"warnings":warnings}
json.dump(D,open(os.path.join(HERE,"stress-dataset.json"),"w"),indent=0)
print("targets",len(out_targets),"datasets",len(DS),"sessions",len(sessions),"hours",D["totals"]["hours"],"nights",D["totals"]["nights"])
print("longest name",max(len(t["name"]) for t in out_targets), [t["name"] for t in out_targets if len(t["name"])>=45])
from collections import Counter
byn={}
for s in sessions: byn.setdefault(s["night"],[]).append((s["camera"],s["target"]))
print("last night", sorted(byn)[-1], byn[sorted(byn)[-1]])
print("scopes", [(s["camera"],s["hours"],s["nights"],s["last"]) for s in out_scopes])
print("statuses", Counter(p["status"] for t in out_targets for p in t["programmes"]))
