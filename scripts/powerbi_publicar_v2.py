#!/usr/bin/env python3
"""
Script v2 — Publicar dataset completo no Power BI Service
Lê todas as 105 demandas do CSV e cria dataset rico para relatórios executivos
"""

import requests
import json
import csv
import sys
import msal
from datetime import datetime
from collections import Counter

# ============================================================
# CONFIGURAÇÕES
# ============================================================
PBI_USERNAME = "admebl@eblsolucoescorporativas.com"
PBI_PASSWORD = "Senha@2026"
KANBOARD_BASE = "http://kanboard.eblsolucoescorp.tec.br"
KANBOARD_USER = "admin"
KANBOARD_PASS = "Senha@2026"
CSV_PATH = "/home/ubuntu/kanboard/powerbi/kanboard_dados.csv"

PBI_API = "https://api.powerbi.com/v1.0/myorg"
AUTHORITY = "https://login.microsoftonline.com/208364c6-eee7-4324-ac4a-d45fe452a1bd"
CLIENT_ID = "04b07795-8ddb-461a-bbee-02f9e1bf7b46"
SCOPE = ["https://analysis.windows.net/powerbi/api/.default"]
DATASET_NAME = "EBL Fast Track Salesforce"

print("=" * 65)
print("  EBL SOLUÇÕES — Power BI Dataset Publisher v2.0")
print("=" * 65)

# ============================================================
# AUTENTICAÇÃO
# ============================================================
print("\n[1/6] Autenticando no Power BI Service...")
app = msal.PublicClientApplication(CLIENT_ID, authority=AUTHORITY)
result = app.acquire_token_by_username_password(
    username=PBI_USERNAME, password=PBI_PASSWORD, scopes=SCOPE
)
if "access_token" not in result:
    print(f"  ❌ {result.get('error_description', result)}")
    sys.exit(1)
ACCESS_TOKEN = result["access_token"]
HEADERS = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
print(f"  ✅ Autenticado com sucesso!")

# ============================================================
# LER CSV COMPLETO (105 demandas)
# ============================================================
print("\n[2/6] Carregando dados do CSV (105 demandas)...")

rows = []
try:
    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            rows.append(row)
    print(f"  ✅ {len(rows)} demandas carregadas do CSV")
    if rows:
        print(f"  📋 Colunas: {list(rows[0].keys())}")
except Exception as e:
    print(f"  ❌ Erro ao ler CSV: {e}")
    sys.exit(1)

# ============================================================
# PREPARAR DADOS RICOS
# ============================================================
print("\n[3/6] Preparando dados enriquecidos...")

demandas_rows = []
hoje = datetime.now()

