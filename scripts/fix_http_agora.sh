#!/bin/bash
# =============================================================
# FIX EMERGENCIAL — Restaura acesso HTTP imediato ao Kanboard
# Resolve: ERR_CONNECTION_REFUSED causado por HSTS + porta 443 sem SSL
# Uso: sudo bash fix_http_agora.sh
# =============================================================

set -e

DOMAIN="kanboard.eblsolucoescorp.tec.br"

# Detectar diretório
for d in /opt/kanboard-ebl ~/kanboard; do
    [ -f "$d/docker-compose.yml" ] && WORKDIR="$d" && break
done
[ -z "$WORKDIR" ] && echo "ERRO: docker-compose.yml não encontrado" && exit 1

cd "$WORKDIR"
echo "=== Fix Emergencial Kanboard ==="
echo "Diretório: $WORKDIR"

# 1. Desabilitar HSTS no config.php
sed -i "s/define('ENABLE_HSTS', true)/define('ENABLE_HSTS', false)/" config.php
echo "[OK] HSTS desabilitado"

# 2. Nginx: apenas HTTP (sem porta 443 com SSL quebrado)
cat > nginx/default.conf << 'EOF'
server {
    listen 80;
    server_name kanboard.eblsolucoescorp.tec.br;
    location /.well-known/acme-challenge/ { root /var/www/certbot; }
    location / {
        proxy_pass http://kanboard:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        client_max_body_size 50M;
    }
}
EOF
echo "[OK] Nginx configurado para HTTP"

# 3. Remover porta 443 do docker-compose temporariamente
sed -i 's/      - "443:443"/      # - "443:443"/' docker-compose.yml
echo "[OK] Porta 443 desativada no docker-compose"

# 4. Reiniciar
docker compose down && sleep 3 && docker compose up -d
echo "[OK] Containers reiniciados"
sleep 15

# 5. Validar
STATUS=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 10 http://$DOMAIN/ 2>/dev/null)
echo ""
if [ "$STATUS" = "302" ] || [ "$STATUS" = "200" ]; then
    echo "=== SUCESSO ==="
    echo "Acesse: http://$DOMAIN"
    echo "Login: admin / admin"
else
    echo "=== AVISO: Status HTTP = $STATUS ==="
    docker compose ps
    docker compose logs --tail=20 nginx
fi
