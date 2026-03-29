#!/usr/bin/env python3
"""
EBL Kanboard → Power BI Sync — Versão GitHub Actions
Lê credenciais de variáveis de ambiente (secrets do GitHub)
"""

import msal, requests, json, csv, sys, os
from datetime import datetime
from pathlib import Path
from collections import Counter, defaultdict

# ===== CREDENCIAIS VIA ENVIRONMENT VARIABLES =====
KANBOARD_URL   = os.environ.get("KANBOARD_URL",   "http://kanboard.eblsolucoescorp.tec.br/jsonrpc.php")
KANBOARD_USER  = os.environ.get("KANBOARD_USER",  "admin")
KANBOARD_PASS  = os.environ.get("KANBOARD_PASS",  "Senha@2026")
KANBOARD_PROJ  = 11

PBI_USERNAME   = os.environ.get("PBI_USERNAME",   "admebl@eblsolucoescorporativas.com")
PBI_PASSWORD   = os.environ.get("PBI_PASSWORD",   "Senha@2026")
PBI_TENANT_ID  = os.environ.get("PBI_TENANT_ID",  "208364c6-eee7-4324-ac4a-d45fe452a1bd")
PBI_CLIENT_ID  = os.environ.get("PBI_CLIENT_ID",  "1950a258-227b-4e31-a9cf-717495945fc2")
PBI_DATASET_ID = os.environ.get("PBI_DATASET_ID", "39d50fe5-cde9-4244-b5e5-422a73e8e142")
PBI_SCOPE      = ["https://analysis.windows.net/powerbi/api/.default"]

BASE_DIR  = Path(__file__).parent.parent
LOG_FILE  = BASE_DIR / "powerbi" / "sync_log.json"
CSV_FILE  = BASE_DIR / "powerbi" / "kanboard_dados_final.csv"
EXCEL_MAP = BASE_DIR / "powerbi" / "excel_map.json"

