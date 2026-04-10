#!/bin/bash
# Correção final: docker-compose.yml e reinicialização com SSL
set -e

DOMAIN="kanboard.eblsolucoescorp.tec.br"
WORKDIR="/opt/kanboard-ebl"

log() { echo "[$(date '+%H:%M:%S')] $1"; }

log "=== CORRIGINDO docker-compose.yml ==="
cd "$WORKDIR"

# Reescrever o docker-compose.yml com a porta 443 correta
cat > "$WORKDIR/docker-compose.yml" << 'COMPOSE'
version: '3.8'
services:
  kanboard:
    image: kanboard/kanboard:latest
    container_name: kanboard_app
    restart: always
    volumes:
      - kanboard_data:/var/www/app/data
      - kanboard_plugins:/var/www/app/plugins
      - ./config.php:/var/www/app/config.php:ro
      - ./css/custom.css:/var/www/app/assets/css/custom.css:ro
    environment:
      DATABASE_URL: "postgres://kanboard:${DB_PASSWORD}@db:5432/kanboard"
      APP_VERSION: "master"
    depends_on:
      db:
        condition: service_healthy
    networks:
      - kanboard_net
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:80/"]
      interval: 30s
      timeout: 10s
      retries: 3

  db:
    image: postgres:16-alpine
    container_name: kanboard_db
    restart: always
    volumes:
      - pg_data:/var/lib/postgresql/data
    environment:
      POSTGRES_USER: kanboard
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: kanboard
    networks:
      - kanboard_net
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U kanboard"]
      interval: 10s
      timeout: 5s
      retries: 5

  nginx:
    image: nginx:alpine
    container_name: kanboard_nginx
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/default.conf:/etc/nginx/conf.d/default.conf:ro
      - certbot_www:/var/www/certbot
      - certbot_conf:/etc/letsencrypt:ro
      - ./ssl:/etc/ssl/kanboard:ro
    depends_on:
      - kanboard
    networks:
      - kanboard_net

  certbot:
    image: certbot/certbot
    container_name: kanboard_certbot
    volumes:
      - certbot_www:/var/www/certbot
      - certbot_conf:/etc/letsencrypt
    entrypoint: "/bin/sh -c 'trap exit TERM; while :; do certbot renew; sleep 12h & wait $${!}; done;'"
    networks:
      - kanboard_net

volumes:
  kanboard_data:
  kanboard_plugins:
  pg_data:
  certbot_www:
  certbot_conf:

networks:
  kanboard_net:
    driver: bridge
COMPOSE

log "docker-compose.yml corrigido."

# Validar YAML
docker compose config > /dev/null 2>&1 && log "YAML valido!" || { log "ERRO no YAML"; docker compose config; exit 1; }

log ""
log "=== REINICIANDO CONTAINERS ==="
docker compose down
sleep 3
docker compose up -d
sleep 15

log ""
log "=== STATUS DOS CONTAINERS ==="
docker compose ps

log ""
log "=== TESTANDO ACESSO ==="
sleep 5
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 http://$DOMAIN/ 2>/dev/null || echo "ERR")
HTTPS_CODE=$(curl -sk -o /dev/null -w "%{http_code}" --max-time 10 https://$DOMAIN/ 2>/dev/null || echo "ERR")

log "HTTP  $DOMAIN: $HTTP_CODE"
log "HTTPS $DOMAIN: $HTTPS_CODE"

if [ "$HTTPS_CODE" = "200" ] || [ "$HTTPS_CODE" = "302" ]; then
    log ""
    log "HTTPS funcionando corretamente!"
else
    log ""
    log "AVISO: HTTPS retornou $HTTPS_CODE - verificar logs do nginx"
    docker logs kanboard_nginx --tail 20
fi

log ""
log "=== CONCLUIDO ==="
