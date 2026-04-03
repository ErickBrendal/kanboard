#!/bin/bash
# Desbloquear conta admin no Kanboard (reset brute force lock)
echo "=== Desbloqueando conta admin ==="

# Encontrar diretório do projeto
for d in /home/ubuntu/kanboard /opt/kanboard-ebl ~/kanboard; do
    [ -f "$d/docker-compose.yml" ] && WORKDIR="$d" && break
done
[ -z "$WORKDIR" ] && echo "ERRO: docker-compose.yml não encontrado" && exit 1
cd "$WORKDIR"

echo "Diretório: $WORKDIR"

# Resetar o bloqueio de brute force no banco de dados
docker compose exec -T db psql -U kanboard -d kanboard -c "
UPDATE users 
SET nb_failed_login = 0, 
    lock_expiration_date = 0 
WHERE username = 'admin';
SELECT username, nb_failed_login, lock_expiration_date FROM users WHERE username = 'admin';
" 2>&1

echo ""
echo "=== Conta admin desbloqueada ==="
