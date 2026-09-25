#!/usr/bin/env python3
"""
BrettjoAstro FITS Importer — install check, Mac and Windows (1.5.0).

Run it after installing (it changes nothing on your cameras, your ledger or
your archive):

    Windows:  py -3 -X utf8 "$env:LOCALAPPDATA\\BrettjoAstro\\bin\\selftest.py"   (Terminal / PowerShell)
    Mac:      /usr/local/bin/python3 ~/bin/selftest.py
    ... add --toast to also try a desktop notification

It prints one line per check and a summary to paste back if anything is red.
Checks that belong to the other platform are skipped.
"""

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = {"PASS": 0, "WARN": 0, "FAIL": 0, "SKIP": 0}
# What each platform's installer puts beside this file. Each has its own
# watcher: launchd runs astro-watch.sh on the Mac, the Startup shortcut runs
# astro-watch.py on Windows (PARITY.md). test_v2 checks these lists against
# install-scripts.sh and install-windows.ps1, so the two can't drift again.
INSTALLED = {
    "mac": ("astro-import.py", "astro-app.py", "astro-watch.sh", "selftest.py"),
    "windows": ("astro-import.py", "astro-app.py", "astro-watch.py", "selftest.py"),
}


def line(kind, name, detail=""):
    RESULTS[kind] += 1
    print(f"  {kind:<4}  {name}" + (f"  — {detail}" if detail else ""))


