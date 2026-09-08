#!/bin/zsh
set -eu
cd -- "${0:A:h}"
if [[ -d "Tracker Radar.app" ]]; then
  open "Tracker Radar.app"
elif [[ -d "dist/Tracker Radar.app" ]]; then
  open "dist/Tracker Radar.app"
else
  print "This is the source package. Download the macOS app to run without Python."
  read "?Press Return to close."
fi
