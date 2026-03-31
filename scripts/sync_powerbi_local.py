#!/usr/bin/env python3
"""
EBL Kanboard → Power BI Sync Automático (com fallback local)
Executa diariamente via cron/GitHub Actions
Versão: 2.1 | Atualizado em: 2026-03-31
Estratégia: tenta buscar do Kanboard; se falhar, usa dados locais enriquecidos
"""

import msal, requests, json, csv, sys, os
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter, defaultdict

# ===== CONFIGURAÇÕES =====
KANBOARD_URL   = "http://kanboard.eblsolucoescorp.tec.br/jsonrpc.php"
KANBOARD_USER  = "admin"
KANBOARD_PASS  = "Senha@2026"
KANBOARD_PROJ  = 11  # [SF] Fast Track — Salesforce

PBI_USERNAME   = "admebl@eblsolucoescorporativas.com"
PBI_PASSWORD   = "Senha@2026"
PBI_TENANT_ID  = "208364c6-eee7-4324-ac4a-d45fe452a1bd"
PBI_CLIENT_ID  = "1950a258-227b-4e31-a9cf-717495945fc2"
PBI_DATASET_ID = "39d50fe5-cde9-4244-b5e5-422a73e8e142"
PBI_SCOPE      = ["https://analysis.windows.net/powerbi/api/.default"]

BASE_DIR       = Path(__file__).parent.parent
EXCEL_MAP      = BASE_DIR / "powerbi" / "excel_map.json"
DATA_ENRICH    = BASE_DIR / "powerbi" / "data_enriquecido.json"
CSV_FINAL      = BASE_DIR / "powerbi" / "kanboard_dados_final.csv"
LOG_FILE       = BASE_DIR / "powerbi" / "sync_log.json"

