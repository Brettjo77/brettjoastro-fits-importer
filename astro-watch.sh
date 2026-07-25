#!/bin/bash
# =============================================================================
# BrettjoAstro FITS Importer — drive watcher (ONE watcher for both cameras)
# =============================================================================
# Plug in either camera → notification → the FITS Importer panel opens (or
# focuses) in your browser. All choices happen inside the panel.
# Replaces asiair-watch.sh + seestar-watch.sh. bash 3.2 compatible.
# =============================================================================

ASIAIR_VOLUME="/Volumes/ASIAIR"
SEESTAR_VOL1="/Volumes/Seestar"
SEESTAR_VOL2="/Volumes/SEESTAR"
IMPORT_SCRIPT="$HOME/bin/astro-import.py"
APP_SCRIPT="$HOME/bin/astro-app.py"
PORT=8765
URL="http://127.0.0.1:$PORT"
WATCH_LOG="/tmp/astro-watch.log"

wlog() { echo "$(date): $1" >> "$WATCH_LOG"; }

asiair_here()  { [ -d "$ASIAIR_VOLUME/Autorun" ]; }
seestar_here() { [ -d "$SEESTAR_VOL1/MyWorks" ] || [ -d "$SEESTAR_VOL2/MyWorks" ]; }

wlog "── new run ── volume change detected, checking for cameras..."

# ── Retry loop: /Volumes changes before the filesystem is fully up ─────────
tries=0
while ! asiair_here && ! seestar_here; do
    tries=$((tries + 1))
    if [ "$tries" -ge 15 ]; then
        wlog "no camera found after ${tries}s — exiting (probably an unmount)"
        exit 0
    fi
    sleep 1
done

DEVICES=""
asiair_here  && DEVICES="ASIAir"
seestar_here && DEVICES="${DEVICES:+$DEVICES + }Seestar"
wlog "detected: $DEVICES (after ${tries}s wait)"

# ── Quick scan for the notification text (read-only, tagged lines) ─────────
SCAN_OUT=$(/usr/bin/python3 "$IMPORT_SCRIPT" --scan-only 2>>"$WATCH_LOG")
NEW_COUNT=$(printf '%s\n' "$SCAN_OUT" | sed -n 's/^ASIAIR-SCAN|COUNT|//p' | tail -1)
wlog "scan: new_targets=${NEW_COUNT:-?}"

if [ -n "$NEW_COUNT" ] && [ "$NEW_COUNT" -gt 0 ] 2>/dev/null; then
    NOTE="$NEW_COUNT target(s) have new frames — opening the FITS Importer panel."
else
    NOTE="Nothing new — all backed up. Opening the FITS Importer panel."
fi
osascript -e 'on run argv' \
          -e 'display notification (item 1 of argv) with title ((item 2 of argv) & " detected")' \
          -e 'end run' -- "$NOTE" "$DEVICES" 2>>"$WATCH_LOG" || true

# ── Make sure the panel app is running, then open/focus it ─────────────────
if ! curl -s -m 2 "$URL/api/ping" >/dev/null 2>&1; then
    wlog "panel not running — starting astro-app.py"
    nohup /usr/bin/python3 "$APP_SCRIPT" --no-browser >>"$WATCH_LOG" 2>&1 &
    tries=0
    while ! curl -s -m 1 "$URL/api/ping" >/dev/null 2>&1; do
        tries=$((tries + 1))
        if [ "$tries" -ge 20 ]; then
            wlog "panel did not come up — falling back to Terminal picker"
            osascript -e "tell application \"Terminal\"
                activate
                do script \"/usr/bin/python3 '$IMPORT_SCRIPT' --pick 2>&1 | tee -a /tmp/astro-import.log\"
            end tell" 2>>"$WATCH_LOG"
            exit 0
        fi
        sleep 0.5
    done
fi

open "$URL" 2>>"$WATCH_LOG" || true
wlog "panel opened"
exit 0
