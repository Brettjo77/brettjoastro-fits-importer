#!/bin/bash
# =============================================================================
# BrettjoAstro FITS Importer — Install / Update  (v5)
# =============================================================================
# One engine, one panel, one watcher for BOTH cameras (ZWO ASIAir + Seestar).
# Works on any Mac: paths derive from $HOME, and optional per-user overrides
# live in ~/Library/Application Support/Astro Import/config.json
# (see config.example.json).
#
# Usage:  bash install-scripts.sh        (from the repo folder)
#
# What gets installed:
#   ~/bin/astro-import.py          <- import engine (ASIAir + Seestar)
#   ~/bin/astro-app.py             <- control panel (localhost:8765)
#   ~/bin/astro-watch.sh           <- drive watcher for both cameras
#   ~/bin/asiair-import.py         <- compatibility copy of the same engine
#   ~/Applications/BrettjoAstro FITS Importer.app  <- app wrapper (ad-hoc
#                                     signed here) giving the panel its own
#                                     identity for macOS disk permissions
#   ~/Desktop/Restart FITS Importer.command  <- one-double-click panel restart
#   ~/Library/LaunchAgents/com.brettjohnson.astro-import.plist  (single agent;
#                                     $HOME substituted at install time)
#
# Python: every launcher prefers python.org Python (/usr/local/bin/python3)
# when installed, falling back to Apple's /usr/bin/python3. python.org Python
# is strongly recommended on modern macOS: Apple's own Python is a "platform
# binary" that is silently DENIED access to USB drives from background
# launches and is never allowed to ask; python.org Python may simply ask,
# and one Allow makes the hands-free flow permanent.
#
# Upgrading from the pre-1.0 personal setup? One-time steps run automatically:
#   - a config.json is seeded to keep the iCloud "Astro Tools" mirror layout
#   - old rollback copies are kept (asiair-import-v1/-v2.py, seestar legacy)
#   - the two old LaunchAgents are unloaded and removed
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BIN_DIR="$HOME/bin"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
# $HOME escaped for a sed replacement ("|", "&" and "\" would break it, V9)
SED_HOME=$(printf '%s' "$HOME" | sed 's/[|&\\]/\\&/g')
STATE_DIR="$HOME/Library/Application Support/Astro Import"
FAILED=0

log()     { echo "  $1"; }
info()    { echo "▸ $1"; }
success() { echo "✓ $1"; }
warn()    { echo "⚠ $1"; }
error()   { echo "✗ $1" >&2; }

echo "═══════════════════════════════════════════════════════════════"
echo "  BrettjoAstro FITS Importer — Install / Update (v5)"
echo "═══════════════════════════════════════════════════════════════"
echo ""
info "Source: $SCRIPT_DIR"
echo ""

mkdir -p "$BIN_DIR"
mkdir -p "$LAUNCH_AGENTS_DIR"

install_file() {
    local src="$1"
    local dst="$2"
    local make_exec="${3:-false}"
    local fname
    fname="$(basename "$src")"

    if [ ! -f "$src" ]; then
        warn "Source not found: $fname — skipping"
        FAILED=$((FAILED + 1))
        return 0    # never abort the installer
    fi
    cp "$src" "$dst"
    if [ "$make_exec" = "true" ]; then
        chmod +x "$dst"
    fi
    success "Installed $fname → $dst"
}

# ── One-time: preserve the pre-1.0 iCloud "Astro Tools" layout ──────────────
# Installs that predate config.json published their mirror (and read
# equipment/receipts) from iCloud. Changing defaults must never move a live
# install, so if that layout exists and no config.json does, seed one.
ICLOUD_TOOLS="$HOME/Library/Mobile Documents/com~apple~CloudDocs/Astro Tools"
if [ ! -f "$STATE_DIR/config.json" ] && [ -f "$ICLOUD_TOOLS/Astro Import/ledger.json" ]; then
    mkdir -p "$STATE_DIR"
    cat > "$STATE_DIR/config.json" <<'CONF'
{
  "ASIAIR_MIRROR": "~/Library/Mobile Documents/com~apple~CloudDocs/Astro Tools/Astro Import",
  "ASIAIR_EQUIPMENT": "~/Library/Mobile Documents/com~apple~CloudDocs/Astro Tools/equipment.json",
  "ASIAIR_RECEIPTS": "~/Library/Mobile Documents/com~apple~CloudDocs/Brettjo77GitHub/AstroLog/astrolog-receipts"
}
CONF
    success "Seeded config.json preserving the existing Astro Tools mirror layout"
fi

