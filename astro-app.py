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
import re
import secrets
import subprocess
import sys  # noqa: F401  (kept for parity)
import threading
import time
import urllib.parse
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
        self._qlock = threading.Lock()
        self._qid = 0
        self.last_result = None               # human summary of last op
        self.last_done = None                 # completion banner payload
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
                # ANY progress line overwrites the previous line of the same
                # label — matched by shape, not by a hardcoded label list
                # (the "319 stacked JPEG bars" incident, 2026-09-05)
                m = re.match(r"^(.*?) \[[█░]+\] \d+/\d+ \(\d+%\)$", piece.lstrip())
                if m and self.log and \
                        self.log[-1].lstrip().startswith(m.group(1) + " ["):
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
        with self._qlock:
            self._qid += 1
            self._answer = None
            self._answer_evt.clear()        # before the card is visible
            self.question = {"id": self._qid, "kind": q.get("kind", "confirm"),
                             "prompt": q.get("prompt", ""),
                             "default": q.get("default", ""),
                             "expect": q.get("expect", "")}
            my_id = self._qid
        got = self._answer_evt.wait(timeout=3600)
        with self._qlock:
            ans = self._answer if got else None
            if self.question is not None and self.question.get("id") == my_id:
                self.question = None
            self._answer = None
        return ans

    def answer(self, value, qid=None):
        """Accept an answer only for the question that is actually pending —
        a stale click must never resolve a later, more dangerous prompt
        (e.g. a flats answer landing on the delete-from-camera card). The
        FIRST answer wins: the card is withdrawn as it is answered, so a
        second click (or a second tab) cannot overwrite a typed DISCARD with
        something else, or vice versa (1.4.2)."""
        with self._qlock:
            q = self.question
            if q is None:
                return False
            if qid is not None and str(qid) != str(q.get("id")):
                return False
            self._answer = value
            self.question = None
            self._answer_evt.set()
            return True

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

    def _run(self, label, fn, need_camera=True):
        if need_camera and not self._camera_ok():
            return False
        if not self.oplock.acquire(blocking=False):
            return False
        # status flips BEFORE the request returns, so a poll right after
        # "started" can never read the previous op's idle (T6)
        self.status = label
        if label != "scanning":
            self.last_done = None   # banner survives rescans, not new ops
            self.last_result = ""   # never show the previous op's verdict (S10)
        def work():
            eng.PROMPT_FN = self.on_prompt
            eng.EVENT_FN = self.on_event
            got_lock = False
            try:
                with contextlib.redirect_stdout(self), contextlib.redirect_stderr(self):
                    if label in ("importing", "reporting", "discarding", "clearing",
                                 "saving"):
                        # The report saves the ledger too — saving over a
                        # running CLI import would drop its entries, so both
                        # take the same engine lock.
                        got_lock = eng.acquire_lock()
                        if not got_lock:
                            self.last_result = ("Another import is already running "
                                                "(perhaps in Terminal). Let it finish, "
                                                "then try again.")
                            return
                    fn()
            except Exception as e:
                self.logline(f"✗ {label} failed: {e}")
                self.last_result = f"{label} failed: {e}"
                if "Operation not permitted" in str(e):
                    real = os.path.realpath(sys.executable)
                    app = (real.split("/Contents/MacOS/")[0]
                           if "/Contents/MacOS/" in real else real)
                    fm = re.match(r"(.*?\.framework/Versions/[^/]+)/", real)
                    if fm:  # framework python → its draggable Python.app sibling
                        cand = os.path.join(fm.group(1), "Resources", "Python.app")
                        if os.path.isdir(cand):
                            app = cand
                    self.logline("▸ macOS is blocking disk access for this panel "
                                 "process. Permanent fix: System Settings → Privacy "
                                 f"& Security → Full Disk Access → add: {app} "
                                 "(drag it in from Finder), then restart the panel. "
                                 "Quick fix: relaunch the panel from Terminal.")
            finally:
                if got_lock:
                    eng.release_lock()
                self.phase = None
                self.status = "idle"
                self.oplock.release()
        threading.Thread(target=work, daemon=True).start()
        return True

    def do_scan(self):
        STAMP = re.compile(r"20\d{6}-\d{6}")

        def last_stamp(files):
            # newest capture stamp in a file list — lexicographic == chronological
            best = ""
            for f in files:
                m = STAMP.search(f.get("filename", ""))
                if m and m.group(0) > best:
                    best = m.group(0)
            return best

        def fn():
            state = eng.State()
            targets, disks = [], []
            scan_a = None
            scope_by_target = {}
            if state.has_ledger():
                for e in state.ledger["files"].values():
                    t = e.get("target")
                    if e.get("scope") and t and t not in scope_by_target:
                        scope_by_target[t] = e["scope"]
            cal_frames = 0
            cal_summary = None
            if os.path.isdir(eng.ASIAIR_VOLUME):
                scan = scan_a = eng.scan_camera(state)
                cal_frames = len(scan["calibration"])
                new_sets, in_lib = {}, 0
                for c in scan["calibration"]:
                    if state.has_ledger() and state.cal_entry(c["relpath"]) is not None:
                        in_lib += 1
                        continue
                    key = eng.cal_set_key(c)
                    g = new_sets.setdefault(key, {
                        "setKey": key,
                        "type": c["frame_type"], "count": 0,
                        "exposureSeconds": c.get("exposure_seconds"),
                        "filter": c.get("filter") or "",
                        "rotation": c.get("rotation"),
                        "night": key.rsplit("|", 1)[-1]})
                    g["count"] += 1
                cal_summary = {"total": len(scan["calibration"]), "inLibrary": in_lib,
                               "newSets": sorted(new_sets.values(),
                                                 key=lambda g: (g["night"], g["type"]))}
                try:
                    # which sets pair with which target, via the real gates
                    cal_summary["pairings"] = eng.preview_cal_pairings(state, scan)
                except Exception as e:
                    cal_summary["pairings"] = {}
                    self.logline(f"⚠ pairing preview failed: {e}")
                for t in scan["targets"]:
                    targets.append({
                        "name": t["name"], "device": "asiair",
                        "display": eng.display_name_for(state, t["name"]),
                        "source": t["source_label"], "skipped": t["skipped"],
                        "scope": scope_by_target.get(t["name"]),
                        "files": len(t["files"]), "new": len(t["new"]),
                        "newBytes": t["new_bytes"], "totalBytes": t["total_bytes"],
                        "hours": round(t["integration_s"] / 3600.0, 1),
                        "lastStamp": last_stamp(t["files"]),
                    })
                if scan["disk"]:
                    disks.append({"label": "ASIAir", **scan["disk"]})
            scan_notes = []
            s = eng.scan_seestar(state)
            if s:
                scope_s = s["camera"].replace("ZWO ", "")
                groups = {g["id"]: g for g in eng.seestar_groups(state, s)}

                def safety(gid):
                    """The pill must say what the SAFE gate says, not what
                    "no new frames" suggests (1.4.3 review B2): unproven files
                    — orphan JPEGs, a failed copy, a baseline-only row — mean
                    NOT backed up, whatever the new-frame count."""
                    g = groups.get(gid)
                    if not g or not state.has_ledger():
                        return "notsafe", 0
                    try:
                        unproven, _b = eng._seestar_unproven_files(
                            state, s["volume"], g["dirs"], exempt_superseded=g["exempt"],
                            camera=s["camera"])
                    except Exception as ex:
                        self.logline(f"⚠ SAFE check failed for {g['display']}: {ex}")
                        return "notsafe", 0
                    return ("safe" if not unproven else "notsafe"), len(unproven)

                for t in s["targets"]:
                    # a target with only new stacks (sub saving off) or only
                    # new JPEG riders (catch-up) is still importable work —
                    # and stacks + JPEGs together count together
                    n_new = (len(t["new"])
                             or (len(t.get("new_stacks") or [])
                                 + len(t.get("new_jpgs") or [])))
                    nb = (sum(f["size"] for f in t["new"])
                          or (sum(f["size"] for f in t.get("new_stacks") or [])
                              + sum(f["size"] for f in t.get("new_jpgs") or [])))
                    what, unit = "", "frames"
                    if n_new:
                        try:
                            d = eng.describe_seestar_files(
                                [f["path"] for f in t["new"] + (t.get("new_stacks") or [])])
                            what = d["label"]
                            if not d["subs"] and d["stacks"]:
                                unit = "stack" if d["stacks"] == 1 else "stacks"
                        except Exception as ex:
                            self.logline(f"⚠ could not describe {t['name']}: {ex}")
                    st, nun = safety(t["sub_name"])
                    targets.append({
                        "name": t["name"], "device": "seestar", "kind": "target",
                        "display": eng.seestar_display(state, t["project_name"]),
                        "source": "", "skipped": t["skipped"],
                        "scope": scope_s,
                        "files": len(t["files"]) + len(t.get("stacks") or []),
                        "new": n_new,
                        "what": what, "unit": unit,
                        # the camera folder name: unique on the card, so the
                        # discard link can never pick the wrong target (1.4.2)
                        "discardId": t["sub_name"],
                        "safeState": st, "unproven": nun,
                        "clearId": t["sub_name"] if st == "safe" else None,
                        "newBytes": nb,
                        "totalBytes": sum(f["size"] for f in t["files"] + (t.get("stacks") or [])),
                        "hours": None,
                        "lastStamp": last_stamp(t["files"] + t.get("stacks", [])),
                    })
                # panel sets and mode folders are rows too — also once
                # imported, so they can be cleared (and never just vanish, S11)
                for p in s["panel_sets"]:
                    st, nun = safety(p["pt_name"])
                    targets.append({
                        "name": p["mosaic_name"].split("_mosaic")[0],
                        "device": "seestar", "kind": "panels",
                        "display": eng.seestar_display(state, p["mosaic_name"]) + " (panels)",
                        "source": "", "skipped": False,
                        "scope": scope_s,
                        "files": len(p["files"]), "new": len(p["new"]),
                        "discardId": p["pt_name"],
                        "safeState": st, "unproven": nun,
                        "clearId": p["pt_name"] if st == "safe" else None,
                        "newBytes": sum(f["size"] for f in p["new"]),
                        "totalBytes": sum(f["size"] for f in p["files"]),
                        "hours": None,
                        "lastStamp": last_stamp(p["files"]),
                    })
                for nd in s["non_dso"]:
                    # Mode folders (Solar/Lunar/…) are ordinary tickable
                    # rows now — no more invisible riders on an import
                    st, nun = safety(nd["src_name"])
                    targets.append({
                        "name": nd["dest_name"], "device": "seestar", "kind": "mode",
                        "display": f"{nd['dest_name']} — "
                                   f"{nd['src_name'].replace('_', ' ')}",
                        "source": "", "skipped": False,
                        "scope": scope_s,
                        "files": len(nd["files"]), "new": len(nd["new"]),
                        "discardId": nd["src_name"],
                        "safeState": st, "unproven": nun,
                        "clearId": nd["src_name"] if st == "safe" else None,
                        "newBytes": sum(f["size"] for f in nd["new"]),
                        "totalBytes": sum(f["size"] for f in nd["files"]),
                        "hours": None,
                        "lastStamp": last_stamp(nd["files"]),
                    })
                if s["disk"]:
                    disks.append({"label": f"Seestar {s['model']}", **s["disk"]})
                notes = []
                for u in s.get("unhandled", []):
                    notes.append(f"On camera, NOT handled by this tool: "
                                 f"{u['name']} ({u['files']} file(s)) — not "
                                 f"backed up, left untouched")
                for xv in s.get("extra_volumes", []):
                    notes.append(f"Another Seestar is mounted at {xv} — one "
                                 f"camera at a time (this scan: {s['volume']})")
                scan_notes = notes
            try:
                dest_plan = eng.preview_dest_plan(state, scan_a, s or None)
            except Exception as e:
                dest_plan = []
                self.logline(f"⚠ destination preview failed: {e}")
            # badge truth: targets with new frames wear the INCOMING scope,
            # not the oldest ledger entry's (multi-rig targets, 2026-08-12)
            plan_scope = {e["target"]: e["scope"]
                          for e in dest_plan if e.get("scope")}
            for t in targets:
                if t["name"] in plan_scope:
                    t["scope"] = plan_scope[t["name"]]
            self.scan = {
                "targets": targets,
                "newTargets": len([t for t in targets if t["new"] and not t["skipped"]]),
                "newFiles": sum(t["new"] for t in targets if not t["skipped"]),
                "newBytes": sum(t["newBytes"] for t in targets if not t["skipped"]),
                "calFrames": cal_frames,
                "calSummary": cal_summary,
                "destPlan": dest_plan,
                "disks": disks,
                "disk": disks[0] if disks else None,
                "hasLedger": state.has_ledger(),
                "notes": scan_notes,
            }
            self.labels = getattr(self, "labels", {})
            for t in targets:
                for k in ("discardId", "clearId"):
                    if t.get(k):
                        self.labels[t[k]] = t["display"]
            self.scanned_at = time.strftime("%H:%M:%S")
            self.logline(f"▸ Scan: {self.scan['newTargets']} target(s) with new frames, "
                         f"{self.scan['newFiles']} files")
        return self._run("scanning", fn)

    def do_import(self, names, cal_decisions=None):
        t0 = time.time()

        def fn():
            state = eng.State()
            if not state.has_ledger():
                if getattr(state, "ledger_corrupt", False):
                    self.logline("✗ ledger.json exists but can't be read — nothing "
                                 "imported. Restore it (python3 ~/bin/astro-import.py "
                                 "--restore-ledger) before importing.")
                    self.last_result = "The ledger can't be read — restore it first."
                    return
                if os.path.isfile(os.path.join(eng.MIRROR_DIR, "ledger.json")):
                    self.logline("⚠ No ledger here, but a mirror copy exists — restore "
                                 "it first (python3 ~/bin/astro-import.py "
                                 "--restore-ledger), or everything would import again.")
                    self.last_result = "Restore the ledger from its mirror first."
                    return
                # First run: back EVERYTHING up. (The baseline — "I already
                # have copies" — stays a deliberate Terminal step, S1.)
                state.new_ledger()
                self.logline("▸ First import: starting a new ledger — everything "
                             "on the camera counts as new.")
            # scan-card checkbox decisions → engine pre-consent map
            eng.CAL_DECISIONS = {
                t: {str(k): bool(v) for k, v in (m or {}).items()}
                for t, m in (cal_decisions or {}).items()
            }
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
                    state.seestar_seen(s)
                    totals = eng.run_seestar_import(state, s, args, only_targets=ssel)
                    total_t += totals["targets"]; total_f += totals["files"]
            self.last_result = (f"Imported {total_f} frame(s) across "
                                f"{total_t} target(s).")
            dur = int(time.time() - t0)
            self.last_done = {
                "op": "import", "targets": total_t, "frames": total_f,
                "seconds": dur,
                "finishedAt": time.strftime("%H:%M:%S"),
            }
            if total_f and sys.platform == "darwin":
                try:  # a chime for imports finished while you're elsewhere
                    subprocess.run(
                        ["osascript", "-e",
                         'display notification "%d frame(s) imported and '
                         'verified across %d target(s)." with title '
                         '"FITS Importer — import complete" sound name "Glass"'
                         % (total_f, total_t)],
                        timeout=5, capture_output=True)
                except Exception:
                    pass
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
        return self._run("reporting", fn, need_camera=False)

    def do_discard(self, name, night=None, reason=""):
        """Delete one Seestar target from the camera without importing it.
        The engine does all the refusing and asks for the typed DISCARD on the
        question card; this only runs it and rescans."""
        def fn():
            state = eng.State()
            res = eng.run_discard(state, name, night=night or None, reason=reason or "")
            label = self._label_for(name)
            self.last_result = {
                "done": f"Discarded {label} from the camera — recorded as never backed up.",
                "partial": f"Discard of {label} was PARTIAL — some files could not be "
                           f"removed and are still on the camera (see the log).",
                "cancelled": "Discard cancelled — nothing deleted.",
                "refused": "Discard refused — see the log for why. Nothing deleted.",
                "safe": f"{label} is already backed up — the SAFE clear was offered "
                        f"and you kept it on the camera.",
                "cleared": f"{label} was already backed up — cleared from the camera "
                           f"the SAFE way.",
            }.get(res, "")
            if res in ("done", "partial", "cleared"):
                self.last_done = {"op": "discard" if res != "cleared" else "clear",
                                  "text": self.last_result,
                                  "warn": res == "partial",
                                  "finishedAt": time.strftime("%H:%M:%S")}
            self.scan = None
        return self._run("discarding", fn)

    def _label_for(self, folder_id):
        """The friendly name the panel showed for a camera folder id (kept
        across rescans — a discard clears the scan before it reports)."""
        lab = getattr(self, "labels", {}).get(folder_id)
        if lab:
            return lab
        return folder_id[:-4] if folder_id.endswith("_sub") else folder_id

    def do_clear(self, folder_id):
        """The SAFE clear for one thing already backed up (panel "clear…")."""
        def fn():
            state = eng.State()
            res = eng.run_clear(state, folder_id)
            label = self._label_for(folder_id)
            self.last_result = {
                "cleared": f"Cleared {label} from the camera — it was backed up and verified.",
                "kept": f"{label} left on the camera.",
                "refused": "Clear refused — see the log for why. Nothing deleted.",
            }.get(res, "")
            if res == "cleared":
                self.last_done = {"op": "clear", "text": self.last_result,
                                  "finishedAt": time.strftime("%H:%M:%S")}
            self.scan = None
        return self._run("clearing", fn)

    def do_skip(self, name, skip):
        """Add a target to, or take it off, the never-import list."""
        def fn():
            state = eng.State()
            changed = False
            if skip and name not in state.skiplist:
                state.skiplist.append(name); changed = True
            elif not skip and name in state.skiplist:
                state.skiplist.remove(name); changed = True
            if changed:
                state.save_skiplist()
                state.history_event("skiplist", target=name, skipped=skip)
                state.publish_mirror()
            self.last_result = (f"{name} is on the never-import list." if skip else
                                f"{name} will be imported again.")
            self.scan = None
        return self._run("saving", fn, need_camera=False)

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
            "lastDone": self.last_done,
            "hasReport": self.report_text is not None,
        }


