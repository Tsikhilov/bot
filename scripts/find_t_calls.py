#!/usr/bin/env python3
"""Deep scan of Hiddify bundle for t() translation calls."""
import re, sys

path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/hiddify_bundle.js"
with open(path, encoding="utf-8", errors="ignore") as f:
    t = f.read()

# Find all t("...") calls — i18n translation function calls
calls = re.findall(r'o\("([^"]{3,60})"\)', t)
calls += re.findall(r't\("([^"]{3,60})"\)', t)
# deduplicate
unique = sorted(set(calls))
for c in unique:
    print(c)
