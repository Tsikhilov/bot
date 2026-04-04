#!/usr/bin/env python3
"""Backward-compatible wrapper.

Use scripts/hiddify_native_ru.py for full native RU hardening.
"""

from hiddify_native_ru import patch_i18n


def main() -> int:
    ru_changed, en_changed = patch_i18n(force_en_ru=True)
    print(f"PATCH_OK ru_changed={int(ru_changed)} en_changed={int(en_changed)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