SYNC_TS        = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def log(msg, level="INFO"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [{level}] {msg}")

# =====================================================================
# AUTENTICAÇÃO POWER BI
# =====================================================================
def get_pbi_token():
    """Obtém token de acesso ao Power BI via MSAL (username/password flow)"""
    log("Autenticando no Power BI Service (MSAL ROPC)...")
    app = msal.PublicClientApplication(
        PBI_CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{PBI_TENANT_ID}"
    )
    result = app.acquire_token_by_username_password(
        PBI_USERNAME, PBI_PASSWORD, scopes=PBI_SCOPE
    )
    if "access_token" not in result:
        err = result.get("error_description", result.get("error", "Desconhecido"))
        raise Exception(f"Falha na autenticação Power BI: {err}")
    log(f"  Token obtido! Expira em {result.get('expires_in', '?')}s")
    return result["access_token"]

# =====================================================================
# BUSCA DE DADOS DO KANBOARD
# =====================================================================
def kanboard_api(method, params=None, timeout=15):
    """Chama a API JSON-RPC do Kanboard"""
    payload = {"jsonrpc": "2.0", "method": method, "id": 1, "params": params or {}}
    r = requests.post(
        KANBOARD_URL, json=payload,
        auth=(KANBOARD_USER, KANBOARD_PASS),
        timeout=timeout
    )
    r.raise_for_status()
    return r.json().get("result")

def try_get_kanboard_tasks():
    """Tenta buscar tarefas do Kanboard; retorna None se falhar"""
    try:
        log("Tentando buscar tarefas abertas do Kanboard...")
        open_tasks = kanboard_api("getAllTasks", {"project_id": KANBOARD_PROJ, "status_id": 1}) or []
        log(f"  → {len(open_tasks)} tarefas abertas")

        log("Tentando buscar tarefas fechadas do Kanboard...")
        closed_tasks = kanboard_api("getAllTasks", {"project_id": KANBOARD_PROJ, "status_id": 0}) or []
        log(f"  → {len(closed_tasks)} tarefas fechadas")

        all_tasks = open_tasks + closed_tasks
        log(f"  Total Kanboard: {len(all_tasks)} tarefas")
        return all_tasks
    except Exception as e:
        log(f"  Kanboard inacessível: {e}", "WARN")
        return None

# =====================================================================
# CARREGAMENTO DE DADOS LOCAIS (FALLBACK)
# =====================================================================
def load_local_enriched():
    """Carrega dados enriquecidos locais como fallback"""
    log("Carregando dados locais enriquecidos (data_enriquecido.json)...")
    with open(DATA_ENRICH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    log(f"  → {len(data)} tarefas carregadas do arquivo local")
    return data

def load_csv_metadata():
    """Carrega metadados do CSV final (task_id, data_criacao)"""
    meta = {}
    if CSV_FINAL.exists():
        with open(CSV_FINAL, 'r', encoding='utf-8-sig') as f:
            for row in csv.DictReader(f, delimiter=';'):
                cherwell = row.get('cherwell', '')
                meta[cherwell] = {
                    'task_id': row.get('task_id', ''),
                    'data_criacao': row.get('data_criacao', ''),
                }
    return meta

def normalize_local_tasks(local_data, csv_meta):
    """Normaliza os dados locais para o formato esperado pelo script"""
    log("Normalizando dados locais para o formato Power BI...")
    normalized = []
    for i, t in enumerate(local_data, 1):
        cherwell = str(t.get('cherwell', ''))
        meta = csv_meta.get(cherwell, {})

        # Normalizar fase (corrigir erros de digitação)
        fase = t.get('fase', '01. Backlog')
        if 'Homog' in fase and fase not in ['08. Homologação']:
            fase = '08. Homologação'

        # Normalizar status
        status = t.get('status', 'Aberta')

        # Prioridade
        pri_raw = str(t.get('pri', '0'))
        try:
            pri_num = int(float(pri_raw))
        except:
            pri_num = 0
        if pri_num >= 3:
            pri = "Alta"
        elif pri_num == 2:
            pri = "Média"
        elif pri_raw in ["Alta", "Média", "Baixa"]:
            pri = pri_raw
        else:
            pri = "Média"

        normalized.append({
            "seq":          t.get('seq', i),
            "cherwell":     cherwell,
            "rdm":          t.get('rdm', ''),
            "titulo":       str(t.get('titulo', ''))[:200],
            "fase":         fase,
            "status":       status,
            "resp":         t.get('resp', 'Não atribuído'),
            "area":         t.get('area', ''),
            "tipo":         t.get('tipo', ''),
            "pri":          pri,
            "golive":       t.get('golive', ''),
            "previsao":     t.get('previsao', ''),
            "obs":          str(t.get('obs', ''))[:300],
            "valor":        float(t.get('valor', 0) or 0),
            "horas":        float(t.get('horas', 0) or 0),
            "dev":          t.get('dev', ''),
            "aprovado":     t.get('aprovado', ''),
            "aprovado_por": t.get('aprovado_por', ''),
            "requisitante": t.get('requisitante', ''),
            "valtech":      t.get('valtech', ''),
            "data_criacao": meta.get('data_criacao', ''),
            "task_id":      meta.get('task_id', ''),
            "sync_at":      SYNC_TS,
        })

    log(f"  → {len(normalized)} tarefas normalizadas")
    return normalized

# =====================================================================
# ENRIQUECIMENTO DO KANBOARD COM EXCEL_MAP
# =====================================================================
def load_excel_enrichment():
    """Carrega dados de enriquecimento do Excel"""
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

def enrich_from_kanboard(tasks, excel_map):
    """Enriquece tarefas brutas do Kanboard com dados do Excel"""
    log("Enriquecendo tarefas do Kanboard com dados do Excel...")

    # Buscar colunas do projeto
    columns = kanboard_api("getColumns", {"project_id": KANBOARD_PROJ}) or []
    columns_cache = {str(c["id"]): c["title"] for c in columns}

    # Mapeamento de responsáveis
    users = kanboard_api("getAllUsers") or []
    users_map = {str(u["id"]): u.get("name") or u.get("username", "") for u in users}

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
        col_name = columns_cache.get(col_id, "Backlog")
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
            "seq":          i,
            "cherwell":     cherwell or f"KB-{task.get('id', '')}",
            "rdm":          rdm or excel_data.get("rdm", ""),
            "titulo":       titulo[:200],
            "fase":         fase,
            "status":       status,
            "resp":         resp,
            "area":         excel_data.get("area", ""),
            "tipo":         excel_data.get("tipo", ""),
            "pri":          pri,
            "golive":       due_str,
            "previsao":     excel_data.get("previsao", ""),
            "obs":          (task.get("description", "") or "")[:300],
            "valor":        float(excel_data.get("valor", 0) or 0),
            "horas":        float(excel_data.get("horas", 0) or 0),
            "dev":          excel_data.get("dev", ""),
            "aprovado":     excel_data.get("aprovado", ""),
            "aprovado_por": excel_data.get("aprovado_por", ""),
            "requisitante": excel_data.get("requisitante", ""),
            "valtech":      excel_data.get("valtech", ""),
            "data_criacao": created_str,
            "task_id":      task.get("id", ""),
            "sync_at":      SYNC_TS,
        })

    log(f"  → {len(enriched)} tarefas enriquecidas")
    return enriched

