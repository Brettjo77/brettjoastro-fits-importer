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
  --dry-run --verbose --all --clean-source-previews

Requires: Python 3.9+, astropy (pip3 install astropy --break-system-packages)
==============================================================================
"""

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timedelta

# ── Lazy astropy ─────────────────────────────────────────────────────────────
_fits = None

def get_fits():
    global _fits
    if _fits is None:
        try:
            from astropy.io import fits as _f
            _fits = _f
        except ImportError:
            error("astropy not installed. Run:")
            error("  pip3 install astropy --break-system-packages")
            sys.exit(1)
    return _fits


# ═══════════════════════════════════════════════════════════════════════════
# CONFIG (env-overridable so the test harness can redirect everything)
# ═══════════════════════════════════════════════════════════════════════════

# Precedence: environment variable > config.json > generic default.
# config.json lives next to the ledger (~/Library/Application Support/
# Astro Import/config.json) and lets any user relocate destinations without
# touching this script — see config.example.json in the repo.
_CONFIG_PATH = os.path.expanduser(os.environ.get(
    "ASIAIR_CONFIG", "~/Library/Application Support/Astro Import/config.json"))
try:
    with open(_CONFIG_PATH) as _cf:
        _CONFIG = json.load(_cf)
    if not isinstance(_CONFIG, dict):
        _CONFIG = {}
except (OSError, ValueError):
    _CONFIG = {}

def _env_path(var, default):
    value = os.environ.get(var) or _CONFIG.get(var) or default
    return os.path.expanduser(value)

ASIAIR_VOLUME = _env_path("ASIAIR_VOLUME", "/Volumes/ASIAIR")
DEST_DIR      = _env_path("ASIAIR_DEST", "~/Documents/Astro/ZWO ASI AIR")
LIBRARY_DIR   = _env_path("ASIAIR_CAL_LIBRARY", "~/Documents/Astro/ASIAir Calibration Library")
STATE_DIR     = _env_path("ASIAIR_STATE", "~/Library/Application Support/Astro Import")
MIRROR_DIR    = _env_path("ASIAIR_MIRROR", "~/Documents/Astro/Import Status")

# One-time migration from the pre-unification state locations (spec §1).
for _old, _new in [
    (os.path.expanduser("~/Library/Application Support/ASIAir Import"), STATE_DIR),
    (os.path.expanduser("~/Library/Mobile Documents/com~apple~CloudDocs/Astro Tools/ASIAir Import"),
     MIRROR_DIR),
]:
    try:
        if os.path.isdir(_old) and not os.path.isdir(_new):
            shutil.move(_old, _new)
            os.makedirs(_old, exist_ok=True)   # breadcrumb for anything bookmarked
            with open(os.path.join(_old, "MOVED.txt"), "w") as _f:
                _f.write("This folder moved to:\n  %s\n"
                         "(ASIAir + Seestar imports were unified into 'Astro Import', "
                         "2026-07-25)\n" % _new)
    except OSError:
        pass

# ── Seestar (S30 Pro / S50) ─────────────────────────────────────────────────
SEESTAR_VOLUME_ENV = os.environ.get("SEESTAR_VOLUME") or _CONFIG.get("SEESTAR_VOLUME")
SEESTAR_VOLUMES = ([SEESTAR_VOLUME_ENV] if SEESTAR_VOLUME_ENV
                   else ["/Volumes/Seestar", "/Volumes/SEESTAR"])
SEESTAR_DEST_S30 = _env_path("SEESTAR_DEST_S30", "~/Documents/Astro/Seestar S30 Pro")
SEESTAR_DEST_S50 = _env_path("SEESTAR_DEST_S50", "~/Documents/Astro/Seestar S50")
MW_PAIR_TOLERANCE = 7200          # s — MW session pairs to the simultaneous DSO
SEESTAR_S50_ONLY_MODES = ["Solar_photo", "Solar_video", "Planetary_photo",
                          "Planetary_video", "Scenery_photo"]
SEESTAR_NON_DSO_MAP = [("Lunar_photo", "Lunar"), ("Solar_photo", "Solar"),
                       ("Planetary_photo", "Planetary"), ("Scenery_photo", "Scenery"),
                       ("Lunar_video", "Lunar Video"), ("Solar_video", "Solar Video"),
                       ("Planetary_video", "Planetary Video")]
SEESTAR_MODE_FOLDERS = set(x for x, _ in SEESTAR_NON_DSO_MAP) | {"Lunar_video"}
SEESTAR_CATALOG_RE = re.compile(
    r"^(HIP \d+|NGC \d+|IC \d+|M \d+|C \d+|Sh2-\d+|GAIA \d+)")
SEESTAR_HIP_REMAP = {"HIP 24727": "IC 405"}   # goto star → proper catalogue ID
STAMP_RE = re.compile(r"\d{8}-\d{6}")
EQUIPMENT_JSON = _env_path("ASIAIR_EQUIPMENT", "~/Documents/Astro/equipment.json")
RECEIPT_BASE  = _env_path("ASIAIR_RECEIPTS", "~/Documents/Astro/astrolog-receipts")
LEGACY_CUSTOM_NAMES = _env_path("ASIAIR_LEGACY_NAMES", "~/.asiair-custom-names.json")

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
SCOPE_SLOT_EXTRA = {"Seestar S30 Pro": 3, "Seestar S50": 3}

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
    if not sys.stdin.isatty():
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

def notify(message, title="FITS Importer"):
    """macOS notification; silently logged if unavailable/unapproved."""
    try:
        r = subprocess.run(
            ["osascript", "-e", 'on run argv',
             "-e", 'display notification (item 1 of argv) with title (item 2 of argv)',
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

def _atomic_write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=1)
    os.replace(tmp, path)

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
        self.ledger = self._load_json(self.ledger_path)
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

    def save_ledger(self):
        if self.ledger is None:
            return
        if os.path.isfile(self.ledger_path):
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
    def file_entry(self, relpath):
        return self.ledger["files"].get(relpath) if self.ledger else None

    def is_imported(self, relpath, size):
        """Returns 'yes' | 'no' | 'mismatch'."""
        e = self.file_entry(relpath)
        if e is None:
            return "no"
        if e.get("size") not in (None, size):
            return "mismatch"
        return "yes"

    def max_day_number(self, target, device="asiair"):
        best = 0
        for e in self.ledger["files"].values():
            if e.get("device", "asiair") != device:
                continue   # each camera numbers its own Days
            if e.get("target") == target and isinstance(e.get("dayNumber"), int):
                best = max(best, e["dayNumber"])
        return best

    def add_file(self, relpath, **fields):
        self.ledger["files"][relpath] = fields
        self._dirty = True

    def add_calibration(self, relpath, **fields):
        self.ledger["calibration"][relpath] = fields
        self._dirty = True

    def cal_entry(self, relpath):
        return self.ledger["calibration"].get(relpath) if self.ledger else None

    def mark_cleared(self, camera_relpaths, device="asiair"):
        """Flag ledger entries (for ONE device) whose files vanished from that
        camera. An EMPTY scan never clears anything (half-mount safety), and a
        scan of one camera never touches the other's entries."""
        if not camera_relpaths:
            return {}
        newly = defaultdict(int)
        stamp = now_stamp()
        for relpath, e in self.ledger["files"].items():
            if e.get("device", "asiair") != device:
                continue
            if relpath not in camera_relpaths and not e.get("clearedFromCamera"):
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

    # ── mirror publish ───────────────────────────────────────────────────
    def publish_mirror(self):
        try:
            generate_dashboard(self)
        except Exception as e:
            warn(f"dashboard generation failed: {e}")
        try:
            os.makedirs(MIRROR_DIR, exist_ok=True)
            for src in [self.ledger_path, self.history_path, self.skiplist_path,
                        self.names_path, self.report_path,
                        os.path.join(STATE_DIR, "dashboard.html")]:
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