APP = App()


# ═══════════════════════════════════════════════════════════════════════════
# HTTP server
# ═══════════════════════════════════════════════════════════════════════════

# A fresh secret per launch, written into the page this server serves. Every
# state-changing request must echo it in a header: another page — even one on
# another localhost port, which shares the "local" hostname — can neither read
# it nor (without a CORS preflight this server never answers) send the header
# (1.4.3 review finding V1).
TOKEN = secrets.token_urlsafe(24)
PORT = 8765
MAX_BODY = 64 * 1024
LOCAL_HOSTS = ("127.0.0.1", "localhost", "::1")


def _split_hostport(raw):
    raw = (raw or "").strip().lower()
    if raw.startswith("["):                        # [::1]:8765
        host, _, rest = raw[1:].partition("]")
        port = rest[1:] if rest.startswith(":") else ""
    else:
        host, _, port = raw.partition(":")
    return host, port


class Handler(BaseHTTPRequestHandler):
    timeout = 15                              # a stalled client can't hold a thread

    def log_message(self, *a):                # silence request logging
        pass

    def _local_ok(self):
        """Only the local panel page may talk to this server. Any web page in
        the same browser can POST to 127.0.0.1 blind (and DNS rebinding fakes
        the host), so every request must carry a local Host on THIS port — and,
        if a browser sent an Origin at all, exactly this server's origin
        (scheme, local host AND port: a page on another localhost port is not
        us, V1)."""
        host, port = _split_hostport(self.headers.get("Host"))
        if host not in LOCAL_HOSTS or (port and port != str(PORT)):
            return False
        origin = self.headers.get("Origin")
        if origin:
            # "null" (sandboxed iframes) is spoofable and never sent by our
            # own page — refuse it like any foreign origin (pass-2 finding)
            try:
                u = urllib.parse.urlsplit(origin.lower())
                ohost, oport = u.hostname, u.port
            except ValueError:
                return False
            if u.scheme != "http" or ohost not in LOCAL_HOSTS or oport != PORT:
                return False
        return True

    def _post_ok(self):
        """State-changing requests: JSON only (a text/plain 'simple request'
        from another page is refused) and the per-launch token."""
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype != "application/json":
            return False
        return secrets.compare_digest(self.headers.get("X-Astro-Token") or "", TOKEN)

    def _security_headers(self, frame_self=False):
        # never framed by another site (clickjacking, V2); the dashboard is
        # framed by the panel's own Dashboard tab
        self.send_header("Content-Security-Policy",
                         "frame-ancestors 'self'" if frame_self else "frame-ancestors 'none'")
        self.send_header("X-Frame-Options", "SAMEORIGIN" if frame_self else "DENY")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self._security_headers()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, text, code=200, frame_self=False):
        body = text.encode()
        self.send_response(code)
        self._security_headers(frame_self)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        """A JSON object, or None for anything malformed or oversized (V8)."""
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return None
        if n < 0 or n > MAX_BODY:
            return None
        if n == 0:
            return {}
        try:
            data = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError, OSError):
            return None
        return data if isinstance(data, dict) else None

    def do_GET(self):
        if not self._local_ok():
            self._json({"error": "forbidden"}, 403)
            return
        if self.path == "/" or self.path.startswith("/index"):
            self._html(PAGE.replace("__ASTRO_TOKEN__", TOKEN))
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
                    self._html(f.read(), frame_self=True)
            except Exception as e:
                self._html(f"<pre>dashboard unavailable: {e}</pre>", 500)
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        if not self._local_ok() or not self._post_ok():
            self._json({"error": "forbidden"}, 403)
            return
        body = self._read_body()
        if body is None:
            self._json({"error": "bad request"}, 400)
            return
        if self.path == "/api/scan":
            self._json({"started": APP.do_scan()})
        elif self.path == "/api/import":
            names = body.get("names") or []
            decisions = body.get("calDecisions") or {}
            if not isinstance(names, list) or not all(isinstance(x, str) for x in names) \
                    or not isinstance(decisions, dict):
                self._json({"started": False, "error": "bad request"}, 400)
            elif not names:
                self._json({"started": False, "error": "no targets selected"}, 400)
            else:
                self._json({"started": APP.do_import(names, decisions)})
        elif self.path == "/api/report":
            self._json({"started": APP.do_report()})
        elif self.path == "/api/discard":
            name, night, reason = body.get("name"), body.get("night"), body.get("reason")
            if not isinstance(name, str) or not name.strip() \
                    or not isinstance(night, (str, type(None))) \
                    or not isinstance(reason, (str, type(None))):
                self._json({"started": False, "error": "no target named"}, 400)
            else:
                self._json({"started": APP.do_discard(name.strip(), night or None,
                                                      (reason or "")[:500])})
        elif self.path == "/api/skip":
            name, skip = body.get("name"), body.get("skip")
            if not isinstance(name, str) or not name.strip() or not isinstance(skip, bool):
                self._json({"started": False, "error": "bad request"}, 400)
            else:
                self._json({"started": APP.do_skip(name.strip(), skip)})
        elif self.path == "/api/clear":
            name = body.get("name")
            if not isinstance(name, str) or not name.strip():
                self._json({"started": False, "error": "bad request"}, 400)
            else:
                self._json({"started": APP.do_clear(name.strip())})
        elif self.path == "/api/eject":
            self._json({"started": APP.do_eject()})
        elif self.path == "/api/answer":
            qid, value = body.get("id"), body.get("value", "")
            if qid is None or not isinstance(value, (str, int, float)):
                # an answer must name the card it answers (V1/T6)
                self._json({"ok": False, "error": "question id required"}, 400)
            else:
                self._json({"ok": bool(APP.answer(str(value), qid=qid))})
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
  --ink:#101318; --ink2:#4d545f; --muted:#646a74;
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
.wrap{position:relative;z-index:1;max-width:min(1780px,96vw);margin:0 auto;padding:26px 30px 40px}
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
.minimeter{width:84px;height:6px;border-radius:3px;overflow:hidden;display:inline-block;
  background:color-mix(in srgb, var(--ink) 12%, transparent);vertical-align:middle}
