#!/usr/bin/env python3
"""
BrettjoAstro FITS Importer — camera watcher for Windows (1.5.0).

The Windows counterpart of astro-watch.sh (which launchd runs on the Mac).
Started at logon from a shortcut in the Startup folder, it runs windowless
under pythonw and checks every few seconds for a camera drive:

  * a drive letter carrying  Autorun\\   is the ASIAir
  * a drive letter carrying  MyWorks\\   is a Seestar

When a camera arrives it makes sure the control panel is running, shows a
notification, and opens the panel in the browser — the same hands-free flow
as the Mac: plug in, notification, panel, scan. Nothing is copied or changed
until you press Import.

Repeat arrivals of the SAME camera set within 10 minutes (a loose cable) do
not notify again. Only one watcher runs at a time.

It also runs on macOS, and imports with no side effects: the FITs Importer
App calls poll_once() from its own loop (1.5.3). On the Mac the web version
keeps using astro-watch.sh. While the app owns this machine (eng.app_owner())
this watcher does nothing and exits.

  pythonw -X utf8 astro-watch.py            run (normally started at logon)
  python  -X utf8 astro-watch.py --once     print what it sees now, and exit
"""

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time
import urllib.request
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE_PATH = os.path.join(HERE, "astro-import.py")
APP_PATH = os.path.join(HERE, "astro-app.py")
POLL_S = float(os.environ.get("ASTRO_WATCH_POLL_S", "3"))
FLAP_GUARD_S = int(os.environ.get("ASTRO_FLAP_GUARD_S", "600"))

_spec = importlib.util.spec_from_file_location("astro_engine_w", ENGINE_PATH)
eng = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eng)

PORT = eng.panel_port()
URL = f"http://127.0.0.1:{PORT}"

LOG_DIR = os.path.join(eng.STATE_DIR, "Logs")
LOG_PATH = os.environ.get("ASTRO_WATCH_LOG") or os.path.join(LOG_DIR, "astro-watch.log")
STATE_PATH = os.environ.get("ASTRO_WATCH_STATE") or os.path.join(eng.STATE_DIR,
                                                                  "astro-watch.state.json")


def wlog(msg):
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        if os.path.isfile(LOG_PATH) and os.path.getsize(LOG_PATH) > 1_000_000:
            os.replace(LOG_PATH, LOG_PATH + ".1")          # keep the log small
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}: {msg}\n")
    except OSError:
        pass


def cameras_now():
    """{'ASIAir': path, 'Seestar': path} for whatever is plugged in now."""
    eng.refresh_camera_volumes(force=True)
    found = {}
    if os.path.isdir(eng.ASIAIR_VOLUME):
        found["ASIAir"] = eng.ASIAIR_VOLUME
    sv = eng.seestar_volume()
    if sv:
        found["Seestar"] = sv
    return found


def presence_key(found):
    return "+".join(f"{k}@{v}" for k, v in sorted(found.items())) or "none"


def panel_up():
    try:
        with urllib.request.urlopen(URL + "/api/ping", timeout=2) as r:
            return json.loads(r.read().decode()).get("ok") is True
    except Exception:
        return False


def start_panel():
    """Start the panel windowless, detached, as its own process."""
    if eng.TEST_ROOT:                          # test mode: recorded, never started
        eng._test_record("panel-start", port=PORT)
        return False
    exe = sys.executable
    if eng.IS_WINDOWS and exe.lower().endswith("python.exe"):
        cand = exe[:-len("python.exe")] + "pythonw.exe"
        if os.path.isfile(cand):
            exe = cand
    flags = 0
    if eng.IS_WINDOWS:
        flags = (getattr(subprocess, "DETACHED_PROCESS", 0x8)
                 | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200)
                 | getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000))
    # no std handles at all: the panel then logs to its own file, and never
    # mistakes NUL for a console (which flashed a window — review W3)
    subprocess.Popen([exe, "-X", "utf8", APP_PATH, "--no-browser", "--port", str(PORT)],
                     cwd=HERE, creationflags=flags, close_fds=True)
    for _ in range(40):
        if panel_up():
            return True
        time.sleep(0.5)
    return False


def load_state():
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"presence": "none", "notifiedAt": 0, "notifiedSet": ""}


def save_state(st):
    try:
        os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(st, f)
    except OSError:
        pass