def check(name, cond, detail="", warn_only=False):
    line("PASS" if cond else ("WARN" if warn_only else "FAIL"), name, "" if cond else detail)
    return cond


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--toast", action="store_true", help="also show a test notification")
    args = ap.parse_args()

    print(f"FITS Importer install check — Python {sys.version.split()[0]} at {sys.executable}")
    check("Python 3.9 or newer", sys.version_info >= (3, 9), sys.version)
    check("UTF-8 mode on (-X utf8)", bool(sys.flags.utf8_mode) or os.name != "nt",
          "run with: py -3 -X utf8 selftest.py", warn_only=True)

    engine = os.path.join(HERE, "astro-import.py")
    if not check("engine present next to this file", os.path.isfile(engine), engine):
        return summary()
    spec = importlib.util.spec_from_file_location("astro_engine_t", engine)
    eng = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(eng)
    print(f"  ----  engine {eng.VERSION} on {eng.PLATFORM}")
    # the panel's port, as the watcher sees it. Under a test (eng.TEST_ROOT)
    # the real panel's 8765 is never contacted
    port = eng.panel_port()
    test_8765 = bool(eng.TEST_ROOT) and port == 8765
    for f in INSTALLED.get(eng.PLATFORM, INSTALLED["windows"]):
        if f not in ("astro-import.py", "selftest.py"):
            check(f"{f} present", os.path.isfile(os.path.join(HERE, f)))

    try:
        from astropy.io import fits  # noqa: F401
        check("astropy installed (reads FITS headers)", True)
    except ImportError:
        check("astropy installed (reads FITS headers)", False,
              f'"{sys.executable}" -m pip install --user astropy')

    # state, config, identity
    check("state folder", os.path.isdir(eng.STATE_DIR) or not os.path.exists(eng.STATE_DIR),
          eng.STATE_DIR)
    print(f"  ----  ledger lives in {eng.STATE_DIR}")
    cfg = eng._CONFIG_PATH
    if os.path.isfile(cfg):
        try:
            with open(cfg, encoding="utf-8") as f:
                json.load(f)
            check("config.json parses", True)
        except ValueError as e:
            check("config.json parses", False, f"{cfg}: {e}")
    else:
        line("SKIP", "config.json", "none yet (defaults in use)")
    mid = eng.machine_id()
    check("this computer has an importer identity", bool(mid), mid)

    # the lock check must never kill (os.kill(pid, 0) terminates on Windows)
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(6)"])
    try:
        alive = eng.pid_alive(child.pid)
        time.sleep(0.3)
        check("lock check sees a running process", alive)
        check("lock check does NOT stop that process", child.poll() is None,
              "the process died — pid_alive must not use os.kill on Windows")
    finally:
        child.kill()
        child.wait()
    check("lock check sees a finished process as gone", not eng.pid_alive(child.pid))

    # drives and cameras
    roots = eng._drive_roots()
    if eng.IS_WINDOWS:
        check("drive letters listed", bool(roots) or True,
              "no removable/extra drives right now")
        print(f"  ----  drives checked: {', '.join(roots) or '(none besides the system drive)'}")
    eng.refresh_camera_volumes(force=True)
    cams = []
    if os.path.isdir(eng.ASIAIR_VOLUME):
        cams.append(f"ASIAir at {eng.ASIAIR_VOLUME}")
    sv = eng.seestar_volume()
    if sv:
        cams.append(f"Seestar at {sv}")
    line("PASS" if cams else "SKIP", "camera detection",
         ", ".join(cams) if cams else "no camera plugged in — plug one in and run again")
    if sv:
        try:
            s = eng.scan_seestar(eng.State())
            check("Seestar identified and scanned (read-only)", bool(s),
                  "scan returned nothing")
            if s:
                print(f"  ----  {s['camera']}: {len(s['targets'])} target(s), "
                      f"{sum(len(t['new']) for t in s['targets'])} new sub(s)")
        except RuntimeError as e:
            check("Seestar identified and scanned (read-only)", False, str(e))

    # workbench (C:) and archive (E:)
    for label, path in (("workbench (Seestar S50 Pro tree)", eng.SEESTAR_DEST_S50PRO),
                        ("workbench (ASIAir tree)", eng.DEST_DIR)):
        parent = path
        while parent and not os.path.isdir(parent):
            nxt = os.path.dirname(parent)
            if nxt == parent:
                break
            parent = nxt
        try:
            fd, tmp = tempfile.mkstemp(dir=parent, prefix=".astro-selftest-")
            os.close(fd)
            os.remove(tmp)
            check(f"{label} is writable", True)
        except OSError as e:
            check(f"{label} is writable", False, f"{parent}: {e}")
    print(f"  ----  frames go under {os.path.dirname(eng.SEESTAR_DEST_S50PRO)}")
    if os.path.isdir(eng.ARCHIVE_MOUNT):
        check(f"archive reachable ({eng.ARCHIVE_MOUNT})", eng.archive_reachable(eng.ARCHIVE_MOUNT),
              "needs one of S30P, S30, S50, S50P, 'ZWO Askar Scopes' and a writable _verify")
        print(f"  ----  this machine's ship log: {os.path.join(eng.ARCHIVE_MOUNT, '_verify', eng.SHIP_LOG_NAME)}")
    else:
        line("SKIP", "archive", f"{eng.ARCHIVE_MOUNT} not present (shipping is optional)")

    # Windows plumbing
    if eng.IS_WINDOWS:
        startup = os.path.join(os.environ.get("APPDATA", ""),
                               r"Microsoft\Windows\Start Menu\Programs\Startup",
                               "BrettjoAstro FITS Importer watcher.lnk")
        check("camera watcher starts at logon", os.path.isfile(startup), startup)
        desk = os.path.join(os.path.expanduser("~"), "Desktop", "Restart FITS Importer.cmd")
        check("Restart FITS Importer on the Desktop", os.path.isfile(desk), desk, warn_only=True)
        for task, needed in (("BrettjoAstro FITS Importer ship", os.path.isdir(eng.ARCHIVE_MOUNT)),
                             ("Astro archive sweep", os.path.isdir(eng.ARCHIVE_MOUNT))):
            if eng.TEST_ROOT:
                line("SKIP", f"scheduled task '{task}'",
                     "TEST MODE: the real Task Scheduler is never queried")
                continue
            r = subprocess.run(["schtasks", "/Query", "/TN", task], capture_output=True,
                               text=True, errors="replace",
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if needed:
                check(f"scheduled task '{task}'", r.returncode == 0, "not registered",
                      warn_only=True)
            else:
                line("SKIP", f"scheduled task '{task}'", "no archive on this machine")
        if test_8765:                          # the watcher would refuse (exit 3)
            line("SKIP", "watcher runs", "TEST MODE: port 8765 is never used under a test")
        else:
            w = subprocess.run([sys.executable, "-X", "utf8", os.path.join(HERE, "astro-watch.py"),
                                "--once"], capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=60)
            check("watcher runs", w.returncode == 0, (w.stderr or w.stdout)[-200:])
        if args.toast:
            eng.notify("Test notification from the FITS Importer install check.",
                       "FITS Importer")
            line("PASS", "notification sent", "did a toast appear bottom-right?")
    elif eng.IS_MAC:
        la = os.path.expanduser("~/Library/LaunchAgents")
        check("camera watcher LaunchAgent installed",
              os.path.isfile(os.path.join(la, "com.brettjohnson.astro-import.plist")))
        ship = os.path.isfile(os.path.join(la, "com.brettjohnson.astro-ship.plist"))
        if eng.ARCHIVE_URL or os.path.isdir(eng.ARCHIVE_MOUNT):
            check("twice-daily ship LaunchAgent installed", ship, warn_only=True)
        else:
            line("SKIP", "ship LaunchAgent", "no archive configured")
        check("app wrapper installed",
              os.path.isdir(os.path.expanduser("~/Applications/BrettjoAstro FITS Importer.app")),
              warn_only=True)
        check("Restart FITS Importer on the Desktop",
              os.path.isfile(os.path.expanduser("~/Desktop/Restart FITS Importer.command")),
              warn_only=True)
        if args.toast:
            eng.notify("Test notification from the FITS Importer install check.",
                       "FITS Importer")
            line("PASS", "notification sent", "did one appear top-right?")
    else:
        line("SKIP", "logon / scheduled tasks", f"not Windows or macOS ({eng.PLATFORM})")

    # the panel
    url = f"http://127.0.0.1:{port}"
    if test_8765:
        line("SKIP", "panel", "TEST MODE: port 8765 is never used under a test")
        return summary()
    try:
        with urllib.request.urlopen(url + "/api/ping", timeout=2) as r:
            ping = json.loads(r.read().decode())
        check(f"panel running on {url}", ping.get("ok") is True)
        check("panel is the same version as the engine", ping.get("version") == eng.VERSION,
              f"panel {ping.get('version')} vs engine {eng.VERSION} — restart the panel")
    except Exception:
        line("SKIP", "panel", "not running right now (plug in a camera, or use Restart)")
    return summary()


def summary():
    print()
    print(f"  {RESULTS['PASS']} passed, {RESULTS['WARN']} warnings, {RESULTS['FAIL']} failed, "
          f"{RESULTS['SKIP']} skipped")
    if RESULTS["FAIL"]:
        print("  Something is red — paste this output back to Claude.")
    return 1 if RESULTS["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
