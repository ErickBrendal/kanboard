#!/usr/bin/env python3
"""
EBL Soluções Corporativas — Kanboard → OneDrive Sync
Versão: 1.0 | 2026-04-13

Fluxo:
  1. Autentica no Microsoft Graph via client_credentials (sem MFA)
  2. Lê todos os projetos ativos do Kanboard via JSON-RPC API
  3. Para cada projeto, busca tarefas abertas e fechadas
  4. Monta CSV com 27 colunas padronizadas
  5. Faz upload do CSV para o OneDrive (pasta /EBL/Kanboard/)
  6. Registra log de execução

Variáveis de ambiente necessárias (arquivo .env ou export):
  KANBOARD_URL, KANBOARD_TOKEN
  AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET
  ONEDRIVE_DRIVE_ID, ONEDRIVE_FOLDER_PATH, ONEDRIVE_FILE_NAME
"""

import os
import sys
import json
import csv
import io
import requests
import logging
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

# ── Carregar .env ──────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / ".env")

# ── Configurações ──────────────────────────────────────────────────────
KANBOARD_URL   = os.environ.get("KANBOARD_URL", "http://localhost/jsonrpc.php")
KANBOARD_TOKEN = os.environ.get("KANBOARD_TOKEN", "ea99d4c7d96dbad1b1a1defd79f92286884e1902015ff96731ce624e6317")
KANBOARD_USER  = os.environ.get("KANBOARD_USER", "admin")

AZURE_TENANT_ID    = os.environ.get("AZURE_TENANT_ID", "")
AZURE_CLIENT_ID    = os.environ.get("AZURE_CLIENT_ID", "")
AZURE_CLIENT_SECRET = os.environ.get("AZURE_CLIENT_SECRET", "")

ONEDRIVE_DRIVE_ID   = os.environ.get("ONEDRIVE_DRIVE_ID", "")
ONEDRIVE_FOLDER     = os.environ.get("ONEDRIVE_FOLDER_PATH", "/EBL/Kanboard")
ONEDRIVE_FILE_NAME  = os.environ.get("ONEDRIVE_FILE_NAME", "kanboard_dados.csv")

LOG_FILE = BASE_DIR / "powerbi" / "sync_log.json"

# ── Logging ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger(__name__)

# ── Mapeamento de colunas → fases ──────────────────────────────────────
COLUMN_MAP = {
    "165": "01. Backlog",       "166": "02. Refinamento",   "167": "03. Priorizada",
    "168": "04. Análise",       "169": "05. Estimativa",    "170": "06. Aprovação",
    "171": "07. Desenvolvimento","172": "08. Homologação",  "173": "09. Deploy",
    "174": "10. Implementado",  "175": "11. Cancelado",
    "176": "01. Backlog",       "177": "02. Refinamento",   "178": "04. Análise",
    "179": "05. Estimativa",    "180": "06. Aprovação",     "181": "07. Desenvolvimento",
    "182": "08. Homologação",   "183": "09. Deploy",        "184": "10. Implementado",
    "185": "11. Cancelado",
    "186": "01. Backlog",       "187": "02. Refinamento",   "188": "04. Análise",
    "189": "05. Estimativa",    "190": "06. Aprovação",     "191": "07. Desenvolvimento",
    "192": "08. Homologação",   "193": "09. Deploy",        "194": "10. Implementado",
    "195": "11. Cancelado",     "39":  "03. Priorizada",
}

PRIORITY_MAP = {0: "Baixa", 1: "Normal", 2: "Alta", 3: "Urgente", 4: "Crítica"}

# 27 colunas do CSV
CSV_COLUMNS = [
    "id", "projeto_id", "projeto_nome", "titulo", "descricao",
    "fase", "status", "prioridade", "responsavel", "criado_por",
    "data_criacao", "data_modificacao", "data_inicio", "data_vencimento", "data_conclusao",
    "estimativa_horas", "horas_gastas", "score", "posicao", "swimlane",
    "tags", "url_tarefa", "cherwell", "rdm", "area",
    "tipo", "sync_timestamp"
]

# ── Kanboard API ───────────────────────────────────────────────────────
_req_id = 0

