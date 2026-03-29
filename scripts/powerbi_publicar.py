#!/usr/bin/env python3
"""
Script para publicar dataset e relatório no Power BI Service
Usa MSAL para autenticação com usuário/senha (ROPC flow)
"""

import requests
import json
import csv
import sys
from datetime import datetime

# ============================================================
# CONFIGURAÇÕES
# ============================================================
PBI_USERNAME = "admebl@eblsolucoescorporativas.com"
PBI_PASSWORD = "Senha@2026"
KANBOARD_BASE = "http://kanboard.eblsolucoescorp.tec.br"
KANBOARD_USER = "admin"
KANBOARD_PASS = "Senha@2026"
CSV_PATH = "/home/ubuntu/kanboard/powerbi/kanboard_dados.csv"

# Power BI API
PBI_API = "https://api.powerbi.com/v1.0/myorg"
AUTHORITY = "https://login.microsoftonline.com/208364c6-eee7-4324-ac4a-d45fe452a1bd"
CLIENT_ID = "04b07795-8ddb-461a-bbee-02f9e1bf7b46"  # Azure CLI public client (works with any tenant)
SCOPE = ["https://analysis.windows.net/powerbi/api/.default"]

print("=" * 60)
print("EBL SOLUÇÕES — Power BI Dataset Publisher")
print("=" * 60)

# ============================================================
# STEP 1: AUTENTICAÇÃO VIA MSAL ROPC
# ============================================================
print("\n[1/5] Autenticando no Power BI Service...")

try:
    import msal
    app = msal.PublicClientApplication(CLIENT_ID, authority=AUTHORITY)
    result = app.acquire_token_by_username_password(
        username=PBI_USERNAME,
        password=PBI_PASSWORD,
        scopes=SCOPE
    )
    
    if "access_token" in result:
        ACCESS_TOKEN = result["access_token"]
        print(f"  ✅ Token obtido com sucesso! Expira em: {result.get('expires_in', 'N/A')}s")
    else:
        print(f"  ❌ Erro de autenticação: {result.get('error_description', result)}")
        sys.exit(1)
except Exception as e:
    print(f"  ❌ Erro MSAL: {e}")
    sys.exit(1)

HEADERS = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

# ============================================================
# STEP 2: BUSCAR DADOS DO KANBOARD VIA API
# ============================================================
print("\n[2/5] Buscando dados do Kanboard...")

def kb_call(method, params=None):
    payload = {"jsonrpc": "2.0", "method": method, "id": 1, "params": params or {}}
    r = requests.post(f"{KANBOARD_BASE}/jsonrpc.php", 
                      json=payload, 
                      auth=(KANBOARD_USER, KANBOARD_PASS),
                      timeout=30)
    return r.json().get("result", [])

# Buscar todas as tarefas do projeto principal (ID 11)
tasks = kb_call("getAllTasks", {"project_id": 11, "status_id": 0})  # 0 = all
if not tasks:
    tasks = kb_call("getAllTasks", {"project_id": 11, "status_id": 1})  # 1 = open

print(f"  📋 {len(tasks)} tarefas encontradas no Kanboard")

# Buscar colunas para mapear IDs
columns = kb_call("getColumns", {"project_id": 11})
col_map = {c["id"]: c["title"] for c in columns} if columns else {}

# Buscar swimlanes
swimlanes = kb_call("getSwimlanes", {"project_id": 11})
swim_map = {s["id"]: s["name"] for s in swimlanes} if swimlanes else {}

print(f"  📊 {len(col_map)} colunas | {len(swim_map)} swimlanes mapeados")

# ============================================================
# STEP 3: PREPARAR DADOS
# ============================================================
print("\n[3/5] Preparando dados para o Power BI...")

