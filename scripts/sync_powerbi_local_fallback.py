#!/usr/bin/env python3
"""
EBL Kanboard → Power BI Sync Automático (com fallback para dados locais)
Executa diariamente via cron/GitHub Actions
Versão: 2.1 | Adaptado em: 2026-04-02
"""

import msal, requests, json, csv, sys, os
from datetime import datetime, timezone
from pathlib import Path

# ===== CONFIGURAÇÕES =====
KANBOARD_URL   = "http://kanboard.eblsolucoescorp.tec.br/jsonrpc.php"
KANBOARD_USER  = "admin"
KANBOARD_TOKEN = "a43a8785a4487979964cd7e12fc8c56bbb6ef7a6fa64bcb6c45fa1afc6ff"
KANBOARD_PROJ  = 11  # [SF] Fast Track — Salesforce

PBI_USERNAME   = "admebl@eblsolucoescorporativas.com"
PBI_PASSWORD   = "Senha@2026"
PBI_TENANT_ID  = "208364c6-eee7-4324-ac4a-d45fe452a1bd"
PBI_CLIENT_ID  = "1950a258-227b-4e31-a9cf-717495945fc2"
PBI_DATASET_ID = "39d50fe5-cde9-4244-b5e5-422a73e8e142"
PBI_SCOPE      = ["https://analysis.windows.net/powerbi/api/.default"]

BASE_DIR = Path(__file__).parent.parent
EXCEL_MAP = BASE_DIR / "powerbi" / "excel_map.json"
LOG_FILE  = BASE_DIR / "powerbi" / "sync_log.json"
LOCAL_SNAPSHOT = BASE_DIR / "backups" / "snapshot_antes_limpeza.json"
LOCAL_CSV = BASE_DIR / "powerbi" / "kanboard_dados_final.csv"

def log(msg, level="INFO"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [{level}] {msg}")

def get_pbi_token():
    """Obtém token de acesso ao Power BI via MSAL"""
    log("Autenticando no Power BI Service...")
    app = msal.PublicClientApplication(PBI_CLIENT_ID, authority=f"https://login.microsoftonline.com/{PBI_TENANT_ID}")
    result = app.acquire_token_by_username_password(PBI_USERNAME, PBI_PASSWORD, scopes=PBI_SCOPE)
    if "access_token" not in result:
        raise Exception(f"Falha na autenticação Power BI: {result.get('error_description','')}")
    log("Token Power BI obtido com sucesso!")
    return result["access_token"]

def kanboard_api(method, params=None):
    """Chama a API JSON-RPC do Kanboard"""
    payload = {"jsonrpc": "2.0", "method": method, "id": 1, "params": params or {}}
    r = requests.post(KANBOARD_URL, json=payload, auth=(KANBOARD_USER, KANBOARD_TOKEN), timeout=30)
    r.raise_for_status()
    return r.json().get("result")

def get_all_tasks():
    """Busca todas as tarefas do projeto (abertas e fechadas) com fallback para dados locais"""
    try:
        log("Tentando buscar tarefas do Kanboard via API...")
        open_tasks = kanboard_api("getAllTasks", {"project_id": KANBOARD_PROJ, "status_id": 1}) or []
        log(f"  → {len(open_tasks)} tarefas abertas")
        
        closed_tasks = kanboard_api("getAllTasks", {"project_id": KANBOARD_PROJ, "status_id": 0}) or []
        log(f"  → {len(closed_tasks)} tarefas fechadas")
        
        all_tasks = open_tasks + closed_tasks
        log(f"Total: {len(all_tasks)} tarefas obtidas da API")
        return all_tasks
    except Exception as e:
        log(f"Erro ao acessar API Kanboard: {e}", "WARN")
        log("Usando dados locais como fallback...", "WARN")
        
        # Carregar snapshot local
        if LOCAL_SNAPSHOT.exists():
            with open(LOCAL_SNAPSHOT, 'r', encoding='utf-8') as f:
                tasks = json.load(f)
            log(f"  → {len(tasks)} tarefas carregadas do snapshot local")
            return tasks
        else:
            raise Exception("Nenhuma fonte de dados disponível (API offline e sem snapshot local)")

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
    }
    for key, val in phase_map.items():
        if key.lower() in (column_name or "").lower():
            return val
    return column_name or "01. Backlog"

def get_column_name(task, columns_cache):
    """Obtém o nome da coluna de uma tarefa"""
    col_id = str(task.get("column_id", ""))
    if col_id in columns_cache:
        return columns_cache[col_id]
    return "Backlog"