def kanboard_call(method, params=None):
    """Chama a API JSON-RPC do Kanboard."""
    global _req_id
    _req_id += 1
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "id": _req_id,
        "params": params or {}
    }
    headers = {"Content-Type": "application/json"}
    # Kanboard aceita Basic Auth com jsonrpc:TOKEN
    auth = ("jsonrpc", KANBOARD_TOKEN)
    # Tentar localhost primeiro (quando rodando na VM), depois URL externa
    urls_to_try = [KANBOARD_URL]
    if "localhost" not in KANBOARD_URL:
        urls_to_try.append(KANBOARD_URL.replace("https://", "http://"))
    else:
        urls_to_try.append("https://kanboard.eblsolucoescorp.tec.br/jsonrpc.php")
        urls_to_try.append("http://kanboard.eblsolucoescorp.tec.br/jsonrpc.php")
    for url_try in urls_to_try:
        try:
            r = requests.post(url_try, json=payload, headers=headers, auth=auth,
                              timeout=30, verify=False)
            r.raise_for_status()
            resp = r.json()
            if "error" in resp:
                raise Exception(f"Kanboard error: {resp['error']}")
            return resp.get("result")
        except requests.exceptions.SSLError:
            continue
        except requests.exceptions.ConnectionError:
            continue
    raise Exception(f"Kanboard inacessível em {KANBOARD_URL}")

def get_all_projects():
    """Retorna todos os projetos ativos."""
    projects = kanboard_call("getAllProjects") or []
    active = [p for p in projects if p.get("is_active") in ("1", 1)]
    log.info(f"Projetos encontrados: {len(active)} ativos de {len(projects)} total")
    return active

def get_users_map():
    """Retorna mapeamento id → nome de todos os usuários."""
    try:
        users = kanboard_call("getAllUsers") or []
        return {str(u["id"]): u.get("name") or u.get("username", "") for u in users}
    except Exception as e:
        log.warning(f"Não foi possível obter usuários: {e}")
        return {
            "1": "admin", "2": "Erick Almeida", "3": "Marcio Souza",
            "4": "Elder Rodrigues", "5": "Felipe Nascimento", "6": "Carlos Almeida"
        }

def get_tasks_for_project(project_id):
    """Busca tarefas abertas e fechadas de um projeto."""
    open_tasks = kanboard_call("getAllTasks", {"project_id": project_id, "status_id": 1}) or []
    closed_tasks = kanboard_call("getAllTasks", {"project_id": project_id, "status_id": 0}) or []
    return open_tasks + closed_tasks

def parse_ts(ts):
    """Converte timestamp Unix para string de data."""
    if not ts or str(ts) == "0":
        return ""
    try:
        return datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(ts)

def extract_cherwell_rdm(title):
    """Extrai Cherwell e RDM do título no formato 'CHW - RDM - Título'."""
    parts = title.split(" - ", 2)
    if len(parts) >= 3:
        return parts[0].strip(), parts[1].strip(), parts[2].strip()
    elif len(parts) == 2:
        return parts[0].strip(), "", parts[1].strip()
    return "", "", title

def map_phase(column_id, column_name=""):
    """Mapeia coluna para fase padronizada."""
    if str(column_id) in COLUMN_MAP:
        return COLUMN_MAP[str(column_id)]
    phase_keywords = {
        "backlog": "01. Backlog", "refinamento": "02. Refinamento",
        "priorizada": "03. Priorizada", "análise": "04. Análise",
        "estimativa": "05. Estimativa", "aprovação": "06. Aprovação",
        "desenvolvimento": "07. Desenvolvimento", "homologação": "08. Homologação",
        "deploy": "09. Deploy", "implementado": "10. Implementado",
        "cancelado": "11. Cancelado",
    }
    col_lower = (column_name or "").lower()
    for kw, phase in phase_keywords.items():
        if kw in col_lower:
            return phase
    return column_name or "01. Backlog"

# ── Microsoft Graph / OneDrive ─────────────────────────────────────────
def get_graph_token():
    """Obtém token do Microsoft Graph via client_credentials (sem MFA)."""
    url = f"https://login.microsoftonline.com/{AZURE_TENANT_ID}/oauth2/v2.0/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": AZURE_CLIENT_ID,
        "client_secret": AZURE_CLIENT_SECRET,
        "scope": "https://graph.microsoft.com/.default",
    }
    r = requests.post(url, data=data, timeout=30)
    r.raise_for_status()
    token = r.json().get("access_token")
    if not token:
        raise Exception(f"Falha ao obter token Graph: {r.text}")
    log.info("Token Microsoft Graph obtido via client_credentials")
    return token

