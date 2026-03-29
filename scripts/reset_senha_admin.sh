#!/bin/bash
# =============================================================================
# RESET DE SENHA DO ADMIN - Kanboard EBL
# Executa dentro do container PostgreSQL para resetar a senha do admin
# =============================================================================

set -e

echo "=================================================="
echo "  RESET DE SENHA DO ADMIN - Kanboard EBL"
echo "=================================================="

# Diretório do projeto
cd /opt/kanboard-ebl 2>/dev/null || cd ~/kanboard-ebl 2>/dev/null || {
  echo "Tentando encontrar o projeto..."
  PROJ=$(find / -name "docker-compose.yml" -path "*/kanboard*" 2>/dev/null | head -1 | xargs dirname)
  cd "$PROJ" || { echo "ERRO: Projeto não encontrado"; exit 1; }
}

echo "Projeto em: $(pwd)"

# Verificar containers rodando
echo ""
echo "Containers ativos:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -i "kanboard\|postgres\|db" || docker ps

# Identificar o container do banco de dados
DB_CONTAINER=$(docker ps --format "{{.Names}}" | grep -i "db\|postgres\|sql" | head -1)
APP_CONTAINER=$(docker ps --format "{{.Names}}" | grep -i "kanboard\|app\|web" | grep -v "db\|postgres" | head -1)

echo ""
echo "Container DB: $DB_CONTAINER"
echo "Container App: $APP_CONTAINER"

# Hash bcrypt da nova senha: EBL@Kanboard2026
# Gerado com bcrypt rounds=10
NOVA_SENHA="EBL@Kanboard2026"
HASH='$2b$10$pRrgh.GCMwmki7aRhX7vJec65A3R05I0jO4kGAoryfF9F1nHcUJSO'

echo ""
echo "Resetando senha do admin..."

# Método 1: Tentar via container do banco PostgreSQL
if [ -n "$DB_CONTAINER" ]; then
  echo "Tentando via container PostgreSQL: $DB_CONTAINER"
  
  # Obter variáveis do banco
  DB_NAME=$(docker exec "$DB_CONTAINER" env | grep -i "POSTGRES_DB\|DB_NAME" | cut -d= -f2 | head -1)
  DB_USER=$(docker exec "$DB_CONTAINER" env | grep -i "POSTGRES_USER\|DB_USER" | cut -d= -f2 | head -1)
  
  DB_NAME=${DB_NAME:-kanboard}
  DB_USER=${DB_USER:-kanboard}
  
  echo "  DB: $DB_NAME, User: $DB_USER"
  
  docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c \
    "UPDATE users SET password = '$HASH' WHERE username = 'admin';" && \
    echo "✅ Senha resetada com sucesso via PostgreSQL!" || \
    echo "❌ Falhou via PostgreSQL"
fi

# Método 2: Tentar via container da aplicação (PHP)
if [ -n "$APP_CONTAINER" ]; then
  echo ""
  echo "Tentando via container da aplicação: $APP_CONTAINER"
  
  docker exec "$APP_CONTAINER" php -r "
    \$hash = password_hash('$NOVA_SENHA', PASSWORD_BCRYPT);
    echo \$hash . PHP_EOL;
  " && echo "PHP hash gerado"
  
  # Tentar via PHP CLI dentro do container
  docker exec "$APP_CONTAINER" php -r "
    require '/var/www/app/app/Core/Security/Token.php';
    echo 'PHP OK';
  " 2>/dev/null || true
fi

# Método 3: Verificar se há arquivo config.php com credenciais do banco
echo ""
echo "Verificando configurações do banco..."
find . -name "*.env" -o -name "config.php" 2>/dev/null | head -5 | xargs grep -l "DB_\|database\|postgres" 2>/dev/null | head -3

# Mostrar variáveis de ambiente do docker-compose
echo ""
echo "Variáveis do banco no docker-compose:"
grep -i "POSTGRES\|DB_\|database\|password" docker-compose.yml 2>/dev/null | grep -v "^#" | head -10

echo ""
echo "=================================================="
echo "  RESULTADO"
echo "=================================================="
echo "Nova senha: $NOVA_SENHA"
echo "URL: http://kanboard.eblsolucoescorp.tec.br"
echo "Usuário: admin"
echo ""
echo "Teste de acesso:"
curl -s --connect-timeout 10 -X POST http://kanboard.eblsolucoescorp.tec.br/jsonrpc.php \
  -H "Content-Type: application/json" \
  -u "admin:$NOVA_SENHA" \
  -d '{"jsonrpc":"2.0","method":"getMe","id":1,"params":{}}' | python3 -c "
import sys, json
try:
  d = json.load(sys.stdin)
  r = d.get('result', {})
  if r:
    print('✅ LOGIN OK! Usuário:', r.get('username'), '| Nome:', r.get('name'))
  else:
    print('❌ Falhou:', d.get('error', {}).get('message'))
except:
  print('❌ Erro ao parsear resposta')
" 2>/dev/null || echo "Teste de API falhou"
