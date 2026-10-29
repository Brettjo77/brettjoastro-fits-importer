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
import shutil
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_env_helper as teh  # noqa: E402
teh.isolate_runner()   # test mode for this process too

BUILD = os.path.dirname(os.path.abspath(__file__))
PASS = FAIL = SKIPPED = 0
FAILURES = []
DETAIL_CAP = 8000
import atexit, traceback
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

def check(name, cond, detail=""):
    """One check; a callable `cond` is called here and an exception is a FAIL, not a
    crash. Failures are listed again in the summary, whole (1.7.0)."""
    global PASS, FAIL
    if callable(cond):
        try:
            cond = cond()
        except Exception:
            cond, detail = False, traceback.format_exc() + (f"\n{detail}" if detail else "")
    print(("  PASS  " if cond else "  FAIL  ") + name + ("" if cond else f"   {str(detail)[:400]}"))
    if cond:
        PASS += 1
    else:
        FAIL += 1
        FAILURES.append((f"{name}  [test_app.py:{sys._getframe(1).f_lineno}]", str(detail)))

def skip(name):
    global SKIPPED
    SKIPPED += 1
    print(f"  SKIP  {name}")

_SUMMARY_DONE = False
def summary(crash=None):
    global _SUMMARY_DONE
    if _SUMMARY_DONE:
        return
    _SUMMARY_DONE = True
    if crash:
        FAILURES.append(("CRASH: the suite stopped here, later checks did not run", crash))
    if FAILURES:
        try:
            show_panel_logs()
        except Exception:
            pass
    print("\n" + "=" * 51)   # plain ASCII: a PowerShell pipe shows box characters as mojibake
    print(f"  {PASS} passed, {FAIL + (1 if crash else 0)} failed"
          + (f", {SKIPPED} skipped" if SKIPPED else ""))
    for name, detail in FAILURES:
        d = detail if len(detail) <= DETAIL_CAP else detail[:DETAIL_CAP] + f"… [{len(detail) - DETAIL_CAP} more]"
        print(f"  ✗ {name}: {d}")
    sys.stdout.flush()

def _excepthook(tp, val, tb):
    summary("".join(traceback.format_exception(tp, val, tb)))
    sys.exit(1)
sys.excepthook = _excepthook
atexit.register(lambda: summary() if not _SUMMARY_DONE and (PASS or FAIL) else None)

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
                json.dump({"pid": os.getpid(), "started": time.strftime("%Y-%m-%dT%H%M%S"), "what": what}, f)
            api("/api/report", {})
            s = wait_for(lambda s: s["status"] == "idle", timeout=30)
            said[what] = str(s.get("lastResult"))
    finally:
        os.remove(lockp)
    check("U6 the panel's banner says what holds the lock in the engine's own words: "
          "'The ship to the archive is running right now', 'The panel is busy right now'",
          said.get("ship", "").startswith("The ship to the archive is running right now. ")
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
    try:
        with open(os.path.join(env.state, "last-scan.json"), encoding="utf-8") as f:
            _ls = json.load(f)
    except (OSError, ValueError) as e:
        _ls = {"error": str(e)}
    check("OB5 (1.7.5) the scan summary the panel writes names every target with new frames by its display name, "
          "biggest first, and says no other computer holds any (none has a record here)",
          _ls.get("targetNames") == [t["display"] for t in sorted((t for t in s["scan"]["targets"] if t["new"] and not t["skipped"]),
                                                                  key=lambda t: -t["new"])]
          and len(_ls.get("targetNames") or []) >= 3 and _ls.get("elsewhereMachine") is None,
          json.dumps(_ls)[:300])
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
env2.env["ASTRO_ARCHIVE_URL"] = "smb://astro@TESTPC/AstroImageData"   # test mode only records a mount
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

    # ── fix c (1.7.0): the panel's import ships straight away when the share
    #    is already up, as a Terminal import does; it never asks Finder to connect ──
    log1 = [str(x) for x in s.get("log") or []]
    check("T14 with the share down the panel's import says nothing about the archive and "
          "doesn't ask Finder to connect (1.7.0)",
          not any(w in x for x in log1 for w in ("not reachable", "Finder", "Shipped"))
          and not teh.os_calls(env2.root, "mount"),
          json.dumps(log1[-4:]) + json.dumps(teh.os_calls(env2.root))[:300])
    os.makedirs(os.path.join(env2.archive, "S30P"))
    env2.add_seestar_sub("M 33", "20260925-213000")
    api("/api/scan", {}, url=URL2)
    t0 = time.time()
    while time.time() - t0 < 60:
        s = api("/api/state", url=URL2)
        if s["status"] == "idle" and s["scan"]:
            break
        time.sleep(0.3)
    api("/api/import", {"names": ["M 33"]}, url=URL2)
    t0 = time.time()
    while time.time() - t0 < 90:
        s = api("/api/state", url=URL2)
        if s.get("question"):
            api("/api/answer", {"id": s["question"]["id"], "value": "n"}, url=URL2)
        elif s["status"] == "idle" and time.time() - t0 > 1:
            break
        time.sleep(0.3)
    ship_log = os.path.join(env2.archive, "_verify", *(("pc", "shipped-pc.jsonl") if os.name == "nt"
                                                      else ("mac", "shipped.jsonl")))
    try:
        with open(ship_log, encoding="utf-8") as f:
            shipped = [r for r in (json.loads(x) for x in f if x.strip()) if r.get("state") == "shipped"]
    except OSError:
        shipped = []
    on_e = [f for _dp, _dn, fs in os.walk(os.path.join(env2.archive, "S30P")) for f in fs]
    check("T14 with the share up the panel's import files every frame not yet shipped into the "
          "archive straight away, and says so (fix c, 1.7.0)",
          len(shipped) == 3 and len(on_e) == 3
          and any("Shipped 3 file(s)" in str(x) for x in s.get("log") or [])
          and not teh.os_calls(env2.root, "mount"),
          json.dumps([str(x) for x in s.get("log") or []][-6:]) + str(on_e))
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
       "until the archive's sweep checks it" + (" (the 03:30 sweep, then the next ship)" if os.name == "nt" else ""))
check("U9 the status line's tooltip, worded for this computer, explains a count "
      "('… only on this Mac/PC until the archive's sweep checks it')",
      f'const STATUS_TIP="{TIP}";' in page4 and "sl.title=sum.onlyHere?STATUS_TIP" in page4,
      re.findall(r"const STATUS_TIP=.*", page4)[:1])

# ── AP (1.5.4, backlog 13): an astropy that won't load fails only the one job ──
# A fake astropy that raises on import comes first on the panel's PYTHONPATH.
# Before 1.5.4 the engine's sys.exit ended the worker thread: an empty banner,
# no reason, and the page's automatic rescan printed the same red lines again
# every second. Now each job fails with the real reason in the banner, and
# the log says it once.
env5 = teh.Env("APP5", asiair=False, seestar=True)
env5.add_seestar_sub("M 42", "20260119-210000")
FAKE_WHY = "dlopen(_compiler.so): Library not loaded: libfake.dylib (a fake astropy for the test)"
fake5 = os.path.join(env5.root, "fake-astropy")
os.makedirs(os.path.join(fake5, "astropy"))
with open(os.path.join(fake5, "astropy", "__init__.py"), "w", encoding="utf-8") as f:
    f.write(f"raise ImportError({FAKE_WHY!r})\n")
env5.env["PYTHONPATH"] = fake5
PORT5 = int(env5.env["ASTRO_PANEL_PORT"])
URL5 = f"http://127.0.0.1:{PORT5}"
proc5 = start_panel(env5, PORT5)
ap, page5 = {"jobs": []}, ""

def ap_job(path, body):
    """One job on panel 5, to the end: what it started, and the state after."""
    started = api(path, body, url=URL5).get("started")
    t0, s = time.time(), {}
    while time.time() - t0 < 60:
        s = api("/api/state", url=URL5)
        if s.get("status") == "idle" and time.time() - t0 > 0.5:
            break
        time.sleep(0.3)
    red = [ln for ln in s.get("log") or [] if str(ln).startswith("✗")]
    ap["jobs"].append({"started": started, "status": s.get("status"),
                       "lastResult": s.get("lastResult"), "red": len(red)})
    return s

try:
    own_panel(URL5, env5, proc5, "AP a panel whose astropy won't load starts, and answers as itself")
    page5 = load_token(URL5)
    for path, body in (("/api/scan", {}), ("/api/scan", {}), ("/api/import", {"names": ["M 42"]}),
                       ("/api/scan", {})):
        s = ap_job(path, body)
    ap["log"] = [str(ln) for ln in s.get("log") or []]
    ap["alive"] = proc5.poll() is None and api("/api/ping", url=URL5).get("ok") is True
    ap["copied"] = [n for _d, _s, fs in os.walk(env5.sdest30) for n in fs]
finally:
    proc5.terminate()
    proc5.wait(timeout=30)
with open(os.path.join(env5.root, "panel.log"), encoding="utf-8", errors="replace") as f:
    ap["traceback"] = "Traceback" in f.read()
WHY5 = f"ImportError: {FAKE_WHY}"
jobs = ap["jobs"]
check("AP each job fails on its own with the real reason in the banner ('scanning failed: "
      "astropy could not be loaded (ImportError: …)'), and the panel stays up for the next",
      len(jobs) == 4 and all(j["started"] is True and j["status"] == "idle" for j in jobs)
      and all(str(j["lastResult"]).startswith(
          f"{w} failed: astropy could not be loaded ({WHY5}). ")
          for j, w in zip(jobs, ("scanning", "scanning", "importing", "scanning")))
      and ap.get("alive") is True and ap.get("copied") == [] and ap.get("traceback") is False,
      json.dumps(ap)[:700])
fix5 = [ln for ln in ap.get("log", []) if sys.executable in ln and "-m pip install" in ln]
check("AP the log says why once, with the command for this Python; later jobs add no red "
      "lines, and a failed scan stops the page's automatic rescan",
      sum(FAKE_WHY in ln for ln in ap.get("log", [])) == 1 and len(fix5) == 1
      and len(jobs) == 4 and jobs[0]["red"] > 0 and len({j["red"] for j in jobs}) == 1
      and '!(s.lastResult||"").startsWith("scanning failed")' in page5,
      json.dumps({"jobs": jobs, "log": ap.get("log", [])[-8:]})[:700])

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

# ── AP (1.5.4): a job the engine ends with sys.exit stops only that job ──
# (the engine's other sys.exit calls, a newer importer's ledger at the save
# for one, reach the panel's worker thread the same way)
apx = {}
try:
    with contextlib.redirect_stdout(said):
        apx["started"] = panel.APP._run("testing", lambda: sys.exit(2), need_camera=False)
        apx["idle"] = ip_idle()
        apx["said"] = panel.APP.last_result
        apx["log"] = [ln for ln in list(panel.APP.log)[-3:] if ln.startswith("✗")]
        apx["next"] = panel.APP._run("testing", lambda: None, need_camera=False)
        apx["idle2"] = ip_idle()
except Exception as x:
    apx["error"] = repr(x)
check("AP a job the engine ends with sys.exit fails on its own: idle again, the banner and "
      "one red line say so, and the next job runs",
      apx.get("started") is True and apx.get("idle") is True
      and apx.get("said") == "testing failed: the engine stopped it (exit code 2). The log says why."
      and apx.get("log") == ["✗ testing stopped by the engine (exit code 2)"]
      and apx.get("next") is True and apx.get("idle2") is True, json.dumps(apx))

# ── AP (1.5.4): in the app the astropy banner fits the app ──
# The app runs this panel in-process, frozen: there is no pip to run against
# it, and no panel to restart. sys.frozen is forced here for one job.
apf, had_frozen = {}, hasattr(sys, "frozen")

def no_astropy():
    raise panel.eng.FitsUnavailable("ImportError: libfake.dylib (the test)")

try:
    with contextlib.redirect_stdout(said):
        for key, frozen in (("web", False), ("app", True)):
            try:
                if frozen:
                    sys.frozen = True
                apf[key + "Started"] = panel.APP._run("scanning", no_astropy, need_camera=False)
                apf[key + "Idle"] = ip_idle()
                apf[key] = panel.APP.last_result
            finally:
                if not had_frozen and hasattr(sys, "frozen"):
                    del sys.frozen
except Exception as x:
    apf["error"] = repr(x)
AP_BANNER = "scanning failed: astropy could not be loaded (ImportError: libfake.dylib (the test)). "
check("AP in the app (sys.frozen forced) the astropy banner says to reinstall FITs Importer App, "
      "then restart the app (no pip command, no panel to restart); the web panel's words are "
      "unchanged",
      apf.get("web") == AP_BANNER + "Install or repair it (the log shows the command), then "
                                    "restart the panel."
      and apf.get("app") == AP_BANNER + "Reinstall FITs Importer App, then restart the app."
      and all(apf.get(k) is True for k in ("webStarted", "webIdle", "appStarted", "appIdle"))
      and hasattr(sys, "frozen") == had_frozen, json.dumps(apf))

# ── U12 (1.5.4): the panel binds without a reverse DNS lookup ──
# http.server's own bind asks socket.getfqdn() for the host's name. In the
# packaged app on the Mac nothing answered, and the panel started 35 s late.
# Here the lookup hangs for 3 s and every call is counted.
u12, asked = {}, []
real_getfqdn = socket.getfqdn

def hanging_getfqdn(name=""):
    asked.append(name)
    time.sleep(3)
    return name

socket.getfqdn = hanging_getfqdn
try:
    with contextlib.redirect_stdout(said):
        t0 = time.time()
        srv = panel.make_server(0)
        u12["secs"] = round(time.time() - t0, 2)
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        url = f"http://127.0.0.1:{srv.server_address[1]}"
        u12["ping"] = api("/api/ping", url=url)
        u12["want"] = teh.instance_id(panel.eng.STATE_DIR)
        u12["name"] = [srv.server_name, srv.server_port, srv.server_address[1], panel.PORT]
        so = socket.SOL_SOCKET
        if os.name == "nt":      # one panel per port: exclusive, and no SO_REUSEADDR
            u12["rules"] = [bool(srv.socket.getsockopt(so, socket.SO_EXCLUSIVEADDRUSE)),
                            bool(srv.socket.getsockopt(so, socket.SO_REUSEADDR))] == [True, False]
        else:                    # ...and no SO_REUSEPORT, which lets a second process bind it too
            u12["rules"] = [bool(srv.socket.getsockopt(so, socket.SO_REUSEADDR)),
                            bool(srv.socket.getsockopt(so, socket.SO_REUSEPORT))] == [True, False]
        srv.shutdown()
        srv.server_close()
        t.join(10)
except Exception as x:
    u12["error"] = repr(x)
finally:
    socket.getfqdn = real_getfqdn
u12["asked"] = asked
check("U12 make_server never asks socket.getfqdn (made to hang 3 s): it returns in under "
      "1 s, and the panel answers as itself",
      u12.get("asked") == [] and u12.get("secs", 99) < 1
      and (u12.get("ping") or {}).get("ok") is True and u12.get("want")
      and (u12.get("ping") or {}).get("instance") == u12["want"], json.dumps(u12))
check("U12 ...with today's bind rules (SO_REUSEADDR and no SO_REUSEPORT on the Mac; "
      "SO_EXCLUSIVEADDRUSE and no SO_REUSEADDR on Windows: one panel per port), server_name "
      "the address itself and server_port the port bound",
      u12.get("rules") is True and u12.get("name", [0])[0] == "127.0.0.1"
      and len(set(u12.get("name", [0, 1])[1:])) == 1, json.dumps(u12))

# ── AD (1.6.0): Astro Desk, the Archive tab, opens the archive read-only ──
# The tab lists what is still to process and opens folders, image files and
# Siril there. A request without the token, a path outside the archive or a
# program file is refused; in test mode every open is recorded, never done.
envd = teh.Env("APPAD", asiair=False, seestar=False)
ad_arch = envd.archive
def ad_put(*parts):
    p = os.path.join(ad_arch, *parts)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(b"\0" * 16)
ad_wiz = ("ZWO Askar Scopes", "Wizard Nebula (NGC 7380)")
ad_put(*ad_wiz, "Wizard Nebula Day 1", "Light_001.fit")
ad_put(*ad_wiz, "WBPP", "masterLight_LUltimate.xisf")
ad_put(*ad_wiz, "Run me.exe")
ad_put(*ad_wiz, "shortcut.lnk")
for r in ("S30P", "S30", "S50", "S50P"):
    os.makedirs(os.path.join(ad_arch, r), exist_ok=True)
ad_ds = os.path.join(envd.root, "obs", "dataset.json")
os.makedirs(os.path.dirname(ad_ds))
with open(ad_ds, "w", encoding="utf-8") as f:
    json.dump({"generatedAt": "2026-10-02 08:00", "targets": [{
        "name": "Wizard Nebula", "codes": ["NGC 7380"], "state": "stacked",
        "programmes": [{"camera": "ASIAir", "hours": 7.5, "nights": 1,
                        "path": "D:\\Astro Image Data\\ZWO Askar Scopes\\Wizard Nebula (NGC 7380)"}],
        "statusCards": [{"camera": "ASIAir", "state": "stacked", "evidence": "1 master"}]}]}, f)
