#!/usr/bin/env python3
"""Scan Hiddify JS bundle for i18n / UI strings."""
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/hiddify_bundle.js"
with open(path, encoding="utf-8", errors="ignore") as f:
    t = f.read()

needles = [
    "Account", "Remaining", "Setup Guide", "No Time Limit",
    "days_rem", "traffic", "Open In", "Install App",
    "auto_update", "copy", "Subscription", "Quick",
    "days left", "GB left", "expires",
]
for needle in needles:
    i = t.find(needle)
    if i >= 0:
        print(f"{needle!r} => {t[max(0,i-20):i+120]!r}")
    else:
        print(f"{needle!r} NOT FOUND")
