#!/usr/bin/env python3
"""End-to-end test of the unified Astro Import control panel against BOTH
simulated cameras: boots the real server, drives it through the HTTP API,
answers the inline questions, and verifies the imports on disk + in the ledger."""

import sys
sys.dont_write_bytecode = True   # nothing is written beside the sources
import contextlib
import gc
import importlib.util
import io
import json
import os
import re
import subprocess
import threading
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_env_helper as teh  # noqa: E402
teh.isolate_runner()   # test mode for this process too

BUILD = os.path.dirname(os.path.abspath(__file__))
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

PANEL_LOGS = []   # each panel's own output, printed when anything fails

def start_panel(env, port):
    """Boot the real panel for `env`; its output goes to a log in the root."""
    log = os.path.join(env.root, "panel.log")
    PANEL_LOGS.append(log)
    with open(log, "w") as out:
        return subprocess.Popen([sys.executable, os.path.join(BUILD, "astro-app.py"),
                                 "--no-browser", "--port", str(port)],
                                env=dict(env.env, PYTHONUNBUFFERED="1"),   # log survives a kill
                                stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)

def show_panel_logs():
    for log in PANEL_LOGS:
        try:
            with open(log, encoding="utf-8", errors="replace") as f:
                print(f"\n── {log} ──\n{f.read()[-3000:]}")
        except OSError:
            pass

def own_panel(url, env, proc, label):
    """Wait for the panel, then make sure it is OURS (/api/ping names this
    env's state folder) before any token is read or request sent: a leftover
    or real panel answering on the port is never driven (1.5.2)."""
    ping = {}
    for _ in range(40):
        try:
            ping = api("/api/ping", url=url)
            if ping.get("ok"):
                break
        except Exception:
            pass
        time.sleep(0.25)
    want = teh.instance_id(env.state)
    check(label, ping.get("instance") == want, f"got {ping.get('instance')!r}, want {want!r}")
    if ping.get("instance") != want:
        proc.terminate()
        print(f"  another panel is answering on {url} — not driving it. Stopping.")
        show_panel_logs()
        sys.exit(1)

# ── The status line (U9, 1.5.3) ─────────────────────────────────────────────
HERE_WORDS = "this PC" if os.name == "nt" else "the Mac"
HERE_MACHINE = "PC" if os.name == "nt" else "Mac"
STATUS_KEYS = {"safe", "onlyHere", "text", "machine"}

def status_line(url=None):
    """GET /api/status with no token, as the page and the app do."""
    try:
        with urllib.request.urlopen((url or URL) + "/api/status", timeout=15) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"error": repr(e)}

def wait_status(pred, timeout=20):
    """The status line once pred(it) holds (it is computed off the request
    thread, so it can trail an operation a little); else the last one seen."""
    t0, last = time.time(), None
    while time.time() - t0 < timeout:
        last = status_line()
        if isinstance(last, dict) and STATUS_KEYS <= set(last) and pred(last):
            return last
        time.sleep(0.3)
    return last

def in_state(s):
    """The status object /api/state carries, found by its shape ("status"
    there already names the operation: idle, scanning, ...)."""
    return next((v for v in s.values() if isinstance(v, dict) and STATUS_KEYS <= set(v)), None)

def answers(url):
    try:
        urllib.request.urlopen(url + "/api/ping", timeout=2).close()
        return True
    except Exception:
        return False

# ── Build the fake two-camera world (shared helpers) ────────────────────────
env = teh.Env("APP", asiair=True, seestar=True)
PORT = int(env.env["ASTRO_PANEL_PORT"])   # a free port, never 8765
URL = f"http://127.0.0.1:{PORT}"
# the fake OS commands first on PATH: <root>/EXECUTED means one ran
env.env["PATH"] = teh.fake_os_commands(env.root) + os.pathsep + env.env["PATH"]
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
                   env=env.env, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   stdin=subprocess.DEVNULL, timeout=120)
