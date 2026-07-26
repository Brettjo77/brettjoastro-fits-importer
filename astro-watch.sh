#!/bin/bash
# =============================================================================
# BrettjoAstro FITS Importer — drive watcher (ONE watcher for both cameras)
# =============================================================================
# Plug in either camera → notification → the FITS Importer panel opens (or
# focuses) in your browser. All choices happen inside the panel.
#
# launchd fires this on ANY /Volumes change (other disks, snapshots, USB
# blips), so the watcher keeps state: it only notifies + opens the panel when
# the set of connected cameras actually CHANGES to include a new arrival.
# Re-observations exit silently; a 10-minute flap guard absorbs a drive that
# drops and remounts repeatedly. bash 3.2 compatible.
# =============================================================================

ASIAIR_VOLUME="${ASIAIR_VOLUME:-/Volumes/ASIAIR}"
SEESTAR_VOL1="${SEESTAR_VOL1:-/Volumes/Seestar}"
SEESTAR_VOL2="${SEESTAR_VOL2:-/Volumes/SEESTAR}"
IMPORT_SCRIPT="${ASTRO_IMPORT_SCRIPT:-$HOME/bin/astro-import.py}"
APP_SCRIPT="${ASTRO_APP_SCRIPT:-$HOME/bin/astro-app.py}"
PORT="${ASTRO_PANEL_PORT:-8765}"
URL="http://127.0.0.1:$PORT"
WATCH_LOG="${ASTRO_WATCH_LOG:-/tmp/astro-watch.log}"
STATE_FILE="${ASTRO_WATCH_STATE:-/tmp/astro-watch.state}"
FLAP_GUARD_S=600   # suppress repeat notifications for the same arrival within 10 min

wlog() { echo "$(date): $1" >> "$WATCH_LOG"; }

asiair_here()  { [ -d "$ASIAIR_VOLUME/Autorun" ]; }
seestar_here() { [ -d "$SEESTAR_VOL1/MyWorks" ] || [ -d "$SEESTAR_VOL2/MyWorks" ]; }

presence() {
    local p=""
    asiair_here  && p="A"
    seestar_here && p="${p}S"
    echo "${p:-none}"
}

read_state() {   # sets PREV and PREV_TS
    PREV="none"; PREV_TS=0
    if [ -f "$STATE_FILE" ]; then
        PREV="$(sed -n 1p "$STATE_FILE" 2>/dev/null)"
        PREV_TS="$(sed -n 2p "$STATE_FILE" 2>/dev/null)"
        [ -n "$PREV" ] || PREV="none"
        case "$PREV_TS" in ''|*[!0-9]*) PREV_TS=0 ;; esac
    fi
}

write_state() {  # $1 = presence, $2 = notify timestamp (or previous)
    printf '%s\n%s\n' "$1" "$2" > "$STATE_FILE"
}

NOW="$(date +%s)"
read_state

# ── Short settle wait: /Volumes changes before the filesystem is fully up ──
tries=0
CUR="$(presence)"
while [ "$CUR" = "none" ] && [ "$tries" -lt 15 ]; do
    tries=$((tries + 1))   # give a slow mount up to 15s to settle
    sleep 1
    CUR="$(presence)"
done

# ── No cameras at all: record absence quietly and leave ────────────────────
if [ "$CUR" = "none" ]; then
    if [ "$PREV" != "none" ]; then
        wlog "cameras gone (was: $PREV) — recorded, silent"
        write_state "none" "$PREV_TS"
    fi
    exit 0
fi

# ── Same camera set as last time: someone else touched /Volumes ────────────
if [ "$CUR" = "$PREV" ]; then
    wlog "volume event but camera set unchanged ($CUR) — silent"
    exit 0
fi

# ── The set changed. Only a NEW ARRIVAL deserves attention ──────────────────
# (a camera leaving while another stays, e.g. AS→S, is recorded silently)
case "$CUR" in
    *A*) case "$PREV" in *A*) : ;; *) NEW_ARRIVAL=1 ;; esac ;;
esac
case "$CUR" in
    *S*) case "$PREV" in *S*) : ;; *) NEW_ARRIVAL=1 ;; esac ;;
esac
if [ -z "${NEW_ARRIVAL:-}" ]; then
    wlog "camera set shrank ($PREV → $CUR) — recorded, silent"
    write_state "$CUR" "$PREV_TS"
    exit 0
fi

# ── Flap guard: same set re-arriving within the window → stay quiet ────────
if [ "$((NOW - PREV_TS))" -lt "$FLAP_GUARD_S" ]; then
    wlog "arrival ($PREV → $CUR) but notified $((NOW - PREV_TS))s ago — flap guard, silent"
    write_state "$CUR" "$PREV_TS"
    exit 0
fi

DEVICES=""
asiair_here  && DEVICES="ASIAir"
seestar_here && DEVICES="${DEVICES:+$DEVICES + }Seestar"
wlog "new arrival: $PREV → $CUR ($DEVICES)"

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
write_state "$CUR" "$NOW"

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