# =====================================================================
# OPERAÇÕES POWER BI
# =====================================================================
def clear_pbi_table(token, table_name):
    """Limpa uma tabela do dataset Power BI"""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    url = f"https://api.powerbi.com/v1.0/myorg/datasets/{PBI_DATASET_ID}/tables/{table_name}/rows"
    r = requests.delete(url, headers=headers, timeout=30)
    if r.status_code in [200, 204]:
        log(f"  Tabela '{table_name}' limpa com sucesso (HTTP {r.status_code})")
    else:
        log(f"  Aviso ao limpar '{table_name}': {r.status_code} - {r.text[:150]}", "WARN")

def push_rows(token, table_name, rows, batch_size=500):
    """Insere linhas em uma tabela do dataset Power BI em lotes"""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    url = f"https://api.powerbi.com/v1.0/myorg/datasets/{PBI_DATASET_ID}/tables/{table_name}/rows"

    total = len(rows)
    inserted = 0
    for i in range(0, total, batch_size):
        batch = rows[i:i + batch_size]
        payload = json.dumps({"rows": batch}, ensure_ascii=False)
        r = requests.post(url, data=payload.encode('utf-8'), headers=headers, timeout=60)
        if r.status_code == 200:
            inserted += len(batch)
            log(f"  Lote {i // batch_size + 1}: {len(batch)} linhas inseridas ({inserted}/{total})")
        else:
            log(f"  ERRO no lote {i // batch_size + 1}: {r.status_code} - {r.text[:200]}", "ERROR")
    return inserted

# =====================================================================
# CÁLCULO DE KPIs E MÉTRICAS
# =====================================================================
def compute_kpis(tasks):
    """Calcula KPIs executivos"""
    total = len(tasks)
    impl = sum(1 for t in tasks if t["status"] == "Implementado")
    alta = sum(1 for t in tasks if t["pri"] == "Alta")
    backlog = sum(1 for t in tasks if t["fase"] == "01. Backlog")
    andamento = sum(1 for t in tasks if t["fase"] in [
        "02. Refinamento", "06. Aprovação", "07. Desenvolvimento", "09. Deploy"
    ])
    valor_total = sum(float(t.get("valor", 0) or 0) for t in tasks)
    horas_total = sum(float(t.get("horas", 0) or 0) for t in tasks)
    taxa = round(impl / total * 100, 1) if total > 0 else 0

    return [
        {"kpi": "Total de Demandas",  "valor": total,        "unidade": "demandas", "descricao": "Base Fast Track Salesforce"},
        {"kpi": "Implementadas",       "valor": impl,         "unidade": "demandas", "descricao": f"{taxa}% de conclusão"},
        {"kpi": "Em Andamento",        "valor": andamento,    "unidade": "demandas", "descricao": "Refin + Aprov + Dev + Deploy"},
        {"kpi": "Alta Prioridade",     "valor": alta,         "unidade": "demandas", "descricao": "Atenção imediata"},
        {"kpi": "No Backlog",          "valor": backlog,      "unidade": "demandas", "descricao": f"{round(backlog / total * 100) if total else 0}% aguardando"},
        {"kpi": "Valor Total",         "valor": valor_total,  "unidade": "R$",       "descricao": f"R$ {valor_total:,.0f}"},
        {"kpi": "Horas Estimadas",     "valor": horas_total,  "unidade": "horas",    "descricao": "Valtech"},
        {"kpi": "Taxa de Conclusão",   "valor": taxa,         "unidade": "%",        "descricao": f"{impl} de {total} implementadas"},
    ]

def compute_fases(tasks):
    """Calcula distribuição por fase"""
    fases = Counter(t["fase"] for t in tasks)
    total = len(tasks)
    return [
        {"fase": f, "quantidade": v, "percentual": round(v / total * 100, 1)}
        for f, v in sorted(fases.items())
    ]

def compute_responsaveis(tasks):
    """Calcula métricas por responsável"""
    resp_data = defaultdict(lambda: {"total": 0, "implementadas": 0, "alta_prioridade": 0, "valor": 0.0, "horas": 0.0})
    for t in tasks:
        r = t["resp"]
        resp_data[r]["total"] += 1
        if t["status"] == "Implementado":
            resp_data[r]["implementadas"] += 1
        if t["pri"] == "Alta":
            resp_data[r]["alta_prioridade"] += 1
        resp_data[r]["valor"] += float(t.get("valor", 0) or 0)
        resp_data[r]["horas"] += float(t.get("horas", 0) or 0)

    result = []
    for resp, d in sorted(resp_data.items(), key=lambda x: -x[1]["total"]):
        taxa = round(d["implementadas"] / d["total"] * 100, 1) if d["total"] > 0 else 0
        result.append({
            "responsavel":    resp,
            "total":          d["total"],
            "implementadas":  d["implementadas"],
            "alta_prioridade": d["alta_prioridade"],
            "valor_total":    d["valor"],
            "horas_total":    d["horas"],
            "taxa_conclusao": taxa,
        })
    return result

