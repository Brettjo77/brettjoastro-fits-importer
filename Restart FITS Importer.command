#!/bin/bash
# BrettjoAstro FITS Importer — one-click panel restart.
# Runs in Terminal's context (the route that has never failed), with
# python.org Python preferred when installed.
if [ -x /usr/local/bin/python3 ]; then PYTHON=/usr/local/bin/python3
else PYTHON=/usr/bin/python3; fi
# the FITs Importer App runs its own panel: start nothing (1.5.3)
# >>> app-owner check (test_v2 runs this block on its own, with a fake engine)
if "$PYTHON" "$HOME/bin/astro-import.py" --app-owner >/dev/null 2>&1; then
    echo "The FITs Importer App is in charge here: open it instead. You can close this window."
    exit 0
fi
# <<< app-owner check
echo "Restarting the FITS Importer panel..."
# match the web panel only (python … ~/bin/astro-app.py), never an editor
# that happens to have the file open (1.4.3, V9), never the app (1.5.3)
pkill -f "[Pp]ython[^ ]* .*$HOME/bin/(asiair|astro)-app\.py" 2>/dev/null
sleep 1
nohup "$PYTHON" "$HOME/bin/astro-app.py" --no-browser >/dev/null 2>&1 &
sleep 1.5
open "http://127.0.0.1:8765"
echo "Done — the panel is open in your browser. You can close this window."
