#!/bin/bash
# =============================================================================
# BrettjoAstro FITS Importer — Install / Update  (v4)
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
#   ~/Library/LaunchAgents/com.brettjohnson.astro-import.plist  (single agent;
#                                     $HOME substituted at install time)
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
STATE_DIR="$HOME/Library/Application Support/Astro Import"
FAILED=0

log()     { echo "  $1"; }
info()    { echo "▸ $1"; }
success() { echo "✓ $1"; }
warn()    { echo "⚠ $1"; }
error()   { echo "✗ $1" >&2; }

echo "═══════════════════════════════════════════════════════════════"
echo "  BrettjoAstro FITS Importer — Install / Update (v4)"
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
# Compatibility copy: `asiair-import.py` IS the unified engine now.
if [ -f "$BIN_DIR/astro-import.py" ]; then
    cp "$BIN_DIR/astro-import.py" "$BIN_DIR/asiair-import.py"
    chmod +x "$BIN_DIR/asiair-import.py"
    success "Compatibility copy: asiair-import.py → same unified engine"
fi
echo ""

# Stop any running panel so the next launch picks up the new build
if pkill -f "asiair-app.py|astro-app.py" 2>/dev/null; then
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
    sed "s|__HOME__|$HOME|g" "$SCRIPT_DIR/com.brettjohnson.astro-import.plist" > "$new_plist"
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

info "Checking Python dependencies..."
if /usr/bin/python3 -c "from astropy.io import fits" 2>/dev/null; then
    success "astropy is installed"
else
    warn "astropy not found — the import engine requires it"
    log "Run: /usr/bin/python3 -m pip install --user astropy"
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
log "First run (in order — every step before 5 is read-only):"
log "  1. Plug in a camera (ASIAir and Seestar can both be attached)"
log "  2. python3 ~/bin/astro-import.py --scan-only    (sanity check)"
log "  3. python3 ~/bin/astro-import.py --report"
log "  4. python3 ~/bin/astro-import.py --baseline     (existing files join the"
log "     ledger without copying — read the audit list it prints)"
log "  5. Import via the panel: http://127.0.0.1:8765"
log ""
log "Optional custom paths: copy config.example.json to"
log "  ~/Library/Application Support/Astro Import/config.json and edit."
echo ""