def ensure_onedrive_folder(token, folder_path):
    """Garante que a pasta existe no OneDrive, criando se necessário."""
    # Normalizar caminho
    parts = [p for p in folder_path.strip("/").split("/") if p]
    base_url = f"https://graph.microsoft.com/v1.0/drives/{ONEDRIVE_DRIVE_ID}/root"
    headers = {"Authorization": f"Bearer {token}"}

    current_path = ""
    for part in parts:
        current_path = f"{current_path}/{part}" if current_path else part
        check_url = f"{base_url}:/{current_path}"
        r = requests.get(check_url, headers=headers, timeout=15)
        if r.status_code == 404:
            # Criar pasta
            parent_url = f"{base_url}:/{'/'.join(current_path.split('/')[:-1])}:/children" \
                if "/" in current_path else f"{base_url}/children"
            create_r = requests.post(parent_url, headers={**headers, "Content-Type": "application/json"},
                                     json={"name": part, "folder": {}, "@microsoft.graph.conflictBehavior": "rename"},
                                     timeout=15)
            if create_r.status_code not in (200, 201):
                log.warning(f"Não foi possível criar pasta '{part}': {create_r.text[:200]}")
        elif r.status_code != 200:
            log.warning(f"Erro ao verificar pasta '{current_path}': {r.status_code}")

def upload_csv_to_onedrive(token, csv_content, folder_path, file_name):
    """Faz upload do CSV para o OneDrive."""
    folder_clean = folder_path.strip("/")
    upload_url = (
        f"https://graph.microsoft.com/v1.0/drives/{ONEDRIVE_DRIVE_ID}"
        f"/root:/{folder_clean}/{file_name}:/content"
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "text/csv; charset=utf-8",
    }
    csv_bytes = csv_content.encode("utf-8-sig")  # BOM para Excel abrir corretamente
    r = requests.put(upload_url, headers=headers, data=csv_bytes, timeout=60)
    if r.status_code in (200, 201):
        item = r.json()
        web_url = item.get("webUrl", "")
        log.info(f"CSV enviado para OneDrive: {web_url}")
        return web_url
    else:
        raise Exception(f"Falha no upload OneDrive ({r.status_code}): {r.text[:500]}")

# ── Pipeline principal ─────────────────────────────────────────────────
def build_csv(projects, users_map):
    """Monta o CSV com todas as tarefas de todos os projetos."""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS, extrasaction="ignore")
    writer.writeheader()

    sync_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    total_tasks = 0

    for project in projects:
        proj_id   = str(project.get("id", ""))
        proj_name = project.get("name", "")
        log.info(f"  Processando projeto [{proj_id}] {proj_name}...")

        try:
            tasks = get_tasks_for_project(int(proj_id))
        except Exception as e:
            log.warning(f"  Erro ao buscar tarefas do projeto {proj_id}: {e}")
            tasks = []

        log.info(f"    → {len(tasks)} tarefas")
        total_tasks += len(tasks)

        for task in tasks:
            title    = task.get("title", "")
            cherwell, rdm, titulo = extract_cherwell_rdm(title)

            col_id   = str(task.get("column_id", ""))
            col_name = task.get("column_name", "")
            fase     = map_phase(col_id, col_name)

            is_closed = task.get("is_active") in ("0", 0)
            status    = "Implementado" if is_closed else "Aberta"

            owner_id  = str(task.get("owner_id", ""))
            resp      = users_map.get(owner_id, "Não atribuído")

            creator_id = str(task.get("creator_id", ""))
            criado_por = users_map.get(creator_id, "")

            pri_num   = int(task.get("priority", 0) or 0)
            prioridade = PRIORITY_MAP.get(pri_num, "Normal")

            tags_raw  = task.get("tags", {})
            if isinstance(tags_raw, dict):
                tags = ", ".join(tags_raw.values())
            elif isinstance(tags_raw, list):
                tags = ", ".join(str(t) for t in tags_raw)
            else:
                tags = str(tags_raw) if tags_raw else ""

            task_url = (
                f"https://kanboard.eblsolucoescorp.tec.br/?controller=TaskViewController"
                f"&action=show&task_id={task.get('id', '')}&project_id={proj_id}"
            )

            row = {
                "id":               task.get("id", ""),
                "projeto_id":       proj_id,
                "projeto_nome":     proj_name,
                "titulo":           titulo[:500],
                "descricao":        (task.get("description", "") or "")[:1000],
                "fase":             fase,
                "status":           status,
                "prioridade":       prioridade,
                "responsavel":      resp,
                "criado_por":       criado_por,
                "data_criacao":     parse_ts(task.get("date_creation")),
                "data_modificacao": parse_ts(task.get("date_modification")),
                "data_inicio":      parse_ts(task.get("date_started")),
                "data_vencimento":  parse_ts(task.get("date_due")),
                "data_conclusao":   parse_ts(task.get("date_completed")),
                "estimativa_horas": task.get("time_estimated", 0) or 0,
                "horas_gastas":     task.get("time_spent", 0) or 0,
                "score":            task.get("score", 0) or 0,
                "posicao":          task.get("position", 0) or 0,
                "swimlane":         task.get("swimlane_name", "") or "",
                "tags":             tags,
                "url_tarefa":       task_url,
                "cherwell":         cherwell,
                "rdm":              rdm,
                "area":             "",   # Enriquecimento via Excel (futuro)
                "tipo":             "",   # Enriquecimento via Excel (futuro)
                "sync_timestamp":   sync_ts,
            }
            writer.writerow(row)

    log.info(f"Total: {total_tasks} tarefas em {len(projects)} projetos")
    return output.getvalue(), total_tasks

