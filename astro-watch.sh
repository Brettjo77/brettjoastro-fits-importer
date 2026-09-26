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

# Tests never run this script (it launches the real app, Terminal and browser):
# a test root here is a tripwire, so stop before touching anything (1.5.2)
if [ -n "${ASTRO_TEST_ROOT+set}" ]; then
    echo "TEST MODE: astro-watch.sh never runs under a test" >&2
    exit 3
fi

ASIAIR_VOLUME="${ASIAIR_VOLUME:-/Volumes/ASIAIR}"
SEESTAR_VOL1="${SEESTAR_VOL1:-/Volumes/Seestar}"
SEESTAR_VOL2="${SEESTAR_VOL2:-/Volumes/SEESTAR}"
IMPORT_SCRIPT="${ASTRO_IMPORT_SCRIPT:-$HOME/bin/astro-import.py}"
APP_SCRIPT="${ASTRO_APP_SCRIPT:-$HOME/bin/astro-app.py}"
# The .app wrapper gives the panel its own TCC identity (drag IT into Full
# Disk Access). When present, all panel launches go through it.
APP_BUNDLE="${ASTRO_APP_BUNDLE:-$HOME/Applications/BrettjoAstro FITS Importer.app}"
# Prefer python.org Python when installed: it is NOT an Apple "platform
# binary", so macOS lets it ASK for removable-volume access (Allow once →
# hands-free forever). Apple's /usr/bin/python3 is the fallback.
PYTHON="${ASTRO_PYTHON:-}"
if [ -z "$PYTHON" ]; then
    if [ -x /usr/local/bin/python3 ]; then PYTHON=/usr/local/bin/python3
    else PYTHON=/usr/bin/python3; fi
fi
PORT="${ASTRO_PANEL_PORT:-8765}"
URL="http://127.0.0.1:$PORT"
# Logs and state live in the user's own Library, not /tmp — /tmp is wiped
# on reboot and any local account can pre-plant a symlink there (1.4.3, V5)
WATCH_LOG="${ASTRO_WATCH_LOG:-$HOME/Library/Logs/astro-watch.log}"
STATE_FILE="${ASTRO_WATCH_STATE:-$HOME/Library/Application Support/Astro Import/astro-watch.state}"
mkdir -p "$(dirname "$WATCH_LOG")" "$(dirname "$STATE_FILE")" 2>/dev/null
# suppress repeat notifications when the SAME camera set re-arrives within 10 min
FLAP_GUARD_S="${ASTRO_FLAP_GUARD_S:-600}"

wlog() { echo "$(date): $1" >> "$WATCH_LOG"; }

asiair_here()  { [ -d "$ASIAIR_VOLUME/Autorun" ]; }
seestar_here() {
  # Fixed names first, then any /Volumes entry that LOOKS like a Seestar —
  # a second unit mounts as "Seestar 1", and a new model may bring its own
  # volume name (S50 Pro onboarding, 2026-09-05)
  local v
  for v in "$SEESTAR_VOL1" "$SEESTAR_VOL2" /Volumes/[Ss][Ee][Ee][Ss][Tt][Aa][Rr]*; do
    [ -d "$v/MyWorks" ] && return 0
  done
  return 1
}

presence() {
    local p=""
    asiair_here  && p="A"
    seestar_here && p="${p}S"
    echo "${p:-none}"
}

read_state() {   # sets PREV, PREV_TS and PREV_NOTIFIED (last camera set notified)
    PREV="none"; PREV_TS=0; PREV_NOTIFIED=""
    if [ -f "$STATE_FILE" ]; then
        PREV="$(sed -n 1p "$STATE_FILE" 2>/dev/null)"
        PREV_TS="$(sed -n 2p "$STATE_FILE" 2>/dev/null)"
        PREV_NOTIFIED="$(sed -n 3p "$STATE_FILE" 2>/dev/null)"
        [ -n "$PREV" ] || PREV="none"
        case "$PREV_TS" in ''|*[!0-9]*) PREV_TS=0 ;; esac
    fi
    # older 2-line state files: assume the last notification was for PREV
    [ -n "$PREV_NOTIFIED" ] || PREV_NOTIFIED="$PREV"
}

write_state() {  # $1 = presence, $2 = notify ts, $3 = last-notified set
    printf '%s\n%s\n%s\n' "$1" "$2" "$3" > "$STATE_FILE"
}

spawn_panel() {   # $1 = "--silent" to suppress the browser tab
    if [ -d "$APP_BUNDLE" ]; then
        # launch through the app → panel carries the app's TCC identity
        open -g -a "$APP_BUNDLE" --args ${1:+"$1"} 2>>"$WATCH_LOG"
    else
        nohup "$PYTHON" "$APP_SCRIPT" --no-browser >>"$WATCH_LOG" 2>&1 &
    fi
}

