#!/usr/bin/env python3
"""
Corrige as 14 tarefas faltantes e ajusta colunas de todas as tarefas
"""

import requests
import openpyxl
import time
from datetime import datetime

BASE_URL = "http://kanboard.eblsolucoescorp.tec.br/jsonrpc.php"
AUTH = ("admin", "Senha@2026")
EXCEL_PATH = "/home/ubuntu/upload/Base_Fast_Tracking_Outubro.xlsx"
SF_PROJECT_ID = 11

# IDs reais das colunas (confirmados via API)
COL_IDS = {
    "01. Backlog":         165,
    "02. Refinamento":     166,
    "03. Priorizada":      167,
    "04. Análise":         168,
    "05. Estimativa":      169,
    "06. Aprovação":       170,
    "07. Desenvolvimento": 171,
    "08. Homologação":     172,
    "09. Deploy":          173,
    "10. Implementado":    174,
    "11. Cancelado":       175,
}

FASE_MAP = {
    "Implementado":            "10. Implementado",
    "Deploy":                  "09. Deploy",
    "Homogação":               "08. Homologação",
    "Homologação":             "08. Homologação",
    "Desenvolvimento":         "07. Desenvolvimento",
    "Aguardando Aprovação":    "06. Aprovação",
    "Aprovação":               "06. Aprovação",
    "Estimativa":              "05. Estimativa",
    "Análise":                 "04. Análise",
    "Priorizada":              "03. Priorizada",
    "Refinamento":             "02. Refinamento",
    "Backlog/Sem priorização": "01. Backlog",
    "Backlog":                 "01. Backlog",
    "Cancelado":               "11. Cancelado",
    "Cancelada":               "11. Cancelado",
}

TIPO_COLOR_MAP = {
    "Parametrização":          "yellow",
    "Produtividade Comercial": "blue",
    "Nova Funcionalidade":     "green",
    "Bug":                     "red",
    "Melhoria":                "teal",
    "Integração":              "purple",
    "Relatório":               "orange",
    "Suporte":                 "grey",
}

def api(method, params={}, retries=3):
    for i in range(retries):
        try:
            r = requests.post(BASE_URL, auth=AUTH,
                json={"jsonrpc":"2.0","method":method,"id":1,"params":params},
                timeout=20)
            result = r.json()
            if "result" in result:
                return result["result"]
        except Exception as e:
            if i < retries - 1:
                time.sleep(2)
    return None

def parse_date(val):
    if not val or str(val) in ["None", "N/A", ""]:
        return None
    try:
        date_str = str(val)[:10]
        for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"]:
            try:
                dt = datetime.strptime(date_str, fmt)
                return int(dt.timestamp())
            except:
                pass
    except:
        pass
    return None

def get_color(tipo):
    if not tipo:
        return "blue"
    for key, color in TIPO_COLOR_MAP.items():
        if key.lower() in str(tipo).lower():
            return color
    return "blue"

def get_priority(fase):
    if fase in ["Desenvolvimento", "Aguardando Aprovação", "Deploy", "Homogação", "Homologação"]:
        return 3
    elif fase in ["Refinamento", "Análise", "Estimativa", "Priorizada"]:
        return 2
    return 1