def append_log(entry):
    """Adiciona entrada ao log JSON."""
    try:
        if LOG_FILE.exists():
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                logs = json.load(f)
        else:
            logs = []
        logs.append(entry)
        # Manter apenas os últimos 100 registros
        logs = logs[-100:]
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log.warning(f"Erro ao salvar log: {e}")

def run():
    """Executa o pipeline completo."""
    start_time = datetime.now(timezone.utc)
    log.info("=" * 60)
    log.info("EBL Kanboard → OneDrive Sync iniciado")
    log.info(f"Timestamp: {start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    log.info("=" * 60)

    result = {
        "timestamp": start_time.isoformat(),
        "status": "error",
        "projects": 0,
        "tasks": 0,
        "onedrive_url": "",
        "error": "",
        "duration_seconds": 0,
    }

    try:
        # 1. Obter token Graph
        graph_token = get_graph_token()

        # 2. Buscar projetos e usuários do Kanboard
        log.info("Buscando projetos do Kanboard...")
        projects = get_all_projects()
        result["projects"] = len(projects)

        log.info("Buscando mapa de usuários...")
        users_map = get_users_map()

        # 3. Montar CSV
        log.info("Montando CSV com 27 colunas...")
        csv_content, total_tasks = build_csv(projects, users_map)
        result["tasks"] = total_tasks

        # 4. Salvar CSV local (backup)
        local_csv = BASE_DIR / "powerbi" / "kanboard_dados.csv"
        with open(local_csv, "w", encoding="utf-8-sig") as f:
            f.write(csv_content)
        log.info(f"CSV salvo localmente: {local_csv}")

        # 5. Garantir pasta no OneDrive e fazer upload
        log.info(f"Criando pasta {ONEDRIVE_FOLDER} no OneDrive (se necessário)...")
        ensure_onedrive_folder(graph_token, ONEDRIVE_FOLDER)

        log.info(f"Fazendo upload para OneDrive: {ONEDRIVE_FOLDER}/{ONEDRIVE_FILE_NAME}")
        web_url = upload_csv_to_onedrive(graph_token, csv_content, ONEDRIVE_FOLDER, ONEDRIVE_FILE_NAME)

        result["status"] = "success"
        result["onedrive_url"] = web_url

    except Exception as e:
        result["error"] = str(e)
        log.error(f"Erro no pipeline: {e}", exc_info=True)

    finally:
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        result["duration_seconds"] = round(duration, 2)
        append_log(result)
        log.info(f"Pipeline finalizado em {duration:.1f}s — status: {result['status']}")
        if result["status"] == "error":
            log.error(f"Erro: {result['error']}")
            sys.exit(1)

    return result

if __name__ == "__main__":
    run()
