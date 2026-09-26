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
PASS, FAIL = 0, 0
FAILURES = []

def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        FAILURES.append((name, detail))
        print(f"  FAIL  {name}   {detail}")

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
    print("  SKIP  S20 link containment (this OS needs admin rights to make links)")

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
check("W1 --version names the one shared version", "1.5.3" in r.stdout, r.stdout + r.stderr)
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
# per-machine ship log on a local archive (the PC case: E:\Astro Image Data)
arch = os.path.join(W1.root, "E-archive")
os.makedirs(os.path.join(arch, "S50P")); os.makedirs(os.path.join(arch, "_verify"))
r = wrun("--ship", extra={"ASTRO_ARCHIVE_MOUNT": arch, "ASTRO_SHIP_LOG": "shipped-pc.jsonl"})
vfiles = sorted(os.listdir(os.path.join(arch, "_verify")))
check("W1 the PC ships into a local archive and writes its OWN ship log",
      "shipped-pc.jsonl" in vfiles and "shipped.jsonl" not in vfiles
      and any(f.endswith(".fit") for _dp, _d, fs in os.walk(os.path.join(arch, "S50P")) for f in fs),
      str(vfiles) + r.stdout[-300:])
# the sweep's verified.jsonl stamps the PC's ledger too — a stray line or a
# size written as text never stops a ship
_rows = [json.loads(l) for l in open(os.path.join(arch, "_verify", "shipped-pc.jsonl"),
                                      encoding="utf-8") if l.strip()]
with open(os.path.join(arch, "_verify", "verified.jsonl"), "w", encoding="utf-8") as vf:
    vf.write("[1, 2]\nnot json\n")
    for i, x in enumerate(_rows):
        vf.write(json.dumps({"relpath": x["relpath"], "sha256": x.get("sha256"),
                             "size": str(x["size"]) if i == 0 else x["size"],
                             "verifiedAt": "2026-09-24T210000"}) + "\n")
r = wrun("--ship", extra={"ASTRO_ARCHIVE_MOUNT": arch, "ASTRO_SHIP_LOG": "shipped-pc.jsonl"})
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
_mac_inst = set(re.findall(r'install_file "\$SCRIPT_DIR/([^"]+)"',
                           open(os.path.join(_here, "install-scripts.sh"), encoding="utf-8").read()))
_ps = open(os.path.join(_here, "install-windows.ps1"), encoding="utf-8-sig").read()
_m = re.search(r"foreach \(\$f in @\(([^)]*'astro-import\.py'[^)]*)\)\)", _ps)
_win_inst = set(re.findall(r"'([^']+)'", _m.group(1))) if _m else set()
check("W1 the Mac install check expects only files install-scripts.sh installs",
      set(_st.INSTALLED["mac"]) <= _mac_inst, f"{_st.INSTALLED['mac']} vs {sorted(_mac_inst)}")
check("W1 the Windows install check expects only files install-windows.ps1 installs",
      set(_st.INSTALLED["windows"]) <= _win_inst, f"{_st.INSTALLED['windows']} vs {sorted(_win_inst)}")
_bin = os.path.join(W1.root, "installed-bin")
os.makedirs(_bin, exist_ok=True)
for _f in _st.INSTALLED.get(engw.PLATFORM, _st.INSTALLED["windows"]):   # what THIS OS installs
    shutil.copy2(os.path.join(_here, _f), _bin)
r = wrun(script=os.path.join(_bin, "selftest.py"))
check("W1 the install check passes from an installed folder (not only the source folder)",
      " present" in r.stdout and not re.search(r"FAIL\s+\S+ present", r.stdout),
      ("\n".join(ln for ln in r.stdout.splitlines() if "FAIL" in ln) or r.stdout[-600:])
      + r.stderr[-300:])

print("\n── Chain P1: --ship files Seestar frames into the archive (1.4.0) ──")
P1 = teh.Env("P1", asiair=False, seestar=True)
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
sl = os.path.join(arch, "_verify", "shipped.jsonl")
lines = [json.loads(x) for x in open(sl)] if os.path.isfile(sl) else []
check("P1 shipped.jsonl written for the PC sweep, one line per file with sha and size",
      len(lines) == 3 and all(l["sha256"] and l["size"] and l["relpath"] for l in lines), str(lines[:1]))
rdir = os.path.join(P1.receipts, "_ship")
check("P1 a filed receipt v2 was written", os.path.isdir(rdir) and any(f.startswith("filed-") for f in os.listdir(rdir)))
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
            "ASTRO_SHIP_LOG"):
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
    print("  SKIP  I1 no fake OS command ran (Windows runs no shell scripts; "
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
    print("  SKIP  I1 ...none of them ran a fake OS command (Windows runs no shell scripts)")
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
    print("  SKIP  I1 a MyWorks linked out of the root (this account can't make symlinks)")
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
    print("  SKIP  I1 ...and the watcher ran no fake OS command (Windows runs no shell scripts)")
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
        json.dump({"pid": os.getpid(), "started": "2026-09-26T101500", "what": what}, f)
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
        print(f"  SKIP  U1 {os.path.basename(name)}'s owner check (no bash here)")
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
    print("  SKIP  U1 install-windows.ps1's owner check through powershell.exe (Windows only)")
    print("  SKIP  U1 the Restart .cmd's owner check through cmd.exe (Windows only)")
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
      rv.returncode == 0 and "1.5.3" in rv.stdout
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
check("U6 a command meeting the held lock says what holds it ('The twice-daily ship to the PC "
      "is running right now')",
      r.returncode == 1
      and "The twice-daily ship to the PC is running right now" in r.stdout + r.stderr,
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
      "PC-verified: 2769." in r.stdout.splitlines()
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

# ═══════════════ Summary ═════════════════════════════════════════════════════
print("\n═══════════════════════════════════════════════════")
print(f"  {PASS} passed, {FAIL} failed")
for name, detail in FAILURES:
    print(f"  ✗ {name}: {detail[:200]}")
sys.exit(1 if FAIL else 0)
