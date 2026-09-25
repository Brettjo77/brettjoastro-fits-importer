"""Shared fake-camera environment for the unified Astro Import test suites.

Everything a test starts runs in TEST MODE (1.5.2): ASTRO_TEST_ROOT names a
temp folder; the engine, panel, watcher and self-test refuse any path outside
it and record (never perform) dialogs, notifications, ejects, mounts and
"open" in <root>/os-calls.jsonl. make_env() builds every launched env."""
import hashlib
import json
import os
import site
import socket
import subprocess
import sys
import tempfile

BUILD = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(BUILD, "astro-import.py")

# The only keys taken from the parent environment; everything else is set
# below (an inherited ASTRO_*, SEESTAR_* or HOME must never reach a test).
ALLOWED_PARENT_ENV = ("PATH", "SYSTEMROOT", "SystemRoot", "SYSTEMDRIVE", "WINDIR", "COMSPEC",
                      "PATHEXT", "TEMP", "TMP", "TMPDIR", "LANG", "LC_ALL", "LC_CTYPE",
                      "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE",
                      "__CF_USER_TEXT_ENCODING")
# where this Python's --user packages live (astropy on the PC), found from the
# REAL home at startup: with a fake home, child Pythons would lose them
_USER_BASE = site.getuserbase()

def free_port():
    """A port nothing listens on right now, and never the real panel's 8765."""
    while True:
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        if port != 8765:
            return port

def make_env(root, **extra):
    """The whole environment of anything a test starts: the allowlisted parent
    keys, test mode, a fake home and every engine path inside `root`, then
    `extra` (None removes a key; to mean "no camera", point at a missing path
    inside the root instead)."""
    env = {}
    for k in ALLOWED_PARENT_ENV:
        v = os.environ.get(k)
        if v is not None and k.upper() not in (x.upper() for x in env):
            env[k] = v          # Windows keys ignore case: SystemRoot once
    home = os.path.join(root, "home")
    os.makedirs(home, exist_ok=True)
    env.update({
        "ASTRO_TEST_ROOT": root,
        "HOME": home, "USERPROFILE": home,
        "LOCALAPPDATA": os.path.join(home, "AppData", "Local"),
        "APPDATA": os.path.join(home, "AppData", "Roaming"),
        "ASIAIR_VOLUME": os.path.join(root, "ASIAIR"),
        "ASIAIR_DEST": os.path.join(root, "dest", "ZWO ASI AIR"),
        "ASIAIR_CAL_LIBRARY": os.path.join(root, "dest", "ASIAir Calibration Library"),
        "ASIAIR_STATE": os.path.join(root, "state"),
        "ASIAIR_MIRROR": os.path.join(root, "mirror"),
        "ASIAIR_EQUIPMENT": os.path.join(root, "equipment.json"),
        "ASIAIR_RECEIPTS": os.path.join(root, "receipts"),
        "ASIAIR_LEGACY_NAMES": os.path.join(root, "no-legacy.json"),
        "ASIAIR_CONFIG": os.path.join(root, "no-config.json"),
        "SEESTAR_VOLUME": os.path.join(root, "Seestar"),
        "SEESTAR_DEST_S30": os.path.join(root, "dest", "Seestar S30 Pro"),
        "SEESTAR_DEST_S50": os.path.join(root, "dest", "Seestar S50"),
        "SEESTAR_DEST_S30_ORIG": os.path.join(root, "dest", "Seestar S30"),
        "SEESTAR_DEST_S50PRO": os.path.join(root, "dest", "Seestar S50 Pro"),
        "ASTRO_ARCHIVE_MOUNT": os.path.join(root, "archive-mount"),
        # never look at the real machine's drives/volumes during a test
        "ASTRO_DRIVE_ROOTS": os.path.join(root, "no-real-drives"),
        "ASTRO_ARCHIVE_URL": "",
        "ASTRO_PANEL_PORT": str(free_port()),
        # the same UTF-8 everywhere (Windows consoles default to cp1252)
        "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUSERBASE": _USER_BASE,
    })
    for k, v in extra.items():
        if v is None:
            env.pop(k, None)
        else:
            env[k] = v
    return env

def isolate_runner():
    """Put the test runner itself in test mode, before it loads the engine
    in-process: os.environ becomes make_env() of a fresh session root."""
    root = tempfile.mkdtemp(prefix="astro-test-session-")
    env = make_env(root)
    os.environ.clear()
    os.environ.update(env)
    return root

def instance_id(state_dir):
    """The "instance" /api/ping reports for a panel keeping its ledger in
    state_dir (so a test knows it is talking to its OWN panel)."""
    return hashlib.sha256(os.path.realpath(state_dir).encode("utf-8")).hexdigest()[:16]

def os_calls(root, kind=None):
    """What test mode recorded instead of doing (<root>/os-calls.jsonl)."""
    out = []
    try:
        with open(os.path.join(root, "os-calls.jsonl"), encoding="utf-8") as f:
            for ln in f:
                try:
                    out.append(json.loads(ln))
                except ValueError:
                    pass
    except OSError:
        pass
    return [r for r in out if kind is None or r.get("kind") == kind]