def acquire_lock():
    os.makedirs(STATE_DIR, exist_ok=True)
    if os.path.isfile(LOCK_PATH):
        try:
            with open(LOCK_PATH) as f:
                data = json.load(f)
            pid = int(data.get("pid", 0))
            os.kill(pid, 0)  # raises if dead
            error(f"Another import is already running (pid {pid}, started {data.get('started')}).")
            error("Wait for it to finish, or delete the lock file if it crashed:")
            error(f"  rm '{LOCK_PATH}'")
            return False
        except (OSError, ValueError, json.JSONDecodeError):
            warn("Stale lock file found — clearing it.")
            try:
                os.remove(LOCK_PATH)
            except OSError:
                pass
    with open(LOCK_PATH, "w") as f:
        json.dump({"pid": os.getpid(), "started": now_stamp()}, f)
    return True

def release_lock():
    try:
        os.remove(LOCK_PATH)
    except OSError:
        pass


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

def get_display_name(state, catalog_name, ask=True, dry_run=False):
    common = DSO_NAMES.get(catalog_name) or _DSO_NAMES_CI.get(catalog_name.lower(), "")
    if common:
        return f"{catalog_name} - {common}"
    if catalog_name in state.custom_names:
        custom = state.custom_names[catalog_name]
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
    if name:
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

