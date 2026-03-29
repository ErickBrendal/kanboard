<?php
/**
 * RESET DE SENHA DO ADMIN - USO ÚNICO
 * Remover após uso!
 */

// Verificar se é uma requisição legítima
$secret = $_GET['secret'] ?? '';
if ($secret !== 'EBL2026reset') {
    http_response_code(403);
    die('Acesso negado');
}

$nova_senha = 'EBL@Kanboard2026';
$hash = password_hash($nova_senha, PASSWORD_BCRYPT);

// Tentar conectar ao banco
try {
    // Carregar configurações do Kanboard
    $config_file = __DIR__ . '/config.php';
    if (!file_exists($config_file)) {
        $config_file = '/var/www/app/config.php';
    }
    
    if (file_exists($config_file)) {
        require_once $config_file;
    }
    
    // Tentar conexão PostgreSQL
    $dsn = sprintf(
        'pgsql:host=%s;port=%s;dbname=%s',
        defined('DB_HOSTNAME') ? DB_HOSTNAME : 'db',
        defined('DB_PORT') ? DB_PORT : '5432',
        defined('DB_NAME') ? DB_NAME : 'kanboard'
    );
    
    $pdo = new PDO(
        $dsn,
        defined('DB_USERNAME') ? DB_USERNAME : 'kanboard',
        defined('DB_PASSWORD') ? DB_PASSWORD : 'kanboard',
        [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]
    );
    
    $stmt = $pdo->prepare("UPDATE users SET password = ? WHERE username = 'admin'");
    $stmt->execute([$hash]);
    
    $affected = $stmt->rowCount();
    
    echo "<h1>Reset de Senha</h1>";
    echo "<p>Linhas afetadas: $affected</p>";
    echo "<p>Nova senha: <strong>$nova_senha</strong></p>";
    echo "<p>Hash: $hash</p>";
    echo "<p><strong>REMOVA ESTE ARQUIVO IMEDIATAMENTE!</strong></p>";
    echo "<p><a href='/login'>Ir para o login</a></p>";
    
} catch (Exception $e) {
    echo "<h1>Erro</h1>";
    echo "<p>" . htmlspecialchars($e->getMessage()) . "</p>";
    echo "<p>Hash gerado: $hash</p>";
    echo "<p>Use este hash para atualizar manualmente no banco:</p>";
    echo "<code>UPDATE users SET password = '$hash' WHERE username = 'admin';</code>";
}