ad_siril = os.path.join(envd.root, "apps", "siril")
os.makedirs(os.path.dirname(ad_siril))
with open(ad_siril, "w") as f:
    f.write("#!/bin/sh\n")
envd.env.update({"ASTRO_OBSERVATORY_DATASET": ad_ds, "ASTRO_SIRIL_EXE": ad_siril})

def ad_tree():
    out = {}
    for root, dirs, fns in os.walk(ad_arch):
        for n in dirs + fns:
            p = os.path.join(root, n)
            out[p] = (os.path.getsize(p) if os.path.isfile(p) else -1, os.path.getmtime(p))
    return out

PORTD = int(envd.env["ASTRO_PANEL_PORT"])
URLD = f"http://127.0.0.1:{PORTD}"
procd = start_panel(envd, PORTD)
try:
    own_panel(URLD, envd, procd, "AD the Astro Desk panel answers with its own instance id")
    tree0 = ad_tree()
    page = urllib.request.urlopen(URLD + "/archive?target=Wizard%20Nebula", timeout=10).read().decode()
    check("AD /archive serves the panel page with its token and the Archive tab",
          'data-tab="archive"' in page and 'id="tab-archive"' in page
          and re.search(r'const TOKEN="[^"]{24,}"', page) is not None)
    load_token(URLD)
    idx = api("/api/archive/index", url=URLD)
    wiz = [i for i in idx.get("items", []) if i.get("rel") == "/".join(ad_wiz)]
    check("AD /api/archive/index joins the dataset (state stacked, 7.5 h) to this archive",
          idx.get("datasetFound") is True and wiz and wiz[0]["state"] == "stacked"
          and wiz[0]["hours"] == 7.5 and idx.get("sirilFound") is True, json.dumps(idx)[:400])
    lst = api("/api/archive/list?rel=" + urllib.parse.quote("/".join(ad_wiz)), url=URLD)
    check("AD /api/archive/list sorts the folder: 1 night with 1 frame, 1 master",
          [n["frames"] for n in lst.get("nights", [])] == [1]
          and [m_["name"] for m_ in lst.get("masters", [])] == ["masterLight_LUltimate.xisf"],
          json.dumps(lst)[:400])
    bad_list = api("/api/archive/list?rel=" + urllib.parse.quote("../state"), url=URLD)
    check("AD listing a path outside the archive is a 404", bad_list.get("_status") == 404, json.dumps(bad_list))

    tok = TOKEN["v"]
    TOKEN["v"] = ""
    no_tok = api("/api/archive/open", {"rel": "/".join(ad_wiz)}, url=URLD)
    TOKEN["v"] = tok
    check("AD opening without the per-launch token is refused (403) and opens nothing",
          no_tok.get("_status") == 403 and not teh.os_calls(envd.root, "open"), json.dumps(no_tok))
    r_folder = api("/api/archive/open", {"rel": "/".join(ad_wiz)}, url=URLD)
    r_master = api("/api/archive/open", {"rel": "/".join(ad_wiz + ("WBPP", "masterLight_LUltimate.xisf"))}, url=URLD)
    r_exe = api("/api/archive/open", {"rel": "/".join(ad_wiz + ("Run me.exe",))}, url=URLD)
    r_lnk = api("/api/archive/open", {"rel": "/".join(ad_wiz + ("shortcut.lnk",))}, url=URLD)
    r_out = api("/api/archive/open", {"rel": "../state"}, url=URLD)
    r_abs = api("/api/archive/open", {"rel": envd.state}, url=URLD)
    opens = teh.os_calls(envd.root, "open")
    check("AD a folder and a master open (recorded in test mode, inside the archive); a program, "
          "a shortcut, a path outside and an absolute path are refused and open nothing",
          r_folder.get("ok") is True and r_master.get("ok") is True
          and [r.get("_status") for r in (r_exe, r_lnk, r_out, r_abs)] == [400] * 4
          and len(opens) == 2 and all(o.get("target", "").startswith(ad_arch) for o in opens),
          json.dumps([r_folder, r_master, r_exe, r_lnk, r_out, r_abs, opens])[:600])
    r_siril = api("/api/archive/siril", {"rel": "/".join(ad_wiz)}, url=URLD)
    launches = teh.os_calls(envd.root, "launch")
    check("AD 'Start Siril here' runs Siril with -d and the target folder (recorded, not started)",
          r_siril.get("ok") is True and len(launches) == 1
          and launches[0].get("args") == ["-d", os.path.join(ad_arch, *ad_wiz)],
          json.dumps([r_siril, launches]))
    os.rename(ad_siril, ad_siril + ".moved")
    r_nosiril = api("/api/archive/siril", {"rel": "/".join(ad_wiz)}, url=URLD)
    r_sfile = api("/api/archive/siril", {"rel": "/".join(ad_wiz + ("WBPP", "masterLight_LUltimate.xisf"))}, url=URLD)
    check("AD with Siril missing the answer says where to set ASTRO_SIRIL_EXE; Siril only starts in a folder",
          r_nosiril.get("ok") is False and "ASTRO_SIRIL_EXE" in (r_nosiril.get("error") or "")
          and r_sfile.get("_status") == 400 and len(teh.os_calls(envd.root, "launch")) == 1,
          json.dumps([r_nosiril, r_sfile]))
    # ── the project layer on the Archive tab (1.7) ─────────────────────────
    check("PL the Archive tab carries the To-process section and its loader",
          'id="deskProjects"' in page and "loadProjects" in page and "data-xopen" in page)
    # The page's script, parse-checked and the new section rendered, in node
    # (a syntax slip anywhere in the inline script would blank every tab)
    import shutil as _sh
    node = _sh.which("node") or next((p for p in ("/opt/node22/bin/node", "/usr/local/bin/node")
                                      if os.path.isfile(p)), None)
    script = re.search(r"<script>(.*?)</script>", page, re.S)
    if node and script:
        r_parse = subprocess.run([node, "-e", "new Function(require('fs').readFileSync(0,'utf8'))"],
                                 input=script.group(1), capture_output=True, text=True, timeout=30)
        check("PL the panel's inline script parses (node)", r_parse.returncode == 0,
              r_parse.stderr[-300:])
        js = script.group(1)
        pieces = [re.search(p_, js, re.S).group(0) for p_ in
                  (r"const MONTHS=[^\n]*", r"const esc=[^\n]*", r"const fmtNight=[^\n]*",
                   r"const PROJ_WHERE=.*?\nfunction projectsHtml\(pj, opts\)\{.*?\n\}\n")]
        fixture = {"ok": True, "opener": "Finder", "command": "python3 ~/bin/astro-import.py --projects",
                   "projects": {"schema": "projects/1", "generated_at": "2026-10-10T08:00:00+00:00",
                                "quiet_period_days": 14, "warnings": ["one warning"],
                                "projects": [{"target_id": "NGC7380", "name": "Wizard <b>Nebula</b>",
                                              "datasets": [
                       {"scope": "FRA400", "scope_name": "Askar FRA400", "site": "Shinfield",
                        "status": "ready_to_process", "nights": 3, "integration_seconds": 27000,
                        "last_session": "2026-09-01", "locations": ["chillblast_archive"],
                        "archive_rel": "/".join(ad_wiz)},
                       {"scope": "S50P", "scope_name": "Seestar S50 Pro", "site": "Shinfield",
                        "status": "in_progress", "nights": 1, "integration_seconds": 100,
                        "last_session": "2026-09-10", "locations": ["chillblast_archive"],
                        "archive_rel": "S50P/Wizard Nebula (NGC 7380)", "calibration": {"applies": False}},
                       {"scope": "S30P", "status": "capturing", "nights": 1, "integration_seconds": 100,
                        "last_session": "2026-10-08", "locations": ["mac-unchecked"], "archive_rel": None}]}]}}
        fixture["projects"]["sources"] = {"snapshots": [{"machine": "Mac", "at": "2026-10-01T08:00:00Z",
                                                          "rows": 5, "age_hours": 240.0}]}
        fixture["projects"]["projects"][0]["datasets"][1]["masters"] = ["masterLight_HOO.xisf"]
        fixture["projects"]["projects"][0]["datasets"][0]["calibration"] = {"applies": True, "darks": 20, "flats": 0, "biases": 50, "shipped": 20, "nights_with": 2, "nights": 3, "missing": ["flats"]}
        fixture["projects"]["warnings"].append("43 target name(s) the contract doesn't know")
        harness = ("let deskSel=null;\n" + "\n".join(pieces) +
                   f"\nprocess.stdout.write(projectsHtml({json.dumps(fixture)}));\n"
                   f"process.stdout.write('\\n---\\n'+projectsHtml({{ok:false,why:'missing',command:'py -3 x'}}));\n"
                   f"process.stdout.write('\\n---\\n'+projectsHtml({json.dumps(fixture)}, {{scope:'Askar FRA400'}}));\n"
                   f"process.stdout.write('\\n---\\n'+projectsHtml({{ok:false,why:'unreadable'}}));\n")
        r_html = subprocess.run([node, "-e", harness], capture_output=True, text=True, timeout=30)
        html, _, rest = r_html.stdout.partition("\n---\n")
        missing, _, rest = rest.partition("\n---\n")
        filtered, _, unreadable = rest.partition("\n---\n")
        check("PL projectsHtml renders the fixture: the name escaped, the dataset's folder on the "
              "button labelled for this computer, hours and nights, the warning, when it was worked "
              "out, and the capturing one's ready-from date; nothing reads 'undefined'",
              r_html.returncode == 0 and "Wizard &lt;b&gt;Nebula&lt;/b&gt;" in html
              and "<b>" not in html and f'data-xopen="{"/".join(ad_wiz)}"' in html
              and "Open in Finder" in html and "7.5 h" in html and "3 nights" in html
              and "⚠ one warning" in html and "Worked out 10 Oct 2026" in html
              and "ready from 23 Oct 2026" in html and "2 min" in html
              and "undefined" not in html and "To process · 1" in html
              and "calibration: 20 darks · 50 bias · no flats" in html and html.count("calibration:") == 1
              and "In progress · 1" in html and "1 still capturing" in html,
              (r_html.stderr or html)[-500:])
        check("PL without projects.json the section says plainly what to run, and where",
              "hasn't been worked out on this computer yet" in missing and "py -3 x" in missing
              and 'id="deskRefresh"' in missing, missing[-300:])
        check("PL (12 Oct) each row says why it is where it is, the sections are collapsible with "
              "To process open, there is a legend, a scope filter with counts, a Refresh button, the "
              "Mac's record and its age, the unknown-names warning stands out, and 'per its ledger' "
              "is said for a frame the Mac's snapshot could not vouch for",
              "nothing new since 1 Sep 2026" in html and "master saved on the archive: masterLight_HOO.xisf" in html
              and "last night 8 Oct 2026 · ready from 23 Oct 2026" in html
              and '<details class="ad-sec" open><summary class="eyebrow">To process · 1' in html
              and '<details class="ad-sec"><summary class="eyebrow">In progress · 1' in html
              and "Still capturing · 1" in html and 'class="ad-legend"' in html
              and '<select id="deskScope"' in html and "All scopes (3)" in html and "Askar FRA400 (1)" in html
              and 'id="deskRefresh"' in html and "from Mac's record as of 1 Oct 2026 (10 days old)" in html
              and '<p class="ad-warn">⚠ 43 target name(s)' in html
              and "on this Mac (per its ledger)" in html,      # rendered as the Mac (the page's default sides, 1.7.1)
              html[-1200:])
        check("PL the scope filter keeps only that scope's rows, and an unreadable list says so without a crash",
              "To process · 1" in filtered and "In progress · " not in filtered and "Still capturing · " not in filtered
              and "couldn't be read" in unreadable and 'id="deskRefresh"' in unreadable,
              filtered[-300:] + unreadable[-300:])
    else:
        skip("PL node isn't installed: the inline script's parse check and the rendered "
              "To-process section")
    statuses = set(re.findall(r'sect\("[^"]+","([a-z_]+)"\)', page)) | \
        set(re.findall(r'status==="([a-z_]+)"', page))
    check("PL every status string the page uses is one the engine writes",
          statuses and statuses <= {"capturing", "ready_to_process", "in_progress", "done", "sample"},   # "sample" since phase 1 (25 Oct)
          str(statuses))
    pj0 = api("/api/projects", url=URLD)
    check("PL /api/projects before --projects has run: ok false, so the tab says to run it "
          "and falls back to the Observatory list",
          pj0.get("ok") is False and pj0.get("projects") is None, json.dumps(pj0))
    os.makedirs(envd.state, exist_ok=True)
    with open(os.path.join(envd.state, "projects.json"), "w", encoding="utf-8") as f:
        json.dump({"schema": "projects/1", "generated_at": "2026-10-10T08:00:00+00:00",
                   "quiet_period_days": 14, "sources": {}, "warnings": [],
                   "projects": [{"target_id": "NGC7380", "name": "Wizard Nebula",
                                 "status": "ready_to_process", "to_process": True,
                                 "last_captured": "2026-09-01", "integration_seconds": 27000,
                                 "datasets": [
                       {"scope": "FRA400", "scope_name": "Askar FRA400", "site": "Shinfield",
                        "status": "ready_to_process", "capture_state": "auto", "nights": 3,
                        "frames": 90, "integration_seconds": 27000,
                        "first_session": "2026-08-20", "last_session": "2026-09-01",
                        "locations": ["chillblast_archive"],
                        "archive_rel": "/".join(ad_wiz)},
                       {"scope": "S30P", "scope_name": "Seestar S30 Pro", "site": "Shinfield",
                        "status": "capturing", "capture_state": "auto", "nights": 1,
                        "frames": 10, "integration_seconds": 100,
                        "first_session": "2026-10-08", "last_session": "2026-10-08",
                        "locations": ["mac"], "archive_rel": None}]}]}, f)
    pj = api("/api/projects", url=URLD)
    pj_ds = (pj.get("projects") or {}).get("projects", [{}])[0].get("datasets", [{}])[0]
    check("PL /api/projects serves projects.json once it exists, with the opener's name "
          "for the button",
          pj.get("ok") is True and pj.get("opener") in ("Explorer", "Finder")
          and pj_ds.get("archive_rel") == "/".join(ad_wiz), json.dumps(pj)[:300])
    opens_before = len(teh.os_calls(envd.root, "open"))
    r_open = api("/api/archive/open", {"rel": pj_ds["archive_rel"]}, url=URLD)
    opens_now = teh.os_calls(envd.root, "open")
    check("PL Open in Explorer/Finder from a To-process row opens the dataset's target "
          "folder on the archive (recorded in test mode)",
          r_open.get("ok") is True and len(opens_now) == opens_before + 1
          and opens_now[-1].get("target") == os.path.join(ad_arch, *ad_wiz),
          json.dumps([r_open, opens_now[-2:]]))
    with open(os.path.join(envd.state, "projects.json"), "w", encoding="utf-8") as f:
        json.dump({"schema": "projects/1", "generated_at": "x", "quiet_period_days": 14,
                   "sources": {}, "warnings": [], "projects": [
                       {"target_id": "X", "name": "X", "status": "ready_to_process",
                        "to_process": True, "last_captured": "2026-09-01",
                        "integration_seconds": 0, "datasets": [
                            {"scope": "S30P", "status": "ready_to_process",
                             "archive_rel": "../state"}]}]}, f)
    r_bad = api("/api/archive/open", {"rel": "../state"}, url=URLD)
    check("PL a hand-edited projects.json cannot point the open outside the archive",
          r_bad.get("_status") == 400 and len(teh.os_calls(envd.root, "open")) == opens_before + 1,
          json.dumps(r_bad))
    os.remove(os.path.join(envd.state, "projects.json"))
    # (12 Oct) the page knows when it is stale; a failed open never reads "Opened"
    st = api("/api/state", url=URLD)
    check("PL /api/state carries the panel's boot id and version, and the page carries the same boot id",
          isinstance(st.get("boot"), str) and len(st["boot"]) == 16 and st.get("version") == api("/api/ping", url=URLD).get("version")
          and f'const BOOT="{st["boot"]}"' in page and "function showStale" in page
          and "s.boot!==BOOT" in page, json.dumps([st.get("boot"), st.get("version")]))
    r_rebuild = api("/api/projects/rebuild", {}, url=URLD)
    check("PL the Refresh button rebuilds projects.json in the panel (the engine's own --projects, one at a time)",
          r_rebuild.get("ok") is True and os.path.isfile(os.path.join(envd.state, "projects.json"))
          and "Wrote" in (r_rebuild.get("said") or ""), json.dumps(r_rebuild)[-400:])
    os.remove(os.path.join(envd.state, "projects.json"))
    check("AD read-only: after all of it the archive is exactly as it was (no _verify probe)",
          ad_tree() == tree0 and not os.path.exists(os.path.join(ad_arch, "_verify")))
finally:
    procd.terminate()
    procd.wait(timeout=30)


