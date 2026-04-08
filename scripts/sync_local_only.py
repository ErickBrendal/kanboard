#!/usr/bin/env python3
"""
EBL Kanboard → Power BI Sync - Modo Local + Token Browser
Versão: 2.4 | Data: 2026-04-08
- Processa dados locais (Kanboard API ou data_enriquecido.json)
- Tenta autenticação Power BI via token capturado no browser
- Gera CSV e log independente do Power BI
"""

import requests, json, csv, sys
from datetime import datetime
from pathlib import Path
from collections import defaultdict

# ===== CONFIGURAÇÕES =====
KANBOARD_URL   = "http://kanboard.eblsolucoescorp.tec.br/jsonrpc.php"
KANBOARD_TOKEN = "65251ba731c6900a80a8a733ced2aae364cb28172e16df1785b22444124e387f"
KANBOARD_PROJ  = 11

PBI_DATASET_ID = "39d50fe5-cde9-4244-b5e5-422a73e8e142"

BASE_DIR         = Path(__file__).parent.parent
EXCEL_MAP        = BASE_DIR / "powerbi" / "excel_map.json"
LOG_FILE         = BASE_DIR / "powerbi" / "sync_log.json"
LOCAL_SNAPSHOT   = BASE_DIR / "backups" / "snapshot_antes_limpeza.json"
DATA_ENRIQUECIDO = BASE_DIR / "powerbi" / "data_enriquecido.json"
LOCAL_CSV        = BASE_DIR / "powerbi" / "kanboard_dados_final.csv"
TOKEN_FILE       = BASE_DIR / "powerbi" / "pbi_token_browser.json"

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
# KANBOARD API
# =====================================================================
_req_id = 0

def kanboard_api(method, params=None):
    global _req_id
    _req_id += 1
    payload = {"jsonrpc": "2.0", "method": method, "id": _req_id, "params": params or {}}
    headers = {"Content-Type": "application/json", "X-API-Auth": KANBOARD_TOKEN}
    r = requests.post(KANBOARD_URL, json=payload, headers=headers, timeout=20)
    r.raise_for_status()
    resp = r.json()
    if "error" in resp:
        raise Exception(f"Kanboard API error: {resp['error']}")
    return resp.get("result")

def get_all_tasks():
    """Obtém tarefas com fallback em cascata"""
    # Tentativa 1: API ao vivo
    try:
        log("Tentando buscar tarefas do Kanboard via API...")
        open_tasks = kanboard_api("getAllTasks", {"project_id": KANBOARD_PROJ, "status_id": 1}) or []
        log(f"  → {len(open_tasks)} tarefas abertas")
        closed_tasks = kanboard_api("getAllTasks", {"project_id": KANBOARD_PROJ, "status_id": 0}) or []
        log(f"  → {len(closed_tasks)} tarefas fechadas")
        tasks = open_tasks + closed_tasks
        if tasks:
            log(f"Total: {len(tasks)} tarefas obtidas da API Kanboard")
            return tasks, "kanboard_api"
    except Exception as e:
        log(f"API Kanboard indisponível: {e}", "WARN")

    # Tentativa 2: data_enriquecido.json
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
# ENRIQUECIMENTO
# =====================================================================
def load_excel_enrichment():
    if EXCEL_MAP.exists():
        with open(EXCEL_MAP, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def map_phase(column_name):
    phase_map = {
        "Backlog": "01. Backlog", "Refinamento": "02. Refinamento",
        "Priorizada": "03. Priorizada", "Análise": "04. Análise",
        "Estimativa": "05. Estimativa", "Aprovação": "06. Aprovação",
        "Desenvolvimento": "07. Desenvolvimento", "Homologação": "08. Homologação",
        "Deploy": "09. Deploy", "Implementado": "10. Implementado",
        "Cancelado": "11. Cancelado",
    }
    for key, val in phase_map.items():
        if key.lower() in (column_name or "").lower():
            return val
    return column_name or "01. Backlog"

def get_users_map():
    try:
        users = kanboard_api("getAllUsers") or []
        return {str(u["id"]): u.get("name") or u.get("username", "") for u in users}
    except:
        return {
            "1": "admin", "2": "Erick Almeida", "3": "Marcio Souza",
            "4": "Elder Rodrigues", "5": "Felipe Nascimento", "6": "Carlos Almeida"
        }

def enrich_from_api_tasks(tasks, excel_map):
    log("Enriquecendo dados das tarefas (fonte: API)...")
    users_map = get_users_map()
    enriched = []
    for i, task in enumerate(tasks, 1):
        title = task.get("title", "")
        cherwell = rdm = ""
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
            "obs": excel_data.get("obs", ""),
            "valor": float(excel_data.get("valor", 0) or 0),
            "horas": float(excel_data.get("horas", 0) or 0),
            "dev": excel_data.get("dev", ""),
            "aprovado": excel_data.get("aprovado", ""),
            "aprovado_por": excel_data.get("aprovado_por", ""),
            "requisitante": excel_data.get("requisitante", ""),
            "valtech": excel_data.get("valtech", ""),
            "projeto": excel_data.get("projeto", "Salesforce"),
            "data_criacao": created_str,
        })
    return enriched

