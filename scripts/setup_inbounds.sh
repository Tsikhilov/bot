#!/bin/bash
# Финальная настройка: создание inbound-ов и сохранение credentials
set -euo pipefail

DOMAIN="sub.smartkama.ru"
PANEL_PORT="55445"
PANEL_USER="admin"
PANEL_PASS="SmartKama2026!"
SECRET_PATH="902184284ee0d060"
CERT="/etc/letsencrypt/live/${DOMAIN}/fullchain.pem"
KEY="/etc/letsencrypt/live/${DOMAIN}/privkey.pem"
XRAY="/usr/local/x-ui/bin/xray-linux-amd64"
REALITY_PORT=8443
WS_PORT=443

echo "[1] Генерация ключей Reality..."
KEYS=$("$XRAY" x25519 2>&1)
PRIV=$(echo "$KEYS" | grep PrivateKey | awk '{print $2}')
PUB=$(echo "$KEYS"  | grep Password   | awk '{print $2}')
SHORT=$(openssl rand -hex 4)
UUID_R=$(cat /proc/sys/kernel/random/uuid)
UUID_W=$(cat /proc/sys/kernel/random/uuid)
WS_PATH="/$(openssl rand -hex 6)"

echo "  PrivateKey : $PRIV"
echo "  PublicKey  : $PUB"
echo "  ShortID    : $SHORT"
echo "  UUID_R     : $UUID_R"
echo "  UUID_W     : $UUID_W"
echo "  WS_PATH    : $WS_PATH"

echo "[2] Логин в API..."
API="https://127.0.0.1:${PANEL_PORT}/${SECRET_PATH}"
JAR=$(mktemp)
RESP=$(curl -sk -c "$JAR" -X POST "${API}/login" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=${PANEL_USER}&password=${PANEL_PASS}")
echo "  Login response: $RESP"
echo "$RESP" | grep -q '"success":true' || { echo "ERROR: Login failed!"; exit 1; }

echo "[3] Создание VLESS+Reality inbound..."
R_RESP=$(curl -sk -b "$JAR" -X POST "${API}/xui/API/inbounds/add" \
    -H "Content-Type: application/json" \
    -d "{
  \"remark\": \"VLESS-Reality\",
  \"enable\": true,
  \"listen\": \"\",
  \"port\": ${REALITY_PORT},
  \"protocol\": \"vless\",
  \"expiryTime\": 0,
  \"settings\": \"{\\\"clients\\\":[{\\\"id\\\":\\\"${UUID_R}\\\",\\\"flow\\\":\\\"xtls-rprx-vision\\\",\\\"email\\\":\\\"default@smartkama\\\",\\\"limitIp\\\":0,\\\"totalGB\\\":0,\\\"expiryTime\\\":0,\\\"enable\\\":true}],\\\"decryption\\\":\\\"none\\\"}\",
  \"streamSettings\": \"{\\\"network\\\":\\\"tcp\\\",\\\"security\\\":\\\"reality\\\",\\\"realitySettings\\\":{\\\"show\\\":false,\\\"dest\\\":\\\"www.microsoft.com:443\\\",\\\"xver\\\":0,\\\"serverNames\\\":[\\\"www.microsoft.com\\\"],\\\"privateKey\\\":\\\"${PRIV}\\\",\\\"shortIds\\\":[\\\"${SHORT}\\\"]}}\",
  \"sniffing\": \"{\\\"enabled\\\":true,\\\"destOverride\\\":[\\\"http\\\",\\\"tls\\\",\\\"quic\\\"]}\",
  \"tag\": \"vless-reality\"
}")
echo "  Reality response: $R_RESP"

echo "[4] Создание VLESS+WS+TLS inbound..."
W_RESP=$(curl -sk -b "$JAR" -X POST "${API}/xui/API/inbounds/add" \
    -H "Content-Type: application/json" \
    -d "{
  \"remark\": \"VLESS-WS-TLS\",
  \"enable\": true,
  \"listen\": \"\",
  \"port\": ${WS_PORT},
  \"protocol\": \"vless\",
  \"expiryTime\": 0,
  \"settings\": \"{\\\"clients\\\":[{\\\"id\\\":\\\"${UUID_W}\\\",\\\"flow\\\":\\\"\\\",\\\"email\\\":\\\"default-ws@smartkama\\\",\\\"limitIp\\\":0,\\\"totalGB\\\":0,\\\"expiryTime\\\":0,\\\"enable\\\":true}],\\\"decryption\\\":\\\"none\\\"}\",
  \"streamSettings\": \"{\\\"network\\\":\\\"ws\\\",\\\"security\\\":\\\"tls\\\",\\\"tlsSettings\\\":{\\\"serverName\\\":\\\"${DOMAIN}\\\",\\\"certificates\\\":[{\\\"certificateFile\\\":\\\"${CERT}\\\",\\\"keyFile\\\":\\\"${KEY}\\\"}]},\\\"wsSettings\\\":{\\\"path\\\":\\\"${WS_PATH}\\\"}}\",
  \"sniffing\": \"{\\\"enabled\\\":true,\\\"destOverride\\\":[\\\"http\\\",\\\"tls\\\",\\\"quic\\\"]}\",
  \"tag\": \"vless-ws-tls\"
}")
echo "  WS response: $W_RESP"

echo "[5] Получение ID inbound-ов..."
LIST=$(curl -sk -b "$JAR" "${API}/xui/API/inbounds")
REALITY_ID=$(echo "$LIST" | python3 -c "import sys,json; d=json.load(sys.stdin); [print(o['id']) for o in d.get('obj',[]) if o.get('tag')=='vless-reality']" 2>/dev/null || echo "1")
WS_ID=$(echo "$LIST" | python3 -c "import sys,json; d=json.load(sys.stdin); [print(o['id']) for o in d.get('obj',[]) if o.get('tag')=='vless-ws-tls']" 2>/dev/null || echo "2")

rm -f "$JAR"

echo "[6] Сохранение credentials..."
cat > /root/3xui_credentials.txt <<EOF
PANEL_URL=https://${DOMAIN}:${PANEL_PORT}/${SECRET_PATH}/
PANEL_USER=${PANEL_USER}
PANEL_PASS=${PANEL_PASS}
PANEL_HOST=https://${DOMAIN}
PANEL_PORT=${PANEL_PORT}
PANEL_PATH=/${SECRET_PATH}

REALITY_INBOUND_ID=${REALITY_ID}
VLESS_REALITY_UUID=${UUID_R}
REALITY_PUBLIC_KEY=${PUB}
REALITY_PRIVATE_KEY=${PRIV}
REALITY_SHORT_ID=${SHORT}
REALITY_PORT=${REALITY_PORT}
REALITY_SNI=www.microsoft.com

WS_INBOUND_ID=${WS_ID}
VLESS_WS_UUID=${UUID_W}
VLESS_WS_PATH=${WS_PATH}
VLESS_WS_PORT=${WS_PORT}
VLESS_WS_DOMAIN=${DOMAIN}
EOF
chmod 600 /root/3xui_credentials.txt

echo ""
echo "==== ГОТОВО ===="
cat /root/3xui_credentials.txt