def copy_file_verified(src, dst, checksum=True):
    """Copy src→dst crash-safely: write .partial, verify, rename.
    Returns (sha256_or_None, size). Raises on failure (partial removed)."""
    partial = dst + ".partial"
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
    return os.path.relpath(path, ASIAIR_VOLUME)

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
    autorun = os.path.join(ASIAIR_VOLUME, AUTORUN_DIR)
    if os.path.isdir(autorun):
        for subdir in ["Bias", "Dark", "Flat"]:
            cdir = os.path.join(autorun, subdir)
            if not os.path.isdir(cdir):
                continue
            for fname in sorted(os.listdir(cdir)):
                low = fname.lower()
                if not low.endswith(".fit") or "_thn." in low:
                    continue
                parsed = parse_calibration_filename(fname)
                if not parsed:
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

def match_calibration_group(group_info, calibration, loose=False, explain=None):
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

def link_calibration_into(state, matched, dest_dir, dry_run=False, checksum=True):
    """Hardlink matched Library frames into dest_dir/calibration/{...}. Idempotent."""
    counts = {"biases": 0, "darks": 0, "flats": 0}
    dest_key = os.path.relpath(dest_dir, DEST_DIR)
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
                # Ask-before-linking gate (Brett, 2026-07-25): when the chosen
                # flats look borrowed (probation flags) or stale, confirm first.
                if (matched["flats"] and matched.get("flatsQuestionable")
                        and not dry_run and not loose):
                    age_txt = (f", {matched['flatsAge']} day(s) old"
                               if matched.get("flatsAge") is not None else "")
                    warn(f"These flats may belong to ANOTHER project "
                         f"(gate flags{age_txt}) — no flats may exist yet for this "
                         f"configuration.")
                    resp = safe_input("Link these flats anyway? [y/N] ", default="n")
                    if resp.lower() != "y":
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
        if args.clean_source_previews and not dry_run and successful > 0:
            removed = 0
            for f in new_files:
                base = os.path.splitext(f["filename"])[0]
                src_dir = os.path.dirname(f["path"])
                for candidate in [base + ".jpg", base + ".jpeg",
                                  base + "_thn.jpg", base + "_thn.jpeg"]:
                    p = os.path.join(src_dir, candidate)
                    if os.path.isfile(p):
                        try:
                            os.remove(p)
                            removed += 1
                        except OSError:
                            pass
            if removed:
                success(f"Cleaned {removed} preview file(s) from source")
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
            os.makedirs(rdir, exist_ok=True)
            rpath = os.path.join(rdir, f"asiair-{receipt['importedAt']}.json")
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
    sscan = scan_seestar(state)
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
    for sroot in (SEESTAR_DEST_S30, SEESTAR_DEST_S50):
        if not os.path.isdir(sroot):
            continue
        for root, _dirs, fnames in os.walk(sroot):
            for fname in fnames:
                if not fname.lower().endswith((".fit", ".fits")):
                    continue
                dest_index.setdefault(fname, os.path.join(root, fname))
                if fname.startswith("MilkyWay_"):
                    stm = STAMP_RE.findall(fname)
                    if stm:
                        dest_index.setdefault(stm[-1] + ".fit",
                                              os.path.join(root, fname))

    svol = seestar_volume()
    upgraded = skipped_archived = failed = 0
    candidates = [(rp, e) for rp, e in state.ledger["files"].items()
                  if e.get("origin") in ("baseline", "merged") and not e.get("verifiedAtImport")]
    info(f"{len(candidates)} baseline/merged entries to reconcile.")
    done = 0
    for relpath, e in candidates:
        done += 1
        show_progress(done, len(candidates), label="Reconciling")
        if e.get("device", "asiair") == "seestar":
            if not svol:
                skipped_archived += 1
                continue
            cam_path = os.path.join(svol, relpath)
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
    out("SAFE TO CLEAR  (every frame imported + verified)")
    reclaim = 0
    if not safe:
        out("  (none yet — run --reconcile to upgrade pre-v2 imports)")
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
    if cal:
        n_ok = 0
        for c in cal:
            e = state.cal_entry(c["relpath"])
            if e and e.get("libraryPath") and e.get("verifiedAtImport"):
                n_ok += 1
        cal_bytes = sum(c["size"] for c in cal)
        verdict = ("SAFE TO CLEAR" if n_ok == len(cal)
                   else f"NOT SAFE — {len(cal) - n_ok} frame(s) not yet verified in Library")
        out(f"Autorun/ calibration: {len(cal)} frames, {human_size(cal_bytes)} — "
            f"{n_ok} in Library ✓ → {verdict}")
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
    sscan = scan_seestar(state)
    if sscan:
        state.mark_cleared(sscan["relpaths"], device="seestar")
        if sscan["disk"]:
            state.ledger["lastSeestarDisk"] = sscan["disk"]
            state._dirty = True
        out(f"SEESTAR {sscan['model']}")
        groups = [(seestar_display(state, t["project_name"]),
                   t["name"], t["files"] + t["stacks"]) for t in sscan["targets"]]
        groups += [(seestar_display(state, p["mosaic_name"]) + " (panels)",
                    p["mosaic_name"].split("_mosaic")[0], p["files"])
                   for p in sscan["panel_sets"]]
        groups += [(n["dest_name"], n["dest_name"], n["files"]) for n in sscan["non_dso"]]
        for display, tname, files in groups:
            if not files:
                continue
            entries, missing = [], 0
            all_ok = True
            for f in files:
                e = state.file_entry(f["relpath"])
                if e is None or state.is_imported(f["relpath"], f["size"]) != "yes":
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
            out(f"  {display:<44} {len(files)} files  {human_size(b)}  {mark}")
            state.ledger.setdefault("lastCategories", {})[f"seestar:{tname}"] = {
                "category": cat, "files": len(files), "bytes": b}
            state._dirty = True
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

    tail = state.history_tail(5)
    if tail:
        out("Recent events:")
        for ev in tail:
            out(f"  {ev.get('ts', '')}  {ev.get('event', ''):<18} "
                f"{ev.get('target', ev.get('frames', ''))}")
    return "\n".join(lines)

