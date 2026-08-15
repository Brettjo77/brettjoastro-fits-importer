#!/bin/bash
# BrettjoAstro FITS Importer — one-click panel restart.
# Runs in Terminal's context (the route that has never failed), with
# python.org Python preferred when installed.
echo "Restarting the FITS Importer panel..."
pkill -f astro-app.py
sleep 1
if [ -x /usr/local/bin/python3 ]; then PYTHON=/usr/local/bin/python3
else PYTHON=/usr/bin/python3; fi
nohup "$PYTHON" "$HOME/bin/astro-app.py" --no-browser >/dev/null 2>&1 &
sleep 1.5
open "http://127.0.0.1:8765"
echo "Done — the panel is open in your browser. You can close this window."
