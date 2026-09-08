#!/bin/sh
set -eu
apt-get update
apt-get install -y --no-install-recommends binutils libx11-6 libxext6 libxrender1 libxft2 libfontconfig1 tk xvfb xauth
python -m pip install -r requirements-build.txt
python -m unittest discover -s tests -v
xvfb-run -a python tracker_radar.py --smoke-test
xvfb-run -a python scripts/gui_qa.py
python build.py
xvfb-run -a 'dist/Tracker Radar/Tracker Radar' --smoke-test
python scripts/verify_native.py Linux-x64
python package.py Linux-x64