def run_report(state):
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
# SEESTAR ADAPTER (S30 Pro / S50) — ported from seestar-import.sh
# Backup-first + SAFE-aware cleanup (unification spec, agreed 2026-07-25).
# Layout preserved exactly: Day folders in the display root ("<sub> Day N"),
# highest stack kept in the root, panels/ for _mosaic_pt, MW pairing intact.
# ═══════════════════════════════════════════════════════════════════════════

def seestar_volume():
    for v in SEESTAR_VOLUMES:
        if os.path.isdir(os.path.join(v, "MyWorks")):
            return v
    return None

def seestar_model(vol):
    """('S30 Pro'|'S50', camera_name, dest_root) via FITS CREATOR; mode-folder
    fallback uses S50-only modes (NOT Lunar — the S30 Pro shoots Lunar too)."""
    myworks = os.path.join(vol, "MyWorks")
    creator = ""
    for root, _d, fnames in os.walk(myworks):
        for fn in fnames:
            if fn.lower().endswith(".fit"):
                try:
                    creator = str(get_fits().getheader(os.path.join(root, fn))
                                  .get("CREATOR", ""))
                except Exception:
                    creator = ""
                break
        if creator or _d is None:
            break
    model = "S30 Pro"
    if "S50" in creator:
        model = "S50"
    elif "S30" in creator:
        model = "S30 Pro"
    elif any(os.path.isdir(os.path.join(myworks, m)) for m in SEESTAR_S50_ONLY_MODES):
        model = "S50"
    camera = f"ZWO Seestar {model}"
    dest = SEESTAR_DEST_S30 if model == "S30 Pro" else SEESTAR_DEST_S50
    return model, camera, dest

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
    model, camera, dest_root = seestar_model(vol)
    myworks = os.path.join(vol, "MyWorks")
    relset = set()

    def fentry(path):
        rel = os.path.relpath(path, vol)
        relset.add(rel)
        try:
            size = os.path.getsize(path)
        except OSError:
            return None
        return {"path": path, "relpath": rel, "filename": os.path.basename(path),
                "size": size}

    def is_new(f):
        return (not state.has_ledger()) or state.is_imported(f["relpath"], f["size"]) != "yes"

    targets, panel_sets, non_dso = [], [], []
    entries = sorted(os.listdir(myworks)) if os.path.isdir(myworks) else []

    for entry in entries:
        if not entry.endswith("_sub"):
            continue
        sub_dir = os.path.join(myworks, entry)
        if not os.path.isdir(sub_dir):
            continue
        base = entry[:-4]
        project_dir = project_name = None
        for cand in sorted(os.listdir(myworks)):
            if not cand.startswith(base):
                continue
            if cand.endswith("_sub") or cand.endswith("_mosaic_pt"):
                continue
            cpath = os.path.join(myworks, cand)
            if os.path.isdir(cpath):
                project_dir, project_name = cpath, cand
                break
        subs = [x for x in (fentry(p) for p in _fits_files(sub_dir)) if x]
        stacks = [x for x in (fentry(p) for p in _fits_files(project_dir, maxdepth=1)) if x] \
            if project_dir else []
        is_mw = base == "MilkyWay" or base.startswith("MilkyWay_")
        targets.append({
            "device": "seestar", "name": base, "sub_name": entry,
            "sub_dir": sub_dir, "project_dir": project_dir,
            "project_name": project_name or base, "is_mw": is_mw,
            "files": subs, "new": [f for f in subs if is_new(f)],
            "stacks": stacks, "new_stacks": [f for f in stacks if is_new(f)],
            "skipped": base in state.skiplist,
        })

    for entry in entries:
        if not entry.endswith("_mosaic_pt"):
            continue
        pt_dir = os.path.join(myworks, entry)
        files = [x for x in (fentry(p) for p in _fits_files(pt_dir, maxdepth=1)) if x]
        panel_sets.append({"pt_name": entry, "pt_dir": pt_dir,
                           "mosaic_name": entry[:-3],  # strip "_pt"
                           "files": files, "new": [f for f in files if is_new(f)]})

    if model == "S50":
        for src_name, dest_name in SEESTAR_NON_DSO_MAP:
            src = os.path.join(myworks, src_name)
            if not os.path.isdir(src):
                continue
            exts = ((".mp4", ".avi", ".mov") if src_name.endswith("_video")
                    else (".fit",))
            files = []
            for fn in sorted(os.listdir(src)):
                if fn.lower().endswith(exts) and "_thn" not in fn.lower():
                    fe = fentry(os.path.join(src, fn))
                    if fe:
                        files.append(fe)
            if files:
                non_dso.append({"src": src, "src_name": src_name, "dest_name": dest_name,
                                "files": files, "new": [f for f in files if is_new(f)]})

    try:
        u = shutil.disk_usage(vol)
        disk = {"total": u.total, "used": u.total - u.free, "free": u.free}
    except OSError:
        disk = None
    return {"device": "seestar", "volume": vol, "model": model, "camera": camera,
            "dest": dest_root, "targets": targets, "panel_sets": panel_sets,
            "non_dso": non_dso, "relpaths": relset, "disk": disk}