print("\n── Chain NL: a panel on a computer that never imported (the archive PC) ──")
envn = teh.Env("NL", asiair=False, seestar=False)
shutil.copytree(os.path.join(BUILD, "contract"), os.path.join(envn.root, "contract"))
shutil.copy(os.path.join(BUILD, "astro-observatory.html"), os.path.join(envn.root, "astro-observatory.html"))
envn.env.update({"ASTRO_CONTRACT_DIR": os.path.join(envn.root, "contract"), "ASTRO_SHIP_FOLDER": "pc",
                 "ASTRO_OBSERVATORY_TEMPLATE": os.path.join(envn.root, "astro-observatory.html"),
                 # the fixture's one 10 s frame must still read as a real dataset, not a
                 # sample (the 1.8.0 rule); the HN checks cover samples with their own fixture
                 "ASTRO_SAMPLE_MINUTES": "0"})
os.makedirs(os.path.join(envn.archive, "S30P"), exist_ok=True)
PORTN = int(envn.env["ASTRO_PANEL_PORT"])
URLN = f"http://127.0.0.1:{PORTN}"
procn = start_panel(envn, PORTN)
try:
    own_panel(URLN, envn, procn, "NL the no-ledger panel answers with its own instance id")
    def get_dash():
        with urllib.request.urlopen(URLN + "/dashboard?t=1", timeout=15) as resp:
            return resp.status, resp.headers.get("X-Frame-Options"), resp.read().decode()
    code, xfo, body = get_dash()
    check("NL the Dashboard tab on a computer with no ledger is a plain sentence (200, framable), not a browser error page",
          code == 200 and xfo == "SAMEORIGIN" and "Nothing has been imported on this" in body
          and "NoneType" not in body, f"{code} {xfo} {body[-200:]}")
    def get_obs():
        with urllib.request.urlopen(URLN + "/observatory?t=1", timeout=30) as resp:
            return resp.status, resp.headers.get("X-Frame-Options"), resp.read().decode()
    code, xfo, body = get_obs()
    check("OB the Observatory tab before anything was worked out is a plain sentence naming Refresh (200, framable)",
          code == 200 and xfo == "SAMEORIGIN" and "hasn't been worked out" in body and "Refresh" in body
          and "<script id=\"dataset\"" not in body, f"{code} {xfo} {body[-200:]}")
    with urllib.request.urlopen(URLN + "/", timeout=15) as resp:
        _pagen = resp.read().decode()
    check("OB the panel's tabs lead with the job (Panel, To process, Observatory, Ledger, Report), each with a "
          "tooltip; the Observatory tab frames /observatory, has its own Refresh, fills the window (flex), and "
          "listens only to its own frame for open / show requests",
          lambda: [m.group(1) for m in re.finditer(r'data-tab="([a-z]+)"[^>]*title="', _pagen)]
                  == ["panel", "archive", "observatory", "dash", "report"]
          and ">To process</button>" in _pagen and 'id="obsFrame"' in _pagen and '"/observatory?t="' in _pagen
          and 'id="obsRefresh"' in _pagen and "#tab-observatory{flex:1;min-height:0" in _pagen
          and "e.source!==fr.contentWindow" in _pagen and 'd.kind==="archive-open"' in _pagen
          and 'd.kind==="archive-show"' in _pagen and 'd.kind==="observatory-ready"' in _pagen,
          _pagen[:200])
    check("OB5 (1.7.5) the panel's own 'Worked out … Refresh now' row goes once the page says it is ready (the "
          "page carries the freshness line and Refresh), comes back while the frame loads or is a note; the page's "
          "Refresh and 'Open the Panel' arrive as observatory-refresh and open-panel and nothing else is accepted; "
          "the footer line is off the Observatory tab; 'see Data checks', never 'Data health'",
          lambda: 'd.kind==="observatory-refresh"' in _pagen and '$("#obsRefresh").click()' in _pagen
          and 'd.kind==="open-panel"' in _pagen and "data-tab=\"panel\"]'); if(b) b.click();" in _pagen
          and '$("#obsHead").style.display="none"' in _pagen and '$("#obsHead").style.display=""' in _pagen
          and 'b.dataset.tab==="observatory"?"none":""' in _pagen and "(see Data health)" not in _pagen,
          _pagen[:200])
    os.makedirs(os.path.join(envn.archive, "_verify", "mac"))
    with open(os.path.join(envn.archive, "_verify", "mac", "ledger-snapshot.json"), "w") as f:
        json.dump({"schema": "ledger-snapshot/1", "machine": "Mac", "machineId": "mac", "machineUid": "m",
                   "at": "2026-10-01T08:00:00Z", "customNames": {},
                   "files": {"a": {"filename": "Light_M 31_10.0s_20260901-220000.fit", "target": "M 31",
                                   "displayName": "M 31 - Andromeda", "night": "2026-09-01", "sourceType": "sub",
                                   "exposureSeconds": 10.0, "size": 4, "sha256": "aa" * 32, "device": "seestar",
                                   "scope": "Seestar S30 Pro", "here": True}}}, f)
    code, xfo, body = get_dash()
    check("NL with the Mac's snapshot on the archive the Dashboard shows the Mac's record, with a banner saying so and how old it is",
          code == 200 and xfo == "SAMEORIGIN" and "This is the Mac's record" in body and "2026-10-01" in body
          and "day(s) ago" in body and "M 31" in body and "__DATA__" not in body, f"{code} {xfo} {body[:300]}")
    # the Refresh button's endpoint writes projects.json and observatory.json; the tab reads the file
    load_token(URLN)
    _rb = api("/api/projects/rebuild", {}, url=URLN)
    code, xfo, body = get_obs()
    _m = re.search(r'<script id="dataset" type="application/json">(.*?)</script>', body, re.S)
    _dsn = {}
    try:
        _dsn = json.loads(_m.group(1)) if _m else {}
    except ValueError as e:
        _dsn = {"error": str(e)}
    check("OB after Refresh the Observatory renders the Mac's record from observatory.json: the page, its "
          "dataset, Andromeda by its code, one session, the snapshot named, no slot left",
          lambda: _rb.get("ok") is True and os.path.isfile(os.path.join(envn.state, "observatory.json"))
          and code == 200 and xfo == "SAMEORIGIN" and "Astro Archive Observatory" in body and "__DATASET__" not in body
          and _dsn.get("schema") == "observatory/1" and [x["name"] for x in _dsn.get("targets", [])] == ["Andromeda Galaxy (M 31)"]
          and len(_dsn.get("sessions", [])) == 1 and _dsn["inputs"]["snapshot"]["machine"] == "Mac"
          and _dsn["targets"][0]["statusCards"][0]["state"] == "stacked" and "<" not in _m.group(1)
          and "What each scope captured" in body and "Needs your attention" in body,
          f"{code} {xfo} rb={json.dumps(_rb)[:200]} " + (json.dumps(_dsn)[:400] if _dsn else body[:300]))
    check("OB (1.7.2) every scope row opens the scope: a scope's name in the six-scope strip, its share-bar "
          "slice and its Equipment card open the scope panel (openScope -> scopePanelFor: one row per object, "
          "90 nights / a year / everything, the quiet band), and every dot opens the night panel (openNight)",
          lambda: "function openScope(cam)" in body and "function scopePanelFor(cam" in body
          and body.count("openScope(") >= 4 and "function openNight(cam,night,target,host" in body
          and "function nightPanelFor(cam,night,target)" in body
          and '["90","90 nights",90],["365","a year",365],["all","everything",' in body
          and "what it has been doing" in body and "Timeline of its projects" in body,
          body[:200])
    check("OB5 (1.7.5) the page opens on the history: the Recent nights ledger (a week / 14 / 30 nights, blank "
          "nights collapsed, the pending-import line naming the targets with 'Open the Panel to import'), the scope "
          "chart rebuilt (tiles, the moon from the date, all-scopes columns, one row per scope, a selected night with "
          "Previous / Next, resting scopes folded), What each scope shot, cards with one row per scope and one lane "
          "per scope, one freshness line, Refresh and Key in the bar; no 'Data health', no stamp in the bar",
          lambda: "function renderRecent(card,changed)" in body and 'id="pendLine"' in body
          and "Open the Panel to import" in body and "no frames on any scope" in body
          and "nights after it are not in this list" in body and "function chartData(N)" in body
          and "function moonAt(night)" in body and "29.530588853" in body
          and "Nights with the moon under half lit" in body and "Biggest night" in body
          and "Resting this period" in body and "length is hours imaged" in body
          and "function renderShotBars(box,d)" in body and "What each scope shot" in body
          and "function latestTxt(t)" in body and "mosaic on the " in body and '"srow"' in body
          and "Built on the " in body and 'id="refreshBtn"' in body and 'id="keyBtn"' in body
          and 'kind:"observatory-refresh"' in body and 'kind:"open-panel"' in body
          and "ready to process from " in body and "Data health" not in body and 'id="asof"' not in body
          and "a grey dot is a night on more than one" not in body and "http://" not in body.replace("http://www.w3.org/2000/svg", ""),
          body[:200])
    check("OB (16 Oct, 1.7.2) the page normalises a thin dataset (missing keys filled once, a null pendingImport "
          "stays null so the page never claims a camera is empty, an unknown state falls back), the drawer is a "
          "dialog, the tooltip is hidden from readers, and scope colour comes only from the dataset (no palette)",
          lambda: "function normalise(d)" in body and "reconciliation:[],warnings:[]" in body
          and "v===null?null:" in body and "stageOf(" in body and "function showDrawer(" in body
          and '<div class="tt" id="tt" aria-hidden="true" role="tooltip">' in body
          and "const CAMORDER" not in body and "--cam-s30p" not in body
          and 'const col=cam=>(BY[cam]&&BY[cam].colour)||"var(--muted)"' in body,
          body[:200])
    # 1.7.2: the page's live refresh: the status carries the Observatory's stamp, and the dataset
    # alone is one GET away (same token and origin rules as the page)
    _stq = {"observatory": api("/api/observatory/status", url=URLN)}
    with urllib.request.urlopen(URLN + "/observatory?json=1&t=2", timeout=30) as resp:
        _dsj = json.loads(resp.read().decode())
    check("OB (1.7.2) /api/observatory/status carries the Observatory's stamp (the dataset's generatedAtIso) and "
          "whether a rebuild is running, and /observatory?json=1 returns the dataset itself with the new facts",
          lambda: isinstance(_stq.get("observatory"), dict) and _stq["observatory"]["generatedAtIso"] == _dsn.get("generatedAtIso")
          and _stq["observatory"]["rebuilding"] is False
          and _dsj.get("schema") == "observatory/1" and _dsj.get("generatedAtIso") == _dsn.get("generatedAtIso")
          and isinstance(_dsj.get("notCounted"), dict) and isinstance(_dsj.get("notices"), list)
          and "scopeOrder" in _dsj and "pendingImport" in _dsj
          and _dsj["targets"][0]["programmes"][0].get("captureState") == "auto"
          and isinstance(_dsj["targets"][0]["programmes"][0].get("sessions"), list),
          json.dumps([_stq.get("observatory"), {k: _dsj.get(k) for k in ("schema", "notCounted", "scopeOrder", "pendingImport")}])[:600])
    # the review round of 17 Oct: a scan with no camera leaves no scan summary; what is still on a
    # camera is THIS computer's last scan, merged at serve time even into a published record
    api("/api/scan", {}, url=URLN)
    _t0 = time.time()
    while time.time() - _t0 < 60 and api("/api/state", url=URLN).get("status") != "idle":
        time.sleep(0.3)
    _no_sum = not os.path.isfile(os.path.join(envn.state, "last-scan.json"))
    with open(os.path.join(envn.state, "last-scan.json"), "w") as f:
        json.dump({"schema": "scan-summary/1", "files": 3559, "targets": 29, "camera": "Seestar",
                   "failedEject": True, "seenAt": "2026-10-16T08:50:00+00:00", "machine": "PC"}, f)
    with urllib.request.urlopen(URLN + "/observatory?json=1&t=3", timeout=30) as resp:
        _dsp = json.loads(resp.read().decode())
    check("OB (review, 1.7.2) a scan with no camera writes no scan summary (so the page says 'not checked', never "
          "'nothing left'); this computer's last scan is merged into the served record at serve time",
          lambda: _no_sum and (_dsp.get("pendingImport") or {}).get("files") == 3559
          and _dsp["pendingImport"]["failedEject"] is True and isinstance(_dsp["pendingImport"].get("ageHours"), (int, float)),
          json.dumps([_no_sum, _dsp.get("pendingImport")])[:400])
    # every script block of the page parses (node), so a slip in the template can't blank the tab
    import shutil as _sh2
    _node = _sh2.which("node") or next((p for p in ("/opt/node22/bin/node", "/usr/local/bin/node")
                                        if os.path.isfile(p)), None)
    _blocks = re.findall(r"<script>(.*?)</script>", body, re.S)
    if _node and _blocks:
        _bad = []
        for i, b in enumerate(_blocks):
            rp = subprocess.run([_node, "-e", "new Function(require('fs').readFileSync(0,'utf8'))"],
                                input=b, capture_output=True, text=True, timeout=30)
            if rp.returncode != 0:
                _bad.append(f"block {i}: {rp.stderr[-200:]}")
        check(f"OB the Observatory page's {len(_blocks)} script blocks parse (node)", not _bad, "; ".join(_bad))
        rj = subprocess.run([_node, "-e", "JSON.parse(require('fs').readFileSync(0,'utf8'))"],
                            input=_m.group(1) if _m else "x", capture_output=True, text=True, timeout=30)
        check("OB the dataset block parses with a browser's JSON.parse (node)", rj.returncode == 0, rj.stderr[-200:])
    else:
        skip("OB the Observatory page's script blocks parse (needs node)")
    # ── HN: phase 1, honest numbers (25 Oct 2026, Observatory_UX_Plan §6) ──────────────────────
    # The page's pure layer (orderDatasets, pipelineGroups, stateTotals, ruleLine, finalsChecks,
    # statesKeptText, newFramesNote, the §9.1 formats) is cut out of the SERVED page and run in node,
    # and the panel's projectsHtml is rendered from the SAME datasets written the projects.json way,
    # so one fixture proves the two lists agree. The expected order is worked out by hand from the
    # rule (most recent capture first; a ready list newest readySince first; ties by hours), not by
    # either implementation.
    import datetime as _hn_dt
    _hn_year = _hn_dt.date.today().year
    _hn_date = lambda dow_d_mon, year: dow_d_mon + ("" if year == _hn_year else " %d" % year)   # "Fri 16 Oct", the year only when not this year
    _HN = [   # one dataset per row: the target, its scope, the engine's facts and phase 1 fields; `old` is the row's 1.7.6 shape
        dict(t="Wizard Nebula (NGC 7380)", tid="wiz", sc="FRA400", cam="Askar FRA400", status="ready_to_process",
             h=12.5, f=900, n=5, last="2026-10-01", readySince="2026-10-16", reason="ready since Fri 16 Oct · 12.5 h on the FRA400"),
        dict(t="Wizard Nebula (NGC 7380)", tid="wiz", sc="S30P", cam="Seestar S30 Pro", status="capturing",
             h=0.75, f=600, n=2, last="2026-10-20", reason="still capturing · ready from Wed 4 Nov"),
        dict(t="Black Eye Galaxy (M 64)", tid="m64", sc="S50", cam="Seestar S50", status="ready_to_process",         # the same night and ready day as the Wizard: more hours wins
             h=29.4, f=3000, n=9, last="2026-10-01", readySince="2026-10-16", reason="ready since Fri 16 Oct · 29.4 h on the S50"),
        dict(t="Great Globular (M 13)", tid="m13", sc="S30P", cam="Seestar S30 Pro", status="ready_to_process",       # closed by hand that night: an older readySince sorts after
             h=4.0, f=400, n=2, last="2026-10-01", readySince="2026-10-01", captureState="complete", reason="ready since Thu 1 Oct · 4.0 h on the S30 Pro"),
        dict(t="Helix Nebula (NGC 7293)", tid="hel", sc="107PHQ", cam="Askar 107PHQ", status="in_progress",
             h=6.0, f=500, n=3, last="2026-10-18", masters=["masterLight_FRA.xisf"], reason="master in the folder · 6.0 h on the 107PHQ"),
        dict(t="Beehive Cluster (M 44)", tid="bee", sc="FRA400", cam="Askar FRA400", status="done",
             h=3.2, f=200, n=2, last="2026-10-19", finals=["Beehive FRA400.jpg"], finalDate="2026-10-16", newFramesSinceFinal=True, reason="finished · final of Fri 16 Oct"),
        dict(t="NGC 6229", tid="n6229", sc="S30P", cam="Seestar S30 Pro", status="sample", sample=True,                 # the rule's sample (3 min): status "sample" since phase 1
             h=0.05, f=30, n=1, last="2026-10-21", reason="sample · 3 min on the S30 Pro", old=dict(status="capturing", sample=False)),
        dict(t="Betelgeuse", tid="betel", sc="S50", cam="Seestar S50", status="sample", sample=True, captureState="sample",   # Brett's quick-look flag
             h=0.1, f=36, n=1, last="2026-09-01", reason="sample · 6 min on the S50", old=dict(status="ready_to_process")),
        dict(t="Tadpoles Nebula (IC 410)", tid="tad", sc="S30P", cam="Seestar S30 Pro", status="capturing",
             h=1.5, f=540, n=1, last="2026-10-22", readyOn="2026-11-06"),
    ]
    _HN_EXPECT = [("ready_to_process", "Black Eye Galaxy (M 64)", "Seestar S50"), ("ready_to_process", "Wizard Nebula (NGC 7380)", "Askar FRA400"),
                  ("ready_to_process", "Great Globular (M 13)", "Seestar S30 Pro"), ("in_progress", "Helix Nebula (NGC 7293)", "Askar 107PHQ"),
                  ("capturing", "Tadpoles Nebula (IC 410)", "Seestar S30 Pro"), ("capturing", "Wizard Nebula (NGC 7380)", "Seestar S30 Pro"),
                  ("done", "Beehive Cluster (M 44)", "Askar FRA400")]
    _HN_RULES = {"quietDays": 10, "sampleMinutes": 20, "activeWindowNights": 30}      # not the defaults, so the line proves it reads them

    def _hn_obs(rows, **top):
        """the Observatory record (observatory/1) for the rows: programmes under their targets"""
        tg = {}
        for r in rows:
            t = tg.setdefault(r["tid"], {"id": r["tid"], "name": r["t"], "programmes": [], "statusCards": [], "codes": [], "cameras": [],
                                         "hours": 0, "lights": 0, "nights": 0, "lastNight": ""})
            p = {"camera": r["cam"], "status": r["status"], "hours": r["h"], "lights": r["f"], "nights": r["n"], "lastNight": r["last"],
                 "firstNight": r["last"], "captureState": r.get("captureState", "auto"), "captureStateSource": "rule", "sample": r.get("sample", False),
                 "mastersNamed": r.get("masters", []), "finalsNamed": r.get("finals", [])}
            for k in ("readySince", "reason", "finalDate", "newFramesSinceFinal", "readyOn"):
                if k in r:
                    p[k] = r[k]
            t["programmes"].append(p); t["cameras"].append(r["cam"]); t["hours"] += r["h"]; t["lights"] += r["f"]; t["nights"] += r["n"]
            t["lastNight"] = max(t["lastNight"], r["last"])
        d = {"schema": "observatory/1", "asOfNight": "2026-10-23", "quietPeriodDays": 14, "targets": list(tg.values()), "sessions": [], "scopes": []}
        d.update(top)
        return d

    def _hn_pj(rows, **top):
        """the same datasets as projects.json (the panel's list)"""
        pj = {}
        for r in rows:
            t = pj.setdefault(r["tid"], {"target_id": r["tid"], "name": r["t"], "datasets": []})
            d = {"scope": r["sc"], "scope_name": r["cam"], "site": "Shinfield", "status": r["status"], "nights": r["n"], "frames": r["f"],
                 "integration_seconds": int(round(r["h"] * 3600)), "last_session": r["last"], "locations": ["chillblast_archive"],
                 "archive_rel": r["sc"] + "/" + r["tid"], "sample": r.get("sample", False)}
            if r.get("captureState") == "complete":
                d["capture_state"] = "complete"
            for k in ("masters", "finals"):
                if k in r:
                    d[k] = r[k]
            for k, pk in (("readySince", "ready_since"), ("reason", "reason"), ("finalDate", "final_date"), ("newFramesSinceFinal", "new_frames_since_final")):
                if k in r:
                    d[pk] = r[k]
            t["datasets"].append(d)
        doc = {"schema": "projects/1", "generated_at": "2026-10-23T08:00:00+00:00", "quiet_period_days": 14, "warnings": [], "projects": list(pj.values())}
        doc.update(top)
        return {"ok": True, "opener": "Finder", "projects": doc}

    _HN_PAGE_PATS = (r"const DEFAULTS = \{.*?\nconst STATE_OF_STATUS=[^\n]*\n", r"const dayMs=864e5;\n.*?const nightIdx=[^\n]*\n",
                     r"const ST=\{.*?\nconst stKey=[^\n]*\n",
                     r"/\* ---------- formatting: ONE rounding function.*?/\* ==== end of the phase 1 pure layer ==== \*/")
    _HN_HARNESS = r"""
let D=JSON.parse(require('fs').readFileSync(0,'utf8')); D=normalise(D);
let SESS=D.sessions, TG=D.targets, PROGS=[]; for(const t of TG) for(const p of t.programmes) PROGS.push({...p,target:t.name,tid:t.id,t});
const out={}; const pg=pipelineGroups();
out.order=pg.groups.flatMap(g=>g.list.map(p=>[g.k,p.target,p.camera])); out.samples=pg.samples.map(p=>p.target);
out.queueReady=orderDatasets(PROGS.filter(p=>!isSample(p)&&stKey(p)==="ready_to_process")).map(p=>p.target);
out.targetsDefault=orderDatasets(TG.filter(t=>!sampleOnly(t))).map(t=>t.name); out.sampleOnly=TG.filter(sampleOnly).map(t=>t.name);
out.totals=stateTotals(); out.rule=ruleLine(); out.kept=statesKeptText(); out.fc=finalsChecks(); out.samplesLine=samplesLine(); out.quiet=RULES().quietDays;
out.reasons=Object.fromEntries(PROGS.map(p=>[p.target+"|"+p.camera,reasonTxt(p)])); out.notes=Object.fromEntries(PROGS.filter(p=>newFramesNote(p)).map(p=>[p.target,newFramesNote(p)]));
out.fmt=[fmtH(0.75),fmtH(0.05),fmtH(1),fmtH(3.24),fmtH(0),fmtDate("2026-10-16"),fmtDate("2025-12-03"),sumH([0.5,0.5,1.04]),fmtHp(0.5).u];
process.stdout.write(JSON.stringify(out));
"""
    _hn_page_pieces = [re.search(p_, body, re.S) for p_ in _HN_PAGE_PATS]
    _hn_panel_m = re.search(r"<script>(.*?)</script>", _pagen, re.S)
    _hn_panel_pieces = [re.search(p_, _hn_panel_m.group(1) if _hn_panel_m else "", re.S) for p_ in
                        (r"const MONTHS=[^\n]*", r"const esc=[^\n]*", r"const fmtNight=[^\n]*",
                         r"const PROJ_WHERE=.*?\nfunction projectsHtml\(pj, opts\)\{.*?\n\}\n")]
    if _node:
        check("HN (phase 1) the served page carries the phase 1 pure layer (DEFAULTS and normalise, the night helpers, the ST "
              "vocabulary with stKey, the formatting helpers through 'end of the phase 1 pure layer') and the panel its "
              "projectsHtml, so the checks below can cut them out and run them in node",
              all(_hn_page_pieces) and all(_hn_panel_pieces), str([bool(m_) for m_ in _hn_page_pieces + _hn_panel_pieces]))
    if _node and all(_hn_page_pieces) and all(_hn_panel_pieces):
        _hn_js = "\n".join(m_.group(0) for m_ in _hn_page_pieces) + _HN_HARNESS

        def _hn_run(record):
            r_ = subprocess.run([_node, "-e", _hn_js], input=json.dumps(record), capture_output=True, text=True, timeout=30)
            if r_.returncode != 0:
                return {"error": r_.stderr[-400:]}
            try:
                return json.loads(r_.stdout)
            except ValueError as e_:
                return {"error": str(e_) + r_.stdout[-200:]}

        def _hn_panel(pj):
            h_ = "let deskSel=null;\n" + "\n".join(m_.group(0) for m_ in _hn_panel_pieces) + f"\nprocess.stdout.write(projectsHtml({json.dumps(pj)}));\n"
            r_ = subprocess.run([_node, "-e", h_], capture_output=True, text=True, timeout=30)
            return r_.stdout if r_.returncode == 0 else "ERROR " + r_.stderr[-400:]

        _hn_fc = {"finalsUnmatched": [{"file": "Soul Nebula HOO.jpg", "folder": "ZWO Askar Scopes", "why": "no target named Soul in the importer's list"}],
                  "finalsAmbiguous": [{"file": "Elephant Trunk.tif", "target": "Elephant's Trunk (IC 1396)", "scopes": ["Askar FRA400", "Askar 107PHQ"]}],
                  "statesKeptFrom": "2026-10-21T03:38:00+00:00", "rules": _HN_RULES,
                  "notices": [{"kind": "finals_unmatched", "count": 1, "text": "1 finished picture(s) match no dataset"},       # the engine's spellings
                              {"kind": "finals-ambiguous", "count": 1, "text": "1 finished picture(s) could be of either Askar"},
                              {"kind": "states_kept", "count": 3, "text": "states kept from 2026-10-21T03:38:00+00:00: Final Astro Images could not be read, so 3 dataset(s) keep the done / in progress state they had"}]}
        _o1 = _hn_run(_hn_obs(_HN, **_hn_fc))                                 # counts added up by the page (no stateCounts)
        _o2 = _hn_run(_hn_obs(_HN, stateCounts={"capturing": 2, "ready_to_process": 3, "in_progress": 1, "done": 7, "sample": 2},
                              stateHours={"capturing": 2.3, "ready_to_process": 45.9, "in_progress": 6.0, "done": 30.0, "sample": 0.15}, **_hn_fc))
        _h1 = _hn_panel(_hn_pj(_HN, rules=_HN_RULES))
        _h_names = re.findall(r'<div class="tname">(.*?)</div>', _h1)
        _h_secs = re.findall(r'<summary class="eyebrow">(.*?)</summary>', _h1)
        _h_notes = re.findall(r'<div class="tnote">(.*?)</div>', _h1)
        _p_order = [tuple(x) for x in (_o1.get("order") or [])]
        check("HN (phase 1) one order everywhere: the page's orderDatasets (What to do next, the Pipeline board, the Targets "
              "default, the lanes) and the panel's To process tab put the same first five datasets in the same order, and it "
              "is the engine's rule worked out by hand (most recent capture first; the same night, newest readySince first; "
              "then hours; then name); the Ready column is the Pipeline's Ready group",
              lambda: _p_order[:5] == _HN_EXPECT[:5] and _p_order == _HN_EXPECT
              and _h_names[:5] == [x[1] for x in _HN_EXPECT[:5]] and _h_names[:7] == [x[1] for x in _HN_EXPECT]
              and _o1["queueReady"] == [x[1] for x in _HN_EXPECT[:3]]
              and _o1["targetsDefault"] == ["Tadpoles Nebula (IC 410)", "Wizard Nebula (NGC 7380)", "Beehive Cluster (M 44)", "Helix Nebula (NGC 7293)",
                                            "Black Eye Galaxy (M 64)", "Great Globular (M 13)"],
              json.dumps([_p_order, _h_names, _o1.get("error"), _h1[:300] if _h1.startswith("ERROR") else ""])[:900])
        check("HN (phase 1) every queue row carries the engine's reason when the record has one, else the page's own words "
              "('ready since', 'ready to process from', 'nothing new for'); the panel row shows the same reason",
              lambda: _o1["reasons"]["Black Eye Galaxy (M 64)|Seestar S50"] == "ready since Fri 16 Oct · 29.4 h on the S50"
              and _o1["reasons"]["Great Globular (M 13)|Seestar S30 Pro"] == "ready since Thu 1 Oct · 4.0 h on the S30 Pro"
              and _o1["reasons"]["Tadpoles Nebula (IC 410)|Seestar S30 Pro"] == "ready to process from " + _hn_date("Fri 6 Nov", 2026) + " unless you add frames"
              and _o1["reasons"]["Betelgeuse|Seestar S50"] == "sample · 6 min on the S50"
              and _h_notes[0] == "ready since Fri 16 Oct · 29.4 h on the S50" and "ready since Fri 16 Oct · 12.5 h on the FRA400" in _h_notes
              and "last night 22 Oct 2026 · ready from 6 Nov 2026" in _h_notes,
              json.dumps([_o1.get("reasons"), _h_notes])[:900])
        check("HN (phase 1, §6.2) samples leave every count, total and queue: the rule's sample (status 'sample', 3 min) and Brett's "
              "quick look are in no Pipeline group and in no Ready/Finish/Capturing list, only in the Samples group (newest first); "
              "the counts the page adds up exclude them (2 · 3 · 1 · 1, samples 2) and the engine's stateCounts win when the record "
              "carries them; the Targets default leaves a sample-only target out; the panel shows 'Samples · 2' as the last, closed "
              "section, 'To process · 3', and the tail says '2 samples set aside'",
              lambda: _o1["samples"] == ["NGC 6229", "Betelgeuse"] and not any(x[1] in ("NGC 6229", "Betelgeuse") for x in _p_order)
              and _o1["totals"]["counts"] == {"capturing": 2, "ready_to_process": 3, "in_progress": 1, "done": 1, "sample": 2}
              and _o1["totals"]["fromEngine"] is False and _o1["totals"]["samples"]["n"] == 2 and _o1["samplesLine"] == "2 samples set aside"
              and _o2["totals"]["counts"]["done"] == 7 and _o2["totals"]["hours"]["done"] == 30.0 and _o2["totals"]["fromEngine"] is True
              and _o1["sampleOnly"] == ["NGC 6229", "Betelgeuse"] and "NGC 6229" not in _o1["targetsDefault"]
              and _h_secs == ["To process · 3", "In progress · 1", "Still capturing · 2", "Done · 1", "Samples · 2"]
              and '<details class="ad-sec ad-samples"><summary class="eyebrow">Samples · 2' in _h1
              and _h_names[7:] == ["NGC 6229", "Betelgeuse"] and "2 still capturing" in _h1 and "1 done, 2 samples set aside." in _h1
              and "Under 20 minutes of integration" in _h1
              and '"Samples ("' in body and "details.samples-grp" in body and "function samplesGroup(" in body
              and "Quick looks, kept out of the queue" not in body,
              json.dumps([_o1.get("samples"), _o1.get("totals"), _o2.get("totals"), _h_secs, _h_names])[:900])
        check("HN (phase 1) Data checks: the rule line comes from the record's rules ('Ready: nothing new for 10 days, or closed by "
              "you. Samples under 20 minutes are set aside.'), QUIET follows it, the unmatched finals (file, folder, why) and the "
              "either-Askar finals (file, target, scopes) come through, the kept-states notice names the date, and the page carries "
              "the headings and the 'no action yet' note",
              lambda: _o1["rule"] == "Ready: nothing new for 10 days, or closed by you. Samples under 20 minutes are set aside."
              and _o1["quiet"] == 10
              and _o1["fc"]["unmatched"] == [{"file": "Soul Nebula HOO.jpg", "folder": "ZWO Askar Scopes", "why": "no target named Soul in the importer's list"}]
              and _o1["fc"]["ambiguous"] == [{"file": "Elephant Trunk.tif", "target": "Elephant's Trunk (IC 1396)", "scopes": ["Askar FRA400", "Askar 107PHQ"]}]
              and _o1["kept"].startswith("states kept from 2026-10-21T03:38:00+00:00: Final Astro Images could not be read")
              and _o1["kept"].endswith("Nothing slipped back; the next rebuild that can read them moves on.")
              and ("kept the state they had on " + _hn_date("Wed 21 Oct", 2026)) in _hn_run(_hn_obs(_HN, statesKeptFrom="2026-10-21T03:38:00+00:00"))["kept"]
              and "Finished pictures that match nothing" in body and "Pictures that could be either Askar" in body
              and "No action yet: the scope can be set later" in body and "States kept from the last build" in body
              and "/^finals[-_](unmatched|ambiguous)$/" in body and 'finals_unmatched:"Finished pictures that match nothing"' in body and "function finalsChecks()" in body and "function ruleLine" in body.replace("const ruleLine=", "function ruleLine"),
              json.dumps([_o1.get("rule"), _o1.get("quiet"), _o1.get("fc"), _o1.get("kept")])[:900])
        check("HN (phase 1, §6.1) Done with nights newer than the final stays Done with 'new frames since {finalDate}' in the §9.1 "
              "date format, on the page and on the panel row; nothing else gets the note",
              lambda: _o1["notes"] == {"Beehive Cluster (M 44)": "new frames since " + _hn_date("Fri 16 Oct", 2026)}
              and _o1["reasons"]["Beehive Cluster (M 44)|Askar FRA400"] == "finished · final of Fri 16 Oct"
              and _p_order[-1][0] == "done"
              and any(n_.startswith("finished · final of Fri 16 Oct") and n_.endswith("· new frames since 16 Oct 2026") for n_ in _h_notes)
              and "function newFramesNote" in body.replace("const newFramesNote=", "function newFramesNote"),
              json.dumps([_o1.get("notes"), _h_notes])[:600])
        check("HN (phase 1, §9.1) one format for durations and dates: minutes under an hour ('45 min', '3 min'), one decimal from an "
              "hour ('1.0 h', '3.2 h'), a total keeps its minute parts, 'Fri 16 Oct' with the year only when it isn't this year; the "
              "panel's fmtHours agrees ('45 min' for 2700 s, '29.4 h')",
              lambda: _o1["fmt"] == ["45 min", "3 min", "1.0 h", "3.2 h", "0.0 h", _hn_date("Fri 16 Oct", 2026), "Wed 3 Dec 2025", 2, "min"]
              and re.findall(r'class="big">(.*?)<', _h1)[:3] == ["29.4 h", "12.5 h", "4.0 h"] and '<div class="big">45 min</div>' in _h1
              and '<div class="big">3 min</div>' in _h1 and "fmtDate(" in body and "const MIN_H=1;" in body,
              json.dumps([_o1.get("fmt"), re.findall(r'class="big">(.*?)<', _h1)])[:600])
        # an OLD record (1.7.6, none of the phase 1 fields) still renders: no script error, the defaults, nothing set aside
        _old_rows = [dict([(k, v) for k, v in r.items() if k not in ("readySince", "reason", "finalDate", "newFramesSinceFinal", "old")] + list(r.get("old", {}).items())) for r in _HN]
        _o3 = _hn_run(_hn_obs(_old_rows))
        _h3 = _hn_panel(_hn_pj(_old_rows))
        check("HN (phase 1) an OLD record (1.7.6 shape, none of the new fields) still renders with no script error: the lists keep "
              "the one order from lastNight and hours alone, the rule line falls back to 14 days / 30 minutes, the quick look is the only sample, no "
              "finals checks, no kept-states notice, no 'undefined'; the panel renders it too",
              lambda: "error" not in _o3 and _o3["order"][0] == ["ready_to_process", "Black Eye Galaxy (M 64)", "Seestar S50"]
              and [x[1] for x in _o3["order"]] == ["Black Eye Galaxy (M 64)", "Wizard Nebula (NGC 7380)", "Great Globular (M 13)", "Helix Nebula (NGC 7293)",
                                                   "Tadpoles Nebula (IC 410)", "NGC 6229", "Wizard Nebula (NGC 7380)", "Beehive Cluster (M 44)"]
              and _o3["reasons"]["Betelgeuse|Seestar S50"] == "nothing new for 52 nights" and _o3["reasons"]["Wizard Nebula (NGC 7380)|Askar FRA400"] == "nothing new for 22 nights"
              and _o3["samples"] == ["Betelgeuse"] and _o3["rule"] == "Ready: nothing new for 14 days, or closed by you. Samples under 30 minutes are set aside."
              and _o3["kept"] == "" and _o3["fc"] == {"unmatched": [], "ambiguous": [], "keptFrom": None} and _o3["notes"] == {}
              and _o3["totals"]["fromEngine"] is False and _o3["totals"]["counts"]["sample"] == 1
              and "undefined" not in json.dumps(_o3) and not _h3.startswith("ERROR") and "undefined" not in _h3
              and "Samples · 1" in _h3 and "To process · 3" in _h3 and "1 sample set aside." in _h3,
              json.dumps(_o3)[:700] + _h3[:200])
    else:
        skip("HN (phase 1) the page's pure layer and the panel's projectsHtml in node (needs node and the marked regions)")
    # ── P2 panel ── (phase 2 "scope first", docs/ux-observatory-25oct/PHASE2-CONTRACT.md, the panel's items):
    # `status` and `space` beside pendingImport in the served record, Dashboard → Ledger, the Observatory
    # in its own tab, pendingImport.scope from the dest plan. Inputs are set by hand and put back after.
    _p2_scan_path = os.path.join(envn.state, "last-scan.json")
    _p2_scan_before = open(_p2_scan_path, encoding="utf-8").read() if os.path.isfile(_p2_scan_path) else None
    import inspect as _p2_inspect
    _p2_pan = globals().get("panel")                 # the U10 in-process panel module, for the pure pieces
    _p2_takes_scope = _p2_pan is not None and "scope" in _p2_inspect.signature(_p2_pan.eng.save_scan_summary).parameters
    with open(_p2_scan_path, "w", encoding="utf-8") as f:
        json.dump({"schema": "scan-summary/1", "files": 7, "targets": 1, "camera": "ASIAir", "failedEject": False,
                   "seenAt": "2026-10-28T20:15:00+00:00", "machine": "PC", "targetNames": ["Wizard Nebula (NGC 7380)"],
                   "scope": "Askar FRA400"}, f)
    _p2_t0 = time.time()                             # the Ledger worker has built once (space comes from its build)
    while time.time() - _p2_t0 < 30 and not api("/api/state", url=URLN).get("dashboardAt"):
        time.sleep(0.3)
    def _p2_get(path, headers=None):
        """A GET as a browser would send it; (status, body)."""
        req = urllib.request.Request(URLN + path, headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", "replace")
    _p2_rec = json.loads(_p2_get("/observatory?json=1&t=p2a")[1])
    _p2s = _p2_rec.get("status") if isinstance(_p2_rec.get("status"), dict) else {}
    check("P2 panel: the served record carries `status` beside pendingImport in the contract's shape: checked true "
          "with onlyHere from the cached status line (SafeStatus, no child process per request), this computer's "
          "label, the last scan's files / camera / seenAt, the record's age in hours (just built: under 24) and "
          "publishedFrom null for its own record; no reason while checked",
          lambda: set(_p2s) == {"checked", "onlyHere", "machine", "pendingFiles", "pendingCamera", "pendingSeenAt",
                                "servedAgeHours", "publishedFrom"}
          and _p2s["checked"] is True and _p2s["onlyHere"] == 0 and _p2s["machine"] in ("Mac", "PC")
          and _p2s["pendingFiles"] == 7 and _p2s["pendingCamera"] == "ASIAir"
          and _p2s["pendingSeenAt"] == "2026-10-28T20:15:00+00:00"
          and isinstance(_p2s["servedAgeHours"], (int, float)) and 0 <= _p2s["servedAgeHours"] < 24
          and _p2s["publishedFrom"] is None and (_p2_rec.get("pendingImport") or {}).get("files") == 7,
          json.dumps(_p2s))
    _p2sp = _p2_rec.get("space")
    check("P2 panel: `space` is this computer's Space figures (the engine's mac_space, as the Ledger's build worked "
          "them out: machine, totals safe / waiting / onlyHere / changed / yours, folders, unknown null), read back "
          "from the Ledger worker's build, never worked out per request",
          lambda: "space" in _p2_rec and isinstance(_p2sp, dict) and _p2sp["machine"] in ("Mac", "PC")
          and set(_p2sp["totals"]) == {"safe", "waiting", "onlyHere", "changed", "yours"}
          and all(set(v) == {"files", "bytes"} for v in _p2sp["totals"].values())
          and isinstance(_p2sp["folders"], list) and _p2sp["unknown"] is None,
          json.dumps(_p2sp)[:400])
    # the amber inputs the panel can't see here: an old record (the file's stamp moved 30 h back, put back after)
    _p2_obs_path = os.path.join(envn.state, "observatory.json")
    with open(_p2_obs_path, encoding="utf-8") as f:
        _p2_obs_text = f.read()
    _p2_old = json.loads(_p2_obs_text)
    _p2_old["generatedAtIso"] = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(time.time() - 30 * 3600))
    with open(_p2_obs_path, "w", encoding="utf-8") as f:
        json.dump(_p2_old, f)
    _p2_aged = (json.loads(_p2_get("/observatory?json=1&t=p2b")[1]).get("status") or {}).get("servedAgeHours")
    with open(_p2_obs_path, "w", encoding="utf-8") as f:
        f.write(_p2_obs_text)
    check("P2 panel: servedAgeHours is the age of the record being served, from its generatedAtIso (a record "
          "stamped 30 h ago serves as 30 h old: over the page's 24 h amber line)",
          lambda: isinstance(_p2_aged, (int, float)) and 29.9 <= _p2_aged <= 30.2, json.dumps(_p2_aged))
    if _p2_pan is not None and hasattr(_p2_pan, "observatory_status"):
        _p2a = _p2_pan.observatory_status({"generatedAtIso": "2026-10-01T00:00:00+00:00",
                                           "servedFrom": {"machine": "PC", "ageHours": 3.0}}, None, None)
        _p2b = _p2_pan.observatory_status({}, {"files": 0, "camera": None, "seenAt": None},
                                          _p2_pan.eng.status_unknown("the ledger can't be read"))
        _p2c = _p2_pan.observatory_status({}, {"files": 12, "camera": "Seestar", "seenAt": "2026-10-20T21:00:00+00:00"},
                                          {"safe": False, "onlyHere": 41, "text": "41 frames only on the Mac", "machine": "Mac"})
        check("P2 panel: the status derivation (observatory_status) — no status line yet: checked false, reason "
              "'still working it out', onlyHere null, publishedFrom names the other side when its published copy is "
              "served, no scan: pendingFiles 0 and pendingSeenAt null; 'Status unknown: …': checked false with the "
              "engine's reason; a line: onlyHere as counted, the scan's figures, no reason key",
              lambda: _p2a["checked"] is False and _p2a["reason"] == "still working it out" and _p2a["onlyHere"] is None
              and _p2a["publishedFrom"] == "PC" and _p2a["servedAgeHours"] > 24 and _p2a["pendingFiles"] == 0
              and _p2a["pendingSeenAt"] is None and _p2a["pendingCamera"] is None
              and _p2b["checked"] is False and _p2b["reason"] == "the ledger can't be read" and _p2b["onlyHere"] is None
              and _p2c["checked"] is True and _p2c["onlyHere"] == 41 and "reason" not in _p2c and _p2c["machine"] == "Mac"
              and _p2c["pendingFiles"] == 12 and _p2c["pendingCamera"] == "Seestar" and _p2c["servedAgeHours"] is None
              and _p2c["publishedFrom"] is None,
              json.dumps([_p2a, _p2b, _p2c]))
    else:
        skip("P2 panel: the status derivation in-process (the U10 panel module isn't loaded)")
    _p2_page = _p2_get("/")[1]
    _p2_lcode, _p2_led = _p2_get("/dashboard?t=p2c")
    check("P2 panel: the Dashboard tab is Ledger (same data-tab and /dashboard route, so the frame and bookmarks keep "
          "working; the tooltip names the ledger); the page served there keeps the verdicts, events and Recent "
          "activity and loses 'Space on this computer' and 'Camera storage' (hidden at serve time, so the page's own "
          "script still runs: Space reaches the Observatory as `space`, the header pill has storage); titled Ledger",
          lambda: ">Ledger</button>" in _p2_page and ">Dashboard</button>" not in _p2_page
          and 'data-tab="dash" title="This computer\'s ledger' in _p2_page
          and _p2_lcode == 200 and "#spaceCard,#storageCard{display:none!important}" in _p2_led
          and "<title>BrettjoAstro FITS Importer — Ledger</title>" in _p2_led and "— Status</title>" not in _p2_led
          and 'id="events"' in _p2_led and "Recent activity" in _p2_led and "M 31" in _p2_led
          and 'id="spaceCard"' in _p2_led and "__DATA__" not in _p2_led,
          _p2_page[:120] + " | " + _p2_led[:300])
    _p2_nav = {"Sec-Fetch-Site": "cross-site", "Sec-Fetch-Mode": "navigate", "Sec-Fetch-Dest": "document"}
    _p2_fetch = {"Sec-Fetch-Site": "cross-site", "Sec-Fetch-Mode": "cors", "Sec-Fetch-Dest": "empty"}
    _p2_c1, _p2_b1 = _p2_get("/observatory?t=p2d", _p2_nav)
    _p2_codes = [_p2_get("/observatory?t=p2e")[0],                                               # typed, no Fetch Metadata
                 _p2_get("/observatory?t=p2f", {"Sec-Fetch-Site": "none", "Sec-Fetch-Dest": "document"})[0],   # bookmark / typed
                 _p2_get("/observatory?t=p2g", {"Sec-Fetch-Site": "same-origin", "Sec-Fetch-Dest": "iframe"})[0],  # the panel's frame
                 _p2_get("/observatory?json=1&t=p2h", _p2_nav)[0],                               # the dataset, cross-site: refused
                 _p2_get("/observatory?json=1&t=p2i", {"Sec-Fetch-Site": "cross-site"})[0],
                 _p2_get("/observatory?t=p2j", _p2_fetch)[0],                                    # fetch() from another site: refused
                 _p2_get("/observatory?t=p2k", {"Sec-Fetch-Site": "cross-site", "Sec-Fetch-Dest": "iframe"})[0],  # framed by another site
                 _p2_get("/dashboard?t=p2l", _p2_nav)[0], _p2_get("/api/state", _p2_nav)[0],    # every other costly GET
                 _p2_get("/api/archive/index", _p2_nav)[0],
                 _p2_get("/observatory?t=p2m", {"Host": f"skylarkpc:{PORTN}"})[0]]              # the Host check, untouched
    check("P2 panel: GET /observatory opened in its own tab serves the full page — typed or bookmarked (no Fetch "
          "Metadata, or Sec-Fetch-Site none / same-origin) and a link clicked from another page (cross-site, "
          "Sec-Fetch-Dest: document) — while the dataset (?json=1), a cross-site fetch() or frame of the page, and "
          "every other costly GET stay refused (403); the Host check, the bind and the token are untouched",
          lambda: _p2_c1 == 200 and "Astro Archive Observatory" in _p2_b1 and "__DATASET__" not in _p2_b1
          and 'const TOKEN="' not in _p2_b1 and "__ASTRO_BOOT__" not in _p2_b1
          and _p2_codes == [200, 200, 200, 403, 403, 403, 403, 403, 403, 403, 403],
          json.dumps([_p2_c1, _p2_codes]))
    if _p2_pan is not None:
        _p2_plan = [{"device": "seestar", "target": "M 31", "scope": "Seestar S30 Pro"},
                    {"device": "asiair", "target": "NGC 7380", "scope": "Askar FRA400"},
                    {"device": "asiair", "target": "IC 410", "scope": "Askar 107PHQ"}]
        _p2_kw = _p2_pan.App._summary_extras({"destPlan": _p2_plan}) if hasattr(_p2_pan.App, "_summary_extras") else None
        check("P2 panel: pendingImport.scope — the dest plan's scope is the FIRST ASIAir entry's (a Seestar entry never "
              "counts; a plan with no ASIAir entry, an unknown scope or no plan gives null), passed to save_scan_summary "
              "as scope= only when this engine's signature takes it (an older engine gets nothing new)",
              lambda: _p2_pan.App._plan_scope(_p2_plan) == "Askar FRA400"
              and _p2_pan.App._plan_scope([{"device": "seestar", "target": "M 31", "scope": "Seestar S30 Pro"}]) is None
              and _p2_pan.App._plan_scope([{"device": "asiair", "target": "X", "scope": None}]) is None
              and _p2_pan.App._plan_scope(None) is None and _p2_pan.App._summary_extras(None) == ({"scope": None} if _p2_takes_scope else {})
              and _p2_kw == ({"scope": "Askar FRA400"} if _p2_takes_scope else {}),
              json.dumps([_p2_kw, _p2_takes_scope]))
    else:
        skip("P2 panel: the dest plan's scope in-process (the U10 panel module isn't loaded)")
    if _p2_pan is not None and _p2_takes_scope:
        # the round trip, in the runner's own state folder (test mode confines the engine to its root): the
        # panel's keyword reaches last-scan.json and read_scan_summary gives it back; the served record carries it
        os.makedirs(_p2_pan.eng.STATE_DIR, exist_ok=True)
        _p2_pan.eng.save_scan_summary(5, 2, camera="ASIAir", **_p2_pan.App._summary_extras({"destPlan": _p2_plan}))
        _p2_rt = _p2_pan.eng.read_scan_summary() or {}
        _p2_pan.eng.save_scan_summary(5, 2, camera="Seestar", **_p2_pan.App._summary_extras({"destPlan": _p2_plan[:1]}))
        _p2_rt2 = _p2_pan.eng.read_scan_summary() or {}
        check("P2 panel: the scope reaches last-scan.json through save_scan_summary(scope=) and comes back from "
              "read_scan_summary ('Askar FRA400'; null for a Seestar-only plan), and the panel serves it as "
              "pendingImport.scope in the record",
              lambda: _p2_rt.get("scope") == "Askar FRA400" and _p2_rt.get("files") == 5
              and "scope" in _p2_rt2 and _p2_rt2["scope"] is None
              and (_p2_rec.get("pendingImport") or {}).get("scope") == "Askar FRA400",
              json.dumps([_p2_rt, _p2_rt2, _p2_rec.get("pendingImport")])[:500])
    else:
        skip("P2 panel: the scope's round trip through last-scan.json (this engine's save_scan_summary doesn't take scope= yet)")
    if _p2_scan_before is None:
        os.remove(_p2_scan_path)
    else:
        with open(_p2_scan_path, "w", encoding="utf-8") as f:
            f.write(_p2_scan_before)
    # ── P2 page ── (phase 2 "scope first", Observatory_UX_Plan §7, PHASE2-CONTRACT.md: the page's side).
    # The served page's phase 2 pure layer (unitsOf / cardModel, statusLine, nextActionTxt, exploreItems,
    # findMatches, unitRows, projectModel, the lines under the cards) is cut out of `body` like the HN checks
    # do and run in node on a fixture that carries the new fields (units[], status, thisMonth, recordsUpTo,
    # nextAction) and on the same rows in the 1.8.0 and 1.7.6 shapes; the DOM side is checked by its markers.
    _P2_SCOPES = [{"camera": "Askar FRA400", "id": "FRA400", "colour": "#D55E00", "kind": "askar", "order": 1, "hours": 15.7, "frames": 1100, "nights": 7, "first": "2025-01-10", "last": "2026-10-19"},
                  {"camera": "Askar 107PHQ", "id": "107PHQ", "colour": "#009E73", "kind": "askar", "order": 2, "hours": 6.0, "frames": 500, "nights": 3, "first": "2025-03-02", "last": "2026-10-18"},
                  {"camera": "Seestar S30 Pro", "id": "S30P", "colour": "#E69F00", "kind": "seestar", "order": 3, "hours": 6.3, "frames": 1570, "nights": 6, "first": "2025-06-01", "last": "2026-10-22"},
                  {"camera": "Seestar S50", "id": "S50", "colour": "#1A1A1A", "kind": "seestar", "order": 4, "hours": 29.5, "frames": 3036, "nights": 10, "first": "2024-11-11", "last": "2026-10-01"},
                  {"camera": "Seestar S30", "id": "S30", "colour": "#0072B2", "kind": "seestar", "order": 5, "hours": 40.0, "frames": 9000, "nights": 30, "first": "2024-09-01", "last": "2025-08-30"}]
    _P2_SESS = [("2026-10-01", "Wizard Nebula (NGC 7380)", "Askar FRA400", 900, 12.5, {"L-eXtreme": 900}, {"300": 900}),
                ("2026-10-20", "Wizard Nebula (NGC 7380)", "Seestar S30 Pro", 600, 0.75, {"LP": 600}, {"10": 600}),
                ("2026-10-01", "Black Eye Galaxy (M 64)", "Seestar S50", 3000, 29.4, {"IRCUT": 3000}, {"10": 3000}),
                ("2026-10-01", "Great Globular (M 13)", "Seestar S30 Pro", 400, 4.0, {"IRCUT": 400}, {"10": 400}),
                ("2026-10-18", "Helix Nebula (NGC 7293)", "Askar 107PHQ", 500, 6.0, {"UV/IR": 500}, {"120": 500}),
                ("2026-10-19", "Beehive Cluster (M 44)", "Askar FRA400", 200, 3.2, {"UV/IR": 200}, {"60": 200}),
                ("2026-10-21", "NGC 6229", "Seestar S30 Pro", 30, 0.05, {"IRCUT": 30}, {"10": 30}),
                ("2026-09-01", "Betelgeuse", "Seestar S50", 36, 0.1, {"IRCUT": 36}, {"10": 36}),
                ("2026-10-22", "Tadpoles Nebula (IC 410)", "Seestar S30 Pro", 540, 1.5, {"LP": 540}, {"10": 540})]
    _p2_sess = lambda: [{"night": n, "target": t, "camera": c, "frames": f, "hours": h, "filters": fl, "exps": ex} for n, t, c, f, h, fl, ex in _P2_SESS]
    _p2_sum = lambda tid, target, cam, state, h, f, n, last, **kw: dict({"tid": tid, "target": target, "codes": [], "camera": cam, "scopeId": cam.split()[-1], "state": state, "hours": h, "frames": f, "nights": n, "firstNight": last, "lastNight": last, "readySince": None, "reason": "", "nextAction": "", "calMissing": False, "mosaic": False}, **kw)
    _P2_UNITS = [   # the engine's units[] (contract): the ZWO unit says "last on the 107PHQ" and the S50 rests, whatever the sessions say
        {"id": "ZWO", "label": "ZWO", "name": "ZWO ASI585MC Air", "kind": "askar", "scopeIds": ["FRA400", "107PHQ"], "scopes": ["Askar FRA400", "Askar 107PHQ"], "colour": "#009E73", "short": "ZWO",
         "onScope": "Askar 107PHQ", "onScopeId": "107PHQ", "onScopeCurrent": False, "active": True, "lastOut": "2026-10-19",
         "current": [_p2_sum("hel", "Helix Nebula (NGC 7293)", "Askar 107PHQ", "in_progress", 6.0, 500, 3, "2026-10-18", nextAction="Finish it · master in the folder")],
         "moreReady": 2, "moreReadyHours": 15.7, "strip": [{"night": "2026-10-18", "hours": 6.0}, {"night": "2026-10-19", "hours": 3.2}],
         "latestDone": {"tid": "bee", "target": "Beehive Cluster (M 44)", "camera": "Askar FRA400", "finalDate": "2026-10-16"}},
        {"id": "S30P", "label": "S30 Pro", "name": "Seestar S30 Pro", "kind": "seestar", "scopeIds": ["S30P"], "scopes": ["Seestar S30 Pro"], "colour": "#E69F00", "short": "S30P",
         "onScope": "Seestar S30 Pro", "onScopeId": "S30P", "onScopeCurrent": True, "active": True, "lastOut": "2026-10-22",
         "current": [_p2_sum("tad", "Tadpoles Nebula (IC 410)", "Seestar S30 Pro", "capturing", 1.5, 540, 1, "2026-10-22", nextAction="Darks or flats missing: no flats filed with these lights", calMissing=True)],
         "moreReady": 1, "moreReadyHours": 4.0, "strip": [{"night": "2026-10-22", "hours": 1.5}], "latestDone": None},
        {"id": "S50", "label": "S50", "name": "Seestar S50", "kind": "seestar", "scopeIds": ["S50"], "scopes": ["Seestar S50"], "colour": "#1A1A1A", "short": "S50",
         "onScope": "Seestar S50", "onScopeId": "S50", "onScopeCurrent": False, "active": False, "lastOut": "2026-10-01", "current": [], "moreReady": 1, "moreReadyHours": 29.4, "strip": [], "latestDone": None}]
    def _p2_obs(rows, **top):
        """the record for the rows with scopes, their order and one session per row (the derived path); `top` adds the engine's / panel's phase 2 fields"""
        return _hn_obs(rows, scopes=json.loads(json.dumps(_P2_SCOPES)), scopeOrder=["FRA400", "107PHQ", "S30P", "S50", "S30"], sessions=_p2_sess(), **top)
    _P2_PATS = _HN_PAGE_PATS[:3] + (r"/\* ---------- scopes: colour and order from the engine only ---------- \*/\n.*?\nconst CAMSHORT=[^\n]*\n",) + _HN_PAGE_PATS[3:] + (
        r"const WINDOW=\(\)=>RULES\(\)\.activeWindowNights;.*?/\* ==== end of the phase 2 pure layer ==== \*/",
        r"function splitName\(n\)\{[^\n]*\n", r"const commonName=[^\n]*\n",
        r"function filtLabel\(f\)[^\n]*\nfunction filtersTxt\(filters\)[^\n]*\nfunction subsTxt\(exps\)[^\n]*\n")
    _P2_HARNESS = r"""
let WARN_N=2; const out={};
out.units=unitsOf().map(u=>[u.id,u.cams,u.onScope,u.onScopeCurrent,u.active,u.fromEngine]);
out.cards=landingCards().map(c=>({id:c.id,label:c.label,title:c.title,onTxt:c.onTxt,active:c.active,current:c.current.map(p=>[p.target,p.camera,p.hoursTxt,p.nightsTxt,p.scope]),next:c.next,nextCal:c.nextCal,more:c.more,done:c.done,empty:c.empty,strip:c.strip.length,lastOut:c.lastOut,colour:c.colour}));
out.status=statusLine(); out.explore=exploreItems().map(i=>[i.id,i.label,i.holds,i.count||0]);
out.find=findMatches("7380").map(h=>[h.name,h.anchor,h.cams]); out.findNone=findMatches("zzz").length;
const wiz=TG.find(t=>t.name.startsWith("Wizard")); const pm=wiz?projectModel(wiz,"Askar FRA400"):null;
out.proj=pm&&{target:pm.target,camera:pm.camera,unit:pm.unit&&pm.unit.id,state:pm.state,stateWord:pm.stateWord,reason:pm.reason,next:pm.next,hoursTxt:pm.hoursTxt,nights:pm.nights,first:pm.first,last:pm.last,filters:pm.filters,perNight:pm.perNight.length,others:pm.others.map(o=>[o.camera,o.hours,o.nights]),chips:pm.chips};
out.also=wiz?alsoOnDisk(wiz,["Askar FRA400","Askar 107PHQ"]):""; out.anchor=wiz?anchorScope(wiz):null;
const zwo=unitsOf().find(u=>u.id==="ZWO"); out.rows=zwo?Object.fromEntries(Object.entries(unitRows(zwo,{})).map(([k,v])=>[k,Array.isArray(v)?v.map(p=>p.target+"|"+p.camera):v])):null;
out.rowsFiltered=zwo?unitRows(zwo,{states:["done"]}).total:null;
out.month=thisMonthLine(); out.ready=readyLine(); out.recent=recentNights(3).map(r=>r.text);
out.next=Object.fromEntries(PROGS.map(p=>[p.target+"|"+p.camera,nextActionTxt(p)]));
process.stdout.write(JSON.stringify(out));
"""
    _p2_pieces = [re.search(p_, body, re.S) for p_ in _P2_PATS]
    check("P2 page: the served page carries the phase 2 layers and controls: the landing (RENDER.overview with unit cards), "
          "the unit layer (openUnit, RENDER.unit) and the project layer (openProjectLayer, RENDER.project) with a way back, "
          "Explore / Find / Filter in the bar, the status line in the header, the build time and the server pill in the footer, "
          "container queries at 600 and 840 px, the reduced-motion rule, the layer slide, the pure layer's markers, orderDatasets "
          "still the one order, the Nights heatmap shared with the unit layer, and every §10 string of SPEC-2",
          lambda: all(_p2_pieces)
          and "function openUnit(" in body and "function openProjectLayer(" in body and "function backFrom(" in body
          and "RENDER.overview=function" in body and "RENDER.unit=function" in body and "RENDER.project=function" in body
          and "RENDER.ready=function" in body and "RENDER.archive=function" in body and "RENDER.scopes=function" in body
          and "function unitsOf()" in body and "function cardModel(" in body and "function statusLine()" in body and "function nextActionTxt(" in body
          and "function exploreItems()" in body and "function findMatches(" in body and "function unitRows(" in body and "function projectModel(" in body
          and 'id="status"' in body and 'id="exploreBtn"' in body and 'id="exploreMenu"' in body and 'id="find"' in body and 'id="filterBtn"' in body and 'id="filterPop"' in body
          and re.search(r'<footer class="foot"><div class="wrap"><div class="fresh" id="fresh"></div>', body) and 'lv.id="live"' in body
          and "@container cards (min-width:600px)" in body and "@container cards (min-width:840px)" in body and "container-type:inline-size" in body
          and "@media (prefers-reduced-motion: reduce)" in body and "section.view.entering.fwd" in body and "section.view.entering.back" in body and "if(reduced()) instant=true;" in body
          and body.count("orderDatasets(") >= 10 and "function heatmapInto(" in body and "heatmapInto(hb,new Set(u.cams)" in body
          and "units:[],thisMonth:null,recordsUpTo:null,status:null,space:null" in body and 'kind:"archive-show",rel:pm.rel' in body
          and "function openScope(cam)" in body and "function scopePanelFor(cam" in body and body.count("openScope(") >= 4
          and "function openNight(cam,night,target,host" in body and "function nightPanelFor(cam,night,target)" in body
          and '["90","90 nights",90],["365","a year",365],["all","everything",' in body and "what it has been doing" in body and "Timeline of its projects" in body
          and "function normalise(d)" in body and "reconciliation:[],warnings:[]" in body and "What each scope captured" in body and "Needs your attention" in body
          and "Astro Archive Observatory" in body and body.count('<script id="dataset" type="application/json">') == 1 and "__DATASET__" not in body
          and 'kind:"observatory-ready"' in body and "Nothing captured in " in body and "The importer isn't answering. Showing the build from " in body
          and "Couldn't check data safety: " in body and "Everything's safe" in body and "records up to " in body and "more ready to process" in body,
          str([bool(m_) for m_ in _p2_pieces]))
    if _node and all(_p2_pieces):
        _p2_js = ("let D=JSON.parse(require('fs').readFileSync(0,'utf8'));\n" + _p2_pieces[0].group(0) + _p2_pieces[1].group(0) + "D=normalise(D);\n"
                  + "\n".join(m_.group(0) for m_ in _p2_pieces[2:]) + _P2_HARNESS)

        def _p2_run(record):
            r_ = subprocess.run([_node, "-e", _p2_js], input=json.dumps(record), capture_output=True, text=True, timeout=30)
            if r_.returncode != 0:
                return {"error": r_.stderr[-500:]}
            try:
                return json.loads(r_.stdout)
            except ValueError as e_:
                return {"error": str(e_) + r_.stdout[-200:]}
        _d1 = _p2_run(_p2_obs(_HN))                                                   # a 1.8.0 panel: no units[], no status
        _d2 = _p2_run(_p2_obs(_HN, units=_P2_UNITS, recordsUpTo="2026-10-23", thisMonth={"month": "2026-10", "movedForward": 5, "finished": 2, "items": []},
                              status={"checked": True, "reason": "", "onlyHere": 0, "machine": "PC", "pendingFiles": 0, "pendingCamera": None, "pendingSeenAt": None, "servedAgeHours": 2.0, "publishedFrom": None}))
        _c1 = {c["id"]: c for c in _d1.get("cards", [])}
        check("P2 page: the landing worked out from scopes[] and sessions[] alone (no units[] in the record): one card per unit in the "
              "fixed order (the two Askars collapsed into the ZWO unit where the first Askar sits, then the Seestars), the ZWO card names "
              "its scope from the newest Askar session ('ZWO · on the FRA400'), each card carries its current project(s) newest first with "
              "hours and nights (the Askar per project on the ZWO card), one next action in words (calibration first), '{n} more ready "
              "to process', and the idle S30 is the Resting row with 'Nothing captured in 30 nights. Last out: Sat 30 Aug 2025'",
              lambda: "error" not in _d1 and [c["id"] for c in _d1["cards"]] == ["ZWO", "S30P", "S50", "S30"]
              and [c["active"] for c in _d1["cards"]] == [True, True, True, False] and all(not u[5] for u in _d1["units"])
              and _c1["ZWO"]["title"] == "ZWO · on the FRA400" and _c1["ZWO"]["onTxt"] == "on the FRA400" and _c1["ZWO"]["colour"] == "#D55E00"
              and [p[0] for p in _c1["ZWO"]["current"]] == ["Beehive Cluster (M 44)", "Helix Nebula (NGC 7293)"] and _c1["ZWO"]["current"][1][4] == "107PHQ" and _c1["ZWO"]["current"][0][2:4] == ["3.2 h", "2 nights"]
              and _c1["ZWO"]["more"] == "1 more ready to process · 12.5 h" and _c1["ZWO"]["strip"] == 3
              and [p[0] for p in _c1["S30P"]["current"]] == ["Tadpoles Nebula (IC 410)", "Wizard Nebula (NGC 7380)"] and _c1["S30P"]["current"][0][4] == ""
              and _c1["S30P"]["next"] == "Still capturing · ready from " + _hn_date("Fri 6 Nov", 2026) and _c1["S30P"]["more"] == "1 more ready to process · 4.0 h"
              and _c1["S50"]["current"][0][0] == "Black Eye Galaxy (M 64)" and _c1["S50"]["next"] == "Next step: collect the lights (9 nights, 3,000 frames)" and _c1["S50"]["more"] == ""
              and _c1["S30"]["current"] == [] and _c1["S30"]["empty"] == "Nothing captured in 30 nights. Last out: " + _hn_date("Sat 30 Aug", 2025)
              and _c1["S30"]["lastOut"] == "2025-08-30" and _c1["S30"]["title"] == "S30",
              json.dumps(_d1.get("error") or _d1.get("cards"))[:1200])
        _c2 = {c["id"]: c for c in _d2.get("cards", [])}
        check("P2 page: the engine's units[] win when the record carries them (they are the contract): the ZWO card says 'last on the "
              "107PHQ' with the engine's current project, '2 more ready to process · 15.7 h' and a calm Done note naming the object and "
              "its final's date; the S30 Pro's next action is the engine's calibration line first; the S50 rests on the engine's word; "
              "'This month' and 'records up to' come from the record",
              lambda: "error" not in _d2 and [c["id"] for c in _d2["cards"]] == ["ZWO", "S30P", "S50"] and all(u[5] for u in _d2["units"])
              and _c2["ZWO"]["title"] == "ZWO · last on the 107PHQ" and _c2["ZWO"]["colour"] == "#009E73"
              and [p[0] for p in _c2["ZWO"]["current"]] == ["Helix Nebula (NGC 7293)"] and _c2["ZWO"]["next"] == "Finish it · master in the folder"
              and _c2["ZWO"]["more"] == "2 more ready to process · 15.7 h" and _c2["ZWO"]["done"] == "Done · Beehive Cluster · final of " + _hn_date("Fri 16 Oct", 2026)
              and _c2["S30P"]["next"] == "Darks or flats missing: no flats filed with these lights" and _c2["S30P"]["nextCal"] is True
              and _c2["S50"]["active"] is False and _c2["S50"]["empty"] == "Nothing captured in 30 nights. Last out: " + _hn_date("Thu 1 Oct", 2026) and _c2["S50"]["more"] == "1 more ready to process · 29.4 h"
              and _d2["month"]["text"] == "This month: 5 projects moved forward · 2 finished" and _d2["month"]["fromEngine"] is True
              and _d2["status"] == {"level": "quiet", "text": "Everything's safe", "more": "records up to " + _hn_date("Fri 23 Oct", 2026), "upTo": "2026-10-23", "facts": []},
              json.dumps(_d2.get("error") or [_d2.get("cards"), _d2.get("month"), _d2.get("status")])[:1200])
        _st = lambda **st: _p2_run(_p2_obs(_HN, status=dict({"checked": True, "reason": "", "onlyHere": 0, "machine": "PC", "pendingFiles": 0, "pendingCamera": None, "pendingSeenAt": None, "servedAgeHours": 2.0, "publishedFrom": None}, **st)))["status"]
        _s_quiet, _s_risk, _s_stale, _s_unch = (_st(), _st(onlyHere=1204, machine="Mac", pendingFiles=87, pendingCamera="ASIAir", pendingSeenAt="2026-10-18T08:50:00+00:00"),
                                                _st(servedAgeHours=41.0, publishedFrom="PC"), _st(checked=False, reason="the ledger is locked by an import"))
        check("P2 page: the status line's four variants from the panel's `status`: quiet 'Everything's safe · records up to Thu 22 Oct' "
              "(the newest night with frames when the record has no recordsUpTo); amber for frames only on this computer and files waiting "
              "on a camera with its last scan; amber for a served record over 24 h old; amber 'Couldn't check data safety: {reason}'; and "
              "a record from an older panel (no status) is amber too, saying the facts weren't checked, never 'safe'",
              lambda: _s_quiet == {"level": "quiet", "text": "Everything's safe", "more": "records up to " + _hn_date("Thu 22 Oct", 2026), "upTo": "2026-10-22", "facts": []}
              and _s_risk["level"] == "amber" and _s_risk["text"] == "1,204 frames only on the Mac"
              and _s_risk["more"] == "87 files waiting on the ASIAir, last scan " + _hn_date("Sun 18 Oct", 2026) + " · records up to " + _hn_date("Thu 22 Oct", 2026)
              and _s_stale["level"] == "amber" and _s_stale["text"] == "this record is 2 days old (the PC's copy)"
              and _s_unch["level"] == "amber" and _s_unch["text"] == "Couldn't check data safety: the ledger is locked by an import"
              and _d1["status"]["level"] == "amber" and _d1["status"]["text"] == "Couldn't check data safety: this record doesn't carry the safety facts",
              json.dumps([_s_quiet, _s_risk, _s_stale, _s_unch, _d1.get("status")])[:1200])
        _ex = {x[1]: x for x in _d1.get("explore", [])}
        _holds = " ".join(x[2] for x in _d1.get("explore", []))
        check("P2 page: the Explore menu names every view of the before record (Ready to process = What to do next, Imaging nights = Nights, "
              "What each scope captured + What each scope shot + Projects that moved lately, Sky = Sky coverage, Footprints, Coverage, "
              "Equipment, Data checks with its count and Needs your attention, Archive = the header totals + Where the hours went, Pipeline, "
              "Targets = Projects); Find opens a project anchored to the scope with the most recent capture and says when nothing matches",
              lambda: [x[1] for x in _d1["explore"]] == ["Ready to process", "Imaging nights", "What each scope captured", "Sky", "Footprints", "Coverage", "Equipment", "Data checks", "Archive", "Pipeline", "Targets"]
              and all(s in _holds for s in ("What to do next", "Nights", "What each scope shot", "Projects that moved lately", "Sky coverage", "Needs your attention", "Where the hours went", "Projects", "the header totals"))
              and _ex["Data checks"][3] == 2 and _ex["Ready to process"][3] == 3
              and _d1["find"] == [["Wizard Nebula (NGC 7380)", "Seestar S30 Pro", ["Askar FRA400", "Seestar S30 Pro"]]] and _d1["findNone"] == 0 and _d1["anchor"] == "Seestar S30 Pro",
              json.dumps([_d1.get("explore"), _d1.get("find")])[:1200])
        check("P2 page: the layers' models: a unit's rows are grouped Ready / Finish it / Still capturing / Done, most recent capture first, "
              "without its current projects, and the Filter narrows them; a project on one scope carries its state and reason, the next step, "
              "hours, nights, first and last imaged, integration by filter, one row per night and the other scopes' data; 'Also on disk' names "
              "the other scopes' hours; the lines under the cards add up (Ready to process, Recent nights, This month)",
              lambda: _d1["rows"] == {"ready": ["Wizard Nebula (NGC 7380)|Askar FRA400"], "finish": [], "capturing": [], "done": [], "samples": [], "total": 1} and _d1["rowsFiltered"] == 0
              and _d1["proj"]["camera"] == "Askar FRA400" and _d1["proj"]["unit"] == "ZWO" and _d1["proj"]["stateWord"] == "Ready to process"
              and _d1["proj"]["reason"] == "ready since Fri 16 Oct · 12.5 h on the FRA400" and _d1["proj"]["next"] == "Next step: collect the lights (5 nights, 900 frames)"
              and _d1["proj"]["hoursTxt"] == "12.5 h" and _d1["proj"]["first"] == "2026-10-01" and _d1["proj"]["last"] == "2026-10-01"
              and _d1["proj"]["filters"] == [{"filter": "L-eXtreme", "hours": 12.5}] and _d1["proj"]["perNight"] == 1
              and _d1["proj"]["others"] == [["Seestar S30 Pro", 0.75, 2]] and _d1["proj"]["chips"] == ["Askar FRA400", "Seestar S30 Pro"]
              and _d1["also"] == "Also on disk: 45 min on the S30 Pro"
              and _d1["ready"]["text"] == "Ready to process: 3 datasets · 45.9 h" and _d1["month"]["text"] == "This month: 3 projects moved forward · 1 finished"
              and _d1["recent"][0] == _hn_date("Thu 22 Oct", 2026) + " · 1.5 h · S30 Pro: Tadpoles Nebula" and len(_d1["recent"]) == 3
              and _d1["next"]["Helix Nebula (NGC 7293)|Askar 107PHQ"] == "Finish it · master in the folder" and _d1["next"]["Beehive Cluster (M 44)|Askar FRA400"] == "Done · final of " + _hn_date("Fri 16 Oct", 2026)
              and _d1["next"]["NGC 6229|Seestar S30 Pro"] == "Sample · 3 min",
              json.dumps([_d1.get("rows"), _d1.get("proj"), _d1.get("also"), _d1.get("ready"), _d1.get("month"), _d1.get("recent"), _d1.get("next")])[:1500])
        _d3 = _p2_run(_hn_obs(_old_rows))                      # 1.7.6 rows, no scopes, no sessions: nothing to derive from
        _d4 = _p2_run(_p2_obs(_old_rows))                      # 1.7.6 rows with scopes and sessions: everything derived
        check("P2 page: an OLD record renders with no script error and no 'undefined': with no scopes or sessions at all the landing is empty "
              "(no cards, the status line amber and honest); with scopes and sessions but none of the phase 1 or 2 fields the cards, the "
              "next actions (from readyOn or the last night plus the quiet period), the lines and the layers' models are worked out by the page",
              lambda: "error" not in _d3 and "error" not in _d4 and "undefined" not in json.dumps(_d3) and "undefined" not in json.dumps(_d4)
              and _d3["cards"] == [] and _d3["status"]["level"] == "amber"
              and [c["id"] for c in _d4["cards"]] == ["ZWO", "S30P", "S50", "S30"] and _d4["cards"][0]["title"] == "ZWO · on the FRA400"
              and _d4["next"]["Tadpoles Nebula (IC 410)|Seestar S30 Pro"] == "Still capturing · ready from " + _hn_date("Fri 6 Nov", 2026)
              and _d4["next"]["Wizard Nebula (NGC 7380)|Seestar S30 Pro"] == "Still capturing · ready from " + _hn_date("Wed 4 Nov", 2026)
              and _d4["next"]["Black Eye Galaxy (M 64)|Seestar S50"] == "Next step: collect the lights (9 nights, 3,000 frames)"
              and _d4["proj"]["reason"] == "nothing new for 22 nights" and _d4["month"]["text"] == "This month: 0 projects moved forward · 0 finished"
              and _d4["ready"]["n"] == 3,
              json.dumps([_d3.get("error"), _d4.get("error"), _d3.get("cards"), _d3.get("status"), [c["id"] for c in _d4.get("cards", [])], _d4.get("next")])[:1200])
    else:
        skip("P2 page: the phase 2 pure layer in node (needs node and the marked regions)")
