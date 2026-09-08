# Third-party components

Tracker Radar is developed by BinaryBears. Runtime distributions include:

- Python 3.13: Python Software Foundation License, with historical license notices. https://docs.python.org/3/license.html
- Tcl/Tk: BSD-style Tcl/Tk license. https://www.tcl-lang.org/software/tcltk/license.html
- certifi: Mozilla Public License 2.0; Mozilla CA bundle. https://github.com/certifi/python-certifi
- OpenSSL (where included by Python): Apache License 2.0. https://www.openssl.org/source/license.html
- PyInstaller bootloader: GPL 2.0-or-later with the bootloader exception permitting distribution of bundled applications under their own license. https://pyinstaller.org/en/stable/license.html

The upstream trackerslist project is used as a remotely fetched data source, not a bundled or guaranteed tracker list: https://github.com/ngosang/trackerslist

Full license texts available in the build environment are copied to `assets/licenses` for inclusion in the app. Packaging does not change the ownership or license of these components.