def _seestar_ledger_add(state, f, vol, camera, kind, target, display, dest_dir,
                        sha, day=None, exposure=None, night=None):
    state.add_file(f["relpath"], **{
        "filename": f["filename"], "size": f["size"], "sha256": sha,
        "origin": "import", "device": "seestar", "target": target,
        "displayName": display, "sourceType": kind, "camera": camera,
        "scope": camera.replace("ZWO ", ""),
        "exposureSeconds": exposure, "night": night, "dayNumber": day,
        "importedAt": now_stamp(), "dest": dest_dir, "verifiedAtImport": True,
    })

def _seestar_day_number(state, dest_project_dir, day_label, target):
    n = 1
    while os.path.isdir(os.path.join(dest_project_dir, f"{day_label} Day {n}")):
        n += 1
    return max(n, state.max_day_number(target, device="seestar") + 1)

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
        day = _seestar_day_number(state, dest_project_dir, t["sub_name"], t["name"])
        day_dirname = f"{t['sub_name']} Day {day}"
        dest_day = os.path.join(dest_project_dir, day_dirname)
        verified = 0

        if t["new"]:
            info(f"{len(t['new'])} new light frame(s) → {day_dirname}")
            if dry_run:
                log(f"[dry-run] Would copy {len(t['new'])} frame(s)")
            else:
                os.makedirs(dest_day, exist_ok=True)
                done = 0
                for f in t["new"]:
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
                    except Exception as e:
                        warn(f"Copy FAILED for {f['filename']}: {e}")
                    done += 1
                    show_progress(done, len(t["new"]))
                success(f"Copied and verified {verified} light frame(s) to {day_dirname}")

        # stacked files: copy highest, remove older stacks at dest
        best, best_count = None, -1
        for s in t["stacks"]:
            mnum = re.match(r"^Stacked_(\d+)_", s["filename"])
            if mnum and int(mnum.group(1)) > best_count:
                best_count, best = int(mnum.group(1)), s
        if best:
            info(f"Highest stack: {best['filename']} ({best_count} subs)")
            if not dry_run:
                os.makedirs(dest_project_dir, exist_ok=True)
                dst = os.path.join(dest_project_dir, best["filename"])
                if not os.path.isfile(dst):
                    try:
                        sha, _sz = copy_file_verified(best["path"], dst, checksum=checksum)
                        _seestar_ledger_add(state, best, vol, camera, "stack",
                                            t["name"], display, dest_project_dir, sha, day=day)
                        success(f"Copied stacked .fit ({best_count} subs)")
                    except Exception as e:
                        warn(f"Stacked copy failed: {e}")
                jpg = os.path.splitext(best["path"])[0] + ".jpg"
                if os.path.isfile(jpg):
                    try:
                        shutil.copy2(jpg, dest_project_dir)
                    except OSError:
                        pass
                for old in os.listdir(dest_project_dir):
                    if old.startswith("Stacked_") and old.endswith(".fit") \
                            and old != best["filename"]:
                        for suffix in ["", ".jpg", "_thn.jpg"]:
                            p = os.path.join(dest_project_dir,
                                             old[:-4] + suffix if suffix else old)
                            try:
                                os.path.isfile(p) and os.remove(p)
                            except OSError:
                                pass
                        log(f"Removed older stack: {old}")
                for fn in os.listdir(dest_project_dir):
                    if "_thn." in fn:
                        try:
                            os.remove(os.path.join(dest_project_dir, fn))
                        except OSError:
                            pass

        if not dry_run and verified > 0:
            state.history_event("import", device="seestar", target=t["name"],
                                displayName=display, scope=scope_name,
                                frames=verified, dayFolder=dest_day)
            state.save_ledger()
            receipt_sessions.append({
                "targetDisplayName": display, "seestarProjectName": t["project_name"],
                "isMosaic": "_mosaic" in t["project_name"], "dayNumber": day,
                "framesCopied": verified, "stackedCount": max(best_count, 0),
                "fitsFolderPath": dest_day})
            totals["files"] += verified
            dirs = [t["sub_dir"]] + ([t["project_dir"]] if t["project_dir"] else [])
            cleanup.append((display, dirs))
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
            day = 1
            while os.path.isdir(os.path.join(dest_project_dir, f"{display} Day {day}")):
                day += 1
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
                if not os.path.isfile(kdst):
                    try:
                        sha, _sz = copy_file_verified(keeper["path"], kdst, checksum=checksum)
                        _seestar_ledger_add(state, keeper, vol, camera, "mw-stack",
                                            t["name"], display, dest_project_dir, sha, day=day)
                        success(f"Copied stacked keeper → {os.path.basename(kdst)}")
                    except Exception as e:
                        warn(f"Keeper copy failed: {e}")
                kjpg = os.path.splitext(keeper["path"])[0] + ".jpg"
                if os.path.isfile(kjpg):
                    try:
                        shutil.copy2(kjpg, os.path.join(dest_project_dir, f"{prefix}{a_stamp}.jpg"))
                    except OSError:
                        pass
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
            cleanup.append((f"Milky Way (paired) ← {t['sub_name']}", dirs))

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
            cleanup.append((f"{display} (panels)", [ps["pt_dir"]]))
        print()

    # ── S50 non-DSO modes ─────────────────────────────────────────────────
    for nd in scan_s["non_dso"]:
        if not nd["new"]:
            continue
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
            cleanup.append((nd["dest_name"], [nd["src"]]))

    # ── Receipt (per Seestar scope) ───────────────────────────────────────
    if not dry_run and receipt_sessions:
        receipt = {"version": 1, "source": "seestar-import", "telescope": scope_name,
                   "importedAt": now_stamp(), "sessions": receipt_sessions}
        rdir = os.path.join(RECEIPT_BASE, scope_name)
        os.makedirs(rdir, exist_ok=True)
        rpath = os.path.join(rdir, f"seestar-{receipt['importedAt']}.json")
        _atomic_write_json(rpath, receipt)
        success(f"AstroLog receipt saved → {scope_name}/{os.path.basename(rpath)}")

    if not dry_run:
        state.save_ledger()
        seestar_safe_cleanup(state, scan_s, cleanup)
        state.publish_mirror()
    emit("run-done", device="seestar", targets=totals["targets"], files=totals["files"])
    return totals


