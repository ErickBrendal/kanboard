#!/usr/bin/env python3
import requests, sys, os

# Configurações via variáveis de ambiente ou editáveis
KANBOARD_URL = os.getenv("KANBOARD_URL", "https://kanboard.eblsolucoescorp.tec.br/jsonrpc.php")
API_USER = "admin"
API_TOKEN = os.getenv("KANBOARD_API_TOKEN", "COLE_TOKEN_API_AQUI")

COLUNAS = [
    "01. Entrada", "02. Backlog", "03. Priorizada", "04. Em Análise",
    "05. Em Estimativa", "06. Em Aprovação", "07. Em Desenvolvimento",
    "08. Em Homologação", "09. Em Implementação", "10. Hypercare",
    "11. Concluído", "12. Cancelado",
]

BOARDS = [
    {"nome": "[TI] Demandas de Tecnologia", "desc": "Infraestrutura, sistemas, suporte e desenvolvimento"},
    {"nome": "[MKT] Demandas de Marketing", "desc": "Campanhas, materiais, eventos, digital"},
    {"nome": "[COM] Demandas Comercial", "desc": "Propostas, CRM, vendas, pipeline"},
    {"nome": "[FIN] Demandas Financeiro", "desc": "Contas, orçamentos, compliance, auditorias"},
    {"nome": "[PRJ] Projetos Internos", "desc": "Iniciativas estratégicas cross-area"},
]

SWIMLANES = ["Urgente / Fast Track", "Normal", "Melhoria Contínua", "Bloqueado"]

CATEGORIAS = [
    "Bug / Incidente", "Nova Funcionalidade", "Melhoria", "Suporte",
    "Infraestrutura", "Compliance / Auditoria", "Projeto Estratégico",
]

_id = 0
def api(method, **params):
    global _id; _id += 1
    r = requests.post(KANBOARD_URL, json={"jsonrpc":"2.0","method":method,"id":_id,"params":params},
                       auth=(API_USER, API_TOKEN), timeout=30)
    data = r.json()
    if "error" in data and data["error"]: print(f"  ERRO [{method}]: {data['error']}"); return None
    return data.get("result")

def main():
    print("=== KANBOARD EBL - Setup ===")
    v = api("getVersion")
    if v: print(f"Conectado! Versão: {v}")
    else: print("Falha na conexão"); sys.exit(1)

    for b in BOARDS:
        pid = api("createProject", name=b["nome"], description=b["desc"])
        if not pid:
            for p in (api("getAllProjects") or []):
                if p["name"] == b["nome"]: pid = int(p["id"]); break
        if not pid: continue
        print(f"\nBoard: {b['nome']} (ID: {pid})")

        # Remover colunas padrão
        for col in (api("getColumns", project_id=pid) or []):
            api("removeColumn", column_id=int(col["id"]))

        # Criar colunas do workflow
        for c in COLUNAS:
            api("addColumn", project_id=pid, title=c)
            print(f"  Coluna: {c}")

        # Swimlanes
        for sl in (api("getAllSwimlanes", project_id=pid) or []):
            if sl.get("is_default") or sl.get("name") == "Default swimlane":
                api("updateSwimlane", swimlane_id=int(sl["id"]), name="Normal")
        for sl in SWIMLANES:
            if sl != "Normal":
                api("addSwimlane", project_id=pid, name=sl)
                print(f"  Swimlane: {sl}")

        # Categorias
        for cat in CATEGORIAS:
            api("createCategory", project_id=pid, name=cat)
            print(f"  Categoria: {cat}")

    print("\n=== SETUP CONCLUÍDO! ===")

if __name__ == "__main__":
    main()