assert "Baseline complete" in r.stdout, r.stdout[-400:]
# a NEW calibration set taken after the baseline → must show in calSummary
env.add_cal("Bias", "1.0ms", "20260801-090000", seq="0099")
# make the targets NEW again (baseline marked them imported)
for t in ["M 81", "MYSTERY 42", "M 42"]:
    subprocess.run([sys.executable, teh.SCRIPT, "--unbaseline", t],
                   env=env.env, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   stdin=subprocess.DEVNULL, timeout=120)

# ── T0 (1.5.2): a test panel never binds the real panel's port 8765 ─────────
def refuses_8765(args, extra):
    try:
        r = subprocess.run([sys.executable, os.path.join(BUILD, "astro-app.py"), "--no-browser",
                            *args], env=dict(env.env, **extra), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, timeout=30)
    except subprocess.TimeoutExpired:
        return "still running after 30 s (it started serving)"
    out = r.stdout + r.stderr
    return "" if r.returncode == 3 and "TEST MODE:" in out and "panel →" not in out \
        else f"rc={r.returncode} {out[-300:]}"
why = refuses_8765(["--port", "8765"], {}) + refuses_8765([], {"ASTRO_PANEL_PORT": "8765"})
check("T0 under a test the panel refuses port 8765 (--port or ASTRO_PANEL_PORT): exit 3, never serves",
      not why, why)
r = subprocess.run([sys.executable, os.path.join(BUILD, "astro-app.py"), "--port", str(PORT), "--help"],
                   env=dict(env.env, ASTRO_PANEL_PORT="abc"), capture_output=True, text=True,
                   encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, timeout=30)
check("T0 an ASTRO_PANEL_PORT that isn't a number never stops the panel (it means 8765)",
      r.returncode == 0 and "usage:" in r.stdout, f"rc={r.returncode} {(r.stdout + r.stderr)[-300:]}")

# ── T0b (1.5.2): without --no-browser a test panel records the browser, opens nothing ──
envb = teh.Env("APPB", asiair=False, seestar=False)
fake = teh.fake_os_commands(envb.root)
logb = os.path.join(envb.root, "panel.log")
PANEL_LOGS.append(logb)
eb = dict(envb.env, PYTHONUNBUFFERED="1", PATH=fake + os.pathsep + envb.env["PATH"])
if os.name != "nt":
    eb["BROWSER"] = os.path.join(fake, "browser")   # what webbrowser would run