rows = []
for t in tasks:
    # Mapear fase
    col_id = str(t.get("column_id", ""))
    fase = col_map.get(col_id, col_map.get(int(col_id) if col_id.isdigit() else 0, "Backlog"))
    
    # Mapear responsável
    owner = t.get("assignee_username", "") or t.get("owner_username", "")
    owner_name = t.get("assignee_name", "") or owner
    
    # Prioridade
    pri_map = {0: "Baixa", 1: "Baixa", 2: "Média", 3: "Alta"}
    prioridade = pri_map.get(t.get("priority", 0), "Média")
    
    # Status
    is_closed = t.get("is_active", 1) == 0
    status = "Implementado" if is_closed else "Aberta"
    
    # Prazo
    due_date = ""
    em_atraso = False
    if t.get("date_due") and t["date_due"] > 0:
        try:
            due_dt = datetime.fromtimestamp(int(t["date_due"]))
            due_date = due_dt.strftime("%Y-%m-%d")
            em_atraso = due_dt < datetime.now() and not is_closed
        except:
            pass
    
    # Extrair ID Cherwell do título
    title = t.get("title", "")
    cherwell_id = ""
    
    # Tipo de demanda (baseado no título)
    tipo = "Parametrização"
    title_lower = title.lower()
    if "incidente" in title_lower or "erro" in title_lower or "falha" in title_lower:
        tipo = "Incidente"
    elif "prod." in title_lower or "produtividade" in title_lower or "melhoria" in title_lower:
        tipo = "Prod. TI"
    elif "comercial" in title_lower or "venda" in title_lower or "cliente" in title_lower:
        tipo = "Prod. Comercial"
    
    # Área (swimlane)
    swim_id = str(t.get("swimlane_id", ""))
    area = swim_map.get(swim_id, swim_map.get(int(swim_id) if swim_id.isdigit() else 0, "Geral"))
    
    rows.append({
        "ID": t.get("id", ""),
        "Titulo": title[:100],
        "Fase": fase,
        "Responsavel": owner_name or owner,
        "Area": area,
        "Tipo": tipo,
        "Prioridade": prioridade,
        "Status": status,
        "Prazo": due_date,
        "Em_Atraso": em_atraso,
        "Data_Criacao": datetime.fromtimestamp(int(t.get("date_creation", 0))).strftime("%Y-%m-%d") if t.get("date_creation") else "",
        "Projeto": "Fast Track Salesforce"
    })

# Também ler do CSV para ter os dados completos (ID Cherwell, RDM, etc)
csv_data = {}
try:
    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            title_key = row.get("Titulo", "")[:50]
            csv_data[title_key] = row
    print(f"  📄 {len(csv_data)} registros do CSV carregados")
except Exception as e:
    print(f"  ⚠️  CSV não encontrado: {e}")

print(f"  ✅ {len(rows)} linhas preparadas para o dataset")

# ============================================================
# STEP 4: CRIAR DATASET NO POWER BI SERVICE
# ============================================================
print("\n[4/5] Criando dataset no Power BI Service...")

dataset_def = {
    "name": "EBL Fast Track Salesforce",
    "defaultMode": "Push",
    "tables": [
        {
            "name": "Demandas",
            "columns": [
                {"name": "ID", "dataType": "Int64"},
                {"name": "Titulo", "dataType": "string"},
                {"name": "Fase", "dataType": "string"},
                {"name": "Responsavel", "dataType": "string"},
                {"name": "Area", "dataType": "string"},
                {"name": "Tipo", "dataType": "string"},
                {"name": "Prioridade", "dataType": "string"},
                {"name": "Status", "dataType": "string"},
                {"name": "Prazo", "dataType": "DateTime"},
                {"name": "Em_Atraso", "dataType": "bool"},
                {"name": "Data_Criacao", "dataType": "DateTime"},
                {"name": "Projeto", "dataType": "string"}
            ]
        },
        {
            "name": "KPIs",
            "columns": [
                {"name": "Metrica", "dataType": "string"},
                {"name": "Valor", "dataType": "Int64"},
                {"name": "Percentual", "dataType": "Double"},
                {"name": "Categoria", "dataType": "string"}
            ]
        }
    ]
}

# Verificar se já existe dataset com mesmo nome
r = requests.get(f"{PBI_API}/datasets", headers=HEADERS)
existing_datasets = r.json().get("value", []) if r.status_code == 200 else []
existing_id = None
for ds in existing_datasets:
    if ds["name"] == "EBL Fast Track Salesforce":
        existing_id = ds["id"]
        print(f"  ℹ️  Dataset existente encontrado: {existing_id} — será atualizado")
        break

if existing_id:
    # Deletar linhas existentes
    del_r = requests.delete(f"{PBI_API}/datasets/{existing_id}/tables/Demandas/rows", headers=HEADERS)
    del_r2 = requests.delete(f"{PBI_API}/datasets/{existing_id}/tables/KPIs/rows", headers=HEADERS)
    dataset_id = existing_id
    print(f"  🗑️  Dados anteriores removidos (status: {del_r.status_code}, {del_r2.status_code})")
