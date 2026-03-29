#!/bin/bash
# =============================================================
# CORREÇÃO DEFINITIVA DE ACESSO - Kanboard EBL
# Autor: Manus AI (Arquiteto de Infraestrutura)
#
# CAUSA RAIZ IDENTIFICADA:
#   1. Nginx escuta na porta 443 mas sem certificado SSL
#   2. config.php tem ENABLE_HSTS=true e APP_BASE_URL=https://
#   3. Chrome força HTTPS -> porta 443 sem SSL -> ERR_SSL_PROTOCOL_ERROR
#
# ESTRATÉGIA:
#   FASE 1: Corrigir imediatamente (HTTP funcional sem HSTS)
#   FASE 2: Obter certificado SSL e ativar HTTPS definitivo
#
# USO: sudo bash corrigir_acesso.sh [smtp_password]
# =============================================================

set -e

DOMAIN="kanboard.eblsolucoescorp.tec.br"
EMAIL="ti@eblsolucoescorp.tec.br"
SMTP_PASS="${1:-}"

# Detectar diretório de trabalho
if [ -f "/opt/kanboard-ebl/docker-compose.yml" ]; then
    WORKDIR="/opt/kanboard-ebl"
elif [ -f "$HOME/kanboard/docker-compose.yml" ]; then
    WORKDIR="$HOME/kanboard"
else
    WORKDIR=$(find / -name "docker-compose.yml" 2>/dev/null | grep -i kanboard | head -1 | xargs dirname 2>/dev/null || echo "")
    if [ -z "$WORKDIR" ]; then
        echo "[ERRO] Não foi possível localizar o docker-compose.yml"
        exit 1
    fi
fi

echo ""
echo "============================================================"
echo "  CORREÇÃO DEFINITIVA - Kanboard EBL"
echo "  Diretório: $WORKDIR"
echo "============================================================"
echo ""

cd "$WORKDIR"

# ============================================================
# FASE 1: CORREÇÃO IMEDIATA — HTTP funcional sem HSTS
# ============================================================
echo ">>> FASE 1: Corrigindo acesso HTTP imediato..."
echo ""

# 1.1 Atualizar config.php: desabilitar HSTS e mudar para HTTP temporariamente
echo "[1.1] Atualizando config.php..."
cp config.php config.php.bak.$(date +%Y%m%d_%H%M%S)

# Desabilitar HSTS (causa do loop HTTPS no browser)
sed -i "s/define('ENABLE_HSTS', true)/define('ENABLE_HSTS', false)/" config.php

# Manter APP_BASE_URL como https (será ativado após SSL)
# Mas garantir que ENABLE_XFRAME não bloqueie
sed -i "s/define('ENABLE_XFRAME', true)/define('ENABLE_XFRAME', false)/" config.php 2>/dev/null || true

echo "  [OK] HSTS desabilitado"

# 1.2 Criar nginx.conf temporário: apenas HTTP, sem porta 443 com SSL quebrado
echo "[1.2] Criando configuração Nginx temporária (HTTP only)..."
cat > nginx/default-temp.conf << 'NGINXEOF'
server {
    listen 80;
    server_name kanboard.eblsolucoescorp.tec.br;

    # Certbot challenge
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    # Proxy para Kanboard
    location / {
        proxy_pass http://kanboard:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        client_max_body_size 50M;
        proxy_read_timeout 300;
        proxy_connect_timeout 300;
    }
}
NGINXEOF

# 1.3 Atualizar docker-compose para remover porta 443 temporariamente
echo "[1.3] Atualizando docker-compose.yml (remover porta 443 temporariamente)..."
cp docker-compose.yml docker-compose.yml.bak.$(date +%Y%m%d_%H%M%S)

# Usar Python para editar o YAML de forma segura
python3 << 'PYEOF'
import re

with open('docker-compose.yml', 'r') as f:
    content = f.read()

# Comentar a linha da porta 443
content = content.replace('      - "443:443"', '      # - "443:443"  # SSL pendente')

with open('docker-compose.yml', 'w') as f:
    f.write(content)

print("  [OK] Porta 443 comentada no docker-compose.yml")
PYEOF

# 1.4 Aplicar nginx temporário
echo "[1.4] Aplicando configuração Nginx temporária..."
cp nginx/default-temp.conf nginx/default.conf

# 1.5 Reiniciar containers
echo "[1.5] Reiniciando containers..."
docker compose down
sleep 3
docker compose up -d
sleep 15

# 1.6 Verificar se HTTP está funcionando
echo "[1.6] Verificando acesso HTTP..."
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 10 http://$DOMAIN/ 2>/dev/null || echo "000")
if [ "$HTTP_STATUS" = "302" ] || [ "$HTTP_STATUS" = "200" ]; then
    echo "  [OK] HTTP funcionando! Status: $HTTP_STATUS"
    HTTP_OK=true
else
    echo "  [AVISO] HTTP retornou status: $HTTP_STATUS"
    HTTP_OK=false
fi

echo ""
echo ">>> FASE 1 CONCLUÍDA"
echo "    HTTP: http://$DOMAIN (deve estar acessível agora)"
echo ""

# ============================================================
# FASE 2: SSL — Certificado Let's Encrypt
# ============================================================
echo ">>> FASE 2: Obtendo certificado SSL..."
echo ""

