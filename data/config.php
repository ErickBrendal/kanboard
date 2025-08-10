<?php
/**
 * Configuração do Kanboard para rodar no Heroku.
 * Coloque este arquivo no caminho: data/config.php
 * Este arquivo lê as credenciais do banco a partir da variável DATABASE_URL do Heroku Postgres.
 */

// Se existir DATABASE_URL (padrão do Heroku), usamos ela:
$databaseUrl = getenv('DATABASE_URL');

if ($databaseUrl) {
    $db = parse_url($databaseUrl);
    // Ex.: postgres://usuario:senha@host:5432/banco
    define('DB_DRIVER', 'postgres');
    define('DB_HOSTNAME', $db['host']);
    define('DB_PORT', isset($db['port']) ? $db['port'] : '5432');
    define('DB_USERNAME', $db['user']);
    define('DB_PASSWORD', $db['pass']);
    define('DB_NAME', ltrim($db['path'], '/'));
} else {
    // Fallback (não recomendado para Heroku, apenas para testes locais)
    define('DB_DRIVER', getenv('DB_DRIVER') ?: 'sqlite');
    define('DB_NAME', getenv('DB_NAME') ?: 'data/db.sqlite');
}

// (Opcional) Habilita instalador de plugins pela interface
define('PLUGIN_INSTALLER', true);

// (Opcional) URLs amigáveis (pode exigir ajustes no .htaccess)
# define('ENABLE_URL_REWRITE', true);
