#!/bin/bash
# ============================================================
# Script para ativar HTTPS no Kanboard - EBL Soluções Corp
# Execute no servidor: sudo bash ativar_https.sh
# ============================================================

set -e
DOMAIN="kanboard.eblsolucoescorp.tec.br"
EMAIL="ti@eblsolucoescorp.tec.br"

# Detectar diretório de trabalho
if [ -f "/opt/kanboard-ebl/docker-compose.yml" ]; then
    WORKDIR="/opt/kanboard-ebl"
elif [ -f "$HOME/kanboard/docker-compose.yml" ]; then
    WORKDIR="$HOME/kanboard"
else
    WORKDIR=$(find /opt /home -name "docker-compose.yml" 2>/dev/null | head -1 | xargs dirname 2>/dev/null || echo "/opt/kanboard-ebl")
fi

echo "======================================"
echo "  ATIVANDO HTTPS NO KANBOARD"
echo "  Domínio: $DOMAIN"
echo "  Diretório: $WORKDIR"
echo "======================================"
echo ""

cd "$WORKDIR"

# 1. Verificar containers
echo "[1/5] Verificando containers..."
docker compose ps

# 2. Obter certificado SSL
echo ""
echo "[2/5] Obtendo certificado SSL Let's Encrypt..."
docker compose run --rm certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email "$EMAIL" \
    --agree-tos \
    --no-eff-email \
    -d "$DOMAIN"

echo "Certificado obtido!"

# 3. Atualizar configuração Nginx
echo ""
echo "[3/5] Atualizando configuração Nginx para HTTPS..."
cat > nginx/default.conf << 'NGINX_CONF'
server {
    listen 80;
    server_name kanboard.eblsolucoescorp.tec.br;
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }
    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl;
    server_name kanboard.eblsolucoescorp.tec.br;

    ssl_certificate /etc/letsencrypt/live/kanboard.eblsolucoescorp.tec.br/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/kanboard.eblsolucoescorp.tec.br/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    location / {
        proxy_pass http://kanboard:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        client_max_body_size 50M;
    }
}
NGINX_CONF

echo "Configuração Nginx atualizada!"

# 4. Reiniciar Nginx
echo ""
echo "[4/5] Reiniciando Nginx..."
docker compose restart nginx
sleep 3

# 5. Verificar HTTPS
echo ""
echo "[5/5] Verificando HTTPS..."
HTTP_CODE=$(curl -sk -o /dev/null -w "%{http_code}" --connect-timeout 10 "https://$DOMAIN/" 2>/dev/null || echo "ERRO")
echo "HTTPS Status: $HTTP_CODE"

if [ "$HTTP_CODE" = "302" ] || [ "$HTTP_CODE" = "200" ]; then
    echo ""
    echo "======================================"
    echo "  HTTPS ATIVADO COM SUCESSO!"
    echo "  Acesse: https://$DOMAIN"
    echo "======================================"
else
    echo "AVISO: HTTPS retornou $HTTP_CODE - verificar logs: docker compose logs nginx"
fi

# Atualizar URL no config.php
echo ""
echo "Atualizando URL base para HTTPS no config.php..."
if grep -q "APP_BASE_URL\|application_url" config.php 2>/dev/null; then
    sed -i "s|http://kanboard|https://kanboard|g" config.php
    docker compose restart kanboard
    echo "URL atualizada e Kanboard reiniciado!"
fi

echo ""
echo "Configurar renovação automática do certificado:"
echo "  (crontab -l 2>/dev/null; echo '0 12 * * * cd $WORKDIR && docker compose run --rm certbot renew --quiet && docker compose restart nginx') | crontab -"
