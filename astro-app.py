#!/usr/bin/env python3
"""
BrettjoAstro FITS Importer — Control Panel (the app)
==============================================================================
One obvious surface replacing every popup: scan the camera, tick targets,
import with live progress, answer naming/flats questions inline, see the
report and dashboard, eject. Runs the PROVEN import engine in-process
(~/bin/astro-import.py) — this file is presentation only.

Serves http://127.0.0.1:8765 (localhost only). Start:
    python3 ~/bin/astro-app.py            # opens your browser
    python3 ~/bin/astro-app.py --no-browser
Tip: in Safari, File → Add to Dock turns the panel into a Dock app with its
own window. The watcher opens/focuses the panel when the camera is plugged in.
==============================================================================
"""

import argparse
import contextlib
import importlib.util
import json
import os
import subprocess
import sys  # noqa: F401  (kept for parity)
import threading
import time
import webbrowser
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

APP_VERSION = "2.0"
ENGINE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "astro-import.py")

# ── Load the engine as a module ──────────────────────────────────────────────
_spec = importlib.util.spec_from_file_location("asiair_engine", ENGINE_PATH)
eng = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eng)


# ═══════════════════════════════════════════════════════════════════════════
# Shared app state
# ═══════════════════════════════════════════════════════════════════════════

class App:
    def __init__(self):
        self.oplock = threading.Lock()        # one engine operation at a time
        self.loglock = threading.Lock()
        self.log = deque(maxlen=1200)         # captured engine output lines
        self.status = "idle"                  # idle | scanning | importing | reporting | ejecting
        self.phase = None                     # from engine emit()
        self.scan = None                      # last scan summary (JSON-safe)
        self.scanned_at = None
        self.question = None                  # {id, kind, prompt, default}
        self._answer = None
        self._answer_evt = threading.Event()
        self._qid = 0
        self.last_result = None               # human summary of last op
        self.report_text = None

    # ── log capture ──────────────────────────────────────────────────────
    def write(self, text):                    # file-like for redirect_stdout
        if not text:
            return
        with self.loglock:
            for piece in text.replace("\r", "\n").split("\n"):
                piece = piece.rstrip()
                if not piece:
                    continue
                # progress lines overwrite the previous progress line
                if piece.lstrip().startswith(("Copying [", "Backing up calibration [",
                                              "Reconciling [", "Verifying [")):
                    if self.log and self.log[-1].lstrip().startswith(piece.lstrip().split("[")[0]):
                        self.log.pop()
                self.log.append(piece)

    def flush(self):
        pass

    def logline(self, s):
        self.write(s + "\n")

    # ── engine hooks ─────────────────────────────────────────────────────
    def on_event(self, ev):
        self.phase = ev

    def on_prompt(self, q):
        self._qid += 1
        self.question = {"id": self._qid, "kind": q.get("kind", "confirm"),
                         "prompt": q.get("prompt", ""), "default": q.get("default", "")}
        self._answer_evt.clear()
        got = self._answer_evt.wait(timeout=3600)
        ans = self._answer if got else None
        self.question = None
        self._answer = None
        return ans

    def answer(self, value):
        self._answer = value
        self._answer_evt.set()

    # ── engine operations (each runs in a worker thread) ────────────────
    def _camera_ok(self):
        if os.path.isdir(eng.ASIAIR_VOLUME) or eng.seestar_volume():
            self._no_cam_warned = False
            return True
        if not getattr(self, "_no_cam_warned", False):
            self.logline("⚠ No camera connected — plug in the ASIAir or the Seestar first.")
            self._no_cam_warned = True
        self.last_result = "No camera connected."
        return False

    def _run(self, label, fn):
        if not self._camera_ok():
            return False
        if not self.oplock.acquire(blocking=False):
            return False
        def work():
            self.status = label
            eng.PROMPT_FN = self.on_prompt
            eng.EVENT_FN = self.on_event
            got_lock = False
            try:
                with contextlib.redirect_stdout(self), contextlib.redirect_stderr(self):
                    if label in ("importing",):
                        got_lock = eng.acquire_lock()
                        if not got_lock:
                            self.last_result = "Another import is running (CLI?) — try again."
                            return
                    fn()
            except Exception as e:
                self.logline(f"✗ {label} failed: {e}")
                self.last_result = f"{label} failed: {e}"
            finally:
                if got_lock:
                    eng.release_lock()
                self.phase = None
                self.status = "idle"
                self.oplock.release()
        threading.Thread(target=work, daemon=True).start()
        return True

    def do_scan(self):
        def fn():
            state = eng.State()
            targets, disks = [], []
            scope_by_target = {}
            if state.has_ledger():
                for e in state.ledger["files"].values():
                    t = e.get("target")
                    if e.get("scope") and t and t not in scope_by_target:
                        scope_by_target[t] = e["scope"]
            cal_frames = 0
            if os.path.isdir(eng.ASIAIR_VOLUME):
                scan = eng.scan_camera(state)
                cal_frames = len(scan["calibration"])
                for t in scan["targets"]:
                    targets.append({
                        "name": t["name"], "device": "asiair",
                        "display": eng.display_name_for(state, t["name"]),
                        "source": t["source_label"], "skipped": t["skipped"],
                        "scope": scope_by_target.get(t["name"]),
                        "files": len(t["files"]), "new": len(t["new"]),
                        "newBytes": t["new_bytes"], "totalBytes": t["total_bytes"],
                        "hours": round(t["integration_s"] / 3600.0, 1),
                    })
                if scan["disk"]:
                    disks.append({"label": "ASIAir", **scan["disk"]})
            s = eng.scan_seestar(state)
            if s:
                for t in s["targets"]:
                    nb = sum(f["size"] for f in t["new"])
                    targets.append({
                        "name": t["name"], "device": "seestar",
                        "display": eng.seestar_display(state, t["project_name"]),
                        "source": "", "skipped": t["skipped"],
                        "scope": s["camera"].replace("ZWO ", ""),
                        "files": len(t["files"]), "new": len(t["new"]),
                        "newBytes": nb,
                        "totalBytes": sum(f["size"] for f in t["files"]),
                        "hours": None,
                    })
                for p in s["panel_sets"]:
                    if p["new"]:
                        targets.append({
                            "name": p["mosaic_name"].split("_mosaic")[0],
                            "device": "seestar",
                            "display": eng.seestar_display(state, p["mosaic_name"]) + " (panels)",
                            "source": "", "skipped": False,
                            "scope": s["camera"].replace("ZWO ", ""),
                            "files": len(p["files"]), "new": len(p["new"]),
                            "newBytes": sum(f["size"] for f in p["new"]),
                            "totalBytes": sum(f["size"] for f in p["files"]),
                            "hours": None,
                        })
                if s["disk"]:
                    disks.append({"label": f"Seestar {s['model']}", **s["disk"]})
            self.scan = {
                "targets": targets,
                "newTargets": len([t for t in targets if t["new"] and not t["skipped"]]),
                "newFiles": sum(t["new"] for t in targets if not t["skipped"]),
                "newBytes": sum(t["newBytes"] for t in targets if not t["skipped"]),
                "calFrames": cal_frames,
                "disks": disks,
                "disk": disks[0] if disks else None,
                "hasLedger": state.has_ledger(),
            }
            self.scanned_at = time.strftime("%H:%M:%S")
            self.logline(f"▸ Scan: {self.scan['newTargets']} target(s) with new frames, "
                         f"{self.scan['newFiles']} files")
        return self._run("scanning", fn)

    def do_import(self, names):
        def fn():
            state = eng.State()
            if not state.has_ledger():
                self.logline("⚠ No ledger — run the baseline from Terminal first "
                             "(python3 ~/bin/astro-import.py --baseline)")
                self.last_result = "No ledger yet — baseline needed."
                return
            args = argparse.Namespace(
                dry_run=False, no_checksum=False, loose_cal=False, explain_cal=False,
                all=False, clean_source_previews=False, targets=None, verbose=False)
            sel = set(names) if names else None
            total_t = total_f = 0
            if os.path.isdir(eng.ASIAIR_VOLUME):
                asel = sel
                if sel is not None:
                    known = {t["name"] for t in (self.scan or {}).get("targets", [])
                             if t.get("device") == "asiair"}
                    asel = sel & known if known else sel
                if asel is None or asel:
                    totals = eng.run_import(state, args, only_targets=asel)
                    total_t += totals["targets"]; total_f += totals["files"]
            s = eng.scan_seestar(state)
            if s:
                ssel = sel
                if sel is not None:
                    known = {t["name"] for t in (self.scan or {}).get("targets", [])
                             if t.get("device") == "seestar"}
                    ssel = sel & known if known else sel
                if ssel is None or ssel:
                    state.mark_cleared(s["relpaths"], device="seestar")
                    totals = eng.run_seestar_import(state, s, args, only_targets=ssel)
                    total_t += totals["targets"]; total_f += totals["files"]
            self.last_result = (f"Imported {total_f} frame(s) across "
                                f"{total_t} target(s).")
            self.scan = None  # force rescan for fresh counts
        return self._run("importing", fn)

    def do_report(self):
        def fn():
            state = eng.State()
            text = eng.build_report(state)
            state.save_ledger()
            state.publish_mirror()
            try:
                with open(state.report_path, "w") as f:
                    f.write(text + "\n")
            except OSError:
                pass
            self.report_text = text
            self.last_result = "Report refreshed."
        return self._run("reporting", fn)

    def do_eject(self):
        def fn():
            vols = []
            if os.path.isdir(eng.ASIAIR_VOLUME):
                vols.append(("ASIAir", eng.ASIAIR_VOLUME))
            svol = eng.seestar_volume()
            if svol:
                vols.append(("Seestar", svol))
            ok = bad = 0
            for label, vol in vols:
                r = subprocess.run(["diskutil", "eject", vol],
                                   capture_output=True, text=True)
                if r.returncode == 0:
                    self.logline(f"✓ {label} ejected safely.")
                    ok += 1
                else:
                    self.logline(f"⚠ Could not eject {label} — is an import still running?")
                    bad += 1
            self.last_result = "Ejected." if not bad else "Eject failed."
            if ok and not bad:
                self.scan = None
        return self._run("ejecting", fn)

    # ── state for the UI ─────────────────────────────────────────────────
    def snapshot(self):
        with self.loglock:
            tail = list(self.log)[-250:]
        return {
            "version": APP_VERSION,
            "status": self.status,
            "phase": self.phase,
            "cameraPresent": os.path.isdir(eng.ASIAIR_VOLUME) or bool(eng.seestar_volume()),
            "devices": (["ASIAir"] if os.path.isdir(eng.ASIAIR_VOLUME) else [])
                       + (["Seestar"] if eng.seestar_volume() else []),
            "scan": self.scan,
            "scannedAt": self.scanned_at,
            "question": self.question,
            "log": tail,
            "lastResult": self.last_result,
            "hasReport": self.report_text is not None,
        }


