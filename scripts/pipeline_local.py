#!/usr/bin/env python3
"""
EBL Kanboard Pipeline Local
Busca tarefas, enriquece com Excel, calcula KPIs e salva resultados.
O token Power BI é obtido separadamente e passado como argumento.
"""

import requests, json, csv, sys, os
from datetime import datetime
from pathlib import Path
from collections import Counter, defaultdict

# ===== CONFIGURAÇÕES =====
KANBOARD_URL   = "http://kanboard.eblsolucoescorp.tec.br/jsonrpc.php"
KANBOARD_TOKEN = "65251ba731c6900a80a8a733ced2aae364cb28172e16df1785b22444124e387f"
KANBOARD_USER  = "admin"
KANBOARD_PASS  = "Senha@2026"
KANBOARD_PROJ  = 11

PBI_DATASET_ID = "39d50fe5-cde9-4244-b5e5-422a73e8e142"

BASE_DIR         = Path(__file__).parent.parent
EXCEL_MAP        = BASE_DIR / "powerbi" / "excel_map.json"
LOG_FILE         = BASE_DIR / "powerbi" / "sync_log.json"
LOCAL_SNAPSHOT   = BASE_DIR / "backups" / "snapshot_antes_limpeza.json"
DATA_ENRIQUECIDO = BASE_DIR / "powerbi" / "data_enriquecido.json"
LOCAL_CSV        = BASE_DIR / "powerbi" / "kanboard_dados_final.csv"
PIPELINE_OUT     = BASE_DIR / "powerbi" / "pipeline_result.json"

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

def kanboard_api(method, params=None, use_basic=False):
    global _req_id
    _req_id += 1
    payload = {"jsonrpc": "2.0", "method": method, "id": _req_id, "params": params or {}}
    if use_basic:
        r = requests.post(KANBOARD_URL, json=payload,
                          auth=("jsonrpc", KANBOARD_TOKEN), timeout=20)
    else:
        headers = {"Content-Type": "application/json", "X-API-Auth": KANBOARD_TOKEN}
        r = requests.post(KANBOARD_URL, json=payload, headers=headers, timeout=20)
    r.raise_for_status()
    resp = r.json()
    if "error" in resp:
        raise Exception(f"Kanboard API error: {resp['error']}")
    return resp.get("result")

def get_all_tasks_from_api():
    log("Tentando buscar tarefas via API (X-API-Auth header)...")
    try:
        open_tasks = kanboard_api("getAllTasks", {"project_id": KANBOARD_PROJ, "status_id": 1}) or []
        log(f"  → {len(open_tasks)} tarefas abertas")
        closed_tasks = kanboard_api("getAllTasks", {"project_id": KANBOARD_PROJ, "status_id": 0}) or []
        log(f"  → {len(closed_tasks)} tarefas fechadas")
        return open_tasks + closed_tasks
    except Exception as e:
        log(f"  X-API-Auth falhou: {e}", "WARN")

    log("Tentando via Basic Auth (jsonrpc:token)...")
    try:
        open_tasks = kanboard_api("getAllTasks", {"project_id": KANBOARD_PROJ, "status_id": 1}, use_basic=True) or []
        log(f"  → {len(open_tasks)} tarefas abertas")
        closed_tasks = kanboard_api("getAllTasks", {"project_id": KANBOARD_PROJ, "status_id": 0}, use_basic=True) or []
        log(f"  → {len(closed_tasks)} tarefas fechadas")
        return open_tasks + closed_tasks
    except Exception as e:
        log(f"  Basic Auth falhou: {e}", "WARN")

    log("Tentando via Basic Auth (admin:senha)...")
    try:
        payload_open = {"jsonrpc": "2.0", "method": "getAllTasks", "id": 1,
                        "params": {"project_id": KANBOARD_PROJ, "status_id": 1}}
        r = requests.post(KANBOARD_URL, json=payload_open,
                          auth=(KANBOARD_USER, KANBOARD_PASS), timeout=20)
        open_tasks = r.json().get("result") or []
        payload_closed = {"jsonrpc": "2.0", "method": "getAllTasks", "id": 2,
                          "params": {"project_id": KANBOARD_PROJ, "status_id": 0}}
        r2 = requests.post(KANBOARD_URL, json=payload_closed,
                           auth=(KANBOARD_USER, KANBOARD_PASS), timeout=20)
        closed_tasks = r2.json().get("result") or []
        log(f"  → {len(open_tasks)} abertas + {len(closed_tasks)} fechadas via admin:senha")
        return open_tasks + closed_tasks
    except Exception as e:
        log(f"  admin:senha falhou: {e}", "WARN")

    return []