finally:
    procn.terminate()
    procn.wait(timeout=30)

# ═══════════════ CHAIN OT: two importing computers, one truth (1.7.1) ════════
# The panel on the PC, with the Mac's record on the archive: rows the Mac
# verified are a third state (no clear, no discard from here), the scan card
# names the record and its age, a panel import files into the archive at once
# and says so, the Dashboard shows both computers, and the page's labels come
# from the engine (so the same page is right on both machines).
from datetime import datetime as _otdt, timezone as _ottz
envo = teh.Env("APPOT", asiair=True, seestar=True)
envo.env.update({"ASTRO_SHIP_FOLDER": "pc", "ASTRO_SHIP_LOG": "shipped-pc.jsonl", "ASTRO_MACHINE_ID": "pc"})
for _r in ("ZWO Askar Scopes", "S30P"):
    os.makedirs(os.path.join(envo.archive, _r), exist_ok=True)
_oto_mac = os.path.join(envo.archive, "_verify", "mac"); os.makedirs(_oto_mac, exist_ok=True)
_oto_l1 = envo.add_light("Plan", "M 81", "0001", dt="20261001-220000")   # the Mac's, verified on the archive
_oto_l2 = envo.add_light("Plan", "M 81", "0002", dt="20261001-221000")   # new to both
_oto_a = envo.add_seestar_sub("M 42", "20261001-210000")                 # the Mac's
_oto_b = envo.add_seestar_sub("M 42", "20261001-210500")                 # new
_oto_m33 = [envo.add_seestar_sub("M 33", f"20261002-21{i}000") for i in (0, 1)]   # all the Mac's
def _oto_rel(p, root):
    return os.path.relpath(p, root).replace("\\", "/")