APP = App()


# ═══════════════════════════════════════════════════════════════════════════
# HTTP server
# ═══════════════════════════════════════════════════════════════════════════

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):                # silence request logging
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, text, code=200):
        body = text.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode() or "{}")
        except json.JSONDecodeError:
            return {}

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/index"):
            self._html(PAGE)
        elif self.path == "/api/ping":
            self._json({"ok": True, "app": "astro-import", "version": APP_VERSION})
        elif self.path == "/api/state":
            self._json(APP.snapshot())
        elif self.path == "/api/report-text":
            self._json({"text": APP.report_text or ""})
        elif self.path == "/dashboard" or self.path.startswith("/dashboard?"):
            try:
                state = eng.State()
                path = eng.generate_dashboard(state)
                with open(path) as f:
                    self._html(f.read())
            except Exception as e:
                self._html(f"<pre>dashboard unavailable: {e}</pre>", 500)
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        body = self._read_body()
        if self.path == "/api/scan":
            self._json({"started": APP.do_scan()})
        elif self.path == "/api/import":
            names = body.get("names") or []
            if not names:
                self._json({"started": False, "error": "no targets selected"}, 400)
            else:
                self._json({"started": APP.do_import(names)})
        elif self.path == "/api/report":
            self._json({"started": APP.do_report()})
        elif self.path == "/api/eject":
            self._json({"started": APP.do_eject()})
        elif self.path == "/api/answer":
            APP.answer(str(body.get("value", "")))
            self._json({"ok": True})
        else:
            self._json({"error": "not found"}, 404)