ensure_panel_silently() {
    # Keep the panel alive on quiet paths: start it if it died (user quit,
    # crash), but never notify, never open a tab — existing tabs self-heal.
    if curl -s -m 2 "$URL/api/ping" >/dev/null 2>&1; then
        return 0
    fi
    wlog "panel not running — restarting silently"
    spawn_panel --silent
}

# ── The FITs Importer App runs its own watcher: stand aside (1.5.3) ────────
# >>> app-owner check (test_v2 runs this block on its own, with a fake engine)
if "$PYTHON" "$IMPORT_SCRIPT" --app-owner >/dev/null 2>&1; then
    wlog "the FITs Importer App is in charge here — nothing to do"
    exit 0
fi
# <<< app-owner check

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
        write_state "none" "$PREV_TS" "$PREV_NOTIFIED"
    fi
    exit 0
fi

# ── Same camera set as last time: someone else touched /Volumes ────────────
if [ "$CUR" = "$PREV" ]; then
    wlog "volume event but camera set unchanged ($CUR) — silent"
    ensure_panel_silently
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
    write_state "$CUR" "$PREV_TS" "$PREV_NOTIFIED"
    exit 0
fi

# ── Flap guard: the SAME set re-arriving within the window → stay quiet ────
# (a DIFFERENT camera arriving always announces itself, e.g. Seestar → ASIAir
#  swaps: only an exact repeat of the last-notified set is treated as a flap)
if [ "$CUR" = "$PREV_NOTIFIED" ] && [ "$((NOW - PREV_TS))" -lt "$FLAP_GUARD_S" ]; then
    wlog "arrival ($PREV → $CUR) but same set notified $((NOW - PREV_TS))s ago — flap guard, silent"
    write_state "$CUR" "$PREV_TS" "$PREV_NOTIFIED"
    ensure_panel_silently
    exit 0
fi

DEVICES=""
asiair_here  && DEVICES="ASIAir"
seestar_here && DEVICES="${DEVICES:+$DEVICES + }Seestar"
wlog "new arrival: $PREV → $CUR ($DEVICES)"

# ── Quick scan for the notification text (read-only, tagged lines) ─────────
SCAN_OUT=$("$PYTHON" "$IMPORT_SCRIPT" --scan-only 2>>"$WATCH_LOG")
NEW_COUNT=$(printf '%s\n' "$SCAN_OUT" | sed -n 's/^ASIAIR-SCAN|COUNT|//p' | tail -1)
ATTN=$(printf '%s\n' "$SCAN_OUT" | sed -n 's/^ASIAIR-SCAN|ATTENTION|//p' | tail -1)
wlog "scan: new_targets=${NEW_COUNT:-?} attention=${ATTN:-0}"

if [ -n "$NEW_COUNT" ] && [ "$NEW_COUNT" -gt 0 ] 2>/dev/null; then
    NOTE="$NEW_COUNT target(s) have new frames — opening the FITS Importer panel."
    if [ -n "$ATTN" ] && [ "$ATTN" -gt 0 ] 2>/dev/null; then
        NOTE="$NEW_COUNT target(s) with new frames + $ATTN item(s) needing a look — opening the panel."
    fi
elif [ "$NEW_COUNT" = "0" ] && [ -n "$ATTN" ] && [ "$ATTN" -gt 0 ] 2>/dev/null; then
    # never say "all backed up" over folders the scan could not account for
    NOTE="$ATTN item(s) on the camera need a look — opening the FITS Importer panel."
elif [ "$NEW_COUNT" = "0" ]; then
    NOTE="Nothing new — all backed up. Opening the FITS Importer panel."
else
    # pre-scan blocked or failed — stay honest, let the panel do the scanning
    NOTE="Camera detected — opening the FITS Importer panel."
fi
osascript -e 'on run argv' \
          -e 'display notification (item 1 of argv) with title ((item 2 of argv) & " detected")' \
          -e 'end run' -- "$NOTE" "$DEVICES" 2>>"$WATCH_LOG" || true
write_state "$CUR" "$NOW" "$CUR"

# ── Make sure the panel app is running, then open/focus it ─────────────────
if ! curl -s -m 2 "$URL/api/ping" >/dev/null 2>&1; then
    wlog "panel not running — starting it"
    spawn_panel --silent
    tries=0
    while ! curl -s -m 1 "$URL/api/ping" >/dev/null 2>&1; do
        tries=$((tries + 1))
        if [ "$tries" -ge 20 ]; then
            wlog "panel did not come up — falling back to Terminal picker"
            osascript -e "tell application \"Terminal\"
                activate
                do script \"$PYTHON '$IMPORT_SCRIPT' --pick 2>&1 | tee -a ~/Library/Logs/astro-import.log\"
            end tell" 2>>"$WATCH_LOG"
            exit 0
        fi
        sleep 0.5
    done
fi

open "$URL" 2>>"$WATCH_LOG" || true
wlog "panel opened"
exit 0