def log(msg, level="INFO"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [{level}] {msg}", flush=True)

def get_pbi_token():
    app = msal.PublicClientApplication(PBI_CLIENT_ID, authority=f"https://login.microsoftonline.com/{PBI_TENANT_ID}")
    result = app.acquire_token_by_username_password(PBI_USERNAME, PBI_PASSWORD, scopes=PBI_SCOPE)
    if "access_token" not in result:
        raise Exception(f"Falha auth PBI: {result.get('error_description','')}")
    return result["access_token"]

def kanboard_api(method, params=None):
    payload = {"jsonrpc": "2.0", "method": method, "id": 1, "params": params or {}}
    r = requests.post(KANBOARD_URL, json=payload, auth=(KANBOARD_USER, KANBOARD_PASS), timeout=30)
    r.raise_for_status()
    return r.json().get("result")

def map_phase(col_name):
    phases = {
        "Backlog": "01. Backlog", "Refinamento": "02. Refinamento",
        "Priorizada": "03. Priorizada", "Análise": "04. Análise",
        "Estimativa": "05. Estimativa", "Aprovação": "06. Aprovação",
        "Desenvolvimento": "07. Desenvolvimento", "Homologação": "08. Homologação",
        "Deploy": "09. Deploy", "Implementado": "10. Implementado",
    }
    for k, v in phases.items():
        if k.lower() in (col_name or "").lower():
            return v
    return col_name or "01. Backlog"

def main():
    start = datetime.now()
    log("=" * 60)
    log("EBL Kanboard → Power BI Sync (GitHub Actions)")
    log("=" * 60)

    # 1. Auth
    log("Autenticando no Power BI...")
    token = get_pbi_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    log("Token obtido!")

    # 2. Buscar tarefas
    log("Buscando tarefas do Kanboard...")
    open_t   = kanboard_api("getAllTasks", {"project_id": KANBOARD_PROJ, "status_id": 1}) or []
    closed_t = kanboard_api("getAllTasks", {"project_id": KANBOARD_PROJ, "status_id": 0}) or []
    all_tasks = open_t + closed_t
    log(f"Total: {len(all_tasks)} tarefas ({len(open_t)} abertas + {len(closed_t)} fechadas)")

    # 3. Metadados
    columns = kanboard_api("getColumns", {"project_id": KANBOARD_PROJ}) or []
    cols_map = {str(c["id"]): c["title"] for c in columns}
    users    = kanboard_api("getAllUsers") or []
    users_map = {str(u["id"]): u.get("name") or u.get("username","") for u in users}

    # 4. Enriquecimento do Excel
    excel_map = {}
    if EXCEL_MAP.exists():
        with open(EXCEL_MAP, 'r', encoding='utf-8') as f:
            excel_map = json.load(f)

    # 5. Processar tarefas
    enriched = []
    for i, task in enumerate(all_tasks, 1):
        title  = task.get("title", "")
        parts  = title.split(" - ", 2)
        cherwell = parts[0].strip() if len(parts) >= 2 else ""
        rdm      = parts[1].strip() if len(parts) >= 3 else ""
        titulo   = parts[-1].strip()
        ex       = excel_map.get(cherwell, {})
        col_name = cols_map.get(str(task.get("column_id","")), "Backlog")
        fase     = map_phase(col_name)
        is_closed = str(task.get("is_active","1")) == "0"
        status   = "Implementado" if is_closed or "Implementado" in col_name else "Aberta"
        resp     = users_map.get(str(task.get("owner_id","")), ex.get("resp","Não atribuído"))
        pri_num  = int(task.get("priority", 0) or 0)
        pri      = "Alta" if pri_num >= 3 else ("Média" if pri_num == 2 else ex.get("pri","Média"))
        due      = task.get("date_due","")
        try:
            due_str = datetime.fromtimestamp(int(due)).strftime("%d/%m/%Y") if due and str(due)!="0" else ex.get("golive","")
        except:
            due_str = ex.get("golive","")
        try:
            created_str = datetime.fromtimestamp(int(task.get("date_creation",""))).strftime("%Y-%m-%d")
        except:
            created_str = ""

        enriched.append({
            "seq": i, "cherwell": cherwell or f"KB-{task.get('id','')}",
            "rdm": rdm or ex.get("rdm",""), "titulo": titulo[:200],
            "fase": fase, "status": status, "resp": resp,
            "area": ex.get("area",""), "tipo": ex.get("tipo",""), "pri": pri,
            "golive": due_str, "previsao": ex.get("previsao",""),
            "obs": (task.get("description","") or "")[:300],
            "valor": float(ex.get("valor",0) or 0), "horas": float(ex.get("horas",0) or 0),
            "dev": ex.get("dev",""), "aprovado": ex.get("aprovado",""),
            "aprovado_por": ex.get("aprovado_por",""), "requisitante": ex.get("requisitante",""),
            "valtech": ex.get("valtech",""), "data_criacao": created_str,
            "task_id": str(task.get("id","")),
            "sync_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })

    # 6. KPIs
    total  = len(enriched)
    impl   = sum(1 for t in enriched if t["status"] == "Implementado")
    alta   = sum(1 for t in enriched if t["pri"] == "Alta")
    backlog = sum(1 for t in enriched if t["fase"] == "01. Backlog")
    andamento = sum(1 for t in enriched if t["fase"] in ["02. Refinamento","06. Aprovação","07. Desenvolvimento","09. Deploy"])
    valor_total = sum(t["valor"] for t in enriched)
    horas_total = sum(t["horas"] for t in enriched)
    taxa = round(impl/total*100, 1) if total > 0 else 0

    kpis = [
        {"kpi": "Total de Demandas",  "valor": total,       "unidade": "demandas", "descricao": "Base Fast Track"},
        {"kpi": "Implementadas",      "valor": impl,        "unidade": "demandas", "descricao": f"{taxa}% de conclusão"},
        {"kpi": "Em Andamento",       "valor": andamento,   "unidade": "demandas", "descricao": "Refin + Aprov + Dev + Deploy"},
        {"kpi": "Alta Prioridade",    "valor": alta,        "unidade": "demandas", "descricao": "Atenção imediata"},
        {"kpi": "No Backlog",         "valor": backlog,     "unidade": "demandas", "descricao": f"{round(backlog/total*100)}% aguardando"},
        {"kpi": "Valor Total",        "valor": valor_total, "unidade": "R$",       "descricao": f"R$ {valor_total:,.0f}"},
        {"kpi": "Horas Estimadas",    "valor": horas_total, "unidade": "horas",    "descricao": "Valtech"},
        {"kpi": "Taxa de Conclusão",  "valor": taxa,        "unidade": "%",        "descricao": f"{impl} de {total}"},
    ]

    fases_cnt = Counter(t["fase"] for t in enriched)
    fases = [{"fase": f, "quantidade": v, "percentual": round(v/total*100,1)} for f, v in sorted(fases_cnt.items())]

    resp_data = defaultdict(lambda: {"total":0,"implementadas":0,"alta_prioridade":0,"valor_total":0,"horas_total":0})
    for t in enriched:
        r = t["resp"]
        resp_data[r]["total"] += 1
        if t["status"] == "Implementado": resp_data[r]["implementadas"] += 1
        if t["pri"] == "Alta": resp_data[r]["alta_prioridade"] += 1
        resp_data[r]["valor_total"] += t["valor"]
        resp_data[r]["horas_total"] += t["horas"]
    responsaveis = [{"responsavel": r, **d, "taxa_conclusao": round(d["implementadas"]/d["total"]*100,1) if d["total"]>0 else 0}
                    for r, d in sorted(resp_data.items(), key=lambda x: -x[1]["total"])]

    # 7. Limpar e inserir no Power BI
    pbi_url = f"https://api.powerbi.com/v1.0/myorg/datasets/{PBI_DATASET_ID}/tables"
    for table in ["Demandas", "KPIs", "Fases", "Responsaveis"]:
        r = requests.delete(f"{pbi_url}/{table}/rows", headers=headers)
        log(f"Limpar {table}: {r.status_code}")

    def push(table, rows):
        payload = json.dumps({"rows": rows}, ensure_ascii=False).encode('utf-8')
        r = requests.post(f"{pbi_url}/{table}/rows", data=payload, headers=headers)
        log(f"Push {table}: {r.status_code} ({len(rows)} linhas)")
        return r.status_code == 200

    push("Demandas", enriched)
    push("KPIs", kpis)
    push("Fases", fases)
    push("Responsaveis", responsaveis)

    # 8. Salvar CSV
    with open(CSV_FILE, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=enriched[0].keys(), delimiter=';')
        writer.writeheader()
        writer.writerows(enriched)

    # 9. Log
    elapsed = (datetime.now() - start).total_seconds()
    sync_result = {"timestamp": start.isoformat(), "status": "success",
                   "tasks_synced": len(enriched), "elapsed_seconds": elapsed}
    logs = []
    if LOG_FILE.exists():
        with open(LOG_FILE) as f:
            try: logs = json.load(f)
            except: pass
    logs.append(sync_result)
    with open(LOG_FILE, 'w') as f:
        json.dump(logs[-30:], f, ensure_ascii=False, indent=2)

    log(f"SYNC CONCLUÍDO em {elapsed:.1f}s — {len(enriched)} demandas sincronizadas")
    return 0

if __name__ == "__main__":
    sys.exit(main())
