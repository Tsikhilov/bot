#!/bin/bash
# =============================================================================
# SmartKamaVPN — завершение настройки 3x-ui
# Запускать после успешной установки x-ui через install_3xui.sh
# =============================================================================
set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

DOMAIN="sub.smartkama.ru"
PANEL_PORT="55445"
PANEL_USER="admin"
PANEL_PASS="$(openssl rand -base64 16 | tr -d '/+=' | head -c 16)"
SECRET_PATH="$(openssl rand -hex 8)"

CERT_PATH="/etc/letsencrypt/live/${DOMAIN}/fullchain.pem"
KEY_PATH="/etc/letsencrypt/live/${DOMAIN}/privkey.pem"
XRAY_BIN=$(find /usr/local/x-ui/bin -name 'xray*' -type f | head -1)

REALITY_PORT=8443
VLESS_WS_PORT=443

[[ $EUID -ne 0 ]] && error "Запускай от root"
[[ -f "$CERT_PATH" ]] || error "SSL сертификат не найден: $CERT_PATH"
[[ -n "$XRAY_BIN" ]] || error "xray binary не найден в /usr/local/x-ui/bin"

info "=== Настройка панели x-ui ==="
# Останавливаем сервис перед изменением настроек
systemctl stop x-ui

# Используем бинарник напрямую (не shell-скрипт x-ui)
/usr/local/x-ui/x-ui setting -username "$PANEL_USER"
/usr/local/x-ui/x-ui setting -password "$PANEL_PASS"
/usr/local/x-ui/x-ui setting -port "$PANEL_PORT"
/usr/local/x-ui/x-ui setting -webBasePath "/$SECRET_PATH"
/usr/local/x-ui/x-ui setting -webCert "$CERT_PATH"
/usr/local/x-ui/x-ui setting -webCertKey "$KEY_PATH"

systemctl start x-ui
info "Ждём запуска x-ui на порту $PANEL_PORT..."
sleep 5

# Дождаться пока порт откроется
for i in {1..12}; do
    if curl -sk "https://127.0.0.1:${PANEL_PORT}/${SECRET_PATH}/login" -o /dev/null; then
        info "Панель доступна"
        break
    fi
    sleep 5
done

info "=== Генерация ключей Reality ==="
REALITY_KEYS=$("$XRAY_BIN" x25519 2>&1)
PRIVATE_KEY=$(echo "$REALITY_KEYS" | grep -i "private" | awk '{print $NF}')
PUBLIC_KEY=$(echo "$REALITY_KEYS"  | grep -i "public"  | awk '{print $NF}')
SHORT_ID=$(openssl rand -hex 4)
VLESS_REALITY_UUID=$(cat /proc/sys/kernel/random/uuid)
VLESS_WS_UUID=$(cat /proc/sys/kernel/random/uuid)
WS_PATH="/$(openssl rand -hex 6)"

[[ -n "$PRIVATE_KEY" ]] || error "Не удалось получить приватный ключ Reality"
info "Reality Public Key: $PUBLIC_KEY"

info "=== Логин в API ==="
API_BASE="https://127.0.0.1:${PANEL_PORT}/${SECRET_PATH}"
COOKIE_JAR=$(mktemp)

