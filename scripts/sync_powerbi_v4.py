#!/usr/bin/env python3
"""
EBL Kanboard → Power BI Sync Automático v4
Versão: 4.0 | 2026-04-07

Melhorias em relação à v3:
  - Novo mapeamento de colunas (nova sequência de status)
  - Leitura de metadados do metaMagik (campos do Excel)
  - Token API correto: jsonrpc + token global
  - Projeto ID: 1 (CRM Salesforce)
  - Campos adicionais no CSV e Power BI: subcategoria, área negócio, risco, datas, custos, ROI
"""

import msal, requests, json, csv, sys
from datetime import datetime
from pathlib import Path
from collections import Counter

# ===== CONFIGURAÇÕES =====
KANBOARD_URL   = "http://kanboard.eblsolucoescorp.tec.br/jsonrpc.php"
KANBOARD_TOKEN = "ea99d4c7d96dbad1b1a1defd79f92286884e1902015ff96731ce624e6317"
KANBOARD_AUTH  = ("jsonrpc", KANBOARD_TOKEN)
KANBOARD_PROJ  = 1  # CRM Salesforce

PBI_USERNAME   = "admebl@eblsolucoescorporativas.com"
PBI_PASSWORD   = "Senha@2026"
PBI_TENANT_ID  = "208364c6-eee7-4324-ac4a-d45fe452a1bd"
PBI_CLIENT_ID  = "1950a258-227b-4e31-a9cf-717495945fc2"
PBI_CLIENT_ID2 = "04b07795-8ddb-461a-bbee-02f9e1bf7b46"
PBI_DATASET_ID = "39d50fe5-cde9-4244-b5e5-422a73e8e142"
PBI_SCOPE      = ["https://analysis.windows.net/powerbi/api/.default"]

BASE_DIR  = Path(__file__).parent.parent
CSV_FINAL = BASE_DIR / "powerbi" / "kanboard_dados_final.csv"
LOG_FILE  = BASE_DIR / "powerbi" / "sync_log.json"
SYNC_TS   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# ===== NOVO MAPEAMENTO DE COLUNAS (IDs → Fases) =====
# Sequência: Ideação/POC > Novo > Backlog > Análise TI > Planejamento >
#            Pendente Aprovação > Em Desenvolvimento > Testes > Hypercare >
#            Concluído > On Hold > Cancelado
COLUMN_MAP = {
    "30": "01. Ideação / POC",
    "29": "02. Novo",
    "1":  "03. Backlog",
    "31": "04. Análise TI",
    "32": "05. Planejamento",
    "33": "06. Pendente Aprovação",
    "34": "07. Em Desenvolvimento",
    "35": "08. Testes",
    "36": "09. Hypercare",
    "37": "10. Concluído",
    "38": "11. On Hold",
    "39": "12. Cancelado",
}

FASE_STATUS_MAP = {
    "10. Concluído":  "Concluído",
    "12. Cancelado":  "Cancelado",
    "11. On Hold":    "On Hold",
}