with open(logb, "w") as out:
    procb = subprocess.Popen([sys.executable, os.path.join(BUILD, "astro-app.py"),
                              "--port", envb.env["ASTRO_PANEL_PORT"]],
                             env=eb, stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
try:
    t0 = time.time()
    while time.time() - t0 < 20 and not teh.os_calls(envb.root, "browser"):
        time.sleep(0.25)
    time.sleep(1.0)                  # past the 0.4 s a real browser open waits
finally:
    procb.terminate()
    procb.wait(timeout=30)
check("T0b without --no-browser a test panel records the browser and opens nothing",
      len(teh.os_calls(envb.root, "browser")) == 1 and (os.name == "nt" or not teh.executed(envb.root)),
      json.dumps(teh.os_calls(envb.root)) + teh.executed(envb.root)[-200:])

# ── Boot the panel server ────────────────────────────────────────────────────
proc = start_panel(env, PORT)
try:
    own_panel(URL, env, proc, "T1 /api/ping carries this panel's instance id (it is OUR panel)")
    check("T1 server pings", api("/api/ping").get("ok") is True)

    page = load_token()
    check("T1 panel page serves", "FITS Importer" in page and "Import selected" in page)
    check("T1 the page carries a per-launch token", len(TOKEN["v"]) >= 24, TOKEN["v"])

    s = api("/api/state")
    check("T1 camera present in state", s["cameraPresent"] is True)
    check("T1 both devices listed", s["devices"] == ["ASIAir", "Seestar"], str(s["devices"]))

    # ── U9 (1.5.3): the status line, served with no token like every GET ──
    st0 = wait_status(lambda x: True)
    check("U9 /api/status (no token) serves the status line: 'Everything is safe' here",
          st0 == {"safe": True, "onlyHere": 0, "text": "Everything is safe",
                  "machine": HERE_MACHINE}, json.dumps(st0))
    s = api("/api/state")
    check("U9 /api/state carries the same object, beside the operation's own 'status'",
          in_state(s) == st0 and s.get("status") == "idle",
          json.dumps({k: v for k, v in s.items() if k != "log"})[:300])

    # ── U7 (1.5.3): a second panel on the same port steps aside (since
    #    1.5.0 W2; checked now because the app relies on it) ──
    envc = teh.Env("APPC", asiair=False, seestar=False)
    try:
        r = subprocess.run([sys.executable, os.path.join(BUILD, "astro-app.py"), "--no-browser",
                            "--port", str(PORT)], env=envc.env, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, timeout=30)
        second = r.stdout + r.stderr
    except subprocess.TimeoutExpired:
        second = "still running after 30 s (it bound the port too)"
    check("U7 a second panel on the same port steps aside, saying the port is in use; "
          "the first still answers as itself",
          "in use" in second and "panel →" not in second
          and api("/api/ping").get("instance") == teh.instance_id(env.state)
          and api("/api/state").get("status") == "idle", second[-300:])

    # ── U6 (1.5.3): the panel's own banner names what holds the lock ──
    lockp = os.path.join(env.state, "import.lock")
    said = {}
    try:
        for what in ("ship", "panel"):
            with open(lockp, "w") as f:         # held by a live process (this runner)
                json.dump({"pid": os.getpid(), "started": "2026-09-26T101500", "what": what}, f)
            api("/api/report", {})
            s = wait_for(lambda s: s["status"] == "idle", timeout=30)
            said[what] = str(s.get("lastResult"))
    finally:
        os.remove(lockp)
    check("U6 the panel's banner says what holds the lock in the engine's own words: "
          "'The twice-daily ship to the PC is running right now', 'The panel is busy right now'",
          said.get("ship", "").startswith("The twice-daily ship to the PC is running right now. ")
          and said.get("panel", "").startswith("The panel is busy right now. ")
          and not s.get("hasReport"), json.dumps(said))

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
    done_notes = [c for c in teh.os_calls(env.root, "notify")
                  if "import complete" in str(c.get("title", ""))]
    check("T3 the panel's own 'import complete' notification is recorded, never shown (1.5.2)",
          bool(done_notes) and (os.name == "nt" or not teh.executed(env.root)),
          json.dumps(teh.os_calls(env.root))[:300] + teh.executed(env.root)[-200:])
    with open(os.path.join(BUILD, "astro-app.py"), encoding="utf-8") as f:
        panel_src = f.read()
    check("U5 ...it goes through eng.notify with the chime (recorded with sound true); "
          "no osascript left in the panel",
          bool(done_notes) and all(c.get("sound") is True for c in done_notes)
          and "osascript" not in panel_src, json.dumps(done_notes)[:300])

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
    try:
        with open(os.path.join(env.state, "import.lock"), encoding="utf-8") as f:
            held = json.load(f)
    except (OSError, ValueError):
        held = {}
    check("U6 while the panel works, import.lock says the panel holds it (what: panel)",
          held.get("what") == "panel", json.dumps(held))
    no_token = raw_status("POST", "/api/quit", f"127.0.0.1:{PORT}", body={}, token=False)
    busy = api("/api/quit", {})
    check("U8 /api/quit needs the token (403) and is refused mid-import (409 busy); a card on its "
          "own and an operation on its own are each checked in-process (U8 below)",
          no_token == 403 and busy.get("_status") == 409 and busy.get("ok") is False
          and busy.get("reason") == "busy", json.dumps([no_token, busy]))
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
    r = subprocess.run([sys.executable, teh.SCRIPT, "--status", "--json"], env=env.env,
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       stdin=subprocess.DEVNULL, timeout=120)
    try:
        want = json.loads(r.stdout)
    except ValueError:
        want = {"error": (r.stdout + r.stderr)[-200:]}
    st1 = wait_status(lambda x: x == want)
    n = st1.get("onlyHere") if isinstance(st1, dict) else None
    check("U9 after the SAFE clear the status line counts the frames now only here "
          "(the same as the CLI's --status)",
          isinstance(n, int) and n >= 1 and st1 == want and st1.get("safe") is False
          and st1.get("text") == f"{n:,} frame{'' if n == 1 else 's'} only on {HERE_WORDS}",
          json.dumps([st1, want]))
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

    # ── U9: the status line follows ledger.json (the PC sweep's stamps) ──
    led_path = os.path.join(env.state, "ledger.json")
    led = env.ledger()
    for row in led["files"].values():
        if row.get("clearedFromCamera") and row.get("verifiedAtImport"):
            row["archiveVerifiedAt"] = "2026-09-26T120000"
    with open(led_path + ".u9", "w") as f:
        json.dump(led, f)
    os.replace(led_path + ".u9", led_path)
    st2 = wait_status(lambda x: x["safe"])
    check("U9 ...and recomputed when ledger.json changes (all now PC-verified): 'Everything is safe'",
          st2 == {"safe": True, "onlyHere": 0, "text": "Everything is safe",
                  "machine": HERE_MACHINE}, json.dumps(st2))

    # ── U8 (1.5.3): an idle panel quits on /api/quit ──
    bye = api("/api/quit", {})
    t0 = time.time()
    while answers(URL) and time.time() - t0 < 15:
        time.sleep(0.2)
    check("U8 an idle panel quits on /api/quit (200, ok) and the port then stops answering",
          bye.get("ok") is True and "_status" not in bye and not answers(URL), json.dumps(bye))
finally:
    proc.terminate()
    proc.wait(timeout=30)

# ── T14 (1.4.3): a brand-new user imports from the panel with no ledger ──
env2 = teh.Env("APP2", asiair=False, seestar=True)
env2.add_seestar_sub("M 33", "20260924-213000")
env2.add_seestar_sub("M 33", "20260924-213100")
PORT2 = int(env2.env["ASTRO_PANEL_PORT"])
URL2 = f"http://127.0.0.1:{PORT2}"
proc2 = start_panel(env2, PORT2)
try:
    own_panel(URL2, env2, proc2, "T14 the second panel answers with its own instance id")
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
    proc2.wait(timeout=30)

# ── U3 (1.5.3): the panel never works on a ledger from a newer importer ──
# The engine refuses to save it; the panel must refuse before it copies or
# deletes anything, not only at the save (like the CLI): an import, the SAFE
# clear, a discard and the report. M 51 is backed up first (under ledger v1,
# kept on the camera) so a clear there would really delete; M 52 is new.
# Every card a refused operation should never show is answered YES here.
env3 = teh.Env("APP3", asiair=False, seestar=True)
m51 = env3.add_seestar_sub("M 51", "20260924-213000")
r = subprocess.run([sys.executable, teh.SCRIPT, "--no-ship"], input="n\nn\nn\nn\n",
                   env=dict(env3.env, ASTRO_STDIN_PROMPTS="1"), capture_output=True, text=True,
                   encoding="utf-8", errors="replace", timeout=120)
m52 = env3.add_seestar_sub("M 52", "20260925-213000")
led3 = os.path.join(env3.state, "ledger.json")
with open(led3, encoding="utf-8") as f:
    newer3 = json.load(f)
backed = [e for e in newer3.get("files", {}).values()
          if e.get("target") == "M 51" and e.get("verifiedAtImport")]
newer3["version"] = 2                          # the app's newer ledger, rows and all
with open(led3, "w", encoding="utf-8") as f:
    json.dump(newer3, f)
def u3_bytes():
    out = {}
    for p in (led3, led3 + ".bak"):
        if os.path.exists(p):
            with open(p, "rb") as f:
                out[os.path.basename(p)] = f.read()
    return out
led3_bytes = u3_bytes()
def u3_copies():
    return sorted(os.path.join(d, n) for d, _, fs in os.walk(env3.sdest30) for n in fs
                  if n.lower().endswith(".fit"))
copies3 = u3_copies()
PORT3 = int(env3.env["ASTRO_PANEL_PORT"])
URL3 = f"http://127.0.0.1:{PORT3}"
proc3 = start_panel(env3, PORT3)
u3 = {"setup": bool(backed) and len(copies3) == 1, "said": {}}

def u3_op(path, body):
    """Run one operation on panel 3 to the end, saying yes to any card."""
    api(path, body, url=URL3)
    t0, s = time.time(), {}
    while time.time() - t0 < 60:
        s = api("/api/state", url=URL3)
        q = s.get("question")
        if q:
            val = q.get("expect") or ("y" if q.get("kind") == "confirm" else "")
            api("/api/answer", {"id": q["id"], "value": val}, url=URL3)
        elif s["status"] == "idle" and time.time() - t0 > 1:
            break
        time.sleep(0.3)
    return s

try:
    own_panel(URL3, env3, proc3, "U3 a panel on a newer importer's ledger (v2) answers as itself")
    load_token(URL3)
    api("/api/scan", {}, url=URL3)
    t0 = time.time()
    while time.time() - t0 < 60:
        s = api("/api/state", url=URL3)
        if s["status"] == "idle" and s["scan"]:
            break
        time.sleep(0.3)
    s = u3_op("/api/import", {"names": ["M 52"]})
    u3["said"]["import"] = s.get("lastResult")
    u3["log"] = [ln for ln in s.get("log") or [] if "newer version" in str(ln)][-2:]
    u3["copied"] = u3_copies() != copies3
    for what, path, body in (("clear", "/api/clear", {"name": "M 51_sub"}),
                             ("discard", "/api/discard", {"name": "M 52_sub"}),
                             ("report", "/api/report", {})):
        u3["said"][what] = u3_op(path, body).get("lastResult")
    u3["same"] = u3_bytes() == led3_bytes
    u3["camera"] = [os.path.isfile(m51), os.path.isfile(m52)]
    u3["copies"] = u3_copies() == copies3
finally:
    proc3.terminate()
    proc3.wait(timeout=30)
check("U3 ...an import there is refused before anything is copied, and says why; "
      "the ledger and its .bak byte-identical",
      u3.get("setup") is True and u3.get("same") is True and u3.get("copied") is False
      and "newer version" in str(u3["said"].get("import")) and bool(u3.get("log")),
      json.dumps(u3)[:600])
check("U3 ...and so are the panel's SAFE clear, discard and report: each says why, both "
      "camera files stay, nothing is copied and the ledger is byte-identical",
      u3.get("setup") is True
      and all("newer version" in str(u3["said"].get(k)) for k in ("clear", "discard", "report"))
      and u3.get("camera") == [True, True] and u3.get("copies") is True
      and u3.get("same") is True, json.dumps(u3)[:600])

# ── U9 (1.5.3): the status line tells the truth when the ledger can't be read ──
# The panel shows status_summary's own words, and never keeps an earlier line
# ("Everything is safe", "1 frame only on the Mac") after it fails to work one out.
env4 = teh.Env("APP4", asiair=False, seestar=False)
os.makedirs(env4.state)
led4 = os.path.join(env4.state, "ledger.json")
def put4(path, data):
    with open(path + ".t", "wb") as f:
        f.write(data)
    os.replace(path + ".t", path)
ONE_HERE = json.dumps({"version": 1, "calibration": {}, "files": {
    "MyWorks/M 42_sub/20260901-000000.fit": {
        "target": "M 42", "filename": "20260901-000000.fit", "device": "seestar",
        "camera": "ZWO Seestar S50 Pro", "sourceType": "sub", "origin": "import",
        "size": 2880, "verifiedAtImport": True, "clearedFromCamera": True}}}).encode()
UNKNOWN = {"safe": False, "onlyHere": None, "text": "Status unknown: the ledger can't be read",
           "machine": HERE_MACHINE}
put4(led4, json.dumps({"version": 1, "files": {}, "calibration": {}}).encode())
PORT4 = int(env4.env["ASTRO_PANEL_PORT"])
URL4 = f"http://127.0.0.1:{PORT4}"
proc4 = start_panel(env4, PORT4)
u4, page4 = {}, ""

def status4(pred, timeout=30):
    t0, last = time.time(), None
    while time.time() - t0 < timeout:
        last = status_line(URL4)
        if isinstance(last, dict) and STATUS_KEYS <= set(last) and pred(last):
            break
        time.sleep(0.3)
    return last

try:
    own_panel(URL4, env4, proc4, "U9 a panel for the status-line checks answers as itself")
    page4 = load_token(URL4)
    u4["good"] = status4(lambda x: True)
    put4(led4, b"{not json")
    put4(led4 + ".bak", b"{not json")
    u4["corrupt"] = status4(lambda x: x["text"] != (u4.get("good") or {}).get("text"))
    u4["corruptState"] = in_state(api("/api/state", url=URL4))
    put4(led4, ONE_HERE)
    u4["one"] = status4(lambda x: x["onlyHere"] == 1)
    put4(led4, ONE_HERE + b"\xff")          # the engine can't even open it (exit 1)
    u4["broken"] = status4(lambda x: x["onlyHere"] != 1)
    u4["brokenState"] = in_state(api("/api/state", url=URL4))
    for p in (led4, led4 + ".bak"):
        os.remove(p)
    u4["none"] = status4(lambda x: x["text"] != UNKNOWN["text"])
finally:
    proc4.terminate()
    proc4.wait(timeout=30)
check("U9 ledger and .bak unreadable: the panel shows status_summary's own 'Status unknown: "
      "the ledger can't be read' (never hidden, never safe), in /api/status and /api/state",
      (u4.get("good") or {}).get("text") == "Everything is safe" and u4.get("corrupt") == UNKNOWN
      and u4.get("corruptState") == UNKNOWN, json.dumps(u4)[:600])
check("U9 ...a ledger the engine can't even open (a stray byte, a crash): 'Status unknown', "
      "never the line from before ('1 frame only …')",
      (u4.get("one") or {}).get("text") == f"1 frame only on {HERE_WORDS}"
      and u4.get("broken") == UNKNOWN and u4.get("brokenState") == UNKNOWN, json.dumps(u4)[:600])
check("U9 ...and no ledger at all: 'Nothing imported yet'",
      u4.get("none") == {"safe": True, "onlyHere": 0, "text": "Nothing imported yet",
                         "machine": HERE_MACHINE}, json.dumps(u4.get("none")))
TIP = (f"Cleared from the camera; the only verified copy is on this {HERE_MACHINE} "
       "until the PC's sweep checks it")
check("U9 the status line's tooltip, worded for this computer, explains a count "
      "('… only on this Mac/PC until the PC's sweep checks it')",
      f'const STATUS_TIP="{TIP}";' in page4 and "sl.title=sum.onlyHere?STATUS_TIP" in page4,
      re.findall(r"const STATUS_TIP=.*", page4)[:1])

# ── U10 (1.5.3): the app runs the panel in-process — make_server() / serve() ──
u10, said = {}, io.StringIO()
computed = []                     # each time the status line is worked out (U9 below)
try:
    with contextlib.redirect_stdout(said):
        spec = importlib.util.spec_from_file_location("astro_app_u10",
                                                      os.path.join(BUILD, "astro-app.py"))
        panel = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(panel)
        # U9 below: the status line then moves only when an operation (or a
        # test) asks it to look, never on its 2-second poll
        panel.STATUS.poll_s = 3600
        real_compute = panel.compute_status

        def spy_compute():
            computed.append(time.time())
            return real_compute()
        panel.compute_status = spy_compute
        u10["instance"] = teh.instance_id(panel.eng.STATE_DIR)
        port = teh.free_port()
        url = f"http://127.0.0.1:{port}"
        srv = panel.make_server(port)
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        u10.update(ping=api("/api/ping", url=url), port=panel.PORT == port)
        srv.shutdown()
        srv.server_close()
        t.join(10)
        u10["closed"] = not answers(url)
        port = teh.free_port()
        url = f"http://127.0.0.1:{port}"
        t = threading.Thread(target=panel.serve, args=(port,), kwargs={"open_browser": False},
                             daemon=True)
        t.start()
        t0 = time.time()
        while not answers(url) and time.time() - t0 < 15:
            time.sleep(0.2)
        u10["ping2"] = api("/api/ping", url=url)
        TOKEN["v"] = panel.TOKEN
        u10["quit"] = api("/api/quit", {}, url=url)
        t.join(15)
        u10["ended"] = not t.is_alive() and not answers(url)
except Exception as x:
    u10["error"] = repr(x)
u10["said"] = said.getvalue()[-200:]
check("U10 make_server(port) in-process answers as this panel with PORT set; shutdown() stops it",
      u10.get("instance") and (u10.get("ping") or {}).get("instance") == u10["instance"]
      and u10.get("port") is True and u10.get("closed") is True, json.dumps(u10)[:400])
check("U10 serve(port, open_browser=False) in a thread: it pings, opens no browser, "
      "and returns after /api/quit",
      (u10.get("ping2") or {}).get("ok") is True and (u10.get("quit") or {}).get("ok") is True
      and u10.get("ended") is True
      and not teh.os_calls(os.environ["ASTRO_TEST_ROOT"], "browser"), json.dumps(u10)[:400])

# ── In-process: port 0, /api/quit while busy, and how the status line is
#    worked out (the same panel module, driven directly) ──
ip = {}
IP_LEDGER = None

def ip_ledger(n):
    """A ledger with n frames only on this computer, in the runner's own state."""
    rows = {f"MyWorks/M 42_sub/20260901-{i:06d}.fit": {
        "target": "M 42", "filename": f"20260901-{i:06d}.fit", "device": "seestar",
        "camera": "ZWO Seestar S50 Pro", "sourceType": "sub", "origin": "import",
        "size": 2880, "verifiedAtImport": True, "clearedFromCamera": True} for i in range(n)}
    os.makedirs(panel.eng.STATE_DIR, exist_ok=True)
    tmp = IP_LEDGER + ".t"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"version": 1, "files": rows, "calibration": {}}, f)
    os.replace(tmp, IP_LEDGER)

