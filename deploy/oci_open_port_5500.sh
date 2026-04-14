#!/bin/bash
# ============================================================
# EBL — Abrir porta 5500 na Security List do OCI
# Versão: 2.0 — Totalmente automatizado
#
# Funcionalidades:
#   1. Configura o firewall local (iptables/ufw)
#   2. Detecta automaticamente o OCID da Security List
#      via OCI Instance Metadata Service (IMDS)
#   3. Adiciona a regra de ingresso TCP 5500 via OCI CLI
#   4. Valida a abertura da porta externamente
#
# Pré-requisitos (apenas para etapa OCI CLI):
#   - OCI CLI instalado: https://docs.oracle.com/en-us/iaas/Content/API/SDKDocs/cliinstall.htm
#   - OCI CLI configurado: oci setup config
#
# Uso:
#   chmod +x oci_open_port_5500.sh
#   ./oci_open_port_5500.sh
#
# Para pular a etapa OCI CLI (somente firewall local):
#   ./oci_open_port_5500.sh --local-only
# ============================================================

set -euo pipefail

# ── Cores para output ──────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# ── Configurações ──────────────────────────────────────────
PORT=5500
PROTOCOL="TCP"
SOURCE_CIDR="0.0.0.0/0"
DESCRIPTION="EBL Kanboard Webhook Server"
LOCAL_ONLY=false

# ── Processar argumentos ───────────────────────────────────
for arg in "$@"; do
    case $arg in
        --local-only) LOCAL_ONLY=true ;;
        --help|-h)
            echo "Uso: $0 [--local-only] [--help]"
            echo "  --local-only   Configura apenas o firewall local (sem OCI CLI)"
            exit 0
            ;;
    esac
done

# ── Banner ─────────────────────────────────────────────────
echo -e "${BOLD}${BLUE}"
echo "╔══════════════════════════════════════════════════════╗"
echo "║   EBL — Abertura de Porta 5500 no OCI               ║"
echo "║   Kanboard Webhook Server                            ║"
echo "╚══════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ══════════════════════════════════════════════════════════
# ETAPA 1 — Firewall local (iptables / ufw)
# ══════════════════════════════════════════════════════════
echo -e "${CYAN}${BOLD}[1/4] Configurando firewall local...${NC}"

# Verificar se a regra já existe
if sudo iptables -C INPUT -p tcp --dport ${PORT} -j ACCEPT 2>/dev/null; then
    echo -e "${GREEN}✓ Regra iptables para porta ${PORT} já existe${NC}"
else
    sudo iptables -I INPUT -p tcp --dport ${PORT} -j ACCEPT
    echo -e "${GREEN}✓ Regra iptables adicionada: TCP porta ${PORT} ACCEPT${NC}"
fi

# Persistir regras
if command -v netfilter-persistent &>/dev/null; then
    sudo netfilter-persistent save 2>/dev/null
    echo -e "${GREEN}✓ Regras persistidas via netfilter-persistent${NC}"
elif command -v ufw &>/dev/null && sudo ufw status | grep -q "active"; then
    sudo ufw allow ${PORT}/tcp comment "${DESCRIPTION}" 2>/dev/null
    echo -e "${GREEN}✓ Regra UFW adicionada para porta ${PORT}${NC}"
elif [ -d /etc/iptables ]; then
    sudo iptables-save | sudo tee /etc/iptables/rules.v4 > /dev/null
    echo -e "${GREEN}✓ Regras salvas em /etc/iptables/rules.v4${NC}"
else
    sudo sh -c "iptables-save > /etc/iptables.rules"
    echo -e "${GREEN}✓ Regras salvas em /etc/iptables.rules${NC}"
fi

# ══════════════════════════════════════════════════════════
# ETAPA 2 — Detectar metadados da instância OCI via IMDS
# ══════════════════════════════════════════════════════════
echo ""
echo -e "${CYAN}${BOLD}[2/4] Detectando metadados da instância OCI...${NC}"

INSTANCE_ID=""
COMPARTMENT_ID=""
REGION=""
PUBLIC_IP=""

# OCI Instance Metadata Service (IMDS) v2
IMDS_TOKEN=$(curl -sf --connect-timeout 3 \
    -H "Authorization: Bearer Oracle" \
    "http://169.254.169.254/opc/v2/instance/" 2>/dev/null | \
    python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('id',''))" 2>/dev/null || echo "")

