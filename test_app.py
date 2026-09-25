#!/usr/bin/env python3
"""End-to-end test of the unified Astro Import control panel against BOTH
simulated cameras: boots the real server, drives it through the HTTP API,
answers the inline questions, and verifies the imports on disk + in the ledger."""

import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.dirname(os.path.abspath(__file__))
PORT = 8991
URL = f"http://127.0.0.1:{PORT}"
PASS = FAIL = 0

def check(name, cond, detail=""):
    global PASS, FAIL
    print(("  PASS  " if cond else "  FAIL  ") + name + ("" if cond else f"   {detail}"))
    if cond:
        PASS += 1
    else:
        FAIL += 1

TOKEN = {"v": ""}   # the per-launch token, read from the page like a browser would

def api(path, body=None, url=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request((url or URL) + path, data=data,
                                 headers={"Content-Type": "application/json",
                                          "X-Astro-Token": TOKEN["v"]},
                                 method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            out = json.loads(e.read().decode())
        except ValueError:
            out = {}
        out["_status"] = e.code
        return out

def load_token(url=None):
    page = urllib.request.urlopen((url or URL) + "/", timeout=10).read().decode()
    m = re.search(r'const TOKEN="([^"]+)"', page)
    TOKEN["v"] = m.group(1) if m else ""
    return page

def wait_for(pred, timeout=60, step=0.3):
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = api("/api/state")
        if pred(s):
            return s
        time.sleep(step)
    raise TimeoutError("condition not met; last status: " + s.get("status", "?"))

# ── Build the fake two-camera world (shared helpers) ────────────────────────
import test_env_helper as teh  # noqa: E402

env = teh.Env("APP", asiair=True, seestar=True)
# ASIAir: known target with fresh matching cal + one UNKNOWN target (naming question)
env.add_light("Plan", "M 81", "0001", dt="20260720-221000", focallen=749)
env.add_light("Plan", "M 81", "0002", dt="20260720-222000", focallen=749)
env.add_light("Live", "MYSTERY 42", "0001", dt="20260721-231500", focallen=402)
env.add_cal("Bias", "1.0ms", "20260719-090000")
env.add_cal("Dark", "300.0s", "20260719-091000")
# in-window but rotation-mismatched flat → questionable → confirm card expected
env.add_cal("Flat", "20.0ms", "20260710-090000", filt="LUltimate", rot="10.0deg")
# CLEAN flat matching MYSTERY 42 (402mm, same rot) → Yes-default consent card
env.add_cal("Flat", "20.0ms", "20260721-100000", filt="LUltimate", rot="120.0deg",
            focallen=402, seq="0050")
# Seestar S30 Pro: one DSO project
env.add_seestar_sub("M 42", "20260119-210000")
env.add_seestar_sub("M 42", "20260119-210500")
env.add_seestar_stack("M 42", 30, "20260119-213000")

r = subprocess.run([sys.executable, teh.SCRIPT, "--baseline"],
                   env=env.env, capture_output=True, text=True, encoding="utf-8", errors="replace")
assert "Baseline complete" in r.stdout, r.stdout[-400:]
# a NEW calibration set taken after the baseline → must show in calSummary
env.add_cal("Bias", "1.0ms", "20260801-090000", seq="0099")
# make the targets NEW again (baseline marked them imported)
for t in ["M 81", "MYSTERY 42", "M 42"]:
    subprocess.run([sys.executable, teh.SCRIPT, "--unbaseline", t],
                   env=env.env, capture_output=True, text=True, encoding="utf-8", errors="replace")

# ── Boot the panel server ────────────────────────────────────────────────────
proc = subprocess.Popen([sys.executable, os.path.join(BUILD, "astro-app.py"),
                         "--no-browser", "--port", str(PORT)],
                        env=env.env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(40):
        try:
            if api("/api/ping").get("ok"):
                break
        except Exception:
            time.sleep(0.25)
    check("T1 server pings", api("/api/ping").get("ok") is True)

    page = load_token()
    check("T1 panel page serves", "FITS Importer" in page and "Import selected" in page)
    check("T1 the page carries a per-launch token", len(TOKEN["v"]) >= 24, TOKEN["v"])

    s = api("/api/state")
    check("T1 camera present in state", s["cameraPresent"] is True)
    check("T1 both devices listed", s["devices"] == ["ASIAir", "Seestar"], str(s["devices"]))

    # ── Scan ────────────────────────────────────────────────────────────
    api("/api/scan", {})
    s = wait_for(lambda s: s["status"] == "idle" and s["scan"])
    names = {t["name"]: t for t in s["scan"]["targets"]}
    check("T2 scan lists both new ASIAir targets",
          names.get("M 81", {}).get("new") == 2 and names.get("MYSTERY 42", {}).get("new") == 1,
          json.dumps(s["scan"])[:300])
    check("T2 scan lists the Seestar project with device tag",
          names.get("M 42", {}).get("device") == "seestar" and names["M 42"]["new"] == 2,
          json.dumps(names.get("M 42", {})))
    check("T2 storage covers both volumes",
          len(s["scan"]["disks"]) == 2 and s["scan"]["disk"] is not None,
          json.dumps(s["scan"].get("disks", [])))
    cs = s["scan"]["calSummary"]
    check("T2 calSummary present with counts",
          cs and cs["total"] == 5 and cs["inLibrary"] == 4, json.dumps(cs))
    check("T2 new calibration set surfaced (post-baseline bias)",
          len(cs["newSets"]) == 1 and cs["newSets"][0]["type"] == "Bias"
          and cs["newSets"][0]["count"] == 1 and cs["newSets"][0]["night"] == "2026-08-01"
          and cs["newSets"][0].get("setKey"),
          json.dumps(cs["newSets"]))
    # ── Pairing preview: real gates, per target ─────────────────────────
    pr = cs.get("pairings") or {}
    mys_rows = {x["type"]: x for x in pr.get("MYSTERY 42", [])}
    m81_rows = {x["type"]: x for x in pr.get("M 81", [])}
    check("T2 pairings cover both ASIAir targets",
          "MYSTERY 42" in pr and "M 81" in pr, json.dumps(list(pr.keys())))
    check("T2 clean flat pairs with MYSTERY 42 only, not questionable",
          mys_rows.get("Flat") and mys_rows["Flat"]["count"] == 1
          and mys_rows["Flat"]["questionable"] is False
          and mys_rows["Flat"]["rotation"] == 120.0,
          json.dumps(pr.get("MYSTERY 42", [])))
    check("T2 M 81 flat pairing flagged questionable (rotation probation)",
          m81_rows.get("Flat") and m81_rows["Flat"]["questionable"] is True,
          json.dumps(pr.get("M 81", [])))
    check("T2 darks and biases pair with M 81",
          m81_rows.get("Dark", {}).get("count") == 1
          and m81_rows.get("Bias", {}).get("count", 0) >= 1,
          json.dumps(pr.get("M 81", [])))
    check("T2 inventory data covers backed-up targets",
          all(k in s["scan"]["targets"][0] for k in ("files", "totalBytes", "display")),
          json.dumps(s["scan"]["targets"][0]))
    check("T2 lastStamp present for date ordering (newest file wins)",
          names["M 81"].get("lastStamp") == "20260720-222000"
          and names["M 42"].get("lastStamp") == "20260119-213000",
          json.dumps({t: names.get(t, {}).get("lastStamp") for t in ("M 81", "M 42")}))
    check("T2 scope badge follows the INCOMING frames' focal length",
          names["M 81"].get("scope") == "Askar 107PHQ"
          and names["MYSTERY 42"].get("scope") == "Askar FRA400",
          json.dumps({t: names.get(t, {}).get("scope") for t in ("M 81", "MYSTERY 42")}))
    # ── Destination preview: predicted Day folders, both devices ────────
    dp = {e["target"]: e for e in s["scan"].get("destPlan", [])}
    check("T2 destPlan covers all three targets",
          {"M 81", "MYSTERY 42", "M 42"} <= set(dp), json.dumps(list(dp)))
    check("T2 M 81 lands in its catalog-named Day 1",
          dp["M 81"]["dayFolder"] == "M 81 - Bode's Galaxy Day 1"
          and dp["M 81"]["askName"] is False and dp["M 81"]["files"] == 2,
          json.dumps(dp.get("M 81")))
    check("T2 unknown target flagged as will-ask-name",
          dp["MYSTERY 42"]["askName"] is True
          and dp["MYSTERY 42"]["dayFolder"] == "MYSTERY 42 Day 1",
          json.dumps(dp.get("MYSTERY 42")))
    check("T2 Seestar day folder predicted",
          dp["M 42"]["device"] == "seestar"
          and dp["M 42"]["dayFolder"] == "M 42_sub Day 1"
          and dp["M 42"]["display"] == "M 42 - Orion Nebula"
          and dp["M 42"]["stack"] and dp["M 42"]["stack"]["subs"] == 30,
          json.dumps(dp.get("M 42")))

    # ── Import ASIAir targets with scan-card decisions:
    #    MYSTERY 42's clean flat TICKED  → links with NO question card
    #    M 81's dark set UNTICKED        → backed up but not linked
    #    M 81's questionable flat        → still asks (No default)
    decisions = {"MYSTERY 42": {mys_rows["Flat"]["setKey"]: True},
                 "M 81": {m81_rows["Dark"]["setKey"]: False}}
    api("/api/import", {"names": ["M 81", "MYSTERY 42"], "calDecisions": decisions})
    s = wait_for(lambda s: s["question"] is not None or s["status"] == "idle", timeout=90)
    seen_kinds, seen_defaults, no_prompts = [], [], []
    while s["question"] is not None:
        q = s["question"]
        seen_kinds.append(q["kind"])
        if q["kind"] == "confirm":
            seen_defaults.append(q.get("default"))
            if q.get("default") == "n":
                no_prompts.append(q["prompt"])
        if q["kind"] == "text":
            api("/api/answer", {"id": q["id"], "value": "Test Nebula"})
        elif q.get("default") == "y":
            api("/api/answer", {"id": q["id"], "value": "y"})
        else:
            api("/api/answer", {"id": q["id"], "value": "n"})   # decline questionable ones
        time.sleep(0.4)
        s = wait_for(lambda s: s["question"] is not None or s["status"] == "idle", timeout=90)
    check("T3 questions were asked inline", "text" in seen_kinds and "confirm" in seen_kinds,
          str(seen_kinds))
    check("T3 pre-ticked flats skipped their card; questionable still asked No-default",
          "n" in seen_defaults and "y" not in seen_defaults, str(seen_defaults))
    check("T3 questionable card is self-describing (set, rotation, vs lights)",
          any("°" in p and "another project" in p.lower() and "lights at" in p
              for p in no_prompts), str(no_prompts))
    s = wait_for(lambda s: s["status"] == "idle", timeout=120)
    check("T3 import finished", "Imported" in (s["lastResult"] or ""), str(s["lastResult"]))
    check("T3 completion payload for the banner",
          bool(s.get("lastDone")) and s["lastDone"]["op"] == "import"
          and s["lastDone"]["frames"] == 3 and s["lastDone"]["targets"] == 2
          and "finishedAt" in s["lastDone"] and "seconds" in s["lastDone"],
          json.dumps(s.get("lastDone")))

    led = env.ledger()
    m81 = [e for e in led["files"].values() if e["target"] == "M 81" and e["origin"] == "import"]
    mys = [e for e in led["files"].values() if e["target"] == "MYSTERY 42" and e["origin"] == "import"]
    check("T4 M 81 frames imported + verified", len(m81) == 2 and all(e["verifiedAtImport"] for e in m81))
    check("T4 naming answer applied", mys and mys[0]["displayName"] == "MYSTERY 42 - Test Nebula",
          str(mys[:1]))
    m81_day = os.path.join(env.dest, "M 81 - Bode's Galaxy", "lights",
                           "M 81 - Bode's Galaxy Day 1", "calibration")
    def n_in(base, sub):
        d = os.path.join(base, sub)
        return len(os.listdir(d)) if os.path.isdir(d) else 0
    check("T4 questionable flats declined via panel", n_in(m81_day, "flats") == 0,
          str(n_in(m81_day, "flats")))
    check("T4 UNTICKED dark set not linked to M 81", n_in(m81_day, "darks") == 0,
          str(n_in(m81_day, "darks")))
    check("T4 biases (no decision) still link silently", n_in(m81_day, "biases") == 1,
          str(n_in(m81_day, "biases")))
    mys_day = os.path.join(env.dest, "MYSTERY 42 - Test Nebula", "lights",
                           "MYSTERY 42 - Test Nebula Day 1", "calibration")
    check("T4 TICKED clean flats linked with no question card",
          n_in(mys_day, "flats") == 1, str(n_in(mys_day, "flats")))
    check("T4 darks link to MYSTERY 42 (untick was target-scoped)",
          n_in(mys_day, "darks") == 1, str(n_in(mys_day, "darks")))
    check("T4 preview matched reality (M 81 Day folder)",
          os.path.isdir(os.path.join(env.dest, "M 81 - Bode's Galaxy", "lights",
                                     dp["M 81"]["dayFolder"])))
    check("T4 Seestar untouched by ASIAir-only selection",
          not [e for e in led["files"].values()
               if e.get("device") == "seestar" and e["origin"] == "import"])

    # ── Import the Seestar project; cleanup question card must appear ───
    api("/api/import", {"names": ["M 42"]})
    s = wait_for(lambda s: s["question"] is not None or s["status"] == "idle", timeout=90)
    cleanup_seen, cleanup_prompt = False, ""
    while s["question"] is not None:
        q = s["question"]
        if "Delete these SAFE" in q["prompt"]:
            cleanup_seen = True
            cleanup_prompt = q["prompt"]
        api("/api/answer", {"id": q["id"], "value": "n"})
        time.sleep(0.4)
        s = wait_for(lambda s: s["question"] is not None or s["status"] == "idle", timeout=90)
    s = wait_for(lambda s: s["status"] == "idle", timeout=120)
    check("T5 SAFE cleanup arrived as a question card", cleanup_seen)
    check("T5 ...and the card itself names the folders it would delete (1.4.3)",
          cleanup_seen and "M 42_sub" in cleanup_prompt
          and "verified byte for byte" in cleanup_prompt, cleanup_prompt)
    check("T5 declining kept the source on the Seestar",
          os.path.isdir(os.path.join(env.myworks, "M 42_sub")))
    led = env.ledger()
    s42 = [e for e in led["files"].values()
           if e.get("device") == "seestar" and e["origin"] == "import"]
    check("T5 Seestar frames imported + verified (subs + stack)",
          len(s42) == 3 and all(e["verifiedAtImport"] for e in s42), str(len(s42)))
    day1 = os.path.join(env.sdest30, "M 42 - Orion Nebula", "M 42_sub Day 1")
    check("T5 Seestar files on disk", os.path.isdir(day1) and len(os.listdir(day1)) == 2)
    check("T5 preview matched reality (Seestar Day folder)",
          os.path.isdir(os.path.join(env.sdest30, dp["M 42"]["display"],
                                     dp["M 42"]["dayFolder"])))
    check("T5 completion payload after Seestar import",
          bool(s.get("lastDone")) and s["lastDone"]["frames"] == 2
          and s["lastDone"]["targets"] == 1, json.dumps(s.get("lastDone")))
    # (2 = the sub lights; the stacked file is reported separately in the log)
    # banner must SURVIVE a rescan (only a new import/report clears it) ──
    api("/api/scan", {})
    s = wait_for(lambda s: s["status"] == "idle" and s["scan"])
    check("T5 banner survives a rescan", bool(s.get("lastDone")),
          json.dumps(s.get("lastDone")))

    # ── Report + dashboard through the panel ────────────────────────────
    api("/api/report", {})
    s = wait_for(lambda s: s["status"] == "idle" and s["hasReport"], timeout=60)
    check("T6 a new operation clears the banner", s.get("lastDone") is None,
          json.dumps(s.get("lastDone")))
    text = api("/api/report-text")["text"]
    check("T6 report available in panel", "SAFE TO CLEAR" in text and "M 81" in text)
    check("T6 report has the Seestar section", "SEESTAR" in text.upper())
    dash = urllib.request.urlopen(URL + "/dashboard", timeout=15).read().decode()
    check("T6 dashboard serves with data", "__DATA__" not in dash and "M 81" in dash)

    # ── Idempotence: rescan shows nothing new ───────────────────────────
    api("/api/scan", {})
    s = wait_for(lambda s: s["status"] == "idle" and s["scan"])
    check("T7 rescan shows nothing new",
          all(t["new"] == 0 for t in s["scan"]["targets"]), json.dumps(s["scan"])[:200])
    check("T7 scan payload carries the honesty notes field",
          "notes" in s["scan"], json.dumps(list(s["scan"].keys())))

    # ── T8: only the local page may drive the panel (Host/Origin gate) ──
    import http.client

    def raw_status(method, path, host_hdr, origin=None, body=None,
                   ctype="application/json", token=True, want_headers=False):
        c = http.client.HTTPConnection("127.0.0.1", PORT, timeout=10)
        headers = {"Host": host_hdr, "Content-Type": ctype}
        if token:
            headers["X-Astro-Token"] = TOKEN["v"]
        if origin:
            headers["Origin"] = origin
        c.request(method, path,
                  body=json.dumps(body) if body is not None else None,
                  headers=headers)
        resp = c.getresponse()
        st, hdrs = resp.status, dict(resp.getheaders())
        resp.read()
        c.close()
        return (st, hdrs) if want_headers else st

    check("T8 spoofed Host is refused (DNS rebinding shield)",
          raw_status("POST", "/api/scan", "evil.example.com", body={}) == 403)
    check("T8 foreign Origin is refused (drive-by POST shield)",
          raw_status("POST", "/api/answer", f"127.0.0.1:{PORT}",
                     origin="https://evil.example.com",
                     body={"value": "y"}) == 403)
    check("T8 the local page itself still passes",
          raw_status("GET", "/api/ping", f"127.0.0.1:{PORT}",
                     origin=f"http://127.0.0.1:{PORT}") == 200)
    # 1.4.3 (review V1/V2/V8)
    check("T8 a page on ANOTHER localhost port is refused (exact origin, V1)",
          raw_status("POST", "/api/scan", f"127.0.0.1:{PORT}",
                     origin=f"http://localhost:{PORT + 1}", body={}) == 403)
    check("T8 a text/plain 'simple request' is refused (no preflight dodge)",
          raw_status("POST", "/api/scan", f"127.0.0.1:{PORT}", body={},
                     ctype="text/plain") == 403)
    check("T8 a POST without the per-launch token is refused",
          raw_status("POST", "/api/scan", f"127.0.0.1:{PORT}", body={}, token=False) == 403)
    check("T8 an answer that doesn't name its card is refused",
          api("/api/answer", {"value": "y"}).get("_status") == 400)
    check("T8 a non-object JSON body is refused, not crashed on",
          raw_status("POST", "/api/import", f"127.0.0.1:{PORT}", body=["M 42"]) == 400)
    check("T8 names must be a list (a string was once imported letter by letter)",
          api("/api/import", {"names": "M 42"}).get("_status") == 400)
    st, hdrs = raw_status("GET", "/", f"127.0.0.1:{PORT}", want_headers=True)
    check("T8 the panel can't be framed by another site (clickjacking, V2)",
          "frame-ancestors 'none'" in hdrs.get("Content-Security-Policy", "")
          and hdrs.get("X-Frame-Options") == "DENY", json.dumps(hdrs))

    # ── T9: an answer only lands on the question that is actually pending ──
    check("T9 an answer with no question pending is ignored",
          api("/api/answer", {"id": 1, "value": "y"}).get("ok") is False)
    env.add_seestar_sub("M 42", "20260620-231500")
    api("/api/scan", {})
    wait_for(lambda s: s["status"] == "idle" and s["scan"])
    api("/api/import", {"names": ["M 42"]})
    s = wait_for(lambda s: s["question"] is not None, timeout=90)
    qid = s["question"]["id"]
    stale = api("/api/answer", {"id": 999999, "value": "y"})
    s2 = api("/api/state")
    check("T9 a stale-id answer is refused and the card survives",
          stale.get("ok") is False and s2["question"] is not None
          and s2["question"]["id"] == qid, json.dumps(s2.get("question")))
    check("T9 the matching-id answer resolves the card",
          api("/api/answer", {"id": qid, "value": "n"}).get("ok") is True)
    wait_for(lambda s: s["status"] == "idle", timeout=120)
    check("T9 declining kept the source on the Seestar (default-No intact)",
          os.path.isdir(os.path.join(env.myworks, "M 42_sub")))

    # ── T10 (1.4.2): a JPEG preview beside an imported FIT is NOT new work ──
    with open(os.path.join(env.myworks, "M 42_sub", "20260620-231500.jpg"),
              "wb") as jf:
        jf.write(b"\xff\xd8\xff\xe0panel-jpg" + b"k" * 300)
    api("/api/scan", {})
    s = wait_for(lambda s: s["status"] == "idle" and s["scan"])
    m42 = [t for t in s["scan"]["targets"] if t["name"] == "M 42"]
    check("T10 a preview beside an imported FIT shows no new work on the panel",
          m42 and m42[0]["new"] == 0, json.dumps(m42))
    check("T10 ...and raises no attention note (it has its FIT twin)",
          not any("JPEG" in n for n in s["scan"].get("notes", [])),
          json.dumps(s["scan"].get("notes")))
    led = env.ledger()
    check("T10 nothing was ledgered for the preview",
          not [e for e in led["files"].values() if e.get("sourceType") == "sub-jpg"])
    # ── T11 (1.4.2): rows say what the new files ARE ──
    env.add_seestar_sub("M 76", "20260923-221000")
    env.add_seestar_sub("M 76", "20260923-221100")
    env.add_seestar_stack("M 97", 458, "20260923-230000")      # stack-only project
    env.add_seestar_panel("M 76_mosaic", "20260923-224000")    # its panels row is "M 76" too
    env.add_seestar_nondso("Lunar_photo", "Lunar_20260923-220000.fit",
                           creator="ZWO Seestar S30 Pro")
    api("/api/scan", {})
    s = wait_for(lambda s: s["status"] == "idle" and s["scan"])
    m76 = [t for t in s["scan"]["targets"] if t["name"] == "M 76"]
    m97 = [t for t in s["scan"]["targets"] if t["name"] == "M 97"]
    check("T11 a subs row says how many subs and how much integration",
          m76 and m76[0]["new"] == 2 and "2 subs" in m76[0]["what"]
          and "integration" in m76[0]["what"] and m76[0]["unit"] == "frames", json.dumps(m76))
    check("T11 a stack-only row says 'stack · up to N subs', not '1 frame'",
          m97 and m97[0]["unit"] == "stack" and "1 stack of up to 458 subs" in m97[0]["what"],
          json.dumps(m97))
    rows = s["scan"]["targets"]
    dso76 = [t for t in m76 if "(panels)" not in t["display"]]
    others = [t for t in rows if t["device"] == "seestar"
              and ("(panels)" in t["display"] or "Lunar" in t["display"])]
    check("T11 every discard link is keyed by its own camera folder (never a shared name)",
          dso76 and dso76[0].get("discardId") == "M 76_sub" and len(others) == 2
          and sorted(t.get("discardId") for t in others) == ["Lunar_photo", "M 76_mosaic_pt"],
          json.dumps([(t["display"], t.get("discardId")) for t in rows]))

    # ── T12 (1.4.2): discard from the panel, typed confirmation ──
    api("/api/discard", {"name": "M 76_sub"})
    s = wait_for(lambda s: s["question"] is not None or s["status"] == "idle", timeout=90)
    q = s["question"] or {}
    check("T12 discard asks on a typed card that says NEVER backed up",
          q.get("kind") == "typed" and q.get("expect") == "DISCARD"
          and "NEVER been backed up" in q.get("prompt", ""), json.dumps(q))
    api("/api/answer", {"id": q.get("id"), "value": "yes please"})
    s = wait_for(lambda s: s["status"] == "idle", timeout=90)
    check("T12 anything but DISCARD cancels and deletes nothing",
          os.path.isfile(os.path.join(env.myworks, "M 76_sub", "20260923-221000.fit"))
          and "cancelled" in (s.get("lastResult") or ""), json.dumps(s.get("lastResult")))
    api("/api/discard", {"name": "M 76_sub"})
    s = wait_for(lambda s: s["question"] is not None, timeout=90)
    typed_id = s["question"]["id"]
    first = api("/api/answer", {"id": typed_id, "value": "DISCARD"})
    second = api("/api/answer", {"id": typed_id, "value": "nope"})   # a double click
    check("T12 the first answer wins; a second answer to the same card is refused",
          first.get("ok") is True and second.get("ok") is False, json.dumps([first, second]))
    s = wait_for(lambda s: (s["question"] is not None and s["question"]["id"] != typed_id)
                 or s["status"] == "idle", timeout=90)
    if s["question"] is not None:                     # the never-import-list offer
        api("/api/answer", {"id": s["question"]["id"], "value": "n"})
    s = wait_for(lambda s: s["status"] == "idle", timeout=90)
    led = env.ledger()
    disc = [v for v in (led.get("discarded") or {}).values() if v.get("target") == "M 76"]
    check("T12 typed DISCARD deletes from the camera and records both files first",
          not os.path.isdir(os.path.join(env.myworks, "M 76_sub")) and len(disc) == 2
          and all(v.get("sha256") for v in disc), json.dumps(s.get("lastResult")))
    check("T12 ...only that target: the same-named mosaic panels are untouched",
          os.path.isfile(os.path.join(env.myworks, "M 76_mosaic_pt", "20260923-224000.fit"))
          and (s.get("lastResult") or "").startswith("Discarded M 76 - "),
          json.dumps(s.get("lastResult")))
    api("/api/discard", {"name": "M 42"})               # imported + verified earlier
    s = wait_for(lambda s: s["question"] is not None or s["status"] == "idle", timeout=90)
    q = s["question"] or {}
    check("T12 an already-backed-up target gets the ordinary SAFE card, not the typed one",
          q.get("kind") == "confirm" and "Delete these SAFE source folders" in q.get("prompt", ""),
          json.dumps(q))
    if q:
        api("/api/answer", {"id": q["id"], "value": "n"})
    s = wait_for(lambda s: s["status"] == "idle" and s["question"] is None, timeout=90)
    check("T12 ...declining it keeps the folder, and the panel says why",
          os.path.isdir(os.path.join(env.myworks, "M 42_sub"))
          and "already backed up" in (s.get("lastResult") or ""), json.dumps(s.get("lastResult")))

    # ── T13 (1.4.3): the inventory tells the truth, and a declined SAFE
    #    clear can be reached again from the panel ──
    with open(os.path.join(env.myworks, "M 42_sub", "20260119-210000.jpg"), "wb") as jf:
        jf.write(b"\xff\xd8\xff\xe0preview" + b"p" * 50)      # a preview: fine
    with open(os.path.join(env.myworks, "M 42_sub", "stray-no-fit.jpg"), "wb") as jf:
        jf.write(b"\xff\xd8\xff\xe0orphan" + b"o" * 50)       # the only copy of something
    api("/api/scan", {})
    s = wait_for(lambda s: s["status"] == "idle" and s["scan"])
    m42 = [t for t in s["scan"]["targets"] if t["name"] == "M 42"]
    check("T13 a target with no new frames but an unproven file is NOT 'backed up'",
          m42 and m42[0]["new"] == 0 and m42[0]["safeState"] == "notsafe"
          and m42[0]["unproven"] == 1 and not m42[0].get("clearId"), json.dumps(m42))
    api("/api/discard", {"name": "M 42_sub"})
    s = wait_for(lambda s: s["question"] is not None or s["status"] == "idle", timeout=90)
    q = s["question"] or {}
    check("T13 discard on a mix offers ONLY the never-backed-up file",
          q.get("kind") == "typed" and "1 JPEG with no FIT" in q.get("prompt", "")
          and "stay on the camera" in q.get("prompt", ""), json.dumps(q))
    if q:
        api("/api/answer", {"id": q["id"], "value": "DISCARD"})
    s = wait_for(lambda s: s["status"] == "idle" and s["question"] is None, timeout=90)
    check("T13 ...which goes, and the backed-up frames stay",
          not os.path.exists(os.path.join(env.myworks, "M 42_sub", "stray-no-fit.jpg"))
          and os.path.isfile(os.path.join(env.myworks, "M 42_sub", "20260119-210000.fit")),
          json.dumps(s.get("lastResult")))
    check("T13 a discard shows a banner, not just a grey line",
          (s.get("lastDone") or {}).get("op") == "discard", json.dumps(s.get("lastDone")))
    api("/api/scan", {})
    s = wait_for(lambda s: s["status"] == "idle" and s["scan"])
    m42 = [t for t in s["scan"]["targets"] if t["name"] == "M 42"]
    check("T13 now everything left is proven: the row offers clear…",
          m42 and m42[0]["safeState"] == "safe" and m42[0].get("clearId") == "M 42_sub",
          json.dumps(m42))
    api("/api/clear", {"name": "M 42_sub"})
    s = wait_for(lambda s: s["question"] is not None or s["status"] == "idle", timeout=90)
    q = s["question"] or {}
    check("T13 clear… asks on the SAFE card, which lists the folders",
          q.get("kind") == "confirm" and q.get("default") == "n"
          and "M 42_sub" in q.get("prompt", ""), json.dumps(q))
    if q:
        api("/api/answer", {"id": q["id"], "value": "y"})
    s = wait_for(lambda s: s["status"] == "idle" and s["question"] is None, timeout=90)
    check("T13 ...Yes clears it the SAFE way and says so",
          not os.path.isdir(os.path.join(env.myworks, "M 42_sub"))
          and (s.get("lastDone") or {}).get("op") == "clear"
          and "Cleared" in (s.get("lastResult") or ""), json.dumps(s.get("lastResult")))
    # never-import list: a skipped target with new frames is NOT backed up
    env.add_seestar_sub("NGC 7000", "20260924-213000")
    r = api("/api/skip", {"name": "NGC 7000", "skip": True})
    s = wait_for(lambda s: s["status"] == "idle", timeout=30)
    api("/api/scan", {})
    s = wait_for(lambda s: s["status"] == "idle" and s["scan"])
    ngc = [t for t in s["scan"]["targets"] if t["name"] == "NGC 7000"]
    check("T13 a never-import target with new frames is flagged as such, not 'backed up'",
          ngc and ngc[0]["skipped"] and ngc[0]["new"] == 1
          and ngc[0]["safeState"] == "notsafe", json.dumps(ngc))
    api("/api/skip", {"name": "NGC 7000", "skip": False})
    s = wait_for(lambda s: s["status"] == "idle", timeout=30)
    api("/api/scan", {})
    s = wait_for(lambda s: s["status"] == "idle" and s["scan"])
    ngc = [t for t in s["scan"]["targets"] if t["name"] == "NGC 7000"]
    check("T13 'import again' takes it off the list — offered as new work",
          ngc and not ngc[0]["skipped"] and ngc[0]["new"] == 1, json.dumps(ngc))
finally:
    proc.terminate()

# ── T14 (1.4.3): a brand-new user imports from the panel with no ledger ──
env2 = teh.Env("APP2", asiair=False, seestar=True)
env2.add_seestar_sub("M 33", "20260924-213000")
env2.add_seestar_sub("M 33", "20260924-213100")
PORT2 = PORT + 1
URL2 = f"http://127.0.0.1:{PORT2}"
proc2 = subprocess.Popen([sys.executable, os.path.join(BUILD, "astro-app.py"),
                          "--no-browser", "--port", str(PORT2)],
                         env=env2.env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(40):
        try:
            if api("/api/ping", url=URL2).get("ok"):
                break
        except Exception:
            time.sleep(0.25)
    load_token(URL2)
    api("/api/scan", {}, url=URL2)
    t0 = time.time()
    while time.time() - t0 < 60:
        s = api("/api/state", url=URL2)
        if s["status"] == "idle" and s["scan"]:
            break
        time.sleep(0.3)
    m33 = [t for t in s["scan"]["targets"] if t["name"] == "M 33"]
    check("T14 with no ledger the scan offers everything as new (no baseline needed)",
          m33 and m33[0]["new"] == 2 and not s["scan"]["hasLedger"], json.dumps(m33))
    api("/api/import", {"names": ["M 33"]}, url=URL2)
    t0 = time.time()
    while time.time() - t0 < 90:
        s = api("/api/state", url=URL2)
        if s.get("question"):
            api("/api/answer", {"id": s["question"]["id"], "value": "n"}, url=URL2)
        elif s["status"] == "idle" and time.time() - t0 > 1:
            break
        time.sleep(0.3)
    led = env2.ledger()
    copied = [e for e in led["files"].values() if e.get("verifiedAtImport")]
    check("T14 ...and the first import really copies and verifies them",
          len(copied) == 2 and any(os.path.isdir(os.path.join(env2.sdest30, d))
                                   for d in os.listdir(env2.sdest30)),
          json.dumps(s.get("lastResult")))
finally:
    proc2.terminate()

print("\n═══════════════════════════════════════")
print(f"  {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
