#!/usr/bin/env python3
"""End-to-end test of the unified Astro Import control panel against BOTH
simulated cameras: boots the real server, drives it through the HTTP API,
answers the inline questions, and verifies the imports on disk + in the ledger."""

import json
import os
import subprocess
import sys
import time
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

def api(path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(URL + path, data=data,
                                 headers={"Content-Type": "application/json"},
                                 method="POST" if body is not None else "GET")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode())

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
# Seestar S30 Pro: one DSO project
env.add_seestar_sub("M 42", "20260119-210000")
env.add_seestar_sub("M 42", "20260119-210500")
env.add_seestar_stack("M 42", 30, "20260119-213000")

r = subprocess.run([sys.executable, teh.SCRIPT, "--baseline"],
                   env=env.env, capture_output=True, text=True)
assert "Baseline complete" in r.stdout, r.stdout[-400:]
# make the targets NEW again (baseline marked them imported)
for t in ["M 81", "MYSTERY 42", "M 42"]:
    subprocess.run([sys.executable, teh.SCRIPT, "--unbaseline", t],
                   env=env.env, capture_output=True, text=True)

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

    page = urllib.request.urlopen(URL + "/", timeout=10).read().decode()
    check("T1 panel page serves", "FITS Importer" in page and "Import selected" in page)

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

    # ── Import ASIAir targets; answer the two inline questions ──────────
    api("/api/import", {"names": ["M 81", "MYSTERY 42"]})
    s = wait_for(lambda s: s["question"] is not None or s["status"] == "idle", timeout=90)
    seen_kinds = []
    while s["question"] is not None:
        q = s["question"]
        seen_kinds.append(q["kind"])
        if q["kind"] == "text":
            api("/api/answer", {"value": "Test Nebula"})
        else:
            api("/api/answer", {"value": "n"})       # decline questionable flats
        time.sleep(0.4)
        s = wait_for(lambda s: s["question"] is not None or s["status"] == "idle", timeout=90)
    check("T3 questions were asked inline", "text" in seen_kinds and "confirm" in seen_kinds,
          str(seen_kinds))
    s = wait_for(lambda s: s["status"] == "idle", timeout=120)
    check("T3 import finished", "Imported" in (s["lastResult"] or ""), str(s["lastResult"]))

    led = env.ledger()
    m81 = [e for e in led["files"].values() if e["target"] == "M 81" and e["origin"] == "import"]
    mys = [e for e in led["files"].values() if e["target"] == "MYSTERY 42" and e["origin"] == "import"]
    check("T4 M 81 frames imported + verified", len(m81) == 2 and all(e["verifiedAtImport"] for e in m81))
    check("T4 naming answer applied", mys and mys[0]["displayName"] == "MYSTERY 42 - Test Nebula",
          str(mys[:1]))
    flats_dir = os.path.join(env.dest, "M 81 - Bode's Galaxy", "lights",
                             "M 81 - Bode's Galaxy Day 1", "calibration", "flats")
    n_flats = len([f for f in os.listdir(flats_dir)]) if os.path.isdir(flats_dir) else 0
    check("T4 questionable flats declined via panel", n_flats == 0, str(n_flats))
    darks_dir = os.path.join(env.dest, "M 81 - Bode's Galaxy", "lights",
                             "M 81 - Bode's Galaxy Day 1", "calibration", "darks")
    check("T4 darks still linked", os.path.isdir(darks_dir) and len(os.listdir(darks_dir)) == 1)
    check("T4 Seestar untouched by ASIAir-only selection",
          not [e for e in led["files"].values()
               if e.get("device") == "seestar" and e["origin"] == "import"])

    # ── Import the Seestar project; cleanup question card must appear ───
    api("/api/import", {"names": ["M 42"]})
    s = wait_for(lambda s: s["question"] is not None or s["status"] == "idle", timeout=90)
    cleanup_seen = False
    while s["question"] is not None:
        q = s["question"]
        if "Delete these SAFE" in q["prompt"]:
            cleanup_seen = True
        api("/api/answer", {"value": "n"})
        time.sleep(0.4)
        s = wait_for(lambda s: s["question"] is not None or s["status"] == "idle", timeout=90)
    s = wait_for(lambda s: s["status"] == "idle", timeout=120)
    check("T5 SAFE cleanup arrived as a question card", cleanup_seen)
    check("T5 declining kept the source on the Seestar",
          os.path.isdir(os.path.join(env.myworks, "M 42_sub")))
    led = env.ledger()
    s42 = [e for e in led["files"].values()
           if e.get("device") == "seestar" and e["origin"] == "import"]
    check("T5 Seestar frames imported + verified (subs + stack)",
          len(s42) == 3 and all(e["verifiedAtImport"] for e in s42), str(len(s42)))
    day1 = os.path.join(env.sdest30, "M 42 - Orion Nebula", "M 42_sub Day 1")
    check("T5 Seestar files on disk", os.path.isdir(day1) and len(os.listdir(day1)) == 2)

    # ── Report + dashboard through the panel ────────────────────────────
    api("/api/report", {})
    s = wait_for(lambda s: s["status"] == "idle" and s["hasReport"], timeout=60)
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
finally:
    proc.terminate()

print("\n═══════════════════════════════════════")
print(f"  {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
