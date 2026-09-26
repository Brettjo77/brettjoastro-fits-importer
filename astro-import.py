#!/usr/bin/env python3
"""
ZWO ASIAir 585MC Air -> Mac Import Script  —  v2 "Backup-First"
==============================================================================
Spec: ASIAir_Import_V2_Spec.md rev 5 (2026-07-25).

Core change from v1: import state lives in a central local ledger
(~/Library/Application Support/ASIAir Import/), independent of where imported
files are later archived. The camera's 256 GB is Brett's backup of record —
this script NEVER offers to delete from the camera.

Modes:
  (default)              interactive import of all new targets
  --targets NAME ...     import only these targets (camera folder names)
  --pick                 session picker dialog, then import ticked targets
  --menu                 Report / Verify / Never-Import / Dry Run menu
  --scan-only            watcher support: 3 plain lines (count/summary/storage)
  --report               safe-to-clear / backup status report
  --reconcile            one-time upgrade of baseline/merged entries
  --verify [--deep]      re-verify un-archived imports
  --baseline             mark everything on camera as imported (no copying)
  --unbaseline NAME      undo baseline for one target
  --restore-ledger       restore local state from the iCloud mirror
  --skip-target NAME / --unskip-target NAME
  --explain-cal          calibration candidate table
  --loose-cal            v1-style calibration matching for this run
  --no-checksum          size-only verification at import
  --dry-run --verbose --all

Runs on macOS and Windows 11 from this one file — same version, same
capabilities (see PARITY.md). Requires: Python 3.9+ and astropy.
==============================================================================
"""

import argparse
import contextlib
import hashlib
import json
import math
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import uuid
import time
from collections import defaultdict
from datetime import datetime, timedelta

# One version for every platform (1.5.0: the Windows 11 edition joins the Mac).
VERSION = "1.5.3"
IS_WINDOWS = os.name == "nt"
IS_MAC = sys.platform == "darwin"
PLATFORM = "windows" if IS_WINDOWS else ("mac" if IS_MAC else "linux")

# ── Lazy astropy ─────────────────────────────────────────────────────────────
_fits = None

def get_fits():
    global _fits
    if _fits is None:
        try:
            from astropy.io import fits as _f
            _fits = _f
        except ImportError:
            # name the interpreter that is actually running (the old hint
            # named Apple's python even when python.org's was in use)
            error("astropy not installed for this Python. Run:")
            if IS_WINDOWS:
                error(f'  "{sys.executable}" -m pip install --user astropy')
            else:
                error(f"  {sys.executable} -m pip install astropy"
                      + (" --break-system-packages" if sys.executable.startswith("/usr/bin/") else ""))
            sys.exit(1)
    return _fits


# ═══════════════════════════════════════════════════════════════════════════
# CONFIG (env-overridable so the test harness can redirect everything)
# ═══════════════════════════════════════════════════════════════════════════

# Test mode (1.5.2). ASTRO_TEST_ROOT=<folder> marks a test run, and the engine
# then fails closed: every default is re-rooted under that folder (with a fake
# home, so every "~" lands there too), any configured path outside it stops
# the run before anything is read or written (exit 3, "TEST MODE: ..."),
# cameras are only ever ASTRO_DRIVE_ROOTS entries (never /Volumes or real
# drive letters), and every OS side effect (dialogs, notifications, Finder
# labels, ejects, mounts, "open", PowerShell) is recorded in
# <root>/os-calls.jsonl instead of performed. Unset, nothing changes.
# Why: the 1.5.1 suites, run on the real Mac, shipped fake frames into the
# real archive and moved a real iCloud folder (25 Sep 2026).

def _test_refuse(msg):
    print(f"TEST MODE: {msg}", file=sys.stderr)
    sys.exit(3)

def _within(path, root):
    """Is `path` the folder `root` or inside it? Both resolved (links, 8.3
    names; case-insensitive on Windows); another drive is outside."""
    p = os.path.normcase(os.path.realpath(path))
    r = os.path.normcase(os.path.realpath(root))
    try:
        return os.path.commonpath([p, r]) == r
    except ValueError:
        return False

TEST_ROOT = os.environ.get("ASTRO_TEST_ROOT")
if TEST_ROOT is None:
    TEST_ROOT = ""
else:
    if not TEST_ROOT or not os.path.isdir(TEST_ROOT):
        _test_refuse(f"ASTRO_TEST_ROOT is not an existing folder: '{TEST_ROOT}'")
    TEST_ROOT = os.path.realpath(TEST_ROOT)
    # a fake home inside the root (child processes inherit it)
    _home = os.path.join(TEST_ROOT, "home")
    for _k, _v in (("HOME", _home), ("USERPROFILE", _home),
                   ("LOCALAPPDATA", os.path.join(_home, "AppData", "Local")),
                   ("APPDATA", os.path.join(_home, "AppData", "Roaming"))):
        if not (os.environ.get(_k) and _within(os.environ[_k], TEST_ROOT)):
            os.environ[_k] = _v
    for _k in ("OneDrive", "HOMEDRIVE", "HOMEPATH"):
        os.environ.pop(_k, None)          # so ntpath.expanduser uses USERPROFILE
    os.makedirs(os.path.expanduser("~"), exist_ok=True)