def get_all_tasks():
    tasks = get_all_tasks_from_api()
    if tasks:
        log(f"Total: {len(tasks)} tarefas obtidas da API Kanboard")
        return tasks, "kanboard_api"

    if DATA_ENRIQUECIDO.exists():
        log("Usando data_enriquecido.json como fonte de dados...", "WARN")
        with open(DATA_ENRIQUECIDO, 'r', encoding='utf-8') as f:
            data = json.load(f)
        log(f"  → {len(data)} tarefas carregadas do data_enriquecido.json")
        return data, "data_enriquecido"

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
    log("Normalizando dados do data_enriquecido.json...")
    sync_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    normalized = []
    for i, d in enumerate(data, 1):
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
# KPIs
# =====================================================================
def compute_kpis(tasks):
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
        {"kpi": "Total de Demandas", "valor": total, "unidade": "demandas", "descricao": "Base Fast Track Salesforce"},
        {"kpi": "Implementadas", "valor": impl, "unidade": "demandas", "descricao": f"{taxa}% de conclusão"},
        {"kpi": "Em Andamento", "valor": andamento, "unidade": "demandas", "descricao": "Refin + Aprov + Dev + Deploy"},
        {"kpi": "Alta Prioridade", "valor": alta, "unidade": "demandas", "descricao": "Atenção imediata"},
        {"kpi": "No Backlog", "valor": backlog, "unidade": "demandas", "descricao": f"{round(backlog/total*100) if total else 0}% aguardando"},
        {"kpi": "Valor Total", "valor": valor_total, "unidade": "R$", "descricao": f"R$ {valor_total:,.0f}"},
        {"kpi": "Horas Estimadas", "valor": horas_total, "unidade": "horas", "descricao": "Valtech"},
        {"kpi": "Taxa de Conclusão", "valor": taxa, "unidade": "%", "descricao": f"{impl} de {total} implementadas"},
    ]

def compute_fases(tasks):
    fases = Counter(t.get("fase", "01. Backlog") for t in tasks)
    total = len(tasks)
    return [
        {"fase": f, "quantidade": v, "percentual": round(v / total * 100, 1)}
        for f, v in sorted(fases.items())
    ]

def compute_responsaveis(tasks):
    resp_data = defaultdict(lambda: {"total": 0, "implementadas": 0, "alta_prioridade": 0, "valor": 0.0, "horas": 0.0})
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
            "responsavel": resp, "total": d["total"], "implementadas": d["implementadas"],
            "alta_prioridade": d["alta_prioridade"], "valor_total": d["valor"],
            "horas_total": d["horas"], "taxa_conclusao": taxa,
        })
    return result

# =====================================================================
# POWER BI PUSH (com token externo)
# =====================================================================
def pbi_headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

def clear_pbi_table(token, table_name):
    url = f"https://api.powerbi.com/v1.0/myorg/datasets/{PBI_DATASET_ID}/tables/{table_name}/rows"
    r = requests.delete(url, headers=pbi_headers(token), timeout=30)
    if r.status_code in [200, 204]:
        log(f"  Tabela '{table_name}' limpa com sucesso")
        return True
    else:
        log(f"  Aviso ao limpar '{table_name}': {r.status_code} - {r.text[:200]}", "WARN")
        return False

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
    log(f"Log salvo em {LOG_FILE}")