for row in rows:
    # Prazo
    prazo_str = row.get("Prazo", "") or row.get("prazo", "") or ""
    prazo_dt = None
    em_atraso = False
    if prazo_str and prazo_str.strip():
        try:
            # Tentar vários formatos
            for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"]:
                try:
                    prazo_dt = datetime.strptime(prazo_str.strip(), fmt)
                    break
                except:
                    pass
            if prazo_dt:
                em_atraso = prazo_dt < hoje and row.get("Status", "Aberta") != "Implementado"
        except:
            pass

    # Data criação
    data_criacao_str = row.get("Data_Criacao", "") or row.get("data_criacao", "") or ""
    
    # Fase limpa (sem "Em ")
    fase = row.get("Fase", "Backlog") or "Backlog"
    fase = fase.replace("Em ", "").strip()
    # Mapear fases para nomes limpos
    fase_map = {
        "01. Backlog": "01. Backlog",
        "02. Refinamento": "02. Refinamento", 
        "06. Aprovação": "06. Aprovação",
        "07. Desenvolvimento": "07. Desenvolvimento",
        "08. Homologação": "08. Homologação",
        "09. Deploy": "09. Deploy",
        "10. Implementado": "10. Implementado",
        "Backlog": "01. Backlog",
        "Refinamento": "02. Refinamento",
        "Aprovação": "06. Aprovação",
        "Desenvolvimento": "07. Desenvolvimento",
        "Homologação": "08. Homologação",
        "Deploy": "09. Deploy",
        "Implementado": "10. Implementado",
    }
    fase_final = fase_map.get(fase, fase)
    
    # Número da fase para ordenação
    fase_num = 1
    if "02" in fase_final or "Refinamento" in fase_final: fase_num = 2
    elif "06" in fase_final or "Aprovação" in fase_final: fase_num = 6
    elif "07" in fase_final or "Desenvolvimento" in fase_final: fase_num = 7
    elif "08" in fase_final or "Homologação" in fase_final: fase_num = 8
    elif "09" in fase_final or "Deploy" in fase_final: fase_num = 9
    elif "10" in fase_final or "Implementado" in fase_final: fase_num = 10

    # Responsável
    resp = row.get("Responsavel_Raia", "") or row.get("Responsavel", "") or "Não atribuído"
    
    # Prioridade
    pri = row.get("Prioridade_Texto", "") or row.get("Prioridade", "Média")
    if pri not in ["Alta", "Média", "Baixa"]:
        pri = "Média"
    pri_num = {"Alta": 3, "Média": 2, "Baixa": 1}.get(pri, 2)
    
    # Status
    status = row.get("Status", "Aberta")
    
    # Tipo
    tipo = row.get("Tipo_Demanda", "") or row.get("Tipo", "Parametrização")
    
    # Área
    area = row.get("Area_Solicitante", "") or row.get("Area", "Geral")
    
    # ID Cherwell
    cherwell = row.get("ID_Cherwell", "") or row.get("id_cherwell", "") or ""
    
    # RDM
    rdm = row.get("RDM", "") or row.get("rdm", "") or ""
    
    # Título
    titulo = row.get("Titulo", "") or row.get("titulo", "") or ""
    
    demandas_rows.append({
        "ID": int(row.get("ID", 0)) if str(row.get("ID", "0")).isdigit() else 0,
        "ID_Cherwell": str(cherwell),
        "RDM": str(rdm),
        "Titulo": titulo[:150],
        "Fase": fase_final,
        "Fase_Numero": fase_num,
        "Responsavel": resp,
        "Area": area,
        "Tipo": tipo,
        "Prioridade": pri,
        "Prioridade_Numero": pri_num,
        "Status": status,
        "Prazo": prazo_dt.strftime("%Y-%m-%dT00:00:00") if prazo_dt else None,
        "Em_Atraso": em_atraso,
        "Data_Criacao": data_criacao_str + "T00:00:00" if data_criacao_str and len(data_criacao_str) == 10 else None,
        "Projeto": "Fast Track Salesforce",
        "Mes_Prazo": prazo_dt.strftime("%Y-%m") if prazo_dt else "Sem prazo",
        "Ano_Prazo": prazo_dt.year if prazo_dt else 0,
    })

print(f"  ✅ {len(demandas_rows)} linhas preparadas")

# Calcular KPIs
total = len(demandas_rows)
implementados = sum(1 for r in demandas_rows if "Implementado" in r["Fase"])
em_atraso_count = sum(1 for r in demandas_rows if r["Em_Atraso"])
alta_pri = sum(1 for r in demandas_rows if r["Prioridade"] == "Alta")
em_andamento = total - implementados
backlog = sum(1 for r in demandas_rows if "Backlog" in r["Fase"])
aprovacao = sum(1 for r in demandas_rows if "Aprovação" in r["Fase"])
desenvolvimento = sum(1 for r in demandas_rows if "Desenvolvimento" in r["Fase"])

print(f"  📊 KPIs: Total={total} | Implementados={implementados} | Atraso={em_atraso_count} | Alta={alta_pri}")

# ============================================================
# GERENCIAR DATASET NO POWER BI
# ============================================================
print("\n[4/6] Gerenciando dataset no Power BI Service...")

# Verificar datasets existentes
r = requests.get(f"{PBI_API}/datasets", headers=HEADERS)
existing = r.json().get("value", []) if r.status_code == 200 else []
dataset_id = None

for ds in existing:
    if ds["name"] == DATASET_NAME:
        dataset_id = ds["id"]
        print(f"  ℹ️  Dataset existente encontrado: {dataset_id}")
        # Limpar dados existentes
        for table in ["Demandas", "KPIs", "Fases", "Responsaveis"]:
            del_r = requests.delete(f"{PBI_API}/datasets/{dataset_id}/tables/{table}/rows", headers=HEADERS)
        print(f"  🗑️  Dados anteriores removidos")
        break