def _oto_row(p, root, **kw):
    r = {"filename": os.path.basename(p), "size": os.path.getsize(p), "sha256": "a" * 64,
         "origin": "import", "verifiedAtImport": True, "archiveVerifiedAt": "2026-10-05T030000"}
    r.update(kw); return r
_oto_files = {_oto_rel(_oto_l1, envo.cam): _oto_row(_oto_l1, envo.cam, target="M 81", sourceType="Plan"),
              _oto_rel(_oto_a, envo.svol): _oto_row(_oto_a, envo.svol, target="M 42", device="seestar",
                                                    camera="ZWO Seestar S30 Pro", sourceType="sub")}
for p in _oto_m33:
    _oto_files[_oto_rel(p, envo.svol)] = _oto_row(p, envo.svol, target="M 33", device="seestar",
                                                  camera="ZWO Seestar S30 Pro", sourceType="sub")
with open(os.path.join(_oto_mac, "ledger-snapshot.json"), "w", encoding="utf-8") as f:
    json.dump({"schema": "ledger-snapshot/1", "machine": "Mac", "machineId": "mac", "machineUid": "mac-uid",
               "at": _otdt.now(_ottz.utc).isoformat(timespec="seconds"), "files": _oto_files,
               "calibration": {}, "library": {}, "discarded": {}, "customNames": {}, "skiplist": [],
               "equipment": {}}, f)
