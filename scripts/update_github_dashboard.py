import requests
import json
import os
import subprocess
import re

# Configurações Kanboard
BASE_URL = "http://kanboard.eblsolucoescorp.tec.br/jsonrpc.php"
AUTH = ("admin", "Senha@2026")
PROJECT_ID = 11

def call_api(method, params=None):
    payload = {"jsonrpc": "2.0", "method": method, "id": 1, "params": params or {}}
    response = requests.post(BASE_URL, json=payload, auth=AUTH)
    response.raise_for_status() # Levanta um erro para códigos de status HTTP ruins
    return response.json().get("result")

def map_status_id_to_status_text(status_id):
    return "Implementado" if status_id == 1 else "Aberta"

def map_priority_to_priority_text(priority_id):
    if priority_id == 3: return "Alta"
    if priority_id == 2: return "Média"
    if priority_id == 1: return "Baixa"
    return "N/A"

def extract_data_from_description(description):
    data = {
        "area": "N/A",
        "valor": 0,
        "horas": 0,
        "seq": "N/A",
        "cherwell": "N/A",
        "rdm": "N/A",
        "titulo": "N/A",
        "golive": "N/A",
        "aprovado": "N/A",
        "aprovado_por": "N/A",
        "requisitante": "N/A",
        "tipo": "N/A",
        "previsao": "N/A",
        "obs": "N/A",
        "valtech": "N/A"
    }
    
    # Limpar a descrição de formatação Markdown como ** antes de aplicar os regex
    clean_description = re.sub(r'\*\*', '', description)

    # Regex para extrair os campos
    patterns = {
        "seq": r"Seq:\s*(\S+)",
        "cherwell": r"ID Cherwell:\s*#?(\S+)",
        "rdm": r"ID RDM:\s*#?(\S+)",
        "titulo": r"Tópico:\s*(.+?)(?:\n|$)",
        "fase": r"Fase:\s*(.+?)(?:\n|$)",
        "resp": r"Responsável:\s*(.+?)(?:\n|$)",
        "area": r"Área Solicitante:\s*(.+?)(?:\n|$)",
        "tipo": r"Tipo:\s*(.+?)(?:\n|$)",
        "pri": r"Prioridade:\s*(.+?)(?:\n|$)",
        "golive": r"Go Live:\s*(\d{2}/\d{2}/\d{4})",
        "previsao": r"Previsão:\s*(\d{2}/\d{2}/\d{4})",
        "obs": r"Observação:\s*(.+?)(?:\n|$)",
        "valor": r"Valor:\s*R\$\s*([\d\.,]+)",
        "horas": r"Horas Valtech:\s*([\d\.,]+)h",
        "aprovado": r"Status Aprovação:\s*(Sim|Não)",
        "aprovado_por": r"Aprovado por:\s*(.+?)(?:\n|$)",
        "requisitante": r"Requisitante:\s*(.+?)(?:\n|$)",
        "valtech": r"ID Valtech:\s*(\S+)"
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, clean_description, re.IGNORECASE | re.MULTILINE)
        if match:
            value = match.group(1).strip()
            if key == "valor":
                try:
                    data[key] = float(value.replace(".", "").replace(",", "."))
                except ValueError:
                    data[key] = 0
            elif key == "horas":
                try:
                    data[key] = float(value.replace(",", "."))
                except ValueError:
                    data[key] = 0
            else:
                data[key] = value
    
    return data

# 1. Obter dados frescos do Kanboard
tasks_raw = call_api("getAllTasks", {"project_id": PROJECT_ID})

if not tasks_raw:
    print("Erro ao obter tarefas do Kanboard.")
    exit()

# Obter colunas (fases) e usuários para mapeamento
columns = call_api("getColumns", {"project_id": PROJECT_ID})
column_mapping = {col["id"]: col["title"] for col in columns}

users = call_api("getAllUsers")
user_mapping = {user["id"]: user["name"] for user in users}

# Pré-processar as tarefas
tasks_processed = []
for task in tasks_raw:
    processed_task = {
        "id": task["id"],
        "title": task["title"],
        "description": task["description"],
        "date_creation": task["date_creation"],
        "date_completed": task["date_completed"],
        "date_due": task["date_due"],
        "date_modification": task["date_modification"],
        "url": task["url"],
        "status": map_status_id_to_status_text(task["is_active"]),
        "pri": map_priority_to_priority_text(task["priority"]),
        "fase": column_mapping.get(task["column_id"], "N/A"),
        "resp": user_mapping.get(task["owner_id"], "N/A"),
        "color": task["color"]
    }
    
    extracted_data = extract_data_from_description(task["description"])
    processed_task.update(extracted_data)
    
    # Se o título foi extraído da descrição e é diferente do título original, usar o da descrição
    if processed_task["titulo"] != "N/A" and processed_task["titulo"] != task["title"]:
        processed_task["title"] = processed_task["titulo"]

    tasks_processed.append(processed_task)

# 2. Gerar o arquivo data.js
new_data_json = json.dumps(tasks_processed, ensure_ascii=False, indent=2)
data_js_content = f"window.DATA = {new_data_json};\n"

docs_path = "/home/ubuntu/kanboard/docs"
data_js_path = os.path.join(docs_path, "data.js")

with open(data_js_path, "w", encoding="utf-8") as f:
    f.write(data_js_content)

# 3. Ler e modificar o template do dashboard (index.html)
template_path = os.path.join(docs_path, "index.html")
with open(template_path, "r", encoding="utf-8") as f:
    html_content = f.read()

# Inserir a tag <script src="data.js"></script> e <script src="script.js"></script> no head
# A ordem é importante: data.js primeiro, depois script.js
script_includes = """<script src="data.js"></script>
<script src="script.js"></script>
"""

# Remover as tags de script existentes para evitar duplicação
html_content = re.sub(r'<script src="data.js"></script>\n', '', html_content)
html_content = re.sub(r'<script src="script.js"></script>\n', '', html_content)

head_end_tag = "</head>"
head_end_index = html_content.find(head_end_tag)
if head_end_index != -1:
    updated_html = html_content[:head_end_index] + script_includes + html_content[head_end_index:]
else:
    print("Erro: Não foi possível encontrar a tag </head> para inserir os scripts.")
    updated_html = html_content # Fallback para evitar erro

with open(template_path, "w", encoding="utf-8") as f:
    f.write(updated_html)

# 4. Push para o GitHub
os.chdir("/home/ubuntu/kanboard")
subprocess.run(["git", "add", "docs/index.html", "docs/data.js", "docs/script.js"])
subprocess.run(["git", "commit", "-m", "fix: Corrigida extração de dados e ordem de scripts."])
subprocess.run(["git", "push", "origin", "main"])

print("DASHBOARD_GITHUB_ATUALIZADO_SUCESSO")
