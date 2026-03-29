#!/bin/bash
# =============================================================
# CORREÇÃO REMOTA COMPLETA - Kanboard EBL
# Executado diretamente no servidor Oracle Cloud
# =============================================================
set -e

DOMAIN="kanboard.eblsolucoescorp.tec.br"
EMAIL="ti@eblsolucoescorp.tec.br"
LOG="/tmp/kanboard_fix_$(date +%Y%m%d_%H%M%S).log"

log() { echo "[$(date '+%H:%M:%S')] $1" | tee -a "$LOG"; }

log "=== INICIANDO CORREÇÃO COMPLETA ==="
log "Servidor: $DOMAIN"
log "Log: $LOG"

# ── Detectar diretório ──────────────────────────────────────
for d in /opt/kanboard-ebl ~/kanboard /home/ubuntu/kanboard; do
    [ -f "$d/docker-compose.yml" ] && WORKDIR="$d" && break
done
[ -z "$WORKDIR" ] && log "ERRO: docker-compose.yml não encontrado" && exit 1
log "Diretório: $WORKDIR"
cd "$WORKDIR"

# ── 1. Status atual ─────────────────────────────────────────
log ""
log "=== [1/6] STATUS ATUAL ==="
docker compose ps 2>&1 | tee -a "$LOG" || true

# ── 2. Backup dos arquivos ──────────────────────────────────
log ""
log "=== [2/6] BACKUP ==="
TS=$(date +%Y%m%d_%H%M%S)
cp config.php "config.php.bak.$TS" && log "config.php backup OK"
cp docker-compose.yml "docker-compose.yml.bak.$TS" && log "docker-compose.yml backup OK"
cp nginx/default.conf "nginx/default.conf.bak.$TS" && log "nginx/default.conf backup OK"

# ── 3. Corrigir config.php ──────────────────────────────────
log ""
log "=== [3/6] CORRIGINDO config.php ==="

# Desabilitar HSTS temporariamente (causa do loop HTTPS)
sed -i "s/define('ENABLE_HSTS', true)/define('ENABLE_HSTS', false)/" config.php
log "HSTS desabilitado"

# Manter APP_BASE_URL como http temporariamente
sed -i "s|define('APP_BASE_URL', 'https://|define('APP_BASE_URL', 'http://|" config.php
log "APP_BASE_URL alterado para http"

# Verificar
grep "ENABLE_HSTS\|APP_BASE_URL" config.php | tee -a "$LOG"

# ── 4. Corrigir Nginx ───────────────────────────────────────
log ""
log "=== [4/6] CORRIGINDO NGINX ==="

# Nginx: apenas HTTP, sem porta 443 quebrada
cat > nginx/default.conf << 'NGINXEOF'
server {
    listen 80;
    server_name kanboard.eblsolucoescorp.tec.br;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

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
log "Nginx configurado para HTTP apenas"

# Remover porta 443 do docker-compose
sed -i 's/      - "443:443"/      # - "443:443"  # SSL pendente/' docker-compose.yml
log "Porta 443 comentada no docker-compose.yml"

# ── 5. Reiniciar containers ─────────────────────────────────
log ""
log "=== [5/6] REINICIANDO CONTAINERS ==="
docker compose down 2>&1 | tee -a "$LOG"
sleep 5
docker compose up -d 2>&1 | tee -a "$LOG"
log "Aguardando containers ficarem prontos..."
sleep 20

# ── 6. Validar HTTP ─────────────────────────────────────────
log ""
log "=== [6/6] VALIDAÇÃO ==="
docker compose ps 2>&1 | tee -a "$LOG"

HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 15 "http://$DOMAIN/" 2>/dev/null || echo "000")
log "HTTP Status: $HTTP_STATUS"

if [ "$HTTP_STATUS" = "302" ] || [ "$HTTP_STATUS" = "200" ]; then
    log ""
    log "============================================"
    log "  FASE 1 CONCLUÍDA COM SUCESSO!"
    log "  URL: http://$DOMAIN"
    log "  Login: admin / admin"
    log "============================================"
    FASE1_OK=true
else
    log "AVISO: HTTP retornou $HTTP_STATUS"
    docker compose logs --tail=30 nginx 2>&1 | tee -a "$LOG"
    FASE1_OK=false
fi

# ── FASE 2: SSL Let's Encrypt ───────────────────────────────
log ""
log "=== FASE 2: OBTENDO CERTIFICADO SSL ==="