# =====================================================================
# LOG
# =====================================================================
def save_log(sync_result):
    """Salva log de sincronização (mantém últimas 30 execuções)"""
    logs = []
    if LOG_FILE.exists():
        try:
            with open(LOG_FILE, 'r') as f:
                logs = json.load(f)
        except:
            logs = []

    logs.append(sync_result)
    logs = logs[-30:]

    with open(LOG_FILE, 'w') as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)
    log(f"  Log salvo em: {LOG_FILE}")

# =====================================================================
# MAIN
# =====================================================================
def main():
    start = datetime.now()
    log("=" * 60)
    log("EBL Kanboard → Power BI Sync v2.1 Iniciado")
    log(f"  Timestamp: {SYNC_TS}")
    log("=" * 60)

    sync_result = {
        "timestamp":     start.isoformat(),
        "status":        "error",
        "tasks_synced":  0,
        "fonte":         "desconhecida",
        "error":         None,
    }

    try:
        # ── 1. Autenticar no Power BI ──────────────────────────────
        token = get_pbi_token()

        # ── 2. Tentar buscar dados do Kanboard ────────────────────
        excel_map = load_excel_enrichment()
        raw_tasks = try_get_kanboard_tasks()

        if raw_tasks is not None:
            # Kanboard acessível: enriquecer com excel_map
            enriched = enrich_from_kanboard(raw_tasks, excel_map)
            sync_result["fonte"] = "kanboard_live"
            log("  Fonte: Kanboard (dados ao vivo)")
        else:
            # Fallback: usar dados locais enriquecidos
            log("  Usando fallback: dados locais enriquecidos", "WARN")
            local_data = load_local_enriched()
            csv_meta   = load_csv_metadata()
            enriched   = normalize_local_tasks(local_data, csv_meta)
            sync_result["fonte"] = "local_enriched"
            log("  Fonte: data_enriquecido.json (fallback local)")

        # ── 3. Calcular métricas ──────────────────────────────────
        log("\nCalculando KPIs e métricas...")
        kpis         = compute_kpis(enriched)
        fases        = compute_fases(enriched)
        responsaveis = compute_responsaveis(enriched)

        log(f"  KPIs calculados: {len(kpis)}")
        log(f"  Fases: {len(fases)}")
        log(f"  Responsáveis: {len(responsaveis)}")

        # Resumo dos KPIs
        for k in kpis:
            log(f"    {k['kpi']}: {k['valor']} {k['unidade']}")

        # ── 4. Limpar tabelas do Power BI ─────────────────────────
        log("\nLimpando tabelas do Power BI...")
        for table in ["Demandas", "KPIs", "Fases", "Responsaveis"]:
            clear_pbi_table(token, table)

        # ── 5. Inserir dados atualizados ──────────────────────────
        log("\nInserindo dados atualizados no Power BI...")
        n_demandas = push_rows(token, "Demandas",      enriched)
        n_kpis     = push_rows(token, "KPIs",          kpis)
        n_fases    = push_rows(token, "Fases",         fases)
        n_resp     = push_rows(token, "Responsaveis",  responsaveis)

        # ── 6. Salvar CSV atualizado ──────────────────────────────
        log(f"\nSalvando CSV atualizado em: {CSV_FINAL}")
        with open(CSV_FINAL, 'w', newline='', encoding='utf-8-sig') as f:
            if enriched:
                writer = csv.DictWriter(f, fieldnames=enriched[0].keys(), delimiter=';')
                writer.writeheader()
                writer.writerows(enriched)
        log(f"  CSV salvo: {CSV_FINAL} ({len(enriched)} linhas)")

        elapsed = (datetime.now() - start).total_seconds()
        log(f"\n{'=' * 60}")
        log(f"SYNC CONCLUÍDO em {elapsed:.1f}s")
        log(f"  Demandas: {n_demandas} | KPIs: {n_kpis} | Fases: {n_fases} | Responsáveis: {n_resp}")
        log(f"  Fonte: {sync_result['fonte']}")
        log(f"{'=' * 60}")

        sync_result.update({
            "status":         "success",
            "tasks_synced":   n_demandas,
            "kpis_synced":    n_kpis,
            "fases_synced":   n_fases,
            "resp_synced":    n_resp,
            "elapsed_seconds": elapsed,
        })

    except Exception as e:
        import traceback
        log(f"ERRO CRÍTICO: {e}", "ERROR")
        log(traceback.format_exc(), "ERROR")
        sync_result["error"] = str(e)
        save_log(sync_result)
        sys.exit(1)

    save_log(sync_result)
    return 0

if __name__ == "__main__":
    sys.exit(main())