def log(msg, level="INFO"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [{level}] {msg}")

# =====================================================================
# AUTENTICAÇÃO POWER BI
# =====================================================================
def get_pbi_token():
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
                log(f"  Token obtido (client_id={cid[:8]}...)")
                return result["access_token"]
            log(f"  Falhou ({cid[:8]}...): {result.get('error_description','')[:80]}", "WARN")
        except Exception as e:
            log(f"  Erro: {e}", "WARN")
    log("  Power BI inacessível. Continuando com CSV.", "WARN")
    return None

# =====================================================================
# KANBOARD API
# =====================================================================
_req_id = 0

def kanboard_api(method, params=None):
    global _req_id
    _req_id += 1
    payload = {"jsonrpc": "2.0", "method": method, "id": _req_id, "params": params or {}}
    r = requests.post(KANBOARD_URL, json=payload, auth=KANBOARD_AUTH, timeout=15)
    resp = r.json()
    if "error" in resp:
        return None
    return resp.get("result")

def fetch_tasks():
    """Busca todas as tarefas do projeto com metadados"""
    log(f"Buscando tarefas do projeto {KANBOARD_PROJ}...")

    open_tasks   = kanboard_api("getAllTasks", {"project_id": KANBOARD_PROJ, "status_id": 1}) or []
    closed_tasks = kanboard_api("getAllTasks", {"project_id": KANBOARD_PROJ, "status_id": 0}) or []
    all_tasks = open_tasks + closed_tasks
    log(f"  Tarefas: {len(all_tasks)} (abertas: {len(open_tasks)}, fechadas: {len(closed_tasks)})")

    if not all_tasks:
        log("  Nenhuma tarefa encontrada!", "WARN")
        return []

    return all_tasks

def fetch_task_metadata(task_id):
    """Busca metadados de uma tarefa via metaMagik"""
    result = kanboard_api("getTaskMetadata", {"task_id": task_id})
    return result or {}

def enrich_tasks(tasks):
    """Enriquece tarefas com metadados do metaMagik e mapeamento de colunas"""
    log(f"Enriquecendo {len(tasks)} tarefas com metadados...")

    enriched = []
    for i, task in enumerate(tasks, 1):
        task_id = task.get("id")
        col_id  = str(task.get("column_id", ""))
        fase    = COLUMN_MAP.get(col_id, f"?? col={col_id}")

        # Status baseado na fase
        is_closed = task.get("is_active") in ("0", 0)
        status = FASE_STATUS_MAP.get(fase, "Em Andamento" if not is_closed else "Concluído")
        if fase in ("03. Backlog", "01. Ideação / POC", "02. Novo"):
            status = "Backlog"

        # Prioridade
        pri_num = int(task.get("priority", 0) or 0)
        prioridade = "Alta" if pri_num >= 3 else ("Média" if pri_num == 2 else "Normal")

        # Data de vencimento
        due_date = task.get("date_due", "")
        due_str = ""
        if due_date and str(due_date) not in ("0", ""):
            try:
                due_str = datetime.fromtimestamp(int(due_date)).strftime("%d/%m/%Y")
            except:
                pass

        # Responsável
        responsavel = task.get("assignee_name") or task.get("owner_name") or "Não Atribuído"

        # Buscar metadados do metaMagik
        meta = fetch_task_metadata(task_id)

        # Montar registro enriquecido
        record = {
            "id":                    task_id,
            "titulo":                task.get("title", ""),
            "fase":                  fase,
            "status":                status,
            "prioridade":            prioridade,
            "responsavel":           meta.get("responsavel_ti") or responsavel,
            "data_vencimento":       due_str,
            "data_criacao":          datetime.fromtimestamp(
                                        int(task.get("date_creation", 0) or 0)
                                     ).strftime("%Y-%m-%d") if task.get("date_creation") else "",
            # Campos do Excel via metaMagik
            "area_ti":               meta.get("area_ti", "CRM Salesforce"),
            "subcategoria":          meta.get("subcategoria", ""),
            "area_negocio":          meta.get("area_negocio", ""),
            "cherwell_id":           meta.get("cherwell_id", ""),
            "classificacao_risco":   meta.get("classificacao_risco", ""),
            "data_golive_original":  meta.get("data_golive_original", ""),
            "data_golive_estimada":  meta.get("data_golive_estimada", ""),
            "data_inicio_planejado": meta.get("data_inicio_planejado", ""),
            "data_fim_planejado":    meta.get("data_fim_planejado", ""),
            "evolucao_planejado":    meta.get("evolucao_planejado_pct", "0"),
            "evolucao_realizado":    meta.get("evolucao_realizado_pct", "0"),
            "desvio_pct":            meta.get("desvio_pct", ""),
            "recurso_tipo":          meta.get("recurso_tipo", ""),
            "custo_planejado":       meta.get("custo_planejado", "0"),
            "custo_realizado":       meta.get("custo_realizado", "0"),
            "roi_aprovado":          meta.get("roi_aprovado", ""),
            "valor_roi":             meta.get("valor_roi", "0"),
        }
        enriched.append(record)

        if i % 10 == 0:
            log(f"  Processadas {i}/{len(tasks)} tarefas...")

    log(f"  Enriquecimento concluído: {len(enriched)} tarefas")
    return enriched

# =====================================================================
# KPIs E MÉTRICAS
# =====================================================================
def compute_kpis(tasks):
    total = len(tasks)
    concluidas = sum(1 for t in tasks if t["status"] == "Concluído")
    em_andamento = sum(1 for t in tasks if t["status"] == "Em Andamento")
    backlog = sum(1 for t in tasks if t["status"] == "Backlog")
    on_hold = sum(1 for t in tasks if t["status"] == "On Hold")
    canceladas = sum(1 for t in tasks if t["status"] == "Cancelado")
    alta_pri = sum(1 for t in tasks if t["prioridade"] == "Alta")
    custo_plan = sum(int(t.get("custo_planejado", 0) or 0) for t in tasks)
    custo_real = sum(int(t.get("custo_realizado", 0) or 0) for t in tasks)

    return [
        {"kpi": "Total Demandas",       "valor": total,       "unidade": "demandas"},
        {"kpi": "Concluídas",           "valor": concluidas,  "unidade": "demandas"},
        {"kpi": "Em Andamento",         "valor": em_andamento,"unidade": "demandas"},
        {"kpi": "Backlog",              "valor": backlog,     "unidade": "demandas"},
        {"kpi": "On Hold",              "valor": on_hold,     "unidade": "demandas"},
        {"kpi": "Canceladas",           "valor": canceladas,  "unidade": "demandas"},
        {"kpi": "Alta Prioridade",      "valor": alta_pri,    "unidade": "demandas"},
        {"kpi": "% Conclusão",          "valor": round(concluidas/total*100, 1) if total else 0, "unidade": "%"},
        {"kpi": "Custo Planejado Total","valor": custo_plan,  "unidade": "R$"},
        {"kpi": "Custo Realizado Total","valor": custo_real,  "unidade": "R$"},
    ]

def compute_fases(tasks):
    fases = Counter(t["fase"] for t in tasks)
    total = len(tasks)
    return [
        {"fase": f, "quantidade": v, "percentual": round(v/total*100, 1)}
        for f, v in sorted(fases.items())
    ]

def compute_responsaveis(tasks):
    resp = Counter(t["responsavel"] for t in tasks)
    return [
        {"responsavel": r, "quantidade": v}
        for r, v in resp.most_common()
    ]

# =====================================================================
# POWER BI — PUSH
# =====================================================================
def pbi_headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

def pbi_clear_table(token, table_name):
    url = f"https://api.powerbi.com/v1.0/myorg/datasets/{PBI_DATASET_ID}/tables/{table_name}/rows"
    r = requests.delete(url, headers=pbi_headers(token), timeout=30)
    if r.status_code in [200, 204]:
        log(f"  Tabela '{table_name}' limpa")
        return True
    log(f"  Aviso ao limpar '{table_name}': {r.status_code}", "WARN")
    return False

def pbi_push_rows(token, table_name, rows, batch_size=1000):
    url = f"https://api.powerbi.com/v1.0/myorg/datasets/{PBI_DATASET_ID}/tables/{table_name}/rows"
    total = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i+batch_size]
        r = requests.post(url, headers=pbi_headers(token),
                          json={"rows": batch}, timeout=60)
        if r.status_code == 200:
            total += len(batch)
        else:
            log(f"  ERRO lote {i//batch_size+1}: {r.status_code} - {r.text[:150]}", "ERROR")
    log(f"  {total} linhas inseridas em '{table_name}'")
    return total