# Verificar IP do servidor
MY_IP=$(curl -s --connect-timeout 5 https://api.ipify.org 2>/dev/null || echo "N/A")
DNS_IP=$(python3 -c "import socket; print(socket.gethostbyname('$DOMAIN'))" 2>/dev/null || echo "N/A")
log "IP do servidor: $MY_IP"
log "DNS $DOMAIN -> $DNS_IP"

if [ "$MY_IP" != "$DNS_IP" ] && [ "$DNS_IP" != "N/A" ]; then
    log "AVISO: IP do servidor ($MY_IP) diferente do DNS ($DNS_IP)"
    log "Certbot pode falhar. Verifique o DNS."
fi

# Solicitar certificado
log "Solicitando certificado para $DOMAIN..."
docker compose run --rm certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email "$EMAIL" \
    --agree-tos \
    --no-eff-email \
    --force-renewal \
    -d "$DOMAIN" 2>&1 | tee -a "$LOG"
CERTBOT_EXIT=${PIPESTATUS[0]}

# Verificar certificado
CERT_OK=false
CERT_VOLUME=$(docker volume ls -q 2>/dev/null | grep -E "certbot_conf|letsencrypt" | head -1)
if [ -n "$CERT_VOLUME" ]; then
    CERT_CHECK=$(docker run --rm -v "${CERT_VOLUME}:/etc/letsencrypt" certbot/certbot \
        certificates 2>/dev/null | grep -c "VALID" || echo "0")
    [ "$CERT_CHECK" -gt "0" ] && CERT_OK=true
fi
[ $CERTBOT_EXIT -eq 0 ] && CERT_OK=true

if [ "$CERT_OK" = true ]; then
    log "Certificado SSL obtido com sucesso!"

    # Reativar porta 443
    sed -i 's/      # - "443:443"  # SSL pendente/      - "443:443"/' docker-compose.yml
    log "Porta 443 reativada"

    # Ativar config HTTPS no Nginx
    cp nginx/default-ssl.conf nginx/default.conf
    log "Nginx configurado para HTTPS"

    # Reativar HSTS e https no config.php
    sed -i "s/define('ENABLE_HSTS', false)/define('ENABLE_HSTS', true)/" config.php
    sed -i "s|define('APP_BASE_URL', 'http://|define('APP_BASE_URL', 'https://|" config.php
    log "HSTS e APP_BASE_URL reativados para HTTPS"

    # Reiniciar com HTTPS
    docker compose down && sleep 5 && docker compose up -d
    log "Containers reiniciados com HTTPS"
    sleep 20

    # Validar HTTPS
    HTTPS_STATUS=$(curl -sk -o /dev/null -w "%{http_code}" --connect-timeout 15 "https://$DOMAIN/" 2>/dev/null || echo "000")
    log "HTTPS Status: $HTTPS_STATUS"

    if [ "$HTTPS_STATUS" = "302" ] || [ "$HTTPS_STATUS" = "200" ]; then
        log ""
        log "============================================"
        log "  FASE 2 CONCLUÍDA - HTTPS ATIVO!"
        log "  URL: https://$DOMAIN"
        log "  SSL: Let's Encrypt válido"
        log "============================================"
        FASE2_OK=true
    else
        log "AVISO: HTTPS retornou $HTTPS_STATUS"
        FASE2_OK=false
    fi
else
    log "Certificado SSL não obtido (certbot exit: $CERTBOT_EXIT)"
    log "Mantendo HTTP funcional"
    FASE2_OK=false
fi

# ── RESUMO FINAL ────────────────────────────────────────────
log ""
log "============================================"
log "  RESULTADO FINAL"
log "============================================"
docker compose ps 2>&1 | tee -a "$LOG"
log ""
if [ "$FASE2_OK" = true ]; then
    log "  STATUS: HTTPS ATIVO E FUNCIONAL"
    log "  URL: https://$DOMAIN"
elif [ "$FASE1_OK" = true ]; then
    log "  STATUS: HTTP ATIVO (HTTPS pendente)"
    log "  URL: http://$DOMAIN"
    log "  Para SSL: re-execute este script após verificar DNS"
else
    log "  STATUS: VERIFICAR MANUALMENTE"
    log "  Execute: docker compose logs nginx"
fi
log "  Login: admin / admin"
log "  Log completo: $LOG"
log "============================================"

# Salvar resultado para consulta
echo "{\"fase1\": $FASE1_OK, \"fase2\": $FASE2_OK, \"http_status\": \"$HTTP_STATUS\", \"https_status\": \"${HTTPS_STATUS:-N/A}\"}" > /tmp/kanboard_fix_result.json
cat /tmp/kanboard_fix_result.json
