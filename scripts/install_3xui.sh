#!/bin/bash
# =============================================================================
# SmartKamaVPN — установка и базовая настройка панели 3x-ui
# Сервер : 72.56.100.45 (root)
# Домен  : sub.smartkama.ru
# Порт   : 55445
# ОС     : Ubuntu 22.04
# =============================================================================
set -euo pipefail

# ---------- цвета ----------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ---------- параметры ----------
DOMAIN="sub.smartkama.ru"
PANEL_PORT="55445"
PANEL_USER="admin"
PANEL_PASS="$(openssl rand -base64 16 | tr -d '/+=' | head -c 16)"
SECRET_PATH="$(openssl rand -hex 8)"

VLESS_WS_PORT=443
REALITY_PORT=8443

# ---------- 0. Проверка root ----------
[[ $EUID -ne 0 ]] && error "Запускай от root"

info "=== 1. Обновление системы ==="
apt-get update -qq
apt-get upgrade -y -qq
apt-get install -y -qq curl wget unzip jq certbot ufw

info "=== 2. Настройка UFW ==="
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 80/tcp           # certbot HTTP-01
ufw allow 443/tcp          # VLESS+TLS+WS
ufw allow "$PANEL_PORT/tcp"   # веб-панель
ufw allow "$REALITY_PORT/tcp" # VLESS+Reality
ufw --force enable
info "UFW настроен"

info "=== 3. Получение SSL-сертификата ==="
# Освобождаем порт 80: останавливаем возможные занимающие его сервисы
for svc in hiddify-haproxy hiddify-nginx hiddify-panel hiddify-panel-background-tasks \
           hiddify-redis hiddify-singbox hiddify-ss-faketls hiddify-xray hiddify-dnstm-router \
           nginx apache2 caddy; do
    systemctl stop "$svc" 2>/dev/null || true
    systemctl disable "$svc" 2>/dev/null || true
done
# Подождём пока порт 80 освободится
sleep 2
certbot certonly --standalone \
    --non-interactive \
    --agree-tos \
    --email "admin@${DOMAIN}" \
    -d "$DOMAIN" \
    || error "Не удалось получить сертификат. Проверь DNS: $DOMAIN → $(curl -s ifconfig.me)"

CERT_PATH="/etc/letsencrypt/live/${DOMAIN}/fullchain.pem"
KEY_PATH="/etc/letsencrypt/live/${DOMAIN}/privkey.pem"
info "Сертификат получен: $CERT_PATH"