def fake_os_commands(root):
    """A folder of stand-ins for the Mac's dialog, eject and "open" commands
    (and a `browser` for $BROWSER) that only write <root>/EXECUTED: put it
    first on PATH, and EXECUTED appearing means one of them ran (Mac/Linux;
    Windows runs no shell scripts)."""
    d = os.path.join(root, "fake-os-commands")
    os.makedirs(d, exist_ok=True)
    for name in ("osascript", "diskutil", "open", "browser"):
        p = os.path.join(d, name)
        with open(p, "w") as f:
            f.write(f'#!/bin/sh\necho "{name} $*" >> "{os.path.join(root, "EXECUTED")}"\n')
        os.chmod(p, 0o755)
    return d

def executed(root):
    """Which fake OS commands ran ("" = none)."""
    try:
        with open(os.path.join(root, "EXECUTED"), encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""

def _card(key, value, string=False):
    if string:
        v = f"'{value}'"
        return f"{key:<8}= {v:<20}".ljust(80)
    return f"{key:<8}= {str(value):>20}".ljust(80)

def make_fits(path, focallen=749, gain=200, exptime=300.0,
              dateobs="2026-07-20T22:05:12", uniq=""):
    cards = [
        _card("SIMPLE", "T"), _card("BITPIX", 8), _card("NAXIS", 0),
        _card("FOCALLEN", focallen), _card("GAIN", gain), _card("EXPTIME", exptime),
        _card("DATE-OBS", dateobs, string=True),
        _card("INSTRUME", "ZWO ASI585MC Air", string=True),
        ("COMMENT " + (uniq or os.path.basename(path))).ljust(80),
        "END".ljust(80),
    ]
    header = "".join(cards)
    header += " " * (2880 - len(header) % 2880 if len(header) % 2880 else 0)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(header)

def make_seestar_fits(path, creator="ZWO Seestar S30 Pro", exptime=10.0,
                      dateobs="2026-06-18T22:44:02", uniq=""):
    """Minimal Seestar frame: metadata lives in the header (CREATOR/EXPTIME/
    DATE-OBS), the filename carries nothing."""
    cards = [
        _card("SIMPLE", "T"), _card("BITPIX", 8), _card("NAXIS", 0),
        _card("EXPTIME", exptime),
        _card("DATE-OBS", dateobs, string=True),
    ]
    if creator:
        cards.append(_card("CREATOR", creator, string=True))
    cards += [
        ("COMMENT " + (uniq or os.path.basename(path))).ljust(80),
        "END".ljust(80),
    ]
    header = "".join(cards)
    header += " " * (2880 - len(header) % 2880 if len(header) % 2880 else 0)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(header)

def stamp_to_dateobs(stamp):
    """'20260618-224402' → '2026-06-18T22:44:02'"""
    d, t = stamp.split("-")
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}T{t[:2]}:{t[2:4]}:{t[4:6]}"

def light_name(target, exp="300.0s", gain=200, dt="20260720-220512", rot="120.0deg",
               temp="-10.0C", filt="LUltimate", seq="0001"):
    f = f"{filt}_" if filt else ""
    return f"Light_{target}_{exp}_Bin1_585MC_gain{gain}_{dt}_{rot}_{temp}_{f}{seq}.fit"

def cal_name(kind, exp, dt, rot="120.0deg", temp="-10.0C", filt=None, seq="0001", gain=200):
    f = f"{filt}_" if filt else ""
    return f"{kind}_{exp}_Bin1_585MC_gain{gain}_{dt}_{rot}_{temp}_{f}{seq}.fit"