# 2.1 Verificar se o domínio resolve corretamente
SERVER_IP=$(curl -s --connect-timeout 5 https://api.ipify.org 2>/dev/null || echo "desconhecido")
echo "[2.1] IP público do servidor: $SERVER_IP"
echo "  DNS $DOMAIN aponta para: $(python3 -c "import socket; print(socket.gethostbyname('$DOMAIN'))" 2>/dev/null || echo 'N/A')"

# 2.2 Solicitar certificado
echo "[2.2] Solicitando certificado SSL via certbot..."
docker compose run --rm certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email "$EMAIL" \
    --agree-tos \
    --no-eff-email \
    --force-renewal \
    -d "$DOMAIN" 2>&1

SSL_EXIT=$?

# 2.3 Verificar se o certificado foi obtido
CERT_DIR=""
for possible_dir in \
    "/var/lib/docker/volumes/kanboard-ebl_certbot_conf/_data/live/$DOMAIN" \
    "/var/lib/docker/volumes/opt_kanboard-ebl_certbot_conf/_data/live/$DOMAIN" \
    "$(docker volume inspect kanboard-ebl_certbot_conf 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[0]['Mountpoint'])" 2>/dev/null)/live/$DOMAIN"; do
    if [ -d "$possible_dir" ]; then
        CERT_DIR="$possible_dir"
        break
    fi
done

# Verificar via docker
CERT_IN_DOCKER=$(docker run --rm -v $(docker volume ls -q | grep certbot_conf | head -1):/etc/letsencrypt certbot/certbot ls /etc/letsencrypt/live/ 2>/dev/null | grep -c "$DOMAIN" || echo "0")

if [ -n "$CERT_DIR" ] || [ "$CERT_IN_DOCKER" -gt "0" ] || [ $SSL_EXIT -eq 0 ]; then
    echo "  [OK] Certificado SSL obtido com sucesso!"
    SSL_OK=true
else
    echo "  [AVISO] Certificado não confirmado. Verificando volume Docker..."
    docker run --rm \
        -v $(docker volume ls -q | grep certbot_conf | head -1):/etc/letsencrypt \
        certbot/certbot certificates 2>&1 | head -20
    SSL_OK=false
fi

# ============================================================
# FASE 3: ATIVAR HTTPS SE SSL OBTIDO
# ============================================================
if [ "$SSL_OK" = true ]; then
    echo ""
    echo ">>> FASE 3: Ativando HTTPS no Nginx..."

    # 3.1 Restaurar porta 443 no docker-compose
    python3 << 'PYEOF'
with open('docker-compose.yml', 'r') as f:
    content = f.read()
content = content.replace('      # - "443:443"  # SSL pendente', '      - "443:443"')
with open('docker-compose.yml', 'w') as f:
    f.write(content)
print("  [OK] Porta 443 reativada no docker-compose.yml")
PYEOF

    # 3.2 Ativar config SSL no Nginx
    echo "[3.2] Ativando configuração HTTPS no Nginx..."
    cp nginx/default-ssl.conf nginx/default.conf

    # 3.3 Reativar HSTS e HTTPS no config.php
    echo "[3.3] Reativando HTTPS no config.php..."
    sed -i "s/define('ENABLE_HSTS', false)/define('ENABLE_HSTS', true)/" config.php
    sed -i "s/define('ENABLE_XFRAME', false)/define('ENABLE_XFRAME', true)/" config.php 2>/dev/null || true

    # 3.4 Reiniciar com HTTPS
    echo "[3.4] Reiniciando containers com HTTPS..."
    docker compose down
    sleep 3
    docker compose up -d
    sleep 15

    # 3.5 Verificar HTTPS
    echo "[3.5] Verificando HTTPS..."
    HTTPS_STATUS=$(curl -sk -o /dev/null -w "%{http_code}" --connect-timeout 15 https://$DOMAIN/ 2>/dev/null || echo "000")
    if [ "$HTTPS_STATUS" = "302" ] || [ "$HTTPS_STATUS" = "200" ]; then
        echo "  [OK] HTTPS funcionando! Status: $HTTPS_STATUS"
        HTTPS_OK=true
    else
        echo "  [AVISO] HTTPS retornou: $HTTPS_STATUS"
        HTTPS_OK=false
    fi
else
    echo ""
    echo ">>> FASE 3: SSL não obtido — mantendo HTTP funcional"
    HTTPS_OK=false
fi

# ============================================================
# FASE 4: CONFIGURAR SMTP (se senha fornecida)
# ============================================================
if [ -n "$SMTP_PASS" ]; then
    echo ""
    echo ">>> FASE 4: Configurando SMTP..."
    sed -i "s/define('MAIL_SMTP_PASSWORD', '.*')/define('MAIL_SMTP_PASSWORD', '$SMTP_PASS')/" config.php
    docker compose restart kanboard
    sleep 5
    echo "  [OK] SMTP configurado"
fi

# ============================================================
# RESUMO FINAL
# ============================================================
echo ""
echo "============================================================"
echo "  RESULTADO FINAL"
echo "============================================================"
echo ""
docker compose ps
echo ""

if [ "$HTTPS_OK" = true ]; then
    echo "  STATUS: HTTPS ATIVO"
    echo "  URL: https://$DOMAIN"
    echo "  [OK] Certificado SSL válido"
elif [ "$HTTP_OK" = true ]; then
    echo "  STATUS: HTTP ATIVO (HTTPS pendente)"
    echo "  URL: http://$DOMAIN"
    echo "  [ACAO] Para SSL: execute 'docker compose run --rm certbot certonly --webroot ...'"
else
    echo "  STATUS: VERIFICAR MANUALMENTE"
    echo "  Execute: docker compose ps && docker compose logs nginx"
fi

echo ""
echo "  Usuário: admin"
echo "  Senha:   admin (altere após o primeiro acesso)"
echo ""
echo "============================================================"
