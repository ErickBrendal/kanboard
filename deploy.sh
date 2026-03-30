#!/bin/bash
# Script de Deploy Automatizado - Kanboard EBL Soluções Corporativas
# Autor: Manus AI
# Uso: sudo bash deploy.sh

set -e

echo "=== Iniciando Deploy Kanboard EBL ==="

# 1. Preparar o servidor
echo "1/7 Atualizando sistema e instalando dependências..."
apt update && apt upgrade -y
apt install -y curl python3-pip python3-venv fail2ban netfilter-persistent

# 2. Instalar Docker
if ! command -v docker &> /dev/null; then
    echo "Instalando Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker && systemctl start docker
fi

# 3. Configurar Firewall
echo "2/7 Configurando Firewall..."

# Oracle Cloud iptables
iptables -A INPUT -p tcp --dport 80 -j ACCEPT
iptables -A INPUT -p tcp --dport 443 -j ACCEPT
netfilter-persistent save

# 4. Preparar estrutura e .env
echo "3/7 Preparando ambiente..."
mkdir -p /home/ubuntu/kanboard/{nginx,css,sql,scripts,logs,backups}


if [ ! -f .env ]; then
    DB_PASS=$(openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 24)
    DOMAIN="kanboard.eblsolucoescorp.tec.br"
    echo "DB_PASSWORD=$DB_PASS" > /home/ubuntu/kanboard/.env
    echo "DOMAIN=$DOMAIN" >> /home/ubuntu/kanboard/.env
    echo "SSL_EMAIL=ti@eblsolucoescorp.tec.br" >> /home/ubuntu/kanboard/.env
    echo "KANBOARD_URL=https://${DOMAIN}/jsonrpc.php" >> /home/ubuntu/kanboard/.env

    # Gerar config.php dinamicamente para evitar conflitos
    cat > /home/ubuntu/kanboard/config.php << EOF
<?php
define(\'DB_DRIVER\', \'postgres\');
define(\'DB_USERNAME\', \'kanboard\');
// Usar a senha gerada diretamente
define(\'DB_PASSWORD\', \'${DB_PASS}\');
define(\'DB_HOSTNAME\', \'db\');
define(\'DB_PORT\', \'5432\');
define(\'DB_NAME\', \'kanboard\');
define(\'DATA_DIR\', __DIR__ . \'/data\');
define(\'APP_NAME\', \'EBL Kanboard\');
define(\'APP_BASE_URL\', \'https://${DOMAIN}/\');
define(\'APP_TIMEZONE\', \'America/Sao_Paulo\');
define(\'APP_LANGUAGE\', \'pt_BR\');
define(\'ENABLE_HSTS\', true);
define(\'ENABLE_XFRAME\', true);
define(\'ENABLE_URL_REWRITE\', true);
define(\'SESSION_DURATION\', 0);
define(\'REMEMBER_ME_AUTH\', true);
define(\'SESSION_HANDLER\', \'db\');
define(\'BRUTEFORCE_CAPTCHA\', 3);
define(\'BRUTEFORCE_LOCKDOWN\', 6);
define(\'BRUTEFORCE_LOCKDOWN_DURATION\', 15);
define(\'API_AUTHENTICATION_HEADER\', \'X-API-Auth\');
define(\'MAIL_TRANSPORT\', \'smtp\');
define(\'MAIL_SMTP_HOSTNAME\', \'smtp.eblsolucoescorp.tec.br\');
define(\'MAIL_SMTP_PORT\', 587);
define(\'MAIL_SMTP_ENCRYPTION\', \'tls\');
define(\'MAIL_SMTP_USERNAME\', \'kanboard@eblsolucoescorp.tec.br\');
define(\'MAIL_SMTP_PASSWORD\', \'ALTERE_SENHA_SMTP\');
define(\'MAIL_FROM\', \'kanboard@eblsolucoescorp.tec.br\');
define(\'LOG_DRIVER\', \'file\');
define(\'LOG_FILE\', DATA_DIR.\'/debug.log\');
define(\'PLUGIN_API_URL\', \'https://kanboard.org/plugin/list.json\');
define(\'PLUGIN_INSTALLER\', true);
define(\'WEBHOOK_URL_BASE_URL\', \'https://${DOMAIN}/\');
EOF

    echo "SENHA DO BANCO GERADA: $DB_PASS"
    echo "ANOTE ESTA SENHA!"
fi

# 5. Subir Containers
echo "4/7 Subindo containers (HTTP)..docker compose -f /home/ubuntu/kanboard/docker-compose.yml up -d
sleep 15

# 6. SSL
echo "5/7 Solicitando certificado SSL..."
docker compose run --rm certbot certonly \
    --webroot --webroot-path=/var/www/certbot \
    --email ti@eblsolucoescorp.tec.br \
    --agree-tos --no-eff-email \
    -d kanboard.eblsolucoescorp.tec.br || echo "Aviso: Falha no SSL. Verifique o DNS e tente novamente."

if [ -d "/etc/letsencrypt/live/kanboard.eblsolucoescorp.tec.br" ]; then
    cp nginx/default-ssl.conf nginx/default.conf
    docker compose restart nginx
    echo "SSL ativado com sucesso!"
fi

# 7. Python Venv
echo "6/7 Configurando ambiente Python para ETL..."
python3 -m venv /home/ubuntu/kanboard/venv
/home/ubuntu/kanboard/venv/bin/pip install requests psycopg2-binary
echo "7/7 Configurando agendamentos (Cron)..."
cat > /etc/cron.d/kanboard-ebl << 'EOF'
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin

# Backup diário às 02:00
0 2 * * * root /home/ubuntu/kanboard/scripts/backup.sh >> /home/ubuntu/kanboard/logs/backup.log 2>&1

# ETL a cada 15 minutos
*/15 * * * * root /home/ubuntu/kanboard/venv/bin/python /home/ubuntu/kanboard/scripts/etl_kanboard.py 2>&1

# Renovação SSL
0 0,12 * * * root cd /home/ubuntu/kanboard && docker compose run --rm certbot renew --quiet && docker compose restart nginx
chmod +x /home/ubuntu/kanboard/scripts/*.sh

echo "=== Deploy Concluído! ==="
echo "Acesse: https://kanboard.eblsolucoescorp.tec.br"
echo "Login inicial: admin / admin"
echo "Após o login, gere o API Token e execute o script de setup dos boards."