def ip_status(url, pred, timeout=20):
    t0, last = time.time(), None
    while time.time() - t0 < timeout:
        last = status_line(url)
        if isinstance(last, dict) and pred(last):
            break
        time.sleep(0.2)
    return last

def ip_idle(timeout=20):
    t0 = time.time()
    while panel.APP.status != "idle" and time.time() - t0 < timeout:
        time.sleep(0.1)
    return panel.APP.status == "idle"

def only_here(n):
    return {"safe": n == 0, "onlyHere": n, "machine": HERE_MACHINE,
            "text": "Everything is safe" if n == 0 else
            f"{n} frame{'' if n == 1 else 's'} only on {HERE_WORDS}"}

try:
    with contextlib.redirect_stdout(said):
        IP_LEDGER = os.path.join(panel.eng.STATE_DIR, "ledger.json")
        srv = panel.make_server(0)                      # port 0: any free one
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        url = f"http://127.0.0.1:{srv.server_address[1]}"
        TOKEN["v"] = panel.TOKEN
        ip["port0"] = [panel.PORT, srv.server_address[1]]
        ip["ping0"] = api("/api/ping", url=url)        # the browser's Host names the real port

        # U9: worked out again only when ledger.json changes, and straight
        # after an operation (the 2-second poll is off here)
        ip["first"] = ip_status(url, lambda x: "text" in x)
        n0 = len(computed)
        panel.APP._run("testing", lambda: None, need_camera=False)   # writes nothing
        ip["idle1"] = ip_idle()
        time.sleep(1.5)
        ip["unchanged"] = len(computed) - n0
        panel.APP._run("testing", lambda: ip_ledger(1), need_camera=False)
        ip["idle2"] = ip_idle()
        ip["afterOp"] = ip_status(url, lambda x: x.get("onlyHere") == 1, timeout=15)

        # a failure to work it out: "Status unknown", never the line before
        panel.STATUS_CMD = [sys.executable, "-c", "import sys; sys.exit(3)"]
        ip_ledger(2)
        panel.STATUS.refresh()
        ip["failed"] = ip_status(url, lambda x: x.get("onlyHere") != 1)
        # the app's own command is used when set
        panel.STATUS_CMD = [sys.executable, "-c", "import json; print(json.dumps({'safe': True, "
                            "'onlyHere': 0, 'text': 'from the app', 'machine': 'Mac'}))"]
        ip_ledger(3)
        panel.STATUS.refresh()
        ip["appCmd"] = ip_status(url, lambda x: x.get("text") == "from the app")

        # the default: the engine's --status --json in a child, so this
        # process never builds a State (the whole parsed ledger) for it...
        RealState = panel.eng.State
        made = []

        class CountingState(RealState):
            def __init__(self, *a, **k):
                made.append(1)
                super().__init__(*a, **k)
        panel.eng.State = CountingState
        panel.STATUS_CMD = None
        ip_ledger(4)
        panel.STATUS.refresh()
        ip["child"] = ip_status(url, lambda x: x.get("onlyHere") == 4)
        ip["madeByChild"] = len(made)
        # ...and a frozen app (no Python to run) works it out here, keeping nothing
        sys.frozen = True
        try:
            ip_ledger(5)
            panel.STATUS.refresh()
            ip["frozen"] = ip_status(url, lambda x: x.get("onlyHere") == 5)
        finally:
            del sys.frozen
            panel.eng.State = RealState
        ip["madeFrozen"] = len(made)
        gc.collect()
        ip["alive"] = sum(isinstance(o, RealState) for o in gc.get_objects())

        # U8: /api/quit is refused while an operation runs, and the operation finishes
        gate = threading.Event()

        def slow():
            gate.wait(20)
            panel.APP.last_result = "the slow operation finished"
        panel.APP._run("testing", slow, need_camera=False)
        ip["quitBusy"] = api("/api/quit", {}, url=url)
        ip["stillUp"] = answers(url)
        gate.set()
        ip["idle3"] = ip_idle()
        ip["finished"] = panel.APP.last_result
        # ...and while a card waits for an answer, even with no operation holding the lock
        panel.APP.question = {"id": 424242, "kind": "confirm", "prompt": "test card",
                              "default": "n", "expect": ""}
        try:
            ip["quitCard"] = api("/api/quit", {}, url=url)
            ip["stillUp2"] = answers(url)
        finally:
            panel.APP.question = None
        ip["quitIdle"] = api("/api/quit", {}, url=url)
        t.join(15)
        ip["ended"] = not t.is_alive() and not answers(url)