# ── One-time rollback copies (no-ops on a fresh Mac) ────────────────────────
if [ -f "$BIN_DIR/asiair-import.py" ] && [ ! -f "$BIN_DIR/asiair-import-v1.py" ]; then
    if ! grep -q 'Backup-First' "$BIN_DIR/asiair-import.py" 2>/dev/null; then
        cp "$BIN_DIR/asiair-import.py" "$BIN_DIR/asiair-import-v1.py"
        success "Kept previous version as asiair-import-v1.py (rollback copy)"
    fi
fi
if [ -f "$BIN_DIR/asiair-import.py" ] && [ ! -f "$BIN_DIR/asiair-import-v2.py" ]; then
    if grep -q 'Backup-First' "$BIN_DIR/asiair-import.py" 2>/dev/null \
       && ! grep -q 'SEESTAR ADAPTER' "$BIN_DIR/asiair-import.py" 2>/dev/null; then
        cp "$BIN_DIR/asiair-import.py" "$BIN_DIR/asiair-import-v2.py"
        success "Kept ASIAir-only v2 as asiair-import-v2.py (rollback copy)"
    fi
fi
if [ -f "$BIN_DIR/seestar-import.sh" ] && [ ! -f "$BIN_DIR/seestar-import-legacy.sh" ]; then
    mv "$BIN_DIR/seestar-import.sh" "$BIN_DIR/seestar-import-legacy.sh"
    success "Retired seestar-import.sh → seestar-import-legacy.sh (rollback copy)"
fi

info "Installing scripts to $BIN_DIR..."
install_file "$SCRIPT_DIR/astro-import.py"  "$BIN_DIR/astro-import.py"  true
install_file "$SCRIPT_DIR/astro-app.py"     "$BIN_DIR/astro-app.py"     true
install_file "$SCRIPT_DIR/astro-watch.sh"   "$BIN_DIR/astro-watch.sh"   true
install_file "$SCRIPT_DIR/selftest.py"      "$BIN_DIR/selftest.py"      true
# Compatibility copy: `asiair-import.py` IS the unified engine now.
if [ -f "$BIN_DIR/astro-import.py" ]; then
    cp "$BIN_DIR/astro-import.py" "$BIN_DIR/asiair-import.py"
    chmod +x "$BIN_DIR/asiair-import.py"
    success "Compatibility copy: asiair-import.py → same unified engine"
fi
echo ""

# ── App wrapper: the panel's own identity for macOS disk permissions ────────
APP_SRC="$SCRIPT_DIR/BrettjoAstro FITS Importer.app"
APP_DST="$HOME/Applications/BrettjoAstro FITS Importer.app"
if [ -d "$APP_SRC" ]; then
    mkdir -p "$HOME/Applications"
    rm -rf "$APP_DST"
    cp -R "$APP_SRC" "$APP_DST"
    chmod +x "$APP_DST/Contents/MacOS/launcher"
    if command -v codesign >/dev/null 2>&1; then
        xattr -cr "$APP_DST" 2>/dev/null || true
        if codesign --force --deep -s - "$APP_DST" 2>/dev/null; then
            success "Installed + ad-hoc signed BrettjoAstro FITS Importer.app"
        else
            warn "App installed but codesign failed — sign manually:"
            log "  xattr -cr \"$APP_DST\" && codesign --force --deep -s - \"$APP_DST\""
        fi
    else
        success "Installed BrettjoAstro FITS Importer.app (codesign unavailable — skipped signing)"
    fi
    log "First time only: right-click the app in ~/Applications → Open (Gatekeeper)."
else
    warn "App bundle not found in the repo folder — skipping"
fi

# ── Desktop restart button (Terminal context — the route that always works) ─
if [ -f "$SCRIPT_DIR/Restart FITS Importer.command" ]; then
    cp "$SCRIPT_DIR/Restart FITS Importer.command" "$HOME/Desktop/"
    chmod +x "$HOME/Desktop/Restart FITS Importer.command"
    success "Installed Restart FITS Importer.command → Desktop"
fi
echo ""

# Stop any running panel so the next launch picks up the new build
if pkill -f "[Pp]ython[^ ]* .*(asiair|astro)-app\.py" 2>/dev/null; then
    success "Stopped the running panel (the watcher restarts it on next plug-in)"
fi

info "Retiring old LaunchAgents (replaced by com.brettjohnson.astro-import)..."
for label in com.brettjohnson.seestar-import com.brettjohnson.asiair-import; do
    plist_path="$LAUNCH_AGENTS_DIR/$label.plist"
    if [ -f "$plist_path" ]; then
        launchctl unload "$plist_path" 2>/dev/null || true
        rm -f "$plist_path"
        success "Removed $label"
    fi
done

info "Installing the LaunchAgent (with \$HOME substituted)..."
new_plist="$LAUNCH_AGENTS_DIR/com.brettjohnson.astro-import.plist"
if [ -f "$new_plist" ]; then
    launchctl unload "$new_plist" 2>/dev/null || true
