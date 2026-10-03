"""Shared fake-camera environment for the unified Astro Import test suites.

Everything a test starts runs in TEST MODE (1.5.2): ASTRO_TEST_ROOT names a
temp folder; the engine, panel, watcher and self-test refuse any path outside
it and record (never perform) dialogs, notifications, ejects, mounts and
"open" in <root>/os-calls.jsonl. make_env() builds every launched env."""
import contextlib
import hashlib
import json
import os
import site
import socket
import subprocess
import sys
import tempfile
import time

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

NO_DELETE_SITE = r'''
# Test only (1.7.0): the archive share user's rights from decision D7 (spec
# P6, P8, 10.1), for a child Python started with teh.no_delete_env(). In
# the archive tree: create, never delete, rename or write over an existing
# file. In _verify: nothing, except inside mac/ and lock/ (Modify). pc/ is
# read only. Every refused attempt is written to <root>/denied.jsonl.
import errno, json, os, shutil, builtins
_ARCH = os.environ.get("ASTRO_TEST_NO_DELETE")
if _ARCH:
    _ARCH = os.path.normcase(os.path.realpath(_ARCH))
    _LOG = os.path.join(os.environ["ASTRO_TEST_ROOT"], "denied.jsonl")
    _orig = {"open": builtins.open, "os_open": os.open, "fdopen": os.fdopen,
             "mkdir": os.mkdir, "utime": os.utime}
    def _rel(p):
        try:
            p = os.path.normcase(os.path.realpath(os.fspath(p)))
        except (TypeError, ValueError):
            return None
        if p == _ARCH:
            return []
        if not p.startswith(_ARCH + os.sep):
            return None
        return p[len(_ARCH) + 1:].split(os.sep)
    def _zone(p):
        parts = _rel(p)
        if parts is None:
            return None
        if parts[:1] == ["_verify"]:
            if len(parts) >= 3 and parts[1] in ("mac", "lock"):
                return "modify"
            return "verify"               # _verify itself, its files, pc/, mac and lock as folders
        return "tree"
    def _deny(op, p):
        with _orig["open"](_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({"op": op, "path": os.fspath(p)}) + "\n")
        raise PermissionError(errno.EACCES, "Permission denied (test: the share user's rights)", os.fspath(p))
    def _guard_change(op, *paths):
        for p in paths:
            z = _zone(p)
            if z is not None and z != "modify":
                _deny(op, p)
    def _wrap(mod, name, n):
        orig = getattr(mod, name)
        def w(*a, **k):
            _guard_change(name, *a[:n])
            return orig(*a, **k)
        setattr(mod, name, w)
    for _name in ("remove", "unlink", "rmdir"):
        _wrap(os, _name, 1)
    _wrap(os, "rename", 2); _wrap(os, "replace", 2)
    _wrap(shutil, "move", 2); _wrap(shutil, "rmtree", 1)
    def _guard_write(p, creating):
        """creating: an exclusive create, which fails by itself on a taken name."""
        z = _zone(p)
        if z is None or z == "modify":
            return
        exists = os.path.lexists(p)
        if exists and creating:
            return
        if z == "verify":
            _deny("write", p)
        if exists:
            _deny("overwrite", p)
    def _open(file, mode="r", *a, **k):
        if isinstance(file, (str, bytes, os.PathLike)) and any(c in mode for c in "wax+"):
            _guard_write(file, creating="x" in mode)
        return _orig["open"](file, mode, *a, **k)
    builtins.open = _open
    _CUT = int(os.environ.get("ASTRO_TEST_CUT_SHIP") or 0)
    _made, _cut_fds = [0], set()
    def _os_open(path, flags, mode=0o777, *a, **k):
        if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
            _guard_write(path, creating=bool(flags & os.O_EXCL))
        fd = _orig["os_open"](path, flags, mode, *a, **k)
        if _CUT and _zone(path) == "tree" and flags & os.O_EXCL:
            _made[0] += 1
            if _made[0] == _CUT:
                _cut_fds.add(fd)
        return fd
    os.open = _os_open
    class _CutFile:
        """The share goes away mid-copy: half the bytes land, then EIO."""
        def __init__(self, f):
            self.f = f
        def write(self, b):
            self.f.write(b[:max(1, len(b) // 2)])
            self.f.flush()
            raise OSError(errno.EIO, "test: the share went away mid-copy")
        def __getattr__(self, n):
            return getattr(self.f, n)
        def __enter__(self):
            return self
        def __exit__(self, *a):
            self.f.close()
            return False
    def _fdopen(fd, *a, **k):
        f = _orig["fdopen"](fd, *a, **k)
        if fd in _cut_fds:
            _cut_fds.discard(fd)          # numbers are reused once closed
            return _CutFile(f)
        return f
    os.fdopen = _fdopen
    def _mkdir(path, *a, **k):
        if os.path.lexists(path):
            raise FileExistsError(errno.EEXIST, "File exists", os.fspath(path))
        if _zone(path) == "verify":
            _deny("mkdir", path)
        return _orig["mkdir"](path, *a, **k)
    os.mkdir = _mkdir
    def _utime(path, *a, **k):
        if _zone(path) == "verify":
            _deny("utime", path)
        return _orig["utime"](path, *a, **k)
    os.utime = _utime
# A file that can't be read just now (ASTRO_TEST_UNREADABLE, os.pathsep
# separated): opening it to read fails as a disk error would.
_UNREAD = {os.path.normcase(os.path.realpath(p))
           for p in (os.environ.get("ASTRO_TEST_UNREADABLE") or "").split(os.pathsep) if p}
if _UNREAD:
    _open_before = builtins.open
    def _open_unread(file, mode="r", *a, **k):
        if isinstance(file, (str, os.PathLike)) and \
                os.path.normcase(os.path.realpath(os.fspath(file))) in _UNREAD:
            raise OSError(errno.EIO, "test: a read error", os.fspath(file))
        return _open_before(file, mode, *a, **k)
    builtins.open = _open_unread
'''