# ═══════════════════════════════════════════════════════════════════════════
# The panel page — "instrument panel for the night sky"
# (dataviz reference palette for data colors; light + dark, dark is the hero)
# ═══════════════════════════════════════════════════════════════════════════

PAGE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BrettjoAstro FITS Importer</title>
<link rel="icon" href='data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="%230b1020"/><circle cx="22" cy="24" r="1.6" fill="%23cfe0ff"/><circle cx="44" cy="16" r="1.1" fill="%23cfe0ff"/><circle cx="50" cy="38" r="1.4" fill="%23cfe0ff"/><circle cx="14" cy="44" r="1.1" fill="%23cfe0ff"/><path d="M32 14l4.2 10.6L47 28l-10.8 3.4L32 42l-4.2-10.6L17 28l10.8-3.4z" fill="%233987e5"/></svg>'>
<style>
:root{
  --page:#f4f5f8; --surface:#ffffff; --surface2:#f8f9fb;
  --ink:#101318; --ink2:#4d545f; --muted:#8a8f98;
  --line:rgba(16,19,24,.09); --line2:rgba(16,19,24,.14);
  --accent:#2a78d6; --accent-ink:#ffffff;
  --good:#0ca30c; --warning:#b97900; --serious:#c25a32;
  --chip1:#2a78d6; --chip2:#c94d1e; --chip3:#12855e;
  --star-op:.35; --shadow:0 10px 30px rgba(16,19,24,.06);
  --logbg:#0e1420; --logink:#c9d4e6;
}
@media (prefers-color-scheme: dark){:root{
  --page:#080b12; --surface:#10151f; --surface2:#0c1019;
  --ink:#eef2f9; --ink2:#aeb6c4; --muted:#7c8494;
  --line:rgba(238,242,249,.08); --line2:rgba(238,242,249,.16);
  --accent:#3987e5; --accent-ink:#ffffff;
  --good:#0ca30c; --warning:#fab219; --serious:#ec835a;
  --chip1:#3987e5; --chip2:#d95926; --chip3:#199e70;
  --star-op:.8; --shadow:0 14px 40px rgba(0,0,0,.45);
  --logbg:#0a0e16; --logink:#c9d4e6;
}}
*{box-sizing:border-box;margin:0}
html,body{height:100%}
body{font:14px/1.5 -apple-system,BlinkMacSystemFont,"SF Pro Text",system-ui,"Segoe UI",sans-serif;
  background:var(--page);color:var(--ink);letter-spacing:.1px}
