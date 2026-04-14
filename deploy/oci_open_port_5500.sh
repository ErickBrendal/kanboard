#!/bin/bash
# ============================================================
# EBL — Abrir porta 5500 na Security List do OCI
# Execute este script na VM Oracle Cloud como ubuntu
# ============================================================

set -euo pipefail

echo "=== Configurando firewall local (iptables) ==="
# Adicionar regra para porta 5500 TCP
sudo iptables -I INPUT -p tcp --dport 5500 -j ACCEPT
echo "✓ Regra iptables adicionada para porta 5500"

# Persistir regras (Oracle Linux / Ubuntu)
if command -v netfilter-persistent &>/dev/null; then
    sudo netfilter-persistent save
    echo "✓ Regras salvas via netfilter-persistent"
elif [ -f /etc/iptables/rules.v4 ]; then
    sudo iptables-save | sudo tee /etc/iptables/rules.v4 > /dev/null
    echo "✓ Regras salvas em /etc/iptables/rules.v4"
else
    sudo sh -c 'iptables-save > /etc/iptables.rules'
    echo "✓ Regras salvas em /etc/iptables.rules"
fi

echo ""
echo "=== Verificando porta 5500 ==="
ss -tlnp | grep 5500 && echo "✓ Porta 5500 ouvindo" || echo "⚠ Porta 5500 não está ouvindo — inicie o serviço"

echo ""
echo "=== Instruções para Security List do OCI ==="
echo ""
echo "1. Acesse: https://cloud.oracle.com → Networking → Virtual Cloud Networks"
echo "2. Clique na sua VCN → Security Lists → Default Security List"
echo "3. Clique em 'Add Ingress Rules'"
echo "4. Preencha:"
echo "   Source CIDR:  0.0.0.0/0"
echo "   IP Protocol:  TCP"
echo "   Source Port:  All"
echo "   Dest Port:    5500"
echo "   Description:  Kanboard Webhook Server"
echo "5. Clique em 'Add Ingress Rules'"
echo ""
echo "Ou via OCI CLI (se configurado):"
echo "  oci network security-list update \\"
echo "    --security-list-id <SEU_SECURITY_LIST_OCID> \\"
echo "    --ingress-security-rules '[{\"source\":\"0.0.0.0/0\",\"protocol\":\"6\",\"tcpOptions\":{\"destinationPortRange\":{\"min\":5500,\"max\":5500}}}]'"
echo ""
echo "=== Teste após configurar o OCI ==="
echo "  curl http://150.230.88.196:5500/health"