info "=== 4. Установка 3x-ui ==="
bash <(curl -Ls https://raw.githubusercontent.com/mhsanaei/3x-ui/master/install.sh) << 'EOF'
EOF

# ждём запуска сервиса
sleep 3
systemctl enable x-ui
systemctl start x-ui
sleep 2

info "=== 5. Настройка панели через CLI ==="
# Устанавливаем пользователя, пароль и порт
x-ui setting -username "$PANEL_USER" -password "$PANEL_PASS"
x-ui setting -port "$PANEL_PORT"
x-ui setting -webBasePath "/$SECRET_PATH"

# Подключаем SSL к панели
x-ui setting -certFile "$CERT_PATH" -keyFile "$KEY_PATH"

systemctl restart x-ui
sleep 2

info "=== 6. Создание inbound: VLESS + Reality ==="
# Генерируем ключи Reality
REALITY_KEYS=$(x-ui gen-x25519)
PRIVATE_KEY=$(echo "$REALITY_KEYS" | grep -i "private" | awk '{print $NF}')
PUBLIC_KEY=$(echo "$REALITY_KEYS" | grep -i "public"  | awk '{print $NF}')
SHORT_ID=$(openssl rand -hex 4)

VLESS_REALITY_UUID=$(cat /proc/sys/kernel/random/uuid)

cat > /tmp/inbound_reality.json <<EOF
{
  "tag": "vless-reality",
  "port": ${REALITY_PORT},
  "protocol": "vless",
  "settings": {
    "clients": [
      {
        "id": "${VLESS_REALITY_UUID}",
        "flow": "xtls-rprx-vision",
        "email": "default@smartkama",
        "limitIp": 0,
        "totalGB": 0,
        "expiryTime": 0,
        "enable": true
      }
    ],
    "decryption": "none"
  },
  "streamSettings": {
    "network": "tcp",
    "security": "reality",
    "realitySettings": {
      "show": false,
      "dest": "www.microsoft.com:443",
      "xver": 0,
      "serverNames": ["www.microsoft.com"],
      "privateKey": "${PRIVATE_KEY}",
      "shortIds": ["${SHORT_ID}"]
    }
  },
  "sniffing": {
    "enabled": true,
    "destOverride": ["http","tls","quic"]
  }
}
EOF

info "=== 7. Создание inbound: VLESS + TLS + WebSocket ==="
VLESS_WS_UUID=$(cat /proc/sys/kernel/random/uuid)
WS_PATH="/$(openssl rand -hex 6)"

cat > /tmp/inbound_vless_ws.json <<EOF
{
  "tag": "vless-ws-tls",
  "port": ${VLESS_WS_PORT},
  "protocol": "vless",
  "settings": {
    "clients": [
      {
        "id": "${VLESS_WS_UUID}",
        "flow": "",
        "email": "default-ws@smartkama",
        "limitIp": 0,
        "totalGB": 0,
        "expiryTime": 0,
        "enable": true
      }
    ],
    "decryption": "none"
  },
  "streamSettings": {
    "network": "ws",
    "security": "tls",
    "tlsSettings": {
      "serverName": "${DOMAIN}",
      "certificates": [
        {
          "certificateFile": "${CERT_PATH}",
          "keyFile": "${KEY_PATH}"
        }
      ]
    },
    "wsSettings": {
      "path": "${WS_PATH}"
    }
  },
  "sniffing": {
    "enabled": true,
    "destOverride": ["http","tls","quic"]
  }
}
EOF

info "=== 8. Применение inbound-ов через API ==="
sleep 2
API_BASE="http://127.0.0.1:${PANEL_PORT}/${SECRET_PATH}"

# Логин в API
COOKIE_JAR=$(mktemp)
LOGIN_RESP=$(curl -s -c "$COOKIE_JAR" -X POST "${API_BASE}/login" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=${PANEL_USER}&password=${PANEL_PASS}")

if ! echo "$LOGIN_RESP" | grep -q '"success":true'; then
    warn "API-логин не удался — добавь inbound-ы вручную через веб-панель"
    warn "Reality JSON: /tmp/inbound_reality.json"
    warn "WS TLS JSON : /tmp/inbound_vless_ws.json"
else
    # Добавляем Reality inbound
    curl -s -b "$COOKIE_JAR" -X POST "${API_BASE}/xui/API/inbounds/add" \
        -H "Content-Type: application/json" \
        -d @/tmp/inbound_reality.json | jq -r '.msg' | xargs -I{} info "Reality: {}"

    # Добавляем WS inbound
    curl -s -b "$COOKIE_JAR" -X POST "${API_BASE}/xui/API/inbounds/add" \
        -H "Content-Type: application/json" \
        -d @/tmp/inbound_vless_ws.json | jq -r '.msg' | xargs -I{} info "WS TLS: {}"

    rm -f "$COOKIE_JAR"
fi

info "=== 9. Автообновление сертификата (cron) ==="
(crontab -l 2>/dev/null; echo "0 3 * * * certbot renew --quiet && systemctl restart x-ui") | crontab -

info "=== 10. Автозапуск x-ui ==="
systemctl enable x-ui

# ---------- Итог ----------
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║           3x-ui успешно установлена!                ║${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║ Панель URL : https://${DOMAIN}:${PANEL_PORT}/${SECRET_PATH}/${NC}"
echo -e "${GREEN}║ Логин      : ${PANEL_USER}${NC}"
echo -e "${GREEN}║ Пароль     : ${PANEL_PASS}${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║ VLESS+Reality UUID : ${VLESS_REALITY_UUID}${NC}"
echo -e "${GREEN}║ Reality Public Key : ${PUBLIC_KEY}${NC}"
echo -e "${GREEN}║ Reality Short ID   : ${SHORT_ID}${NC}"
echo -e "${GREEN}║ Reality Port       : ${REALITY_PORT}${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║ VLESS+WS+TLS UUID : ${VLESS_WS_UUID}${NC}"
echo -e "${GREEN}║ WS Path           : ${WS_PATH}${NC}"
echo -e "${GREEN}║ WS Port           : ${VLESS_WS_PORT}${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}ВАЖНО: Сохрани эти данные! Выше — все UUID и ключи.${NC}"
echo ""

# Сохраняем данные в файл для бота
cat > /root/3xui_credentials.txt <<EOF
PANEL_URL=https://${DOMAIN}:${PANEL_PORT}/${SECRET_PATH}/
PANEL_USER=${PANEL_USER}
PANEL_PASS=${PANEL_PASS}
PANEL_HOST=https://${DOMAIN}
PANEL_PORT=${PANEL_PORT}
PANEL_PATH=/${SECRET_PATH}

VLESS_REALITY_UUID=${VLESS_REALITY_UUID}
REALITY_PUBLIC_KEY=${PUBLIC_KEY}
REALITY_PRIVATE_KEY=${PRIVATE_KEY}
REALITY_SHORT_ID=${SHORT_ID}
REALITY_PORT=${REALITY_PORT}

VLESS_WS_UUID=${VLESS_WS_UUID}
VLESS_WS_PATH=${WS_PATH}
VLESS_WS_PORT=${VLESS_WS_PORT}
VLESS_WS_TLS=true
VLESS_WS_DOMAIN=${DOMAIN}
EOF

chmod 600 /root/3xui_credentials.txt
info "Данные сохранены в /root/3xui_credentials.txt"
info "Готово! Запустить бота: обнови config.py данными из /root/3xui_credentials.txt"