PORTO = int(envo.env["ASTRO_PANEL_PORT"])
URLO = f"http://127.0.0.1:{PORTO}"
proco = start_panel(envo, PORTO)
try:
    own_panel(URLO, envo, proco, "OT the two-computer panel answers with its own instance id")
    pageo = load_token(URLO)
    def wait_o(pred, timeout=90):
        t0 = time.time()
        while time.time() - t0 < timeout:
            st = api("/api/state", url=URLO)
            if pred(st):
                return st
            time.sleep(0.3)
        raise TimeoutError("OT: condition not met; last status " + str(st.get("status")))
    api("/api/scan", {}, url=URLO)
    so = wait_o(lambda st: st["status"] == "idle" and st["scan"])
    rows = {t["name"]: t for t in so["scan"]["targets"]}
    check("OT the scan's rows carry the third state: M 81 one new, one backed up by the Mac (verified on the "
          "archive); M 42 one new, one the Mac's; M 33 nothing new, both the Mac's; the scan names the record",
          rows.get("M 81", {}).get("new") == 1 and rows["M 81"].get("elsewhere") == 1
          and rows["M 81"].get("elsewhereArchived") == 1 and rows["M 81"].get("elsewhereMachine") == "Mac"
          and rows.get("M 42", {}).get("new") == 1 and rows["M 42"].get("elsewhere") == 1
          and rows.get("M 33", {}).get("new") == 0 and rows["M 33"].get("elsewhere") == 2
          and (so["scan"].get("other") or {}).get("machine") == "Mac" and so["scan"].get("elsewhereFiles") == 4
          and so["scan"]["sides"]["hereSide"] == "pc" and so["scan"]["sides"]["there"] == "Mac",
          json.dumps({k: {x: v.get(x) for x in ("new", "elsewhere", "elsewhereArchived", "elsewhereMachine")}
                      for k, v in rows.items()}) + json.dumps(so["scan"].get("other")))
    check("OT the scan's log line counts what the Mac already holds and names its record",
          any("already backed up by the Mac" in ln and "its record from" in ln for ln in so["log"]),
          json.dumps([ln for ln in so["log"] if "Scan:" in ln])[:400])
    check("OT /api/state carries the two computers' names, and the page builds its 'where' labels from them "
          "(no hard-coded Mac/PC), with the third-state pill and 'clear it from the …'",
          so.get("sides", {}).get("there") == "Mac" and "function projWhere(" in pageo
          and "backed up by the ${esc(otherWho(t))}" in pageo and "clear it from the" in pageo
          and "on the ${SIDES.there}" not in pageo and 'pc:"on this PC"' not in pageo,
          json.dumps(so.get("sides")))
    pj = api("/api/projects", url=URLO)
    check("OT /api/projects carries the same names", pj.get("sides", {}).get("hereSide") == "pc", json.dumps(pj.get("sides")))
    with urllib.request.urlopen(URLO + "/dashboard?t=1", timeout=15) as resp:
        dash0 = resp.read().decode()
    check("OT the Dashboard with no ledger here shows the Mac's record and says so",
          "Nothing has been imported on this" in dash0 and "This is the Mac's record" in dash0 and "NoneType" not in dash0,
          dash0[-300:])
    # import the one new Seestar sub: the first import here, filed into the (local) archive at once
    api("/api/import", {"names": ["M 42"]}, url=URLO)
    t0 = time.time()
    while time.time() - t0 < 120:
        st = api("/api/state", url=URLO)
        if st["status"] == "idle":
            break
        if st.get("question"):
            api("/api/answer", {"id": st["question"]["id"], "value": "n"}, url=URLO)
        time.sleep(0.3)
    so = st
    check("OT the first import on this computer names the Mac's record in the log, copies only the new sub, "
          "files into the archive at once and says so, and leaves this computer's record on the archive",
          any("First import on this" in ln and "The Mac's record from" in ln for ln in so["log"])
          and "filed into the archive" in str(so.get("lastResult"))
          and os.path.isfile(os.path.join(envo.archive, "_verify", "pc", "ledger-snapshot.json"))
          and _oto_rel(_oto_b, envo.svol) in json.load(open(os.path.join(envo.state, "ledger.json")))["files"]
          and _oto_rel(_oto_a, envo.svol) not in json.load(open(os.path.join(envo.state, "ledger.json")))["files"],
          json.dumps([so.get("lastResult")] + [ln for ln in so["log"] if "First import" in ln or "already backed up" in ln])[:600])
    with urllib.request.urlopen(URLO + "/dashboard?t=2", timeout=15) as resp:
        dash1 = resp.read().decode()
    check("OT the Dashboard now shows this computer's imports and the Mac's record together",
          "and the Mac's record together" in dash1 and "NoneType" not in dash1, dash1[-300:])
    api("/api/scan", {}, url=URLO)
    so = wait_o(lambda st: st["status"] == "idle" and st["scan"] and st.get("scannedAt"))
    rows = {t["name"]: t for t in so["scan"]["targets"]}
    check("OT after the import M 42 is all backed up (one here, one the Mac's): no new frames, still one 'elsewhere'",
          rows.get("M 42", {}).get("new") == 0 and rows["M 42"].get("elsewhere") == 1, json.dumps(rows.get("M 42")))
    api("/api/discard", {"name": "M 33_sub"}, url=URLO)
    so = wait_o(lambda st: st["status"] == "idle" and st.get("lastResult"))
    check("OT DISCARD of a target the Mac verified is refused from here ('clear it from the Mac'), no card, "
          "nothing leaves the camera",
          str(so.get("lastResult")).startswith("Discard refused") and so.get("question") is None
          and all(os.path.isfile(p) for p in _oto_m33)
          and any("clear it from the Mac" in ln for ln in so["log"]),
          json.dumps([so.get("lastResult")] + [ln for ln in so["log"] if "Mac" in ln][-3:]))