def normalize_enriquecido(data):
    log("Normalizando dados do data_enriquecido.json...")
    normalized = []
    for i, item in enumerate(data, 1):
        row = dict(item)
        row["seq"] = i
        row["valor"] = float(row.get("valor", 0) or 0)
        row["horas"] = float(row.get("horas", 0) or 0)
        for field in ["cherwell", "rdm", "titulo", "fase", "status", "resp", "area",
                      "tipo", "pri", "golive", "previsao", "obs", "dev", "aprovado",
                      "aprovado_por", "requisitante", "valtech", "projeto"]:
            if field not in row:
                row[field] = ""
            elif row[field] is None:
                row[field] = ""
        normalized.append(row)
    return normalized

# =====================================================================
# KPIs
# =====================================================================
def compute_kpis(enriched):
    total = len(enriched)
    abertas = sum(1 for t in enriched if t.get("status", "") not in ("Implementado", "Cancelado"))
    implementadas = sum(1 for t in enriched if t.get("status", "") == "Implementado")
    canceladas = sum(1 for t in enriched if t.get("status", "") == "Cancelado")
    valor_total = sum(float(t.get("valor", 0) or 0) for t in enriched)
    horas_total = sum(float(t.get("horas", 0) or 0) for t in enriched)
    alta_pri = sum(1 for t in enriched if t.get("pri", "") == "Alta")
    perc_impl = round(implementadas / total * 100, 1) if total > 0 else 0

    return [
        {"kpi": "Total de Demandas", "valor": total, "unidade": "demandas"},
        {"kpi": "Demandas Abertas", "valor": abertas, "unidade": "demandas"},
        {"kpi": "Implementadas", "valor": implementadas, "unidade": "demandas"},
        {"kpi": "Canceladas", "valor": canceladas, "unidade": "demandas"},
        {"kpi": "% Implementado", "valor": perc_impl, "unidade": "%"},
        {"kpi": "Valor Total", "valor": round(valor_total, 2), "unidade": "R$"},
        {"kpi": "Horas Totais", "valor": round(horas_total, 1), "unidade": "h"},
        {"kpi": "Alta Prioridade", "valor": alta_pri, "unidade": "demandas"},
    ]

def compute_fases(enriched):
    counter = defaultdict(int)
    for t in enriched:
        counter[t.get("fase", "Sem Fase")] += 1
    total_geral = len(enriched)
    return [
        {
            "fase": k,
            "quantidade": v,
            "percentual": round(v / total_geral * 100, 1) if total_geral > 0 else 0
        }
        for k, v in sorted(counter.items())
    ]

def compute_responsaveis(enriched):
    data = defaultdict(lambda: {"total": 0, "abertas": 0, "implementadas": 0, "valor": 0.0, "horas": 0.0})
    for t in enriched:
        resp = t.get("resp", "Não atribuído") or "Não atribuído"
        data[resp]["total"] += 1
        if t.get("status") == "Implementado":
            data[resp]["implementadas"] += 1
        elif t.get("status") != "Cancelado":
            data[resp]["abertas"] += 1
        data[resp]["valor"] += float(t.get("valor", 0) or 0)
        data[resp]["horas"] += float(t.get("horas", 0) or 0)
    return [
        {
            "responsavel": k,
            "total": v["total"],
            "implementadas": v["implementadas"],
        }
        for k, v in sorted(data.items(), key=lambda x: -x[1]["total"])
    ]

# =====================================================================
# POWER BI API
# =====================================================================
def get_pbi_token_from_browser():
    """Tenta obter token Power BI capturado via browser"""
    # Verificar arquivo de token do browser
    if TOKEN_FILE.exists():
        try:
            with open(TOKEN_FILE) as f:
                data = json.load(f)
            token = data.get("access_token", "")
            if token:
                log("  Token do browser encontrado, verificando validade...")
                test_url = f"https://api.powerbi.com/v1.0/myorg/datasets/{PBI_DATASET_ID}"
                r = requests.get(test_url, headers={"Authorization": f"Bearer {token}"}, timeout=10)
                if r.status_code == 200:
                    log("  Token válido!")
                    return token
                else:
                    log(f"  Token expirado (HTTP {r.status_code})", "WARN")
        except Exception as e:
            log(f"  Erro ao ler token do browser: {e}", "WARN")
    return None

def pbi_headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8",
    }

def clear_pbi_table(token, table_name):
    url = f"https://api.powerbi.com/v1.0/myorg/datasets/{PBI_DATASET_ID}/tables/{table_name}/rows"
    r = requests.delete(url, headers=pbi_headers(token), timeout=30)
    if r.status_code == 200:
        log(f"  Tabela '{table_name}' limpa com sucesso")
    else:
        log(f"  Aviso ao limpar '{table_name}': {r.status_code} - {r.text[:100]}", "WARN")

def push_rows(token, table_name, rows, batch_size=500):
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
    logs = []
    if LOG_FILE.exists():
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            try:
                logs = json.load(f)
            except:
                logs = []
    logs.append(sync_result)
    logs = logs[-30:]
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)