.minimeter>span{display:block;height:100%;background:var(--accent);border-radius:3px}
#scanEyebrow{display:flex;justify-content:space-between;align-items:baseline}
#scanEyebrow #scannedAt{font-weight:500;letter-spacing:.02em;text-transform:none;
  color:var(--muted);font-size:11px}
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
.cols{display:grid;grid-template-columns:minmax(440px,5fr) minmax(430px,7fr);gap:18px}
@media(max-width:1000px){.cols{grid-template-columns:minmax(0,1fr)}}
/* ── one-page app layout: page never scrolls, panes scroll inside ── */
@media(min-width:1001px){
  html,body{height:100%;overflow:hidden}
  .wrap{height:100vh;display:flex;flex-direction:column;overflow:hidden;
    padding-top:18px;padding-bottom:10px}
  header{margin-bottom:14px}
  .tabs{margin-bottom:12px}
  #tab-panel{flex:1;min-height:0;display:flex;flex-direction:column}
  .cols{flex:1;min-height:0}
  .cols>div:first-child{display:flex;flex-direction:column;min-height:0}
  .cols>div:first-child>.card:first-child{flex:1;min-height:0;overflow-y:auto}
  #logcard{min-height:0}
  #log{height:auto;flex:1;min-height:0}
  #tab-report{flex:1;min-height:0;overflow:auto}
  #tab-dash{flex:1;min-height:0}
  #tab-dash iframe{height:100%}
  .foot{margin-top:10px}
}
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
.tmeta{display:flex;gap:4px 8px;align-items:center;flex-wrap:wrap;margin-top:3px;font-size:12px;color:var(--muted)}
.tmeta .chip{white-space:nowrap;flex:none}
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
  padding:11px 13px;height:clamp(420px,calc(100vh - 430px),860px);overflow-y:auto;
  font:12px/1.5 ui-monospace,"SF Mono",Menlo,monospace}
