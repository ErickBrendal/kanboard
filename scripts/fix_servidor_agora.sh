#!/bin/bash
# ============================================================
# CORREÇÃO EMERGENCIAL - Kanboard EBL
# Execute no servidor Oracle Cloud:
#   curl -fsSL https://raw.githubusercontent.com/ErickBrendal/kanboard/main/scripts/fix_servidor_agora.sh | sudo bash
# OU via console Oracle:
#   sudo bash /home/ubuntu/kanboard/scripts/fix_servidor_agora.sh
# ============================================================

set -e
DOMAIN="kanboard.eblsolucoescorp.tec.br"
LOG="/tmp/fix_kanboard_$(date +%Y%m%d_%H%M%S).log"

log() { echo "[$(date '+%H:%M:%S')] $1" | tee -a "$LOG"; }

log "============================================================"
log "CORREÇÃO EMERGENCIAL KANBOARD - $(date)"
log "============================================================"

# Detectar diretório
for d in /home/ubuntu/kanboard /opt/kanboard-ebl ~/kanboard; do
    [ -f "$d/docker-compose.yml" ] && WORKDIR="$d" && break
done
[ -z "$WORKDIR" ] && log "ERRO: docker-compose.yml não encontrado" && exit 1
log "Diretório: $WORKDIR"
cd "$WORKDIR"

# ── DIAGNÓSTICO ──────────────────────────────────────────────
log ""
log "=== STATUS ATUAL ==="
docker compose ps 2>&1 | tee -a "$LOG" || true
log ""
log "=== LOGS NGINX (últimas 30 linhas) ==="
docker compose logs --tail=30 nginx 2>&1 | tee -a "$LOG" || true

# ── BACKUP ───────────────────────────────────────────────────
TS=$(date +%Y%m%d_%H%M%S)
cp nginx/default.conf "nginx/default.conf.bak.$TS" 2>/dev/null || true
cp docker-compose.yml "docker-compose.yml.bak.$TS" 2>/dev/null || true
cp config.php "config.php.bak.$TS" 2>/dev/null || true
log "Backups criados"

# ── NGINX: HTTP ONLY (sem SSL) ────────────────────────────────
log ""
log "=== CORRIGINDO NGINX ==="
cat > nginx/default.conf << 'NGINXEOF'
server {
    listen 80;
    server_name kanboard.eblsolucoescorp.tec.br _;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        proxy_pass http://kanboard:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300;
        proxy_connect_timeout 300;
        client_max_body_size 50M;
    }
}
NGINXEOF
log "[OK] Nginx configurado para HTTP-only"

# ── DOCKER-COMPOSE: REMOVER PORTA 443 ────────────────────────
log ""
log "=== CORRIGINDO DOCKER-COMPOSE ==="
# Comentar porta 443 se estiver ativa
sed -i 's/^      - "443:443"$/      # - "443:443"  # desativado temporariamente/' docker-compose.yml
log "[OK] Porta 443 desativada no docker-compose"

# ── CONFIG.PHP: DESABILITAR HSTS ─────────────────────────────
log ""
log "=== CORRIGINDO CONFIG.PHP ==="
sed -i "s/define('ENABLE_HSTS', true)/define('ENABLE_HSTS', false)/" config.php
sed -i "s|define('APP_BASE_URL', 'https://|define('APP_BASE_URL', 'http://|" config.php
log "[OK] HSTS desabilitado"
log "[OK] APP_BASE_URL alterado para HTTP"

# Verificar
grep "ENABLE_HSTS\|APP_BASE_URL" config.php | tee -a "$LOG"

# ── REINICIAR CONTAINERS ──────────────────────────────────────
log ""
log "=== REINICIANDO CONTAINERS ==="
docker compose down 2>&1 | tee -a "$LOG"
sleep 5
docker compose up -d 2>&1 | tee -a "$LOG"
log "Aguardando 25s para inicialização..."
sleep 25

# ── VALIDAÇÃO ─────────────────────────────────────────────────
log ""
log "=== VALIDAÇÃO ==="
docker compose ps 2>&1 | tee -a "$LOG"

HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 15 "http://$DOMAIN/" 2>/dev/null || echo "000")
log "HTTP Status externo: $HTTP_STATUS"

HTTP_LOCAL=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 10 "http://localhost/" 2>/dev/null || echo "000")
log "HTTP Status local: $HTTP_LOCAL"

log ""
log "=== LOGS NGINX PÓS-RESTART ==="
docker compose logs --tail=20 nginx 2>&1 | tee -a "$LOG"

log ""
log "============================================================"
if [[ "$HTTP_STATUS" =~ ^(200|302|301)$ ]] || [[ "$HTTP_LOCAL" =~ ^(200|302|301)$ ]]; then
    log "  SUCESSO! Kanboard está acessível"
    log "  URL: http://$DOMAIN"
    log "  Login: admin / Senha@2026"
else
    log "  ATENÇÃO: Status HTTP = $HTTP_STATUS (externo) / $HTTP_LOCAL (local)"
    log "  Verifique os logs: docker compose logs nginx kanboard"
fi
log "  Log completo: $LOG"
log "============================================================"