def seestar_safe_cleanup(state, scan_s, cleanup_candidates):
    """SAFE-aware cleanup (Brett's chosen model): only offer source folders in
    which EVERY .fit/video file is ledger-verified. Default No."""
    vol = scan_s["volume"]
    safe = []
    for label, dirs in cleanup_candidates:
        all_ok, total_bytes = True, 0
        for d in dirs:
            if not d or not os.path.isdir(d):
                continue
            # Superseded stacks (lower Stacked_N than the dir's highest) are
            # disposable by the established keep-highest rule — they never
            # enter the ledger and must not block the offer.
            stack_best = {}
            for root, _dd, fnames in os.walk(d):
                for fn in fnames:
                    ms = re.match(r"^Stacked_(\d+)_", fn)
                    if ms and int(ms.group(1)) > stack_best.get(root, -1):
                        stack_best[root] = int(ms.group(1))
            for root, _dd, fnames in os.walk(d):
                for fn in fnames:
                    low = fn.lower()
                    if "_thn" in low or low.endswith((".jpg", ".jpeg")):
                        continue
                    if not low.endswith((".fit", ".fits", ".mp4", ".avi", ".mov")):
                        continue
                    p = os.path.join(root, fn)
                    try:
                        size = os.path.getsize(p)
                    except OSError:
                        size = None
                    ms = re.match(r"^Stacked_(\d+)_", fn)
                    if ms and int(ms.group(1)) < stack_best.get(root, -1):
                        total_bytes += size or 0   # superseded — deleted, not gating
                        continue
                    rel = os.path.relpath(p, vol)
                    e = state.file_entry(rel)
                    if e is None or not e.get("verifiedAtImport") or e.get("size") != size:
                        all_ok = False
                    else:
                        total_bytes += size or 0
        if all_ok and total_bytes >= 0 and dirs:
            safe.append((label, dirs, total_bytes))
    if not safe:
        return
    print()
    info("These Seestar source folders are fully imported + verified (SAFE):")
    for label, dirs, b in safe:
        log(f"  {label}  ({human_size(b)})  ← " +
            ", ".join(os.path.basename(d.rstrip('/')) for d in dirs if d))
    warn("Deleting frees space on the Seestar. This cannot be undone.")
    resp = safe_input("Delete these SAFE source folders from the Seestar? [y/N] ",
                      default="n")
    if resp.lower() != "y":
        info("Skipped — source files left on the Seestar.")
        return
    stamp = now_stamp()
    for label, dirs, _b in safe:
        for d in dirs:
            if d and os.path.isdir(d) and os.path.realpath(d).startswith(os.path.realpath(vol)):
                shutil.rmtree(d, ignore_errors=True)
                # We know exactly what we deleted — flag it now rather than
                # relying on the next scan (which refuses to clear on empty).
                relprefix = os.path.relpath(d, vol) + os.sep
                for rp, e in state.ledger["files"].items():
                    if e.get("device") == "seestar" and rp.startswith(relprefix) \
                            and not e.get("clearedFromCamera"):
                        e["clearedFromCamera"] = True
                        e["clearedNoticedAt"] = stamp
                        state._dirty = True
        success(f"Cleared {label} from the Seestar")
        state.history_event("seestar-cleared", target=label)
    state.save_ledger()


