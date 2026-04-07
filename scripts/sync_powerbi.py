#!/usr/bin/env python3
"""
EBL Kanboard → Power BI Sync Automático (com fallback para dados locais)
Executa diariamente via cron/GitHub Actions
Versão: 2.2 | Atualizado em: 2026-04-07
Melhorias v2.2:
  - Usa data_enriquecido.json como fonte principal (105 tarefas)
  - Tenta API Kanboard com X-API-Auth header (config.php personalizado)
  - Fallback robusto: data_enriquecido.json → snapshot_antes_limpeza.json
  - Autenticação Power BI com múltiplos client_ids
  - KPIs, Fases e Responsáveis calculados e enviados ao Power BI
"""

import msal, requests, json, csv, sys, os
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter, defaultdict

# ===== CONFIGURAÇÕES =====
KANBOARD_URL   = "http://kanboard.eblsolucoescorp.tec.br/jsonrpc.php"
KANBOARD_USER  = "admin"
KANBOARD_PASS  = "Senha@2026"
# Token API atual (obtido via /user/1/api no Kanboard)
KANBOARD_TOKEN = "65251ba731c6900a80a8a733ced2aae364cb28172e16df1785b22444124e387f"
KANBOARD_PROJ  = 11  # [SF] Fast Track — Salesforce

PBI_USERNAME   = "admebl@eblsolucoescorporativas.com"
PBI_PASSWORD   = "Senha@2026"
PBI_TENANT_ID  = "208364c6-eee7-4324-ac4a-d45fe452a1bd"
PBI_CLIENT_ID  = "1950a258-227b-4e31-a9cf-717495945fc2"
PBI_CLIENT_ID2 = "04b07795-8ddb-461a-bbee-02f9e1bf7b46"
PBI_DATASET_ID = "39d50fe5-cde9-4244-b5e5-422a73e8e142"
PBI_SCOPE      = ["https://analysis.windows.net/powerbi/api/.default"]

BASE_DIR       = Path(__file__).parent.parent
EXCEL_MAP      = BASE_DIR / "powerbi" / "excel_map.json"
LOG_FILE       = BASE_DIR / "powerbi" / "sync_log.json"
LOCAL_SNAPSHOT = BASE_DIR / "backups" / "snapshot_antes_limpeza.json"
DATA_ENRIQUECIDO = BASE_DIR / "powerbi" / "data_enriquecido.json"
LOCAL_CSV      = BASE_DIR / "powerbi" / "kanboard_dados_final.csv"

# Mapeamento de colunas (IDs → Fases) para projeto 11
COLUMN_MAP = {
    "165": "01. Backlog", "166": "02. Refinamento", "167": "03. Priorizada",
    "168": "04. Análise", "169": "05. Estimativa", "170": "06. Aprovação",
    "171": "07. Desenvolvimento", "172": "08. Homologação", "173": "09. Deploy",
    "174": "10. Implementado", "175": "11. Cancelado",
    "176": "01. Backlog", "177": "02. Refinamento", "178": "04. Análise",
    "179": "05. Estimativa", "180": "06. Aprovação", "181": "07. Desenvolvimento",
    "182": "08. Homologação", "183": "09. Deploy", "184": "10. Implementado",
    "185": "11. Cancelado",
    "186": "01. Backlog", "187": "02. Refinamento", "188": "04. Análise",
    "189": "05. Estimativa", "190": "06. Aprovação", "191": "07. Desenvolvimento",
    "192": "08. Homologação", "193": "09. Deploy", "194": "10. Implementado",
    "195": "11. Cancelado", "39": "03. Priorizada"
}

