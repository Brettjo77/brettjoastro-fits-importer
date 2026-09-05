#!/usr/bin/env python3
"""Sandbox test suite for asiair-import.py v2 (spec §12).
Simulated ASIAIR volume with real (minimal) FITS files; every scenario runs
the actual script as a subprocess with env-redirected paths."""

import json
import os
import shutil
import subprocess
import sys
import tempfile

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
        self.env = dict(os.environ)
        self.env.update({
            "ASIAIR_VOLUME": self.cam, "ASIAIR_DEST": self.dest,
            "ASIAIR_CAL_LIBRARY": self.lib, "ASIAIR_STATE": self.state,
            "ASIAIR_MIRROR": self.mirror, "ASIAIR_EQUIPMENT": eqp,
            "ASIAIR_RECEIPTS": self.receipts,
            "ASIAIR_LEGACY_NAMES": os.path.join(self.root, "no-legacy.json"),
            "ASIAIR_CONFIG": os.path.join(self.root, "no-config.json"),
            # keep the unified engine blind to any real Seestar in these chains
            "SEESTAR_VOLUME": os.path.join(self.root, "no-seestar"),
        })

    def run(self, *args, stdin=""):
        r = subprocess.run([sys.executable, SCRIPT, *args], env=self.env,
                           input=stdin, capture_output=True, text=True, timeout=120)
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

# A7: reconcile upgrades entries whose dest copies exist
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
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_env_helper as teh  # noqa: E402

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
                   capture_output=True, text=True, timeout=120)
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

print("\n── Chain S16: per-sub JPEG riders (S50 Pro first light) ──────")
S16 = teh.Env("S16", asiair=False, seestar=True)

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

# ═══════════════ Summary ═════════════════════════════════════════════════════
print("\n═══════════════════════════════════════════════════")
print(f"  {PASS} passed, {FAIL} failed")
for name, detail in FAILURES:
    print(f"  ✗ {name}: {detail[:200]}")
sys.exit(1 if FAIL else 0)
