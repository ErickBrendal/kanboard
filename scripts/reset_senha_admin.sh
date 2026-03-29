#!/bin/bash
# =============================================================================
# RESET DE SENHA DO ADMIN - Kanboard EBL
# Execute este script no servidor Oracle Cloud
# =============================================================================

set -e

echo "=================================================="
echo "  RESET DE SENHA DO ADMIN - Kanboard EBL"
echo "=================================================="

# Ir para o diretório do projeto
cd /opt/kanboard-ebl 2>/dev/null || {
  echo "Tentando localizar o projeto..."
  cd $(find /home /opt /root -name "docker-compose.yml" 2>/dev/null | grep -i kanboard | head -1 | xargs dirname) 2>/dev/null || {
    echo "ERRO: Projeto não encontrado em /opt/kanboard-ebl"
    echo "Por favor, execute: cd /caminho/do/projeto && bash scripts/reset_senha_admin.sh"
    exit 1
  }
}

echo "Projeto em: $(pwd)"

# Verificar se os containers estão rodando
echo ""
echo "Status dos containers:"
docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E "kanboard|NAME"

# Nova senha
NOVA_SENHA="EBL@Kanboard2026"

echo ""
echo "Gerando hash bcrypt da nova senha..."

# Gerar hash bcrypt via PHP dentro do container da aplicação
HASH=$(docker exec kanboard_app php -r "echo password_hash('${NOVA_SENHA}', PASSWORD_BCRYPT);")
echo "Hash gerado: ${HASH:0:20}..."

echo ""
echo "Atualizando senha no banco de dados PostgreSQL..."

# Atualizar a senha diretamente no banco PostgreSQL
docker exec kanboard_db psql -U kanboard -d kanboard -c \
  "UPDATE users SET password = '${HASH}', api_access_token = '' WHERE username = 'admin';"

echo ""
echo "Verificando atualização..."
docker exec kanboard_db psql -U kanboard -d kanboard -c \
  "SELECT id, username, name, email, role FROM users WHERE username = 'admin';"

echo ""
echo "=================================================="
echo "  SENHA RESETADA COM SUCESSO!"
echo "=================================================="
echo ""
echo "  URL:    http://kanboard.eblsolucoescorp.tec.br"
echo "  Usuário: admin"
echo "  Senha:   ${NOVA_SENHA}"
echo ""
echo "  Após o login, vá em:"
echo "  Perfil > Editar > Alterar senha"
echo "  para definir uma nova senha segura."
echo "=================================================="