def main():
    print("=" * 60)
    print("🔧 CORREÇÃO DE IMPORTAÇÃO - EBL FAST TRACK SALESFORCE")
    print("=" * 60)

    me = api("getMe")
    if not me:
        print("❌ Falha na autenticação!")
        return
    print(f"✅ Conectado: {me['name']}")

    # Buscar swimlanes
    sws = api("getAllSwimlanes", {"project_id": SF_PROJECT_ID}) or []
    sw_map = {s["name"]: s["id"] for s in sws}
    print(f"🏊 Swimlanes: {list(sw_map.keys())}")

    # Buscar tarefas existentes para evitar duplicatas
    existing_tasks = api("getAllTasks", {"project_id": SF_PROJECT_ID, "status_id": 1}) or []
    existing_titles = set()
    for t in existing_tasks:
        # Extrair ID Cherwell do título
        title = t.get("title", "")
        import re
        match = re.search(r'\[(\d{5,6})\]', title)
        if match:
            existing_titles.add(match.group(1))

    print(f"📋 Tarefas existentes: {len(existing_tasks)} | IDs Cherwell: {len(existing_titles)}")

    # Ler Excel
    wb = openpyxl.load_workbook(EXCEL_PATH, data_only=True)
    ws = wb["Status Report"]

    tasks_excel = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not any(v for v in row if v is not None):
            continue

        def g(idx):
            if idx < len(row) and row[idx] is not None:
                return str(row[idx]).strip()
            return ""

        topico = g(4)
        if not topico or topico == "None":
            continue

        tasks_excel.append({
            "seq": g(0),
            "cherwell_id": g(2),
            "topico": topico,
            "fase": g(5),
            "go_live": row[3] if 3 < len(row) else None,
            "obs": g(7),
            "area": g(8),
            "responsavel": g(9),
            "requisitante": g(10),
            "rdm": g(11),
            "desenvolvimento": g(12),
            "valtech_id": g(13),
            "horas_valtech": g(14),
            "horas_elgin": g(15),
            "valor": g(16),
            "tipo": g(17),
            "aprovado": g(18),
            "aprovado_por": g(20),
        })

    print(f"📊 {len(tasks_excel)} demandas no Excel")

    # Identificar as faltantes
    missing = []
    for task in tasks_excel:
        cid = task["cherwell_id"]
        if cid and cid not in existing_titles:
            missing.append(task)

    print(f"🔍 {len(missing)} demandas faltantes para importar")

    # Importar faltantes
    imported = 0
    errors = 0

    for i, task in enumerate(missing, 1):
        fase = task["fase"]
        col_name = FASE_MAP.get(fase, "01. Backlog")
        col_id = COL_IDS.get(col_name, COL_IDS["01. Backlog"])

        resp = task["responsavel"]
        sw_id = 0
        for sw_name, sw_id_val in sw_map.items():
            if resp and resp in sw_name:
                sw_id = sw_id_val
                break
        if not sw_id:
            priority_int = get_priority(fase)
            if priority_int == 3:
                sw_id = sw_map.get("🔴 Alta Prioridade", 0)
            elif priority_int == 2:
                sw_id = sw_map.get("🟡 Média Prioridade", 0)
            else:
                sw_id = sw_map.get("📋 Backlog Geral", 0)

        # Construir título
        title_parts = []
        if task["cherwell_id"] not in ["None", ""]:
            title_parts.append(f"[{task['cherwell_id']}]")
        if task["rdm"] not in ["None", ""]:
            title_parts.append(f"[RDM-{task['rdm']}]")
        title_parts.append(task["topico"])
        title = " ".join(title_parts)[:200]

        # Construir descrição
        desc_lines = []
        if task["obs"] not in ["None", ""]:
            desc_lines.append(f"**📝 Observação:** {task['obs']}")
        desc_lines.append("\n---\n### 📋 Detalhes da Demanda\n")
        if task["area"]: desc_lines.append(f"**🏢 Área Solicitante:** {task['area']}")
        if task["requisitante"]: desc_lines.append(f"**👤 Requisitante:** {task['requisitante']}")
        if task["responsavel"]: desc_lines.append(f"**🎯 Responsável:** {task['responsavel']}")
        if task["tipo"]: desc_lines.append(f"**📌 Tipo:** {task['tipo']}")
        if task["desenvolvimento"]: desc_lines.append(f"**⚙️ Desenvolvimento:** {task['desenvolvimento']}")
        desc_lines.append("\n### 💰 Financeiro & Estimativas\n")
        if task["horas_valtech"] not in ["None", ""]: desc_lines.append(f"**⏱️ Horas Valtech:** {task['horas_valtech']}h")
        if task["horas_elgin"] not in ["None", ""]: desc_lines.append(f"**⏱️ Horas Elgin:** {task['horas_elgin']}h")
        if task["valor"] not in ["None", ""]:
            try:
                v = f"R$ {float(task['valor']):,.2f}".replace(",","X").replace(".",",").replace("X",".")
                desc_lines.append(f"**💵 Valor:** {v}")
            except:
                desc_lines.append(f"**💵 Valor:** {task['valor']}")
        desc_lines.append("\n### ✅ Aprovação\n")
        if task["aprovado"] not in ["None", ""]: desc_lines.append(f"**Status Aprovação:** {task['aprovado']}")
        if task["aprovado_por"] not in ["None", ""]: desc_lines.append(f"**Aprovado por:** {task['aprovado_por']}")
        desc_lines.append("\n### 🔗 Referências\n")
        if task["cherwell_id"] not in ["None", ""]: desc_lines.append(f"**ID Cherwell:** #{task['cherwell_id']}")
        if task["valtech_id"] not in ["None", ""]: desc_lines.append(f"**ID Valtech:** {task['valtech_id']}")
        if task["rdm"] not in ["None", ""]: desc_lines.append(f"**N° RDM:** {task['rdm']}")

        task_params = {
            "project_id": SF_PROJECT_ID,
            "title": title,
            "column_id": col_id,
            "color_id": get_color(task["tipo"]),
            "priority": get_priority(fase),
            "description": "\n".join(desc_lines),
        }
        if sw_id:
            task_params["swimlane_id"] = sw_id
        due_ts = parse_date(task["go_live"])
        if due_ts:
            task_params["date_due"] = due_ts

        result = api("createTask", task_params)
        if result and result != 0:
            imported += 1
            print(f"  ✅ [{i}] {title[:70]}")
        else:
            errors += 1
            print(f"  ❌ [{i}] ERRO: {title[:70]}")

        time.sleep(0.3)

    print(f"\n✅ Faltantes importadas: {imported} | Erros: {errors}")

    # Agora corrigir colunas das tarefas existentes
    print(f"\n🔧 Corrigindo colunas das tarefas existentes...")

    # Recarregar todas as tarefas
    all_tasks = api("getAllTasks", {"project_id": SF_PROJECT_ID, "status_id": 1}) or []
    print(f"  Total de tarefas abertas: {len(all_tasks)}")

    # Construir mapa de cherwell_id -> fase do Excel
    excel_fase_map = {}
    for task in tasks_excel:
        if task["cherwell_id"] and task["cherwell_id"] not in ["None", ""]:
            excel_fase_map[task["cherwell_id"]] = task["fase"]

    moved = 0
    closed = 0
    import re

    for t in all_tasks:
        title = t.get("title", "")
        match = re.search(r'\[(\d{5,6})\]', title)
        if not match:
            continue

        cherwell_id = match.group(1)
        fase = excel_fase_map.get(cherwell_id)
        if not fase:
            continue

        col_name = FASE_MAP.get(fase, "01. Backlog")
        correct_col_id = COL_IDS.get(col_name, COL_IDS["01. Backlog"])
        current_col_id = t.get("column_id")

        # Mover para coluna correta se necessário
        if current_col_id != correct_col_id:
            result = api("moveTaskPosition", {
                "project_id": SF_PROJECT_ID,
                "task_id": t["id"],
                "column_id": correct_col_id,
                "position": 1,
                "swimlane_id": t.get("swimlane_id", 0)
            })
            if result:
                moved += 1

        # Fechar tarefas implementadas/canceladas
        if fase in ["Implementado", "Cancelado", "Cancelada"]:
            api("closeTask", {"task_id": t["id"]})
            closed += 1

    print(f"  📦 Tarefas movidas para coluna correta: {moved}")
    print(f"  ✅ Tarefas fechadas (Implementado/Cancelado): {closed}")

    # Verificação final
    time.sleep(2)
    open_tasks = api("getAllTasks", {"project_id": SF_PROJECT_ID, "status_id": 1}) or []
    closed_tasks = api("getAllTasks", {"project_id": SF_PROJECT_ID, "status_id": 0}) or []
    total = len(open_tasks) + len(closed_tasks)

    print(f"\n{'='*60}")
    print(f"📊 RESULTADO FINAL:")
    print(f"  Tarefas abertas: {len(open_tasks)}")
    print(f"  Tarefas fechadas: {len(closed_tasks)}")
    print(f"  TOTAL: {total} / 105 esperadas")

    # Distribuição por coluna
    col_count = {}
    for t in open_tasks:
        for cname, cid in COL_IDS.items():
            if cid == t.get("column_id"):
                col_count[cname] = col_count.get(cname, 0) + 1
                break

    print(f"\n  📊 Distribuição por fase (abertas):")
    for col, count in sorted(col_count.items()):
        bar = "█" * min(count, 40)
        print(f"    {col:30s} | {bar} {count}")

    print(f"\n🎉 PRONTO! Acesse: http://kanboard.eblsolucoescorp.tec.br/project/11/board")

if __name__ == "__main__":
    main()