finally:
    proco.terminate()
    proco.wait(timeout=30)

# ═══════════════ CHAIN PR: the panel after the 1.7.1 review (16 Oct) ═════════
# The Mac's panel with a reachable archive on which the PC holds the ship
# lock: the import's banner says the ship didn't finish (not "filed"); a
# request while the importer is busy is answered with why; cross-site GETs
# that act or cost are refused; an application bundle on the archive is never
# opened; bad calDecisions are a 400; the Dashboard is built off the request
# thread and /api/state says when; the page keeps ticks across rescans, polls
# one at a time and takes the two computers' names from /api/projects.
envp = teh.Env("APPPR", asiair=True, seestar=False)
envp.env["ASTRO_SHIP_FOLDER"] = "mac"
_pr_root = os.path.join(envp.archive, "ZWO Askar Scopes")
os.makedirs(_pr_root, exist_ok=True)                       # the archive is reachable
_pr_m81 = envp.add_light("Plan", "M 81", "0001", dt="20261003-220000")
_pr_mys = envp.add_light("Live", "MYSTERY 9", "0001", dt="20261003-230000", focallen=402)  # asks its name
# folders on the archive: a plain one, an application bundle, a bundle in disguise
_pr_plain = os.path.join(_pr_root, "Wizard Nebula (NGC 7380)")
_pr_app = os.path.join(_pr_root, "Evil.APP")
_pr_plist = os.path.join(_pr_root, "Looks Plain")
for _d in (_pr_plain, _pr_app, os.path.join(_pr_plist, "Contents")):
    os.makedirs(_d, exist_ok=True)
