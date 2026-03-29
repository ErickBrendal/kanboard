#!/usr/bin/env python3
"""
Setup Completo Kanboard EBL Soluções Corporativas
Configura: API Token, Admin, Boards, Colunas, Swimlanes, Categorias
"""
import requests
import sys
import os
import json
import secrets
import string

KANBOARD_URL = os.getenv("KANBOARD_URL", "http://kanboard.eblsolucoescorp.tec.br/jsonrpc.php")
API_USER = "admin"
API_PASS = os.getenv("KANBOARD_PASS", "admin")

COLUNAS = [
    "01. Entrada", "02. Backlog", "03. Priorizada", "04. Em Análise",
    "05. Em Estimativa", "06. Em Aprovação", "07. Em Desenvolvimento",
    "08. Em Homologação", "09. Em Implementação", "10. Hypercare",
    "11. Concluído", "12. Cancelado",
]

BOARDS = [
    {"nome": "[TI] Demandas de Tecnologia",   "desc": "Infraestrutura, sistemas, suporte e desenvolvimento"},
    {"nome": "[MKT] Demandas de Marketing",   "desc": "Campanhas, materiais, eventos, digital"},
    {"nome": "[COM] Demandas Comercial",       "desc": "Propostas, CRM, vendas, pipeline"},
    {"nome": "[FIN] Demandas Financeiro",      "desc": "Contas, orçamentos, compliance, auditorias"},
    {"nome": "[PRJ] Projetos Internos",        "desc": "Iniciativas estratégicas cross-area"},
]

SWIMLANES = ["Urgente / Fast Track", "Normal", "Melhoria Contínua", "Bloqueado"]
CATEGORIAS = [
    "Bug / Incidente", "Nova Funcionalidade", "Melhoria", "Suporte",
    "Infraestrutura", "Compliance / Auditoria", "Projeto Estratégico",
]

_id = 0

def api(method, **params):
    global _id
    _id += 1
    try:
        r = requests.post(
            KANBOARD_URL,
            json={"jsonrpc": "2.0", "method": method, "id": _id, "params": params},
            auth=(API_USER, API_PASS),
            timeout=30
        )
        data = r.json()
        if "error" in data and data["error"]:
            print(f"  ERRO [{method}]: {data['error']}")
            return None
        return data.get("result")
    except Exception as e:
        print(f"  EXCEÇÃO [{method}]: {e}")
        return None

def gerar_senha(tamanho=16):
    chars = string.ascii_letters + string.digits + "!@#$%"
    return ''.join(secrets.choice(chars) for _ in range(tamanho))

def main():
    print("=" * 60)
    print("  KANBOARD EBL - SETUP COMPLETO")
    print("=" * 60)

    # 1. Verificar conexão
    v = api("getVersion")
    if not v:
        print("FALHA: Não foi possível conectar ao Kanboard.")
        sys.exit(1)
    print(f"\n[OK] Conectado! Versão Kanboard: {v}")

    # 2. Gerar token de API para o admin
    print("\n[1/5] Gerando token de API...")
    token = api("createAPIAccessToken")
    if token:
        print(f"  Token gerado: {token}")
    else:
        # Tentar obter token existente
        me = api("getMe")
        token = me.get("api_access_token") if me else None
        if token:
            print(f"  Token existente: {token}")
        else:
            print("  Aviso: não foi possível gerar/obter token de API")
            token = "N/A"

    # 3. Atualizar admin com e-mail e senha segura
    print("\n[2/5] Configurando usuário admin...")
    nova_senha = gerar_senha(16)
    result = api("updateUser",
        id=1,
        name="Administrador EBL",
        email="ti@eblsolucoescorp.tec.br",
        password=nova_senha,
        role="app-admin"
    )
    if result:
        print(f"  Admin atualizado: nome='Administrador EBL', email='ti@eblsolucoescorp.tec.br'")
        print(f"  Nova senha admin: {nova_senha}")
    else:
        print("  Aviso: não foi possível atualizar o admin via API (pode precisar de senha atual)")
        nova_senha = "admin (não alterada)"

    # 4. Criar Boards
    print("\n[3/5] Criando Boards...")
    projetos_criados = {}
    for b in BOARDS:
        pid = api("createProject", name=b["nome"], description=b["desc"])
        if not pid:
            # Verificar se já existe
            projetos = api("getAllProjects") or []
            for p in projetos:
                if p["name"] == b["nome"]:
                    pid = int(p["id"])
                    print(f"  Board já existe: {b['nome']} (ID: {pid})")
                    break
        else:
            print(f"  Board criado: {b['nome']} (ID: {pid})")

        if not pid:
            print(f"  ERRO: Não foi possível criar/encontrar board: {b['nome']}")
            continue

        projetos_criados[b["nome"]] = pid

        # Remover colunas padrão
        colunas_atuais = api("getColumns", project_id=pid) or []
        for col in colunas_atuais:
            api("removeColumn", column_id=int(col["id"]))

        # Criar colunas do workflow
        for c in COLUNAS:
            api("addColumn", project_id=pid, title=c)
        print(f"    {len(COLUNAS)} colunas criadas")

        # Swimlanes
        swimlanes_atuais = api("getAllSwimlanes", project_id=pid) or []
        for sl in swimlanes_atuais:
            if sl.get("name") == "Default swimlane":
                api("updateSwimlane", swimlane_id=int(sl["id"]), name="Normal")

        for sl in SWIMLANES:
            if sl != "Normal":
                api("addSwimlane", project_id=pid, name=sl)
        print(f"    {len(SWIMLANES)} swimlanes configuradas")

        # Categorias
        for cat in CATEGORIAS:
            api("createCategory", project_id=pid, name=cat)
        print(f"    {len(CATEGORIAS)} categorias criadas")

    # 5. Resumo final
    print("\n[4/5] Configurando permissões de projetos...")
    for nome, pid in projetos_criados.items():
        # Tornar projetos ativos e com permissão pública interna
        api("updateProject", id=pid, is_active=1)
    print(f"  {len(projetos_criados)} projetos ativados")

    print("\n[5/5] Verificando configuração final...")
    projetos_final = api("getAllProjects") or []
    print(f"  Total de projetos: {len(projetos_final)}")

    # Salvar resultado
    resultado = {
        "url": "http://kanboard.eblsolucoescorp.tec.br",
        "url_https": "https://kanboard.eblsolucoescorp.tec.br",
        "usuario_admin": "admin",
        "senha_admin": nova_senha,
        "email_admin": "ti@eblsolucoescorp.tec.br",
        "api_token": token,
        "boards_criados": list(projetos_criados.keys()),
        "versao_kanboard": v
    }

    with open("/tmp/kanboard_resultado.json", "w") as f:
        json.dump(resultado, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print("  SETUP CONCLUÍDO!")
    print("=" * 60)
    print(f"  URL HTTP:    http://kanboard.eblsolucoescorp.tec.br")
    print(f"  URL HTTPS:   https://kanboard.eblsolucoescorp.tec.br (após SSL)")
    print(f"  Usuário:     admin")
    print(f"  Senha:       {nova_senha}")
    print(f"  API Token:   {token}")
    print(f"  Boards:      {len(projetos_criados)}")
    print("=" * 60)

    return resultado

if __name__ == "__main__":
    main()