#log .ll{white-space:pre-wrap;overflow-wrap:anywhere;padding-left:2ch;text-indent:-2ch;margin:1.5px 0}
#log .ok{color:#63c76a}#log .wa{color:#e8b34b}#log .er{color:#e8756b;font-weight:600}#log .hd{color:#8fb6f2}
#log .lr{border-top:1px solid color-mix(in srgb, var(--logink) 22%, transparent);margin:9px 2px}
#log .lsp{height:7px}
.result{font-size:12.5px;color:var(--ink2);margin-top:10px;min-height:18px}
/* ── question ── */
.q{border:1px solid color-mix(in srgb, var(--warning) 55%, transparent);
  background:color-mix(in srgb, var(--warning) 7%, var(--surface));
  border-radius:16px;padding:16px 18px;margin-bottom:16px;box-shadow:var(--shadow)}
.q .qh{display:flex;gap:10px;align-items:center;font-weight:650;margin-bottom:8px}
/* ── completion banner ── */
.done{border:1px solid color-mix(in srgb, var(--good) 55%, transparent);
  background:color-mix(in srgb, var(--good) 8%, var(--surface));
  border-radius:16px;padding:16px 18px;margin-bottom:16px;box-shadow:var(--shadow)}
.done .dh{display:flex;gap:10px;align-items:center;font-weight:650;margin-bottom:6px;
  font-size:15.5px}
.done .dh svg{width:21px;height:21px;flex:none}
.done p{color:var(--ink2);margin-bottom:12px}
.q .qh svg{width:20px;height:20px;flex:none}
.q.danger{border-color:color-mix(in srgb, var(--serious) 60%, transparent);
  background:color-mix(in srgb, var(--serious) 7%, var(--surface))}