with open(os.path.join(_pr_plist, "Contents", "Info.plist"), "w") as f:
    f.write("<plist/>")
# the PC is shipping right now: a live lock (renewed this second, another machine)
_pr_lockdir = os.path.join(envp.archive, "_verify", "lock")
os.makedirs(_pr_lockdir, exist_ok=True)
_pr_now = _otdt.now(_ottz.utc).isoformat(timespec="seconds")
with open(os.path.join(_pr_lockdir, "ship.lock"), "w", encoding="utf-8") as f:
    json.dump({"schema": "ship-lock/1", "machineId": "pc", "machine": "pc-machine-uid", "host": "SKYLARKPC",
               "platform": "windows", "pid": os.getpid(), "op": "ship", "startedAt": _pr_now, "renewedAt": _pr_now}, f)
with open(teh.SCRIPT, encoding="utf-8") as f:
    _pr_engine_reports = "SHIP_AFTER_IMPORT_REPORTS = True" in f.read()
PORTP = int(envp.env["ASTRO_PANEL_PORT"])
URLP = f"http://127.0.0.1:{PORTP}"
procp = start_panel(envp, PORTP)

def _pr_get(path, headers=None):
    """A GET as a browser would send it; (status, body)."""
    req = urllib.request.Request(URLP + path, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")

try:
    own_panel(URLP, envp, procp, "PR the reviewed panel answers with its own instance id")
    pagep = load_token(URLP)
    def wait_p(pred, timeout=90):
        t0 = time.time()
        while time.time() - t0 < timeout:
            st = api("/api/state", url=URLP)
            if pred(st):
                return st
            time.sleep(0.3)
        raise TimeoutError("PR: condition not met; last status " + str(st.get("status")))
    # ── the page (static) ───────────────────────────────────────────────────
    check("PR the page polls one at a time and drops an older answer, keeps ticks and pairing decisions "
          "across rescans, draws a scan that can't be shown as a note, loads the Dashboard frame once and "
          "again only when dashboardAt changes, takes the sides /api/projects gives, reloads the Report when "
          "a report finished (no 1.5 s timer), gives focus back after a card, takes Space on row buttons, "
          "says what to do when the Observatory frame is a note, and tells the banner why a button did nothing",
          "tickBusy" in pagep and "seq!==tickSeq" in pagep and "wasTicked" in pagep and "wasCal" in pagep
          and "The scan couldn't be shown:" in pagep and "s.dashboardAt!==dashAt" in pagep
          and 'if(b.dataset.tab==="dash" && !dashShown) showDash();' in pagep
          and "if(pj&&pj.sides) SIDES=pj.sides;" in pagep and 'prevStatus==="reporting"' in pagep
          and "setTimeout(loadReport,1500)" not in pagep and "qPrevFocus=document.activeElement" in pagep
          and pagep.count('e.key===" "') == 2 and "See the note in the frame." in pagep
          and "function startOp(" in pagep and 'startOp("/api/import"' in pagep and 'startOp("/api/scan"' in pagep
          and "importedHere" in pagep and "so anything the ${esc(SIDES.there)} imported shows as new here" in pagep,
          "")
    import shutil as _shp
    _nodep = _shp.which("node") or next((p for p in ("/opt/node22/bin/node", "/usr/local/bin/node")
                                         if os.path.isfile(p)), None)
    _scriptp = re.search(r"<script>(.*?)</script>", pagep, re.S)
    if _nodep and _scriptp:
        _jsp = _scriptp.group(1)
        r_parse = subprocess.run([_nodep, "-e", "new Function(require('fs').readFileSync(0,'utf8'))"],
                                 input=_jsp, capture_output=True, text=True, timeout=30)
        check("PR the panel's inline script still parses (node)", r_parse.returncode == 0, r_parse.stderr[-300:])
        # projectsHtml rendered as the PC, from the sides the answer carries; the pill as the Mac
        _piecesp = [re.search(p_, _jsp, re.S).group(0) for p_ in
                    (r"const MONTHS=[^\n]*", r"const esc=[^\n]*", r"const fmtNight=[^\n]*",
                     r"const PROJ_WHERE=.*?\nfunction projectsHtml\(pj, opts\)\{.*?\n\}\n",
                     r"const otherAll=.*?\nfunction pillFor\(t\)\{.*?\n\}\n")]
        _fixp = {"ok": True, "opener": "Explorer",
                 "sides": {"here": "PC", "hereSide": "pc", "there": "Mac", "thereSide": "mac"},
                 "projects": {"schema": "projects/1", "generated_at": "2026-10-16T08:00:00+00:00", "quiet_period_days": 14,
                              "projects": [{"target_id": "M31", "name": "Andromeda", "datasets": [
                                  {"scope_name": "Askar FRA400", "status": "capturing", "nights": 1, "integration_seconds": 600,
                                   "last_session": "2026-10-10", "locations": ["pc-unchecked", "mac"], "archive_rel": None}]}]}}
        _harp = ("let deskSel=null;\n" + "\n".join(_piecesp)
                 + f"\nprocess.stdout.write(projectsHtml({json.dumps(_fixp)}));\n"
                 + "process.stdout.write('\\n---\\n'+pillFor({device:'asiair',new:0,elsewhere:3,importedHere:5,elsewhereMachine:'Mac'}));\n"
                 + "process.stdout.write('\\n---\\n'+pillFor({device:'asiair',new:0,elsewhere:3,elsewhereMachine:'Mac'}));\n"
                 + "process.stdout.write('\\n---\\n'+pillFor({device:'asiair',new:0,elsewhere:0,importedHere:5}));\n")
        r_pr = subprocess.run([_nodep, "-e", _harp], capture_output=True, text=True, timeout=30)
        _outp = r_pr.stdout.split("\n---\n")
        check("PR projectsHtml takes the sides it is given (rendered as the PC: 'on this PC (per its ledger) and on "
              "the Mac'); the ASIAir pill splits what each computer holds, and reads as before when the engine "
              "doesn't say (nothing 'undefined')",
              r_pr.returncode == 0 and len(_outp) == 4
              and "on this PC (per its ledger) and on the Mac" in _outp[0]
              and _outp[1] == '<span class="bak">backed up: 5 on this PC, 3 by the Mac · kept on ASIAir</span>'
              and "backed up by the Mac" in _outp[2] and "undefined" not in r_pr.stdout
              and "kept on ASIAir" in _outp[3] and "by the" not in _outp[3],
              (r_pr.stderr or r_pr.stdout)[-600:])
    else:
        skip("PR node isn't installed: the inline script's parse check and the rendered pieces")
    # ── cross-site GETs (item 9) ────────────────────────────────────────────
    _cs = {"Sec-Fetch-Site": "cross-site"}
    check("PR a GET that acts or costs is refused when the browser says it came from another site "
          "(Sec-Fetch-Site: cross-site → 403 for /api/state, /dashboard, /api/archive/index), allowed "
          "without the header, same-origin, or for /api/ping",
          _pr_get("/api/state", _cs)[0] == 403 and _pr_get("/dashboard?t=1", _cs)[0] == 403
          and _pr_get("/api/archive/index", _cs)[0] == 403
          and _pr_get("/api/state")[0] == 200 and _pr_get("/api/state", {"Sec-Fetch-Site": "same-origin"})[0] == 200
          and _pr_get("/api/ping", _cs)[0] == 200,
          json.dumps([_pr_get("/api/state", _cs)[0], _pr_get("/dashboard?t=1", _cs)[0], _pr_get("/api/state")[0]]))
    _stp = status_line(URLP)
    check("PR /api/status always has the status line's shape (the line itself, or 'Status unknown: still working it out')",
          isinstance(_stp, dict) and STATUS_KEYS <= set(_stp) and isinstance(_stp.get("text"), str), json.dumps(_stp))
    # ── the archive open (item 11) ──────────────────────────────────────────
    r_app = api("/api/archive/open", {"rel": "ZWO Askar Scopes/Evil.APP"}, url=URLP)
    r_plist = api("/api/archive/open", {"rel": "ZWO Askar Scopes/Looks Plain"}, url=URLP)
    r_plain = api("/api/archive/open", {"rel": "ZWO Askar Scopes/Wizard Nebula (NGC 7380)"}, url=URLP)
    _opens = teh.os_calls(envp.root, "open")
    check("PR a folder named *.app (any case) or carrying Contents/Info.plist is refused by /api/archive/open "
          "(400, 'application') and nothing is opened; a plain folder still opens",
          r_app.get("_status") == 400 and "application" in str(r_app.get("error"))
          and r_plist.get("_status") == 400 and r_plain.get("ok") is True
          and len(_opens) == 1 and _opens[0].get("target") == _pr_plain,
          json.dumps([r_app, r_plist, r_plain, _opens]))
    # ── bad calDecisions (item 20) ──────────────────────────────────────────
    r_bad = api("/api/import", {"names": ["M 81"], "calDecisions": {"M 81": True}}, url=URLP)
    check("PR calDecisions whose values aren't maps are a 400, nothing starts",
          r_bad.get("_status") == 400 and r_bad.get("started") is False
          and api("/api/state", url=URLP)["status"] == "idle", json.dumps(r_bad))
    # ── the scan: no record from the PC, said once (items 12, 14) ───────────
    api("/api/scan", {}, url=URLP)
    sp = wait_p(lambda st: st["status"] == "idle" and st["scan"])
    api("/api/scan", {}, url=URLP)
    sp = wait_p(lambda st: st["status"] == "idle" and st["scan"] and st.get("scannedAt"))
    _norec = [ln for ln in sp["log"] if "record isn't on the archive" in ln]
    check("PR with no record from the PC the scan says so once per panel run ('anything the PC imported shows "
          "as new here'), the rows carry importedHere (None from an engine that doesn't say it), and the "
          "other computer is named by its side",
          sp["scan"].get("other") is None and len(_norec) == 1 and "anything the PC imported shows as new here" in _norec[0]
          and all("importedHere" in t for t in sp["scan"]["targets"])
          and all(t.get("importedHere") in (None, 0) for t in sp["scan"]["targets"])
          and sp["scan"]["sides"]["there"] == "PC",
          json.dumps([_norec, [{k: t.get(k) for k in ("name", "new", "importedHere")} for t in sp["scan"]["targets"]]])[:500])
    # ── the Dashboard, built by the worker (item 2) ─────────────────────────
    sp = wait_p(lambda st: st.get("dashboardAt"), timeout=20)
    _dash_at0 = sp["dashboardAt"]
    _code0, _dash0 = _pr_get("/dashboard?t=1")
    check("PR /api/state says when the Dashboard was built; with nothing imported anywhere /dashboard is the note page",
          bool(_dash_at0) and _code0 == 200 and "Nothing has been imported on this Mac yet, and the PC's record" in _dash0,
          json.dumps([_dash_at0, _code0, _dash0[-200:]]))
    # ── import while the PC holds the ship lock; a request while busy (items 1, 6, 13) ─
    r_imp = api("/api/import", {"names": ["M 81", "MYSTERY 9"]}, url=URLP)
    sp = wait_p(lambda st: st["question"] is not None or st["status"] == "idle")
    _busy = None
    _kinds = []
    while sp["question"] is not None:
        q = sp["question"]
        _kinds.append(q["kind"])
        if _busy is None:
            _busy = api("/api/scan", {}, url=URLP)        # the card is up: the importer is busy
            _busy_state = api("/api/state", url=URLP)
        api("/api/answer", {"id": q["id"], "value": "" if q["kind"] == "text" else "n"}, url=URLP)
        time.sleep(0.3)
        sp = wait_p(lambda st: st["question"] is not None or st["status"] == "idle")
    sp = wait_p(lambda st: st["status"] == "idle")
    check("PR a request while the importer is busy is answered with why (started: false, 'The importer is busy "
          "(importing)…'), and the banner says the same",
          r_imp.get("started") is True and _busy is not None and _busy.get("started") is False
          and "busy (importing)" in str(_busy.get("error")) and "busy (importing)" in str(_busy_state.get("lastResult")),
          json.dumps([r_imp, _kinds, _busy, (_busy_state or {}).get("lastResult") if _busy else None]))
    _lockline = [ln for ln in sp["log"] if "shipping into the archive right now" in ln]
    check("PR the import copied both frames, honoured the PC's live ship lock (nothing shipped, said in the log), "
          "and cleared the scan for fresh counts",
          "Imported 2 frame(s) across 2 target(s)" in str(sp.get("lastResult")) and len(_lockline) == 1
          and sp.get("scan") is None and not os.listdir(os.path.join(envp.archive, "ZWO Askar Scopes", "Wizard Nebula (NGC 7380)")),
          json.dumps([sp.get("lastResult"), _lockline]))
    if _pr_engine_reports:
        check("PR the banner is worded on the ship's REAL result: the ship didn't finish (the lock was held), so it "
              "never says 'filed into the archive'",
              "the ship to the archive didn't finish — see the log; the scheduled ship files them later" in str(sp.get("lastResult"))
              and "filed into the archive" not in str(sp.get("lastResult")), str(sp.get("lastResult")))
    else:
        skip("PR the banner on the ship's real result: the engine doesn't report it yet (SHIP_AFTER_IMPORT_REPORTS; "
             "run panel_engine_patch.py)")
    sp = wait_p(lambda st: st.get("dashboardAt") and st["dashboardAt"] != _dash_at0, timeout=30)
    _code1, _dash1 = _pr_get("/dashboard?t=2")
    check("PR after the import the worker rebuilt the Dashboard (dashboardAt changed) and /dashboard is this "
          "computer's dashboard, served from its file",
          sp["dashboardAt"] != _dash_at0 and _code1 == 200 and "Nothing has been imported" not in _dash1
          and "__DATA__" not in _dash1 and '"frames": 2' in _dash1,
          json.dumps([_dash_at0, sp.get("dashboardAt"), _code1, _dash1[:200]]))
    # ── a failed import leaves no stale scan (item 13): a newer importer's ledger ─
    api("/api/scan", {}, url=URLP)
    sp = wait_p(lambda st: st["status"] == "idle" and st["scan"])
    _ledp = os.path.join(envp.state, "ledger.json")
    with open(_ledp, encoding="utf-8") as f:
        _newer = json.load(f)
    _newer["version"] = (_newer.get("version") or 1) + 1
    with open(_ledp, "w", encoding="utf-8") as f:
        json.dump(_newer, f)
    envp.add_light("Plan", "M 81", "0002", dt="20261004-220000")
    api("/api/import", {"names": ["M 81"]}, url=URLP)
    sp = wait_p(lambda st: st["status"] == "idle" and st.get("lastResult"))
    check("PR an import refused before it starts (a newer importer's ledger) still clears the scan: no stale "
          "counts and no live Import button",
          "newer version" in str(sp.get("lastResult")) and sp.get("scan") is None, json.dumps([sp.get("lastResult"), bool(sp.get("scan"))]))
finally:
    procp.terminate()
    procp.wait(timeout=30)

summary()
sys.exit(1 if FAIL else 0)
