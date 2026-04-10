#!/bin/bash
# ============================================================
# SETUP SSL COMPLETO - Kanboard EBL
# Emite certificado Let's Encrypt e habilita HTTPS no nginx
# ============================================================
set -e

DOMAIN="kanboard.eblsolucoescorp.tec.br"
EMAIL="ti@eblsolucoescorp.tec.br"
WORKDIR="/opt/kanboard-ebl"
LOG="/tmp/ssl_setup_$(date +%Y%m%d_%H%M%S).log"

log() { echo "[$(date '+%H:%M:%S')] $1" | tee -a "$LOG"; }

log "============================================================"
log "SETUP SSL COMPLETO - $DOMAIN"
log "============================================================"

cd "$WORKDIR"

# ── PASSO 1: Emitir certificado SSL ─────────────────────────
log ""
log "[1/5] Emitindo certificado SSL via Certbot..."
docker exec kanboard_certbot certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email "$EMAIL" \
    --agree-tos \
    --no-eff-email \
    --force-renewal \
    -d "$DOMAIN" 2>&1 | tee -a "$LOG"

# Verificar se certificado foi emitido
if docker exec kanboard_certbot test -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem"; then
    log "Certificado SSL emitido com sucesso!"
else
    log "ERRO: Certificado nao foi gerado. Verifique o log acima."
    exit 1
fi

# ── PASSO 2: Criar nova configuração nginx com HTTPS ────────
log ""
log "[2/5] Criando configuracao nginx com HTTPS..."

# Backup da config atual
cp "$WORKDIR/nginx/default.conf" "$WORKDIR/nginx/default.conf.bak.$(date +%Y%m%d_%H%M%S)"

cat > "$WORKDIR/nginx/default.conf" << 'NGINX_CONF'
# HTTP → redirecionar para HTTPS
server {
    listen 80;
    server_name kanboard.eblsolucoescorp.tec.br;

    # Certbot challenge (necessário para renovação)
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    # Redirecionar tudo para HTTPS
    location / {
        return 301 https://$host$request_uri;
    }
}

# HTTPS
server {
    listen 443 ssl;
    server_name kanboard.eblsolucoescorp.tec.br;

    # Certificados SSL
    ssl_certificate     /etc/letsencrypt/live/kanboard.eblsolucoescorp.tec.br/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/kanboard.eblsolucoescorp.tec.br/privkey.pem;

    # Configurações SSL seguras
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-CHACHA20-POLY1305;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;

    # Headers de segurança
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options SAMEORIGIN always;
    add_header X-Content-Type-Options nosniff always;

    # Proxy para Kanboard
    location / {
        proxy_pass http://kanboard:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        client_max_body_size 50M;
        proxy_read_timeout 300;
        proxy_connect_timeout 300;
    }
}
NGINX_CONF

log "Configuracao nginx criada."

# ── PASSO 3: Habilitar porta 443 no docker-compose ──────────
log ""
log "[3/5] Habilitando porta 443 no docker-compose.yml..."

# Backup
cp "$WORKDIR/docker-compose.yml" "$WORKDIR/docker-compose.yml.bak.$(date +%Y%m%d_%H%M%S)"

# Habilitar porta 443 (remover comentário)
sed -i 's|# - "443:443".*|      - "443:443"|g' "$WORKDIR/docker-compose.yml"
sed -i 's|#- "443:443".*|      - "443:443"|g' "$WORKDIR/docker-compose.yml"

# Verificar se a linha foi alterada
if grep -q '"443:443"' "$WORKDIR/docker-compose.yml"; then
    log "Porta 443 habilitada no docker-compose.yml"
else
    # Adicionar manualmente se sed não funcionou
    sed -i 's|      - "80:80"|      - "80:80"\n      - "443:443"|' "$WORKDIR/docker-compose.yml"
    log "Porta 443 adicionada manualmente"
fi

# ── PASSO 4: Atualizar config.php para HTTPS ────────────────
log ""
log "[4/5] Atualizando config.php para HTTPS..."

cp "$WORKDIR/config.php" "$WORKDIR/config.php.bak.$(date +%Y%m%d_%H%M%S)"

# Atualizar APP_BASE_URL para https
sed -i "s|define('APP_BASE_URL', 'http://|define('APP_BASE_URL', 'https://|g" "$WORKDIR/config.php"

# Garantir que ENABLE_HSTS está false (para evitar loops)
if grep -q "ENABLE_HSTS" "$WORKDIR/config.php"; then
    sed -i "s|define('ENABLE_HSTS', true)|define('ENABLE_HSTS', false)|g" "$WORKDIR/config.php"
else
    echo "define('ENABLE_HSTS', false);" >> "$WORKDIR/config.php"
fi

log "config.php atualizado."

# ── PASSO 5: Reiniciar containers ───────────────────────────
log ""
log "[5/5] Reiniciando containers..."

docker compose down 2>&1 | tee -a "$LOG"
sleep 3
docker compose up -d 2>&1 | tee -a "$LOG"
sleep 10

log ""
log "=== STATUS FINAL ==="
docker compose ps 2>&1 | tee -a "$LOG"

log ""
log "=== TESTE HTTPS ==="
sleep 5
curl -s -o /dev/null -w "HTTP: %{http_code}\n" http://$DOMAIN/ 2>&1 | tee -a "$LOG"
curl -sk -o /dev/null -w "HTTPS: %{http_code}\n" https://$DOMAIN/ 2>&1 | tee -a "$LOG"

log ""
log "============================================================"
log "SETUP SSL CONCLUIDO"
log "Log completo: $LOG"
log "============================================================"
