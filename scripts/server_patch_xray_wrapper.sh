#!/usr/bin/env bash
set -euo pipefail

XRAY="/usr/local/x-ui/bin/xray-linux-amd64"
if [ ! -f "${XRAY}.real" ]; then
  mv "$XRAY" "${XRAY}.real"
fi

cat > "$XRAY" <<'SH'
#!/usr/bin/env bash
REAL="/usr/local/x-ui/bin/xray-linux-amd64.real"
if [ "$1" = "x25519" ]; then
  OUT="$($REAL "$@")"
  printf "%s\n" "$OUT"
  if ! printf "%s\n" "$OUT" | grep -q "Public key:"; then
    PWD_LINE="$(printf "%s\n" "$OUT" | awk -F': ' '/^Password:/{print $2; exit}')"
    if [ -n "$PWD_LINE" ]; then
      printf "Public key: %s\n" "$PWD_LINE"
    fi
  fi
  exit 0
fi
exec "$REAL" "$@"
SH

chmod +x "$XRAY"
"$XRAY" x25519 -i mLYMWFI-tPEhB612x4UTBK9Ja89rSpuUM6ZeFXDxTWc | sed -n '1,20p'
systemctl restart x-ui
sleep 1
systemctl --no-pager --full status x-ui | sed -n '1,60p'