# =====================================================================
# MAIN
# =====================================================================
def main():
    start = datetime.now()
    log("=" * 60)
    log("EBL Kanboard → Power BI Sync v2.4 (Local + Token Browser)")
    log("=" * 60)

    sync_result = {
        "timestamp": start.strftime("%Y-%m-%d %H:%M:%S"),
        "versao": "v2.4",
        "status": "partial",
        "tasks_synced": 0,
        "error": None,
        "data_source": "unknown",
        "powerbi_status": "skipped",
    }

    try:
        # 1. Buscar dados do Kanboard (com fallback)
        raw_tasks, data_source = get_all_tasks()
        sync_result["data_source"] = data_source
        log(f"Fonte de dados: {data_source} ({len(raw_tasks)} registros)")

        # 2. Enriquecer / normalizar dados
        if data_source == "kanboard_api":
            excel_map = load_excel_enrichment()
            enriched = enrich_from_api_tasks(raw_tasks, excel_map)
        elif data_source == "data_enriquecido":
            enriched = normalize_enriquecido(raw_tasks)
        else:
            excel_map = load_excel_enrichment()
            enriched = enrich_from_api_tasks(raw_tasks, excel_map)

        log(f"Total de demandas processadas: {len(enriched)}")

        # 3. Calcular métricas
        kpis = compute_kpis(enriched)
        fases = compute_fases(enriched)
        responsaveis = compute_responsaveis(enriched)

        log("\nKPIs calculados:")
        for k in kpis:
            log(f"  {k['kpi']}: {k['valor']} {k['unidade']}")

        log("\nDistribuição por Fase:")
        for f in fases:
            log(f"  {f['fase']}: {f['quantidade']} demandas")

        log("\nTop Responsáveis:")
        for r in responsaveis[:5]:
            log(f"  {r['responsavel']}: {r['total']} demandas (impl: {r['implementadas']})")

        # 4. Salvar CSV atualizado (independente do Power BI)
        with open(LOCAL_CSV, 'w', newline='', encoding='utf-8-sig') as f:
            if enriched:
                writer = csv.DictWriter(f, fieldnames=enriched[0].keys(), delimiter=';')
                writer.writeheader()
                writer.writerows(enriched)
        log(f"\nCSV salvo: {LOCAL_CSV} ({len(enriched)} linhas)")
        sync_result["tasks_synced"] = len(enriched)

        # 5. Tentar Power BI com token do browser
        log("\nTentando autenticação Power BI via token do browser...")
        token = get_pbi_token_from_browser()

        if token:
            log("Token Power BI disponível! Sincronizando...")

            # Limpar tabelas
            log("\nLimpando tabelas do Power BI...")
            for table in ["Demandas", "KPIs", "Fases", "Responsaveis"]:
                clear_pbi_table(token, table)

            # Preparar dados para inserção (remover campos não existentes no dataset)
            DEMANDAS_FIELDS = ["seq", "cherwell", "rdm", "titulo", "fase", "status", "resp",
                               "area", "tipo", "pri", "golive", "previsao", "obs", "valor",
                               "horas", "dev", "aprovado", "aprovado_por", "requisitante",
                               "valtech", "data_criacao", "task_id", "sync_at"]
            enriched_clean = []
            sync_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for row in enriched:
                clean = {k: row.get(k) for k in DEMANDAS_FIELDS if k in row or k in ("task_id", "sync_at")}
                clean["sync_at"] = sync_at
                clean["task_id"] = row.get("task_id", row.get("seq", 0))
                # Remover campos None para evitar erros
                clean = {k: v for k, v in clean.items() if v is not None}
                enriched_clean.append(clean)

            # Inserir dados
            log("\nInserindo dados atualizados no Power BI...")
            n_demandas = push_rows(token, "Demandas", enriched_clean)
            n_kpis = push_rows(token, "KPIs", kpis)
            n_fases = push_rows(token, "Fases", fases)
            n_resp = push_rows(token, "Responsaveis", responsaveis)

            sync_result.update({
                "status": "success",
                "powerbi_status": "synced",
                "kpis_synced": n_kpis,
                "fases_synced": n_fases,
                "responsaveis_synced": n_resp,
            })
            log(f"\nPower BI: Demandas={n_demandas} | KPIs={n_kpis} | Fases={n_fases} | Resp={n_resp}")
        else:
            log("Token Power BI não disponível. Dados processados localmente.", "WARN")
            log("Para sincronizar com Power BI, complete a autenticação MFA e execute novamente.", "WARN")
            sync_result.update({
                "status": "partial_csv_only",
                "powerbi_status": "auth_required_mfa",
            })

        elapsed = (datetime.now() - start).total_seconds()
        log(f"\n{'=' * 60}")
        log(f"PROCESSAMENTO CONCLUÍDO em {elapsed:.1f}s")
        log(f"  Fonte: {data_source}")
        log(f"  Demandas processadas: {len(enriched)}")
        log(f"  Power BI: {sync_result['powerbi_status']}")
        log(f"  CSV: {LOCAL_CSV}")
        log(f"{'=' * 60}")

        sync_result["elapsed_seconds"] = round(elapsed, 1)

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