def seestar_baseline(state, scan_s):
    """Record everything currently on the Seestar as imported (no copying)."""
    stamp = now_stamp()
    added = 0
    camera = scan_s["camera"]
    for t in scan_s["targets"]:
        display = seestar_display(state, t["project_name"], ask=False)
        for f in t["files"] + t["stacks"]:
            if state.file_entry(f["relpath"]) is None:
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
            if state.file_entry(f["relpath"]) is None:
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
            if state.file_entry(f["relpath"]) is None:
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
              "Seestar S30 Pro": 3, "Seestar S50": 3}  # fixed order; others → slot 3

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
    payload = json.dumps(data).replace("</", "<\\/")
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
        s = scan_seestar(state)
        s_new = [t for t in s["targets"] if (t["new"] or t["new_stacks"]) and not t["skipped"]]
        s_panels = [p for p in s["panel_sets"] if p["new"]]
        s_nd = [n for n in s["non_dso"] if n["new"]]
        total_new += len(s_new) + len(s_panels) + len(s_nd)
        n_files += sum(len(t["new"]) for t in s_new) + sum(len(p["new"]) for p in s_panels)
        n_bytes += sum(sum(f["size"] for f in t["new"]) for t in s_new)
        for t in sorted(s_new, key=lambda t: -len(t["new"]))[:4]:
            disp = seestar_display(state, t["project_name"])
            rows.append(f"   {'[Seestar] ' if both else ''}{disp}  —  {len(t['new']):,} frame(s)")
        if s["disk"]:
            d = s["disk"]
            storages.append(f"Seestar {human_size(d['used'])}/{human_size(d['total'])} "
                            f"({human_size(d['free'])} free)")

    if not state.has_ledger():
        summary = "No import ledger yet — first run will offer a baseline."
    elif total_new:
        lines = [f"{total_new} target(s) have new frames — "
                 f"{n_files:,} files, {human_size(n_bytes)}", ""] + rows
        summary = "\\n".join(lines)
    else:
        summary = "Nothing new. Every frame is backed up."
    storage = " · ".join(storages) if storages else "Camera storage: unknown"
    print(f"ASIAIR-SCAN|COUNT|{total_new}")
    print(f"ASIAIR-SCAN|SUMMARY|{summary}")
    print(f"ASIAIR-SCAN|STORAGE|{storage}")

