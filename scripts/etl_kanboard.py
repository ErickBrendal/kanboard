#!/usr/bin/env python3
import requests
import psycopg2
import os
import logging
from datetime import datetime, timezone

# Configurações via variáveis de ambiente
KANBOARD_URL = os.getenv("KANBOARD_URL", "http://kanboard/jsonrpc.php")
API_USER = "admin"
API_TOKEN = os.getenv("KANBOARD_API_TOKEN", "")
DB_HOST = "db"
DB_PORT = "5432"
DB_NAME = "kanboard"
DB_USER = "kanboard"
DB_PASS = os.getenv("DB_PASSWORD", "")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("/opt/kanboard-ebl/logs/etl.log"), logging.StreamHandler()])
log = logging.getLogger("etl")

def api_call(method, **params):
    payload = {"jsonrpc": "2.0", "method": method, "id": 1, "params": params}
    try:
        r = requests.post(KANBOARD_URL, json=payload, auth=(API_USER, API_TOKEN), timeout=30)
        r.raise_for_status()
        result = r.json()
        if "error" in result and result["error"]:
            log.error(f"API [{method}]: {result['error']}")
            return None
        return result.get("result")
    except Exception as e:
        log.error(f"API [{method}]: {e}")
        return None

def ts(val):
    if not val or val == "0": return None
    try: return datetime.fromtimestamp(int(val), tz=timezone.utc)
    except: return None

def main():
    log.info("ETL iniciado")
    if not API_TOKEN:
        log.error("API_TOKEN não configurado")
        return

    conn = psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASS)
    conn.autocommit = False
    cur = conn.cursor()
    now = datetime.now(timezone.utc)

    projects = api_call("getAllProjects") or []
    for p in projects:
        cur.execute("""INSERT INTO bi_kanboard.dim_projetos (projeto_id,nome,descricao,ativo,data_sync)
            VALUES (%s,%s,%s,%s,NOW()) ON CONFLICT (projeto_id) DO UPDATE SET nome=EXCLUDED.nome,ativo=EXCLUDED.ativo,data_sync=NOW()""",
            (int(p["id"]), p.get("name",""), p.get("description",""), p.get("is_active")=="1"))

        columns = api_call("getColumns", project_id=int(p["id"])) or []
        for col in columns:
            cur.execute("""INSERT INTO bi_kanboard.dim_colunas (coluna_id,projeto_id,nome,posicao,data_sync)
                VALUES (%s,%s,%s,%s,NOW()) ON CONFLICT (coluna_id) DO UPDATE SET nome=EXCLUDED.nome,posicao=EXCLUDED.posicao,data_sync=NOW()""",
                (int(col["id"]), int(p["id"]), col.get("title",""), int(col.get("position",0))))

        tasks = api_call("getAllTasks", project_id=int(p["id"])) or []
        for t in tasks:
            dc = ts(t.get("date_creation"))
            df = ts(t.get("date_completed"))
            sla = ts(t.get("date_due"))
            lt = round((df - dc).total_seconds()/86400, 2) if dc and df else None
            ag = int((now - dc).total_seconds()/86400) if dc else None
            st = t.get("column_name","")
            ativa = st not in ("Concluído","Cancelado","")
            sla_ok = None
            if sla and df: sla_ok = df <= sla
            elif sla and ativa and now.timestamp() > int(t.get("date_due",0)): sla_ok = False

            cur.execute("""INSERT INTO bi_kanboard.fato_tarefas
                (tarefa_id,projeto_id,coluna_id,responsavel_id,criador_id,titulo,prioridade,cor,swimlane,categoria,
                 data_criacao,data_inicio,data_fim_planejada,data_fim_real,prazo_sla,sla_cumprido,lead_time_dias,aging_dias,status_atual,is_ativa,data_sync)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
                ON CONFLICT (tarefa_id) DO UPDATE SET coluna_id=EXCLUDED.coluna_id,responsavel_id=EXCLUDED.responsavel_id,
                prioridade=EXCLUDED.prioridade,sla_cumprido=EXCLUDED.sla_cumprido,lead_time_dias=EXCLUDED.lead_time_dias,
                aging_dias=EXCLUDED.aging_dias,status_atual=EXCLUDED.status_atual,is_ativa=EXCLUDED.is_ativa,data_sync=NOW()""",
                (int(t["id"]),int(p["id"]),int(t.get("column_id",0)) or None,int(t.get("owner_id",0)) or None,
                 int(t.get("creator_id",0)) or None,t.get("title",""),t.get("priority","0"),t.get("color_id",""),
                 t.get("swimlane_name",""),t.get("category_name",""),dc,ts(t.get("date_started")),
                 sla,df,sla,sla_ok,lt,ag if ativa else None,st,ativa))

    users = api_call("getAllUsers") or []
    for u in users:
        cur.execute("""INSERT INTO bi_kanboard.dim_usuarios (usuario_id,nome,username,ativo,data_sync)
            VALUES (%s,%s,%s,%s,NOW()) ON CONFLICT (usuario_id) DO UPDATE SET nome=EXCLUDED.nome,ativo=EXCLUDED.ativo,data_sync=NOW()""",
            (int(u["id"]), u.get("name",u.get("username","")), u.get("username",""), u.get("is_active")=="1"))

    conn.commit()
    cur.close()
    conn.close()
    log.info("ETL concluído!")

if __name__ == "__main__":
    main()