if not dataset_id:
    # Criar dataset com schema completo
    dataset_def = {
        "name": DATASET_NAME,
        "defaultMode": "Push",
        "tables": [
            {
                "name": "Demandas",
                "columns": [
                    {"name": "ID", "dataType": "Int64"},
                    {"name": "ID_Cherwell", "dataType": "string"},
                    {"name": "RDM", "dataType": "string"},
                    {"name": "Titulo", "dataType": "string"},
                    {"name": "Fase", "dataType": "string"},
                    {"name": "Fase_Numero", "dataType": "Int64"},
                    {"name": "Responsavel", "dataType": "string"},
                    {"name": "Area", "dataType": "string"},
                    {"name": "Tipo", "dataType": "string"},
                    {"name": "Prioridade", "dataType": "string"},
                    {"name": "Prioridade_Numero", "dataType": "Int64"},
                    {"name": "Status", "dataType": "string"},
                    {"name": "Prazo", "dataType": "DateTime"},
                    {"name": "Em_Atraso", "dataType": "bool"},
                    {"name": "Data_Criacao", "dataType": "DateTime"},
                    {"name": "Projeto", "dataType": "string"},
                    {"name": "Mes_Prazo", "dataType": "string"},
                    {"name": "Ano_Prazo", "dataType": "Int64"},
                ]
            },
            {
                "name": "KPIs",
                "columns": [
                    {"name": "Metrica", "dataType": "string"},
                    {"name": "Valor", "dataType": "Int64"},
                    {"name": "Percentual", "dataType": "Double"},
                    {"name": "Categoria", "dataType": "string"},
                    {"name": "Icone", "dataType": "string"},
                    {"name": "Cor", "dataType": "string"},
                ]
            },
            {
                "name": "Fases",
                "columns": [
                    {"name": "Fase", "dataType": "string"},
                    {"name": "Quantidade", "dataType": "Int64"},
                    {"name": "Percentual", "dataType": "Double"},
                    {"name": "Ordem", "dataType": "Int64"},
                ]
            },
            {
                "name": "Responsaveis",
                "columns": [
                    {"name": "Responsavel", "dataType": "string"},
                    {"name": "Total", "dataType": "Int64"},
                    {"name": "Alta_Prioridade", "dataType": "Int64"},
                    {"name": "Em_Atraso", "dataType": "Int64"},
                    {"name": "Implementados", "dataType": "Int64"},
                ]
            }
        ]
    }
    
    r = requests.post(f"{PBI_API}/datasets", headers=HEADERS, json=dataset_def)
    if r.status_code in [200, 201]:
        dataset_id = r.json()["id"]
        print(f"  ✅ Dataset criado! ID: {dataset_id}")
    else:
        print(f"  ❌ Erro: {r.status_code} — {r.text[:400]}")
        sys.exit(1)

# ============================================================
# INSERIR DADOS
# ============================================================
print("\n[5/6] Inserindo dados no dataset...")

# Tabela Demandas (em lotes de 100)
total_inserted = 0
for i in range(0, len(demandas_rows), 100):
    batch = demandas_rows[i:i+100]
    r = requests.post(
        f"{PBI_API}/datasets/{dataset_id}/tables/Demandas/rows",
        headers=HEADERS, json={"rows": batch}
    )
    if r.status_code == 200:
        total_inserted += len(batch)
        print(f"  ✅ Demandas lote {i//100+1}: {len(batch)} linhas (total: {total_inserted})")
    else:
        print(f"  ❌ Erro lote {i//100+1}: {r.status_code} — {r.text[:200]}")

# Tabela KPIs
kpi_data = [
    {"Metrica": "Total de Demandas", "Valor": total, "Percentual": 100.0, "Categoria": "Geral", "Icone": "📋", "Cor": "#0078D4"},
    {"Metrica": "Implementadas", "Valor": implementados, "Percentual": round(implementados/total*100,1), "Categoria": "Concluído", "Icone": "✅", "Cor": "#107C10"},
    {"Metrica": "Em Andamento", "Valor": em_andamento, "Percentual": round(em_andamento/total*100,1), "Categoria": "Ativo", "Icone": "🔄", "Cor": "#0078D4"},
    {"Metrica": "Em Atraso", "Valor": em_atraso_count, "Percentual": round(em_atraso_count/total*100,1), "Categoria": "Crítico", "Icone": "⚠️", "Cor": "#D83B01"},
    {"Metrica": "Alta Prioridade", "Valor": alta_pri, "Percentual": round(alta_pri/total*100,1), "Categoria": "Urgente", "Icone": "🔴", "Cor": "#A80000"},
    {"Metrica": "No Backlog", "Valor": backlog, "Percentual": round(backlog/total*100,1), "Categoria": "Pipeline", "Icone": "📥", "Cor": "#8764B8"},
    {"Metrica": "Em Aprovação", "Valor": aprovacao, "Percentual": round(aprovacao/total*100,1), "Categoria": "Pipeline", "Icone": "📝", "Cor": "#F7630C"},
    {"Metrica": "Em Desenvolvimento", "Valor": desenvolvimento, "Percentual": round(desenvolvimento/total*100,1), "Categoria": "Pipeline", "Icone": "💻", "Cor": "#0099BC"},
]
r = requests.post(f"{PBI_API}/datasets/{dataset_id}/tables/KPIs/rows", headers=HEADERS, json={"rows": kpi_data})
print(f"  {'✅' if r.status_code == 200 else '❌'} KPIs: {len(kpi_data)} métricas (status: {r.status_code})")