def get_columns_cache():
    """Obtém cache de colunas (com fallback para mapeamento local)"""
    try:
        columns = kanboard_api("getColumns", {"project_id": KANBOARD_PROJ}) or []
        return {str(c["id"]): c["title"] for c in columns}
    except:
        log("Usando mapeamento de colunas local (powerbi_config.json)", "WARN")
        # Carregar mapeamento completo do powerbi_config.json
        try:
            pbi_conf = BASE_DIR / "powerbi" / "powerbi_config.json"
            with open(pbi_conf, 'r', encoding='utf-8') as f:
                conf_data = json.load(f)
            col_map = conf_data.get('kanboard_powerbi_config', {}).get('mapeamento_colunas', {})
            if col_map:
                log(f"  → {len(col_map)} colunas carregadas do powerbi_config.json")
                return col_map
        except Exception as e:
            log(f"  Erro ao carregar powerbi_config.json: {e}", "WARN")
        # Fallback hardcoded com mapeamento completo
        return {
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

def get_users_map():
    """Obtém mapeamento de usuários (com fallback)"""
    try:
        users = kanboard_api("getAllUsers") or []
        return {str(u["id"]): u.get("name") or u.get("username","") for u in users}
    except:
        log("Usando mapeamento de usuários local", "WARN")
        return {
            "1": "admin", "2": "Erick Almeida", "3": "Marcio Souza",
            "4": "Elder Rodrigues", "5": "Felipe Nascimento", "6": "Carlos Almeida"
        }

def enrich_tasks(tasks, excel_map):
    """Enriquece as tarefas com dados do Excel e normaliza campos"""
    log("Enriquecendo dados das tarefas...")
    
    columns_cache = get_columns_cache()
    users_map = get_users_map()
    
    enriched = []
    for i, task in enumerate(tasks, 1):
        title = task.get("title", "")
        cherwell = ""
        rdm = ""
        
        # Extrair Cherwell e RDM do título
        parts = title.split(" - ", 2)
        if len(parts) >= 2:
            cherwell = parts[0].strip()
            rdm = parts[1].strip() if len(parts) > 2 else ""
            titulo = parts[-1].strip()
        else:
            titulo = title
        
        # Buscar enriquecimento do Excel
        excel_data = excel_map.get(cherwell, {})
        
        # Coluna/fase
        col_name = get_column_name(task, columns_cache)
        fase = map_phase(col_name)
        
        # Status
        is_closed = task.get("is_active") == "0" or task.get("is_active") == 0
        status = "Implementado" if is_closed or "Implementado" in col_name else "Aberta"
        
        # Responsável
        owner_id = str(task.get("owner_id", ""))
        resp = users_map.get(owner_id, excel_data.get("resp", "Não atribuído"))
        
        # Prioridade
        pri_num = int(task.get("priority", 0) or 0)
        if pri_num >= 3:
            pri = "Alta"
        elif pri_num == 2:
            pri = "Média"
        else:
            pri = excel_data.get("pri", "Média")
        
        # Datas
        due_date = task.get("date_due", "")
        if due_date and str(due_date) != "0":
            try:
                due_dt = datetime.fromtimestamp(int(due_date))
                due_str = due_dt.strftime("%d/%m/%Y")
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
            "cherwell": cherwell or f"KB-{task.get('id','')}",
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

def clear_pbi_table(token, table_name):
    """Limpa uma tabela do dataset Power BI"""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    url = f"https://api.powerbi.com/v1.0/myorg/datasets/{PBI_DATASET_ID}/tables/{table_name}/rows"
    r = requests.delete(url, headers=headers)
    if r.status_code in [200, 204]:
        log(f"  Tabela '{table_name}' limpa com sucesso")
    else:
        log(f"  Aviso ao limpar '{table_name}': {r.status_code} - {r.text[:100]}", "WARN")

def push_rows(token, table_name, rows, batch_size=500):
    """Insere linhas em uma tabela do dataset Power BI em lotes"""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    url = f"https://api.powerbi.com/v1.0/myorg/datasets/{PBI_DATASET_ID}/tables/{table_name}/rows"
    
    total = len(rows)
    inserted = 0
    for i in range(0, total, batch_size):
        batch = rows[i:i+batch_size]
        payload = json.dumps({"rows": batch}, ensure_ascii=False)
        r = requests.post(url, data=payload.encode('utf-8'), headers=headers)
        if r.status_code == 200:
            inserted += len(batch)
            log(f"  Lote {i//batch_size+1}: {len(batch)} linhas inseridas ({inserted}/{total})")
        else:
            log(f"  ERRO no lote {i//batch_size+1}: {r.status_code} - {r.text[:200]}", "ERROR")
    return inserted

def compute_kpis(tasks):
    """Calcula KPIs executivos"""
    total = len(tasks)
    impl = sum(1 for t in tasks if t["status"] == "Implementado")
    alta = sum(1 for t in tasks if t["pri"] == "Alta")
    backlog = sum(1 for t in tasks if t["fase"] == "01. Backlog")
    andamento = sum(1 for t in tasks if t["fase"] in ["02. Refinamento","06. Aprovação","07. Desenvolvimento","09. Deploy"])
    valor_total = sum(t["valor"] for t in tasks)
    horas_total = sum(t["horas"] for t in tasks)
    taxa = round(impl/total*100, 1) if total > 0 else 0
    
    return [
        {"kpi": "Total de Demandas", "valor": total, "unidade": "demandas", "descricao": "Base Fast Track Outubro"},
        {"kpi": "Implementadas", "valor": impl, "unidade": "demandas", "descricao": f"{taxa}% de conclusão"},
        {"kpi": "Em Andamento", "valor": andamento, "unidade": "demandas", "descricao": "Refin + Aprov + Dev + Deploy"},
        {"kpi": "Alta Prioridade", "valor": alta, "unidade": "demandas", "descricao": "Atenção imediata"},
        {"kpi": "No Backlog", "valor": backlog, "unidade": "demandas", "descricao": f"{round(backlog/total*100)}% aguardando"},
        {"kpi": "Valor Total", "valor": valor_total, "unidade": "R$", "descricao": f"R$ {valor_total:,.0f}"},
        {"kpi": "Horas Estimadas", "valor": horas_total, "unidade": "horas", "descricao": "Valtech"},
        {"kpi": "Taxa de Conclusão", "valor": taxa, "unidade": "%", "descricao": f"{impl} de {total} implementadas"},
    ]

def compute_fases(tasks):
    """Calcula distribuição por fase"""
    from collections import Counter
    fases = Counter(t["fase"] for t in tasks)
    total = len(tasks)
    return [{"fase": f, "quantidade": v, "percentual": round(v/total*100, 1)} for f, v in sorted(fases.items())]

def compute_responsaveis(tasks):
    """Calcula métricas por responsável"""
    from collections import defaultdict
    resp_data = defaultdict(lambda: {"total":0,"implementadas":0,"alta_prioridade":0,"valor":0,"horas":0})
    for t in tasks:
        r = t["resp"]
        resp_data[r]["total"] += 1
        if t["status"] == "Implementado":
            resp_data[r]["implementadas"] += 1
        if t["pri"] == "Alta":
            resp_data[r]["alta_prioridade"] += 1
        resp_data[r]["valor"] += t["valor"]
        resp_data[r]["horas"] += t["horas"]
    
    result = []
    for resp, d in sorted(resp_data.items(), key=lambda x: -x[1]["total"]):
        taxa = round(d["implementadas"]/d["total"]*100, 1) if d["total"] > 0 else 0
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

def save_log(sync_result):
    """Salva log de sincronização"""
    logs = []
    if LOG_FILE.exists():
        with open(LOG_FILE, 'r') as f:
            try:
                logs = json.load(f)
            except:
                logs = []
    
    logs.append(sync_result)
    logs = logs[-30:]  # Manter últimas 30 execuções
    
    with open(LOG_FILE, 'w') as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)

