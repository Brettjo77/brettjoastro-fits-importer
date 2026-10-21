#!/usr/bin/env python3
"""Sandbox test suite for asiair-import.py v2 (spec §12).
Simulated ASIAIR volume with real (minimal) FITS files; every scenario runs
the actual script as a subprocess with env-redirected paths."""

import sys
sys.dont_write_bytecode = True   # nothing is written beside the sources
import importlib.util
import json
import os
import re
import shutil
import subprocess
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_env_helper as teh  # noqa: E402
teh.isolate_runner()   # test mode for this process too, before any in-process engine load

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "astro-import.py")
# the one shared version, read from the engine: a release changes only its
# VERSION line, never these checks (1.5.4)
with open(SCRIPT, encoding="utf-8") as _f:
    VERSION = re.search(r'^VERSION = "(\d+\.\d+\.\d+)"$', _f.read(), re.M).group(1)
PASS, FAIL, SKIPPED = 0, 0, 0
FAILURES = []
DETAIL_CAP = 8000     # a failure's detail is kept whole up to this (1.7.0: 1400 hid the cause)
import atexit, traceback
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # Windows consoles (1.7.0)
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

def check(name, cond, detail=""):
    """One check. `cond` may be a callable: it is called here, and an exception is a
    FAIL with the traceback, never a crash of the suite (1.7.0)."""
    global PASS, FAIL
    if callable(cond):
        try:
            cond = cond()
        except Exception:
            cond, detail = False, traceback.format_exc() + (f"\n{detail}" if detail else "")
    if cond:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        line = sys._getframe(1).f_lineno
        FAILURES.append((f"{name}  [test_v2.py:{line}]", str(detail)))
        print(f"  FAIL  {name}   {str(detail)[:400]}")

def skip(name):
    """A check this OS or account can't run: printed and counted, never silent (1.7.0)."""
    global SKIPPED
    SKIPPED += 1
    print(f"  SKIP  {name}")

_SUMMARY_DONE = False
def summary(crash=None):
    """The one summary, printed once, also when the suite dies early (1.7.0): a crash
    half-way used to leave no summary at all, and the last FAIL lines scrolled away."""
    global _SUMMARY_DONE
    if _SUMMARY_DONE:
        return
    _SUMMARY_DONE = True
    print("\n" + "=" * 51)   # plain ASCII: a PowerShell pipe shows box characters as mojibake
    if crash:
        FAILURES.append(("CRASH: the suite stopped here, later checks did not run", crash))
    print(f"  {PASS} passed, {FAIL + (1 if crash else 0)} failed, {SKIPPED} skipped"
          + (f"  ({PASS + FAIL + SKIPPED} checks on this OS)" if SKIPPED else ""))
    for name, detail in FAILURES:
        d = detail if len(detail) <= DETAIL_CAP else detail[:DETAIL_CAP] + f"… [{len(detail) - DETAIL_CAP} more]"
        print(f"  ✗ {name}: {d}")
    sys.stdout.flush()

def _excepthook(tp, val, tb):
    summary("".join(traceback.format_exception(tp, val, tb)))
    sys.exit(1)
sys.excepthook = _excepthook
atexit.register(lambda: summary() if not _SUMMARY_DONE and (PASS or FAIL) else None)

# ── Minimal FITS generator ───────────────────────────────────────────────────
def _card(key, value, string=False):
    if string:
        v = f"'{value}'"
        return f"{key:<8}= {v:<20}".ljust(80)
    return f"{key:<8}= {str(value):>20}".ljust(80)

def make_fits(path, focallen=749, gain=200, exptime=300.0, dateobs="2026-07-20T22:05:12",
              uniq=""):
    cards = [
        _card("SIMPLE", "T"), _card("BITPIX", 8), _card("NAXIS", 0),
        _card("FOCALLEN", focallen), _card("GAIN", gain), _card("EXPTIME", exptime),
        _card("DATE-OBS", dateobs, string=True),
        _card("INSTRUME", "ZWO ASI585MC Air", string=True),
        _card("TELESCOP", "ZWO AM3N", string=True),
        ("COMMENT " + (uniq or os.path.basename(path))).ljust(80),
        "END".ljust(80),
    ]
    header = "".join(cards)
    header += " " * (2880 - len(header) % 2880 if len(header) % 2880 else 0)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(header)

def light_name(target, exp="300.0s", gain=200, dt="20260720-220512", rot="120.0deg",
               temp="-10.0C", filt="LUltimate", seq="0001"):
    return f"Light_{target}_{exp}_Bin1_585MC_gain{gain}_{dt}_{rot}_{temp}_{filt}_{seq}.fit"

def cal_name(kind, exp, dt, rot="120.0deg", temp="-10.0C", filt=None, seq="0001", gain=200):
    f = f"{filt}_" if filt else ""
    return f"{kind}_{exp}_Bin1_585MC_gain{gain}_{dt}_{rot}_{temp}_{f}{seq}.fit"

# ── Environment ──────────────────────────────────────────────────────────────
class Env:
    def __init__(self, name):
        self.root = tempfile.mkdtemp(prefix=f"v2test-{name}-")
        self.cam = os.path.join(self.root, "ASIAIR")
        self.dest = os.path.join(self.root, "dest", "ZWO ASI AIR")
        self.lib = os.path.join(self.root, "dest", "ASIAir Calibration Library")
        self.state = os.path.join(self.root, "state")
        self.mirror = os.path.join(self.root, "mirror")
        self.receipts = os.path.join(self.root, "receipts")
        os.makedirs(self.cam, exist_ok=True)
        eqp = os.path.join(self.root, "equipment.json")
        with open(eqp, "w") as f:
            json.dump({"telescopes": []}, f)
        # (make_env also puts the archive, Seestar trees and home in the root)
        self.env = teh.make_env(self.root, **{
            "ASIAIR_VOLUME": self.cam, "ASIAIR_DEST": self.dest,
            "ASIAIR_CAL_LIBRARY": self.lib, "ASIAIR_STATE": self.state,
            "ASIAIR_MIRROR": self.mirror, "ASIAIR_EQUIPMENT": eqp,
            "ASIAIR_RECEIPTS": self.receipts,
            "ASIAIR_LEGACY_NAMES": os.path.join(self.root, "no-legacy.json"),
            "ASIAIR_CONFIG": os.path.join(self.root, "no-config.json"),
            # keep the unified engine blind to any real Seestar in these chains
            "SEESTAR_VOLUME": os.path.join(self.root, "no-seestar"),
            "ASTRO_DRIVE_ROOTS": os.path.join(self.root, "no-real-drives"),
        })

    def run(self, *args, stdin=""):
        r = subprocess.run([sys.executable, SCRIPT, *args], env=self.env,
                           input=stdin, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        return r

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

def day_dir(env, display, day, panel=None):
    if panel:
        return os.path.join(env.dest, display, panel, "lights", f"{panel} Day {day}")
    return os.path.join(env.dest, display, "lights", f"{display} Day {day}")

def count_fits(d):
    if not os.path.isdir(d):
        return 0
    return sum(1 for f in os.listdir(d) if f.lower().endswith(".fit"))


# ═══════════════ CHAIN A: baseline → import → archive → day numbering ═══════
print("\n── Chain A: lifecycle ─────────────────────────────────────────")
A = Env("A")
for seq in ["0001", "0002", "0003"]:
    A.add_light("Plan", "M 81", seq, dt=f"20260501-22{seq[-2:]}00", focallen=749)
    A.add_light("Live", "Sh2-129", seq, dt=f"20260502-23{seq[-2:]}00", focallen=402)
A.add_cal("Bias", "1.0ms", "20260719-090000")
A.add_cal("Dark", "300.0s", "20260719-091000")
A.add_cal("Flat", "20.0ms", "20260720-090000", filt="LUltimate")

r = A.run("--baseline")
led = A.ledger()
check("A1 baseline records 6 lights", len(led["files"]) == 6, f"got {len(led['files'])}")
check("A1 baseline records 3 cal", len(led["calibration"]) == 3)
check("A1 audit flags missing local copies", "NO local copy found" in r.stdout)
check("A1 baseline entries unverified",
      all(not e["verifiedAtImport"] and e["origin"] == "baseline" for e in led["files"].values()))
check("A1 mirror published", os.path.isfile(os.path.join(A.mirror, "ledger.json")))

# A2: new frames → import
A.add_light("Plan", "M 81", "0004", dt="20260721-010000")
A.add_light("Plan", "M 81", "0005", dt="20260721-011000")
r = A.run(stdin="n\n")
d1 = day_dir(A, "M 81 - Bode's Galaxy", 1)
check("A2 Day 1 created with 2 frames", count_fits(d1) == 2, d1)
led = A.ledger()
imported = [e for e in led["files"].values() if e["origin"] == "import"]
check("A2 2 import entries, verified + sha", len(imported) == 2 and
      all(e["verifiedAtImport"] and e["sha256"] for e in imported))
check("A2 scope recorded", all(e.get("scope") == "Askar 107PHQ" for e in imported))
check("A2 capture detail recorded",
      all(e.get("gain") == 200 and e.get("exposureSeconds") == 300.0 and
          e.get("filter") == "LUltimate" for e in imported))
check("A2 manifest written", os.path.isfile(
    os.path.join(A.dest, "M 81 - Bode's Galaxy", ".imported_files")))
check("A2 library ingested all 3 cal",
      sum(count_fits(os.path.join(A.lib, s)) for s in ["biases", "darks", "flats"]) == 3)
caldir = os.path.join(d1, "calibration")
n_linked = sum(count_fits(os.path.join(caldir, s)) for s in ["biases", "darks", "flats"])
check("A2 calibration linked into Day 1", n_linked == 3, f"linked={n_linked}")
flat_link = os.path.join(caldir, "flats", cal_name("Flat", "20.0ms", "20260720-090000", filt="LUltimate"))
check("A2 links are hardlinks", os.path.isfile(flat_link) and os.stat(flat_link).st_nlink >= 2)
scopes = os.listdir(A.receipts) if os.path.isdir(A.receipts) else []
check("A2 receipt under scope dir", scopes == ["Askar 107PHQ"], str(scopes))
dash_path = os.path.join(A.mirror, "dashboard.html")
check("A2 dashboard generated + mirrored", os.path.isfile(dash_path))
dash = open(dash_path).read()
check("A2 dashboard data injected", "__DATA__" not in dash and "M 81" in dash)

# A3: idempotent
r = A.run(stdin="n\n")
check("A3 re-run imports nothing", "Nothing new" in r.stdout and count_fits(d1) == 2)

# A4: archive the whole target — THE original bug
shutil.move(os.path.join(A.dest, "M 81 - Bode's Galaxy"),
            os.path.join(A.root, "archived-M81"))
r = A.run(stdin="n\n")
check("A4 archived target does NOT re-import", "Nothing new" in r.stdout,
      r.stdout[-400:])
check("A4 no resurrected folder", not os.path.isdir(os.path.join(A.dest, "M 81 - Bode's Galaxy")))

# A5: new frames after archiving → Day 2, not Day 1
A.add_light("Plan", "M 81", "0006", dt="20260722-010000")
r = A.run(stdin="n\n")
d2 = day_dir(A, "M 81 - Bode's Galaxy", 2)
check("A5 day numbering continues after archive (Day 2)", count_fits(d2) == 1,
      f"day2={count_fits(d2)} out={r.stdout[-300:]}")

# A6: report categories
r = A.run("--report")
out = r.stdout
check("A6 report runs", r.returncode == 0, r.stderr[-300:])
m81_zone = out.split("NOT SAFE")[0] if "NOT SAFE" in out else out
check("A6 M 81 not in SAFE section",
      "M 81" not in out.split("BACKED UP")[0].split("SAFE TO CLEAR")[1] if "BACKED UP" in out else True)
check("A6 unverified category present", "BACKED UP, UNVERIFIED" in out)
check("A6 Autorun verdict present", "Autorun/ calibration:" in out)
check("A6 report saved + mirrored",
      os.path.isfile(os.path.join(A.mirror, "last-report.txt")))

# A7: reconcile upgrades entries whose dest copies exist (it also walks the
# Seestar trees: before 1.5.2 those were the REAL workbench; now the Env's own)
legacy = os.path.join(A.dest, "Sh2-129 - Flying Bat Nebula", "lights", "legacy Day 1")
os.makedirs(legacy, exist_ok=True)
for seq in ["0001", "0002", "0003"]:
    src = os.path.join(A.cam, "Live", "Light", "Sh2-129",
                       light_name("Sh2-129", dt=f"20260502-23{seq[-2:]}00", seq=seq))
    shutil.copy2(src, legacy)
r = A.run("--reconcile")
led = A.ledger()
sh_entries = [e for e in led["files"].values() if e["target"] == "Sh2-129"]
check("A7 reconcile upgrades Sh2-129", all(e["verifiedAtImport"] for e in sh_entries),
      r.stdout[-300:])
r = A.run("--report")
safe_zone = r.stdout.split("SAFE TO CLEAR")[1].split("BACKED UP")[0] if "BACKED UP" in r.stdout \
    else r.stdout.split("SAFE TO CLEAR")[1]
check("A7 Sh2-129 now SAFE", "Sh2-129" in safe_zone, r.stdout[:800])
dash = open(os.path.join(A.mirror, "dashboard.html")).read()
check("A7 dashboard carries report verdicts", '"status": "safe"' in dash
      or '"status":"safe"' in dash)

# A8: cleared-from-camera tracking
shutil.rmtree(os.path.join(A.cam, "Live", "Light", "Sh2-129"))
r = A.run("--report")
led = A.ledger()
sh_entries = [e for e in led["files"].values() if e["target"] == "Sh2-129"]
check("A8 cleared flags set", all(e.get("clearedFromCamera") for e in sh_entries))
check("A8 cleared section in report", "Recently cleared from camera" in r.stdout)

# ═══════════════ CHAIN B: crash recovery + adopt + continuation ═════════════
print("\n── Chain B: crash recovery / adopt / night continuation ──────")
B = Env("B")
f1 = B.add_light("Plan", "NGC 6888", "0001", dt="20260710-230000")
f2 = B.add_light("Plan", "NGC 6888", "0002", dt="20260710-231000")
# simulate a crashed previous run: file1 fully copied, file2 left as .partial; no ledger
crash_day = day_dir(B, "NGC 6888 - Crescent Nebula", 1)
os.makedirs(crash_day, exist_ok=True)
shutil.copy2(f1, os.path.join(crash_day, os.path.basename(f1)))
with open(os.path.join(crash_day, os.path.basename(f2) + ".partial"), "w") as fh:
    fh.write("TRUNCATED")
r = B.run(stdin="n\n")   # first run: declines baseline → empty ledger → all new
led = B.ledger()
e1 = [e for e in led["files"].values() if e["filename"] == os.path.basename(f1)]
e2 = [e for e in led["files"].values() if e["filename"] == os.path.basename(f2)]
check("B1 complete file adopted as merged", e1 and e1[0]["origin"] == "merged")
check("B1 partial re-imported properly", e2 and e2[0]["origin"] == "import" and e2[0]["sha256"])
check("B1 no .partial left", not any(x.endswith(".partial") for x in os.listdir(crash_day)))
check("B1 single Day folder", count_fits(crash_day) == 2 and
      not os.path.isdir(day_dir(B, "NGC 6888 - Crescent Nebula", 2)))

# B2: same-night continuation
B.add_light("Plan", "NGC 6888", "0003", dt="20260711-003000")  # same observing night (after midnight)
r = B.run(stdin="n\n")
check("B2 same-night frames continue into Day 1", count_fits(crash_day) == 3 and
      not os.path.isdir(day_dir(B, "NGC 6888 - Crescent Nebula", 2)),
      r.stdout[-300:])
# B3: different night → Day 2
B.add_light("Plan", "NGC 6888", "0004", dt="20260715-221500")
r = B.run(stdin="n\n")
check("B3 new night creates Day 2",
      count_fits(day_dir(B, "NGC 6888 - Crescent Nebula", 2)) == 1)

# ═══════════════ CHAIN C: mosaic panels + filename collision ════════════════
print("\n── Chain C: mosaic + filename collision ──────────────────────")
C = Env("C")
n = light_name("Squid", seq="0001", dt="20260718-220000")   # IDENTICAL name both panels
for panel in ["Squid_1-2", "Squid_2-2"]:
    make_fits(os.path.join(C.cam, "Plan", "Light", panel, n),
              focallen=402, uniq=f"panel-{panel}")
C.add_cal("Dark", "300.0s", "20260718-100000", focallen=402)
r = C.run(stdin="n\n")
led = C.ledger()
check("C1 both panels imported despite same filename", len(
    [e for e in led["files"].values() if e["origin"] == "import"]) == 2, r.stdout[-400:])
p1 = day_dir(C, "Squid", 1, panel="Squid_1-2")
p2 = day_dir(C, "Squid", 1, panel="Squid_2-2")
check("C1 panel Day folders under parent", count_fits(p1) == 1 and count_fits(p2) == 1,
      f"{p1}={count_fits(p1)} {p2}={count_fits(p2)}")
parent_cal = os.path.join(C.dest, "Squid", "calibration", "darks")
check("C1 shared calibration at mosaic parent", count_fits(parent_cal) == 1)
r = C.run("--report")
check("C2 report resolves mosaic panel names", "Squid · 1-2" in r.stdout, r.stdout[:600])

# ═══════════════ CHAIN D: mixed exposure + probation gates ══════════════════
print("\n── Chain D: mixed exposure + probation ───────────────────────")
D = Env("D")
D.add_light("Plan", "M 42", "0001", dt="20260719-220000", exp="300.0s", rot="120.0deg")
D.add_light("Plan", "M 42", "0002", dt="20260719-221000", exp="30.0s", rot="120.0deg")
D.add_cal("Dark", "300.0s", "20260719-100000")
D.add_cal("Dark", "30.0s", "20260719-101000")
D.add_cal("Flat", "20.0ms", "20260719-102000", filt="LUltimate", rot="10.0deg")  # rotation mismatch
r = D.run(stdin="n\n")
check("D1 mixed-exposure groups detected", "(filter, exposure) groups" in r.stdout)
darks_dir = os.path.join(day_dir(D, "M 42 - Orion Nebula", 1), "calibration", "darks")
check("D1 darks for BOTH exposures linked", count_fits(darks_dir) == 2,
      f"got {count_fits(darks_dir)}")
check("D1 probation warning recorded (aggregated)", "probation:" in r.stdout
      and "rotation" in r.stdout and "-frame flat set" in r.stdout)
flats_dir = os.path.join(day_dir(D, "M 42 - Orion Nebula", 1), "calibration", "flats")
check("D1 questionable flats DECLINED headless (ask-gate)", count_fits(flats_dir) == 0
      and "Flats skipped" in r.stdout, r.stdout[-400:])

# ═══════════════ CHAIN E: skiplist, scan-only, --all guard, receipts ════════
print("\n── Chain E: skiplist / scan-only / --all guard / receipts ────")
E = Env("E")
E.add_light("Plan", "M 31", "0001", dt="20260720-220000", focallen=402)
E.add_light("Live", "M 97", "0001", dt="20260720-223000", focallen=749)
E.add_light("Live", "junk_test", "0001", dt="20260720-224500", focallen=749)
r = E.run("--skip-target", "junk_test")
check("E1 skip-target", r.returncode == 0 and "Never import" in r.stdout)
r = E.run("--scan-only")
def tag(out, key):
    for ln in out.splitlines():
        if ln.startswith(f"ASIAIR-SCAN|{key}|"):
            return ln.split("|", 2)[2]
    return None
check("E2 scan-only tagged lines present", all(tag(r.stdout, k) is not None
      for k in ["COUNT", "SUMMARY", "STORAGE"]), r.stdout)
check("E2 scan-only excludes skipped (2 targets)", tag(r.stdout, "COUNT") == "2",
      str(tag(r.stdout, "COUNT")))
check("E2 storage line (two-device format)",
      "ASIAir" in (tag(r.stdout, "STORAGE") or "") and "free" in (tag(r.stdout, "STORAGE") or ""),
      tag(r.stdout, "STORAGE") or "no tag")
# pollution immunity: extra stdout before the tags must not break parsing
check("E2 tags survive stray output", tag("junk line\n" + r.stdout, "COUNT") == "2")
r = E.run(stdin="n\n")   # decline baseline offer → empty ledger → import both
led = E.ledger()
check("E3 skipped target not imported",
      not any(e["target"] == "junk_test" for e in led["files"].values()))
scopes = sorted(os.listdir(E.receipts)) if os.path.isdir(E.receipts) else []
check("E3 one receipt PER SCOPE in one run", scopes == ["Askar 107PHQ", "Askar FRA400"],
      str(scopes))
r = E.run("--all", stdin="n\n")
check("E4 --all guard cancels without confirmation", "Cancelled" in r.stdout, r.stdout[-300:])
check("E4 no duplicate Day folders",
      not os.path.isdir(day_dir(E, "M 31 - Andromeda Galaxy", 2)))
r = E.run("--pick")
check("E5 --pick degrades gracefully headless",
      r.returncode == 0 and ("cancelled" in r.stdout.lower() or "Nothing new" in r.stdout))
r = E.run("--unbaseline", "M 31")
check("E6 unbaseline touches only baseline entries",
      "0 baseline-only entries" in r.stdout.replace("Removed 0", "Removed 0 baseline-only")
      or "Removed 0" in r.stdout)

# ═══════════════ CHAIN F: ledger size-mismatch = treat as new ════════════════
print("\n── Chain F: key-hit size mismatch ─────────────────────────────")
F = Env("F")
p = F.add_light("Plan", "IC 1396", "0001", dt="20260721-220000")
F.run("--baseline")
# same relpath, different content/size (simulates run-scoped names colliding)
with open(p, "a") as fh:
    fh.write(" " * 2880)
r = F.run(stdin="n\n")
led = F.ledger()
entries = [e for e in led["files"].values() if e["target"] == "IC 1396"]
check("F1 mismatch warned + treated as new", "treating as NEW" in r.stdout
      and any(e["origin"] == "import" for e in entries), r.stdout[-400:])

# ═══════════════ CHAIN P: parser + rotation pure checks ═════════════════════
print("\n── Chain P: parsers ──────────────────────────────────────────")
import importlib.util as _ilu
_spec = _ilu.spec_from_file_location("engmod", SCRIPT)
eng = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(eng)
p1 = eng.parse_light_filename("Light_M 31_180.0s_Bin1_585MC_gain200_20260710-233354_0deg_-9.8C_0001.fit")
check("P1 no-filter light filename parses", p1 is not None and p1["exposure_seconds"] == 180.0
      and p1["filter"] == "" and p1["rotation"] == 0.0, str(p1))
p2 = eng.parse_light_filename("Light_M 81_300.0s_Bin1_585MC_gain200_20260509-081535_359deg_-10.0C_LUltimate_0001.fit")
check("P1 filtered light filename still parses", p2 is not None and p2["filter"] == "LUltimate")
p3 = eng.parse_light_filename("Light_M 81_300.0s_Bin1_585MC_gain200_20260509-081535_359deg_-10.0C__0001.fit")
check("P1 empty-segment variant still parses", p3 is not None and p3["filter"] == "")
rot = eng.dominant_rotation([0.0, 230.0, 231.0])
check("P2 pre-solve 0deg dropped, circular mean used", rot is not None and 229.5 <= rot <= 231.5, str(rot))
check("P2 wraparound mean sane", 358.0 <= (eng.dominant_rotation([359.0, 1.0]) or -1) or
      (eng.dominant_rotation([359.0, 1.0]) or 999) <= 2.0, str(eng.dominant_rotation([359.0, 1.0])))
check("P2 legit all-zero rotation kept", eng.dominant_rotation([0.0, 0.0]) == 0.0)
_filtered_flat = {"frame_type": "Flat", "gain": "gain200", "exposure_seconds": 0.02,
                  "sensor_temp": -9.8, "filter": "LUltimate", "rotation": None,
                  "capture_datetime": None, "filename": "f.fit", "source_path": "/nope"}
_gi = {"gain": "gain200", "exposure_seconds": 300.0, "sensor_temp": -10.0, "filter": "",
       "rotation": None, "focal_length": None, "scope": "x",
       "earliest_dt": None, "latest_dt": None}
_m = eng.match_calibration_group(_gi, [_filtered_flat])
check("P3 named-filter flat rejected for no-filter lights", _m["flats"] == [])

# ═══════════════ CHAIN H: no-filter baseline + refresh-metadata ═════════════
print("\n── Chain H: no-filter targets + refresh ──────────────────────")
H = Env("H")
for seq, dt, rot in [("0001", "20260710-233354", "0deg"), ("0002", "20260710-235659", "231deg")]:
    nm = f"Light_M 31_180.0s_Bin1_585MC_gain200_{dt}_{rot}_-9.8C_{seq}.fit"
    make_fits(os.path.join(H.cam, "Plan", "Light", "M 31", nm), focallen=402, uniq="nf" + seq)
r = H.run("--baseline")
led = H.ledger()
es = list(led["files"].values())
check("H1 no-filter baseline carries exposure + night",
      all(e.get("exposureSeconds") == 180.0 and e.get("night") == "2026-07-10" for e in es),
      str(es[:1]))
# strip metadata to simulate pre-patch baseline, then refresh
for e in led["files"].values():
    for k in ["exposureSeconds", "night", "scope", "gain"]:
        e.pop(k, None)
with open(os.path.join(H.state, "ledger.json"), "w") as f:
    json.dump(led, f)
r = H.run("--refresh-metadata")
led = H.ledger()
es = list(led["files"].values())
check("H2 refresh back-fills exposure/night/gain",
      all(e.get("exposureSeconds") == 180.0 and e.get("night") == "2026-07-10"
          and e.get("gain") == 200 for e in es), r.stdout[-300:])
check("H2 refresh fills scope from camera FITS",
      all(e.get("scope") == "Askar FRA400" for e in es), str(es[:1]))

# ═══════════════ CHAIN G: display-name hygiene ══════════════════════════════
print("\n── Chain G: display-name hygiene ─────────────────────────────")
G = Env("G")
os.makedirs(G.state, exist_ok=True)
with open(os.path.join(G.state, "custom-names.json"), "w") as f:
    json.dump({"Fish on the platter nebula": "Fish on a Platter Nebula",
               "NGC 9999": "Globular Cluster NGC 9999"}, f)
G.add_light("Live", "Fish on the platter nebula", "0001", dt="20260722-220000")
G.add_light("Live", "NGC 9999", "0001", dt="20260722-221500")
G.add_light("Plan", "NGC 9999", "0002", dt="20260723-221500")
r = G.run("--baseline")
led = G.ledger()
disp = {e["target"]: e["displayName"] for e in led["files"].values()}
check("G1 stopword-equal custom name not doubled",
      disp.get("Fish on the platter nebula") == "Fish on a Platter Nebula", str(disp))
check("G1 containment collapses to custom",
      disp.get("NGC 9999") == "Globular Cluster NGC 9999", str(disp))
r = G.run("--report")
check("G2 no doubled name in report", "nebula - Fish" not in r.stdout)
check("G2 Live/Plan duplicates disambiguated",
      "(Live)" in r.stdout and "(Plan)" in r.stdout, r.stdout[:800])

# ═══════════════ CHAIN S: Seestar adapter (unified engine) ══════════════════
print("\n── Chain S1: Seestar detect + scan + baseline ────────────────")
S1 = teh.Env("S1", asiair=False, seestar=True)
S1.add_seestar_sub("M 27", "20260618-224402")
S1.add_seestar_sub("M 27", "20260618-224502")
S1.add_seestar_stack("M 27", 120, "20260618-231500")
# S30 Pro shoots Lunar too — folder present must NOT flip model detection
# (Lunar is not an S50-only mode), but since 1.3.0 its files DO back up
S1.add_seestar_nondso("Lunar_photo", "Moon_001.fit", creator="ZWO Seestar S30 Pro")

r = S1.run("--scan-only")
def tag_s(out, key):
    for line in out.splitlines():
        if line.startswith(f"ASIAIR-SCAN|{key}|"):
            return line.split("|", 2)[2]
    return None
check("S1 scan-only emits tags for a Seestar-only session (Lunar counts now)",
      tag_s(r.stdout, "COUNT") == "2" and "Seestar" in (tag_s(r.stdout, "STORAGE") or ""),
      r.stdout[:300])

r = S1.run("--baseline")
check("S1 baseline sees the S30 Pro", "Seestar (S30 Pro)" in r.stdout, r.stdout[:400])
led = S1.ledger()
sees = [e for e in led["files"].values() if e.get("device") == "seestar"]
# 1.3.0: backup-first means Lunar is scanned on EVERY model, S30 Pro included
check("S1 baseline records Seestar files (subs+stack+Lunar — all models)",
      len(sees) == 4 and all(e["origin"] == "baseline" for e in sees),
      f"got {len(sees)}")
check("S1 baseline entries carry camera + scope",
      all(e["camera"] == "ZWO Seestar S30 Pro" and e["scope"] == "Seestar S30 Pro"
          for e in sees), str(sees[:1]))
check("S1 audit flags missing local copy", "NO local copy found" in r.stdout)

print("\n── Chain S2: Seestar DSO import (keep-highest, ledger, receipt) ──")
S2 = teh.Env("S2", asiair=False, seestar=True)
S2.add_seestar_sub("M 27", "20260618-224402")
S2.add_seestar_sub("M 27", "20260618-225402")
S2.add_seestar_stack("M 27", 20, "20260618-223000")   # superseded
S2.add_seestar_stack("M 27", 50, "20260618-230000")   # highest — the keeper
r = S2.run()   # headless: baseline offer + cleanup both default to No
disp27 = "M 27 - Dumbbell Nebula"
d1 = os.path.join(S2.sdest30, disp27, "M 27_sub Day 1")
check("S2 Day 1 created with 2 subs", count_fits(d1) == 2, d1)
root_stacks = [f for f in os.listdir(os.path.join(S2.sdest30, disp27))
               if f.startswith("Stacked_")] if os.path.isdir(os.path.join(S2.sdest30, disp27)) else []
check("S2 only the highest stack copied", root_stacks == ["Stacked_50_M 27_10.0s_IRCUT_20260618-230000.fit"],
      str(root_stacks))
led = S2.ledger()
subs = [e for e in led["files"].values()
        if e.get("device") == "seestar" and e.get("sourceType") == "sub"]
check("S2 sub entries verified with sha + header metadata",
      len(subs) == 2 and all(e["verifiedAtImport"] and e["sha256"] and
                             e["exposureSeconds"] == 10.0 and e["night"] == "2026-06-18" and
                             e["dayNumber"] == 1 for e in subs), str(subs[:1]))
stk = [e for e in led["files"].values() if e.get("sourceType") == "stack"]
check("S2 stack entry ledgered", len(stk) == 1 and stk[0]["displayName"] == disp27)
check("S2 manifest written",
      os.path.isfile(os.path.join(S2.sdest30, disp27, ".imported_files")))
rdir = os.path.join(S2.receipts, "Seestar S30 Pro")
receipts = os.listdir(rdir) if os.path.isdir(rdir) else []
check("S2 receipt under Seestar scope dir",
      len(receipts) == 1 and receipts[0].startswith("seestar-"), str(receipts))
check("S2 cleanup offered but declined leaves source intact",
      "SAFE" in r.stdout and os.path.isdir(os.path.join(S2.myworks, "M 27_sub")),
      r.stdout[-500:])
check("S2 superseded stack did not block the offer",
      "M 27 - Dumbbell Nebula" in r.stdout.split("fully imported + verified")[-1],
      r.stdout[-500:])

r = S2.run()   # second run: ledger exists → no baseline prompt
led2 = S2.ledger()
check("S2 re-run imports nothing new",
      len(led2["files"]) == len(led["files"]) and
      not os.path.isdir(os.path.join(S2.sdest30, disp27, "M 27_sub Day 2")),
      r.stdout[-300:])

print("\n── Chain S3: Milky Way pairing ───────────────────────────────")
S3 = teh.Env("S3", asiair=False, seestar=True)
S3.add_seestar_sub("NGC 6960", "20260618-230000")
S3.add_seestar_stack("NGC 6960", 80, "20260618-231500")
S3.add_seestar_sub("MilkyWay", "20260618-225010")
S3.add_seestar_sub("MilkyWay", "20260618-225510")
S3.add_seestar_stack("MilkyWay", 60, "20260618-231000")
r = S3.run()
mw_disp = "Milky Way Core - NGC 6960"
mw_day = os.path.join(S3.sdest30, mw_disp, f"{mw_disp} Day 1")
check("S3 MW paired to the simultaneous DSO", os.path.isdir(mw_day), r.stdout[-600:])
mw_files = sorted(os.listdir(mw_day)) if os.path.isdir(mw_day) else []
check("S3 MW frames renamed with DSO + stamp",
      mw_files == ["MilkyWay_NGC 6960_20260618-225010.fit",
                   "MilkyWay_NGC 6960_20260618-225510.fit"], str(mw_files))
keeper = os.path.join(S3.sdest30, mw_disp, "MilkyWay_NGC 6960_20260618-231000.fit")
check("S3 stacked keeper copied beside the Day folder", os.path.isfile(keeper))
led = S3.ledger()
mw_entries = [e for e in led["files"].values() if e.get("sourceType") in ("mw", "mw-stack")]
check("S3 MW ledger entries (2 subs + keeper)",
      len(mw_entries) == 3 and all(e["displayName"] == mw_disp for e in mw_entries),
      str(len(mw_entries)))
veil_day = os.path.join(S3.sdest30, "NGC 6960 - Western Veil Nebula", "NGC 6960_sub Day 1")
check("S3 the DSO itself imported normally too", count_fits(veil_day) == 1)

print("\n── Chain S4: S50 fallback detection + non-DSO modes ──────────")
S4 = teh.Env("S4", asiair=False, seestar=True)
# no CREATOR header anywhere → detection falls back to S50-only mode folders
S4.add_seestar_sub("M 45", "20260201-201000", creator=None)
S4.add_seestar_nondso("Solar_photo", "Solar_20260201.fit", creator=None)
S4.add_seestar_nondso("Lunar_video", "Moon_20260201.mp4")
r = S4.run()
check("S4 fallback detects S50 from Solar_photo", "Seestar: S50" in r.stdout, r.stdout[:600])
check("S4 DSO lands in the S50 destination",
      count_fits(os.path.join(S4.sdest50, "M 45 - Pleiades", "M 45_sub Day 1")) == 1)
check("S4 Solar photo imported", count_fits(os.path.join(S4.sdest50, "Solar")) == 1)
check("S4 Lunar video imported",
      os.path.isfile(os.path.join(S4.sdest50, "Lunar Video", "Moon_20260201.mp4")))
led = S4.ledger()
check("S4 entries say S50",
      all(e["camera"] == "ZWO Seestar S50" for e in led["files"].values()
          if e.get("device") == "seestar"), "")

print("\n── Chain S5: SAFE cleanup accept + mixed-device scoping ──────")
S5 = teh.Env("S5", asiair=True, seestar=True)
S5.add_light("Plan", "M 81", "0001", dt="20260720-221000", focallen=749)
S5.add_seestar_sub("M 42", "20260119-210000")
S5.add_seestar_sub("M 42", "20260119-210500")
r = S5.run()   # headless: every prompt takes its default
check("S5 both devices in one run",
      "ASIAir:" in r.stdout and "Seestar:" in r.stdout, r.stdout[:600])
check("S5 headless cleanup defaults to No (source intact)",
      "SAFE" in r.stdout and os.path.isdir(os.path.join(S5.myworks, "M 42_sub")),
      r.stdout[-400:])
check("S5 ASIAir source never offered for cleanup",
      os.path.isdir(os.path.join(S5.cam, "Plan", "Light", "M 81")) and
      "ASIAir" not in r.stdout.split("fully imported + verified")[-1].split("Delete")[0])
led = S5.ledger()
a_entries = [e for e in led["files"].values() if e.get("device", "asiair") == "asiair"]
s_entries = [e for e in led["files"].values() if e.get("device") == "seestar"]
check("S5 ledger split by device", len(a_entries) == 1 and len(s_entries) == 2,
      f"a={len(a_entries)} s={len(s_entries)}")

# Accept path: drive the cleanup confirm through PROMPT_FN (app-mode contract)
S5B = teh.Env("S5B", asiair=False, seestar=True)
S5B.add_seestar_sub("M 42", "20260119-210000")
S5B.add_seestar_sub("M 42", "20260119-210500")
driver = r"""
import argparse, importlib.util, sys
spec = importlib.util.spec_from_file_location("eng", sys.argv[1])
eng = importlib.util.module_from_spec(spec)
spec.loader.exec_module(eng)
def prompt_fn(q):
    return "y" if "Delete these SAFE" in q["prompt"] else q.get("default", "n")
eng.PROMPT_FN = prompt_fn
state = eng.State()
if not state.has_ledger():
    state.new_ledger()
sscan = eng.scan_seestar(state)
args = argparse.Namespace(dry_run=False, no_checksum=False, loose_cal=False,
                          explain_cal=False, all=False, clean_source_previews=False,
                          targets=None, verbose=False)
state.mark_cleared(sscan["relpaths"], device="seestar")
eng.run_seestar_import(state, sscan, args)
"""
r = subprocess.run([sys.executable, "-c", driver, SCRIPT], env=S5B.env,
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
check("S5 accepted cleanup removed the SAFE source folder",
      "Cleared" in r.stdout and not os.path.isdir(os.path.join(S5B.myworks, "M 42_sub")),
      r.stdout[-400:] + r.stderr[-400:])
led_b = S5B.ledger()
check("S5 cleared-from-camera flags set at deletion time",
      all(e.get("clearedFromCamera") for e in led_b["files"].values()
          if e.get("device") == "seestar"), str(list(led_b["files"].values())[:1]))
hist = open(os.path.join(S5B.state, "history.jsonl")).read()
check("S5 history logs the clear", "seestar-cleared" in hist)

r = S5.run("--report")
check("S5 report shows the Seestar section", "SEESTAR" in r.stdout.upper(), r.stdout[:400])
check("S5 cleared flags never leak to ASIAir entries",
      not any(e.get("clearedFromCamera")
              for e in S5.ledger()["files"].values()
              if e.get("device", "asiair") == "asiair"))

print("\n── Chain S6: mosaic panels + panel dedup ─────────────────────")
S6 = teh.Env("S6", asiair=False, seestar=True)
S6.add_seestar_sub("NGC 7000_mosaic", "20260701-220000")
S6.add_seestar_panel("NGC 7000_mosaic", "20260701-221500")
S6.add_seestar_panel("NGC 7000_mosaic", "20260701-223000")
S6.add_seestar_stack("NGC 7000_mosaic", 40, "20260701-224500")
r = S6.run()
disp70 = "NGC 7000 - North America Nebula (mosaic)"
check("S6 mosaic display name applied",
      os.path.isdir(os.path.join(S6.sdest30, disp70)), str(os.listdir(S6.sdest30)
      if os.path.isdir(S6.sdest30) else []))
check("S6 subs in mosaic Day folder",
      count_fits(os.path.join(S6.sdest30, disp70, "NGC 7000_mosaic_sub Day 1")) == 1)
check("S6 panels land in panels/",
      count_fits(os.path.join(S6.sdest30, disp70, "panels")) == 2)
r = S6.run()
check("S6 panels not re-imported on re-run",
      count_fits(os.path.join(S6.sdest30, disp70, "panels")) == 2, r.stdout[-300:])


print("\n── Chain S7: Seestar reconcile (old-script history) ──────────")
# Simulates Brett's real rollout: frames already imported to disk by the OLD
# bash script (incl. a renamed MW frame), then --baseline, then --reconcile.
S7 = teh.Env("S7", asiair=False, seestar=True)
p1 = S7.add_seestar_sub("M 27", "20260618-224402")
p2 = S7.add_seestar_sub("M 27", "20260618-224502")
mw = S7.add_seestar_sub("MilkyWay", "20260618-225010")
S7.add_seestar_stack("MilkyWay", 60, "20260618-231000")
# old-script layout at dest: subs under Day folder, MW renamed with DSO+stamp
old_day = os.path.join(S7.sdest30, "M 27 - Dumbbell Nebula", "M 27_sub Day 1")
os.makedirs(old_day, exist_ok=True)
shutil.copy2(p1, old_day)
shutil.copy2(p2, old_day)
old_mw = os.path.join(S7.sdest30, "Milky Way Core - M 27",
                      "Milky Way Core - M 27 Day 1")
os.makedirs(old_mw, exist_ok=True)
shutil.copy2(mw, os.path.join(old_mw, "MilkyWay_M 27_20260618-225010.fit"))

r = S7.run("--baseline")
check("S7 baseline audit sees the old-script folder",
      "M 27 - Dumbbell Nebula: destination folder present" in r.stdout, r.stdout[-600:])
r = S7.run("--reconcile")
check("S7 reconcile runs", r.returncode == 0, r.stderr[-300:])
led = S7.ledger()
subs = [e for e in led["files"].values()
        if e.get("device") == "seestar" and e.get("target") == "M 27"]
check("S7 Seestar subs upgraded to verified + sha",
      len(subs) == 2 and all(e["verifiedAtImport"] and e["sha256"] for e in subs),
      str(subs[:1]))
mws = [e for e in led["files"].values()
       if e.get("device") == "seestar" and e.get("target") == "MilkyWay"
       and e["filename"] == "20260618-225010.fit"]
check("S7 renamed MW frame matched via stamp index",
      mws and mws[0]["verifiedAtImport"], str(mws[:1]))
stk = [e for e in led["files"].values()
       if e.get("device") == "seestar" and e["filename"].startswith("Stacked_")]
check("S7 never-imported stack stays honest (unverified)",
      stk and not stk[0]["verifiedAtImport"])

# Mixed-target rescue (the Lion scenario): unbaseline strips ONLY unverified
r = S7.run("--unbaseline", "M 27")
led = S7.ledger()
m27 = [e for e in led["files"].values() if e.get("target") == "M 27"]
check("S7 unbaseline keeps verified entries", len(m27) == 2 and "kept 2 verified" in r.stdout,
      r.stdout[-300:])
r = S7.run("--unbaseline", "MilkyWay")
led = S7.ledger()
mw_left = [e for e in led["files"].values() if e.get("target") == "MilkyWay"]
check("S7 unbaseline removes only the unverified straggler",
      len(mw_left) == 1 and mw_left[0]["filename"] == "20260618-225010.fit",
      str([e["filename"] for e in mw_left]))

print("\n── Chain S8: night continuation + --merge-days ───────────────")
S8 = teh.Env("S8", asiair=False, seestar=True)
S8.add_seestar_sub("M 8", "20260817-205403")
S8.add_seestar_sub("M 8", "20260817-205843")
S8.add_seestar_stack("M 8", 30, "20260817-205900")   # stack lives at ROOT
r = S8.run()   # first (interrupted-equivalent) import → Day 1
disp8 = "M 8 - Lagoon Nebula"
d1 = os.path.join(S8.sdest30, disp8, "M 8_sub Day 1")
check("S8 first partial import lands in Day 1", count_fits(d1) == 2, r.stdout[-300:])
S8.add_seestar_sub("M 8", "20260817-210202")   # the resume: same night,
S8.add_seestar_sub("M 8", "20260817-210234")   # more frames on camera
r = S8.run()
check("S8 resumed import CONTINUES into Day 1 (same observing night)",
      count_fits(d1) == 4
      and not os.path.isdir(os.path.join(S8.sdest30, disp8, "M 8_sub Day 2")),
      r.stdout[-300:])
S8.add_seestar_sub("M 8", "20260818-213000")   # genuinely new night
r = S8.run()
d2 = os.path.join(S8.sdest30, disp8, "M 8_sub Day 2")
check("S8 a new night still opens Day 2", count_fits(d2) == 1, r.stdout[-300:])
# fabricate the historic damage: strand one Day-1 file in a fake Day 3
d3 = os.path.join(S8.sdest30, disp8, "M 8_sub Day 3")
os.makedirs(d3)
led = S8.ledger()
entmv = next(e for e in led["files"].values()
             if e.get("dayNumber") == 1 and e["filename"].endswith("205843.fit"))
shutil.move(os.path.join(d1, entmv["filename"]), os.path.join(d3, entmv["filename"]))
entmv["dest"] = d3
entmv["dayNumber"] = 3
# live-bug reproduction: the root-dwelling STACK also carries a merged-day
# number — merge must leave it at the project root untouched
entstk = next(e for e in led["files"].values() if e.get("sourceType") == "stack")
entstk["dayNumber"] = 3
with open(os.path.join(S8.state, "ledger.json"), "w") as f:
    json.dump(led, f)
r = S8.run("--merge-days", "M 8", "1", "3")
check("S8 --merge-days moves the strays home and removes the empty Day",
      count_fits(d1) == 4 and not os.path.isdir(d3), r.stdout[-400:])
led = S8.ledger()
check("S8 merge rewrote ledger dest + dayNumber for subs",
      all(e.get("dayNumber") == 1 and e.get("dest") == d1
          for e in led["files"].values()
          if e.get("target") == "M 8" and e.get("sourceType") == "sub"
          and "20260817" in e["filename"]),
      r.stdout[-300:])
stk_after = next(e for e in led["files"].values() if e.get("sourceType") == "stack")
proot = os.path.join(S8.sdest30, disp8)
check("S8 merge left the ROOT stack untouched (live-bug regression)",
      stk_after["dest"].rstrip("/") == proot.rstrip("/")
      and os.path.isfile(os.path.join(proot, stk_after["filename"])),
      str(stk_after["dest"]))
check("S8 merge logged a history event", "days-merged" in
      open(os.path.join(S8.state, "history.jsonl")).read(), "no event")
# renumber: close a gap by renaming Day 2 → Day 5 and back
r = S8.run("--renumber-day", "M 8", "2", "5")
d5 = os.path.join(S8.sdest30, disp8, "M 8_sub Day 5")
led = S8.ledger()
check("S8 --renumber-day renames folder and rewrites ledger",
      os.path.isdir(d5) and not os.path.isdir(d2) and count_fits(d5) == 1
      and all(e.get("dayNumber") == 5 and e.get("dest") == d5
              for e in led["files"].values()
              if e.get("target") == "M 8" and "20260818" in e.get("filename", "")
              and e.get("sourceType") == "sub"),
      r.stdout[-300:])

print("\n── Chain S9: two Seestars, one sky (original S30) ────────────")
S9 = teh.Env("S9", asiair=False, seestar=True)
S9.add_seestar_sub("M 8", "20260817-210000")
S9.add_seestar_sub("M 8", "20260817-210500")
r = S9.run()   # the S30 Pro's night
disp9 = "M 8 - Lagoon Nebula"
pro_d1 = os.path.join(S9.sdest30, disp9, "M 8_sub Day 1")
check("S9 Pro import lands in the Pro tree Day 1", count_fits(pro_d1) == 2,
      r.stdout[-300:])
# swap cameras: the ORIGINAL S30 arrives carrying its own night of M 8
shutil.rmtree(os.path.join(S9.myworks, "M 8_sub"))
S9.add_seestar_sub("M 8", "20260818-220000", creator="ZWO Seestar S30")
S9.add_seestar_sub("M 8", "20260818-220500", creator="ZWO Seestar S30")
r = S9.run()
check("S9 original S30 detected with its own destination",
      "Seestar: S30 — destination" in r.stdout and S9.sdest30o in r.stdout,
      r.stdout[-400:])
orig_d1 = os.path.join(S9.sdest30o, disp9, "M 8_sub Day 1")
check("S9 original S30 gets its OWN tree and its OWN Day 1",
      count_fits(orig_d1) == 2 and count_fits(pro_d1) == 2, r.stdout[-300:])
led = S9.ledger()
pro_ents = [e for e in led["files"].values()
            if e.get("camera") == "ZWO Seestar S30 Pro" and e.get("origin") == "import"]
s30_ents = [e for e in led["files"].values()
            if e.get("camera") == "ZWO Seestar S30" and e.get("origin") == "import"]
check("S9 entries carry their own camera identity + independent Day numbers",
      len(pro_ents) == 2 and len(s30_ents) == 2
      and all(e["dayNumber"] == 1 for e in s30_ents), str(len(s30_ents)))
check("S9 the S30's import did NOT flag the Pro's files as cleared",
      not any(e.get("clearedFromCamera") for e in pro_ents),
      str([e.get("clearedFromCamera") for e in pro_ents]))

print("\n── Chain S10: Seestar S50 Pro — fourth camera, own identity ──")
S10 = teh.Env("S10", asiair=False, seestar=True)
# Phase A: a brand-new S50 Pro arrives — DSO subs + a Solar photo (four worlds)
S10.add_seestar_sub("M 8", "20260904-213000", creator="Seestar S50 Pro")
S10.add_seestar_sub("M 8", "20260904-213500", creator="Seestar S50 Pro")
S10.add_seestar_nondso("Solar_photo", "Sun_20260904-120000.fit",
                       creator="Seestar S50 Pro")
r = S10.run()
disp10 = "M 8 - Lagoon Nebula"
check("S10 S50 Pro detected with its OWN destination (not the S50's)",
      f"Seestar: S50 Pro — destination {S10.sdest50p}" in r.stdout,
      r.stdout[-400:])
p50_d1 = os.path.join(S10.sdest50p, disp10, "M 8_sub Day 1")
check("S10 subs land in the S50 Pro tree Day 1", count_fits(p50_d1) == 2,
      r.stdout[-300:])
check("S10 non-DSO modes are live for the S50 Pro (Solar photo imported)",
      count_fits(os.path.join(S10.sdest50p, "Solar")) == 1, r.stdout[-400:])
led = S10.ledger()
p50_ents = [e for e in led["files"].values()
            if e.get("camera") == "ZWO Seestar S50 Pro" and e.get("origin") == "import"]
check("S10 ledger entries carry the S50 Pro camera + scope identity",
      len(p50_ents) == 3 and all(e.get("scope") == "Seestar S50 Pro"
                                 for e in p50_ents), str(len(p50_ents)))
# Phase B: swap to a PLAIN S50 shooting the same target — must stay separate
shutil.rmtree(os.path.join(S10.myworks, "M 8_sub"))
shutil.rmtree(os.path.join(S10.myworks, "Solar_photo"))
S10.add_seestar_sub("M 8", "20260905-220000", creator="ZWO Seestar S50")
r = S10.run()
check("S10 plain S50 still detected as S50 with its own destination",
      f"Seestar: S50 — destination {S10.sdest50}" in r.stdout,
      r.stdout[-400:])
s50_d1 = os.path.join(S10.sdest50, disp10, "M 8_sub Day 1")
check("S10 S50 gets its OWN tree and OWN Day 1; Pro tree untouched",
      count_fits(s50_d1) == 1 and count_fits(p50_d1) == 2, r.stdout[-300:])
led = S10.ledger()
p50_ents = [e for e in led["files"].values()
            if e.get("camera") == "ZWO Seestar S50 Pro" and e.get("origin") == "import"]
check("S10 the S50's import did NOT flag the S50 Pro's files as cleared",
      not any(e.get("clearedFromCamera") for e in p50_ents),
      str([e.get("clearedFromCamera") for e in p50_ents]))
# Phase C: CREATOR spelling variant ("SeestarS50Pro", no spaces) must map to
# the SAME S50 Pro identity — and continue its day numbering, not restart it
shutil.rmtree(os.path.join(S10.myworks, "M 8_sub"))
S10.add_seestar_sub("M 8", "20260906-213000", creator="SeestarS50Pro")
r = S10.run()
p50_d2 = os.path.join(S10.sdest50p, disp10, "M 8_sub Day 2")
check("S10 creator-spelling variant maps to the same S50 Pro identity (Day 2)",
      "Seestar: S50 Pro — destination" in r.stdout and count_fits(p50_d2) == 1,
      r.stdout[-400:])

print("\n── Chain S11: SAFE means EVERY file (JPEGs, rogue files) ─────")
S11 = teh.Env("S11", asiair=False, seestar=True)
# Solar shots land as FIT + JPG pairs — both must back up, both must clear
S11.add_seestar_nondso("Solar_photo", "Sun_20260905-110000.fit",
                       creator="Seestar S50 Pro")
with open(os.path.join(S11.myworks, "Solar_photo", "Sun_20260905-110000.jpg"),
          "wb") as f:
    f.write(b"\xff\xd8\xff\xe0JPGDATA-sun" + b"x" * 500)
STDIN_Y = {"ASTRO_STDIN_PROMPTS": "1"}   # let piped answers reach prompts
# first prompt is the baseline offer (decline), second the cleanup card (YES)
r = S11.run(stdin="n\ny\n", extra_env=STDIN_Y)
check("S11 Solar FIT and JPG both imported (JPEGs are data too)",
      os.path.isfile(os.path.join(S11.sdest50p, "Solar", "Sun_20260905-110000.fit"))
      and os.path.isfile(os.path.join(S11.sdest50p, "Solar", "Sun_20260905-110000.jpg")),
      r.stdout[-500:])
led = S11.ledger()
check("S11 the JPG is ledgered + verified like any frame",
      any(e.get("filename") == "Sun_20260905-110000.jpg" and e.get("verifiedAtImport")
          for e in led["files"].values()))
check("S11 fully-proven Solar folder cleared on Yes (nothing left behind)",
      not os.path.isdir(os.path.join(S11.myworks, "Solar_photo")), r.stdout[-500:])
# A folder holding ANY file the tool did not prove backed up is NEVER offered
S11.add_seestar_sub("M 42", "20260905-210000", creator="Seestar S50 Pro")
rogue = os.path.join(S11.myworks, "M 42_sub", "focus-notes.txt")
with open(rogue, "w") as f:
    f.write("HFD 2.1 at 220am")
r = S11.run(stdin="y\n", extra_env=STDIN_Y)
check("S11 folder with an unproven file is NOT offered as SAFE (survives a Yes)",
      os.path.isdir(os.path.join(S11.myworks, "M 42_sub")) and os.path.isfile(rogue)
      and count_fits(os.path.join(S11.sdest50p, "M 42 - Orion Nebula",
                                  "M 42_sub Day 1")) == 1,
      r.stdout[-500:])
# Unknown MyWorks folders: on camera, unreadable by this tool — say so loudly
os.makedirs(os.path.join(S11.myworks, "WideField_live"), exist_ok=True)
teh.make_seestar_fits(os.path.join(S11.myworks, "WideField_live", "pano_001.fit"),
                      creator="Seestar S50 Pro", uniq="wf-pano-1")
r = S11.run("--scan-only")
check("S11 unrecognised MyWorks folders are loudly reported, never silent",
      "NOT handled" in r.stdout and "WideField_live/" in r.stdout,
      r.stdout[:400])
check("S11 scan-only emits an ATTENTION count for the watcher notification",
      "ASIAIR-SCAN|ATTENTION|1" in r.stdout, r.stdout[:400])
# Stack JPGs must be in the scan's relpath set — a --report right after an
# import must NOT flag them "cleared from camera" while they still sit there
S11.add_seestar_sub("M 45", "20260906-201000", creator="Seestar S50 Pro")
S11.add_seestar_stack("M 45", 25, "20260906-203000", creator="Seestar S50 Pro")
sjpg = os.path.join(S11.myworks, "M 45",
                    "Stacked_25_M 45_10.0s_IRCUT_20260906-203000.jpg")
with open(sjpg, "wb") as f:
    f.write(b"\xff\xd8\xff\xe0JPG-m45" + b"y" * 300)
r = S11.run()
r = S11.run("--report")
led = S11.ledger()
sj = [e for e in led["files"].values() if e.get("sourceType") == "stack-jpg"]
check("S11 stack JPG imported+ledgered and NOT falsely marked cleared by --report",
      len(sj) == 1 and sj[0].get("verifiedAtImport")
      and not sj[0].get("clearedFromCamera"),
      str(sj))

print("\n── Chain S12: cleanup cleared-flags are camera-scoped ────────")
S12 = teh.Env("S12", asiair=False, seestar=True)
S12.add_seestar_sub("M 45", "20260901-201000", creator="Seestar S50 Pro")
r = S12.run()                     # Pro imports M 45; card untouched (default No)
shutil.rmtree(os.path.join(S12.myworks, "M 45_sub"))
S12.add_seestar_sub("M 45", "20260902-201000", creator="ZWO Seestar S50")
r = S12.run(stdin="y\n", extra_env={"ASTRO_STDIN_PROMPTS": "1"})
# ^ the S50 imports the same-named target and the user clears ITS card
led = S12.ledger()
pro12 = [e for e in led["files"].values()
         if e.get("camera") == "ZWO Seestar S50 Pro" and e.get("origin") == "import"]
s5012 = [e for e in led["files"].values()
         if e.get("camera") == "ZWO Seestar S50" and e.get("origin") == "import"]
check("S12 clearing the S50's folder flags ONLY the S50's ledger entries",
      s5012 and all(e.get("clearedFromCamera") for e in s5012)
      and pro12 and not any(e.get("clearedFromCamera") for e in pro12),
      f"pro={[e.get('clearedFromCamera') for e in pro12]} "
      f"s50={[e.get('clearedFromCamera') for e in s5012]}")

print("\n── Chain S13: identity refusals (unknown / mixed creators) ───")
S13 = teh.Env("S13", asiair=False, seestar=True)
S13.add_seestar_sub("M 51", "20260903-221000", creator="Seestar X99")
r = S13.run()
check("S13 unknown Seestar identity REFUSES to import (no guessed tree)",
      r.returncode != 0 and "unrecognised Seestar identity"
      in (r.stdout + r.stderr)
      and "Traceback" not in r.stderr   # a designed refusal, not a crash
      and not os.path.isdir(os.path.join(S13.sdest30, "M 51 - Whirlpool Galaxy")),
      (r.stdout + r.stderr)[-400:])
shutil.rmtree(os.path.join(S13.myworks, "M 51_sub"))
S13.add_seestar_sub("M 51", "20260903-221000", creator="ZWO Seestar S30 Pro")
S13.add_seestar_sub("M 52", "20260903-222000", creator="ZWO Seestar S50")
r = S13.run()
check("S13 two identities on one volume refuse the import (mixed leftovers)",
      r.returncode != 0 and "two different Seestar identities"
      in (r.stdout + r.stderr), (r.stdout + r.stderr)[-400:])

print("\n── Chain S14: Milky Way nights continue + survive archiving ──")
S14 = teh.Env("S14", asiair=False, seestar=True)
S14.add_seestar_sub("M 8", "20260910-220000")
S14.add_seestar_stack("M 8", 40, "20260910-221500")
S14.add_seestar_sub("MilkyWay", "20260910-221000")
r = S14.run()
mwd = "Milky Way Core - M 8"
mw_day1 = os.path.join(S14.sdest30, mwd, f"{mwd} Day 1")
check("S14 MW night lands in Day 1", count_fits(mw_day1) == 1, r.stdout[-400:])
# resumed import, SAME night (the yanked-cable case) → same Day folder
S14.add_seestar_sub("MilkyWay", "20260910-234500")
r = S14.run()
check("S14 same-night MW resume continues into Day 1 (no fragmentation)",
      count_fits(mw_day1) == 2
      and not os.path.isdir(os.path.join(S14.sdest30, mwd, f"{mwd} Day 2")),
      r.stdout[-400:])
# archive the MW folder off disk; a NEW night must become Day 2, not Day 1
shutil.move(os.path.join(S14.sdest30, mwd),
            os.path.join(S14.sdest30, mwd + " ARCHIVED"))
S14.add_seestar_stack("M 8", 60, "20260911-222000")   # night-2 pairing anchor
S14.add_seestar_sub("MilkyWay", "20260911-221000")
r = S14.run()
led = S14.ledger()
mw_new = [e for e in led["files"].values()
          if e.get("sourceType") == "mw" and "20260911" in e.get("filename", "")]
check("S14 archived MW history still counts — new night is Day 2",
      mw_new and all(e.get("dayNumber") == 2 for e in mw_new)
      and os.path.isdir(os.path.join(S14.sdest30, mwd, f"{mwd} Day 2")),
      str([e.get("dayNumber") for e in mw_new]) + r.stdout[-300:])
# THE pass-2 BLOCKER repro: an MW folder holds one keeper PER SESSION. A
# lower-N keeper whose own session never bucketed (no subs) stays unledgered
# — the old "superseded stack" exemption would have let a Yes DELETE it.
S14.add_seestar_stack("MilkyWay", 10, "20260912-200000")   # orphan session
S14.add_seestar_sub("MilkyWay", "20260912-221000")
S14.add_seestar_stack("MilkyWay", 200, "20260912-223000")  # this session's keeper
S14.add_seestar_stack("M 8", 80, "20260912-221500")        # pairing anchor
r = S14.run(stdin="y\n", extra_env={"ASTRO_STDIN_PROMPTS": "1"})
check("S14 MW folder with an unledgered session keeper is NOT SAFE, survives a Yes",
      os.path.isdir(os.path.join(S14.myworks, "MilkyWay"))
      and os.path.isfile(os.path.join(
          S14.myworks, "MilkyWay",
          "Stacked_10_MilkyWay_10.0s_IRCUT_20260912-200000.fit"))
      and "NOT SAFE" in r.stdout and "Stacked_10" in r.stdout,
      r.stdout[-600:])

print("\n── Chain S15: stack-only projects (sub saving OFF, the default) ──")
S15 = teh.Env("S15", asiair=False, seestar=True)
S15.add_seestar_stack("M 101", 30, "20260913-221000")
with open(os.path.join(S15.myworks, "M 101",
                       "Stacked_30_M 101_10.0s_IRCUT_20260913-221000.jpg"),
          "wb") as f:
    f.write(b"\xff\xd8\xff\xe0JPG-m101" + b"z" * 200)
# an unrelated _sub target with no project dir must NOT adopt "M 101"
# via prefix matching (M 1 is a prefix of M 101 — the pass-2 matcher fix)
S15.add_seestar_sub("M 1", "20260913-220000")
r = S15.run(stdin="n\ny\n", extra_env={"ASTRO_STDIN_PROMPTS": "1"})
d101 = os.path.join(S15.sdest30, "M 101 - Pinwheel Galaxy")
check("S15 stack-only project imports (stack + JPG, no Day folder)",
      count_fits(d101) == 1
      and os.path.isfile(os.path.join(
          d101, "Stacked_30_M 101_10.0s_IRCUT_20260913-221000.jpg"))
      and not any("Day" in x for x in os.listdir(d101)),
      r.stdout[-500:])
check("S15 stack-only folder cleared on Yes (fully proven, ledgered)",
      not os.path.isdir(os.path.join(S15.myworks, "M 101")), r.stdout[-400:])
led = S15.ledger()
m1 = [e for e in led["files"].values()
      if e.get("target") == "M 1" and e.get("origin") == "import"]
check("S15 'M 1' did NOT adopt 'M 101' as its project dir (exact match only)",
      len(m1) == 1 and m1[0].get("sourceType") == "sub"
      and count_fits(os.path.join(S15.sdest30, "M 1 - Crab Nebula",
                                  "M 1_sub Day 1")) == 1,
      str(m1))

print("\n── Chain S16: per-sub JPEG riders, OPT-IN since 1.4.2 ─────────")
S16 = teh.Env("S16", asiair=False, seestar=True)
S16.env["SEESTAR_IMPORT_SUB_JPEGS"] = "1"   # riders are off by default since 1.4.2

def s16_add(stamp, jpg=True, target="M 33"):
    """S50 Pro naming form: Light_<t>_30.0s_IRCUT_<stamp>.fit (+ .jpg twin)."""
    base = f"Light_{target}_30.0s_IRCUT_{stamp}"
    fp = os.path.join(S16.myworks, f"{target}_sub", base + ".fit")
    teh.make_seestar_fits(fp, creator="Seestar S50 Pro", exptime=30.0,
                          dateobs=teh.stamp_to_dateobs(stamp),
                          uniq=f"s16-{stamp}")
    if jpg:
        with open(os.path.join(S16.myworks, f"{target}_sub", base + ".jpg"),
                  "wb") as f:
            f.write(b"\xff\xd8\xff\xe0" + stamp.encode() + b"j" * 400)

# Phase A — fresh import: FITs and their JPEG twins land together
s16_add("20260905-013205")
s16_add("20260905-013238")
r = S16.run(stdin="n\ny\n", extra_env={"ASTRO_STDIN_PROMPTS": "1"})
d16 = os.path.join(S16.sdest50p, "M 33 - Triangulum Galaxy", "M 33_sub Day 1")
check("S16 JPEG twins land in the Day folder beside their FITs",
      count_fits(d16) == 2
      and os.path.isfile(os.path.join(
          d16, "Light_M 33_30.0s_IRCUT_20260905-013205.jpg"))
      and os.path.isfile(os.path.join(
          d16, "Light_M 33_30.0s_IRCUT_20260905-013238.jpg")),
      r.stdout[-500:])
led = S16.ledger()
sjp = [e for e in led["files"].values() if e.get("sourceType") == "sub-jpg"]
check("S16 sub-jpg entries verified, camera-tagged, day-numbered",
      len(sjp) == 2 and all(e.get("verifiedAtImport") and e.get("dayNumber") == 1
                            and e.get("camera") == "ZWO Seestar S50 Pro"
                            for e in sjp), str(sjp[:1]))
check("S16 fully-proven folder (FITs + JPEGs) cleared on Yes",
      not os.path.isdir(os.path.join(S16.myworks, "M 33_sub")), r.stdout[-400:])

# Phase B — CATCH-UP (Brett's live 2026-09-05 state): FITs imported on an
# older build, JPEG twins still on camera. They must join the FITs' OWN Day
# folder via the ledger sibling lookup — never a fresh Day number.
s16_add("20260906-013205", jpg=False)
r = S16.run()                              # night 2 FITs alone → Day 2
s16_add("20260906-013205", jpg=True)       # ...now the twin appears
r = S16.run(stdin="y\n", extra_env={"ASTRO_STDIN_PROMPTS": "1"})
d16b = os.path.join(S16.sdest50p, "M 33 - Triangulum Galaxy", "M 33_sub Day 2")
led = S16.ledger()
catchup = [e for e in led["files"].values()
           if e.get("sourceType") == "sub-jpg" and "20260906" in e.get("filename", "")]
check("S16 catch-up JPEG joins its sibling FIT's Day 2 (not a new day)",
      os.path.isfile(os.path.join(
          d16b, "Light_M 33_30.0s_IRCUT_20260906-013205.jpg"))
      and len(catchup) == 1 and catchup[0].get("dayNumber") == 2,
      r.stdout[-500:])
check("S16 catch-up run re-arms the cleanup offer and Yes clears the folder",
      not os.path.isdir(os.path.join(S16.myworks, "M 33_sub")), r.stdout[-400:])

print("\n── Chain S17: camera re-saves its stack → re-copy, re-verify ──")
S17 = teh.Env("S17", asiair=False, seestar=True)
S17.add_seestar_sub("M 27", "20260907-213000", creator="Seestar S50 Pro")
spath = S17.add_seestar_stack("M 27", 120, "20260907-215500",
                              creator="Seestar S50 Pro")
r = S17.run()                       # first import: sub + stack, default No
disp17 = "M 27 - Dumbbell Nebula"
sdst = os.path.join(S17.sdest50p, disp17, os.path.basename(spath))
size0 = os.path.getsize(sdst)
# The S50 Pro re-saves the stack after a session (annotation pass) — the
# camera copy changes while our dest copy holds the OLD bytes
with open(spath, "ab") as f:
    f.write(b"ANNOTATED-LAYER" * 64)
newsize = os.path.getsize(spath)
r = S17.run(stdin="y\n", extra_env={"ASTRO_STDIN_PROMPTS": "1"})
led = S17.ledger()
sent = [e for e in led["files"].values() if e.get("sourceType") == "stack"
        and e.get("target") == "M 27"]
check("S17 changed stack re-copied atomically and re-verified",
      os.path.getsize(sdst) == newsize and newsize > size0, r.stdout[-400:])
check("S17 ledger updated to the camera's new stack bytes",
      len(sent) == 1 and sent[0].get("size") == os.path.getsize(sdst)
      and sent[0].get("verifiedAtImport"), str(sent))
check("S17 with the refreshed stack proven, Yes clears the folder",
      not os.path.isdir(os.path.join(S17.myworks, "M 27_sub"))
      and not os.path.isdir(os.path.join(S17.myworks, "M 27")),
      r.stdout[-400:])

print("\n── Chain S18: one stack per night, archive never pruned (1.3.1) ──")
S18 = teh.Env("S18", asiair=False, seestar=True)
# Night 1: two stacks on the camera (20 then 50). Night 2: one stack (90).
S18.add_seestar_sub("M 27", "20260901-224402")
S18.add_seestar_stack("M 27", 20, "20260901-223000")   # night 1, superseded
S18.add_seestar_stack("M 27", 50, "20260901-230000")   # night 1 keeper
S18.add_seestar_sub("M 27", "20260902-224402")
S18.add_seestar_stack("M 27", 90, "20260902-231500")   # night 2 keeper
r = S18.run()
disp = "M 27 - Dumbbell Nebula"
tdir = os.path.join(S18.sdest30, disp)
def stacks_on_disk():
    return sorted(f for f in os.listdir(tdir) if f.startswith("Stacked_") and f.endswith(".fit"))
check("S18 one keeper per night: both nights' stacks archived, night-1 loser not",
      stacks_on_disk() == ["Stacked_50_M 27_10.0s_IRCUT_20260901-230000.fit",
                           "Stacked_90_M 27_10.0s_IRCUT_20260902-231500.fit"],
      str(stacks_on_disk()) + r.stdout[-300:])
led = S18.ledger()
stk = {e["filename"]: e for e in led["files"].values() if e.get("sourceType") == "stack"}
check("S18 stack entries carry night and subCount",
      stk.get("Stacked_50_M 27_10.0s_IRCUT_20260901-230000.fit", {}).get("night") == "2026-09-01"
      and stk["Stacked_50_M 27_10.0s_IRCUT_20260901-230000.fit"].get("subCount") == 50
      and stk.get("Stacked_90_M 27_10.0s_IRCUT_20260902-231500.fit", {}).get("subCount") == 90,
      str(stk))
check("S18 night-1 superseded stack on camera does not block SAFE (winner verified)",
      "NOT SAFE" not in r.stdout and disp in r.stdout.split("fully imported + verified")[-1],
      r.stdout[-500:])
# THE regression: camera cleared, fresh project starts at a LOW N on a new night.
# The archived higher-N stacks must survive the next import untouched.
shutil.rmtree(os.path.join(S18.myworks, "M 27_sub"))
shutil.rmtree(os.path.join(S18.myworks, "M 27"))
S18.add_seestar_sub("M 27", "20260910-224402")
S18.add_seestar_stack("M 27", 7, "20260910-230000")    # night 3, low N
r = S18.run()
check("S18 archived stacks survive an import whose camera stack has a lower N",
      stacks_on_disk() == ["Stacked_50_M 27_10.0s_IRCUT_20260901-230000.fit",
                           "Stacked_7_M 27_10.0s_IRCUT_20260910-230000.fit",
                           "Stacked_90_M 27_10.0s_IRCUT_20260902-231500.fit"],
      str(stacks_on_disk()) + r.stdout[-300:])
check("S18 nothing is ever logged as removed", "Removed older stack" not in r.stdout,
      r.stdout[-300:])
# Same night, higher N arrives later (camera re-stacked): the older keeper is
# reported as superseded and LEFT IN PLACE, then --tidy-stacks offers it.
S18.add_seestar_stack("M 27", 12, "20260910-234500")   # night 3, outranks 7
r = S18.run()
check("S18 same-night higher stack imported, older left in place and reported",
      "Stacked_7_M 27_10.0s_IRCUT_20260910-230000.fit" in stacks_on_disk()
      and "Stacked_12_M 27_10.0s_IRCUT_20260910-234500.fit" in stacks_on_disk()
      and "Superseded stack left in place" in r.stdout,
      str(stacks_on_disk()) + r.stdout[-400:])
r = S18.run("--tidy-stacks", "--dry-run")
check("S18 --tidy-stacks --dry-run lists only the same-night loser",
      "Stacked_7_" in r.stdout and "Stacked_50_" not in r.stdout
      and "Stacked_90_" not in r.stdout and "Nothing removed" in r.stdout
      and "Stacked_7_M 27_10.0s_IRCUT_20260910-230000.fit" in stacks_on_disk(),
      r.stdout[-500:])
r = S18.run("--tidy-stacks", stdin="no\n", extra_env={"ASTRO_STDIN_PROMPTS": "1"})
check("S18 --tidy-stacks without typed DELETE keeps everything",
      "Stacked_7_M 27_10.0s_IRCUT_20260910-230000.fit" in stacks_on_disk(), r.stdout[-300:])
r = S18.run("--tidy-stacks", stdin="DELETE\n", extra_env={"ASTRO_STDIN_PROMPTS": "1"})
led = S18.ledger()
tid = [e for e in led["files"].values() if e.get("filename", "").startswith("Stacked_7_")]
check("S18 typed DELETE removes the loser; ledger row kept and marked tidied",
      "Stacked_7_M 27_10.0s_IRCUT_20260910-230000.fit" not in stacks_on_disk()
      and len(stacks_on_disk()) == 3 and tid and tid[0].get("tidiedAt"),
      str(stacks_on_disk()) + str(tid))
rp = os.path.join(S18.receipts, "Seestar S30 Pro")
recs = [json.load(open(os.path.join(rp, f))) for f in sorted(os.listdir(rp))]
nights_seen = {x["night"] for rc in recs for ss in rc["sessions"] for x in ss.get("stacks", [])}
check("S18 receipts list per-night stacks",
      nights_seen == {"2026-09-01", "2026-09-02", "2026-09-10"}, str(nights_seen))

print("\n── Chain S19: per-sub JPEG previews are NOT imported (1.4.2) ──")
def s19_add(env, stamp, jpg=True, target="M 33"):
    base = f"Light_{target}_30.0s_IRCUT_{stamp}"
    fp = os.path.join(env.myworks, f"{target}_sub", base + ".fit")
    teh.make_seestar_fits(fp, creator="Seestar S50 Pro", exptime=30.0,
                          dateobs=teh.stamp_to_dateobs(stamp), uniq=f"{env.root}-{stamp}")
    if jpg:
        with open(os.path.join(env.myworks, f"{target}_sub", base + ".jpg"), "wb") as f:
            f.write(b"\xff\xd8\xff\xe0" + stamp.encode() + b"p" * 300)
    return base

S19 = teh.Env("S19", asiair=False, seestar=True)
Y19 = {"ASTRO_STDIN_PROMPTS": "1"}
s19_add(S19, "20260919-013205")
s19_add(S19, "20260919-013238")
stk = S19.add_seestar_stack("M 33", 2, "20260919-020000", creator="Seestar S50 Pro")
with open(stk[:-4] + ".jpg", "wb") as f:
    f.write(b"\xff\xd8\xff\xe0stackjpg" + b"s" * 200)
r = S19.run(stdin="n\ny\n", extra_env=Y19)
d19 = os.path.join(S19.sdest50p, "M 33 - Triangulum Galaxy", "M 33_sub Day 1")
check("S19 FITs import; their JPEG previews do not",
      count_fits(d19) == 2 and not [x for x in os.listdir(d19) if x.lower().endswith(".jpg")],
      str(os.listdir(d19)) + r.stdout[-300:])
led = S19.ledger()
check("S19 no sub-jpg ledger entries by default",
      not [e for e in led["files"].values() if e.get("sourceType") in ("sub-jpg", "mw-jpg")])
check("S19 the stack's own JPG still imports, verified",
      any(e.get("sourceType") == "stack-jpg" and e.get("verifiedAtImport")
          for e in led["files"].values()))
check("S19 cleanup still offered and clears: previews of proven FITs are not data",
      not os.path.isdir(os.path.join(S19.myworks, "M 33_sub")), r.stdout[-400:])
# a second night, cleanup declined: its previews must not show as new work
s19_add(S19, "20260920-013205")
r = S19.run()
r = S19.run("--scan-only")
check("S19 a target whose only leftovers are previews reports nothing new",
      "ASIAIR-SCAN|COUNT|0" in r.stdout, r.stdout[:300])
# a JPEG with NO FIT twin is the only copy of something: it still blocks
orphan = "Light_M 33_30.0s_IRCUT_20260920-030000.jpg"
with open(os.path.join(S19.myworks, "M 33_sub", orphan), "wb") as f:
    f.write(b"\xff\xd8\xff\xe0orphan" + b"o" * 200)
r = S19.run(stdin="y\n", extra_env=Y19)
check("S19 a JPEG with no FIT twin is never silent: reported NOT handled, left on camera",
      os.path.isfile(os.path.join(S19.myworks, "M 33_sub", orphan))
      and "NOT handled" in r.stdout and "JPEGs with no FIT" in r.stdout, r.stdout[-500:])
r = S19.run("--scan-only")
check("S19 the orphan raises the watcher's attention count",
      "ASIAIR-SCAN|ATTENTION|1" in r.stdout, r.stdout[:400])
r = S19.run("--report")
check("S19 the report will not call that folder SAFE",
      "M 33" in r.stdout and "NOT SAFE" in r.stdout and orphan in r.stdout, r.stdout[-700:])

# --ship: previews ledgered by an older build stay on the Mac
S19b = teh.Env("S19b", asiair=False, seestar=True)
s19_add(S19b, "20260921-013205")
r = S19b.run("--no-ship", extra_env={"SEESTAR_IMPORT_SUB_JPEGS": "1"})   # 1.4.1-style riders
legacy = [e for e in S19b.ledger()["files"].values() if e.get("sourceType") == "sub-jpg"]
os.makedirs(os.path.join(S19b.archive, "_verify"))
os.makedirs(os.path.join(S19b.archive, "S50P"))
r = S19b.run("--ship")
landed = [os.path.join(dp, f) for dp, _d, fs in os.walk(S19b.archive) for f in fs]
check("S19 --ship files the FIT but leaves legacy rider JPEGs on the Mac",
      len(legacy) == 1 and any(x.endswith(".fit") for x in landed)
      and not any(x.lower().endswith(".jpg") for x in landed),
      str([os.path.relpath(x, S19b.archive) for x in landed]) + r.stdout[-300:])
check("S19 --ship reports nothing outstanding afterwards",
      "Ship: 0 file(s)" in S19b.run("--ship", "--dry-run").stdout)

print("\n── Chain S20: discard — delete from camera WITHOUT importing (1.4.2) ──")
Y20 = {"ASTRO_STDIN_PROMPTS": "1"}
def s20_target(env, name, stamps, stack=None):
    for st in stamps:
        env.add_seestar_sub(name, st, creator="Seestar S50 Pro")
        with open(os.path.join(env.myworks, f"{name}_sub", f"{st}.jpg"), "wb") as f:
            f.write(b"\xff\xd8\xff\xe0" + st.encode() + b"d" * 100)
    if stack:
        env.add_seestar_stack(name, stack[0], stack[1], creator="Seestar S50 Pro")

def s20_seed_ledger(env):
    os.makedirs(env.state, exist_ok=True)
    with open(os.path.join(env.state, "ledger.json"), "w") as f:
        json.dump({"version": 1, "files": {}, "calibration": {}}, f)

S20 = teh.Env("S20", asiair=False, seestar=True)
S20n = teh.Env("S20n", asiair=False, seestar=True)
s20_target(S20n, "M 101", ["20260923-213000"])
r = S20n.run("--discard", "M 101", stdin="DISCARD\n", extra_env=Y20)
check("S20 with no ledger at all, discard refuses (nothing could remember it)",
      r.returncode == 1 and "No import ledger yet" in (r.stdout + r.stderr)
      and os.path.isfile(os.path.join(S20n.myworks, "M 101_sub", "20260923-213000.fit")), r.stdout[-300:])
s20_seed_ledger(S20)
s20_target(S20, "M 101", ["20260923-213000", "20260923-213100", "20260923-213200"],
           stack=(3, "20260923-214000"))
sub_dir = os.path.join(S20.myworks, "M 101_sub")
keep = os.path.join(S20.root, "keep.fit")
shutil.copy2(os.path.join(sub_dir, "20260923-213000.fit"), keep)
r = S20.run("--discard", "M 101", "--dry-run")
check("S20 dry run describes what the files ARE and deletes nothing",
      "3 subs" in r.stdout and "1 stack of up to 3 subs" in r.stdout
      and "NEVER been backed up" in r.stdout and "Nothing deleted" in r.stdout
      and len(os.listdir(sub_dir)) == 6 and r.returncode == 0, r.stdout[-600:])
r = S20.run("--discard", "M 101")                       # headless: nobody typed anything
check("S20 no typed DISCARD → cancelled, nothing deleted",
      "Cancelled" in r.stdout and len(os.listdir(sub_dir)) == 6, r.stdout[-300:])
r = S20.run("--discard", "M 101", stdin="yes\n", extra_env=Y20)
check("S20 anything but the exact word cancels (a 'yes' is not enough)",
      "Cancelled" in r.stdout and len(os.listdir(sub_dir)) == 6, r.stdout[-300:])
r = S20.run("--discard", "M 101", "--reason", "3 frames, clouds",
            stdin="DISCARD\nn\n", extra_env=Y20)
check("S20 typed DISCARD deletes the target's folders from the camera",
      not os.path.isdir(sub_dir) and not os.path.isdir(os.path.join(S20.myworks, "M 101"))
      and r.returncode == 0, r.stdout[-400:])
led = S20.ledger()
reg = led.get("discarded", {})
check("S20 every discarded file recorded first: hash, size, night, reason",
      len(reg) == 7 and all(v.get("sha256") and v.get("size") and v.get("reason") == "3 frames, clouds"
                            and v.get("origin") == "discarded" and not v.get("verifiedAtImport")
                            for v in reg.values()), str(list(reg.values())[:1]))
check("S20 discarded files never enter the backed-up register",
      not [e for e in led["files"].values() if e.get("target") == "M 101"])
check("S20 nothing was copied anywhere",
      not os.path.isdir(os.path.join(S20.sdest50p, "M 101 - Pinwheel Galaxy")))
r = S20.run("--report")
check("S20 the report shows discards in their own never-backed-up category",
      "Deliberately discarded" in r.stdout and "M 101" in r.stdout.split("Deliberately discarded")[1]
      and "3 frames, clouds" in r.stdout, r.stdout[-600:])
os.makedirs(sub_dir)
shutil.copy2(keep, os.path.join(sub_dir, "20260923-213000.fit"))   # the same bytes turn up again
r = S20.run("--scan-only")
check("S20 bytes that were discarded are recognised, not offered as new",
      "ASIAIR-SCAN|COUNT|0" in r.stdout, r.stdout[:300])

S20b = teh.Env("S20b", asiair=False, seestar=True)
s20_target(S20b, "M 102", ["20260923-220000", "20260923-220100"])
r = S20b.run()                                           # imported + verified
r = S20b.run("--discard", "M 102", stdin="n\n", extra_env=Y20)
check("S20 an all-backed-up target is handed to the SAFE clear (default No keeps it)",
      "SAFE clear, not a discard" in r.stdout and "Delete these SAFE source folders" in r.stdout
      and os.path.isfile(os.path.join(S20b.myworks, "M 102_sub", "20260923-220000.fit")),
      r.stdout[-400:])
r = S20b.run("--discard", "M 102", stdin="y\n", extra_env=Y20)
led = S20b.ledger()
m102 = [e for e in led["files"].values() if e.get("target") == "M 102"]
check("S20 ...and Yes clears it the SAFE way: flagged cleared, nothing 'discarded'",
      not os.path.isdir(os.path.join(S20b.myworks, "M 102_sub")) and m102
      and all(e.get("clearedFromCamera") for e in m102) and not led.get("discarded"),
      r.stdout[-400:])
S20f = teh.Env("S20f", asiair=False, seestar=True)
s20_target(S20f, "M 57", ["20260922-213000"])
r = S20f.run()                                           # night 22 imported + verified
s20_target(S20f, "M 57", ["20260923-213000"])            # night 23 never imported
r = S20f.run("--discard", "M 57", stdin="DISCARD\nn\n", extra_env=Y20)
left = sorted(os.listdir(os.path.join(S20f.myworks, "M 57_sub")))
check("S20 a mix offers ONLY the never-backed-up files; the backed-up night stays (1.4.3)",
      r.returncode == 0 and "is a mix" in r.stdout and "stay on the camera" in r.stdout
      and left == ["20260922-213000.fit", "20260922-213000.jpg"]
      and "Never import" not in r.stdout, str(left) + r.stdout[-400:])
s20_target(S20f, "M 57", ["20260923-213000"])            # night 23 re-shot
r = S20f.run("--discard", "M 57", "--night", "2026-09-23", stdin="DISCARD\n", extra_env=Y20)
left = sorted(os.listdir(os.path.join(S20f.myworks, "M 57_sub")))
check("S20 ...and --night on the never-imported night discards just that",
      left == ["20260922-213000.fit", "20260922-213000.jpg"], str(left) + r.stdout[-300:])

S20c = teh.Env("S20c", asiair=False, seestar=True)
s20_seed_ledger(S20c)
s20_target(S20c, "M 51", ["20260922-213000", "20260923-213000", "20260923-213100"])
r = S20c.run("--discard", "M 51", "--night", "2026-09-23", stdin="DISCARD\n", extra_env=Y20)
left = sorted(os.listdir(os.path.join(S20c.myworks, "M 51_sub")))
check("S20 --night discards only that night; the other night stays on the camera",
      left == ["20260922-213000.fit", "20260922-213000.jpg"], str(left) + r.stdout[-300:])

S20d = teh.Env("S20d", asiair=False, seestar=True)
s20_seed_ledger(S20d)
s20_target(S20d, "M 13", ["20260923-230000"])
with open(os.path.join(S20d.myworks, "M 13_sub", "20260923-230000_thn.jpg"), "wb") as f:
    f.write(b"thumb")                                   # camera thumbnail: neutral
r = S20d.run("--discard", "M 13", stdin="DISCARD\ny\n", extra_env=Y20)
check("S20 a camera thumbnail does not turn a clean discard into a 'mix'",
      not os.path.isdir(os.path.join(S20d.myworks, "M 13_sub")), r.stdout[-300:])
sk = json.load(open(os.path.join(S20d.state, "skiplist.json")))
check("S20 after a whole-target discard, Yes adds it to the never-import list",
      "M 13" in sk, str(sk) + r.stdout[-300:])

S20e = teh.Env("S20e", asiair=True, seestar=False)
S20e.add_light("Plan", "M 31", "0001")
r = S20e.run("--discard", "M 31", stdin="DISCARD\n", extra_env=Y20)
check("S20 the ASIAir is never deleted from — discard refuses outright",
      r.returncode == 1 and "Seestar-only" in (r.stdout + r.stderr)
      and any(f.endswith(".fit") for _dp, _d, fs in os.walk(S20e.cam) for f in fs), r.stdout[-300:])

# ── review fixes (1.4.2): exact target, containment, partial, one camera ──
S20g = teh.Env("S20g", asiair=False, seestar=True)
s20_seed_ledger(S20g)
s20_target(S20g, "M 81", ["20260923-213000"])
s20_target(S20g, "M 81 wide", ["20260923-223000"])     # same object, second project
r = S20g.run("--discard", "M 81", "--dry-run")
disp = r.stdout.split("DISCARD — ")[1].split(" (")[0] if "DISCARD — " in r.stdout else "?"
r = S20g.run("--discard", disp, stdin="DISCARD\n", extra_env=Y20)
check("S20 a name that matches two targets is refused and lists the camera folders",
      r.returncode == 1 and "matches more than one" in (r.stdout + r.stderr)
      and "M 81 wide_sub" in r.stdout
      and os.path.isdir(os.path.join(S20g.myworks, "M 81_sub"))
      and os.path.isdir(os.path.join(S20g.myworks, "M 81 wide_sub")), disp + r.stdout[-400:])
r = S20g.run("--discard", "M 81 wide_sub", stdin="DISCARD\nn\n", extra_env=Y20)
check("S20 ...and the camera folder name picks exactly one (the other stays)",
      not os.path.isdir(os.path.join(S20g.myworks, "M 81 wide_sub"))
      and os.path.isfile(os.path.join(S20g.myworks, "M 81_sub", "20260923-213000.fit")),
      r.stdout[-300:])

S20h = teh.Env("S20h", asiair=False, seestar=True)
s20_seed_ledger(S20h)
outside = os.path.join(S20h.root, "outside")
os.makedirs(outside)
S20h_keep = os.path.join(outside, "20260923-213000.fit")
teh.make_fits(S20h_keep, uniq="outside-precious")
CAN_LINK = True
try:
    os.symlink(outside, os.path.join(S20h.myworks, "M 3_sub"))  # a folder link off the card
except (OSError, NotImplementedError):
    CAN_LINK = False     # Windows without Developer Mode: links need admin
if CAN_LINK:
    r = S20h.run("--discard", "M 3", stdin="DISCARD\nn\n", extra_env=Y20)
    check("S20 a camera folder that links OFF the card is refused, nothing deleted",
          r.returncode == 1 and "Nothing was touched" in (r.stdout + r.stderr)
          and os.path.isfile(S20h_keep), (r.stdout + r.stderr)[-300:])
    os.remove(os.path.join(S20h.myworks, "M 3_sub"))
    s20_target(S20h, "M 3", ["20260923-213000"])
    os.symlink(S20h_keep, os.path.join(S20h.myworks, "M 3_sub", "20260923-213500.fit"))
    r = S20h.run("--discard", "M 3", stdin="DISCARD\nn\n", extra_env=Y20)
    check("S20 a file link inside a camera folder is refused, nothing deleted",
          r.returncode == 1 and os.path.isfile(S20h_keep)
          and os.path.isfile(os.path.join(S20h.myworks, "M 3_sub", "20260923-213000.fit")),
          (r.stdout + r.stderr)[-300:])
else:
    skip("S20 link containment (this OS needs admin rights to make links)")

# The two faults a subprocess can't stage on its own (a delete that fails, a
# second Seestar mounted) are injected through a tiny wrapper.
PATCHED = os.path.join(tempfile.mkdtemp(prefix="v2test-wrap-"), "patched.py")
with open(PATCHED, "w") as f:
    f.write(f'''import importlib.util, os, sys
spec = importlib.util.spec_from_file_location("astro_import", {SCRIPT!r})
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
if os.environ.get("FAIL_REMOVE"):
    _rm = os.remove
    def rm(p, *a, **k):
        if os.environ["FAIL_REMOVE"] in os.path.basename(p):
            raise PermissionError(1, "Operation not permitted", p)
        return _rm(p, *a, **k)
    os.remove = rm
if os.environ.get("EXTRA_SEESTAR"):
    m.seestar_extra_volumes = lambda primary: [os.environ["EXTRA_SEESTAR"]]
m.main()
''')
def run_patched(env, *args, stdin="", extra=None):
    e = dict(env.env); e.update(Y20); e.update(extra or {})
    return subprocess.run([sys.executable, PATCHED, *args], env=e, input=stdin,
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)

S20i = teh.Env("S20i", asiair=False, seestar=True)
s20_seed_ledger(S20i)
s20_target(S20i, "M 92", ["20260923-213000", "20260923-213100"])
r = run_patched(S20i, "--discard", "M 92", stdin="DISCARD\nn\n",
                extra={"FAIL_REMOVE": "213100.fit"})
reg = S20i.ledger().get("discarded", {})
stuck = [v for v in reg.values() if v["filename"] == "20260923-213100.fit"]
gone = [v for v in reg.values() if v["filename"] == "20260923-213000.fit"]
check("S20 ...it says how many could NOT be removed and are still on the Seestar",
      r.returncode == 1 and "could NOT be removed" in (r.stdout + r.stderr)
      and "Discarded 1 file(s)" not in r.stdout, (r.stdout + r.stderr)[-400:])
check("S20 ...the stuck file's record says stillOnCamera; the deleted one's doesn't",
      stuck and stuck[0].get("stillOnCamera") is True
      and gone and gone[0].get("stillOnCamera") is False, str(stuck) + str(gone))
r = S20i.run("--scan-only")
check("S20 ...and the frame still on the camera keeps showing as new work",
      "ASIAIR-SCAN|COUNT|1" in r.stdout, r.stdout[:300])
r = S20i.run("--report")
check("S20 ...and the report doesn't count it as discarded",
      "NOT deleted — still on the" in r.stdout
      and "M 92" in r.stdout.split("Deliberately discarded")[1], r.stdout[-500:])

S20j = teh.Env("S20j", asiair=False, seestar=True)
s20_seed_ledger(S20j)
s20_target(S20j, "M 15", ["20260923-213000"])
r = run_patched(S20j, "--discard", "M 15", stdin="DISCARD\nn\n",
                extra={"EXTRA_SEESTAR": os.path.join(S20j.root, "Seestar 1")})
check("S20 with two Seestars mounted, discard refuses (one camera at a time)",
      r.returncode == 1 and "one camera" in (r.stdout + r.stderr)
      and os.path.isfile(os.path.join(S20j.myworks, "M 15_sub", "20260923-213000.fit")),
      (r.stdout + r.stderr)[-300:])

S20k = teh.Env("S20k", asiair=False, seestar=True)
s20_seed_ledger(S20k)
for st, exp in (("20260923-213000", "10.0"), ("20260923-213100", "30.0")):
    p = S20k.add_seestar_sub("M 5", st, creator="Seestar S50 Pro")
    os.rename(p, os.path.join(os.path.dirname(p), f"Light_M 5_{exp}s_IRCUT_{st}.fit"))
r = S20k.run("--discard", "M 5", "--dry-run")
check("S20 integration adds up each sub's own exposure (10 s + 30 s = 0.7 min)",
      "2 subs (0.7 min integration)" in r.stdout, r.stdout[-400:])
S20k.add_seestar_sub("", "20260923-210000", creator="Seestar S50 Pro")   # MyWorks/_sub/
r = S20k.run("--discard", "_sub", stdin="DISCARD\nn\n", extra_env=Y20)
r2 = S20k.run("--scan-only")
check("S20 a folder literally named '_sub' is no target: not discardable, reported unhandled",
      r.returncode == 1 and os.path.isfile(os.path.join(S20k.myworks, "_sub", "20260923-210000.fit"))
      and os.path.isdir(os.path.join(S20k.myworks, "M 5_sub")) and "_sub/" in r2.stdout,
      (r.stdout + r.stderr)[-300:] + r2.stdout[:400])

print("\n── Chain S21: review fixes — what the preview exemption may NOT cover (1.4.2) ──")
# A Lunar_photo JPEG is data (the camera's processed image), not a preview:
# if its copy fails, the folder must stay NOT SAFE even though the FIT twin is proven.
S21 = teh.Env("S21", asiair=False, seestar=True)
s20_seed_ledger(S21)
S21.add_seestar_nondso("Lunar_photo", "Lunar_20260923-220000.fit", creator="Seestar S50 Pro")
with open(os.path.join(S21.myworks, "Lunar_photo", "Lunar_20260923-220000.jpg"), "wb") as f:
    f.write(b"\xff\xd8\xff\xe0moon-processed" + b"L" * 500)
os.makedirs(os.path.join(S21.sdest50p, "Lunar", "Lunar_20260923-220000.jpg.partial"))
r = S21.run("--no-ship", stdin="y\n", extra_env=Y20)
check("S21 a mode-folder JPEG whose copy FAILED keeps the folder NOT SAFE (twin or not)",
      "NOT SAFE" in r.stdout and os.path.isfile(
          os.path.join(S21.myworks, "Lunar_photo", "Lunar_20260923-220000.jpg")), r.stdout[-500:])
# The preview exemption matches its FIT twin whatever the extension's case.
S21b = teh.Env("S21b", asiair=False, seestar=True)
s20_seed_ledger(S21b)
p = S21b.add_seestar_sub("M 2", "20260923-213000", creator="Seestar S50 Pro")
os.rename(p, p[:-4] + ".FIT")
with open(os.path.join(S21b.myworks, "M 2_sub", "20260923-213000.jpg"), "wb") as f:
    f.write(b"\xff\xd8\xff\xe0prev" + b"p" * 100)
r = S21b.run("--no-ship", stdin="y\n", extra_env=Y20)
check("S21 a preview beside an upper-case .FIT twin still clears SAFE",
      not os.path.isdir(os.path.join(S21b.myworks, "M 2_sub")), r.stdout[-500:])

print("\n── Chain S22: 1.4.3 review fixes — the SAFE rule, the ledger, the camera ──")
Y22 = {"ASTRO_STDIN_PROMPTS": "1"}
def s22_env(tag):
    e = teh.Env(tag, asiair=False, seestar=True)
    s20_seed_ledger(e)
    return e
def s22_sub(env, target, stamp, creator, tag, exp="10.0"):
    p = os.path.join(env.myworks, f"{target}_sub", f"Light_{target}_{exp}s_IRCUT_{stamp}.fit")
    teh.make_seestar_fits(p, creator=creator, dateobs=teh.stamp_to_dateobs(stamp),
                          uniq=f"{tag}-{stamp}")
    return p

# H1 — two Seestars, same target, same second, same size: two frames, two rows
H1 = s22_env("S22a")
s22_sub(H1, "M 31", "20260923-213000", "ZWO Seestar S30", "S30")
H1.run("--no-ship", stdin="n\n", extra_env=Y22)
shutil.rmtree(H1.myworks); os.makedirs(H1.myworks)
b = s22_sub(H1, "M 31", "20260923-213000", "ZWO Seestar S50", "S50-other-photons")
r = H1.run("--scan-only")
check("S22 an S50 frame with the S30's name and size is NEW, not 'already imported' (H1)",
      "ASIAIR-SCAN|COUNT|1" in r.stdout, r.stdout[:300])
r = H1.run("--no-ship", stdin="y\n", extra_env=Y22)
s50copy = os.path.join(H1.sdest50, "M 31 - Andromeda Galaxy", "M 31_sub Day 1",
                       "Light_M 31_10.0s_IRCUT_20260923-213000.fit")
rows = [e for e in H1.ledger()["files"].values() if e["filename"].endswith("20260923-213000.fit")]
check("S22 ...it is copied and verified before the camera is cleared",
      os.path.isfile(s50copy) and not os.path.exists(b), r.stdout[-400:])
check("S22 ...and both cameras keep their own ledger row (none overwritten)",
      sorted(e["camera"] for e in rows) == ["ZWO Seestar S30", "ZWO Seestar S50"], str(rows))

# H6 — a second stacking session on the same night keeps its own stack
H6 = s22_env("S22b")
H6.add_seestar_stack("M 33", 100, "20260923-220000", creator="Seestar S50 Pro")
lp = os.path.join(H6.myworks, "M 33", "Stacked_150_M 33_10.0s_LP_20260923-233000.fit")
teh.make_seestar_fits(lp, creator="Seestar S50 Pro", uniq="lp-session")
r = H6.run("--no-ship", stdin="y\n", extra_env=Y22)
dest33 = os.path.join(H6.sdest50p, "M 33 - Triangulum Galaxy")
got = sorted(f for f in os.listdir(dest33) if f.startswith("Stacked_")) if os.path.isdir(dest33) else []
check("S22 a filter change mid-night: BOTH sessions' stacks are copied before any clear (H6)",
      any("_IRCUT_" in f and f.endswith(".fit") for f in got)
      and any("_LP_" in f and f.endswith(".fit") for f in got), str(got) + r.stdout[-300:])
H6b = s22_env("S22c")
H6b.add_seestar_stack("M 33", 180, "20260923-220000", creator="Seestar S50 Pro")
H6b.add_seestar_stack("M 33", 120, "20260924-010000", creator="Seestar S50 Pro")   # restarted, N reset
H6b.run("--no-ship", stdin="y\n", extra_env=Y22)
d = os.path.join(H6b.sdest50p, "M 33 - Triangulum Galaxy")
got = sorted(f for f in os.listdir(d) if f.startswith("Stacked_") and f.endswith(".fit")) if os.path.isdir(d) else []
check("S22 a restarted stack (lower N, later) is its own keeper, never 'outranked'",
      len(got) == 2, str(got))
r = H6b.run("--tidy-stacks", "--dry-run")
check("S22 ...and --tidy-stacks does not offer either one for removal",
      "No superseded" in r.stdout, r.stdout[-300:])

# H3 — the camera is swapped while the SAFE question waits: nothing is deleted
H3 = s22_env("S22d")
for st in ("20260923-213000", "20260923-213100"):
    H3.add_seestar_sub("M 51", st, creator="ZWO Seestar S30")
SWAP = os.path.join(tempfile.mkdtemp(prefix="v2test-wrap-"), "swap.py")
with open(SWAP, "w") as f:
    f.write(f"""import importlib.util, os, sys, shutil
sys.path.insert(0, {os.path.dirname(SCRIPT)!r})
import test_env_helper as teh
spec = importlib.util.spec_from_file_location("astro_import", {SCRIPT!r})
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
_real = m.safe_input
def swapping(prompt, default=""):
    if "SAFE source folders" in prompt:
        mw = os.path.join(os.environ["SEESTAR_VOLUME"], "MyWorks")
        shutil.rmtree(mw); os.makedirs(mw)
        for st in ("20260924-220000", "20260924-220100"):
            teh.make_seestar_fits(os.path.join(mw, "M 51_sub", st + ".fit"),
                                  creator="ZWO Seestar S50", uniq="S50-" + st)
        return "y"
    return _real(prompt, default)
m.safe_input = swapping
m.main()
""")
e = dict(H3.env); e.update(Y22)
r = subprocess.run([sys.executable, SWAP, "--no-ship"], env=e, input="n\n",
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
left = sorted(os.listdir(os.path.join(H3.myworks, "M 51_sub"))) \
    if os.path.isdir(os.path.join(H3.myworks, "M 51_sub")) else []
check("S22 a camera swapped while the SAFE card waited: the new camera's frames survive (H3)",
      left == ["20260924-220000.fit", "20260924-220100.fit"]
      and "no longer the" in (r.stdout + r.stderr), str(left) + (r.stdout + r.stderr)[-300:])

# H4 — the camera re-saves a stack in place at the same size: re-copied, never cleared stale
H4 = s22_env("S22e")
H4.add_seestar_sub("M 27", "20260923-213000", creator="Seestar S50 Pro")
stk = H4.add_seestar_stack("M 27", 1, "20260923-213500", creator="Seestar S50 Pro")
H4.run("--no-ship", stdin="n\n", extra_env=Y22)
data = bytearray(open(stk, "rb").read()); data[-50:] = b"R" * 50
open(stk, "wb").write(bytes(data))
later = os.path.getmtime(stk) + 1234   # not a whole quarter-hour (that reads as a DST/travel shift)
os.utime(stk, (later, later))                       # re-saved at the end of the session
r = H4.run("--scan-only")
check("S22 a stack re-saved at the same size shows as new work (H4)",
      "ASIAIR-SCAN|COUNT|1" in r.stdout, r.stdout[:300])
r = H4.run("--no-ship", stdin="y\n", extra_env=Y22)
mac = os.path.join(H4.sdest50p, "M 27 - Dumbbell Nebula", os.path.basename(stk))
check("S22 ...the import copies the NEW bytes before the SAFE clear",
      os.path.isfile(mac) and open(mac, "rb").read() == bytes(data), r.stdout[-300:])

# H2 — a ledger-writing command waits for the lock (it never saves over an import)
H2 = s22_env("S22f")
H2.add_seestar_stack("M 8", 10, "20260923-220000", creator="Seestar S50 Pro")
with open(os.path.join(H2.state, "import.lock"), "w") as f:
    json.dump({"pid": os.getpid(), "started": "now"}, f)
r = H2.run("--tidy-stacks", stdin="DELETE\n", extra_env=Y22)
r2 = H2.run("--skip-target", "M 8")
check("S22 --tidy-stacks and --skip-target refuse while an import holds the lock (H2)",
      r.returncode == 1 and r2.returncode == 1
      and "already running" in (r.stdout + r.stderr + r2.stdout + r2.stderr),
      (r.stdout + r.stderr)[-200:])
os.remove(os.path.join(H2.state, "import.lock"))

# H10 — a copy without a checksum is not "verified", so it can't clear the camera
H10 = s22_env("S22g")
H10.add_seestar_sub("M 57", "20260923-213000", creator="Seestar S50 Pro")
r = H10.run("--no-ship", "--no-checksum", stdin="y\n", extra_env=Y22)
row = [e for e in H10.ledger()["files"].values() if e["filename"].startswith("2026")][0]
check("S22 --no-checksum rows are not 'verified' and the SAFE clear is not offered (H10)",
      row.get("verifiedAtImport") is False and row.get("checksumSkipped")
      and os.path.isdir(os.path.join(H10.myworks, "M 57_sub")), str(row))

# H11 — different bytes at a binned path are new work, not "already discarded"
H11 = s22_env("S22h")
p11 = H11.add_seestar_sub("M 45", "20260923-213000", creator="Seestar S50 Pro")
H11.run("--discard", "M 45", stdin="DISCARD\nn\n", extra_env=Y22)
teh.make_seestar_fits(p11, creator="Seestar S50 Pro", uniq="a-different-frame")
r = H11.run("--scan-only")
check("S22 a new frame at a discarded path (same name and size) is offered, not hidden (H11)",
      "ASIAIR-SCAN|COUNT|1" in r.stdout, r.stdout[:300])

# H7 — a card with no FITS (identity guessed) never flags another camera's frames
H7 = s22_env("S22i")
for st in ("20260920-213000", "20260920-213100"):
    H7.add_seestar_sub("M 13", st, creator="ZWO Seestar S30 Pro")
H7.run("--no-ship", stdin="n\n", extra_env=Y22)
shutil.rmtree(H7.myworks); os.makedirs(H7.myworks)
H7.add_seestar_nondso("Lunar_video", "Lunar_20260923-230000.mp4", creator="ZWO Seestar S50 Pro")
H7.run("--no-ship", stdin="n\n", extra_env=Y22)
flagged = [e for e in H7.ledger()["files"].values()
           if e.get("target") == "M 13" and e.get("clearedFromCamera")]
check("S22 a FITS-less card never marks the S30 Pro's frames 'cleared from camera' (H7)",
      not flagged, str(len(flagged)))

# H8 — an unreadable ledger is never published over the mirror
H8 = s22_env("S22j")
H8.add_seestar_sub("M 2", "20260923-213000", creator="Seestar S50 Pro")
H8.run("--no-ship", stdin="n\n", extra_env=Y22)
mirror_ledger = os.path.join(H8.mirror, "ledger.json")
good = open(mirror_ledger).read()
for n in ("ledger.json", "ledger.json.bak"):
    with open(os.path.join(H8.state, n), "w") as f:
        f.write("{ not json")
H8.run("--skip-target", "M 99")
check("S22 a corrupt ledger (and .bak) never overwrites the good mirror copy (H8)",
      open(mirror_ledger).read() == good)

# H9 — the ASIAir-deleting flag is gone
r = teh.Env("S22k").run("--clean-source-previews", "--scan-only")
check("S22 --clean-source-previews no longer exists (it deleted from the ASIAir, H9)",
      r.returncode == 2 and "unrecognized" in r.stderr, r.stderr[-200:])

# V3 / V4 — names never become paths
check("S22 typed target names that are paths are refused (V3)",
      eng.clean_target_name("../../etc") is None and eng.clean_target_name("/Users/x") is None
      and eng.clean_target_name("Sh2-132: Lion") is None
      and eng.clean_target_name("  Lion   Nebula ") == "Lion Nebula")
V4 = s22_env("S22l")
V4.add_seestar_sub("M 20", "20260923-213000", creator="Seestar S50 Pro")
V4.add_seestar_sub("..", "20260923-213500", creator="Seestar S50 Pro")      # MyWorks/.._sub/
r = V4.run("--no-ship", stdin="y\n", extra_env=Y22)
check("S22 a folder named '.._sub' is not a target and the card root is never touched (V4)",
      os.path.isdir(V4.myworks) and os.path.isdir(os.path.join(V4.myworks, ".._sub"))
      and not os.path.isdir(os.path.join(V4.myworks, "M 20_sub"))
      and ".._sub/" in V4.run("--scan-only").stdout, r.stdout[-300:])

# discard reaches panel sets and mode folders by their camera folder name
DP = s22_env("S22m")
DP.add_seestar_panel("M 31_mosaic", "20260923-224000", creator="Seestar S50 Pro")
DP.add_seestar_nondso("Lunar_photo", "Lunar_20260923-220000.fit", creator="Seestar S50 Pro")
r = DP.run("--discard", "M 31_mosaic_pt", stdin="DISCARD\n", extra_env=Y22)
r2 = DP.run("--discard", "Lunar_photo", stdin="DISCARD\n", extra_env=Y22)
check("S22 discard reaches a mosaic's panels and a mode folder by camera folder name",
      not os.path.isdir(os.path.join(DP.myworks, "M 31_mosaic_pt"))
      and not os.path.isdir(os.path.join(DP.myworks, "Lunar_photo"))
      and "Never import" not in r.stdout + r2.stdout, (r.stdout + r2.stdout)[-400:])

print("\n── Chain W1: the Windows edition's platform layer, simulated (1.5.0) ──")
# Cameras as "drive letters": found by what is ON them, not by /Volumes names
W1 = teh.Env("W1", asiair=False, seestar=False)
drives = {n: os.path.join(W1.root, "drives", n) for n in ("F", "G", "H")}
for d in drives.values():
    os.makedirs(d)
teh.make_seestar_fits(os.path.join(drives["F"], "MyWorks", "M 42_sub", "20260924-210000.fit"),
                      creator="Seestar S50 Pro", uniq="w1-sub")
teh.make_fits(os.path.join(drives["G"], "Autorun", "Light", "M 81",
                           teh.light_name("M 81", seq="0001")), uniq="w1-light")
wenv = dict(W1.env)
# no fixed Seestar path: a missing one (removed, the Mac's /Volumes/Seestar
# default would return outside test mode). ASIAIR_VOLUME is unset: any value
# pins the ASIAir and switches off the drive-letter search tested here.
wenv["SEESTAR_VOLUME"] = os.path.join(W1.root, "no-seestar-volume")
wenv.pop("ASIAIR_VOLUME")
wenv["ASTRO_DRIVE_ROOTS"] = os.pathsep.join(drives[n] for n in ("F", "G", "H"))
def wrun(*args, stdin="", script=SCRIPT, extra=None):
    e = dict(wenv); e.update(extra or {})
    return subprocess.run([sys.executable, script, *args], env=e, input=stdin,
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=120)
r = wrun("--version")
check("W1 --version names the one shared version", f"FITS Importer {VERSION} (" in r.stdout,
      r.stdout + r.stderr)
r = wrun("--once", script=os.path.join(os.path.dirname(SCRIPT), "astro-watch.py"))
check("W1 the watcher finds the Seestar and the ASIAir by what is on each drive",
      f"ASIAir at {drives['G']}" in r.stdout and f"Seestar at {drives['F']}" in r.stdout,
      r.stdout + r.stderr[-300:])
r = wrun("--scan-only")
check("W1 the engine scans both cameras found on drive letters",
      "|STORAGE|ASIAir" in r.stdout and "· Seestar" in r.stdout
      and "No camera found" not in r.stdout + r.stderr, r.stdout[:400] + r.stderr[-300:])
r = wrun("--no-ship", "--targets", "M 42", stdin="n\n", extra={"ASTRO_STDIN_PROMPTS": "1"})
keys = list(W1.ledger()["files"].keys()) if os.path.isfile(os.path.join(W1.state, "ledger.json")) else []
check("W1 ledger keys are relative to the drive root and '/'-separated (same as a Mac ledger)",
      "MyWorks/M 42_sub/20260924-210000.fit" in keys, str(keys) + r.stdout[-300:])
# the lock's liveness check must never harm the process it looks at
spec_w = importlib.util.spec_from_file_location("engw", SCRIPT)
engw = importlib.util.module_from_spec(spec_w); spec_w.loader.exec_module(engw)
kid = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(5)"])
alive = engw.pid_alive(kid.pid); time.sleep(0.2)
check("W1 the lock's process check sees a live process and leaves it running",
      alive and kid.poll() is None)
kid.kill(); kid.wait()
check("W1 ...and sees a finished one as gone", not engw.pid_alive(kid.pid))
check("W1 drive-root prefixes get exactly one separator ('F:\\\\' stays 'F:\\\\')",
      engw._prefix("F:\\") == "F:\\" and engw._prefix("/a/b") == "/a/b" + os.sep)
# each machine publishes its own mirror; another machine's is left alone
W2state = os.path.join(W1.root, "second-machine-state")
r = wrun("--skip-target", "X", extra={"ASIAIR_STATE": W2state})
owner = json.load(open(os.path.join(W1.mirror, "mirror-owner.json")))
check("W1 a second machine pointed at the same mirror does NOT publish over it",
      "belongs to another computer" in r.stdout + r.stderr
      and owner["id"] == json.load(open(os.path.join(W1.state, "machine.json")))["id"],
      (r.stdout + r.stderr)[-300:])
r = wrun("--restore-ledger", stdin="n\n", extra={"ASIAIR_STATE": W2state, "ASTRO_STDIN_PROMPTS": "1"})
check("W1 ...and won't restore another machine's ledger as its own without being told",
      "Not restored" in r.stdout + r.stderr and not os.path.isfile(os.path.join(W2state, "ledger.json")),
      (r.stdout + r.stderr)[-300:])
# per-machine ship log on a local archive (the PC case: E:\Astro Image Data),
# in the PC's own _verify folder from 1.7.0 (decision D7)
arch = os.path.join(W1.root, "E-archive")
os.makedirs(os.path.join(arch, "S50P")); os.makedirs(os.path.join(arch, "_verify"))
PC_SHIP = {"ASTRO_ARCHIVE_MOUNT": arch, "ASTRO_SHIP_LOG": "shipped-pc.jsonl", "ASTRO_SHIP_FOLDER": "pc"}
r = wrun("--ship", extra=PC_SHIP)
vfiles = sorted(os.listdir(os.path.join(arch, "_verify")))
pcfiles = sorted(os.listdir(os.path.join(arch, "_verify", "pc"))) \
    if os.path.isdir(os.path.join(arch, "_verify", "pc")) else []
check("W1 the PC ships into a local archive and writes its OWN ship log",
      "shipped-pc.jsonl" in pcfiles and not any(f.startswith("shipped") for f in vfiles)
      and "mac" not in vfiles
      and any(f.endswith(".fit") for _dp, _d, fs in os.walk(os.path.join(arch, "S50P")) for f in fs),
      str(vfiles) + str(pcfiles) + r.stdout[-300:])
# the sweep's verified.jsonl stamps the PC's ledger too — a stray line or a
# size written as text never stops a ship (the 1.6 place, still read)
_rows = [x for x in (json.loads(l) for l in open(os.path.join(arch, "_verify", "pc", "shipped-pc.jsonl"),
                                                encoding="utf-8") if l.strip())
         if x.get("state") == "shipped"]
with open(os.path.join(arch, "_verify", "verified.jsonl"), "w", encoding="utf-8") as vf:
    vf.write("[1, 2]\nnot json\n")
    for i, x in enumerate(_rows):
        vf.write(json.dumps({"relpath": x["relpath"], "sha256": x.get("sha256"),
                             "size": str(x["size"]) if i == 0 else x["size"],
                             "verifiedAt": "2026-09-24T210000"}) + "\n")
r = wrun("--ship", extra=PC_SHIP)
_led = json.load(open(os.path.join(W1.state, "ledger.json"), encoding="utf-8"))["files"]
_shipped = [e for e in _led.values() if e.get("archiveLocation")]
check("W1 the sweep's verified.jsonl stamps the PC's ledger (stray lines and text sizes tolerated)",
      r.returncode == 0 and _rows and _shipped
      and all(e.get("archiveVerifiedAt") == "2026-09-24T210000" for e in _shipped),
      f"rc={r.returncode} rows={len(_rows)} shipped={len(_shipped)} " + (r.stdout + r.stderr)[-300:])

# carrying settings to the other computer (names, never-import, equipment)
json.dump({"IC 1396": "Elephant's Trunk", "Sh2-132": "Lion Nebula"},
          open(os.path.join(W1.state, "custom-names.json"), "w"))
json.dump(["NGC 7000"], open(os.path.join(W1.state, "skiplist.json"), "w"))
eqf = os.path.join(W1.root, "equipment.json")
json.dump({"telescopes": [{"name": "Askar FRA400", "focal": 400}]}, open(eqf, "w"))
bundle = os.path.join(W1.root, "settings.json")
r = wrun("--export-settings", bundle)
b = json.load(open(bundle))
check("W1 --export-settings carries names, never-import list and equipment — not the ledger",
      b["customNames"].get("IC 1396") == "Elephant's Trunk" and b["skiplist"] == ["NGC 7000"]
      and b["equipment"]["telescopes"][0]["focal"] == 400
      and "ledger" not in b and "files" not in b, json.dumps(b)[:300])
PC = teh.Env("W1pc", asiair=False, seestar=True)
os.makedirs(PC.state, exist_ok=True)
json.dump({"IC 1396": "IC 1396 (kept here)"}, open(os.path.join(PC.state, "custom-names.json"), "w"))
pc_eq = os.path.join(PC.root, "pc-equipment.json")
pc_bundle = os.path.join(PC.root, "settings.json")   # carried over to the PC
shutil.copy2(bundle, pc_bundle)
r = PC.run("--import-settings", pc_bundle, extra_env={"ASIAIR_EQUIPMENT": pc_eq})
names = json.load(open(os.path.join(PC.state, "custom-names.json")))
check("W1 --import-settings adds what is missing and never overwrites what the PC has",
      names.get("Sh2-132") == "Lion Nebula" and names.get("IC 1396") == "IC 1396 (kept here)"
      and json.load(open(os.path.join(PC.state, "skiplist.json"))) == ["NGC 7000"]
      and json.load(open(pc_eq))["telescopes"][0]["focal"] == 400
      and not os.path.isfile(os.path.join(PC.state, "ledger.json")), r.stdout[-400:])

# the install check looks for exactly what each installer installs (1.5.0:
# the Mac's selftest looked for astro-watch.py, which only Windows installs)
_here = os.path.dirname(SCRIPT)
_st_spec = importlib.util.spec_from_file_location("selftest_w1", os.path.join(_here, "selftest.py"))
_st = importlib.util.module_from_spec(_st_spec); _st_spec.loader.exec_module(_st)
_sh_text = open(os.path.join(_here, "install-scripts.sh"), encoding="utf-8").read()
_mac_inst = set(re.findall(r'install_file "\$SCRIPT_DIR/([^"]+)"', _sh_text))
# the contract files go through the marked `contract update` loop (1.7.0)
_m = re.search(r'for f in ([^;]+); do\s*\n\s*src="\$SCRIPT_DIR/contract/\$f"', _sh_text)
if _m:
    _mac_inst |= {"contract/" + f for f in _m.group(1).split()}
_ps = open(os.path.join(_here, "install-windows.ps1"), encoding="utf-8-sig").read()
_m = re.search(r"foreach \(\$f in @\(([^)]*'astro-import\.py'[^)]*)\)\)", _ps)
_win_inst = set(re.findall(r"'([^']+)'", _m.group(1))) if _m else set()
_m = re.search(r"foreach \(\$f in @\(([^)]*'targets\.json'[^)]*)\)\)", _ps)   # the contract (1.7)
if _m:
    _win_inst |= {"contract/" + f for f in re.findall(r"'([^']+)'", _m.group(1))}
check("W1 the Mac install check expects only files install-scripts.sh installs",
      set(_st.INSTALLED["mac"]) <= _mac_inst, f"{_st.INSTALLED['mac']} vs {sorted(_mac_inst)}")
check("W1 the Windows install check expects only files install-windows.ps1 installs",
      set(_st.INSTALLED["windows"]) <= _win_inst, f"{_st.INSTALLED['windows']} vs {sorted(_win_inst)}")
_pip_hints = [ln.strip() for ln in _ps.splitlines() if "Warn" in ln and "-m pip install" in ln]
check("W1 the Windows installer's astropy hint pastes into Terminal's PowerShell: & before the "
      "quoted python.exe (1.5.4)",
      bool(_pip_hints) and all('& `"$py`" -m pip install' in ln for ln in _pip_hints), str(_pip_hints))
# 1.7.0: the PC's jobs are Python, started by two tasks (read, never run here)
_s7 = _ps[_ps.index("# ── 7. The archive PC's own jobs"):_ps.index("# ── 8. Start")] \
    if "# ── 7. The archive PC's own jobs" in _ps else ""
check("W1 the Windows installer schedules the PC's jobs in Python, as Brett: 'Astro archive "
      "sweep' runs --pc-nightly at logon and 03:30, 'Astro sync requests' runs --pc-tick every "
      "5 minutes, neither twice at once; it makes _verify\\pc, _verify\\mac\\requests, "
      "_verify\\lock and _Quarantine\\ship-incomplete; sweep.ps1 is gone",
      "--pc-nightly" in _s7 and "--pc-tick" in _s7 and "'Astro archive sweep'" in _s7
      and "'Astro sync requests'" in _s7 and "-At 03:30" in _s7 and "-AtLogOn" in _s7
      and "New-TimeSpan -Minutes 5" in _s7 and _s7.count("-MultipleInstances IgnoreNew") == 2
      and "-RunLevel Limited" in _ps and "powershell.exe" not in _s7
      and all(d in _s7 for d in ("'_verify\\pc'", "'_verify\\mac\\requests'", "'_verify\\lock'",
                                 "'_Quarantine\\ship-incomplete'"))
      and not os.path.exists(os.path.join(_here, "pc", "sweep.ps1"))
      and not os.path.exists(os.path.join(_here, "pc", "install_sweep.ps1")), _s7[:300])
with open(os.path.join(_here, "pc", "set-archive-rights.ps1"), "rb") as _f:
    _rraw = _f.read()
_rights = _rraw.decode("utf-8-sig")
_body = _rights[_rights.index("param("):]
_gate = _body.index("if (-not $Apply)")
_changes = [m.start() for m in re.finditer(r"& icacls\.exe \$s\.Path", _body)]
_saves = [m.start() for m in re.finditer(r"/save", _body)]
check("W1 set-archive-rights.ps1 changes nothing without -Apply, saves today's rights before its "
      "first change, names the share's user by SID (no password anywhere), and refuses Brett's "
      "own account, a group or an administrator (UTF-8 with a BOM, CRLF)",
      _rraw.startswith(b"\xef\xbb\xbf") and b"\n" not in _rraw.replace(b"\r\n", b"")
      and _changes and _saves and all(c > _gate for c in _changes + _saves)
      and max(_saves) < min(_changes) and "Translate([System.Security.Principal.SecurityIdentifier])" in _body
      and '$u = "*$sid"' in _body and "password" not in _body.lower().replace("never a password", "")
      and "is the account you are signed in with" in _body and "not a local user account" in _body
      and "is an administrator on this PC" in _body and "/deny" in _body and "(DE,DC)" in _body,
      f"gate {_gate} saves {_saves} changes {_changes}")
_full_save = _body[_body.index("archive-all.acl"):_body.index("Today's rights saved")]
check("W1 ...on Windows PowerShell 5.1 its save of every file's rights can't stop it half-way (that "
      "one icacls call runs under Continue, its exit code decides); _verify\\mac and _verify\\lock get "
      "Modify inside but no Delete on the folder itself, never a /deny that would strip their grant; "
      "it says when the share itself gives Full Control",
      "$ErrorActionPreference = 'Continue'" in _full_save and "$LASTEXITCODE" in _full_save
      and "2>$null" not in _body and "(OI)(CI)(IO)(M)" in _body
      and not re.search(r"Path = \$(mac|lock);[^\n]*'/deny'", _body)
      and "Get-SmbShareAccess" in _body and "AccessRight Change" in _body
      and "TrimEnd('\\')" in _body, _full_save[:300])
_bin = os.path.join(W1.root, "installed-bin")
os.makedirs(_bin, exist_ok=True)
for _f in _st.INSTALLED.get(engw.PLATFORM, _st.INSTALLED["windows"]):   # what THIS OS installs
    _dst = os.path.join(_bin, _f)                 # contract/… keeps its folder
    os.makedirs(os.path.dirname(_dst), exist_ok=True)
    shutil.copy2(os.path.join(_here, _f), _dst)
# The Desktop as the installer names it: with OneDrive it is OneDrive\Desktop (the PC,
# 11 Oct 2026, warned about a button that was there). In test mode never the real one.
_home_desk = os.path.join(os.path.expanduser("~"), "Desktop")
_shell_desk = lambda: os.path.join("X:\\", "OneDrive", "Desktop")
check("W1 the self-test looks for the Restart button where Windows says the Desktop is (OneDrive "
      "may move it), and only under the test home in test mode",
      _st.desktop_dir(test_mode=True, shell=_shell_desk) == _home_desk
      and _st.desktop_dir(test_mode=False, shell=lambda: "") == _home_desk
      and (_st.desktop_dir(test_mode=False, shell=_shell_desk) == _shell_desk()
           if os.name == "nt" else _st.desktop_dir(test_mode=False, shell=_shell_desk) == _home_desk),
      _st.desktop_dir(test_mode=False, shell=_shell_desk))
r = wrun(script=os.path.join(_bin, "selftest.py"))
check("W1 the install check passes from an installed folder (not only the source folder)",
      " present" in r.stdout and not re.search(r"FAIL\s+\S+ present", r.stdout),
      ("\n".join(ln for ln in r.stdout.splitlines() if "FAIL" in ln) or r.stdout[-600:])
      + r.stderr[-300:])

print("\n── Chain P1: --ship files Seestar frames into the archive (1.4.0) ──")
# Ship as the Mac on every OS (1.7.0): on the PC the engine's own log is
# _verify\pc\shipped-pc.jsonl, and this chain reads the Mac's. D7 and PC do the same.
D7_MAC = {"ASTRO_SHIP_FOLDER": "mac", "ASTRO_SHIP_LOG": "shipped.jsonl"}
P1 = teh.Env("P1", asiair=False, seestar=True)
P1.env.update(D7_MAC)
# The archive already holds Dumbbell Nebula (M 27) with Day 1 (night 1 Sep) and Day 2 (night 2 Sep)
arch = P1.archive
tE = os.path.join(arch, "S30P", "Dumbbell Nebula (M 27)")
for n, stamp in ((1, "20260901-223000"), (2, "20260902-223000")):
    d = os.path.join(tE, f"M 27_sub Day {n}"); os.makedirs(d)
    open(os.path.join(d, f"Light_M 27_10.0s_IRCUT_{stamp}.fit"), "wb").write(b"old")
os.makedirs(os.path.join(arch, "_verify"))
# The Mac imports night 2 Sep (again, resumed) and a new night 10 Sep, plus a stack
P1.add_seestar_sub("M 27", "20260902-231000")
P1.add_seestar_sub("M 27", "20260910-224402")
P1.add_seestar_stack("M 27", 60, "20260910-230000")
r = P1.run("--no-ship")            # import only; ship is exercised explicitly below
r = P1.run("--ship", "--dry-run")
check("P1 dry run names the archive target and copies nothing",
      "Dumbbell Nebula (M 27)" in r.stdout and "Nothing copied" in r.stdout
      and not os.path.isdir(os.path.join(tE, "M 27_sub Day 3")), r.stdout[-500:])
r = P1.run("--ship")
d2 = os.path.join(tE, "M 27_sub Day 2"); d3 = os.path.join(tE, "M 27_sub Day 3")
check("P1 same night merges into the archive's Day 2, new night becomes Day 3",
      os.path.isfile(os.path.join(d2, "20260902-231000.fit"))
      and os.path.isfile(os.path.join(d2, "Light_M 27_10.0s_IRCUT_20260902-223000.fit"))
      and count_fits(d3) == 1, r.stdout[-500:])
check("P1 stack lands loose at the archive target root",
      os.path.isfile(os.path.join(tE, "Stacked_60_M 27_10.0s_IRCUT_20260910-230000.fit")), r.stdout[-300:])
check("P1 the archive's pre-existing file is untouched",
      open(os.path.join(tE, "M 27_sub Day 1", "Light_M 27_10.0s_IRCUT_20260901-223000.fit"), "rb").read() == b"old")
led = P1.ledger()
shipped = [e for e in led["files"].values() if e.get("archiveShippedAt")]
check("P1 ledger entries stamped with archiveLocation and archiveShippedAt, not yet verified",
      len(shipped) == 3 and all(e.get("archiveLocation", "").startswith("S30P\\") for e in shipped)
      and not any(e.get("archiveVerifiedAt") for e in shipped), str([e.get("archiveLocation") for e in shipped]))
sl = os.path.join(arch, "_verify", "mac", "shipped.jsonl")      # this machine's own folder (1.7.0)
lines = [x for x in (json.loads(y) for y in open(sl)) if x.get("state") == "shipped"] \
    if os.path.isfile(sl) else []
check("P1 shipped.jsonl written for the PC sweep, one line per file with sha and size",
      len(lines) == 3 and all(l["sha256"] and l["size"] and l["relpath"] for l in lines), str(lines[:1]))
rdir = os.path.join(P1.receipts, "_ship")
check("P1 a filed receipt v2 was written", os.path.isdir(rdir) and any(f.startswith("filed-") for f in os.listdir(rdir)))
_snap = os.path.join(arch, "_verify", "mac", "ledger-snapshot.json")
_sj = json.load(open(_snap, encoding="utf-8")) if os.path.isfile(_snap) else {}
check("P1 the ship leaves a copy of this computer's ledger rows in its own _verify folder "
      "(ledger-snapshot.json), for the other computer's --projects (1.7.0)",
      _sj.get("schema") == "ledger-snapshot/1" and _sj.get("machineId") and _sj.get("machineUid")
      and set(_sj.get("files") or {}) == set(P1.ledger()["files"])      # every row since 1.7.1
      and all(r.get("here") is True and "dest" not in r for r in _sj["files"].values())
      and all(r.get("verifiedAtImport") is True for k, r in _sj["files"].items()
              if P1.ledger()["files"][k].get("verifiedAtImport")),
      f"schema={_sj.get('schema')} uid={bool(_sj.get('machineUid'))} rows={sorted(_sj.get('files') or {})} "
      f"ledger={sorted(P1.ledger()['files'])} here={[r.get('here') for r in (_sj.get('files') or {}).values()]}")
r = P1.run("--ship")
check("P1 re-run ships nothing (already shipped, awaiting the sweep)",
      "Ship: 0 file(s)" in r.stdout and "3 already shipped" in r.stdout, r.stdout[-400:])
# The PC sweep verifies three of the four; the Mac stamps them on the next ship
with open(os.path.join(arch, "_verify", "verified.jsonl"), "w") as f:
    for l in lines[:2]:
        f.write(json.dumps({"sha256": l["sha256"], "size": l["size"], "relpath": l["relpath"], "verifiedAt": "2026-09-19T030000"}) + "\n")
r = P1.run("--ship")
led = P1.ledger()
ver = [e for e in led["files"].values() if e.get("archiveVerifiedAt")]
check("P1 verified.jsonl from the PC stamps archiveVerifiedAt on exactly those files",
      len(ver) == 2 and "2 frame(s) confirmed verified" in r.stdout, r.stdout[-400:])
# (1.4.3: one import run files each night in its own Mac Day folder too)
check("P1 nothing on the Mac was deleted or moved — and each night got its own Day",
      os.path.isfile(os.path.join(P1.sdest30, "M 27 - Dumbbell Nebula", "M 27_sub Day 1", "20260902-231000.fit"))
      and os.path.isfile(os.path.join(P1.sdest30, "M 27 - Dumbbell Nebula", "M 27_sub Day 2", "20260910-224402.fit")))

print("\n── Chain P2: --ship ASIAir naming and archive Day convention ──")
P2 = teh.Env("P2")
os.makedirs(os.path.join(P2.archive, "ZWO Askar Scopes"))
os.makedirs(os.path.join(P2.archive, "_verify"))
P2.add_light("Plan", "M 27", "0001", dt="20260720-220512")
P2.add_light("Plan", "M 27", "0002", dt="20260721-221512")
r = P2.run(stdin="n\n")           # a plain import ships by itself when the share is up
tE2 = os.path.join(P2.archive, "ZWO Askar Scopes", "Dumbbell Nebula (M 27)")
check("P2 an ordinary import ships automatically when the archive is mounted",
      "Shipped 2 file(s)" in r.stdout and os.path.isdir(tE2), r.stdout[-500:])
check("P2 ASIAir frames land under ZWO Askar Scopes\\Name (CODE)\\Name (CODE) Day N, one Day per night, no lights level",
      os.path.isdir(os.path.join(tE2, "Dumbbell Nebula (M 27) Day 1")) and os.path.isdir(os.path.join(tE2, "Dumbbell Nebula (M 27) Day 2"))
      and not os.path.isdir(os.path.join(tE2, "lights")), r.stdout[-500:] + str(os.listdir(tE2) if os.path.isdir(tE2) else "no dir"))

print("\n── Chain P3: --ship with the archive unreachable, and a conflicting file ──")
P3 = teh.Env("P3", asiair=False, seestar=True)
P3.add_seestar_sub("M 27", "20260910-224402")
shutil.rmtree(P3.archive, ignore_errors=True)   # share not mounted
r = P3.run()
check("P3 an import with the share down neither ships nor complains", "not reachable" not in r.stdout and "Shipped" not in r.stdout, r.stdout[-300:])
r = P3.run("--ship")
check("P3 unreachable archive is a quiet no-op", "not reachable" in r.stdout and r.returncode == 0, r.stdout[-300:])
os.makedirs(os.path.join(P3.archive, "S30P", "Dumbbell Nebula (M 27)", "M 27_sub Day 1"))
open(os.path.join(P3.archive, "S30P", "Dumbbell Nebula (M 27)", "M 27_sub Day 1", "20260910-224402.fit"), "wb").write(b"different bytes")
r = P3.run("--ship")
check("P3 an archive file with different content is reported and left untouched, entry not stamped",
      "different" in r.stdout and open(os.path.join(P3.archive, "S30P", "Dumbbell Nebula (M 27)", "M 27_sub Day 1", "20260910-224402.fit"), "rb").read() == b"different bytes"
      and not any(e.get("archiveShippedAt") for e in P3.ledger()["files"].values()), r.stdout[-400:])

print("\n── Chain P4: --ship finds frames moved by hand, matches targets by name (1.4.1) ──")
P4 = teh.Env("P4", asiair=False, seestar=True)
os.makedirs(os.path.join(P4.archive, "S30P", "Cave Nebula (Sh2-155)", "Sh2-155_sub Day 1"))
os.makedirs(os.path.join(P4.archive, "_verify"))
P4.add_seestar_sub("C 9", "20260910-224402")     # the camera calls it C 9; the archive says Sh2-155
P4.add_seestar_sub("C 9", "20260910-225402")
r = P4.run("--no-ship")
# Brett gathers the night into a flat lights/ folder by hand (Collect Lights style)
tmac = os.path.join(P4.sdest30, "C 9 - Cave Nebula")
ld = [d for d in os.listdir(tmac) if d.endswith("Day 1")][0]
os.makedirs(os.path.join(tmac, "lights"))
for fn in os.listdir(os.path.join(tmac, ld)):
    shutil.move(os.path.join(tmac, ld, fn), os.path.join(tmac, "lights", fn))
r = P4.run("--ship")
tE4 = os.path.join(P4.archive, "S30P", "Cave Nebula (Sh2-155)")
check("P4 frames moved into a flat lights folder are still found and shipped",
      "Shipped 2 file(s)" in r.stdout and "missing on Mac" not in r.stdout, r.stdout[-500:])
check("P4 a target whose camera token differs joins the archive's existing folder by name, next Day",
      os.path.isdir(os.path.join(tE4, "Sh2-155_sub Day 2"))
      and count_fits(os.path.join(tE4, "Sh2-155_sub Day 2")) == 2
      and not os.path.isdir(os.path.join(P4.archive, "S30P", "Cave Nebula (C 9)")),
      str(os.listdir(os.path.join(P4.archive, "S30P"))))

# ═══════════════ CHAIN D7: shipping without Delete rights (1.7.0) ════════════
print("\n── Chain D7: shipping without Delete rights (1.7.0, decision D7) ──")
# From 1.7.0 the archive's share user may create and write in the archive tree
# but never delete or rename there (spec P8), and in _verify only mac/ and
# lock/ are its own (10.1). teh.no_delete_env runs the real engine with those
# rights simulated, recording every refused attempt. 1.6.0 fails every check
# here: its probe, its .partial rename and its lock release all need Delete.
import hashlib
from datetime import datetime as _dt, timedelta as _td, timezone as _tz

def d7_tree(root):
    """Every file (size, mtime) and folder under root, '/'-separated."""
    out = {}
    for dp, dns, fns in os.walk(root):
        for d in dns:
            out[os.path.relpath(os.path.join(dp, d), root).replace(os.sep, "/") + "/"] = "dir"
        for fn in fns:
            p = os.path.join(dp, fn)
            st = os.stat(p)
            out[os.path.relpath(p, root).replace(os.sep, "/")] = (st.st_size, st.st_mtime_ns)
    return out

def d7_rows(path, state=None):
    try:
        with open(path, encoding="utf-8") as f:
            rows = [json.loads(x) for x in f if x.strip()]
    except OSError:
        return []
    return [x for x in rows if state is None or x.get("state") == state]

def d7_bad(root):
    """Refused attempts, except the harmless try at taking the 1.6 lock in _verify."""
    return [d for d in teh.denied(root)
            if not (d["op"] == "write" and d["path"].replace(os.sep, "/").endswith("_verify/ship.lock"))]

def d7_sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()

# These checks are the Mac's ship over the share, run on any computer: the
# PC's own log lives in _verify/pc, which the share user may only read.
# D7_MAC is defined before chain P1 (the ship chains all run as the Mac)

def d7_at(arch, rel):
    return os.path.join(arch, *rel.split("\\"))

def d7_probe(env, code):
    """Load the engine in a child (as m), run `code`; the JSON it printed last."""
    head = ("import importlib.util, json, os, sys\n"
            "s = importlib.util.spec_from_file_location('eng', sys.argv[1])\n"
            "m = importlib.util.module_from_spec(s); s.loader.exec_module(m)\n")
    r = subprocess.run([sys.executable, "-c", head + code, SCRIPT], env=env, input="",
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=120)
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {"error": (r.stdout + r.stderr)[-300:]}

D7 = teh.Env("D7", asiair=False, seestar=True)
D7.env.update(D7_MAC)
d7a = D7.archive
os.makedirs(os.path.join(d7a, "S30P")); os.makedirs(os.path.join(d7a, "_verify"))
with open(os.path.join(d7a, "_verify", "shipped.jsonl"), "w", encoding="utf-8") as f:
    # the 1.6 Mac's ship log: history now, never written again
    f.write(json.dumps({"relpath": "S30P\\old.fit", "size": 1, "sha256": "0" * 64}) + "\n")
for st in ("20260910-224402", "20260910-225402", "20260911-224402"):
    D7.add_seestar_sub("M 27", st)
D7.run("--no-ship")
ND = teh.no_delete_env(D7.root, d7a)
d7_before = d7_tree(d7a)
r = D7.run("--ship", extra_env=ND)
d7_after = d7_tree(d7a)
mlog = os.path.join(d7a, "_verify", "mac", "shipped.jsonl")
d7_started, d7_shipped = d7_rows(mlog, "started"), d7_rows(mlog, "shipped")
check("D7 without Delete rights the ship still files every frame under its final name",
      "Shipped 3 file(s)" in r.stdout and len(d7_shipped) == 3
      and all(os.path.isfile(d7_at(d7a, x["relpath"])) for x in d7_shipped),
      r.stdout[-500:] + r.stderr[-300:])
check("D7 ...and never tries to delete, rename or write over anything on the archive "
      "(its one refused try is the 1.6 lock in _verify)",
      d7_bad(D7.root) == [], str(teh.denied(D7.root))[:400])
_new = sorted(set(d7_after) - set(d7_before))
_changed = sorted(k for k in d7_before if k in d7_after and d7_before[k] != d7_after[k])
_gone = sorted(set(d7_before) - set(d7_after))
check("D7 all it writes is on the spec's allow-list: frames in the archive tree, its log in "
      "_verify/mac, its lock in _verify/lock; no .partial anywhere (10.1)",
      _new and not _gone and not _changed
      and all(p.startswith(("S30P/", "_verify/mac/", "_verify/lock/")) for p in _new)
      and not any(".partial" in p for p in d7_after),
      f"new={_new} changed={_changed} gone={_gone}")
check("D7 the 1.6 ship log in _verify is left exactly as it was",
      "_verify/shipped.jsonl" in d7_after
      and d7_before["_verify/shipped.jsonl"] == d7_after["_verify/shipped.jsonl"])
check("D7 a 'started' row before each frame and a 'shipped' row after its read-back, "
      "with the schema, size and hash",
      len(d7_started) == 3 and {x["relpath"] for x in d7_started} == {x["relpath"] for x in d7_shipped}
      and all(x.get("schema") == "ship-row/1" and x.get("sha256") and x.get("size")
              for x in d7_started + d7_shipped), str(d7_rows(mlog))[:400])
check("D7 the archive lock lives in _verify/lock and is released afterwards",
      not os.path.exists(os.path.join(d7a, "_verify", "lock", "ship.lock"))
      and not os.path.exists(os.path.join(d7a, "_verify", "ship.lock")))

# a copy cut off mid-file (the share went away), the PC sets it aside, the retry
D7b = teh.Env("D7b", asiair=False, seestar=True)
D7b.env.update(D7_MAC)
b_arch = D7b.archive
os.makedirs(os.path.join(b_arch, "S30P"))
for st in ("20260910-224402", "20260910-225402", "20260911-224402"):
    D7b.add_seestar_sub("M 27", st)
D7b.run("--no-ship")
r = D7b.run("--ship", extra_env=teh.no_delete_env(D7b.root, b_arch, cut_ship=3))
blog = os.path.join(b_arch, "_verify", "mac", "shipped.jsonl")
_failed = d7_rows(blog, "failed")
cut_rel = _failed[0]["relpath"] if _failed else "missing"
cut_path = d7_at(b_arch, cut_rel)
check("D7 a copy cut off mid-file stays under its final name, logged 'failed'; nothing is "
      "renamed or deleted",
      "Shipped 2 file(s)" in r.stdout and len(_failed) == 1 and "cut off" in _failed[0].get("why", "")
      and os.path.isfile(cut_path) and os.path.getsize(cut_path) < _failed[0]["size"]
      and d7_bad(D7b.root) == [], r.stdout[-400:] + str(_failed))
check("D7 ...and that frame is not stamped shipped in the ledger",
      sum(1 for e in D7b.ledger()["files"].values() if e.get("archiveShippedAt")) == 2)
D7b.add_seestar_sub("M 27", "20260912-224402")          # a new night meanwhile
D7b.run("--no-ship")
_size_cut = os.path.getsize(cut_path) if os.path.isfile(cut_path) else -1
r = D7b.run("--ship", extra_env=teh.no_delete_env(D7b.root, b_arch))
check("D7 the next ship leaves the unfinished copy alone for the PC and says so; the new "
      "night still ships",
      "1 file(s) wait for the archive sweep to set aside an unfinished copy" in r.stdout
      and "Shipped 1 file(s)" in r.stdout and os.path.getsize(cut_path) == _size_cut
      and len(d7_rows(blog, "started")) == 4, r.stdout[-500:])
# the PC's sweep sets it aside (the PC may move files on the archive; the Mac may not)
_q = os.path.join(b_arch, "_Quarantine", "ship-incomplete", *cut_rel.split("\\"))
os.makedirs(os.path.dirname(_q), exist_ok=True)
shutil.move(cut_path, _q)
r = D7b.run("--ship", extra_env=teh.no_delete_env(D7b.root, b_arch))
_again = [x for x in d7_rows(blog, "shipped") if x["relpath"] == cut_rel]
check("D7 once the PC has set it aside, the frame goes again to the same path",
      "Shipped 1 file(s)" in r.stdout and len(_again) == 1 and os.path.isfile(cut_path)
      and d7_sha(cut_path) == _again[0]["sha256"] and d7_bad(D7b.root) == [], r.stdout[-400:])
_days = {}
for x in d7_rows(blog, "shipped"):
    _days.setdefault(x["relpath"].split("\\")[-2], set()).add(
        re.search(r"(\d{8})-\d{6}", x["relpath"]).group(1))
check("D7 ...so its night keeps its Day folder, and the new night took the next Day",
      len(_days) == 3 and all(len(v) == 1 for v in _days.values()), str(_days))

# every byte arrived but the "shipped" row (and the ledger stamp) didn't
D7.add_seestar_sub("M 27", "20260913-224402")
D7.run("--no-ship")
D7.run("--ship", extra_env=ND)
_rows = d7_rows(mlog)
_last = [x for x in _rows if x.get("state") == "shipped"][-1]["relpath"]
with open(mlog, "w", encoding="utf-8") as f:
    for x in _rows:
        if not (x.get("state") == "shipped" and x["relpath"] == _last):
            f.write(json.dumps(x) + "\n")
_ledp = os.path.join(D7.state, "ledger.json")
_led = json.load(open(_ledp, encoding="utf-8"))
for e in _led["files"].values():
    if e.get("archiveLocation") == _last:
        e.pop("archiveLocation"); e.pop("archiveShippedAt")
json.dump(_led, open(_ledp, "w", encoding="utf-8"))
r = D7.run("--ship", extra_env=ND)
_adopted = [x for x in d7_rows(mlog, "shipped") if x["relpath"] == _last]
check("D7 a complete copy whose 'shipped' row was lost is recognised by its hash, not left waiting",
      "Shipped 1 file(s)" in r.stdout and len(_adopted) == 1 and _adopted[0].get("adopted") is True
      and any(e.get("archiveLocation") == _last for e in D7.ledger()["files"].values()),
      r.stdout[-400:])

# the Mac's copy changed since import: nothing is started for it
D7.add_seestar_sub("M 27", "20260914-224402")
D7.run("--no-ship")
_e14 = [e for e in D7.ledger()["files"].values() if e["filename"] == "20260914-224402.fit"][0]
_p14 = os.path.join(_e14["dest"], _e14["filename"])
_b = bytearray(open(_p14, "rb").read()); _b[-10] ^= 0xFF
open(_p14, "wb").write(bytes(_b))
_n_started = len(d7_rows(mlog, "started"))
r = D7.run("--ship", extra_env=ND)
check("D7 a frame changed on this computer since import is not sent, and nothing is started "
      "for it on the archive (1.6 renamed such a copy .BAD after writing it)",
      "no longer matches the ledger" in r.stdout and len(d7_rows(mlog, "started")) == _n_started
      and not any("20260914-224402" in p for p in d7_tree(d7a)), r.stdout[-400:])
open(_p14, "wb").write(bytes(_b[:-10]) + bytes([_b[-10] ^ 0xFF]) + bytes(_b[-9:]))  # put it back

# the archive lock (spec 11): live, stale, and a 1.6 machine's
_lockp = os.path.join(d7a, "_verify", "lock", "ship.lock")
def d7_put_lock(minutes_ago):
    t = (_dt.now(_tz.utc) - _td(minutes=minutes_ago)).isoformat(timespec="seconds")
    with open(_lockp, "w", encoding="utf-8") as f:
        json.dump({"schema": "ship-lock/1", "machineId": "chillblast", "machine": "the-pc",
                   "host": "CHILLBLAST", "pid": 4242, "op": "ship", "startedAt": t,
                   "renewedAt": t}, f)
d7_put_lock(1)
r = D7.run("--ship", extra_env=ND)
check("D7 another computer's live lock (renewed a minute ago): nothing shipped, its lock left alone",
      "CHILLBLAST is shipping into the archive right now" in r.stdout and "Shipped" not in r.stdout
      and json.load(open(_lockp, encoding="utf-8"))["host"] == "CHILLBLAST", r.stdout[-300:])
d7_put_lock(11)
r = D7.run("--ship", extra_env=ND)
check("D7 a lock not renewed for ten minutes is broken, that is written in the ship log, and "
      "the ship goes ahead",
      "Breaking a stale archive ship lock" in r.stdout and "Shipped 1 file(s)" in r.stdout
      and any(x.get("state") == "lock-broken" and (x.get("held") or {}).get("host") == "CHILLBLAST"
              for x in d7_rows(mlog)) and not os.path.exists(_lockp), r.stdout[-400:])
_legacy = os.path.join(d7a, "_verify", "ship.lock")
with open(_legacy, "w", encoding="utf-8") as f:
    json.dump({"machine": "old-mac", "host": "OLDMAC", "pid": 1, "at": "2026-10-03T090000"}, f)
D7.add_seestar_sub("M 27", "20260916-224402")
D7.run("--no-ship")
r = D7.run("--ship", extra_env=ND)
check("D7 a 1.6 importer's fresh _verify/ship.lock still stops this ship",
      "OLDMAC (an older importer) is shipping" in r.stdout and "Shipped" not in r.stdout
      and not os.path.exists(_lockp), r.stdout[-300:])
_old = time.time() - 7 * 3600
os.utime(_legacy, (_old, _old))
r = D7.run("--ship", extra_env=ND)
check("D7 ...but not once it is six hours old; the old lock file is left where it is",
      "Shipped 1 file(s)" in r.stdout and os.path.isfile(_legacy), r.stdout[-300:])
os.remove(_legacy)
got = d7_probe(D7.env, "\n".join([
    "p = os.path.join(m.ARCHIVE_MOUNT, '_verify', 'lock', 'ship.lock')",
    "L = m._archive_ship_lock(m.ARCHIVE_MOUNT)",
    "L.rec['renewedAt'] = '2000-01-01T00:00:00+00:00'",
    "ok1 = L.renew()",
    "fresh = json.load(open(p))['renewedAt'] != '2000-01-01T00:00:00+00:00'",
    "json.dump(dict(json.load(open(p)), pid=999999, host='OTHER'), open(p, 'w'))",
    "ok2 = L.renew()",
    "lost = L.lost",
    "L.release()",
    "print(json.dumps({'ok1': ok1, 'fresh': fresh, 'ok2': ok2, 'lost': lost,",
    "                  'kept': json.load(open(p))['host'] == 'OTHER'}))"]))
check("D7 the holder renews its lock, notices when another run has taken it over, and then "
      "leaves that run's lock alone",
      got == {"ok1": True, "fresh": True, "ok2": False, "lost": True, "kept": True}, str(got))
if os.path.exists(_lockp):
    os.remove(_lockp)

# why the archive isn't reachable (fix d)
D7d = teh.Env("D7d", asiair=False, seestar=True)
D7d.env.update(D7_MAC)
D7d.add_seestar_sub("M 27", "20260910-224402")
D7d.run("--no-ship")
r1 = D7d.run("--ship")
os.makedirs(D7d.archive)
r2 = D7d.run("--ship")
os.makedirs(os.path.join(D7d.archive, "S30P")); os.makedirs(os.path.join(D7d.archive, "_verify"))
open(os.path.join(D7d.archive, "_verify", "mac"), "w").close()       # can't be a folder now
r3 = D7d.run("--ship")
check("D7 'not reachable' says why: not mounted, no camera folders, or _verify/mac can't be "
      "written (fix d)",
      ("the folder isn't there" if os.name == "nt" else "the share isn't mounted") in r1.stdout
      and "none of S30P" in r2.stdout and "can't write in _verify" in r3.stdout
      and all(x.returncode == 0 and "not reachable" in x.stdout for x in (r1, r2, r3)),
      r1.stdout[-200:] + r2.stdout[-200:] + r3.stdout[-200:])
D7d.add_seestar_sub("M 27", "20260911-224402")
shutil.rmtree(D7d.archive)
r = D7d.run(extra_env={"ASTRO_ARCHIVE_URL": "smb://astro@TESTPC/AstroImageData"})
check("D7 a Terminal import with the share down still asks Finder to connect without a word, "
      "as 1.6 did",
      [c.get("url") for c in teh.os_calls(D7d.root, "mount")] == ["smb://astro@TESTPC/AstroImageData"]
      and "Finder" not in r.stdout and "not reachable" not in r.stdout and "Shipped" not in r.stdout,
      r.stdout[-300:])

# the archive's free space, and the PC's verified rows in _verify/pc
D7.add_seestar_sub("M 27", "20260917-224402")
D7.run("--no-ship")
_n_started = len(d7_rows(mlog, "started"))
r = D7.run("--ship", extra_env=dict(ND, ASTRO_ARCHIVE_MIN_FREE_GB="100000000"))
check("D7 a ship that would leave the archive short of space sends nothing and says so",
      "Nothing shipped: free up space on the archive" in r.stdout
      and len(d7_rows(mlog, "started")) == _n_started, r.stdout[-300:])
_ship_rows = d7_rows(mlog, "shipped")
with open(os.path.join(d7a, "_verify", "pc", "verified.jsonl"), "w", encoding="utf-8") as f:
    for x in _ship_rows[:2]:
        f.write(json.dumps({"schema": "verified-row/1", "relpath": x["relpath"], "sha256": x["sha256"],
                            "size": x["size"], "verifiedAt": "2026-10-04T033000"}) + "\n")
r = D7.run("--ship", extra_env=ND)
_ver = [e for e in D7.ledger()["files"].values() if e.get("archiveVerifiedAt") == "2026-10-04T033000"]
check("D7 the PC's verified rows, now in _verify/pc, stamp archiveVerifiedAt",
      len(_ver) == 2 and "2 frame(s) confirmed verified" in r.stdout, r.stdout[-300:])

# this computer's names (spec section 2)
_mid = json.load(open(os.path.join(D7.state, "machine.json"), encoding="utf-8"))["id"]
_idcode = "print(json.dumps(m.machine_identity()))"
g1 = d7_probe(D7.env, _idcode)
g2 = d7_probe(dict(D7.env, ASTRO_MACHINE_ID="Chill Blast"), _idcode)
g3 = d7_probe(dict(D7.env, ASTRO_MACHINE_ID="chillblast", ASTRO_MACHINE_LABEL="Chillblast"), _idcode)
_slug = "mac" if sys.platform == "darwin" else ("pc" if os.name == "nt" else "linux")
check("D7 each computer has a short name and a label beside its unchanged id; a name that "
      "breaks the rule is flagged",
      g1.get("id") == _mid and g1.get("slug") == _slug and g1.get("slugValid") is True
      and g2.get("slugValid") is False and g3.get("slug") == "chillblast"
      and g3.get("label") == "Chillblast" and g3.get("slugValid") is True and g3.get("id") == _mid,
      f"{g1} {g2} {g3}")
D7.add_seestar_sub("M 27", "20260918-224402")
D7.run("--no-ship")
_n_rows = len(d7_rows(mlog))
r = D7.run("--ship", extra_env=dict(ND, ASTRO_MACHINE_ID="Chill Blast"))
check("D7 ...and with such a name the ship writes nothing and says what to change",
      "Nothing shipped: this computer's short name 'Chill Blast' breaks the rule" in r.stdout
      and "ASTRO_MACHINE_ID" in r.stdout and len(d7_rows(mlog)) == _n_rows
      and not os.path.exists(_lockp), r.stdout[-300:])
r = D7.run("--ship", extra_env=dict(ND, ASTRO_MACHINE_ID="chillblast"))
_last = d7_rows(mlog, "shipped")[-1:]
check("D7 ...while a good one goes into each row it writes",
      "Shipped 1 file(s)" in r.stdout and _last and _last[0].get("machineId") == "chillblast",
      r.stdout[-300:])

# Collect Lights copies (fix b)
D7e = teh.Env("D7e", asiair=False, seestar=True)
D7e.env.update(D7_MAC)
os.makedirs(os.path.join(D7e.archive, "S30P"))
for st in ("20260910-224402", "20260910-225402", "20260910-230402"):
    D7e.add_seestar_sub("C 9", st)
D7e.run("--no-ship")
_tmac = os.path.join(D7e.sdest30, "C 9 - Cave Nebula")
_day = [d for d in os.listdir(_tmac) if d.endswith("Day 1")][0]
os.makedirs(os.path.join(_tmac, "lights", "lights"))
for fn in sorted(os.listdir(os.path.join(_tmac, _day))):
    _dst = os.path.join(_tmac, "lights", "lights", f"{_day.replace(' ', '_')}_{fn}")
    shutil.move(os.path.join(_tmac, _day, fn), _dst)
    if fn.startswith("20260910-230402"):          # same size, other bytes: not the frame
        _b = bytearray(open(_dst, "rb").read()); _b[-5] ^= 0xFF
        open(_dst, "wb").write(bytes(_b))
r = D7e.run("--ship", extra_env=teh.no_delete_env(D7e.root, D7e.archive))
_on_e = sorted(f for _dp, _d, fs in os.walk(os.path.join(D7e.archive, "S30P")) for f in fs)
check("D7 a frame Collect Lights renamed into lights/lights is found and filed under its own "
      "name (fix b)",
      "Shipped 2 file(s)" in r.stdout and "missing on Mac" not in r.stdout
      and _on_e == ["20260910-224402.fit", "20260910-225402.fit"], r.stdout[-400:] + str(_on_e))
check("D7 ...but a renamed file of the same size with other bytes is not taken for the frame",
      "no longer matches the ledger" in r.stdout and d7_bad(D7e.root) == [], r.stdout[-300:])

# calibration frames go with their lights (fix a)
D7c = teh.Env("D7c")
D7c.env.update(D7_MAC)
os.makedirs(os.path.join(D7c.archive, "ZWO Askar Scopes"))
D7c.add_light("Plan", "M 27", "0001", dt="20260721-010000")
D7c.add_light("Plan", "M 27", "0002", dt="20260721-011000")
D7c.add_cal("Bias", "1.0ms", "20260719-090000")
D7c.add_cal("Dark", "300.0s", "20260719-091000")
D7c.add_cal("Flat", "20.0ms", "20260720-090000", filt="LUltimate")
D7c.run("--no-ship", stdin="n\n")
r = D7c.run("--ship", "--dry-run")
check("D7 a dry run lists the calibration frames that would go, on their own line",
      "of which calibration frames: 3 file(s)" in r.stdout, r.stdout[-400:])
r = D7c.run("--ship", extra_env=teh.no_delete_env(D7c.root, D7c.archive))
_tE = os.path.join(D7c.archive, "ZWO Askar Scopes", "Dumbbell Nebula (M 27)", "Dumbbell Nebula (M 27) Day 1")
_cal_on_e = {k: os.listdir(os.path.join(_tE, "calibration", k))
             for k in ("biases", "darks", "flats") if os.path.isdir(os.path.join(_tE, "calibration", k))}
_cled = D7c.ledger()["calibration"]
check("D7 calibration frames now go with their lights, into the archive Day folder's "
      "calibration/biases, darks and flats (fix a)",
      "Shipped 5 file(s)" in r.stdout and sorted(_cal_on_e) == ["biases", "darks", "flats"]
      and all(len(v) == 1 for v in _cal_on_e.values()) and d7_bad(D7c.root) == []
      and all(len(c.get("archive") or {}) == 1 and all(x.get("shippedAt") and "\\calibration\\" in x["location"]
                                                       for x in c["archive"].values())
              for c in _cled.values()),
      r.stdout[-400:] + str(_cal_on_e))
_crows = [x for x in d7_rows(os.path.join(D7c.archive, "_verify", "mac", "shipped.jsonl"), "shipped")
          if "\\calibration\\" in x["relpath"]]
with open(os.path.join(D7c.archive, "_verify", "pc", "verified.jsonl"), "w", encoding="utf-8") as f:
    for x in _crows:
        f.write(json.dumps({"relpath": x["relpath"], "sha256": x["sha256"], "size": x["size"],
                            "verifiedAt": "2026-10-04T033000"}) + "\n")
r = D7c.run("--ship", extra_env=teh.no_delete_env(D7c.root, D7c.archive))
check("D7 ...the PC's check stamps each calibration copy, and nothing is sent twice",
      len(_crows) == 3 and "Ship: 0 file(s)" in r.stdout
      and all(x.get("verifiedAt") == "2026-10-04T033000"
              for c in D7c.ledger()["calibration"].values() for x in c["archive"].values()),
      r.stdout[-300:])

# The same under the operating system's own rights (plan, phase 0): a camera
# folder whose Delete is refused by an ACL (a Mac) or icacls (the PC), so a
# delete or rename anywhere in the ship would fail for real. Not on Linux
# (no such ACLs, and a test there may run as root, which ignores them).
D7r = teh.Env("D7r", asiair=False, seestar=True)
D7r.env.update(D7_MAC)
_rcam = os.path.join(D7r.archive, "S30P")
os.makedirs(_rcam); os.makedirs(os.path.join(D7r.archive, "_verify", "mac"))
for st in ("20260910-224402", "20260911-224402"):
    D7r.add_seestar_sub("M 27", st)
D7r.run("--no-ship")
# Who runs this test, asked of the OS: the suite wipes its own environment for
# test mode (isolate_runner), so USERDOMAIN and USERNAME are empty here. An
# empty name made icacls put the rule on the group "BUILTIN", which binds
# nobody, and the delete went through (first PC run, 11 Oct).
_me = ""
if os.name == "nt":
    _me = subprocess.run(["whoami"], capture_output=True, text=True).stdout.strip()
    if not _me:
        try:
            _me = os.getlogin()
        except OSError:
            _me = ""
if sys.platform == "darwin":
    _deny = ["chmod", "+a", "everyone deny delete,delete_child,file_inherit,directory_inherit", _rcam]
    _undo = ["chmod", "-R", "-N", _rcam]
elif os.name == "nt" and _me:
    _deny = ["icacls", _rcam, "/deny", f"{_me}:(OI)(CI)(DE,DC)"]
    _undo = ["icacls", _rcam, "/remove:d", _me, "/t", "/c", "/q"]
else:
    _deny = _undo = None
if _deny:
    _dr = subprocess.run(_deny, capture_output=True, text=True)
    try:
        r = D7r.run("--ship")
        _shipped = [os.path.join(dp, f) for dp, _d, fs in os.walk(_rcam) for f in fs]
        _acl = ""
        if _shipped and os.name == "nt":          # what the rule really put on the file
            _acl = " || ".join(subprocess.run(["icacls", q], capture_output=True, text=True).stdout.strip()[:220]
                               for q in (_shipped[0], os.path.dirname(_shipped[0]), _rcam))
        try:
            os.remove(_shipped[0])
            _refused = False
        except (OSError, IndexError):
            _refused = bool(_shipped)
        check("D7 under a real no-Delete rule from the operating system (an ACL on a Mac, icacls "
              "on the PC) the ship still files every frame, and a delete there is refused",
              _dr.returncode == 0 and "Shipped 2 file(s)" in r.stdout and len(_shipped) == 2
              and _refused,
              f"refused={_refused} shipped-on-disk={len(_shipped)} said-shipped-2={'Shipped 2 file(s)' in r.stdout} "
              f"ship rc={r.returncode} rights rc={_dr.returncode} | {r.stdout[-300:]!r} | {r.stderr[-300:]!r} "
              f"| {(_dr.stdout + _dr.stderr)[-120:]!r} | acl: {_acl}")
    finally:
        subprocess.run(_undo, capture_output=True, text=True)
elif os.name == "nt" or sys.platform == "darwin":
    # on Brett's machines this check must run: a skip there is a failure (1.7.0)
    check("D7 a real no-Delete folder from the operating system could be set up on this "
          "Mac or PC (the check above needs it)", False,
          "this PC could not say who runs the test (whoami failed)" if os.name == "nt"
          else "chmod +a / the ACL test could not be set up on this Mac")
else:
    skip("D7 a real no-Delete folder from the operating system (a Mac or the PC only)")

# ═══════════════ CHAIN PC: the archive PC's own jobs (1.7.0, phase 0) ════════
print("\n── Chain PC: the PC's sweep, inventory, hash cache and requests (1.7.0) ──")
# The PC runs this same engine (Sync View spec, section 2): --sweep replaces
# sweep.ps1 and writes only in _verify/pc; it sets aside only copies a ship
# started and never finished (decision 1), never the hand-copied ones. Test
# mode stands in for the PC on any computer.
import glob as _glob
PCX = {"ASTRO_SHIP_FOLDER": "pc", "ASTRO_SHIP_LOG": "shipped-pc.jsonl",
       "ASTRO_MACHINE_ID": "chillblast", "ASTRO_MACHINE_LABEL": "Chillblast"}
_READ = "unbuffered" if os.name == "nt" else "buffered"

def pc_rows(arch, name, **match):
    return [r for r in d7_rows(os.path.join(arch, "_verify", "pc", name))
            if all(r.get(k) == v for k, v in match.items())]

def pc_json(arch, *parts):
    try:
        with open(os.path.join(arch, "_verify", "pc", *parts), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}

def pc_file(arch, rel, data):
    p = os.path.join(arch, *rel.replace("\\", "/").split("/"))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(data)
    return p

def pc_sha(b):
    return hashlib.sha256(b).hexdigest()

def pc_utc(minutes_ago=0):
    return (_dt.now(_tz.utc) - _td(minutes=minutes_ago)).isoformat(timespec="seconds")

def pc_put_rows(path, rows, mode="a"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, mode, encoding="utf-8") as f:
        for x in rows:
            f.write(json.dumps(x) + "\n")

# the Mac ships four frames into the archive (D7 rights) ...
PCS = teh.Env("PCS", asiair=False, seestar=True)
PCS.env.update(D7_MAC)
pa = PCS.archive
os.makedirs(os.path.join(pa, "S30P"))
for st in ("20260910-224402", "20260910-225402", "20260911-224402", "20260911-225402"):
    PCS.add_seestar_sub("M 27", st)
PCS.run("--no-ship")
ND_S = teh.no_delete_env(PCS.root, pa)
r = PCS.run("--ship", extra_env=ND_S)
assert "Shipped 4 file(s)" in r.stdout, r.stdout[-400:]
# ... beside the 1.6 logs, now history, and the PC's own 1.7 log
_old_dir = "S30P\\Old (X 1)\\X 1_sub Day 1\\"
pc_file(pa, _old_dir + "old.fit", b"old frame")
pc_file(pa, _old_dir + "done.fit", b"done")
pc_file(pa, _old_dir + "bad.fit", b"wrong bytes")
pc_file(pa, _old_dir + "short.fit", b"12345")
_zwo = "ZWO Askar Scopes\\T (T 1)\\T (T 1) Day 1\\Light_T_1.fit"
pc_file(pa, _zwo, b"PC frame")
pc_put_rows(os.path.join(pa, "_verify", "shipped.jsonl"), [
    {"relpath": _old_dir + "old.fit", "size": 9, "sha256": pc_sha(b"old frame"), "machine": "Mac"},
    {"relpath": _old_dir + "done.fit", "size": 4, "sha256": pc_sha(b"done"), "machine": "Mac"},
    {"relpath": _old_dir + "bad.fit", "size": 11, "sha256": pc_sha(b"right bytes"), "machine": "Mac"},
    {"relpath": _old_dir + "short.fit", "size": 9, "sha256": pc_sha(b"123456789"), "machine": "Mac"},
    {"relpath": _old_dir + "gone.fit", "size": 3, "sha256": pc_sha(b"abc"), "machine": "Mac"},
    {"relpath": "..\\..\\outside.fit", "size": 3, "sha256": pc_sha(b"abc"), "machine": "Mac"}], "w")
pc_put_rows(os.path.join(pa, "_verify", "verified.jsonl"), [
    {"relpath": _old_dir + "done.fit", "sha256": pc_sha(b"done"), "size": 4,
     "verifiedAt": "2026-09-27T033000"}], "w")
pc_put_rows(os.path.join(pa, "_verify", "pc", "shipped-pc.jsonl"), [
    {"schema": "ship-row/1", "state": s_, "relpath": _zwo, "size": 8, "sha256": pc_sha(b"PC frame"),
     "machine": "PC", "machineId": "chillblast", "shipId": "p1", "at": pc_utc(90)}
    for s_ in ("started", "shipped")], "w")
_leg = {n: d7_sha(os.path.join(pa, "_verify", n)) for n in ("shipped.jsonl", "verified.jsonl")}
r = PCS.run("--sweep", extra_env=PCX)
_ver = pc_rows(pa, "verified.jsonl")
_prob = pc_rows(pa, "problems.jsonl")
_st = pc_json(pa, "status.json")
_mac_rels = {x["relpath"] for x in d7_rows(os.path.join(pa, "_verify", "mac", "shipped.jsonl"), "shipped")}
check("PC the sweep re-reads every frame each computer's log calls shipped (the 1.6 Mac's in "
      "_verify, the Mac's in _verify/mac, the PC's own in _verify/pc) from the PC's disk, and "
      "records each match in _verify/pc/verified.jsonl: schema, how it was read, by whom",
      r.returncode == 0 and {x["relpath"] for x in _ver} == _mac_rels | {_old_dir + "old.fit", _zwo}
      and len(_ver) == 6
      and all(x.get("schema") == "verified-row/1" and x.get("read") == _READ
              and x.get("hashedBy") == "chillblast" for x in _ver), r.stdout[-400:] + str(_ver)[:300])
check("PC ...a frame the old sweep verified isn't read again, and the 1.6 files in _verify are "
      "left exactly as they were",
      not any(x["relpath"].endswith("done.fit") for x in _ver)
      and _leg == {n: d7_sha(os.path.join(pa, "_verify", n)) for n in _leg}
      and not _glob.glob(os.path.join(pa, "_verify", "sweep_*.log")), str(_leg))
check("PC a wrong hash, a wrong size, a missing file and a path that leaves the archive each "
      "become one problem row, and the sweep says where to look",
      sorted(x["problem"] for x in _prob) == ["hash", "missing", "outside archive", "size 5"]
      and next(x for x in _prob if x["problem"] == "hash").get("found") == pc_sha(b"wrong bytes")
      and all(x.get("schema") == "problem-row/1" for x in _prob) and "ATTENTION" in r.stdout,
      str(_prob)[:400])
check("PC status.json keeps the old sweep's fields (Brett's PowerShell checks read them) and adds "
      "the new ones; the sweep's log is in _verify/pc",
      _st.get("verifiedThisRun") == 6 and _st.get("failedThisRun") == 3
      and _st.get("missingThisRun") == 1 and _st.get("pendingBefore") == 10
      and _st.get("totalVerified") == 7 and _st.get("totalProblems") == 4
      and _st.get("schema") == "sweep-status/1" and _st.get("machineId") == "chillblast"
      and _st.get("read") == _READ and _st.get("sweptAt") and _st.get("sweptAtUtc")
      and len(_glob.glob(os.path.join(pa, "_verify", "pc", "sweep_*.log"))) == 1, str(_st))
r = PCS.run("--sweep", extra_env=PCX)
check("PC a second sweep has nothing left to check: a problem is never retried by itself",
      len(pc_rows(pa, "verified.jsonl")) == 6 and len(pc_rows(pa, "problems.jsonl")) == 4
      and pc_json(pa, "status.json").get("pendingBefore") == 0, r.stdout[-300:])
r = PCS.run("--ship", extra_env=ND_S)
check("PC ...and the Mac's next ship stamps its four frames verified from _verify/pc",
      "4 frame(s) confirmed verified by the PC sweep" in r.stdout
      and sum(1 for e in PCS.ledger()["files"].values() if e.get("archiveVerifiedAt")) == 4,
      r.stdout[-300:])

# copies a ship never finished: set aside, only those, and only when it's safe
PCQ = teh.Env("PCQ", asiair=False, seestar=True)
PCQ.env.update(D7_MAC)
qa = PCQ.archive
os.makedirs(os.path.join(qa, "S30P"))
for st in ("20260910-224402", "20260910-225402", "20260911-224402"):
    PCQ.add_seestar_sub("M 27", st)
PCQ.run("--no-ship")
r = PCQ.run("--ship", extra_env=teh.no_delete_env(PCQ.root, qa, cut_ship=2))
qlog = os.path.join(qa, "_verify", "mac", "shipped.jsonl")
_cut = d7_rows(qlog, "failed")
_cut_rel = _cut[0]["relpath"] if _cut else "?"
_cut_path = d7_at(qa, _cut_rel)
_rd = os.path.join(qa, "_verify", "mac", "requests")
_reqs = sorted(os.listdir(_rd)) if os.path.isdir(_rd) else []
check("PC a ship that leaves a copy unfinished asks the PC for a sweep straight away "
      "(a request in _verify/mac/requests)",
      "Shipped 2 file(s)" in r.stdout and len(_cut) == 1 and len(_reqs) == 1
      and re.fullmatch(r"sweep-\d{8}T\d{6}Z-[a-z0-9-]+-[0-9a-f]{8}\.json", _reqs[0] or "")
      and "Asked the PC" in r.stdout, r.stdout[-400:] + str(_reqs))
_hand = pc_file(qa, "S30P/Hand (H 1)/H 1_sub Day 1/Light_hand.fit", b"hand copy")   # like the 865
_dss = pc_file(qa, "S30P/Dumbbell Nebula (M 27)/M 27_sub Day 1/.DS_Store", b"x")
r = PCQ.run("--sweep", extra_env=PCX)
check("PC the sweep leaves an unfinished copy alone for ten minutes after its ship",
      os.path.isfile(_cut_path) and not os.path.exists(os.path.join(qa, "_Quarantine"))
      and "less than ten minutes" in r.stdout, r.stdout[-300:])
r = PCQ.run("--pc-tick", extra_env=PCX)
_resp = pc_json(qa, "responses", _reqs[0] if _reqs else "?")
check("PC ...so the Mac's request is answered 'queued' and tried again at the next tick",
      _resp.get("status") == "queued" and _resp.get("schema") == "response/1", str(_resp))
_rows = d7_rows(qlog)
for x in _rows:
    x["at"] = pc_utc(60)                  # an hour passes (the copy was written after its row)
pc_put_rows(qlog, _rows, "w")
_qlock = os.path.join(qa, "_verify", "lock", "ship.lock")
with open(_qlock, "w", encoding="utf-8") as f:
    json.dump({"schema": "ship-lock/1", "machineId": "mac", "host": "BRETTS-MAC", "pid": 1,
               "op": "ship", "startedAt": pc_utc(2), "renewedAt": pc_utc(1)}, f)
r = PCQ.run("--sweep", extra_env=PCX)
check("PC ...and alone while any ship holds the archive lock",
      os.path.isfile(_cut_path) and "a ship is running" in r.stdout, r.stdout[-300:])
os.remove(_qlock)
r = PCQ.run("--pc-tick", extra_env=PCX)
_qdest = os.path.join(qa, "_Quarantine", "ship-incomplete", *_cut_rel.split("\\"))
_qrows = pc_rows(qa, "quarantine.jsonl")
check("PC then it moves that copy, and only it, into _Quarantine/ship-incomplete under the same "
      "path, and logs it; the hand-copied frame and Finder's file stay where they are",
      not os.path.exists(_cut_path) and os.path.isfile(_qdest) and len(_qrows) == 1
      and _qrows[0].get("relpath") == _cut_rel and _qrows[0].get("state") == "failed"
      and _qrows[0].get("schema") == "quarantine-row/1"
      and _qrows[0].get("expectedSize", 0) > _qrows[0].get("size", 0)
      and os.path.isfile(_hand) and os.path.isfile(_dss), str(_qrows)[:400])
_resp = pc_json(qa, "responses", _reqs[0] if _reqs else "?")
check("PC ...and answers the Mac's request: done, with what it did",
      _resp.get("status") == "done" and (_resp.get("result") or {}).get("setAside") == 1
      and os.path.isfile(os.path.join(_rd, _reqs[0] if _reqs else "?")), str(_resp))
r = PCQ.run("--ship", extra_env=teh.no_delete_env(PCQ.root, qa))
check("PC the Mac's next ship sends that frame again, to the same path",
      "Shipped 1 file(s)" in r.stdout and os.path.isfile(_cut_path)
      and os.path.getsize(_cut_path) == _cut[0].get("size"), r.stdout[-300:])
r = PCQ.run("--sweep", extra_env=PCX)
check("PC ...and the next sweep verifies it",
      any(x["relpath"] == _cut_rel for x in pc_rows(qa, "verified.jsonl")), r.stdout[-300:])
PCQ.add_seestar_sub("M 27", "20260912-224402")
PCQ.run("--no-ship")
PCQ.run("--ship", extra_env=teh.no_delete_env(PCQ.root, qa))
_urel = d7_rows(qlog, "shipped")[-1]["relpath"]
_up = d7_at(qa, _urel)
with teh.held_exclusively(_up):
    r = PCQ.run("--sweep", extra_env=dict(PCX, **teh.read_error_env(PCQ.root, [_up])))
check("PC a shipped frame that can't be read just now (in use, or a disk error) gets no problem "
      "row: the sweep says so and reads it again next time",
      "couldn't be read just now" in r.stdout
      and not any(x["relpath"] == _urel for x in pc_rows(qa, "problems.jsonl"))
      and not any(x["relpath"] == _urel for x in pc_rows(qa, "verified.jsonl"))
      and pc_json(qa, "status.json").get("unreadableThisRun") == 1, r.stdout[-300:])
r = PCQ.run("--sweep", extra_env=PCX)
check("PC ...and once it can be read, the next sweep verifies it",
      any(x["relpath"] == _urel for x in pc_rows(qa, "verified.jsonl")), r.stdout[-300:])
# every byte arrived, but the read-back over the share said otherwise
PCQ.add_seestar_sub("M 27", "20260914-224402")
PCQ.run("--no-ship")
PCQ.run("--ship", extra_env=teh.no_delete_env(PCQ.root, qa))
_rows = d7_rows(qlog)
_whole = [x for x in _rows if x.get("state") == "shipped"][-1]
for x in _rows:
    if x is _whole:
        x.update(state="failed", why="read back differs from what was sent")
    if x.get("relpath") == _whole["relpath"]:
        x["at"] = pc_utc(60)
pc_put_rows(qlog, _rows, "w")
_ledp = os.path.join(PCQ.state, "ledger.json")
_led = json.load(open(_ledp, encoding="utf-8"))
for e in _led["files"].values():
    if e.get("archiveLocation") == _whole["relpath"]:
        e.pop("archiveLocation"); e.pop("archiveShippedAt")
json.dump(_led, open(_ledp, "w", encoding="utf-8"))
r = PCQ.run("--sweep", extra_env=PCX)
check("PC a copy whose read-back failed but whose bytes are all there is left where it is "
      "(the PC reads it whole and correct), with no problem row",
      os.path.isfile(d7_at(qa, _whole["relpath"])) and "whole and correct" in r.stdout
      and not any(x["relpath"] == _whole["relpath"] for x in pc_rows(qa, "quarantine.jsonl"))
      and not any(x["relpath"] == _whole["relpath"] for x in pc_rows(qa, "problems.jsonl")),
      r.stdout[-300:])
r = PCQ.run("--ship", extra_env=teh.no_delete_env(PCQ.root, qa))
check("PC ...and the Mac's next ship records it as shipped without sending it again",
      "Shipped 1 file(s)" in r.stdout
      and [x.get("adopted") for x in d7_rows(qlog, "shipped") if x["relpath"] == _whole["relpath"]] == [True]
      and any(e.get("archiveLocation") == _whole["relpath"] for e in PCQ.ledger()["files"].values()),
      r.stdout[-300:])
_odd1 = pc_file(qa, "S30P/Odd (O 1)/O 1_sub Day 1/older.fit", b"older")
teh.backdate(_odd1, 3 * 3600)
_odd2 = pc_file(qa, "S30P/Odd (O 1)/O 1_sub Day 1/bigger.fit", b"far too many bytes")
pc_put_rows(qlog, [{"schema": "ship-row/1", "state": "started", "relpath": rel, "size": size,
                    "sha256": "0" * 64, "machine": "Mac", "machineId": "mac", "shipId": "odd",
                    "at": pc_utc(60)}
                   for rel, size in (("S30P\\Odd (O 1)\\O 1_sub Day 1\\older.fit", 5),
                                     ("S30P\\Odd (O 1)\\O 1_sub Day 1\\bigger.fit", 4))])
PCQ.run("--sweep", extra_env=PCX)
r = PCQ.run("--sweep", extra_env=PCX)
_oddp = [x for x in pc_rows(qa, "problems.jsonl")
         if str(x.get("problem")).startswith("unfinished copy left where it is")]
check("PC a 'started' copy older than its ship, or bigger than its frame, is never moved: one "
      "problem row each, not repeated",
      os.path.isfile(_odd1) and os.path.isfile(_odd2) and len(_oddp) == 2
      and any("older than the ship" in x["problem"] for x in _oddp)
      and any("bigger than the frame" in x["problem"] for x in _oddp), str(_oddp)[:400])
_twice = "S30P\\Odd (O 1)\\O 1_sub Day 2\\twice.fit"
for n in (1, 2):
    pc_file(qa, _twice, b"half")
    pc_put_rows(qlog, [{"schema": "ship-row/1", "state": s_, "relpath": _twice, "size": 8,
                        "sha256": "1" * 64, "machine": "Mac", "machineId": "mac",
                        "shipId": f"t{n}", "at": pc_utc(60 - n)} for s_ in ("started", "failed")])
    PCQ.run("--sweep", extra_env=PCX)
_qd = os.path.join(qa, "_Quarantine", "ship-incomplete", "S30P", "Odd (O 1)", "O 1_sub Day 2")
check("PC a second unfinished copy under the same path is set aside beside the first, never over it",
      sorted(os.listdir(_qd)) == ["twice (2).fit", "twice.fit"] if os.path.isdir(_qd) else False,
      str(os.listdir(_qd)) if os.path.isdir(_qd) else "no folder")
_day1 = "S30P/Dumbbell Nebula (M 27)/M 27_sub Day 1/"
_op1 = pc_file(qa, _day1 + "20260910-224402.fit.mac.partial", b"p" * 10)
_op2 = pc_file(qa, _day1 + "20260910-224402.fit.BAD", b"b" * 20)
r = PCQ.run("--sweep", extra_env=PCX)
_st = pc_json(qa, "status.json")
check("PC partial and .BAD copies a 1.6 ship left are listed (status and log) and left where they are",
      (_st.get("oldPartials") or {}).get("count") == 2 and (_st.get("oldPartials") or {}).get("bytes") == 30
      and os.path.isfile(_op1) and os.path.isfile(_op2) and "--move-old-partials" in r.stdout,
      str(_st.get("oldPartials")) + r.stdout[-300:])
with open(os.path.join(qa, "_verify", "ship.lock"), "w") as f:
    f.write("{}")
PCQ.run("--sweep", "--move-old-partials", extra_env=PCX)
_kept = os.path.isfile(_op1) and os.path.isfile(_op2)
os.remove(os.path.join(qa, "_verify", "ship.lock"))
r = PCQ.run("--sweep", "--move-old-partials", extra_env=PCX)
_od = os.path.join(qa, "_Quarantine", "old-partials", *_day1.rstrip("/").split("/"))
check("PC --move-old-partials waits while a 1.6 ship may be running, and otherwise moves them "
      "into _Quarantine/old-partials, logged; nothing is deleted",
      _kept and not os.path.exists(_op1) and not os.path.exists(_op2)
      and sorted(os.listdir(_od)) == ["20260910-224402.fit.BAD", "20260910-224402.fit.mac.partial"]
      and (pc_json(qa, "status.json").get("oldPartials") or {}).get("movedThisRun") == 2
      and sum(1 for x in pc_rows(qa, "quarantine.jsonl") if "1.6" in str(x.get("why"))) == 2,
      r.stdout[-300:])
# a job lock that a stopped job left behind, its process number since reused
# (here: this test's own, which is alive) only blocks while it is renewed
_jl = os.path.join(PCQ.state, "sweep.lock")
with open(_jl, "w", encoding="utf-8") as f:
    json.dump({"pid": os.getpid(), "since": pc_utc(20)}, f)
r_fresh = PCQ.run("--sweep", extra_env=PCX)
teh.backdate(_jl, 20 * 60)
r_old = PCQ.run("--sweep", extra_env=PCX)
check("PC a running job's lock blocks a second sweep, but one not renewed for ten minutes is a "
      "leftover, even when its process number now belongs to a live program",
      "already running" in r_fresh.stdout and "Sweep:" not in r_fresh.stdout
      and "Sweep:" in r_old.stdout and not os.path.exists(_jl),
      r_fresh.stdout[-200:] + r_old.stdout[-200:])
_pcb = d7_tree(os.path.join(qa, "_verify", "pc"))
r = PCQ.run("--sweep", extra_env=dict(PCX, ASTRO_MACHINE_ID="Chill Blast"))
check("PC with a short name that breaks the rule the sweep does nothing and says what to change",
      r.returncode == 2 and "ASTRO_MACHINE_ID" in r.stderr
      and d7_tree(os.path.join(qa, "_verify", "pc")) == _pcb, r.stderr[-300:])

# the inventory (spec 7.1)
pc_file(pa, "_Index/sweep/sweep.ps1", b"x")
pc_file(pa, "_rights-check/tree/canary.fit", b"c")
pc_file(pa, "_Quarantine/ship-incomplete/S30P/q.fit", b"q")
_ret = "_to_delete/S30P/Gone (G 1)/G 1_sub Day 3/20260801-220000.fit"
pc_file(pa, _ret, b"retired")
_dark = "ZWO Askar Scopes/T (T 1)/T (T 1) Day 1/calibration/darks/Dark_300.0s_Bin1_20260720-090000_0001.fit"
teh.backdate(pc_file(pa, _dark, b"dark frame"), 2 * 86400)
_stack = "S30P/Dumbbell Nebula (M 27)/Stacked_30_M 27_10.0s_IRCUT_20260910-230000.fit"
pc_file(pa, _stack, b"stack")
_jpg = "S30P/Dumbbell Nebula (M 27)/preview.jpg"
teh.backdate(pc_file(pa, _jpg, b"jpg"), 86400)
if os.name != "nt":
    os.symlink(PCS.state, os.path.join(pa, "S30P", "link-out"))
r = PCS.run("--inventory", "--root", pa, extra_env=PCX)
_ist = pc_json(pa, "inventory-E.status.json")
_gen = os.path.join(pa, "_verify", "pc", str(_ist.get("file")))
_irows = d7_rows(_gen)
_by = {x["relpath"]: x for x in _irows}
check("PC --inventory of the archive writes a new generation in _verify/pc, then the status file "
      "naming it, with its row count and its sha256",
      r.returncode == 0 and _ist.get("schema") == "inventory-status/1"
      and _ist.get("file") == f"inventory-E-{_ist.get('generation')}.jsonl"
      and _ist.get("rows") == len(_irows) > 0 and _ist.get("sha256OfJsonl") == d7_sha(_gen)
      and _ist.get("shipInProgress") is False, str(_ist))
check("PC ...it lists the frames and leaves out _verify, _Index, _Quarantine, the rights check "
      "and links",
      _old_dir.replace("\\", "/") + "old.fit" in _by
      and not any(k.split("/")[0] in ("_verify", "_Index", "_Quarantine", "_rights-check") for k in _by)
      and not any("link-out" in k for k in _by), str(sorted(_by))[:400])
_m27 = [x for x in _irows if x.get("target") == "Dumbbell Nebula (M 27)" and x.get("kind") == "light"]
check("PC ...each row says what its path says: camera and target folders, Day, night (from the "
      "name, noon to noon) and kind; _to_delete rows are marked retired",
      len(_m27) == 4 and all(x["camera"] == "S30P" and x["schema"] == "inventory-row/1"
                             and (x["day"], x["night"]) in ((1, "2026-09-10"), (2, "2026-09-11"))
                             and x["nightSource"] == "filename" for x in _m27)
      and (_by.get(_dark) or {}).get("kind") == "dark" and (_by.get(_stack) or {}).get("kind") == "stack"
      and (_by.get(_jpg) or {}).get("kind") == "other"
      and (_by.get(_ret) or {}).get("retired") is True and (_by.get(_ret) or {}).get("camera") == "S30P"
      and (_by.get(_ret) or {}).get("target") == "Gone (G 1)"
      and (_by.get(_ret) or {}).get("day") == 3, str(_m27)[:300] + str(_by.get(_ret)))
check("PC ...and no row has a hash yet: those come only from the PC's own hash cache",
      all(x.get("sha256") is None and x.get("read") is None for x in _irows), "")
r = PCS.run("--hash", "--root", pa, extra_env=PCX)
_cache = d7_rows(os.path.join(PCS.state, "hash-cache.jsonl"))
_seed = [x for x in _cache if x.get("source") == "verified.jsonl"]
_mine = [x for x in _cache if not x.get("source")]
_order = [x["relpath"] for x in _mine]
# Windows re-reads, unbuffered, only the seeded rows the old sweep read buffered
# (done.fit, from the 1.6 verified.jsonl); the PC's own sweep rows were read
# unbuffered already and are not read again. 6 files are new to the cache.
_n_own = 6 + (sum(1 for x in _seed if x.get("read") != "unbuffered") if os.name == "nt" else 0)
check("PC --hash starts the PC's cache from verified.jsonl (sizes that still match), then hashes "
      "the rest of the archive itself, newest first",
      r.returncode == 0 and len(_seed) == 7 and len(_mine) == _n_own
      and all(x["root"] == "E" and x["hashedBy"] == "chillblast" and x["read"] == _READ
              and x["sha256"] == d7_sha(d7_at(pa, x["relpath"])) for x in _mine)
      and _jpg in _order and _dark in _order and _order.index(_jpg) < _order.index(_dark)
      and f"Hashed {_n_own} file(s)" in r.stdout, r.stdout[-300:] + str(_order))
r = PCS.run("--inventory", "--root", pa, extra_env=PCX)
_irows = d7_rows(os.path.join(pa, "_verify", "pc", pc_json(pa, "inventory-E.status.json").get("file", "?")))
check("PC ...so the next inventory carries every file's hash, who made it and how it was read",
      _irows and all(x.get("sha256") == d7_sha(d7_at(pa, x["relpath"])) and x.get("hashedBy")
                     for x in _irows), str([x for x in _irows if not x.get("sha256")])[:300])
with open(d7_at(pa, _old_dir + "old.fit"), "ab") as f:
    f.write(b" and more")
PCS.run("--hash", "--root", pa, "--max-minutes", "0", extra_env=PCX)
r = PCS.run("--hash", "--root", pa, "--max-minutes", "0", extra_env=PCX)
_chg = [x for x in pc_rows(pa, "problems.jsonl") if x.get("problem") == "changed since it was hashed"]
check("PC a hashed file whose size or time changes is a problem (P7), written once; "
      "--max-minutes 0 hashes nothing and says what is left",
      len(_chg) == 1 and _chg[0]["relpath"].endswith("old.fit") and "Hashed 0 file(s)" in r.stdout
      and "1 left for next time" in r.stdout, r.stdout[-300:] + str(_chg))
_victim = d7_at(pa, _old_dir + "done.fit")
_vst = os.stat(_victim)
with open(_victim, "r+b") as f:
    f.write(b"DONE")                                 # same size, other bytes
os.utime(_victim, ns=(_vst.st_atime_ns, _vst.st_mtime_ns))
_last = [x for x in d7_rows(os.path.join(PCS.state, "hash-cache.jsonl"))
         if x["relpath"].endswith("done.fit")][-1]
pc_put_rows(os.path.join(PCS.state, "hash-cache.jsonl"),
            [dict(_last, checkedAt="2000-01-01T00:00:00+00:00")])      # checked longest ago
r = PCS.run("--hash", "--root", pa, "--rolling", extra_env=PCX)
_rot = [x for x in pc_rows(pa, "problems.jsonl")
        if x.get("problem") == "content changed since it was hashed"]
check("PC --rolling re-reads the 1/30th checked longest ago; a frame whose bytes changed under "
      "the same size and time is a problem (P7, bit rot)",
      len(_rot) == 1 and _rot[0]["relpath"].endswith("done.fit")
      and _rot[0].get("found") == d7_sha(_victim), r.stdout[-300:] + str(_rot))
_nfd = "S30P/Cafe\u0301 (C 1)/C 1_sub Day 1/20260801-210000.fit"       # é stored as e + accent
pc_file(pa, _nfd, b"accent")
r = PCS.run("--hash", "--root", pa, extra_env=PCX)
_crow = [x for x in d7_rows(os.path.join(PCS.state, "hash-cache.jsonl"))
         if x["relpath"] == "S30P/Caf\u00e9 (C 1)/C 1_sub Day 1/20260801-210000.fit"]
check("PC a name stored decomposed (é as e + accent) is read as it is on the disk, and listed "
      "in its composed (NFC) spelling",
      bool(_crow) and _crow[-1]["sha256"] == pc_sha(b"accent") and "couldn't be read" not in r.stdout,
      r.stdout[-300:])
_g_old = os.path.join(pa, "_verify", "pc", "inventory-E-20200101T000000Z.jsonl")
open(_g_old, "w").close()
_g_prev = pc_json(pa, "inventory-E.status.json").get("file")
r = PCS.run("--inventory", "--root", pa, extra_env=PCX)
_gens = sorted(os.path.basename(p) for p in _glob.glob(os.path.join(pa, "_verify", "pc", "inventory-E-*.jsonl")))
check("PC each inventory is a new generation; the one before stays for a day, older ones go",
      not os.path.exists(_g_old) and len(_gens) == 2 and _g_prev in _gens
      and pc_json(pa, "inventory-E.status.json").get("file") == _gens[-1], str(_gens))
with open(os.path.join(pa, "_verify", "lock", "ship.lock"), "w", encoding="utf-8") as f:
    json.dump({"schema": "ship-lock/1", "machineId": "mac", "pid": 1, "op": "ship",
               "startedAt": pc_utc(1), "renewedAt": pc_utc(0)}, f)
r = PCS.run("--inventory", "--root", pa, extra_env=PCX)
os.remove(os.path.join(pa, "_verify", "lock", "ship.lock"))
check("PC an inventory taken while a ship runs says so (shipInProgress), so newer files count as "
      "not yet listed",
      pc_json(pa, "inventory-E.status.json").get("shipInProgress") is True
      and "a ship was running" in r.stdout, r.stdout[-300:])
if os.name != "nt":
    _bad1 = pc_file(pa, "S30P/Odd/trailing.fit ", b"x")
    _bad2 = pc_file(pa, "S30P/Odd/NUL.fit", b"y")
    PCS.run("--inventory", "--root", pa, extra_env=PCX)
    r = PCS.run("--inventory", "--root", pa, extra_env=PCX)
    _uns = [x for x in pc_rows(pa, "problems.jsonl") if str(x.get("problem")).startswith("unsafe name")]
    _irows = d7_rows(os.path.join(pa, "_verify", "pc", pc_json(pa, "inventory-E.status.json").get("file", "?")))
    check("PC a file whose name breaks the spec's path rules (a trailing space, NUL.fit) is left out "
          "of the inventory and counted, and is one problem row, never opened",
          pc_json(pa, "inventory-E.status.json").get("skippedRows") == 2 and len(_uns) == 2
          and not any("/Odd/" in x["relpath"] for x in _irows), str(_uns)[:300])
    os.remove(_bad1); os.remove(_bad2)
else:
    skip("PC unsafe names in the archive (Windows can't make them)")
_wb_before = d7_tree(pa)
r1 = PCS.run("--inventory", "--root", PCS.sdest30)
r2 = PCS.run("--hash", "--root", PCS.sdest30)
_local = _glob.glob(os.path.join(PCS.state, "inventory-*.jsonl"))
_lrows = d7_rows(_local[0]) if len(_local) == 1 else []
check("PC on the Mac, --inventory and --hash of its own frame folders write only into its state "
      "folder (inventory-<short name>.jsonl, the hash cache), never on the archive",
      r1.returncode == 0 and r2.returncode == 0 and len(_local) == 1 and len(_lrows) == 4
      and any(x.get("root") == "workbench" for x in d7_rows(os.path.join(PCS.state, "hash-cache.jsonl")))
      and os.path.isfile(_local[0].replace(".jsonl", ".status.json")) and d7_tree(pa) == _wb_before,
      r1.stdout[-200:] + r2.stdout[-200:] + str(_local))

# path rules (spec 12) and the PC's reads
_cases = ["S30P/M 27/Day 1/a.fit", "S30P\\M 27\\a.fit", "/abs/a.fit", "C:/x.fit", "//server/share/a.fit",
          "S30P/../a.fit", "S30P/a\u0001.fit", "S30P/a:b.fit", "S30P/a.fit.", "S30P/a.fit ",
          "x/" + "a" * 300, "S30P/NUL.txt", "S30P/con", "S30P/CONIN$", "S30P/COM\u00b9.fit",
          "S30P/lpt3.fit", "Cafe\u0301/a.fit", "", "S30P//a.fit"]
_got = d7_probe(PCS.env, "print(json.dumps([m.safe_relpath(x) for x in " + json.dumps(_cases) + "]))")
check("PC paths read from any file follow spec 12: '/' and NFC; absolute, drive, UNC, '..', "
      "control characters, ':', a trailing dot or space, over 260, reserved names (NUL.txt, "
      "CONIN$, COM¹, LPT3) are refused",
      _got == ["S30P/M 27/Day 1/a.fit", "S30P/M 27/a.fit"] + [None] * 14 + ["Caf\u00e9/a.fit", None, None],
      str(_got))
_blob = os.urandom(3 * 1024 * 1024 + 123)
_hp = pc_file(PCS.root, "blob.fit", _blob)
_got = d7_probe(PCS.env, f"print(json.dumps(m.hash_file_unbuffered({_hp!r})))")
check("PC the PC's own reads bypass Windows' cache (FILE_FLAG_NO_BUFFERING, P1) and agree with an "
      "ordinary sha256, odd sizes too; elsewhere they say 'buffered'",
      _got == [pc_sha(_blob), len(_blob), _READ], str(_got))

# requests, answers and the heartbeat (spec 10)
_rdir = os.path.join(pa, "_verify", "mac", "requests")
r = PCS.run("--request", "sweep", extra_env=ND_S)
_rq = sorted(os.listdir(_rdir)) if os.path.isdir(_rdir) else []
_body = {}
if len(_rq) == 1:
    with open(os.path.join(_rdir, _rq[0]), encoding="utf-8") as f:
        _body = json.load(f)
check("PC --request on the Mac files <kind>-<UTC time>-<short name>-<8 hex>.json in "
      "_verify/mac/requests (spec 10.2)",
      r.returncode == 0 and len(_rq) == 1
      and re.fullmatch(r"sweep-\d{8}T\d{6}Z-[a-z0-9-]+-[0-9a-f]{8}\.json", _rq[0] if _rq else "")
      and _body.get("schema") == "request/1" and _body.get("kind") == "sweep"
      and _body.get("id") == (_rq[0][:-5] if _rq else None) and d7_bad(PCS.root) == [],
      r.stdout[-300:] + str(_rq))
r = PCS.run("--request", "sweep", extra_env=ND_S)
check("PC ...asked again while that one waits, it is reused, not repeated",
      sorted(os.listdir(_rdir)) == _rq and "already waiting" in r.stdout, r.stdout[-200:])
r = PCS.run("--pc-tick", extra_env=PCX)
_resp = pc_json(pa, "responses", _rq[0] if _rq else "?")
check("PC --pc-tick runs the sweep the Mac asked for and answers it (started, then done, with "
      "the result); the PC never moves or deletes the request",
      _resp.get("status") == "done" and _resp.get("kind") == "sweep" and _resp.get("startedAt")
      and _resp.get("finishedAt") and (_resp.get("result") or {}).get("ok") is True
      and os.path.isfile(os.path.join(_rdir, _rq[0] if _rq else "?")), str(_resp))
_t0 = d7_tree(pa)
r = PCS.run("--pc-tick", extra_env=PCX)
_t1 = d7_tree(pa)
_hb = pc_json(pa, "pc-heartbeat.json")
_hbt = _dt.fromisoformat(_hb.get("generatedAt", "2000-01-01T00:00:00+00:00"))
check("PC with nothing to do a tick writes only the heartbeat: who, when, and that nothing runs",
      sorted(k for k in set(_t0) | set(_t1) if _t0.get(k) != _t1.get(k)) == ["_verify/pc/pc-heartbeat.json"]
      and _hb.get("schema") == "pc-heartbeat/1" and _hb.get("job") == "idle"
      and _hb.get("sweepRunning") is False and _hb.get("inventoryRunning") is False
      and _hb.get("machineId") == "chillblast" and _hb.get("machineLabel") == "Chillblast"
      and abs((_dt.now(_tz.utc) - _hbt).total_seconds()) < 120, str(_hb))
_now = _dt.now(_tz.utc).strftime("%Y%m%dT%H%M%SZ")
_bad = {"expired": ("sweep-20200101T000000Z-macbook-0123abcd.json", "{}"),
        "big": (f"inventory-{_now}-macbook-11111111.json", json.dumps({"pad": "x" * 5000})),
        "notjson": (f"sweep-{_now}-macbook-22222222.json", "nope"),
        "later": (f"hash-{_now}-macbook-33333333.json", "{}"),
        "badname": ("sweep-now.json", "{}"),
        "unknown": (f"delete-{_now}-macbook-44444444.json", "{}")}
for _n, (_fn, _txt) in _bad.items():
    with open(os.path.join(_rdir, _fn), "w", encoding="utf-8") as f:
        f.write(_txt)
r = PCS.run("--pc-tick", extra_env=PCX)
_answers = {k: pc_json(pa, "responses", fn).get("status") for k, (fn, _t) in _bad.items()}
check("PC requests are checked before anything runs: over a day old is expired; too big, not "
      "JSON, or a kind for a later version is rejected; a name that isn't a request gets no answer",
      _answers == {"expired": "expired", "big": "rejected", "notjson": "rejected",
                   "later": "rejected", "badname": None, "unknown": None}, str(_answers))
r = PCS.run("--request", "inventory", extra_env=ND_S)
_left = sorted(os.listdir(_rdir))
_inv = [x for x in _left if x.startswith("inventory-") and "-macbook-" not in x]
check("PC the Mac's next --request tidies away its own requests the PC has finished with, and "
      "leaves other computers' alone",
      (_rq[0] if _rq else "?") not in _left and _bad["expired"][0] in _left and len(_inv) == 1,
      str(_left))
r = PCS.run("--pc-tick", extra_env=PCX)
_resp = pc_json(pa, "responses", _inv[0] if _inv else "?")
check("PC ...and an inventory request gets a new generation and is answered done",
      _resp.get("status") == "done" and ((_resp.get("result") or {}).get("rows") or 0) > 0,
      str(_resp))
r = PCS.run("--pc-nightly", extra_env=PCX)
check("PC --pc-nightly runs the sweep, the inventory and the hash (and the inventory again when "
      "it hashed anything), and leaves the heartbeat idle",
      r.returncode == 0 and "Sweep:" in r.stdout and r.stdout.count("Inventory:") >= 1
      and "Hashed" in r.stdout and pc_json(pa, "pc-heartbeat.json").get("job") == "idle",
      r.stdout[-400:])

# the share's rights, tried from the Mac on the PC's test folder
CR = teh.Env("CR", asiair=False, seestar=True)
r0 = CR.run("--check-share-rights")
_rc = os.path.join(CR.archive, "_rights-check")
pc_file(_rc, "tree/canary.fit", b"PC canary")
pc_file(_rc, "_verify/canary.jsonl", b"{}\n")
pc_file(_rc, "_verify/pc/canary.json", b"{}\n")
r1 = CR.run("--check-share-rights", extra_env=teh.no_delete_env(CR.root, _rc))
r2 = CR.run("--check-share-rights")
check("PC --check-share-rights with no test folder says to run the PC's script first",
      r0.returncode == 1 and "set-archive-rights.ps1 -Scratch" in r0.stderr, r0.stderr[-200:])
check("PC ...under D7's rights every answer is right (create and write, never delete or rename; "
      "in _verify only mac and lock) and it says so",
      r1.returncode == 0 and "FAIL" not in r1.stdout and r1.stdout.count("PASS") == 24
      and "what D7 needs" in r1.stdout, r1.stdout[-600:] + r1.stderr[-200:])
check("PC ...with the old rights it names each wrong answer and says not to apply them; it never "
      "touches anything outside the test folder",
      r2.returncode == 1 and r2.stdout.count("FAIL") == 11 and "Don't apply" in r2.stderr
      and os.listdir(CR.archive) == ["_rights-check"], r2.stdout[-400:] + str(os.listdir(CR.archive)))

print("\n── Chain F2: --set-filter ledger correction ─────────────────")
F2 = teh.Env("F2")
F2.add_light("Plan", "NGC 7822", "0001", dt="20260623-235000", filt=None)
F2.add_light("Plan", "NGC 7822", "0002", dt="20260624-231500", filt=None)
F2.add_light("Plan", "M 81", "0001", dt="20260623-221000")
r = F2.run("--baseline")
led = F2.ledger()
check("F2 no-token lights recorded as no filter",
      all(e["filter"] == "" for e in led["files"].values() if e["target"] == "NGC 7822"))
r = F2.run("--set-filter", "NGC 7822", "LeNhance", "--night", "2026-06-23")
led = F2.ledger()
by_night = {e["night"]: e["filter"] for e in led["files"].values()
            if e["target"] == "NGC 7822"}
check("F2 night-limited correction",
      by_night.get("2026-06-23") == "LeNhance" and by_night.get("2026-06-24") == "",
      str(by_night) + r.stdout[-200:])
r = F2.run("--set-filter", "NGC 7822", "LeNhance")
led = F2.ledger()
check("F2 full-target correction",
      all(e["filter"] == "LeNhance" for e in led["files"].values()
          if e["target"] == "NGC 7822"))
check("F2 other targets untouched",
      all(e["filter"] == "LUltimate" for e in led["files"].values()
          if e["target"] == "M 81"))
r = F2.run("--set-filter", "NGC 7822", "none")
led = F2.ledger()
check("F2 'none' clears the filter",
      all(e["filter"] == "" for e in led["files"].values()
          if e["target"] == "NGC 7822"))
hist = open(os.path.join(F2.state, "history.jsonl")).read()
check("F2 history logs corrections", hist.count("filter-corrected") >= 3)

# ═══════════════ CHAIN I1: test mode (1.5.2) ══════════════════════════════════
print("\n── Chain I1: test mode — nothing outside the test root, no OS side effects (1.5.2) ──")
# 25 Sep 2026: the 1.5.1 suites, run on the real Mac, shipped fake frames into
# the real archive, moved a real iCloud folder and popped real dialogs. Every
# check here but the last fails on 1.5.1. "Outside" is a sibling temp folder.
HERE = os.path.dirname(SCRIPT)

def irun(env, *args, script=SCRIPT, stdin=""):
    return subprocess.run([sys.executable, script, *args], env=env, input=stdin,
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=120)

def probe(env, code, before=""):
    """Load the engine in a child (as m), run `code`; the JSON it printed last."""
    head = ("import importlib.util, json, os, sys\n"
            "s = importlib.util.spec_from_file_location('eng', sys.argv[1])\n"
            "m = importlib.util.module_from_spec(s); s.loader.exec_module(m)\n")
    # stdin: an empty pipe, never a tty (Windows' NUL claims to be one)
    r = subprocess.run([sys.executable, "-c", before + head + code, SCRIPT], env=env,
                       input="", capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=120)
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {"error": (r.stdout + r.stderr)[-300:]}

def inside(path, root):
    p, r = (os.path.normcase(os.path.realpath(x)) for x in (path, root))
    return p == r or p.startswith(r.rstrip(os.sep) + os.sep)

def mentions(call, path):
    """Does a recorded OS call name `path` (or something inside it)?"""
    return any(isinstance(v, str) and inside(v, path)
               for k, v in call.items() if k not in ("kind", "at"))

# every configured path outside the root stops the engine before it does anything
I1 = teh.Env("I1", asiair=False, seestar=False)
outside = tempfile.mkdtemp(prefix="v2test-I1-outside-")
for var in ("ASIAIR_CONFIG", "ASIAIR_VOLUME", "ASIAIR_DEST", "ASIAIR_CAL_LIBRARY",
            "ASIAIR_STATE", "ASIAIR_MIRROR", "ASTRO_ARCHIVE_MOUNT", "SEESTAR_VOLUME",
            "SEESTAR_DEST_S30", "SEESTAR_DEST_S50", "SEESTAR_DEST_S30_ORIG",
            "SEESTAR_DEST_S50PRO", "ASIAIR_EQUIPMENT", "ASIAIR_RECEIPTS",
            "ASIAIR_LEGACY_NAMES", "ASTRO_DRIVE_ROOTS", "ASTRO_WATCH_LOG", "ASTRO_WATCH_STATE",
            "ASTRO_SHIP_LOG", "ASTRO_PHONE_DIR"):
    r = I1.run("--version", extra_env={var: os.path.join(outside, var)})
    out = r.stdout + r.stderr
    check(f"I1 {var} outside the test root is refused at start (exit 3), nothing written there",
          r.returncode == 3 and "TEST MODE:" in out and var in out and not os.listdir(outside),
          f"rc={r.returncode} {out[-300:]}")
# a config.json outside stops the run; the same file inside is honoured
cfg_out = os.path.join(tempfile.mkdtemp(prefix="v2test-I1-config-"), "config.json")
cfg_in = os.path.join(I1.root, "config.json")
named = os.path.join(outside, "archive-named-by-config")
for p in (cfg_out, cfg_in):
    with open(p, "w") as f:
        json.dump({"ASTRO_ARCHIVE_MOUNT": named}, f)
r = irun(teh.make_env(I1.root, ASIAIR_CONFIG=cfg_out, ASTRO_ARCHIVE_MOUNT=None), "--version")
out = r.stdout + r.stderr
check("I1 an outside config.json stops the run, exit 3",
      r.returncode == 3 and "ASIAIR_CONFIG" in out and "ASTRO_ARCHIVE_MOUNT" not in out
      and named not in out, f"rc={r.returncode} {out[-300:]}")
r = irun(teh.make_env(I1.root, ASIAIR_CONFIG=cfg_in, ASTRO_ARCHIVE_MOUNT=None), "--version")
out = r.stdout + r.stderr
check("I1 ...the same file inside the root IS read, and the outside archive it names refused",
      r.returncode == 3 and "ASTRO_ARCHIVE_MOUNT" in out, f"rc={r.returncode} {out[-300:]}")
# a path typed on the command line is judged too
r = I1.run("--export-settings", os.path.join(outside, "settings.json"))
check("I1 --export-settings to a file outside the test root stops (exit 3), nothing written",
      r.returncode == 3 and "TEST MODE:" in r.stdout + r.stderr and not os.listdir(outside),
      f"rc={r.returncode} " + (r.stdout + r.stderr)[-300:])
# make_env takes only the allowlisted keys from the runner's own environment
saved = dict(os.environ)
try:
    os.environ.update(ASTRO_LEAK_SENTINEL="1", HOME="/nonexistent-real")
    leak = teh.make_env(I1.root)
finally:
    os.environ.clear()
    os.environ.update(saved)
check("I1 make_env passes on no stray parent key (ASTRO_LEAK_SENTINEL) and never the real HOME",
      "ASTRO_LEAK_SENTINEL" not in leak and leak.get("HOME") == os.path.join(I1.root, "home"),
      str({k: leak.get(k) for k in ("ASTRO_LEAK_SENTINEL", "HOME")}))

# with no path set at all and HOME elsewhere, every default lands in the root
I1d = teh.Env("I1d", asiair=False, seestar=False)
away = tempfile.mkdtemp(prefix="v2test-I1-home-")
got = probe(teh.make_env(I1d.root, HOME=away, USERPROFILE=away,
                         LOCALAPPDATA=os.path.join(away, "AppData", "Local"),
                         APPDATA=os.path.join(away, "AppData", "Roaming"),
                         **{v: None for v in (
                             "ASIAIR_VOLUME", "ASIAIR_DEST", "ASIAIR_CAL_LIBRARY", "ASIAIR_STATE",
                             "ASIAIR_MIRROR", "ASIAIR_EQUIPMENT", "ASIAIR_RECEIPTS",
                             "ASIAIR_LEGACY_NAMES", "ASIAIR_CONFIG", "SEESTAR_VOLUME",
                             "SEESTAR_DEST_S30", "SEESTAR_DEST_S50", "SEESTAR_DEST_S30_ORIG",
                             "SEESTAR_DEST_S50PRO", "ASTRO_ARCHIVE_MOUNT", "ASTRO_DRIVE_ROOTS")}),
            "names = ('_CONFIG_PATH', 'ASIAIR_VOLUME', 'DEST_DIR', 'LIBRARY_DIR', 'STATE_DIR',\n"
            "         'MIRROR_DIR', 'ARCHIVE_MOUNT', 'SEESTAR_DEST_S30', 'SEESTAR_DEST_S50',\n"
            "         'SEESTAR_DEST_S30_ORIG', 'SEESTAR_DEST_S50PRO', 'EQUIPMENT_JSON',\n"
            "         'RECEIPT_BASE', 'LEGACY_CUSTOM_NAMES')\n"
            "print(json.dumps({'paths': {n: getattr(m, n) for n in names},\n"
            "                  'seestar': m.SEESTAR_VOLUMES, 'drives': m._drive_roots(),\n"
            "                  'home': os.path.expanduser('~')}))\n")
paths = got.get("paths") or {}
bad = {k: v for k, v in paths.items() if not inside(v, I1d.root)}
check("I1 with no path set, every engine default lands inside the test root (no /Volumes, E:\\, real home)",
      bool(paths) and not bad, str(bad or got)[:300])
check("I1 ...no default Seestar volumes and no drive letters to look at",
      got.get("seestar") == [] and got.get("drives") == [], str(got)[:300])
check("I1 ...and a HOME outside the root is swapped for a fake one inside it",
      inside(got.get("home") or away, I1d.root) and not os.listdir(away), str(got)[:300])

# the one-time legacy migration (the pre-July-2026 state and iCloud folders)
def legacy_folders(home):
    """The two pre-unification folders under `home`, each holding a ledger."""
    out = []
    for parts in (("Library", "Application Support", "ASIAir Import"),
                  ("Library", "Mobile Documents", "com~apple~CloudDocs", "Astro Tools",
                   "ASIAir Import")):
        d = os.path.join(home, *parts)
        os.makedirs(d)
        with open(os.path.join(d, "ledger.json"), "w") as f:
            json.dump({"version": 1, "files": {}, "calibration": {}}, f)
        out.append(d)
    return out

def stayed(d):
    return os.path.isfile(os.path.join(d, "ledger.json")) \
        and not os.path.exists(os.path.join(d, "MOVED.txt"))

I1m = teh.Env("I1mig", asiair=False, seestar=False)
old_state, old_mirror = legacy_folders(os.path.join(I1m.root, "home"))
# state at its default (in the fake home), so only test mode can stop that move
r = irun(teh.make_env(I1m.root, ASIAIR_STATE=None), "--version")
check("I1 under a test the legacy migration never runs (both old folders stay put)",
      r.returncode == 0 and stayed(old_state) and stayed(old_mirror), (r.stdout + r.stderr)[-300:])
# a REAL run (no test root) with HOME, config, state and mirror all in a temp folder
mig = tempfile.mkdtemp(prefix="v2test-I1-migrate-")
old_state, old_mirror = legacy_folders(os.path.join(mig, "home"))
r = irun(teh.make_env(mig, ASTRO_TEST_ROOT=None), "--version")
check("I1 a real run never migrates into a redirected state or mirror folder",
      r.returncode == 0 and stayed(old_state) and stayed(old_mirror), (r.stdout + r.stderr)[-300:])
mig = tempfile.mkdtemp(prefix="v2test-I1-migrate-")
old_state, old_mirror = legacy_folders(os.path.join(mig, "home"))
r = irun(teh.make_env(mig, ASTRO_TEST_ROOT=None, ASIAIR_MIRROR=None), "--version")
new_mirror = os.path.join(mig, "home", "Documents", "Astro", "Import Status")
check("I1 ...but still migrates into the DEFAULT mirror folder (breadcrumb left), pair by pair",
      os.path.isfile(os.path.join(new_mirror, "ledger.json"))
      and os.path.isfile(os.path.join(old_mirror, "MOVED.txt")) and stayed(old_state),
      (r.stdout + r.stderr)[-300:])
# ...and into a mirror chosen in config.json (Brett's own set-up: the iCloud
# mirror). A user's setting is not a redirect; only the environment is.
mig = tempfile.mkdtemp(prefix="v2test-I1-migrate-")
old_state, old_mirror = legacy_folders(os.path.join(mig, "home"))
cfg_mirror = os.path.join(mig, "home", "iCloud", "Astro Import")
cfg_path = os.path.join(mig, "config.json")
with open(cfg_path, "w") as f:
    json.dump({"ASIAIR_MIRROR": cfg_mirror}, f)
r = irun(teh.make_env(mig, ASTRO_TEST_ROOT=None, ASIAIR_MIRROR=None,
                      ASIAIR_CONFIG=cfg_path), "--version")
check("I1 ...and into a mirror set in config.json (a user's choice, not a redirect)",
      os.path.isfile(os.path.join(cfg_mirror, "ledger.json"))
      and os.path.isfile(os.path.join(old_mirror, "MOVED.txt")) and stayed(old_state),
      (r.stdout + r.stderr)[-300:])

# an ASIAir import: notification, Finder label and the name dialog are recorded,
# never shown. The fake OS commands first on PATH prove nothing ran.
I1i = teh.Env("I1imp")
I1i.add_light("Plan", "M 81", "0001", dt="20260720-221000")
I1i.add_light("Plan", "MYSTERY 7", "0001", dt="20260720-223000")
e = dict(I1i.env)
e["PATH"] = teh.fake_os_commands(I1i.root) + os.pathsep + e["PATH"]
r = irun(e, stdin="n\n")
calls = teh.os_calls(I1i.root)
check("I1 an import's notification and Finder label are recorded, not shown",
      any(c["kind"] == "notify" for c in calls)
      and any(c["kind"] == "tag" and mentions(c, I1i.cam) for c in calls),
      json.dumps(calls)[:300] + r.stdout[-300:])
check("I1 an unknown target's name dialog is recorded; the import goes on under the folder name",
      any(c["kind"] == "dialog" and "MYSTERY 7" in c.values() for c in calls)
      and count_fits(day_dir(I1i, "MYSTERY 7", 1)) == 1, json.dumps(calls)[:300] + r.stdout[-300:])
if os.name == "nt":
    skip("I1 no fake OS command ran (Windows runs no shell scripts; "
          "the records above are the proof)")
else:
    check("I1 ...and no OS command ran (the fake ones first on PATH stayed silent)",
          not teh.executed(I1i.root), teh.executed(I1i.root)[-300:])

# the S11 case: a piped 'y' meant for a SAFE card that never came lands on the
# eject offer. Recorded; the temp card is never ejected.
I1e = teh.Env("I1ej", asiair=False, seestar=True)
s20_seed_ledger(I1e)                                   # no baseline offer to answer first
I1e.add_seestar_sub("M 42", "20260905-210000", creator="Seestar S50 Pro")
with open(os.path.join(I1e.myworks, "M 42_sub", "focus-notes.txt"), "w") as f:
    f.write("HFD 2.1")                                 # unproven: no SAFE card
e = dict(I1e.env, ASTRO_STDIN_PROMPTS="1")
e["PATH"] = teh.fake_os_commands(I1e.root) + os.pathsep + e["PATH"]
r = irun(e, "--no-ship", stdin="y\n")
ej = teh.os_calls(I1e.root, "eject")
check("I1 a stray 'y' on the eject offer is recorded and nothing is ejected (the S11 case)",
      any(mentions(c, I1e.svol) for c in ej) and not teh.executed(I1e.root),
      json.dumps(ej) + r.stdout[-300:])

# every OS gate called directly (most are out of the suites' reach otherwise)
I1g = teh.Env("I1gate", asiair=False, seestar=False)
e = dict(I1g.env)
e["PATH"] = teh.fake_os_commands(I1g.root) + os.pathsep + e["PATH"]
GATE_PROBE = """
import ctypes, types
root = m.TEST_ROOT
err = {}
for kind, call in (
        ('notify', lambda: m.notify('hi')),
        ('eject', lambda: m.eject_volume(os.path.join(root, 'Seestar'))),
        ('open', lambda: m.open_path(os.path.join(root, 'dashboard.html'))),
        ('mount', lambda: m._try_mount_archive(os.path.join(root, 'archive-mount'),
                                               'smb://example.invalid/x', wait=0)),
        ('powershell', lambda: m._powershell('Write-Output hi')),
        ('choose', lambda: m._choose_from_list(['a'], 'p', 't')),
        ('dialog', lambda: m.ask_target_name('X')),
        ('tag', lambda: m.tag_purple(root))):
    try:
        call()
    except Exception as x:
        err[kind] = repr(x)
within = [m._within(root, root), m._within(os.path.join(root, 'a'), root),
          m._within(root + '-other', root), m._within(os.path.dirname(root), root)]
# Windows forced, no ASTRO_DRIVE_ROOTS: a stand-in ctypes that reports a
# removable E: shows whether the real drive letters would be looked at
os.environ.pop('ASTRO_DRIVE_ROOTS', None)
touched = []
class _K32:
    def __getattr__(self, n):
        touched.append(n)
        return lambda *a: {'GetLogicalDrives': 1 << 4, 'GetDriveTypeW': 2}.get(n, 0)
sys.modules['ctypes'] = types.SimpleNamespace(windll=types.SimpleNamespace(kernel32=_K32()),
                                              c_wchar_p=str)
was, m.IS_WINDOWS = m.IS_WINDOWS, True
try:
    drives = m._drive_roots()
finally:
    m.IS_WINDOWS = was
    sys.modules['ctypes'] = ctypes
# the real console fallbacks (test mode off, not a Mac): stdin is not a tty,
# so they return at once, asking and running nothing
tty = bool(sys.stdin and sys.stdin.isatty())
m.TEST_ROOT, m.IS_MAC = '', False
console = None if tty else [m._choose_from_list(['a', 'b'], 'p', 't'),
                            list(m.ask_target_name('X'))]
print(json.dumps({'err': err, 'within': within, 'drives': drives, 'ctypes': touched,
                  'tty': tty, 'console': console}))
"""
got = probe(e, GATE_PROBE)
calls = teh.os_calls(I1g.root)
for kind in ("notify", "eject", "open", "mount", "powershell", "choose", "dialog", "tag"):
    n = sum(c.get("kind") == kind for c in calls)
    check(f"I1 gate '{kind}' called directly: recorded exactly once, not performed",
          n == 1 and kind not in (got.get("err") or {}), f"{n} record(s) {json.dumps(got)[:300]}")
if os.name == "nt":
    skip("I1 ...none of them ran a fake OS command (Windows runs no shell scripts)")
else:
    check("I1 ...none of them ran an OS command (the fake ones stayed silent)",
          not teh.executed(I1g.root), teh.executed(I1g.root)[-300:])
check("I1 _within: the root and inside it yes; a same-named sibling and the parent no",
      got.get("within") == [True, True, False, False], str(got)[:300])
check("I1 _drive_roots under a test, Windows forced, no ASTRO_DRIVE_ROOTS: [] and ctypes untouched",
      got.get("drives") == [] and got.get("ctypes") == [], str(got)[:300])
check("I1 the console fallbacks with no tty: the chooser gives None, the name question (None, False)",
      got.get("tty") is False and got.get("console") == [None, [None, False]], str(got)[:300])

# Seestar discovery never lists /Volumes (SEESTAR_VOLUME missing or unset, no drive roots)
I1s = teh.Env("I1see", asiair=False, seestar=False)
wrap = ("import os\nseen = []\n"
        "for _n in ('listdir', 'scandir'):\n"
        "    def _w(p='.', _f=getattr(os, _n)):\n"
        "        seen.append(str(p)); return _f(p)\n"
        "    setattr(os, _n, _w)\n")
found = [probe(teh.make_env(I1s.root, SEESTAR_VOLUME=sv, ASTRO_DRIVE_ROOTS=None),
               "print(json.dumps({'vol': m.seestar_volume(), 'seen': seen}))", before=wrap)
         for sv in (os.path.join(I1s.root, "no-seestar-here"), None)]
check("I1 Seestar discovery under a test never lists /Volumes and finds no camera",
      all("seen" in x and x["vol"] is None
          and not any(p.replace("\\", "/").startswith("/Volumes") for p in x["seen"])
          for x in found), json.dumps(found)[:400])

# a ledger row pointing outside the root (camera- or ledger-made paths are not
# config, so the start guard can't see them): the operation stops before it
I1c = teh.Env("I1conf", asiair=False, seestar=True)
day1 = os.path.join(I1c.sdest30, "M 8 - Lagoon Nebula", "M 8_sub Day 1")
day3 = os.path.join(tempfile.mkdtemp(prefix="v2test-I1-outside-"), "M 8_sub Day 3")
os.makedirs(day1); os.makedirs(day3); os.makedirs(I1c.state)
teh.make_seestar_fits(os.path.join(day1, "20260817-205403.fit"), uniq="in-the-root")
stray = os.path.join(day3, "20260817-205843.fit")
teh.make_seestar_fits(stray, uniq="outside-the-root")
stray_bytes = open(stray, "rb").read()
with open(os.path.join(I1c.state, "ledger.json"), "w") as f:
    json.dump({"version": 1, "calibration": {}, "files": {
        f"MyWorks/M 8_sub/{os.path.basename(p)}": {
            "target": "M 8", "filename": os.path.basename(p), "dest": os.path.dirname(p),
            "dayNumber": n, "device": "seestar", "sourceType": "sub"}
        for p, n in ((os.path.join(day1, "20260817-205403.fit"), 1), (stray, 3))}}, f)
r = I1c.run("--merge-days", "M 8", "1", "3")
check("I1 --merge-days on a ledger row outside the test root stops (exit 3), that file untouched",
      r.returncode == 3 and "TEST MODE:" in r.stdout + r.stderr and os.path.isfile(stray)
      and open(stray, "rb").read() == stray_bytes and os.listdir(day1) == ["20260817-205403.fit"],
      f"rc={r.returncode} " + (r.stdout + r.stderr)[-300:])
r = I1c.run("--renumber-day", "M 8", "3", "2")
check("I1 --renumber-day on a ledger row outside the test root stops (exit 3), that folder untouched",
      r.returncode == 3 and "TEST MODE:" in r.stdout + r.stderr and os.path.isfile(stray)
      and not os.path.exists(os.path.join(os.path.dirname(day3), "M 8_sub Day 2")),
      f"rc={r.returncode} " + (r.stdout + r.stderr)[-300:])

# a Seestar in the root whose MyWorks is a link out of it: the SAFE clear and
# discard judge where the deletes would really land, and stop before any
I1l = teh.Env("I1link", asiair=False, seestar=False)
card = tempfile.mkdtemp(prefix="v2test-I1-outside-")
os.makedirs(os.path.join(card, "MyWorks"))
os.makedirs(I1l.svol)
try:
    os.symlink(os.path.join(card, "MyWorks"), I1l.myworks, target_is_directory=True)
except (OSError, NotImplementedError):
    I1l = None
if I1l is None:
    skip("I1 a MyWorks linked out of the root (this account can't make symlinks)")
else:
    s20_seed_ledger(I1l)
    subs = [I1l.add_seestar_sub("M 42", st, creator="Seestar S50 Pro")
            for st in ("20260905-210000", "20260905-210500")]
    r = I1l.run("--no-ship", stdin="y\ny\ny\n", extra_env={"ASTRO_STDIN_PROMPTS": "1"})
    out = r.stdout + r.stderr
    check("I1 the SAFE clear of a MyWorks linked out of the root stops (exit 3), the files there stay",
          r.returncode == 3 and "the SAFE clear would touch" in out
          and all(os.path.isfile(p) for p in subs), f"rc={r.returncode} {out[-300:]}")
    r = I1l.run("--discard", "M 42_sub")
    out = r.stdout + r.stderr
    check("I1 ...and so does --discard of it (exit 3), nothing deleted",
          r.returncode == 3 and "--discard would touch" in out
          and all(os.path.isfile(p) for p in subs), f"rc={r.returncode} {out[-300:]}")

# the self-test and the watcher never touch the real panel's port under a test
I1t = teh.Env("I1port", asiair=False, seestar=False)
for port, why in (("8765", ""), ("abc", ", and a port that isn't a number means 8765, no crash")):
    r = irun(teh.make_env(I1t.root, ASTRO_PANEL_PORT=port), script=os.path.join(HERE, "selftest.py"))
    check(f"I1 the install check under a test skips the panel on 8765 (never connects){why}",
          re.search(r"SKIP\s+panel\b.*TEST MODE", r.stdout) is not None
          and "127.0.0.1:8765" not in r.stdout, r.stdout[-400:] + r.stderr[-200:])
    r = irun(teh.make_env(I1t.root, ASTRO_PANEL_PORT=port), "--once",
             script=os.path.join(HERE, "astro-watch.py"))
    check(f"I1 the watcher under a test refuses port 8765 (exit 3){why}",
          r.returncode == 3 and "TEST MODE:" in r.stdout + r.stderr,
          f"rc={r.returncode} " + (r.stdout + r.stderr)[-300:])

# the watcher's own gates, in-process (the suites only ever run --once):
# Popen and webbrowser are stand-ins that fail the check if they are reached
I1w = teh.Env("I1watch", asiair=False, seestar=False)
e = dict(I1w.env)
e["PATH"] = teh.fake_os_commands(I1w.root) + os.pathsep + e["PATH"]
WATCH_PROBE = """
import ctypes, types
spec = importlib.util.spec_from_file_location(
    'watch', os.path.join(os.path.dirname(sys.argv[1]), 'astro-watch.py'))
w = importlib.util.module_from_spec(spec); spec.loader.exec_module(w)
ran, out = [], {}
def _popen(*a, **k):
    ran.append('Popen'); raise RuntimeError('a process was started')
w.subprocess = types.SimpleNamespace(Popen=_popen)
w.webbrowser = types.SimpleNamespace(open=lambda url: ran.append('webbrowser'))
try:
    out['start'] = w.start_panel()
except Exception as x:
    out['start'] = repr(x)
w.panel_up = lambda: True             # as if the panel were up: on to the browser
try:
    w.on_arrival({'Seestar': os.path.join(m.TEST_ROOT, 'Seestar')}, {}, open_browser=True)
except Exception as x:
    out['arrival'] = repr(x)
touched = []
class _Ctypes:
    def __getattr__(self, n):
        touched.append(n); raise AttributeError(n)
sys.modules['ctypes'] = _Ctypes()
os.makedirs(os.path.dirname(w.STATE_PATH), exist_ok=True)
was, w.eng.IS_WINDOWS = w.eng.IS_WINDOWS, True
try:
    out['single'] = w.single_instance()
finally:
    w.eng.IS_WINDOWS = was
    sys.modules['ctypes'] = ctypes
try:
    out['pid'] = open(w.STATE_PATH + '.pid').read().strip() == str(os.getpid())
except OSError:
    out['pid'] = False
out.update(ran=ran, ctypes=touched)
print(json.dumps(out))
"""
got = probe(e, WATCH_PROBE)
calls = teh.os_calls(I1w.root)
def kinds(k):
    return sum(c.get("kind") == k for c in calls)
check("I1 watcher start_panel() under a test records panel-start and starts nothing",
      got.get("start") is False and kinds("panel-start") == 1 and "Popen" not in (got.get("ran") or []),
      json.dumps(got)[:300])
check("I1 watcher on_arrival() records the notification and the browser, opens nothing",
      "arrival" not in got and kinds("notify") == 1 and kinds("browser") == 1
      and "webbrowser" not in (got.get("ran") or []), json.dumps(got)[:300] + json.dumps(calls)[:200])
check("I1 watcher single_instance() under a test, Windows forced: the pid file, never the mutex",
      got.get("single") is True and got.get("pid") is True and got.get("ctypes") == [],
      json.dumps(got)[:300])
if os.name == "nt":
    skip("I1 ...and the watcher ran no fake OS command (Windows runs no shell scripts)")
else:
    check("I1 ...and the watcher ran no OS command (the fake ones stayed silent)",
          not teh.executed(I1w.root), teh.executed(I1w.root)[-300:])

# no test mounts volumes or makes drive letters: cameras are temp folders
# only. The whole text of each test file is scanned, on both OSes' commands
# (each name is split here, so this list never matches itself).
NO_MOUNT = re.compile("|".join((
    "hdi" "util", "mount" "_smbfs", r"\bmount" " ", "disk" "util", r"\bsub" r"st\b",
    "disk" "part", "mount" "vol", "Mount-" "DiskImage", "Mount-" "VHD", "New-" "VHD",
    "New-" "PSDrive", r"\bnet\s+" r"use\b")), re.IGNORECASE)
# the one allowed mention: the helper that makes the harmless stand-in
# (it only writes <root>/EXECUTED)
NO_MOUNT_OK = {("test_env_helper.py",
                'for name in ("osascript", "disk' 'util", "open", "browser"):')}
hits = []
for name in ("test_v2.py", "test_app.py", "test_env_helper.py"):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        hits += [f"{name}:{n}: {ln.strip()[:80]}" for n, ln in enumerate(f, 1)
                 if NO_MOUNT.search(ln) and (name, ln.strip()) not in NO_MOUNT_OK]
check("I1 no test file names a command that mounts a disk or makes a drive letter",
      not hits, str(hits))

# ═══════════════ CHAIN U: what the FITs Importer App needs (1.5.3) ═══════════
print("\n── Chain U: what the FITs Importer App needs from the web version (1.5.3) ──")
# The app (app repo, PLAN.md "Upstream first") runs this same engine, panel and
# watcher. Every check here fails on 1.5.2; where only part of a check is new,
# the rest keeps it honest (a watcher that always stood aside would pass alone).
HERE_WORDS = "this PC" if os.name == "nt" else "the Mac"      # the status line's
HERE_MACHINE = "PC" if os.name == "nt" else "Mac"

def upr(env, code, before=""):
    """probe(), but a watcher that never returns is a failed check, not a hang."""
    try:
        return probe(env, code, before)
    except subprocess.TimeoutExpired:
        return {"error": "timed out"}

def owner_record(env, app_path, owner="app", path=None):
    """The app's owner record (only the app writes it; here the test does)."""
    os.makedirs(env.state, exist_ok=True)
    with open(path or os.path.join(env.state, "app-takeover.json"), "w", encoding="utf-8") as f:
        json.dump({"owner": owner, "appPath": app_path, "appVersion": "0.1.0",
                   "engine": "1.5.3", "at": "2026-09-26T101500", "steps": []}, f)

def the_app(env):
    """The app in this root, on disk; and where a trashed one used to be."""
    p = os.path.join(env.root, "Applications", "BrettjoAstro FITs Importer.app")
    os.makedirs(p, exist_ok=True)
    return p, os.path.join(env.root, "Trash", "BrettjoAstro FITs Importer.app")

def hold_lock(env, what="import"):
    """import.lock held by a live process (this runner)."""
    os.makedirs(env.state, exist_ok=True)
    p = os.path.join(env.state, "import.lock")
    with open(p, "w") as f:
        json.dump({"pid": os.getpid(), "started": time.strftime("%Y-%m-%dT%H%M%S"), "what": what}, f)
    return p

# U1 — the owner record: --app-owner answers the installers, watchers and app
U1 = teh.Env("U1", asiair=False, seestar=False)
OWNER = os.path.join(U1.state, "app-takeover.json")
U1_APP, U1_GONE = the_app(U1)

def app_owner(*extra, flags=(), cwd=None):
    r = subprocess.run([sys.executable, *flags, SCRIPT, "--app-owner", *extra], env=U1.env,
                       input="", capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=120, cwd=cwd)
    return r.returncode, r.stdout.strip()

def handed_back():
    return sorted(f for f in os.listdir(U1.state) if f.startswith("app-takeover.handed-back-"))

os.makedirs(U1.state)
got = app_owner()
check("U1 --app-owner with no record: 'web', exit 1", got == (1, "web"), str(got))
owner_record(U1, U1_APP)
lock = hold_lock(U1)
got = app_owner(flags=("-S",))                  # -S: no site-packages, so no astropy
check("U1 ...the app's record, its app on disk: 'app <path>', exit 0 (a lock held, no astropy)",
      got == (0, f"app {U1_APP}") and os.path.isfile(lock), str(got))
os.remove(lock)
owner_record(U1, U1_GONE)
got = app_owner()
check("U1 ...its app gone (trashed without handing back): 'stale <path>', exit 2",
      got == (2, f"stale {U1_GONE}"), str(got))
with open(OWNER, "w") as f:
    f.write('{"owner": "app", "appPath": ')                # cut short
bad = app_owner()
owner_record(U1, U1_APP, owner="web")
other = app_owner()
check("U1 ...an unreadable record, or one not owned by 'app', means 'web', exit 1",
      bad == (1, "web") and other == (1, "web"), str([bad, other]))
# an appPath that isn't absolute means 'web' wherever it is asked from: the
# installer (run from the home folder) and the watcher (run from /) never
# disagree. Asked from the root, where the relative app path exists:
rel = os.path.relpath(U1_APP, U1.root)
got_rel = []
for p in (rel, ".", os.path.join("Trash", "gone.app")):
    owner_record(U1, p)
    got_rel.append(app_owner(cwd=U1.root))
check("U1 ...an appPath that isn't absolute (an existing relative one, '.', a missing one) "
      "means 'web', exit 1: never app or stale",
      os.path.isdir(os.path.join(U1.root, rel)) and got_rel == [(1, "web")] * 3, str(got_rel))
owner_record(U1, U1_GONE)
stale_bytes = open(OWNER, "rb").read()
got = app_owner("--archive-stale")
named = re.fullmatch(r"archived (app-takeover\.handed-back-[^\\/]+\.json)", got[1])
kept = os.path.join(U1.state, named.group(1)) if named else ""
after = app_owner()
check("U1 --app-owner --archive-stale renames a stale record aside, exit 0 (never deleted), then 'web'",
      got[0] == 0 and named is not None and handed_back() == [named.group(1)]
      and not os.path.exists(OWNER) and open(kept, "rb").read() == stale_bytes
      and after == (1, "web"), str([got, after, sorted(os.listdir(U1.state))]))
owner_record(U1, U1_APP)
got = app_owner("--archive-stale")
still = os.path.isfile(OWNER)
os.remove(OWNER)
none = app_owner("--archive-stale")
check("U1 ...and is plain --app-owner otherwise: the app's own record is never archived",
      got == (0, f"app {U1_APP}") and still and none == (1, "web") and len(handed_back()) == 1,
      str([got, none, handed_back()]))

# the watcher, in-process in test mode, run through main() with time.sleep
# replaced: each nap runs the next step, and after the last it stops the loop
WATCH_LOOP = """
import time
spec = importlib.util.spec_from_file_location(
    'watch', os.path.join(os.path.dirname(sys.argv[1]), 'astro-watch.py'))
w = importlib.util.module_from_spec(spec); spec.loader.exec_module(w)
class Stop(BaseException):
    pass
polls = []
if hasattr(w, 'poll_once'):           # main() is the loop around poll_once (U4)
    def _spy(*a, _poll=w.poll_once, **k):
        polls.append(1)
        return _poll(*a, **k)
    w.poll_once = _spy
w.panel_up = lambda: True             # as if the panel were up: on to the notification
def _nap(s):
    if not STEPS:
        raise Stop()
    STEPS.pop(0)()
time.sleep = _nap
sys.argv = ['astro-watch.py']
try:
    out = {'rc': w.main()}
except Stop:
    out = {'rc': 'still polling'}
out['polls'] = len(polls)
print(json.dumps(out))
"""

def acted(env):
    return {k: len(teh.os_calls(env.root, k)) for k in ("notify", "browser", "panel-start")}

def watch_log(env):
    try:
        with open(os.path.join(env.state, "Logs", "astro-watch.log"), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""

U1wa = teh.Env("U1wapp")                                # a camera is plugged in
owner_record(U1wa, the_app(U1wa)[0])
got_a = upr(U1wa.env, WATCH_LOOP, before="STEPS = []\n")
U1ws = teh.Env("U1wstale")
owner_record(U1ws, the_app(U1ws)[1])
got_s = upr(U1ws.env, WATCH_LOOP, before="STEPS = []\n")
check("U1 the watcher exits 0 and does nothing while the app owns the machine (one log line); "
      "on a stale record it acts as before",
      got_a.get("rc") == 0 and "in charge" in watch_log(U1wa)
      and acted(U1wa) == {"notify": 0, "browser": 0, "panel-start": 0}
      and got_s.get("rc") == "still polling" and acted(U1ws)["notify"] == 1
      and acted(U1ws)["browser"] == 1,
      json.dumps([got_a, acted(U1wa), got_s, acted(U1ws)]) + watch_log(U1wa)[-200:])
# the app takes over while the watcher runs: the next arrival is left alone
U1wb = teh.Env("U1wlate", asiair=False)
staged = os.path.join(U1wb.root, "app-takeover.staged.json")
owner_record(U1wb, the_app(U1wb)[0], path=staged)
got_b = upr(U1wb.env, WATCH_LOOP, before=(
    f"STEPS = [lambda: (os.replace({staged!r}, "
    f"{os.path.join(U1wb.state, 'app-takeover.json')!r}), os.makedirs({U1wb.cam!r}))]\n"))
check("U1 ...and an arrival after the app took over is left alone (no panel, notification or browser)",
      got_b.get("rc") in (0, "still polling") and not os.path.exists(staged)
      and acted(U1wb) == {"notify": 0, "browser": 0, "panel-start": 0},
      json.dumps([got_b, acted(U1wb)]) + watch_log(U1wb)[-200:])

# the install check names the owner, and WARNs when both would run
U1t = teh.Env("U1self", asiair=False, seestar=False)
os.makedirs(U1t.state)
set_to_start = (   # the web watcher's autostart: the Mac's LaunchAgent, the PC's Startup shortcut
    os.path.join(U1t.root, "home", "Library", "LaunchAgents", "com.brettjohnson.astro-import.plist"),
    os.path.join(U1t.env["APPDATA"], "Microsoft", "Windows", "Start Menu", "Programs", "Startup",
                 "BrettjoAstro FITS Importer watcher.lnk"))

def selftest():
    r = irun(U1t.env, script=os.path.join(HERE, "selftest.py"))
    return r.stdout + r.stderr

def warns(out, word=""):
    return [ln.strip() for ln in out.splitlines()
            if ln.strip().startswith("WARN") and word in ln.lower()]

out_web = selftest()
t_app, t_gone = the_app(U1t)
owner_record(U1t, t_app)
out_off = selftest()
for p in set_to_start:
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w").close()
out_on = selftest()
owner_record(U1t, t_gone)
out_stale = selftest()
check("U1 the install check names the owner: 'web version' with no record",
      "web version" in out_web, out_web[-600:])
check("U1 ...'FITs Importer App (<path>)' when the app owns it, and WARNs only while "
      "the web watcher is still set to start",
      f"FITs Importer App ({t_app})" in out_off and not warns(out_off, "watcher")
      and warns(out_on, "watcher"), str(warns(out_off) + warns(out_on)) + out_off[-400:])
check("U1 ...and no Restart-button WARN while the app owns it (the installer leaves the "
      "button out then); with no record the WARN stays",
      not warns(out_off, "restart") and not warns(out_on, "restart")
      and warns(out_web, "restart"), str(warns(out_off) + warns(out_web)))
check("U1 ...a stale record is a WARN, with the fix",
      any("run the web installer, or reinstall the app" in ln for ln in warns(out_stale)),
      str(warns(out_stale)) + out_stale[-400:])

# The scripts' own owner checks. Tests never run the installers, the Restart
# buttons, astro-watch.sh or the launcher: each script marks its owner check
# ("# >>> app-owner check" ... "# <<< app-owner check"; "rem app-owner check:
# begin/end" in the Windows Restart .cmd), and only that block runs here, in
# a temp script with every path in a test root, launchctl and "open" stubbed,
# and a fake engine answering as the app, a stale record, the web version, a
# crash, or an engine too old to know --app-owner (exit 2, usage on stderr).
U1g = teh.Env("U1gate", asiair=False, seestar=False)
G_BIN = os.path.join(U1g.root, "home", "bin")                # ~/bin, the web version's
G_WINBIN = os.path.join(U1g.env["LOCALAPPDATA"], "BrettjoAstro", "bin")
G_APP = os.path.join(U1g.root, "Applications", "BrettjoAstro FITs Importer.app")
G_CALLS = os.path.join(U1g.root, "engine-calls.jsonl")
G_LAUNCHCTL = os.path.join(U1g.root, "launchctl.log")
G_STUBS = os.path.join(U1g.root, "stubs")
FAKE_ENGINE = '''import json, os, sys
with open(os.environ["FAKE_CALLS"], "a", encoding="utf-8") as f:
    f.write(json.dumps(sys.argv[1:]) + "\\n")
mode, app = os.environ["FAKE_OWNER"], os.environ["FAKE_APP"]
if mode == "crash":
    raise RuntimeError("the engine crashed")
if mode == "old":                        # 1.5.2's engine: no --app-owner at all
    sys.stderr.write("usage: astro-import.py [-h] ...\\n"
                     "astro-import.py: error: unrecognized arguments: --app-owner\\n")
    sys.exit(2)
if mode == "app":
    print("app " + app)
    sys.exit(0)
if mode == "stale":
    if "--archive-stale" in sys.argv:
        print("archived app-takeover.handed-back-20260926T120000.json")
        sys.exit(0)
    print("stale " + app)
    sys.exit(2)
print("web")
sys.exit(1)
'''
for d in (G_BIN, G_WINBIN, G_STUBS, G_APP):
    os.makedirs(d, exist_ok=True)
for d in (G_BIN, G_WINBIN):
    with open(os.path.join(d, "astro-import.py"), "w", encoding="utf-8") as f:
        f.write(FAKE_ENGINE)
with open(os.path.join(G_STUBS, "launchctl"), "w") as f:
    f.write(f'#!/bin/sh\necho "$*" >> "{G_LAUNCHCTL}"\n')
os.chmod(os.path.join(G_STUBS, "launchctl"), 0o755)
OWNER_MODES = ("app", "stale", "web", "crash", "old")

def owner_block(path, begin="# >>> app-owner check", end="# <<< app-owner check"):
    """The lines between a script's owner-check markers (None if not exactly one block)."""
    with open(path, encoding="utf-8-sig") as f:
        lines = f.read().splitlines()
    a = [i for i, ln in enumerate(lines) if ln.strip().startswith(begin)]
    b = [i for i, ln in enumerate(lines) if ln.strip().startswith(end)]
    if len(a) != 1 or len(b) != 1 or b[0] <= a[0] + 1:
        return None
    return lines[a[0] + 1:b[0]]

def gate_env(mode):
    for p in (G_CALLS, G_LAUNCHCTL):
        if os.path.exists(p):
            os.remove(p)
    return dict(U1g.env, FAKE_OWNER=mode, FAKE_CALLS=G_CALLS, FAKE_APP=G_APP,
                PATH=G_STUBS + os.pathsep + teh.fake_os_commands(U1g.root)
                + os.pathsep + U1g.env["PATH"])

def gate_calls():
    """The fake engine's calls (argv lists) and launchctl's, since gate_env()."""
    calls = []
    if os.path.exists(G_CALLS):
        with open(G_CALLS, encoding="utf-8") as f:
            calls = [json.loads(ln) for ln in f if ln.strip()]
    lc = open(G_LAUNCHCTL).read().split("\n") if os.path.exists(G_LAUNCHCTL) else []
    return calls, [x for x in lc if x]

shq = lambda p: "'" + p.replace("'", "'\\''") + "'"         # a bash single-quoted word
BASH_GATES = {   # script: (what the block needs set first, what it prints after)
    "install-scripts.sh": (
        "set -euo pipefail\n"
        'info() { echo "INFO $1"; }; success() { echo "OK $1"; }; warn() { echo "WARN $1"; }\n'
        f"BIN_DIR={shq(G_BIN)}\nPYCHECK={shq(sys.executable)}\n",
        'echo "DECISION APP_OWNS=[$APP_OWNS]"\n'),
    "astro-watch.sh": (
        'wlog() { echo "LOG $1"; }\n'
        f"PYTHON={shq(sys.executable)}\nIMPORT_SCRIPT={shq(os.path.join(G_BIN, 'astro-import.py'))}\n",
        'echo "DECISION normal"\n'),
    "Restart FITS Importer.command": (
        f"PYTHON={shq(sys.executable)}\n", 'echo "DECISION normal"\n'),
    os.path.join("BrettjoAstro FITS Importer.app", "Contents", "MacOS", "launcher"): (
        'open() { echo "OPEN $*"; }\n'                  # never the real open
        f"PYTHON={shq(sys.executable)}\n", 'echo "DECISION normal"\n'),
}

def bash_decision(name, rc, out):
    calls, lc = gate_calls()
    archived = ["--app-owner", "--archive-stale"] in calls
    enabled = any(x.startswith("enable gui/") and x.endswith("/com.brettjohnson.astro-import")
                  for x in lc)
    if name == "install-scripts.sh":
        m = re.search(r"^DECISION APP_OWNS=\[(.*)\]$", out, re.M)
        if rc != 0 or not m:
            return f"broken (rc={rc})"
        if m.group(1):
            return "skip web setup" if m.group(1) == G_APP and not archived and not lc \
                else f"skip web setup?? {m.group(1)} {archived} {lc}"
        if archived and enabled and len(lc) == 1:
            return "archive+enable"
        return "normal" if not archived and not lc else f"normal?? {archived} {lc}"
    if "DECISION normal" in out:
        return "normal" if "OPEN" not in out else "normal??"
    if rc != 0:
        return f"broken (rc={rc})"
    if name.endswith("launcher"):
        return "open the app" if f"OPEN -a {G_APP}" in out else "stand aside??"
    return "stand aside"

if os.name == "nt" or not shutil.which("bash"):
    for name in BASH_GATES:
        skip(f"U1 {os.path.basename(name)}'s owner check (no bash here)")
else:
    for name, (pre, post) in BASH_GATES.items():
        block = owner_block(os.path.join(HERE, name))
        want = {"app": "open the app" if name.endswith("launcher") else
                ("skip web setup" if name == "install-scripts.sh" else "stand aside"),
                "stale": "archive+enable" if name == "install-scripts.sh" else "normal",
                "web": "normal", "crash": "normal", "old": "normal"}
        got = {}
        if block is not None:
            path = os.path.join(U1g.root, "block-" + os.path.basename(name).replace(" ", "-") + ".sh")
            with open(path, "w", encoding="utf-8") as f:
                f.write("#!/bin/bash\n" + pre + "\n".join(block) + "\n" + post)
            for mode in OWNER_MODES:
                r = subprocess.run(["bash", path], env=gate_env(mode), cwd=U1g.root,
                                   stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                   encoding="utf-8", errors="replace", timeout=60)
                got[mode] = bash_decision(name, r.returncode, r.stdout)
        check(f"U1 {os.path.basename(name)}'s own owner check, run on its own: app → "
              f"{want['app']}; stale → {want['stale']}; web, a crash or an old engine → normal",
              got == want, json.dumps(got) if block is not None else "no marked block")

# The Windows installer's owner check and the Restart .cmd it writes: the same,
# through powershell.exe and cmd.exe (Windows only: they can't run here)
with open(os.path.join(HERE, "install-windows.ps1"), encoding="utf-8-sig") as f:
    PS_TEXT = f.read()
CMD_BLOCK = owner_block(os.path.join(HERE, "install-windows.ps1"),
                        begin="rem app-owner check: begin", end="rem app-owner check: end")
cmd_exit = [ln.strip().lower() for ln in (CMD_BLOCK or [])]
check("U1 the Restart .cmd's owner check waits before it closes (its message can be read)",
      "exit /b 0" in cmd_exit and any(ln.startswith("timeout /t ") for ln in
                                      cmd_exit[:cmd_exit.index("exit /b 0")]),
      str(CMD_BLOCK))
if os.name != "nt":
    skip("U1 install-windows.ps1's owner check through powershell.exe (Windows only)")
    skip("U1 the Restart .cmd's owner check through cmd.exe (Windows only)")
else:
    SYSROOT = os.environ.get("SYSTEMROOT") or r"C:\Windows"
    POWERSHELL = os.path.join(SYSROOT, "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
    POWERSHELL = POWERSHELL if os.path.isfile(POWERSHELL) else "powershell.exe"
    CMD = os.environ.get("COMSPEC") or "cmd.exe"
    ps_block = owner_block(os.path.join(HERE, "install-windows.ps1"))
    got = {}
    if ps_block is not None:
        path = os.path.join(U1g.root, "block-install-windows.ps1")
        psq = lambda p: "'" + p.replace("'", "''") + "'"
        with open(path, "w", encoding="utf-8-sig", newline="\r\n") as f:
            f.write("$ErrorActionPreference = 'Continue'\n"
                    "[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false\n"
                    'function Ok($m)   { Write-Output "OK $m" }\n'
                    'function Info($m) { Write-Output "INFO $m" }\n'
                    'function Warn($m) { Write-Output "WARN $m" }\n'
                    f"$py = {psq(sys.executable)}\n$bin = {psq(G_WINBIN)}\n"
                    + "\n".join(ps_block) + '\nWrite-Output "DECISION appOwns=$appOwns"\n')
        for mode in OWNER_MODES:
            r = subprocess.run([POWERSHELL, "-NoProfile", "-NonInteractive",
                                "-ExecutionPolicy", "Bypass", "-File", path],
                               env=gate_env(mode), cwd=U1g.root, stdin=subprocess.DEVNULL,
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=120)
            calls, _ = gate_calls()
            archived = ["--app-owner", "--archive-stale"] in calls
            if "DECISION appOwns=True" in r.stdout:
                got[mode] = "skip web setup" if not archived else "skip web setup??"
            elif "DECISION appOwns=False" in r.stdout:
                got[mode] = "archive" if archived else "normal"
            else:
                got[mode] = f"broken (rc={r.returncode}) {(r.stdout + r.stderr)[-200:]}"
    check("U1 install-windows.ps1's own owner check, run on its own: app → skip web setup; "
          "stale → archive; web, a crash or an old engine → normal",
          got == {"app": "skip web setup", "stale": "archive", "web": "normal",
                  "crash": "normal", "old": "normal"},
          json.dumps(got) if ps_block is not None else "no marked block")
    got = {}
    if CMD_BLOCK is not None:
        path = os.path.join(U1g.root, "block-restart.cmd")
        # the installer's here-string fills in $py; nothing else in the block is PowerShell's
        text = "\n".join(CMD_BLOCK).replace('"$py"', f'"{sys.executable}"')
        with open(path, "w", encoding="oem", errors="replace", newline="\r\n") as f:
            f.write("@echo off\n" + text + "\necho DECISION normal\n")
        for mode in OWNER_MODES:
            r = subprocess.run([CMD, "/d", "/c", path], env=gate_env(mode), cwd=U1g.root,
                               stdin=subprocess.DEVNULL, capture_output=True, text=True,
                               encoding="oem", errors="replace", timeout=120)
            if "DECISION normal" in r.stdout:
                got[mode] = "normal"
            elif "in charge here" in r.stdout:
                got[mode] = "stand aside"
            else:
                got[mode] = f"broken (rc={r.returncode}) {(r.stdout + r.stderr)[-200:]}"
    check("U1 the Restart .cmd's own owner check, run on its own: app → stand aside; "
          "stale, web, a crash or an old engine → normal",
          got == {"app": "stand aside", "stale": "normal", "web": "normal",
                  "crash": "normal", "old": "normal"},
          json.dumps(got) if CMD_BLOCK is not None else "no marked block")

# ...and what the installers do with the answer: every web-only step (the
# watcher, the Restart button, stopping the panel, starting it, the first-run
# text) sits under an "only when the app isn't in charge" guard
def bash_unguarded(path, steps):
    """Lines doing one of `steps` (regexes) outside an if whose condition is
    [ -z "$APP_OWNS" ] (or the else of [ -n "$APP_OWNS" ]), or an inline guard."""
    stack, bad, heredoc = [], [], None
    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()
    for n, ln in enumerate(lines, 1):
        t = ln.strip()
        if heredoc:
            heredoc = None if t == heredoc else heredoc
            continue
        if t.startswith("#") or not t:
            continue
        m = re.search(r"<<-?\s*'?(\w+)'?", t)
        if m:
            heredoc = m.group(1)
        if t.startswith("if "):
            stack.append([t, False])
        elif t.startswith("elif "):
            stack[-1] = [t, False]
        elif (t == "else" or t.startswith("else ")) and stack:
            stack[-1][1] = True
        guarded = any(('-z "$APP_OWNS"' in c and not e) or ('-n "$APP_OWNS"' in c and e)
                      for c, e in stack)
        for rx in steps:
            hit = re.search(rx, ln)
            if hit and not guarded and '-z "$APP_OWNS"' not in ln[:hit.start()]:
                bad.append(f"{n}: {t[:70]}")
        if re.search(r"(^|[;\s])fi$", t) and stack:
            stack.pop()
    return bad

def ps_unguarded(text, steps):
    """The same for PowerShell: outside a { } block whose header says -not $appOwns
    (here-string bodies are the .cmd's text, not code)."""
    stack, bad, here = [], [], False
    for n, ln in enumerate(text.splitlines(), 1):
        t = ln.strip()
        if here:
            here = not t.startswith('"@')
            continue
        if t.startswith("#"):
            continue
        for rx in steps:
            if re.search(rx, ln) and not any("-not $appOwns" in h for h in stack):
                bad.append(f"{n}: {t[:70]}")
        for i, ch in enumerate(ln):
            if ch == "{":
                stack.append(ln[:i])
            elif ch == "}" and stack:
                stack.pop()
        if t.endswith('@"'):
            here = True
    return bad

mac_bad = bash_unguarded(os.path.join(HERE, "install-scripts.sh"), (
    r'cp "\$SCRIPT_DIR/Restart FITS Importer\.command"', r"\bpkill\b",
    r'launchctl load "\$new_plist"', r'log "First run:"'))
win_bad = ps_unguarded(PS_TEXT, (
    r"\$lnk\.Save\(\)", r"WriteAllText\(\(Join-Path \$desktop", r"\bStop-Process\b",
    r"Start-Process -FilePath \$pyw", r"Start-Process 'http", r'Write-Host "Next:"'))
with open(os.path.join(HERE, "install-scripts.sh"), encoding="utf-8") as f:
    SH_TEXT = f.read()
check("U1 while the app is in charge, the installers only update files: the watcher, the "
      "Restart button, the panel stop and start, and the first-run text are all guarded "
      "(one line says to open the app instead)",
      not mac_bad and not win_bad and "Open the FITs Importer App" in PS_TEXT
      and "Open the FITs Importer App" in SH_TEXT, str(mac_bad + win_bad))

# U2 — every kill pattern matches only the web version's own files. The Mac's
# are real patterns (pkill -f is an extended regex on the whole command line):
# fill in $HOME and the script's own variables, and try them on command lines
U2_HOME = "/Users/brett"
U2_WEB = [f"/usr/local/bin/python3 {U2_HOME}/bin/astro-app.py --no-browser",
          "/Library/Frameworks/Python.framework/Versions/3.12/Resources/Python.app/"
          f"Contents/MacOS/Python {U2_HOME}/bin/astro-app.py --no-browser"]
U2_OLD = f"/usr/local/bin/python3 {U2_HOME}/bin/asiair-app.py"      # the old panel name
U2_NOT = [  # the app's own Python, its own copies, a source folder, an editor (V9)
    "/Applications/BrettjoAstro FITs Importer.app/Contents/Resources/python/bin/python3 "
    "/Applications/BrettjoAstro FITs Importer.app/Contents/Resources/app/astro-app.py",
    "/Applications/BrettjoAstro FITs Importer.app/Contents/MacOS/python3 "
    f"{U2_HOME}/Library/Application Support/BrettjoAstro FITs Importer App/bin/astro-app.py",
    f"/usr/local/bin/python3 {U2_HOME}/Code/brettjoastro-fits-importer/astro-app.py --port 50123",
    f"vim {U2_HOME}/bin/astro-app.py"]

def kill_patterns(path):
    """Every pkill/pgrep -f pattern in a shell script, its variables filled in."""
    vals = {"HOME": U2_HOME}
    def fill(s):
        return re.sub(r"\$\{?([A-Za-z_]\w*)\}?", lambda v: vals.get(v.group(1), v.group(0)), s)
    pats = []
    with open(path, encoding="utf-8") as f:
        for ln in f:
            if ln.lstrip().startswith("#"):
                continue
            a = re.match(r"\s*(?:export\s+|local\s+)?([A-Za-z_]\w*)="
                         r"(?:\"([^\"]*)\"|'([^']*)'|([^\s;]*))", ln)
            if a:
                vals[a.group(1)] = a.group(3) if a.group(3) is not None \
                    else fill(a.group(2) if a.group(2) is not None else a.group(4))
            for k in re.finditer(r"\b(?:pkill|pgrep)\b(?:\s+-\w+)*?\s+-f\s+(?:--\s+)?"
                                 r"(?:\"([^\"]*)\"|'([^']*)'|(\S+))", ln):
                pats.append(k.group(2) if k.group(2) is not None
                            else fill(k.group(1) if k.group(1) is not None else k.group(3)))
    return pats

u2 = {n: kill_patterns(os.path.join(HERE, n)) for n in (
    "install-scripts.sh", "Restart FITS Importer.command", "astro-watch.sh",
    os.path.join("BrettjoAstro FITS Importer.app", "Contents", "MacOS", "launcher"))}
bad = []
for n, pats in u2.items():
    for p in pats:
        try:
            rx = re.compile(p)
        except re.error as x:
            bad.append(f"{n}: {p!r} ({x})")
            continue
        need = U2_WEB + ([U2_OLD] if n == "install-scripts.sh" else [])
        miss = [c for c in need if not rx.search(c)]
        hit = [c for c in U2_NOT if rx.search(c)]
        if miss or hit:
            bad.append(f"{n}: {p!r} misses {miss} / matches {hit}")
check("U2 the Mac kill patterns (installer, Restart .command) match only ~/bin's panel: "
      "never the app's own Python, a source folder or an editor",
      u2["install-scripts.sh"] and u2["Restart FITS Importer.command"] and not bad,
      str(bad or u2))
# Windows: no pwsh here, so the filter lines are read: each names the web bin
with open(os.path.join(HERE, "install-windows.ps1"), encoding="utf-8-sig") as f:
    ps_filters = [ln.strip() for ln in f.read().splitlines() if "CommandLine" in ln]
bare = [ln for ln in ps_filters
        if "astro-" not in ln or not re.search(r"BrettjoAstro\\{1,2}bin|\$bin\b", ln)]
check("U2 the Windows kill filters (installer and its Restart .cmd) name "
      "%LOCALAPPDATA%\\BrettjoAstro\\bin: no bare astro-app.py match left",
      len(ps_filters) >= 2 and not bare, str(bare or ps_filters))

# U3 — a ledger from a newer version is never written by this one
U3 = Env("U3")
U3.add_light("Plan", "M 81", "0001", dt="20260720-221000")
os.makedirs(U3.state)
u3_ledger = os.path.join(U3.state, "ledger.json")
newer = (json.dumps({"version": 2, "files": {}, "calibration": {}, "futureRows": {}},
                    indent=1) + "\n").encode()
with open(u3_ledger, "wb") as f:
    f.write(newer)
r = U3.run(stdin="n\n")
out = r.stdout + r.stderr
check("U3 an import refuses a ledger from a newer version (v2): exit 2, says so, "
      "the ledger byte-identical, nothing copied",
      r.returncode == 2 and "newer version of the importer" in out and "nothing was written" in out
      and open(u3_ledger, "rb").read() == newer and not os.path.exists(u3_ledger + ".bak")
      and count_fits(day_dir(U3, "M 81 - Bode's Galaxy", 1)) == 0,
      f"rc={r.returncode} {out[-300:]}")
rv, rs, ro = U3.run("--version"), U3.run("--status"), U3.run("--app-owner")
check("U3 ...while --version, --status and --app-owner still answer (status: unknown, "
      "never 'safe', for a newer ledger)",
      rv.returncode == 0 and f"FITS Importer {VERSION} (" in rv.stdout
      and (rs.returncode, rs.stdout.strip())
      == (0, "Status unknown: the ledger is from a newer version of the importer")
      and (ro.returncode, ro.stdout.strip()) == (1, "web") and open(u3_ledger, "rb").read() == newer,
      str([(x.returncode, (x.stdout + x.stderr)[-150:]) for x in (rv, rs, ro)]))

def dest_fits(env):
    return sum(1 for _d, _s, fs in os.walk(env.dest) for f in fs if f.lower().endswith(".fit"))

# ...and every path that restores or re-reads the ledger refuses a newer one
# before anything is copied, tagged or deleted: the mirror (a first run, or
# --restore-ledger), the .bak, and a ledger replaced after the first look
U3m = Env("U3mirror")
U3m.add_light("Plan", "M 81", "0001", dt="20260720-221000")
U3m.run("--baseline")
m_led = os.path.join(U3m.mirror, "ledger.json")
with open(m_led, encoding="utf-8") as f:
    mled = json.load(f)
mled["version"] = 2                                     # the app's newer ledger, mirrored
with open(m_led, "w", encoding="utf-8") as f:
    json.dump(mled, f)
with open(m_led, "rb") as f:
    m_bytes = f.read()
for n in ("ledger.json", "ledger.json.bak"):           # this Mac's own copy lost
    if os.path.exists(os.path.join(U3m.state, n)):
        os.remove(os.path.join(U3m.state, n))
u3_new = [U3m.add_light("Plan", "M 81", "0002", dt="20260721-220512"),
          U3m.add_light("Plan", "M 81", "0003", dt="20260721-221012")]

def u3_yes(env, *args):
    """A run that answers yes to everything it is asked."""
    return subprocess.run([sys.executable, SCRIPT, *args], env=dict(env.env, ASTRO_STDIN_PROMPTS="1"),
                          input="y\ny\ny\ny\n", capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=120)

r1, r2 = u3_yes(U3m, "--no-ship"), u3_yes(U3m, "--restore-ledger")
out1, out2 = r1.stdout + r1.stderr, r2.stdout + r2.stderr
check("U3 a newer importer's ledger in the mirror is never restored: a first-run import "
      "stops (exit 2) before it copies or tags anything, and --restore-ledger copies nothing",
      r1.returncode == 2 and "newer version of the importer" in out1 and dest_fits(U3m) == 0
      and "Tagging" not in out1 and all(os.path.isfile(p) for p in u3_new)
      and r2.returncode == 2 and "newer version of the importer" in out2
      and not os.path.exists(os.path.join(U3m.state, "ledger.json"))
      and open(m_led, "rb").read() == m_bytes,
      f"rc={r1.returncode}/{r2.returncode} fits={dest_fits(U3m)} {out1[-300:]} | {out2[-200:]}")
U3b = Env("U3bak")
U3b.add_light("Plan", "M 81", "0001", dt="20260720-221000")
os.makedirs(U3b.state)
with open(os.path.join(U3b.state, "ledger.json"), "w") as f:
    f.write("{not json")                                   # unreadable: the .bak is used
with open(os.path.join(U3b.state, "ledger.json.bak"), "wb") as f:
    f.write(newer)
r = u3_yes(U3b, "--no-ship")
check("U3 ...an unreadable ledger whose .bak is a newer importer's: refused (exit 2), nothing "
      "copied, both files as they were",
      r.returncode == 2 and "newer version of the importer" in r.stdout + r.stderr
      and dest_fits(U3b) == 0 and open(os.path.join(U3b.state, "ledger.json")).read() == "{not json"
      and open(os.path.join(U3b.state, "ledger.json.bak"), "rb").read() == newer,
      f"rc={r.returncode} {(r.stdout + r.stderr)[-300:]}")
# the ledger is fine at the first look, and a newer importer saves it before
# the lock is taken: re-read under the lock, it is refused again
U3r = Env("U3race")
U3r.add_light("Plan", "M 81", "0001", dt="20260720-221000")
os.makedirs(U3r.state)
got = probe(dict(U3r.env, ASTRO_STDIN_PROMPTS="1"), """
led = os.path.join(m.STATE_DIR, 'ledger.json')
v1 = json.dumps({'version': 1, 'files': {}, 'calibration': {}})
v2 = json.dumps({'version': 2, 'files': {}, 'calibration': {}})
real = m.acquire_lock
def acquire(what='import'):
    ok = real(what)
    with open(led, 'w') as f:
        f.write(v2)                        # a newer importer saved it just now
    return ok
m.acquire_lock = acquire
out = {}
for argv in (['--no-ship'], ['--ship'], ['--discard', 'M 81'], ['--skip-target', 'M 81']):
    with open(led, 'w') as f:
        f.write(v1)
    sys.argv = ['astro-import.py'] + argv
    try:
        m.main()
        out[argv[0]] = 'ran'
    except SystemExit as e:
        out[argv[0]] = e.code
out['after'] = open(led).read() == v2
print(json.dumps(out))
""")
check("U3 ...a ledger a newer importer saves after the first look is refused again under the "
      "lock (exit 2) by an import, --ship, --discard and --skip-target; nothing copied",
      got == {"--no-ship": 2, "--ship": 2, "--discard": 2, "--skip-target": 2, "after": True}
      and dest_fits(U3r) == 0, json.dumps(got)[:300] + f" fits={dest_fits(U3r)}")

# U4 — the watcher imports cleanly and polls through poll_once(), on this OS too
U4 = teh.Env("U4", asiair=False, seestar=False)
u4_drive = os.path.join(U4.root, "drives", "F")
u4_out = os.path.join(U4.root, "unplugged-F")        # a Seestar card, out of its slot
teh.make_seestar_fits(os.path.join(u4_out, "MyWorks", "M 42_sub", "20260926-210000.fit"),
                      creator="Seestar S50 Pro", uniq="u4-sub")
os.makedirs(os.path.dirname(u4_drive))
u4env = dict(U4.env, SEESTAR_VOLUME=os.path.join(U4.root, "no-seestar-volume"),
             ASTRO_DRIVE_ROOTS=u4_drive)
u4env.pop("ASIAIR_VOLUME")                           # the drive-root search, as W1
POLL_PROBE = """
def files():
    return sorted(os.path.join(d, f) for d, _s, fs in os.walk(m.TEST_ROOT) for f in fs)
before = files()
spec = importlib.util.spec_from_file_location(
    'watch', os.path.join(os.path.dirname(sys.argv[1]), 'astro-watch.py'))
w = importlib.util.module_from_spec(spec); spec.loader.exec_module(w)
out = {'quiet': files() == before}
calls = []
st = w.load_state()
def look():
    ev = w.poll_once(st, on_arrival=lambda *a, **k: calls.append(['arrival', list(a), k]),
                     on_removed=lambda *a, **k: calls.append(['removed', list(a), k]),
                     on_rearrived=lambda *a, **k: calls.append(['rearrived', list(a), k]))
    try:
        with open(w.STATE_PATH, encoding='utf-8') as f:
            saved = json.load(f)
    except (OSError, ValueError):
        saved = {}
    return [ev, len(calls), saved.get('presence'),
            [saved.get('notifiedSet'), bool(saved.get('notifiedAt'))]]
steps = [look()]
os.rename(OUT, DRIVE)
steps += [look(), look()]
os.rename(DRIVE, OUT)
steps += [look()]
os.rename(OUT, DRIVE)                 # the same card back seconds later: a loose cable
steps += [look()]
os.rename(DRIVE, OUT)
steps += [look()]
w.FLAP_GUARD_S = 0                    # the guard has run out
os.rename(OUT, DRIVE)
steps += [look()]
out.update(steps=steps, calls=calls)
print(json.dumps(out))
"""
got = upr(u4env, POLL_PROBE, before=f"OUT, DRIVE = {u4_out!r}, {u4_drive!r}\n")
steps = (got.get("steps") or []) + [[None, 0, None, None]] * 7
calls = (got.get("calls") or []) + [[None, [], {}]] * 5

def event(step):
    """A look's only event as (kind, payload), else (None, None)."""
    ev = step[0]
    if isinstance(ev, list) and len(ev) == 1 and isinstance(ev[0], list) and len(ev[0]) == 2:
        return tuple(ev[0])
    return None, None

def same(a, b):
    n = lambda p: os.path.normcase(os.path.realpath(p)).rstrip("\\/")
    return isinstance(a, str) and n(a) == n(b)

def passed(call, found):
    """Was `found` handed to this callback?"""
    return found in call[1] + list(call[2].values())

kind, found = event(steps[1])
found = found if isinstance(found, dict) else {}
check("U4 the watcher imports with no side effects (no file, no OS call); "
      "poll_once() with no camera: []",
      got.get("quiet") is True and steps[0][0] == [] and not teh.os_calls(U4.root),
      json.dumps(got)[:400])
check("U4 poll_once on a fake drive root: an arrival → [('arrived', found)], on_arrival(found), "
      "the state file saved; no change → []",
      kind == "arrived" and set(found) == {"Seestar"} and same(found.get("Seestar"), u4_drive)
      and steps[1][1] == 1 and calls[0][0] == "arrival" and passed(calls[0], found)
      and steps[1][2] not in (None, "none") and steps[2][:2] == [[], 1],
      json.dumps(got)[:400])
check("U4 ...and a removal → [('gone', previous)], on_removed(previous), saved as none",
      bool(found) and event(steps[3]) == ("gone", found) and steps[3][1] == 2
      and calls[1][0] == "removed" and passed(calls[1], found) and steps[3][2] == "none",
      json.dumps(got)[:400])
check("U4 poll_once keeps the flap guard itself (for the app too): the arrival acted on is "
      "saved with it (notifiedSet, notifiedAt) in the same save; back within FLAP_GUARD_S → "
      "[('rearrived', found)] and on_rearrived, never a second on_arrival; later, an arrival",
      bool(found) and steps[1][3] == [steps[1][2], True]
      and event(steps[4]) == ("rearrived", found) and event(steps[6]) == ("arrived", found)
      and [c[0] for c in calls[:5]] == ["arrival", "removed", "rearrived", "removed", "arrival"]
      and passed(calls[2], found), json.dumps(got)[-600:])
U4f = teh.Env("U4flap")                              # a camera is plugged in
unplugged = U4f.cam + "-unplugged"
got = upr(U4f.env, WATCH_LOOP, before=(
    f"STEPS = [lambda: os.rename({U4f.cam!r}, {unplugged!r}), "
    f"lambda: os.rename({unplugged!r}, {U4f.cam!r})]\n"))
check("U4 main() is the loop around poll_once: an arrival is acted on as before (notification, "
      "browser); re-plugged within 10 minutes, no second one (flap guard)",
      got.get("polls", 0) >= 3 and got.get("rc") == "still polling"
      and acted(U4f) == {"notify": 1, "browser": 1, "panel-start": 0},
      json.dumps([got, acted(U4f)]) + watch_log(U4f)[-300:])

# 1.7.4: the panel is always on. With no camera the watcher starts the panel as it
# starts and keeps checking; while the app owns the machine it never does
WATCH_KEEP = WATCH_LOOP.replace("w.panel_up = lambda: True", "w.panel_up = lambda: False")
U4k = teh.Env("U4keep", asiair=False, seestar=False)
u4k_env = dict(U4k.env, ASTRO_KEEP_PANEL_S="0", ASTRO_PANEL_RETRY_S="0")
got_k = upr(u4k_env, WATCH_KEEP, before="STEPS = [lambda: None, lambda: None]\n")
U4ka = teh.Env("U4keepapp", asiair=False, seestar=False)
owner_record(U4ka, the_app(U4ka)[0])
got_ka = upr(dict(U4ka.env, ASTRO_KEEP_PANEL_S="0", ASTRO_PANEL_RETRY_S="0"), WATCH_KEEP,
             before="STEPS = [lambda: None]\n")
check("U4 the panel is always on (1.7.4): with no camera the watcher starts the panel as it "
      "starts and again at every check while it is not answering, with no notification and no "
      "browser; a start that fails names the Restart button in the log; while the app is in "
      "charge it starts nothing",
      got_k.get("rc") == "still polling" and got_k.get("polls") == 3
      and acted(U4k) == {"notify": 0, "browser": 0, "panel-start": 4}
      and "Restart FITS Importer" in watch_log(U4k)
      and got_ka.get("rc") == 0 and acted(U4ka)["panel-start"] == 0,
      json.dumps([got_k, acted(U4k), got_ka, acted(U4ka)]) + watch_log(U4k)[-300:])

# U5 — NOTIFY_FN: the app shows notifications itself
U5 = teh.Env("U5", asiair=False, seestar=False)
e = dict(U5.env)
e["PATH"] = teh.fake_os_commands(U5.root) + os.pathsep + e["PATH"]
got = probe(e, """
got = []
m.NOTIFY_FN = lambda message, title: got.append([message, title])
m.notify('3 frames imported', 'FITS Importer - import complete', sound=True)
def _boom(message, title):
    raise RuntimeError('the app is closing')
m.NOTIFY_FN = _boom
try:
    m.notify('into a closing app')
    quiet = True
except Exception as x:
    quiet = repr(x)
m.NOTIFY_FN = None
m.notify('plain')
m.notify('chime', 'FITS Importer', sound=True)
print(json.dumps({'got': got, 'quiet': quiet}))
""")
notes = teh.os_calls(U5.root, "notify")
check("U5 NOTIFY_FN receives message and title; nothing is recorded or run",
      got.get("got") == [["3 frames imported", "FITS Importer - import complete"]]
      and not [c for c in notes if c.get("message") in ("3 frames imported", "into a closing app")]
      and (os.name == "nt" or not teh.executed(U5.root)),
      json.dumps(got)[:300] + json.dumps(notes)[:300])
check("U5 ...a NOTIFY_FN that fails never stops the engine", got.get("quiet") is True,
      json.dumps(got)[:300])
check("U5 without one, test mode records the notification with its sound (False, True when asked)",
      [(c.get("message"), c.get("sound")) for c in notes] == [("plain", False), ("chime", True)],
      json.dumps(notes)[:300])

# U6 — import.lock says what holds it
U6 = teh.Env("U6", asiair=True, seestar=False)   # a camera, so an import gets as far as the lock
got = probe(U6.env, """
out = {}
for what in (None, 'ship'):
    ok = m.acquire_lock() if what is None else m.acquire_lock(what)
    with open(m.LOCK_PATH, encoding='utf-8') as f:
        out[str(what)] = [ok, json.load(f).get('what')]
    m.release_lock()
seen = []
m.acquire_lock = lambda what='import': seen.append(what) or False
for argv in (['--ship'], ['--discard', 'M 42'], ['--no-ship']):
    sys.argv = ['astro-import.py'] + argv
    try:
        m.main()
    except SystemExit:
        pass
out['callers'] = seen
print(json.dumps(out))
""")
check("U6 import.lock records what holds it ('import' by default, else as passed)",
      got.get("None") == [True, "import"] and got.get("ship") == [True, "ship"],
      json.dumps(got)[:300])
check("U6 ...and the engine's callers pass the right word: ship, discard, import",
      got.get("callers") == ["ship", "discard", "import"], json.dumps(got)[:300])
lock = hold_lock(U6, "ship")
r = U6.run("--skip-target", "M 42")
check("U6 a command meeting the held lock says what holds it ('The ship to the archive "
      "is running right now')",
      r.returncode == 1
      and "The ship to the archive is running right now" in r.stdout + r.stderr,
      f"rc={r.returncode} " + (r.stdout + r.stderr)[-300:])
os.remove(lock)
lock = hold_lock(U6, "panel")
r = U6.run("--skip-target", "M 42")
check("U6 ...and a lock the panel holds reads 'The panel is busy right now', not 'another panel'",
      r.returncode == 1 and "The panel is busy right now" in r.stdout + r.stderr
      and "Another panel" not in r.stdout + r.stderr,
      f"rc={r.returncode} " + (r.stdout + r.stderr)[-300:])
os.remove(lock)

# U9 — the status line: frames whose only copy is on this computer
U9 = teh.Env("U9", asiair=False, seestar=False)
os.makedirs(U9.state)

def u9_ledger(counted):
    """`counted` frames only here, and one of each kind that must not count."""
    rows = {}
    def row(name, **kw):
        e = {"target": "M 42", "filename": name, "device": "seestar",
             "camera": "ZWO Seestar S50 Pro", "sourceType": "sub", "origin": "import",
             "size": 2880, "verifiedAtImport": True, "clearedFromCamera": True}
        e.update(kw)
        rows[f"MyWorks/M 42_sub/{name}"] = e
    for i in range(counted):
        row(f"20260901-{i:06d}.fit")
    row("20260902-210000.fit", clearedFromCamera=False)              # still on the camera
    row("20260902-210100.fit", archiveVerifiedAt="2026-09-03T090000")  # the PC has it too
    row("20260902-210200.fit", verifiedAtImport=False)               # never proven (baseline)
    row("20260902-210300.jpg", sourceType="sub-jpg")                 # a preview rider: never ships
    with open(os.path.join(U9.state, "ledger.json"), "w", encoding="utf-8") as f:
        json.dump({"version": 1, "files": rows, "calibration": {}}, f)

def u9_status(*extra):
    r = U9.run("--status", *extra)
    if "--json" not in extra:
        return r.returncode, r.stdout.strip()
    try:
        return r.returncode, json.loads(r.stdout)
    except ValueError:
        return r.returncode, (r.stdout + r.stderr)[-200:]

u9_ledger(0)
a, b = u9_status(), u9_status("--json")
check("U9 --status: 'Everything is safe' when nothing is only here (uncleared, PC-verified, "
      "unproven and rider rows don't count)",
      a == (0, "Everything is safe") and b == (0, {"safe": True, "onlyHere": 0,
                                                   "text": "Everything is safe",
                                                   "machine": HERE_MACHINE}), str([a, b]))
u9_ledger(1)
a = u9_status()
check(f"U9 ...one frame: '1 frame only on {HERE_WORDS}'", a == (0, f"1 frame only on {HERE_WORDS}"),
      str(a))
u9_ledger(2769)
lock = hold_lock(U9)
a, b = u9_status(), u9_status("--json")
check("U9 ...2,769 frames, with the thousands separator; --json gives the dict; "
      "no lock taken (one is held), exit 0",
      a == (0, f"2,769 frames only on {HERE_WORDS}")
      and b == (0, {"safe": False, "onlyHere": 2769, "text": f"2,769 frames only on {HERE_WORDS}",
                    "machine": HERE_MACHINE}) and os.path.isfile(lock), str([a, b]))
os.remove(lock)
FORCE = """
out = []
for win in (True, False):
    m.IS_WINDOWS, m.IS_MAC = win, not win
    m.PLATFORM, m.MACHINE_LABEL = ('windows', 'PC') if win else ('mac', 'Mac')
    out.append(m.status_summary(m.State()))
print(json.dumps(out))
"""
many = probe(U9.env, FORCE)
os.makedirs(os.path.join(U9.archive, "S50P"))        # a reachable archive, nothing to ship
r = U9.run("--ship")
u9_ledger(1)
one = probe(U9.env, FORCE)
both = (one if isinstance(one, list) else [one]) + (many if isinstance(many, list) else [many])
check("U9 the platform forced in-process: '1 frame only on this PC', '2,769 frames only on "
      "this PC', machine PC (and the Mac's wording forced the other way)",
      [(x.get("text"), x.get("machine")) for x in both]
      == [("1 frame only on this PC", "PC"), ("1 frame only on the Mac", "Mac"),
          ("2,769 frames only on this PC", "PC"), ("2,769 frames only on the Mac", "Mac")],
      json.dumps(both)[:400])
check("U9 the ship summary line is unchanged (2769, no separator), the same count as --status",
      "✓ Shipped 0 file(s). Problems: 0. Frames cleared from a camera and not yet "
      "verified on the archive: 2769." in r.stdout.splitlines()
      and isinstance(b[1], dict) and b[1].get("onlyHere") == 2769, r.stdout[-400:])
# never "safe" when it can't tell: no ledger yet, an unreadable ledger, and the
# .bak recovery warning never mixed into --json (the app parses it)
U9n = teh.Env("U9n", asiair=False, seestar=False)
r = U9n.run("--status")
check("U9 with no ledger yet: 'Nothing imported yet', not 'Everything is safe'",
      r.returncode == 0 and r.stdout.strip() == "Nothing imported yet", (r.stdout + r.stderr)[-200:])
with open(os.path.join(U9.state, "ledger.json"), "w") as f:
    f.write("{not json")
shutil.copy(os.path.join(U9.state, "ledger.json"), os.path.join(U9.state, "ledger.json.bak"))
a, b = u9_status(), u9_status("--json")
check("U9 ledger and .bak unreadable: 'Status unknown: the ledger can't be read', safe false, "
      "and --json is still pure JSON",
      a[0] == 0 and a[1].splitlines()[-1] == "Status unknown: the ledger can't be read"
      and b[0] == 0 and isinstance(b[1], dict) and b[1].get("safe") is False
      and b[1].get("onlyHere") is None, str([a, b]))
u9_ledger(1)
shutil.copy(os.path.join(U9.state, "ledger.json"), os.path.join(U9.state, "ledger.json.bak"))
with open(os.path.join(U9.state, "ledger.json"), "w") as f:
    f.write("{not json")
r = U9.run("--status", "--json")
try:
    rec = json.loads(r.stdout)
except ValueError:
    rec = None
check("U9 recovering from ledger.json.bak: the warning goes to stderr, --json stays parseable",
      isinstance(rec, dict) and rec.get("onlyHere") == 1 and "ledger.json.bak" in r.stderr,
      (r.stdout + " | " + r.stderr)[-300:])

# U11 — a frozen app is never re-launched as "python -X utf8"
U11 = teh.Env("U11", asiair=False, seestar=False)
got = probe(dict(U11.env, PYTHONUTF8="0"), """
import subprocess
class _Spawned(Exception):
    pass
def _popen(*a, **k):
    raise _Spawned()
subprocess.Popen = _popen
m.IS_WINDOWS = True                  # the only platform that re-launches
out = {'utf8': sys.flags.utf8_mode}
for frozen in (False, True):
    if frozen:
        sys.frozen = True
    try:
        m._platform_bootstrap(sys.argv[1])
        out[str(frozen)] = 'no relaunch'
    except _Spawned:
        out[str(frozen)] = 'relaunched'
print(json.dumps(out))
""")
check("U11 with sys.frozen set, _platform_bootstrap never re-launches "
      "(Windows forced, UTF-8 mode off; without sys.frozen it does)",
      got == {"utf8": 0, "False": "relaunched", "True": "no relaunch"}, json.dumps(got))

# ═══════════════ CHAIN AP: an astropy that won't load (1.5.4) ═══════════════
print("\n── Chain AP: an astropy that won't load says why, and stops only the job (1.5.4) ──")
# Backlog 13. A fake astropy that raises on import comes first on PYTHONPATH.
# Before 1.5.4 the engine said "astropy not installed", whatever the real
# reason, and called sys.exit, which in the panel ended the worker thread.
AP = teh.Env("AP", asiair=False, seestar=True)
AP.add_seestar_sub("M 42", "20260119-210000")
AP_WHY = "dlopen(_compiler.so): Library not loaded: libfake.dylib (a fake astropy for the test)"
ap_site = os.path.join(AP.root, "fake-astropy")
os.makedirs(os.path.join(ap_site, "astropy"))
with open(os.path.join(ap_site, "astropy", "__init__.py"), "w", encoding="utf-8") as f:
    f.write(f"raise ImportError({AP_WHY!r})\n")
ap_env = dict(AP.env, PYTHONPATH=ap_site)

def ap_command(fix, exe=sys.executable, windows=os.name == "nt"):
    """The line that installs or repairs astropy, as the engine words it for
    each platform: on Windows for PowerShell, & before the quoted python.exe."""
    return (f'  & "{exe}" -m pip install --user {fix}' if windows
            else f"  {exe} -m pip install {fix}")

AP_REPAIR = "--upgrade --force-reinstall astropy"
runs = [irun(ap_env, "--scan-only"), irun(ap_env, stdin="n\nn\nn\n")]   # the watcher's scan; an import
check("AP the CLI says why astropy won't load (the real ImportError) and how to repair it for "
      "this Python, then exits 1: no traceback, no scan result, nothing copied",
      all(x.returncode == 1 and f"ImportError: {AP_WHY}" in x.stderr
          and "To repair it, run" in x.stderr and ap_command(AP_REPAIR) in x.stderr
          and "Traceback" not in x.stdout + x.stderr
          and "ASIAIR-SCAN|COUNT" not in x.stdout for x in runs)
      and not [n for _d, _s, fs in os.walk(AP.sdest30) for n in fs],
      " | ".join(f"rc={x.returncode} {(x.stdout + x.stderr)[-250:]}" for x in runs))
AP_CODE = """
import contextlib, io
err, out = io.StringIO(), {}
with contextlib.redirect_stderr(err):
    for i in range(3):
        try:
            m.get_fits()
            out[str(i)] = 'loaded'
        except m.FitsUnavailable as e:
            out[str(i)] = [isinstance(e, SystemExit), e.code, e.why]
    try:
        out['model'] = list(m.seestar_model_ex(%r)[:2])
    except m.FitsUnavailable:
        out['model'] = 'stopped'
out['said'] = err.getvalue()
print(json.dumps(out))
""" % AP.svol
got = probe(ap_env, AP_CODE)
ap_said = str(got.get("said", "")) if isinstance(got, dict) else ""
check("AP in the engine: every FITS read stops with FitsUnavailable, a SystemExit(1) carrying "
      "the real reason, said once; the engine's own `except Exception` guards never swallow it "
      "(a Seestar is never named from its folder names instead)",
      isinstance(got, dict) and all(got.get(str(i)) == [True, 1, f"ImportError: {AP_WHY}"]
                                    for i in range(3))
      and got.get("model") == "stopped" and ap_said.count(AP_WHY) == 1
      and ap_said.count("-m pip install") == 1, json.dumps(got)[:500])
# not installed at all: this child can't see any site-packages folder
NO_SITE = "import sys; sys.path[:] = [p for p in sys.path if 'site-packages' not in p]\n"
got = probe(AP.env, AP_CODE, before=NO_SITE)
ap_said = str(got.get("said", "")) if isinstance(got, dict) else ""
check("AP astropy not installed at all: 'To install it', and the plain pip install for this "
      "Python (no --force-reinstall), in this platform's form",
      isinstance(got, dict)
      and got.get("0") == [True, 1, "ModuleNotFoundError: No module named 'astropy'"]
      and "To install it, run" in ap_said and ap_command("astropy") in ap_said
      and "--force-reinstall" not in ap_said, json.dumps(got)[:500])

# The advice as each platform words it, and the app: the platform, sys.frozen
# and sys.executable forced in-process, one case after another
AP_AS = """
import contextlib, io
out = {}
for key, win, frozen, exe in %r:
    m._fits = m._fits_error = None
    m.IS_WINDOWS, sys.executable = win, exe
    if frozen:
        sys.frozen = True
    elif hasattr(sys, 'frozen'):
        del sys.frozen
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        try:
            m.get_fits()
            out[key] = 'loaded'
        except m.FitsUnavailable as e:
            out[key] = {'how': e.how, 'said': err.getvalue()}
print(json.dumps(out))
"""
PYW = "C:\\Users\\Brett\\AppData\\Local\\Programs\\Python\\Python314\\pythonw.exe"   # the panel's
PYX = PYW[:-len("pythonw.exe")] + "python.exe"
MAC_PY = "/usr/local/bin/python3"
AS_PY = [("pythonw", True, False, PYW), ("python", True, False, PYX), ("mac", False, False, MAC_PY)]
as_py = {"broken": probe(ap_env, AP_AS % (AS_PY,)),
         "missing": probe(AP.env, AP_AS % (AS_PY,), before=NO_SITE)}

def ap_how(windows, missing):
    """The two lines the log and the install check show, for python.exe on
    Windows (never pythonw.exe) and python.org's python3 on the Mac."""
    return [("To install it, run" if missing else "To repair it, run")
            + (" this in Terminal (PowerShell):" if windows else ":"),
            ap_command("astropy" if missing else AP_REPAIR, PYX if windows else MAC_PY, windows)]

check("AP on Windows (forced in-process) the command pastes into Terminal's PowerShell: "
      "& \"…\\python.exe\" -m pip install --user …, naming python.exe even when the panel runs "
      "under pythonw.exe (no pip output there); on the Mac the command is as before",
      all(isinstance(got, dict) and isinstance(got.get(key), dict)
          and got[key]["how"] == ap_how(win, kind == "missing")
          and all(ln in got[key]["said"] for ln in got[key]["how"])
          for kind, got in as_py.items() for key, win, _frozen, _exe in AS_PY),
      json.dumps(as_py)[:900])
APP_MAC = "/Users/brett/Applications/FITs Importer App.app/Contents/MacOS/FITs Importer App"
APP_WIN = "C:\\Users\\Brett\\AppData\\Local\\FITs Importer App\\FITs Importer App.exe"
got = probe(ap_env, AP_AS % ([("mac", False, True, APP_MAC), ("windows", True, True, APP_WIN)],))
AP_REINSTALL = ["The FITS header reader built into this app is missing or damaged: "
                "reinstall FITs Importer App."]
check("AP in the app (sys.frozen forced, Mac and Windows) no pip command aimed at the app's "
      "own executable: the log says to reinstall FITs Importer App",
      isinstance(got, dict)
      and all(isinstance(got.get(k), dict) and got[k]["how"] == AP_REINSTALL
              and AP_REINSTALL[0] in got[k]["said"] and "by this app (" in got[k]["said"]
              and "pip" not in got[k]["said"] for k in ("mac", "windows")),
      json.dumps(got)[:600])

# numpy's own failure to load (on Windows, the usual "DLL load failed") wraps
# the real error in a page of advice; its first line said nothing useful
NP_CAUSE = "DLL load failed while importing _multiarray_umath: The specified module could not be found."
NP_MSG = ("\n\nIMPORTANT: PLEASE READ THIS FOR ADVICE ON HOW TO SOLVE THIS ISSUE!\n\n"
          "Importing the numpy C-extensions failed. This error can happen for\n"
          "many reasons, often due to issues with your setup or how NumPy was\n"
          "installed.\n\nWe have compiled some common reasons and troubleshooting tips at:\n\n"
          "    https://numpy.org/devdocs/user/troubleshooting-importerror.html\n\n"
          "Please note and check the following:\n\n"
          '  * The Python version is: Python 3.14 from "C:\\Python314\\pythonw.exe"\n'
          '  * The NumPy version is: "2.5.2"\n\n'
          "and make sure that they are the versions you expect.\n\n"
          f"Original error was: {NP_CAUSE}\n")
np_site = os.path.join(AP.root, "fake-astropy-numpy")
os.makedirs(os.path.join(np_site, "astropy"))
with open(os.path.join(np_site, "astropy", "__init__.py"), "w", encoding="utf-8") as f:
    f.write("import os\n"
            f"cause, msg = {NP_CAUSE!r}, {NP_MSG!r}\n"
            "if os.environ.get('AP_NUMPY_FROM') == '1':\n"
            "    try:\n"
            "        raise ImportError(cause)\n"
            "    except ImportError as exc:\n"
            "        raise ImportError(msg) from exc     # as numpy/_core/__init__.py does\n"
            "raise ImportError(msg)                      # the text alone\n")
got = probe(dict(AP.env, PYTHONPATH=np_site), """
import contextlib, io
out = {}
for style in ('1', '0'):
    os.environ['AP_NUMPY_FROM'] = style
    m._fits = m._fits_error = None
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        try:
            m.get_fits()
            out[style] = 'loaded'
        except m.FitsUnavailable as e:
            out[style] = [e.why, err.getvalue()]
print(json.dumps(out))
""")
check("AP numpy's page of advice ('IMPORTANT: PLEASE READ THIS…') is skipped: the banner's "
      "reason and the log give the line that says why (the DLL error), whether it was raised "
      "`from` that error (as numpy does) or only quotes it",
      isinstance(got, dict)
      and all(isinstance(got.get(k), list) and got[k][0] == f"ImportError: {NP_CAUSE}"
              and f"  ImportError: {NP_CAUSE}" in got[k][1] and "IMPORTANT" not in got[k][1]
              for k in ("1", "0")), json.dumps(got)[:700])

# An import checks astropy before it copies anything (1.5.4). An ASIAir's
# calibration frames go to the Library before the first header is read, so a
# broken astropy stopped the import after copying them, unrecorded (adopted
# by size alone, unverified, next time). Here a healthy import first, so
# there's a ledger to keep, then new lights and calibration frames.
APA = teh.Env("APasiair", asiair=True, seestar=False)
APA.add_light("Plan", "M 81", "0001", dt="20260501-220100")
APA.add_cal("Bias", "1.0ms", "20260430-090000")
r0 = APA.run(stdin="n\nn\nn\nn\n")
apa_ledger = os.path.join(APA.state, "ledger.json")

def apa_now():
    """Every file in the workbench and the Calibration Library, and the ledger's bytes."""
    files = sorted(os.path.relpath(os.path.join(d, n), APA.root)
                   for top in (APA.dest, APA.lib) for d, _s, fs in os.walk(top) for n in fs)
    return files, (open(apa_ledger, "rb").read() if os.path.isfile(apa_ledger) else None)

apa_before = apa_now()
for seq in ("0002", "0003"):
    APA.add_light("Plan", "M 81", seq, dt=f"20260502-22{seq[-2:]}00")
APA.add_cal("Bias", "1.0ms", "20260719-090000")
APA.add_cal("Dark", "300.0s", "20260719-091000")
APA.add_cal("Flat", "20.0ms", "20260720-090000", filt="LUltimate")
r = irun(dict(APA.env, PYTHONPATH=ap_site), stdin="n\nn\nn\nn\n")
apa_after = apa_now()
check("AP an ASIAir import checks astropy before it copies anything: exit 1 with the reason, no "
      "new file in the workbench or the Calibration Library (lights and calibration frames), "
      "and the ledger unchanged",
      r0.returncode == 0 and apa_before[1] is not None
      and any(f.startswith(os.path.join("dest", "ASIAir Calibration Library")) for f in apa_before[0])
      and r.returncode == 1 and f"ImportError: {AP_WHY}" in r.stderr and apa_after == apa_before,
      f"rc0={r0.returncode} rc={r.returncode} new="
      f"{sorted(set(apa_after[0]) - set(apa_before[0]))} ledger same: {apa_after[1] == apa_before[1]} "
      + (r.stdout + r.stderr)[-300:])
got = probe(AP.env, """
import argparse
out = {}
state = m.State()
state.new_ledger()
s = m.scan_seestar(state)                    # astropy loads: the Seestar is known
out['scanned'] = bool(s)
m._fits, m._fits_error = None, 'ImportError: gone after the scan (the test)'
args = argparse.Namespace(dry_run=False, no_checksum=False, loose_cal=False, explain_cal=False,
                          all=False, clean_source_previews=False, targets=None, verbose=False)
try:
    m.run_seestar_import(state, s, args)
    out['import'] = 'finished'
except m.FitsUnavailable as e:
    out['import'] = e.why
out['copied'] = [n for d, _s, fs in os.walk(%r) for n in fs]
print(json.dumps(out))
""" % os.path.join(AP.root, "dest"))
check("AP ...and so does a Seestar import (astropy gone after the scan): stopped before its first "
      "copy, nothing copied",
      isinstance(got, dict) and got.get("scanned") is True
      and got.get("import") == "ImportError: gone after the scan (the test)"
      and got.get("copied") == [], json.dumps(got)[:500])

# The install check loads astropy the engine's way (1.5.4). Before, it caught
# only an ImportError (anything else ended it with a traceback, skipping every
# later check), and said "pip install" for an astropy that was there but broken
APS = teh.Env("APself", asiair=False, seestar=False)
RT_WHY = "module compiled against ABI version 0x1000009 but this version of numpy is 0x2000000"
rt_site = os.path.join(APS.root, "fake-astropy")
os.makedirs(os.path.join(rt_site, "astropy"))
with open(os.path.join(rt_site, "astropy", "__init__.py"), "w", encoding="utf-8") as f:
    f.write(f"raise RuntimeError({RT_WHY!r})\n")
st = {}
for key, env in (("healthy", APS.env), ("ImportError", dict(APS.env, PYTHONPATH=ap_site)),
                 ("RuntimeError", dict(APS.env, PYTHONPATH=rt_site))):
    r = irun(env, script=os.path.join(HERE, "selftest.py"))
    st[key] = r.stdout + r.stderr

def st_says(out, why):
    """The astropy FAIL line with the real reason, then the engine's two lines;
    and the checks after it still ran, to the summary."""
    lines = [ln.strip() for ln in out.splitlines()]
    i = next((n for n, ln in enumerate(lines) if "astropy loads (reads FITS headers)" in ln), None)
    return (i is not None
            and lines[i:i + 3] == [f"FAIL  astropy loads (reads FITS headers)  — {why}",
                                   ap_how(os.name == "nt", False)[0],   # this platform's words
                                   ap_command(AP_REPAIR).strip()]       # ...for this Python
            and "Traceback" not in out and "this computer has an importer identity" in out
            and re.search(r"\d+ passed, \d+ warnings, \d+ failed", out) is not None)

check("AP the install check loads astropy the engine's way: the real reason (a RuntimeError too, "
      "which used to end it with a traceback) and the command that reinstalls it; the checks "
      "after it still run",
      "PASS  astropy loads (reads FITS headers)" in st["healthy"]
      and st_says(st["ImportError"], f"ImportError: {AP_WHY}")
      and st_says(st["RuntimeError"], f"RuntimeError: {RT_WHY}"),
      json.dumps({k: v[-600:] for k, v in st.items()})[:1500])

# ═══════════════ CHAIN SP: space on this Mac (1.5.5) ════════════════════════
print("\n── Chain SP: what on this computer is safe to delete, read-only (1.5.5) ──")
# Brett asked for a picture of what he can delete off the Mac. "Safe" means the
# PC's sweep re-hashed the archive copy (archiveVerifiedAt). Shipped-but-unchecked,
# never-shipped, edited-here and Brett's own files are always kept.
SP = teh.Env("SP", asiair=False, seestar=False)
os.makedirs(SP.state)
SP_ROWS = {}

def sp_file(root, target, day, name, size=2880, **kw):
    """A frame on disk plus its ledger row (kw can change what the ledger says)."""
    d = os.path.join(root, target, day) if day else os.path.join(root, target)
    os.makedirs(d, exist_ok=True)
    if kw.pop("on_disk", True):
        with open(os.path.join(d, name), "wb") as f:
            f.write(b"\0" * kw.pop("disk_size", size))
    kw.pop("disk_size", None)
    e = {"target": target, "displayName": target, "filename": name, "dest": kw.pop("dest", d),
         "device": "asiair", "camera": "ZWO ASI585MC Air", "origin": "import", "size": size,
         "verifiedAtImport": True}
    e.update(kw)
    SP_ROWS[f"{target}/{day}/{name}"] = e

VER = {"archiveLocation": "x", "archiveVerifiedAt": "2026-09-27T033000"}
sp_file(SP.dest, "M 31", "M 31 Day 1", "a1.fit", **VER)
sp_file(SP.dest, "M 31", "M 31 Day 1", "a2.fit", **VER)
sp_file(SP.dest, "M 31", "M 31 Day 1", "gone.fit", on_disk=False, **VER)     # already deleted
sp_file(SP.dest, "M 31", "M 31 Day 2", "b1.fit", **VER)
sp_file(SP.dest, "M 31", "M 31 Day 2", "b2.fit", archiveLocation="x")          # not yet re-checked
os.makedirs(os.path.join(SP.dest, "M 31", "WBPP"))
with open(os.path.join(SP.dest, "M 31", "WBPP", "master.xisf"), "wb") as f:   # Brett's own work
    f.write(b"\0" * 5000)
sp_file(SP.dest, "M 81", "M 81 Day 1", "c1.fit", **VER)
sp_file(SP.dest, "M 81", "M 81 Day 1", "c2.fit", **VER)
with open(os.path.join(SP.dest, "M 81", "M 81 Day 1", ".DS_Store"), "wb") as f:
    f.write(b"\0" * 10)                                                         # Finder's, not Brett's
# a frame gathered by hand into lights/ (Collect Lights) is still found, and still safe
sp_file(SP.dest, "M 81", "lights", "c3.fit", dest=os.path.join(SP.dest, "M 81", "M 81 Day 1"), **VER)
sp_file(SP.sdest30, "M 42", "M 42 Day 1", "d1.fit", device="seestar",
        camera="ZWO Seestar S30 Pro")                                           # never shipped
sp_file(SP.sdest30, "M 42", "M 42 Day 1", "d2.fit", device="seestar", camera="ZWO Seestar S30 Pro",
        disk_size=3000, **VER)                                                  # edited here
sp_file(SP.sdest30, "M 42", "M 42 Day 1", "d3.jpg", device="seestar", camera="ZWO Seestar S30 Pro",
        sourceType="sub-jpg", **VER)                                            # a rider never ships
sp_file(SP.dest, "M 45", "M 45 Day 1", "e1.fit", origin="backfill", archivePath="x", **VER)
with open(os.path.join(SP.state, "ledger.json"), "w", encoding="utf-8") as f:
    json.dump({"version": 1, "files": SP_ROWS, "calibration": {}}, f)

def sp_snapshot():
    """Every file on the workbench (both camera trees), with size and time."""
    out = {}
    for root, _d, fns in os.walk(os.path.join(SP.root, "dest")):
        for n in fns:
            p = os.path.join(root, n)
            out[p] = (os.path.getsize(p), os.path.getmtime(p))
    return out

before = sp_snapshot()
got = probe(SP.env, "sp = m.mac_space(m.State()); print(json.dumps(sp))")
tot = got.get("totals") or {}
fold = {os.path.basename(f["path"]): f for f in got.get("folders", [])} if isinstance(got, dict) else {}
check("SP totals: 6 frames safe (the PC re-checked them, one gathered into lights/), 1 waiting, "
      "2 only here (never shipped, and a preview rider), 1 edited here, 1 of Brett's own; "
      "Finder's .DS_Store, a back-catalogue row and a frame already gone don't count as here",
      [tot.get(k, {}).get("files") for k in ("safe", "waiting", "onlyHere", "changed", "yours")]
      == [6, 1, 2, 1, 1] and tot["safe"]["bytes"] == 6 * 2880 and tot["yours"]["bytes"] == 5000
      and got.get("gone") == 1 and got.get("unknown") is None, json.dumps(got)[:600])
check("SP M 81: every file checked on the archive, so the whole folder is safe; M 31: only Day 1 "
      "is safe on its own (Day 2 has an unchecked frame, WBPP is Brett's); M 42: nothing safe",
      fold.get("M 81", {}).get("wholeSafe") is True and fold["M 81"]["safeDays"] == []
      and fold.get("M 31", {}).get("wholeSafe") is False
      and [d["name"] for d in fold["M 31"]["safeDays"]] == ["M 31 Day 1"]
      and fold["M 31"]["safeDays"][0]["bytes"] == 2 * 2880
      and fold.get("M 42", {}).get("wholeSafe") is False and fold["M 42"]["safeDays"] == []
      and "M 45" not in fold, json.dumps(fold)[:600])
check("SP folders come most-safe-first (M 81 and M 31 before M 42)",
      [os.path.basename(f["path"]) for f in got.get("folders", [])][-1] == "M 42", str(list(fold)))
r = SP.run("--space")
check("SP --space says the importer never deletes, then lists the whole folder and the Day "
      "folder that are safe, with their paths; exit 0",
      r.returncode == 0 and "never deletes" in r.stdout
      and "Whole folders safe to delete:" in r.stdout
      and os.path.join(SP.dest, "M 81") in r.stdout
      and os.path.join(SP.dest, "M 31", "M 31 Day 1") in r.stdout
      and os.path.join(SP.sdest30, "M 42") not in r.stdout, (r.stdout + r.stderr)[-600:])
got_d = probe(SP.env, "p = m.generate_dashboard(m.State()); print(json.dumps(open(p, encoding='utf-8').read()))")
check("SP the dashboard carries the same figures and draws the Space card",
      isinstance(got_d, str) and '"wholeSafe": true' in got_d and 'id="spaceCard"' in got_d
      and "Safe to delete" in got_d, str(got_d)[:300])
calls = teh.os_calls(SP.root) if hasattr(teh, "os_calls") else []
check("SP read-only: no file under the workbench changed or vanished, and no OS call was made",
      sp_snapshot() == before and not calls, str(calls)[:300])
with open(os.path.join(SP.state, "ledger.json"), "w", encoding="utf-8") as f:
    f.write("{not json")
got = probe(SP.env, "sp = m.mac_space(m.State()); print(json.dumps(sp))")
r = SP.run("--space")
check("SP an unreadable ledger (no .bak): 'can't tell', nothing marked safe, in the view and in --space",
      isinstance(got, dict) and got.get("unknown") == "the ledger can't be read"
      and got.get("folders") == [] and got["totals"]["safe"]["files"] == 0
      and "Can't tell what is safe to delete" in r.stdout and "Whole folders" not in r.stdout,
      json.dumps(got)[:300] + " | " + r.stdout[-200:])

# ═══════════════ CHAIN AD: Astro Desk, the archive read-only (1.6.0) ═══════════
print("\n── Chain AD: Astro Desk lists the archive for processing, read-only (1.6.0) ──")
# Brett forgets, after weeks of cloud, what is still to process on the PC and
# where it is. The Archive tab joins the Observatory's states with the archive's
# own folders and opens them; it must never write to the archive.
AD = teh.Env("AD", asiair=False, seestar=False)
AD_ARCH = AD.archive

def ad_file(*parts, size=16):
    p = os.path.join(AD_ARCH, *parts)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(b"\0" * size)

AD_WIZ = ("ZWO Askar Scopes", "Wizard Nebula (NGC 7380)")
for _d in (1, 2, 3, 10):
    for _i in range(_d + 3 if _d < 10 else 1):
        ad_file(*AD_WIZ, f"Wizard Nebula Day {_d}", f"Light_Wizard_{_d}_{_i:03d}.fit")
ad_file(*AD_WIZ, "WBPP", "master", "masterLight_BIN-1_FILTER-LUltimate.xisf")
ad_file(*AD_WIZ, "Wizard_Nebula_Final_V2.jpg")
ad_file(*AD_WIZ, "Wizard.psd")
ad_file(*AD_WIZ, "Wizard.xosm")
ad_file(*AD_WIZ, "notes.txt")
ad_file(*AD_WIZ, "Run me.exe")
ad_file(*AD_WIZ, "_Working Files (regenerable - safe to delete)", "registered", "r_0001.xisf")
ad_file("S30P", "Iris Nebula (NGC 7023)", "NGC 7023_sub Day 1", "Light_NGC 7023_10.0s_IRCUT_20260920-220000.fit")
ad_file("S30P", "Iris Nebula (NGC 7023)", "Stacked_540_NGC 7023_10.0s_IRCUT_20260920-235959.fit")
ad_file("S30P", "_Quarantine", "odd.fit")
ad_file("S50", "Helix Nebula (NGC 7293)", "Exports", "Helix.jpg")
for _r in ("S30", "S50P"):
    os.makedirs(os.path.join(AD_ARCH, _r), exist_ok=True)
AD_DS = os.path.join(AD.root, "obs", "dataset.json")
os.makedirs(os.path.dirname(AD_DS))
with open(AD_DS, "w", encoding="utf-8") as f:
    json.dump({"generatedAt": "2026-10-02 08:00", "targets": [
        {"name": "Wizard Nebula", "codes": ["NGC 7380"], "state": "stacked",
         "programmes": [{"camera": "ASIAir", "hours": 7.5, "lights": 15, "nights": 3,
                         "lastNight": "2026-09-11", "filters": {"LUltimate": 15}, "masters": 1,
                         "path": "D:\\Astro Image Data\\ZWO Askar Scopes\\Wizard Nebula (NGC 7380)"}],
         "statusCards": [{"camera": "ASIAir", "state": "stacked", "evidence": "1 master, no final"}]},
        {"name": "Gone Nebula", "codes": [], "state": "captured",
         "programmes": [{"camera": "Seestar S50", "hours": 1, "path": "D:\\Astro Image Data\\S50\\Gone Nebula"}],
         "statusCards": []}]}, f)
AD_SIRIL = os.path.join(AD.root, "apps", "siril")
os.makedirs(os.path.dirname(AD_SIRIL))
with open(AD_SIRIL, "w") as f:
    f.write("#!/bin/sh\n")
AD.env.update({"ASTRO_OBSERVATORY_DATASET": AD_DS, "ASTRO_SIRIL_EXE": AD_SIRIL})

def ad_snapshot():
    out = {}
    for root, dirs, fns in os.walk(AD_ARCH):
        for n in dirs + fns:
            p = os.path.join(root, n)
            out[p] = (os.path.isdir(p), os.path.getsize(p) if os.path.isfile(p) else 0,
                      os.path.getmtime(p))
    return out

ad_before = ad_snapshot()
idx = probe(AD.env, "print(json.dumps(m.archive_index()))")
items = {i["rel"]: i for i in idx.get("items", [])} if isinstance(idx, dict) else {}
wiz = items.get("ZWO Askar Scopes/Wizard Nebula (NGC 7380)", {})
check("AD the index joins the Observatory's view to this archive: a D:\\ path lands on this "
      "machine's mount, with its state, evidence and hours; a folder the dataset no longer finds "
      "is flagged missing",
      idx.get("datasetFound") is True and idx.get("generatedAt") == "2026-10-02 08:00"
      and wiz.get("state") == "stacked" and wiz.get("evidence") == "1 master, no final"
      and wiz.get("hours") == 7.5 and wiz.get("exists") is True and wiz.get("root") == "ASIAir (Askar)"
      and items.get("S50/Gone Nebula", {}).get("exists") is False, json.dumps(idx)[:700])
check("AD folders the dataset doesn't know are listed from the archive itself (no state); "
      "_Quarantine and other '_' shelves are not targets",
      items.get("S30P/Iris Nebula (NGC 7023)", {}).get("state") is None
      and "S50/Helix Nebula (NGC 7293)" in items
      and not any("/_" in r for r in items), str(sorted(items)))
lst = probe(AD.env, "print(json.dumps(m.archive_folder_listing('ZWO Askar Scopes/Wizard Nebula (NGC 7380)')))")
names = lambda k: [x["name"] for x in lst.get(k, [])] if isinstance(lst, dict) else []
check("AD a target folder is sorted for processing: its nights in order (Day 10 last) with "
      "frame counts, the master, processed files, the finished picture, the working folder noted",
      [(n["name"], n["frames"]) for n in lst.get("nights", [])]
      == [("Wizard Nebula Day 1", 4), ("Wizard Nebula Day 2", 5), ("Wizard Nebula Day 3", 6),
          ("Wizard Nebula Day 10", 1)]
      and lst.get("frames") == 16 and names("masters") == ["masterLight_BIN-1_FILTER-LUltimate.xisf"]
      and sorted(names("processed")) == ["Wizard.psd", "Wizard.xosm"]
      and names("finals") == ["Wizard_Nebula_Final_V2.jpg"] and lst.get("working") is True
      and "Run me.exe" not in json.dumps(lst), json.dumps(lst)[:700])
other = probe(AD.env, "print(json.dumps([m.archive_folder_listing('S30P/Iris Nebula (NGC 7023)')['autostacks'], "
                      "[f['name'] for f in m.archive_folder_listing('S50/Helix Nebula (NGC 7293)')['finals']]]))")
check("AD a Seestar's own live stacks are counted as autostacks; a picture in an Exports folder "
      "is a finished one", other == [1, ["Helix.jpg"]], str(other))
bad = probe(AD.env, "print(json.dumps([m.archive_resolve(x) for x in "
                    "['../x', '/etc', 'C:/Windows', 'S30P/../../state', 'S30P/a:b', 7, None]] "
                    "+ [m.archive_folder_listing('../state'), m.archive_folder_listing('S30P/nope')]))")
check("AD only paths inside the archive resolve: climbing out, absolute paths, drive letters, "
      "':' streams and non-text are refused; an unknown folder lists as nothing",
      bad == [None] * 9, str(bad))
check("AD read-only: listing the archive changed nothing in it (no _verify probe either) and "
      "made no OS call",
      ad_snapshot() == ad_before and not os.path.exists(os.path.join(AD_ARCH, "_verify"))
      and not teh.os_calls(AD.root), str(teh.os_calls(AD.root))[:300])
if os.name != "nt":
    os.symlink(AD.state, os.path.join(AD_ARCH, "S30", "escape"))
    esc_ = probe(AD.env, "print(json.dumps([m.archive_resolve('S30/escape'), "
                         "m.archive_folder_listing('S30/escape')]))")
    os.remove(os.path.join(AD_ARCH, "S30", "escape"))
    check("AD a link inside the archive that points outside it is refused", esc_ == [None, None], str(esc_))
la = probe(AD.env, "print(json.dumps([m.launch_app(os.path.join(os.path.dirname(m.SIRIL_EXE), 'nope'), ['-d', 'x']), "
                   "m.launch_app(m.SIRIL_EXE, ['-d', m.ARCHIVE_MOUNT])]))")
launches = teh.os_calls(AD.root, "launch")
check("AD launch_app: a missing program is False and starts nothing; Siril is recorded (test "
      "mode) with -d and the folder, never started",
      la == [False, True] and len(launches) == 1 and launches[0].get("args") == ["-d", AD_ARCH]
      and inside(launches[0].get("exe", ""), AD.root), str(la) + str(launches))
r = AD.run("--help", extra_env={"ASTRO_SIRIL_EXE": os.path.join(tempfile.gettempdir(), "not-in-root", "siril")})
check("AD test mode refuses a Siril path outside the test root before anything runs",
      r.returncode == 3 and "ASTRO_SIRIL_EXE is outside the test root" in r.stderr, r.stderr[-300:])

# ═══════════════ CHAIN PL: the project layer, read-only (1.7) ═════════════════
print("\n── Chain PL: projects.json — what is ready to process, derived, read-only (1.7) ──")
# After the frames ship, nothing says "you captured this, now process it".
# --projects derives a status per dataset (target + scope + site) from the
# ledger(s), the PC's inventory and Final Astro Images, and writes ONE
# regenerable file. Status is derived, never typed in (spec: Project_Layer_Spec).
PL = teh.Env("PL", asiair=False, seestar=False)
PL_TODAY = "2026-10-10"
PL_SRC = os.path.dirname(SCRIPT)

# the shipped contract, copied INTO the root (test mode reads nothing outside)
PL_CON = os.path.join(PL.root, "contract")
os.makedirs(PL_CON)
for _f in ("targets.json", "scopes.json"):
    shutil.copy(os.path.join(PL_SRC, "contract", _f), PL_CON)
PL.env.update({"ASTRO_CONTRACT_DIR": PL_CON,
               "ASTRO_FINALS_DIR": os.path.join(PL.root, "finals"),
               "ASTRO_SHIP_FOLDER": "mac"})   # runs as the Mac on every OS, like D7

def pl_row(target, display, night, *, scope=None, device=None, st="sub", exp=10.0,
           here=False, arch=None, sha=None):
    """A ledger row the way the import writes one: `dest` is the folder, the
    frame is `dest/filename`. here=True also puts the file on this computer."""
    fn = f"Light_{target}_{exp}s_{night.replace('-', '')}-220000.fit"
    r = {"filename": fn, "target": target, "displayName": display, "night": night,
         "sourceType": st, "exposureSeconds": exp, "size": 4,
         "sha256": sha or hashlib.sha256(fn.encode()).hexdigest()}
    if device:
        r.update(device="seestar", scope=scope)
    else:
        r.update(camera="ZWO ASI585MC Air", scope=scope)
    r["dest"] = os.path.join(PL.root, "dest", target)
    if here:
        os.makedirs(r["dest"], exist_ok=True)
        with open(os.path.join(r["dest"], fn), "wb") as f:
            f.write(b"\0\0\0\0")
    if arch:
        r["archiveLocation"] = arch
    return r

PL_LED = {"version": 1, "calibration": {}, "files": {
    # Iris on the FRA400: archived and still here, a master AND a final → done
    "i1": pl_row("NGC 7023", "NGC 7023 - Iris Nebula", "2026-09-01", st="Plan",
                 scope="Askar FRA400", exp=300.0, here=True,
                 arch="ZWO Askar Scopes\\Iris Nebula (NGC 7023)\\Iris Day 1\\i1.fit"),
    "i2": pl_row("NGC 7023", "NGC 7023 - Iris Nebula", "2026-09-20", st="Plan",
                 scope="Askar FRA400", exp=300.0,
                 arch="ZWO Askar Scopes\\Iris Nebula (NGC 7023)\\Iris Day 2\\i2.fit"),
    # Iris on the 107PHQ: same shared Askar folder, no rig on the master → in progress, shared
    "i3": pl_row("NGC 7023", "NGC 7023 - Iris Nebula", "2026-09-05", st="Live",
                 scope="Askar 107PHQ", exp=120.0,
                 arch="ZWO Askar Scopes\\Iris Nebula (NGC 7023)\\Iris Day 1\\i3.fit"),
    # M 42 on the S30 Pro: two days ago, still here, only its autostack on the archive → capturing
    "m1": pl_row("M 42", "M 42 - Orion Nebula", "2026-10-08",
                 device=True, scope="Seestar S30 Pro", here=True),
    # Wizard on the S50 Pro: 39 quiet days → ready to process; cleared from this Mac by hand
    "w1": pl_row("NGC 7380", "NGC 7380 - Wizard Nebula", "2026-09-01",
                 device=True, scope="Seestar S50 Pro", sha="w1" * 32,
                 arch="S50P\\Wizard Nebula (NGC 7380)\\Wizard Day 1\\w1.fit"),
    # the quiet-period boundary: day 14 still capturing, day 15 ready
    "b1": pl_row("NGC 1499", "NGC 1499 - California Nebula", "2026-09-26",
                 device=True, scope="Seestar S50", here=True),
    "b2": pl_row("NGC 2244", "NGC 2244 - Rosette Nebula", "2026-09-25",
                 device=True, scope="Seestar S50", here=True),
    # overrides: open keeps capturing after 40 days; complete is ready inside 5
    "o1": pl_row("NGC 281", "NGC 281 - Pacman Nebula", "2026-08-31",
                 device=True, scope="Seestar S30 Pro", here=True),
    "o2": pl_row("Sh2-129", "Sh2-129 - Flying Bat Nebula", "2026-10-05",
                 device=True, scope="Seestar S30 Pro", here=True),
    # Bubble on the S30 Pro: its final sits in a folder named for the scope → done
    "u2": pl_row("NGC 7635", "NGC 7635 - Bubble Nebula", "2026-08-20",
                 device=True, scope="Seestar S30 Pro", here=True),
    # a second S50 Pro (Starfront): no unit identity exists yet, so it is the home S50P
    "sf1": pl_row("NGC 6888", "NGC 6888 - Crescent Nebula", "2026-09-02",
                  device=True, scope="Seestar S50 Pro",
                  arch="S50P\\Crescent Nebula (NGC 6888)\\Crescent Day 1\\c1.fit"),
    # a merged ASIAir row (no night in the row: the filename's stamp is used),
    # and a baseline ASIAir row with no scope at all (warned, not counted)
    "g1": {"filename": "Light_NGC 7023_300.0s_20260910-221500.fit", "target": "NGC 7023",
           "displayName": "NGC 7023 - Iris Nebula", "sourceType": "Plan", "origin": "merged",
           "camera": "ZWO ASI585MC Air", "scope": "Askar 107PHQ", "exposureSeconds": 300.0},
    "g2": {"filename": "Light_NGC 7023_300.0s_20260911-221500.fit", "target": "NGC 7023",
           "sourceType": "Live", "origin": "baseline", "camera": "ZWO ASI585MC Air",
           "night": "2026-09-11"},
    # never lights: a stack, a jpg, a mosaic panel stack and a Milky Way frame
    "x1": {"filename": "Stacked_120_M 42.fit", "target": "M 42", "device": "seestar",
           "scope": "Seestar S30 Pro", "sourceType": "stack", "night": "2026-10-08"},
    "x2": {"filename": "M 42.jpg", "target": "M 42", "device": "seestar",
           "scope": "Seestar S30 Pro", "sourceType": "sub-jpg", "night": "2026-10-08"},
    "x3": {"filename": "M 42_mosaic_pt1.fit", "target": "M 42", "device": "seestar",
           "scope": "Seestar S30 Pro", "sourceType": "panel", "night": "2026-10-08"},
    "x4": {"filename": "Light_MW_10.0s_20261008-221500.fit", "target": "MilkyWay",
           "device": "seestar", "scope": "Seestar S30 Pro", "sourceType": "mw",
           "night": "2026-10-08"},
    # names the contract doesn't know, and one that names several objects
    "u1": pl_row("Nannys Favourite", "Nannys Favourite", "2026-09-02",
                 device=True, scope="Seestar S30 Pro", here=True),
    "u3": pl_row("Leo Triplet", "Leo Triplet (M 65, M 66, NGC 3628)", "2026-03-02",
                 device=True, scope="Seestar S30 Pro", here=True),
}}
os.makedirs(PL.state, exist_ok=True)
with open(os.path.join(PL.state, "ledger.json"), "w") as f:
    json.dump(PL_LED, f)
with open(os.path.join(PL.state, "capture-state.json"), "w") as f:
    json.dump({"datasets": {"NGC281|S30P|Shinfield": "open",
                            "Sh2-129|S30P|Shinfield": "complete",
                            "M42|S30P|Shinfield": "sideways"}}, f)   # junk value ignored

# the PC's inventory: a plain master for Iris (shared folder), an autostack
# for M 42, a rig-tagged master in the Wizard's Askar folder, and a master
# for the Wizard in a second, renamed folder of the same target
PL_PC = os.path.join(PL.archive, "_verify", "pc")
os.makedirs(PL_PC)
def pl_inv_row(rel, root, folder):
    return {"schema": "inventory-row/1", "relpath": rel, "camera": root,
            "target": folder, "size": 1, "mtimeNs": 1, "kind": "light", "retired": False}
with open(os.path.join(PL_PC, "inventory-E-20261009T000000Z.jsonl"), "w") as f:
    for r in [pl_inv_row("ZWO Askar Scopes/Iris Nebula (NGC 7023)/processed/master_integration.fit",
                         "ZWO Askar Scopes", "Iris Nebula (NGC 7023)"),
              pl_inv_row("S30P/Orion Nebula (M 42)/Stacked_120_M 42.fit",
                         "S30P", "Orion Nebula (M 42)"),
              pl_inv_row("ZWO Askar Scopes/Wizard Nebula (NGC 7380)/masterLight_107PHQ.fit",
                         "ZWO Askar Scopes", "Wizard Nebula (NGC 7380)"),
              pl_inv_row("S30P/NGC 7635 - Bubble/WBPP/master/masterLight.xisf",
                         "S30P", "NGC 7635 - Bubble")]:
        f.write(json.dumps(r) + "\n")
    f.write("this line is not JSON\n")
with open(os.path.join(PL_PC, "inventory-E.status.json"), "w") as f:
    json.dump({"schema": "inventory-status/1", "generation": "20261009T000000Z"}, f)
# finals: Iris finished on the FRA400 (named rig, named scope-root folder); the
# Bubble in a folder named for its scope; a loose Iris picture that names no
# scope (two Iris datasets: it marks neither); a Crescent one (one dataset: done)
os.makedirs(os.path.join(PL.root, "finals", "ZWO Askar Scopes"))
os.makedirs(os.path.join(PL.root, "finals", "Seestar S30 Pro"))
for _p in (("ZWO Askar Scopes", "NGC7023_Iris_Nebula__2026-10_FRA400.jpg"),
           ("Seestar S30 Pro", "NGC7635_Bubble_Nebula.jpg"),
           ("NGC7023_Iris_loose.jpg",), ("NGC6888_Crescent_Nebula.jpg",),
           ("._NGC6888_Crescent_Nebula.jpg",)):
    with open(os.path.join(PL.root, "finals", *_p), "w") as f:
        f.write("x")

def pl_build(extra=""):
    return probe(PL.env, "st = m.State()\n"
                 f"doc = m.build_projects(st{extra}, today='{PL_TODAY}')\n"
                 "print(json.dumps(doc))\n")

def pl_ds(doc, tid, sid):
    for p in doc.get("projects", []):
        if p.get("target_id") == tid:
            for d in p.get("datasets", []):
                if d.get("scope") == sid:
                    return p, d
    return {}, {}

names = probe(PL.env, "c = m.load_contract()\n"
              "r = lambda x: (m.resolve_target(c, x)[0] or {}).get('id')\n"
              "print(json.dumps({'a': [r(x) for x in ['NGC 7380', 'NGC 7380 - Wizard Nebula', "
              "'Wizard Nebula (NGC 7380)', 'Wizard', 'M 31_1-2', 'M 31 - Andromeda Galaxy · 1-2', "
              "'Sh 2-129', 'SH2 129', 'HIP 24727', 'IC 1318A', 'IC 1318', 'LDN 1622', "
              "'Horsehead (IC 434 / B33)', 'Leo Triplet (M 65, M 66, NGC 3628)', "
              "'Reflection Nebula', 'MUSIC 42', 'the b4 crop']], "
              "'rigs': [m._rigs_in(x, c) for x in ['NGC7023_Iris_Nebula__2026-10_FRA400', "
              "'M45_Pleiades_15s_500subs', 'M31_10s_300x', 'NGC7023_FRA400_107PHQ', 'IC1396_S30Pro']],"
              "'codes': m._codes_in('NGC7023_Iris_B33_crop vdB142 IC1318A')}))\n")
check("PL names resolve as Brett writes them: codes in any spelling, display and folder "
      "forms, mosaic panels, an alias, a letter suffix, LDN; the HIP goto star maps to IC 405; "
      "a name for several objects, a generic name and a false code don't resolve",
      names.get("a") == ["NGC7380", "NGC7380", "NGC7380", "NGC7380", "M31", "M31", "Sh2-129",
                         "Sh2-129", "IC405", "IC1318A", "IC1318", "LDN1622", "IC434", None, None,
                         None, None], json.dumps(names.get("a")))
check("PL a scope in a filename is a whole word: S30Pro is the S30 Pro and never the S30, "
      "'500subs' is not the S50, and a final named for both Askars names both",
      names.get("rigs") == [["FRA400"], [], [], ["FRA400", "107PHQ"], ["S30P"]]
      and names.get("codes") == ["NGC7023", "BARNARD33", "VDB142", "IC1318A", "IC1318"],
      json.dumps([names.get("rigs"), names.get("codes")]))

pl_state0 = {f: os.path.getsize(os.path.join(PL.state, f)) for f in os.listdir(PL.state)}
doc = pl_build()
_, d_fra = pl_ds(doc, "NGC7023", "FRA400")
_, d_107 = pl_ds(doc, "NGC7023", "107PHQ")
check("PL done beats everything: the Iris FRA400 final (code + rig in the filename, in the "
      "scope's folder) makes that dataset done; its frames are both on the archive and here",
      d_fra.get("status") == "done"
      and d_fra.get("finals") == ["NGC7023_Iris_Nebula__2026-10_FRA400.jpg"]
      and d_fra.get("locations") == ["chillblast_archive", "mac"], json.dumps(d_fra))
check("PL a master with no rig in a shared Askar folder: the 107PHQ dataset is in progress "
      "and says the folder is shared; the FRA400 final and the loose Iris final never mark it "
      "done (a final that names no scope counts only for a one-dataset target)",
      d_107.get("status") == "in_progress" and "shared-folder" in (d_107.get("attribution") or [])
      and "unscoped-final" in (d_107.get("attribution") or [])
      and d_107.get("masters") == ["master_integration.fit"], json.dumps(d_107))
check("PL a merged row with no night is dated from its filename (107PHQ Iris: 2 nights); "
      "a baseline row with no scope is warned about, not counted",
      d_107.get("nights") == 2 and d_107.get("first_session") == "2026-09-05"
      and any("no scope recorded" in w for w in doc.get("warnings", [])),
      json.dumps([d_107.get("nights"), doc.get("warnings")]))
p_iris, _ = pl_ds(doc, "NGC7023", "FRA400")
check("PL the project rolls up to its least advanced dataset (Iris: in progress, not done) "
      "and is named with its code",
      p_iris.get("status") == "in_progress" and p_iris.get("to_process") is False
      and p_iris.get("name") == "Iris Nebula (NGC 7023)",
      json.dumps({k: v for k, v in p_iris.items() if k != "datasets"}))
_, d_m42 = pl_ds(doc, "M42", "S30P")
check("PL a Seestar autostack is the scope's own work, not Brett's: M 42 stays capturing, "
      "still on this Mac, with 1 frame (stack, preview, panel stack and Milky Way rows are "
      "never sessions), and its archive folder is named from the inventory",
      d_m42.get("status") == "capturing" and not d_m42.get("masters")
      and d_m42.get("locations") == ["mac"] and d_m42.get("frames") == 1
      and d_m42.get("archive_rel") == "S30P/Orion Nebula (M 42)", json.dumps(d_m42))
p_wiz, d_wiz = pl_ds(doc, "NGC7380", "S50P")
_, d_wiz_ask = pl_ds(doc, "NGC7380", "107PHQ")
check("PL 39 quiet days make the Wizard S50P ready to process (and the project says so); "
      "cleared from this Mac by hand, it is only on the archive; the rig-tagged Askar master "
      "touches no S50P dataset",
      d_wiz.get("status") == "ready_to_process" and p_wiz.get("to_process") is True
      and d_wiz.get("locations") == ["chillblast_archive"]
      and not d_wiz.get("masters") and not d_wiz_ask, json.dumps(d_wiz))
_, d_b14 = pl_ds(doc, "NGC1499", "S50")
_, d_b15 = pl_ds(doc, "NGC2237", "S50")
check("PL the quiet period boundary: 14 days without a session is still capturing, 15 is "
      "ready (and 'NGC 2244' resolves to the merged Rosette target NGC2237)",
      d_b14.get("status") == "capturing" and d_b15.get("status") == "ready_to_process",
      json.dumps([d_b14, d_b15]))
_, d_open = pl_ds(doc, "NGC281", "S30P")
_, d_comp = pl_ds(doc, "Sh2-129", "S30P")
check("PL capture_state: 'open' holds capturing through 40 quiet days, 'complete' is ready "
      "after 5, and a junk value is ignored",
      d_open.get("status") == "capturing" and d_open.get("capture_state") == "open"
      and d_comp.get("status") == "ready_to_process"
      and d_m42.get("capture_state") == "auto", json.dumps([d_open, d_comp]))
_, d_bub = pl_ds(doc, "NGC7635", "S30P")
check("PL a final in a folder named for the scope marks that scope's dataset done; a master "
      "in a renamed folder of the same target still counts as that target's",
      d_bub.get("status") == "done" and d_bub.get("finals") == ["NGC7635_Bubble_Nebula.jpg"]
      and d_bub.get("masters") == ["masterLight.xisf"]
      and d_bub.get("archive_rel") == "S30P/NGC 7635 - Bubble", json.dumps(d_bub))
_, d_sf = pl_ds(doc, "NGC6888", "S50P")
_, d_sf2 = pl_ds(doc, "NGC6888", "S50P-STARFRONT")
check("PL a second S50 Pro can't be told apart yet, so its frames are the home S50P at "
      "Shinfield (the Starfront entry stays switched off); its loose final counts because "
      "the target has one dataset, and a ._ sidecar is not a second final",
      d_sf.get("site") == "Shinfield" and d_sf.get("status") == "done" and not d_sf2
      and d_sf.get("finals") == ["NGC6888_Crescent_Nebula.jpg"], json.dumps([d_sf, d_sf2]))
check("PL two unknown names become one warning, not a crash, and neither is counted",
      any("2 target name" in w for w in doc.get("warnings", []))
      and not pl_ds(doc, "NGC3628", "S30P")[1], json.dumps(doc.get("warnings")))
check("PL build_projects wrote nothing: the state folder is untouched and no OS call was made",
      {f: os.path.getsize(os.path.join(PL.state, f)) for f in os.listdir(PL.state)} == pl_state0
      and not teh.os_calls(PL.root), str(teh.os_calls(PL.root))[:200])

# another computer's ledger (--with-ledger): the PC's copy of the Wizard adds
# a night, repeats w1 (same bytes: never counted twice) and says the frames
# are on the PC, which this Mac can't check
PL_PC_LED = os.path.join(PL.root, "pc-ledger.json")
with open(PL_PC_LED, "w") as f:
    json.dump({"version": 1, "calibration": {}, "files": {
        "w1-again": dict(PL_LED["files"]["w1"], dest="C:\\Astro\\S50P"),
        "w2": pl_row("NGC 7380", "NGC 7380 - Wizard Nebula", "2026-09-03",
                     device=True, scope="Seestar S50 Pro")}}, f)
doc2 = pl_build(extra=f", extra_ledgers=[{PL_PC_LED!r}]")
_, d_wiz2 = pl_ds(doc2, "NGC7380", "S50P")
check("PL --with-ledger merges another computer's sessions into the same dataset: 2 nights "
      "and 2 frames (the repeated frame counted once), on the archive and 'on the PC per its "
      "ledger'",
      d_wiz2.get("nights") == 2 and d_wiz2.get("frames") == 2
      and d_wiz2.get("locations") == ["chillblast_archive", "pc-unchecked"],
      json.dumps(d_wiz2))
r_out = PL.run("--projects", "--with-ledger", os.path.join(tempfile.gettempdir(), "not-in-root", "ledger.json"))
check("PL test mode refuses a --with-ledger file outside the test root (exit 3), and writes nothing",
      r_out.returncode == 3 and not os.path.exists(os.path.join(PL.state, "projects.json")),
      r_out.stderr[-300:])

r = PL.run("--projects")
pj_path = os.path.join(PL.state, "projects.json")
with open(pj_path) as f:
    pj1 = json.load(f)
no_mirror = not os.path.exists(os.path.join(PL.mirror, "projects.json"))
probe(PL.env, "print(json.dumps(m.mirror_owner_ok(m.MIRROR_DIR, claim=True)[0]))")
r2 = PL.run("--projects")
with open(pj_path) as f:
    pj2 = json.load(f)
pj1.pop("generated_at"), pj2.pop("generated_at")
check("PL --projects writes projects.json, says the counts, and a re-run is identical apart "
      "from the timestamp; the mirror copy only once this computer has claimed its mirror",
      r.returncode == 0 and "ready to process" in r.stdout and pj1 == pj2 and no_mirror
      and os.path.isfile(os.path.join(PL.mirror, "projects.json")), r.stdout[-300:])
check("PL projects.json carries the schema, the quiet period, the night it was worked out for "
      "and its sources (the inventory the status file names)",
      pj1.get("schema") == "projects/1" and pj1.get("quiet_period_days") == 14
      and re.fullmatch(r"\d{4}-\d{2}-\d{2}", pj1.get("as_of_night", ""))
      and pj1["sources"].get("inventory") == "inventory-E-20261009T000000Z.jsonl",
      json.dumps(pj1.get("sources")))
# The archive PC has never imported: no ledger.json at all. Its --projects must
# not mistake that for a broken ledger (the real PC, 12 Oct 2026, said "can't be
# read" and listed nothing); it reads the Mac's snapshot from _verify/mac by itself.
PLp = teh.Env("PLp", asiair=False, seestar=False)
PLp_CON = os.path.join(PLp.root, "contract")
shutil.copytree(PL_CON, PLp_CON)
PLp.env.update({"ASTRO_CONTRACT_DIR": PLp_CON, "ASTRO_SHIP_FOLDER": "pc",
                "ASTRO_FINALS_DIR": os.path.join(PLp.root, "finals")})
os.makedirs(os.path.join(PLp.archive, "_verify", "mac"))
with open(os.path.join(PLp.archive, "_verify", "mac", "ledger-snapshot.json"), "w") as f:
    json.dump({"schema": "ledger-snapshot/1", "machineId": "mac",
               "customNames": {"Nannys Favourite": "M 31 - Andromeda"},   # the Mac's custom name
               "files": {k: {kk: vv for kk, vv in r.items() if kk != "dest"}
                         for k, r in PL_LED["files"].items()}}, f)
r = PLp.run("--projects")
_pjp_path = os.path.join(PLp.state, "projects.json")
_pjp = json.load(open(_pjp_path)) if os.path.isfile(_pjp_path) else {}
check("PL on a computer that has never imported (no ledger.json) --projects says so, reads the "
      "other computer's ledger-snapshot.json from its _verify folder by itself, and writes the list",
      r.returncode == 0 and "no ledger yet" in (r.stdout + r.stderr)
      and "ledger-snapshot.json" in json.dumps(_pjp.get("sources", {}))
      and len(_pjp.get("projects") or []) >= 5
      and sum(1 for p in _pjp["projects"] for e in p["datasets"]) == sum(1 for p in pj1["projects"] for e in p["datasets"]) + 1
      and any(p.get("target_id") == "M31" for p in _pjp["projects"]),      # the snapshot's custom name resolved it
      (r.stdout + r.stderr)[-300:] + json.dumps(_pjp.get("sources")))
r = PLp.run("--targets-draft")
_drp = os.path.join(PLp.state, "targets-draft.json")
_dr = json.load(open(_drp)) if os.path.isfile(_drp) else {}
check("PL ...and --targets-draft there reads the same snapshot: the Mac's names, resolved with the "
      "Mac's custom names, and the unknown ones listed",
      r.returncode == 0 and any(x.get("target_id") == "NGC7023" for x in _dr.get("resolved", []))
      and any(x.get("target_id") == "M31" and x["raw"] == "Nannys Favourite" for x in _dr.get("resolved", []))
      and any(x["raw"].startswith("Leo Triplet") for x in _dr.get("unresolved", []))
      and any("ledger-snapshot.json" in str(x) for x in _dr.get("ledgers", [])),
      (r.stdout + r.stderr)[-300:] + str(_dr.get("unresolved"))[:200])
# ...and with no snapshot either, a good projects.json is never replaced by an empty one
PLq = teh.Env("PLq", asiair=False, seestar=False)
shutil.copytree(PL_CON, os.path.join(PLq.root, "contract"))
PLq.env.update({"ASTRO_CONTRACT_DIR": os.path.join(PLq.root, "contract"), "ASTRO_SHIP_FOLDER": "pc"})
os.makedirs(PLq.state, exist_ok=True)
with open(os.path.join(PLq.state, "projects.json"), "w") as f:
    f.write('{"schema": "projects/1", "projects": [{"keep": "me"}]}')
r = PLq.run("--projects")
check("PL ...and with no ledger and no snapshot the last good projects.json is left alone, with a reason",
      "left as it is" in (r.stdout + r.stderr)
      and json.load(open(os.path.join(PLq.state, "projects.json")))["projects"] == [{"keep": "me"}],
      (r.stdout + r.stderr)[-300:])

# ── the ten-reviewer pass, 12 Oct 2026: each fix with the input that broke it ──
def pl_pc_env(name, snapshot_files, **snap_extra):
    """A PC that never imported, with the contract and the Mac's snapshot."""
    e = teh.Env(name, asiair=False, seestar=False)
    # the shipped contract (PL_CON is gone once chain PL has cleaned up)
    shutil.copytree(PL_CON if os.path.isdir(PL_CON) else os.path.join(PL_SRC, "contract"),
                    os.path.join(e.root, "contract"))
    e.env.update({"ASTRO_CONTRACT_DIR": os.path.join(e.root, "contract"), "ASTRO_SHIP_FOLDER": "pc",
                  "ASTRO_FINALS_DIR": os.path.join(e.root, "finals")})
    os.makedirs(os.path.join(e.archive, "_verify", "mac"), exist_ok=True)
    os.makedirs(e.state, exist_ok=True)
    snap = {"schema": "ledger-snapshot/1", "machine": "Mac", "machineId": "mac", "machineUid": "mac-1",
            "at": "2026-10-10T08:00:00Z", "files": snapshot_files, "customNames": {}}
    snap.update(snap_extra)
    with open(os.path.join(e.archive, "_verify", "mac", "ledger-snapshot.json"), "w") as f:
        json.dump(snap, f)
    return e

def pl_snap_row(target, display, night, sha, scope="Seestar S30 Pro", key=None, size=4, **extra):
    r = {"filename": f"Light_{target}_10.0s_{night.replace('-', '')}-220000.fit", "target": target,
         "displayName": display, "night": night, "sourceType": "sub", "exposureSeconds": 10.0,
         "size": size, "sha256": sha, "device": "seestar", "scope": scope}
    r.update(extra)
    return r

# 1. a dataset whose first copy was dropped (unknown name) and whose second copy is
#    a duplicate by bytes crashed build_projects (IndexError on an empty nights dict);
#    and the same frame with a sha on one side and none on the other was counted twice
PLd = pl_pc_env("PLd", {
    "a": pl_snap_row("Old Seestar Name", "Old Seestar Name", "2026-09-01", "aa" * 32),
    "b": pl_snap_row("NGC 7023", "NGC 7023 - Iris Nebula", "2026-09-01", "aa" * 32),
    "S30P/M 27/x1.fit": pl_snap_row("M 27", "M 27 - Dumbbell", "2026-09-02", "bb" * 32, size=7),
    "S30P/M 27/x1.fit|cam=ZWO Seestar S30 Pro": pl_snap_row("M 27", "M 27 - Dumbbell", "2026-09-02", None, size=7),
    "junk1": {"filename": "Light_M 42_10.0s_20260903-220000.fit", "target": "M 42", "night": "2026-09-03",
              "sourceType": ["sub"], "size": [4], "device": "seestar", "scope": "Seestar S30 Pro"},
    "junk2": pl_snap_row("M 42", "M 42 - Orion", "2026-09-03", "cc" * 32, exposureSeconds=float("inf")),
    "junk3": pl_snap_row("M 42", "M 42 - Orion", "2026-09-03", "dd" * 32, exposureSeconds=10 ** 400),
    "junk4": pl_snap_row("M 42", "M 42 - Orion", "2026-09-03", "ee" * 32, size="four"),
}, customNames=["not", "a", "dict"])
r = PLd.run("--projects")
_pjd = json.load(open(os.path.join(PLd.state, "projects.json"))) if os.path.isfile(os.path.join(PLd.state, "projects.json")) else {}
_, _iris = pl_ds(_pjd, "NGC7023", "S30P")
_, _m27 = pl_ds(_pjd, "M27", "S30P")
_, _m42 = pl_ds(_pjd, "M42", "S30P")
check("PL a frame whose first copy had an unknown name and whose second copy is the same bytes "
      "is one frame in the dataset that resolved (no crash); the same frame with and without a sha "
      "is one frame; rows that are not ledger rows (lists, inf, 10**400, 'four') are not counted and "
      "do not crash; a garbage customNames is ignored",
      r.returncode == 0 and _iris.get("frames") == 1 and _m27.get("frames") == 1
      and _m42.get("frames") == 3 and _m42.get("integration_seconds") == 10
      and any("could not be read" in w for w in _pjd.get("warnings", [])),
      f"rc={r.returncode} iris={_iris.get('frames')} m27={_m27.get('frames')} m42={_m42.get('frames')}/"
      f"{_m42.get('integration_seconds')} warn={_pjd.get('warnings')} | {(r.stdout + r.stderr)[-400:]!r}")

# 2. a snapshot a newer importer wrote is not read; a stale one is said to be stale
PLv = pl_pc_env("PLv", {"a": pl_snap_row("M 31", "M 31", "2026-09-01", "aa" * 32)}, schema="ledger-snapshot/9")
r = PLv.run("--projects")
_pjv = json.load(open(os.path.join(PLv.state, "projects.json"))) if os.path.isfile(os.path.join(PLv.state, "projects.json")) else {}
check("PL a snapshot written by a newer importer is a warning and not counted",
      r.returncode == 0 and any("newer importer" in w for w in _pjv.get("warnings", []))
      and not _pjv.get("projects") and _pjv["sources"]["snapshots"][0]["rows"] == 0,
      f"rc={r.returncode} {_pjv.get('warnings')} | {(r.stdout + r.stderr)[-300:]!r}")
PLo = pl_pc_env("PLo", {"a": pl_snap_row("M 31", "M 31", "2026-09-01", "aa" * 32)}, at="2026-09-20T08:00:00Z")
r = PLo.run("--projects")
_pjo = json.load(open(os.path.join(PLo.state, "projects.json")))
check("PL a snapshot older than 36 hours is said to be stale (its age is in sources.snapshots) and still counted",
      r.returncode == 0 and any("day(s) old" in w for w in _pjo.get("warnings", []))
      and _pjo["sources"]["snapshots"][0]["age_hours"] > 24 * 10 and len(_pjo["projects"]) == 1,
      f"{_pjo.get('warnings')} {_pjo['sources'].get('snapshots')}")

# 3. capture-state.json with a byte-order mark (PowerShell 5, Notepad) and a capitalised value
PLb = pl_pc_env("PLb", {"a": pl_snap_row("NGC 281", "NGC 281 - Pacman", "2026-08-20", "aa" * 32)})
with open(os.path.join(PLb.state, "capture-state.json"), "wb") as f:
    f.write(b"\xef\xbb\xbf" + json.dumps({"datasets": {"NGC281|S30P|Shinfield": "Open ", "NGC9999|S30P|Shinfield": "open",
                                                        "NGC281|S30|Shinfield": "maybe"}}).encode())
r = PLb.run("--projects")
_pjb = json.load(open(os.path.join(PLb.state, "projects.json")))
_, _pac = pl_ds(_pjb, "NGC281", "S30P")
check("PL capture-state.json with a BOM and 'Open ' still holds the Pacman capturing after 50 quiet days; a key "
      "for a dataset that doesn't exist and a value that isn't auto/open/complete are warnings",
      _pac.get("status") == "capturing" and _pac.get("capture_state") == "open"
      and any("NGC9999" in w for w in _pjb["warnings"]) and any("maybe" in w for w in _pjb["warnings"]),
      f"{_pac.get('status')}/{_pac.get('capture_state')} {_pjb.get('warnings')}")

# 4. calibration masters are not Brett's processing; a final names its scope as '30P' or by a
#    folder on the way; an unscoped final in the scope's own root folder marks the one dataset there
PLm = pl_pc_env("PLm", {
    "a": pl_snap_row("M 42", "M 42 - Orion", "2026-08-01", "aa" * 32),
    "b": pl_snap_row("NGC 7000", "NGC 7000 - North America", "2026-08-01", "bb" * 32),
    "c": pl_snap_row("NGC 7000", "NGC 7000 - North America", "2026-08-02", "cc" * 32, scope="Seestar S30",
                     camera="ZWO Seestar S30"),
    "d": pl_snap_row("NGC 7380", "NGC 7380 - Wizard", "2026-08-01", "dd" * 32, scope="Askar FRA400",
                     device=None, camera="ZWO ASI585MC Air", sourceType="Plan"),
    "e": pl_snap_row("NGC 7380", "NGC 7380 - Wizard", "2026-08-01", "ee" * 32),
})
_mpc = os.path.join(PLm.archive, "_verify", "pc"); os.makedirs(_mpc)
with open(os.path.join(_mpc, "inventory-E-20261010T000000Z.jsonl"), "w") as f:
    for rel, root, folder in [("S30P/Orion Nebula (M 42)/calibration/darks/masterDark_10s.fit", "S30P", "Orion Nebula (M 42)"),
                              ("S30P/Orion Nebula (M 42)/masterFlat_x.xisf", "S30P", "Orion Nebula (M 42)")]:
        f.write(json.dumps({"schema": "inventory-row/1", "relpath": rel, "camera": root, "target": folder,
                            "size": 1, "mtimeNs": 1, "kind": "light", "retired": False}) + "\n")
with open(os.path.join(_mpc, "inventory-E.status.json"), "w") as f:
    json.dump({"schema": "inventory-status/1", "generation": "20261010T000000Z"}, f)
for sub_, name in (("S30P Final Images/NGC 7000 North America", "NGC7000_NorthAmerican_Nebula_30P_August_2026.jpg"),
                   ("ZWO Askar Scopes", "NGC7380_Wizard_HOO.jpg")):
    os.makedirs(os.path.join(PLm.root, "finals", sub_), exist_ok=True)
    open(os.path.join(PLm.root, "finals", sub_, name), "wb").write(b"x")
r = PLm.run("--projects")
_pjm = json.load(open(os.path.join(PLm.state, "projects.json")))
_, _m42m = pl_ds(_pjm, "M42", "S30P"); _, _na30p = pl_ds(_pjm, "NGC7000", "S30P"); _, _na30 = pl_ds(_pjm, "NGC7000", "S30")
_, _wfra = pl_ds(_pjm, "NGC7380", "FRA400"); _, _ws30p = pl_ds(_pjm, "NGC7380", "S30P")
check("PL masterDark and masterFlat never make a dataset 'in progress'; '30P' in a final's name (and 'S30P' two "
      "folders up) marks the S30 Pro dataset done and not the S30's; a final with no scope in the Askar root folder "
      "marks the one Askar dataset done and not the S30P's",
      _m42m.get("status") == "ready_to_process" and _na30p.get("status") == "done" and _na30.get("status") != "done"
      and _wfra.get("status") == "done" and _ws30p.get("status") == "ready_to_process",
      f"m42={_m42m.get('status')} na30p={_na30p.get('status')} na30={_na30.get('status')} "
      f"wfra={_wfra.get('status')} ws30p={_ws30p.get('status')} {(r.stdout + r.stderr)[-200:]!r}")

# 5. names: an unknown letter suffix falls back to its code; long catalogue names and leading
#    zeros; the Double Cluster is one target; a generic name is nobody's; the Sadr Region is the nebula
_nm = probe(PLd.env, "c = m.load_contract()\n"
            "r = lambda x: (m.resolve_target(c, x)[0] or {}).get('id')\n"
            "print(json.dumps([r(x) for x in ['NGC 7023B', 'IC 1396A', 'Messier 31', 'NGC 0224', 'Caldwell 25', "
            "'Double Cluster', 'NGC 869/884', 'Sadr Region', 'Reflection Nebula', 'Sharpless 157', 'HIP 106890 - Elephant Trunk Nebula (mosaic)']] + c['warnings']))\n")
check("PL 'NGC 7023B' (unknown suffix) is NGC 7023, 'IC 1396A' is IC 1396, 'Messier 31' and 'NGC 0224' are M 31, "
      "'Caldwell 25' is NGC 2419, the Double Cluster is NGC 869 whichever way it is written, 'Sadr Region' is the "
      "nebula, a generic name is nobody's, and the contract loads without a warning",
      _nm == ["NGC7023", "IC1396", "M31", "M31", "NGC2419", "NGC869", "NGC869", "IC1318", None, "Sh2-157", "IC1396"],
      json.dumps(_nm))

# 6. the Mac with the share gone: a list that had the PC's half is left alone, not replaced by a Mac-only one
PLu = teh.Env("PLu", asiair=False, seestar=False)
shutil.copytree(PL_CON, os.path.join(PLu.root, "contract"))
PLu.env.update({"ASTRO_CONTRACT_DIR": os.path.join(PLu.root, "contract"), "ASTRO_SHIP_FOLDER": "mac",
                "ASTRO_ARCHIVE_MOUNT": os.path.join(PLu.root, "not-mounted")})
os.makedirs(PLu.state, exist_ok=True)
with open(os.path.join(PLu.state, "ledger.json"), "w") as f:
    json.dump({"version": 1, "calibration": {}, "files": {"a": pl_snap_row("M 31", "M 31", "2026-09-01", "aa" * 32)}}, f)
with open(os.path.join(PLu.state, "projects.json"), "w") as f:
    json.dump({"schema": "projects/1", "projects": [{"keep": "me"}], "sources": {"snapshots": [{"rows": 9}]}}, f)
r = PLu.run("--projects")
check("PL on the Mac with the archive not mounted, a projects.json that carried the PC's record is left alone "
      "and the reason is said; --projects never asks Finder to mount",
      "wasn't read this time" in (r.stdout + r.stderr)
      and json.load(open(os.path.join(PLu.state, "projects.json")))["projects"] == [{"keep": "me"}]
      and teh.os_calls(PLu.root, "mount") == [], (r.stdout + r.stderr)[-300:])

# 7. the PC's nightly on a PC that never imported: the list is built right after the inventory,
#    the status file says which step did what, and a step that fails doesn't cost the night its list
PLn = pl_pc_env("PLn", {"a": pl_snap_row("M 31", "M 31", "2026-09-01", "aa" * 32)})
PLn.env.update(PCX)
os.makedirs(os.path.join(PLn.archive, "S30P"), exist_ok=True)
r = PLn.run("--pc-nightly", "--max-minutes", "0")
_ns = pc_json(PLn.archive, "nightly-status.json")
_pjn_path = os.path.join(PLn.state, "projects.json")
_pjn = json.load(open(_pjn_path)) if os.path.isfile(_pjn_path) else {}
check("PL --pc-nightly on a PC with no ledger builds projects.json from the Mac's snapshot right after the "
      "inventory (before the hash), writes _verify/pc/nightly-status.json with each step's result, exits 0, "
      "and creates no ledger of its own",
      r.returncode == 0 and len(_pjn.get("projects") or []) == 1 and _ns.get("ok") is True
      and list(_ns.get("steps", {}))[:3] == ["sweep", "inventory", "projects"]
      and _ns.get("projectsGeneratedAt") and not os.path.isfile(os.path.join(PLn.state, "ledger.json")),
      f"rc={r.returncode} steps={_ns.get('steps')} ok={_ns.get('ok')} n={len(_pjn.get('projects') or [])} "
      f"| {(r.stdout + r.stderr)[-300:]!r}")

# 8. --ship on a computer that never imported (the PC's scheduled 09:30 ship) says so and takes no lock
PLs = teh.Env("PLs", asiair=False, seestar=True)
os.makedirs(os.path.join(PLs.archive, "S30P"), exist_ok=True)
r = PLs.run("--ship")
check("PL --ship on a computer with no ledger says there is nothing to ship, exits 0, and never touches the archive",
      r.returncode == 0 and "nothing to ship" in r.stdout
      and not os.path.exists(os.path.join(PLs.archive, "_verify")), (r.stdout + r.stderr)[-300:])

# 9. the snapshot is one computer's: another computer's file in the same folder is never replaced;
#    an atomic write that fails leaves no temp file behind
PLw = teh.Env("PLw", asiair=False, seestar=False)
PLw.env.update({"ASTRO_SHIP_FOLDER": "mac"})
os.makedirs(os.path.join(PLw.archive, "S30P")); os.makedirs(os.path.join(PLw.archive, "_verify", "mac"))
os.makedirs(PLw.state, exist_ok=True)
with open(os.path.join(PLw.state, "ledger.json"), "w") as f:
    json.dump({"version": 1, "calibration": {}, "files": {"a": pl_snap_row("M 31", "M 31", "2026-09-01", "aa" * 32)}}, f)
_foreign = os.path.join(PLw.archive, "_verify", "mac", "ledger-snapshot.json")
with open(_foreign, "w") as f:
    json.dump({"schema": "ledger-snapshot/1", "machineUid": "someone-else", "machine": "Other Mac", "files": {"z": {}}}, f)
_w = probe(PLw.env, "st = m.State()\n"
           "got = m.write_ledger_snapshot(st)\n"
           "d = os.path.join(m.STATE_DIR, 'adir'); os.makedirs(d); open(os.path.join(d, 'x'), 'w').close()\n"
           "err = None\n"
           "try: m._atomic_write_json(d, {'a': 1})\n"
           "except OSError as e: err = type(e).__name__\n"
           "print(json.dumps({'got': got, 'err': err, 'tmp': [n for n in os.listdir(m.STATE_DIR) if n.endswith('.tmp')]}))\n")
check("PL the ledger snapshot never replaces another computer's, and an atomic write that fails leaves no .tmp behind",
      _w.get("got") is None and json.load(open(_foreign))["machineUid"] == "someone-else"
      and _w.get("err") and _w.get("tmp") == [], json.dumps(_w))
with open(os.path.join(PL.state, "ledger.json"), "w") as f:
    f.write("{ not json")
with open(os.path.join(PL.state, "ledger.json.bak"), "w") as f:
    f.write("{ not json either")
r3 = PL.run("--projects")
with open(pj_path) as f:
    pj3 = json.load(f)
pj3.pop("generated_at")
check("PL a ledger that can't be read leaves the last good projects.json alone",
      r3.returncode == 0 and "left as it is" in r3.stdout + r3.stderr and pj3 == pj2,
      (r3.stdout + r3.stderr)[-300:])
with open(os.path.join(PL.state, "ledger.json"), "w") as f:
    json.dump(PL_LED, f)
os.remove(os.path.join(PL.state, "ledger.json.bak"))

rd = PL.run("--targets-draft")
with open(os.path.join(PL.state, "targets-draft.json")) as f:
    draft = json.load(f)
check("PL --targets-draft resolves every known name and lists the unknown ones for Brett "
      "(with why), and never touches the contract",
      rd.returncode == 0
      and sorted(u["raw"] for u in draft["unresolved"]) == ["Leo Triplet (M 65, M 66, NGC 3628)",
                                                           "Nannys Favourite"]
      and any(x["raw"] == "NGC 7380 - Wizard Nebula" and x["target_id"] == "NGC7380"
              for x in draft["resolved"])
      and json.load(open(os.path.join(PL_CON, "targets.json")))
      == json.load(open(os.path.join(PL_SRC, "contract", "targets.json"))),
      rd.stdout[-300:])

# no inventory and no finals: warnings, never a crash, statuses still derived;
# a contract file that isn't JSON is one warning, not a crash
PL2 = teh.Env("PL2", asiair=False, seestar=False)
os.makedirs(os.path.join(PL2.root, "contract"))
for _f in ("targets.json", "scopes.json"):
    shutil.copy(os.path.join(PL_SRC, "contract", _f), os.path.join(PL2.root, "contract"))
PL2.env.update({"ASTRO_CONTRACT_DIR": os.path.join(PL2.root, "contract")})
os.makedirs(PL2.state, exist_ok=True)
with open(os.path.join(PL2.state, "ledger.json"), "w") as f:
    json.dump({"version": 1, "calibration": {}, "files": {
        "w1": {"filename": "Light_NGC 7380_20.0s_20260901-220000.fit", "target": "NGC 7380",
               "device": "seestar", "scope": "Seestar S50 Pro", "sourceType": "sub",
               "night": "2026-09-01", "exposureSeconds": 20.0}}}, f)
doc3 = probe(PL2.env, "st = m.State()\n"
             "doc = m.build_projects(st, today='2026-10-10')\n"
             "print(json.dumps(doc))\n")
_, d3 = pl_ds(doc3, "NGC7380", "S50P")
check("PL with no inventory and no finals folder the rollup still derives Ready, and says "
      "what it could not check",
      d3.get("status") == "ready_to_process"
      and any("inventory" in w for w in doc3.get("warnings", []))
      and any("finished pictures" in w.lower() for w in doc3.get("warnings", [])),
      json.dumps(doc3.get("warnings")))
with open(os.path.join(PL2.root, "contract", "targets.json"), "w") as f:
    f.write("[1, 2, 3]")
doc4 = probe(PL2.env, "st = m.State()\n"
             "doc = m.build_projects(st, today='2026-10-10')\n"
             "print(json.dumps(doc))\n")
check("PL a contract file of the wrong shape is a warning and an empty list, not a crash",
      doc4.get("projects") == [] and any("targets.json" in w for w in doc4.get("warnings", [])),
      json.dumps(doc4.get("warnings") or doc4)[:300])
shutil.rmtree(PL2.root, ignore_errors=True)
shutil.rmtree(PL.root, ignore_errors=True)

# ═══════════════ CHAIN OB: the Observatory, fed from the same pass as projects.json ═══
print("\n── Chain OB: the Observatory page, written with projects.json, served by the panel ──")
from datetime import date as _date
_ob_n = lambda back: (_date.today() - _td(days=back)).isoformat()   # nights relative to today: the
OB_N = {"m1": _ob_n(5), "m2": _ob_n(4), "i1": _ob_n(70), "i2": _ob_n(69)}  # statuses stay the same all year
OB = pl_pc_env("OB", {
    "a1": pl_snap_row("M 31", "Andromeda Galaxy (M 31) (mosaic)", OB_N["m1"], "a1" * 32, size=1000),
    "a2": pl_snap_row("M 31", "Andromeda Galaxy (M 31) (mosaic)", OB_N["m1"], "a2" * 32, size=1000),
    "a3": pl_snap_row("M 31", "Andromeda Galaxy (M 31) (mosaic)", OB_N["m2"], "a3" * 32, size=1000, filter="LP"),
    "b1": pl_snap_row("NGC 7023", "NGC 7023 - Iris Nebula", OB_N["i1"], "b1" * 32, scope="Seestar S50",
                      exposureSeconds=20.0, archiveLocation="S50/NGC 7023 - Iris Nebula/Day 1/x.fit"),
    "b2": pl_snap_row("NGC 7023", "NGC 7023 - Iris Nebula", OB_N["i2"], "b2" * 32, scope="Seestar S50",
                      exposureSeconds=20.0),
    # the Seestar's filter sits in the filename, never in a row field
    "b3": dict(pl_snap_row("NGC 7023", "NGC 7023 - Iris Nebula", OB_N["i2"], "b3" * 32, scope="Seestar S50",
                           exposureSeconds=20.0), filename=f"Light_NGC 7023_20.0s_IRCUT_{OB_N['i2'].replace('-', '')}-221000.fit"),
    # two contract targets that share a plain name ('Spiral Galaxy'): never one on the page
    "g1": pl_snap_row("M 106", "M 106 - Spiral Galaxy", OB_N["i1"], "g1" * 32),
    "g2": pl_snap_row("NGC 2403", "NGC 2403 - Spiral Galaxy", OB_N["i1"], "g2" * 32),
    "c1": pl_snap_row("Nobody Knows", "Nobody Knows", OB_N["i2"], "c1" * 32),
    "c2": pl_snap_row("Odd <!--<script> \u2028 name", "Odd <!--<script> \u2028 name", OB_N["i2"], "c2" * 32),
}, at=_dt.now(_tz.utc).isoformat(timespec="seconds"), machine="Mac<!--<script>")   # a hostile label reaches the page
shutil.copy(os.path.join(PL_SRC, "astro-observatory.html"), os.path.join(OB.root, "astro-observatory.html"))
OB.env.update({"ASTRO_OBSERVATORY_TEMPLATE": os.path.join(OB.root, "astro-observatory.html"),
               "ASTRO_ARCHIVE_LABEL": "E:\\Astro Image Data", "ASTRO_QUIET_PERIOD_DAYS": "14"})
def ob_listing(root):
    """relpath -> sha256 of every file (folders too), so a rewrite in place shows."""
    out = {}
    for dp, dn, fn in os.walk(root):
        for d in dn:
            out[os.path.relpath(os.path.join(dp, d), root) + os.sep] = "dir"
        for f in fn:
            q = os.path.join(dp, f)
            with open(q, "rb") as fh:
                out[os.path.relpath(q, root)] = hashlib.sha256(fh.read()).hexdigest()
    return out
def ob_dataset(path):
    html = open(path, encoding="utf-8").read()
    m = re.search(r'<script id="dataset" type="application/json">(.*?)</script>', html, re.S)
    return (json.loads(m.group(1)) if m else None), html
_strict = lambda s: json.loads(s, parse_constant=lambda c: (_ for _ in ()).throw(ValueError(c)))

# --projects writes projects.json AND observatory.json, from one pass
_before = ob_listing(OB.root)
r = OB.run("--projects")
_after = ob_listing(OB.root)
_changed = {k for k in set(_before) | set(_after) if _before.get(k) != _after.get(k)} - {os.path.join("state", "machine.json")}   # the identity, made on first run
_pj_rel, _oj_rel = (os.path.relpath(os.path.join(OB.state, n), OB.root) for n in ("projects.json", "observatory.json"))
_oj = json.load(open(os.path.join(OB.state, "observatory.json"))) if os.path.isfile(os.path.join(OB.state, "observatory.json")) else {}
_pj = json.load(open(os.path.join(OB.state, "projects.json"))) if os.path.isfile(os.path.join(OB.state, "projects.json")) else {}
check("OB --projects writes projects.json and observatory.json in the state folder, and changes nothing else",
      lambda: r.returncode == 0 and _changed == {_pj_rel, _oj_rel} and "observatory.json" in r.stdout
      and _oj.get("schema") == "observatory/1",
      f"rc={r.returncode} changed={sorted(_changed)} {r.stdout[-300:]}")
_tg = {x["id"]: x for x in _oj.get("targets", [])}
_m31, _iris, _m106, _n2403 = (_tg.get(k, {}) for k in ("M31", "NGC7023", "M106", "NGC2403"))
check("OB targets are keyed by the contract's id and named with their code: two 'Spiral Galaxy' "
      "entries stay two targets, each with its own position",
      lambda: _m106["name"] == "Spiral Galaxy (M 106)" and _n2403["name"] == "Spiral Galaxy (NGC 2403)"
      and _m106["ra"] != _n2403["ra"] and _oj["totals"]["targets"] == 4
      and _m31["name"] == "Andromeda Galaxy (M 31)" and "M 31" in _m31["codes"]
      and _m31["constellation"] == "Andromeda" and isinstance(_m31["ra"], float) and _m31["mosaic"] is True
      and "Nobody Knows" not in {x["name"] for x in _oj["targets"]},
      json.dumps([_m106.get("name"), _n2403.get("name"), (_oj or {}).get("totals")]))
_card = lambda tg: (tg.get("statusCards") or [{}])[0]
check("OB the statuses are the project layer's, in the page's words, with a reason, a next step and "
      "where the frames are; a frame 4 nights ago is Still capturing with its ready-from night",
      lambda: _m31["state"] == "captured" and _iris["state"] == "stacked"
      and _card(_m31)["camera"] == "Seestar S30 Pro" and _card(_iris)["camera"] == "Seestar S50"
      and _card(_iris)["action"] == "Process it" and "no new frames since" in _card(_iris)["evidence"]
      and f"({(_date.fromisoformat(_oj['asOfNight']) - _date.fromisoformat(OB_N['i2'])).days} nights)" in _card(_iris)["evidence"]
      and _card(_iris)["badges"] == ["on the archive"]
      and _card(_m31)["action"] == "Keep capturing" and "ready to process from" in _card(_m31)["evidence"]
      and _card(_m31)["readyOn"] == (_date.fromisoformat(OB_N["m2"]) + _td(days=15)).isoformat()
      and _card(_m31)["label"] == "Andromeda Galaxy (M 31) (mosaic)" and _m31["programmes"][0]["mosaic"] is True
      and _card(_m31)["lights"] == 3,
      json.dumps([_card(_m31), _card(_iris)]))
_sess = sorted((s["target"], s["camera"], s["night"], s["frames"], s["hours"]) for s in _oj.get("sessions", []))
check("OB sessions are one target, one scope, one night; filters add up to the frames (a Seestar's "
      "filter read from its filename, the rest 'unrecorded'); exposures and bytes per dataset",
      lambda: _sess == [("Andromeda Galaxy (M 31)", "Seestar S30 Pro", OB_N["m1"], 2, round(20 / 3600, 3)),
                        ("Andromeda Galaxy (M 31)", "Seestar S30 Pro", OB_N["m2"], 1, round(10 / 3600, 3)),
                        ("Iris Nebula (NGC 7023)", "Seestar S50", OB_N["i1"], 1, round(20 / 3600, 3)),
                        ("Iris Nebula (NGC 7023)", "Seestar S50", OB_N["i2"], 2, round(40 / 3600, 3)),
                        ("Spiral Galaxy (M 106)", "Seestar S30 Pro", OB_N["i1"], 1, round(10 / 3600, 3)),
                        ("Spiral Galaxy (NGC 2403)", "Seestar S30 Pro", OB_N["i1"], 1, round(10 / 3600, 3))]
      and next(s for s in _oj["sessions"] if s["night"] == OB_N["m2"] and s["target"].startswith("Andromeda"))["filters"] == {"LP": 1}
      and _m31["programmes"][0]["filters"] == {"LP": 1, "unrecorded": 2}
      and _iris["programmes"][0]["filters"] == {"IRCUT": 1, "unrecorded": 2}
      and _m31["programmes"][0]["exposures"] == {"10": 3} and _m31["programmes"][0]["bytes"] == 3000,
      json.dumps(_sess) + json.dumps([_m31.get("programmes"), _iris.get("programmes")])[:600])
_sc = {s["camera"]: s for s in _oj.get("scopes", [])}
check("OB per-scope totals carry the contract colour; the grand totals; the archive path and rel the "
      "drawer's buttons use; a dataset not on the archive says so",
      lambda: _sc["Seestar S30 Pro"]["frames"] == 5 and _sc["Seestar S30 Pro"]["colour"] == "#eda100"
      and _sc["Seestar S50"]["nights"] == 2 and _sc["Seestar S50"]["first"] == OB_N["i1"]
      and _oj["totals"]["lights"] == 8 and _oj["totals"]["nights"] == 4 and _oj["totals"]["sessions"] == 6
      and _iris["programmes"][0]["path"] == "E:\\Astro Image Data\\S50\\NGC 7023 - Iris Nebula"
      and _iris["programmes"][0]["rel"] == "S50/NGC 7023 - Iris Nebula"
      and _m31["programmes"][0]["rel"] is None and _m31["programmes"][0]["path"] == "",
      json.dumps([_sc, (_oj or {}).get("totals"), (_iris.get("programmes") or [{}])[0].get("path")]))
check("OB Data health says what was read and what was not, the unknown names are a warning, and "
      "'how the numbers add up' explains every row not counted (never a MATCH over different numbers)",
      lambda: _oj["health"][0]["severity"] == "info" and "'s record" in _oj["health"][0]["detail"]
      and "not checked here" in _oj["health"][0]["detail"]
      and any(h["severity"] == "warn" and "contract doesn't know" in h["detail"] for h in _oj["health"])
      and sum(1 for h in _oj["health"] if "snapshot is old" in h.get("title", "")) == 0
      and _oj["reconciliation"][0]["expected"] == 10 and _oj["reconciliation"][0]["computed"] == 8
      and "2 not counted: 2 names the contract doesn't know" in _oj["reconciliation"][0]["note"]
      and all(x["ok"] for x in _oj["reconciliation"]) and len(_oj["reconciliation"]) == 3
      and _oj["inputs"]["snapshot"]["rows"] == 10 and _oj["inputs"]["finals"] is False
      and _pj["sources"]["dropped"] == {"unknown_names": 2, "no_scope": 0, "no_night": 0, "unreadable": 0, "duplicates": 0}
      and all("key" in e for p in _pj["projects"] for e in p["datasets"]),
      json.dumps([(_oj or {}).get("health"), (_oj or {}).get("reconciliation"), (_pj.get("sources") or {}).get("dropped")])[:900])

# --observatory: the standalone page, and the dataset block as a browser reads it
_before = ob_listing(OB.root)
r = OB.run("--observatory")
_after = ob_listing(OB.root)
_changed = {k for k in set(_before) | set(_after) if _before.get(k) != _after.get(k)}
_obf = os.path.join(OB.state, "observatory.html")
_ds, _html = ob_dataset(_obf) if os.path.isfile(_obf) else (None, "")
check("OB --observatory writes one standalone page in the state folder and changes nothing else",
      lambda: r.returncode == 0 and _changed == {os.path.relpath(_obf, OB.root)} and "Observatory written" in r.stdout
      and _ds["totals"]["lights"] == 8, f"rc={r.returncode} changed={sorted(_changed)} {r.stdout[-300:]}")
_blob = re.search(r'<script id="dataset" type="application/json">(.*?)</script>', _html, re.S)
_blob = _blob.group(1) if _blob else ""
check("OB the dataset block can't end the script or open a comment (a hostile name from the other "
      "computer's snapshot), is strict JSON (no NaN), and __DATASET__ is gone",
      lambda: bool(_blob) and "<" not in _blob and ">" not in _blob and "&" not in _blob
      and any("Mac<!--<script>" in h["detail"] for h in _strict(_blob)["health"]) and "__DATASET__" not in _html,
      _blob[:300])
# the output path: a custom file inside the root; never the archive, a record file, or a file that isn't a page
_custom = os.path.join(OB.root, "out", "obs.html")
_outx = OB.root + "-outside.html"
_arc = os.path.join(OB.archive, "obs.html")
_rec = os.path.join(OB.state, "ledger.json")
_other = os.path.join(OB.root, "notes.txt")
open(_other, "w").write("Brett's notes")
try:
    r2 = OB.run("--observatory", _custom)
    r3 = OB.run("--observatory", _outx)
    r4 = OB.run("--observatory", extra_env={"ASTRO_OBSERVATORY_TEMPLATE": os.path.join(OB.root, "missing.html")})
    r5 = OB.run("--observatory", _arc)
    r6 = OB.run("--observatory", _rec)
    r7 = OB.run("--observatory", _other)
    r8 = OB.run("--observatory", os.path.join(OB.root, "dry.html"), "--dry-run")
    r9 = OB.run("--observatory", _custom)                       # replacing its own page is fine
    check("OB --observatory FILE writes where it is told (inside the root), replaces only an Observatory page, "
          "never writes under the archive or over a record file, refuses outside the root, honours --dry-run, "
          "and says plainly when the page template is missing",
          lambda: r2.returncode == 0 and os.path.isfile(_custom) and ob_dataset(_custom)[0]["totals"]["lights"] == 8
          and r3.returncode == 3 and "outside the test root" in (r3.stdout + r3.stderr) and not os.path.exists(_outx)
          and r4.returncode == 1 and "run the installer again" in (r4.stdout + r4.stderr)
          and r5.returncode == 0 and "inside the archive" in (r5.stdout + r5.stderr) and not os.path.exists(_arc)
          and r6.returncode == 0 and "own record files" in (r6.stdout + r6.stderr) and not os.path.exists(_rec)
          and r7.returncode == 0 and "isn't an Observatory page" in (r7.stdout + r7.stderr)
          and open(_other).read() == "Brett's notes"
          and r8.returncode == 0 and "Dry run" in r8.stdout and not os.path.exists(os.path.join(OB.root, "dry.html"))
          and r9.returncode == 0 and not any(f.endswith(".tmp") for f in os.listdir(os.path.dirname(_custom))),
          " | ".join(f"rc{i}={x.returncode} {(x.stdout + x.stderr)[-120:]!r}" for i, x in
                     enumerate((r2, r3, r4, r5, r6, r7, r8, r9), 2)))
finally:
    if os.path.exists(_outx):
        os.remove(_outx)

# every state from the facts, through build_observatory itself at a fixed night
OB2_DK = "ZWO ASI AIR/Wizard Nebula/2026-09-26 Day 1"
OB2_ASI = dict(device="asiair", camera="ZWO ASI585MC Air", scope="Askar FRA400", sourceType="Plan", dayKey=OB2_DK)
OB2 = pl_pc_env("OB2", {
    "w1": pl_snap_row("NGC 7380", "NGC 7380 - Wizard Nebula", "2026-09-26", "w1" * 32, exposureSeconds=1800.0, here=True, **OB2_ASI),
    "w2": pl_snap_row("NGC 7380", "NGC 7380 - Wizard Nebula", "2026-09-26", "w2" * 32, exposureSeconds=1800.0, filter="Ha", **OB2_ASI),
    "r1": pl_snap_row("NGC 2244", "NGC 2244 - Rosette Nebula", "2026-09-25", "r1" * 32, exposureSeconds=900.0,
                      dest=os.path.join(tempfile.gettempdir(), "x")),
    "p1": pl_snap_row("M 42", "M 42 - Orion Nebula", "2026-09-01", "p1" * 32,
                      archiveLocation="S30P/Orion Nebula (M 42)/Day 1/p1.fit"),
    "d1": pl_snap_row("NGC 7635", "NGC 7635 - Bubble Nebula", "2026-08-20", "d1" * 32),
    "q1": pl_snap_row("M 45", "M 45 - Pleiades", "20260815", "q1" * 32, exposureSeconds=0),   # a bare night spelling, no exposure
}, at="2026-10-01T08:00:00Z",
   calibration={"d1": {"frameType": "Dark", "filename": "Dark_1800s.fit", "linkedInto": [OB2_DK], "shipped": [OB2_DK]},
                "b1": {"frameType": "Bias", "filename": "Bias.fit", "linkedInto": [OB2_DK], "shipped": []},
                "f1": {"frameType": "Flat", "filename": "Flat_1.fit", "linkedInto": ["ZWO ASI AIR/Wizard Nebula"], "shipped": []},
                "f2": {"frameType": "Flat", "filename": "Flat_2.fit", "linkedInto": ["ZWO ASI AIR/Wizard Nebula"], "shipped": []},
                "x1": {"frameType": "Flat", "filename": "Other.fit", "linkedInto": ["ZWO ASI AIR/Elsewhere/2026-09-26 Day 1"], "shipped": []}})
_pc2 = os.path.join(OB2.archive, "_verify", "pc"); os.makedirs(_pc2, exist_ok=True)
with open(os.path.join(_pc2, "inventory-E-20261009T033000Z.jsonl"), "w") as f:
    f.write(json.dumps(pl_inv_row("S30P/Orion Nebula (M 42)/WBPP/master/masterLight.xisf", "S30P", "Orion Nebula (M 42)")) + "\n")
with open(os.path.join(_pc2, "inventory-E.status.json"), "w") as f:
    json.dump({"schema": "inventory-status/1", "generation": "20261009T033000Z"}, f)
os.makedirs(os.path.join(OB2.root, "finals", "Seestar S30 Pro"))
open(os.path.join(OB2.root, "finals", "Seestar S30 Pro", "NGC7635_Bubble_Nebula.jpg"), "w").write("x")
_o = probe(OB2.env, "st = m.State()\nextra, names = m.projects_inputs(st)\n"
           f"print(json.dumps(m.build_observatory(st, extra, today='{PL_TODAY}', custom_names=names)))\n")
_by = {c: x for x in _o.get("targets", []) for c in x["codes"]}
_cd = lambda c: _by[c]["statusCards"][0]
check("OB2 all four states from the facts, with the page's actions, reasons, badges and real hours; a bare "
      "night spelling is one night; the old snapshot is one warning, not two",
      lambda: [_by[c]["state"] for c in ("NGC 7380", "NGC 2244", "M 42", "NGC 7635")] == ["captured", "stacked", "processing", "complete"]
      and _by["NGC 7380"]["cameras"] == ["Askar FRA400"]
      and [_cd(c)["action"] for c in ("NGC 7380", "NGC 2244", "M 42", "NGC 7635")]
          == ["Keep capturing", "Process it", "Finish it: process to a final", ""]
      and _cd("M 42")["evidence"].startswith("master saved: masterLight.xisf")
      and _cd("NGC 7635")["evidence"] == "finished picture NGC7635_Bubble_Nebula.jpg"
      and _cd("NGC 7380")["badges"] == ["on the Mac"] and _cd("NGC 2244")["badges"] == ["on the Mac (per its ledger)"]
      and _cd("M 42")["badges"] == ["on the archive"]
      and _by["NGC 7380"]["programmes"][0]["hours"] == 1.0 and _cd("NGC 7380")["hours"] == 1.0
      and _by["NGC 7380"]["programmes"][0]["filters"] == {"Ha": 1, "unrecorded": 1}
      and _by["M 42"]["programmes"][0]["processedFiles"] == 1 and _by["NGC 7635"]["pendingProgrammes"] == 0
      and _by["M 45"]["lastNight"] == "2026-08-15" and _by["M 45"]["statusCards"][0]["lights"] == 1
      and sum(1 for h in _o["health"] if "snapshot is old" in h.get("title", "") or "day(s) old" in h.get("detail", "")) == 1
      and _o["inputs"]["inventoryAt"] == "2026-10-09T03:30:00+00:00" and _o["inputs"]["finals"] is True
      and "Final Astro Images" in _o["health"][0]["detail"] and "archive's inventory of 9 Oct 2026" in _o["health"][0]["detail"]
      and _o["asOfNight"] == PL_TODAY and _o["quietPeriodDays"] == 14
      and all(x["ok"] for x in _o["reconciliation"]),
      json.dumps(_o)[:900] if isinstance(_o, dict) else str(_o))
_pr_cal = probe(OB2.env, "st = m.State()\nextra, names = m.projects_inputs(st)\n"
                f"d = m.build_projects(st, extra, today='{PL_TODAY}', custom_names=names)\n"
                "print(json.dumps({p['target_id']: [e.get('calibration') for e in p['datasets']] for p in d['projects']}))\n")
check("OB2 calibration follows the lights: an ASIAir session counts the darks and bias linked into its "
      "Day folder and the flats linked to the target folder above it (a mosaic's shared set), never "
      "another target's; a Seestar dataset says none of ours applies",
      lambda: _pr_cal["NGC7380"] == [{"applies": True, "mode": "tracked", "biases": 1, "darks": 1, "flats": 2, "shipped": 1,
                                      "nights_with": 1, "nights": 1, "nights_without": 0, "missing": []}]
      and _pr_cal["M42"] == [{"applies": False, "mode": "inCamera"}]
      and _pr_cal["NGC2237"][0]["applies"] is False     # the Rosette (its id is NGC 2237), a Seestar row: pl_snap_row's default device
      and next(s for s in _o["sessions"] if s["target"].startswith("Wizard"))["cal"] == {"darks": 1, "flats": 2, "biases": 1}
      and next(s for s in _o["sessions"] if s["target"].startswith("Orion"))["cal"] is None
      and _by["NGC 7380"]["programmes"][0]["calibration"]["flats"] == 2
      and "linked to its lights" not in _cd("NGC 7380")["evidence"],
      json.dumps([_pr_cal, [s for s in _o["sessions"] if s["target"].startswith("Wizard")]]))
# an ASIAir dataset with no calibration at all is flagged where it matters: when it is ready
OB2b = pl_pc_env("OB2b", {
    "n1": pl_snap_row("NGC 2244", "NGC 2244 - Rosette Nebula", "2026-08-20", "n1" * 32, exposureSeconds=300.0,
                      **dict(OB2_ASI, dayKey="ZWO ASI AIR/Rosette Nebula/2026-08-20 Day 1")),
}, at="2026-10-01T08:00:00Z")
_o2 = probe(OB2b.env, "st = m.State()\nextra, names = m.projects_inputs(st)\n"
            f"print(json.dumps(m.build_observatory(st, extra, today='{PL_TODAY}', custom_names=names)))\n")
check("OB2b a ready ASIAir dataset with no darks or flats linked says so in its reason, and the "
      "dataset's calibration names what is missing",
      lambda: "no darks or flats linked to its lights" in _o2["targets"][0]["statusCards"][0]["evidence"]
      and _o2["targets"][0]["programmes"][0]["calibration"]["missing"] == ["darks", "flats"]
      and _o2["targets"][0]["statusCards"][0]["state"] == "stacked",
      json.dumps(_o2.get("targets"))[:600])
shutil.rmtree(OB2b.root, ignore_errors=True)
shutil.rmtree(OB2.root, ignore_errors=True)

# the PC publishes its list in its own _verify folder; the Mac's panel prefers it while it is fresh
OB3 = teh.Env("OB3", asiair=False, seestar=False)      # a Mac (ASTRO_SHIP_FOLDER=mac) with its own small ledger
shutil.copytree(PL_CON if os.path.isdir(PL_CON) else os.path.join(PL_SRC, "contract"), os.path.join(OB3.root, "contract"))
OB3.env.update({"ASTRO_CONTRACT_DIR": os.path.join(OB3.root, "contract"), "ASTRO_SHIP_FOLDER": "mac"})
os.makedirs(OB3.state, exist_ok=True)
_ob3_day = os.path.join(OB3.env["ASIAIR_DEST"], "Wizard Nebula", "2026-09-01 Day 1")
with open(os.path.join(OB3.state, "ledger.json"), "w") as f:
    json.dump({"version": 1,
               "calibration": {"Autorun/Dark/d.fit": {"frameType": "Dark", "filename": "d.fit", "sha256": "d" * 64,
                                                      "verifiedAtImport": True, "linkedInto": ["Wizard Nebula/2026-09-01 Day 1"],
                                                      "archive": {"Wizard Nebula/2026-09-01 Day 1": {"verifiedAt": "2026-09-02T090000"}}},
                               "Autorun/Flat/f.fit": {"frameType": "Flat", "filename": "f.fit", "linkedInto": ["Wizard Nebula/2026-09-01 Day 1"]},
                               "Autorun/Flat/unlinked.fit": {"frameType": "Flat", "filename": "u.fit", "linkedInto": []}},
               "files": {"w1": {
        "filename": "Light_NGC 7380_300.0s_Bin1_gain200_20260901-220000.fit", "target": "NGC 7380", "device": "asiair",
        "camera": "ZWO ASI585MC Air", "scope": "Askar FRA400", "sourceType": "Plan", "night": "2026-09-01",
        "exposureSeconds": 300.0, "dest": _ob3_day}}}, f)
r = OB3.run("--projects")
_own = json.load(open(os.path.join(OB3.state, "projects.json")))
_pr_own = probe(OB3.env, "st = m.State()\nimport json\n"
                "print(json.dumps({'links': m._calibration_links(st.ledger), 'day': m._day_key(st.ledger['files']['w1']['dest'])}))\n")
check("OB3 this computer's own ledger: a light row's Day folder is keyed as the calibration links name "
      "it, the linked dark (its archive copy verified) and flat count, the unlinked flat does not",
      lambda: _pr_own["day"] == "Wizard Nebula/2026-09-01 Day 1"
      and set(_pr_own["links"]) == {"Autorun/Dark/d.fit", "Autorun/Flat/f.fit"}
      and _pr_own["links"]["Autorun/Dark/d.fit"]["shipped"] == ["Wizard Nebula/2026-09-01 Day 1"]
      and _own["projects"][0]["datasets"][0]["calibration"] == {"applies": True, "mode": "tracked", "biases": 0, "darks": 1,
                                                               "flats": 1, "shipped": 1, "nights_with": 1, "nights": 1,
                                                               "nights_without": 0, "missing": []},
      json.dumps([_pr_own, _own["projects"][0]["datasets"][0].get("calibration")]))
_pcdir = os.path.join(OB3.archive, "_verify", "pc"); os.makedirs(_pcdir, exist_ok=True)
_pub = dict(_own); _pub["generated_at"] = _dt.now(_tz.utc).isoformat(timespec="seconds")
_pub["projects"] = [{"target_id": "M42", "name": "Orion Nebula (M 42)", "status": "done", "to_process": False,
                     "last_captured": "2026-09-01", "integration_seconds": 100,
                     "datasets": [{"key": "M42|S30P|Shinfield", "scope": "S30P", "scope_name": "Seestar S30 Pro",
                                   "site": "Shinfield", "status": "done", "nights": 1, "frames": 1,
                                   "integration_seconds": 100, "first_session": "2026-09-01",
                                   "last_session": "2026-09-01", "locations": ["chillblast_archive"],
                                   "archive_rel": "S30P/Orion Nebula (M 42)", "finals": ["x.jpg"]}]}]
json.dump(_pub, open(os.path.join(_pcdir, "projects.json"), "w"))
_obs_pub = {"schema": "observatory/1", "generatedAtIso": _pub["generated_at"], "generatedAt": "now", "targets": [{"id": "M42"}],
            "scopes": [], "sessions": [], "totals": {}, "health": [], "reconciliation": [], "warnings": [], "sources": {}}
json.dump(_obs_pub, open(os.path.join(_pcdir, "observatory.json"), "w"))
_pr = probe(OB3.env, "a = m.load_projects(); b = m.load_projects(prefer_published=True); c = m.load_observatory(prefer_published=True)\n"
            "print(json.dumps({'own': [p['target_id'] for p in a['projects']], 'pref': [p['target_id'] for p in b['projects']],"
            " 'by': (b.get('sources') or {}).get('published_by'), 'obs': (c or {}).get('servedFrom'), 'obsT': [t['id'] for t in (c or {}).get('targets', [])]}))\n")
_old = dict(_pub); _old["generated_at"] = (_dt.now(_tz.utc) - _td(hours=72)).isoformat(timespec="seconds")
json.dump(_old, open(os.path.join(_pcdir, "projects.json"), "w"))
_pr2 = probe(OB3.env, "b = m.load_projects(prefer_published=True)\nprint(json.dumps({'pref': [p['target_id'] for p in b['projects']], 'by': (b.get('sources') or {}).get('published_by')}))\n")
check("OB3 on the Mac, the PC's published list (its own _verify/pc folder on the archive) is preferred while "
      "it is under 48 h old, and named as the PC's; an old one gives way to the Mac's own; the Observatory the same",
      lambda: _pr["own"] == ["NGC7380"] and _pr["pref"] == ["M42"] and _pr["by"] == "pc"
      and isinstance(_pr["obs"], dict) and _pr["obs"].get("machine") == "PC" and _pr["obsT"] == ["M42"]
      and _pr2["pref"] == ["NGC7380"] and _pr2["by"] is None,
      json.dumps([_pr, _pr2]))
# the PC's nightly job publishes both files (chain PC runs the job; here the publisher alone)
_pr3 = probe(OB.env, "n = m.publish_projects()\nimport os\n"
             "print(json.dumps({'n': n, 'files': sorted(os.listdir(os.path.join(m.ARCHIVE_MOUNT, '_verify', 'pc')))}))\n")
check("OB publish_projects puts projects.json and observatory.json in this computer's own _verify folder, nothing else",
      lambda: _pr3["n"] == 2 and _pr3["files"] == ["observatory.json", "projects.json"], str(_pr3))
shutil.rmtree(OB3.root, ignore_errors=True)
shutil.rmtree(OB.root, ignore_errors=True)

# ═══════════════ CHAIN IN: the installers and the suite itself (1.7.0) ════════
print("\n── Chain IN: the installers and the suite itself (1.7.0, ten-reviewer pass) ──")
IN_ROOT = tempfile.mkdtemp(prefix="v2test-IN-")
teh.make_env(IN_ROOT)
with open(os.path.join(HERE, "install-windows.ps1"), encoding="utf-8-sig") as f:
    IN_PS = f.read()
with open(os.path.join(HERE, "install-scripts.sh"), encoding="utf-8") as f:
    IN_SH = f.read()
with open(os.path.join(HERE, "com.brettjohnson.astro-ship.plist"), encoding="utf-8") as f:
    IN_PLIST = f.read()

# every contract file we ship is in shipped.sha256, so an unedited installed copy
# is updated instead of being left behind with a .new beside it
with open(os.path.join(HERE, "contract", "shipped.sha256"), encoding="utf-8") as f:
    IN_SHIPPED = {ln.split()[0].lower() for ln in f if ln.strip() and not ln.startswith("#")}
_missing = []
for _f in ("targets.json", "scopes.json"):
    with open(os.path.join(HERE, "contract", _f), "rb") as f:
        h = hashlib.sha256(f.read()).hexdigest()
    if h not in IN_SHIPPED:
        _missing.append(f"{h}  {_f}")
check("IN contract/shipped.sha256 lists the hash of every contract file in this build "
      "(add the new line when a contract file changes)", not _missing,
      "add to contract/shipped.sha256: " + "; ".join(_missing))

# the Mac installer's contract block, run on its own: new → installed; an unedited
# shipped copy → replaced (no .new); Brett's edits → kept, the new copy beside it
_cblock = owner_block(os.path.join(HERE, "install-scripts.sh"),
                      begin="# >>> contract update", end="# <<< contract update")
if os.name == "nt" or not shutil.which("bash") or not shutil.which("shasum"):
    skip("IN the Mac installer's contract update block (needs bash and shasum)")
elif _cblock is None:
    check("IN install-scripts.sh has exactly one marked contract update block", False, "no block")
else:
    src = os.path.join(IN_ROOT, "zip", "contract")
    bin_ = os.path.join(IN_ROOT, "bin", "contract")
    os.makedirs(src); os.makedirs(bin_)
    shutil.copy(os.path.join(HERE, "contract", "scopes.json"), src)
    with open(os.path.join(src, "targets.json"), "w") as f:
        f.write('{"shipped": "new"}')
    with open(os.path.join(src, "shipped.sha256"), "w") as f:
        f.write("# test list\n" + hashlib.sha256(b'{"shipped": "old"}').hexdigest() + "  targets.json\n")
    _script = os.path.join(IN_ROOT, "contract-block.sh")
    with open(_script, "w", encoding="utf-8") as f:
        f.write("#!/bin/bash\nset -euo pipefail\n"
                'success() { echo "OK $1"; }; warn() { echo "WARN $1"; }\n'
                'install_file() { cp "$1" "$2"; echo "INSTALL $(basename "$2")"; }\n'
                f"SCRIPT_DIR={shq(os.path.join(IN_ROOT, 'zip'))}\nBIN_DIR={shq(os.path.join(IN_ROOT, 'bin'))}\n"
                + "\n".join(_cblock) + "\n")
    def _run_block():
        return subprocess.run(["bash", _script], capture_output=True, text=True, timeout=60)
    r1 = _run_block()                                  # nothing installed yet
    _t = os.path.join(bin_, "targets.json")
    check("IN contract block: a first install copies both contract files, no .new",
          r1.returncode == 0 and open(_t).read() == '{"shipped": "new"}'
          and os.path.exists(os.path.join(bin_, "scopes.json")) and not os.path.exists(_t + ".new"),
          r1.stdout + r1.stderr)
    with open(_t, "w") as f:
        f.write('{"shipped": "old"}')                  # an older shipped copy, unedited
    with open(_t + ".new", "w") as f:
        f.write("stale")
    r2 = _run_block()
    check("IN contract block: an unedited older shipped copy is simply updated, and a stale .new "
          "beside it removed", r2.returncode == 0 and open(_t).read() == '{"shipped": "new"}'
          and not os.path.exists(_t + ".new") and "updated" in r2.stdout, r2.stdout + r2.stderr)
    with open(_t, "w") as f:
        f.write('{"mine": "edited by Brett"}')
    r3 = _run_block()
    check("IN contract block: Brett's edited copy is kept, the shipped one lands as .new, "
          "and the installer carries on", r3.returncode == 0
          and open(_t).read() == '{"mine": "edited by Brett"}'
          and os.path.exists(_t + ".new") and open(_t + ".new").read() == '{"shipped": "new"}'
          and "your edits" in r3.stdout, r3.stdout + r3.stderr)

# the Windows installer: what the reviews asked for, read from the script
check("IN install-windows.ps1 refuses an Administrator window unless -AllowElevated, and names "
      "the three tasks to unregister",
      "IsInRole" in IN_PS and "AllowElevated" in IN_PS
      and all(f"'{n}'" in IN_PS for n in ("BrettjoAstro FITS Importer ship", "Astro archive sweep",
                                           "Astro sync requests")))
check("IN install-windows.ps1 takes the account from WindowsIdentity, never USERDOMAIN\\USERNAME",
      "WindowsIdentity]::GetCurrent()" in IN_PS and "$env:USERDOMAIN" not in IN_PS)
check("IN install-windows.ps1 registers all three tasks through one helper with the Unregister hint",
      IN_PS.count("Register-AstroTask ") == 3 and IN_PS.count("function Register-AstroTask") == 1
      and IN_PS.count("Register-ScheduledTask ") == 1 and "Unregister-ScheduledTask -TaskName '$name'" in IN_PS)
_sw = IN_PS.find("if ($sweepOk) {")
check("IN install-windows.ps1 sets sweep.ps1 aside only after the Python sweep task registered",
      _sw > 0 and "Rename-Item" in IN_PS[_sw:_sw + 600] and IN_PS.count("sweep.ps1.retired") == 0
      and IN_PS.count("'sweep.ps1', 'install_sweep.ps1'") == 1)
check("IN install-windows.ps1 reads contract\\shipped.sha256 and replaces only unedited shipped copies",
      "shipped.sha256" in IN_PS and "$shipped -contains $have" in IN_PS)
check("IN install-windows.ps1 cuts a stuck sync tick after 15 minutes, not 2 hours",
      "--pc-tick" in IN_PS and "ExecutionTimeLimit (New-TimeSpan -Minutes 15)" in IN_PS)
check("IN install-windows.ps1 is still UTF-8 with a BOM and CRLF",
      open(os.path.join(HERE, "install-windows.ps1"), "rb").read()[:3] == b"\xef\xbb\xbf"
      and "\r\n" in open(os.path.join(HERE, "install-windows.ps1"), newline="").read()
      and "\n" not in open(os.path.join(HERE, "install-windows.ps1"), newline="").read().replace("\r\n", ""))

# the Mac installer and the ship agent
check("IN install-scripts.sh strips the quarantine flag from the Desktop Restart button",
      "xattr -d com.apple.quarantine" in IN_SH)
check("IN install-scripts.sh reads config.json with the same Python as the owner check, and "
      "a failure there can't stop the installer (set -e)",
      '"$PYCHECK" - <<\'PY\' 2>/dev/null || true' in IN_SH and "/usr/bin/python3 - <<'PY'" not in IN_SH)
check("IN install-scripts.sh leaves the web ship agent off while the FITs Importer App is in charge",
      'if [ -n "$APP_OWNS" ]; then' in IN_SH
      and IN_SH.find('if [ -n "$APP_OWNS" ]; then') < IN_SH.find('elif [ -z "$ARCHIVE_CONFIGURED" ]; then'))
_wsh = open(os.path.join(HERE, "astro-watch.sh"), encoding="utf-8").read()
_wsh_none = _wsh[_wsh.find('if [ "$CUR" = "none" ]; then'):]
_wsh_none = _wsh_none[:_wsh_none.find("\nfi\n")]
_plist = open(os.path.join(HERE, "com.brettjohnson.astro-import.plist"), encoding="utf-8").read()
check("IN the Mac watcher keeps the panel up too (1.7.4): its no-camera branch calls "
      "ensure_panel_silently (ping, start only when silent, never a tab), and the LaunchAgent "
      "runs it at load, on /Volumes changes and every five minutes (StartInterval 300)",
      "ensure_panel_silently" in _wsh_none and "<key>WatchPaths</key>" in _plist
      and "<key>RunAtLoad</key>\n    <true/>" in _plist
      and "<key>StartInterval</key>\n    <integer>300</integer>" in _plist)
check("IN both installers say the panel is always running, the Mac installer no longer says the "
      "panel waits for the next plug-in, and the install check says the watcher starts it",
      "any time, camera or not" in IN_SH and "any time, camera or not" in IN_PS
      and "next plug-in" not in IN_SH
      and "the watcher starts it within a minute" in open(os.path.join(HERE, "selftest.py"),
                                                           encoding="utf-8").read())
check("IN the ship agent runs under caffeinate -i, from a plain bash -c, and still falls back "
      "to Apple's python3",
      "/usr/bin/caffeinate -i" in IN_PLIST and "<string>-c</string>" in IN_PLIST
      and "<string>-lc</string>" not in IN_PLIST and "P=/usr/bin/python3" in IN_PLIST)
check("IN .gitattributes keeps .ps1 and .cmd files CRLF on every clone",
      os.path.exists(os.path.join(HERE, ".gitattributes"))
      and "*.ps1 text eol=crlf" in open(os.path.join(HERE, ".gitattributes")).read()
      and "*.cmd text eol=crlf" in open(os.path.join(HERE, ".gitattributes")).read())

# the share-host probe before `open smb://`: a PC that is off answers nothing, so the
# Mac asks Finder for nothing (no "connecting" sheet, no 20-second wait)
import socket as _sock
_srv = _sock.socket(); _srv.bind(("127.0.0.1", 0)); _srv.listen(1)
_open_port = _srv.getsockname()[1]
_closed = _sock.socket(); _closed.bind(("127.0.0.1", 0)); _closed_port = _closed.getsockname()[1]; _closed.close()
_env_in = teh.make_env(IN_ROOT)
_t0 = time.time()
_pr = probe(_env_in, "print(json.dumps({"
            f"'up': m._share_host_up('smb://astro@127.0.0.1:{_open_port}/AstroImageData'),"
            f"'down': m._share_host_up('smb://astro@127.0.0.1:{_closed_port}/AstroImageData'),"
            "'bad': m._share_host_up('not a url'), 'none': m._share_host_up(None),"
            "'nohost': m._share_host_up('smb:///share')}))\n")
_took = time.time() - _t0
_srv.close()
check("IN _share_host_up: a listening host is up, a closed port, no URL or no host is down, "
      "and it answers in seconds",
      _pr.get("up") is True and _pr.get("down") is False and _pr.get("bad") is False
      and _pr.get("none") is False and _pr.get("nohost") is False and _took < 15,
      f"{_pr} took {_took:.1f}s")
check("IN _try_mount_archive asks Finder only after the probe (the probe comes first in the code)",
      "if not _share_host_up(url):" in open(SCRIPT, encoding="utf-8").read()
      and open(SCRIPT, encoding="utf-8").read().find("if not _share_host_up(url):")
      < open(SCRIPT, encoding="utf-8").read().find('subprocess.run(["open", url]'))

# a config.json saved by Notepad (UTF-8 with a byte-order mark) is read, not ignored
_cfg = os.path.join(IN_ROOT, "config.json")
with open(_cfg, "w", encoding="utf-8-sig") as f:
    json.dump({"ASTRO_QUIET_PERIOD_DAYS": 5}, f)
_pr = probe(teh.make_env(IN_ROOT, ASIAIR_CONFIG=_cfg), "print(json.dumps({'q': m.QUIET_PERIOD_DAYS}))\n")
check("IN a config.json with a byte-order mark (Notepad) is honoured", _pr.get("q") == 5, str(_pr))

# the suite's own plumbing: a check given a callable that raises is a FAIL with the
# traceback, not a crash of the whole suite (checked through a child, so this run's
# own count stays honest)
_plumb = os.path.join(IN_ROOT, "plumb.py")
with open(_plumb, "w", encoding="utf-8") as f:
    f.write("import sys, re, os\n"
            f"__file__ = {os.path.join(HERE, 'test_v2.py')!r}\n"
            f"src = open({os.path.join(HERE, 'test_v2.py')!r}, encoding='utf-8').read()\n"
            "head = src[:src.index('# ── Minimal FITS generator')]\n"
            "head = head.replace('teh.isolate_runner()', 'pass')\n"
            "exec(compile(head, 'head', 'exec'))\n"
            "check('a check that raises', lambda: 1 // 0)\n"
            "skip('something this OS cannot do')\n"
            "check('a plain pass', True)\n"
            "raise RuntimeError('the suite died here')\n")
_r = subprocess.run([sys.executable, _plumb], capture_output=True, text=True, encoding="utf-8",
                    errors="replace", timeout=120, cwd=HERE,
                    env=dict(os.environ, PYTHONPATH=HERE))
check("IN the suite's check() turns a raising callable into a FAIL with the traceback, counts "
      "skips, and a crash still ends in a summary that names it",
      _r.returncode == 1 and "FAIL  a check that raises" in _r.stdout and "ZeroDivisionError" in _r.stdout
      and "1 passed, 2 failed, 1 skipped" in _r.stdout and "CRASH: the suite stopped here" in _r.stdout
      and "the suite died here" in _r.stdout and "[test_v2.py:" in _r.stdout
      and _r.stdout.count("passed,") == 1,
      (_r.stdout + _r.stderr)[-1500:])
shutil.rmtree(IN_ROOT, ignore_errors=True)

# the Observatory's 1.7.2 fields: facts the page used to regex out of sentences (SPEC §6)
OB4_DK1 = "ZWO ASI AIR/Wizard Nebula/2026-09-26 Day 1"
OB4_DK2 = "ZWO ASI AIR/Wizard Nebula/2026-09-28 Day 2"
OB4_ASI = dict(device="asiair", camera="ZWO ASI585MC Air", scope="Askar FRA400", sourceType="Plan")
OB4 = pl_pc_env("OB4", {
    "w1": pl_snap_row("NGC 7380", "NGC 7380 - Wizard Nebula", "2026-09-26", "w1" * 32, exposureSeconds=300.0, gain=100,
                      archiveLocation="ZWO Askar Scopes/Wizard Nebula (NGC 7380)/Wizard Nebula Day 1/w1.fit",
                      archiveVerifiedAt="2026-09-27T030000", dayKey=OB4_DK1, **OB4_ASI),
    "w2": pl_snap_row("NGC 7380", "NGC 7380 - Wizard Nebula", "2026-09-26", "w2" * 32, exposureSeconds=300.0, gain=100,
                      filter="Ha", dayKey=OB4_DK1, **OB4_ASI),
    "w3": pl_snap_row("NGC 7380", "NGC 7380 - Wizard Nebula", "2026-09-28", "w3" * 32, exposureSeconds=180.0, gain=200,
                      dayKey=OB4_DK2, **OB4_ASI),
    "s1": pl_snap_row("M 13", "M 13 - Hercules Cluster", "2026-08-01", "s1" * 32),      # a sample, by Brett's flag
    "m1": pl_snap_row("M 27", "M 27 - Dumbbell Nebula", "2026-08-10", "m1" * 32, exposureSeconds=0),   # no exposure recorded
    "m2": pl_snap_row("M 27", "M 27 - Dumbbell Nebula", "2026-08-10", "m2" * 32, exposureSeconds=0),
    "u1": pl_snap_row("Old Name Nobody Knows", "Old Name Nobody Knows", "2026-08-11", "u1" * 32),
    "k1": pl_snap_row("M 42", "M 42 - Orion Nebula", "2026-08-12", "k1" * 32, sourceType="stack"),   # not a light frame
}, at="2026-10-09T08:00:00Z",
   calibration={"d1": {"frameType": "Dark", "filename": "Dark_300s.fit", "linkedInto": [OB4_DK1], "shipped": [OB4_DK1],
                       "exposureSeconds": 300.0, "gain": 100, "filter": ""},
                "f1": {"frameType": "Flat", "filename": "Flat_Ha.fit", "linkedInto": [OB4_DK1], "shipped": [],
                       "exposureSeconds": 2.0, "gain": 100, "filter": "Ha"},
                "b1": {"frameType": "Bias", "filename": "Bias.fit", "linkedInto": [OB4_DK1], "shipped": [], "gain": 100}})
_pc4 = os.path.join(OB4.archive, "_verify", "pc"); os.makedirs(_pc4, exist_ok=True)
with open(os.path.join(_pc4, "inventory-E-20261009T033000Z.jsonl"), "w") as f:
    for r in [pl_inv_row("ZWO Askar Scopes/Wizard Nebula (NGC 7380)/Wizard Nebula Day 1/w1.fit", "ZWO Askar Scopes", "Wizard Nebula (NGC 7380)"),
              pl_inv_row("ZWO Askar Scopes/Wizard Nebula (NGC 7380)/Wizard Nebula Day 1/Stacked_60_x.fit", "ZWO Askar Scopes", "Wizard Nebula (NGC 7380)"),
              pl_inv_row("ZWO Askar Scopes/Wizard Nebula (NGC 7380)/Wizard Nebula Day 1/_Working Files (regenerable - safe to delete)/tmp.xisf", "ZWO Askar Scopes", "Wizard Nebula (NGC 7380)")]:
        r["size"] = 10
        f.write(json.dumps(r) + "\n")
with open(os.path.join(_pc4, "inventory-E.status.json"), "w") as f:
    json.dump({"schema": "inventory-status/1", "generation": "20261009T033000Z"}, f)
with open(os.path.join(OB4.state, "capture-state.json"), "w") as f:
    json.dump({"M13|S30P|Shinfield": "sample", "M27|S30P|Shinfield": {"state": "complete", "exposure": 10},
               "NGC7380|FRA400|Shinfield": {"state": "open"}}, f)
_o4 = probe(OB4.env, "st = m.State()\nextra, names = m.projects_inputs(st)\n"
            "m.save_scan_summary(3559, 29, camera='Seestar', failed_eject=True, elsewhere=12, "
            "target_names=['Tadpoles Nebula (IC 410)', 'Western Veil Nebula (NGC 6960)', 7, ''], elsewhere_machine='PC')\n"
            f"print(json.dumps(m.build_observatory(st, extra, today='{PL_TODAY}', custom_names=names)))\n")
_by4 = {c: x for x in _o4.get("targets", []) for c in x["codes"]}
_wiz = _by4.get("NGC 7380", {}).get("programmes", [{}])[0]
_wn = {x["night"]: x for x in _wiz.get("sessions", [])}
check("OB4 (1.7.2) every dataset carries its capture state and where it came from, Brett's sample flag "
      "keeps a quick look out of the queue, an exposure note turns unrecorded exposures into hours "
      "(marked as from the note), and the one rule for the quiet period still stands",
      lambda: _wiz.get("captureState") == "open" and _wiz.get("captureStateSource") == "capture-state.json"
      and _wiz.get("status") == "capturing" and _wiz.get("sample") is False
      and _by4["M 13"]["programmes"][0]["sample"] is True and _by4["M 13"]["programmes"][0]["status"] == "ready_to_process"
      and _by4["M 13"]["statusCards"][0]["sample"] is True
      and _by4["M 27"]["programmes"][0]["exposureOverride"] == 10 and _by4["M 27"]["programmes"][0]["hours"] == round(20 / 3600, 2)
      and _by4["M 27"]["programmes"][0]["sessions"][0]["integrationFromNote"] is True
      and _by4["M 27"]["programmes"][0]["framesWithoutExposure"] == 2
      and _by4["M 27"]["programmes"][0]["captureState"] == "complete",
      json.dumps([_wiz.get("captureState"), _wiz.get("status"), (_by4.get("M 13") or {}).get("programmes"),
                  (_by4.get("M 27") or {}).get("programmes")])[:900])
check("OB4 (1.7.2) the night panel's facts: one row per night with the morning date, gains, which computer "
      "imported it, how many copies the archive verified, the Day folder keys, the archive's Day folder with "
      "what sits in it (autostacks, working files), and the calibration linked that night in detail",
      lambda: _wn["2026-09-26"]["morning"] == "2026-09-27" and _wn["2026-09-26"]["gains"] == [100]
      and _wn["2026-09-26"]["importedOn"] == ["mac"] and _wn["2026-09-26"]["archived"] == 1
      and _wn["2026-09-26"]["dayKeys"] == [OB4_DK1]
      and _wn["2026-09-26"]["archiveDays"] == ["ZWO Askar Scopes/Wizard Nebula (NGC 7380)/Wizard Nebula Day 1"]
      and _wn["2026-09-26"]["archive"] == {"files": 3, "bytes": 30, "autostacks": 1, "autostackBytes": 10, "workingBytes": 10}
      and _wn["2026-09-26"]["calibration"] == {"darks": 1, "flats": 1, "biases": 1, "shipped": 1,
                                                "darkExposures": [300.0], "darkGains": [100], "flatFilters": ["Ha"], "biasGains": [100]}
      and _wn["2026-09-28"]["calibration"]["darks"] == 0 and _wn["2026-09-28"]["gains"] == [200]
      and "archive" not in _wn["2026-09-28"]
      and _wiz["calibration"]["mode"] == "tracked" and _wiz["calibration"]["nights_without"] == 1
      and _by4["M 13"]["programmes"][0]["calibration"] == {"applies": False, "mode": "inCamera"}
      and next(x for x in _o4["sessions"] if x["target"].startswith("Wizard") and x["night"] == "2026-09-26")["calDetail"]["flatFilters"] == ["Ha"]
      and next(x for x in _o4["sessions"] if x["target"].startswith("Wizard") and x["night"] == "2026-09-26")["morning"] == "2026-09-27",
      json.dumps(_wn)[:1200])
check("OB4 (1.7.2) the page counts facts, not sentences: what was not counted (names, frames, duplicates, rows "
      "that are not light frames), the unknown names themselves, notices with a kind and a count, the scopes "
      "in the contract's order with their kind, what the last scan left on the camera, and the local time",
      lambda: _o4["notCounted"] == {"unknownNames": {"names": 1, "frames": 1}, "noScope": 0, "noNight": 0,
                                    "unreadable": 0, "duplicates": 0, "notLightFrames": 1}
      and _o4["unknownNames"] == ["Old Name Nobody Knows"]
      and any(n["kind"] == "unknown_names" and n["count"] == 1 and n["frames"] == 1 for n in _o4["notices"])
      and all(set(n) == {"kind", "count", "frames", "text"} for n in _o4["notices"])
      and len(_o4["notices"]) == len(_o4["warnings"])
      and [x["id"] for x in _o4["scopes"]] == ["S30P", "FRA400"] and _o4["scopeOrder"] == ["S30P", "FRA400"]
      and [x["kind"] for x in _o4["scopes"]] == ["seestar", "askar"] and [x["order"] for x in _o4["scopes"]] == [1, 5]
      and _o4["pendingImport"]["files"] == 3559 and _o4["pendingImport"]["targets"] == 29
      and _o4["pendingImport"]["failedEject"] is True and _o4["pendingImport"]["camera"] == "Seestar"
      and _o4["pendingImport"]["elsewhere"] == 12 and isinstance(_o4["pendingImport"]["ageHours"], (int, float))
      and isinstance(_o4["generatedAtLocal"], str) and "T" in _o4["generatedAtLocal"]
      and all(k in _o4["reconciliation"][0]["note"] for k in ("1 not counted",)),
      json.dumps([_o4.get("notCounted"), _o4.get("unknownNames"), _o4.get("notices"), _o4.get("scopeOrder"),
                  _o4.get("pendingImport"), _o4.get("generatedAtLocal")])[:1200])
check("OB5 (1.7.5) the scan summary names the targets still on the camera (display names, strings only, at most "
      "12) and the other computer that already holds the rest, and the Observatory carries both",
      lambda: _o4["pendingImport"]["targetNames"] == ["Tadpoles Nebula (IC 410)", "Western Veil Nebula (NGC 6960)"]
      and _o4["pendingImport"]["elsewhereMachine"] == "PC",
      json.dumps(_o4.get("pendingImport"))[:400])
_o5 = probe(OB4.env, "import json, os\n"
            "p = os.path.join(m.STATE_DIR, 'last-scan.json')\n"
            "json.dump({'schema': 'scan-summary/1', 'files': 5, 'targets': 1, 'elsewhere': 0, 'camera': 'ASIAir',"
            " 'failedEject': False, 'seenAt': '2026-10-16T08:50:00+00:00', 'machine': 'Mac'}, open(p, 'w'))\n"
            "old = m.read_scan_summary()\n"
            "json.dump({'schema': 'scan-summary/1', 'files': 5, 'targets': 1, 'targetNames': 'M 31',"
            " 'elsewhereMachine': 7, 'seenAt': '2026-10-16T08:50:00+00:00'}, open(p, 'w'))\n"
            "bad = m.read_scan_summary()\n"
            "m.save_scan_summary(3559, 29, camera='Seestar', failed_eject=True, elsewhere=12, "
            "target_names=['Tadpoles Nebula (IC 410)', 'Western Veil Nebula (NGC 6960)'], elsewhere_machine='PC')\n"
            "print(json.dumps({'old': old, 'bad': bad}))\n")
check("OB5 a 1.7.2 scan summary without the new fields reads as no names and no other computer, and fields of "
      "the wrong type read the same way, never a crash",
      lambda: _o5["old"]["targetNames"] == [] and _o5["old"]["elsewhereMachine"] is None and _o5["old"]["files"] == 5
      and _o5["bad"]["targetNames"] == [] and _o5["bad"]["elsewhereMachine"] is None,
      json.dumps(_o5)[:400])
# ── Chain PH: the phone's copy of the Observatory record (1.7.6) ──────────────
PH = teh.Env("PH", asiair=False, seestar=False)
ph_dir = os.path.join(PH.root, "Mobile Documents", "iCloud~Brettjo~Astrolog", "Documents")
ph_env = dict(PH.env, ASTRO_PHONE_DIR=ph_dir, ASTRO_SHIP_FOLDER="mac")
os.makedirs(os.path.join(PH.root, "Mobile Documents"))                 # iCloud Drive is on
os.makedirs(PH.state, exist_ok=True)
_ph_doc = {"schema": "observatory/1", "generatedAtIso": "2026-10-20T03:38:00+00:00", "generatedAt": "20 Oct",
           "targets": [{"id": "M31"}], "scopes": [], "sessions": [], "totals": {}, "health": [],
           "reconciliation": [], "warnings": [], "sources": {}}
with open(os.path.join(PH.state, "observatory.json"), "w") as f:
    json.dump(_ph_doc, f)
_ph = probe(ph_env, "import json, os\n"
            "a = m.publish_phone(); b = m.publish_phone()\n"
            "p = os.path.join(m.PHONE_DIR, 'observatory.json')\n"
            "got = json.load(open(p))\n"
            "print(json.dumps({'a': a, 'b': b, 'same': got == json.load(open(os.path.join(m.STATE_DIR, 'observatory.json'))),"
            " 'files': sorted(os.listdir(m.PHONE_DIR)), 'tmp': [x for x in os.listdir(m.PHONE_DIR) if x.endswith('.tmp')]}))\n")
check("PH (1.7.6) publish_phone writes this computer's Observatory record, and only that, into the phone folder "
      "(created under Mobile Documents), atomically; a second call with the same record writes nothing",
      lambda: _ph["a"] is True and _ph["b"] is False and _ph["same"] is True
      and _ph["files"] == ["observatory.json"] and _ph["tmp"] == [], json.dumps(_ph)[:400])
_ph_pc = os.path.join(PH.archive, "_verify", "pc"); os.makedirs(_ph_pc, exist_ok=True)
_ph_pub = dict(_ph_doc); _ph_pub["generatedAtIso"] = _dt.now(_tz.utc).isoformat(timespec="seconds"); _ph_pub["targets"] = [{"id": "M42"}]
with open(os.path.join(_ph_pc, "observatory.json"), "w") as f:
    json.dump(_ph_pub, f)
_ph2 = probe(ph_env, "import json, os\n"
             "s = m.observatory_stamp()\n"
             "got = json.load(open(os.path.join(m.PHONE_DIR, 'observatory.json')))\n"
             "print(json.dumps({'stamp': s, 'ids': [t['id'] for t in got['targets']], 'from': (got.get('servedFrom') or {}).get('machine'),"
             " 'arch': sorted(os.listdir(os.path.join(m.ARCHIVE_MOUNT, '_verify', 'pc')))}))\n")
check("PH the PC's newer published copy reaches the phone through the panel's stamp check (observatory_stamp), "
      "labelled as the PC's; nothing is written on the archive",
      lambda: _ph2["stamp"] == _ph_pub["generatedAtIso"] and _ph2["ids"] == ["M42"] and _ph2["from"] == "PC"
      and _ph2["arch"] == ["observatory.json"], json.dumps(_ph2)[:400])
_ph3 = probe(dict(PH.env, ASTRO_SHIP_FOLDER="mac"), "import os\n"
             "print(json.dumps({'dir': m.PHONE_DIR, 'wrote': m.publish_phone(),"
             " 'nothing': not os.path.exists(os.path.join(m.TEST_ROOT, 'unset', 'ASTRO_PHONE_DIR'))}))\n")
_ph4 = probe(dict(ph_env, ASTRO_PHONE_DIR=os.path.join(PH.root, "no-icloud", "iCloud~Brettjo~Astrolog", "Documents")),
             "import os\nprint(json.dumps({'wrote': m.publish_phone(), 'made': os.path.exists(os.path.join(m.TEST_ROOT, 'no-icloud'))}))\n")
check("PH with no phone folder configured (the PC, or a Mac without the app) nothing is written anywhere; with "
      "iCloud Drive off (no Mobile Documents folder) nothing is created either",
      lambda: _ph3["wrote"] is False and _ph3["nothing"] is True
      and _ph4["wrote"] is False and _ph4["made"] is False, json.dumps([_ph3, _ph4])[:400])

# a sample that has a master stays a project, with a notice saying so; the scan summary is confined and read back
with open(os.path.join(_pc4, "inventory-E-20261009T033000Z.jsonl"), "a") as f:
    f.write(json.dumps(dict(pl_inv_row("S30P/Hercules Cluster (M 13)/masterLight.xisf", "S30P", "Hercules Cluster (M 13)"), size=5)) + "\n")
_o4b = probe(OB4.env, "st = m.State()\nextra, names = m.projects_inputs(st)\n"
             f"d = m.build_observatory(st, extra, today='{PL_TODAY}', custom_names=names)\n"
             "import os\n"
             "print(json.dumps({'m13': [p for t in d['targets'] if t['id'] == 'M13' for p in t['programmes']],"
             " 'notes': [n for n in d['notices'] if n['kind'] == 'capture_state_bad'],"
             " 'read': m.read_scan_summary(), 'file': sorted(os.listdir(m.STATE_DIR))}))\n")
check("OB4 (1.7.2) a sample with a master of Brett's stays a project (a notice says so) and the scan summary is "
      "one small file in the state folder that reads back as it was written",
      lambda: _o4b["m13"][0]["sample"] is False and _o4b["m13"][0]["status"] == "in_progress"
      and any("marks M13|S30P|Shinfield as a sample" in n["text"] for n in _o4b["notes"])
      and _o4b["read"]["files"] == 3559 and _o4b["read"]["targets"] == 29
      and "last-scan.json" in _o4b["file"],
      json.dumps(_o4b)[:900])
shutil.rmtree(OB4.root, ignore_errors=True)

# the review round of 17 Oct: a quick look never drives its project's state; gain travels in the
# snapshot; an unreadable row is not also "not a light frame"; a corrupt scan summary never crashes
OB4c = pl_pc_env("OB4c", {
    "a1": pl_snap_row("NGC 7380", "NGC 7380 - Wizard Nebula", "2026-08-01", "a1" * 32, exposureSeconds=300.0, **OB4_ASI),
    "a2": pl_snap_row("NGC 7380", "NGC 7380 - Wizard Nebula", "2026-08-02", "a2" * 32),     # the same object on the S30P, old, a sample
    "bad": {"filename": "x.fit", "sourceType": ["not", "a", "string"], "night": "2026-08-03"},
}, at="2026-10-09T08:00:00Z")
_pc4c = os.path.join(OB4c.archive, "_verify", "pc"); os.makedirs(_pc4c, exist_ok=True)
with open(os.path.join(_pc4c, "inventory-E-20261009T033000Z.jsonl"), "w") as f:
    f.write(json.dumps(pl_inv_row("ZWO Askar Scopes/Wizard Nebula (NGC 7380)/masterLight_FRA400.xisf", "ZWO Askar Scopes", "Wizard Nebula (NGC 7380)")) + "\n")
with open(os.path.join(_pc4c, "inventory-E.status.json"), "w") as f:
    json.dump({"schema": "inventory-status/1", "generation": "20261009T033000Z"}, f)
with open(os.path.join(OB4c.state, "capture-state.json"), "w") as f:
    json.dump({"NGC7380|S30P|Shinfield": "sample"}, f)
with open(os.path.join(OB4c.state, "last-scan.json"), "w") as f:
    json.dump({"schema": "scan-summary/1", "files": "abc", "targets": None, "camera": 7, "seenAt": "garbage"}, f)
_o4c = probe(OB4c.env, "st = m.State()\nextra, names = m.projects_inputs(st)\n"
             f"d = m.build_projects(st, extra, today='{PL_TODAY}', custom_names=names)\n"
             f"o = m.build_observatory(st, extra, today='{PL_TODAY}', custom_names=names)\n"
             "print(json.dumps({'p': [(p['target_id'], p['status'], p['to_process'], [(e['scope'], e['status'], e['sample'], e['capture_state_source']) for e in p['datasets']]) for p in d['projects']],"
             " 't': [(t['id'], t['state'], t['pendingProgrammes']) for t in o['targets']], 'nc': o['notCounted'],"
             " 'pend': o['pendingImport'], 'gain': 'gain' in m._SNAPSHOT_FIELDS, 'n': len(o['notices']) == len(o['warnings'])}))\n")
check("OB4 (review) a quick look never drives its project's state or the target's (the FRA400 master makes "
      "it In progress, the S30P sample stays out of the pending count and names capture-state.json as its "
      "source); gain travels in the snapshot; an unreadable row is counted once; a corrupt last-scan.json reads "
      "as zeros, never a crash; one notice per warning",
      lambda: _o4c["p"] == [["NGC7380", "in_progress", False, [["FRA400", "in_progress", False, "rule"], ["S30P", "ready_to_process", True, "capture-state.json"]]]]
      and _o4c["t"] == [["NGC7380", "processing", 1]]
      and _o4c["nc"]["unreadable"] == 1 and _o4c["nc"]["notLightFrames"] == 0
      and _o4c["pend"]["files"] == 0 and _o4c["pend"]["camera"] is None and _o4c["pend"]["ageHours"] is None
      and _o4c["gain"] is True and _o4c["n"] is True,
      json.dumps(_o4c)[:900])
shutil.rmtree(OB4c.root, ignore_errors=True)

# ═══════════════ CHAIN AA: --adopt-archive (1.7.3) ═══════════════════════════
# Frames this computer imported and verified that reached the archive without
# a ship (moved there by hand in the summer): the ledger catches up with proof
# from the PC's inventory hashes, or a read-back over the share; nothing on the
# archive is created, renamed or removed; a dry run writes nothing anywhere.
import hashlib as _adh
AD = teh.Env("AD", asiair=False, seestar=True)
AD.env.update(D7_MAC)
ad_arch = AD.archive
os.makedirs(os.path.join(ad_arch, "S30P", "Dumbbell by hand"), exist_ok=True)
for st in ("20260801-224402", "20260801-225402", "20260802-224402", "20260802-225402", "20260803-224402"):
    AD.add_seestar_sub("M 27", st)
AD.run("--no-ship")
_adl = AD.ledger()["files"]
_ad_rows = sorted((k, e) for k, e in _adl.items() if e.get("sourceType") == "sub")
check("AA five subs imported and verified, none located on the archive yet",
      len(_ad_rows) == 5 and all(e.get("verifiedAtImport") and not e.get("archiveLocation") for _k, e in _ad_rows),
      json.dumps(_ad_rows)[:400])
def _ad_sha(p):
    h = _adh.sha256()
    with open(p, "rb") as f:
        h.update(f.read())
    return h.hexdigest()
# A: moved by hand, the PC hashed it; B: moved by hand, not hashed yet; C: moved by hand but the
# archive's copy differs (a re-save); D: still here AND a copy on the archive, hashed; E: gone, nowhere
_ad = {}
for tag, (k, e) in zip("ABCDE", _ad_rows):
    src = os.path.join(e["dest"], e["filename"])
    dst = os.path.join(ad_arch, "S30P", "Dumbbell by hand", e["filename"])
    if tag in "ABC":
        os.replace(src, dst)
    elif tag == "D":
        shutil.copy(src, dst)
    else:
        os.remove(src)
    if tag == "C":                        # the same size, different bytes (a re-save)
        with open(dst, "r+b") as f:
            f.seek(-1, 2); last = f.read(1); f.seek(-1, 2); f.write(b"\x01" if last != b"\x01" else b"\x02")
    _ad[tag] = (k, e, dst)
_ad_pc = os.path.join(ad_arch, "_verify", "pc"); os.makedirs(_ad_pc, exist_ok=True)
with open(os.path.join(_ad_pc, "inventory-E-20261018T030000Z.jsonl"), "w", encoding="utf-8") as f:
    for tag in "ABCD":
        k, e, dst = _ad[tag]
        row = {"schema": "inventory-row/1", "relpath": "S30P/Dumbbell by hand/" + e["filename"], "camera": "S30P",
               "target": "Dumbbell by hand", "size": os.path.getsize(dst), "mtimeNs": 1, "kind": "light",
               "retired": False, "sha256": None, "hashedAt": None}
        if tag in "AD":
            row["sha256"], row["hashedAt"], row["hashedBy"] = _ad_sha(dst), "2026-10-18T03:10:00+00:00", "pc"
        if tag == "C":
            row["sha256"], row["hashedAt"] = _ad_sha(dst), "2026-10-18T03:10:00+00:00"     # the archive's bytes, not the ledger's
        f.write(json.dumps(row) + "\n")
with open(os.path.join(_ad_pc, "inventory-E.status.json"), "w") as f:
    json.dump({"schema": "inventory-status/1", "generation": "20261018T030000Z"}, f)
ADN = teh.no_delete_env(AD.root, ad_arch)
_ad_before_tree = d7_tree(ad_arch)
_ad_before = json.dumps(AD.ledger(), sort_keys=True)
r = AD.run("--adopt-archive", extra_env=ADN)
_ad_mlog = os.path.join(ad_arch, "_verify", "mac", "shipped.jsonl")
check("AA a dry run reads the inventory and says what it would prove (2 by the PC's hash, 1 not hashed "
      "yet, 1 whose bytes differ, 1 not on the archive) and writes nothing: not the ledger, not the "
      "ship log, nothing on the archive",
      r.returncode == 0 and "Proven on the archive: 2" in r.stdout and "by the PC's hash: 2" in r.stdout
      and "not yet hashed by the PC: 1" in r.stdout and "--hash-here" in r.stdout
      and "Bytes differ: 1" in r.stdout and "Not on the archive at all: 1" in r.stdout
      and "Dry run: nothing written" in r.stdout
      and json.dumps(AD.ledger(), sort_keys=True) == _ad_before and not os.path.exists(_ad_mlog)
      and d7_tree(ad_arch) == _ad_before_tree,
      r.stdout[-900:] + r.stderr[-300:])
r = AD.run("--adopt-archive", "--apply", extra_env=ADN)
_adl2 = AD.ledger()["files"]
_ad_after_tree = d7_tree(ad_arch)
_new = sorted(set(_ad_after_tree) - set(_ad_before_tree))
_gone = sorted(set(_ad_before_tree) - set(_ad_after_tree))
_changed = sorted(k for k in _ad_before_tree if k in _ad_after_tree and _ad_before_tree[k] != _ad_after_tree[k])
_shipped = d7_rows(_ad_mlog, "shipped")
check("AA --apply records the two proven frames as a ship records an adopted copy: archiveLocation with "
      "the archive's separators, archiveShippedAt, archiveVerifiedAt from the PC's hash time, adoptedFromArchive; "
      "a 'shipped' row (adopted, by the PC's hash) in this computer's own log; the other three untouched",
      r.returncode == 0 and "Recorded 2 frame(s)" in r.stdout
      and all(_adl2[_ad[t][0]].get("archiveLocation") == "S30P\\Dumbbell by hand\\" + _ad[t][1]["filename"]
              and _adl2[_ad[t][0]].get("archiveShippedAt") and _adl2[_ad[t][0]].get("archiveVerifiedAt") == "2026-10-18T03:10:00+00:00"
              and _adl2[_ad[t][0]].get("archiveVerifiedBy") == "pc-inventory"
              and _adl2[_ad[t][0]].get("adoptedFromArchive", {}).get("by") == "pc-inventory-hash" for t in "AD")
      and all(not _adl2[_ad[t][0]].get("archiveLocation") and not _adl2[_ad[t][0]].get("archiveVerifiedAt") for t in "BCE")
      and len(_shipped) == 2 and all(x.get("adopted") is True and x.get("adoptedBy") == "pc-inventory-hash"
                                     and x.get("sha256") == _adl2[_ad["A"][0]]["sha256"] or x.get("sha256") == _adl2[_ad["D"][0]]["sha256"]
                                     for x in _shipped),
      json.dumps([{t: {k: _adl2[_ad[t][0]].get(k) for k in ("archiveLocation", "archiveShippedAt", "archiveVerifiedAt", "adoptedFromArchive")} for t in "ABCDE"}, _shipped])[:900]
      + r.stdout[-400:])
check("AA nothing on the archive is created, renamed or removed apart from this computer's own log and "
      "record in _verify/mac (the share's rights refused nothing)",
      not _gone and all(p.startswith("_verify/mac/") for p in _new + _changed) and d7_bad(AD.root) == [],
      f"new={_new} changed={_changed} gone={_gone} denied={teh.denied(AD.root)}"[:600])
r = AD.run("--adopt-archive", "--apply", "--hash-here", extra_env=ADN)
_adl3 = AD.ledger()["files"]
_shipped3 = d7_rows(_ad_mlog, "shipped")
check("AA --hash-here reads the un-hashed copy back over the share and adopts it on this computer's own "
      "read-back (located and shipped, verification left to the PC's sweep); the differing copy is never "
      "adopted; the missing one stays missing",
      r.returncode == 0 and "read back here: 1" in r.stdout and "Bytes differ: 1" in r.stdout
      and _adl3[_ad["B"][0]].get("archiveLocation") and not _adl3[_ad["B"][0]].get("archiveVerifiedAt")
      and _adl3[_ad["B"][0]].get("adoptedFromArchive", {}).get("by") == "mac-readback"
      and not _adl3[_ad["C"][0]].get("archiveLocation") and not _adl3[_ad["E"][0]].get("archiveLocation")
      and len(_shipped3) == 3 and d7_bad(AD.root) == [],
      r.stdout[-700:] + json.dumps({t: _adl3[_ad[t][0]].get("archiveLocation") for t in "BCE"}))
r = AD.run("--ship", "--dry-run", extra_env=ADN)
check("AA after adoption the ship has nothing to send: the frame still on this computer whose copy was "
      "adopted is not shipped again (no second copy on the archive)",
      r.returncode == 0 and "Ship: 0 file(s)" in r.stdout and _adl3[_ad["D"][0]].get("archiveLocation"),
      r.stdout[-600:])
r = AD.run("--adopt-archive", extra_env=ADN)
check("AA a second dry run finds nothing more to prove for the adopted ones (idempotent)",
      r.returncode == 0 and "Proven on the archive: 0" in r.stdout and "Bytes differ: 1" in r.stdout
      and "Not on the archive at all: 1" in r.stdout, r.stdout[-400:])
shutil.rmtree(AD.root, ignore_errors=True)

# ═══════════════ CHAIN OT: two importing computers, one truth (1.7.1) ════════
# The PC imports too (Brett, 16 Oct 2026). Each computer keeps its own ledger;
# the archive carries each one's record; a scan reads the OTHER computer's
# record so a frame it verified is not offered again, named for what it is,
# and never a proof for a clear or a discard here.
import hashlib as _hl
from datetime import datetime as _otdt, timezone as _ottz, timedelta as _ottd

def _ot_sha(p):
    h = _hl.sha256()
    with open(p, "rb") as f:
        h.update(f.read())
    return h.hexdigest()

OT = teh.Env("OT", asiair=True, seestar=True)          # the PC: ASTRO_SHIP_FOLDER=pc
OT.env.update({"ASTRO_SHIP_FOLDER": "pc", "ASTRO_SHIP_LOG": "shipped-pc.jsonl", "ASTRO_MACHINE_ID": "pc"})
for _r in ("ZWO Askar Scopes", "S30P"):
    os.makedirs(os.path.join(OT.archive, _r), exist_ok=True)
_ot_macdir = os.path.join(OT.archive, "_verify", "mac"); os.makedirs(_ot_macdir, exist_ok=True)
# the camera: M 81 (three lights: one the Mac verified AND the PC checked on the
# archive, one the Mac verified but hasn't shipped, one new), NGC 7000 (the
# Mac only has a BASELINE row: never copied, so new), M 101 (new; on the Mac's
# never-import list), MYSTERY 7 (unknown here; the Mac named it)
_ot_m81 = [OT.add_light("Plan", "M 81", f"000{i}", dt=f"20261001-22000{i}") for i in (1, 2, 3)]
_ot_n7000 = OT.add_light("Plan", "NGC 7000", "0001", dt="20261002-220000")
_ot_m101 = OT.add_light("Live", "M 101", "0001", dt="20261002-221000")
_ot_myst = OT.add_light("Plan", "MYSTERY 7", "0001", dt="20261003-220000")
_ot_dark = OT.add_cal("Dark", "300.0s", "20261001-090000")          # in the Mac's Library
_ot_flat = OT.add_cal("Flat", "20.0ms", "20261001-100000", filt="LUltimate")   # new to both
# the Seestar S30 Pro: M 42 (sub A the Mac verified, sub B new, the stack the
# Mac verified, sub C binned on the Mac, sub D that another Seestar model
# imported at the same path and size), M 33 (every sub the Mac verified)
_ot_a = OT.add_seestar_sub("M 42", "20261001-210000")
_ot_b = OT.add_seestar_sub("M 42", "20261001-210500")
_ot_c = OT.add_seestar_sub("M 42", "20261001-211000")
_ot_d = OT.add_seestar_sub("M 42", "20261001-211500")
_ot_stack = OT.add_seestar_stack("M 42", 40, "20261001-213000")
_ot_m33 = [OT.add_seestar_sub("M 33", f"20261002-21{i}000") for i in (0, 1)]
_ot_cam = os.path.join(OT.root, "ASIAIR")
def _ot_rel(p, root):
    return os.path.relpath(p, root).replace("\\", "/")
def _ot_row(p, root, **kw):
    r = {"filename": os.path.basename(p), "size": os.path.getsize(p), "sha256": "a" * 64,
         "origin": "import", "verifiedAtImport": True}
    r.update(kw); return r
_ot_files = {
    _ot_rel(_ot_m81[0], _ot_cam): _ot_row(_ot_m81[0], _ot_cam, target="M 81", sourceType="Plan",
                                         archiveVerifiedAt="2026-10-05T030000"),
    _ot_rel(_ot_m81[1], _ot_cam): _ot_row(_ot_m81[1], _ot_cam, target="M 81", sourceType="Plan"),
    _ot_rel(_ot_n7000, _ot_cam): _ot_row(_ot_n7000, _ot_cam, target="NGC 7000", sourceType="Plan",
                                        origin="baseline", verifiedAtImport=False),
    _ot_rel(_ot_a, OT.svol): _ot_row(_ot_a, OT.svol, target="M 42", device="seestar",
                                    camera="ZWO Seestar S30 Pro", sourceType="sub", archiveVerifiedAt="2026-10-05T030000"),
    _ot_rel(_ot_stack, OT.svol): _ot_row(_ot_stack, OT.svol, target="M 42", device="seestar",
                                        camera="ZWO Seestar S30 Pro", sourceType="stack"),
    _ot_rel(_ot_d, OT.svol): _ot_row(_ot_d, OT.svol, target="M 42", device="seestar",
                                    camera="ZWO Seestar S50", sourceType="sub"),
}
for p in _ot_m33:
    _ot_files[_ot_rel(p, OT.svol)] = _ot_row(p, OT.svol, target="M 33", device="seestar",
                                            camera="ZWO Seestar S30 Pro", sourceType="sub",
                                            archiveVerifiedAt="2026-10-05T030000")
_ot_snapshot = {
    "schema": "ledger-snapshot/1", "machine": "Mac", "machineId": "mac", "machineUid": "mac-uid",
    "at": _otdt.now(_ottz.utc).isoformat(timespec="seconds"),
    "files": _ot_files, "calibration": {},
    "library": {_ot_rel(_ot_dark, _ot_cam): {"frameType": "Dark", "size": os.path.getsize(_ot_dark),
                                             "verifiedAtImport": True}},
    "discarded": {f"{_ot_rel(_ot_c, OT.svol)}|{os.path.getsize(_ot_c)}": {
        "relpath": _ot_rel(_ot_c, OT.svol), "size": os.path.getsize(_ot_c), "sha256": _ot_sha(_ot_c),
        "camera": "ZWO Seestar S30 Pro", "stillOnCamera": False}},
    "customNames": {"MYSTERY 7": "Fuzzy Blob"}, "skiplist": ["M 101"], "equipment": {"1000": "Big Scope"},
}
_ot_snap_path = os.path.join(_ot_macdir, "ledger-snapshot.json")
with open(_ot_snap_path, "w", encoding="utf-8") as f:
    json.dump(_ot_snapshot, f)

_OT_SCAN = ("st = m.State()\n"
            "a = m.scan_camera(st); s = m.scan_seestar(st)\n"
            "def tg(name): return next(t for t in a['targets'] if t['name'] == name)\n"
            "def sg(name): return next(t for t in s['targets'] if t['name'] == name)\n"
            "print(json.dumps({"
            " 'm81_new': [f['filename'] for f in tg('M 81')['new']],"
            " 'm81_else': len(tg('M 81')['elsewhere']), 'm81_arch': tg('M 81')['elsewhere_archived'],"
            " 'm81_who': tg('M 81')['elsewhere_machine'],"
            " 'n7000_new': len(tg('NGC 7000')['new']), 'n7000_else': len(tg('NGC 7000')['elsewhere']),"
            " 'm101_new': len(tg('M 101')['new']), 'm101_skip': tg('M 101')['other_skip'],"
            " 'dark_other': bool(next(c for c in a['calibration'] if c['frame_type']=='Dark').get('other')),"
            " 'flat_other': bool(next(c for c in a['calibration'] if c['frame_type']=='Flat').get('other')),"
            " 'other': a['other'],"
            " 'm42_new': sorted(os.path.basename(f['path']) for f in sg('M 42')['new']),"
            " 'm42_new_stacks': len(sg('M 42')['new_stacks']),"
            " 'm42_else': sorted(os.path.basename(f['path']) for f in sg('M 42')['elsewhere']),"
            " 'm33_new': len(sg('M 33')['new']), 'm33_else': len(sg('M 33')['elsewhere']),"
            " 'myst': m.display_name_for(st, 'MYSTERY 7')}))\n")
_ot = probe(OT.env, _OT_SCAN)
check("OT the ASIAir scan reads the Mac's record: the two M 81 lights the Mac VERIFIED are not new "
      "(one of them checked on the archive), the third is; the Mac's BASELINE row proves nothing, "
      "so NGC 7000 stays new; M 101 is new and flagged as on the Mac's never-import list",
      lambda: _ot["m81_new"] == [os.path.basename(_ot_m81[2])] and _ot["m81_else"] == 2 and _ot["m81_arch"] == 1
      and _ot["m81_who"] == "Mac" and _ot["n7000_new"] == 1 and _ot["n7000_else"] == 0
      and _ot["m101_new"] == 1 and _ot["m101_skip"] is True, json.dumps(_ot)[:600])
check("OT the calibration frames know the Mac's Library (the dark), a flat new to both does not; the scan "
      "names the record (machine, when, not stale)",
      lambda: _ot["dark_other"] is True and _ot["flat_other"] is False
      and _ot["other"]["machine"] == "Mac" and _ot["other"]["stale"] is False and _ot["other"]["files"] == len(_ot_files),
      json.dumps(_ot)[:600])
check("OT the Seestar scan: sub A and the stack the Mac verified are not new, sub B is; sub C binned on the "
      "Mac (its bytes match) is neither new nor 'elsewhere'; sub D that another Seestar model holds at "
      "the same path and size is new here (a row belongs to one camera); M 33 is all the Mac's",
      lambda: _ot["m42_new"] == sorted([os.path.basename(_ot_b), os.path.basename(_ot_d)])
      and _ot["m42_new_stacks"] == 0
      and _ot["m42_else"] == sorted([os.path.basename(_ot_a), os.path.basename(_ot_stack)])
      and _ot["m33_new"] == 0 and _ot["m33_else"] == 2, json.dumps(_ot)[:600])
check("OT a name the Mac already saved is used here without a question; a scan only reads it (nothing "
      "written by a read-only path), the import below saves it",
      lambda: _ot["myst"] == "MYSTERY 7 - Fuzzy Blob"
      and not os.path.isfile(os.path.join(OT.state, "custom-names.json")),
      json.dumps(_ot.get("myst")))
r = OT.run("--scan-only")
check("OT --scan-only (the watcher's line) counts what the Mac already holds",
      "already backed up by the Mac" in r.stdout, r.stdout[-400:])
# switched off, or no record: everything is new again (more copying is the safe direction)
_ot_off = probe(dict(OT.env, ASTRO_OTHER_RECORD="off"), _OT_SCAN)
check("OT ASTRO_OTHER_RECORD=off: the record is ignored, every frame is new, no 'elsewhere'",
      lambda: len(_ot_off["m81_new"]) == 3 and _ot_off["m81_else"] == 0 and _ot_off["other"] is None
      and _ot_off["m33_new"] == 2, json.dumps(_ot_off)[:400])
_ot_old = dict(_ot_snapshot); _ot_old["at"] = (_otdt.now(_ottz.utc) - _ottd(days=3)).isoformat(timespec="seconds")
with open(_ot_snap_path, "w", encoding="utf-8") as f:
    json.dump(_ot_old, f)
_ot_stale = probe(OT.env, _OT_SCAN)
_ot_new_schema = dict(_ot_snapshot); _ot_new_schema["schema"] = "ledger-snapshot/2"
with open(_ot_snap_path, "w", encoding="utf-8") as f:
    json.dump(_ot_new_schema, f)
_ot_newer = probe(OT.env, _OT_SCAN)
with open(_ot_snap_path, "w", encoding="utf-8") as f:
    json.dump(_ot_snapshot, f)
check("OT an old record is still read but said to be stale; one from a newer importer is not read at all "
      "(every frame new), and the scan says so",
      lambda: _ot_stale["other"]["stale"] is True and _ot_stale["m81_else"] == 2
      and _ot_newer["other"] is None and len(_ot_newer["m81_new"]) == 3,
      json.dumps([_ot_stale.get("other"), _ot_newer.get("other"), _ot_newer.get("m81_new")])[:400])

# the import: copies only what is new here, says what the Mac holds, never asks
# the question the Mac answered; then files into the (local) archive at once,
# leaves THIS computer's record and its receipts there
r = OT.run(stdin="n\n")
_ot_led = OT.ledger()
_ot_keys = set(_ot_led["files"])
check("OT the import copies the new frames only: M 81's third light, NGC 7000, M 101, MYSTERY 7 (as Fuzzy "
      "Blob, no 'Unknown target' question); not the two M 81 lights the Mac verified",
      r.returncode == 0 and _ot_rel(_ot_m81[2], _ot_cam) in _ot_keys and _ot_rel(_ot_n7000, _ot_cam) in _ot_keys
      and _ot_rel(_ot_m101, _ot_cam) in _ot_keys and _ot_rel(_ot_myst, _ot_cam) in _ot_keys
      and _ot_rel(_ot_m81[0], _ot_cam) not in _ot_keys and _ot_rel(_ot_m81[1], _ot_cam) not in _ot_keys
      and "Unknown target" not in r.stdout
      and "Using the Mac's name: MYSTERY 7" in r.stdout
      and json.load(open(os.path.join(OT.state, "custom-names.json"))).get("MYSTERY 7") == "Fuzzy Blob"
      and "Fuzzy Blob" in str(_ot_led["files"][_ot_rel(_ot_myst, _ot_cam)].get("displayName")),
      f"rc={r.returncode} keys={sorted(_ot_keys)[:8]} " + r.stdout[-500:])
check("OT ...and says what it skipped: 'already backed up by the Mac (1 verified on the archive)'",
      "already backed up by the Mac" in r.stdout and "verified on the archive" in r.stdout, r.stdout[-600:])
_ot_sub_keys = {k for k in _ot_keys if k.startswith("MyWorks/")}
check("OT the Seestar import copies sub B and sub D, not sub A, the stack or binned sub C; M 33 nothing",
      _ot_rel(_ot_b, OT.svol) in _ot_keys and any(k.startswith(_ot_rel(_ot_d, OT.svol)) for k in _ot_keys)
      and _ot_rel(_ot_a, OT.svol) not in _ot_keys and _ot_rel(_ot_stack, OT.svol) not in _ot_keys
      and _ot_rel(_ot_c, OT.svol) not in _ot_keys and not any("M 33_sub" in k for k in _ot_keys),
      str(sorted(_ot_sub_keys)))
_ot_pc_snap = os.path.join(OT.archive, "_verify", "pc", "ledger-snapshot.json")
_ot_pcs = json.load(open(_ot_pc_snap)) if os.path.isfile(_ot_pc_snap) else {}
check("OT the import filed into the archive at once and left THIS computer's record there, with every row "
      "(lights and the Seestar's sub), the Library, the binned register, the never-import list and the "
      "scopes, and each row says whether its copy was verified",
      lambda: _ot_pcs.get("schema") == "ledger-snapshot/1" and _ot_pcs.get("machineId") == "pc"
      and _ot_rel(_ot_b, OT.svol) in _ot_pcs["files"] and _ot_rel(_ot_myst, _ot_cam) in _ot_pcs["files"]
      and _ot_pcs["files"][_ot_rel(_ot_myst, _ot_cam)].get("verifiedAtImport") is True
      and isinstance(_ot_pcs.get("library"), dict) and _ot_rel(_ot_dark, _ot_cam) in _ot_pcs["library"]
      and isinstance(_ot_pcs.get("discarded"), dict) and isinstance(_ot_pcs.get("skiplist"), list)
      and isinstance(_ot_pcs.get("equipment"), dict),
      json.dumps({k: (len(v) if isinstance(v, (dict, list)) else v) for k, v in _ot_pcs.items()})[:400])
_ot_rc = os.path.join(OT.archive, "_verify", "pc", "receipts")
_ot_rcs = [os.path.join(dp, f) for dp, _d, fs in os.walk(_ot_rc) for f in fs] if os.path.isdir(_ot_rc) else []
check("OT the AstroLog receipts of this import are published into this computer's own _verify folder on "
      "the archive (one per scope, the same files as in Documents)",
      lambda: len(_ot_rcs) >= 2 and all(json.load(open(p)).get("version") == 1 for p in _ot_rcs)
      and any("asiair-" in os.path.basename(p) for p in _ot_rcs) and any("seestar-" in os.path.basename(p) for p in _ot_rcs),
      str(_ot_rcs))
r2 = OT.run("--ship")
_ot_rcs2 = [os.path.join(dp, f) for dp, _d, fs in os.walk(_ot_rc) for f in fs]
check("OT a second ship publishes nothing twice (exclusive create, by name)",
      r2.returncode == 0 and sorted(_ot_rcs2) == sorted(_ot_rcs), r2.stdout[-300:])

# discard: never bins what the Mac holds verified; the SAFE clear is the Mac's to do
r = OT.run("--discard", "M 33", stdin="DISCARD\n", extra_env={"ASTRO_STDIN_PROMPTS": "1"})
check("OT DISCARD on a Seestar target the Mac verified is refused — 'backed up by the Mac ... clear it from "
      "the Mac' — and nothing leaves the camera",
      r.returncode == 1 and "backed up by the Mac" in r.stdout + r.stderr
      and "clear it from the Mac" in r.stdout + r.stderr
      and all(os.path.isfile(p) for p in _ot_m33), (r.stdout + r.stderr)[-400:])
r = OT.run("--discard", "M 42", "--dry-run")
check("OT a mix (sub C never backed up anywhere, A and the stack the Mac's, B and D this computer's): the "
      "dry run offers sub C only and says the Mac's stay",
      "backed up by the Mac" in r.stdout and os.path.basename(_ot_c) in r.stdout
      and os.path.basename(_ot_a) not in r.stdout.split("would delete")[-1]
      and "would delete" in r.stdout and r.stdout.count("would delete: ") == 1, r.stdout[-700:])

# the SAFE gate itself is untouched: only THIS ledger's verified copies prove a clear
_ot_safe = probe(OT.env, "st = m.State(); s = m.scan_seestar(st)\n"
                 "g = next(x for x in m.seestar_groups(st, s) if x['id'] == 'M 33_sub')\n"
                 "un, _b = m._seestar_unproven_files(st, s['volume'], g['dirs'], exempt_superseded=g['exempt'], camera=s['camera'])\n"
                 "print(json.dumps({'unproven': len(un)}))\n")
check("OT the SAFE gate still judges by this ledger alone: M 33's subs (the Mac's) are UNPROVEN here, so no "
      "clear from this computer, whatever the record says",
      lambda: _ot_safe.get("unproven") == 2, json.dumps(_ot_safe))

# calibration linked on both computers is one set, not two
_ot_cal = probe(OT.env, "idx = m._calibration_index(["
                "{'Autorun/Dark/d1.fit': {'frameType': 'Dark', 'linkedInto': ['T/Day 5'], 'shipped': ['T/Day 5']},"
                " 'Autorun/Dark/d2.fit': {'frameType': 'Dark', 'linkedInto': ['T/Day 5']}},"
                "{'Autorun/Dark/d1.fit': {'frameType': 'Dark', 'linkedInto': ['T/Day 1'], 'shipped': []},"
                " 'Autorun/Flat/f1.fit': {'frameType': 'Flat', 'linkedInto': ['T/Day 1']}}])\n"
                "print(json.dumps(m._calibration_for(idx, ['T/Day 5', 'T/Day 1'])))\n")
check("OT the same dark linked by both computers (into their own Day folders of one night) counts once: "
      "2 darks, 1 flat, 1 shipped",
      lambda: _ot_cal == {"biases": 0, "darks": 2, "flats": 1, "shipped": 1}, json.dumps(_ot_cal))

# the Day a night was started into, by EITHER computer, is where it stays
_ot_tdir = os.path.join(OT.archive, "ZWO Askar Scopes", "Seed Target")
os.makedirs(os.path.join(_ot_tdir, "Seed Target Day 3"), exist_ok=True)      # the Mac's started, set-aside copy left it empty
with open(os.path.join(_ot_macdir, "shipped.jsonl"), "a", encoding="utf-8") as f:
    f.write(json.dumps({"schema": "ship-row/1", "state": "started", "machine": "Mac",
                        "relpath": "ZWO Askar Scopes\\Seed Target\\Seed Target Day 3\\Light_Seed_300.0s_Bin1_gain200_20260901-220000.fit",
                        "size": 1, "sha256": "b" * 64}) + "\n")
_ot_seed = probe(OT.env, "arch = m.ARCHIVE_MOUNT\n"
                 "seeds = m._ship_seeds(m._all_ship_rows(arch, m.own_ship_rows(arch)), arch)\n"
                 "tdir = os.path.normcase(os.path.normpath(os.path.join(arch, 'ZWO Askar Scopes', 'Seed Target')))\n"
                 "dm = m._DayMap(tdir, False, seed=seeds.get(tdir))\n"
                 "print(json.dumps({'day': dm.day_for('2026-09-01'), 'next': dm.day_for('2026-09-02')}))\n")
check("OT a night the Mac's ship started into Day 3 (and the sweep emptied) goes back into Day 3 from this "
      "computer too, not into a new Day; the next night gets Day 4",
      lambda: _ot_seed == {"day": 3, "next": 4}, json.dumps(_ot_seed))

# the Windows cloud-sync guard, on any OS
_ot_cloud = probe(OT.env, "m.IS_WINDOWS = True\n"
                  "m.DEST_DIR = os.path.join(m.TEST_ROOT, 'OneDrive', 'Documents', 'Astro')\n"
                  "a = m.documents_under_icloud()\n"
                  "m.DEST_DIR = os.path.join(m.TEST_ROOT, 'Local', 'Astro'); m.LIBRARY_DIR = m.DEST_DIR\n"
                  "print(json.dumps({'onedrive': a, 'plain': m.documents_under_icloud()}))\n")
check("OT on Windows an import folder under OneDrive is noticed (Files On-Demand evicts frames), a plain "
      "one is not",
      lambda: _ot_cloud == {"onedrive": True, "plain": False}, json.dumps(_ot_cloud))

# a Seestar stack re-saved under a name the other computer already filed with
# different bytes: filed beside it with this computer's tag, nothing written over
OT2 = teh.Env("OT2", asiair=False, seestar=True)
OT2.env.update({"ASTRO_SHIP_FOLDER": "pc", "ASTRO_SHIP_LOG": "shipped-pc.jsonl", "ASTRO_MACHINE_ID": "pc"})
OT2.add_seestar_sub("M 45", "20261003-210000")
_ot2_stack = OT2.add_seestar_stack("M 45", 20, "20261003-213000")
r = OT2.run(stdin="n\n")                      # the archive folder doesn't exist yet: imported, not shipped
os.makedirs(os.path.join(OT2.archive, "S30P"), exist_ok=True)
_ot2_plan = probe(OT2.env, "st = m.State(); items, notes = m.ship_plan(st, m.ARCHIVE_MOUNT)\n"
                  "print(json.dumps([i['rel'] for i in items if i['entry'].get('filename', '').startswith('Stacked_')]))\n")
_ot2_rel = _ot2_plan[0] if isinstance(_ot2_plan, list) and _ot2_plan else None
if _ot2_rel:
    _ot2_dst = os.path.join(OT2.archive, _ot2_rel.replace("\\", "/"))
    os.makedirs(os.path.dirname(_ot2_dst), exist_ok=True)
    with open(_ot2_dst, "wb") as f:
        f.write(b"the Mac's earlier stack, different bytes")
r = OT2.run("--ship")
_ot2_led = OT2.ledger()
_ot2_row = next((e for e in _ot2_led["files"].values() if e.get("filename", "").startswith("Stacked_")), {})
_ot2_loc = str(_ot2_row.get("archiveLocation") or "")
_ot2_beside = os.path.join(OT2.archive, _ot2_loc.replace("\\", "/")) if _ot2_loc else ""
check("OT a re-saved stack whose name the archive already holds with different bytes is filed BESIDE it "
      "as <name>__pc.fit: the first file untouched, the row's archive location is the new name, the ship "
      "says so, and the problem does not recur",
      lambda: _ot2_rel is not None and r.returncode == 0 and "__pc" in _ot2_loc and os.path.isfile(_ot2_beside)
      and open(_ot2_dst, "rb").read() == b"the Mac's earlier stack, different bytes"
      and "filed beside it" in r.stdout and "Problems: 0" in r.stdout,
      f"rel={_ot2_rel} loc={_ot2_loc} " + r.stdout[-500:])

# ═══════════════ CHAIN RB: robustness (review of 16 Oct 2026, 1.7.1) ════════
# Sixteen findings from a review of the engine, each with the check that
# fails without its fix: a --no-checksum reconcile proving nothing, the PC's
# problem rows sending a frame again, a camera that stops answering half-way
# (scan, import, SAFE gate), a ledger file of the wrong shape, a file name
# whose numbers don't parse, the ship plan listing the archive once, the
# ledger saved once a minute, NFC/NFD spellings on the archive, a stale lock,
# the Seestar volume cache and Windows' long paths.
import hashlib as _rbhl
import unicodedata as _rbud
from datetime import datetime as _rbdt, timezone as _rbtz, timedelta as _rbtd

def _rb_sha(data):
    return _rbhl.sha256(data).hexdigest()

def _rb_put(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)

def _rb_code(template, **vals):
    """Probe code from a template: @name@ becomes repr(value)."""
    for k, v in vals.items():
        template = template.replace(f"@{k}@", repr(v))
    return template

def _rb_rel(p, root):
    return os.path.relpath(p, root).replace("\\", "/")

_RB_PCX = {"ASTRO_SHIP_FOLDER": "pc", "ASTRO_SHIP_LOG": "shipped-pc.jsonl",
           "ASTRO_MACHINE_ID": "chillblast", "ASTRO_MACHINE_LABEL": "Chillblast"}
_RB_CAPTURE = ("import io, contextlib\n"
               "_buf = io.StringIO()\n"
               "class _Cap:\n"
               "    def __enter__(self):\n"
               "        self.a = contextlib.redirect_stdout(_buf); self.b = contextlib.redirect_stderr(_buf)\n"
               "        self.a.__enter__(); self.b.__enter__(); return _buf\n"
               "    def __exit__(self, *x):\n"
               "        self.b.__exit__(*x); self.a.__exit__(*x)\n")

# ── 1. --reconcile --no-checksum: the same size proves nothing ──────────────
RB1 = teh.Env("RB1", asiair=False, seestar=True)
os.makedirs(RB1.archive, exist_ok=True)
_rb1_sub = RB1.add_seestar_sub("M 42", "20261001-210000")
_rb1_dest = os.path.join(RB1.sdest30, "M 42 - Orion Nebula", "M 42_sub Day 1")
_rb1_bytes = bytearray(open(_rb1_sub, "rb").read())
_rb1_bytes[-1] ^= 0xFF                                  # same size, one byte differs
_rb_put(os.path.join(_rb1_dest, os.path.basename(_rb1_sub)), bytes(_rb1_bytes))
_rb1 = probe(RB1.env, _RB_CAPTURE + _rb_code(
    "st = m.State(); st.new_ledger()\n"
    "rel = @REL@\n"
    "st.add_file(rel, filename=@FN@, size=os.path.getsize(@SUB@), sha256=None, origin='baseline',\n"
    "            device='seestar', camera='ZWO Seestar S30 Pro', target='M 42', displayName='M 42 - Orion Nebula',\n"
    "            sourceType='sub', dest=@DEST@, verifiedAtImport=False)\n"
    "st.save_ledger()\n"
    "with _Cap() as buf:\n"
    "    m.run_reconcile(st, deep=False)\n"
    "st2 = m.State(); e = st2.ledger['files'][rel]\n"
    "un, _b = m._seestar_unproven_files(st2, @VOL@, [os.path.dirname(@SUB@)], exempt_superseded=True,\n"
    "                                   camera='ZWO Seestar S30 Pro')\n"
    "items, notes = m.ship_plan(st2, m.ARCHIVE_MOUNT)\n"
    "print(json.dumps({'verified': e.get('verifiedAtImport'), 'skipped': e.get('checksumSkipped'),\n"
    "                  'reconciled': bool(e.get('reconciledAt')), 'unproven': un, 'plan': len(items),\n"
    "                  'said': \"size alone can't prove a backup\" in buf.getvalue()}))\n",
    REL=_rb_rel(_rb1_sub, RB1.svol), FN=os.path.basename(_rb1_sub), SUB=_rb1_sub, DEST=_rb1_dest, VOL=RB1.svol))
check("RB a --reconcile without checksums over a same-size copy with different bytes leaves the row "
      "UNVERIFIED (checksumSkipped, as a --no-checksum import's row) and says size alone can't prove a backup",
      lambda: _rb1["verified"] is False and _rb1["skipped"] is True and _rb1["reconciled"] is True
      and _rb1["said"] is True, json.dumps(_rb1)[:500])
check("RB ...so the SAFE gate lists that file as unproven and the ship plan leaves it out",
      lambda: _rb1["unproven"] == [os.path.basename(_rb1_sub)] and _rb1["plan"] == 0, json.dumps(_rb1)[:500])

# ── 2. the PC's problem rows send a frame again ─────────────────────────────
RB2 = teh.Env("RB2", asiair=True)
RB2.env.update({"ASTRO_SHIP_FOLDER": "mac", "ASTRO_MACHINE_ID": "mac"})
os.makedirs(os.path.join(RB2.archive, "ZWO Askar Scopes"), exist_ok=True)
os.makedirs(os.path.join(RB2.archive, "_verify", "pc"), exist_ok=True)
_rb2_dest = os.path.join(RB2.dest, "M 81 - Bode's Galaxy", "lights", "M 81 - Bode's Galaxy Day 1")
_rb2_fn = teh.light_name("M 81", dt="20260901-220000", seq="0001")
_rb2_data = b"RB2 frame, the one the PC found damaged"
_rb_put(os.path.join(_rb2_dest, _rb2_fn), _rb2_data)
_rb2_key = f"Plan/Light/M 81/{_rb2_fn}"
_rb2_row = {"filename": _rb2_fn, "size": len(_rb2_data), "sha256": _rb_sha(_rb2_data), "origin": "import",
            "target": "M 81", "displayName": "M 81 - Bode's Galaxy", "sourceType": "Plan",
            "camera": "ZWO ASI585MC Air", "dest": _rb2_dest, "night": "2026-09-01", "dayNumber": 1,
            "importedAt": "2026-09-02T010000", "verifiedAtImport": True, "clearedFromCamera": True}
os.makedirs(RB2.state, exist_ok=True)
with open(os.path.join(RB2.state, "ledger.json"), "w") as f:
    json.dump({"version": 1, "files": {_rb2_key: _rb2_row}, "calibration": {}}, f)
_rb2_plan = probe(RB2.env, "st = m.State(); items, _n = m.ship_plan(st, m.ARCHIVE_MOUNT)\n"
                           "print(json.dumps({'rel': items[0]['rel'] if items else None}))\n")
_rb2_loc = str(_rb2_plan.get("rel") or "").replace("/", "\\")
_rb2_row.update({"archiveLocation": _rb2_loc, "archiveShippedAt": "2026-09-03T020000"})   # shipped, then...
with open(os.path.join(RB2.state, "ledger.json"), "w") as f:
    json.dump({"version": 1, "files": {_rb2_key: _rb2_row}, "calibration": {}}, f)
_rb2_noted = _rbdt.now(_rbtz.utc) - _rbtd(seconds=120)
with open(os.path.join(RB2.archive, "_verify", "pc", "problems.jsonl"), "w", encoding="utf-8") as f:
    f.write(json.dumps({"schema": "problem-row/1", "relpath": _rb2_loc, "sha256": _rb_sha(_rb2_data),
                        "size": len(_rb2_data), "problem": "hash", "found": "f" * 64,
                        "at": _rb2_noted.strftime("%Y-%m-%dT%H%M%S"),
                        "atUtc": _rb2_noted.isoformat(timespec="seconds"), "machineId": "chillblast"}) + "\n")
_rb2 = probe(RB2.env, _rb_code(
    "st = m.State(); arch = m.ARCHIVE_MOUNT\n"
    "moved = m._ship_apply_problems(st, arch, m.own_ship_rows(arch))\n"
    "items, _n = m.ship_plan(st, arch)\n"
    "e = st.ledger['files'][@KEY@]\n"
    "sp = m.mac_space(st)['totals']\n"
    "print(json.dumps({'moved': moved, 'in_plan': [i['key'] for i in items], 'todo': [i['key'] for i in items if not m._item_shipped(i)],\n"
    "                  'problem': e.get('archiveProblem'), 'loc': e.get('archiveLocation'),\n"
    "                  'status': m.status_summary(st), 'onlyHere': sp['onlyHere']['files'], 'waiting': sp['waiting']['files']}))\n",
    KEY=_rb2_key))
check("RB a BADHASH row the PC's sweep wrote for a shipped frame puts it back into the ship's to-do: its "
      "archiveLocation/archiveShippedAt move into archiveProblem (why, at, location) and the row counts as "
      "only here, never 'waiting'",
      lambda: _rb2["moved"] == 1 and _rb2["todo"] == [_rb2_key] and _rb2["loc"] is None
      and (_rb2["problem"] or {}).get("why") == "hash" and (_rb2["problem"] or {}).get("location") == _rb2_loc
      and _rb2["status"]["onlyHere"] == 1 and _rb2["status"]["safe"] is False
      and _rb2["onlyHere"] == 1 and _rb2["waiting"] == 0, json.dumps(_rb2)[:700])
r = RB2.run("--ship", "--dry-run")
check("RB --ship --dry-run says so: '1 frame(s) the PC found damaged on the archive are being re-sent' and "
      "plans that one file",
      lambda: r.returncode == 0 and "1 frame(s) the PC found damaged on the archive are being re-sent" in r.stdout
      and "Ship: 1 file(s)" in r.stdout, r.stdout[-600:] + r.stderr[-300:])
r = RB2.run("--ship")
_rb2_led = RB2.ledger()["files"][_rb2_key]
check("RB the real ship sends it again (the problem goes into archiveProblems, the row is 'shipped' once more)",
      lambda: r.returncode == 0 and "Shipped 1 file(s)" in r.stdout and _rb2_led.get("archiveLocation")
      and not _rb2_led.get("archiveProblem") and len(_rb2_led.get("archiveProblems") or []) == 1,
      r.stdout[-500:] + json.dumps(_rb2_led)[:300])
r = RB2.run("--ship", "--dry-run")
check("RB ...and the old problem row is history: a problem noted BEFORE this computer's last 'shipped' row for "
      "that path is not applied again (no loop of re-sends)",
      lambda: "being re-sent" not in r.stdout and "Ship: 0 file(s)" in r.stdout, r.stdout[-500:])
r = RB2.run("--sweep", extra_env=_RB_PCX)
_rb2_ver = [json.loads(l) for l in open(os.path.join(RB2.archive, "_verify", "pc", "verified.jsonl"), encoding="utf-8")
            if l.strip()] if os.path.isfile(os.path.join(RB2.archive, "_verify", "pc", "verified.jsonl")) else []
check("RB the PC's sweep checks a path with a problem row again once a ship sent the frame again after the "
      "problem was noted, and verifies it",
      lambda: r.returncode == 0 and any(v.get("relpath") == _rb2_loc and v.get("sha256") == _rb_sha(_rb2_data)
                                         for v in _rb2_ver), r.stdout[-500:] + json.dumps(_rb2_ver)[:300])

# ── 3. mark_cleared: re-appeared frames, incomplete scans ───────────────────
_rb3 = probe(RB2.env, _RB_CAPTURE +
    "st = m.State(); st.new_ledger()\n"
    "for n in ('a', 'b'):\n"
    "    st.add_file(f'Plan/Light/M 81/{n}.fit', filename=f'{n}.fit', size=1, sha256='0' * 64, origin='import',\n"
    "                target='M 81', verifiedAtImport=True)\n"
    "st.mark_cleared({'Plan/Light/M 81/a.fit'})\n"
    "b = st.ledger['files']['Plan/Light/M 81/b.fit']\n"
    "one = (b.get('clearedFromCamera'), m.only_on_this_machine(st))\n"
    "st.mark_cleared({'Plan/Light/M 81/a.fit', 'Plan/Light/M 81/b.fit'})\n"
    "two = (b.get('clearedFromCamera'), bool(b.get('reappearedAt')), m.only_on_this_machine(st))\n"
    "st.add_file('MyWorks/M 42_sub/x.fit', filename='x.fit', size=1, sha256='0' * 64, origin='import', device='seestar',\n"
    "            camera='ZWO Seestar S30 Pro', target='M 42', verifiedAtImport=True)\n"
    "with _Cap() as buf:\n"
    "    st.seestar_seen({'volume': m.TEST_ROOT, 'camera': 'ZWO Seestar S30 Pro', 'relpaths': {'MyWorks/M 42_sub/other.fit'},\n"
    "                     'incomplete': True, 'identityGuessed': False})\n"
    "inc = (st.ledger['files']['MyWorks/M 42_sub/x.fit'].get('clearedFromCamera'), 'nothing was marked cleared' in buf.getvalue())\n"
    "print(json.dumps({'one': one, 'two': two, 'inc': inc}))\n")
check("RB mark_cleared({a}) flags b; mark_cleared({a, b}) un-flags it (reappearedAt) and nothing is 'only on "
      "this computer' any more",
      lambda: _rb3["one"] == [True, 1] and _rb3["two"] == [False, True, 0], json.dumps(_rb3))
check("RB a Seestar scan that could not read the whole card marks nothing cleared, and says so",
      lambda: _rb3["inc"] == [None, True], json.dumps(_rb3))
RB3 = teh.Env("RB3", asiair=True)
_rb3_light = RB3.add_light("Plan", "M 81", "0001")
_rb3_broken = os.path.join(RB3.cam, "Plan", "Light", "M 81", "broken.fit")
os.symlink(os.path.join(RB3.root, "nowhere.fit"), _rb3_broken)          # listed by the walk, unreadable
_rb3s = probe(RB3.env, _rb_code(
    "st = m.State(); st.new_ledger()\n"
    "st.add_file('Plan/Light/M 81/gone.fit', filename='gone.fit', size=1, sha256='0' * 64, origin='import',\n"
    "            target='M 81', verifiedAtImport=True)\n"
    "st.save_ledger()\n"
    "s = m.scan_camera(st)\n"
    "print(json.dumps({'incomplete': s['incomplete'], 'broken_in': 'Plan/Light/M 81/broken.fit' in s['relpaths'],\n"
    "                  'files': len(s['targets'][0]['files'])}))\n"))
check("RB scan_camera: a file the walk lists but cannot size is in the relpath set (never 'gone') and the "
      "scan is marked incomplete",
      lambda: _rb3s == {"incomplete": True, "broken_in": True, "files": 1}, json.dumps(_rb3s))
r = RB3.run("--report")
_rb3_gone = RB3.ledger()["files"]["Plan/Light/M 81/gone.fit"]
check("RB --report over an incomplete scan marks nothing cleared and says 'the camera could not be read "
      "completely; nothing was marked cleared'",
      lambda: r.returncode == 0 and "nothing was marked cleared" in r.stdout
      and not _rb3_gone.get("clearedFromCamera"), r.stdout[-400:] + r.stderr[-200:])
os.remove(_rb3_broken)
r = RB3.run("--report")
check("RB ...and once the card reads completely the missing frame is flagged as before",
      lambda: RB3.ledger()["files"]["Plan/Light/M 81/gone.fit"].get("clearedFromCamera") is True,
      r.stdout[-300:])

# ── 4. a camera unplugged mid-copy ──────────────────────────────────────────
RB4 = teh.Env("RB4", asiair=True)
for i in (1, 2, 3, 4):
    RB4.add_light("Plan", "M 81", f"000{i}", dt=f"20260901-22000{i}")
_RB4_ARGS = ("import argparse\n"
             "args = argparse.Namespace(dry_run=False, no_checksum=False, loose_cal=False, explain_cal=False, all=False)\n")
_rb4 = probe(RB4.env, _RB_CAPTURE + _RB4_ARGS +
    "st = m.State(); st.new_ledger(); st.save_ledger()\n"
    "orig, done = m.copy_file_verified, [0]\n"
    "def wrapped(src, dst, **kw):\n"
    "    r = orig(src, dst, **kw); done[0] += 1\n"
    "    if done[0] == 2:\n"
    "        shutil.rmtree(m.ASIAIR_VOLUME)          # the ASIAir goes away after the second frame\n"
    "    return r\n"
    "m.copy_file_verified = wrapped\n"
    "with _Cap() as buf:\n"
    "    totals = m.run_import(st, args)\n"
    "out = buf.getvalue()\n"
    "print(json.dumps({'warned': out.count('The ASIAir stopped answering (unplugged?)'), 'rows': len(m.State().ledger['files']),\n"
    "                  'stopped': totals.get('stoppedEarly'), 'files': totals['files'], 'summary': 'Import stopped early' in out,\n"
    "                  'tail': out[-300:]}))\n", before="import shutil\n")
check("RB ASIAir unplugged after the second frame: one plain-words warning, the run stops, exactly the two "
      "verified frames are in the ledger, and the summary says it stopped early",
      lambda: _rb4["warned"] == 1 and _rb4["rows"] == 2 and _rb4["files"] == 2 and _rb4["stopped"] is True
      and _rb4["summary"] is True, json.dumps(_rb4)[:700])
RB4s = teh.Env("RB4s", asiair=False, seestar=True)
for i in (0, 1, 2, 3):
    RB4s.add_seestar_sub("M 42", f"20261001-21{i}000")
_rb4s = probe(RB4s.env, _RB_CAPTURE + _RB4_ARGS +
    "st = m.State(); st.new_ledger(); st.save_ledger()\n"
    "scan = m.scan_seestar(st)\n"
    "orig, done = m.copy_file_verified, [0]\n"
    "def wrapped(src, dst, **kw):\n"
    "    r = orig(src, dst, **kw); done[0] += 1\n"
    "    if done[0] == 2:\n"
    "        shutil.rmtree(scan['volume'])\n"
    "    return r\n"
    "m.copy_file_verified = wrapped\n"
    "with _Cap() as buf:\n"
    "    totals = m.run_seestar_import(st, scan, args)\n"
    "out = buf.getvalue()\n"
    "print(json.dumps({'warned': out.count('stopped answering (unplugged?)'), 'rows': len(m.State().ledger['files']),\n"
    "                  'stopped': totals.get('stoppedEarly'), 'tail': out[-300:]}))\n",
    before="import shutil\n")
check("RB Seestar unplugged after the second sub: one warning, two ledger rows, the run stops early (and offers "
      "no clear on a camera that has gone)",
      lambda: _rb4s["warned"] == 1 and _rb4s["rows"] == 2 and _rb4s["stopped"] is True
      and not teh.os_calls(RB4s.root, "dialog"), json.dumps(_rb4s)[:600])

# ── 5. State.load: a file of the wrong shape ────────────────────────────────
RB5 = teh.Env("RB5", asiair=True)
RB5.add_light("Plan", "M 81", "0001")
os.makedirs(RB5.state, exist_ok=True)
with open(os.path.join(RB5.state, "ledger.json"), "w") as f:
    f.write("[]")
_rb5a = probe(RB5.env, _RB_CAPTURE +
    "with _Cap() as buf:\n"
    "    st = m.State()\n"
    "print(json.dumps({'corrupt': st.ledger_corrupt, 'has': st.has_ledger(), 'status': m.status_summary(st),\n"
    "                  'said': 'not a ledger' in buf.getvalue()}))\n")
check("RB a ledger.json that parses as a list is treated like one that doesn't parse: ledger_corrupt, "
      "'Status unknown', never 'safe', never a baseline offer",
      lambda: _rb5a["corrupt"] is True and _rb5a["has"] is False and _rb5a["status"]["safe"] is False
      and "Status unknown" in _rb5a["status"]["text"] and _rb5a["said"] is True, json.dumps(_rb5a))
_rb5_fn = os.path.basename(RB5.add_light("Plan", "M 81", "0002", dt="20260901-220002"))
with open(os.path.join(RB5.state, "ledger.json"), "w") as f:
    json.dump({"version": 1, "files": {"x": 1, "Plan/Light/M 81/old.fit": {
        "filename": "old.fit", "size": 1, "sha256": "0" * 64, "origin": "import", "target": "M 81",
        "verifiedAtImport": True}}, "calibration": {}}, f)
with open(os.path.join(RB5.state, "skiplist.json"), "w") as f:
    json.dump({"a": 1}, f)
with open(os.path.join(RB5.state, "custom-names.json"), "w") as f:
    json.dump({"M 81": "Bode", "M 82": 7, "M 83": ["x"]}, f)
_rb5b = probe(RB5.env, _RB_CAPTURE +
    "with _Cap() as buf:\n"
    "    st = m.State()\n"
    "out = buf.getvalue()\n"
    "print(json.dumps({'skip': st.skiplist, 'names': st.custom_names, 'files': sorted(st.ledger['files']),\n"
    "                  'aside': st.ledger.get('malformedRows'), 'corrupt': st.ledger_corrupt,\n"
    "                  'warned_row': 'not records' in out and \"x\" in out, 'warned_skip': 'skiplist.json' in out,\n"
    "                  'warned_names': 'custom-names.json' in out}))\n")
check("RB a skiplist that is not a list is an empty list, a names file keeps only name → name, and a ledger "
      "row that is not a record is set aside (malformedRows) — each with a warning naming what was dropped",
      lambda: _rb5b["skip"] == [] and _rb5b["names"] == {"M 81": "Bode"} and _rb5b["files"] == ["Plan/Light/M 81/old.fit"]
      and _rb5b["aside"] == {"x": 1} and _rb5b["corrupt"] is False
      and _rb5b["warned_row"] and _rb5b["warned_skip"] and _rb5b["warned_names"], json.dumps(_rb5b)[:600])
r1 = RB5.run("--scan-only"); r2 = RB5.run("--report")
check("RB ...and every command still runs over that ledger (--scan-only, --report)",
      lambda: r1.returncode == 0 and "ASIAIR-SCAN|SUMMARY" in r1.stdout and r2.returncode == 0
      and "BACKUP REPORT" in r2.stdout, r1.stderr[-300:] + r2.stderr[-300:])

# ── 6. a Light file whose numbers don't parse ───────────────────────────────
RB6 = teh.Env("RB6", asiair=True)
RB6.add_light("Plan", "M 81", "0001", dt="20260901-220001")
_rb6_odd = "Light_M 81_1.2.3s_Bin1_585MC_gain200_20260901-220002_120.0deg_-10.0C_LUltimate_0002.fit"
teh.make_fits(os.path.join(RB6.cam, "Plan", "Light", "M 81", _rb6_odd), dateobs="2026-09-01T22:00:02", uniq="rb6-odd")
_rb6 = probe(RB6.env, _rb_code(
    "st = m.State(); s = m.scan_camera(st)\n"
    "print(json.dumps({'files': len(s['targets'][0]['files']), 'odd': s['light_unparseable'],\n"
    "                  'parsed': m.parse_light_filename(@ODD@), 'cal': m.parse_calibration_filename('Dark_1.2.3s_Bin1_585MC_gain200_20260901-090000_120.0deg_-10.0C_0001.fit')}))\n",
    ODD=_rb6_odd))
check("RB a Light_…_1.2.3s_… name no longer crashes the scan: parse_light_filename is None, the scan completes "
      "with the file counted, and names it as unrecognised",
      lambda: _rb6["files"] == 2 and _rb6["odd"] == [f"M 81/{_rb6_odd}"] and _rb6["parsed"] is None
      and _rb6["cal"] is None, json.dumps(_rb6)[:500])
r = RB6.run("--report")
check("RB the report lists it: 'unrecognised name: M 81/Light_M 81_1.2.3s_…'",
      lambda: r.returncode == 0 and f"unrecognised name: M 81/{_rb6_odd}" in r.stdout, r.stdout[-600:] + r.stderr[-200:])
r = RB6.run("--no-ship")
check("RB ...and the import still backs it up, by its FITS headers (two verified rows)",
      lambda: r.returncode == 0 and sum(1 for e in RB6.ledger()["files"].values() if e.get("verifiedAtImport")) == 2,
      r.stdout[-400:] + r.stderr[-300:])

# ── 7 + 8. the ship plan lists the archive once; the ledger is saved once a minute
RB7 = teh.Env("RB7", asiair=True)
RB7.env.update({"ASTRO_SHIP_FOLDER": "mac", "ASTRO_MACHINE_ID": "mac"})
os.makedirs(os.path.join(RB7.archive, "ZWO Askar Scopes"), exist_ok=True)
_rb7_dest = os.path.join(RB7.dest, "M 81 - Bode's Galaxy", "lights", "M 81 - Bode's Galaxy Day 1")
_rb7_rows = {}
for i in range(400):
    fn = f"Light_M 81_300.0s_Bin1_585MC_gain200_20260901-22{i // 60:02d}{i % 60:02d}_120.0deg_-10.0C_LUltimate_{i:04d}.fit"
    data = b"RB7 frame %d" % i
    _rb_put(os.path.join(_rb7_dest, fn), data)
    _rb7_rows[f"Plan/Light/M 81/{fn}"] = {
        "filename": fn, "size": len(data), "sha256": _rb_sha(data), "origin": "import", "target": "M 81",
        "displayName": "M 81 - Bode's Galaxy", "sourceType": "Plan", "camera": "ZWO ASI585MC Air",
        "dest": _rb7_dest, "night": "2026-09-01", "dayNumber": 1, "importedAt": "2026-09-02T010000",
        "verifiedAtImport": True}
os.makedirs(RB7.state, exist_ok=True)
with open(os.path.join(RB7.state, "ledger.json"), "w") as f:
    json.dump({"version": 1, "files": _rb7_rows, "calibration": {}}, f)
_rb7 = probe(RB7.env,
    "calls, orig = [], os.listdir\n"
    "os.listdir = lambda p: (calls.append(str(p)), orig(p))[1]\n"
    "st = m.State(); items, notes = m.ship_plan(st, m.ARCHIVE_MOUNT)\n"
    "os.listdir = orig\n"
    "root = os.path.join(m.ARCHIVE_MOUNT, 'ZWO Askar Scopes')\n"
    "print(json.dumps({'items': len(items), 'listdir': len(calls), 'root_listed': calls.count(root)}))\n")
check("RB ship_plan over 400 rows of one target lists the archive root once (and a handful of folders), not "
      "once per row",
      lambda: _rb7["items"] == 400 and _rb7["root_listed"] == 1 and _rb7["listdir"] <= 10, json.dumps(_rb7))
_rb8 = probe(RB7.env, _RB_CAPTURE +
    "saves, orig_save = [0], m.State.save_ledger\n"
    "def counting(self):\n"
    "    saves[0] += 1\n"
    "    return orig_save(self)\n"
    "m.State.save_ledger = counting\n"
    "st = m.State()\n"
    "with _Cap() as buf:\n"
    "    ok = m.run_ship(st)\n"
    "during = saves[0]\n"
    "led = json.load(open(st.ledger_path)); bak = json.load(open(st.ledger_path + '.bak'))\n"
    "shipped = sum(1 for e in led['files'].values() if e.get('archiveLocation'))\n"
    "bak_shipped = sum(1 for e in bak['files'].values() if e.get('archiveLocation'))\n"
    "st.ledger['rbMarker'] = 1; st.save_ledger(); st.ledger['rbMarker'] = 2; st.save_ledger()\n"
    "bak2 = json.load(open(st.ledger_path + '.bak')); led2 = json.load(open(st.ledger_path))\n"
    "print(json.dumps({'ok': ok, 'shipped': shipped, 'saves': during, 'bak_shipped': bak_shipped,\n"
    "                  'bak_marker': bak2.get('rbMarker'), 'led_marker': led2.get('rbMarker'), 'tail': buf.getvalue()[-200:]}))\n")
check("RB a 400-file ship saves the ledger at most once a minute plus once at the end (not every 50 files)",
      lambda: _rb8["ok"] is True and _rb8["shipped"] == 400 and 1 <= _rb8["saves"] <= 2, json.dumps(_rb8)[:500])
check("RB ...and the .bak is taken once per run: it holds the ledger as the run found it, and later saves in "
      "the same run leave it alone",
      lambda: _rb8["bak_shipped"] == 0 and _rb8["bak_marker"] is None and _rb8["led_marker"] == 2, json.dumps(_rb8)[:500])

# ── 9. the sweep finds a frame whose name is spelled NFD on disk ────────────
RB9 = teh.Env("RB9", asiair=False, seestar=True)
_rb9_nfc = _rbud.normalize("NFC", "Caf\u00e9 (M 1)")
_rb9_nfd = _rbud.normalize("NFD", _rb9_nfc)
_rb9_data = b"an NFD-named frame on the archive"
_rb_put(os.path.join(RB9.archive, "S30P", _rb9_nfd, f"{_rb9_nfd}_sub Day 1", "20261001-210000.fit"), _rb9_data)
_rb9_rel = f"S30P\\{_rb9_nfc}\\{_rb9_nfc}_sub Day 1\\20261001-210000.fit"
os.makedirs(os.path.join(RB9.archive, "_verify", "mac"), exist_ok=True)
with open(os.path.join(RB9.archive, "_verify", "mac", "shipped.jsonl"), "w", encoding="utf-8") as f:
    f.write(json.dumps({"schema": "ship-row/1", "state": "shipped", "relpath": _rb9_rel, "size": len(_rb9_data),
                        "sha256": _rb_sha(_rb9_data), "machine": "Mac", "machineId": "mac", "shipId": "r9",
                        "at": (_rbdt.now(_rbtz.utc) - _rbtd(minutes=30)).isoformat(timespec="seconds")}) + "\n")
r = RB9.run("--sweep", extra_env=_RB_PCX)
_rb9_pc = os.path.join(RB9.archive, "_verify", "pc")
_rb9_ver = [json.loads(l) for l in open(os.path.join(_rb9_pc, "verified.jsonl"), encoding="utf-8") if l.strip()] \
    if os.path.isfile(os.path.join(_rb9_pc, "verified.jsonl")) else []
_rb9_prob = [json.loads(l) for l in open(os.path.join(_rb9_pc, "problems.jsonl"), encoding="utf-8") if l.strip()] \
    if os.path.isfile(os.path.join(_rb9_pc, "problems.jsonl")) else []
check("RB the sweep tries the row's spelling, NFC and NFD before calling a frame MISSING: a file stored "
      "decomposed is verified under the row's composed name",
      lambda: r.returncode == 0 and any(v.get("relpath") == _rb9_rel for v in _rb9_ver)
      and not any(p.get("problem") == "missing" for p in _rb9_prob) and _rb9_nfc != _rb9_nfd,
      r.stdout[-400:] + json.dumps(_rb9_prob)[:200])

# ── 10. a camera that stops answering while it is listed ────────────────────
RB10 = teh.Env("RB10", asiair=True)
RB10.add_light("Plan", "M 81", "0001")
RB10.add_light("Live", "M 82", "0001")
_rb10 = probe(RB10.env, _RB_CAPTURE +
    "orig, hits, cam = os.listdir, [0], m.ASIAIR_VOLUME\n"
    "def ld(p):\n"
    "    if str(p).startswith(cam):\n"
    "        hits[0] += 1\n"
    "        if hits[0] >= 2:\n"
    "            raise OSError(errno.EIO, 'Input/output error', str(p))\n"
    "    return orig(p)\n"
    "os.listdir = ld\n"
    "st = m.State()\n"
    "with _Cap() as buf:\n"
    "    m.run_scan_only(st)\n"
    "hits[0] = 0\n"
    "try:\n"
    "    m.scan_camera(st); msg = None\n"
    "except RuntimeError as e:\n"
    "    msg = str(e)\n"
    "os.listdir = orig\n"
    "print(json.dumps({'out': buf.getvalue(), 'msg': msg}))\n", before="import errno\n")
check("RB os.listdir raising EIO on the second camera folder: scan_camera refuses with 'the ASIAir stopped "
      "answering while it was being read (unplugged?)', run_scan_only prints 'NOT scanned' and ends cleanly, "
      "never 'Every frame is backed up'",
      lambda: "ASIAir NOT scanned" in _rb10["out"] and "stopped answering while it was being read" in (_rb10["msg"] or "")
      and "ASIAIR-SCAN|ATTENTION|1" in _rb10["out"] and "Every frame is backed up" not in _rb10["out"]
      and "first import backs everything up" not in _rb10["out"], json.dumps(_rb10)[:600])
_rb10s = probe(RB1.env,
    "orig, hits, mw = os.listdir, [0], os.path.join(m.seestar_volume(), 'MyWorks')\n"
    "def ld(p):\n"
    "    if str(p).startswith(mw):\n"
    "        hits[0] += 1\n"
    "        if hits[0] >= 2:\n"
    "            raise OSError(errno.EIO, 'Input/output error', str(p))\n"
    "    return orig(p)\n"
    "os.listdir = ld\n"
    "st = m.State()\n"
    "try:\n"
    "    m.scan_seestar(st); msg = None\n"
    "except RuntimeError as e:\n"
    "    msg = str(e)\n"
    "os.listdir = orig\n"
    "print(json.dumps({'msg': msg}))\n", before="import errno\n")
check("RB the same for a Seestar: 'the Seestar stopped answering while it was being read' (the refusal every "
      "scan path already handles)",
      lambda: "the Seestar stopped answering while it was being read" in (_rb10s.get("msg") or ""), json.dumps(_rb10s))

# ── 11. creation time without SetFile ───────────────────────────────────────
_rb11 = probe(RB10.env, _rb_code(
    "calls = []\n"
    "class R:\n"
    "    returncode = 0\n"
    "    stdout = '1700000000\\n'\n"
    "m.subprocess.run = lambda *a, **k: (calls.append(list(a[0])), R())[1]\n"
    "m.IS_MAC = True; m._SETFILE = None\n"
    "m.preserve_creation_time(@SRC@, @SRC@)\n"
    "none = len(calls)\n"
    "m._SETFILE = '/fake/bin/SetFile'\n"
    "m.preserve_creation_time(@SRC@, @SRC@)\n"
    "print(json.dumps({'none': none, 'last': calls[-1][0] if calls else None, 'date': calls[-1][2] if calls else None}))\n",
    SRC=os.path.join(RB10.cam, "Plan", "Light", "M 81", os.listdir(os.path.join(RB10.cam, "Plan", "Light", "M 81"))[0])))
check("RB preserve_creation_time runs no subprocess when SetFile is absent, and calls the SetFile it found once "
      "when present (birth time from os.stat where Python has it)",
      lambda: _rb11["none"] == 0 and _rb11["last"] == "/fake/bin/SetFile" and "/" in str(_rb11["date"]), json.dumps(_rb11))

# ── 12. the discard refusal over files the other computer holds ─────────────
RB12 = teh.Env("RB12", asiair=False, seestar=True)
RB12.env.update({"ASTRO_SHIP_FOLDER": "pc", "ASTRO_SHIP_LOG": "shipped-pc.jsonl", "ASTRO_MACHINE_ID": "pc"})
os.makedirs(os.path.join(RB12.archive, "S30P"), exist_ok=True)
os.makedirs(os.path.join(RB12.archive, "_verify", "mac"), exist_ok=True)
_rb12_subs = [RB12.add_seestar_sub("M 42", f"20261001-21{i}000") for i in (0, 1)]
_rb12_files = {_rb_rel(p, RB12.svol): {"filename": os.path.basename(p), "size": os.path.getsize(p), "sha256": "a" * 64,
                                       "origin": "import", "verifiedAtImport": True, "archiveVerifiedAt": "2026-10-05T030000",
                                       "device": "seestar", "camera": "ZWO Seestar S30 Pro", "target": "M 42", "sourceType": "sub"}
               for p in _rb12_subs}
with open(os.path.join(RB12.archive, "_verify", "mac", "ledger-snapshot.json"), "w", encoding="utf-8") as f:
    json.dump({"schema": "ledger-snapshot/1", "machine": "Mac", "machineId": "mac", "machineUid": "mac-uid",
               "at": _rbdt.now(_rbtz.utc).isoformat(timespec="seconds"), "files": _rb12_files, "calibration": {},
               "library": {}, "discarded": {}, "customNames": {}, "skiplist": [], "equipment": {}}, f)
_rb12 = probe(RB12.env, _RB_CAPTURE +
    "st = m.State(); st.new_ledger(); st.save_ledger()\n"
    "rec = m.other_record(); orig = rec.backed_up\n"
    "def bu(rel, size, camera=None):\n"
    "    h = orig(rel, size, camera)\n"
    "    if h and sys._getframe(1).f_code.co_name == 'run_discard':\n"
    "        p = os.path.join(m.seestar_volume(), rel)        # gone between the look and the message\n"
    "        if os.path.exists(p):\n"
    "            os.remove(p)\n"
    "    return h\n"
    "rec.backed_up = bu\n"
    "with _Cap() as buf:\n"
    "    try:\n"
    "        res = m.run_discard(st, 'M 42')\n"
    "    except Exception as e:\n"
    "        res = 'CRASH ' + repr(e)\n"
    "print(json.dumps({'res': res, 'refused': 'clear it from the Mac' in buf.getvalue(), 'tail': buf.getvalue()[-300:]}))\n")
check("RB the discard refusal ('clear it from the Mac') still prints when a judged file vanished between the "
      "look and the message: sizes come from the dict, never a fresh getsize in the message",
      lambda: _rb12["res"] == "refused" and _rb12["refused"] is True, json.dumps(_rb12)[:600])

# ── 13. the SAFE gate: a file that cannot be stat'ed is unproven ─────────────
RB13 = teh.Env("RB13", asiair=False, seestar=True)
_rb13_s20 = RB13.add_seestar_stack("M 42", 20, "20261001-213000")
_rb13_s40 = RB13.add_seestar_stack("M 42", 40, "20261001-214000")
_rb13 = probe(RB13.env, _rb_code(
    "st = st_ = m.State(); st.new_ledger(); vol = m.seestar_volume()\n"
    "p40, p20 = @P40@, @P20@\n"
    "s40 = os.stat(p40)\n"
    "st.add_file(m._rel(p40, vol), filename=os.path.basename(p40), size=s40.st_size, sha256='0' * 64, origin='import',\n"
    "            device='seestar', camera='ZWO Seestar S30 Pro', target='M 42', sourceType='stack', verifiedAtImport=True,\n"
    "            cameraMtime=s40.st_mtime)\n"
    "orig_walk, n = os.walk, [0]\n"
    "def w(d, **k):\n"
    "    items = list(orig_walk(d, **k)); n[0] += 1\n"
    "    if n[0] == 2 and os.path.exists(p20):\n"
    "        os.remove(p20)                 # listed, then gone before its stat\n"
    "    yield from items\n"
    "os.walk = w\n"
    "un, _b = m._seestar_unproven_files(st, vol, [os.path.dirname(p20)], exempt_superseded=True, camera='ZWO Seestar S30 Pro')\n"
    "os.walk = orig_walk\n"
    "print(json.dumps({'unproven': un}))\n", P40=_rb13_s40, P20=_rb13_s20))
check("RB a stack listed by the walk but gone before its stat is UNPROVEN at once, even though a verified later "
      "stack would have made it 'superseded'",
      lambda: _rb13.get("unproven") == [os.path.basename(_rb13_s20)], json.dumps(_rb13))

# ── 14. a stale lock ─────────────────────────────────────────────────────────
_rb14 = probe(RB10.env, _RB_CAPTURE +
    "from datetime import datetime, timedelta\n"
    "os.makedirs(m.STATE_DIR, exist_ok=True)\n"
    "def lock(age_days):\n"
    "    with open(m.LOCK_PATH, 'w') as f:\n"
    "        json.dump({'pid': os.getpid(), 'started': (datetime.now() - timedelta(days=age_days)).strftime('%Y-%m-%dT%H%M%S'),\n"
    "                   'what': 'import'}, f)\n"
    "lock(2)\n"
    "with _Cap() as buf:\n"
    "    old = m.acquire_lock('ship')\n"
    "rec = json.load(open(m.LOCK_PATH)); said = 'Stale lock' in buf.getvalue()\n"
    "m.release_lock(); lock(0)\n"
    "with _Cap() as buf:\n"
    "    fresh = m.acquire_lock('ship')\n"
    "m.release_lock()\n"
    "print(json.dumps({'old': old, 'said': said, 'what': rec.get('what'), 'host': bool(rec.get('host')), 'fresh': fresh}))\n")
check("RB a lock whose pid is alive but whose 'started' is two days old is stale (taken, 'Stale lock' said), the "
      "new lock names what holds it and the host; a fresh live lock is still refused",
      lambda: _rb14["old"] is True and _rb14["said"] is True and _rb14["what"] == "ship" and _rb14["host"] is True
      and _rb14["fresh"] is False, json.dumps(_rb14))

# ── 15. seestar_volume() from a 1.5 s cache ──────────────────────────────────
_rb15 = probe(RB10.env,
    "calls, orig = [0], m._volumes_named_seestar\n"
    "def counting():\n"
    "    calls[0] += 1\n"
    "    return orig()\n"
    "m._volumes_named_seestar = counting\n"
    "for _ in range(10):\n"
    "    m.seestar_volume()\n"
    "a = calls[0]\n"
    "m.seestar_volume(force=True)\n"
    "print(json.dumps({'cached': a, 'forced': calls[0]}))\n")
check("RB ten seestar_volume() calls within a second look at the volumes once; force=True looks again",
      lambda: _rb15 == {"cached": 1, "forced": 2}, json.dumps(_rb15))

# ── 16. long names and Windows' long paths ──────────────────────────────────
_rb16 = probe(RB10.env,
    "cut = m.clean_target_name('A' * 100)\n"
    "same = m._win_long('/tmp/' + 'y' * 300)\n"
    "m.IS_WINDOWS = True\n"
    "win = m._win_long('C:\\\\' + 'x' * 300 + '\\\\f.fit'); short = m._win_long('C:\\\\short\\\\f.fit')\n"
    "print(json.dumps({'cut': len(cut or ''), 'same': same == '/tmp/' + 'y' * 300, 'win': win[:4], 'short': short}))\n")
check("RB clean_target_name caps a 100-character name at 80; _win_long leaves a path alone off Windows",
      lambda: _rb16["cut"] == 80 and _rb16["same"] is True, json.dumps(_rb16))
if os.name == "nt":
    check("RB _win_long prefixes a 300-character Windows path with \\\\?\\ and leaves a short one alone",
          lambda: _rb16["win"] == "\\\\?\\" and _rb16["short"] == "C:\\short\\f.fit", json.dumps(_rb16))
else:
    skip("RB _win_long prefixes a 300-character Windows path with \\\\?\\ (Windows only)")

# ═══════════════ Summary ═════════════════════════════════════════════════════
summary()
sys.exit(1 if FAIL else 0)
