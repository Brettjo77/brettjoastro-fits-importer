#!/bin/bash
# BrettjoAstro FITS Importer — double-click installer.
# Runs the standard installer from wherever this folder was unzipped.
cd "$(dirname "$0")"
echo "Installing from: $(pwd)"
echo ""
bash install-scripts.sh
echo ""
echo "You can close this window."
