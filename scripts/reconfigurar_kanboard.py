#!/usr/bin/env python3
"""
EBL Kanboard — Reconfiguração Completa do Projeto CRM Salesforce
Versão: 1.0 | 2026-04-07

Operações:
  1. Reordenar colunas: Ideação/POC > Novo > Backlog > Análise TI > Planejamento >
     Pendente Aprovação > Em Desenvolvimento > Testes > Hypercare > Concluído > On Hold > Cancelado
  2. Renomear colunas para nomes padronizados
  3. Criar campos customizados do Excel (via plugin CustomFields ou via descrição estruturada)
  4. Atualizar powerbi_config.json com novo mapeamento
"""

import requests
import json
import time
from datetime import datetime
from pathlib import Path

# ===== CONFIGURAÇÕES =====
TOKEN      = "ea99d4c7d96dbad1b1a1defd79f92286884e1902015ff96731ce624e6317"
URL        = "http://kanboard.eblsolucoescorp.tec.br/jsonrpc.php"
AUTH       = ("jsonrpc", TOKEN)
PROJECT_ID = 1  # CRM Salesforce
BASE_DIR   = Path(__file__).parent.parent

_req_id = 0

def log(msg, level="INFO"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [{level}] {msg}")

def api(method, params=None):
    global _req_id
    _req_id += 1
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "id": _req_id,
        "params": params or {}
    }
    r = requests.post(URL, json=payload, auth=AUTH, timeout=15)
    resp = r.json()
    if "error" in resp:
        log(f"  API erro em {method}: {resp['error']}", "WARN")
        return None
    return resp.get("result")

def api_raw(method, params=None):
    """Retorna resposta completa incluindo erros"""
    global _req_id
    _req_id += 1
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "id": _req_id,
        "params": params or {}
    }
    r = requests.post(URL, json=payload, auth=AUTH, timeout=15)
    return r.json()

# ===== NOVA SEQUÊNCIA DE COLUNAS =====
# Formato: (nome_atual_ou_novo, nova_posição, descrição)
NOVA_SEQUENCIA = [
    ("Ideação / POC",       1,  "Em fase de ideação ou prova de conceito"),
    ("Novo",                2,  "Novas demandas registradas"),
    ("Backlog",             3,  "Demandas aguardando priorização"),
    ("Análise TI",          4,  "Em análise pela equipe de TI"),
    ("Planejamento",        5,  "Em planejamento e estimativa de esforço"),
    ("Pendente Aprovação",  6,  "Aguardando aprovação de diretoria ou ROI"),
    ("Em Desenvolvimento",  7,  "Em desenvolvimento ativo"),
    ("Testes",              8,  "Em testes unitários e integrados"),
    ("Hypercare",           9,  "Em hypercare / acompanhamento pós-deploy"),
    ("Concluído",           10, "Demanda concluída e publicada em produção"),
    ("On Hold",             11, "Em espera ou com impedimento"),
    ("Cancelado",           12, "Demanda cancelada"),
]

# Mapeamento de nomes antigos → novos
RENAME_MAP = {
    "Testes / Homologação":  "Testes",
    "Hypercare / Deploy":    "Hypercare",
    "On Hold / Impedimento": "On Hold",
    "Concluído":             "Concluído",  # sem alteração
}

# ===== CAMPOS CUSTOMIZADOS DO EXCEL =====
# Kanboard suporta campos customizados via plugin CustomFields
# Tipos: text, integer, date, list, url, email
CUSTOM_FIELDS = [
    {"name": "Subcategoria",              "field_type": "text",    "description": "Subcategoria do projeto (ex: CRM Salesforce, Integração)"},
    {"name": "Área Negócio",              "field_type": "text",    "description": "Área de negócio solicitante (ex: eCommerce, Financeiro)"},
    {"name": "Classificação Risco",       "field_type": "list",    "description": "Nível de risco: Baixo, Médio, Alto, Crítico",
     "values": "Baixo,Médio,Alto,Crítico"},
    {"name": "Data GoLive Estimada",      "field_type": "date",    "description": "Nova data estimada de Go-Live"},
    {"name": "Data Início Planejado",     "field_type": "date",    "description": "Data de início planejada do projeto"},
    {"name": "Data Fim Planejado",        "field_type": "date",    "description": "Data de fim planejada do projeto"},
    {"name": "% Evolução Planejado",      "field_type": "integer", "description": "Percentual de evolução planejado (0-100)"},
    {"name": "% Evolução Realizado",      "field_type": "integer", "description": "Percentual de evolução realizado (0-100)"},
    {"name": "Desvio %",                  "field_type": "integer", "description": "Desvio entre planejado e realizado (%)"},
    {"name": "Recurso",                   "field_type": "list",    "description": "Tipo de recurso: Interno, Externo, Misto",
     "values": "Interno,Externo,Misto"},
    {"name": "Custo Planejado",           "field_type": "integer", "description": "Custo planejado em R$"},
    {"name": "Custo Realizado",           "field_type": "integer", "description": "Custo realizado em R$"},
    {"name": "ROI Aprovado",              "field_type": "list",    "description": "ROI aprovado: Sim, Não, Qualitativo",
     "values": "Sim,Não,Qualitativo,N/A"},
    {"name": "Valor ROI",                 "field_type": "integer", "description": "Valor do ROI em R$ (se aplicável)"},
]