# =====================================================================
# SALVAR CSV
# =====================================================================
def save_csv(tasks):
    if not tasks:
        return
    fieldnames = list(tasks[0].keys())
    with open(CSV_FINAL, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(tasks)
    log(f"CSV salvo: {CSV_FINAL} ({len(tasks)} linhas)")

# =====================================================================
# MAIN
# =====================================================================
def main():
    start = datetime.now()
    log("=" * 60)
    log("EBL Kanboard → Power BI Sync v4")
    log("=" * 60)

    # 1. Autenticar Power BI
    pbi_token = get_pbi_token()

    # 2. Buscar tarefas do Kanboard
    raw_tasks = fetch_tasks()
    if not raw_tasks:
        log("Sem tarefas para processar!", "ERROR")
        return 1

    # 3. Enriquecer com metadados
    tasks = enrich_tasks(raw_tasks)

    # 4. Calcular KPIs e métricas
    kpis = compute_kpis(tasks)
    fases = compute_fases(tasks)
    responsaveis = compute_responsaveis(tasks)

    log("")
    log("KPIs calculados:")
    for k in kpis:
        log(f"  {k['kpi']}: {k['valor']} {k['unidade']}")

    # 5. Salvar CSV
    save_csv(tasks)

    # 6. Push para Power BI
    pbi_ok = False
    if pbi_token:
        log("")
        log("Enviando dados para o Power BI...")
        pbi_clear_table(pbi_token, "Demandas")
        pbi_clear_table(pbi_token, "KPIs")
        pbi_clear_table(pbi_token, "Fases")
        pbi_clear_table(pbi_token, "Responsaveis")

        pbi_push_rows(pbi_token, "Demandas", tasks)
        pbi_push_rows(pbi_token, "KPIs", kpis)
        pbi_push_rows(pbi_token, "Fases", fases)
        pbi_push_rows(pbi_token, "Responsaveis", responsaveis)
        pbi_ok = True

    # 7. Salvar log
    elapsed = (datetime.now() - start).total_seconds()
    log_entry = {
        "timestamp": SYNC_TS,
        "versao": "v4",
        "tarefas": len(tasks),
        "kpis": len(kpis),
        "fases": len(fases),
        "responsaveis": len(responsaveis),
        "powerbi_ok": pbi_ok,
        "elapsed_s": round(elapsed, 1),
        "status": "success"
    }

    log_data = []
    if LOG_FILE.exists():
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                log_data = json.load(f)
        except:
            pass
    log_data.append(log_entry)
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(log_data[-50:], f, ensure_ascii=False, indent=2)

    log("")
    log("=" * 60)
    log(f"SYNC CONCLUÍDO em {elapsed:.1f}s")
    log(f"  Tarefas: {len(tasks)}")
    log(f"  Power BI: {'✓' if pbi_ok else '✗ (CSV salvo)'}")
    log("=" * 60)
    return 0

if __name__ == "__main__":
    sys.exit(main())
