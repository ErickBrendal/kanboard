#!/bin/bash
# =============================================================
# CORREÇÃO COMPLETA KANBOARD - ERR_CONNECTION_REFUSED
# Execute no servidor Oracle Cloud:
#   curl -fsSL https://raw.githubusercontent.com/ErickBrendal/kanboard/main/scripts/fix_completo_agora.sh | sudo bash
# OU:
#   sudo bash /home/ubuntu/kanboard/scripts/fix_completo_agora.sh
# =============================================================
set -e

DOMAIN="kanboard.eblsolucoescorp.tec.br"
LOG="/tmp/fix_kanboard_$(date +%Y%m%d_%H%M%S).log"

log() { echo "[$(date '+%H:%M:%S')] $1" | tee -a "$LOG"; }

log "============================================================"
log "CORREÇÃO COMPLETA KANBOARD EBL - $(date)"
log "============================================================"

# Detectar diretório
for d in /home/ubuntu/kanboard /opt/kanboard-ebl ~/kanboard; do
    [ -f "$d/docker-compose.yml" ] && WORKDIR="$d" && break
done
[ -z "$WORKDIR" ] && log "ERRO: docker-compose.yml não encontrado" && exit 1
log "Diretório: $WORKDIR"
cd "$WORKDIR"

# ── PASSO 1: Atualizar repositório ──────────────────────────
log ""
log "=== [1/5] ATUALIZANDO REPOSITÓRIO ==="
git pull origin main 2>&1 | tee -a "$LOG" || log "AVISO: git pull falhou (sem internet ou sem git)"

# ── PASSO 2: Garantir config.php correto ────────────────────
log ""
log "=== [2/5] VERIFICANDO config.php ==="

# Desabilitar HSTS e usar HTTP
sed -i "s/define('ENABLE_HSTS', true)/define('ENABLE_HSTS', false)/" config.php 2>/dev/null || true
sed -i "s|define('APP_BASE_URL', 'https://|define('APP_BASE_URL', 'http://|" config.php 2>/dev/null || true
log "HSTS desabilitado, APP_BASE_URL = http://"

# ── PASSO 3: Nginx HTTP only (sem porta 443 com SSL quebrado) ─
log ""
log "=== [3/5] CONFIGURANDO NGINX ==="
cat > nginx/default.conf << 'NGINX'
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
        client_max_body_size 50M;
        proxy_read_timeout 300;
        proxy_connect_timeout 300;
    }
}
NGINX
log "Nginx configurado para HTTP only"

# Comentar porta 443 no docker-compose
sed -i 's/      - "443:443"/      # - "443:443"  # FIX: desativado/' docker-compose.yml 2>/dev/null || true
log "Porta 443 desativada no docker-compose"

# ── PASSO 4: Reiniciar containers ────────────────────────────
log ""
log "=== [4/5] REINICIANDO CONTAINERS ==="
docker compose down 2>&1 | tee -a "$LOG" || docker-compose down 2>&1 | tee -a "$LOG" || true
sleep 3
docker compose up -d 2>&1 | tee -a "$LOG" || docker-compose up -d 2>&1 | tee -a "$LOG"
log "Aguardando containers iniciarem..."
sleep 15

# ── PASSO 5: Desbloquear conta admin ─────────────────────────
log ""
log "=== [5/5] DESBLOQUEANDO CONTA ADMIN ==="
docker compose exec -T db psql -U kanboard -d kanboard -c "
UPDATE users SET nb_failed_login = 0, lock_expiration_date = 0 WHERE username = 'admin';
SELECT username, nb_failed_login, lock_expiration_date FROM users WHERE username = 'admin';
" 2>&1 | tee -a "$LOG" || log "AVISO: Não foi possível desbloquear via banco (container db pode não estar pronto)"

# ── VALIDAÇÃO FINAL ──────────────────────────────────────────
log ""
log "=== VALIDAÇÃO FINAL ==="
docker compose ps 2>&1 | tee -a "$LOG" || true

sleep 5
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 10 http://$DOMAIN/ 2>/dev/null || echo "000")
log "HTTP Status: $HTTP_STATUS"

if [ "$HTTP_STATUS" = "302" ] || [ "$HTTP_STATUS" = "200" ]; then
    log ""
    log "============================================================"
    log "SUCESSO! Kanboard acessível em: http://$DOMAIN"
    log "Login: admin / Senha@2026"
    log "============================================================"
else
    log ""
    log "AVISO: Status HTTP = $HTTP_STATUS"
    log "Verificar logs: docker compose logs --tail=50"
fi

log ""
log "Log salvo em: $LOG"
