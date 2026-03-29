#!/bin/bash
# =============================================================
# Script de Correção SSL - Kanboard EBL Soluções Corporativas
# Autor: Manus AI
# Uso: sudo bash fix_ssl.sh
# =============================================================
set -e

DOMAIN="kanboard.eblsolucoescorp.tec.br"
EMAIL="ti@eblsolucoescorp.tec.br"
WORKDIR="/opt/kanboard-ebl"
SMTP_PASSWORD="${1:-ALTERE_SENHA_SMTP}"  # Passe a senha como argumento: sudo bash fix_ssl.sh "SuaSenha"

echo ""
echo "============================================================"
echo "  CORREÇÃO SSL + SMTP - Kanboard EBL"
echo "============================================================"
echo ""

# 1. Verificar se está no diretório correto
if [ ! -f "$WORKDIR/docker-compose.yml" ]; then
    echo "[ERRO] Arquivo docker-compose.yml não encontrado em $WORKDIR"
    echo "Verificando localização alternativa..."
    WORKDIR=$(find / -name "docker-compose.yml" -path "*/kanboard*" 2>/dev/null | head -1 | xargs dirname)
    if [ -z "$WORKDIR" ]; then
        echo "[ERRO FATAL] docker-compose.yml não encontrado. Verifique a instalação."
        exit 1
    fi
    echo "Encontrado em: $WORKDIR"
fi

cd "$WORKDIR"
echo "[OK] Diretório de trabalho: $WORKDIR"

# 2. Verificar status dos containers
echo ""
echo "[1/6] Verificando containers Docker..."
docker compose ps

# 3. Garantir que todos os containers estão rodando
echo ""
echo "[2/6] Reiniciando containers..."
docker compose up -d
sleep 10
echo "[OK] Containers iniciados"

# 4. Verificar se o Nginx está respondendo
echo ""
echo "[3/6] Verificando Nginx..."
if curl -sf --connect-timeout 5 http://localhost/ > /dev/null 2>&1; then
    echo "[OK] Nginx respondendo via HTTP"
else
    echo "[AVISO] Nginx não respondeu localmente, verificando via domínio..."
    curl -sI --connect-timeout 10 http://$DOMAIN/ | head -5
fi

# 5. Solicitar certificado SSL via Certbot
echo ""
echo "[4/6] Solicitando certificado SSL para $DOMAIN..."
docker compose run --rm certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email "$EMAIL" \
    --agree-tos \
    --no-eff-email \
    --force-renewal \
    -d "$DOMAIN" 2>&1

SSL_STATUS=$?

if [ $SSL_STATUS -eq 0 ] && [ -d "/var/lib/docker/volumes/kanboard-ebl_certbot_conf/_data/live/$DOMAIN" ]; then
    echo "[OK] Certificado SSL obtido com sucesso!"
    CERT_OK=true
else
    # Verificar no volume Docker
    CERT_PATH=$(docker run --rm -v kanboard-ebl_certbot_conf:/etc/letsencrypt certbot/certbot ls /etc/letsencrypt/live/ 2>/dev/null)
    if echo "$CERT_PATH" | grep -q "$DOMAIN"; then
        echo "[OK] Certificado SSL encontrado no volume Docker!"
        CERT_OK=true
    else
        echo "[AVISO] Certificado SSL não obtido. Verifique se o DNS está propagado."
        echo "  Execute manualmente: docker compose run --rm certbot certonly --webroot --webroot-path=/var/www/certbot --email $EMAIL --agree-tos --no-eff-email -d $DOMAIN"
        CERT_OK=false
    fi
fi

# 6. Ativar configuração HTTPS no Nginx
if [ "$CERT_OK" = true ]; then
    echo ""
    echo "[5/6] Ativando HTTPS no Nginx..."
    cp nginx/default-ssl.conf nginx/default.conf
    docker compose restart nginx
    sleep 5
    echo "[OK] Nginx reiniciado com HTTPS"

    # Testar HTTPS
    if curl -sf --connect-timeout 10 https://$DOMAIN/ > /dev/null 2>&1; then
        echo "[OK] HTTPS funcionando!"
    else
        echo "[AVISO] HTTPS ainda não respondeu. Aguarde alguns segundos e tente novamente."
    fi
else
    echo ""
    echo "[5/6] HTTPS não ativado (certificado não obtido)"
fi

# 7. Atualizar senha SMTP no config.php
echo ""
echo "[6/6] Atualizando configuração SMTP..."
if [ "$SMTP_PASSWORD" != "ALTERE_SENHA_SMTP" ]; then
    # Atualizar senha no config.php dentro do container
    docker exec kanboard_app sed -i "s/define('MAIL_SMTP_PASSWORD', '.*')/define('MAIL_SMTP_PASSWORD', '$SMTP_PASSWORD')/" /var/www/app/config.php 2>/dev/null || \
    sed -i "s/define('MAIL_SMTP_PASSWORD', '.*')/define('MAIL_SMTP_PASSWORD', '$SMTP_PASSWORD')/" "$WORKDIR/config.php"
    echo "[OK] Senha SMTP atualizada"
    docker compose restart kanboard
else
    echo "[AVISO] Senha SMTP não fornecida. Use: sudo bash fix_ssl.sh 'SuaSenhaSmtp'"
    echo "  Ou edite manualmente: $WORKDIR/config.php"
    echo "  Linha: define('MAIL_SMTP_PASSWORD', 'SUA_SENHA');"
fi

# 8. Resumo final
echo ""
echo "============================================================"
echo "  RESULTADO"
echo "============================================================"
echo ""
docker compose ps
echo ""
if [ "$CERT_OK" = true ]; then
    echo "  URL HTTPS: https://$DOMAIN"
    echo "  [OK] SSL ativo"
else
    echo "  URL HTTP:  http://$DOMAIN"
    echo "  [PENDENTE] SSL - execute o certbot manualmente"
fi
echo ""
echo "  Para gerar o Token de API:"
echo "  1. Acesse o Kanboard"
echo "  2. Clique no seu avatar (canto superior direito)"
echo "  3. Vá em 'Perfil' > 'API'"
echo "  4. Clique em 'Gerar novo token'"
echo ""
echo "============================================================"
echo "  CONCLUÍDO!"
echo "============================================================"