except Exception as x:
    ip["error"] = repr(x)
check("U10 make_server(0) binds a free port and sets PORT to it, so the page's own requests pass",
      ip.get("port0", [0, 0])[0] == ip.get("port0", [0, 1])[1] != 0
      and (ip.get("ping0") or {}).get("ok") is True, json.dumps(ip)[:400])
check("U9 the status line is not worked out again after an operation that left ledger.json "
      "alone; after one that changed it, it is, straight away (not on a poll)",
      ip.get("idle1") is True and ip.get("unchanged") == 0 and ip.get("idle2") is True
      and ip.get("afterOp") == only_here(1), json.dumps(ip)[:600])
check("U9 when working it out fails, the line says 'Status unknown', never the line before; "
      "an app's own STATUS_CMD is used when set",
      ip.get("failed") == UNKNOWN and (ip.get("appCmd") or {}).get("text") == "from the app",
      json.dumps(ip)[:600])
check("U9 by default the engine's --status --json works it out in a short-lived child: this "
      "process never builds a State (the parsed ledger) for it",
      ip.get("child") == only_here(4) and ip.get("madeByChild") == 0, json.dumps(ip)[:600])
check("U9 ...a frozen app works it out in-process, and no State is kept afterwards",
      ip.get("frozen") == only_here(5) and ip.get("madeFrozen") == 1 and ip.get("alive") == 0,
      json.dumps(ip)[:600])
check("U8 /api/quit while an operation runs: 409 busy, the panel stays up, and the operation "
      "finishes",
      (ip.get("quitBusy") or {}).get("_status") == 409
      and (ip.get("quitBusy") or {}).get("reason") == "busy" and ip.get("stillUp") is True
      and ip.get("idle3") is True and ip.get("finished") == "the slow operation finished",
      json.dumps(ip)[:600])
check("U8 ...and while a question card is pending (no operation holding the lock): 409 busy; "
      "idle again, it quits",
      (ip.get("quitCard") or {}).get("_status") == 409 and ip.get("stillUp2") is True
      and (ip.get("quitIdle") or {}).get("ok") is True and ip.get("ended") is True,
      json.dumps(ip)[:600])

if FAIL:
    show_panel_logs()
print("\n═══════════════════════════════════════")
print(f"  {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