def no_delete_env(root, archive, cut_ship=0):
    """Env additions that run a child Python with the archive share user's
    rights from 1.7.0 simulated on `archive` (see NO_DELETE_SITE): the PC
    setup's folders _verify/mac, _verify/lock and _verify/pc are made first,
    as the PC does. cut_ship=N cuts the N-th new archive file off mid-copy."""
    for d in ("mac", "lock", "pc"):
        os.makedirs(os.path.join(archive, "_verify", d), exist_ok=True)
    site = os.path.join(root, "no-delete-site")
    os.makedirs(site, exist_ok=True)
    with open(os.path.join(site, "sitecustomize.py"), "w", encoding="utf-8") as f:
        f.write(NO_DELETE_SITE)
    env = {"PYTHONPATH": site, "ASTRO_TEST_NO_DELETE": archive}
    if cut_ship:
        env["ASTRO_TEST_CUT_SHIP"] = str(cut_ship)
    return env

def backdate(path, seconds):
    """Make a file look `seconds` older: its modification time everywhere and,
    on Windows, its creation time too (the PC's sweep reads that there; on a
    Mac an earlier modification time pulls the creation time back with it)."""
    t = time.time() - seconds
    os.utime(path, (t, t))
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateFileW.restype = wintypes.HANDLE
        k32.CreateFileW.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                    wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD,
                                    wintypes.HANDLE)
        k32.SetFileTime.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.FILETIME),
                                    ctypes.POINTER(wintypes.FILETIME),
                                    ctypes.POINTER(wintypes.FILETIME))
        k32.CloseHandle.argtypes = (wintypes.HANDLE,)
        # FILE_WRITE_ATTRIBUTES, any sharing, OPEN_EXISTING, BACKUP_SEMANTICS (folders too)
        h = k32.CreateFileW(os.path.abspath(path), 0x100, 0x7, None, 3, 0x02000000, None)
        ft = int((t + 11644473600) * 10 ** 7)
        when = wintypes.FILETIME(ft & 0xFFFFFFFF, ft >> 32)
        k32.SetFileTime(h, ctypes.byref(when), None, ctypes.byref(when))
        k32.CloseHandle(h)

def read_error_env(root, paths):
    """Env additions under which a child Python can't read `paths` (a disk
    error on open). On Windows the engine reads through CreateFileW, so a
    test also holds the file with held_exclusively()."""
    site = os.path.join(root, "no-delete-site")
    os.makedirs(site, exist_ok=True)
    with open(os.path.join(site, "sitecustomize.py"), "w", encoding="utf-8") as f:
        f.write(NO_DELETE_SITE)
    return {"PYTHONPATH": site, "ASTRO_TEST_UNREADABLE": os.pathsep.join(paths)}

@contextlib.contextmanager
def held_exclusively(path):
    """Windows: hold `path` open with no sharing, so no other process can
    open it until the block ends. Elsewhere it does nothing."""
    if os.name != "nt":
        yield
        return
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateFileW.restype = wintypes.HANDLE
    k32.CreateFileW.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD,
                                wintypes.HANDLE)
    k32.CloseHandle.argtypes = (wintypes.HANDLE,)
    h = k32.CreateFileW(os.path.abspath(path), 0x80000000, 0, None, 3, 0, None)
    try:
        yield
    finally:
        k32.CloseHandle(h)

def denied(root):
    """What the simulated share rights refused (<root>/denied.jsonl)."""
    out = []
    try:
        with open(os.path.join(root, "denied.jsonl"), encoding="utf-8") as f:
            for ln in f:
                try:
                    out.append(json.loads(ln))
                except ValueError:
                    pass
    except OSError:
        pass
    return out

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