# Tabela Fases
fase_counter = Counter(r["Fase"] for r in demandas_rows)
fase_ordem = {"01. Backlog": 1, "02. Refinamento": 2, "06. Aprovação": 6, "07. Desenvolvimento": 7, 
              "08. Homologação": 8, "09. Deploy": 9, "10. Implementado": 10}
fases_data = [
    {"Fase": fase, "Quantidade": qtd, "Percentual": round(qtd/total*100,1), "Ordem": fase_ordem.get(fase, 99)}
    for fase, qtd in sorted(fase_counter.items(), key=lambda x: fase_ordem.get(x[0], 99))
]
r = requests.post(f"{PBI_API}/datasets/{dataset_id}/tables/Fases/rows", headers=HEADERS, json={"rows": fases_data})
print(f"  {'✅' if r.status_code == 200 else '❌'} Fases: {len(fases_data)} fases (status: {r.status_code})")

# Tabela Responsáveis
resp_counter = Counter(r["Responsavel"] for r in demandas_rows)
resp_data = []
for resp, total_resp in resp_counter.most_common():
    resp_data.append({
        "Responsavel": resp,
        "Total": total_resp,
        "Alta_Prioridade": sum(1 for r in demandas_rows if r["Responsavel"] == resp and r["Prioridade"] == "Alta"),
        "Em_Atraso": sum(1 for r in demandas_rows if r["Responsavel"] == resp and r["Em_Atraso"]),
        "Implementados": sum(1 for r in demandas_rows if r["Responsavel"] == resp and "Implementado" in r["Fase"]),
    })
r = requests.post(f"{PBI_API}/datasets/{dataset_id}/tables/Responsaveis/rows", headers=HEADERS, json={"rows": resp_data})
print(f"  {'✅' if r.status_code == 200 else '❌'} Responsáveis: {len(resp_data)} pessoas (status: {r.status_code})")

# ============================================================
# SALVAR CONFIGURAÇÕES
# ============================================================
print("\n[6/6] Salvando configurações...")

config = {
    "dataset_id": dataset_id,
    "dataset_name": DATASET_NAME,
    "tenant_id": "208364c6-eee7-4324-ac4a-d45fe452a1bd",
    "client_id": CLIENT_ID,
    "username": PBI_USERNAME,
    "total_rows": total_inserted,
    "last_update": datetime.now().isoformat(),
    "kanboard_api": f"{KANBOARD_BASE}/jsonrpc.php",
    "powerbi_url": f"https://app.powerbi.com/groups/me/datasets/{dataset_id}/details"
}

with open("/home/ubuntu/kanboard/powerbi/pbi_config.json", "w") as f:
    json.dump(config, f, indent=2)

with open("/home/ubuntu/kanboard/powerbi/pbi_dataset_id.txt", "w") as f:
    f.write(dataset_id)

print("=" * 65)
print("  RESULTADO FINAL")
print("=" * 65)
print(f"  ✅ Dataset ID: {dataset_id}")
print(f"  ✅ Total inserido: {total_inserted} demandas")
print(f"  ✅ KPIs: {len(kpi_data)} métricas")
print(f"  ✅ Fases: {len(fases_data)} fases")
print(f"  ✅ Responsáveis: {len(resp_data)} pessoas")
print(f"\n  🔗 Dataset no Power BI:")
print(f"     https://app.powerbi.com/groups/me/datasets/{dataset_id}/details")
print(f"\n  📊 Para criar relatório:")
print(f"     https://app.powerbi.com/groups/me/datasets/{dataset_id}/createreport")
print("=" * 65)