.q p.pre{white-space:pre-line}
.q .qfolders{font:12.5px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace}
button.dangerbtn{background:#b3261e;border-color:#b3261e;color:#fff;font-weight:600}   /* 6.5:1 in both themes (S9) */
button.dangerbtn:hover:not(:disabled){color:#fff;filter:brightness(1.08)}
button.disc{font-size:11.5px;font-weight:500;color:var(--muted);background:none;border:none;
  padding:0 2px;margin-left:auto;border-radius:4px;text-decoration:underline;
  text-underline-offset:2px;box-shadow:none}
button.disc:hover:not(:disabled){color:var(--serious);border:none}
.q p{color:var(--ink2);margin-bottom:12px}
.q input[type=text]{font:inherit;width:100%;padding:9px 11px;border:1px solid var(--line2);
  border-radius:9px;background:var(--surface);color:var(--ink);margin-bottom:11px}
.row{display:flex;gap:9px;align-items:center;flex-wrap:wrap}
/* ── tabs content ── */
iframe{width:100%;height:calc(100vh - 180px);border:1px solid var(--line);border-radius:16px;background:var(--surface)}
#reportPre{font:12px/1.55 ui-monospace,"SF Mono",Menlo,monospace;white-space:pre-wrap;background:var(--surface);
  border:1px solid var(--line);border-radius:16px;padding:18px 20px;overflow-x:auto;box-shadow:var(--shadow)}
.foot{color:var(--muted);font-size:11.5px;margin-top:20px;text-align:center}

.calcard{margin-top:12px;font-size:13px;color:var(--muted);line-height:1.55}
.calcard b{color:var(--ink)}
.calset{display:flex;gap:8px;align-items:center;padding-top:3px}
.calset .dot2{width:6px;height:6px;border-radius:50%;background:var(--warning);flex:0 0 auto}
.pairhead{margin-top:11px;font-weight:650;color:var(--ink);font-size:13px}
.pairtarget{margin-top:8px;font-weight:600;color:var(--ink2);font-size:12.5px;
  letter-spacing:.02em}
.pairrow{display:flex;gap:8px;align-items:center;padding:3px 0 0 8px;cursor:pointer;
  color:var(--muted)}
.pairrow input.caldec{appearance:none;width:16px;height:16px;border:1.5px solid var(--line2);
  border-radius:5px;background:var(--surface);cursor:pointer;flex:0 0 auto;position:relative;
  transition:all .12s;margin:0}
.pairrow input.caldec:checked{background:var(--accent);border-color:var(--accent)}
.pairrow input.caldec:checked::after{content:"";position:absolute;left:4.5px;top:1.5px;
  width:4px;height:8px;border:solid #fff;border-width:0 2px 2px 0;transform:rotate(42deg)}
.pairrow input.caldec:checked+span{color:var(--ink)}
.pairrow.qrow{cursor:default}
.qdot{width:8px;height:8px;border-radius:50%;background:var(--warning);flex:0 0 auto}
.scannote{border:1px solid color-mix(in srgb, var(--warning) 55%, transparent);
  background:color-mix(in srgb, var(--warning) 7%, var(--surface));
  border-radius:9px;padding:7px 10px;margin:0 0 8px;font-size:12.5px;line-height:1.45}
.qnote{font-size:11px;font-weight:600;color:var(--warning);margin-left:4px;
  background:color-mix(in srgb, var(--warning) 12%, transparent);
  padding:1px 8px;border-radius:999px}
.libtag{font-size:10.5px;font-weight:700;letter-spacing:.03em;color:var(--accent);
  background:color-mix(in srgb, var(--accent) 13%, transparent);
  padding:1px 7px;border-radius:999px}
.pairnote{padding:2px 0 0 8px;font-size:12px;color:var(--muted);font-style:italic}
/* ── destination preview tree ── */
.dest{margin-top:16px;border:1px solid var(--line2);border-radius:12px;
  padding:12px 14px;background:var(--surface2)}
.dest .eyebrow{margin-bottom:8px}
.droot{font:600 12.5px/1.75 ui-monospace,"SF Mono",Menlo,monospace;color:var(--ink);
  margin-top:4px}
.droot:first-of-type{margin-top:0}
.drow{font:12px/1.75 ui-monospace,"SF Mono",Menlo,monospace;color:var(--muted);
  white-space:pre-wrap;overflow-wrap:anywhere}
.dfold{color:var(--ink);font-weight:600}
.dmeta{color:var(--muted)}
.dnote{font-size:10.5px;font-weight:700;color:var(--accent);
  background:color-mix(in srgb, var(--accent) 13%, transparent);
  padding:1px 7px;border-radius:999px}
.dask{font-size:10.5px;font-weight:700;color:var(--warning);
  background:color-mix(in srgb, var(--warning) 12%, transparent);
  padding:1px 7px;border-radius:999px}
details.inv{margin-top:16px}
details.inv summary{cursor:pointer;font-size:13.5px;font-weight:600;color:var(--ink);
  list-style:none;display:flex;align-items:center;gap:10px;padding:11px 14px;
  border:1px solid var(--line2);border-radius:12px;background:var(--surface2)}
details.inv summary:hover{border-color:color-mix(in srgb, var(--accent) 40%, var(--line2))}
details.inv summary::-webkit-details-marker{display:none}
details.inv summary::before{content:"▸";transition:transform .15s;display:inline-block;
  color:var(--muted)}
details.inv[open] summary{border-bottom-left-radius:0;border-bottom-right-radius:0}
details.inv[open] summary::before{transform:rotate(90deg)}
details.inv summary .cnt{margin-left:auto;font-size:11.5px;font-weight:700;
  color:var(--accent);background:color-mix(in srgb, var(--accent) 13%, transparent);
  padding:3px 10px;border-radius:999px;font-variant-numeric:tabular-nums}
.invlist{border:1px solid var(--line2);border-top:none;border-radius:0 0 12px 12px;
  max-height:320px;overflow-y:auto;padding:4px 8px;background:var(--surface2)}
.irow{display:flex;align-items:center;gap:12px;padding:10px 8px;
  border-bottom:1px solid var(--line2)}
.irow:last-child{border-bottom:none}
.irow .nm{flex:1;font-size:14.5px;font-weight:600;color:var(--ink);
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.irow .sz{color:var(--muted);font-size:12px;flex:0 0 auto;font-variant-numeric:tabular-nums}
.irow .dt{color:var(--ink2);font-size:12px;font-weight:600;flex:0 0 78px;text-align:right;
  font-variant-numeric:tabular-nums}
.bak{font-size:10.5px;font-weight:700;letter-spacing:.04em;padding:2px 9px;border-radius:999px;
  flex:0 0 auto;color:var(--accent);background:color-mix(in srgb, var(--accent) 14%, transparent)}
.bak.skip{color:var(--muted);background:color-mix(in srgb, var(--muted) 16%, transparent)}
.bak.no{color:var(--serious);background:color-mix(in srgb, var(--serious) 14%, transparent)}
button.linkbtn{font-size:11.5px;font-weight:600;color:var(--accent);background:none;border:none;
  padding:2px 4px;cursor:pointer;text-decoration:underline;text-underline-offset:2px;flex:0 0 auto}
button.linkbtn:disabled{opacity:.5;cursor:default}
.skipbox{margin-top:16px;border:1px solid color-mix(in srgb, var(--serious) 45%, transparent);
  border-radius:12px;padding:8px 10px}
.skipbox .eyebrow{color:var(--serious);margin-bottom:4px}
.importrow{position:sticky;bottom:0;background:var(--surface);padding:10px 0 2px;z-index:2}
.done.warnd{border-color:color-mix(in srgb, var(--warning) 55%, transparent)}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
@media(max-width:520px){
  .irow{flex-wrap:wrap;row-gap:4px}
  .irow .nm{flex:1 1 100%}
  .irow .dt{flex:0 0 auto;text-align:left}
  header{flex-wrap:wrap}
}
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
  <span class="pill" id="storPill" style="display:none" title="camera storage"><span id="storageText"></span>
    <span class="minimeter"><span id="storageBar" style="width:0%"></span></span></span>
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

<div id="qbox" aria-live="assertive"></div>
<div id="doneBox" aria-live="polite"></div>

<div id="tab-panel">
  <div class="cols">
    <div>
      <div class="card">
        <div class="eyebrow" id="scanEyebrow"><span>Targets with new frames</span><span id="scannedAt"></span></div>
        <div id="notesBox"></div>
        <div id="targetList"></div>
        <div class="row importrow" style="margin-top:14px">
          <button class="primary" id="btnImport" disabled style="flex:1">Import selected</button>
        </div>
        <div class="result" id="calNote"></div>
        <div id="destBox"></div>
        <div id="invBox"></div>
      </div>
    </div>
    <div class="card" id="logcard">
      <div class="eyebrow">Activity</div>
      <div id="livebarbox">
        <div id="livebarlabel"><span id="livebarname"></span><span id="livebarpct"></span></div>
        <div id="livebar"><div style="width:0%"></div></div>
      </div>
      <div id="log"></div>
      <div class="result" id="lastResult" aria-live="polite"></div>
    </div>
  </div>
</div>

<div id="tab-report" style="display:none">
  <pre id="reportPre">No report yet — click “Refresh report”.</pre>
</div>
<div id="tab-dash" style="display:none">
  <iframe id="dashFrame" title="dashboard"></iframe>
</div>

<div class="foot">Engine: astro-import.py (backup-first, ASIAir + Seestar) · the ASIAir is never modified · the Seestar is only cleared with your Yes (SAFE: backed up and verified) or a typed DISCARD ·
tip: Safari → File → Add to Dock turns this into a Dock app</div>
</div>
<script>
const $=s=>document.querySelector(s);
const fmtGB=b=>b>=1073741824?(b/1073741824).toFixed(1)+" GB":Math.round(b/1048576)+" MB";
const MONTHS=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
const fmtStamp=st=>{ // "20260808-231544" → "8 Aug 26"
  if(!st||st.length<8) return "";
  return `${+st.slice(6,8)} ${MONTHS[+st.slice(4,6)-1]} ${st.slice(2,4)}`;
};
const byNewest=(a,b)=>(b.lastStamp||"").localeCompare(a.lastStamp||"");
const esc=s=>String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
let busy=false, lastLogSig="", lastScanStamp="", curScan=null;

document.querySelectorAll(".tabs button").forEach(b=>b.addEventListener("click",()=>{
  document.querySelectorAll(".tabs button").forEach(x=>x.classList.remove("on"));
  b.classList.add("on");
  ["panel","report","dash"].forEach(t=>$("#tab-"+t).style.display = b.dataset.tab===t?"":"none");
  if(b.dataset.tab==="dash") $("#dashFrame").src="/dashboard?t="+Date.now();
  if(b.dataset.tab==="report") loadReport();
}));

const TOKEN="__ASTRO_TOKEN__";
async function api(path, body){
  const r=await fetch(path,{method:body!==undefined?"POST":"GET",
    headers:{"Content-Type":"application/json","X-Astro-Token":TOKEN},
    body:body!==undefined?JSON.stringify(body):undefined});
  return r.json();
}

function scopeChip(t){
  if(!t.scope) return t.source ? '<span class="chip plain">'+esc(t.source)+'</span>' : '';
  const cls = t.scope.includes("FRA400") ? "c1" : (t.scope.includes("107PHQ") ? "c2" : "c3");
  return `<span class="chip ${cls}">${esc(t.scope.replace("Askar ",""))}</span>`
         + (t.source ? `<span class="chip plain">${esc(t.source)}</span>` : "");
}

function notesHtml(scan){
  if(!scan.notes||!scan.notes.length) return "";
  return scan.notes.map(n=>`<div class="scannote">⚠ ${esc(n)}</div>`).join("");
}
const unitFor=t=>(t.unit==="frames"||!t.unit)?(t.new===1?"frame":"frames"):t.unit;
function pillFor(t){
  if(t.skipped) return `<span class="bak skip">never import</span>`;
  if(t.device!=="seestar") return `<span class="bak">backed up · kept on ASIAir</span>`;
  if(t.safeState==="safe") return `<span class="bak">backed up</span>`;
  return `<span class="bak no">NOT backed up${t.unproven?` · ${t.unproven} file${t.unproven===1?"":"s"}`:""}</span>`;
}
function invSection(scan){
  const rest=scan.targets.filter(t=>!(t.new>0 && !t.skipped)).sort(byNewest);
  const skippedNew=rest.filter(t=>t.skipped && t.new>0);
  const others=rest.filter(t=>!(t.skipped && t.new>0));
  let h="";
  if(skippedNew.length){
    // a never-import target with new frames is NOT backed up — never listed
    // under "all backed up" again (1.4.3 review B1)
    h+=`<div class="skipbox"><div class="eyebrow">On the never-import list — NOT backed up</div>`+
      skippedNew.map(t=>`<div class="irow"><div class="nm">${esc(t.display)}</div>
        <div class="dt">${fmtStamp(t.lastStamp)}</div>
        <div class="sz">${t.new.toLocaleString()} new · ${fmtGB(t.newBytes||0)}</div>
        <button type="button" class="linkbtn unskip" data-name="${encodeURIComponent(t.name)}"
          aria-label="Take ${esc(t.display)} off the never-import list">import again</button></div>`).join("")+
      `</div>`;
  }
  if(!others.length) return h;
  const notSafe=others.filter(t=>t.device==="seestar"&&!t.skipped&&t.safeState!=="safe").length;
  const tot=others.reduce((a,t)=>a+(t.totalBytes||0),0);
  const wasOpen=!!document.querySelector("#invBox details.inv[open]");
  h+=`<details class="inv"${wasOpen||notSafe?" open":""}><summary>${notSafe?"Also on camera":"Also on camera — all backed up"}
      <span class="cnt">${others.length} item${others.length>1?"s":""} · ${fmtGB(tot)}${notSafe?` · ${notSafe} not backed up`:""}</span></summary>
    <div class="invlist">
    ${others.map(t=>{
      let act="";
      if(t.clearId && !t.skipped)
        act=`<button type="button" class="linkbtn clr" data-id="${encodeURIComponent(t.clearId)}"
               aria-label="Clear ${esc(t.display)} from the camera (backed up and verified)"
               title="Delete from the Seestar — everything in it is backed up and verified">clear…</button>`;
      else if(t.device==="seestar" && t.safeState!=="safe" && t.discardId)
        act=`<button type="button" class="disc" data-name="${encodeURIComponent(t.discardId)}"
               aria-label="Discard the never-backed-up files of ${esc(t.display)}"
               title="Delete the files that were NEVER backed up — asks you to type DISCARD">discard…</button>`;
      return `<div class="irow"><div class="nm">${esc(t.display)}</div>
      <div class="dt">${fmtStamp(t.lastStamp)}</div>
      <div class="sz">${(t.files||0).toLocaleString()} file${t.files===1?"":"s"} · ${fmtGB(t.totalBytes||0)}</div>
      ${pillFor(t)}${act}</div>`;}).join("")}
    </div>
  </details>`;
  return h;
}
function bindRowActions(root){
  root.querySelectorAll(".disc").forEach(b=>b.addEventListener("click",e=>{
    e.preventDefault(); e.stopPropagation();          // never toggles the row's checkbox
    if(busy) return;
    api("/api/discard",{name:decodeURIComponent(b.dataset.name)});
  }));
  root.querySelectorAll(".clr").forEach(b=>b.addEventListener("click",e=>{
    e.preventDefault(); if(busy) return;
    api("/api/clear",{name:decodeURIComponent(b.dataset.id)});
  }));
  root.querySelectorAll(".unskip").forEach(b=>b.addEventListener("click",e=>{
    e.preventDefault(); if(busy) return;
    api("/api/skip",{name:decodeURIComponent(b.dataset.name),skip:false});
  }));
}
function setEyebrow(text){ $("#scanEyebrow").firstElementChild.textContent=text; }
function renderTargets(scan){
  const box=$("#targetList");
  const withNew=scan.targets.filter(t=>t.new>0 && !t.skipped)
      .sort((a,b)=>byNewest(a,b)||b.new-a.new);   // most recent night first
  $("#notesBox").innerHTML = notesHtml(scan);
  if(!withNew.length){
    const notSafe=scan.targets.filter(t=>t.device==="seestar"&&!t.skipped&&t.safeState!=="safe").length;
    const skippedNew=scan.targets.filter(t=>t.skipped&&t.new>0).length;
    const attn=(scan.notes||[]).length+notSafe+skippedNew;
    box.innerHTML = !scan.targets.length
      ? `<div class="clear"><b>Nothing on the camera</b><span>No frames found to back up.</span></div>`
      : attn
      ? `<div class="clear"><b>Nothing new to import</b><span>${attn} item(s) on the camera are NOT backed up — see below.</span></div>`
      : `<div class="clear"><div class="ring">
           <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M4.5 12.5l5 5 10-11" stroke="var(--good)" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
         </div><b>All backed up</b><span>Every file on the camera is backed up and verified.</span></div>`;
    $("#invBox").innerHTML = invSection(scan);
    bindRowActions($("#invBox"));
    $("#btnImport").disabled=true;
    $("#btnImport").textContent="Import selected";
    setEyebrow("Targets");
    return;
  }
  setEyebrow(scan.hasLedger?"Targets with new frames":"First import — everything on the camera is new");
  box.innerHTML = withNew.map(t=>`
    <label class="trow">
      <input type="checkbox" class="cb sel" data-name="${encodeURIComponent(t.name)}" checked
        aria-label="Import ${esc(t.display)}">
      <div class="tmain">
        <div class="tname">${esc(t.display)}</div>
        <div class="tmeta">${scopeChip(t)}${t.what?`<span>${esc(t.what)}</span>`:(t.hours==null?"":`<span>${t.hours.toFixed(1)} h integration</span>`)}${t.discardId&&scan.hasLedger?`<button type="button" class="disc" data-name="${encodeURIComponent(t.discardId)}" aria-label="Discard ${esc(t.display)} without importing" title="Delete from the Seestar WITHOUT importing — asks you to type DISCARD">discard…</button>`:""}</div>
      </div>
      <div class="tstats">
        <div class="big">${t.new.toLocaleString()}</div>
        <div class="small">${esc(unitFor(t))} · ${fmtGB(t.newBytes)}</div>
      </div>
    </label>`).join("");
  $("#invBox").innerHTML = invSection(scan);
  box.querySelectorAll(".sel").forEach(c=>c.addEventListener("change",updateImportBtn));
  bindRowActions(box); bindRowActions($("#invBox"));
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

const stripYN=p=>String(p||"").replace(/\s*\[[yYnN]\/[yYnN]\]\s*$/,"");
function qTitle(q){
  const p=q.prompt||"";
  if(q.kind==="text") return "Name this target";
  if(/SAFE source folders/.test(p)) return "Clear from the camera?";
  if(/^Never import/.test(p)) return "Never import this target?";
  if(/flat/i.test(p)) return "Flats need your decision";
  return "A question before continuing";
}
function wireKeys(card, yes, no, okToSubmit){
  card.addEventListener("keydown",e=>{
    if(e.key==="Escape"){ e.preventDefault(); no.click(); }
    else if(e.key==="Enter" && e.target.tagName==="INPUT" && okToSubmit()){ e.preventDefault(); yes.click(); }
  });
}
function renderQuestion(q){
  const box=$("#qbox");
  if(!q){ box.innerHTML=""; box.dataset.qid=""; return; }
  if(box.dataset.qid==String(q.id)) return;
  box.dataset.qid=q.id;
  const isText=q.kind==="text";
  if(q.kind==="typed"){
    const want=q.expect||"DISCARD";
    box.innerHTML=`<div class="q danger" role="alertdialog" aria-labelledby="qtitle"><div class="qh" id="qtitle">
      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M12 3l9.5 17h-19L12 3z" stroke="var(--serious)" stroke-width="1.8" stroke-linejoin="round"/><path d="M12 10v4.5" stroke="var(--serious)" stroke-width="1.8" stroke-linecap="round"/><circle cx="12" cy="17.4" r="1.1" fill="var(--serious)"/></svg>
      Delete from the camera — these were never backed up</div>
      <p class="pre">${esc(q.prompt.replace(/\n> $/,""))}</p>
      <input type="text" id="qval" autocomplete="off" spellcheck="false" placeholder="type ${esc(want)} to confirm"
        aria-label="Type ${esc(want)} to confirm">
      <div class="row"><button class="dangerbtn" id="qyes" disabled>Delete from camera</button><button class="primary" id="qno">Cancel</button></div></div>`;
    const inp=$("#qval"), yes=$("#qyes"), no=$("#qno");
    inp.addEventListener("input",()=>{ yes.disabled = inp.value.trim()!==want; });
    yes.onclick=()=>{ if(inp.value.trim()===want) api("/api/answer",{id:q.id,value:inp.value.trim()}); };
    no.onclick=()=>api("/api/answer",{id:q.id,value:""});
    wireKeys(box.firstElementChild, yes, no, ()=>inp.value.trim()===want);
    inp.focus();
    return;
  }
  const p=stripYN(q.prompt);
  const safeCard=/SAFE source folders/.test(q.prompt), neverCard=/^Never import/.test(q.prompt);
  let buttons;
  if(isText) buttons='<button class="primary" id="qyes">Save name</button><button id="qno">Skip</button>';
  else if(safeCard) buttons='<button class="dangerbtn" id="qyes">Delete from camera</button><button class="primary" id="qno">Keep on camera</button>';
  else if(neverCard) buttons='<button id="qyes">Never import</button><button class="primary" id="qno">Keep importing it</button>';
  else if(q.default==="n") buttons='<button id="qyes">Yes</button><button class="primary" id="qno">No</button>';
  else buttons='<button class="primary" id="qyes">Yes</button><button id="qno">No</button>';
  box.innerHTML=`<div class="q" role="alertdialog" aria-labelledby="qtitle"><div class="qh" id="qtitle">
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M12 3l9.5 17h-19L12 3z" stroke="var(--warning)" stroke-width="1.8" stroke-linejoin="round"/><path d="M12 10v4.5" stroke="var(--warning)" stroke-width="1.8" stroke-linecap="round"/><circle cx="12" cy="17.4" r="1.1" fill="var(--warning)"/></svg>
    ${esc(qTitle(q))}</div>
    <p class="pre${safeCard?" qfolders":""}">${esc(p)}</p>
    ${isText?'<input type="text" id="qval" placeholder="(leave blank to keep the folder name)" aria-label="Target name">':""}
    <div class="row">${buttons}</div></div>`;
  const yes=$("#qyes"), no=$("#qno");
  yes.onclick=()=>api("/api/answer",{id:q.id,value:isText?($("#qval").value||""):"y"});
  no.onclick=()=>api("/api/answer",{id:q.id,value:isText?"":"n"});
  wireKeys(box.firstElementChild, yes, no, ()=>true);
  if(isText) $("#qval").focus();
  else (box.querySelector("button.primary")||no).focus();
}

function calCountsFor(target){
  // Sum the currently TICKED pairing rows per frame type for one target.
  const out={Bias:0,Dark:0,Flat:0,ask:false};
  const rows=(((curScan||{}).calSummary||{}).pairings||{})[target]||[];
  for(const x of rows){
    if(x.questionable){ if(x.type==="Flat") out.ask=true; continue; }
    const cb=document.querySelector(
      `.caldec[data-t="${encodeURIComponent(target)}"][data-k="${encodeURIComponent(x.setKey)}"]`);
    if(!cb||cb.checked) out[x.type]=(out[x.type]||0)+x.count;
  }
  return out;
}

function renderDestPlan(){
  const box=$("#destBox");
  const plan=(curScan||{}).destPlan||[];
  if(!plan.length){box.innerHTML="";return;}
  const groups={};
  plan.forEach(e=>{(groups[e.deviceRoot]=groups[e.deviceRoot]||[]).push(e)});
  let h=`<div class="dest"><div class="eyebrow">Where files will land</div>`;
  for(const root of Object.keys(groups)){
    h+=`<div class="droot">${esc(root)}/</div>`;
    const es=groups[root];
    es.forEach((e,i)=>{
      const last=i===es.length-1, l1=last?"└─":"├─", pipe=last?"&nbsp;&nbsp;&nbsp;":"│&nbsp;&nbsp;";
      const nameNote=e.askName?` <span class="dnote">will ask for a friendly name</span>`:"";
      h+=`<div class="drow">${l1} <span class="dfold">${esc(e.treeRoot.join("/"))}/</span>${nameNote}</div>`;
      if(e.device==="asiair"){
        const nights=e.nights.length>1?` · ${e.nights.length} nights`:"";
        const cont=e.continuing?` <span class="dnote">continues the existing folder</span>`:"";
        h+=`<div class="drow">${pipe}└─ <span class="dfold">lights/${esc(e.dayFolder)}/</span> `+
           `<span class="dmeta">${e.files.toLocaleString()} lights · ${fmtGB(e.bytes)}${nights}</span>${cont}</div>`;
        const c=calCountsFor(e.target);
        const parts=[];
        if(c.Bias) parts.push(`${c.Bias.toLocaleString()} biases`);
        if(c.Dark) parts.push(`${c.Dark.toLocaleString()} darks`);
        if(c.Flat) parts.push(`${c.Flat.toLocaleString()} flats`);
        let cal=parts.length
          ?`<span class="dfold">calibration/</span> <span class="dmeta">${parts.join(" · ")} linked${e.sharedCal?" (shared, target level)":""}</span>`
          :`<span class="dmeta">no calibration linked</span>`;
        if(c.ask) cal+=` <span class="dask">flats ask at import</span>`;
        h+=`<div class="drow">${pipe}&nbsp;&nbsp;&nbsp;└─ ${cal}</div>`;
      } else {
        if(e.files && e.dayFolder)
          h+=`<div class="drow">${pipe}${e.stack?"├─":"└─"} <span class="dfold">${esc(e.dayFolder)}/</span> `+
             `<span class="dmeta">${e.files.toLocaleString()} lights · ${fmtGB(e.bytes)}${(e.nights||[]).length>1?` · ${e.nights.length} nights, one Day each`:""}</span></div>`;
        else if(e.files)
          h+=`<div class="drow">${pipe}${e.stack?"├─":"└─"} <span class="dmeta">${e.files.toLocaleString()} file(s) · ${fmtGB(e.bytes)}${e.continuing?" · joins existing folder":""}</span></div>`;
        if(e.stack)
          h+=`<div class="drow">${pipe}└─ <span class="dfold">${esc(e.stack.filename)}</span> `+
             `<span class="dmeta">${e.stack.count>1?`${e.stack.count} stacks, one per session`:`${e.stack.subs.toLocaleString()} subs`} · kept beside earlier stacks</span></div>`;
      }
    });
  }
  box.innerHTML=h+"</div>";
}
document.addEventListener("change",e=>{
  if(e.target && e.target.classList && e.target.classList.contains("caldec")) renderDestPlan();
});

let dismissedDone="";
function renderDone(d){
  const box=$("#doneBox");
  if(d && d.op && d.op!=="import" && !busy && d.finishedAt!==dismissedDone){
    const title=d.op==="clear"?"Cleared from the camera":(d.warn?"Discard only partly done":"Discarded");
    if(box.dataset.sig===d.finishedAt+title) return;
    box.dataset.sig=d.finishedAt+title;
    box.innerHTML=`<div class="done${d.warn?" warnd":""}"><div class="dh">
      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="12" cy="12" r="10" stroke="var(--${d.warn?"warning":"good"})" stroke-width="1.8"/><path d="M7.5 12.5l3 3 6-7" stroke="var(--${d.warn?"warning":"good"})" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
      ${esc(title)}</div><p>${esc(d.text||"")}</p><button id="doneOk">Dismiss</button></div>`;
    $("#doneOk").onclick=()=>{dismissedDone=d.finishedAt; box.dataset.sig=""; renderDone(null);};
    return;
  }
  box.dataset.sig="";
  if(!d || !d.frames || busy || d.finishedAt===dismissedDone){
    box.innerHTML=""; document.title="BrettjoAstro FITS Importer"; return;
  }
  const mins=Math.floor(d.seconds/60), secs=d.seconds%60;
  const dur=d.seconds>=60?`${mins}m ${secs}s`:`${d.seconds}s`;
  document.title="✓ Import complete — BrettjoAstro FITS Importer";
  box.innerHTML=`<div class="done"><div class="dh">
    <svg viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" stroke="var(--good)" stroke-width="1.8"/><path d="M7.5 12.5l3 3 6-7" stroke="var(--good)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
    Import complete</div>
    <p><b>${d.frames.toLocaleString()}</b> frame${d.frames===1?"":"s"} imported and verified across <b>${d.targets.toLocaleString()}</b> target${d.targets===1?"":"s"} · took ${dur} · finished ${esc(d.finishedAt)}</p>
    <button id="doneOk">Nice — dismiss</button></div>`;
  $("#doneOk").onclick=()=>{dismissedDone=d.finishedAt; renderDone(null);};
}

function renderLog(lines){
  const el=$("#log");
  el.innerHTML = lines.map(l=>{
    // display only: shorten /Users/<name>/ to ~/ so paths fit on one line
    const raw=l.replace(/\/(?:Users|home)\/[^\/\s]+\//g,"~/");
    if(/^\s*[─—=_-]{6,}\s*$/.test(raw)) return '<div class="lr"></div>';
    if(!raw.trim()) return '<div class="lsp"></div>';
    let cls="";
    if(raw.startsWith("✓")) cls=" ok";
    else if(raw.startsWith("⚠")||raw.startsWith("△")) cls=" wa";
    else if(raw.startsWith("✗")) cls=" er";
    else if(raw.startsWith("▸")) cls=" hd";
    return `<div class="ll${cls}">${esc(raw)}</div>`;
  }).join("");
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
    ["btnScan","btnEject"].forEach(id=>$("#"+id).disabled=busy||!s.cameraPresent);
    $("#btnReport").disabled=busy;
    if(s.scan && (s.scannedAt!==lastScanStamp)){
      lastScanStamp=s.scannedAt;
      curScan=s.scan;
      renderTargets(s.scan);
      const cs=s.scan.calSummary;
      if(cs && cs.total){
        const exp=x=>x.exposureSeconds==null?"":(x.exposureSeconds>=1?` ${x.exposureSeconds}s`:` ${Math.round(x.exposureSeconds*1000)}ms`);
        const setLabel=x=>`${x.count} × ${esc(x.type)}${exp(x)}${x.filter?" · "+esc(x.filter):""}${x.type==="Flat"&&x.rotation!=null?" · "+x.rotation+"°":""} · ${esc(x.night)}`;
        let h=`<b>${cs.total.toLocaleString()}</b> calibration frames on camera · <b>${cs.inLibrary.toLocaleString()}</b> already in the Library`;
        const nNew=cs.newSets.reduce((a,x)=>a+x.count,0);
        if(nNew){
          h+=` · <b>${nNew.toLocaleString()} new</b> — backed up to the Library on next import:`;
          h+=cs.newSets.map(x=>`<div class="calset"><span class="dot2"></span>${setLabel(x)}</div>`).join("");
        }
        const pr=cs.pairings||{};
        const tn=Object.keys(pr);
        if(tn.length){
          h+=`<div class="pairhead">Pairings for this import — untick anything that isn't for that target:</div>`;
          for(const t of tn){
            const disp=((s.scan.targets||[]).find(x=>x.name===t)||{}).display||t;
            h+=`<div class="pairtarget">${esc(disp)}</div>`;
            const rows=pr[t]||[];
            if(!rows.length){h+=`<div class="pairnote">no matching calibration — imports without cal links</div>`;continue;}
            h+=rows.map(x=>{
              const lib=x.inLibrary>=x.count?` <span class="libtag">from Library</span>`:"";
              if(x.questionable)
                return `<div class="pairrow qrow"><span class="qdot"></span>${setLabel(x)}${lib}<span class="qnote">asks during import</span></div>`;
              return `<label class="pairrow"><input type="checkbox" class="caldec" `+
                     `data-t="${encodeURIComponent(t)}" data-k="${encodeURIComponent(x.setKey)}" checked>`+
                     `<span>${setLabel(x)}${lib}</span></label>`;
            }).join("");
            if(!rows.some(x=>x.type==="Flat"))
              h+=`<div class="pairnote">no matching flats — imports without flats</div>`;
          }
          h+=`<div style="margin-top:6px">Ticked pairings link without asking · untick = don't link (frames still back up) · amber ones ask during the import.</div>`;
        } else if(nNew){
          h+=`<div style="margin-top:5px">Flats always ask before linking to a target's Day folder.</div>`;
        }
        $("#calNote").innerHTML=h;
        $("#calNote").className="result calcard";
      } else {
        $("#calNote").textContent="";
      }
      renderDestPlan();
      if(s.scan.disks && s.scan.disks.length){
        const parts=s.scan.disks.map(d=>d.label+" "+fmtGB(d.used)+" / "+fmtGB(d.total)+" · "+fmtGB(d.free)+" free");
        $("#storageText").textContent=parts.join("  ·  ");
        const d=s.scan.disks[0], pct=Math.round(100*d.used/d.total);
        $("#storageBar").style.width=pct+"%";
        $("#storPill").style.display="";
      } else if(s.scan.disk){
        const d=s.scan.disk, pct=Math.round(100*d.used/d.total);
        $("#storageText").textContent=fmtGB(d.used)+" / "+fmtGB(d.total)+" · "+fmtGB(d.free)+" free";
        $("#storageBar").style.width=pct+"%";
        $("#storPill").style.display="";
      }
      $("#scannedAt").textContent = s.scannedAt ? "scanned "+s.scannedAt : "";
    }
    if(!s.scan && !busy && s.cameraPresent && !(s.lastResult||"").startsWith("scanning failed")){ /* fresh state after import → rescan */ api("/api/scan",{}); }
    if(!s.cameraPresent && !busy && !s.question){
      if(!$("#targetList").dataset.nocam){
        $("#targetList").dataset.nocam="1";
        $("#targetList").innerHTML=`<div class="clear"><b>Plug in your Seestar or ASIAir</b><span>It is scanned automatically — nothing is copied or changed until you press Import.</span></div>`;
        $("#notesBox").innerHTML=""; $("#invBox").innerHTML=""; $("#destBox").innerHTML="";
        $("#btnImport").disabled=true; lastScanStamp=""; setEyebrow("Targets");
      }
    } else { $("#targetList").dataset.nocam=""; }
    updateImportBtn();
    renderQuestion(s.question);
    renderDone(s.lastDone);
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
  if(!names.length) return;
  const dec={};
  document.querySelectorAll(".caldec").forEach(cb=>{
    const t=decodeURIComponent(cb.dataset.t);
    (dec[t]=dec[t]||{})[decodeURIComponent(cb.dataset.k)]=cb.checked;
  });
  api("/api/import",{names,calDecisions:dec});
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

    global PORT
    PORT = args.port
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