if [ -n "$IMDS_TOKEN" ]; then
    INSTANCE_ID="$IMDS_TOKEN"
    COMPARTMENT_ID=$(curl -sf --connect-timeout 3 \
        -H "Authorization: Bearer Oracle" \
        "http://169.254.169.254/opc/v2/instance/" 2>/dev/null | \
        python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('compartmentId',''))" 2>/dev/null || echo "")
    REGION=$(curl -sf --connect-timeout 3 \
        -H "Authorization: Bearer Oracle" \
        "http://169.254.169.254/opc/v2/instance/" 2>/dev/null | \
        python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('regionInfo',{}).get('regionIdentifier',''))" 2>/dev/null || echo "")
    PUBLIC_IP=$(curl -sf --connect-timeout 3 \
        "http://169.254.169.254/opc/v2/vnics/" 2>/dev/null | \
        python3 -c "import sys,json; d=json.load(sys.stdin); print(d[0].get('publicIp','') if d else '')" 2>/dev/null || echo "")
    echo -e "${GREEN}✓ Instância detectada via IMDS${NC}"
    echo -e "  Instance ID:    ${INSTANCE_ID:0:30}..."
    echo -e "  Compartment ID: ${COMPARTMENT_ID:0:30}..."
    echo -e "  Região:         ${REGION}"
    echo -e "  IP Público:     ${PUBLIC_IP:-150.230.88.196}"
else
    echo -e "${YELLOW}⚠ IMDS não disponível (script rodando fora da VM OCI)${NC}"
    echo -e "  Usando valores padrão do projeto EBL"
    PUBLIC_IP="150.230.88.196"
fi

# ══════════════════════════════════════════════════════════
# ETAPA 3 — Abrir porta na Security List via OCI CLI
# ══════════════════════════════════════════════════════════
echo ""
echo -e "${CYAN}${BOLD}[3/4] Configurando Security List do OCI...${NC}"

if [ "$LOCAL_ONLY" = true ]; then
    echo -e "${YELLOW}⚠ Modo --local-only: etapa OCI CLI ignorada${NC}"
elif ! command -v oci &>/dev/null; then
    echo -e "${YELLOW}⚠ OCI CLI não encontrado. Instalando...${NC}"
    bash -c "$(curl -L https://raw.githubusercontent.com/oracle/oci-cli/master/scripts/install/install.sh)" \
        -- --accept-all-defaults 2>/dev/null && \
        export PATH="$HOME/bin:$PATH" && \
        echo -e "${GREEN}✓ OCI CLI instalado${NC}" || \
        echo -e "${RED}✗ Falha ao instalar OCI CLI — siga as instruções manuais abaixo${NC}"
fi

if command -v oci &>/dev/null && [ "$LOCAL_ONLY" = false ]; then
    # Verificar se OCI CLI está configurado
    if ! oci iam region list &>/dev/null 2>&1; then
        echo -e "${YELLOW}⚠ OCI CLI não configurado. Execute: oci setup config${NC}"
        OCI_CONFIGURED=false
    else
        OCI_CONFIGURED=true
        echo -e "${GREEN}✓ OCI CLI configurado e autenticado${NC}"
    fi

    if [ "$OCI_CONFIGURED" = true ]; then
        # Descobrir Security List automaticamente
        echo "  Buscando Security Lists na VCN..."

        # Listar VCNs no compartimento
        VCN_ID=$(oci network vcn list \
            --compartment-id "${COMPARTMENT_ID}" \
            --query 'data[0].id' \
            --raw-output 2>/dev/null || echo "")

        if [ -n "$VCN_ID" ]; then
            echo -e "  VCN ID: ${VCN_ID:0:40}..."

            # Listar Security Lists da VCN
            SECURITY_LIST_ID=$(oci network security-list list \
                --compartment-id "${COMPARTMENT_ID}" \
                --vcn-id "${VCN_ID}" \
                --query 'data[0].id' \
                --raw-output 2>/dev/null || echo "")

            if [ -n "$SECURITY_LIST_ID" ]; then
                echo -e "  Security List ID: ${SECURITY_LIST_ID:0:40}..."

                # Obter regras de ingresso atuais
                CURRENT_RULES=$(oci network security-list get \
                    --security-list-id "${SECURITY_LIST_ID}" \
                    --query 'data."ingress-security-rules"' \
                    2>/dev/null || echo "[]")

                # Verificar se a regra para porta 5500 já existe
                if echo "${CURRENT_RULES}" | python3 -c "
