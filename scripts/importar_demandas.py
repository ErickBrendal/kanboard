#!/usr/bin/env python3
"""
Importação definitiva das demandas do Excel para o Kanboard
Usa a aba 'Status Report' com 105 demandas reais
"""

import requests
import json
import openpyxl
import time
from datetime import datetime

BASE_URL = "http://kanboard.eblsolucoescorp.tec.br/jsonrpc.php"
AUTH = ("admin", "Senha@2026")
EXCEL_PATH = "/home/ubuntu/upload/Base_Fast_Tracking_Outubro.xlsx"
SF_PROJECT_ID = 11  # [SF] Fast Track — Salesforce

def api(method, params={}, retries=3):
    for i in range(retries):
        try:
            r = requests.post(BASE_URL, auth=AUTH,
                json={"jsonrpc":"2.0","method":method,"id":1,"params":params},
                timeout=20)
            result = r.json()
            if "result" in result:
                return result["result"]
            elif "error" in result:
                return None
        except Exception as e:
            if i < retries - 1:
                time.sleep(2)
    return None

# Mapeamento de fases do Excel para colunas do Kanboard
FASE_MAP = {
    "Implementado":           "10. Implementado",
    "Deploy":                 "09. Deploy",
    "Homogação":              "08. Homologação",
    "Homologação":            "08. Homologação",
    "Desenvolvimento":        "07. Desenvolvimento",
    "Aguardando Aprovação":   "06. Aprovação",
    "Aprovação":              "06. Aprovação",
    "Estimativa":             "05. Estimativa",
    "Análise":                "04. Análise",
    "Priorizada":             "03. Priorizada",
    "Refinamento":            "02. Refinamento",
    "Backlog/Sem priorização":"01. Backlog",
    "Backlog":                "01. Backlog",
    "Cancelado":              "11. Cancelado",
    "Cancelada":              "11. Cancelado",
}

# Mapeamento de responsável para swimlane
RESP_SWIMLANE_MAP = {
    "Erick Almeida":    "Erick Almeida",
    "Marcio Souza":     "Marcio Souza",
    "Elder Rodrigues":  "Elder Rodrigues",
    "Felipe Nascimento":"Felipe Nascimento",
    "Carlos Almeida":   "Carlos Almeida",
}

# Cores por tipo de demanda
TIPO_COLOR_MAP = {
    "Parametrização":           "yellow",
    "Produtividade Comercial":  "blue",
    "Nova Funcionalidade":      "green",
    "Bug":                      "red",
    "Melhoria":                 "teal",
    "Integração":               "purple",
    "Relatório":                "orange",
    "Suporte":                  "grey",
}

def get_columns():
    cols = api("getColumns", {"project_id": SF_PROJECT_ID}) or []
    return {c["title"]: c["id"] for c in cols}

def get_swimlanes():
    sws = api("getAllSwimlanes", {"project_id": SF_PROJECT_ID}) or []
    return {s["name"]: s["id"] for s in sws}

def get_categories():
    cats = api("getAllCategories", {"project_id": SF_PROJECT_ID}) or []
    return {c["name"]: c["id"] for c in cats}

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

def get_color_for_tipo(tipo):
    if not tipo:
        return "blue"
    for key, color in TIPO_COLOR_MAP.items():
        if key.lower() in str(tipo).lower():
            return color
    return "blue"

def get_priority_for_fase(fase):
    """Prioridade baseada na fase"""
    if fase in ["Desenvolvimento", "Aguardando Aprovação", "Deploy", "Homogação", "Homologação"]:
        return 3  # Alta
    elif fase in ["Refinamento", "Análise", "Estimativa", "Priorizada"]:
        return 2  # Média
    else:
        return 1  # Baixa

