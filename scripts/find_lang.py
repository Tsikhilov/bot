#!/usr/bin/env python3
"""Scan Hiddify bundle for language detection / i18n init."""
import re, sys

path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/hiddify_bundle.js"
with open(path, encoding="utf-8", errors="ignore") as f:
    t = f.read()

needles = [
    "localStorage", "navigator.language", "initReactI18next",
    "i18next", "changeLanguage", "?lng", "lngs", "lng=",
    "defaultLocale", "Russian", "Choose your preferred language",
]

for needle in needles:
    i = t.find(needle)
    if i >= 0:
        print(f"[{needle}] => {t[max(0,i-30):i+180]!r}")
    else:
        print(f"[{needle}] NOT FOUND")