class Env:
    def __init__(self, name, asiair=True, seestar=False):
        self.root = tempfile.mkdtemp(prefix=f"v2test-{name}-")
        self.cam = os.path.join(self.root, "ASIAIR")
        self.svol = os.path.join(self.root, "Seestar")
        self.myworks = os.path.join(self.svol, "MyWorks")
        self.dest = os.path.join(self.root, "dest", "ZWO ASI AIR")
        self.sdest30 = os.path.join(self.root, "dest", "Seestar S30 Pro")
        self.sdest30o = os.path.join(self.root, "dest", "Seestar S30")
        self.sdest50 = os.path.join(self.root, "dest", "Seestar S50")
        self.sdest50p = os.path.join(self.root, "dest", "Seestar S50 Pro")
        self.lib = os.path.join(self.root, "dest", "ASIAir Calibration Library")
        self.state = os.path.join(self.root, "state")
        self.mirror = os.path.join(self.root, "mirror")
        self.receipts = os.path.join(self.root, "receipts")
        if asiair:
            os.makedirs(self.cam, exist_ok=True)
        if seestar:
            os.makedirs(self.myworks, exist_ok=True)
        eqp = os.path.join(self.root, "equipment.json")
        with open(eqp, "w") as f:
            json.dump({"telescopes": []}, f)
        self.env = make_env(self.root, **{
            "ASIAIR_VOLUME": self.cam, "ASIAIR_DEST": self.dest,
            "ASIAIR_CAL_LIBRARY": self.lib, "ASIAIR_STATE": self.state,
            "ASIAIR_MIRROR": self.mirror, "ASIAIR_EQUIPMENT": eqp,
            "ASIAIR_RECEIPTS": self.receipts,
            "ASIAIR_LEGACY_NAMES": os.path.join(self.root, "no-legacy.json"),
            "ASIAIR_CONFIG": os.path.join(self.root, "no-config.json"),
            "SEESTAR_VOLUME": self.svol,
            "SEESTAR_DEST_S30": self.sdest30, "SEESTAR_DEST_S50": self.sdest50,
            "SEESTAR_DEST_S30_ORIG": self.sdest30o,
            "SEESTAR_DEST_S50PRO": self.sdest50p,
            "ASTRO_ARCHIVE_MOUNT": os.path.join(self.root, "archive-mount"),
            "ASTRO_DRIVE_ROOTS": os.path.join(self.root, "no-real-drives"),
        })
        self.archive = os.path.join(self.root, "archive-mount")

    def run(self, *args, stdin="", extra_env=None):
        env = dict(self.env)
        if extra_env:
            env.update(extra_env)
        return subprocess.run([sys.executable, SCRIPT, *args], env=env,
                              input=stdin, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=120)

    def ledger(self):
        with open(os.path.join(self.state, "ledger.json")) as f:
            return json.load(f)

    def add_light(self, subdir, target, seq, dt="20260720-220512", exp="300.0s",
                  focallen=749, filt="LUltimate", rot="120.0deg"):
        name = light_name(target, exp=exp, dt=dt, filt=filt, seq=seq, rot=rot)
        path = os.path.join(self.cam, subdir, "Light", target, name)
        make_fits(path, focallen=focallen,
                  exptime=float(exp[:-1]) if exp.endswith("s") and not exp.endswith("ms") else 0.02,
                  uniq=f"{target}-{subdir}-{seq}-{dt}")
        return path

    def add_cal(self, kind, exp, dt, filt=None, rot="120.0deg", focallen=749, seq="0001"):
        name = cal_name(kind, exp, dt, rot=rot, filt=filt, seq=seq)
        path = os.path.join(self.cam, "Autorun", kind, name)
        make_fits(path, focallen=focallen, uniq=f"cal-{kind}-{exp}-{dt}-{seq}")
        return path

    # ── Seestar fixtures (MyWorks sibling-folder semantics) ────────────────
    def add_seestar_sub(self, project, stamp, creator="ZWO Seestar S30 Pro",
                        exptime=10.0):
        """Sub light frame: MyWorks/<project>_sub/<stamp>.fit (bare-stamp name)."""
        path = os.path.join(self.myworks, f"{project}_sub", f"{stamp}.fit")
        make_seestar_fits(path, creator=creator, exptime=exptime,
                          dateobs=stamp_to_dateobs(stamp),
                          uniq=f"{project}-sub-{stamp}")
        return path

    def add_seestar_stack(self, project, count, stamp, creator="ZWO Seestar S30 Pro",
                          exp="10.0s", filt="IRCUT"):
        """Stacked result: MyWorks/<project>/Stacked_<count>_<...>_<stamp>.fit"""
        base = project.split("_mosaic")[0]
        name = f"Stacked_{count}_{base}_{exp}_{filt}_{stamp}.fit"
        path = os.path.join(self.myworks, project, name)
        make_seestar_fits(path, creator=creator,
                          dateobs=stamp_to_dateobs(stamp),
                          uniq=f"{project}-stack-{count}-{stamp}")
        return path

    def add_seestar_panel(self, mosaic_project, stamp, creator="ZWO Seestar S30 Pro"):
        """Panel stack: MyWorks/<mosaic_project>_pt/<stamp>.fit
        (mosaic_project should end in '_mosaic')."""
        path = os.path.join(self.myworks, f"{mosaic_project}_pt", f"{stamp}.fit")
        make_seestar_fits(path, creator=creator,
                          dateobs=stamp_to_dateobs(stamp),
                          uniq=f"{mosaic_project}-panel-{stamp}")
        return path

    def add_seestar_nondso(self, mode_folder, filename, creator="ZWO Seestar S50"):
        """Non-DSO content, e.g. ('Solar_photo', 'Solar_001.fit') or
        ('Lunar_video', 'Moon.mp4')."""
        path = os.path.join(self.myworks, mode_folder, filename)
        if filename.lower().endswith(".fit"):
            make_seestar_fits(path, creator=creator, uniq=f"{mode_folder}-{filename}")
        else:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as f:
                f.write(b"FAKEVIDEO-" + filename.encode() + b"-" * 100)
        return path