def step1_reorder_columns():
    """Etapa 1: Reordenar e renomear colunas"""
    log("=" * 60)
    log("ETAPA 1: Reordenando e renomeando colunas...")
    log("=" * 60)

    # Obter colunas atuais
    cols = api("getColumns", {"project_id": PROJECT_ID})
    if not cols:
        log("Erro ao obter colunas", "ERROR")
        return False

    log(f"Colunas atuais ({len(cols)}):")
    col_by_name = {}
    col_by_id = {}
    for c in cols:
        log(f"  ID={c['id']} pos={c['position']} nome='{c['title']}'")
        col_by_name[c['title']] = c
        col_by_id[c['id']] = c

    log("")
    log("Aplicando nova sequência...")

    # Para cada coluna na nova sequência, atualizar posição e nome
    for new_name, new_pos, new_desc in NOVA_SEQUENCIA:
        # Encontrar a coluna pelo nome atual (pode ter nome diferente)
        old_name = new_name
        for old, new in RENAME_MAP.items():
            if new == new_name:
                old_name = old
                break

        col = col_by_name.get(new_name) or col_by_name.get(old_name)

        if col:
            col_id = col['id']
            # Atualizar posição e nome
            result = api("updateColumn", {
                "column_id": col_id,
                "title": new_name,
                "task_limit": col.get('task_limit', 0),
                "description": new_desc,
                "position": new_pos
            })
            if result:
                renamed = f" (renomeado de '{old_name}')" if old_name != new_name else ""
                log(f"  ✓ '{new_name}' → posição {new_pos}{renamed}")
            else:
                log(f"  ✗ Falha ao atualizar '{new_name}'", "WARN")
        else:
            # Criar nova coluna se não existir
            log(f"  + Criando coluna '{new_name}' na posição {new_pos}...")
            result = api("addColumn", {
                "project_id": PROJECT_ID,
                "title": new_name,
                "task_limit": 0,
                "description": new_desc
            })
            if result:
                log(f"  ✓ Coluna '{new_name}' criada (ID={result})")
            else:
                log(f"  ✗ Falha ao criar '{new_name}'", "WARN")

        time.sleep(0.3)

    # Verificar resultado
    log("")
    cols_after = api("getColumns", {"project_id": PROJECT_ID})
    log(f"Colunas após reordenação ({len(cols_after or [])}):")
    for c in sorted(cols_after or [], key=lambda x: x['position']):
        log(f"  pos={c['position']} ID={c['id']} nome='{c['title']}'")

    return True

def step2_create_custom_fields():
    """Etapa 2: Criar campos customizados via plugin"""
    log("")
    log("=" * 60)
    log("ETAPA 2: Criando campos customizados...")
    log("=" * 60)

    # Verificar se o plugin CustomFields está disponível
    test = api_raw("getProjectCustomFields", {"project_id": PROJECT_ID})
    if "error" in test and test["error"].get("code") == -32601:
        log("Plugin CustomFields não está instalado no servidor.", "WARN")
        log("Os campos serão registrados no powerbi_config.json para uso no sync.", "WARN")
        log("Para instalar o plugin, acesse: Kanboard > Configurações > Plugins > CustomFields", "INFO")
        return False, "plugin_not_installed"

    # Plugin disponível - criar campos
    existing = api("getProjectCustomFields", {"project_id": PROJECT_ID}) or []
    existing_names = {f['name'] for f in existing}
    log(f"Campos existentes: {len(existing)}")

    created = 0
    for field in CUSTOM_FIELDS:
        if field['name'] in existing_names:
            log(f"  → '{field['name']}' já existe, pulando")
            continue

        params = {
            "project_id": PROJECT_ID,
            "field_type": field['field_type'],
            "name": field['name'],
            "description": field.get('description', ''),
        }
        if field.get('values'):
            params['values'] = field['values']

        result = api("createProjectCustomField", params)
        if result:
            log(f"  ✓ Campo '{field['name']}' criado (tipo={field['field_type']})")
            created += 1
        else:
            log(f"  ✗ Falha ao criar '{field['name']}'", "WARN")
        time.sleep(0.2)

    log(f"Campos criados: {created}/{len(CUSTOM_FIELDS)}")
    return True, "success"

