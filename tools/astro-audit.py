#!/usr/bin/env python3
"""astro-audit.py: what this computer's astro folder holds, and what of it
is already on the archive. READ ONLY: it never deletes, moves, renames or
changes a file, on this computer or on the archive. The one thing it writes
is its own report, a CSV in your home folder.

It uses the installed FITS Importer for its settings (where the archive is,
where your frames live) and for the PC's list of the archive (the inventory
the PC's nightly job writes). Every file under the astro folder is put in
one of four groups:

  proven     the archive holds the same bytes: the PC has checked them, or
             this computer's ledger hash equals the PC's hash for that file
  same name  a file with the same name and size is on the archive, but no
             hash proves it is the same bytes yet (use --hash to check)
  different  same name and size on the archive, but the bytes differ
  not on     no file of that name and size on the archive: keep it

Mac:     /usr/local/bin/python3 astro-audit.py [--hash] [FOLDER]
Windows: py -3 -X utf8 astro-audit.py [--hash] [FOLDER]
"""
import argparse
import csv
import datetime
import hashlib
import importlib.util
import os
import platform
import sys
import time

FRAME_EXT = {".fit", ".fits", ".fts"}
WORK_EXT = {".xisf", ".tif", ".tiff", ".psd", ".psb", ".xosm", ".jpg", ".jpeg", ".png",
            ".pxiproject", ".xdrz", ".xnml", ".ssf", ".seq"}
CLUTTER = {".ds_store", "thumbs.db", "desktop.ini"}
GROUPS = ("proven", "same name", "different", "not on")


def gb(n):
    if n >= 1e8:
        return f"{n / 1e9:,.1f} GB"
    return f"{n / 1e6:,.0f} MB" if n >= 1e6 else f"{n / 1e3:,.0f} KB"