def main():
    print("=" * 60)
    print("📥 IMPORTAÇÃO DEFINITIVA - EBL FAST TRACK SALESFORCE")
    print("=" * 60)

    # Verificar conexão
    me = api("getMe")
    if not me:
        print("❌ Falha na autenticação!")
        return
    print(f"✅ Conectado: {me['name']}")

    # Carregar mapeamentos
    col_map = get_columns()
    sw_map = get_swimlanes()
    cat_map = get_categories()

    print(f"\n📋 Colunas: {list(col_map.keys())}")
    print(f"🏊 Swimlanes: {list(sw_map.keys())}")
    print(f"🏷️  Categorias: {list(cat_map.keys())}")

    # Ler Excel - aba Status Report
    wb = openpyxl.load_workbook(EXCEL_PATH, data_only=True)
    ws = wb["Status Report"]

    # Índices das colunas (baseado na análise)
    # [0] Sequencia, [1] Prioridade area, [2] ID Cherwell, [3] Go Live
    # [4] Tópico, [5] Fase Atual, [6] Previsão Etapa, [7] Obs
    # [8] Área Solicitante, [9] Responsavel, [10] Requisitante
    # [11] N°RDM, [12] Desenvolvimento, [13] N° Valtech
    # [14] Horas Valtech, [15] Horas Elgin, [16] Valor
    # [17] Tipo de Demanda, [18] Aprovado, [19] Data Aprovação, [20] Aprovado por

    tasks = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not any(v for v in row if v is not None):
            continue

        def g(idx):
            if idx < len(row) and row[idx] is not None:
                return str(row[idx]).strip()
            return ""

        seq = g(0)
        cherwell_id = g(2)
        topico = g(4)
        fase = g(5)
        go_live = row[3] if 3 < len(row) else None
        previsao = row[6] if 6 < len(row) else None
        obs = g(7)
        area = g(8)
        responsavel = g(9)
        requisitante = g(10)
        rdm = g(11)
        desenvolvimento = g(12)
        valtech_id = g(13)
        horas_valtech = g(14)
        horas_elgin = g(15)
        valor = g(16)
        tipo = g(17)
        aprovado = g(18)
        data_aprovacao = row[19] if 19 < len(row) else None
        aprovado_por = g(20)

        if not topico or topico == "None":
            continue

        tasks.append({
            "seq": seq,
            "cherwell_id": cherwell_id,
            "topico": topico,
            "fase": fase,
            "go_live": go_live,
            "previsao": previsao,
            "obs": obs,
            "area": area,
            "responsavel": responsavel,
            "requisitante": requisitante,
            "rdm": rdm,
            "desenvolvimento": desenvolvimento,
            "valtech_id": valtech_id,
            "horas_valtech": horas_valtech,
            "horas_elgin": horas_elgin,
            "valor": valor,
            "tipo": tipo,
            "aprovado": aprovado,
            "data_aprovacao": data_aprovacao,
            "aprovado_por": aprovado_por,
        })

    print(f"\n📊 {len(tasks)} demandas encontradas no Excel")

    # Importar tarefas
    imported = 0
    errors = 0
    error_list = []

    for i, task in enumerate(tasks, 1):
        # Determinar coluna
        fase = task["fase"]
        col_name = FASE_MAP.get(fase, "01. Backlog")
        col_id = col_map.get(col_name)
        if not col_id:
            col_id = list(col_map.values())[0]

        # Determinar swimlane (por responsável)
        resp = task["responsavel"]
        sw_id = 0
        for sw_name, sw_id_val in sw_map.items():
            if resp and resp in sw_name:
                sw_id = sw_id_val
                break
        if not sw_id:
            # Usar swimlane por prioridade
            priority_int = get_priority_for_fase(fase)
            if priority_int == 3:
                sw_id = sw_map.get("🔴 Alta Prioridade", 0)
            elif priority_int == 2:
                sw_id = sw_map.get("🟡 Média Prioridade", 0)
            else:
                sw_id = sw_map.get("📋 Backlog Geral", 0)

        # Determinar prioridade
        priority = get_priority_for_fase(fase)

        # Determinar cor
        color = get_color_for_tipo(task["tipo"])

        # Construir título
        title_parts = []
        if task["cherwell_id"] and task["cherwell_id"] not in ["None", ""]:
            title_parts.append(f"[{task['cherwell_id']}]")
        if task["rdm"] and task["rdm"] not in ["None", ""]:
            title_parts.append(f"[RDM-{task['rdm']}]")
        title_parts.append(task["topico"])
        title = " ".join(title_parts)[:200]

        # Construir descrição rica em Markdown
        desc_lines = []

        if task["obs"] and task["obs"] not in ["None", ""]:
            desc_lines.append(f"**📝 Observação:** {task['obs']}")

        desc_lines.append("")
        desc_lines.append("---")
        desc_lines.append("### 📋 Detalhes da Demanda")
        desc_lines.append("")

        if task["area"]:
            desc_lines.append(f"**🏢 Área Solicitante:** {task['area']}")
        if task["requisitante"]:
            desc_lines.append(f"**👤 Requisitante:** {task['requisitante']}")
        if task["responsavel"]:
            desc_lines.append(f"**🎯 Responsável:** {task['responsavel']}")
        if task["tipo"]:
            desc_lines.append(f"**📌 Tipo:** {task['tipo']}")
        if task["desenvolvimento"]:
            desc_lines.append(f"**⚙️ Desenvolvimento:** {task['desenvolvimento']}")

        desc_lines.append("")
        desc_lines.append("### 💰 Financeiro & Estimativas")
        desc_lines.append("")

        if task["horas_valtech"] and task["horas_valtech"] not in ["None", ""]:
            desc_lines.append(f"**⏱️ Horas Valtech:** {task['horas_valtech']}h")
        if task["horas_elgin"] and task["horas_elgin"] not in ["None", ""]:
            desc_lines.append(f"**⏱️ Horas Elgin:** {task['horas_elgin']}h")
        if task["valor"] and task["valor"] not in ["None", ""]:
            try:
                valor_fmt = f"R$ {float(task['valor']):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                desc_lines.append(f"**💵 Valor:** {valor_fmt}")
            except:
                desc_lines.append(f"**💵 Valor:** {task['valor']}")

        desc_lines.append("")
        desc_lines.append("### ✅ Aprovação")
        desc_lines.append("")

        if task["aprovado"] and task["aprovado"] not in ["None", ""]:
            desc_lines.append(f"**Status Aprovação:** {task['aprovado']}")
        if task["aprovado_por"] and task["aprovado_por"] not in ["None", ""]:
            desc_lines.append(f"**Aprovado por:** {task['aprovado_por']}")

        desc_lines.append("")
        desc_lines.append("### 🔗 Referências")
        desc_lines.append("")

        if task["cherwell_id"] and task["cherwell_id"] not in ["None", ""]:
            desc_lines.append(f"**ID Cherwell:** #{task['cherwell_id']}")
        if task["valtech_id"] and task["valtech_id"] not in ["None", ""]:
            desc_lines.append(f"**ID Valtech:** {task['valtech_id']}")
        if task["rdm"] and task["rdm"] not in ["None", ""]:
            desc_lines.append(f"**N° RDM:** {task['rdm']}")

        description = "\n".join(desc_lines)

        # Parâmetros da tarefa
        task_params = {
            "project_id": SF_PROJECT_ID,
            "title": title,
            "column_id": col_id,
            "color_id": color,
            "priority": priority,
            "description": description,
        }

        if sw_id:
            task_params["swimlane_id"] = sw_id

        # Data de vencimento (Go Live)
        due_ts = parse_date(task["go_live"])
        if due_ts:
            task_params["date_due"] = due_ts

        # Criar tarefa
        result = api("createTask", task_params)

        if result:
            imported += 1
            # Mover para coluna correta se necessário (status closed)
            if fase in ["Implementado", "Cancelado"]:
                api("closeTask", {"task_id": result})
        else:
            errors += 1
            error_list.append(f"  [{i}] {title[:60]}")

        if i % 10 == 0:
            print(f"  📌 {i}/{len(tasks)} | ✅ {imported} OK | ❌ {errors} erros")

        if i % 25 == 0:
            time.sleep(1)

    print(f"\n{'='*60}")
    print(f"✅ IMPORTAÇÃO CONCLUÍDA!")
    print(f"  📌 Importadas: {imported}")
    print(f"  ❌ Erros: {errors}")
    print(f"  📊 Total: {len(tasks)}")

    if error_list:
        print(f"\n  Erros detalhados:")
        for e in error_list[:10]:
            print(e)

    # Verificação final
    time.sleep(2)
    all_tasks = api("getAllTasks", {"project_id": SF_PROJECT_ID, "status_id": 1}) or []
    closed_tasks = api("getAllTasks", {"project_id": SF_PROJECT_ID, "status_id": 0}) or []
    print(f"\n📊 VERIFICAÇÃO FINAL:")
    print(f"  Tarefas abertas: {len(all_tasks)}")
    print(f"  Tarefas fechadas: {len(closed_tasks)}")
    print(f"  Total: {len(all_tasks) + len(closed_tasks)}")

    # Distribuição por coluna
    col_count = {}
    for t in all_tasks + closed_tasks:
        col_name = "?"
        for cname, cid in col_map.items():
            if cid == t.get("column_id"):
                col_name = cname
                break
        col_count[col_name] = col_count.get(col_name, 0) + 1

    print(f"\n  📊 Distribuição por fase:")
    for col, count in sorted(col_count.items()):
        bar = "█" * min(count, 40)
        print(f"    {col:30s} | {bar} {count}")

    # Distribuição por responsável (swimlane)
    sw_count = {}
    for t in all_tasks:
        sw_name = "?"
        for sname, sid in sw_map.items():
            if sid == t.get("swimlane_id"):
                sw_name = sname
                break
        sw_count[sw_name] = sw_count.get(sw_name, 0) + 1

    print(f"\n  👥 Distribuição por responsável:")
    for sw, count in sorted(sw_count.items(), key=lambda x: -x[1]):
        bar = "█" * min(count, 40)
        print(f"    {sw:30s} | {bar} {count}")

if __name__ == "__main__":
    main()