def step3_update_config():
    """Etapa 3: Atualizar powerbi_config.json com novo mapeamento"""
    log("")
    log("=" * 60)
    log("ETAPA 3: Atualizando configuração de mapeamento...")
    log("=" * 60)

    # Obter colunas atualizadas
    cols = api("getColumns", {"project_id": PROJECT_ID}) or []
    col_map = {str(c['id']): c['title'] for c in cols}

    # Novo mapeamento de fases para o Power BI
    phase_map = {}
    for c in cols:
        pos = c['position']
        name = c['title']
        phase_map[name] = f"{pos:02d}. {name}"

    # Carregar config existente
    config_path = BASE_DIR / "powerbi" / "powerbi_config.json"
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except:
        config = {}

    # Atualizar mapeamento de colunas
    if 'kanboard_powerbi_config' not in config:
        config['kanboard_powerbi_config'] = {}

    config['kanboard_powerbi_config']['mapeamento_colunas'] = col_map
    config['kanboard_powerbi_config']['mapeamento_fases'] = phase_map
    config['kanboard_powerbi_config']['campos_customizados'] = [f['name'] for f in CUSTOM_FIELDS]
    config['kanboard_powerbi_config']['ultima_reconfig'] = datetime.now().isoformat()
    config['kanboard_powerbi_config']['conexao'] = {
        "url_api": URL,
        "usuario": "jsonrpc",
        "token_api": TOKEN,
        "autenticacao": "Basic (jsonrpc:token_api em Base64)"
    }

    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    log(f"  ✓ powerbi_config.json atualizado com {len(col_map)} colunas")
    log(f"  ✓ Mapeamento de fases: {len(phase_map)} entradas")
    log(f"  ✓ Campos customizados registrados: {len(CUSTOM_FIELDS)}")

    # Salvar também um arquivo de referência dos campos
    fields_ref_path = BASE_DIR / "powerbi" / "campos_customizados.json"
    with open(fields_ref_path, 'w', encoding='utf-8') as f:
        json.dump({
            "projeto": "CRM Salesforce",
            "project_id": PROJECT_ID,
            "gerado_em": datetime.now().isoformat(),
            "campos": CUSTOM_FIELDS,
            "instrucoes": "Para ativar campos customizados no Kanboard, instale o plugin 'CustomFields' em Configurações > Plugins"
        }, f, ensure_ascii=False, indent=2)
    log(f"  ✓ Referência de campos salva em campos_customizados.json")

    return col_map, phase_map

def main():
    log("=" * 60)
    log("EBL Kanboard — Reconfiguração do Projeto CRM Salesforce")
    log("=" * 60)
    log(f"Projeto ID: {PROJECT_ID}")
    log(f"Endpoint: {URL}")
    log("")

    # Verificar conexão
    version = api("getVersion")
    if not version:
        log("Falha na conexão com o Kanboard!", "ERROR")
        return 1
    log(f"Kanboard versão: {version}")
    log("")

    results = {
        "timestamp": datetime.now().isoformat(),
        "status": "success",
        "etapas": {}
    }

    # Etapa 1: Reordenar colunas
    ok1 = step1_reorder_columns()
    results["etapas"]["reordenacao_colunas"] = "success" if ok1 else "error"

    # Etapa 2: Campos customizados
    ok2, msg2 = step2_create_custom_fields()
    results["etapas"]["campos_customizados"] = msg2

    # Etapa 3: Atualizar configuração
    col_map, phase_map = step3_update_config()
    results["etapas"]["config_atualizada"] = "success"
    results["colunas_mapeadas"] = len(col_map)

    # Resumo final
    log("")
    log("=" * 60)
    log("RECONFIGURAÇÃO CONCLUÍDA")
    log("=" * 60)
    log(f"  Colunas reordenadas: {'✓' if ok1 else '✗'}")
    log(f"  Campos customizados: {msg2}")
    log(f"  Config atualizada: ✓")
    log("")
    log("Nova sequência de colunas:")
    for name, pos, _ in NOVA_SEQUENCIA:
        log(f"  {pos:2d}. {name}")

    if msg2 == "plugin_not_installed":
        log("")
        log("AÇÃO NECESSÁRIA: Para adicionar os campos customizados do Excel,")
        log("instale o plugin 'CustomFields' no Kanboard:")
        log("  1. Acesse: http://kanboard.eblsolucoescorp.tec.br")
        log("  2. Vá em: Configurações > Gerenciar Plugins")
        log("  3. Instale: 'Custom Fields' ou 'MetaMagik'")
        log("  4. Execute este script novamente")

    # Salvar resultado
    result_path = BASE_DIR / "powerbi" / "reconfig_result.json"
    with open(result_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    log(f"\nResultado salvo em: {result_path}")

    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