def _test_record(kind, **info):
    """Test mode: note an OS side effect in <root>/os-calls.jsonl instead of
    performing it. Never raises."""
    if not TEST_ROOT:
        return
    try:
        rec = {"kind": kind, "at": datetime.now().isoformat(timespec="seconds"), **info}
        with open(os.path.join(TEST_ROOT, "os-calls.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, default=str) + "\n")
    except Exception:
        pass

def _confine(path, what):
    """Test mode: stop before `what` touches `path` outside the root — for
    paths that come from the ledger or the camera, not from config."""
    if TEST_ROOT and not _within(path, TEST_ROOT):
        _test_refuse(f"{what} would touch {path}, outside the test root {TEST_ROOT}")

def _test_root_guard():
    """Test mode: every configured path must lie inside the root, or the run
    stops here, before anything is read or written. Called once, after the
    last path constant below."""
    if not TEST_ROOT:
        return
    paths = [("ASIAIR_CONFIG", _CONFIG_PATH), ("ASIAIR_VOLUME", ASIAIR_VOLUME),
             ("ASIAIR_DEST", DEST_DIR), ("ASIAIR_CAL_LIBRARY", LIBRARY_DIR),
             ("ASIAIR_STATE", STATE_DIR), ("ASIAIR_MIRROR", MIRROR_DIR),
             ("ASTRO_ARCHIVE_MOUNT", ARCHIVE_MOUNT),
             ("ASTRO_SHIP_LOG", os.path.join(ARCHIVE_MOUNT, "_verify", SHIP_LOG_NAME)),
             ("SEESTAR_DEST_S30", SEESTAR_DEST_S30), ("SEESTAR_DEST_S50", SEESTAR_DEST_S50),
             ("SEESTAR_DEST_S30_ORIG", SEESTAR_DEST_S30_ORIG),
             ("SEESTAR_DEST_S50PRO", SEESTAR_DEST_S50PRO),
             ("ASIAIR_EQUIPMENT", EQUIPMENT_JSON), ("ASIAIR_RECEIPTS", RECEIPT_BASE),
             ("ASIAIR_LEGACY_NAMES", LEGACY_CUSTOM_NAMES)]
    paths += [("SEESTAR_VOLUME", v) for v in SEESTAR_VOLUMES]
    paths += [("ASTRO_DRIVE_ROOTS", r)
              for r in (os.environ.get("ASTRO_DRIVE_ROOTS") or "").split(os.pathsep)]
    paths += [(k, os.environ.get(k)) for k in ("ASTRO_WATCH_LOG", "ASTRO_WATCH_STATE")]
    for var, p in paths:
        if p and not _within(p, TEST_ROOT):
            _test_refuse(f"{var} is outside the test root {TEST_ROOT}: {p}")

# Precedence: environment variable > config.json > generic default.
# config.json lives next to the ledger (~/Library/Application Support/
# Astro Import/config.json) and lets any user relocate destinations without
# touching this script — see config.example.json in the repo.
# Per-platform homes for state (the ledger) — the only default that differs
# by OS besides where cameras and the archive appear (PARITY.md).
if IS_WINDOWS:
    _DEF_STATE = os.path.join(os.environ.get("LOCALAPPDATA")
                              or os.path.expanduser("~/AppData/Local"), "Astro Import")
else:
    _DEF_STATE = "~/Library/Application Support/Astro Import"
_CONFIG_PATH = os.path.expanduser(os.environ.get(
    "ASIAIR_CONFIG", os.path.join(_DEF_STATE, "config.json")))
if TEST_ROOT and _CONFIG_PATH and not _within(_CONFIG_PATH, TEST_ROOT):
    _test_refuse(f"ASIAIR_CONFIG is outside the test root {TEST_ROOT}: {_CONFIG_PATH}")
try:
    with open(_CONFIG_PATH) as _cf:
        _CONFIG = json.load(_cf)
    if not isinstance(_CONFIG, dict):
        _CONFIG = {}
except (OSError, ValueError):
    _CONFIG = {}

def _env_path(var, default):
    value = os.environ.get(var) or _CONFIG.get(var)
    if not value and TEST_ROOT and not _within(os.path.expanduser(default), TEST_ROOT):
        value = os.path.join(TEST_ROOT, "unset", var)   # never a real default
    return os.path.expanduser(value or default)

# On Windows cameras arrive as drive letters, found by what is ON them
# (Autorun\ = ASIAir, MyWorks\ = Seestar) — see refresh_camera_volumes().
ASIAIR_VOLUME_FIXED = bool(os.environ.get("ASIAIR_VOLUME") or _CONFIG.get("ASIAIR_VOLUME"))
ASIAIR_VOLUME = _env_path("ASIAIR_VOLUME", "/Volumes/ASIAIR" if not IS_WINDOWS
                          else os.path.join(_DEF_STATE, "no ASIAir drive connected"))
DEST_DIR      = _env_path("ASIAIR_DEST", "~/Documents/Astro/ZWO ASI AIR")
LIBRARY_DIR   = _env_path("ASIAIR_CAL_LIBRARY", "~/Documents/Astro/ASIAir Calibration Library")
STATE_DIR     = _env_path("ASIAIR_STATE", _DEF_STATE)
MIRROR_DIR    = _env_path("ASIAIR_MIRROR", "~/Documents/Astro/Import Status")
# The archive on the PC, as mounted on this Mac (SMB share). --ship files
# verified frames there; the PC's sweep verifies them independently.
# On Windows the archive is a local folder (the PC IS the archive machine:
# E: is the archive, C: the processing workbench — Brett, 24 Sep 2026).
ARCHIVE_MOUNT = _env_path("ASTRO_ARCHIVE_MOUNT", "E:\\Astro Image Data" if IS_WINDOWS
                          else "/Volumes/AstroImageData")
ARCHIVE_LABEL = os.environ.get("ASTRO_ARCHIVE_LABEL") or _CONFIG.get("ASTRO_ARCHIVE_LABEL") \
    or (ARCHIVE_MOUNT if TEST_ROOT else "E:\\Astro Image Data")
# smb:// URL of the share; when set, --ship asks Finder to mount it on demand
# (the keychain supplies the password after the first "remember" connection),
# so no permanent connection is needed.
ARCHIVE_URL = os.environ.get("ASTRO_ARCHIVE_URL") or _CONFIG.get("ASTRO_ARCHIVE_URL") or ""
# Each machine writes its OWN ship log; the PC's sweep reads every
# shipped*.jsonl. No file on the archive is ever appended to by two machines.
SHIP_LOG_NAME = os.environ.get("ASTRO_SHIP_LOG") or _CONFIG.get("ASTRO_SHIP_LOG") \
    or ("shipped-pc.jsonl" if IS_WINDOWS else "shipped.jsonl")

# ── Seestar (S30 Pro / S50) ─────────────────────────────────────────────────
SEESTAR_VOLUME_ENV = os.environ.get("SEESTAR_VOLUME") or _CONFIG.get("SEESTAR_VOLUME")
SEESTAR_VOLUMES = ([SEESTAR_VOLUME_ENV] if SEESTAR_VOLUME_ENV
                   else ([] if IS_WINDOWS or TEST_ROOT
                         else ["/Volumes/Seestar", "/Volumes/SEESTAR"]))
SEESTAR_DEST_S30 = _env_path("SEESTAR_DEST_S30", "~/Documents/Astro/Seestar S30 Pro")
SEESTAR_DEST_S50 = _env_path("SEESTAR_DEST_S50", "~/Documents/Astro/Seestar S50")
# The ORIGINAL (non-Pro) S30 gets its own tree — two different optical
# systems must never interleave in one folder (Brett's second Seestar, 2026-08-18)
SEESTAR_DEST_S30_ORIG = _env_path("SEESTAR_DEST_S30_ORIG",
                                  "~/Documents/Astro/Seestar S30")
# The S50 Pro (dual-camera 4K, 2026-09) likewise gets its own tree —
# "S50" and "S50 Pro" are different optical systems and never interleave
SEESTAR_DEST_S50PRO = _env_path("SEESTAR_DEST_S50PRO",
                                "~/Documents/Astro/Seestar S50 Pro")
# ═══════════════════════════════════════════════════════════════════════════
# PLATFORM LAYER — everything that differs between macOS and Windows lives
# here, so the rest of the engine is one codebase (PARITY.md). 1.5.0.
# ═══════════════════════════════════════════════════════════════════════════

def _prefix(p):
    """A directory path with exactly one trailing separator — safe for
    startswith() containment checks even on a drive root ("F:\\")."""
    return p if p.endswith(("/", "\\")) else p + os.sep

def _rel(path, root):
    """Camera-relative path as the ledger stores it: always "/"-separated,
    so a Mac ledger and a Windows ledger describe a card the same way."""
    return os.path.relpath(path, root).replace("\\", "/")

_WIN_ERRMODE_SET = False

def _drive_roots():
    """Candidate camera drives: ASTRO_DRIVE_ROOTS (tests, or to pin drives
    by hand), else on Windows every removable or fixed drive letter except
    the system drive. Empty elsewhere (the Mac uses /Volumes) and in test
    mode (never a real drive letter)."""
    env = os.environ.get("ASTRO_DRIVE_ROOTS")
    if env is not None:
        return [p for p in env.split(os.pathsep) if p]
    if not IS_WINDOWS or TEST_ROOT:
        return []
    global _WIN_ERRMODE_SET
    roots = []
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        if not _WIN_ERRMODE_SET:
            # never let an empty card reader pop "Insert a disk" dialogs
            # (OR into the existing mode rather than replacing it)
            old = k32.SetErrorMode(0x0001 | 0x8000)
            k32.SetErrorMode(old | 0x0001 | 0x8000)
            _WIN_ERRMODE_SET = True
        mask = k32.GetLogicalDrives()
        system = (os.environ.get("SystemDrive") or "C:").upper().rstrip("\\")
        # drives that hold this tool's own folders (the archive on E:, the
        # workbench, the ledger) are never cameras, whatever is on them
        ours = {os.path.splitdrive(os.path.abspath(p))[0].upper()
                for p in (ARCHIVE_MOUNT, DEST_DIR, STATE_DIR, MIRROR_DIR, LIBRARY_DIR)
                if p}
        for i in range(26):
            if not mask & (1 << i):
                continue
            letter = chr(65 + i) + ":"
            if letter.upper() == system:
                continue
            root = letter + "\\"
            kind = k32.GetDriveTypeW(ctypes.c_wchar_p(root))
            if kind == 2:                                    # removable: a camera or card
                roots.append(root)
            elif kind == 3 and letter.upper() not in ours \
                    and not os.path.isdir(os.path.join(root, "Windows")) \
                    and not os.path.isdir(os.path.join(root, "Users")):
                roots.append(root)       # a USB camera that reports itself as a fixed disk
    except Exception:
        pass
    return roots

_VOL_CACHE = {"t": 0.0}

def refresh_camera_volumes(force=False):
    """Windows: find the ASIAir by its Autorun folder on any drive letter
    (drives come and go while the panel runs, so this is re-checked, at most
    every 1.5 s). A configured ASIAIR_VOLUME always wins; on the Mac the
    fixed /Volumes/ASIAIR path is used and this does nothing."""
    global ASIAIR_VOLUME
    if ASIAIR_VOLUME_FIXED:
        return
    if not IS_WINDOWS and os.environ.get("ASTRO_DRIVE_ROOTS") is None:
        return
    now = time.time()
    if not force and now - _VOL_CACHE["t"] < 1.5:
        return
    _VOL_CACHE["t"] = now
    for root in _drive_roots():
        if os.path.isdir(os.path.join(root, "Autorun")) \
                and not os.path.isdir(os.path.join(root, "MyWorks")):
            ASIAIR_VOLUME = root
            return
    ASIAIR_VOLUME = os.path.join(STATE_DIR, "no ASIAir drive connected")

def pid_alive(pid):
    """Is process `pid` running? On Windows os.kill(pid, 0) does NOT test —
    it TERMINATES the process — so the lock check must never use it there."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if IS_WINDOWS:
        try:
            import ctypes
            from ctypes import wintypes
            k32 = ctypes.WinDLL("kernel32", use_last_error=True)
            k32.OpenProcess.restype = wintypes.HANDLE
            k32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
            k32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
            k32.CloseHandle.argtypes = (wintypes.HANDLE,)
            h = k32.OpenProcess(0x1000, False, pid)        # QUERY_LIMITED_INFORMATION
            if not h:
                return ctypes.get_last_error() == 5          # access denied = it exists
            code = wintypes.DWORD()
            ok = k32.GetExitCodeProcess(h, ctypes.byref(code))
            k32.CloseHandle(h)
            return bool(ok) and code.value == 259            # STILL_ACTIVE
        except Exception:
            return True                                      # unsure: keep the lock
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True

def _powershell(script, env_extra=None, timeout=20):
    """Run a PowerShell snippet with data passed ONLY through environment
    variables (never spliced into the script), so no name can inject code."""
    if TEST_ROOT:
        _test_record("powershell", script=script.strip()[:200])
        return subprocess.CompletedProcess(["powershell.exe"], 1, b"", b"test mode: not run")
    env = dict(os.environ)
    env.update(env_extra or {})
    return subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive",
                           "-ExecutionPolicy", "Bypass", "-Command", script],
                          env=env, capture_output=True, timeout=timeout,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

_WIN_TOAST = r"""
$ErrorActionPreference = 'Stop'
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
$t = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$x = $t.GetElementsByTagName('text')
$x.Item(0).AppendChild($t.CreateTextNode($env:ASTRO_TOAST_TITLE)) > $null
$x.Item(1).AppendChild($t.CreateTextNode($env:ASTRO_TOAST_MSG)) > $null
$n = [Windows.UI.Notifications.ToastNotification]::new($t)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe').Show($n)
"""

_WIN_EJECT = r"""
$d = $env:ASTRO_EJECT_DRIVE
(New-Object -ComObject Shell.Application).Namespace(17).ParseName($d).InvokeVerb('Eject')
"""

def eject_volume(vol):
    """Safely eject a camera drive. True when it is gone afterwards."""
    if TEST_ROOT:
        _test_record("eject", vol=vol)
        return False
    try:
        if IS_MAC:
            return subprocess.run(["diskutil", "eject", vol], capture_output=True,
                                  text=True, timeout=60).returncode == 0
        if IS_WINDOWS:
            drive = os.path.splitdrive(os.path.abspath(vol))[0]     # "F:"
            _powershell(_WIN_EJECT, {"ASTRO_EJECT_DRIVE": drive}, timeout=30)
            for _ in range(20):
                if not os.path.isdir(vol):
                    return True
                time.sleep(0.5)
            return False
    except Exception:
        return False
    return False

def open_path(target):
    """Open a file or URL with the system's default app."""
    if TEST_ROOT:
        _test_record("open", target=target)
        return
    try:
        if IS_WINDOWS:
            os.startfile(target)            # noqa: platform-specific
        elif IS_MAC:
            subprocess.run(["open", target], capture_output=True, timeout=10)
        else:
            subprocess.run(["xdg-open", target], capture_output=True, timeout=10)
    except Exception:
        pass

def machine_id():
    """A stable id for THIS computer's importer (created once, kept in the
    state folder). Hostnames drift on a Mac; this doesn't."""
    p = os.path.join(STATE_DIR, "machine.json")
    try:
        with open(p) as f:
            return json.load(f)["id"]
    except (OSError, ValueError, KeyError, TypeError):
        pass
    rec = {"id": uuid.uuid4().hex, "platform": PLATFORM,
           "host": socket.gethostname(), "created": datetime.now().isoformat(timespec="seconds")}
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(p, "w") as f:
            json.dump(rec, f, indent=1)
    except OSError:
        pass
    return rec["id"]

def mirror_owner_ok(mirror_dir, claim=False):
    """Each machine publishes to its OWN mirror folder. Two ledgers in one
    folder would overwrite each other (the per-machine rule, 17 Sep 2026).
    Returns (ok, owner_record)."""
    p = os.path.join(mirror_dir, "mirror-owner.json")
    mine = machine_id()
    try:
        with open(p) as f:
            rec = json.load(f)
    except (OSError, ValueError):
        rec = None
    if rec and rec.get("id") and rec["id"] != mine:
        return False, rec
    if claim and not rec:
        try:
            os.makedirs(mirror_dir, exist_ok=True)
            with open(p, "w") as f:
                json.dump({"id": mine, "platform": PLATFORM, "host": socket.gethostname(),
                           "claimed": datetime.now().isoformat(timespec="seconds")}, f, indent=1)
        except OSError:
            pass
    return True, rec

def lock_clear_hint(path):
    return (f'  del "{path}"' if IS_WINDOWS else f"  rm '{path}'")


def _env_flag(var, default=False):
    """Boolean setting: environment variable > config.json > default."""
    v = os.environ.get(var)
    if v is None:
        v = _CONFIG.get(var)
    if v is None:
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "on")

def panel_port():
    """The panel's port: ASTRO_PANEL_PORT, else 8765 (as is a value that
    isn't a number: a typo must never stop the panel or the install check)."""
    try:
        return int(os.environ.get("ASTRO_PANEL_PORT") or 8765)
    except ValueError:
        return 8765

# Per-sub JPEG previews (the S50 Pro writes one beside every sub). OFF by
# default since 1.4.2 (Brett, 12 + 24 Sep 2026: "don't want JPGs imported").
# When off they are neither imported nor shipped, and the SAFE gate treats a
# preview whose FIT twin is proven as not-data. Set to 1 to restore riders.
SEESTAR_IMPORT_SUB_JPEGS = _env_flag("SEESTAR_IMPORT_SUB_JPEGS", False)
MW_PAIR_TOLERANCE = 7200          # s — MW session pairs to the simultaneous DSO
SEESTAR_S50_ONLY_MODES = ["Solar_photo", "Solar_video", "Planetary_photo",
                          "Planetary_video", "Scenery_photo"]
SEESTAR_NON_DSO_MAP = [("Lunar_photo", "Lunar"), ("Solar_photo", "Solar"),
                       ("Planetary_photo", "Planetary"), ("Scenery_photo", "Scenery"),
                       ("Lunar_video", "Lunar Video"), ("Solar_video", "Solar Video"),
                       ("Planetary_video", "Planetary Video")]
SEESTAR_CATALOG_RE = re.compile(
    r"^(HIP \d+|NGC \d+|IC \d+|M \d+|C \d+|Sh2-\d+|GAIA \d+)")
SEESTAR_HIP_REMAP = {"HIP 24727": "IC 405"}   # goto star → proper catalogue ID
STAMP_RE = re.compile(r"\d{8}-\d{6}")
EQUIPMENT_JSON = _env_path("ASIAIR_EQUIPMENT", "~/Documents/Astro/equipment.json")
RECEIPT_BASE  = _env_path("ASIAIR_RECEIPTS", "~/Documents/Astro/astrolog-receipts")
LEGACY_CUSTOM_NAMES = _env_path("ASIAIR_LEGACY_NAMES", "~/.asiair-custom-names.json")
_test_root_guard()

# One-time migration from the pre-unification state locations (spec §1).
# Never in test mode, and never into a folder an environment variable points
# at: that is a test or a one-off run, not the old folder's heir (1.5.2 — a
# test's temp mirror swallowed the real iCloud folder). config.json still counts.
for _old, _new, _var in [
    (os.path.expanduser("~/Library/Application Support/ASIAir Import"), STATE_DIR, "ASIAIR_STATE"),
    (os.path.expanduser("~/Library/Mobile Documents/com~apple~CloudDocs/Astro Tools/ASIAir Import"),
     MIRROR_DIR, "ASIAIR_MIRROR"),
]:
    try:
        if not TEST_ROOT and not os.environ.get(_var) \
                and os.path.isdir(_old) and not os.path.isdir(_new):
            shutil.move(_old, _new)
            os.makedirs(_old, exist_ok=True)   # breadcrumb for anything bookmarked
            with open(os.path.join(_old, "MOVED.txt"), "w") as _f:
                _f.write("This folder moved to:\n  %s\n"
                         "(ASIAir + Seestar imports were unified into 'Astro Import', "
                         "2026-07-25)\n" % _new)
    except OSError:
        pass

CAMERA_NAME = "ZWO ASI585MC Air"
SOURCE_SUBDIRS = ["Live/Light", "Plan/Light"]
AUTORUN_DIR = "Autorun"

# Matching constants (spec §4b)
DARK_TEMP_TOLERANCE = 10.0        # °C
EXPOSURE_TOLERANCE = 0.5          # s (darks)
FOCALLEN_TOLERANCE = 10           # mm
ROTATION_TOLERANCE = 5.0          # deg, wraparound-aware
FLAT_WINDOW_DAYS = 30
DARKBIAS_WINDOW_DAYS = 365
FLAT_STALENESS_WARN_DAYS = 7
CAL_GATES_PROBATION = True        # flats FOCALLEN/rotation gates warn, don't reject
NIGHT_PIVOT_HOURS = 12            # noon-to-noon observing night

LEDGER_VERSION = 1
HISTORY_VERSION = 1

SCOPE_LOOKUP = {402: "Askar FRA400", 749: "Askar 107PHQ"}

# ── DSO Name Lookup ──────────────────────────────────────────────────────────
DSO_NAMES = {
    "M 1": "Crab Nebula", "M 8": "Lagoon Nebula", "M 13": "Great Globular Cluster",
    "M 16": "Eagle Nebula", "M 17": "Omega Nebula", "M 20": "Trifid Nebula",
    "M 27": "Dumbbell Nebula", "M 31": "Andromeda Galaxy", "M 33": "Triangulum Galaxy",
    "M 42": "Orion Nebula", "M 43": "De Mairan's Nebula", "M 44": "Beehive Cluster",
    "M 45": "Pleiades", "M 51": "Whirlpool Galaxy", "M 57": "Ring Nebula",
    "M 63": "Sunflower Galaxy", "M 64": "Black Eye Galaxy", "M 76": "Little Dumbbell Nebula",
    "M 78": "Reflection Nebula", "M 81": "Bode's Galaxy", "M 82": "Cigar Galaxy",
    "M 83": "Southern Pinwheel Galaxy", "M 87": "Virgo A", "M 94": "Cat's Eye Galaxy",
    "M 97": "Owl Nebula", "M 101": "Pinwheel Galaxy", "M 104": "Sombrero Galaxy",
    "M 106": "Spiral Galaxy", "M 110": "Satellite of Andromeda",
    "NGC 224": "Andromeda Galaxy", "NGC 253": "Sculptor Galaxy", "NGC 281": "Pacman Nebula",
    "NGC 457": "Owl Cluster", "NGC 869": "Double Cluster (h)", "NGC 884": "Double Cluster (chi)",
    "NGC 1333": "Reflection Nebula", "NGC 1499": "California Nebula", "NGC 1952": "Crab Nebula",
    "NGC 1977": "Running Man Nebula", "NGC 2024": "Flame Nebula", "NGC 2070": "Tarantula Nebula",
    "NGC 2174": "Monkey Head Nebula", "NGC 2237": "Rosette Nebula", "NGC 2238": "Rosette Nebula",
    "NGC 2239": "Rosette Nebula", "NGC 2244": "Rosette Nebula", "NGC 2264": "Cone Nebula",
    "NGC 2359": "Thor's Helmet", "NGC 2392": "Eskimo Nebula", "NGC 2403": "Spiral Galaxy",
    "NGC 2736": "Pencil Nebula", "NGC 2841": "Tiger's Eye Galaxy", "NGC 3372": "Carina Nebula",
    "NGC 3628": "Hamburger Galaxy", "NGC 4565": "Needle Galaxy", "NGC 4631": "Whale Galaxy",
    "NGC 4656": "Hockey Stick Galaxy", "NGC 5128": "Centaurus A", "NGC 5139": "Omega Centauri",
    "NGC 5907": "Splinter Galaxy", "NGC 6334": "Cat's Paw Nebula", "NGC 6357": "Lobster Nebula",
    "NGC 6369": "Little Ghost Nebula", "NGC 6503": "Lost-in-Space Galaxy",
    "NGC 6543": "Cat's Eye Nebula", "NGC 6559": "Emission Nebula",
    "NGC 6572": "Emerald Eye Nebula", "NGC 6618": "Omega Nebula", "NGC 6720": "Ring Nebula",
    "NGC 6826": "Blinking Nebula", "NGC 6888": "Crescent Nebula",
    "NGC 6960": "Western Veil Nebula", "NGC 6979": "Pickering's Triangle",
    "NGC 6992": "Eastern Veil Nebula", "NGC 6995": "Eastern Veil Nebula",
    "NGC 7000": "North America Nebula", "NGC 7023": "Iris Nebula", "NGC 7293": "Helix Nebula",
    "NGC 7380": "Wizard Nebula", "NGC 7635": "Bubble Nebula", "NGC 7822": "Cederblad 214",
    "NGC 896": "Heart Nebula (part)",
    "IC 405": "Flaming Star Nebula", "IC 410": "Tadpole Nebula", "IC 434": "Horsehead Nebula",
    "IC 443": "Jellyfish Nebula", "IC 1318": "Sadr Region", "IC 1396": "Elephant's Trunk Nebula",
    "IC 1805": "Heart Nebula", "IC 1848": "Soul Nebula", "IC 2118": "Witch Head Nebula",
    "IC 2177": "Seagull Nebula", "IC 4604": "Rho Ophiuchi", "IC 5067": "Pelican Nebula",
    "IC 5070": "Pelican Nebula", "IC 5146": "Cocoon Nebula",
    "Sh2-129": "Flying Bat Nebula", "Sh2-132": "Lion Nebula", "Sh2-155": "Cave Nebula",
    "Sh2-171": "Phantom Nebula", "Sh2-240": "Simeis 147", "Sh2-261": "Lower's Nebula",
    "Barnard 33": "Horsehead Nebula", "LDN 1622": "Boogeyman Nebula",
    "vdB 142": "Elephant's Trunk",
    # Seestar-side names (merged from seestar-import.sh)
    "C 9": "Cave Nebula", "MilkyWay": "Milky Way Core",
    "GAIA 2192287033139966848": "Squid Nebula",
    "IC 1318A": "Sadr Region (A)",
}


# ═══════════════════════════════════════════════════════════════════════════
# UX
# ═══════════════════════════════════════════════════════════════════════════

VERBOSE = False

# ── App hooks (set by asiair-app.py; None = classic CLI behavior) ───────────
PROMPT_FN = None   # fn({kind:'confirm'|'text', prompt, default}) -> str | None
EVENT_FN = None    # fn({event: str, ...}) — structured progress for the panel
NOTIFY_FN = None   # fn(message, title) — the app shows notifications itself (1.5.3)

def emit(event, **fields):
    if EVENT_FN is not None:
        try:
            EVENT_FN({"event": event, **fields})
        except Exception:
            pass

def log(msg):     print(f"  {msg}")
def info(msg):    print(f"▸ {msg}")
def success(msg): print(f"✓ {msg}")
def warn(msg):    print(f"⚠ {msg}")
def error(msg):   print(f"✗ {msg}", file=sys.stderr)

def debug(msg):
    if VERBOSE:
        print(f"  [debug] {msg}")

def show_progress(current, total, label="Copying"):
    if total == 0:
        return
    width = 40
    percent = current * 100 // total
    filled = current * width // total
    bar = "█" * filled + "░" * (width - filled)
    end = "\n" if current == total else ""
    print(f"\r  {label} [{bar}] {current}/{total} ({percent}%)", end=end, flush=True)

def safe_input(prompt, default=""):
    """input() that survives non-interactive runs; routed to the panel in app mode."""
    if PROMPT_FN is not None:
        try:
            r = PROMPT_FN({"kind": "confirm", "prompt": prompt, "default": default})
            return default if r is None else str(r).strip()
        except Exception:
            return default
    if (sys.stdin is None or not sys.stdin.isatty()) and not os.environ.get("ASTRO_STDIN_PROMPTS"):
        # Piped/headless runs answer every prompt with its (safe) default.
        # ASTRO_STDIN_PROMPTS=1 opts into reading piped answers instead —
        # how the test suite exercises the real Yes paths (e.g. cleanup).
        return default
    try:
        return input(prompt).strip()
    except EOFError:
        return default

def human_size(n):
    if n >= 1024 ** 3:
        return f"{n / 1024**3:.1f} GB"
    if n >= 1024 ** 2:
        return f"{n / 1024**2:.0f} MB"
    return f"{n / 1024:.0f} KB"

def human_hours(seconds):
    return f"≈ {seconds / 3600:.1f} h"

def now_stamp():
    return datetime.now().strftime("%Y-%m-%dT%H%M%S")

def notify(message, title="FITS Importer", sound=False):
    """Desktop notification (macOS Notification Centre / Windows toast);
    silently logged if unavailable or not allowed. sound=True adds the
    panel's "Glass" chime on the Mac (a Windows toast brings its own)."""
    if NOTIFY_FN is not None:
        try:
            NOTIFY_FN(message, title)
        except Exception:
            pass
        return
    if TEST_ROOT:
        _test_record("notify", message=message, title=title, sound=sound)
        return
    if IS_WINDOWS:
        try:
            r = _powershell(_WIN_TOAST, {"ASTRO_TOAST_TITLE": title,
                                         "ASTRO_TOAST_MSG": message})
            if r.returncode != 0:
                debug(f"toast failed: {r.stderr.decode(errors='replace').strip()[:200]}")
        except Exception as e:
            debug(f"toast unavailable: {e}")
        return
    if not IS_MAC:
        return
    try:
        r = subprocess.run(
            ["osascript", "-e", 'on run argv',
             "-e", 'display notification (item 1 of argv) with title (item 2 of argv)'
             + (' sound name "Glass"' if sound else ""),
             "-e", "end run", "--", message, title],
            capture_output=True, timeout=10,
        )
        if r.returncode != 0:
            debug(f"notification failed: {r.stderr.decode(errors='replace').strip()}")
    except Exception as e:
        debug(f"notification unavailable: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# FILENAME PARSING (v1, validated against real ASIAir formats)
# ═══════════════════════════════════════════════════════════════════════════

CALIB_FILENAME_RE = re.compile(
    r"^(?P<frame_type>Bias|Dark|Flat)_"
    r"(?P<exposure>[\d.]+(?:ms|s))_"
    r"(?P<binning>Bin\d+)_"
    r"(?P<camera>\w+)_"
    r"(?P<gain>gain\d+)_"
    r"(?P<datetime>\d{8}-\d{6})_"
    r"(?P<rotation>[\d.]+deg)_"
    r"(?P<temp>-?[\d.]+C)_"
    r"(?:(?P<filter>[^_]+)_)?"
    r"(?P<seq>\d+)\.fit$",
    re.IGNORECASE,
)

LIGHT_FILENAME_RE = re.compile(
    r"^Light_.*?"
    r"(?P<exposure>[\d.]+(?:ms|s))_"
    r"(?P<binning>Bin\d+)_"
    r"(?P<camera>\w+)_"
    r"(?P<gain>gain\d+)_"
    r"(?P<datetime>\d{8}-\d{6})_"
    r"(?P<rotation>[\d.]+deg)_"
    r"(?P<temp>-?[\d.]+C)_"
    r"(?:(?P<filter>[^_]*)_)?"      # filter token absent entirely on no-filter targets
    r"(?P<seq>\d+)\.fit$",
    re.IGNORECASE,
)

def _parse_common(m):
    exposure_str = m.group("exposure")
    if exposure_str.lower().endswith("ms"):
        exposure_seconds = float(exposure_str[:-2]) / 1000.0
    else:
        exposure_seconds = float(exposure_str[:-1])
    sensor_temp = float(m.group("temp")[:-1])
    gain_str = m.group("gain")
    rotation = float(m.group("rotation")[:-3])
    try:
        capture_dt = datetime.strptime(m.group("datetime"), "%Y%m%d-%H%M%S")
    except ValueError:
        capture_dt = None
    return {
        "exposure_seconds": exposure_seconds,
        "binning": m.group("binning"),
        "camera": m.group("camera"),
        "gain": gain_str,
        "gain_value": int(gain_str.replace("gain", "")),
        "sensor_temp": sensor_temp,
        "rotation": rotation,
        "filter": (m.group("filter") or ""),
        "capture_datetime": capture_dt,
    }

def parse_calibration_filename(filename):
    m = CALIB_FILENAME_RE.match(filename)
    if not m:
        return None
    d = _parse_common(m)
    d["frame_type"] = m.group("frame_type").capitalize()
    d["filename"] = filename
    return d

def parse_light_filename(filename):
    m = LIGHT_FILENAME_RE.match(filename)
    if not m:
        return None
    d = _parse_common(m)
    d["filename"] = filename
    return d

def observing_night(dt):
    """Noon-to-noon night key. Timestamp source semantics verified in rollout."""
    if dt is None:
        return None
    return (dt - timedelta(hours=NIGHT_PIVOT_HOURS)).strftime("%Y-%m-%d")

def dominant_rotation(rotations):
    """Session rotation from many frames. ASIAir stamps 0deg on frames captured
    before the first plate-solve, then the solved angle (verified on real files
    2026-07-25: 0deg → 230deg → 231deg). Drop a lone pre-solve zero, then take
    the circular mean so wraparound (359°≈0°) behaves."""
    vals = [r % 360.0 for r in rotations if r is not None]
    if not vals:
        return None
    if len(vals) > 1:
        nonzero = [v for v in vals if v != 0.0]
        if nonzero:
            vals = nonzero
    x = sum(math.cos(math.radians(v)) for v in vals)
    y = sum(math.sin(math.radians(v)) for v in vals)
    if abs(x) < 1e-9 and abs(y) < 1e-9:
        return vals[0]
    return round(math.degrees(math.atan2(y, x)) % 360.0, 1)


# ═══════════════════════════════════════════════════════════════════════════
# FITS HELPERS
# ═══════════════════════════════════════════════════════════════════════════

_focallen_cache = {}

def read_fits_focallen(filepath):
    if filepath in _focallen_cache:
        return _focallen_cache[filepath]
    val = None
    try:
        header = get_fits().getheader(filepath)
        raw = header.get("FOCALLEN")
        if raw is not None:
            val = int(float(raw))
    except Exception:
        val = None
    _focallen_cache[filepath] = val
    return val

def read_fits_header_summary(filepath):
    """Key headers from a light frame (fallback when filename parsing fails)."""
    try:
        header = get_fits().getheader(filepath)
        focallen = header.get("FOCALLEN")
        result = {
            "focal_length": int(float(focallen)) if focallen else None,
            "instrume": str(header.get("INSTRUME", "")).strip(),
        }
        gain_val = header.get("GAIN")
        if gain_val is not None:
            result["gain"] = f"gain{int(float(gain_val))}"
            result["gain_value"] = int(float(gain_val))
        exptime = header.get("EXPTIME") or header.get("EXPOSURE")
        if exptime is not None:
            result["exposure_seconds"] = float(exptime)
        ccd_temp = header.get("CCD-TEMP")
        if ccd_temp is not None:
            result["sensor_temp"] = float(ccd_temp)
        filt = str(header.get("FILTER", "")).strip()
        if filt:
            result["filter"] = filt
        date_obs = str(header.get("DATE-OBS", "")).strip()
        if date_obs:
            try:
                result["capture_datetime"] = datetime.strptime(date_obs[:19], "%Y-%m-%dT%H:%M:%S")
            except ValueError:
                pass
        return result
    except Exception:
        return {"focal_length": None, "instrume": ""}

def _read_fits_filter(filepath):
    try:
        val = get_fits().getheader(filepath).get("FILTER")
        if val and str(val).strip():
            return str(val).strip()
    except Exception:
        pass
    return ""


# ═══════════════════════════════════════════════════════════════════════════
# STATE: LEDGER / HISTORY / SKIPLIST / CUSTOM NAMES / LOCK / MIRROR
# ═══════════════════════════════════════════════════════════════════════════

RECEIPT_TAG = "pc-" if IS_WINDOWS else ""   # "seestar-pc-<stamp>.json" (1.5.0)

def _unique_receipt_path(rdir, stem):
    """Receipts are named by a one-second stamp; two runs inside the same
    second (tests, or a quick re-run) must never overwrite each other (1.3.1).
    From 1.5.0 the PC's receipts carry "-pc", so two machines writing into
    one receipts folder can never produce the same name."""
    if RECEIPT_TAG:
        kind, _, rest = stem.partition("-")
        stem = f"{kind}-{RECEIPT_TAG}{rest}" if rest else f"{RECEIPT_TAG}{stem}"
    rpath = os.path.join(rdir, stem + ".json")
    k = 2
    while os.path.exists(rpath):
        rpath = os.path.join(rdir, f"{stem}-{k}.json")
        k += 1
    return rpath


def _atomic_write_json(path, data):
    # A tmp name per writer: two processes saving at once must never share
    # (and interleave into) one ledger.json.tmp (1.4.3 review finding H2).
    tmp = f"{path}.{os.getpid()}.{threading.get_ident()}.tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=1)
        f.flush()
        os.fsync(f.fileno())   # a power cut must not leave a truncated ledger
    for attempt in range(40):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            # Windows: a reader holding the file open blocks the rename for a
            # moment (Python never opens with FILE_SHARE_DELETE) — wait, retry
            if not IS_WINDOWS or attempt == 39:
                raise
            time.sleep(0.25)

CAMERA_KEY_SEP = "|cam="

def ledger_relpath(key):
    """The camera-relative path behind a ledger key (strips the camera
    qualifier a second Seestar's row carries — see State.key_for)."""
    return key.split(CAMERA_KEY_SEP, 1)[0]

def _row_camera(e):
    if e.get("device", "asiair") != "seestar":
        return None
    return e.get("camera") or "ZWO Seestar S30 Pro"

def refuse_newer_ledger(ledger):
    """True, and says so, for a ledger a newer importer wrote (1.5.3, U3):
    this version never writes it, restores it or acts on it."""
    v = ledger.get("version") if isinstance(ledger, dict) else None
    if isinstance(v, (int, float)) and v > LEDGER_VERSION:
        error(f"This ledger was written by a newer version of the importer "
              f"(ledger v{v}). Update this copy first; nothing was written.")
        return True
    return False

class State:
    def __init__(self):
        os.makedirs(STATE_DIR, exist_ok=True)
        self.ledger_path = os.path.join(STATE_DIR, "ledger.json")
        self.history_path = os.path.join(STATE_DIR, "history.jsonl")
        self.skiplist_path = os.path.join(STATE_DIR, "skiplist.json")
        self.names_path = os.path.join(STATE_DIR, "custom-names.json")
        self.report_path = os.path.join(STATE_DIR, "last-report.txt")
        self.ledger = None
        self.skiplist = []
        self.custom_names = {}
        self._dirty = False
        self.load()

    # ── load/save ────────────────────────────────────────────────────────
    def load(self):
        self.ledger_corrupt = False
        self._skip_bak_once = False
        self.ledger = self._load_json(self.ledger_path)
        if self.ledger is None and os.path.isfile(self.ledger_path):
            # ledger.json exists but would not parse — NEVER fall through to
            # "no ledger" (that path offers a baseline, which would mark
            # never-copied camera files as imported). Use the .bak, loudly.
            if os.path.isfile(self.ledger_path + ".bak"):
                warn("ledger.json is unreadable — recovering from ledger.json.bak")
                self.ledger = self._load_json(self.ledger_path + ".bak")
                if self.ledger is not None:
                    # don't let the next save overwrite the good .bak with a
                    # copy of the corrupt main file (pass-2 finding)
                    self._skip_bak_once = True
            if self.ledger is None:
                self.ledger_corrupt = True   # both unreadable — callers must
                #                              refuse to baseline over this
        if self.ledger is not None:
            self.ledger.setdefault("files", {})
            self.ledger.setdefault("calibration", {})
        self.skiplist = self._load_json(self.skiplist_path) or []
        self.custom_names = self._load_json(self.names_path)
        if self.custom_names is None:
            self.custom_names = {}
            legacy = self._load_json(LEGACY_CUSTOM_NAMES)
            if legacy:
                self.custom_names = dict(legacy)
                self._save_names()
                info(f"Migrated custom target names into {os.path.basename(self.names_path)}")

    @staticmethod
    def _load_json_quiet(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except (OSError, ValueError):
            return None

    @staticmethod
    def _load_json(path):
        if not os.path.isfile(path):
            return None
        try:
            with open(path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            warn(f"Could not read {os.path.basename(path)}: {e}")
            return None

    def has_ledger(self):
        return self.ledger is not None

    def new_ledger(self):
        self.ledger = {"version": LEDGER_VERSION, "files": {}, "calibration": {}}
        self._dirty = True

    def ledger_too_new(self):
        """A ledger written by a newer importer is never written by this one:
        its rows may mean things this version doesn't know (1.5.3). Says so."""
        return refuse_newer_ledger(self.ledger)

    def save_ledger(self):
        if self.ledger is None:
            return
        if self.ledger_too_new():
            sys.exit(2)          # before the .bak too: both files stay as they are
        if getattr(self, "_skip_bak_once", False):
            self._skip_bak_once = False   # main file is corrupt — keep the
            #                               .bak that just saved us intact
        elif os.path.isfile(self.ledger_path):
            try:
                shutil.copy2(self.ledger_path, self.ledger_path + ".bak")
            except OSError:
                pass
        _atomic_write_json(self.ledger_path, self.ledger)
        self._dirty = False

    def _save_names(self):
        _atomic_write_json(self.names_path, self.custom_names)

    def save_skiplist(self):
        _atomic_write_json(self.skiplist_path, self.skiplist)

    # ── history ──────────────────────────────────────────────────────────
    def history_event(self, event, **fields):
        rec = {"v": HISTORY_VERSION, "ts": now_stamp(), "event": event}
        rec.update(fields)
        try:
            with open(self.history_path, "a") as f:
                f.write(json.dumps(rec) + "\n")
        except OSError as e:
            warn(f"history write failed: {e}")

    def history_tail(self, n=6):
        try:
            with open(self.history_path, "r") as f:
                lines = f.readlines()
            return [json.loads(x) for x in lines[-n:]]
        except Exception:
            return []

    # ── ledger queries ───────────────────────────────────────────────────
    # Seestar paths REPEAT across units: "MyWorks/M 31_sub/<stamp>.fit" exists
    # on every Seestar, and two units shooting one target stamp some subs in
    # the same second — at the same size when the sensors match. A row keyed
    # by path alone let the second camera's frame read "already imported"
    # (never copied, then cleared as SAFE), or overwrite the first camera's
    # row (1.4.3 review BLOCKER H1). So a Seestar row belongs to ONE camera:
    # the plain key stays with whichever camera got there first (camera-less
    # rows are grandfathered to the S30 Pro, as everywhere else), and another
    # camera's row for the same path lives under "<path>|cam=<camera>".
    def key_for(self, relpath, camera=None):
        if camera is None or not self.ledger:
            return relpath
        files = self.ledger["files"]
        q = relpath + CAMERA_KEY_SEP + camera
        if q in files:
            return q
        e = files.get(relpath)
        if e is None or _row_camera(e) in (None, camera):
            return relpath
        return q

    def file_entry(self, relpath, camera=None):
        if not self.ledger:
            return None
        return self.ledger["files"].get(self.key_for(relpath, camera))

    def is_imported(self, relpath, size, camera=None):
        """Returns 'yes' | 'no' | 'mismatch'. Pass the Seestar camera for
        Seestar files — without it a same-named frame from another unit
        would count."""
        e = self.file_entry(relpath, camera)
        if e is None:
            return "no"
        if e.get("size") not in (None, size):
            return "mismatch"
        return "yes"

    def max_day_number(self, target, device="asiair", camera=None,
                       by_display=False):
        """Highest Day number the ledger knows for a target (survives the
        folders being archived off-disk). by_display matches the displayName
        field instead of target — Milky Way sessions all share the target
        'MilkyWay' but number their Days per paired-DSO display folder."""
        best = 0
        if not self.ledger:
            return 0
        field = "displayName" if by_display else "target"
        for e in self.ledger["files"].values():
            if e.get("device", "asiair") != device:
                continue   # each camera numbers its own Days
            if camera is not None and \
                    e.get("camera", "ZWO Seestar S30 Pro") != camera:
                continue   # ...and each SEESTAR its own, too
            if e.get(field) == target and isinstance(e.get("dayNumber"), int):
                best = max(best, e["dayNumber"])
        return best

    def add_file(self, relpath, **fields):
        # A copy made without a checksum is size-checked only — never
        # "verified", so the SAFE gate cannot clear its source (H10).
        if fields.get("origin") == "import" and fields.get("verifiedAtImport") \
                and not fields.get("sha256"):
            fields["verifiedAtImport"] = False
            fields["checksumSkipped"] = True
        cam = fields.get("camera") if fields.get("device") == "seestar" else None
        self.ledger["files"][self.key_for(relpath, cam)] = fields
        self._dirty = True

    def add_calibration(self, relpath, **fields):
        self.ledger["calibration"][relpath] = fields
        self._dirty = True

    def cal_entry(self, relpath):
        return self.ledger["calibration"].get(relpath) if self.ledger else None

    def mark_cleared(self, camera_relpaths, device="asiair", camera=None):
        """Flag ledger entries (for ONE device) whose files vanished from that
        camera. An EMPTY scan never clears anything (half-mount safety), and a
        scan of one camera never touches the other's entries. With two
        Seestars, `camera` narrows further: the S30's scan must not flag the
        S30 Pro's still-on-camera files (entries without a recorded camera
        are grandfathered to the S30 Pro, the only Seestar before 2026-08-18)."""
        if not camera_relpaths:
            return {}
        newly = defaultdict(int)
        stamp = now_stamp()
        for relpath, e in self.ledger["files"].items():
            if e.get("device", "asiair") != device:
                continue
            if camera is not None and \
                    e.get("camera", "ZWO Seestar S30 Pro") != camera:
                continue
            if ledger_relpath(relpath) not in camera_relpaths \
                    and not e.get("clearedFromCamera"):
                e["clearedFromCamera"] = True
                e["clearedNoticedAt"] = stamp
                newly[e.get("target", "?")] += 1
                self._dirty = True
        for relpath, e in self.ledger["calibration"].items():
            if device != "asiair":
                break
            if relpath not in camera_relpaths and not e.get("clearedFromCamera"):
                e["clearedFromCamera"] = True
                e["clearedNoticedAt"] = stamp
                self._dirty = True
        for target, count in newly.items():
            self.history_event("cleared-noticed", target=target, frames=count)
        return dict(newly)

    def seestar_seen(self, scan_s):
        """Bookkeeping after a Seestar scan, under the lock: flag this camera's
        rows whose files have gone (mark_cleared — never on a GUESSED identity,
        which would flag the real camera's frames, H7), and settle discard
        records left 'stillOnCamera' by a crash mid-discard: the file is either
        still there or it is not (H5)."""
        if not scan_s or not self.ledger:
            return
        vol, camera = scan_s["volume"], scan_s["camera"]
        if not scan_s.get("identityGuessed"):
            self.mark_cleared(scan_s["relpaths"], device="seestar", camera=camera)
        for rec in (self.ledger.get("discarded") or {}).values():
            if rec.get("stillOnCamera") and rec.get("camera") == camera \
                    and rec.get("relpath") and os.path.isdir(os.path.join(vol, "MyWorks")) \
                    and not os.path.exists(os.path.join(vol, rec["relpath"])):
                rec["stillOnCamera"] = False
                rec["goneNoticedAt"] = now_stamp()
                self._dirty = True

    # ── mirror publish ───────────────────────────────────────────────────
    def publish_mirror(self):
        try:
            generate_dashboard(self)
        except Exception as e:
            warn(f"dashboard generation failed: {e}")
        _confine(MIRROR_DIR, "the mirror publish")
        ok, owner = mirror_owner_ok(MIRROR_DIR, claim=True)
        if not ok:
            warn(f"The mirror folder {MIRROR_DIR} belongs to another computer "
                 f"({owner.get('host', '?')}, {owner.get('platform', '?')}) — NOT published. "
                 f"Give this machine its own ASIAIR_MIRROR folder in config.json (or, if "
                 f"this IS that computer after a rebuild, run --restore-ledger).")
            return False
        try:
            os.makedirs(MIRROR_DIR, exist_ok=True)
            for src in [self.ledger_path, self.history_path, self.skiplist_path,
                        self.names_path, self.report_path,
                        os.path.join(STATE_DIR, "dashboard.html")]:
                if src == self.ledger_path and self._load_json_quiet(src) is None:
                    # never publish an unreadable ledger over the mirror —
                    # the mirror is the one copy that can restore it (H8)
                    warn("ledger.json does not parse — the mirror copy was NOT "
                         "overwritten.")
                    continue
                if os.path.isfile(src):
                    dst = os.path.join(MIRROR_DIR, os.path.basename(src))
                    tmp = dst + ".tmp"
                    shutil.copy2(src, tmp)
                    os.replace(tmp, dst)
            meta = {
                "schemaVersions": {"ledger": LEDGER_VERSION, "history": HISTORY_VERSION},
                "lastRunAt": now_stamp(),
                "lastPublishAt": now_stamp(),
                "fileCount": len(self.ledger["files"]) if self.ledger else 0,
                "calibrationCount": len(self.ledger["calibration"]) if self.ledger else 0,
            }
            _atomic_write_json(os.path.join(MIRROR_DIR, "meta.json"), meta)
            debug(f"mirror published → {MIRROR_DIR}")
            return True
        except OSError as e:
            warn(f"Mirror publish failed (will retry next run): {e}")
            return False

    def restore_from_mirror(self):
        m_ledger = os.path.join(MIRROR_DIR, "ledger.json")
        if not os.path.isfile(m_ledger):
            error("No mirror ledger found — nothing to restore from.")
            return False
        if refuse_newer_ledger(self._load_json_quiet(m_ledger)):
            # a newer importer's ledger is never restored by this one: stop
            # before anything is copied, here or by the import that asked (U3)
            sys.exit(2)
        ok, owner = mirror_owner_ok(MIRROR_DIR)
        if not ok:
            # Another machine's ledger describes copies on THAT machine; as
            # this one's it would let the SAFE clear trust files not here.
            # But this may BE that machine, rebuilt — so ask, never assume.
            warn(f"This mirror was published by {owner.get('host', '?')} "
                 f"({owner.get('platform', '?')}), not by this computer's importer.")
            warn("Restore it ONLY if this is that same computer after a rebuild or "
                 "rename. Another machine's ledger describes copies that are not here.")
            if owner.get("platform") not in (None, PLATFORM):
                error("It came from a different kind of computer — not restored.")
                return False
            if safe_input("Is this that computer, rebuilt? [y/N] ", default="n").lower() != "y":
                info("Not restored.")
                return False
            try:
                with open(os.path.join(STATE_DIR, "machine.json"), "w") as f:
                    json.dump({"id": owner["id"], "platform": PLATFORM,
                               "host": socket.gethostname(),
                               "adoptedFrom": owner.get("host")}, f, indent=1)
            except OSError as e:
                error(f"Could not adopt the mirror's identity: {e}")
                return False
        meta = self._load_json(os.path.join(MIRROR_DIR, "meta.json")) or {}
        info(f"Mirror found: last run {meta.get('lastRunAt', 'unknown')}, "
             f"{meta.get('fileCount', '?')} light frames, "
             f"{meta.get('calibrationCount', '?')} calibration frames")
        for ev in self.history_tail(4):
            log(f"recent event: {ev.get('ts')} {ev.get('event')} {ev.get('target', '')}")
        warn("Restoring an OLD mirror can re-import anything captured since it was published.")
        resp = safe_input("Restore local state from this mirror? [y/N] ", default="n")
        if resp.lower() != "y":
            info("Restore cancelled.")
            return False
        for name in ["ledger.json", "history.jsonl", "skiplist.json", "custom-names.json"]:
            src = os.path.join(MIRROR_DIR, name)
            if os.path.isfile(src):
                shutil.copy2(src, os.path.join(STATE_DIR, name))
        self.load()
        self.history_event("restored-from-mirror", mirrorLastRunAt=meta.get("lastRunAt"))
        success("Local state restored from mirror.")
        return True


# ── Lockfile ─────────────────────────────────────────────────────────────────

LOCK_PATH = os.path.join(STATE_DIR, "import.lock")

# What Brett reads when the lock is held, by what holds it: the same words
# from the command line and on the panel's banner (1.5.3)
LOCK_HOLDER_TEXT = {"panel": "The panel is busy right now",
                    "ship": "The twice-daily ship to the PC is running right now"}

def lock_busy_text(what):
    """'The panel is busy right now', 'Another import is already running', ..."""
    return LOCK_HOLDER_TEXT.get(what) or f"Another {what} is already running"

def acquire_lock(what="import"):
    """`what` holds it: import / ship / panel / clear / discard (1.5.3)."""
    os.makedirs(STATE_DIR, exist_ok=True)
    if os.path.isfile(LOCK_PATH):
        try:
            with open(LOCK_PATH) as f:
                data = json.load(f)
            pid = int(data.get("pid", 0))
            if not pid_alive(pid):
                raise ProcessLookupError(pid)
            what = data.get("what") or "import"
            error(lock_busy_text(what) + f" (pid {pid}, started {data.get('started')}).")
            error("Wait for it to finish, or delete the lock file if it crashed:")
            error(lock_clear_hint(LOCK_PATH))
            return False
        except (OSError, ValueError, json.JSONDecodeError):
            warn("Stale lock file found — clearing it.")
            try:
                os.remove(LOCK_PATH)
            except OSError:
                pass
    try:
        fd = os.open(LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        # two starters raced for the lock this instant — the other one won
        error("Another import grabbed the lock just now — try again in a moment.")
        return False
    with os.fdopen(fd, "w") as f:
        json.dump({"pid": os.getpid(), "started": now_stamp(), "what": what}, f)
    return True

def release_lock():
    try:
        os.remove(LOCK_PATH)
    except OSError:
        pass


# ── Who runs this machine: the web version or the FITs Importer App (1.5.3) ──
# Only the app writes this record; the engine reads it, and archives a stale
# one (never deletes it). The web watchers and installers step aside for "app".

APP_OWNER_FILE = os.path.join(STATE_DIR, "app-takeover.json")

def app_owner_state():
    """("app", record) while the app that took over is on disk; ("stale",
    record) when it was trashed without handing back; ("web", None) otherwise,
    an unreadable record, or one whose appPath isn't absolute, included."""
    try:
        with open(APP_OWNER_FILE, encoding="utf-8-sig") as f:
            rec = json.load(f)
    except (OSError, ValueError):
        return "web", None
    if not isinstance(rec, dict) or rec.get("owner") != "app":
        return "web", None
    path = rec.get("appPath")
    if not (isinstance(path, str) and os.path.isabs(path)):
        # a relative path would mean one thing to the installer (run from
        # the home folder) and another to the watcher (run from /): only an
        # absolute one counts, the same everywhere
        return "web", None
    return ("app" if os.path.exists(path) else "stale"), rec

def app_owner():
    """The app's record while it owns this machine, else None."""
    owner, rec = app_owner_state()
    return rec if owner == "app" else None

def archive_stale_owner():
    """Rename the record aside as app-takeover.handed-back-<stamp>.json (never
    over another). Returns the new name."""
    stamp, n = now_stamp(), 1
    name = f"app-takeover.handed-back-{stamp}.json"
    while os.path.exists(os.path.join(STATE_DIR, name)):
        n += 1
        name = f"app-takeover.handed-back-{stamp}-{n}.json"
    os.rename(APP_OWNER_FILE, os.path.join(STATE_DIR, name))
    return name


# ═══════════════════════════════════════════════════════════════════════════
# EQUIPMENT / NAMES
# ═══════════════════════════════════════════════════════════════════════════

def load_equipment_scope_lookup():
    """equipment.json may extend SCOPE_LOOKUP for future scopes.
    Built-in names win for known focal lengths (receipt-folder stability)."""
    lookup = dict(SCOPE_LOOKUP)
    try:
        with open(EQUIPMENT_JSON) as f:
            eq = json.load(f)
        for t in eq.get("telescopes", []):
            fl = t.get("fitsFocalLen")
            if isinstance(fl, (int, float)) and int(fl) not in lookup:
                name = t.get("name", "").split(" ")
                lookup[int(fl)] = " ".join(name[:2]) if len(name) >= 2 else t.get("name", "Unknown Scope")
    except Exception:
        pass
    return lookup

def scope_from_focallen(focal_length, lookup):
    if focal_length:
        for known_fl, name in lookup.items():
            if abs(focal_length - known_fl) <= FOCALLEN_TOLERANCE:
                return name
    return "Unknown Scope"

def ask_typed(prompt, expect):
    """Typed confirmation for irreversible actions. True ONLY when the answer
    is exactly `expect`. Panel: a danger card with a text box (kind "typed").
    Terminal: input(). Piped/headless: always False — the safe default."""
    if PROMPT_FN is not None:
        try:
            r = PROMPT_FN({"kind": "typed", "prompt": prompt, "expect": expect,
                           "default": ""})
        except Exception:
            r = None
        return r is not None and str(r).strip() == expect
    return safe_input(prompt, default="").strip() == expect

def ask_target_name(catalog_name):
    """Ask for an unknown target's name. Panel question in app mode, macOS
    dialog otherwise. Timeout/cancel returns (None, False); explicit skip
    returns ("", True); a name returns (name, True)."""
    if PROMPT_FN is not None:
        try:
            r = PROMPT_FN({"kind": "text",
                           "prompt": f"The camera folder is named '{catalog_name}'. "
                                     f"What is this target? (leave blank to keep the name)",
                           "default": ""})
        except Exception:
            r = None
        if r is None:
            return None, False
        r = str(r).strip()
        return (r, True) if r else ("", True)
    if TEST_ROOT:
        _test_record("dialog", name=catalog_name)   # = headless: skip for this run
        return None, False
    if not IS_MAC:
        # Windows/Linux Terminal: ask in the console; headless = skip for now
        if not sys.stdin or not sys.stdin.isatty():
            return None, False
        try:
            r = input(f"The camera folder is named '{catalog_name}'. What is this "
                      f"target? (blank = keep the name, '-' = never ask again): ").strip()
        except EOFError:
            return None, False
        return ("", True) if r == "-" else ((r, True) if r else (None, False))
    script = (
        'on run argv\n'
        'set catName to item 1 of argv\n'
        'set theResult to display dialog '
        '"The ASIAir target folder is named:\\n\\n   " & catName & "\\n\\n'
        'What is this target? (e.g. Squid Nebula)\\n'
        'Leave blank to keep the folder name as-is." '
        'default answer "" buttons {"Skip", "Save Name"} default button "Save Name" '
        'with title "Unknown Target Name" with icon note\n'
        'if button returned of theResult is "Save Name" then\n'
        '    return "NAME:" & text returned of theResult\n'
        'else\n'
        '    return "SKIP:"\n'
        'end if\n'
        'end run'
    )
    try:
        result = subprocess.run(["osascript", "-e", script, "--", catalog_name],
                                capture_output=True, text=True, timeout=120)
        out = result.stdout.strip()
        if out.startswith("NAME:"):
            return out[5:].strip(), True
        if out.startswith("SKIP:"):
            return "", True
    except (subprocess.TimeoutExpired, OSError):
        pass
    return None, False

_session_skipped_names = set()
_DSO_NAMES_CI = {k.lower(): v for k, v in DSO_NAMES.items()}
_NAME_STOPWORDS = {"the", "a", "an", "of"}

def _name_key(s):
    return " ".join(t for t in re.findall(r"[a-z0-9]+", s.lower())
                    if t not in _NAME_STOPWORDS)

_BAD_NAME_CHARS = set('/\\:<>"|?*')

def clean_target_name(name):
    """A typed target name becomes a FOLDER on this Mac and on the PC archive,
    so it must be a plain name: no path separators, no '..', nothing Windows
    cannot store, no control characters (1.4.3 review finding V3). Returns
    the tidied name, or None when it cannot be used."""
    name = " ".join(str(name or "").split())
    if not name or len(name) > 120 or name.startswith(".") \
            or any(c in _BAD_NAME_CHARS or ord(c) < 32 for c in name):
        return None
    return name

def get_display_name(state, catalog_name, ask=True, dry_run=False):
    common = DSO_NAMES.get(catalog_name) or _DSO_NAMES_CI.get(catalog_name.lower(), "")
    if common:
        return f"{catalog_name} - {common}"
    if catalog_name in state.custom_names:
        custom = state.custom_names[catalog_name]
        if custom and clean_target_name(custom) is None:
            custom = ""   # a hostile or hand-edited name never becomes a path
        if custom:
            ck, nk = _name_key(catalog_name), _name_key(custom)
            if ck == nk or ck in nk:
                return custom          # folder name already IS the name — no doubling
            if nk in ck:
                return catalog_name
            return f"{catalog_name} - {custom}"
        return catalog_name
    if catalog_name in _session_skipped_names or not ask or dry_run:
        return catalog_name
    info(f"Unknown target: {catalog_name}")
    name, explicit = ask_target_name(catalog_name)
    if name and clean_target_name(name) is None:
        warn(f"'{name}' can't be used as a folder name (no / \\ : < > \" | ? * or "
             f"leading dot). Keeping '{catalog_name}' for this run.")
        name, explicit = None, False
    if name:
        name = clean_target_name(name)
        state.custom_names[catalog_name] = name
        state._save_names()
        success(f"Saved name: {catalog_name} → {name}")
        return get_display_name(state, catalog_name, ask=False)
    if explicit:
        # Explicit Skip click → remember permanently (spec §9.3)
        state.custom_names[catalog_name] = ""
        state._save_names()
    else:
        # Timeout / cancel / headless → skip for this run only
        _session_skipped_names.add(catalog_name)
    return catalog_name

MOSAIC_RE = re.compile(r"^(.+)_(\d+-\d+)$")

def display_name_for(state, folder_name, ask=False, dry_run=False):
    """Display name for ANY camera folder, resolving mosaic panels through
    their base target (report/scan/dashboard parity with the import path)."""
    m = MOSAIC_RE.match(folder_name)
    if m:
        base = get_display_name(state, m.group(1), ask=ask, dry_run=dry_run)
        return f"{base} · {m.group(2)}"
    return get_display_name(state, folder_name, ask=ask, dry_run=dry_run)


# ═══════════════════════════════════════════════════════════════════════════
# FILE OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════

def _hash_stream(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def _hash_dest_uncached(path):
    """Hash destination, bypassing page cache where the OS supports it."""
    h = hashlib.sha256()
    f = open(path, "rb")
    try:
        try:
            import fcntl
            if hasattr(fcntl, "F_NOCACHE"):
                fcntl.fcntl(f.fileno(), fcntl.F_NOCACHE, 1)
        except Exception:
            pass
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    finally:
        f.close()
    return h.hexdigest()

def sha256_of(path, bufsize=8*1024*1024):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(bufsize), b""):
            h.update(chunk)
    return h.hexdigest()


def copy_file_verified(src, dst, checksum=True, partial_suffix=".partial"):
    """Copy src→dst crash-safely: write .partial, verify, rename.
    Returns (sha256_or_None, size). Raises on failure (partial removed).
    The ship names its partials per machine, so two computers filing the same
    frame into the archive can never write into one .partial."""
    partial = dst + partial_suffix
    src_hash = hashlib.sha256() if checksum else None
    size = 0
    try:
        with open(src, "rb") as fin, open(partial, "wb") as fout:
            for chunk in iter(lambda: fin.read(1024 * 1024), b""):
                fout.write(chunk)
                size += len(chunk)
                if src_hash:
                    src_hash.update(chunk)
            fout.flush()
            os.fsync(fout.fileno())
        shutil.copystat(src, partial)
        dst_size = os.path.getsize(partial)
        if dst_size != size:
            raise IOError(f"size mismatch after copy ({dst_size} != {size})")
        sha = None
        if checksum:
            sha = src_hash.hexdigest()
            dst_sha = _hash_dest_uncached(partial)
            if dst_sha != sha:
                raise IOError("checksum mismatch after copy")
        os.replace(partial, dst)
        preserve_creation_time(src, dst)
        return sha, size
    except Exception:
        try:
            os.remove(partial)
        except OSError:
            pass
        raise

def preserve_creation_time(src, dst):
    if not IS_MAC:
        return   # Windows keeps the copy's own creation time; mtime is preserved
    try:
        result = subprocess.run(["stat", "-f", "%B", src], capture_output=True, text=True)
        if result.returncode == 0:
            birth = result.stdout.strip()
            if birth and birth != "0":
                dt = datetime.fromtimestamp(int(birth))
                subprocess.run(["SetFile", "-d", dt.strftime("%m/%d/%Y %H:%M:%S"), dst],
                               capture_output=True)
    except Exception:
        pass

def hardlink_or_copy(src, dst, checksum=True):
    """Hardlink (same volume, free) or verified copy. Returns ('link'|'copy', sha, size)."""
    try:
        os.link(src, dst)
        return "link", None, os.path.getsize(dst)
    except OSError:
        sha, size = copy_file_verified(src, dst, checksum=checksum)
        return "copy", sha, size

def tag_purple(folder_path):
    """Finder's purple "done" tag — a macOS nicety with no Windows
    equivalent (NTFS has no Finder labels); the ledger is the real record."""
    if TEST_ROOT:
        _test_record("tag", path=folder_path)
        return
    if not IS_MAC:
        return
    folder_path = folder_path.rstrip("/")
    try:
        subprocess.run(
            ["osascript", "-e", "on run argv",
             "-e", 'tell application "Finder" to set label index of '
                   '(POSIX file (item 1 of argv) as alias) to 5',
             "-e", "end run", "--", folder_path],
            capture_output=True, timeout=15,
        )
    except Exception:
        pass

def documents_under_icloud():
    """Preflight: detect iCloud Desktop & Documents sync (breaks hardlinks/evicts)."""
    docs = os.path.realpath(os.path.expanduser("~/Documents"))
    return "com~apple~CloudDocs" in docs or "Mobile Documents" in docs


# ═══════════════════════════════════════════════════════════════════════════
# CAMERA SCAN
# ═══════════════════════════════════════════════════════════════════════════

def camera_relpath(path):
    return _rel(path, ASIAIR_VOLUME)

def scan_camera(state):
    """Walk the camera. Returns dict with targets, calibration, relpath set, disk usage."""
    targets = []
    all_relpaths = set()

    for source_subdir in SOURCE_SUBDIRS:
        source_dir = os.path.join(ASIAIR_VOLUME, source_subdir)
        if not os.path.isdir(source_dir):
            continue
        source_label = source_subdir.split("/")[0]
        for entry in sorted(os.listdir(source_dir)):
            tdir = os.path.join(source_dir, entry)
            if not os.path.isdir(tdir) or entry.startswith("."):
                continue
            files = []
            for root, _dirs, fnames in os.walk(tdir):
                for fname in fnames:
                    low = fname.lower()
                    if low.endswith((".fit", ".fits")) and "_thn." not in low:
                        fpath = os.path.join(root, fname)
                        try:
                            fsize = os.path.getsize(fpath)
                        except OSError:
                            continue
                        rel = camera_relpath(fpath)
                        all_relpaths.add(rel)
                        files.append({"path": fpath, "relpath": rel,
                                      "filename": fname, "size": fsize})
            if not files:
                continue
            new = [f for f in files if state.has_ledger()
                   and state.is_imported(f["relpath"], f["size"]) != "yes"]
            if not state.has_ledger():
                new = list(files)
            integration = 0.0
            for f in new:
                p = parse_light_filename(f["filename"])
                if p:
                    integration += p["exposure_seconds"]
            targets.append({
                "name": entry,
                "source_label": source_label,
                "dir": tdir,
                "files": files,
                "new": new,
                "new_bytes": sum(f["size"] for f in new),
                "total_bytes": sum(f["size"] for f in files),
                "integration_s": integration,
                "skipped": entry in state.skiplist,
            })

    calibration = []
    cal_unparseable = []
    autorun = os.path.join(ASIAIR_VOLUME, AUTORUN_DIR)
    if os.path.isdir(autorun):
        for subdir in ["Bias", "Dark", "Flat"]:
            cdir = os.path.join(autorun, subdir)
            if not os.path.isdir(cdir):
                continue
            for fname in sorted(os.listdir(cdir)):
                low = fname.lower()
                if "_thn." in low or fname.startswith("._") or fname == ".DS_Store":
                    continue
                if not low.endswith(".fit"):
                    # A stray non-FITS file in Autorun is a file this tool can
                    # never prove backed up — it must weigh on the verdict too
                    cal_unparseable.append(f"{subdir}/{fname}")
                    continue
                parsed = parse_calibration_filename(fname)
                if not parsed:
                    # These never enter the Library, so they must also weigh
                    # against any "SAFE TO CLEAR" verdict on Autorun/
                    cal_unparseable.append(f"{subdir}/{fname}")
                    debug(f"unparseable calibration name skipped: {fname}")
                    continue
                fpath = os.path.join(cdir, fname)
                try:
                    fsize = os.path.getsize(fpath)
                except OSError:
                    continue
                rel = camera_relpath(fpath)
                all_relpaths.add(rel)
                parsed["source_path"] = fpath
                parsed["relpath"] = rel
                parsed["size"] = fsize
                calibration.append(parsed)

    try:
        usage = shutil.disk_usage(ASIAIR_VOLUME)
        disk = {"total": usage.total, "used": usage.total - usage.free, "free": usage.free}
    except OSError:
        disk = None

    return {"targets": targets, "calibration": calibration,
            "cal_unparseable": cal_unparseable,
            "relpaths": all_relpaths, "disk": disk}


# ═══════════════════════════════════════════════════════════════════════════
# CALIBRATION: INGEST-ALL LIBRARY + CONFIG-GATED MATCHING
# ═══════════════════════════════════════════════════════════════════════════

LIB_SUBDIR = {"Bias": "biases", "Dark": "darks", "Flat": "flats"}

def library_ingest_all(state, calibration, dry_run=False, checksum=True):
    """Every parseable calibration frame is backed up into the Library once."""
    ingested = 0
    degrade_links = documents_under_icloud()
    total = len(calibration)
    for idx, cal in enumerate(calibration):
        if not dry_run and total > 0:
            show_progress(idx + 1, total, label="Backing up calibration")
        entry = state.cal_entry(cal["relpath"])
        if entry is not None and entry.get("size") == cal["size"] and entry.get("libraryPath"):
            cal["library_path"] = os.path.join(LIBRARY_DIR, entry["libraryPath"])
            continue
        prior_origin = (entry or {}).get("origin")
        rel_lib = os.path.join(LIB_SUBDIR[cal["frame_type"]], cal["filename"])
        lib_path = os.path.join(LIBRARY_DIR, rel_lib)
        if dry_run:
            log(f"[dry-run] Would ingest {cal['filename']} → Library/{LIB_SUBDIR[cal['frame_type']]}/")
            cal["library_path"] = lib_path
            continue
        os.makedirs(os.path.dirname(lib_path), exist_ok=True)
        if os.path.isfile(lib_path) and os.path.getsize(lib_path) == cal["size"]:
            sha, size = None, cal["size"]
        else:
            try:
                sha, size = copy_file_verified(cal["source_path"], lib_path, checksum=checksum)
            except Exception as e:
                warn(f"Calibration ingest failed for {cal['filename']}: {e}")
                continue
        state.add_calibration(cal["relpath"], **{
            "filename": cal["filename"], "size": size, "sha256": sha,
            "frameType": cal["frame_type"], "camera": CAMERA_NAME,
            "gain": cal["gain_value"], "exposureSeconds": cal["exposure_seconds"],
            "filter": cal["filter"], "rotation": cal["rotation"],
            "libraryPath": rel_lib, "ingestedAt": now_stamp(),
            "verifiedAtImport": bool(sha), "linkedInto": [],
            **({"origin": prior_origin} if prior_origin else {}),
        })
        cal["library_path"] = lib_path
        ingested += 1
    if ingested:
        success(f"Calibration Library: ingested {ingested} new frame(s)"
                + (" (copies, not hardlinks — iCloud Documents detected)" if degrade_links else ""))
        state.history_event("calibration-ingest", frames=ingested)
    return ingested

def _closest_date_group(candidates, ref_dt):
    """Group by capture date, return the group whose midpoint is nearest ref_dt."""
    if not candidates:
        return []
    if ref_dt is None:
        return candidates
    groups = defaultdict(list)
    for c in candidates:
        key = c["capture_datetime"].strftime("%Y-%m-%d") if c["capture_datetime"] else "unknown"
        groups[key].append(c)
    dated = {k: v for k, v in groups.items() if k != "unknown"}
    if not dated:
        return candidates
    best_key, best_dist = None, None
    for key, members in dated.items():
        ts = [m["capture_datetime"] for m in members if m["capture_datetime"]]
        mid = min(ts) + (max(ts) - min(ts)) / 2
        dist = abs((mid - ref_dt).total_seconds())
        if best_dist is None or dist < best_dist:
            best_key, best_dist = key, dist
    return dated[best_key]

def _rot_delta(a, b):
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)

def match_calibration_group(group_info, calibration, loose=False, explain=None,
                            quiet=False):
    """Match calibration for one (filter, exposure) session group.
    group_info: gain(str), gain_value, exposure_seconds, sensor_temp, filter,
                rotation, focal_length, earliest_dt, latest_dt
    Returns {biases, darks, flats, warnings:[...]}"""
    warnings = []
    ref_dt = group_info.get("latest_dt") or group_info.get("earliest_dt")
    flat_window = timedelta(days=FLAT_WINDOW_DAYS)
    db_window = timedelta(days=DARKBIAS_WINDOW_DAYS)

    def in_window(cal, window):
        if cal["capture_datetime"] is None or ref_dt is None:
            return True
        return abs((cal["capture_datetime"] - ref_dt).total_seconds()) <= window.total_seconds()

    def note(cal, gate, detail, rejected):
        if explain is not None:
            explain.append({"file": cal["filename"], "type": cal["frame_type"],
                            "gate": gate, "detail": detail,
                            "result": "REJECT" if rejected else "pass"})

    biases, darks, flats = [], [], []
    prob_sets = {}
    for cal in calibration:          # clear stale probation marks from any
        cal.pop("_prob", None)       # earlier match run (preview or prior target)

    def prob_hit(cal, detail):
        cal["_prob"] = True   # marks this frame's set as questionable if chosen
        day = (cal["capture_datetime"].strftime("%Y-%m-%d")
               if cal["capture_datetime"] else "unknown date")
        key = (day, cal["exposure_seconds"], cal.get("filter") or "no filter", detail)
        prob_sets[key] = prob_sets.get(key, 0) + 1

    for cal in calibration:
        t = cal["frame_type"]
        if cal["gain"] != group_info["gain"]:
            note(cal, "gain", f"{cal['gain']} != {group_info['gain']}", True)
            continue
        note(cal, "gain", cal["gain"], False)
        if t == "Bias":
            if not in_window(cal, db_window):
                note(cal, "window", f">{DARKBIAS_WINDOW_DAYS}d", True); continue
            biases.append(cal)
        elif t == "Dark":
            if abs(cal["exposure_seconds"] - group_info["exposure_seconds"]) > EXPOSURE_TOLERANCE:
                note(cal, "exposure", f"{cal['exposure_seconds']}s vs {group_info['exposure_seconds']}s", True); continue
            temp = group_info.get("sensor_temp")
            if temp is not None and abs(cal["sensor_temp"] - temp) > DARK_TEMP_TOLERANCE:
                note(cal, "temp", f"{cal['sensor_temp']}C vs {temp}C", True); continue
            if not in_window(cal, db_window):
                note(cal, "window", f">{DARKBIAS_WINDOW_DAYS}d", True); continue
            darks.append(cal)
        elif t == "Flat":
            cal_filter = (cal.get("filter") or "").lower()
            t_filter = (group_info.get("filter") or "").lower()
            if cal_filter and t_filter and cal_filter != t_filter:
                note(cal, "filter", f"'{cal['filter']}' != '{group_info['filter']}'", True); continue
            if cal_filter and not t_filter:
                # A named-filter flat can never calibrate no-filter lights
                # (Lion run 2026-07-25: L-Ultimate flats were offered to a bare sensor)
                note(cal, "filter", f"'{cal['filter']}' flat vs no-filter lights", True); continue
            # FOCALLEN gate (required in v2, probation-aware)
            t_focal = group_info.get("focal_length")
            if t_focal is not None and not loose:
                cal_focal = read_fits_focallen(cal["source_path"])
                if cal_focal is None:
                    if CAL_GATES_PROBATION:
                        prob_hit(cal, "FOCALLEN unreadable")
                        note(cal, "focallen", "unreadable (probation pass)", False)
                    else:
                        note(cal, "focallen", "unreadable", True); continue
                elif abs(cal_focal - t_focal) > FOCALLEN_TOLERANCE:
                    note(cal, "focallen", f"{cal_focal} vs {t_focal}", True); continue
                else:
                    note(cal, "focallen", f"{cal_focal}", False)
            # Rotation gate (probation-aware, wraparound)
            t_rot = group_info.get("rotation")
            if t_rot is not None and cal.get("rotation") is not None and not loose:
                delta = _rot_delta(cal["rotation"], t_rot)
                if delta > ROTATION_TOLERANCE:
                    if CAL_GATES_PROBATION:
                        prob_hit(cal, f"rotation Δ{delta:.0f}° "
                                      f"({cal['rotation']:g}° vs lights {t_rot:g}°)")
                        note(cal, "rotation", f"Δ{delta:.1f}° (probation pass)", False)
                    else:
                        note(cal, "rotation", f"Δ{delta:.1f}°", True); continue
                else:
                    note(cal, "rotation", f"Δ{delta:.1f}°", False)
            if not in_window(cal, flat_window):
                note(cal, "window", f">{FLAT_WINDOW_DAYS}d", True); continue
            flats.append(cal)

    # One aggregated probation line per flat SET (the Lion run produced 400
    # per-frame lines — per-frame detail lives in --explain-cal instead)
    for (day, exp, filt, detail), n in sorted(prob_sets.items()):
        warnings.append(f"probation: {n}-frame flat set ({exp:g}s, {filt}, {day}): "
                        f"{detail} — would be REJECTED once gates harden")

    biases = _closest_date_group(biases, ref_dt)
    darks = _closest_date_group(darks, ref_dt)
    flats = _closest_date_group(flats, ref_dt)

    # Flat age transparency + questionable-set assessment (feeds the ask-gate)
    flats_age = None
    flats_questionable = False
    if flats and ref_dt:
        ages = [abs((f["capture_datetime"] - ref_dt).days)
                for f in flats if f["capture_datetime"]]
        if ages:
            age = min(ages)
            flats_age = age
            rot = flats[0].get("rotation")
            if not quiet:
                info(f"Flats: {len(flats)} frames — shot {age} day(s) from this session"
                     + (f", rotation {rot}°" if rot is not None else "")
                     + (f", {flats[0]['filter']}" if flats[0].get("filter") else ""))
            if age > FLAT_STALENESS_WARN_DAYS:
                warnings.append(f"flats are {age} days old — consider shooting fresh flats "
                                f"for this configuration")
    if flats and (any(f.get("_prob") for f in flats)
                  or (flats_age is not None and flats_age > FLAT_STALENESS_WARN_DAYS)):
        flats_questionable = True
    if not flats:
        cfg = (f"{group_info.get('scope', 'scope?')} + "
               f"{group_info.get('filter') or 'no filter'}"
               + (f" + rotation {group_info.get('rotation')}°" if group_info.get("rotation") is not None else ""))
        warnings.append(f"no flats match this configuration ({cfg}) — session will import "
                        f"without flats; shoot flats and re-run to link them in")

    return {"biases": biases, "darks": darks, "flats": flats, "warnings": warnings,
            "flatsQuestionable": flats_questionable, "flatsAge": flats_age}

# ── Panel pre-consent (Brett, 2026-08-09) ───────────────────────────────────
# The panel's scan card shows which calibration SET pairs with which target and
# lets Brett confirm each pairing with a checkbox before the import runs.
# CAL_DECISIONS carries those ticks: {target_name: {cal_set_key: bool}}.
# CLI runs leave it empty, so every prompt behaves exactly as before.
CAL_DECISIONS = {}

def cal_set_key(c):
    """Canonical identity of a calibration SET (type, exposure, filter,
    rotation, calendar day) — the same grouping the panel's cal card shows."""
    night = (c["capture_datetime"].strftime("%Y-%m-%d")
             if c.get("capture_datetime") else "unknown date")
    exp = c.get("exposure_seconds")
    rot = c.get("rotation")
    return "|".join([c["frame_type"],
                     ("%g" % exp) if exp is not None else "",
                     (c.get("filter") or ""),
                     ("%g" % rot) if rot is not None else "",
                     night])

def _attach_light_meta(new_files):
    """Same per-frame metadata prep the import performs (shared for preview)."""
    for f in new_files:
        if f.get("meta"):
            continue
        p = parse_light_filename(f["filename"])
        if not p:
            hdr = read_fits_header_summary(f["path"])
            p = {"exposure_seconds": hdr.get("exposure_seconds", 0.0),
                 "gain": hdr.get("gain", ""), "gain_value": hdr.get("gain_value"),
                 "sensor_temp": hdr.get("sensor_temp"), "rotation": None,
                 "filter": hdr.get("filter", ""),
                 "capture_datetime": hdr.get("capture_datetime")}
        f["meta"] = p

def preview_cal_pairings(state, scan):
    """Read-only preview for the panel: run the REAL matching gates for every
    target with new frames and report which calibration sets would pair with
    it. Returns {target_name: [set dict, ...]} where each set dict carries
    setKey/type/count/exposureSeconds/filter/rotation/night/inLibrary/
    questionable — questionable sets keep their mid-import question."""
    out = {}
    scope_lookup = load_equipment_scope_lookup()
    for target in scan["targets"]:
        if target["skipped"] or not target["new"]:
            continue
        new_files = list(target["new"])
        _attach_light_meta(new_files)
        focal_length = read_fits_focallen(new_files[0]["path"])
        if focal_length is None:
            focal_length = read_fits_header_summary(new_files[0]["path"]).get("focal_length")
        scope = scope_from_focallen(focal_length, scope_lookup)
        groups = defaultdict(list)
        for f in new_files:
            m = f["meta"]
            groups[((m.get("filter") or "").lower(),
                    round(m.get("exposure_seconds") or 0, 1))].append(f)
        sets = {}
        for (g_filter, g_exp), members in groups.items():
            metas = [x["meta"] for x in members]
            dts = [m["capture_datetime"] for m in metas if m.get("capture_datetime")]
            rotations = [m["rotation"] for m in metas if m.get("rotation") is not None]
            ginfo = {
                "gain": metas[0].get("gain") or "",
                "exposure_seconds": g_exp,
                "sensor_temp": metas[0].get("sensor_temp"),
                "filter": g_filter,
                "rotation": dominant_rotation(rotations),
                "focal_length": focal_length,
                "scope": scope,
                "earliest_dt": min(dts) if dts else None,
                "latest_dt": max(dts) if dts else None,
            }
            matched = match_calibration_group(ginfo, scan["calibration"],
                                              quiet=True)
            for kind in ("biases", "darks", "flats"):
                for c in matched[kind]:
                    k = cal_set_key(c)
                    e = sets.setdefault(k, {
                        "setKey": k, "type": c["frame_type"], "count": 0,
                        "exposureSeconds": c.get("exposure_seconds"),
                        "filter": c.get("filter") or "",
                        "rotation": c.get("rotation"),
                        "night": k.rsplit("|", 1)[-1],
                        "inLibrary": 0, "questionable": False})
                    e["count"] += 1
                    if state.has_ledger() and state.cal_entry(c["relpath"]) is not None:
                        e["inLibrary"] += 1
                    if kind == "flats" and matched.get("flatsQuestionable"):
                        e["questionable"] = True
        out[target["name"]] = sorted(sets.values(),
                                     key=lambda s: (s["type"], s["night"]))
    return out

def preview_dest_plan(state, scan=None, sscan=None):
    """Read-only prediction of where the NEXT import will land every target's
    new frames — the same Day-folder names the import itself would compute
    (next_day_number + continuation_day / _seestar_day_number). Powers the
    panel's destination-tree preview (Brett, 2026-08-09)."""
    plan = []
    scope_lookup = load_equipment_scope_lookup()
    if scan:
        for target in scan["targets"]:
            if target["skipped"] or not target["new"]:
                continue
            name = target["name"]
            new_files = list(target["new"])
            _attach_light_meta(new_files)
            m = re.match(r"^(.+)_(\d+-\d+)$", name)
            if m:  # mosaic panel: lights under parent/panel, cal shared at parent
                base = m.group(1)
                display = display_name_for(state, base)
                day_label = name
                dest_target_dir = os.path.join(DEST_DIR, display, name, "lights")
                tree_root = [display, name]
                ask_name = display == base
                shared_cal = True
            else:
                display = display_name_for(state, name)
                day_label = display
                dest_target_dir = os.path.join(DEST_DIR, display, "lights")
                tree_root = [display]
                ask_name = display == name
                shared_cal = False
            nights = {observing_night(f["meta"].get("capture_datetime"))
                      for f in new_files if f["meta"].get("capture_datetime")}
            nights.discard(None)
            day = next_day_number(state, dest_target_dir, day_label, name)
            day = continuation_day(dest_target_dir, day_label, day, nights)
            day_folder = f"{day_label} Day {day}"
            focal_length = read_fits_focallen(new_files[0]["path"])
            if focal_length is None:
                focal_length = read_fits_header_summary(new_files[0]["path"]).get("focal_length")
            plan.append({
                "device": "asiair", "target": name, "display": display,
                "askName": ask_name,
                # scope of the INCOMING frames (badges must not show a
                # target's ancestral scope when tonight's rig differs)
                "scope": scope_from_focallen(focal_length, scope_lookup),
                "deviceRoot": os.path.basename(DEST_DIR.rstrip("/")),
                "treeRoot": tree_root, "dayFolder": day_folder,
                "continuing": os.path.isdir(os.path.join(dest_target_dir, day_folder)),
                "files": len(new_files),
                "bytes": sum(f["size"] for f in new_files),
                "nights": sorted(nights),
                "sharedCal": shared_cal,
            })
    if sscan:
        dest_root = sscan["dest"]
        for t in sscan["targets"]:
            if t["skipped"] or t.get("is_mw"):
                continue
            if not t["new"] and not t.get("new_stacks") and not t.get("new_jpgs"):
                continue
            display = seestar_display(state, t["project_name"])
            day = _seestar_day_number(state, os.path.join(dest_root, display),
                                      t["sub_name"], t["name"],
                                      incoming_files=t["new"],
                                      camera=sscan.get("camera"))
            s_nights = sorted({_seestar_file_night(f["filename"]) or "" for f in t["new"]})
            # the stacks the import will actually copy: one per session (1.4.3)
            new_st = t.get("new_stacks") or []
            keep_new = [(n, s_) for _night, n, s_ in seestar_stack_keepers(t.get("stacks", []))
                        if s_ in new_st]
            stack = ({"filename": keep_new[-1][1]["filename"], "subs": keep_new[-1][0],
                      "count": len(keep_new)} if keep_new else None)
            new_jpgs = t.get("new_jpgs") or []
            plan.append({
                "device": "seestar", "target": t["name"], "display": display,
                "askName": display in (t["project_name"], t["name"]),
                "deviceRoot": os.path.basename(dest_root.rstrip("/")),
                "treeRoot": [display],
                # stack-only / jpg-only work creates no NEW Day folder; two
                # nights of subs become two Days (1.4.3)
                "dayFolder": (f"{t['sub_name']} Day {day}"
                              + (f"–{day + len(s_nights) - 1}" if len(s_nights) > 1 else "")
                              if t["new"] else None),
                "continuing": bool(not t["new"] and new_jpgs),
                "files": len(t["new"]) or len(new_jpgs),
                "bytes": sum(f["size"] for f in t["new"])
                or sum(f["size"] for f in new_jpgs),
                "nights": s_nights, "sharedCal": False, "stack": stack,
            })
        for nd in sscan["non_dso"]:
            if not nd["new"]:
                continue
            plan.append({
                "device": "seestar", "target": nd["dest_name"],
                "display": nd["dest_name"], "askName": False,
                "deviceRoot": os.path.basename(dest_root.rstrip("/")),
                "treeRoot": [nd["dest_name"]], "dayFolder": None,
                "continuing": os.path.isdir(os.path.join(dest_root, nd["dest_name"])),
                "files": len(nd["new"]),
                "bytes": sum(f["size"] for f in nd["new"]),
                "nights": [], "sharedCal": False, "stack": None,
            })
    return plan

def link_calibration_into(state, matched, dest_dir, dry_run=False, checksum=True):
    """Hardlink matched Library frames into dest_dir/calibration/{...}. Idempotent."""
    counts = {"biases": 0, "darks": 0, "flats": 0}
    dest_key = _rel(dest_dir, DEST_DIR)
    for cal_type in ["biases", "darks", "flats"]:
        cal_dest = os.path.join(dest_dir, "calibration", cal_type)
        if not dry_run:
            os.makedirs(cal_dest, exist_ok=True)
        for cal in matched.get(cal_type, []):
            dst = os.path.join(cal_dest, cal["filename"])
            if os.path.exists(dst):
                continue
            lib = cal.get("library_path")
            if not lib or not os.path.isfile(lib):
                lib = cal["source_path"]  # fallback: link/copy straight from camera
            if dry_run:
                debug(f"[dry-run] would link {cal['filename']} → {cal_type}/")
                counts[cal_type] += 1
                continue
            try:
                hardlink_or_copy(lib, dst, checksum=checksum)
                counts[cal_type] += 1
                entry = state.cal_entry(cal["relpath"])
                if entry is not None and dest_key not in entry.get("linkedInto", []):
                    entry.setdefault("linkedInto", []).append(dest_key)
                    state._dirty = True
            except Exception as e:
                warn(f"Failed to link calibration {cal['filename']}: {e}")
    return counts


# ═══════════════════════════════════════════════════════════════════════════
# MANIFESTS / DAY FOLDERS
# ═══════════════════════════════════════════════════════════════════════════

def read_manifest(manifest_path):
    names = set()
    if os.path.isfile(manifest_path):
        with open(manifest_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    names.add(line)
    return names

def scan_existing_fits(dest_target_dir):
    """filename → full path map of .fit files already under the target's lights dir."""
    found = {}
    if not os.path.isdir(dest_target_dir):
        return found
    for root, _dirs, fnames in os.walk(dest_target_dir):
        for fname in fnames:
            low = fname.lower()
            if low.endswith((".fit", ".fits")) and not low.endswith(".partial"):
                found[fname] = os.path.join(root, fname)
    return found

def next_day_number(state, dest_target_dir, day_label, target):
    """max(folder scan, ledger) + 1  (spec: archiving must not restart numbering)."""
    n = 1
    if os.path.isdir(dest_target_dir):
        while os.path.isdir(os.path.join(dest_target_dir, f"{day_label} Day {n}")):
            n += 1
    ledger_next = state.max_day_number(target) + 1
    return max(n, ledger_next)

def continuation_day(dest_target_dir, day_label, candidate_day, incoming_nights):
    """If Day (candidate-1) exists and holds frames from the same observing night,
    continue into it instead of splitting the night (spec §2)."""
    prev = candidate_day - 1
    if prev < 1 or not incoming_nights:
        return candidate_day
    prev_dir = os.path.join(dest_target_dir, f"{day_label} Day {prev}")
    if not os.path.isdir(prev_dir):
        return candidate_day
    for fname in os.listdir(prev_dir):
        p = parse_light_filename(fname)
        if p and p.get("capture_datetime"):
            if observing_night(p["capture_datetime"]) in incoming_nights:
                return prev
    return candidate_day


# ═══════════════════════════════════════════════════════════════════════════
# IMPORT
# ═══════════════════════════════════════════════════════════════════════════

def run_import(state, args, only_targets=None):
    dry_run = args.dry_run
    checksum = not args.no_checksum
    loose = args.loose_cal
    explain = [] if args.explain_cal else None

    if documents_under_icloud():
        warn("~/Documents appears to be under iCloud Desktop & Documents sync.")
        warn("Hardlinks are degraded to full copies, and iCloud may evict FITS data —")
        warn("consider moving the Astro folders to plain local storage.")

    scan = scan_camera(state)
    scope_lookup = load_equipment_scope_lookup()

    if not dry_run:
        state.mark_cleared(scan["relpaths"])
        if scan["disk"]:
            state.ledger["lastCameraDisk"] = scan["disk"]
        state.ledger["lastScanAt"] = now_stamp()
        state._dirty = True

    emit("run-start", targets=len([t for t in scan["targets"] if t["new"]]))

    # Calibration backup first — independent of target matching (spec §4a)
    if scan["calibration"]:
        info(f"Calibration: {len(scan['calibration'])} frames on camera — backing up to Library")
        emit("phase", name="calibration-backup", frames=len(scan["calibration"]))
        library_ingest_all(state, scan["calibration"], dry_run=dry_run, checksum=checksum)
    print()

    receipt_sessions = []
    totals = {"targets": 0, "files": 0, "cal": {"biases": 0, "darks": 0, "flats": 0}}
    probation_notes = []

    for target in scan["targets"]:
        name = target["name"]
        if only_targets is not None and name not in only_targets:
            continue
        if target["skipped"]:
            debug(f"skip-listed: {name}")
            continue

        new_files = list(target["new"])
        if args.all and not new_files:
            new_files = list(target["files"])

        # ── Mosaic detection (v1 behavior preserved) ──────────────────
        mosaic_match = re.match(r"^(.+)_(\d+-\d+)$", name)
        is_mosaic = bool(mosaic_match)
        if is_mosaic:
            mosaic_base, panel_id = mosaic_match.group(1), mosaic_match.group(2)
            parent_display = get_display_name(state, mosaic_base, dry_run=dry_run)
            display_name = parent_display
            day_label = name
            parent_dir = os.path.join(DEST_DIR, parent_display)
            old_panel = os.path.join(DEST_DIR, name)
            new_panel = os.path.join(parent_dir, name)
            if os.path.isdir(old_panel) and not os.path.isdir(new_panel) and not dry_run:
                os.makedirs(parent_dir, exist_ok=True)
                shutil.move(old_panel, new_panel)
                success(f"Moved {name} into {parent_display}/")
            dest_target_dir = os.path.join(parent_dir, name, "lights")
            manifest_path = os.path.join(parent_dir, name, ".imported_files")
            cal_dest_parent = parent_dir
        else:
            display_name = get_display_name(state, name, dry_run=dry_run)
            day_label = display_name
            dest_target_dir = os.path.join(DEST_DIR, display_name, "lights")
            manifest_path = os.path.join(DEST_DIR, display_name, ".imported_files")
            cal_dest_parent = None
            # rename catalog-only folder → display name (v1 migration, kept)
            old_dest = os.path.join(DEST_DIR, name)
            new_dest = os.path.join(DEST_DIR, display_name)
            if display_name != name and os.path.isdir(old_dest) and not os.path.isdir(new_dest):
                if dry_run:
                    log(f"[dry-run] Would rename: {name} → {display_name}")
                else:
                    shutil.move(old_dest, new_dest)
                    lights_dir = os.path.join(new_dest, "lights")
                    if os.path.isdir(lights_dir):
                        for old_day in os.listdir(lights_dir):
                            if old_day.startswith(f"{name} Day "):
                                day_num = old_day.split("Day ")[-1]
                                shutil.move(os.path.join(lights_dir, old_day),
                                            os.path.join(lights_dir, f"{display_name} Day {day_num}"))
                    old_light = os.path.join(new_dest, "Light")
                    if os.path.isdir(old_light) and not os.path.isdir(lights_dir):
                        shutil.move(old_light, lights_dir)
                    success(f"Renamed: {name} → {display_name}")

        ledger_display = f"{display_name} · {panel_id}" if is_mosaic else display_name

        # ── Supplementary union + adopt-with-verify (spec §2) ─────────
        dest_index = scan_existing_fits(dest_target_dir)
        manifest_names = read_manifest(manifest_path)
        still_new = []
        for f in new_files:
            status = state.is_imported(f["relpath"], f["size"])
            if status == "mismatch":
                warn(f"{f['filename']}: ledger entry exists with different size — treating as NEW")
                still_new.append(f)
                continue
            dest_path = dest_index.get(f["filename"])
            if dest_path is not None:
                try:
                    if os.path.getsize(dest_path) == f["size"]:
                        if not dry_run:
                            state.add_file(f["relpath"], **{
                                "filename": f["filename"], "size": f["size"], "sha256": None,
                                "origin": "merged", "target": name, "displayName": ledger_display,
                                "sourceType": target["source_label"], "camera": CAMERA_NAME,
                                "importedAt": now_stamp(), "dest": os.path.dirname(dest_path),
                                "verifiedAtImport": False,
                            })
                        debug(f"adopted existing dest copy: {f['filename']}")
                        continue
                    else:
                        warn(f"{f['filename']}: destination copy has wrong size — re-importing")
                except OSError:
                    pass
            elif f["filename"] in manifest_names:
                # manifest says imported but the file is archived — trust ledger only.
                # Without a ledger entry this file is NEW (pre-v2 manifests merge at baseline).
                pass
            still_new.append(f)
        new_files = still_new

        if not new_files:
            if target["new"]:
                info(f"{display_name}: all files already present — adopted, nothing to copy")
            continue

        if args.all and target["new"] != new_files:
            pass  # --all confirmed in main()

        totals["targets"] += 1
        print("───────────────────────────────────────────────────────────────")
        label = f"{display_name} — Panel {panel_id}" if is_mosaic else display_name
        emit("phase", name="target", target=label, files=len(new_files))
        info(f"Target: {label} ({target['source_label']})")
        info(f"{len(new_files)} new file(s) to copy ({len(target['files'])} total on ASIAir)")

        # ── Per-frame detail + session groups (filter, exposure) ──────
        for f in new_files:
            p = parse_light_filename(f["filename"])
            if not p:
                hdr = read_fits_header_summary(f["path"])
                p = {"exposure_seconds": hdr.get("exposure_seconds", 0.0),
                     "gain": hdr.get("gain", ""), "gain_value": hdr.get("gain_value"),
                     "sensor_temp": hdr.get("sensor_temp"), "rotation": None,
                     "filter": hdr.get("filter", ""),
                     "capture_datetime": hdr.get("capture_datetime")}
                debug(f"filename unparseable, used FITS headers: {f['filename']}")
            f["meta"] = p
        focal_length = read_fits_focallen(new_files[0]["path"])
        if focal_length is None:
            focal_length = read_fits_header_summary(new_files[0]["path"]).get("focal_length")
        scope = scope_from_focallen(focal_length, scope_lookup)

        groups = defaultdict(list)
        for f in new_files:
            m = f["meta"]
            groups[((m.get("filter") or "").lower(), round(m.get("exposure_seconds") or 0, 1))].append(f)
        if len(groups) > 1:
            info(f"Session contains {len(groups)} (filter, exposure) groups — "
                 f"calibration matched per group")

        nights = {observing_night(f["meta"].get("capture_datetime"))
                  for f in new_files if f["meta"].get("capture_datetime")}
        nights.discard(None)

        first = new_files[0]["meta"]
        info(f"FITS: {first.get('exposure_seconds')}s, {first.get('gain') or '?'}, "
             f"Filter: {first.get('filter') or 'None'}, "
             f"Sensor: {first.get('sensor_temp', '?')}°C, Scope: {scope}")

        # ── Day number: max(folders, ledger) + continuation ───────────
        day = next_day_number(state, dest_target_dir, day_label, name)
        day = continuation_day(dest_target_dir, day_label, day, nights)
        day_folder_name = f"{day_label} Day {day}"
        dest_day_dir = os.path.join(dest_target_dir, day_folder_name)
        if os.path.isdir(dest_day_dir):
            info(f"Continuing into existing {day_folder_name} (same observing night)")
        elif day > 1:
            info(f"Project exists — this will be Day {day}")
        else:
            info("New project — creating as Day 1")

        # ── Copy lights ────────────────────────────────────────────────
        copied = successful = 0
        if dry_run:
            log(f"[dry-run] Would copy {len(new_files)} file(s) to {day_folder_name}")
        else:
            os.makedirs(dest_day_dir, exist_ok=True)
            os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
            copy_failed = False
            for f in new_files:
                dest_file = os.path.join(dest_day_dir, f["filename"])
                try:
                    sha, size = copy_file_verified(f["path"], dest_file, checksum=checksum)
                    m = f["meta"]
                    state.add_file(f["relpath"], **{
                        "filename": f["filename"], "size": size, "sha256": sha,
                        "origin": "import", "target": name, "displayName": ledger_display,
                        "sourceType": target["source_label"], "camera": CAMERA_NAME,
                        "scope": scope,
                        "gain": m.get("gain_value"),
                        "exposureSeconds": m.get("exposure_seconds"),
                        "filter": m.get("filter") or "",
                        "rotation": m.get("rotation"),
                        "night": observing_night(m.get("capture_datetime")),
                        "dayNumber": day, "importedAt": now_stamp(),
                        "dest": dest_day_dir, "verifiedAtImport": True,
                    })
                    with open(manifest_path, "a") as mf:  # v1 rollback compatibility
                        mf.write(f["filename"] + "\n")
                    successful += 1
                except Exception as e:
                    copy_failed = True
                    warn(f"Copy FAILED for {f['filename']}: {e}")
                copied += 1
                show_progress(copied, len(new_files))
            if copy_failed:
                warn(f"Copied {successful} of {copied} — {copied - successful} failed "
                     f"(re-run to retry; nothing failed is marked imported)")
            else:
                success(f"Copied {successful} new frame(s) to {day_folder_name} "
                        f"(verified{' + SHA-256' if checksum else ', size only'})")

        # ── Calibration matching + linking per group ──────────────────
        if scan["calibration"] and (successful > 0 or dry_run):
            agg = {"biases": 0, "darks": 0, "flats": 0}
            for (g_filter, g_exp), members in groups.items():
                metas = [x["meta"] for x in members]
                dts = [m["capture_datetime"] for m in metas if m.get("capture_datetime")]
                rotations = [m["rotation"] for m in metas if m.get("rotation") is not None]
                ginfo = {
                    "gain": metas[0].get("gain") or "",
                    "exposure_seconds": g_exp,
                    "sensor_temp": metas[0].get("sensor_temp"),
                    "filter": g_filter,
                    "rotation": dominant_rotation(rotations),
                    "focal_length": focal_length,
                    "scope": scope,
                    "earliest_dt": min(dts) if dts else None,
                    "latest_dt": max(dts) if dts else None,
                }
                matched = match_calibration_group(ginfo, scan["calibration"],
                                                  loose=loose, explain=explain)
                for w in matched["warnings"]:
                    warn(w)
                    if w.startswith("probation:"):
                        probation_notes.append(f"{label}: {w}")
                        state.history_event("probation-gate", target=name, detail=w)
                # Panel pre-consent (Brett, 2026-08-09): checkbox decisions from
                # the scan card. Unticked sets are dropped here (frames still
                # get backed up to the Library — only the target link is skipped).
                dec = CAL_DECISIONS.get(name) or {}
                if dec:
                    for kind in ("biases", "darks", "flats"):
                        if not matched[kind]:
                            continue
                        keep = [c for c in matched[kind]
                                if dec.get(cal_set_key(c)) is not False]
                        dropped = len(matched[kind]) - len(keep)
                        if dropped:
                            matched[kind] = keep
                            info(f"{dropped} {kind[:-1]} frame(s) unticked on the "
                                 f"panel — not linked to {display_name}.")
                            state.history_event("cal-unticked", target=name,
                                                kind=kind, frames=dropped)
                # Ask-before-linking gate (Brett, 2026-07-25): when the chosen
                # flats look borrowed (probation flags) or stale, confirm first.
                if matched["flats"] and not dry_run and not loose:
                    age_txt = (f", {matched['flatsAge']} day(s) old"
                               if matched.get("flatsAge") is not None else "")
                    flat_keys = {cal_set_key(c) for c in matched["flats"]}
                    pre_yes = (bool(dec) and not matched.get("flatsQuestionable")
                               and all(dec.get(k) is True for k in flat_keys))
                    if matched.get("flatsQuestionable"):
                        warn(f"These flats may belong to ANOTHER project "
                             f"(gate flags{age_txt}) — no flats may exist yet for this "
                             f"configuration.")
                        # Self-describing question (Brett, 2026-08-12): name the
                        # set and the mismatch so the card needs no log-reading.
                        f0 = matched["flats"][0]
                        f_night = (f0["capture_datetime"].strftime("%Y-%m-%d")
                                   if f0.get("capture_datetime") else "unknown date")
                        f_desc = f"{len(matched['flats'])} flat(s) from {f_night}"
                        if f0.get("rotation") is not None:
                            f_desc += f" at {f0['rotation']:g}°"
                        f_desc += age_txt
                        l_desc = display_name
                        if ginfo.get("rotation") is not None:
                            l_desc += f" (lights at {ginfo['rotation']:g}°)"
                        resp = safe_input(
                            f"These look like another project's flats — {f_desc}. "
                            f"Link to {l_desc} anyway? [y/N] ", default="n")
                        declined = resp.lower() != "y"
                    elif pre_yes:
                        # Confirmed up front on the scan card — no interruption.
                        info(f"Flats confirmed on the panel — linking "
                             f"{len(matched['flats'])}.")
                        declined = False
                    elif PROMPT_FN is not None:
                        # Panel mode: every flat link is confirmed, not just
                        # questionable ones (Brett, 2026-08-08). Default Yes.
                        dest_label = (f"{parent_display}/ (shared)"
                                      if is_mosaic else day_folder_name)
                        resp = safe_input(
                            f"Link {len(matched['flats'])} matched flat(s) "
                            f"({g_filter or 'no filter'}{age_txt}) into "
                            f"{dest_label}? [Y/n] ", default="y")
                        declined = resp.lower() in ("n", "no")
                    else:
                        declined = False
                    if declined:
                        matched["flats"] = []
                        info("Flats skipped — shoot flats for this target and re-run; "
                             "they'll link into this same Day folder.")
                        state.history_event("flats-declined", target=name)
                b, d, fl = len(matched["biases"]), len(matched["darks"]), len(matched["flats"])
                suffix = f" [{g_filter or 'no filter'} @ {g_exp}s]" if len(groups) > 1 else ""
                info(f"Calibration matched{suffix}: {b} bias, {d} dark, {fl} flat")
                link_dest = cal_dest_parent if is_mosaic else dest_day_dir
                counts = link_calibration_into(state, matched, link_dest,
                                               dry_run=dry_run, checksum=checksum)
                for k in agg:
                    agg[k] += counts[k]
            if sum(agg.values()) > 0:
                where = f"{parent_display}/ (shared)" if is_mosaic else f"{day_folder_name}/"
                success(f"Calibration linked into {where} "
                        f"({agg['biases']}b, {agg['darks']}d, {agg['flats']}f)")
            for k in totals["cal"]:
                totals["cal"][k] += agg[k]

        # ── Wrap-up per target ─────────────────────────────────────────
        if not dry_run and successful > 0:
            info(f"Tagging {name} purple on ASIAir...")
            tag_purple(target["dir"])
            integ = sum((f["meta"].get("exposure_seconds") or 0)
                        for f in new_files)
            session = {
                "targetDisplayName": display_name, "asiairTargetName": name,
                "sourceType": target["source_label"], "dayNumber": day,
                "framesCopied": successful, "fitsFolderPath": dest_day_dir,
                "scope": scope,
            }
            if is_mosaic:
                session.update({"isMosaic": True, "panelId": panel_id, "mosaicBase": mosaic_base})
            receipt_sessions.append(session)
            state.history_event("import", target=name, displayName=display_name,
                                scope=scope, frames=successful,
                                bytes=sum(x["size"] for x in new_files),
                                integrationSeconds=round(integ, 1),
                                dayFolder=dest_day_dir,
                                looseCal=bool(loose))
            state.save_ledger()  # flush per target (spec §2)
            totals["files"] += successful

        # ── Clean previews if requested ────────────────────────────────
        # (--clean-source-previews removed in 1.4.3: it deleted JPEGs from the
        #  ASIAir, which this tool promises never to touch — review H9)
        print()

    # ── Receipts: one per scope (spec §9.2) ───────────────────────────
    if not dry_run and receipt_sessions:
        by_scope = defaultdict(list)
        for s in receipt_sessions:
            by_scope[s["scope"]].append(s)
        for scope_name, sessions in by_scope.items():
            receipt = {"version": 1, "source": "asiair-import",
                       "telescope": scope_name, "importedAt": now_stamp(),
                       "sessions": sessions}
            rdir = os.path.join(RECEIPT_BASE, scope_name)
            _confine(rdir, "the AstroLog receipt")
            os.makedirs(rdir, exist_ok=True)
            rpath = _unique_receipt_path(rdir, f"asiair-{receipt['importedAt']}")
            _atomic_write_json(rpath, receipt)
            success(f"AstroLog receipt saved → {scope_name}/{os.path.basename(rpath)}")

    # ── Summary / eject ────────────────────────────────────────────────
    print("═══════════════════════════════════════════════════════════════")
    if totals["targets"] == 0:
        success("Nothing new — every frame on the camera is already backed up.")
    else:
        success(f"Done! {totals['targets']} target(s), {totals['files']} frame(s) imported.")
        cal_total = sum(totals["cal"].values())
        if cal_total:
            success(f"Calibration linked: {totals['cal']['biases']} bias, "
                    f"{totals['cal']['darks']} dark, {totals['cal']['flats']} flat.")
        if probation_notes:
            print()
            warn(f"{len(probation_notes)} probation-gate note(s) recorded — "
                 f"review with --explain-cal before gates harden.")
    if explain is not None and explain:
        print()
        info("Calibration gate table (--explain-cal):")
        for row in explain:
            log(f"{row['result']:>6}  {row['type']:<5} {row['file']}  [{row['gate']}: {row['detail']}]")

    emit("run-done", targets=totals["targets"], files=totals["files"])
    if not dry_run:
        state.save_ledger()
        state.publish_mirror()
        if totals["files"] > 0:
            notify(f"{totals['targets']} target(s), {totals['files']} frames imported ✓")
    return totals


# ═══════════════════════════════════════════════════════════════════════════
# BASELINE / UNBASELINE / RECONCILE
# ═══════════════════════════════════════════════════════════════════════════

def run_baseline(state, assume_yes=False):
    asiair_here = os.path.isdir(ASIAIR_VOLUME)
    scan = scan_camera(state) if asiair_here else {"targets": [], "calibration": []}
    try:
        sscan = scan_seestar(state)
    except RuntimeError as e:
        error(f"Seestar NOT baselined: {e}")
        sscan = None
        if not asiair_here:
            sys.exit(1)
    n_lights = sum(len(t["files"]) for t in scan["targets"])
    n_cal = len(scan["calibration"])
    n_seestar = 0
    if sscan:
        n_seestar = (sum(len(t["files"]) + len(t["stacks"]) for t in sscan["targets"])
                     + sum(len(p["files"]) for p in sscan["panel_sets"])
                     + sum(len(n["files"]) for n in sscan["non_dso"]))
    if asiair_here:
        info(f"ASIAir holds {n_lights} light frames across {len(scan['targets'])} targets, "
             f"+ {n_cal} calibration frames.")
    if sscan:
        info(f"Seestar ({sscan['model']}) holds {n_seestar} files across "
             f"{len(sscan['targets'])} projects.")
    if not state.has_ledger():
        state.new_ledger()
    if not assume_yes:
        warn("Baseline marks EVERYTHING currently on the camera(s) as already imported (no copying).")
        warn("Choose No only if some targets have never been imported.")
        resp = safe_input(f"Mark all {n_lights + n_cal + n_seestar} files as imported? [y/N] ",
                          default="n")
        if resp.lower() != "y":
            info("Baseline cancelled.")
            return False

    stamp = now_stamp()
    added = 0
    for target in scan["targets"]:
        display = display_name_for(state, target["name"])
        for f in target["files"]:
            if state.file_entry(f["relpath"]) is not None:
                continue
            p = parse_light_filename(f["filename"]) or {}
            state.add_file(f["relpath"], **{
                "filename": f["filename"], "size": f["size"], "sha256": None,
                "origin": "baseline", "target": target["name"], "displayName": display,
                "sourceType": target["source_label"], "camera": CAMERA_NAME,
                "gain": p.get("gain_value"), "exposureSeconds": p.get("exposure_seconds"),
                "filter": p.get("filter") or "", "rotation": p.get("rotation"),
                "night": observing_night(p.get("capture_datetime")),
                "importedAt": stamp, "baselined": True, "verifiedAtImport": False,
            })
            added += 1
    for cal in scan["calibration"]:
        if state.cal_entry(cal["relpath"]) is None:
            state.add_calibration(cal["relpath"], **{
                "filename": cal["filename"], "size": cal["size"], "sha256": None,
                "frameType": cal["frame_type"], "camera": CAMERA_NAME,
                "gain": cal["gain_value"], "exposureSeconds": cal["exposure_seconds"],
                "filter": cal["filter"], "rotation": cal["rotation"],
                "libraryPath": None, "ingestedAt": None, "origin": "baseline",
                "verifiedAtImport": False, "linkedInto": [],
            })
            added += 1
    if sscan:
        added += seestar_baseline(state, sscan)
    state.ledger["baselinedAt"] = stamp
    state.save_ledger()
    state.history_event("baseline", frames=added)
    success(f"Baseline complete — {added} file(s) recorded without copying.")

    # ── Audit: which targets have no local trace? (spec §2) ────────────
    print()
    info("Baseline audit — checking each target for a local copy:")
    flagged = 0
    for target in scan["targets"]:
        display = display_name_for(state, target["name"])
        candidates = [os.path.join(DEST_DIR, display), os.path.join(DEST_DIR, target["name"])]
        mosaic = re.match(r"^(.+)_(\d+-\d+)$", target["name"])
        if mosaic:
            pdisp = get_display_name(state, mosaic.group(1), ask=False)
            candidates.append(os.path.join(DEST_DIR, pdisp, target["name"]))
        if any(os.path.isdir(c) for c in candidates):
            log(f"{display}: destination folder present ✓")
        else:
            flagged += 1
            warn(f"{display}: NO local copy found — if this was never imported, run:")
            log(f"    --unbaseline \"{target['name']}\"   then import normally")
    if sscan:
        for t in sscan["targets"]:
            display = seestar_display(state, t["project_name"])
            cands = [os.path.join(sscan["dest"], display),
                     os.path.join(sscan["dest"], t["project_name"])]
            if any(os.path.isdir(c) for c in cands):
                log(f"{display}: destination folder present ✓")
            else:
                flagged += 1
                warn(f"{display}: NO local copy found — if never imported, run:")
                log(f"    --unbaseline \"{t['name']}\"   then import normally")
    if flagged == 0:
        success("Every baselined target has a destination folder — baseline looks sound.")
    state.publish_mirror()
    return True

def run_merge_days(state, target_name, day_args):
    """Merge several Day folders of one target into the lowest listed day —
    heals a single observing night fragmented by interrupted/resumed imports
    (seen live: M 8 and NGC 7293 split across three Days, 2026-08-18).
    Moves the files, updates ledger dest/dayNumber, removes emptied folders.
    Aborts untouched on any filename collision."""
    if not state.has_ledger():
        error("No ledger.")
        return
    try:
        days = sorted({int(d) for d in day_args})
    except ValueError:
        error("--merge-days wants: TARGET DAY DAY ...  (day numbers)")
        return
    if len(days) < 2:
        error("Give at least two day numbers to merge.")
        return
    into = days[0]
    def _in_day_folder(e):
        # Only frames that LIVE in a Day folder move. Stacks (and anything
        # else kept at the project root) carry a dayNumber but must stay put
        # (live lesson: M 8's stacks dragged into Day 2, 2026-08-18).
        return os.path.basename(e.get("dest", "")).endswith(f"Day {e.get('dayNumber')}")
    ents = [(rel, e) for rel, e in state.ledger["files"].items()
            if e.get("target") == target_name and e.get("dayNumber") in days
            and _in_day_folder(e)]
    if not ents:
        error(f"No ledger entries for '{target_name}' with days {days}.")
        return
    into_dirs = {e["dest"] for _, e in ents if e.get("dayNumber") == into}
    if len(into_dirs) != 1:
        error(f"Day {into} maps to {len(into_dirs)} folder(s) in the ledger — "
              f"cannot merge safely.")
        return
    into_dir = into_dirs.pop()
    movers = [(rel, e) for rel, e in ents if e.get("dayNumber") != into]
    for d in sorted({e["dest"] for _, e in ents}):
        _confine(d, "--merge-days")
    # pre-flight: every source present, no destination collisions
    problems = []
    for rel, e in movers:
        src = os.path.join(e["dest"], e["filename"])
        dst = os.path.join(into_dir, e["filename"])
        if not os.path.isfile(src):
            problems.append(f"missing on disk: {src}")
        elif os.path.exists(dst):
            problems.append(f"name collision at destination: {e['filename']}")
    if problems:
        error(f"Merge aborted — nothing was moved:")
        for pr in problems[:6]:
            error(f"  {pr}")
        return
    old_dirs = sorted({e["dest"] for _, e in movers})
    for rel, e in movers:
        shutil.move(os.path.join(e["dest"], e["filename"]),
                    os.path.join(into_dir, e["filename"]))
        e["dest"] = into_dir
        e["dayNumber"] = into
    for d in old_dirs:
        try:
            ds = os.path.join(d, ".DS_Store")
            if os.path.isfile(ds):
                os.remove(ds)
            leftovers = os.listdir(d)
            if leftovers:
                warn(f"Left in place (unledgered content): {d} ({len(leftovers)} item(s))")
            else:
                os.rmdir(d)
                info(f"Removed emptied folder: {os.path.basename(d)}")
        except OSError as ex:
            warn(f"Could not tidy {d}: {ex}")
    state.history_event("days-merged", target=target_name,
                        detail=f"days {days} → Day {into}", frames=len(movers))
    state.save_ledger()
    state.publish_mirror()
    success(f"Merged {len(movers)} frame(s) from days {days[1:]} into Day {into} "
            f"({os.path.basename(into_dir)}).")

def run_renumber_day(state, target_name, from_day, to_day):
    """Rename one Day folder to a different number (folder + every ledger
    entry). Companion to --merge-days for closing numbering gaps left when a
    fragment turned out to be unledgered."""
    if not state.has_ledger():
        error("No ledger.")
        return
    try:
        from_day, to_day = int(from_day), int(to_day)
    except ValueError:
        error("--renumber-day wants: TARGET FROM TO")
        return
    ents = [e for e in state.ledger["files"].values()
            if e.get("target") == target_name and e.get("dayNumber") == from_day
            and os.path.basename(e.get("dest", "")).endswith(f"Day {from_day}")]
    if not ents:
        error(f"No ledger entries for '{target_name}' Day {from_day}.")
        return
    dirs = {e["dest"] for e in ents}
    if len(dirs) != 1:
        error(f"Day {from_day} maps to {len(dirs)} folders — cannot renumber.")
        return
    src_dir = dirs.pop()
    base = os.path.basename(src_dir)
    dst_dir = os.path.join(os.path.dirname(src_dir),
                           base.replace(f"Day {from_day}", f"Day {to_day}"))
    _confine(src_dir, "--renumber-day")
    _confine(dst_dir, "--renumber-day")
    if os.path.exists(dst_dir):
        error(f"Already exists: {dst_dir}")
        return
    shutil.move(src_dir, dst_dir)
    for e in ents:
        e["dest"] = dst_dir
        e["dayNumber"] = to_day
    state.history_event("day-renumbered", target=target_name,
                        detail=f"Day {from_day} → Day {to_day}", frames=len(ents))
    state.save_ledger()
    state.publish_mirror()
    success(f"Renamed {base} → {os.path.basename(dst_dir)} ({len(ents)} entries).")

def run_set_filter(state, target_name, filter_tag, night=None):
    """Correct the recorded filter for already-imported frames. The ASIAir
    only writes a filter token into filenames when the app's filter setting
    is configured — a blank setting records 'no filter' even with glass in
    the drawer (seen live: Fish on the Platter, 2026-06-23). This fixes the
    LEDGER's history; calibration matching at import time always reads the
    camera's own filenames, so future sessions need the app set correctly."""
    if not state.has_ledger():
        error("No ledger.")
        return
    tag = "" if filter_tag.lower() in ("none", "-") else filter_tag
    touched = 0
    nights = set()
    for e in state.ledger["files"].values():
        if e.get("device", "asiair") != "asiair":
            continue
        if e.get("target") != target_name:
            continue
        if night and e.get("night") != night:
            continue
        if e.get("filter", "") == tag:
            continue
        e["filter"] = tag
        touched += 1
        if e.get("night"):
            nights.add(e["night"])
        state._dirty = True
    if not touched:
        info(f"No entries needed changing for '{target_name}'"
             + (f" on {night}" if night else "") + ".")
        return
    state.save_ledger()
    state.history_event("filter-corrected", target=target_name,
                        filter=tag or "none", frames=touched, night=night)
    success(f"Recorded filter '{tag or 'no filter'}' on {touched} frame(s) of "
            f"'{target_name}'"
            + (f" ({night})" if night else
               (f" across {len(nights)} night(s)" if nights else "")))
    warn("Reminder: set the filter in the ASIAir app when you swap glass — "
         "filenames only carry what the app is told.")
    state.publish_mirror()


def run_unbaseline(state, target_name):
    if not state.has_ledger():
        error("No ledger.")
        return
    removed = kept = 0
    for relpath in list(state.ledger["files"].keys()):
        e = state.ledger["files"][relpath]
        if e.get("target") == target_name and e.get("origin") == "baseline":
            if e.get("verifiedAtImport"):
                kept += 1   # reconcile PROVED this file is on disk — it stays
                continue
            del state.ledger["files"][relpath]
            removed += 1
    state.save_ledger()
    state.history_event("unbaseline", target=target_name, frames=removed, kept=kept)
    success(f"Removed {removed} unverified baseline entries for '{target_name}'"
            + (f" — kept {kept} verified (reconciled) entries."
               if kept else " (real imports untouched)."))
    if removed:
        info("Those files now count as NEW — the next import copies them properly.")
    state.publish_mirror()

def run_reconcile(state, deep=True):
    """Upgrade baseline/merged entries by comparing camera ↔ destination
    while both copies still exist (spec §2/§7)."""
    if not state.has_ledger():
        error("No ledger — run --baseline first.")
        return
    info("Building destination file index (walks your Astro folders once)...")
    dest_index = {}
    for root, _dirs, fnames in os.walk(DEST_DIR):
        if os.path.abspath(root).startswith(os.path.abspath(LIBRARY_DIR)):
            continue
        for fname in fnames:
            if fname.lower().endswith((".fit", ".fits")):
                dest_index.setdefault(fname, os.path.join(root, fname))
    # Seestar destinations too — baseline entries from the Seestar must be
    # upgradable the same way. MW frames were RENAMED on import
    # (MilkyWay_<dso>_<stamp>.fit) so also index them under their original
    # bare-stamp camera name (stamps are unique per camera).
    for sroot in (SEESTAR_DEST_S30, SEESTAR_DEST_S30_ORIG, SEESTAR_DEST_S50,
                  SEESTAR_DEST_S50PRO):
        if not os.path.isdir(sroot):
            continue
        for root, _dirs, fnames in os.walk(sroot):
            for fname in fnames:
                low = fname.lower()
                # media too: baselined JPEG/video entries must be upgradable,
                # or the every-file SAFE gate blocks them forever (pass-2)
                if not low.endswith((".fit", ".fits", ".jpg", ".jpeg",
                                     ".mp4", ".avi", ".mov")):
                    continue
                if "_thn" in low:
                    continue
                dest_index.setdefault(fname, os.path.join(root, fname))
                if fname.startswith("MilkyWay_"):
                    stm = STAMP_RE.findall(fname)
                    if stm:
                        dest_index.setdefault(stm[-1] + ".fit",
                                              os.path.join(root, fname))

    svol = seestar_volume()
    s_camera = None
    if svol:
        try:
            s_camera = seestar_model(svol)[1]
        except RuntimeError as ex:
            warn(f"Seestar identity unclear ({ex}) — Seestar entries not reconciled")
            svol = None
    upgraded = skipped_archived = failed = 0
    candidates = [(rp, e) for rp, e in state.ledger["files"].items()
                  if e.get("origin") in ("baseline", "merged") and not e.get("verifiedAtImport")]
    info(f"{len(candidates)} baseline/merged entries to reconcile.")
    done = 0
    for relpath, e in candidates:
        done += 1
        show_progress(done, len(candidates), label="Reconciling")
        if e.get("device", "asiair") == "seestar":
            if not svol or _row_camera(e) != s_camera:
                skipped_archived += 1   # only the camera that wrote the row can prove it
                continue
            cam_path = os.path.join(svol, ledger_relpath(relpath))
        else:
            cam_path = os.path.join(ASIAIR_VOLUME, relpath)
        dest_path = dest_index.get(e["filename"])
        if dest_path is None or not os.path.isfile(cam_path):
            skipped_archived += 1
            continue
        try:
            if os.path.getsize(dest_path) != os.path.getsize(cam_path):
                failed += 1
                warn(f"{e['filename']}: size differs camera vs destination — NOT upgraded")
                continue
            if deep:
                cam_sha = _hash_stream(cam_path)
                dst_sha = _hash_stream(dest_path)
                if cam_sha != dst_sha:
                    failed += 1
                    warn(f"{e['filename']}: checksum differs — NOT upgraded")
                    continue
                e["sha256"] = cam_sha
            e["verifiedAtImport"] = True
            e["dest"] = os.path.dirname(dest_path)
            e["reconciledAt"] = now_stamp()
            state._dirty = True
            upgraded += 1
        except OSError as ex:
            failed += 1
            warn(f"{e['filename']}: {ex}")
    state.save_ledger()
    state.history_event("reconcile", upgraded=upgraded,
                        archivedOrMissing=skipped_archived, failed=failed)
    print()
    success(f"Reconcile: {upgraded} upgraded to verified, "
            f"{skipped_archived} unverifiable (archived or off-camera), {failed} mismatches.")
    if skipped_archived:
        info("Archived-before-v2 entries stay honest: 'check your archive before clearing'.")
    state.publish_mirror()


# ═══════════════════════════════════════════════════════════════════════════
# SHIP — file verified frames from this Mac into the archive on the PC (1.4.0)
# ═══════════════════════════════════════════════════════════════════════════
# Ledger-driven: every entry that is verified here and not yet verified on the
# archive is a candidate. The archive's own folder names and Day numbers win;
# a night that already exists there is merged into its Day folder, a new night
# takes the next free number. Copies go through a .partial name, are read back
# from the share and compared to the ledger hash, then the entry is stamped
# archiveLocation + archiveShippedAt. The PC sweep re-hashes on its side and
# appends _verify\verified.jsonl; the next --ship reads that and stamps
# archiveVerifiedAt. Nothing here deletes, overwrites, or touches the camera.

SHIP_ROOTS = {"ZWO Seestar S30 Pro": "S30P", "ZWO Seestar S30": "S30",
              "ZWO Seestar S50": "S50", "ZWO Seestar S50 Pro": "S50P",
              "ZWO ASI585MC Air": "ZWO Askar Scopes"}
SHIP_WORKING = "_Working Files (regenerable - safe to delete)"
_GENERIC_NAMES = {"globular cluster", "open star cluster", "open cluster", "star cluster",
                  "galaxy", "nebula", "planetary nebula"}
_DISPLAY_RE = re.compile(r"^(.+?)\s+-\s+(.+?)(\s+\(mosaic\))?$")
_MAC_DAY_RE = re.compile(r"^(.*?)(?:_sub)? Day (\d+)$")
_E_DAY_RE = re.compile(r"^(.*?)(?:_sub)? Day (\d+)$")

def archive_reachable(mount=None, write_test=True):
    """True when the archive is mounted AND alive. After a PC reboot or power
    cut a stale SMB mount can still list directories from cache while refusing
    every write (seen 19 Sep 2026, PermissionError on makedirs), so the check
    also touches a scratch file under _verify."""
    mount = mount or ARCHIVE_MOUNT
    try:
        if not os.path.isdir(mount) or not any(os.path.isdir(os.path.join(mount, r)) for r in SHIP_ROOTS.values()):
            return False
        if write_test:
            vdir = os.path.join(mount, "_verify")
            _confine(vdir, "the archive probe")
            os.makedirs(vdir, exist_ok=True)
            probe = os.path.join(vdir, f".ship-probe-{os.getpid()}")
            with open(probe, "w") as f:
                f.write(now_stamp())
            os.remove(probe)
        return True
    except OSError:
        return False

def _ship_target_folder(root_dir, display, mosaic):
    """Archive folder for a Mac display name. Prefer a folder that already
    exists on the archive for the same catalogue code; else build one in the
    archive's 'Name (CODE)' form (bare code where the name is generic)."""
    disp = re.sub(r"\s+\(mosaic\)$", "", display or "").strip()
    m = _DISPLAY_RE.match(disp)
    code, name = (m.group(1).strip(), m.group(2).strip()) if m else (disp, "")
    want_suffix = " (mosaic)" if mosaic else ""
    try:
        existing = [d for d in os.listdir(root_dir) if os.path.isdir(os.path.join(root_dir, d))]
    except OSError:
        existing = []
    def _norm(x):
        return re.sub(r"[\s_]+", "", x or "").lower()
    by_name = None
    for d in existing:
        base = d[:-9] if d.endswith(" (mosaic)") else d
        is_m = d.endswith(" (mosaic)")
        if is_m != bool(mosaic):
            continue
        mm = re.match(r"^(.*?)\s*\(([^()]+)\)$", base)
        dcode = mm.group(2).strip() if mm else base.strip()
        dname = mm.group(1).strip() if mm else ""
        if dcode.lower() == code.lower() or base.lower() == disp.lower():
            return d
        # camera token differs from the archive code but the common name is
        # the same: "LDN 1163 - Lion Nebula" -> "Lion Nebula (Sh2-132)"
        if by_name is None and name and dname and _norm(dname) == _norm(name) \
                and _norm(name) not in {_norm(g) for g in _GENERIC_NAMES}:
            by_name = d
        # the archive code appears inside a display that has no separator:
        # "SH2-171 Teddy Bear" -> "Teddy Bear Nebula (Sh2-171)"
        if by_name is None and not name and dcode and len(_norm(dcode)) >= 4 \
                and _norm(dcode) in _norm(disp):
            by_name = d
    if by_name:
        return by_name
    if not name or name.lower() in _GENERIC_NAMES:
        return code + want_suffix
    return f"{name} ({code}){want_suffix}"

def _file_night_any(filename):
    return _seestar_file_night(filename)   # both camera families stamp yyyymmdd-hhmmss

class _DayMap:
    """Night -> Day number for one archive target folder (or mosaic panel folder)."""
    def __init__(self, folder, seestar):
        self.folder, self.seestar = folder, seestar
        self.nights, self.max_n, self.token = {}, 0, None
        try:
            entries = os.listdir(folder)
        except OSError:
            entries = []
        toks = {}
        for d in entries:
            m = _E_DAY_RE.match(d)
            if not m or not os.path.isdir(os.path.join(folder, d)):
                continue
            n = int(m.group(2)); self.max_n = max(self.max_n, n)
            toks[m.group(1)] = toks.get(m.group(1), 0) + 1
            try:
                for fn in os.listdir(os.path.join(folder, d)):
                    nt = _file_night_any(fn)
                    if nt:
                        self.nights.setdefault(nt, n)
            except OSError:
                pass
        if toks:
            self.token = max(toks, key=toks.get)
    def day_for(self, night):
        if night in self.nights:
            return self.nights[night]
        self.max_n += 1
        self.nights[night] = self.max_n
        return self.max_n
    def dirname(self, n, mac_token, target_name):
        if self.seestar:
            return f"{self.token or mac_token}_sub Day {n}"
        return f"{target_name} Day {n}"

def _find_moved_file(dest, filename, size, index):
    """A frame the ledger placed in a Day folder may since have been gathered
    into a flat lights/ folder (Collect Lights, or by hand). Look for it by
    name and size anywhere under the target folder, walking up from the Day
    folder to the first folder that is not a Day/lights/panels level. One
    directory walk per target folder, cached in `index`."""
    d = os.path.normpath(dest)
    for _ in range(3):
        parent = os.path.dirname(d)
        if not parent or parent == d:
            return None
        d = parent
        base = os.path.basename(d)
        if base in ("lights", "panels") or _MAC_DAY_RE.match(base):
            continue
        if d not in index:
            _confine(d, "the moved-frame search")
            idx = {}
            if os.path.isdir(d):
                for root, _dirs, fns in os.walk(d):
                    for fn in fns:
                        idx.setdefault(fn, []).append(os.path.join(root, fn))
            index[d] = idx
        for cand in index[d].get(filename, []):
            try:
                if size is None or os.path.getsize(cand) == size:
                    return cand
            except OSError:
                pass
        return None
    return None

def _is_unshipped_rider(e):
    """A per-sub JPEG preview ledgered by 1.3.x–1.4.1 that no longer ships
    (riders off). 'mw-jpg' also names the Milky Way keeper stack's own JPG —
    that one is a stack preview and keeps shipping."""
    if SEESTAR_IMPORT_SUB_JPEGS:
        return False
    st = e.get("sourceType")
    if st == "sub-jpg":
        return True
    return st == "mw-jpg" and _stack_n(e.get("filename") or "") is None

def only_on_this_machine(state):
    """Frames whose one copy is here: cleared from a camera, verified at
    import, not yet PC-verified on the archive (riders don't ship, so don't count)."""
    if not state.ledger:
        return 0
    return sum(1 for e in state.ledger["files"].values()
               if e.get("clearedFromCamera") and e.get("verifiedAtImport")
               and not e.get("archiveVerifiedAt") and not _is_unshipped_rider(e))

def status_unknown(why="the ledger can't be read"):
    """The status line when it can't be worked out: never "safe" (1.5.3).
    The panel shows it too when computing the line fails."""
    return {"safe": False, "onlyHere": None, "machine": "PC" if IS_WINDOWS else "Mac",
            "text": f"Status unknown: {why}"}

def status_summary(state):
    """The one status line the panel and the app show (1.5.3). Never "safe"
    when the ledger can't be read."""
    machine = "PC" if IS_WINDOWS else "Mac"
    if getattr(state, "ledger_corrupt", False):
        return status_unknown()
    if state.ledger and (state.ledger.get("version") or 0) > LEDGER_VERSION:
        # written by a newer importer: this one can't vouch for its rows
        return status_unknown("the ledger is from a newer version of the importer")
    if not state.ledger:
        return {"safe": True, "onlyHere": 0, "text": "Nothing imported yet",
                "machine": machine}
    n = only_on_this_machine(state)
    text = "Everything is safe" if n == 0 else \
        f"{n:,} frame{'' if n == 1 else 's'} only on {'this PC' if IS_WINDOWS else 'the Mac'}"
    return {"safe": n == 0, "onlyHere": n, "text": text,
            "machine": "PC" if IS_WINDOWS else "Mac"}

def ship_plan(state, mount):
    """Return (items, notes). items: dict(rel, src, entry, key). rel is the
    archive-relative path with the archive's own separators (\\\\)."""
    items, notes = [], []
    daymaps = {}
    _tree_index = {}
    home = os.path.expanduser("~")
    for key, e in state.ledger["files"].items():
        if not e.get("verifiedAtImport") or e.get("archiveVerifiedAt") or e.get("tidiedAt"):
            continue
        cam = e.get("camera") or ("ZWO ASI585MC Air" if e.get("device", "asiair") == "asiair" else "ZWO Seestar S30 Pro")
        root = SHIP_ROOTS.get(cam)
        dest = e.get("dest")
        if not root or not dest or not e.get("filename"):
            continue
        if e.get("origin") == "backfill" or e.get("archivePath"):
            continue   # back-catalogue rows already live in the archive; --repoint owns them
        if _is_unshipped_rider(e):
            continue   # 1.4.2: per-sub JPEG previews are not shipped to the archive
        src = os.path.join(dest, e["filename"])
        if not os.path.isfile(src):
            src = _find_moved_file(dest, e["filename"], e.get("size"), _tree_index)
            if not src:
                if dest.startswith(home):
                    notes.append(("missing on Mac", key))
                continue
        seestar = e.get("device") == "seestar"
        root_dir = os.path.join(mount, root)
        display = e.get("displayName") or e.get("target") or ""
        panel = None
        if not seestar and " · " in display:            # ASIAir mosaic panel
            display, panel = display.rsplit(" · ", 1)
        mosaic = seestar and ("_mosaic" in (e.get("target") or "") or display.endswith("(mosaic)"))
        st = e.get("sourceType") or ""
        base = os.path.basename(dest.rstrip("/"))
        # non-DSO modes live at the root by mode name
        if seestar and base in {n for _, n in SEESTAR_NON_DSO_MAP}:
            rel = os.path.join(root, base, e["filename"])
            items.append({"rel": rel, "src": src, "entry": e, "key": key}); continue
        tfolder = _ship_target_folder(root_dir, display, mosaic)
        tdir = os.path.join(root_dir, tfolder)
        if panel:
            tdir = os.path.join(tdir, panel)
        dm_key = tdir
        if dm_key not in daymaps:
            daymaps[dm_key] = _DayMap(tdir, seestar)
        dm = daymaps[dm_key]
        m = _MAC_DAY_RE.match(base)
        if m and st in ("sub", "sub-jpg", "mw", "Plan", "Live", "panel-day"):
            night = e.get("night") or _file_night_any(e["filename"])
            if not night:
                rel = os.path.join(root, "_UNPLACED", tfolder, e["filename"])
            else:
                n = dm.day_for(night)
                rel = os.path.join(os.path.relpath(tdir, mount), dm.dirname(n, m.group(1), panel or tfolder), e["filename"])
        elif base == "panels":
            rel = os.path.join(os.path.relpath(tdir, mount), "panels", e["filename"])
        elif st in ("stack", "stack-jpg", "mw-stack", "mw-jpg", "media"):
            rel = os.path.join(os.path.relpath(tdir, mount), e["filename"])   # loose at the target root
        elif base == "lights" and st in ("Plan", "Live"):
            # ASIAir tree keeps a lights/ level on the Mac; the archive has none
            night = e.get("night") or _file_night_any(e["filename"])
            n = dm.day_for(night) if night else None
            rel = os.path.join(os.path.relpath(tdir, mount), dm.dirname(n, "", panel or tfolder), e["filename"]) if n \
                  else os.path.join(root, "_UNPLACED", tfolder, e["filename"])
        else:
            rel = os.path.join(SHIP_WORKING, root, tfolder, base, e["filename"])
        items.append({"rel": rel, "src": src, "entry": e, "key": key})
    return items, notes

def _ship_apply_verified(state, mount):
    """Read the PC's verified.jsonl and stamp archiveVerifiedAt on matching entries."""
    vpath = os.path.join(mount, "_verify", "verified.jsonl")
    if not os.path.isfile(vpath):
        return 0
    by_loc = {}
    for k, e in state.ledger["files"].items():
        loc = e.get("archiveLocation")
        if loc and not e.get("archiveVerifiedAt"):
            by_loc[loc.replace("/", "\\").lower()] = e
    n = 0
    with open(vpath, encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if not isinstance(r, dict):
                continue                     # a stray line never stops a ship
            try:
                rsize = int(r.get("size"))
            except (TypeError, ValueError):
                continue
            e = by_loc.get(str(r.get("relpath", "")).replace("/", "\\").lower())
            if e and (e.get("sha256") in (None, r.get("sha256"))) and e.get("size") == rsize:
                e["archiveVerifiedAt"] = r.get("verifiedAt") or now_stamp()
                state._dirty = True; n += 1
    return n

def _try_mount_archive(mount, url, wait=20):
    """Ask Finder to mount the share (password from the keychain). Returns True when
    the archive becomes reachable within `wait` seconds."""
    if TEST_ROOT and url:
        _test_record("mount", url=url)      # never mounted, never waited for
        return False
    if not url or sys.platform != "darwin":
        return False
    try:
        subprocess.run(["open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
    except Exception:
        return False
    for _ in range(wait * 2):
        if archive_reachable(mount):
            return True
        time.sleep(0.5)
    return False

MACHINE_LABEL = "Mac" if IS_MAC else ("PC" if IS_WINDOWS else PLATFORM)
SHIP_LOCK_STALE_S = 6 * 3600

def _archive_ship_lock(mount):
    """One computer ships into the archive at a time (1.5.0). The lock lives
    ON the archive (_verify/ship.lock), so the Mac and the PC see the same one.
    Returns the lock path, or None when another run holds it."""
    path = os.path.join(mount, "_verify", "ship.lock")
    _confine(path, "the archive ship lock")
    me = {"machine": machine_id(), "host": socket.gethostname(), "platform": PLATFORM,
          "pid": os.getpid(), "at": now_stamp()}
    for _ in range(2):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w") as f:
                json.dump(me, f)
            return path
        except FileExistsError:
            try:
                with open(path) as f:
                    held = json.load(f)
            except (OSError, ValueError):
                held = {}
            try:
                age = time.time() - os.path.getmtime(path)
            except OSError:
                continue
            mine_dead = held.get("machine") == me["machine"] and not pid_alive(held.get("pid"))
            if age > SHIP_LOCK_STALE_S or mine_dead:
                warn(f"Clearing a stale archive ship lock ({held.get('host', '?')}, "
                     f"{held.get('at', '?')}).")
                try:
                    os.remove(path)
                except OSError:
                    return None
                continue
            info(f"{held.get('host', 'Another computer')} is shipping into the archive right "
                 f"now (since {held.get('at', '?')}) — nothing shipped; will try next time.")
            return None
        except OSError as e:
            warn(f"Could not take the archive ship lock: {e}")
            return None
    return None

def run_ship(state, dry_run=False, mount=None, checksum=True):
    mount = mount or ARCHIVE_MOUNT
    if not dry_run and archive_reachable(mount):
        lock = _archive_ship_lock(mount)
        if lock is None:
            emit("ship", reachable=True, shipped=0, problems=0, busy=True)
            return False
        try:
            return _run_ship(state, dry_run=dry_run, mount=mount, checksum=checksum)
        finally:
            try:
                os.remove(lock)
            except OSError:
                pass
    return _run_ship(state, dry_run=dry_run, mount=mount, checksum=checksum)

def _run_ship(state, dry_run=False, mount=None, checksum=True):
    mount = mount or ARCHIVE_MOUNT
    if not archive_reachable(mount) and ARCHIVE_URL:
        info(f"Archive not mounted; asking Finder to connect to {ARCHIVE_URL} ...")
        _try_mount_archive(mount, ARCHIVE_URL)
    if not archive_reachable(mount):
        info(f"Archive not reachable at {mount} ({ARCHIVE_LABEL}). Nothing shipped; will try next time.")
        emit("ship", reachable=False)
        return False
    stamped = _ship_apply_verified(state, mount)
    if stamped:
        success(f"{stamped} frame(s) confirmed verified by the PC sweep")
    items, notes = ship_plan(state, mount)
    todo = [i for i in items if not i["entry"].get("archiveShippedAt")]
    waiting = len(items) - len(todo)
    total = sum(i["entry"].get("size") or 0 for i in todo)
    info(f"Ship: {len(todo)} file(s), {human_size(total)} to {ARCHIVE_LABEL}; "
         f"{waiting} already shipped and awaiting the PC sweep")
    for why, key in notes[:10]:
        warn(f"{why}: {key}")
    if len(notes) > 10:
        warn(f"... and {len(notes)-10} more")
    by_target = {}
    for i in todo:
        parts = i["rel"].replace("\\", "/").split("/")
        by_target.setdefault("/".join(parts[:2]), [0, 0])
        by_target["/".join(parts[:2])][0] += 1; by_target["/".join(parts[:2])][1] += i["entry"].get("size") or 0
    for t, (n, b) in sorted(by_target.items()):
        log(f"  {t.replace('/', chr(92))}: {n} file(s), {human_size(b)}")
    if dry_run:
        info("[dry-run] Nothing copied.")
        return True
    vdir = os.path.join(mount, "_verify"); os.makedirs(vdir, exist_ok=True)
    shipped_log = os.path.join(vdir, SHIP_LOG_NAME)   # this machine's own log
    _confine(shipped_log, "the ship log")
    shipped, problems, frames = 0, [], []
    stamp = now_stamp()
    real_mount = _prefix(os.path.realpath(mount))
    for n, i in enumerate(todo, 1):
        e, rel = i["entry"], i["rel"].replace("\\", "/")
        dst = os.path.join(mount, rel)
        if ".." in rel.split("/") or os.path.isabs(rel) \
                or not os.path.realpath(dst).startswith(real_mount):
            # a folder name must never walk a copy out of the archive (V3)
            problems.append((rel, "path leaves the archive folder; not shipped"))
            continue
        _confine(dst, "the ship")        # its folder, .partial and .BAD sit beside it
        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if os.path.isfile(dst):
                if os.path.getsize(dst) == e.get("size"):
                    h = sha256_of(dst) if checksum else None
                    if h is None or e.get("sha256") in (None, h):
                        sha = h or e.get("sha256")
                        status = "already there"
                    else:
                        problems.append((rel, "exists on the archive with different content; left untouched")); continue
                else:
                    problems.append((rel, "exists on the archive with a different size; left untouched")); continue
            else:
                sha, _sz = copy_file_verified(i["src"], dst, checksum=checksum,
                                              partial_suffix=f".{MACHINE_LABEL.lower()}.partial")
                if checksum and e.get("sha256") and sha != e["sha256"]:
                    os.replace(dst, dst + ".BAD")
                    problems.append((rel, "read-back hash differs from the ledger; renamed .BAD")); continue
                status = "shipped"
            loc = rel.replace("/", "\\")
            # the log row FIRST: a frame stamped as shipped but never logged
            # would never be swept, so never verified (1.5.0 review W6)
            with open(shipped_log, "a", encoding="utf-8") as f:
                f.write(json.dumps({"sha256": sha, "size": e.get("size"), "relpath": loc,
                                    "shippedAt": stamp, "machine": MACHINE_LABEL}) + "\n")
            e["archiveLocation"] = loc; e["archiveShippedAt"] = stamp
            if e.get("sha256") is None and sha:
                e["sha256"] = sha
            state._dirty = True
            frames.append({"sha256": sha, "size": e.get("size"), "filename": e["filename"],
                           "location": loc, "status": status})
            shipped += 1
        except OSError as ex:
            problems.append((rel, str(ex)))
            if not archive_reachable(mount):
                warn("Archive stopped responding; stopping this ship run. What shipped is recorded; the rest waits for next time.")
                break
        except Exception as ex:
            problems.append((rel, str(ex)))
        if n % 50 == 0 or n == len(todo):
            show_progress(n, len(todo))
            state.save_ledger()
    state.history_event("ship", shipped=shipped, problems=len(problems))
    state.save_ledger()
    if frames:
        rdir = os.path.join(RECEIPT_BASE, "_ship"); os.makedirs(rdir, exist_ok=True)
        _atomic_write_json(_unique_receipt_path(rdir, f"filed-{stamp}"),
                           {"version": 2, "kind": "filed", "at": stamp, "tool": "astro-import",
                            "machine": MACHINE_LABEL, "archive": ARCHIVE_LABEL,
                            "verifiedBy": f"{MACHINE_LABEL.lower()}-readback",
                            "frames": frames, "problems": problems})
    only_mac = only_on_this_machine(state)
    success(f"Shipped {shipped} file(s). Problems: {len(problems)}. "
            f"Frames cleared from a camera and not yet PC-verified: {only_mac}.")
    for rel, why in problems[:20]:
        warn(f"  {rel}: {why}")
    emit("ship", reachable=True, shipped=shipped, problems=len(problems), onlyMac=only_mac)
    state.publish_mirror()
    return True


_EXPOSURE_TOKEN = re.compile(r"_(\d+(?:\.\d+)?)s_")

def _seestar_sub_seconds(path):
    """Exposure of one Seestar sub: from the filename when the camera writes
    it there (S50 Pro: ..._30.0s_...), else the FITS header."""
    m = _EXPOSURE_TOKEN.search(os.path.basename(path))
    if m:
        return float(m.group(1))
    exp, _n = _sub_meta(path)
    return exp

def describe_seestar_files(paths):
    """Plain-words summary of what a set of camera files actually IS, so
    '1 frame · 47 MB' can never hide 458 subs of integration behind it.
    Returns dict(subs, stacks, best_n, previews, other, seconds, label)."""
    subs = [p for p in paths if p.lower().endswith((".fit", ".fits"))
            and _stack_n(os.path.basename(p)) is None]
    stacks = [p for p in paths if p.lower().endswith((".fit", ".fits"))
              and _stack_n(os.path.basename(p)) is not None]
    jpgs = [p for p in paths if p.lower().endswith((".jpg", ".jpeg"))]
    stems = {}
    for p in jpgs:
        d = os.path.dirname(p)
        if d not in stems:
            try:
                stems[d] = {os.path.splitext(n)[0] for n in os.listdir(d)
                            if n.lower().endswith((".fit", ".fits"))}
            except OSError:
                stems[d] = set()
    previews = [p for p in jpgs
                if os.path.splitext(os.path.basename(p))[0] in stems[os.path.dirname(p)]]
    lone = [p for p in jpgs if p not in set(previews)]
    listed = set(subs) | set(stacks) | set(jpgs)
    other = [p for p in paths if p not in listed]
    secs = None
    if subs:
        # Sum per-file exposures where the filename carries one (a night can
        # mix 10 s and 30 s subs); files without the token are costed from ONE
        # header read, not hundreds over USB on every panel scan.
        tokened = [float(m.group(1)) for m in
                   (_EXPOSURE_TOKEN.search(os.path.basename(p)) for p in subs) if m]
        rest = [p for p in subs if not _EXPOSURE_TOKEN.search(os.path.basename(p))]
        total = sum(tokened)
        if rest:
            per = _seestar_sub_seconds(rest[0])
            total = total + per * len(rest) if per else (total or None)
        secs = total or None
    best_n = max((_stack_n(os.path.basename(p)) for p in stacks), default=None)
    bits = []
    if subs:
        bits.append(f"{len(subs)} sub{'s' if len(subs) != 1 else ''}"
                    + (f" ({integration_label(secs)})" if secs else ""))
    if stacks:
        bits.append(f"{len(stacks)} stack{'s' if len(stacks) != 1 else ''}"
                    + (f" of up to {best_n} subs" if best_n else ""))
    if previews:
        bits.append(f"{len(previews)} JPEG preview{'s' if len(previews) != 1 else ''}")
    if lone:
        bits.append(f"{len(lone)} JPEG{'s' if len(lone) != 1 else ''} with no FIT "
                    f"(the only copy)")
    if other:
        bits.append(f"{len(other)} other file{'s' if len(other) != 1 else ''}")
    return {"subs": len(subs), "stacks": len(stacks), "best_n": best_n,
            "previews": len(previews), "lone_jpegs": len(lone), "other": len(other),
            "seconds": secs,
            "label": " · ".join(bits) or "no files"}

def integration_label(seconds):
    if not seconds:
        return ""
    if seconds < 3570:          # 59.5 min and up reads as hours, never "60 min"
        m = seconds / 60.0
        return f"{m:.0f} min integration" if m >= 10 else f"{m:.1f} min integration"
    return f"{seconds / 3600.0:.1f} h integration"

def seestar_groups(state, s):
    """Everything on a scanned Seestar that can be cleared or discarded as a
    unit, named by its camera folder: DSO targets (the _sub folder plus its
    project folder), mosaic panel sets, and mode folders (Lunar_photo, …).
    `exempt` says whether the SAFE rule's continued-stack exemption applies
    (DSO only — Milky Way, panels and modes keep every file)."""
    out = []
    for t in s["targets"]:
        out.append({"id": t["sub_name"], "name": t["name"], "kind": "target",
                    "display": seestar_display(state, t["project_name"], ask=False),
                    "dirs": [d for d in (t.get("sub_dir"), t.get("project_dir")) if d],
                    "exempt": not t.get("is_mw"), "is_mw": bool(t.get("is_mw")),
                    "skipped": bool(t.get("skipped"))})
    for p in s["panel_sets"]:
        out.append({"id": p["pt_name"], "name": p["mosaic_name"].split("_mosaic")[0],
                    "kind": "panels",
                    "display": seestar_display(state, p["mosaic_name"], ask=False) + " (panels)",
                    "dirs": [p["pt_dir"]], "exempt": False, "is_mw": False,
                    "skipped": False})
    for nd in s["non_dso"]:
        out.append({"id": nd["src_name"], "name": nd["dest_name"], "kind": "mode",
                    "display": f"{nd['dest_name']} — {nd['src_name'].replace('_', ' ')}",
                    "dirs": [nd["src"]], "exempt": False, "is_mw": False,
                    "skipped": False})
    return out


def run_clear(state, group_id):
    """The SAFE clear for one thing on the camera, on demand — the panel's
    "clear…" action (1.4.3; until now the offer only appeared at the end of an
    import, so a declined one could not be reached again from the panel).
    Same every-file gate, same default-No card, same second check at delete
    time. Returns 'cleared' / 'kept' / 'refused'."""
    svol = seestar_volume()
    if not svol:
        error("No Seestar connected. (The ASIAir is never cleared by this tool.)")
        return "refused"
    if not state.has_ledger():
        error("No import ledger yet — nothing can be proven backed up.")
        return "refused"
    try:
        s = scan_seestar(state)
    except RuntimeError as e:
        error(f"Seestar NOT scanned: {e}")
        return "refused"
    if s.get("extra_volumes"):
        error("More than one Seestar is mounted — clear one camera at a time.")
        return "refused"
    state.seestar_seen(s)
    g = next((x for x in seestar_groups(state, s)
              if x["id"].lower() == group_id.strip().lower()), None)
    if not g:
        error(f"Nothing called '{group_id}' on the camera.")
        return "refused"
    n = seestar_safe_cleanup(state, s, [(g["display"], g["dirs"], g["exempt"])])
    state.save_ledger()
    state.publish_mirror()
    return "cleared" if n else "kept"


def run_discard(state, target_name, night=None, reason="", dry_run=False):
    """Delete a Seestar target (or one night of it) from the CAMERA without
    importing it — for the three-frames-before-cloud nights. The one path in
    this tool that destroys frames with no backup, so: Seestar only (the
    ASIAir is the backup of record and is never deleted from), only ever the
    files that are NOT backed up (already-backed-up files are a SAFE cleanup,
    not a discard), typed confirmation, and every file is hashed and recorded in the
    ledger's separate `discarded` register BEFORE it is deleted. Nothing in
    that register ever counts as backed up. When EVERYTHING selected is
    already proven, it hands over to the ordinary SAFE cleanup instead (the
    only other way to reach it is the end of an import). Returns 'done' /
    'cancelled' / 'dry-run' / 'refused' / 'partial' (some files could not be
    removed and are still on the camera) / 'safe' (handed to the SAFE clear,
    declined) / 'cleared' (handed to the SAFE clear, which cleared it). A mix
    of backed-up and never-backed-up files offers only the never-backed-up
    ones (1.4.3)."""
    if not seestar_volume():
        if os.path.isdir(ASIAIR_VOLUME):
            error("Discard is Seestar-only. The ASIAir is the backup of record; "
                  "this tool never deletes from it.")
        else:
            error("No Seestar connected — discard deletes from the camera, so the "
                  "camera has to be plugged in.")
        return "refused"
    if not state.has_ledger():
        # The ledger is what remembers a discard; creating one here would also
        # silently skip the first-run baseline offer. Refuse instead.
        error("No import ledger yet — run your first import (or --baseline) before "
              "discarding. The ledger is what remembers what you binned.")
        return "refused"
    try:
        s = scan_seestar(state)
    except RuntimeError as e:
        error(f"Seestar NOT scanned: {e}")
        return "refused"
    vol = s["volume"]
    _confine(vol, "--discard")
    if not dry_run:
        state.seestar_seen(s)   # settle old records first (crash mid-discard, H5)
    if s.get("extra_volumes"):
        # Two Seestars mounted: the scan above read ONE of them. Deleting
        # unbacked-up frames is not the moment to be unsure which camera.
        error("More than one Seestar is mounted (" + ", ".join(
              [vol] + list(s["extra_volumes"])) + ") — discard works on one camera "
              "at a time. Eject the others and try again. Nothing was touched.")
        return "refused"
    want = target_name.strip().lower()
    # Groups are named by their CAMERA FOLDER ("M 42_sub", "IC 1396_mosaic_pt",
    # "Lunar_photo"), which is unique on the card and is what the panel sends.
    # A typed target or display name can match more than one group (a mosaic
    # and a single-field shot of the same object) — then refuse and list them
    # rather than guess which one to delete (1.4.2).
    groups = seestar_groups(state, s)
    exact = [g for g in groups if g["id"].lower() == want]
    if exact:
        g = exact[0]
    else:
        cands = [g for g in groups if want in (g["name"].lower(), g["display"].lower())]
        if len(cands) > 1:
            error(f"'{target_name}' matches more than one thing on the camera — "
                  f"nothing was touched. Name the camera folder instead:")
            for c in cands:
                info(f"    --discard \"{c['id']}\"   ({c['display']})")
            return "refused"
        g = cands[0] if cands else None
    if not g:
        error(f"No Seestar target called '{target_name}' on the camera.")
        names = sorted({x["name"] for x in groups})
        if names:
            info("Targets on the camera: " + ", ".join(names))
        return "refused"
    t = {"name": g["name"], "is_mw": g["is_mw"]}
    disp = g["display"]
    if night and not re.match(r"^\d{4}-\d{2}-\d{2}$", night):
        error(f"--night wants YYYY-MM-DD (got '{night}').")
        return "refused"

    # Containment: every folder must be a direct child of the camera's
    # MyWorks and every file must really live on the camera volume — a
    # symlink on the card must never steer a delete somewhere else (1.4.2).
    real_mw = os.path.realpath(os.path.join(vol, "MyWorks"))
    _confine(real_mw, "--discard")               # where the deletes really land
    real_vol = _prefix(os.path.realpath(vol))
    dirs, seen_dirs = [], set()
    for d in g["dirs"]:
        if not d or not os.path.isdir(d):
            continue
        rd = os.path.realpath(d)
        if os.path.dirname(rd) != real_mw:
            error(f"{d} does not resolve to a folder inside the camera's MyWorks — "
                  f"refusing to delete anything. Nothing was touched.")
            return "refused"
        if rd not in seen_dirs:
            seen_dirs.add(rd)
            dirs.append(d)
    files, seen_files = [], set()
    for d in dirs:
        for root, _dd, fns in os.walk(d):
            for fn in sorted(fns):
                if fn.startswith("._") or fn == ".DS_Store":
                    continue
                if night and _seestar_file_night(fn) != night:
                    continue
                p = os.path.join(root, fn)
                rp = os.path.realpath(p)
                if os.path.islink(p) or not rp.startswith(real_vol):
                    error(f"{_rel(p, vol)} is a link, or points outside the "
                          f"camera — refusing to delete anything. Nothing was touched.")
                    return "refused"
                if rp in seen_files:
                    continue
                seen_files.add(rp)
                files.append(p)
    if not files:
        info(f"Nothing to discard for {disp}" + (f" on the night of {night}." if night else "."))
        return "refused"

    sizes = {}
    for p in files:
        try:
            sizes[p] = os.path.getsize(p)
        except OSError:
            sizes[p] = None
    # Classify with the SAME gate the SAFE cleanup uses, so the two can never
    # disagree: previews of proven FITs and stacks a verified later stack
    # continues count as proven; camera thumbnails are neutral.
    exempt = g["exempt"]
    proven_paths = []
    _seestar_unproven_files(state, vol, dirs, exempt_superseded=exempt,
                            camera=s["camera"], collect=proven_paths)
    proven_set = {os.path.realpath(p) for p in proven_paths}
    judged = [p for p in files if "_thn" not in os.path.basename(p).lower()]
    proven = [p for p in judged if os.path.realpath(p) in proven_set]
    kept_note = ""
    if proven and len(proven) == len(judged):
        if night:
            error("Everything on that night is already backed up and verified — that is "
                  "a SAFE clear, and SAFE clears whole folders. Nothing was touched.")
            info(f"Run the discard for the whole target ('{t['name']}') and it will "
                 f"offer the SAFE clear instead.")
            return "refused"
        # Nothing here is at risk: hand over to the ordinary SAFE cleanup — the
        # same every-file gate, the same default-No card, camera-scoped flags.
        info(f"Everything in {disp} is already backed up and verified — that's a "
             f"SAFE clear, not a discard.")
        n = seestar_safe_cleanup(state, s, [(disp, dirs, exempt)])
        state.save_ledger()
        state.publish_mirror()
        return "cleared" if n else "safe"
    if proven:
        # A mix — tonight's three cloudy frames on a target whose earlier
        # nights are imported, or stray JPEGs beside imported subs. Offer to
        # bin EXACTLY the never-backed-up files and leave the rest (1.4.3;
        # 1.4.2 refused, which left no way out on the panel).
        files = [p for p in judged if os.path.realpath(p) not in proven_set]
        kept_note = (f"{len(proven)} file(s) that ARE backed up stay on the camera "
                     f"(clear those the SAFE way).")
        info(f"{disp} is a mix: {len(proven)} file(s) already backed up, "
             f"{len(files)} never backed up. Only the never-backed-up files are offered.")
        sizes = {p: sizes.get(p) for p in files}

    desc = describe_seestar_files(files)
    total = sum(sizes.get(p) or 0 for p in files)
    nights = sorted({n for n in (_seestar_file_night(os.path.basename(p)) for p in files) if n})
    scope = s["camera"].replace("ZWO ", "")
    print("───────────────────────────────────────────────────────────────")
    warn(f"DISCARD — {disp} ({scope})" + (f", night of {night}" if night else ""))
    log(f"  {desc['label']}")
    log(f"  {len(files)} file(s), {human_size(total)} on the camera"
        + (f" — night(s): {', '.join(nights)}" if nights else ""))
    warn("These files have NEVER been backed up. Deleting them cannot be undone.")
    if kept_note:
        log(f"  {kept_note}")
    if dry_run:
        for p in files[:12]:
            log(f"    would delete: {_rel(p, vol)}")
        if len(files) > 12:
            log(f"    ... and {len(files) - 12} more")
        info("[dry-run] Nothing deleted.")
        return "dry-run"

    summary = (f"DISCARD {disp} ({scope})" + (f", night of {night}" if night else "")
               + f"\n{desc['label']} — {len(files)} file(s), {human_size(total)}"
               + (f" — night(s): {', '.join(nights)}" if nights else "")
               + "\nThese have NEVER been backed up and cannot be recovered."
               + (f"\n{kept_note}" if kept_note else "")
               + "\nType DISCARD to delete them from the Seestar; anything else cancels.")
    if not ask_typed(summary + "\n> ", "DISCARD"):
        info("Cancelled — nothing deleted.")
        return "cancelled"

    # Hash and RECORD first; only then delete. Every record is written as
    # stillOnCamera=True and flipped only after its delete succeeds, so a
    # crash in between leaves "recorded, still on the camera" (and the scan
    # keeps offering those frames) — never "gone" for something still there.
    stamp = now_stamp()
    reg = state.ledger.setdefault("discarded", {})
    recs, unread = [], 0
    for n_done, p in enumerate(files, 1):
        rel = _rel(p, vol)
        try:
            sha = sha256_of(p)
        except OSError as ex:
            unread += 1
            warn(f"Could not read {os.path.basename(p)} ({ex}) — left on the camera")
            continue
        rec = {"filename": os.path.basename(p), "relpath": rel, "size": sizes[p],
               "sha256": sha, "origin": "discarded", "device": "seestar",
               "camera": s["camera"], "target": t["name"], "displayName": disp,
               "night": _seestar_file_night(os.path.basename(p)),
               "discardedAt": stamp, "reason": reason or "",
               "verifiedAtImport": False, "stillOnCamera": True}
        try:
            rec["cameraMtime"] = os.path.getmtime(p)
        except OSError:
            pass
        reg[f"{rel}|{sizes[p]}"] = rec
        recs.append((p, rec))
        show_progress(n_done, len(files), label="Recording")
    state._dirty = True
    state.save_ledger()

    deleted, deleted_bytes, failed = 0, 0, 0
    for p, rec in recs:
        try:
            os.remove(p)
            rec["stillOnCamera"] = False
            deleted += 1
            deleted_bytes += rec["size"] or 0
        except OSError as ex:
            failed += 1
            warn(f"Could not delete {rec['filename']}: {ex}")
    # folders that now hold nothing but macOS litter go too
    for d in dirs:
        for root, dds, fns in sorted(os.walk(d), key=lambda x: -len(x[0])):
            if all(f.startswith("._") or f == ".DS_Store" for f in fns) and not \
                    [x for x in dds if os.path.isdir(os.path.join(root, x))]:
                if (os.path.realpath(root) + os.sep).startswith(real_mw + os.sep) \
                        and os.path.realpath(root) != real_mw:
                    shutil.rmtree(root, ignore_errors=True)
    state._dirty = True
    state.history_event("discarded", device="seestar", target=t["name"], displayName=disp,
                        frames=deleted, bytes=deleted_bytes, night=night,
                        reason=reason or "", leftOnCamera=failed + unread)
    state.save_ledger()
    if failed or unread:
        warn(f"Discarded {deleted} of {len(files)} file(s), {human_size(deleted_bytes)} — "
             f"{failed + unread} could NOT be removed and are still on the Seestar "
             f"(they will keep showing on the panel). Nothing that was left is "
             f"counted as discarded.")
        state.publish_mirror()
        return "partial"
    success(f"Discarded {deleted} file(s), {human_size(deleted_bytes)} from the Seestar — "
            f"recorded in the ledger as never backed up.")

    if not night and not kept_note and g["kind"] == "target" \
            and t["name"] not in state.skiplist:
        # Worded for what it really does: EVERY future session of this target
        # is ignored, not just a re-shot stray (1.4.3 review — a "yes" at 2 a.m.
        # later hid a real 240-sub night). Default No.
        if safe_input(f"Never import '{t['name']}' again? Every FUTURE session of it "
                      f"would be left on the camera and not backed up — only say yes "
                      f"if you never want this target. [y/N] ", default="n").lower() == "y":
            state.skiplist.append(t["name"])
            state.save_skiplist()
            state.history_event("skiplist", target=t["name"], skipped=True)
            success(f"Never import: {t['name']}")
    state.publish_mirror()
    return "done"

# Settings that mean the same thing on every computer. Paths are NOT among
# them (a Mac path means nothing on Windows) — each machine keeps its own.
PORTABLE_CONFIG_KEYS = ("SEESTAR_IMPORT_SUB_JPEGS", "ASTRO_ARCHIVE_LABEL")

def run_export_settings(state, path=None):
    """Write this machine's SETTINGS (not its ledger) to one JSON file, to
    carry to another computer: custom target names, the never-import list,
    the equipment (scope) table and the portable config keys. 1.5.0."""
    if not path:
        desk = os.path.expanduser(os.path.join("~", "Desktop"))
        if not os.path.isdir(desk):          # e.g. a Desktop redirected to OneDrive
            od = os.path.join(os.environ.get("OneDrive", ""), "Desktop")
            desk = od if os.environ.get("OneDrive") and os.path.isdir(od) \
                else os.path.expanduser("~")
        path = os.path.join(desk, "fits-importer-settings.json")
    path = os.path.expanduser(path)
    _confine(path, "--export-settings")
    try:
        with open(EQUIPMENT_JSON, encoding="utf-8") as f:
            equipment = json.load(f)
    except (OSError, ValueError):
        equipment = None
    bundle = {
        "kind": "brettjoastro-fits-importer-settings", "version": VERSION,
        "exportedAt": now_stamp(), "fromPlatform": PLATFORM,
        "fromHost": socket.gethostname(),
        "customNames": dict(state.custom_names or {}),
        "skiplist": list(state.skiplist or []),
        "equipment": equipment,
        "config": {k: _CONFIG[k] for k in PORTABLE_CONFIG_KEYS if k in _CONFIG},
        "pathsForReference": {k: v for k, v in _CONFIG.items()
                              if k not in PORTABLE_CONFIG_KEYS and not k.startswith("//")},
    }
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    _atomic_write_json(path, bundle)
    success(f"Settings exported → {path}")
    info(f"  {len(bundle['customNames'])} custom name(s), {len(bundle['skiplist'])} "
         f"never-import target(s), equipment table: "
         f"{'yes' if equipment is not None else 'none'}. The ledger is NOT included — "
         f"each computer keeps its own.")
    return path

def run_import_settings(state, path, dry_run=False):
    """Merge settings exported on another computer INTO this one. Adds what
    is missing; never overwrites a name or the equipment table this machine
    already has (differences are listed); never touches the ledger."""
    try:
        with open(os.path.expanduser(path), encoding="utf-8") as f:
            b = json.load(f)
    except (OSError, ValueError) as e:
        error(f"Could not read {path}: {e}")
        return False
    if b.get("kind") != "brettjoastro-fits-importer-settings":
        error(f"{path} is not a FITS Importer settings file.")
        return False
    added_names, clashes = 0, []
    for k, v in (b.get("customNames") or {}).items():
        if k not in state.custom_names:
            if v and clean_target_name(v) is None:
                clashes.append(f"{k}: '{v}' is not a usable folder name — skipped")
                continue
            state.custom_names[k] = v
            added_names += 1
        elif state.custom_names[k] != v:
            clashes.append(f"{k}: kept '{state.custom_names[k]}' (other computer: '{v}')")
    added_skips = [t for t in (b.get("skiplist") or []) if t not in state.skiplist]
    eq_note = "none in the file"
    if b.get("equipment") is not None:
        if os.path.isfile(EQUIPMENT_JSON):
            try:
                with open(EQUIPMENT_JSON, encoding="utf-8") as f:
                    same = json.load(f) == b["equipment"]
            except (OSError, ValueError):
                same = False
            eq_note = "same as here" if same else "this computer's kept (it differs — compare by hand)"
        else:
            eq_note = f"written to {EQUIPMENT_JSON}"
    cfg_added = {k: v for k, v in (b.get("config") or {}).items()
                 if k in PORTABLE_CONFIG_KEYS and k not in _CONFIG}
    info(f"From {b.get('fromHost', '?')} ({b.get('fromPlatform', '?')}, {b.get('version', '?')}):")
    log(f"  custom names: {added_names} added" + (f", {len(clashes)} kept as they are" if clashes else ""))
    for c in clashes[:20]:
        log(f"    {c}")
    log(f"  never-import list: {len(added_skips)} added")
    log(f"  equipment table: {eq_note}")
    log(f"  config: {', '.join(cfg_added) or 'nothing new'} (paths stay this computer's own)")
    if dry_run:
        info("[dry-run] Nothing changed.")
        return True
    if added_names:
        state._save_names()
    if added_skips:
        state.skiplist.extend(added_skips)
        state.save_skiplist()
    if b.get("equipment") is not None and not os.path.isfile(EQUIPMENT_JSON):
        _confine(EQUIPMENT_JSON, "--import-settings")
        os.makedirs(os.path.dirname(EQUIPMENT_JSON), exist_ok=True)
        _atomic_write_json(EQUIPMENT_JSON, b["equipment"])
    if cfg_added:
        cfg = dict(_CONFIG)
        cfg.update(cfg_added)
        _confine(_CONFIG_PATH, "--import-settings")
        os.makedirs(os.path.dirname(_CONFIG_PATH), exist_ok=True)
        _atomic_write_json(_CONFIG_PATH, cfg)
    state.history_event("settings-imported", fromHost=b.get("fromHost"),
                        names=added_names, skips=len(added_skips))
    state.publish_mirror()
    success("Settings imported. The ledger was not touched.")
    return True

def run_tidy_stacks(state, dry_run=False):
    """List archived Seestar stacks outranked by a higher Stacked_N from the
    SAME observing night in the same target folder, and offer to remove them.
    Never automatic: an import only ever adds stacks (1.3.1). Different nights
    are never offered — one keeper per night is the archive rule."""
    candidates = []   # (path, size, winner)
    for sroot in (SEESTAR_DEST_S30, SEESTAR_DEST_S30_ORIG, SEESTAR_DEST_S50,
                  SEESTAR_DEST_S50PRO):
        if not os.path.isdir(sroot):
            continue
        for tdir in sorted(os.listdir(sroot)):
            full = os.path.join(sroot, tdir)
            if not os.path.isdir(full) or tdir.startswith("."):
                continue
            stacks_here = [fn for fn in os.listdir(full)
                           if fn.lower().endswith(".fit") and _stack_n(fn) is not None]
            for fn in stacks_here:
                # outranked only by a CONTINUATION of the same session (1.4.3):
                # a filter change or a restarted stack is its own keeper
                winners = [w for w in stacks_here if _stack_supersedes(w, fn)]
                if not winners:
                    continue
                winner = max(winners, key=lambda w: _stack_n(w))
                pth = os.path.join(full, fn)
                try:
                    size = os.path.getsize(pth)
                except OSError:
                    size = 0
                candidates.append((pth, size, winner, _seestar_file_night(fn) or ""))
    if not candidates:
        success("No superseded same-night stacks found. Nothing to tidy.")
        return
    total = sum(c[1] for c in candidates)
    info(f"{len(candidates)} superseded same-night stack(s), {human_size(total)}:")
    for pth, size, winner, night in candidates:
        log(f"  {os.path.relpath(pth, os.path.dirname(os.path.dirname(pth)))}"
            f"  ({human_size(size)})  outranked on {night or 'unknown night'} by {winner}")
    if dry_run:
        info("[dry-run] Nothing removed.")
        return
    warn("These are the ONLY files this tool will ever offer to delete from "
         "the archive, and only with your say-so. Their JPG siblings go with them. "
         "Ledger entries are kept (marked tidied), never removed.")
    resp = safe_input("Type DELETE to remove them, anything else to keep: ", default="")
    if resp.strip() != "DELETE":
        info("Kept. Nothing removed.")
        return
    stamp = now_stamp()
    removed = 0
    for pth, _size, _winner, _night in candidates:
        _confine(pth, "--tidy-stacks")
        for cand in (pth, pth[:-4] + ".jpg"):
            if os.path.isfile(cand):
                try:
                    os.remove(cand)
                    removed += 1
                except OSError as e:
                    warn(f"Could not remove {cand}: {e}")
        fn = os.path.basename(pth)
        for rp, e in state.ledger["files"].items():
            if e.get("device") == "seestar" and e.get("filename") in (fn, fn[:-4] + ".jpg") \
                    and e.get("dest") == os.path.dirname(pth):
                e["tidiedAt"] = stamp
                state._dirty = True
    state.history_event("tidy-stacks", removed=removed)
    state.save_ledger()
    success(f"Removed {removed} file(s). Ledger entries kept and marked tidied.")


def run_refresh_metadata(state):
    """Back-fill exposure/night/gain/filter/rotation from filenames (using the
    current parsers) and scope from one FITS read per target where the camera
    file is still present. Fixes baseline-era entries recorded before a parser
    improvement — e.g. no-filter filenames (2026-07-25)."""
    if not state.has_ledger():
        error("No ledger.")
        return
    updated = scoped = 0
    for relpath, e in state.ledger["files"].items():
        p = parse_light_filename(e.get("filename", ""))
        if not p:
            continue
        changed = False
        if not e.get("exposureSeconds") and p.get("exposure_seconds"):
            e["exposureSeconds"] = p["exposure_seconds"]; changed = True
        if e.get("gain") is None and p.get("gain_value") is not None:
            e["gain"] = p["gain_value"]; changed = True
        if not e.get("filter") and p.get("filter"):
            e["filter"] = p["filter"]; changed = True
        if not e.get("night") and p.get("capture_datetime"):
            e["night"] = observing_night(p["capture_datetime"]); changed = True
        if e.get("rotation") is None and p.get("rotation") is not None:
            e["rotation"] = p["rotation"]; changed = True
        if changed:
            updated += 1
            state._dirty = True
    if os.path.isdir(ASIAIR_VOLUME):
        lookup = load_equipment_scope_lookup()
        by_target = defaultdict(list)
        for relpath, e in state.ledger["files"].items():
            if not e.get("scope"):
                by_target[e.get("target", "?")].append((relpath, e))
        for target, entries in by_target.items():
            fl = None
            for relpath, _e in entries:
                cam = os.path.join(ASIAIR_VOLUME, relpath)
                if os.path.isfile(cam):
                    fl = read_fits_focallen(cam)
                    if fl:
                        break
            if fl:
                scope = scope_from_focallen(fl, lookup)
                for _relpath, e in entries:
                    if not e.get("scope"):
                        e["scope"] = scope
                        scoped += 1
                        state._dirty = True
    else:
        info("Camera not attached — scope back-fill skipped (re-run with it plugged in).")
    state.save_ledger()
    state.history_event("refresh-metadata", updated=updated, scopeFilled=scoped)
    success(f"Metadata refresh: {updated} entries back-filled from filenames, "
            f"{scoped} scope fields filled from FITS headers.")
    state.publish_mirror()

def run_verify(state, deep=False):
    if not state.has_ledger():
        error("No ledger.")
        return
    checked = ok = bad = archived = 0
    entries = list(state.ledger["files"].items())
    for i, (relpath, e) in enumerate(entries):
        show_progress(i + 1, len(entries), label="Verifying")
        dest_dir = e.get("dest")
        if not dest_dir:
            archived += 1
            continue
        path = os.path.join(dest_dir, e["filename"])
        if not os.path.isfile(path):
            archived += 1
            continue
        checked += 1
        try:
            if os.path.getsize(path) != e.get("size"):
                bad += 1
                warn(f"{e['filename']}: size mismatch at {path}")
                continue
            if deep and e.get("sha256"):
                if _hash_stream(path) != e["sha256"]:
                    bad += 1
                    warn(f"{e['filename']}: checksum mismatch at {path}")
                    continue
            ok += 1
        except OSError as ex:
            bad += 1
            warn(f"{e['filename']}: {ex}")
    print()
    success(f"Verify: {ok} OK, {bad} problems, {archived} archived "
            f"(verified at import — see report).")
    state.history_event("verify", ok=ok, bad=bad, archived=archived, deep=deep)


# ═══════════════════════════════════════════════════════════════════════════
# REPORT
# ═══════════════════════════════════════════════════════════════════════════

def build_report(state):
    lines = []
    def out(s=""):
        lines.append(s)

    asiair_here = os.path.isdir(ASIAIR_VOLUME)
    scan = scan_camera(state) if asiair_here else {"targets": [], "calibration": [],
                                                   "relpaths": set(), "disk": None}
    if asiair_here:
        state.mark_cleared(scan["relpaths"])
        if scan["disk"]:
            state.ledger["lastCameraDisk"] = scan["disk"]
    state.ledger["lastScanAt"] = now_stamp()
    state._dirty = True

    safe, unverified, notsafe, skipped = [], [], [], []
    display_counts = defaultdict(int)
    for t in scan["targets"]:
        display_counts[display_name_for(state, t["name"])] += 1
    for target in scan["targets"]:
        name = target["name"]
        display = display_name_for(state, name)
        if display_counts[display] > 1:
            display = f"{display} ({target['source_label']})"
        if target["skipped"]:
            skipped.append((display, target))
            continue
        entries = []
        missing = []
        for f in target["files"]:
            e = state.file_entry(f["relpath"])
            if e is None or state.is_imported(f["relpath"], f["size"]) != "yes":
                missing.append(f)
            else:
                entries.append(e)
        all_verified = entries and all(e.get("verifiedAtImport") for e in entries)
        if missing:
            notsafe.append((display, target, entries, missing, "unimported"))
            cat = "notsafe"
        elif not all_verified:
            unverified.append((display, target, entries))
            cat = "unverified"
        else:
            safe.append((display, target, entries))
            cat = "safe"
        state.ledger.setdefault("lastCategories", {})[name] = {
            "category": cat, "files": len(target["files"]),
            "bytes": target["total_bytes"],
        }
    state.ledger["lastReportAt"] = now_stamp()
    state._dirty = True

    def day_lines(entries):
        by_day = defaultdict(list)
        for e in entries:
            by_day[e.get("dayNumber") or 0].append(e)
        rows = []
        for day in sorted(by_day):
            es = by_day[day]
            n_ver = sum(1 for e in es if e.get("verifiedAtImport"))
            integ = sum((e.get("exposureSeconds") or 0) for e in es)
            scope = next((e.get("scope") for e in es if e.get("scope")), "?")
            date = min((e.get("night") or e.get("importedAt", ""))[:10] for e in es)
            tag = "✓ verified" if n_ver == len(es) else f"{n_ver}/{len(es)} verified"
            label = f"Day {day}" if day else "baseline-era"
            rows.append(f"      {label:<12} {date:<11} {scope:<14} {len(es)} frames {tag}   {human_hours(integ)}")
        return rows

    out("BrettjoAstro FITS Importer — BACKUP REPORT — " + now_stamp())
    out("═" * 63)
    out()
    # This first block is the ASIAIR's (the Seestar has its own section
    # below) — labelled, so it can't contradict the Seestar rows (review S5)
    if asiair_here:
        out("ASIAIR — SAFE TO CLEAR  (every frame imported + verified; clear these "
            "on the ASIAir yourself — this tool never deletes from it)")
    else:
        out("ASIAIR — not connected (SAFE TO CLEAR needs the camera; Seestar below)")
    reclaim = 0
    if not safe and asiair_here:
        out("  (none on the ASIAir right now)")
    for display, target, entries in sorted(safe, key=lambda x: -x[1]["total_bytes"]):
        integ = sum((e.get("exposureSeconds") or 0) for e in entries)
        out(f"  {display:<44} {len(target['files'])} files  "
            f"{human_size(target['total_bytes'])}  {human_hours(integ)}")
        lines.extend(day_lines(entries))
        reclaim += target["total_bytes"]
    out(f"{'':>50}─────────")
    out(f"{'':>40}{human_size(reclaim)} reclaimable")
    out()
    if unverified:
        out("BACKED UP, UNVERIFIED  (in the ledger, never byte-compared)")
        for display, target, entries in unverified:
            archived = not any(os.path.isfile(os.path.join(e.get("dest") or "", e["filename"]))
                               for e in entries if e.get("dest"))
            out(f"  {display:<44} {len(target['files'])} files  {human_size(target['total_bytes'])}")
            lines.extend(day_lines(entries))
            if archived:
                out("      → recommendation: archived before v2 — check your archive before clearing")
            else:
                out("      → recommendation: run --reconcile while the Mac copies still exist")
        out()
    if notsafe:
        out("NOT SAFE")
        for display, target, entries, missing, _why in notsafe:
            out(f"  {display:<44} {len(target['files'])} files  {human_size(target['total_bytes'])}")
            lines.extend(day_lines(entries))
            miss_bytes = sum(f["size"] for f in missing)
            out(f"      not yet imported: {len(missing)} frames   {human_size(miss_bytes)}")
            out(f"      → recommendation: import the {len(missing)} new frames; "
                f"target then clears {human_size(target['total_bytes'])}")
        out()
    if skipped:
        out("NEVER-IMPORT (excluded from backup accounting)")
        for display, target in skipped:
            out(f"  {display:<44} {human_size(target['total_bytes'])}")
        out()

    # Autorun verdict (spec §6)
    cal = scan["calibration"]
    unparse = scan.get("cal_unparseable") or []
    if cal or unparse:
        n_ok = 0
        for c in cal:
            e = state.cal_entry(c["relpath"])
            if e and e.get("libraryPath") and e.get("verifiedAtImport"):
                n_ok += 1
        cal_bytes = sum(c["size"] for c in cal)
        if unparse:
            # Files the Library can never ingest are files we can never prove
            # backed up — they force NOT SAFE, and they get named.
            verdict = (f"NOT SAFE — {len(unparse)} file(s) this tool cannot "
                       f"ingest (unrecognised names)")
        elif n_ok == len(cal):
            verdict = "SAFE TO CLEAR"
        else:
            verdict = f"NOT SAFE — {len(cal) - n_ok} frame(s) not yet verified in Library"
        out(f"Autorun/ calibration: {len(cal)} frames, {human_size(cal_bytes)} — "
            f"{n_ok} in Library ✓ → {verdict}")
        for fn in unparse[:6]:
            out(f"      unrecognised, NOT backed up by this tool: {fn}")
        if len(unparse) > 6:
            out(f"      … and {len(unparse) - 6} more")
    lib_ok = os.path.isdir(LIBRARY_DIR)
    ever_ingested = any(e.get("libraryPath") for e in state.ledger["calibration"].values())
    if not asiair_here:
        pass
    elif lib_ok:
        n_lib, b_lib = 0, 0
        for root, _d, fnames in os.walk(LIBRARY_DIR):
            for fn in fnames:
                if fn.lower().endswith((".fit", ".fits")):
                    n_lib += 1
                    try:
                        b_lib += os.path.getsize(os.path.join(root, fn))
                    except OSError:
                        pass
        out(f"Calibration Library: OK ({n_lib} files, {human_size(b_lib)})")
    elif ever_ingested:
        out("⚠ Calibration Library MISSING at expected location — was it moved/archived?")
    else:
        out("Calibration Library: not created yet — the first import run will back up "
            "every calibration frame into it.")
    if scan["disk"]:
        d = scan["disk"]
        out(f"Camera: {human_size(d['used'])} used / {human_size(d['total'])} "
            f"({human_size(d['free'])} free) — clearing all SAFE items frees {human_size(reclaim)}")
    out()

    # ── Seestar section (unification) ────────────────────────────────────
    try:
        sscan = scan_seestar(state)
    except RuntimeError as e:
        sscan = None
        out(f"SEESTAR — NOT scanned: {e}")
        out()
    if sscan:
        state.seestar_seen(sscan)
        if sscan["disk"]:
            state.ledger["lastSeestarDisk"] = sscan["disk"]
            state._dirty = True
        out(f"SEESTAR {sscan['model']}")
        groups = [(seestar_display(state, t["project_name"]),
                   t["name"], t["files"] + t["stacks"],
                   [t["sub_dir"], t["project_dir"]], not t.get("is_mw"))
                  for t in sscan["targets"]]
        groups += [(seestar_display(state, p["mosaic_name"]) + " (panels)",
                    p["mosaic_name"].split("_mosaic")[0], p["files"],
                    [p["pt_dir"]], False)
                   for p in sscan["panel_sets"]]
        groups += [(n["dest_name"], n["dest_name"], n["files"],
                    [n["src"]], False) for n in sscan["non_dso"]]
        for display, tname, files, gdirs, exempt_sup in groups:
            if not files:
                continue
            entries, missing = [], 0
            all_ok = True
            for f in files:
                e = state.file_entry(f["relpath"], sscan["camera"])
                if e is None or state.is_imported(f["relpath"], f["size"],
                                                  sscan["camera"]) != "yes":
                    missing += 1
                    all_ok = False
                else:
                    entries.append(e)
                    if not e.get("verifiedAtImport"):
                        all_ok = False
            b = sum(f["size"] for f in files)
            if missing:
                cat, mark = "notsafe", f"NOT SAFE — {missing} file(s) not yet imported"
            elif all_ok:
                cat, mark = "safe", "✓ SAFE TO CLEAR"
            else:
                cat, mark = "unverified", "backed up, unverified (baseline-era)"
            if cat == "safe":
                # The report's SAFE must mean what the cleanup gate's SAFE
                # means: EVERY file in the folder proven, not just the
                # scanned frame classes (pass-2 finding)
                unproven, _pb = _seestar_unproven_files(
                    state, sscan["volume"], gdirs, exempt_superseded=exempt_sup,
                    camera=sscan["camera"])
                if unproven:
                    cat = "notsafe"
                    mark = (f"NOT SAFE — {len(unproven)} file(s) not proven "
                            f"backed up (e.g. {unproven[0]})")
            out(f"  {display:<44} {len(files)} files  {human_size(b)}  {mark}")
            state.ledger.setdefault("lastCategories", {})[f"seestar:{tname}"] = {
                "category": cat, "files": len(files), "bytes": b}
            state._dirty = True
        for u in sscan.get("unhandled", []):
            out(f"  ⚠ ON CAMERA, NOT handled by this tool: {u['name']} "
                f"({u['files']} file(s)) — in no backup accounting above")
        for xv in sscan.get("extra_volumes", []):
            out(f"  ⚠ Another Seestar is mounted at {xv} — one camera at a time")
        if sscan["disk"]:
            d = sscan["disk"]
            out(f"Seestar storage: {human_size(d['used'])} used / {human_size(d['total'])} "
                f"({human_size(d['free'])} free)")
        out()

    # Recently cleared
    cleared = defaultdict(lambda: {"frames": 0, "scope": set(), "when": ""})
    for e in state.ledger["files"].values():
        if e.get("clearedFromCamera"):
            c = cleared[e.get("displayName") or e.get("target")]
            c["frames"] += 1
            if e.get("scope"):
                c["scope"].add(e["scope"])
            c["when"] = max(c["when"], e.get("clearedNoticedAt", ""))
    if cleared:
        out("Recently cleared from camera (ledger keeps their history):")
        for name, c in sorted(cleared.items(), key=lambda x: -len(x[1]["when"])):
            scopes = ", ".join(sorted(c["scope"])) or "?"
            out(f"  {name} — {c['frames']} frames, {scopes} — noticed gone {c['when'][:10]}")
        out()

    disc = state.ledger.get("discarded") or {}
    if disc:
        by = defaultdict(lambda: {"n": 0, "bytes": 0, "when": "", "reason": "",
                                  "nights": set()})
        still = 0
        for rec in disc.values():
            if rec.get("stillOnCamera"):
                still += 1      # recorded, but the delete never happened
                continue
            b = by[rec.get("displayName") or rec.get("target") or "?"]
            b["n"] += 1
            b["bytes"] += rec.get("size") or 0
            if rec.get("night"):
                b["nights"].add(rec["night"])
            if rec.get("discardedAt", "") >= b["when"]:
                b["when"], b["reason"] = rec.get("discardedAt", ""), rec.get("reason") or ""
        out("Deliberately discarded from camera (NEVER backed up — by your choice):")
        for name, b in sorted(by.items(), key=lambda kv: kv[1]["when"], reverse=True):
            why = f' — "{b["reason"]}"' if b["reason"] else ""
            shot = (f", shot {', '.join(sorted(b['nights']))}" if b["nights"] else "")
            out(f"  {name} — {b['n']} file(s), {human_size(b['bytes'])}{shot}, "
                f"binned {b['when'][:10]}{why}")
        if still:
            out(f"  ({still} file(s) recorded for discard but NOT deleted — still on the "
                f"camera, still offered for import)")
        out()

    tail = state.history_tail(5)
    if tail:
        out("Recent events:")
        for ev in tail:
            out(f"  {ev.get('ts', '')}  {ev.get('event', ''):<18} "
                f"{ev.get('target', ev.get('frames', ''))}")
    return "\n".join(lines)

def run_report(state):
    # NOTE: the CLI already holds the import lock here — main() wraps every
    # non-scan-only command in acquire_lock(). The panel takes the same lock
    # for its report op, so ledger saves can never race an import.
    text = build_report(state)
    print(text)
    try:
        with open(state.report_path, "w") as f:
            f.write(text + "\n")
    except OSError:
        pass
    state.save_ledger()
    state.publish_mirror()


# ═══════════════════════════════════════════════════════════════════════════
# SEESTAR ADAPTER (S30 Pro / S30 / S50 / S50 Pro) — ported from seestar-import.sh
# Backup-first + SAFE-aware cleanup (unification spec, agreed 2026-07-25).
# Layout preserved exactly: Day folders in the display root ("<sub> Day N"),
# highest stack kept in the root, panels/ for _mosaic_pt, MW pairing intact.
# ═══════════════════════════════════════════════════════════════════════════

def _volumes_named_seestar():
    """Every mounted /Volumes entry that looks like a Seestar (name starts
    'Seestar', any case — macOS mounts a second unit as 'Seestar 1', and a
    future model may bring its own name) and actually carries MyWorks."""
    out = []
    if IS_WINDOWS or TEST_ROOT or os.environ.get("ASTRO_DRIVE_ROOTS") is not None:
        # Windows: a Seestar is any drive letter carrying MyWorks\ (labels
        # vary by firmware; what is ON the card is what makes it a Seestar).
        # Test mode never lists the real /Volumes.
        return sorted(r for r in _drive_roots()
                      if os.path.isdir(os.path.join(r, "MyWorks")))
    try:
        names = sorted(os.listdir("/Volumes"))
    except OSError:
        return out
    for n in names:
        p = os.path.join("/Volumes", n)
        if n.lower().startswith("seestar") and \
                os.path.isdir(os.path.join(p, "MyWorks")):
            out.append(p)
    return out

def seestar_volume():
    for v in SEESTAR_VOLUMES:
        if os.path.isdir(os.path.join(v, "MyWorks")):
            return v
    named = _volumes_named_seestar()
    return named[0] if named else None

def seestar_extra_volumes(primary):
    """Other Seestar volumes mounted besides the one being scanned — the
    one-camera-at-a-time rule should be announced, never silent."""
    return [p for p in _volumes_named_seestar()
            if os.path.realpath(p) != os.path.realpath(primary or "")]

def _seestar_creator_model(creator):
    """Map one FITS CREATOR string to a Seestar model.
    Returns None for an empty/absent header, '?' for a non-empty string that
    matches no known camera. Spacing/case/dash variants all read the same
    ("Seestar S50 Pro", "SeestarS50Pro", "SEESTAR_S50-PRO"); Pro variants are
    checked BEFORE bare models (the original-S30 lesson, applied to the S50
    family), and each token must END cleanly so "S50 PROTOTYPE" can never
    pass as an S50 Pro."""
    norm = re.sub(r"[\s_\-]+", "", str(creator or "")).upper()
    if not norm:
        return None
    for token, model in (("S50PRO", "S50 Pro"), ("S50", "S50"),
                         ("S30PRO", "S30 Pro"), ("S30", "S30")):
        if re.search(re.escape(token) + r"(?=$|[^A-Z0-9])", norm):
            return model
    return "?"

def seestar_model(vol):
    return seestar_model_ex(vol)[:3]

def seestar_model_ex(vol):
    """('S30 Pro'|'S30'|'S50'|'S50 Pro', camera_name, dest_root, guessed).
    `guessed` is True when no FITS header could vote and the model came from
    folder names alone — never trusted to flag another camera's rows (H7).

    Identity is read from FITS CREATOR headers — one vote per top-level
    MyWorks folder, because one stale leftover project from another camera
    must not classify the whole volume (os.walk order is arbitrary). Two
    different identities, or an identity this tool does not know, REFUSE the
    scan: a misfiled import writes a wrong camera into a ledger that never
    forgets. Mode-folder fallback (no readable FITS anywhere) uses S50-only
    modes (NOT Lunar — the S30 Pro shoots Lunar too); a FITS-less volume
    cannot tell an S50 Pro from an S50 and falls back to plain S50."""
    myworks = os.path.join(vol, "MyWorks")
    votes = {}          # model -> first folder that voted for it
    raw = {}            # model -> the raw CREATOR string behind the vote
    entries = sorted(os.listdir(myworks)) if os.path.isdir(myworks) else []
    for entry in entries:
        edir = os.path.join(myworks, entry)
        if entry.startswith(".") or not os.path.isdir(edir):
            continue
        creator = None
        # Filter AppleDouble litter BEFORE taking the sample — ._*.fit sorts
        # ahead of real data and must not burn the tries (pass-2 finding)
        cands = [p for p in _fits_files(edir)
                 if not os.path.basename(p).startswith("._")][:3]
        for p in cands:
            try:
                creator = str(get_fits().getheader(p).get("CREATOR", ""))
                break
            except Exception:
                continue
        m = _seestar_creator_model(creator)
        if m is not None:
            votes.setdefault(m, entry)
            raw.setdefault(m, creator)
    # Loose FITs at the MyWorks root vote too (refuse-don't-guess doctrine)
    loose = [os.path.join(myworks, f) for f in entries
             if f.lower().endswith(".fit") and not f.startswith("._")
             and not f.startswith(".")
             and os.path.isfile(os.path.join(myworks, f))][:3]
    for p in loose:
        try:
            creator = str(get_fits().getheader(p).get("CREATOR", ""))
        except Exception:
            continue
        m = _seestar_creator_model(creator)
        if m is not None:
            votes.setdefault(m, "(MyWorks root)")
            raw.setdefault(m, creator)
            break
    known = sorted(m for m in votes if m != "?")
    if len(known) > 1:
        raise RuntimeError(
            "two different Seestar identities on one volume — "
            + "; ".join(f"'{raw[m]}' in {votes[m]}/ → {m}" for m in known)
            + ". Mixed leftovers from another camera? Nothing was imported — "
            "sort the card out first (one camera's files per volume).")
    if "?" in votes:
        raise RuntimeError(
            f"unrecognised Seestar identity '{raw['?']}' (in {votes['?']}/). "
            "Refusing to guess a destination tree — the ledger would remember "
            "a wrong camera forever. This importer needs updating for that model.")
    guessed = not known
    if known:
        model = known[0]
    elif any(os.path.isdir(os.path.join(myworks, m)) for m in SEESTAR_S50_ONLY_MODES):
        model = "S50"
    else:
        model = "S30 Pro"
    camera = f"ZWO Seestar {model}"
    dest = {"S30 Pro": SEESTAR_DEST_S30,
            "S30": SEESTAR_DEST_S30_ORIG,
            "S50": SEESTAR_DEST_S50,
            "S50 Pro": SEESTAR_DEST_S50PRO}[model]
    return model, camera, dest, guessed

def _stamp(name):
    m = STAMP_RE.findall(name)
    return m[-1] if m else None

def _stamp_dt(stamp):
    try:
        return datetime.strptime(stamp, "%Y%m%d-%H%M%S")
    except (ValueError, TypeError):
        return None

def seestar_display(state, project_name, ask=False, dry_run=False):
    """Port of bash get_display_name: strip _mosaic, isolate the catalogue ID,
    HIP remap, DSO/custom lookup, '(mosaic)' suffix."""
    is_mosaic = "_mosaic" in project_name
    catalog = project_name.split("_mosaic")[0]
    m = SEESTAR_CATALOG_RE.match(catalog)
    stripped = m.group(1) if m else catalog
    stripped = SEESTAR_HIP_REMAP.get(stripped, stripped)
    display = get_display_name(state, stripped, ask=ask, dry_run=dry_run)
    if is_mosaic:
        display += " (mosaic)"
    return display

def _fits_files(d, maxdepth=None):
    out = []
    if not os.path.isdir(d):
        return out
    if maxdepth == 1:
        for fn in sorted(os.listdir(d)):
            if fn.lower().endswith(".fit") and "_thn" not in fn.lower():
                out.append(os.path.join(d, fn))
        return out
    for root, _dd, fnames in os.walk(d):
        for fn in sorted(fnames):
            if fn.lower().endswith(".fit") and "_thn" not in fn.lower():
                out.append(os.path.join(root, fn))
    return out

def scan_seestar(state):
    vol = seestar_volume()
    if not vol:
        return None
    model, camera, dest_root, guessed = seestar_model_ex(vol)
    myworks = os.path.join(vol, "MyWorks")
    relset = set()

    def fentry(path):
        rel = _rel(path, vol)
        relset.add(rel)
        try:
            st = os.stat(path)
        except OSError:
            return None
        return {"path": path, "relpath": rel, "filename": os.path.basename(path),
                "size": st.st_size, "mtime": st.st_mtime}

    discarded = (state.ledger.get("discarded") or {}) if state.has_ledger() else {}

    def binned(f, rec):
        """Brett binned exactly THESE bytes from THIS camera (1.4.2). Path and
        size alone are not identity — a re-used stamp can bring a new frame
        of the same size to the same path (1.4.3, H11), and a camera whose
        clock repeated would repeat the mtime too — so the SHA-256 recorded
        before deletion has to match. Only files that re-appear at a binned
        path are ever hashed here, which is rare."""
        if not rec or rec.get("stillOnCamera") or rec.get("camera") != camera:
            return False
        try:
            return sha256_of(f["path"]) == rec.get("sha256")
        except OSError:
            return False

    def is_new(f):
        if binned(f, discarded.get(f"{f['relpath']}|{f['size']}")):
            return False
        if not state.has_ledger():
            return True
        if state.is_imported(f["relpath"], f["size"], camera) != "yes":
            return True
        # same path + size but the camera re-saved it since import (H4)
        return _camera_changed(state.file_entry(f["relpath"], camera), f.get("mtime"))

    targets, panel_sets, non_dso = [], [], []
    consumed = set()   # top-level MyWorks names the scan actually understands
    orphan_notes = []  # (sub folder, n) — JPEGs with no FIT twin, reported below
    entries = sorted(os.listdir(myworks)) if os.path.isdir(myworks) else []

    for entry in entries:
        if not entry.endswith("_sub"):
            continue
        sub_dir = os.path.join(myworks, entry)
        if not os.path.isdir(sub_dir):
            continue
        base = entry[:-4]
        if not base.strip() or base.startswith("."):
            # "_sub" or ".._sub" is no target — left unhandled (".." once
            # made the card root a project dir, 1.4.3 review finding V4)
            continue
        consumed.add(entry)
        project_dir = project_name = None
        # EXACT name match only — startswith() once let "M 8_sub" adopt the
        # unrelated "M 81" project dir and rewrite its stack's ledger target
        # (pass-2 finding; mosaic names already carry _mosaic in `base`)
        cpath = os.path.join(myworks, base)
        if base and os.sep not in base and not base.endswith(("_sub", "_mosaic_pt")) \
                and os.path.isdir(cpath):
            project_dir, project_name = cpath, base
            consumed.add(base)
        subs = [x for x in (fentry(p) for p in _fits_files(sub_dir)) if x]
        stacks = [x for x in (fentry(p) for p in _fits_files(project_dir, maxdepth=1)) if x] \
            if project_dir else []
        if project_dir:
            # Register the stacks' JPG siblings in the relpath set: they are
            # ledgered on import, and a relpath missing from the scan would
            # let mark_cleared falsely flag them as gone (pass-2 finding)
            for fn in sorted(os.listdir(project_dir)):
                lowfn = fn.lower()
                if lowfn.endswith((".jpg", ".jpeg")) and "_thn" not in lowfn \
                        and not fn.startswith("._"):
                    fentry(os.path.join(project_dir, fn))
        # Per-sub JPEG previews (the S50 Pro writes one beside every sub —
        # first light 2026-09-05). Always collected, so their relpaths stay in
        # the scan set and already-ledgered riders are never falsely flagged
        # "cleared from camera". Only offered as NEW work when riders are
        # enabled (SEESTAR_IMPORT_SUB_JPEGS, off by default since 1.4.2).
        jpgs = []
        for fn in sorted(os.listdir(sub_dir)):
            lowfn = fn.lower()
            if lowfn.endswith((".jpg", ".jpeg")) and "_thn" not in lowfn \
                    and not fn.startswith("._"):
                fe = fentry(os.path.join(sub_dir, fn))
                if fe:
                    jpgs.append(fe)
        # A preview with no FIT beside it cannot be a rider (nothing to ride
        # on) and is not a preview of anything proven — it is the only copy of
        # whatever it shows. Never silent: reported as NOT handled (1.4.2).
        fit_stems = {os.path.splitext(fn)[0] for fn in os.listdir(sub_dir)
                     if fn.lower().endswith((".fit", ".fits"))}
        orphans = [f for f in jpgs
                   if os.path.splitext(f["filename"])[0] not in fit_stems and is_new(f)]
        if orphans:
            orphan_notes.append((entry, len(orphans)))
        twinned = [f for f in jpgs if os.path.splitext(f["filename"])[0] in fit_stems]
        is_mw = base == "MilkyWay" or base.startswith("MilkyWay_")
        targets.append({
            "device": "seestar", "name": base, "sub_name": entry,
            "sub_dir": sub_dir, "project_dir": project_dir,
            "project_name": project_name or base, "is_mw": is_mw,
            "files": subs, "new": [f for f in subs if is_new(f)],
            "stacks": stacks, "new_stacks": [f for f in stacks if is_new(f)],
            "jpgs": jpgs,
            "new_jpgs": ([f for f in twinned if is_new(f)]
                         if SEESTAR_IMPORT_SUB_JPEGS else []),
            "skipped": base in state.skiplist,
        })

    # Stack-only projects: sub-frame saving is OFF by default on Seestars, so
    # a first night at stock settings produces project dirs with Stacked_*.fit
    # and no _sub sibling. They import through the same path — display naming,
    # keep-highest, JPG rider (pass-2 finding). MilkyWay stack-only dirs are
    # deliberately NOT adopted (their multi-session keepers don't fit the
    # keep-highest rule) and stay visibly "NOT handled" instead.
    _mode_names = set(x for x, _ in SEESTAR_NON_DSO_MAP)
    for entry in entries:
        if entry in consumed or entry.startswith(".") or entry.endswith("_sub") \
                or entry.endswith("_mosaic_pt") or entry in _mode_names \
                or entry == "MilkyWay" or entry.startswith("MilkyWay_"):
            continue
        edir = os.path.join(myworks, entry)
        if not os.path.isdir(edir):
            continue
        st_files = [x for x in (fentry(p) for p in _fits_files(edir, maxdepth=1)) if x]
        if not any(re.match(r"^Stacked_\d+_", f["filename"]) for f in st_files):
            for f in st_files:
                relset.discard(f["relpath"])   # not adopted — stays unhandled
            continue
        consumed.add(entry)
        for fn in sorted(os.listdir(edir)):
            lowfn = fn.lower()
            if lowfn.endswith((".jpg", ".jpeg")) and "_thn" not in lowfn \
                    and not fn.startswith("._"):
                fentry(os.path.join(edir, fn))
        targets.append({
            "device": "seestar", "name": entry, "sub_name": entry,
            "sub_dir": None, "project_dir": edir,
            "project_name": entry, "is_mw": False,
            "files": [], "new": [],
            "stacks": st_files, "new_stacks": [f for f in st_files if is_new(f)],
            "jpgs": [], "new_jpgs": [],
            "skipped": entry in state.skiplist,
        })

    for entry in entries:
        if not entry.endswith("_mosaic_pt"):
            continue
        pt_dir = os.path.join(myworks, entry)
        if not os.path.isdir(pt_dir):
            continue
        consumed.add(entry)
        files = [x for x in (fentry(p) for p in _fits_files(pt_dir, maxdepth=1)) if x]
        panel_sets.append({"pt_name": entry, "pt_dir": pt_dir,
                           "mosaic_name": entry[:-3],  # strip "_pt"
                           "files": files, "new": [f for f in files if is_new(f)]})

    # Non-DSO modes are scanned on EVERY model — an S30 Pro shoots Lunar too,
    # and "backup-first" means whatever is on the card gets offered, not just
    # the modes the model is marketed on (1.3.0 review finding).
    for src_name, dest_name in SEESTAR_NON_DSO_MAP:
        src = os.path.join(myworks, src_name)
        if not os.path.isdir(src):
            continue
        consumed.add(src_name)
        # _photo modes save JPEG siblings next to the FITs — back those up
        # too, or the SAFE gate could never honestly clear the folder.
        exts = ((".mp4", ".avi", ".mov") if src_name.endswith("_video")
                else (".fit", ".jpg", ".jpeg"))
        files = []
        for fn in sorted(os.listdir(src)):
            if fn.lower().endswith(exts) and "_thn" not in fn.lower():
                fe = fentry(os.path.join(src, fn))
                if fe:
                    files.append(fe)
        if files:
            non_dso.append({"src": src, "src_name": src_name, "dest_name": dest_name,
                            "files": files, "new": [f for f in files if is_new(f)]})

    # Anything else in MyWorks is data this tool does NOT understand — a new
    # firmware folder, a wide-camera product, a stack-only project. Never be
    # silent about it: it is on the camera and NOT backed up by this tool.
    unhandled = []
    for entry in entries:
        if entry in consumed or entry.startswith("._") or entry == ".DS_Store":
            continue
        if entry.startswith(".") and not entry.endswith("_sub"):
            continue   # hidden system folders; a dot-named "_sub" IS reported
        epath = os.path.join(myworks, entry)
        if os.path.isdir(epath):
            n = 0
            for _r, _dd, fnames in os.walk(epath):
                n += sum(1 for fn in fnames
                         if not fn.startswith(".") and not fn.startswith("._"))
            unhandled.append({"name": entry + "/", "files": n})
        else:
            unhandled.append({"name": entry, "files": 1})
    for entry, n in orphan_notes:
        unhandled.append({"name": f"{entry}/ (JPEGs with no FIT beside them — the only "
                                  f"copy; bin them with discard… on that row)",
                          "files": n})

    try:
        u = shutil.disk_usage(vol)
        disk = {"total": u.total, "used": u.total - u.free, "free": u.free}
    except OSError:
        disk = None
    return {"device": "seestar", "volume": vol, "model": model, "camera": camera,
            "dest": dest_root, "targets": targets, "panel_sets": panel_sets,
            "non_dso": non_dso, "relpaths": relset, "disk": disk,
            "unhandled": unhandled, "identityGuessed": guessed,
            "extra_volumes": seestar_extra_volumes(vol)}


def _seestar_ledger_add(state, f, vol, camera, kind, target, display, dest_dir,
                        sha, day=None, exposure=None, night=None, sub_count=None):
    entry = {
        "filename": f["filename"], "size": f["size"], "sha256": sha,
        "origin": "import", "device": "seestar", "target": target,
        "displayName": display, "sourceType": kind, "camera": camera,
        "scope": camera.replace("ZWO ", ""),
        "exposureSeconds": exposure, "night": night, "dayNumber": day,
        "importedAt": now_stamp(), "dest": dest_dir, "verifiedAtImport": True,
    }
    mt = f.get("mtime")
    if mt is None:
        try:
            mt = os.path.getmtime(f["path"])
        except (OSError, KeyError):
            mt = None
    if mt is not None:
        entry["cameraMtime"] = mt   # what "these bytes" meant at import (H4)
    if sub_count is not None:
        entry["subCount"] = sub_count   # the Seestar's running N for a stack
    state.add_file(f["relpath"], **entry)


_STACK_N_RE = re.compile(r"^Stacked_(\d+)_")

def _stack_n(filename):
    m = _STACK_N_RE.match(filename)
    return int(m.group(1)) if m else None

_STACK_SESSION_RE = re.compile(r"_(\d+(?:\.\d+)?)s_([A-Za-z0-9]+)_(\d{8}-\d{6})")

def _stack_info(filename):
    """(n, session, stamp, night) for a Stacked_N_… name, or None. `session`
    is (exposure, filter) from the name when the camera writes them."""
    n = _stack_n(filename)
    if n is None:
        return None
    m = _STACK_SESSION_RE.search(filename)
    sess = (m.group(1), m.group(2).upper()) if m else None
    st = _SEESTAR_STAMP_RE.search(filename)
    stamp = (st.group(1) + "-" + st.group(2)) if st else None
    return (n, sess, stamp, _seestar_file_night(filename) or "")

def _stack_supersedes(newer, older):
    """True only when stack `newer` is a CONTINUATION of `older`: same night,
    same exposure and filter, a higher N AND a later stamp. Anything else —
    a filter change, a restarted stack whose N began again, a missing stamp —
    is a separate session with its own keeper (1.4.3 review BLOCKER H6: the
    old "highest N tonight" rule dropped a second session's stack and then
    cleared the camera's only copy of it)."""
    a, b = _stack_info(newer), _stack_info(older)
    if not a or not b:
        return False
    return (a[3] == b[3] and a[1] == b[1] and a[0] > b[0]
            and a[2] is not None and b[2] is not None and a[2] > b[2])

def seestar_stack_keepers(stacks):
    """Every stack that no other stack in the list supersedes — one keeper
    per stacking SESSION (1.4.3; was one per night in 1.3.1). Returns
    [(night, n, stack_dict)] in night-then-time order. A stack with no
    parseable name is always kept."""
    out = []
    for s in stacks:
        info_ = _stack_info(s["filename"])
        if info_ is None:
            continue
        if any(_stack_supersedes(o["filename"], s["filename"]) for o in stacks if o is not s):
            continue
        out.append((info_[3], info_[0], s, info_[2] or ""))
    out.sort(key=lambda x: (x[0], x[3], x[1]))
    return [(night, n, s) for night, n, s, _st in out]

def _mtime_close(a, b):
    """Camera mtimes compared across mounts. FAT-family cards store local
    time, so a DST change or travel shifts every mtime by a whole number of
    quarter-hours — that is the same file. A re-saved file differs by an
    arbitrary amount."""
    try:
        d = abs(float(a) - float(b))
    except (TypeError, ValueError):
        return True
    if d <= 2:
        return True
    q = d % 900
    return d <= 14 * 3600 + 2 and (q <= 2 or q >= 898)

def _camera_changed(e, mtime):
    """The ledger row was written from different bytes than the camera now
    holds at this path (same size, re-saved — H4). Rows from before 1.4.3
    carry no camera mtime and are not judged."""
    return bool(e) and e.get("cameraMtime") is not None and mtime is not None \
        and not _mtime_close(e["cameraMtime"], mtime)

_SEESTAR_STAMP_RE = re.compile(r"(20\d{6})-(\d{6})")

def _seestar_file_night(filename):
    """Observing night for a Seestar file, parsed from the timestamp in its
    name (bare-stamp and Light_-prefixed firmware forms both carry one)."""
    m = _SEESTAR_STAMP_RE.search(filename)
    if not m:
        return None
    try:
        dt = datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")
    except ValueError:
        return None
    return observing_night(dt)

def _seestar_day_number(state, dest_project_dir, day_label, target,
                        incoming_files=None, camera=None, by_display=False):
    n = 1
    while os.path.isdir(os.path.join(dest_project_dir, f"{day_label} Day {n}")):
        n += 1
    day = max(n, state.max_day_number(target, device="seestar",
                                      camera=camera,
                                      by_display=by_display) + 1)
    # Night continuation (Brett, 2026-08-18): a resumed/interrupted import must
    # land in the SAME night's folder, not fragment one night across Days —
    # same rule the ASIAir path has always had.
    if incoming_files:
        nights = {_seestar_file_night(f["filename"]) for f in incoming_files}
        nights.discard(None)
        prev_dir = os.path.join(dest_project_dir, f"{day_label} Day {day - 1}")
        if nights and day > 1 and os.path.isdir(prev_dir):
            for fname in os.listdir(prev_dir):
                if _seestar_file_night(fname) in nights:
                    return day - 1
    return day

def _sub_meta(path):
    """EXPTIME/DATE-OBS for a Seestar sub (names carry no metadata)."""
    try:
        h = get_fits().getheader(path)
        exp = h.get("EXPTIME")
        d = str(h.get("DATE-OBS", ""))[:19]
        dt = datetime.strptime(d, "%Y-%m-%dT%H:%M:%S") if d else None
        return (float(exp) if exp is not None else None,
                observing_night(dt) if dt else None)
    except Exception:
        return None, None


def run_seestar_import(state, scan_s, args, only_targets=None):
    dry_run = args.dry_run
    checksum = not args.no_checksum
    vol, camera, model = scan_s["volume"], scan_s["camera"], scan_s["model"]
    dest_root = scan_s["dest"]
    scope_name = camera.replace("ZWO ", "")
    totals = {"targets": 0, "files": 0}
    receipt_sessions = []
    cleanup = []   # (label, [dirs], all_relpaths_for_safety)

    if not dry_run:
        os.makedirs(dest_root, exist_ok=True)
    info(f"Seestar: {model} — destination {dest_root}")
    for u in scan_s.get("unhandled", []):
        warn(f"On camera but NOT handled by this tool (left untouched): "
             f"{u['name']} — {u['files']} file(s)")
    for xv in scan_s.get("extra_volumes", []):
        warn(f"Another Seestar is mounted at {xv} — one camera at a time: "
             f"this run covers only {vol}. Import it after a swap.")
    emit("run-start", device="seestar", targets=len([t for t in scan_s['targets'] if t['new']]))

    # ── DSO projects (non-MW) ────────────────────────────────────────────
    for t in scan_s["targets"]:
        if t["is_mw"] or t["skipped"]:
            continue
        if only_targets is not None and t["name"] not in only_targets:
            continue
        if not t["new"] and not t["new_stacks"]:
            continue
        display = seestar_display(state, t["project_name"], ask=not dry_run, dry_run=dry_run)
        dest_project_dir = os.path.join(dest_root, display)
        # rename raw-named legacy folder
        old_dest = os.path.join(dest_root, t["project_name"])
        if display != t["project_name"] and os.path.isdir(old_dest) \
                and not os.path.isdir(dest_project_dir) and not dry_run:
            shutil.move(old_dest, dest_project_dir)
            success(f"Renamed: {t['project_name']} → {display}")

        totals["targets"] += 1
        print("───────────────────────────────────────────────────────────────")
        emit("phase", name="target", target=display, files=len(t["new"]))
        info(f"Seestar target: {display}")
        manifest = os.path.join(dest_project_dir, ".imported_files")
        # One Day folder per OBSERVING NIGHT (1.4.3): an import that brings
        # two nights of subs files them as two Days, as HOW-IT-WORKS always
        # promised (review S7) — the numbering still continues a resumed night.
        by_night = {}
        for f in t["new"]:
            by_night.setdefault(_seestar_file_night(f["filename"]) or "", []).append(f)
        day = _seestar_day_number(state, dest_project_dir, t["sub_name"], t["name"],
                                  incoming_files=t["new"], camera=camera)
        day_dirname = f"{t['sub_name']} Day {day}"
        dest_day = os.path.join(dest_project_dir, day_dirname)
        verified = 0
        stacks_copied = 0
        last_day = 0
        for night_key in sorted(by_night):
            group = by_night[night_key]
            day = _seestar_day_number(state, dest_project_dir, t["sub_name"], t["name"],
                                      incoming_files=group, camera=camera)
            if day <= last_day:
                day = last_day + 1      # dry run: the earlier night's folder isn't made
            last_day = day
            day_dirname = f"{t['sub_name']} Day {day}"
            dest_day = os.path.join(dest_project_dir, day_dirname)
            info(f"{len(group)} new light frame(s)"
                 + (f" from {night_key}" if night_key and len(by_night) > 1 else "")
                 + f" → {day_dirname}")
            if dry_run:
                log(f"[dry-run] Would copy {len(group)} frame(s)")
                continue
            os.makedirs(dest_day, exist_ok=True)
            done = n_ok = 0
            for f in group:
                try:
                    sha, _size = copy_file_verified(f["path"],
                                                    os.path.join(dest_day, f["filename"]),
                                                    checksum=checksum)
                    exp, night = _sub_meta(f["path"])
                    _seestar_ledger_add(state, f, vol, camera, "sub", t["name"],
                                        display, dest_day, sha, day=day,
                                        exposure=exp, night=night)
                    with open(manifest, "a") as mf:
                        mf.write(f["filename"] + "\n")
                    verified += 1
                    n_ok += 1
                except Exception as e:
                    warn(f"Copy FAILED for {f['filename']}: {e}")
                done += 1
                show_progress(done, len(group))
            success(f"Copied and verified {n_ok} light frame(s) to {day_dirname}")

        # Stacks: one keeper per stacking SESSION (1.4.3; per night since
        # 1.3.1), and the archive is never pruned. Before 1.3.1 the importer
        # kept only the single highest Stacked_N and DELETED every other stack
        # at the destination on filename inequality. Deletion is Brett's hand;
        # this tool only ever adds.
        keepers = seestar_stack_keepers(t["stacks"])
        best_count = max([n for _night, n, _s in keepers], default=-1)
        superseded_here = []   # archived same-night stacks now outranked
        if keepers:
            for night, n, best in keepers:
                info(f"Stack for {night or 'unknown night'}: "
                     f"{best['filename']} ({n} subs)")
            if not dry_run:
                os.makedirs(dest_project_dir, exist_ok=True)
            for night, n, best in keepers:
                if dry_run:
                    continue
                dst = os.path.join(dest_project_dir, best["filename"])
                # Re-copy when the CAMERA's stack changed since it was
                # ledgered — the S50 Pro re-saves its stack after a session
                # (first light, 2026-09-05). Atomic overwrite, re-verified.
                if not os.path.isfile(dst) or \
                        state.is_imported(best["relpath"], best["size"], camera) != "yes" \
                        or _camera_changed(state.file_entry(best["relpath"], camera),
                                           best.get("mtime")):
                    try:
                        sha, _sz = copy_file_verified(best["path"], dst, checksum=checksum)
                        _seestar_ledger_add(state, best, vol, camera, "stack",
                                            t["name"], display, dest_project_dir, sha,
                                            day=day, night=night or None, sub_count=n)
                        stacks_copied += 1
                        success(f"Copied stacked .fit for {night or 'unknown night'} ({n} subs)")
                    except Exception as e:
                        warn(f"Stacked copy failed: {e}")
                # The stack's JPG rides along VERIFIED and LEDGERED — an
                # unledgered file would (rightly) block the SAFE gate forever
                jpg = os.path.splitext(best["path"])[0] + ".jpg"
                if os.path.isfile(jpg):
                    jdst = os.path.join(dest_project_dir, os.path.basename(jpg))
                    try:
                        jf = {"path": jpg, "relpath": _rel(jpg, vol),
                              "filename": os.path.basename(jpg),
                              "size": os.path.getsize(jpg)}
                        if state.is_imported(jf["relpath"], jf["size"], camera) != "yes" \
                                or not os.path.isfile(jdst):
                            sha, _sz = copy_file_verified(jpg, jdst, checksum=checksum)
                            _seestar_ledger_add(state, jf, vol, camera, "stack-jpg",
                                                t["name"], display,
                                                dest_project_dir, sha, day=day,
                                                night=night or None, sub_count=n)
                    except Exception as e:
                        warn(f"Stack JPG copy failed: {e}")
                # An archived stack this one CONTINUES (same session, later,
                # higher N): report it, never touch it.
                for old in os.listdir(dest_project_dir):
                    if not old.endswith(".fit") or old == best["filename"]:
                        continue
                    if _stack_supersedes(best["filename"], old):
                        superseded_here.append((old, best["filename"]))
            if superseded_here and not dry_run:
                for old, newer in superseded_here:
                    log(f"Superseded stack left in place: {old} (same night as {newer})")
                info("Stacks a later one continues are never deleted by an import. "
                     "Review them with --tidy-stacks.")

        if not dry_run and (verified > 0 or stacks_copied > 0):
            state.history_event("import", device="seestar", target=t["name"],
                                displayName=display, scope=scope_name,
                                frames=verified,
                                dayFolder=dest_day if t["new"] else None)
            state.save_ledger()
            receipt_sessions.append({
                "targetDisplayName": display, "seestarProjectName": t["project_name"],
                "isMosaic": "_mosaic" in t["project_name"], "dayNumber": day,
                "framesCopied": verified, "stackedCount": max(best_count, 0),
                "stacks": [{"night": night or None, "subCount": n,
                            "filename": best["filename"]} for night, n, best in keepers],
                "fitsFolderPath": dest_day if t["new"] else dest_project_dir})
            # banner/receipt semantics: subs count as "frames"; a stack-only
            # import counts its stacks so the run never reports 0 files
            totals["files"] += verified if verified else stacks_copied
            dirs = ([t["sub_dir"]] if t["sub_dir"] else []) \
                + ([t["project_dir"]] if t["project_dir"] else [])
            cleanup.append((display, dirs, True))   # DSO: keep-highest applies
        print()

    # ── Milky Way sessions (paired to simultaneous DSO) ──────────────────
    mw_common = DSO_NAMES.get("MilkyWay", "Milky Way Core")
    dso_anchors = []   # (epoch_dt, project_name) from ALL source stacks
    for t in scan_s["targets"]:
        if t["is_mw"]:
            continue
        for s in t["stacks"]:
            st = _stamp(s["filename"])
            dt = _stamp_dt(st) if st else None
            if dt:
                dso_anchors.append((dt, t["project_name"].split("_mosaic")[0]))

    def nearest_dso(dt):
        best, bestdiff = "", None
        for adt, name in dso_anchors:
            diff = abs((adt - dt).total_seconds())
            if bestdiff is None or diff < bestdiff:
                bestdiff, best = diff, name
        return best if (bestdiff is not None and bestdiff <= MW_PAIR_TOLERANCE) else ""

    for t in scan_s["targets"]:
        if not t["is_mw"] or t["skipped"]:
            continue
        if only_targets is not None and t["name"] not in only_targets:
            continue
        anchors = []   # (dt, stamp, keeper_file)
        for s in t["stacks"]:
            st = _stamp(s["filename"])
            dt = _stamp_dt(st) if st else None
            if dt:
                anchors.append((dt, st, s))
        anchors.sort(key=lambda a: a[0])
        buckets = [[] for _ in range(len(anchors) + 1)]
        open_max = None
        for f in t["new"]:
            st = _stamp(f["filename"])
            dt = _stamp_dt(st) if st else None
            idx = len(anchors)
            if dt:
                for i, (adt, _s, _k) in enumerate(anchors):
                    if adt >= dt:
                        idx = i
                        break
                if idx == len(anchors) and (open_max is None or dt > open_max[0]):
                    open_max = (dt, st)
            buckets[idx].append(f)

        mw_verified_total = 0
        for si, bucket in enumerate(buckets):
            if not bucket:
                continue
            if si < len(anchors):
                a_dt, a_stamp, keeper = anchors[si]
            else:
                a_dt, a_stamp, keeper = (open_max or (None, None)) + (None,) \
                    if open_max else (None, None, None)
            dso = nearest_dso(a_dt) if a_dt else ""
            display = f"{mw_common} - {dso}" if dso else mw_common
            prefix = f"MilkyWay_{dso}_" if dso else "MilkyWay_"
            dest_project_dir = os.path.join(dest_root, display)
            # Same ledger-aware, night-continuing numbering as DSO subs —
            # a yanked cable or an archived folder must not fragment or
            # restart a Milky Way night (1.3.0 review finding). MW entries
            # share the target "MilkyWay*", so scope by display folder.
            day = _seestar_day_number(state, dest_project_dir, display,
                                      display, incoming_files=bucket,
                                      camera=camera, by_display=True)
            day_dirname = f"{display} Day {day}"
            dest_day = os.path.join(dest_project_dir, day_dirname)
            print("───────────────────────────────────────────────────────────────")
            info(f"Milky Way: {display}" + (f" (paired, session {a_stamp})" if dso else ""))
            if not dso:
                warn(f"No DSO match within {MW_PAIR_TOLERANCE}s — filing as {mw_common}")
            if dry_run:
                log(f"[dry-run] Would copy {len(bucket)} frame(s) → {day_dirname}")
                continue
            os.makedirs(dest_day, exist_ok=True)
            manifest = os.path.join(dest_project_dir, ".imported_files")
            done = verified = 0
            for f in bucket:
                st = _stamp(f["filename"]) or f["filename"]
                try:
                    sha, _sz = copy_file_verified(
                        f["path"], os.path.join(dest_day, f"{prefix}{st}.fit"),
                        checksum=checksum)
                    _seestar_ledger_add(state, f, vol, camera, "mw", t["name"],
                                        display, dest_day, sha, day=day,
                                        night=observing_night(_stamp_dt(_stamp(f["filename"]))))
                    with open(manifest, "a") as mf:
                        mf.write(f["filename"] + "\n")
                    verified += 1
                except Exception as e:
                    warn(f"MW copy FAILED {f['filename']}: {e}")
                done += 1
                show_progress(done, len(bucket), label="Milky Way")
            success(f"Copied and verified {verified} Milky Way frame(s) → {day_dirname}")
            mw_verified_total += verified
            if keeper is not None:
                kdst = os.path.join(dest_project_dir, f"{prefix}{a_stamp}.fit")
                if not os.path.isfile(kdst) or \
                        state.is_imported(keeper["relpath"], keeper["size"], camera) != "yes":
                    try:
                        sha, _sz = copy_file_verified(keeper["path"], kdst, checksum=checksum)
                        _seestar_ledger_add(state, keeper, vol, camera, "mw-stack",
                                            t["name"], display, dest_project_dir, sha, day=day)
                        success(f"Copied stacked keeper → {os.path.basename(kdst)}")
                    except Exception as e:
                        warn(f"Keeper copy failed: {e}")
                kjpg = os.path.splitext(keeper["path"])[0] + ".jpg"
                if os.path.isfile(kjpg):
                    kjdst = os.path.join(dest_project_dir, f"{prefix}{a_stamp}.jpg")
                    try:
                        jf = {"path": kjpg, "relpath": _rel(kjpg, vol),
                              "filename": os.path.basename(kjpg),
                              "size": os.path.getsize(kjpg)}
                        if state.is_imported(jf["relpath"], jf["size"], camera) != "yes" \
                                or not os.path.isfile(kjdst):
                            sha, _sz = copy_file_verified(kjpg, kjdst, checksum=checksum)
                            _seestar_ledger_add(state, jf, vol, camera, "mw-jpg",
                                                t["name"], display,
                                                dest_project_dir, sha, day=day)
                    except Exception as e:
                        warn(f"MW JPG copy failed: {e}")
            if verified:
                state.history_event("import", device="seestar", target=t["name"],
                                    displayName=display, scope=scope_name,
                                    frames=verified, pairedDso=dso, dayFolder=dest_day)
                state.save_ledger()
                receipt_sessions.append({
                    "targetDisplayName": display, "seestarProjectName": t["name"],
                    "isMilkyWay": True, "pairedDso": dso, "dayNumber": day,
                    "framesCopied": verified, "fitsFolderPath": dest_day})
                totals["files"] += verified
        if mw_verified_total:
            totals["targets"] += 1
            dirs = [t["sub_dir"]] + ([t["project_dir"]] if t["project_dir"] else [])
            # MW dirs hold one keeper PER SESSION — never exempt "superseded"
            # stacks there (pass-2 BLOCKER: an unledgered lower-N keeper is a
            # different night's only copy, not a disposable duplicate)
            cleanup.append((f"Milky Way (paired) ← {t['sub_name']}", dirs, False))

    # ── JPEG riders (per-sub previews — S50 Pro first light, 2026-09-05) ──
    # The S50 Pro writes a JPEG beside every sub. They back up like any
    # frame — verified, ledgered, filed beside their sibling FIT — including
    # CATCH-UP for fits imported before this existed (ledger sibling lookup
    # supplies the right Day folder, so a later night can't misfile them).
    cleanup_labels = {c[0] for c in cleanup}
    mw_common_j = DSO_NAMES.get("MilkyWay", "Milky Way Core")
    for t in scan_s["targets"]:
        if t["skipped"] or not t.get("new_jpgs"):
            continue
        if only_targets is not None and t["name"] not in only_targets:
            continue
        display = seestar_display(state, t["project_name"], ask=False)
        print("───────────────────────────────────────────────────────────────")
        info(f"JPEG previews: {display} — {len(t['new_jpgs'])} new file(s)")
        if dry_run:
            log(f"[dry-run] Would copy {len(t['new_jpgs'])} JPEG(s) beside their FITs")
            continue
        done = jverified = 0
        for jf in t["new_jpgs"]:
            done += 1
            sib = state.file_entry(os.path.splitext(jf["relpath"])[0] + ".fit", camera)
            if not sib or not sib.get("dest"):
                warn(f"No imported sibling FIT for {jf['filename']} — left on camera")
                continue
            jname = jf["filename"]
            if sib.get("sourceType") == "mw":
                st = _stamp(jf["filename"]) or os.path.splitext(jf["filename"])[0]
                disp = sib.get("displayName") or mw_common_j
                dso = (disp[len(mw_common_j) + 3:]
                       if disp.startswith(mw_common_j + " - ") else "")
                jname = f"MilkyWay_{dso}_{st}.jpg" if dso else f"MilkyWay_{st}.jpg"
            try:
                _confine(sib["dest"], "a JPEG preview copy")
                os.makedirs(sib["dest"], exist_ok=True)
                sha, _sz = copy_file_verified(jf["path"],
                                              os.path.join(sib["dest"], jname),
                                              checksum=checksum)
                _seestar_ledger_add(
                    state, jf, vol, camera,
                    "mw-jpg" if sib.get("sourceType") == "mw" else "sub-jpg",
                    t["name"], sib.get("displayName") or display,
                    sib["dest"], sha, day=sib.get("dayNumber"),
                    night=_seestar_file_night(jf["filename"]))
                jverified += 1
            except Exception as e:
                warn(f"JPEG copy FAILED {jf['filename']}: {e}")
            show_progress(done, len(t["new_jpgs"]), label="JPEGs")
        if jverified:
            success(f"Copied and verified {jverified} JPEG preview(s) beside their FITs")
            state.save_ledger()
            label = (f"Milky Way (paired) ← {t['sub_name']}" if t.get("is_mw")
                     else display)
            if label not in cleanup_labels:
                dirs = ([t["sub_dir"]] if t["sub_dir"] else []) \
                    + ([t["project_dir"]] if t["project_dir"] else [])
                cleanup.append((label, dirs, not t.get("is_mw")))
                cleanup_labels.add(label)
            if not t["new"] and not t.get("new_stacks"):
                # a jpg-only catch-up run still reports what it did
                totals["files"] += jverified
                state.history_event("import", device="seestar", target=t["name"],
                                    displayName=display, scope=scope_name,
                                    frames=jverified, jpegs=True)
        print()

    # ── Mosaic panels ─────────────────────────────────────────────────────
    for ps in scan_s["panel_sets"]:
        if only_targets is not None and ps["mosaic_name"].split("_mosaic")[0] not in only_targets:
            continue
        if not ps["new"]:
            continue
        display = seestar_display(state, ps["mosaic_name"], ask=not dry_run, dry_run=dry_run)
        dest_project_dir = os.path.join(dest_root, display)
        dest_panels = os.path.join(dest_project_dir, "panels")
        print("───────────────────────────────────────────────────────────────")
        info(f"Mosaic panels: {display} — {len(ps['new'])} new panel file(s)")
        if dry_run:
            log("[dry-run] Would copy panels to panels/")
            continue
        os.makedirs(dest_panels, exist_ok=True)
        manifest = os.path.join(dest_project_dir, ".imported_panels")
        done = verified = 0
        for f in ps["new"]:
            try:
                sha, _sz = copy_file_verified(f["path"],
                                              os.path.join(dest_panels, f["filename"]),
                                              checksum=checksum)
                _seestar_ledger_add(state, f, vol, camera, "panel",
                                    ps["mosaic_name"].split("_mosaic")[0],
                                    display, dest_panels, sha,
                                    night=observing_night(_stamp_dt(_stamp(f["filename"]))))
                with open(manifest, "a") as mf:
                    mf.write(f["filename"] + "\n")
                verified += 1
            except Exception as e:
                warn(f"Panel copy FAILED {f['filename']}: {e}")
            done += 1
            show_progress(done, len(ps["new"]), label="Panels")
        success(f"Copied and verified {verified} mosaic panel(s) to panels/")
        if verified:
            state.history_event("import", device="seestar",
                                target=ps["mosaic_name"].split("_mosaic")[0],
                                displayName=display, scope=scope_name,
                                frames=verified, panels=True)
            state.save_ledger()
            totals["files"] += verified
            cleanup.append((f"{display} (panels)", [ps["pt_dir"]], False))
        print()

    # ── Non-DSO modes (Lunar/Solar/Planetary/Scenery), every model ───────
    for nd in scan_s["non_dso"]:
        if not nd["new"]:
            continue
        if only_targets is not None and nd["dest_name"] not in only_targets \
                and nd["src_name"] not in only_targets:
            continue   # panel tick / --targets governs these too — either
            #            the destination name ("Lunar") or the camera folder
            #            name ("Lunar_photo") selects a mode
        dest_mode = os.path.join(dest_root, nd["dest_name"])
        print("───────────────────────────────────────────────────────────────")
        info(f"{nd['dest_name']}: {len(nd['new'])} new file(s)")
        if dry_run:
            continue
        os.makedirs(dest_mode, exist_ok=True)
        manifest = os.path.join(dest_mode, ".imported_files")
        verified = 0
        for f in nd["new"]:
            try:
                sha, _sz = copy_file_verified(f["path"],
                                              os.path.join(dest_mode, f["filename"]),
                                              checksum=checksum)
                _seestar_ledger_add(state, f, vol, camera, "media",
                                    nd["dest_name"], nd["dest_name"], dest_mode, sha)
                with open(manifest, "a") as mf:
                    mf.write(f["filename"] + "\n")
                verified += 1
            except Exception as e:
                warn(f"{nd['dest_name']} copy FAILED {f['filename']}: {e}")
        success(f"Copied and verified {verified} {nd['dest_name']} file(s)")
        if verified:
            totals["files"] += verified
            state.save_ledger()
            cleanup.append((nd["dest_name"], [nd["src"]], False))

    # ── Receipt (per Seestar scope) ───────────────────────────────────────
    if not dry_run and receipt_sessions:
        receipt = {"version": 1, "source": "seestar-import", "telescope": scope_name,
                   "importedAt": now_stamp(), "sessions": receipt_sessions}
        rdir = os.path.join(RECEIPT_BASE, scope_name)
        _confine(rdir, "the AstroLog receipt")
        os.makedirs(rdir, exist_ok=True)
        rpath = _unique_receipt_path(rdir, f"seestar-{receipt['importedAt']}")
        _atomic_write_json(rpath, receipt)
        success(f"AstroLog receipt saved → {scope_name}/{os.path.basename(rpath)}")

    if not dry_run:
        state.save_ledger()
        seestar_safe_cleanup(state, scan_s, cleanup)
        state.publish_mirror()
    emit("run-done", device="seestar", targets=totals["targets"], files=totals["files"])
    return totals


def _seestar_unproven_files(state, vol, dirs, exempt_superseded=True, camera=None,
                            collect=None):
    """Files under `dirs` (on-camera paths) that the ledger cannot PROVE are
    backed up — the every-file SAFE rule. Proven means: a verified ledger row
    for THIS camera (1.4.3, H1), at the file's current size, written from
    these bytes (the camera mtime recorded at import still matches — a stack
    re-saved in place at the same size is NOT proven, H4).

    Always exempt: camera thumbnails (_thn) and macOS litter (._*, .DS_Store).
    Only where `exempt_superseded` (DSO project dirs): a stack that a verified
    stack in the same directory CONTINUES — same night, exposure and filter, a
    higher N and a later stamp (1.4.3, H6; a second session's stack is its own
    keeper). Its JPG sibling is exempt on the same terms. MW dirs hold one
    keeper PER SESSION, so they never exempt. A per-sub JPEG preview beside a
    proven FIT in a _sub folder is exempt (1.4.2).

    `collect`, if a list, receives the path of every file judged proven or
    exempt — the SAFE clear deletes exactly those (H3). Returns
    (unproven_names, proven_bytes)."""
    if camera is None:
        try:
            camera = seestar_model(vol)[1]
        except Exception:
            camera = None
    unproven, proven_bytes = [], 0
    twin_cache = {}

    def ok(p, size):
        nonlocal proven_bytes
        proven_bytes += size or 0
        if collect is not None:
            collect.append(p)

    for d in dirs:
        if not d or not os.path.isdir(d):
            continue
        verified_stacks = {}   # root -> [filename] of VERIFIED, unchanged stacks
        if exempt_superseded:
            for root, _dd, fnames in os.walk(d):
                for fn in fnames:
                    if _stack_n(fn) is None or not fn.lower().endswith(".fit"):
                        continue
                    p = os.path.join(root, fn)
                    e = state.file_entry(_rel(p, vol), camera)
                    if e is None or not e.get("verifiedAtImport"):
                        continue
                    try:
                        st = os.stat(p)
                    except OSError:
                        continue
                    if e.get("size") != st.st_size or _camera_changed(e, st.st_mtime):
                        continue
                    verified_stacks.setdefault(root, []).append(fn)
        for root, _dd, fnames in os.walk(d):
            for fn in fnames:
                low = fn.lower()
                p = os.path.join(root, fn)
                if "_thn" in low or fn.startswith("._") or fn == ".DS_Store":
                    if collect is not None:
                        collect.append(p)   # thumbnails + macOS litter, not data
                    continue
                try:
                    st = os.stat(p)
                    size, mtime = st.st_size, st.st_mtime
                except OSError:
                    size = mtime = None
                if exempt_superseded:
                    stem = fn[:-4] if low.endswith((".fit", ".jpg")) else fn
                    if _stack_n(stem) is not None and any(
                            _stack_supersedes(w, stem + ".fit")
                            for w in verified_stacks.get(root, [])):
                        ok(p, size)   # a verified later stack continues it
                        continue
                if (not SEESTAR_IMPORT_SUB_JPEGS and low.endswith((".jpg", ".jpeg"))
                        and os.path.basename(root.rstrip(os.sep)).endswith("_sub")
                        and _jpeg_twin_proven(state, vol, root, fn, twin_cache, camera)):
                    # a per-sub PREVIEW of a proven frame — not data. Only in a
                    # target's _sub folder: stack JPGs and Solar/Lunar/... JPGs
                    # are imported as data and must prove themselves (review
                    # BLOCKER: a failed mode-JPEG copy was otherwise cleared)
                    ok(p, size)
                    continue
                e = state.file_entry(_rel(p, vol), camera)
                if e is None or not e.get("verifiedAtImport") or e.get("size") != size \
                        or _camera_changed(e, mtime):
                    unproven.append(fn)
                else:
                    ok(p, size)
    return unproven, proven_bytes


def _jpeg_twin_proven(state, vol, root, fn, cache=None, camera=None):
    """1.4.2 rule: a JPEG is a regenerable PREVIEW, not data, when a FIT with
    the same stem sits in the same folder and that FIT is ledger-verified at
    its current size, for this camera. A JPEG with no proven twin is the only
    copy of something, so it still has to be backed up itself. The twin is
    found by listing the folder (real names — macOS disks are
    case-insensitive, the ledger's keys are not)."""
    cache = {} if cache is None else cache
    if root not in cache:
        stems = {}
        try:
            for name in os.listdir(root):
                b, ext = os.path.splitext(name)
                if ext.lower() in (".fit", ".fits") and not name.startswith("._"):
                    stems.setdefault(b, name)
        except OSError:
            pass
        cache[root] = stems
    twin = cache[root].get(os.path.splitext(fn)[0])
    if not twin:
        return False
    tp = os.path.join(root, twin)
    te = state.file_entry(_rel(tp, vol), camera)
    try:
        st = os.stat(tp)
    except OSError:
        return False
    return bool(te and te.get("verifiedAtImport") and te.get("size") == st.st_size
                and not _camera_changed(te, st.st_mtime))


def seestar_safe_cleanup(state, scan_s, cleanup_candidates):
    """SAFE-aware cleanup (Brett's chosen model): only offer source folders in
    which EVERY file is ledger-verified. Default No.

    "Every file" means every file — including JPEGs and anything with an
    extension this tool has never heard of (see _seestar_unproven_files for
    the only exemptions). One unproven file makes the whole folder NOT SAFE,
    and the refusal NAMES the files instead of going quiet (pass-2 finding).

    The answer can come an hour later from the panel, so after a Yes the
    camera's identity and every folder are CHECKED AGAIN, and only the files
    that pass that second check are deleted — never a blind rmtree of a
    folder that may since hold something else (1.4.3 review finding H3).
    Returns the number of folders cleared."""
    vol = scan_s["volume"]
    _confine(vol, "the SAFE clear")
    camera = scan_s["camera"]
    real_mw = os.path.realpath(os.path.join(vol, "MyWorks"))
    _confine(real_mw, "the SAFE clear")          # where the deletes really land
    safe, blocked = [], []
    for label, dirs, exempt_sup in cleanup_candidates:
        dirs = [d for d in dirs if d]
        if not dirs:
            continue
        unproven, total_bytes = _seestar_unproven_files(
            state, vol, dirs, exempt_superseded=exempt_sup, camera=camera)
        if unproven:
            blocked.append((label, unproven))
        else:
            safe.append((label, dirs, total_bytes, exempt_sup))
    for label, unproven in blocked:
        shown = ", ".join(unproven[:4]) + ("…" if len(unproven) > 4 else "")
        warn(f"NOT SAFE — {label}: {len(unproven)} file(s) on camera not "
             f"proven backed up ({shown}). Folder left untouched.")
    if not safe:
        return 0
    print()
    info("These Seestar source folders are fully imported + verified (SAFE):")
    lines = []
    for label, dirs, b, _ex in safe:
        lines.append(f"  {label}  ({human_size(b)})  ← " +
                     ", ".join(os.path.basename(d.rstrip('/')) for d in dirs if d))
    for ln in lines:
        log(ln)
    warn("Deleting frees space on the Seestar. This cannot be undone.")
    scope = camera.replace("ZWO ", "")
    q = "Delete these SAFE source folders from the Seestar? [y/N] "
    if PROMPT_FN is not None:
        # the panel card must say WHAT it deletes — the log pane is not the card
        q = (f"Clear from the {scope}: every file below is backed up on this Mac and "
             f"verified byte for byte (that is what SAFE means).\n" + "\n".join(lines)
             + "\n" + q)
    resp = safe_input(q, default="n")
    if resp.lower() != "y":
        info("Skipped — source files left on the Seestar.")
        return 0
    # ── the second check, at the moment of deletion ──
    try:
        now_camera = seestar_model(vol)[1] if os.path.isdir(os.path.join(vol, "MyWorks")) else None
    except Exception:
        now_camera = None
    if now_camera != camera:
        error(f"The camera at {vol} is no longer the {scope} that was checked "
              f"({now_camera or 'nothing readable'}). Nothing was deleted — rescan first.")
        return 0
    stamp = now_stamp()
    cleared = 0
    for label, dirs, _b, exempt_sup in safe:
        todo = []
        unproven, _pb = _seestar_unproven_files(state, vol, dirs,
                                                exempt_superseded=exempt_sup,
                                                camera=camera, collect=todo)
        if unproven:
            warn(f"NOT SAFE any more — {label}: {len(unproven)} file(s) changed or "
                 f"appeared since the check ({unproven[0]}). Folder left untouched.")
            continue
        bad = [p for p in todo
               if not os.path.realpath(p).startswith(real_mw + os.sep) or os.path.islink(p)]
        if bad:
            error(f"{label}: {_rel(bad[0], vol)} resolves outside the "
                  f"camera's MyWorks — nothing deleted here.")
            continue
        removed = []
        for p in todo:
            try:
                os.remove(p)
                removed.append(p)
            except OSError as ex:
                warn(f"Could not delete {os.path.basename(p)}: {ex}")
        # folders that now hold nothing (or only macOS litter) go too — each
        # must sit strictly inside MyWorks
        for d in dirs:
            if not os.path.isdir(d):
                continue
            for root, _dd, fns in sorted(os.walk(d), key=lambda x: -len(x[0])):
                rr = os.path.realpath(root)
                if not rr.startswith(real_mw + os.sep):
                    continue
                if all(f.startswith("._") or f == ".DS_Store" for f in fns) and \
                        not [x for x in os.listdir(root)
                             if os.path.isdir(os.path.join(root, x))]:
                    shutil.rmtree(root, ignore_errors=True)
        # flag exactly the rows whose files were just deleted (this camera only)
        gone = {_rel(p, vol) for p in removed}
        for rp, e in state.ledger["files"].items():
            if e.get("device") == "seestar" and ledger_relpath(rp) in gone \
                    and _row_camera(e) == camera and not e.get("clearedFromCamera"):
                e["clearedFromCamera"] = True
                e["clearedNoticedAt"] = stamp
                state._dirty = True
        if len(removed) == len(todo):
            cleared += 1
            success(f"Cleared {label} from the Seestar")
        else:
            warn(f"Cleared {len(removed)} of {len(todo)} file(s) of {label} — the rest "
                 f"are still on the Seestar.")
        state.history_event("seestar-cleared", target=label, files=len(removed))
    state.save_ledger()
    return cleared


def seestar_baseline(state, scan_s):
    """Record everything currently on the Seestar as imported (no copying)."""
    stamp = now_stamp()
    added = 0
    camera = scan_s["camera"]
    for t in scan_s["targets"]:
        display = seestar_display(state, t["project_name"], ask=False)
        riders = t.get("jpgs", []) if SEESTAR_IMPORT_SUB_JPEGS else []
        for f in t["files"] + t["stacks"] + riders:
            if state.file_entry(f["relpath"], camera) is None:
                state.add_file(f["relpath"], **{
                    "filename": f["filename"], "size": f["size"], "sha256": None,
                    "origin": "baseline", "device": "seestar", "target": t["name"],
                    "displayName": display, "camera": camera,
                    "scope": camera.replace("ZWO ", ""),
                    "importedAt": stamp, "baselined": True, "verifiedAtImport": False,
                })
                added += 1
    for ps in scan_s["panel_sets"]:
        for f in ps["files"]:
            if state.file_entry(f["relpath"], camera) is None:
                state.add_file(f["relpath"], **{
                    "filename": f["filename"], "size": f["size"], "sha256": None,
                    "origin": "baseline", "device": "seestar",
                    "target": ps["mosaic_name"].split("_mosaic")[0],
                    "displayName": ps["mosaic_name"], "camera": camera,
                    "scope": camera.replace("ZWO ", ""),
                    "importedAt": stamp, "baselined": True, "verifiedAtImport": False,
                })
                added += 1
    for nd in scan_s["non_dso"]:
        for f in nd["files"]:
            if state.file_entry(f["relpath"], camera) is None:
                state.add_file(f["relpath"], **{
                    "filename": f["filename"], "size": f["size"], "sha256": None,
                    "origin": "baseline", "device": "seestar", "target": nd["dest_name"],
                    "displayName": nd["dest_name"], "camera": camera,
                    "scope": camera.replace("ZWO ", ""),
                    "importedAt": stamp, "baselined": True, "verifiedAtImport": False,
                })
                added += 1
    return added


# ═══════════════════════════════════════════════════════════════════════════
# DASHBOARD (self-contained HTML, regenerated on every state-changing run)
# ═══════════════════════════════════════════════════════════════════════════
# Design follows the dataviz reference palette (validated 2026-07-25, slots 1-3
# light+dark; light aqua contrast WARN covered by visible labels + table view).
# The page inlines one DATA object matching the ledger schema — the future
# app consumes the same contract.

SCOPE_SLOT = {"Askar FRA400": 1, "Askar 107PHQ": 2,
              "Seestar S30 Pro": 3, "Seestar S30": 3,
              "Seestar S50": 3, "Seestar S50 Pro": 3}  # palette has 3 slots; all
              # Seestars share slot 3 and are told apart by name in the legend

DASHBOARD_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BrettjoAstro FITS Importer — Status</title>
<style>
.viz-root{color-scheme:light;
 --page:#f9f9f7;--surface-1:#fcfcfb;--ink:#0b0b0b;--ink-2:#52514e;--muted:#898781;
 --grid:#e1e0d9;--baseline:#c3c2b7;--ring:rgba(11,11,11,.10);
 --series-1:#2a78d6;--series-2:#eb6834;--series-3:#1baf7a;
 --seq-250:#86b6ef;--good:#0ca30c;--warning:#fab219;--serious:#ec835a;--critical:#d03b3b;}
@media (prefers-color-scheme: dark){:root:where(:not([data-theme="light"])) .viz-root{color-scheme:dark;
 --page:#0d0d0d;--surface-1:#1a1a19;--ink:#ffffff;--ink-2:#c3c2b7;--muted:#898781;
 --grid:#2c2c2a;--baseline:#383835;--ring:rgba(255,255,255,.10);
 --series-1:#3987e5;--series-2:#d95926;--series-3:#199e70;--seq-250:#184f95;}}
:root[data-theme="dark"] .viz-root{color-scheme:dark;
 --page:#0d0d0d;--surface-1:#1a1a19;--ink:#ffffff;--ink-2:#c3c2b7;--muted:#898781;
 --grid:#2c2c2a;--baseline:#383835;--ring:rgba(255,255,255,.10);
 --series-1:#3987e5;--series-2:#d95926;--series-3:#199e70;--seq-250:#184f95;}
*{box-sizing:border-box;margin:0}
body{font:14px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
.viz-root{background:var(--page);color:var(--ink);min-height:100vh;padding:28px 32px 40px}
.wrap{max-width:1060px;margin:0 auto}
h1{font-size:20px;font-weight:650}
.sub{color:var(--ink-2);margin-top:2px;font-size:13px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:20px 0 14px}
.tile{background:var(--surface-1);border:1px solid var(--ring);border-radius:10px;padding:12px 14px}
.tile .v{font-size:24px;font-weight:650;margin-top:2px}
.tile .k{color:var(--muted);font-size:12px}
.tile .s{color:var(--ink-2);font-size:12px;margin-top:2px}
.card{background:var(--surface-1);border:1px solid var(--ring);border-radius:10px;padding:16px 18px;margin:12px 0}
.card h2{font-size:13.5px;font-weight:650;margin-bottom:2px}
.card .note{color:var(--muted);font-size:12px;margin-bottom:10px}
.storage{height:10px;border-radius:5px;background:var(--grid);overflow:hidden;margin:8px 0 4px}
.storage>div{height:100%;background:var(--series-1)}
table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}
th{color:var(--muted);font-size:11.5px;text-transform:uppercase;letter-spacing:.04em;
   text-align:left;font-weight:600;padding:6px 8px;border-bottom:1px solid var(--grid)}
td{padding:7px 8px;border-bottom:1px solid var(--grid);font-size:13px}
td.num,th.num{text-align:right}
tr:last-child td{border-bottom:none}
.chip{display:inline-flex;align-items:center;gap:5px;font-size:12px;color:var(--ink-2)}
.chip .dot{width:8px;height:8px;border-radius:50%}
.rowlab{display:flex;justify-content:space-between;font-size:12.5px;margin-bottom:3px}
.rowlab b{font-weight:600}.rowlab span{color:var(--ink-2)}
.hbar{height:14px;border-radius:0 4px 4px 0;margin-bottom:10px}
.events{list-style:none}
.events li{padding:6px 0;border-bottom:1px solid var(--grid);font-size:13px;display:flex;gap:10px}
.events li:last-child{border-bottom:none}
.events .t{color:var(--muted);white-space:nowrap;font-variant-numeric:tabular-nums}
svg text{font:11px system-ui,-apple-system,"Segoe UI",sans-serif;fill:var(--muted)}
.tip{position:fixed;pointer-events:none;background:var(--surface-1);border:1px solid var(--ring);
     border-radius:8px;padding:6px 9px;font-size:12px;color:var(--ink);box-shadow:0 4px 14px rgba(0,0,0,.12);
     display:none;z-index:9}
.foot{color:var(--muted);font-size:11.5px;margin-top:18px}
</style></head>
<body class="viz-root"><div class="wrap">
<h1>BrettjoAstro FITS Importer — Status</h1>
<div class="sub" id="sub"></div>
<div class="cards" id="tiles"></div>
<div class="card" id="storageCard" style="display:none">
  <h2>Camera storage</h2><div class="note" id="storageNote"></div>
  <div class="storage"><div id="storageBar"></div></div>
</div>
<div class="card"><h2>Frames imported per month</h2>
  <div class="note">Light frames landed on the Mac, by capture month</div>
  <div id="monthly"></div></div>
<div class="card"><h2>Integration by rig</h2>
  <div class="note">Total exposure hours per telescope</div>
  <div id="rigs"></div></div>
<div class="card"><h2>Targets</h2>
  <div class="note" id="catNote"></div>
  <table id="targets"><thead><tr>
    <th>Target</th><th>Rig</th><th class="num">Days</th><th class="num">Frames</th>
    <th class="num">Hours</th><th class="num">Size</th><th>Backup status</th>
  </tr></thead><tbody></tbody></table></div>
<div class="card"><h2>Recent activity</h2><ul class="events" id="events"></ul></div>
<div class="foot">Regenerated automatically after every import, report, or reconcile ·
data contract: ledger v1 (this page is the seed of the future app) · verdicts refresh on
<code>--report</code> with the camera attached.</div>
</div>
<div class="tip" id="tip"></div>
<script>
const DATA = __DATA__;
const $ = (s)=>document.querySelector(s);
const esc = (s)=>String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const fmtGB = (b)=> b>=1073741824? (b/1073741824).toFixed(1)+" GB" : Math.round(b/1048576)+" MB";
const CHIP = {safe:["--good","✓","Safe to clear"], unverified:["--warning","◐","Backed up, unverified"],
              notsafe:["--serious","!","Not safe"], skipped:["--muted","–","Never-import"],
              cleared:["--muted","∅","Cleared from camera"], unknown:["--muted","·","No verdict yet"]};
$("#sub").textContent = "Generated " + DATA.generatedAt +
  (DATA.lastScanAt ? " · camera last seen " + DATA.lastScanAt : "");
// tiles
const tiles=[["Frames imported",DATA.totals.frames.toLocaleString(),DATA.totals.baselineFrames?("+ "+DATA.totals.baselineFrames.toLocaleString()+" baseline-era"):""],
 ["Integration",DATA.totals.hours.toFixed(1)+" h",""],
 ["Targets",DATA.totals.targets,""],
 ["Verified",DATA.totals.verifiedPct+"%","of ledgered frames"],
 ["Calibration library",DATA.totals.calFrames+" frames",""]];
$("#tiles").innerHTML = tiles.map(t=>`<div class="tile"><div class="k">${esc(t[0])}</div><div class="v">${esc(t[1])}</div><div class="s">${esc(t[2])}</div></div>`).join("");
// storage
if (DATA.camera){$("#storageCard").style.display="block";
  const pct=Math.round(100*DATA.camera.used/DATA.camera.total);
  $("#storageBar").style.width=pct+"%";
  $("#storageNote").textContent=fmtGB(DATA.camera.used)+" used of "+fmtGB(DATA.camera.total)+
    " ("+fmtGB(DATA.camera.free)+" free) — as of "+(DATA.lastScanAt||"last plug-in");}
// monthly bars (single series → no legend; selective direct label on max)
(function(){
  const m=DATA.monthly; if(!m.length){$("#monthly").innerHTML='<div class="note">No imports recorded yet.</div>';return;}
  const W=Math.max(420,$("#monthly").clientWidth||640),H=170,P={l:8,r:8,t:16,b:22};
  const max=Math.max(...m.map(d=>d.frames)),iMax=m.findIndex(d=>d.frames===max);
  const bw=Math.max(6,Math.min(46,(W-P.l-P.r)/m.length-2));
  let s=`<svg width="100%" viewBox="0 0 ${W} ${H}">`;
  [0.5,1].forEach(f=>{const y=P.t+(H-P.t-P.b)*(1-f);
    s+=`<line x1="${P.l}" x2="${W-P.r}" y1="${y}" y2="${y}" stroke="var(--grid)" stroke-width="1"/>`;});
  m.forEach((d,i)=>{const x=P.l+i*((W-P.l-P.r)/m.length)+((W-P.l-P.r)/m.length-bw)/2;
    const h=Math.max(2,(H-P.t-P.b)*d.frames/max), y=H-P.b-h, r=Math.min(4,bw/2);
    s+=`<path class="bar" data-i="${i}" d="M${x} ${H-P.b} V${y+r} Q${x} ${y} ${x+r} ${y} H${x+bw-r} Q${x+bw} ${y} ${x+bw} ${y+r} V${H-P.b} Z" fill="var(--series-1)"/>`;
    if(i===iMax) s+=`<text x="${x+bw/2}" y="${y-5}" text-anchor="middle" style="fill:var(--ink-2);font-weight:600">${d.frames}</text>`;
    if(m.length<=14||i%2===0||i===m.length-1) s+=`<text x="${x+bw/2}" y="${H-7}" text-anchor="middle">${esc(d.label)}</text>`;});
  s+=`<line x1="${P.l}" x2="${W-P.r}" y1="${H-P.b}" y2="${H-P.b}" stroke="var(--baseline)" stroke-width="1"/></svg>`;
  $("#monthly").innerHTML=s;
  const tip=$("#tip");
  $("#monthly").querySelectorAll(".bar").forEach(b=>{
    b.addEventListener("mousemove",e=>{const d=m[+b.dataset.i];
      tip.style.display="block";tip.style.left=(e.clientX+12)+"px";tip.style.top=(e.clientY+12)+"px";
      tip.innerHTML=`<b>${esc(d.label)}</b><br>${d.frames} frames · ${d.hours.toFixed(1)} h`;});
    b.addEventListener("mouseleave",()=>tip.style.display="none");});
})();
// rigs (identity via row label; color follows the entity)
(function(){
  const r=DATA.rigs; if(!r.length){$("#rigs").innerHTML='<div class="note">No rig data yet.</div>';return;}
  const max=Math.max(...r.map(d=>d.hours));
  $("#rigs").innerHTML=r.map(d=>`
    <div class="rowlab"><b>${esc(d.scope)}</b><span>${d.hours.toFixed(1)} h · ${d.frames.toLocaleString()} frames</span></div>
    <div class="hbar" style="width:${Math.max(2,100*d.hours/max)}%;background:var(--series-${d.slot})"></div>`).join("");
})();
// targets table
(function(){
  const tb=$("#targets tbody");
  tb.innerHTML=DATA.targets.map(t=>{
    const c=CHIP[t.status]||CHIP.unknown;
    return `<tr><td>${esc(t.display)}</td><td>${esc(t.scopes)}</td>
      <td class="num">${t.days||"–"}</td><td class="num">${t.frames.toLocaleString()}</td>
      <td class="num">${t.hours.toFixed(1)}</td><td class="num">${fmtGB(t.bytes)}</td>
      <td><span class="chip"><span class="dot" style="background:var(${c[0]})"></span>${c[1]} ${esc(c[2])}</span></td></tr>`;
  }).join("");
  $("#catNote").textContent = DATA.lastReportAt ?
    ("Backup verdicts as of last report: "+DATA.lastReportAt) :
    "Run --report with the camera attached to get backup verdicts.";
})();
// events
$("#events").innerHTML = DATA.events.map(e=>
  `<li><span class="t">${esc(e.ts)}</span><span>${esc(e.text)}</span></li>`).join("")
  || '<li><span>No events yet.</span></li>';
</script></body></html>
"""

def _humanize_event(ev):
    e = ev.get("event", "")
    if e == "import":
        return (f"Imported {ev.get('frames', '?')} frames of "
                f"{ev.get('displayName') or ev.get('target', '?')} "
                f"({ev.get('scope', '?')})")
    if e == "baseline":
        return f"Baseline: {ev.get('frames', '?')} files marked as already imported"
    if e == "unbaseline":
        return f"Unbaselined {ev.get('target', '?')} ({ev.get('frames', 0)} entries)"
    if e == "reconcile":
        return (f"Reconcile: {ev.get('upgraded', 0)} upgraded to verified, "
                f"{ev.get('failed', 0)} mismatches")
    if e == "cleared-noticed":
        return f"{ev.get('target', '?')}: {ev.get('frames', '?')} frames cleared from camera"
    if e == "calibration-ingest":
        return f"Calibration Library: {ev.get('frames', '?')} new frames backed up"
    if e == "verify":
        return f"Verify: {ev.get('ok', 0)} OK, {ev.get('bad', 0)} problems"
    if e == "skiplist":
        return f"Never-import list: {ev.get('target', '?')} {'added' if ev.get('skipped') else 'removed'}"
    if e == "probation-gate":
        return f"Probation note on {ev.get('target', '?')} (calibration gate)"
    if e == "restored-from-mirror":
        return "Local state restored from iCloud mirror"
    return e

def generate_dashboard(state):
    """Build the self-contained status page from the ledger. No camera needed."""
    if not state.has_ledger():
        return None
    led = state.ledger
    per_target = {}
    monthly = defaultdict(lambda: {"frames": 0, "hours": 0.0})
    rigs = defaultdict(lambda: {"frames": 0, "hours": 0.0})
    n_verified = n_import = n_baseline = 0
    for e in led["files"].values():
        dev = e.get("device", "asiair")
        t = per_target.setdefault(f"{dev}:{e.get('target', '?')}", {
            "display": e.get("displayName") or e.get("target", "?"),
            "scopes": set(), "days": set(), "frames": 0, "hours": 0.0,
            "bytes": 0, "cleared": 0, "device": dev, "target": e.get("target", "?"),
        })
        t["frames"] += 1
        t["bytes"] += e.get("size") or 0
        t["hours"] += (e.get("exposureSeconds") or 0) / 3600.0
        if e.get("scope"):
            t["scopes"].add(e["scope"])
        if e.get("dayNumber"):
            t["days"].add(e["dayNumber"])
        if e.get("clearedFromCamera"):
            t["cleared"] += 1
        if e.get("verifiedAtImport"):
            n_verified += 1
        if e.get("origin") == "import":
            n_import += 1
            key = (e.get("night") or e.get("importedAt", ""))[:7]
            if key:
                monthly[key]["frames"] += 1
                monthly[key]["hours"] += (e.get("exposureSeconds") or 0) / 3600.0
        else:
            n_baseline += 1
        if e.get("scope"):
            rigs[e["scope"]]["frames"] += 1
            rigs[e["scope"]]["hours"] += (e.get("exposureSeconds") or 0) / 3600.0

    cats = led.get("lastCategories", {})
    targets = []
    for _key, t in sorted(per_target.items(), key=lambda kv: -kv[1]["bytes"]):
        name = t["target"]
        cat_key = name if t["device"] == "asiair" else f"seestar:{name}"
        status = cats.get(cat_key, {}).get("category", "unknown")
        if name in state.skiplist:
            status = "skipped"
        elif t["cleared"] == t["frames"] and t["frames"] > 0:
            status = "cleared"
        targets.append({
            "display": t["display"],
            "scopes": ", ".join(sorted(t["scopes"])) or "–",
            "days": len(t["days"]), "frames": t["frames"],
            "hours": round(t["hours"], 2), "bytes": t["bytes"], "status": status,
        })

    months_sorted = sorted(monthly.keys())[-12:]
    monthly_rows = [{"label": m[2:] if len(m) >= 7 else m,
                     "frames": monthly[m]["frames"],
                     "hours": round(monthly[m]["hours"], 2)} for m in months_sorted]
    rig_rows = [{"scope": s, "frames": v["frames"], "hours": round(v["hours"], 2),
                 "slot": SCOPE_SLOT.get(s, 3)}
                for s, v in sorted(rigs.items(), key=lambda kv: -kv[1]["hours"])]
    total = len(led["files"])
    data = {
        "generatedAt": now_stamp(),
        "lastScanAt": led.get("lastScanAt"),
        "lastReportAt": led.get("lastReportAt"),
        "camera": led.get("lastCameraDisk"),
        "totals": {
            "frames": n_import, "baselineFrames": n_baseline,
            "hours": round(sum(t["hours"] for t in per_target.values()), 1),
            "targets": len(per_target),
            "verifiedPct": round(100 * n_verified / total) if total else 0,
            "calFrames": len(led["calibration"]),
        },
        "monthly": monthly_rows, "rigs": rig_rows, "targets": targets,
        "events": [{"ts": ev.get("ts", "")[:16].replace("T", " "),
                    "text": _humanize_event(ev)}
                   for ev in reversed(state.history_tail(8))],
    }
    # every "<" escaped (not just "</"): a name containing "<!--" once
    # blanked the whole dashboard (1.4.3, V7). JSON reads \u003c as "<".
    payload = json.dumps(data).replace("<", "\\u003c").replace(">", "\\u003e") \
        .replace("&", "\\u0026")
    html = DASHBOARD_TEMPLATE.replace("__DATA__", payload)
    path = os.path.join(STATE_DIR, "dashboard.html")
    try:
        with open(path + ".tmp", "w") as f:
            f.write(html)
        os.replace(path + ".tmp", path)
        return path
    except OSError as e:
        warn(f"dashboard write failed: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════
# WATCHER SUPPORT / DIALOG FLOWS
# ═══════════════════════════════════════════════════════════════════════════

def run_scan_only(state):
    """Tagged lines for the watcher: count / summary / storage — both devices."""
    rows, storages = [], []
    total_new = n_files = n_bytes = 0
    asiair_here = os.path.isdir(ASIAIR_VOLUME)
    svol = seestar_volume()
    both = asiair_here and bool(svol)

    if asiair_here:
        scan = scan_camera(state)
        with_new = [t for t in scan["targets"] if t["new"] and not t["skipped"]]
        total_new += len(with_new)
        n_files += sum(len(t["new"]) for t in with_new)
        n_bytes += sum(t["new_bytes"] for t in with_new)
        for t in sorted(with_new, key=lambda t: -len(t["new"]))[:4]:
            disp = display_name_for(state, t["name"])
            rows.append(f"   {'[ASIAir] ' if both else ''}{disp}  —  {len(t['new']):,} frame(s)")
        if scan["disk"]:
            d = scan["disk"]
            storages.append(f"ASIAir {human_size(d['used'])}/{human_size(d['total'])} "
                            f"({human_size(d['free'])} free)")
    if svol:
        try:
            s = scan_seestar(state)
        except RuntimeError as e:
            s = None
            rows.append(f"   ✗ Seestar NOT scanned: {e}")
    if svol and s:
        s_new = [t for t in s["targets"]
                 if (t["new"] or t["new_stacks"] or t.get("new_jpgs"))
                 and not t["skipped"]]
        s_panels = [p for p in s["panel_sets"] if p["new"]]
        s_nd = [n for n in s["non_dso"] if n["new"]]
        total_new += len(s_new) + len(s_panels) + len(s_nd)
        n_files += (sum(len(t["new"]) + len(t["new_stacks"])
                        + len(t.get("new_jpgs") or []) for t in s_new)
                    + sum(len(p["new"]) for p in s_panels)
                    + sum(len(n["new"]) for n in s_nd))
        n_bytes += (sum(sum(f["size"] for f in
                            t["new"] + t["new_stacks"] + (t.get("new_jpgs") or []))
                        for t in s_new)
                    + sum(sum(f["size"] for f in p["new"]) for p in s_panels)
                    + sum(sum(f["size"] for f in n["new"]) for n in s_nd))
        for t in sorted(s_new, key=lambda t: -len(t["new"]))[:4]:
            disp = seestar_display(state, t["project_name"])
            rows.append(f"   {'[Seestar] ' if both else ''}{disp}  —  {len(t['new']):,} frame(s)")
        if s["disk"]:
            d = s["disk"]
            storages.append(f"Seestar {human_size(d['used'])}/{human_size(d['total'])} "
                            f"({human_size(d['free'])} free)")
        for u in s.get("unhandled", []):
            rows.append(f"   ⚠ NOT handled by this tool: {u['name']} "
                        f"({u['files']} file(s)) — on camera, not backed up")
        for xv in s.get("extra_volumes", []):
            rows.append(f"   ⚠ Another Seestar mounted at {xv} — one at a time")
        attention = len(s.get("unhandled", [])) + len(s.get("extra_volumes", []))
    elif svol:
        attention = 1   # the identity check refused the scan — needs a look
    else:
        attention = 0
    unhandled_n = attention

    if not state.has_ledger():
        summary = "No import ledger yet — the first import backs everything up."
    elif total_new:
        lines = [f"{total_new} target(s) have new frames — "
                 f"{n_files:,} files, {human_size(n_bytes)}", ""] + rows
        summary = "\\n".join(lines)
    elif unhandled_n or (svol and not s):
        # Never say "every frame is backed up" over data we couldn't read
        # (unhandled folders, or a scan the identity check refused)
        summary = "\\n".join(
            ["Nothing new that this tool recognises — attention needed:", ""]
            + rows)
    else:
        summary = "Nothing new. Every frame is backed up."
    storage = " · ".join(storages) if storages else "Camera storage: unknown"
    print(f"ASIAIR-SCAN|COUNT|{total_new}")
    print(f"ASIAIR-SCAN|ATTENTION|{attention}")
    print(f"ASIAIR-SCAN|SUMMARY|{summary}")
    print(f"ASIAIR-SCAN|STORAGE|{storage}")

def _choose_from_list(items, prompt, title, multiple=True, timeout=3600):
    """osascript choose from list via argv (quote-safe), killable timeout.
    Outside macOS: a numbered list in the console (the panel is the main
    route on every platform; this is the Terminal fallback)."""
    if TEST_ROOT:
        _test_record("choose", prompt=prompt, title=title, items=list(items))
        return None
    if not IS_MAC:
        if not items or not sys.stdin or not sys.stdin.isatty():
            return None
        print(f"\n{title} — {prompt}")
        for i, it in enumerate(items, 1):
            print(f"  {i:>3}. {it}")
        hint = "numbers separated by commas, 'all', or Enter to cancel" if multiple \
            else "a number, or Enter to cancel"
        try:
            ans = input(f"Choose ({hint}): ").strip().lower()
        except EOFError:
            return None
        if not ans:
            return None
        if multiple and ans == "all":
            return list(items)
        picked = []
        for tok in ans.replace(" ", "").split(","):
            if tok.isdigit() and 1 <= int(tok) <= len(items):
                picked.append(items[int(tok) - 1])
        if not multiple:
            picked = picked[:1]
        return picked or None
    script_lines = [
        "on run argv",
        "set thePrompt to item 1 of argv",
        "set theTitle to item 2 of argv",
        "set theItems to {}",
        "repeat with i from 3 to count of argv",
        "set end of theItems to item i of argv",
        "end repeat",
        "set theChoice to choose from list theItems with prompt thePrompt with title theTitle "
        + ("with multiple selections allowed" if multiple else ""),
        'if theChoice is false then return "CANCELLED"',
        'set text item delimiters to linefeed',
        "return theChoice as text",
        "end run",
    ]
    args = ["osascript"]
    for line in script_lines:
        args += ["-e", line]
    args += ["--", prompt, title] + list(items)
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        out = r.stdout.strip()
        if r.returncode != 0 or out == "CANCELLED" or not out:
            return None
        return out.split("\n")
    except (subprocess.TimeoutExpired, OSError):
        return None

def run_pick(state, args):
    entries = []   # (device, target_name, row)
    idx = 0
    if os.path.isdir(ASIAIR_VOLUME):
        scan = scan_camera(state)
        lookup = load_equipment_scope_lookup()
        for t in sorted([t for t in scan["targets"] if t["new"] and not t["skipped"]],
                        key=lambda t: -len(t["new"])):
            idx += 1
            disp = display_name_for(state, t["name"], ask=True, dry_run=args.dry_run)
            scope = ""
            fl = read_fits_focallen(t["new"][0]["path"])
            if fl:
                scope = " — " + scope_from_focallen(fl, lookup)
            entries.append(("asiair", t["name"],
                            f"{idx} · {disp} — {len(t['new'])} new "
                            f"({human_size(t['new_bytes'])}, {human_hours(t['integration_s'])})"
                            f"{scope}"))
    svol = seestar_volume()
    if svol:
        try:
            s = scan_seestar(state)
        except RuntimeError as e:
            error(f"Seestar NOT scanned: {e}")
            s = None
            svol = None
    if svol:
        for t in sorted([t for t in s["targets"]
                         if (t["new"] or t["new_stacks"] or t.get("new_jpgs"))
                         and not t["skipped"]],
                        key=lambda t: -len(t["new"])):
            idx += 1
            disp = seestar_display(state, t["project_name"], ask=True, dry_run=args.dry_run)
            n_new = (len(t["new"]) or len(t.get("new_stacks") or [])
                     or len(t.get("new_jpgs") or []))
            nb = (sum(f["size"] for f in t["new"])
                  or sum(f["size"] for f in t.get("new_jpgs") or []))
            entries.append(("seestar", t["name"],
                            f"{idx} · {disp} — {n_new} new "
                            f"({human_size(nb)}) — Seestar {s['model']}"))
        for p in s["panel_sets"]:
            if p["new"]:
                idx += 1
                disp = seestar_display(state, p["mosaic_name"]) + " (panels)"
                entries.append(("seestar", p["mosaic_name"].split("_mosaic")[0],
                                f"{idx} · {disp} — {len(p['new'])} new panel(s)"))
        for nd in s["non_dso"]:
            if nd["new"]:
                idx += 1
                entries.append(("seestar", nd["dest_name"],
                                f"{idx} · {nd['dest_name']} "
                                f"({nd['src_name'].replace('_', ' ')}) — "
                                f"{len(nd['new'])} new file(s)"))
    if not entries:
        info("Nothing new to import.")
        return
    mapping = {}
    rows = []
    for dev, name, row in entries:
        mapping[row.split(" ·", 1)[0].strip()] = (dev, name)
        rows.append(row)
    picked = _choose_from_list(rows, "Tick the targets to import:", "FITS Importer",
                               multiple=True)
    if picked is None:
        info("Picker cancelled — nothing imported.")
        return
    chosen_a, chosen_s = set(), set()
    for row in picked:
        key = row.split("·", 1)[0].strip()
        if key in mapping:
            dev, name = mapping[key]
            (chosen_a if dev == "asiair" else chosen_s).add(name)
    if not chosen_a and not chosen_s:
        info("No targets selected — nothing imported.")
        return
    info(f"Importing {len(chosen_a) + len(chosen_s)} target(s)")
    print()
    if chosen_a:
        run_import(state, args, only_targets=chosen_a)
    if chosen_s:
        try:
            sscan = scan_seestar(state)
        except RuntimeError as e:
            error(f"Seestar NOT imported: {e}")
            sscan = None
        if sscan:
            if not args.dry_run:
                state.seestar_seen(sscan)
            run_seestar_import(state, sscan, args, only_targets=chosen_s)

def offer_eject(args):
    """End-of-run eject offer covering every mounted camera (CLI only —
    the panel has its own Eject button and never routes through main())."""
    if args.dry_run:
        return
    vols = []
    if os.path.isdir(ASIAIR_VOLUME):
        vols.append(("ASIAir", ASIAIR_VOLUME))
    sv = seestar_volume()
    if sv:
        vols.append(("Seestar", sv))
    if not vols:
        return
    label = " + ".join(name for name, _v in vols)
    print()
    resp = safe_input(f"Eject the {label} drive{'s' if len(vols) > 1 else ''}? [y/N] ",
                      default="n")
    if resp.lower() != "y":
        return
    for name, v in vols:
        if eject_volume(v):
            success(f"{name} ejected safely.")
        else:
            warn(f"Could not eject {name} — try manually.")

def run_menu(state, args):
    choice = _choose_from_list(
        ["Backup Report", "Open Dashboard", "Verify Backups", "Never-Import List", "Dry Run"],
        "ASIAir tools:", "FITS Importer", multiple=False)
    if not choice:
        return
    c = choice[0]
    if c == "Backup Report":
        run_report(state)
    elif c == "Open Dashboard":
        open_dashboard(state)
    elif c == "Verify Backups":
        run_verify(state, deep=False)
    elif c == "Never-Import List":
        run_skiplist_dialog(state)
    elif c == "Dry Run":
        args.dry_run = True
        run_import(state, args)

def open_dashboard(state):
    path = generate_dashboard(state)
    if not path:
        error("No ledger yet — nothing to show.")
        return
    state.publish_mirror()
    mirror_copy = os.path.join(MIRROR_DIR, "dashboard.html")
    target_path = mirror_copy if os.path.isfile(mirror_copy) else path
    success(f"Dashboard: {target_path}")
    open_path(target_path)

def run_skiplist_dialog(state):
    scan = scan_camera(state)
    rows, mapping = [], {}
    for i, t in enumerate(scan["targets"], 1):
        mark = "✓ SKIPPED — " if t["name"] in state.skiplist else ""
        row = f"{i} · {mark}{t['name']} ({human_size(t['total_bytes'])})"
        rows.append(row)
        mapping[str(i)] = t["name"]
    picked = _choose_from_list(rows, "Select targets to TOGGLE on the never-import list:",
                               "Never-Import List", multiple=True)
    if not picked:
        return
    for row in picked:
        idx = row.split("·", 1)[0].strip()
        name = mapping.get(idx)
        if not name:
            continue
        if name in state.skiplist:
            state.skiplist.remove(name)
            success(f"Un-skipped: {name}")
        else:
            state.skiplist.append(name)
            success(f"Never import: {name}")
        state.history_event("skiplist", target=name,
                            skipped=name in state.skiplist)
    state.save_skiplist()
    state.publish_mirror()


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main():
    global VERBOSE
    p = argparse.ArgumentParser(description="BrettjoAstro FITS Importer — backup-first (ASIAir + Seestar)")
    p.add_argument("--targets", nargs="+", metavar="NAME",
                   help="import only these targets (camera folder names)")
    p.add_argument("--pick", action="store_true")
    p.add_argument("--menu", action="store_true")
    p.add_argument("--export-settings", nargs="?", const="", metavar="FILE",
                   help="write this computer's settings (names, never-import list, "
                        "equipment, portable config — NOT the ledger) to a file to "
                        "carry to your other computer (default: Desktop)")
    p.add_argument("--import-settings", metavar="FILE",
                   help="merge settings exported on another computer (adds what is "
                        "missing, never overwrites; --dry-run to preview)")
    p.add_argument("--version", action="version",
                   version=f"BrettjoAstro FITS Importer {VERSION} ({PLATFORM})")
    p.add_argument("--app-owner", action="store_true",
                   help="who runs this computer's importer: prints 'app PATH' (exit 0), "
                        "'web' (exit 1) or 'stale PATH' (exit 2)")
    p.add_argument("--archive-stale", action="store_true",
                   help="with --app-owner: rename a stale owner record aside (never deleted)")
    p.add_argument("--status", action="store_true",
                   help="one line: everything safe, or how many frames are only on this "
                        "computer (--json for the details; no lock, no camera)")
    p.add_argument("--json", action="store_true")
    p.add_argument("--scan-only", action="store_true")
    p.add_argument("--report", action="store_true")
    p.add_argument("--reconcile", action="store_true")
    p.add_argument("--verify", action="store_true")
    p.add_argument("--deep", action="store_true")
    p.add_argument("--baseline", action="store_true")
    p.add_argument("--unbaseline", metavar="NAME")
    p.add_argument("--restore-ledger", action="store_true")
    p.add_argument("--dashboard", action="store_true",
                   help="regenerate and open the status page (no camera needed)")
    p.add_argument("--refresh-metadata", action="store_true",
                   help="back-fill ledger metadata from filenames/FITS (safe, repeatable)")
    p.add_argument("--ship", action="store_true",
                   help="file verified frames into the archive on the PC over the mounted share "
                        "(no camera needed; safe to repeat; --dry-run lists only)")
    p.add_argument("--no-ship", action="store_true",
                   help="do not file frames to the archive after this import")
    p.add_argument("--tidy-stacks", action="store_true",
                   help="list archived Seestar stacks outranked by a higher stack from "
                        "the SAME night and offer to remove them (typed DELETE; "
                        "--dry-run lists only)")
    p.add_argument("--set-filter", nargs=2, metavar=("TARGET", "FILTER"),
                   help="correct the recorded filter on a target's ledger entries "
                        "('none' clears); add --night YYYY-MM-DD to limit to one night")
    p.add_argument("--discard", metavar="TARGET",
                   help="delete a Seestar target from the CAMERA without importing it "
                        "(never-backed-up frames: typed DISCARD confirmation, refused if "
                        "anything is already backed up; --night limits it to one night; "
                        "--dry-run lists only). Never touches the ASIAir.")
    p.add_argument("--reason", metavar="TEXT",
                   help="why a --discard was done (kept in the ledger and the report)")
    p.add_argument("--night", metavar="YYYY-MM-DD",
                   help="restrict --set-filter or --discard to a single observing night")
    p.add_argument("--skip-target", metavar="NAME")
    p.add_argument("--unskip-target", metavar="NAME")
    p.add_argument("--merge-days", nargs="+", metavar="ARG",
                   help="TARGET DAY DAY ... — merge the listed Day folders into "
                        "the lowest (heals a night split by interrupted imports)")
    p.add_argument("--renumber-day", nargs=3, metavar=("TARGET", "FROM", "TO"),
                   help="rename one Day folder to a different number "
                        "(folder + ledger), e.g. after removing empty fragments")
    p.add_argument("--explain-cal", action="store_true")
    p.add_argument("--loose-cal", action="store_true")
    p.add_argument("--no-checksum", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--all", action="store_true")
    args = p.parse_args()
    VERBOSE = args.verbose

    # Read-only answers for the installers, watchers and the app: no lock,
    # no camera, no astropy (1.5.3)
    if args.app_owner:
        owner, rec = app_owner_state()
        if owner == "stale" and args.archive_stale:
            try:
                print(f"archived {archive_stale_owner()}")
                sys.exit(0)
            except OSError as e:
                error(f"Could not archive {APP_OWNER_FILE}: {e}")
        print("web" if rec is None else f"{owner} {rec.get('appPath') or ''}")
        sys.exit({"app": 0, "web": 1, "stale": 2}[owner])
    if args.status:
        with contextlib.redirect_stdout(sys.stderr if args.json else sys.stdout):
            st = State()            # load warnings never mix into --json
        s = status_summary(st)
        print(json.dumps(s) if args.json else s["text"])
        sys.exit(0)

    refresh_camera_volumes(force=True)

    if args.targets is not None and len(args.targets) == 0:
        error("--targets given with no names.")
        sys.exit(2)

    state = State()
    if state.ledger_too_new():
        sys.exit(2)

    def reload():
        """Re-read the ledger under the lock (H2), and refuse it again if a
        newer importer replaced it since the check above: before anything is
        copied, tagged or deleted (U3)."""
        state.load()
        if state.ledger_too_new():
            sys.exit(2)

    def locked(fn):
        """Every command that SAVES the ledger holds the import lock and
        re-reads the ledger under it — a whole-ledger save from a command that
        loaded it earlier would otherwise wipe what a concurrent import just
        wrote (1.4.3 review finding H2)."""
        if not acquire_lock():
            sys.exit(1)
        try:
            reload()
            return fn()
        finally:
            release_lock()

    # State-only commands that don't need the camera:
    if args.export_settings is not None:
        run_export_settings(state, args.export_settings or None)
        return
    if args.import_settings:
        if args.dry_run:
            run_import_settings(state, args.import_settings, dry_run=True)
        else:
            locked(lambda: run_import_settings(state, args.import_settings))
        return
    if args.dashboard:
        open_dashboard(state)
        return
    if args.restore_ledger:
        locked(state.restore_from_mirror)
        return
    if args.refresh_metadata:
        locked(lambda: run_refresh_metadata(state))
        return
    if args.tidy_stacks:
        if args.dry_run:
            run_tidy_stacks(state, dry_run=True)
        else:
            locked(lambda: run_tidy_stacks(state))
        return
    if args.ship:
        if not acquire_lock("ship"):
            sys.exit(1)
        try:
            reload()
            run_ship(state, dry_run=args.dry_run, checksum=not args.no_checksum)
        finally:
            release_lock()
        return
    if args.discard:
        if not acquire_lock("discard"):
            sys.exit(1)
        try:
            reload()
            res = run_discard(state, args.discard, night=args.night,
                              reason=args.reason or "", dry_run=args.dry_run)
        finally:
            release_lock()
        sys.exit(1 if res in ("refused", "partial") else 0)
    if args.merge_days:
        if len(args.merge_days) < 3:
            error("--merge-days wants: TARGET DAY DAY ...")
            sys.exit(2)
        locked(lambda: run_merge_days(state, args.merge_days[0], args.merge_days[1:]))
        return
    if args.renumber_day:
        locked(lambda: run_renumber_day(state, args.renumber_day[0],
                                        args.renumber_day[1], args.renumber_day[2]))
        return
    if args.set_filter:
        locked(lambda: run_set_filter(state, args.set_filter[0], args.set_filter[1],
                                      night=args.night))
        return
    if args.unbaseline:
        locked(lambda: run_unbaseline(state, args.unbaseline))
        return
    if args.skip_target:
        def _skip():
            if args.skip_target not in state.skiplist:
                state.skiplist.append(args.skip_target)
                state.save_skiplist()
                state.history_event("skiplist", target=args.skip_target, skipped=True)
            success(f"Never import: {args.skip_target}")
            state.publish_mirror()
        locked(_skip)
        return
    if args.unskip_target:
        def _unskip():
            if args.unskip_target in state.skiplist:
                state.skiplist.remove(args.unskip_target)
                state.save_skiplist()
                state.history_event("skiplist", target=args.unskip_target, skipped=False)
            success(f"Un-skipped: {args.unskip_target}")
            state.publish_mirror()
        locked(_unskip)
        return

    # Everything else needs a camera (either device):
    asiair_here = os.path.isdir(ASIAIR_VOLUME)
    svol = seestar_volume()
    if not asiair_here and not svol:
        if IS_WINDOWS or os.environ.get("ASTRO_DRIVE_ROOTS") is not None:
            error("No camera found — no drive letter carries an ASIAir (Autorun\\) "
                  "or a Seestar (MyWorks\\). Checked: "
                  + (", ".join(_drive_roots()) or "no drives besides the system drive") + ".")
        else:
            error(f"No camera found — looked for ASIAir at {ASIAIR_VOLUME} "
                  f"and a Seestar (MyWorks) at {', '.join(SEESTAR_VOLUMES)}.")
        error("Connect a camera via USB and make sure the drive is mounted.")
        sys.exit(1)

    if args.scan_only:
        run_scan_only(state)   # read-only, no lock, no prompts
        return

    if not acquire_lock():
        sys.exit(1)
    try:
        reload()       # re-read under the lock (H2), refused if newer (U3)
        print("═══════════════════════════════════════════════════════════════")
        print("  BrettjoAstro FITS Importer — backup-first (ASIAir + Seestar)")
        print("═══════════════════════════════════════════════════════════════")
        print()
        if asiair_here:
            info(f"ASIAir:      {ASIAIR_VOLUME} → {DEST_DIR}")
        if svol:
            info(f"Seestar:     {svol}")
        info(f"Ledger:      {STATE_DIR}")
        if args.dry_run:
            warn("DRY RUN MODE — no files will be changed")
        if args.loose_cal:
            warn("LOOSE CALIBRATION MATCHING (v1 rules) for this run")
        print()

        os.makedirs(DEST_DIR, exist_ok=True)

        # First run: no ledger → offer restore, then baseline
        if not state.has_ledger():
            if getattr(state, "ledger_corrupt", False):
                error("ledger.json EXISTS but is unreadable (and no usable "
                      ".bak). Refusing to treat this as a first run — a "
                      "baseline now would mark never-copied files as "
                      "imported. Restore the ledger from the iCloud mirror "
                      "or a backup, then rerun.")
                sys.exit(1)
            warn("No import ledger found.")
            if os.path.isfile(os.path.join(MIRROR_DIR, "ledger.json")):
                if state.restore_from_mirror():
                    pass
            if not state.has_ledger():
                if args.baseline or safe_input(
                        "Mark everything currently on the camera as already imported, "
                        "WITHOUT copying it? Only say yes if you already have copies of "
                        "these files on this Mac (no = back everything up) [y/N] ",
                        default="n").lower() == "y":
                    run_baseline(state, assume_yes=args.baseline)
                    if not (args.report or args.reconcile or args.verify):
                        return
                else:
                    state.new_ledger()
                    info("Starting with an empty ledger — everything on camera counts as new.")

        if args.baseline:
            run_baseline(state, assume_yes=True)
            return
        if args.reconcile:
            run_reconcile(state, deep=not args.no_checksum)
            return
        if args.verify:
            run_verify(state, deep=args.deep)
            return
        if args.report:
            run_report(state)
            return
        if args.menu:
            run_menu(state, args)
            return
        if args.pick:
            run_pick(state, args)
            offer_eject(args)
            return

        # --all guard (spec §10)
        if args.all and asiair_here:
            scan = scan_camera(state)
            dup_files = sum(len(t["files"]) - len(t["new"]) for t in scan["targets"])
            dup_bytes = sum(sum(f["size"] for f in t["files"]) - t["new_bytes"]
                            for t in scan["targets"])
            if dup_files:
                warn(f"--all will RE-COPY {dup_files} already-imported frames "
                     f"({human_size(dup_bytes)}) into new Day folders.")
                if safe_input("Continue? [y/N] ", default="n").lower() != "y":
                    info("Cancelled.")
                    return

        only = set(args.targets) if args.targets else None
        if asiair_here:
            run_import(state, args, only_targets=only)
        if svol:
            try:
                sscan = scan_seestar(state)
            except RuntimeError as e:
                # The designed identity refusal — a clean message, never a
                # traceback (pass-2 finding). Nothing was scanned or written.
                error(f"Seestar NOT imported: {e}")
                sscan = None
                if not asiair_here:
                    sys.exit(1)
        if svol and sscan:
            if not args.dry_run:
                state.seestar_seen(sscan)
                if sscan["disk"]:
                    state.ledger["lastSeestarDisk"] = sscan["disk"]
                state._dirty = True
            run_seestar_import(state, sscan, args, only_targets=only)
        # File what just arrived into the archive on the PC while the lock is
        # still held (1.4.0). Quiet no-op when the share is not mounted.
        if not args.dry_run and not args.no_ship:
            try:
                if not archive_reachable() and ARCHIVE_URL:
                    _try_mount_archive(ARCHIVE_MOUNT, ARCHIVE_URL)
                if archive_reachable():
                    print()
                    run_ship(state, checksum=not args.no_checksum)
            except Exception as e:
                warn(f"Ship after import failed (frames are safe on this Mac): {e}")
        offer_eject(args)
    finally:
        release_lock()


def _platform_bootstrap(script_path):
    """Windows only: run in UTF-8 mode (every report, log and ledger line is
    UTF-8, and a cp1252 console can't print a ✓), send output somewhere when
    started windowless by pythonw, and switch on console colours."""
    if not IS_WINDOWS:
        return
    if not sys.flags.utf8_mode and not getattr(sys, "frozen", False):
        # the launchers all pass -X utf8; this is only the safety net (never
        # in a frozen app: its executable is the app, not Python). Wait
        # for the child through Ctrl+C (it gets the Ctrl+C too, and must be
        # allowed to finish its cleanup — lock release, ledger save).
        child = subprocess.Popen([sys.executable, "-X", "utf8", script_path, *sys.argv[1:]])
        while True:
            try:
                sys.exit(child.wait())
            except KeyboardInterrupt:
                continue
    if sys.stdout is None or sys.stderr is None:            # pythonw: no console
        logdir = os.path.join(STATE_DIR, "Logs")
        os.makedirs(logdir, exist_ok=True)
        name = os.path.splitext(os.path.basename(script_path))[0]
        f = open(os.path.join(logdir, f"{name}.console.log"), "a", encoding="utf-8",
                 buffering=1)
        sys.stdout = sys.stdout or f
        sys.stderr = sys.stderr or f
        return
    try:
        # ANSI colours in a real console only (NUL also reports isatty, and
        # os.system("") there would flash a window) — ENABLE_VIRTUAL_TERMINAL
        import ctypes
        import msvcrt
        k32 = ctypes.windll.kernel32
        h = msvcrt.get_osfhandle(sys.stdout.fileno())
        mode = ctypes.c_uint32()
        if k32.GetConsoleMode(h, ctypes.byref(mode)):
            k32.SetConsoleMode(h, mode.value | 0x0004)
    except Exception:
        pass


if __name__ == "__main__":
    _platform_bootstrap(os.path.abspath(__file__))
    main()
