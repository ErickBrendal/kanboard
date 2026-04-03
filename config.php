<?php
define('DB_DRIVER', 'postgres');
define('DB_USERNAME', 'kanboard');
define('DB_PASSWORD', getenv('DATABASE_URL') ? parse_url(getenv('DATABASE_URL'))['pass'] : 'DB_PASSWORD_PLACEHOLDER');
define('DB_HOSTNAME', getenv('DATABASE_URL') ? parse_url(getenv('DATABASE_URL'))['host'] : 'db');
define('DB_PORT', '5432');
define('DB_NAME', 'kanboard');

define('APP_NAME', 'EBL Kanboard');
define('APP_BASE_URL', 'http://kanboard.eblsolucoescorp.tec.br/'); // FIX: temporario ate SSL ser renovado
define('APP_TIMEZONE', 'America/Sao_Paulo');
define('APP_LANGUAGE', 'pt_BR');

define('ENABLE_HSTS', false); // FIX: desabilitado - reativar apos certificado SSL valido
define('ENABLE_XFRAME', true);
define('ENABLE_URL_REWRITE', true);
define('SESSION_DURATION', 0);
define('REMEMBER_ME_AUTH', true);
define('SESSION_HANDLER', 'db');

define('BRUTEFORCE_CAPTCHA', 3);
define('BRUTEFORCE_LOCKDOWN', 6);
define('BRUTEFORCE_LOCKDOWN_DURATION', 15);

define('API_AUTHENTICATION_HEADER', 'X-API-Auth');

define('MAIL_TRANSPORT', 'smtp');
define('MAIL_SMTP_HOSTNAME', 'smtp.eblsolucoescorp.tec.br');
define('MAIL_SMTP_PORT', 587);
define('MAIL_SMTP_ENCRYPTION', 'tls');
define('MAIL_SMTP_USERNAME', 'kanboard@eblsolucoescorp.tec.br');
define('MAIL_SMTP_PASSWORD', 'ALTERE_SENHA_SMTP');
define('MAIL_FROM', 'kanboard@eblsolucoescorp.tec.br');

define('LOG_DRIVER', 'file');
define('LOG_FILE', DATA_DIR.'/debug.log');

define('PLUGIN_API_URL', 'https://kanboard.org/plugin/list.json');
define('PLUGIN_INSTALLER', true);

define('WEBHOOK_URL_BASE_URL', 'https://kanboard.eblsolucoescorp.tec.br/');