import sys, json
rules = json.load(sys.stdin)
exists = any(
    r.get('protocol') == '6' and
    r.get('tcp-options', {}).get('destination-port-range', {}).get('min') == 5500
    for r in rules
)
sys.exit(0 if exists else 1)
" 2>/dev/null; then
                    echo -e "${GREEN}✓ Regra TCP 5500 já existe na Security List${NC}"
                else
                    # Construir nova lista de regras com a porta 5500 adicionada
                    NEW_RULES=$(echo "${CURRENT_RULES}" | python3 -c "
import sys, json
rules = json.load(sys.stdin)
new_rule = {
    'source': '0.0.0.0/0',
    'protocol': '6',
    'isStateless': False,
    'description': 'EBL Kanboard Webhook Server',
    'tcpOptions': {
        'destinationPortRange': {'min': 5500, 'max': 5500}
    }
}
rules.append(new_rule)
print(json.dumps(rules))
")
                    # Aplicar as novas regras
                    oci network security-list update \
                        --security-list-id "${SECURITY_LIST_ID}" \
                        --ingress-security-rules "${NEW_RULES}" \
                        --force \
                        2>/dev/null && \
                        echo -e "${GREEN}✓ Regra TCP ${PORT} adicionada à Security List com sucesso!${NC}" || \
                        echo -e "${RED}✗ Falha ao atualizar Security List — verifique permissões IAM${NC}"
                fi
            else
                echo -e "${YELLOW}⚠ Security List não encontrada automaticamente${NC}"
            fi
        else
            echo -e "${YELLOW}⚠ VCN não encontrada — verifique o Compartment ID${NC}"
        fi
    fi
else
    echo -e "${YELLOW}⚠ OCI CLI não disponível. Siga as instruções manuais abaixo.${NC}"
fi

# ══════════════════════════════════════════════════════════
# ETAPA 4 — Validação
# ══════════════════════════════════════════════════════════
echo ""
echo -e "${CYAN}${BOLD}[4/4] Validando configuração...${NC}"

# Verificar se a porta está ouvindo localmente
if ss -tlnp 2>/dev/null | grep -q ":${PORT}" || \
   netstat -tlnp 2>/dev/null | grep -q ":${PORT}"; then
    echo -e "${GREEN}✓ Porta ${PORT} ouvindo localmente (serviço ativo)${NC}"
else
    echo -e "${YELLOW}⚠ Porta ${PORT} não está ouvindo — inicie o serviço:${NC}"
    echo -e "  sudo systemctl start kanboard-webhook"
fi

# Teste de conectividade local
if curl -sf --connect-timeout 3 "http://localhost:${PORT}/health" | \
   python3 -c "import sys,json; d=json.load(sys.stdin); print('✓ Health:', d['status'])" 2>/dev/null; then
    echo -e "${GREEN}✓ Health check local OK${NC}"
else
    echo -e "${YELLOW}⚠ Health check local falhou — serviço pode não estar rodando${NC}"
fi

# ══════════════════════════════════════════════════════════
# Instruções manuais (sempre exibidas como referência)
# ══════════════════════════════════════════════════════════
echo ""
echo -e "${BOLD}════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}  Instruções Manuais — OCI Console${NC}"
echo -e "${BOLD}════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  1. Acesse: ${BLUE}https://cloud.oracle.com${NC}"
echo -e "  2. Navegue: ${CYAN}Networking → Virtual Cloud Networks → sua VCN${NC}"
echo -e "  3. Clique: ${CYAN}Security Lists → Default Security List${NC}"
echo -e "  4. Clique: ${CYAN}Add Ingress Rules${NC}"
echo -e "  5. Preencha:"
echo -e "     ${YELLOW}Source CIDR:   0.0.0.0/0${NC}"
echo -e "     ${YELLOW}IP Protocol:   TCP${NC}"
echo -e "     ${YELLOW}Source Port:   All${NC}"
echo -e "     ${YELLOW}Dest Port:     5500${NC}"
echo -e "     ${YELLOW}Description:   ${DESCRIPTION}${NC}"
echo -e "  6. Clique: ${CYAN}Add Ingress Rules${NC}"
echo ""
echo -e "${BOLD}  Ou via OCI CLI (com Security List OCID):${NC}"
echo ""
echo -e "  ${CYAN}oci network security-list update \\${NC}"
echo -e "  ${CYAN}  --security-list-id <OCID_DA_SECURITY_LIST> \\${NC}"
echo -e "  ${CYAN}  --ingress-security-rules '[{${NC}"
echo -e "  ${CYAN}    \"source\":\"0.0.0.0/0\",${NC}"
echo -e "  ${CYAN}    \"protocol\":\"6\",${NC}"
echo -e "  ${CYAN}    \"isStateless\":false,${NC}"
echo -e "  ${CYAN}    \"description\":\"${DESCRIPTION}\",${NC}"
echo -e "  ${CYAN}    \"tcpOptions\":{\"destinationPortRange\":{\"min\":5500,\"max\":5500}}${NC}"
echo -e "  ${CYAN}  }]' --force${NC}"
echo ""
echo -e "${BOLD}  Teste externo após configurar o OCI:${NC}"
echo -e "  ${CYAN}curl http://${PUBLIC_IP:-150.230.88.196}:${PORT}/health${NC}"
echo ""
echo -e "${BOLD}════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${GREEN}${BOLD}Script concluído!${NC}"