def _choose_from_list(items, prompt, title, multiple=True, timeout=3600):
    """osascript choose from list via argv (quote-safe), killable timeout."""
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
        s = scan_seestar(state)
        for t in sorted([t for t in s["targets"]
                         if (t["new"] or t["new_stacks"]) and not t["skipped"]],
                        key=lambda t: -len(t["new"])):
            idx += 1
            disp = seestar_display(state, t["project_name"], ask=True, dry_run=args.dry_run)
            nb = sum(f["size"] for f in t["new"])
            entries.append(("seestar", t["name"],
                            f"{idx} · {disp} — {len(t['new'])} new "
                            f"({human_size(nb)}) — Seestar {s['model']}"))
        for p in s["panel_sets"]:
            if p["new"]:
                idx += 1
                disp = seestar_display(state, p["mosaic_name"]) + " (panels)"
                entries.append(("seestar", p["mosaic_name"].split("_mosaic")[0],
                                f"{idx} · {disp} — {len(p['new'])} new panel(s)"))
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
        sscan = scan_seestar(state)
        if sscan:
            if not args.dry_run:
                state.mark_cleared(sscan["relpaths"], device="seestar")
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
        r = subprocess.run(["diskutil", "eject", v], capture_output=True, text=True)
        if r.returncode == 0:
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
    try:
        subprocess.run(["open", target_path], capture_output=True, timeout=10)
    except Exception:
        pass

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
    p.add_argument("--skip-target", metavar="NAME")
    p.add_argument("--unskip-target", metavar="NAME")
    p.add_argument("--explain-cal", action="store_true")
    p.add_argument("--loose-cal", action="store_true")
    p.add_argument("--no-checksum", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--all", action="store_true")
    p.add_argument("--clean-source-previews", action="store_true")
    args = p.parse_args()
    VERBOSE = args.verbose

    if args.targets is not None and len(args.targets) == 0:
        error("--targets given with no names.")
        sys.exit(2)

    state = State()

    # State-only commands that don't need the camera:
    if args.dashboard:
        open_dashboard(state)
        return
    if args.restore_ledger:
        state.restore_from_mirror()
        return
    if args.refresh_metadata:
        run_refresh_metadata(state)
        return
    if args.unbaseline:
        run_unbaseline(state, args.unbaseline)
        return
    if args.skip_target:
        if args.skip_target not in state.skiplist:
            state.skiplist.append(args.skip_target)
            state.save_skiplist()
            state.history_event("skiplist", target=args.skip_target, skipped=True)
        success(f"Never import: {args.skip_target}")
        state.publish_mirror()
        return
    if args.unskip_target:
        if args.unskip_target in state.skiplist:
            state.skiplist.remove(args.unskip_target)
            state.save_skiplist()
            state.history_event("skiplist", target=args.unskip_target, skipped=False)
        success(f"Un-skipped: {args.unskip_target}")
        state.publish_mirror()
        return

    # Everything else needs a camera (either device):
    asiair_here = os.path.isdir(ASIAIR_VOLUME)
    svol = seestar_volume()
    if not asiair_here and not svol:
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
            warn("No import ledger found.")
            if os.path.isfile(os.path.join(MIRROR_DIR, "ledger.json")):
                if state.restore_from_mirror():
                    pass
            if not state.has_ledger():
                if args.baseline or safe_input(
                        "Mark everything currently on the camera as already imported? "
                        "(Recommended on first run) [y/N] ", default="n").lower() == "y":
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
            sscan = scan_seestar(state)
            if not args.dry_run:
                state.mark_cleared(sscan["relpaths"], device="seestar")
                if sscan["disk"]:
                    state.ledger["lastSeestarDisk"] = sscan["disk"]
                state._dirty = True
            run_seestar_import(state, sscan, args, only_targets=only)
        offer_eject(args)
    finally:
        release_lock()


if __name__ == "__main__":
    main()