# =====================================================================
# MAIN
# =====================================================================
def main():
    start = datetime.now()
    log("=" * 60)
    log("EBL Kanboard Pipeline Local v1.0")
    log("=" * 60)

    # Verificar se token foi passado como argumento
    pbi_token = None
    token_file = "/tmp/pbi_token.json"
    if os.path.exists(token_file):
        with open(token_file) as f:
            pbi_token = json.load(f).get("access_token")
        log(f"Token Power BI carregado de {token_file}")
    elif len(sys.argv) > 1:
        pbi_token = sys.argv[1]
        log("Token Power BI recebido via argumento")

    sync_result = {
        "timestamp": start.strftime("%Y-%m-%d %H:%M:%S"),
        "versao": "pipeline_local_v1.0",
        "status": "error",
        "tasks_synced": 0,
        "error": None,
        "data_source": "unknown",
        "pbi_sync": False,
    }

    try:
        # 1. Buscar dados do Kanboard
        raw_tasks, data_source = get_all_tasks()
        sync_result["data_source"] = data_source
        log(f"Fonte de dados: {data_source} ({len(raw_tasks)} registros)")

        # 2. Enriquecer / normalizar
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

        # 4. Salvar resultado do pipeline para uso posterior
        pipeline_data = {
            "enriched": enriched,
            "kpis": kpis,
            "fases": fases,
            "responsaveis": responsaveis,
            "data_source": data_source,
            "timestamp": start.strftime("%Y-%m-%d %H:%M:%S"),
        }
        with open(PIPELINE_OUT, 'w', encoding='utf-8') as f:
            json.dump(pipeline_data, f, ensure_ascii=False, indent=2)
        log(f"Dados do pipeline salvos em {PIPELINE_OUT}")

        # 5. Salvar CSV
        with open(LOCAL_CSV, 'w', newline='', encoding='utf-8-sig') as f:
            if enriched:
                writer = csv.DictWriter(f, fieldnames=enriched[0].keys(), delimiter=';')
                writer.writeheader()
                writer.writerows(enriched)
        log(f"CSV salvo: {LOCAL_CSV} ({len(enriched)} linhas)")

        # 6. Push para Power BI (se token disponível)
        n_demandas = n_kpis = n_fases = n_resp = 0
        if pbi_token:
            log("\nToken Power BI disponível — iniciando push...")
            for table in ["Demandas", "KPIs", "Fases", "Responsaveis"]:
                clear_pbi_table(pbi_token, table)
            n_demandas = push_rows(pbi_token, "Demandas", enriched)
            n_kpis = push_rows(pbi_token, "KPIs", kpis)
            n_fases = push_rows(pbi_token, "Fases", fases)
            n_resp = push_rows(pbi_token, "Responsaveis", responsaveis)
            sync_result["pbi_sync"] = True
            log(f"Power BI: Demandas={n_demandas} | KPIs={n_kpis} | Fases={n_fases} | Resp={n_resp}")
        else:
            log("Token Power BI não disponível — dados salvos localmente apenas.", "WARN")

        elapsed = (datetime.now() - start).total_seconds()
        log(f"\n{'='*60}")
        log(f"PIPELINE CONCLUÍDO em {elapsed:.1f}s")
        log(f"  Fonte: {data_source} | Demandas: {len(enriched)}")
        log(f"  CSV: {LOCAL_CSV}")
        log(f"{'='*60}")

        sync_result.update({
            "status": "success",
            "tasks_synced": len(enriched),
            "kpis_count": len(kpis),
            "fases_count": len(fases),
            "responsaveis_count": len(responsaveis),
            "elapsed_seconds": round(elapsed, 1),
            "pbi_demandas": n_demandas,
            "pbi_kpis": n_kpis,
            "pbi_fases": n_fases,
            "pbi_responsaveis": n_resp,
        })

    except Exception as e:
        log(f"ERRO CRÍTICO: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        sync_result["error"] = str(e)

    save_log(sync_result)
    return 0 if sync_result["status"] == "success" else 1

if __name__ == "__main__":
    sys.exit(main())