fi
if [ -f "$SCRIPT_DIR/com.brettjohnson.astro-import.plist" ]; then
    mkdir -p "$HOME/Library/Logs"
    sed "s|__HOME__|$SED_HOME|g" "$SCRIPT_DIR/com.brettjohnson.astro-import.plist" > "$new_plist"
    success "Installed com.brettjohnson.astro-import.plist → $new_plist"
    if launchctl load "$new_plist" 2>/dev/null; then
        success "Loaded com.brettjohnson.astro-import"
    else
        warn "Could not load com.brettjohnson.astro-import — may need to log out/in"
    fi
else
    warn "Source not found: com.brettjohnson.astro-import.plist — skipping"
    FAILED=$((FAILED + 1))
fi
echo ""

ship_plist="$LAUNCH_AGENTS_DIR/com.brettjohnson.astro-ship.plist"
# The ship agent is only for people who keep an archive on another computer
# (see PC-SYNC.md). Installed when an archive URL is configured, or when it
# was already installed (an upgrade) — never by default (1.4.3, review S2).
ARCHIVE_CONFIGURED=$(/usr/bin/python3 - <<'PY' 2>/dev/null
import json, os
p = os.path.expanduser("~/Library/Application Support/Astro Import/config.json")
try:
    print("yes" if (json.load(open(p)) or {}).get("ASTRO_ARCHIVE_URL") else "")
except Exception:
    print("")
PY
)
if [ -f "$ship_plist" ]; then
    launchctl unload "$ship_plist" 2>/dev/null || true
    ARCHIVE_CONFIGURED=yes
fi
if [ -z "$ARCHIVE_CONFIGURED" ]; then
    info "No PC archive configured — skipping the ship agent (optional; see PC-SYNC.md)."
elif [ -f "$SCRIPT_DIR/com.brettjohnson.astro-ship.plist" ]; then
    info "Installing the twice-daily ship agent (files verified frames to the PC archive)..."
    mkdir -p "$HOME/Library/Logs"
    sed "s|__HOME__|$SED_HOME|g" "$SCRIPT_DIR/com.brettjohnson.astro-ship.plist" > "$ship_plist"
    if launchctl load "$ship_plist" 2>/dev/null; then
        success "Loaded com.brettjohnson.astro-ship (09:00 and 21:00; mounts the share itself)"
    else
        warn "Could not load com.brettjohnson.astro-ship — may need to log out/in"
    fi
else
    warn "Source not found: com.brettjohnson.astro-ship.plist — skipping"
fi
echo ""

info "Checking Python..."
if [ -x /usr/local/bin/python3 ]; then
    PYCHECK=/usr/local/bin/python3
    success "python.org Python found — launchers will prefer it (recommended)"
else
    PYCHECK=/usr/bin/python3
    warn "python.org Python not found — falling back to Apple's /usr/bin/python3."
    log "Recommended: install from https://www.python.org/downloads/ — Apple's"
    log "Python is barred from asking for USB-drive access on background"
    log "launches; python.org Python asks once and the grant is permanent."
fi
if "$PYCHECK" -c "from astropy.io import fits" 2>/dev/null; then
    success "astropy is installed for $PYCHECK"
else
    warn "astropy not found for $PYCHECK — the import engine requires it"
    log "Run: $PYCHECK -m pip install astropy   (add --user if permissions complain)"
    FAILED=$((FAILED + 1))
fi
echo ""

echo "═══════════════════════════════════════════════════════════════"
if [ "$FAILED" -gt 0 ]; then
    warn "Finished with $FAILED problem(s) — see warnings above."
    echo ""
    exit 1
fi
success "All done! BrettjoAstro FITS Importer installed."
echo ""
log "First run:"
log "  1. Plug in a camera (ASIAir and/or Seestar) — the panel opens by itself"
log "     (or open http://127.0.0.1:8765). Scanning only reads the camera."
log "  2. Tick what you want and press Import. The first import starts the"
log "     ledger and backs everything up, verified byte for byte."
log "  Already have copies of everything on this Mac? Instead of step 2, run"
log "     python3 ~/bin/astro-import.py --baseline"
log "  to record them WITHOUT copying (read the audit list it prints)."
log ""
log "macOS permission (once): if a dialog asks to allow access to files on a"
log "removable volume, click Allow — that makes the hands-free flow permanent."
log "If a background-started panel ever logs 'Operation not permitted', use"
log "the Desktop 'Restart FITS Importer' button and see README → Permissions."
log ""
log "Optional custom paths: copy config.example.json to"
log "  ~/Library/Application Support/Astro Import/config.json and edit."
echo ""