def main():
    start = datetime.now()
    log("=" * 60)
    log("EBL Kanboard → Power BI Sync Iniciado (com fallback local)")
    log("=" * 60)
    
    sync_result = {
        "timestamp": start.isoformat(),
        "status": "error",
        "tasks_synced": 0,
        "error": None,
        "data_source": "unknown",
    }
    
    try:
        # 1. Autenticar no Power BI
        token = get_pbi_token()
        
        # 2. Buscar dados do Kanboard (com fallback)
        tasks = get_all_tasks()
        sync_result["data_source"] = "kanboard_api" if len(tasks) > 97 else "local_snapshot"
        
        # 3. Enriquecer com dados do Excel
        excel_map = load_excel_enrichment()
        enriched = enrich_tasks(tasks, excel_map)
        
        # 4. Calcular métricas
        kpis = compute_kpis(enriched)
        fases = compute_fases(enriched)
        responsaveis = compute_responsaveis(enriched)
        
        # 5. Limpar tabelas existentes
        log("\nLimpando tabelas do Power BI...")
        for table in ["Demandas", "KPIs", "Fases", "Responsaveis"]:
            clear_pbi_table(token, table)
        
        # 6. Inserir dados atualizados
        log("\nInserindo dados atualizados no Power BI...")
        n_demandas = push_rows(token, "Demandas", enriched)
        n_kpis = push_rows(token, "KPIs", kpis)
        n_fases = push_rows(token, "Fases", fases)
        n_resp = push_rows(token, "Responsaveis", responsaveis)
        
        # 7. Salvar CSV atualizado
        csv_path = BASE_DIR / "powerbi" / "kanboard_dados_final.csv"
        with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
            if enriched:
                writer = csv.DictWriter(f, fieldnames=enriched[0].keys(), delimiter=';')
                writer.writeheader()
                writer.writerows(enriched)
        log(f"\nCSV atualizado: {csv_path}")
        
        elapsed = (datetime.now() - start).total_seconds()
        log(f"\n{'='*60}")
        log(f"SYNC CONCLUÍDO em {elapsed:.1f}s")
        log(f"  Fonte: {sync_result['data_source']}")
        log(f"  Demandas: {n_demandas} | KPIs: {n_kpis} | Fases: {n_fases} | Responsáveis: {n_resp}")
        log(f"{'='*60}")
        
        sync_result.update({
            "status": "success",
            "tasks_synced": n_demandas,
            "elapsed_seconds": elapsed,
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