def on_arrival(found, st=None, open_browser=True, repeat=False):
    """The web version's arrival: the panel up, a notification and the browser.
    True when Brett was told (poll_once then starts the flap guard); False
    when nothing was shown. repeat: the same cameras re-plugged within the
    flap guard, so the panel is only kept up, never announced again. (st is
    no longer read here: the guard lives in poll_once, 1.5.3.)"""
    label = " + ".join(sorted(found))
    if eng.app_owner():                        # U1: the app handles arrivals, not this
        wlog(f"{label} arrived — the FITs Importer App is in charge here, nothing done")
        return False
    if not panel_up():
        wlog(f"{label} arrived — starting the panel")
        if not start_panel():
            wlog("panel did not come up — use 'Restart FITS Importer' on the Desktop")
            eng.notify(f"{label} connected, but the panel did not start. Use "
                       f"'Restart FITS Importer' on the Desktop.", "FITS Importer")
            return False
    if repeat:
        wlog(f"{label} re-arrived within {FLAP_GUARD_S}s — no second notification")
        return False
    eng.notify(f"{label} connected — opening the FITS Importer. Nothing is copied "
               f"until you press Import.", "FITS Importer")
    if open_browser:
        if eng.TEST_ROOT:                      # test mode: recorded, never opened
            eng._test_record("browser", url=URL)
        else:
            webbrowser.open(URL)
    wlog(f"{label} arrived — notified, panel opened")
    return True


def poll_once(st, on_arrival=None, on_removed=None, on_rearrived=None):
    """One look at the drives: [("arrived", found)] or [("gone", previous)]
    when what is plugged in changed since the last look, else []. The same
    cameras back within FLAP_GUARD_S of the last arrival acted on (a loose
    cable) give [("rearrived", found)] and on_rearrived(found), never a second
    on_arrival: the flap guard is here, for the web watcher and the app alike.
    The callbacks get found / previous. An arrival acted on (on_arrival not
    returning False) starts the guard, and st, guard included, is saved on
    every change, right after the callback."""
    found = cameras_now()
    key = presence_key(found)
    if key == st.get("presence"):
        return []
    if found:
        now = time.time()
        if st.get("notifiedSet") == key and now - (st.get("notifiedAt") or 0) < FLAP_GUARD_S:
            event = ("rearrived", found)
            if on_rearrived:
                on_rearrived(found)
        else:
            event = ("arrived", found)
            if on_arrival is None or on_arrival(found) is not False:
                st["notifiedSet"], st["notifiedAt"] = key, now
    else:
        event = ("gone", st.get("found") or {})
        if on_removed:
            on_removed(event[1])
    st["presence"], st["found"] = key, found
    save_state(st)
    return [event]


def single_instance():
    """True if this is the only watcher. A named mutex on Windows; a pid
    file elsewhere, and under a test (which must never hold, or be refused
    by, the real watcher's mutex)."""
    if eng.IS_WINDOWS and not eng.TEST_ROOT:
        try:
            import ctypes
            k32 = ctypes.WinDLL("kernel32", use_last_error=True)
            single_instance.handle = k32.CreateMutexW(None, False, "Local\\BrettjoAstroWatch")
            return ctypes.get_last_error() != 183          # ERROR_ALREADY_EXISTS
        except Exception:
            return True
    pid_path = STATE_PATH + ".pid"
    try:
        with open(pid_path) as f:
            if eng.pid_alive(int(f.read().strip() or 0)):
                return False
    except (OSError, ValueError):
        pass
    try:
        with open(pid_path, "w") as f:
            f.write(str(os.getpid()))
    except OSError:
        pass
    return True


def main(argv=None):
    ap = argparse.ArgumentParser(description="FITS Importer camera watcher")
    ap.add_argument("--once", action="store_true",
                    help="print the cameras seen right now and exit (changes nothing)")
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args(argv)
    if eng.TEST_ROOT and PORT == 8765:
        # 8765 is the real panel's port: a test watcher never pings or starts it
        print("TEST MODE: the watcher never uses port 8765 under a test "
              "(set ASTRO_PANEL_PORT)", file=sys.stderr)
        return 3

    if args.once:
        found = cameras_now()
        print(f"FITS Importer watcher {eng.VERSION} ({eng.PLATFORM})")
        print("drives checked:", ", ".join(eng._drive_roots()) or "(none)")
        print("cameras:", ", ".join(f"{k} at {v}" for k, v in sorted(found.items())) or "none")
        print("panel running:", "yes" if panel_up() else "no")
        return 0

    rec = eng.app_owner()
    if rec:                                    # U1: the app runs its own watcher
        wlog(f"the FITs Importer App is in charge here ({rec.get('appPath')}) "
             "— watcher not started")
        return 0
    if not single_instance():
        return 0
    wlog(f"watcher {eng.VERSION} started (poll {POLL_S}s)")
    st = load_state()
    while True:
        try:
            poll_once(st,
                      on_arrival=lambda found: on_arrival(found, st,
                                                          open_browser=not args.no_browser),
                      on_removed=lambda previous: wlog("cameras removed"),
                      on_rearrived=lambda found: on_arrival(found, st, repeat=True))
        except Exception as e:                           # never die on a hiccup
            wlog(f"watcher error: {e}")
        time.sleep(POLL_S)


if __name__ == "__main__":
    eng._platform_bootstrap(os.path.abspath(__file__))
    sys.exit(main())