LOGIN_RESP=$(curl -sk -c "$COOKIE_JAR" -X POST "${API_BASE}/login" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=${PANEL_USER}&password=${PANEL_PASS}")

if ! echo "$LOGIN_RESP" | grep -q '"success":true'; then
    error "API-логин не удался: $LOGIN_RESP"
fi
info "API-логин успешен"

info "=== Создание VLESS + Reality inbound ==="
REALITY_BODY=$(cat <<JSON
{
  "tag": "vless-reality",
  "port": ${REALITY_PORT},
  "protocol": "vless",
  "settings": "{\"clients\":[{\"id\":\"${VLESS_REALITY_UUID}\",\"flow\":\"xtls-rprx-vision\",\"email\":\"default@smartkama\",\"limitIp\":0,\"totalGB\":0,\"expiryTime\":0,\"enable\":true}],\"decryption\":\"none\"}",
  "streamSettings": "{\"network\":\"tcp\",\"security\":\"reality\",\"realitySettings\":{\"show\":false,\"dest\":\"www.microsoft.com:443\",\"xver\":0,\"serverNames\":[\"www.microsoft.com\"],\"privateKey\":\"${PRIVATE_KEY}\",\"shortIds\":[\"${SHORT_ID}\"]}}",
  "sniffing": "{\"enabled\":true,\"destOverride\":[\"http\",\"tls\",\"quic\"]}",
  "listen": "",
  "remark": "VLESS-Reality",
  "enable": true,
  "expiryTime": 0,
  "clientStats": null
}
JSON
)

REALITY_RESP=$(curl -sk -b "$COOKIE_JAR" -X POST "${API_BASE}/xui/API/inbounds/add" \
    -H "Content-Type: application/json" \
    -d "$REALITY_BODY")
echo "Reality inbound: $(echo "$REALITY_RESP" | grep -o '"msg":"[^"]*"' | head -1)"

info "=== Создание VLESS + TLS + WS inbound ==="
WS_BODY=$(cat <<JSON
{
  "tag": "vless-ws-tls",
  "port": ${VLESS_WS_PORT},
  "protocol": "vless",
  "settings": "{\"clients\":[{\"id\":\"${VLESS_WS_UUID}\",\"flow\":\"\",\"email\":\"default-ws@smartkama\",\"limitIp\":0,\"totalGB\":0,\"expiryTime\":0,\"enable\":true}],\"decryption\":\"none\"}",
  "streamSettings": "{\"network\":\"ws\",\"security\":\"tls\",\"tlsSettings\":{\"serverName\":\"${DOMAIN}\",\"certificates\":[{\"certificateFile\":\"${CERT_PATH}\",\"keyFile\":\"${KEY_PATH}\"}]},\"wsSettings\":{\"path\":\"${WS_PATH}\"}}",
  "sniffing": "{\"enabled\":true,\"destOverride\":[\"http\",\"tls\",\"quic\"]}",
  "listen": "",
  "remark": "VLESS-WS-TLS",
  "enable": true,
  "expiryTime": 0,
  "clientStats": null
}
JSON
)

WS_RESP=$(curl -sk -b "$COOKIE_JAR" -X POST "${API_BASE}/xui/API/inbounds/add" \
    -H "Content-Type: application/json" \
    -d "$WS_BODY")
echo "WS inbound: $(echo "$WS_RESP" | grep -o '"msg":"[^"]*"' | head -1)"

# Получить ID inbound-ов
REALITY_ID=$(curl -sk -b "$COOKIE_JAR" "${API_BASE}/xui/API/inbounds" | \
    python3 -c "import sys,json; data=json.load(sys.stdin); objs=data.get('obj',[]); [print(o['id']) for o in objs if o.get('tag')=='vless-reality']" 2>/dev/null || echo "1")
WS_ID=$(curl -sk -b "$COOKIE_JAR" "${API_BASE}/xui/API/inbounds" | \
    python3 -c "import sys,json; data=json.load(sys.stdin); objs=data.get('obj',[]); [print(o['id']) for o in objs if o.get('tag')=='vless-ws-tls']" 2>/dev/null || echo "2")

rm -f "$COOKIE_JAR"

info "=== Cron для обновления сертификата ==="
(crontab -l 2>/dev/null; echo "0 3 * * * certbot renew --quiet && systemctl restart x-ui") | sort -u | crontab -

# Сохраняем данные
cat > /root/3xui_credentials.txt <<EOF
PANEL_URL=https://${DOMAIN}:${PANEL_PORT}/${SECRET_PATH}/
PANEL_USER=${PANEL_USER}
PANEL_PASS=${PANEL_PASS}
PANEL_HOST=https://${DOMAIN}
PANEL_PORT=${PANEL_PORT}
PANEL_PATH=/${SECRET_PATH}

REALITY_INBOUND_ID=${REALITY_ID}
VLESS_REALITY_UUID=${VLESS_REALITY_UUID}
REALITY_PUBLIC_KEY=${PUBLIC_KEY}
REALITY_PRIVATE_KEY=${PRIVATE_KEY}
REALITY_SHORT_ID=${SHORT_ID}
REALITY_PORT=${REALITY_PORT}

WS_INBOUND_ID=${WS_ID}
VLESS_WS_UUID=${VLESS_WS_UUID}
VLESS_WS_PATH=${WS_PATH}
VLESS_WS_PORT=${VLESS_WS_PORT}
VLESS_WS_DOMAIN=${DOMAIN}
EOF
chmod 600 /root/3xui_credentials.txt

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║       3x-ui полностью настроена!                    ║${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║ Панель: https://${DOMAIN}:${PANEL_PORT}/${SECRET_PATH}/ ${NC}"
echo -e "${GREEN}║ Логин : ${PANEL_USER}                                ${NC}"
echo -e "${GREEN}║ Пароль: ${PANEL_PASS}                                ${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║ Reality UUID: ${VLESS_REALITY_UUID}   ${NC}"
echo -e "${GREEN}║ Reality PubKey: ${PUBLIC_KEY}         ${NC}"
echo -e "${GREEN}║ Reality ShortID: ${SHORT_ID}          ${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║ WS UUID: ${VLESS_WS_UUID}             ${NC}"
echo -e "${GREEN}║ WS Path: ${WS_PATH}                   ${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Данные в /root/3xui_credentials.txt"
info "Готово!"
