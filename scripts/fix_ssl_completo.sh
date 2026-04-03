#!/bin/bash
# =============================================================
# CORREÇÃO SSL/HTTPS - Kanboard EBL Soluções Corporativas
# Problema: ERR_CONNECTION_REFUSED por falha no certificado SSL
# Executar como: sudo bash fix_ssl_completo.sh
# =============================================================
set -e

DOMAIN="kanboard.eblsolucoescorp.tec.br"
EMAIL="ti@eblsolucoescorp.tec.br"
LOG="/tmp/fix_ssl_$(date +%Y%m%d_%H%M%S).log"

log() { echo "[$(date '+%H:%M:%S')] $1" | tee -a "$LOG"; }

log "=== CORREÇÃO SSL/HTTPS KANBOARD EBL ==="
log "Domínio: $DOMAIN"
log "Log: $LOG"

# ── Detectar diretório de trabalho ──────────────────────────
for d in /home/ubuntu/kanboard /opt/kanboard-ebl ~/kanboard; do
    [ -f "$d/docker-compose.yml" ] && WORKDIR="$d" && break
done
[ -z "$WORKDIR" ] && log "ERRO: docker-compose.yml não encontrado" && exit 1
log "Diretório: $WORKDIR"
cd "$WORKDIR"

# ── 1. Status atual dos containers ──────────────────────────
log ""
log "=== [1/7] STATUS ATUAL DOS CONTAINERS ==="
docker compose ps 2>&1 | tee -a "$LOG" || docker-compose ps 2>&1 | tee -a "$LOG" || true

# ── 2. Backup dos arquivos críticos ─────────────────────────
log ""
log "=== [2/7] BACKUP ==="
TS=$(date +%Y%m%d_%H%M%S)
cp config.php "config.php.bak.$TS" && log "config.php backup OK"
cp nginx/default.conf "nginx/default.conf.bak.$TS" && log "nginx/default.conf backup OK"

# ── 3. Verificar certificado SSL atual ──────────────────────
log ""
log "=== [3/7] VERIFICANDO CERTIFICADO SSL ==="
CERT_PATH="/etc/letsencrypt/live/$DOMAIN/fullchain.pem"

if docker compose exec -T nginx test -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" 2>/dev/null; then
    log "Certificado encontrado no container nginx"
    docker compose exec -T nginx openssl x509 -in "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" -noout -dates 2>&1 | tee -a "$LOG" || true
elif [ -f "$CERT_PATH" ]; then
    log "Certificado encontrado no host"
    openssl x509 -in "$CERT_PATH" -noout -dates 2>&1 | tee -a "$LOG" || true
else
    log "AVISO: Certificado SSL não encontrado — será emitido novo certificado"
fi

# ── 4. Garantir que porta 80 está acessível para ACME ───────
log ""
log "=== [4/7] CONFIGURANDO NGINX PARA ACME CHALLENGE ==="

# Usar config HTTP simples (sem redirect HTTPS) para permitir certbot
cat > nginx/default.conf << 'NGINX_HTTP'
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
    }
}
NGINX_HTTP

log "Config nginx HTTP aplicada"

# ── 5. Garantir que containers estão rodando ────────────────
log ""
log "=== [5/7] REINICIANDO CONTAINERS ==="
docker compose up -d --remove-orphans 2>&1 | tee -a "$LOG" || docker-compose up -d --remove-orphans 2>&1 | tee -a "$LOG"
sleep 5

# Recarregar nginx com nova config
docker compose exec -T nginx nginx -s reload 2>&1 | tee -a "$LOG" || true
log "Nginx recarregado"

# ── 6. Emitir/renovar certificado Let's Encrypt ─────────────
log ""
log "=== [6/7] EMITINDO/RENOVANDO CERTIFICADO SSL ==="

# Tentar renovação primeiro
if docker compose run --rm certbot renew --webroot -w /var/www/certbot 2>&1 | tee -a "$LOG"; then
    log "Certificado renovado com sucesso"
else
    log "Renovação falhou — tentando emissão de novo certificado..."
    docker compose run --rm certbot certonly \
        --webroot \
        -w /var/www/certbot \
        -d "$DOMAIN" \
        --email "$EMAIL" \
        --agree-tos \
        --non-interactive \
        --force-renewal 2>&1 | tee -a "$LOG" || {
            log "AVISO: Certbot falhou. Verificar logs acima."
        }
fi

# ── 7. Ativar HTTPS com certificado válido ──────────────────
log ""
log "=== [7/7] ATIVANDO CONFIGURAÇÃO HTTPS ==="

# Verificar se certificado foi emitido
if docker compose exec -T nginx test -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" 2>/dev/null || \
   [ -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then

    log "Certificado válido encontrado — ativando HTTPS"

    # Aplicar config SSL completa
    cat > nginx/default.conf << 'NGINX_SSL'
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
    listen 443 ssl http2;
    server_name kanboard.eblsolucoescorp.tec.br;

    ssl_certificate /etc/letsencrypt/live/kanboard.eblsolucoescorp.tec.br/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/kanboard.eblsolucoescorp.tec.br/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    add_header Strict-Transport-Security "max-age=63072000" always;
    add_header X-Frame-Options SAMEORIGIN;
    add_header X-Content-Type-Options nosniff;

    client_max_body_size 50M;

    location / {
        proxy_pass http://kanboard:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_read_timeout 300;
        proxy_connect_timeout 300;
    }
}
NGINX_SSL

    log "Config HTTPS aplicada"
    docker compose exec -T nginx nginx -s reload 2>&1 | tee -a "$LOG" || true
    log "Nginx recarregado com HTTPS"

else
    log "AVISO: Certificado não encontrado — mantendo HTTP por enquanto"
    log "Acesse via: http://$DOMAIN"
fi

# ── Status final ─────────────────────────────────────────────
log ""
log "=== STATUS FINAL ==="
docker compose ps 2>&1 | tee -a "$LOG" || true

log ""
log "=== TESTE DE ACESSO ==="
sleep 3
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 10 http://$DOMAIN/ 2>/dev/null || echo "000")
log "HTTP Status: $HTTP_STATUS"

HTTPS_STATUS=$(curl -sk -o /dev/null -w "%{http_code}" --connect-timeout 10 https://$DOMAIN/ 2>/dev/null || echo "000")
log "HTTPS Status: $HTTPS_STATUS"

log ""
log "=== CORREÇÃO CONCLUÍDA ==="
log "Log salvo em: $LOG"
log "Acesse: https://$DOMAIN"