def load_engine(path):
    if not os.path.isfile(path):
        sys.exit(f"The FITS Importer was not found at {path}. Pass its path with --engine.")
    spec = importlib.util.spec_from_file_location("astro_import_engine", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def default_engine():
    if platform.system() == "Windows":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~/AppData/Local")
        return os.path.join(base, "BrettjoAstro", "bin", "astro-import.py")
    return os.path.expanduser("~/bin/astro-import.py")


def kind_of(name):
    ext = os.path.splitext(name)[1].lower()
    if ext in FRAME_EXT:
        return "frame"
    if ext in WORK_EXT:
        return "work"
    return "other"


def sha256_of(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def archive_index(m):
    """{(name lower, size): [(relpath, sha256 or None)]} from the PC's
    inventory, plus the inventory's path and age."""
    inv = m._latest_inventory_path()
    if not inv:
        return None, None, None
    idx = {}
    rows = 0
    for r in m._iter_jsonl_rows(inv):
        rel = r.get("relpath")
        if r.get("retired") or not isinstance(rel, str) or "/" not in rel:
            continue
        try:
            size = int(r.get("size"))
        except (TypeError, ValueError):
            continue
        sha = r.get("sha256") if isinstance(r.get("sha256"), str) else None
        name = rel.rsplit("/", 1)[1]
        idx.setdefault((name.lower(), size), []).append((rel, sha))
        stem, ext = os.path.splitext(name)
        if "__" in stem:                    # the ship files a clash as <name>__<slug>.<ext>
            idx.setdefault((stem.rsplit("__", 1)[0].lower() + ext.lower(), size), []).append((rel, sha))
        rows += 1
    try:
        age_h = (time.time() - os.path.getmtime(inv)) / 3600
    except OSError:
        age_h = None
    return idx, inv, (rows, age_h)


def ledger_index(m):
    """{normalised local path: (sha256, archive checked)} for the frames this
    computer imported, from its own ledger. Read only."""
    out = {}
    try:
        st = m.State()
    except Exception as e:                  # an unreadable ledger only means no ledger proof
        print(f"  (this computer's ledger could not be read: {e}; hashes from it are not used)")
        return out
    files = (st.ledger or {}).get("files") or {}
    for e in files.values():
        if not isinstance(e, dict) or not e.get("dest") or not e.get("filename"):
            continue
        p = os.path.normcase(os.path.abspath(os.path.join(e["dest"], e["filename"])))
        out[p] = (e.get("sha256"), bool(e.get("archiveVerifiedAt")))
    return out


def lookup(idx, name, size):
    """Archive rows for a file: by its own name, or, for a copy renamed with
    a prefix (Collect Lights puts one in front), by the name after it."""
    hits = idx.get((name.lower(), size))
    if hits:
        return hits
    parts = name.split("_")
    for i in range(1, min(len(parts), 6)):
        hits = idx.get(("_".join(parts[i:]).lower(), size))
        if hits:
            return hits
    return []


def main():
    ap = argparse.ArgumentParser(description="Read-only: what this computer's astro folder holds "
                                             "and what of it is already on the archive.")
    ap.add_argument("folder", nargs="?", help="the folder to audit (default: the importer's own "
                                              "workbench, e.g. Documents/Astro)")
    ap.add_argument("--hash", action="store_true",
                    help="also read 'same name' files to prove or disprove them (slower)")
    ap.add_argument("--engine", default=default_engine(), help="path to astro-import.py")
    ap.add_argument("--out", help="where to write the CSV (default: your home folder)")
    ap.add_argument("--top", type=int, default=30, help="folders listed per section")
    a = ap.parse_args()

    m = load_engine(a.engine)
    machine = "PC" if m.IS_WINDOWS else "Mac"
    root = os.path.abspath(os.path.expanduser(a.folder or m.workbench_root()))
    if not os.path.isdir(root):
        sys.exit(f"Not a folder: {root}")
    if m._is_archive_root(root) or m._within(root, m.ARCHIVE_MOUNT):
        sys.exit(f"{root} is the archive itself. Point this at this computer's own astro folder.")

    print(f"Astro audit of the {machine} (read only: nothing is changed or deleted)")
    print(f"  folder:  {root}")
    idx, inv, meta = archive_index(m)
    if idx is None:
        sys.exit(f"The PC's list of the archive was not found under {m.ARCHIVE_MOUNT}. "
                 "Is the archive connected? Nothing was audited.")
    rows, age_h = meta
    age = f", {age_h:.0f} h old" if age_h is not None else ""
    print(f"  archive: {m.ARCHIVE_MOUNT} ({rows:,} files in the PC's list {os.path.basename(inv)}{age})")
    if age_h is not None and age_h > 48:
        print("  ! The PC's list is more than two days old. Files shipped since then show as 'not on'.")
    led = ledger_index(m)
    print(f"  ledger:  {len(led):,} files this computer imported")
    print("  Reading the folder…", flush=True)

    files = []
    clutter = [0, 0]
    skipped = 0
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if not d.startswith(".")]
        for fn in fns:
            low = fn.lower()
            p = os.path.join(dp, fn)
            try:
                st = os.lstat(p)
            except OSError:
                skipped += 1
                continue
            if not os.path.isfile(p) or os.path.islink(p):
                continue
            if low in CLUTTER or fn.startswith("._"):
                clutter[0] += 1
                clutter[1] += st.st_size
                continue
            files.append((p, fn, st.st_size))
    total = sum(s for _p, _f, s in files)
    print(f"  {len(files):,} files, {gb(total)}"
          + (f" (plus {clutter[0]:,} system clutter files, {gb(clutter[1])})" if clutter[0] else ""))

    to_hash = []
    result = []
    for p, fn, size in files:
        hits = lookup(idx, fn, size)
        lk = led.get(os.path.normcase(os.path.abspath(p)))
        group, where = "not on", ""
        if hits:
            where = hits[0][0]
            group = "same name"
            if lk and lk[0]:
                shas = {h for _r, h in hits if h}
                if lk[1] or lk[0] in shas:
                    group = "proven"
                elif shas and lk[0] not in shas:
                    group = "different"
            elif lk and lk[1]:
                group = "proven"
            if group == "same name" and any(h for _r, h in hits):
                to_hash.append(len(result))
        result.append([p, fn, size, kind_of(fn), group, where])

    if a.hash and to_hash:
        n_bytes = sum(result[i][2] for i in to_hash)
        print(f"  Checking {len(to_hash):,} 'same name' files by their bytes ({gb(n_bytes)})…", flush=True)
        done, t0, last = 0, time.time(), 0.0
        for i in to_hash:
            r = result[i]
            hits = lookup(idx, r[1], r[2])
            shas = {h for _rel, h in hits if h}
            try:
                mine = sha256_of(r[0])
            except OSError:
                continue
            r[4] = "proven" if mine in shas else "different"
            done += r[2]
            if time.time() - last > 15:
                last = time.time()
                rate = done / max(0.1, last - t0)
                print(f"    {gb(done)} of {gb(n_bytes)}, {rate / 1e6:,.0f} MB/s", flush=True)

    # totals
    print("\nWhat this folder holds")
    print(f"  {'':12} {'frames':>12} {'work files':>12} {'other':>12} {'all':>12}")
    label = {"proven": "on archive, proven", "same name": "on archive, unproven",
             "different": "DIFFERENT bytes", "not on": "NOT on archive"}
    for g in GROUPS:
        sz = {k: sum(r[2] for r in result if r[4] == g and r[3] == k) for k in ("frame", "work", "other")}
        if sum(sz.values()) == 0:
            continue
        print(f"  {label[g]:22} {gb(sz['frame']):>10} {gb(sz['work']):>12} {gb(sz['other']):>12} "
              f"{gb(sum(sz.values())):>12}")

    # by folder: two levels below the root (scope / target)
    by = {}
    for p, fn, size, kind, g, _w in result:
        rel = os.path.relpath(p, root).split(os.sep)
        key = os.sep.join(rel[:2]) if len(rel) > 2 else (rel[0] if len(rel) > 1 else ".")
        d = by.setdefault(key, {x: 0 for x in GROUPS})
        d[g] += size

    def table(title, keyfn, filt):
        rows_ = sorted(((k, v) for k, v in by.items() if filt(v)), key=keyfn, reverse=True)[:a.top]
        if not rows_:
            return
        print(f"\n{title}")
        print(f"  {'proven':>9} {'unproven':>9} {'NOT on':>9}  folder")
        for k, v in rows_:
            print(f"  {gb(v['proven']):>9} {gb(v['same name']):>9} {gb(v['not on'] + v['different']):>9}  {k}")

    table("Folders with the most that is NOT on the archive (keep these, or ship them)",
          lambda kv: kv[1]["not on"] + kv[1]["different"], lambda v: v["not on"] + v["different"] > 0)
    table("Folders whose contents are all on the archive, proven (candidates to free)",
          lambda kv: kv[1]["proven"],
          lambda v: v["proven"] > 0 and v["not on"] + v["different"] + v["same name"] == 0)
    table("Folders on the archive by name and size, not yet proven (run with --hash to check)",
          lambda kv: kv[1]["same name"], lambda v: v["same name"] > 0)

    stamp = datetime.datetime.now().strftime("%Y-%m-%d-%H%M")
    out = a.out or os.path.join(os.path.expanduser("~"), f"astro-audit-{machine}-{stamp}.csv")
    try:
        with open(out, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["path", "size_bytes", "kind", "group", "archive_copy"])
            for p, _fn, size, kind, g, where in sorted(result):
                safe = lambda s: ("'" + s) if s[:1] in ("=", "+", "-", "@") else s
                w.writerow([safe(p), size, kind, g, safe(where)])
        print(f"\nEvery file is listed in {out}")
    except OSError as e:
        print(f"\nThe list could not be saved ({e}).")
    if skipped:
        print(f"{skipped:,} files could not be read and are not counted.")
    print("Nothing was changed or deleted.")


if __name__ == "__main__":
    main()
