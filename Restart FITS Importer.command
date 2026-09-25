#!/bin/bash
# BrettjoAstro FITS Importer — one-click panel restart.
# Runs in Terminal's context (the route that has never failed), with
# python.org Python preferred when installed.
echo "Restarting the FITS Importer panel..."
# match the running panel only (python … astro-app.py), never an editor
# that happens to have the file open (1.4.3, V9)
pkill -f "[Pp]ython[^ ]* .*astro-app\.py" 2>/dev/null
sleep 1
if [ -x /usr/local/bin/python3 ]; then PYTHON=/usr/local/bin/python3
else PYTHON=/usr/bin/python3; fi
nohup "$PYTHON" "$HOME/bin/astro-app.py" --no-browser >/dev/null 2>&1 &
sleep 1.5
open "http://127.0.0.1:8765"
echo "Done — the panel is open in your browser. You can close this window."