else:
    # Criar novo dataset
    r = requests.post(f"{PBI_API}/datasets", headers=HEADERS, json=dataset_def)
    if r.status_code in [200, 201]:
        dataset_id = r.json()["id"]
        print(f"  ✅ Dataset criado! ID: {dataset_id}")
    else:
        print(f"  ❌ Erro ao criar dataset: {r.status_code} — {r.text[:300]}")
        sys.exit(1)

# ============================================================
# STEP 5: INSERIR DADOS NO DATASET
# ============================================================
print("\n[5/5] Inserindo dados no dataset...")

# Preparar linhas para a tabela Demandas
demandas_rows = []
for row in rows:
    demandas_rows.append({
        "ID": int(row["ID"]) if str(row["ID"]).isdigit() else 0,
        "Titulo": row["Titulo"],
        "Fase": row["Fase"],
        "Responsavel": row["Responsavel"],
        "Area": row["Area"],
        "Tipo": row["Tipo"],
        "Prioridade": row["Prioridade"],
        "Status": row["Status"],
        "Prazo": row["Prazo"] + "T00:00:00" if row["Prazo"] else None,
        "Em_Atraso": row["Em_Atraso"],
        "Data_Criacao": row["Data_Criacao"] + "T00:00:00" if row["Data_Criacao"] else None,
        "Projeto": row["Projeto"]
    })

# Inserir em lotes de 100
batch_size = 100
total_inserted = 0
for i in range(0, len(demandas_rows), batch_size):
    batch = demandas_rows[i:i+batch_size]
    r = requests.post(
        f"{PBI_API}/datasets/{dataset_id}/tables/Demandas/rows",
        headers=HEADERS,
        json={"rows": batch}
    )
    if r.status_code == 200:
        total_inserted += len(batch)
        print(f"  ✅ Lote {i//batch_size + 1}: {len(batch)} linhas inseridas (total: {total_inserted})")
    else:
        print(f"  ❌ Erro no lote {i//batch_size + 1}: {r.status_code} — {r.text[:200]}")

# Calcular KPIs
total = len(rows)
implementados = sum(1 for r in rows if r["Status"] == "Implementado")
em_atraso = sum(1 for r in rows if r["Em_Atraso"])
alta_pri = sum(1 for r in rows if r["Prioridade"] == "Alta")
em_andamento = total - implementados

kpi_rows = [
    {"Metrica": "Total de Demandas", "Valor": total, "Percentual": 100.0, "Categoria": "Geral"},
    {"Metrica": "Implementadas", "Valor": implementados, "Percentual": round(implementados/total*100, 1) if total else 0, "Categoria": "Concluído"},
    {"Metrica": "Em Andamento", "Valor": em_andamento, "Percentual": round(em_andamento/total*100, 1) if total else 0, "Categoria": "Ativo"},
    {"Metrica": "Em Atraso", "Valor": em_atraso, "Percentual": round(em_atraso/total*100, 1) if total else 0, "Categoria": "Crítico"},
    {"Metrica": "Alta Prioridade", "Valor": alta_pri, "Percentual": round(alta_pri/total*100, 1) if total else 0, "Categoria": "Urgente"},
]

r = requests.post(
    f"{PBI_API}/datasets/{dataset_id}/tables/KPIs/rows",
    headers=HEADERS,
    json={"rows": kpi_rows}
)
print(f"  {'✅' if r.status_code == 200 else '❌'} KPIs inseridos (status: {r.status_code})")

# ============================================================
# RESULTADO FINAL
# ============================================================
print("\n" + "=" * 60)
print("RESULTADO FINAL")
print("=" * 60)
print(f"  Dataset ID: {dataset_id}")
print(f"  Total de linhas inseridas: {total_inserted}")
print(f"  KPIs: {len(kpi_rows)}")
print(f"\n  🔗 Power BI Service: https://app.powerbi.com")
print(f"  📊 Dataset: EBL Fast Track Salesforce")
print(f"\n  Para criar o relatório, acesse:")
print(f"  https://app.powerbi.com/groups/me/datasets/{dataset_id}/details")
print("=" * 60)

# Salvar dataset_id para uso posterior
with open("/home/ubuntu/kanboard/powerbi/pbi_dataset_id.txt", "w") as f:
    f.write(dataset_id)

print(f"\n✅ Dataset ID salvo em: /home/ubuntu/kanboard/powerbi/pbi_dataset_id.txt")