/* ── starfield ── */
#sky{position:fixed;inset:0;pointer-events:none;opacity:var(--star-op);z-index:0;
  background-image:
    radial-gradient(1.4px 1.4px at 8% 12%, #9db8e8 50%, transparent 51%),
    radial-gradient(1px 1px at 22% 68%, #8aa6d6 50%, transparent 51%),
    radial-gradient(1.6px 1.6px at 34% 28%, #cfe0ff 50%, transparent 51%),
    radial-gradient(1px 1px at 47% 82%, #9db8e8 50%, transparent 51%),
    radial-gradient(1.2px 1.2px at 58% 10%, #cfe0ff 50%, transparent 51%),
    radial-gradient(1px 1px at 66% 52%, #8aa6d6 50%, transparent 51%),
    radial-gradient(1.7px 1.7px at 78% 24%, #cfe0ff 50%, transparent 51%),
    radial-gradient(1px 1px at 86% 72%, #9db8e8 50%, transparent 51%),
    radial-gradient(1.2px 1.2px at 94% 40%, #8aa6d6 50%, transparent 51%),
    radial-gradient(1px 1px at 15% 90%, #cfe0ff 50%, transparent 51%),
    radial-gradient(1.3px 1.3px at 72% 92%, #9db8e8 50%, transparent 51%),
    radial-gradient(1px 1px at 40% 50%, #cfe0ff 50%, transparent 51%);
}
@media (prefers-color-scheme: light){#sky{filter:invert(.75) opacity(.5)}}
#twinkle{position:fixed;inset:0;pointer-events:none;z-index:0;opacity:var(--star-op);
  background-image:
    radial-gradient(2px 2px at 30% 18%, #ffffff 50%, transparent 51%),
    radial-gradient(1.8px 1.8px at 82% 60%, #ffffff 50%, transparent 51%),
    radial-gradient(2px 2px at 12% 55%, #ffffff 50%, transparent 51%);
  animation:tw 7s ease-in-out infinite}
@keyframes tw{0%,100%{opacity:calc(var(--star-op)*.25)}50%{opacity:var(--star-op)}}
.wrap{position:relative;z-index:1;max-width:1180px;margin:0 auto;padding:26px 30px 40px}
/* ── header ── */
header{display:flex;align-items:center;gap:16px;flex-wrap:wrap;margin-bottom:20px}
.brand{display:flex;align-items:center;gap:12px}
.brand svg{width:34px;height:34px;flex:none}
.brand h1{font-size:20px;font-weight:700;letter-spacing:.2px}
.brand .sub{font-size:12px;color:var(--muted);margin-top:1px}
.pill{display:inline-flex;align-items:center;gap:7px;font-size:12.5px;font-weight:500;color:var(--ink2);
  border:1px solid var(--line2);border-radius:999px;padding:5px 12px;background:var(--surface)}
.dot{width:8px;height:8px;border-radius:50%;background:var(--muted)}
.dot.on{background:var(--good);box-shadow:0 0 0 3px color-mix(in srgb, var(--good) 22%, transparent)}
.dot.busy{background:var(--accent);animation:pulse 1.1s ease-in-out infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.35}}
.spacer{flex:1}
button{font:inherit;font-weight:500;border:1px solid var(--line2);background:var(--surface);
  color:var(--ink);border-radius:9px;padding:8px 15px;cursor:pointer;transition:all .15s}
button:hover:not(:disabled){border-color:var(--accent);color:var(--accent)}
button:disabled{opacity:.4;cursor:default}
button.primary{background:var(--accent);border-color:var(--accent);color:var(--accent-ink);
  font-weight:600;padding:11px 20px;border-radius:10px;font-size:14.5px;
  box-shadow:0 6px 18px color-mix(in srgb, var(--accent) 35%, transparent)}
button.primary:hover:not(:disabled){color:var(--accent-ink);filter:brightness(1.08)}
/* ── tabs (segmented) ── */
.tabs{display:inline-flex;background:var(--surface2);border:1px solid var(--line);
  border-radius:11px;padding:3px;gap:2px;margin-bottom:18px}
.tabs button{border:none;background:transparent;color:var(--ink2);border-radius:8px;padding:7px 18px}
.tabs button:hover{color:var(--ink)}
.tabs button.on{background:var(--surface);color:var(--ink);font-weight:600;
  box-shadow:0 2px 8px rgba(0,0,0,.14);border:1px solid var(--line)}
/* ── layout ── */
.cols{display:grid;grid-template-columns:minmax(470px,7fr) minmax(380px,6fr);gap:18px}
@media(max-width:1000px){.cols{grid-template-columns:1fr}}
.card{background:var(--surface);border:1px solid var(--line);border-radius:16px;
  padding:18px 20px;box-shadow:var(--shadow)}
.eyebrow{font-size:11px;font-weight:650;letter-spacing:.09em;text-transform:uppercase;
  color:var(--muted);margin-bottom:10px}
/* ── targets ── */
.trow{display:flex;align-items:center;gap:13px;padding:11px 12px;border-radius:12px;
  border:1px solid transparent;transition:all .12s}
.trow:hover{background:var(--surface2);border-color:var(--line)}
.trow + .trow{margin-top:2px}
.cb{appearance:none;width:21px;height:21px;border:1.5px solid var(--line2);border-radius:7px;
  background:var(--surface);cursor:pointer;flex:none;position:relative;transition:all .12s}
.cb:checked{background:var(--accent);border-color:var(--accent)}
.cb:checked::after{content:"";position:absolute;left:6.5px;top:2.5px;width:5px;height:10px;
  border:solid #fff;border-width:0 2px 2px 0;transform:rotate(42deg)}
.tmain{flex:1;min-width:0}
.tname{font-weight:600;font-size:14.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tmeta{display:flex;gap:8px;align-items:center;margin-top:3px;font-size:12px;color:var(--muted)}
.chip{display:inline-flex;align-items:center;gap:5px;font-size:11px;font-weight:600;
  padding:2px 9px;border-radius:999px;color:#fff}
.chip.c1{background:var(--chip1)}.chip.c2{background:var(--chip2)}.chip.c3{background:var(--chip3)}
.chip.plain{background:transparent;color:var(--muted);border:1px solid var(--line2);font-weight:500}
.tstats{text-align:right;font-variant-numeric:tabular-nums;flex:none}
.tstats .big{font-size:16px;font-weight:650}
.tstats .small{font-size:11.5px;color:var(--muted);margin-top:1px}
/* ── all-clear state ── */
.clear{display:flex;flex-direction:column;align-items:center;text-align:center;padding:34px 10px 30px}
.clear .ring{width:64px;height:64px;border-radius:50%;display:flex;align-items:center;justify-content:center;
  background:color-mix(in srgb, var(--good) 14%, transparent);margin-bottom:14px}
.clear .ring svg{width:32px;height:32px}
.clear b{font-size:16.5px;font-weight:650}
.clear span{color:var(--muted);font-size:13px;margin-top:4px}
/* ── storage ── */
.meter{height:9px;border-radius:5px;background:color-mix(in srgb, var(--ink) 9%, transparent);
  overflow:hidden;margin:9px 0 7px}
.meter>div{height:100%;background:linear-gradient(90deg,var(--accent),color-mix(in srgb, var(--accent) 65%, #7db4f0));border-radius:5px}
.legend{display:flex;gap:16px;font-size:12px;color:var(--muted)}
.legend i{width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:5px}
/* ── activity ── */
#logcard{display:flex;flex-direction:column}
#livebarbox{display:none;margin-bottom:10px}
#livebarlabel{font-size:12px;color:var(--ink2);margin-bottom:5px;display:flex;justify-content:space-between}
#livebar{height:8px;border-radius:4px;background:color-mix(in srgb, var(--ink) 9%, transparent);overflow:hidden}
#livebar>div{height:100%;background:var(--accent);border-radius:4px;transition:width .3s}
#log{background:var(--logbg);color:var(--logink);border:1px solid var(--line);border-radius:12px;
  padding:12px 14px;height:460px;overflow-y:auto;font:11.5px/1.65 ui-monospace,"SF Mono",Menlo,monospace;
  white-space:pre-wrap;word-break:break-word}
#log .ok{color:#63c76a}#log .wa{color:#e8b34b}#log .er{color:#e8756b}#log .hd{color:#8fb6f2}
.result{font-size:12.5px;color:var(--ink2);margin-top:10px;min-height:18px}
/* ── question ── */
.q{border:1px solid color-mix(in srgb, var(--warning) 55%, transparent);
  background:color-mix(in srgb, var(--warning) 7%, var(--surface));
  border-radius:16px;padding:16px 18px;margin-bottom:16px;box-shadow:var(--shadow)}
.q .qh{display:flex;gap:10px;align-items:center;font-weight:650;margin-bottom:8px}
.q .qh svg{width:20px;height:20px;flex:none}
.q p{color:var(--ink2);margin-bottom:12px}
.q input[type=text]{font:inherit;width:100%;padding:9px 11px;border:1px solid var(--line2);
  border-radius:9px;background:var(--surface);color:var(--ink);margin-bottom:11px}
.row{display:flex;gap:9px;align-items:center;flex-wrap:wrap}
/* ── tabs content ── */
iframe{width:100%;height:calc(100vh - 180px);border:1px solid var(--line);border-radius:16px;background:var(--surface)}
#reportPre{font:12px/1.55 ui-monospace,"SF Mono",Menlo,monospace;white-space:pre-wrap;background:var(--surface);
  border:1px solid var(--line);border-radius:16px;padding:18px 20px;overflow-x:auto;box-shadow:var(--shadow)}
.foot{color:var(--muted);font-size:11.5px;margin-top:20px;text-align:center}
</style></head>
<body><div id="sky"></div><div id="twinkle"></div><div class="wrap">
<header>
  <div class="brand">
    <svg viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="#0b1020"/>
      <circle cx="22" cy="24" r="1.6" fill="#cfe0ff"/><circle cx="44" cy="16" r="1.1" fill="#cfe0ff"/>
      <circle cx="50" cy="38" r="1.4" fill="#cfe0ff"/><circle cx="14" cy="44" r="1.1" fill="#cfe0ff"/>
      <path d="M32 14l4.2 10.6L47 28l-10.8 3.4L32 42l-4.2-10.6L17 28l10.8-3.4z" fill="#3987e5"/></svg>
    <div><h1>FITS Importer</h1><div class="sub">by BrettjoAstro · backup-first · everything local</div></div>
  </div>
  <span class="pill"><span class="dot" id="camDot"></span><span id="camText">checking…</span></span>
  <span class="pill"><span class="dot" id="busyDot"></span><span id="statusText">idle</span></span>
  <span class="spacer"></span>
  <button id="btnScan">Rescan</button>
  <button id="btnReport">Refresh report</button>
  <button id="btnEject">Eject</button>
</header>
<div class="tabs">
  <button class="on" data-tab="panel">Panel</button>
  <button data-tab="report">Report</button>
  <button data-tab="dash">Dashboard</button>
</div>

<div id="qbox"></div>

<div id="tab-panel">
  <div class="cols">
    <div>
      <div class="card">
        <div class="eyebrow" id="scanEyebrow">Targets with new frames</div>
        <div id="targetList"></div>
        <div class="row" style="margin-top:14px">
          <button class="primary" id="btnImport" disabled style="flex:1">Import selected</button>
        </div>
        <div class="result" id="calNote"></div>
      </div>
      <div class="card" style="margin-top:16px" id="storageCard">
        <div class="eyebrow">Camera storage</div>
        <div class="result" id="storageText" style="margin:0">No scan yet.</div>
        <div class="meter"><div id="storageBar" style="width:0%"></div></div>
        <div class="legend"><span><i style="background:var(--accent)"></i>Used</span>
          <span><i style="background:color-mix(in srgb, var(--ink) 18%, transparent)"></i>Free</span>
          <span class="spacer"></span><span id="scannedAt"></span></div>
      </div>
    </div>
    <div class="card" id="logcard">
      <div class="eyebrow">Activity</div>
      <div id="livebarbox">
        <div id="livebarlabel"><span id="livebarname"></span><span id="livebarpct"></span></div>
        <div id="livebar"><div style="width:0%"></div></div>
      </div>
      <div id="log"></div>
      <div class="result" id="lastResult"></div>
    </div>
  </div>
</div>

<div id="tab-report" style="display:none">
  <pre id="reportPre">No report yet — click “Refresh report”.</pre>
</div>
<div id="tab-dash" style="display:none">
  <iframe id="dashFrame" title="dashboard"></iframe>
</div>

<div class="foot">Engine: astro-import.py (backup-first, ASIAir + Seestar) · the camera is never modified except purple done-tags ·
tip: Safari → File → Add to Dock turns this into a Dock app</div>
</div>
<script>
const $=s=>document.querySelector(s);
const fmtGB=b=>b>=1073741824?(b/1073741824).toFixed(1)+" GB":Math.round(b/1048576)+" MB";
const esc=s=>String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
let busy=false, lastLogSig="", lastScanStamp="";

document.querySelectorAll(".tabs button").forEach(b=>b.addEventListener("click",()=>{
  document.querySelectorAll(".tabs button").forEach(x=>x.classList.remove("on"));
  b.classList.add("on");
  ["panel","report","dash"].forEach(t=>$("#tab-"+t).style.display = b.dataset.tab===t?"":"none");
  if(b.dataset.tab==="dash") $("#dashFrame").src="/dashboard?t="+Date.now();
  if(b.dataset.tab==="report") loadReport();
}));

async function api(path, body){
  const r=await fetch(path,{method:body!==undefined?"POST":"GET",
    headers:{"Content-Type":"application/json"},
    body:body!==undefined?JSON.stringify(body):undefined});
  return r.json();
}

function scopeChip(t){
  if(!t.scope) return t.source ? '<span class="chip plain">'+esc(t.source)+'</span>' : '';
  const cls = t.scope.includes("FRA400") ? "c1" : (t.scope.includes("107PHQ") ? "c2" : "c3");
  return `<span class="chip ${cls}">${esc(t.scope.replace("Askar ",""))}</span>`
         + (t.source ? `<span class="chip plain">${esc(t.source)}</span>` : "");
}

function renderTargets(scan){
  const box=$("#targetList");
  const withNew=scan.targets.filter(t=>t.new>0 && !t.skipped).sort((a,b)=>b.new-a.new);
  if(!withNew.length){
    const n=scan.targets.filter(t=>!t.skipped).length;
    box.innerHTML = scan.hasLedger
      ? `<div class="clear"><div class="ring">
           <svg viewBox="0 0 24 24" fill="none"><path d="M4.5 12.5l5 5 10-11" stroke="var(--good)" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
         </div><b>All backed up</b><span>Every frame across ${n} targets is safe in the ledger.</span></div>`
      : `<div class="clear"><b>No ledger yet</b><span>Run the baseline once from Terminal:<br>python3 ~/bin/asiair-import.py --baseline</span></div>`;
    $("#btnImport").disabled=true;
    $("#btnImport").textContent="Import selected";
    $("#scanEyebrow").textContent="Targets";
    return;
  }
  $("#scanEyebrow").textContent="Targets with new frames";
  box.innerHTML = withNew.map(t=>`
    <label class="trow">
      <input type="checkbox" class="cb sel" data-name="${encodeURIComponent(t.name)}" checked>
      <div class="tmain">
        <div class="tname">${esc(t.display)}</div>
        <div class="tmeta">${scopeChip(t)}${t.hours==null?"":`<span>${t.hours.toFixed(1)} h integration</span>`}</div>
      </div>
      <div class="tstats">
        <div class="big">${t.new.toLocaleString()}</div>
        <div class="small">frames · ${fmtGB(t.newBytes)}</div>
      </div>
    </label>`).join("");
  box.querySelectorAll(".sel").forEach(c=>c.addEventListener("change",updateImportBtn));
  updateImportBtn();
}
function updateImportBtn(){
  const sel=[...document.querySelectorAll(".sel:checked")];
  const all=[...document.querySelectorAll(".sel")];
  if(!all.length){ $("#btnImport").disabled=true; return; }
  $("#btnImport").disabled = busy || !sel.length;
  $("#btnImport").textContent = sel.length
    ? `Import ${sel.length} target${sel.length>1?"s":""}` : "Import selected";
}

function renderQuestion(q){
  const box=$("#qbox");
  if(!q){ box.innerHTML=""; box.dataset.qid=""; return; }
  if(box.dataset.qid==String(q.id)) return;
  box.dataset.qid=q.id;
  const isText=q.kind==="text";
  box.innerHTML=`<div class="q"><div class="qh">
    <svg viewBox="0 0 24 24" fill="none"><path d="M12 3l9.5 17h-19L12 3z" stroke="var(--warning)" stroke-width="1.8" stroke-linejoin="round"/><path d="M12 10v4.5" stroke="var(--warning)" stroke-width="1.8" stroke-linecap="round"/><circle cx="12" cy="17.4" r="1.1" fill="var(--warning)"/></svg>
    The import needs an answer</div>
    <p>${esc(q.prompt)}</p>
    ${isText?'<input type="text" id="qval" placeholder="(leave blank to keep the folder name)">':""}
    <div class="row">
      ${isText?'<button class="primary" id="qyes">Save name</button><button id="qno">Skip</button>'
              :(q.default==="n"
                ?'<button id="qyes">Yes</button><button class="primary" id="qno">No</button>'
                :'<button class="primary" id="qyes">Yes</button><button id="qno">No</button>')}
    </div></div>`;
  $("#qyes").onclick=()=>api("/api/answer",{value:isText?($("#qval").value||""):"y"});
  $("#qno").onclick=()=>api("/api/answer",{value:isText?"":"n"});
  if(isText) $("#qval").focus();
}

function renderLog(lines){
  const el=$("#log");
  el.innerHTML = lines.map(l=>{
    const t=esc(l);
    if(l.startsWith("✓")) return `<span class="ok">${t}</span>`;
    if(l.startsWith("⚠")) return `<span class="wa">${t}</span>`;
    if(l.startsWith("✗")) return `<span class="er">${t}</span>`;
    if(l.startsWith("▸")) return `<span class="hd">${t}</span>`;
    return t;
  }).join("\n");
  el.scrollTop=el.scrollHeight;
}

function renderLiveBar(lines){
  const box=$("#livebarbox");
  for(let i=lines.length-1;i>=Math.max(0,lines.length-3);i--){
    const m=lines[i].match(/^\s*(.+?)\s*\[[█░]*\]\s*(\d+)\/(\d+)\s*\((\d+)%\)/);
    if(m && busy){
      box.style.display="";
      $("#livebarname").textContent=m[1];
      $("#livebarpct").textContent=`${(+m[2]).toLocaleString()} / ${(+m[3]).toLocaleString()} · ${m[4]}%`;
      $("#livebar>div") && ($("#livebar").firstElementChild.style.width=m[4]+"%");
      return;
    }
  }
  box.style.display="none";
}

async function loadReport(){
  const r=await api("/api/report-text");
  if(r.text) $("#reportPre").textContent=r.text;
}

async function tick(){
  try{
    const s=await api("/api/state");
    $("#camDot").className="dot"+(s.cameraPresent?" on":"");
    $("#camText").textContent=s.cameraPresent?((s.devices||[]).join(" + ")||"camera")+" connected":"no camera connected";
    busy = s.status!=="idle";
    $("#busyDot").className="dot"+(busy?" busy":"");
    $("#statusText").textContent=busy?s.status+"…":"idle";
    ["btnScan","btnReport","btnEject"].forEach(id=>$("#"+id).disabled=busy);
    if(s.scan && (s.scannedAt!==lastScanStamp)){
      lastScanStamp=s.scannedAt;
      renderTargets(s.scan);
      $("#calNote").textContent = s.scan.calFrames
        ? s.scan.calFrames.toLocaleString()+" calibration frames on camera — backed up automatically on import"
        : "";
      if(s.scan.disks && s.scan.disks.length){
        const parts=s.scan.disks.map(d=>d.label+": "+fmtGB(d.used)+" / "+fmtGB(d.total)+" ("+fmtGB(d.free)+" free)");
        $("#storageText").textContent=parts.join("   ·   ");
        const d=s.scan.disks[0], pct=Math.round(100*d.used/d.total);
        $("#storageBar").style.width=pct+"%";
      } else if(s.scan.disk){
        const d=s.scan.disk, pct=Math.round(100*d.used/d.total);
        $("#storageText").textContent=fmtGB(d.used)+" used of "+fmtGB(d.total)+" — "+fmtGB(d.free)+" free";
        $("#storageBar").style.width=pct+"%";
      }
      $("#scannedAt").textContent = s.scannedAt ? "scanned "+s.scannedAt : "";
    }
    if(!s.scan && !busy && s.cameraPresent){ /* fresh state after import → rescan */ api("/api/scan",{}); }
    updateImportBtn();
    renderQuestion(s.question);
    // progress lines REPLACE the last entry, so compare content, not length
    const logSig=s.log.length+"|"+(s.log[s.log.length-1]||"");
    if(logSig!==lastLogSig){ lastLogSig=logSig; renderLog(s.log); }
    renderLiveBar(s.log);
    $("#lastResult").textContent=s.lastResult||"";
  }catch(e){
    $("#camText").textContent="panel disconnected — is the app running?";
    $("#camDot").className="dot";
  }
}

$("#btnScan").onclick=()=>{lastScanStamp="";api("/api/scan",{})};
$("#btnReport").onclick=async()=>{await api("/api/report",{}); setTimeout(loadReport,1500);};
$("#btnEject").onclick=()=>api("/api/eject",{});
$("#btnImport").onclick=()=>{
  const names=[...document.querySelectorAll(".sel:checked")].map(x=>decodeURIComponent(x.dataset.name));
  if(names.length) api("/api/import",{names});
};

tick(); setInterval(tick, 1000);
</script></body></html>
"""


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════

def main():
    p = argparse.ArgumentParser(description="BrettjoAstro FITS Importer control panel")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--no-browser", action="store_true")
    args = p.parse_args()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}"
    print(f"FITS Importer panel → {url}   (Ctrl-C to quit)")
    APP.logline(f"▸ Panel started at {url}")
    if not args.no_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