def log(msg, level="INFO"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [{level}] {msg}")

# =====================================================================
# AUTENTICAÇÃO POWER BI
# =====================================================================
def get_pbi_token():
    """Obtém token de acesso ao Power BI via MSAL com múltiplos client IDs"""
    log("Autenticando no Power BI Service...")
    for cid in [PBI_CLIENT_ID, PBI_CLIENT_ID2]:
        try:
            app = msal.PublicClientApplication(
                cid, authority=f"https://login.microsoftonline.com/{PBI_TENANT_ID}"
            )
            result = app.acquire_token_by_username_password(
                PBI_USERNAME, PBI_PASSWORD, scopes=PBI_SCOPE
            )
            if "access_token" in result:
                log(f"  Token Power BI obtido com sucesso! (client_id={cid[:8]}...)")
                return result["access_token"]
            err = result.get("error_description", result.get("error", ""))
            log(f"  Falhou com client_id={cid[:8]}...: {str(err)[:100]}", "WARN")
        except Exception as e:
            log(f"  Erro com client_id={cid[:8]}...: {e}", "WARN")
    raise Exception("Falha na autenticação Power BI com todos os client IDs")

# =====================================================================
# KANBOARD API (com X-API-Auth header personalizado)
# =====================================================================
_req_id = 0

def kanboard_api(method, params=None):
    """Chama a API JSON-RPC do Kanboard via X-API-Auth header"""
    global _req_id
    _req_id += 1
    payload = {"jsonrpc": "2.0", "method": method, "id": _req_id, "params": params or {}}
    headers = {
        "Content-Type": "application/json",
        "X-API-Auth": KANBOARD_TOKEN,
    }
    r = requests.post(KANBOARD_URL, json=payload, headers=headers, timeout=20)
    r.raise_for_status()
    resp = r.json()
    if "error" in resp:
        raise Exception(f"Kanboard API error: {resp['error']}")
    return resp.get("result")

def get_all_tasks_from_api():
    """Busca todas as tarefas do projeto (abertas e fechadas) via API"""
    log("Tentando buscar tarefas do Kanboard via API...")
    open_tasks = kanboard_api("getAllTasks", {"project_id": KANBOARD_PROJ, "status_id": 1}) or []
    log(f"  → {len(open_tasks)} tarefas abertas")
    closed_tasks = kanboard_api("getAllTasks", {"project_id": KANBOARD_PROJ, "status_id": 0}) or []
    log(f"  → {len(closed_tasks)} tarefas fechadas")
    return open_tasks + closed_tasks

# =====================================================================
# FONTES DE DADOS (com fallback em cascata)
# =====================================================================
def get_all_tasks():
    """
    Obtém tarefas com fallback em cascata:
    1. API Kanboard (ao vivo)
    2. data_enriquecido.json (105 tarefas já enriquecidas)
    3. snapshot_antes_limpeza.json (97 tarefas brutas)
    """
    # Tentativa 1: API ao vivo
    try:
        tasks = get_all_tasks_from_api()
        if tasks:
            log(f"Total: {len(tasks)} tarefas obtidas da API Kanboard")
            return tasks, "kanboard_api"
    except Exception as e:
        log(f"API Kanboard indisponível: {e}", "WARN")

    # Tentativa 2: data_enriquecido.json (já processado)
    if DATA_ENRIQUECIDO.exists():
        log("Usando data_enriquecido.json como fonte de dados...", "WARN")
        with open(DATA_ENRIQUECIDO, 'r', encoding='utf-8') as f:
            data = json.load(f)
        log(f"  → {len(data)} tarefas carregadas do data_enriquecido.json")
        return data, "data_enriquecido"

    # Tentativa 3: snapshot bruto
    if LOCAL_SNAPSHOT.exists():
        log("Usando snapshot local como fallback...", "WARN")
        with open(LOCAL_SNAPSHOT, 'r', encoding='utf-8') as f:
            tasks = json.load(f)
        log(f"  → {len(tasks)} tarefas carregadas do snapshot local")
        return tasks, "local_snapshot"

    raise Exception("Nenhuma fonte de dados disponível")

# =====================================================================
# ENRIQUECIMENTO DE DADOS
# =====================================================================
def load_excel_enrichment():
    """Carrega dados de enriquecimento do Excel (área, valor, horas, etc.)"""
    if EXCEL_MAP.exists():
        with open(EXCEL_MAP, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def map_phase(column_name):
    """Mapeia nome da coluna para fase padronizada"""
    phase_map = {
        "Backlog": "01. Backlog",
        "Refinamento": "02. Refinamento",
        "Priorizada": "03. Priorizada",
        "Análise": "04. Análise",
        "Estimativa": "05. Estimativa",
        "Aprovação": "06. Aprovação",
        "Desenvolvimento": "07. Desenvolvimento",
        "Homologação": "08. Homologação",
        "Deploy": "09. Deploy",
        "Implementado": "10. Implementado",
        "Cancelado": "11. Cancelado",
    }
    for key, val in phase_map.items():
        if key.lower() in (column_name or "").lower():
            return val
    return column_name or "01. Backlog"

def get_users_map():
    """Obtém mapeamento de usuários (com fallback)"""
    try:
        users = kanboard_api("getAllUsers") or []
        return {str(u["id"]): u.get("name") or u.get("username", "") for u in users}
    except:
        return {
            "1": "admin", "2": "Erick Almeida", "3": "Marcio Souza",
            "4": "Elder Rodrigues", "5": "Felipe Nascimento", "6": "Carlos Almeida"
        }

def enrich_from_api_tasks(tasks, excel_map):
    """Enriquece tarefas brutas da API com dados do Excel e normaliza campos"""
    log("Enriquecendo dados das tarefas (fonte: API)...")
    users_map = get_users_map()
    enriched = []
    for i, task in enumerate(tasks, 1):
        title = task.get("title", "")
        cherwell = ""
        rdm = ""
        parts = title.split(" - ", 2)
        if len(parts) >= 2:
            cherwell = parts[0].strip()
            rdm = parts[1].strip() if len(parts) > 2 else ""
            titulo = parts[-1].strip()
        else:
            titulo = title

        excel_data = excel_map.get(cherwell, {})
        col_id = str(task.get("column_id", ""))
        col_name = COLUMN_MAP.get(col_id, "01. Backlog")
        fase = map_phase(col_name)

        is_closed = task.get("is_active") in ("0", 0)
        status = "Implementado" if is_closed or "Implementado" in col_name else "Aberta"

        owner_id = str(task.get("owner_id", ""))
        resp = users_map.get(owner_id, excel_data.get("resp", "Não atribuído"))

        pri_num = int(task.get("priority", 0) or 0)
        if pri_num >= 3:
            pri = "Alta"
        elif pri_num == 2:
            pri = "Média"
        else:
            pri = excel_data.get("pri", "Média")

        due_date = task.get("date_due", "")
        if due_date and str(due_date) != "0":
            try:
                due_str = datetime.fromtimestamp(int(due_date)).strftime("%d/%m/%Y")
            except:
                due_str = str(due_date)
        else:
            due_str = excel_data.get("golive", "")

        created_at = task.get("date_creation", "")
        try:
            created_str = datetime.fromtimestamp(int(created_at)).strftime("%Y-%m-%d") if created_at else ""
        except:
            created_str = ""

        enriched.append({
            "seq": i,
            "cherwell": cherwell or f"KB-{task.get('id', '')}",
            "rdm": rdm or excel_data.get("rdm", ""),
            "titulo": titulo[:200],
            "fase": fase,
            "status": status,
            "resp": resp,
            "area": excel_data.get("area", ""),
            "tipo": excel_data.get("tipo", ""),
            "pri": pri,
            "golive": due_str,
            "previsao": excel_data.get("previsao", ""),
            "obs": (task.get("description", "") or "")[:300],
            "valor": float(excel_data.get("valor", 0) or 0),
            "horas": float(excel_data.get("horas", 0) or 0),
            "dev": excel_data.get("dev", ""),
            "aprovado": excel_data.get("aprovado", ""),
            "aprovado_por": excel_data.get("aprovado_por", ""),
            "requisitante": excel_data.get("requisitante", ""),
            "valtech": excel_data.get("valtech", ""),
            "data_criacao": created_str,
            "task_id": task.get("id", ""),
            "sync_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })
    log(f"Enriquecimento concluído: {len(enriched)} tarefas processadas")
    return enriched

def normalize_enriquecido(data):
    """Normaliza dados do data_enriquecido.json para o formato padrão"""
    log("Normalizando dados do data_enriquecido.json...")
    sync_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    normalized = []
    for i, d in enumerate(data, 1):
        # Garantir que todos os campos necessários existam
        record = {
            "seq": d.get("seq", i),
            "cherwell": d.get("cherwell", ""),
            "rdm": d.get("rdm", ""),
            "titulo": str(d.get("titulo", ""))[:200],
            "fase": d.get("fase", "01. Backlog"),
            "status": d.get("status", "Aberta"),
            "resp": d.get("resp", "Não atribuído"),
            "area": d.get("area", ""),
            "tipo": d.get("tipo", ""),
            "pri": d.get("pri", "Média"),
            "golive": d.get("golive", ""),
            "previsao": d.get("previsao", ""),
            "obs": str(d.get("obs", ""))[:300],
            "valor": float(d.get("valor", 0) or 0),
            "horas": float(d.get("horas", 0) or 0),
            "dev": d.get("dev", ""),
            "aprovado": d.get("aprovado", ""),
            "aprovado_por": d.get("aprovado_por", ""),
            "requisitante": d.get("requisitante", ""),
            "valtech": d.get("valtech", ""),
            "data_criacao": d.get("data_criacao", ""),
            "task_id": d.get("task_id", d.get("id", "")),
            "sync_at": sync_at,
        }
        normalized.append(record)
    log(f"Normalização concluída: {len(normalized)} registros")
    return normalized

# =====================================================================
# KPIs E MÉTRICAS
# =====================================================================
def compute_kpis(tasks):
    """Calcula KPIs executivos"""
    total = len(tasks)
    impl = sum(1 for t in tasks if t.get("status") == "Implementado")
    alta = sum(1 for t in tasks if t.get("pri") == "Alta")
    backlog = sum(1 for t in tasks if "Backlog" in str(t.get("fase", "")))
    andamento = sum(1 for t in tasks if t.get("fase", "") in [
        "02. Refinamento", "06. Aprovação", "07. Desenvolvimento", "09. Deploy"
    ])
    valor_total = sum(float(t.get("valor", 0) or 0) for t in tasks)
    horas_total = sum(float(t.get("horas", 0) or 0) for t in tasks)
    taxa = round(impl / total * 100, 1) if total > 0 else 0

    return [
        {"kpi": "Total de Demandas", "valor": total, "unidade": "demandas",
         "descricao": "Base Fast Track Salesforce"},
        {"kpi": "Implementadas", "valor": impl, "unidade": "demandas",
         "descricao": f"{taxa}% de conclusão"},
        {"kpi": "Em Andamento", "valor": andamento, "unidade": "demandas",
         "descricao": "Refin + Aprov + Dev + Deploy"},
        {"kpi": "Alta Prioridade", "valor": alta, "unidade": "demandas",
         "descricao": "Atenção imediata"},
        {"kpi": "No Backlog", "valor": backlog, "unidade": "demandas",
         "descricao": f"{round(backlog/total*100) if total else 0}% aguardando"},
        {"kpi": "Valor Total", "valor": valor_total, "unidade": "R$",
         "descricao": f"R$ {valor_total:,.0f}"},
        {"kpi": "Horas Estimadas", "valor": horas_total, "unidade": "horas",
         "descricao": "Valtech"},
        {"kpi": "Taxa de Conclusão", "valor": taxa, "unidade": "%",
         "descricao": f"{impl} de {total} implementadas"},
    ]

def compute_fases(tasks):
    """Calcula distribuição por fase"""
    fases = Counter(t.get("fase", "01. Backlog") for t in tasks)
    total = len(tasks)
    return [
        {"fase": f, "quantidade": v, "percentual": round(v / total * 100, 1)}
        for f, v in sorted(fases.items())
    ]

def compute_responsaveis(tasks):
    """Calcula métricas por responsável"""
    resp_data = defaultdict(lambda: {
        "total": 0, "implementadas": 0, "alta_prioridade": 0, "valor": 0.0, "horas": 0.0
    })
    for t in tasks:
        r = t.get("resp", "Não atribuído")
        resp_data[r]["total"] += 1
        if t.get("status") == "Implementado":
            resp_data[r]["implementadas"] += 1
        if t.get("pri") == "Alta":
            resp_data[r]["alta_prioridade"] += 1
        resp_data[r]["valor"] += float(t.get("valor", 0) or 0)
        resp_data[r]["horas"] += float(t.get("horas", 0) or 0)

    result = []
    for resp, d in sorted(resp_data.items(), key=lambda x: -x[1]["total"]):
        taxa = round(d["implementadas"] / d["total"] * 100, 1) if d["total"] > 0 else 0
        result.append({
            "responsavel": resp,
            "total": d["total"],
            "implementadas": d["implementadas"],
            "alta_prioridade": d["alta_prioridade"],
            "valor_total": d["valor"],
            "horas_total": d["horas"],
            "taxa_conclusao": taxa,
        })
    return result

# =====================================================================
# POWER BI — PUSH
# =====================================================================
def pbi_headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

def clear_pbi_table(token, table_name):
    """Limpa uma tabela do dataset Power BI"""
    url = f"https://api.powerbi.com/v1.0/myorg/datasets/{PBI_DATASET_ID}/tables/{table_name}/rows"
    r = requests.delete(url, headers=pbi_headers(token), timeout=30)
    if r.status_code in [200, 204]:
        log(f"  Tabela '{table_name}' limpa com sucesso")
    else:
        log(f"  Aviso ao limpar '{table_name}': {r.status_code} - {r.text[:100]}", "WARN")

def push_rows(token, table_name, rows, batch_size=500):
    """Insere linhas em uma tabela do dataset Power BI em lotes"""
    url = f"https://api.powerbi.com/v1.0/myorg/datasets/{PBI_DATASET_ID}/tables/{table_name}/rows"
    total = len(rows)
    inserted = 0
    for i in range(0, total, batch_size):
        batch = rows[i:i + batch_size]
        payload = json.dumps({"rows": batch}, ensure_ascii=False)
        r = requests.post(url, data=payload.encode('utf-8'), headers=pbi_headers(token), timeout=60)
        if r.status_code == 200:
            inserted += len(batch)
            log(f"  Lote {i // batch_size + 1}: {len(batch)} linhas inseridas ({inserted}/{total})")
        else:
            log(f"  ERRO no lote {i // batch_size + 1}: {r.status_code} - {r.text[:200]}", "ERROR")
    return inserted

# =====================================================================
# LOG
# =====================================================================
def save_log(sync_result):
    """Salva log de sincronização"""
    logs = []
    if LOG_FILE.exists():
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            try:
                logs = json.load(f)
            except:
                logs = []
    logs.append(sync_result)
    logs = logs[-30:]  # Manter últimas 30 execuções
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)

# =====================================================================
# MAIN
# =====================================================================
def main():
    start = datetime.now()
    log("=" * 60)
    log("EBL Kanboard → Power BI Sync v2.2 (com fallback robusto)")
    log("=" * 60)

    sync_result = {
        "timestamp": start.strftime("%Y-%m-%d %H:%M:%S"),
        "versao": "v2.2",
        "status": "error",
        "tasks_synced": 0,
        "error": None,
        "data_source": "unknown",
    }

    try:
        # 1. Autenticar no Power BI
        token = get_pbi_token()

        # 2. Buscar dados do Kanboard (com fallback em cascata)
        raw_tasks, data_source = get_all_tasks()
        sync_result["data_source"] = data_source
        log(f"Fonte de dados: {data_source} ({len(raw_tasks)} registros)")

        # 3. Enriquecer / normalizar dados
        if data_source == "kanboard_api":
            excel_map = load_excel_enrichment()
            enriched = enrich_from_api_tasks(raw_tasks, excel_map)
        elif data_source == "data_enriquecido":
            enriched = normalize_enriquecido(raw_tasks)
        else:
            # snapshot bruto — enriquecer com excel_map
            excel_map = load_excel_enrichment()
            enriched = enrich_from_api_tasks(raw_tasks, excel_map)

        log(f"Total de demandas processadas: {len(enriched)}")

        # 4. Calcular métricas
        kpis = compute_kpis(enriched)
        fases = compute_fases(enriched)
        responsaveis = compute_responsaveis(enriched)

        log("\nKPIs calculados:")
        for k in kpis:
            log(f"  {k['kpi']}: {k['valor']} {k['unidade']}")

        # 5. Limpar tabelas existentes no Power BI
        log("\nLimpando tabelas do Power BI...")
        for table in ["Demandas", "KPIs", "Fases", "Responsaveis"]:
            clear_pbi_table(token, table)

        # 6. Inserir dados atualizados em lotes de 500
        log("\nInserindo dados atualizados no Power BI...")
        n_demandas = push_rows(token, "Demandas", enriched)
        n_kpis = push_rows(token, "KPIs", kpis)
        n_fases = push_rows(token, "Fases", fases)
        n_resp = push_rows(token, "Responsaveis", responsaveis)

        # 7. Salvar CSV atualizado
        csv_path = LOCAL_CSV
        with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
            if enriched:
                writer = csv.DictWriter(f, fieldnames=enriched[0].keys(), delimiter=';')
                writer.writeheader()
                writer.writerows(enriched)
        log(f"\nCSV salvo: {csv_path} ({len(enriched)} linhas)")

        elapsed = (datetime.now() - start).total_seconds()
        log(f"\n{'=' * 60}")
        log(f"SYNC CONCLUÍDO em {elapsed:.1f}s")
        log(f"  Fonte: {data_source}")
        log(f"  Demandas: {n_demandas} | KPIs: {n_kpis} | Fases: {n_fases} | Responsáveis: {n_resp}")
        log(f"{'=' * 60}")

        sync_result.update({
            "status": "success",
            "tasks_synced": n_demandas,
            "kpis_synced": n_kpis,
            "fases_synced": n_fases,
            "responsaveis_synced": n_resp,
            "elapsed_seconds": round(elapsed, 1),
        })

    except Exception as e:
        log(f"ERRO CRÍTICO: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        sync_result["error"] = str(e)
        save_log(sync_result)
        sys.exit(1)

    save_log(sync_result)
    return 0

if __name__ == "__main__":
    sys.exit(main())
