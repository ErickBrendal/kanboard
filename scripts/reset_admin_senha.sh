#!/bin/bash
# Reset da senha do admin para EBL@Kanboard2026
# Executar no servidor Oracle Cloud

HASH='$2y$10$EBLKanboard2026HashXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'

echo "=== Gerando hash bcrypt da senha ==="
# Usar PHP para gerar hash compatível com Kanboard (usa $2y$ não $2b$)
HASH=$(docker exec kanboard_app php -r "echo password_hash('EBL@Kanboard2026', PASSWORD_BCRYPT, ['cost'=>10]);")
echo "Hash gerado: $HASH"

echo ""
echo "=== Atualizando senha no banco de dados ==="
docker exec kanboard_db psql -U kanboard -d kanboard -c "
UPDATE users 
SET password = '$HASH', 
    nb_failed_login = 0, 
    lock_expiration_date = 0 
WHERE username = 'admin';
"

echo ""
echo "=== Verificando resultado ==="
docker exec kanboard_db psql -U kanboard -d kanboard -c "
SELECT id, username, nb_failed_login, lock_expiration_date FROM users WHERE username = 'admin';
"

echo ""
echo "=== CONCLUIDO: Senha do admin resetada para EBL@Kanboard2026 ==="
